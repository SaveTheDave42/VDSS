import streamlit as st
import pandas as pd
import json
import requests
import os
from datetime import datetime, date, timedelta, time as dt_time
import time
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import numpy as np
import calendar # For week/weekday calculations
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Polygon as ShapelyPolygon, LineString
import hashlib
from utils.custom_styles import apply_chart_styling, apply_kpi_styles
from utils.map_utils import (
    update_map_view_to_project_bounds,
    create_geojson_feature,
    create_pydeck_geojson_layer,
    create_pydeck_path_layer,
    create_pydeck_access_route_layer,
)
from utils.dashoboard_utils import (
    parse_time_from_string,
    get_week_options,
    get_week_options_for_year,
    get_days_in_week,
    build_hourly_layer_cache,
)
from filelock import FileLock
import re
from config import API_URL  # Import centralized config


# API_URL is now imported from config.py

# Set this to True to see debug info
DEBUG_COORDS = False 
DEBUG_OSM = False    

# Define cache directory for OSM data
CACHE_DIR = "data/prepared/osm_cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Capacity mapping for OSM highway types
CAPACITY_MAP = {
    'motorway': 2000, 'trunk': 1800, 'primary': 1500,
    'secondary': 1000, 'tertiary': 700,
    'motorway_link': 1000, 'trunk_link': 900, 'primary_link': 750,
    'secondary_link': 500, 'tertiary_link': 350,
    'residential': 400, 'unclassified': 300, 'road': 300,
    'living_street': 100, 'service': 150, 'track': 50, 'path': 30,
    'cycleway': 50, 'footway': 20, 'pedestrian': 20, 'steps': 10
}
DEFAULT_CAPACITY = 200

# --- GLOBAL FEATURE FLAGS ---
# Disable/enable the dashboard hour animation. When set to False the play/pause
# button is removed and the dashboard will never trigger automatic reruns.
ENABLE_ANIMATION = True


def _render_traffic_tab(project):
    """Render the traffic dashboard tab content"""
    st.markdown("<h2 style='text-align: center;'>Verkehrs-Dashboard</h2>", unsafe_allow_html=True)
    
    # Session state checks and data loading
    if "selected_counters" not in st.session_state and "selected_counters" in project:
        # Parse counter coordinates from project which might be loaded from JSON
        if DEBUG_COORDS:
            st.write("DEBUG: Processing project selected_counters: ")
            st.write(f"  - Type: {type(project['selected_counters'])}")
            if len(project['selected_counters']) > 0:
                st.write(f"  - First item type: {type(project['selected_counters'][0])}")
                if 'coordinates' in project['selected_counters'][0]:
                    st.write(f"  - First coords type: {type(project['selected_counters'][0]['coordinates'])}")
                    st.write(f"  - First coords: {project['selected_counters'][0]['coordinates']}")
        
        # Make sure each counter has its coordinates properly parsed
        parsed_counters = []
        for counter in project["selected_counters"]:
            parsed_counter = counter.copy() if isinstance(counter, dict) else dict(counter)
            if 'coordinates' in parsed_counter:
                # Handle json-serialized coordinates that may have been loaded as strings
                if isinstance(parsed_counter['coordinates'], str):
                    try:
                        if parsed_counter['coordinates'].startswith('[') and parsed_counter['coordinates'].endswith(']'):
                            coords_str = parsed_counter['coordinates'].strip('[]')
                            lat, lon = map(float, coords_str.split(','))
                            parsed_counter['coordinates'] = [lat, lon]
                            if DEBUG_COORDS:
                                st.write(f"DEBUG: Parsed project coords for {parsed_counter.get('id')}: {parsed_counter['coordinates']}")
                    except Exception as e:
                        if DEBUG_COORDS:
                            st.write(f"DEBUG: Failed to parse coords: {e}")
            parsed_counters.append(parsed_counter)
        
        # Set the parsed counters in session state
        st.session_state.selected_counters = parsed_counters
        if DEBUG_COORDS:
            st.write("DEBUG: selected_counters loaded from project:")
            for i, counter in enumerate(st.session_state.selected_counters[:2]):  # Show first 2 only
                st.write(f"{i}: {counter.get('id')} - coords: {counter.get('coordinates')}")
    
    if "primary_counter" not in st.session_state and "primary_counter" in project:
        st.session_state.primary_counter = project["primary_counter"]
    
    if ("counter_profiles" not in st.session_state or not st.session_state.counter_profiles) and \
       ("selected_counters" in st.session_state and st.session_state.selected_counters):
        load_profiles_for_counters(project)
    
    if "counter_profiles" not in st.session_state or not st.session_state.counter_profiles:
        st.warning("Keine Verkehrszählstellen ausgewählt oder Profile konnten nicht geladen werden. Bitte gehen Sie zur Projekteinrichtung.")
        if st.button("Zur Projekteinrichtung"):
            st.session_state.page = "project_setup"
            st.rerun()
        return
    
    ensure_profile_coordinates()
    
    if DEBUG_COORDS:
        st.write("DEBUG: After ensure_profile_coordinates:")
        for i, (pid, profile) in enumerate(list(st.session_state.counter_profiles.items())[:2]):  # First 2
            st.write(f"{i}: {pid} - coords: {profile.get('coordinates')}")
    
    sanitize_counters(st.session_state.get("selected_counters", []))
    sanitize_counter(st.session_state.get("primary_counter", None))

    # Ensure project data is available
    if not project or "id" not in project:
        st.error("Projektdaten sind nicht korrekt geladen.")
        st.session_state.map_layers = [] # Clear map layers
        return

    # Get base OSM segments (cached or fetched)
    base_osm_segments = get_base_osm_segments(project)
    if not base_osm_segments and DEBUG_OSM: # Only show warning if in debug, otherwise it might be alarming
        st.warning("OSM: Keine OSM-Basissegmente konnten generiert werden. Karte zeigt möglicherweise keine Verkehrswege.")

    # Initialize animation state
    # Ensure animation is turned off when the feature flag is disabled
    if not ENABLE_ANIMATION:
        st.session_state.animation_running = False
    elif "animation_running" not in st.session_state:
        # Only initialise when animation is enabled and not yet set
        st.session_state.animation_running = False
    if "animation_current_hour" not in st.session_state:
        st.session_state.animation_current_hour = (project.get("delivery_hours", {}).get("start", "06:00"))

    # Center map view on project bounds
    view_key = f"dashboard_view_set_{project.get('id')}"
    if view_key not in st.session_state:
        # Use utility from map_utils.py
        if "map_bounds" in project:
            update_map_view_to_project_bounds(project.get("map_bounds"))
        st.session_state[view_key] = True

    # --- Unified Date Selector -------------------------------------------------
    # Determine selectable range from project start/end dates (if provided)
    min_date, max_date = date(2024, 9, 5), date(2026, 6, 30)
    if "dates" in project:
        if "start_date" in project["dates"]:
            min_date = datetime.fromisoformat(project["dates"]["start_date"]).date()
        if "end_date" in project["dates"]:
            max_date = datetime.fromisoformat(project["dates"]["end_date"]).date()

    selected_date_for_map = st.date_input(
        "Datum",
        value=date.today(),
        min_value=min_date,
        max_value=max_date,
        key="date_dashboard_ctrl",
    )

    # Ensure the chosen date is an allowed delivery day; otherwise, auto-adjust
    delivery_days_names = project.get("delivery_days", ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"])
    weekday_map_to_iso = {"Montag": 0, "Dienstag": 1, "Mittwoch": 2, "Donnerstag": 3, "Freitag": 4, "Samstag": 5, "Sonntag": 6}
    allowed_weekdays = [weekday_map_to_iso[d] for d in delivery_days_names if d in weekday_map_to_iso]

    if selected_date_for_map.weekday() not in allowed_weekdays:
        # Try to move to the next allowed weekday (forward, then backward)
        next_valid = None
        for offset in range(1, 7):
            cand = selected_date_for_map + timedelta(days=offset)
            if cand.weekday() in allowed_weekdays:
                next_valid = cand
                break
        if next_valid is None:
            for offset in range(1, 7):
                cand = selected_date_for_map - timedelta(days=offset)
                if cand.weekday() in allowed_weekdays:
                    next_valid = cand
                    break
        if next_valid:
            st.info(
                f"{selected_date_for_map.strftime('%A')} ist kein Liefertag. Stattdessen wird {next_valid.strftime('%A, %d.%m.%Y')} verwendet."
            )
            selected_date_for_map = next_valid

    # Re-create week context so downstream logic and caching stay unchanged
    week_year, week_num, _ = selected_date_for_map.isocalendar()
    start_of_week = date.fromisocalendar(week_year, week_num, 1)
    end_of_week = start_of_week + timedelta(days=6)

    selected_week_dict = {
        "year": week_year,
        "week": week_num,
        "start_date": start_of_week,
        "end_date": end_of_week,
        "label": f"KW {week_num} | {start_of_week.strftime('%d.%m')} - {end_of_week.strftime('%d.%m')}",
    }

    days_in_week = get_days_in_week(week_year, week_num, delivery_days_names)

    # --- Cache management when week/year changes ---
    current_week_key = f"current_dashboard_week_{project.get('id', 'default')}"
    selected_week_id = f"{selected_week_dict['year']}_{selected_week_dict['week']}"
    if st.session_state.get(current_week_key) != selected_week_id:
        st.session_state[current_week_key] = selected_week_id
        week_cache_key = (
            f"traffic_data_week_{selected_week_dict['year']}_{selected_week_dict['week']}_{project.get('id', 'default')}"
        )
        if week_cache_key in st.session_state:
            if DEBUG_OSM:
                st.write(f"OSM: Clearing old week cache {week_cache_key}")
            del st.session_state[week_cache_key]
        preload_traffic_data_for_week(selected_week_dict, project, base_osm_segments)

    delivery_hours = project.get("delivery_hours", {})
    start_hour_str = delivery_hours.get("start", "06:00")
    end_hour_str = delivery_hours.get("end", "18:00")
    start_hour = parse_time_from_string(start_hour_str, dt_time(6,0)).hour
    end_hour = parse_time_from_string(end_hour_str, dt_time(18,0)).hour

    # Initialize animation_current_hour if it's the first run or project changes, or date changes
    # This ensures the animation starts from the beginning of the selected day's range.
    if "last_selected_date_for_animation_init" not in st.session_state or \
        st.session_state.last_selected_date_for_animation_init != selected_date_for_map or \
        "animation_current_hour_value" not in st.session_state:
        st.session_state.animation_current_hour_value = start_hour
        st.session_state.last_selected_date_for_animation_init = selected_date_for_map

    # Advance animation one step (only relevant when ENABLE_ANIMATION is True)
    def animation_step():
        if ENABLE_ANIMATION and st.session_state.animation_running:
            current_val = st.session_state.animation_current_hour_value
            next_val = current_val + 1 if current_val < end_hour else start_hour
            st.session_state.animation_current_hour_value = next_val

    # Smooth hour selection slider bound directly to session state.
    selected_hour_for_map = st.slider(
        "Stunde",
        min_value=start_hour,
        max_value=end_hour,
        value=st.session_state.get("sel_hour", start_hour),
        step=1,
        format="%d:00",
        key="sel_hour",
    )

    selected_date_str_for_map = selected_date_for_map.strftime("%Y-%m-%d")

    st.markdown("<hr>", unsafe_allow_html=True)

    # Key Metrics - moved to after time selection to ensure proper spacing
    # Pass base_osm_segments to get_traffic_data
    current_traffic_data = get_traffic_data(selected_date_str_for_map, selected_hour_for_map, project, base_osm_segments)
    avg_cong_display = "N/A"
    if current_traffic_data and current_traffic_data["stats"]["average_congestion"] is not None:
        avg_cong = current_traffic_data['stats']['average_congestion']
        avg_cong_display = 'Low' if avg_cong < 0.3 else 'Medium' if avg_cong < 0.7 else 'High'
    
    # ---------------- Day Metrics -------------------------------------------------
    # Calculate daily aggregates once to avoid repeated API calls later
    total_deliveries_day = sum(
        get_traffic_data(selected_date_str_for_map, hr, project, base_osm_segments)["stats"]["deliveries_count"]
        for hr in range(start_hour, end_hour + 1)
    )
    total_traffic_day = sum(
        get_traffic_data(selected_date_str_for_map, hr, project, base_osm_segments)["stats"]["total_traffic"]
        for hr in range(start_hour, end_hour + 1)
    )
    avg_congestion_day = (
        sum(
            get_traffic_data(selected_date_str_for_map, hr, project, base_osm_segments)["stats"]["average_congestion"]
            for hr in range(start_hour, end_hour + 1)
        )
        / (end_hour - start_hour + 1)
    ) if end_hour >= start_hour else 0

    delivery_share_pct = (total_deliveries_day / total_traffic_day * 100 * 2) if total_traffic_day else 0

    # --- Access OSM segments (segments that overlap with the access route) ---
    access_osm_segments = _get_access_osm_segments(project, base_osm_segments)

    # Use access_osm_segments instead of base_osm_segments for access route calculations
    access_traffic_day = (
        sum(get_traffic_data(selected_date_str_for_map, hr, project, access_osm_segments)["stats"]["access_traffic"]
            for hr in range(start_hour, end_hour + 1)) / (end_hour - start_hour + 1)
    ) if access_osm_segments else 0

    construction_traffic_day = sum(
        get_traffic_data(selected_date_str_for_map, hr, project, base_osm_segments)["stats"]["construction_traffic"]
        for hr in range(start_hour, end_hour + 1)
    ) if base_osm_segments else 0

    construction_share_pct_day = (construction_traffic_day / access_traffic_day * 100) if access_traffic_day else 0

    # Apply KPI styles (reusable)
    apply_kpi_styles()

    # Render the three KPIs with tooltips
    kpi_html = f"""
    <div class="kpi-wrapper">
        <div class="kpi-card" data-tooltip="Gesamtanzahl der Lieferungen für den ausgewählten Tag basierend auf dem Bauzeitplan">
            <h4>Gesamtlieferungen (Tag)</h4><p>{total_deliveries_day}</p>
        </div>
        <div class="kpi-card" data-tooltip="Anteil der Lieferfahrzeuge am gesamten Verkehrsaufkommen in Prozent">
            <h4>Lieferungen % des Verkehrs</h4><p>{delivery_share_pct:.1f}%</p>
        </div>
        <div class="kpi-card" data-tooltip="Durchschnittliche Verkehrsbelastung (0=frei, 1=Stau) über alle Strassensegmente">
            <h4>Durchschn. Verkehrsbelastung</h4><p>{avg_congestion_day:.2f}</p>
        </div>
    </div>
    """

    st.markdown(kpi_html, unsafe_allow_html=True)

    # ---- NEW KPI card row with tooltips ----
    additional_kpi_html = f"""
    <div class="kpi-wrapper">
        <div class="kpi-card" data-tooltip="Verkehrsaufkommen auf den Zufahrtsstrassen zur Baustelle pro Tag">
            <h4>Zufahrtsverkehr (Tag)</h4><p>{access_traffic_day:.2f}</p>
        </div>
        <div class="kpi-card" data-tooltip="Anzahl der Baustellenfahrzeuge basierend auf Material-Lieferungen">
            <h4>Baustellenverkehr</h4><p>{construction_traffic_day}</p>
        </div>
        <div class="kpi-card" data-tooltip="Anteil des Baustellenverkehrs am gesamten Zufahrtsverkehr in Prozent">
            <h4>Baustellenanteil</h4><p>{construction_share_pct_day:.1f}%</p>
        </div>
    </div>
    
    <style>
    /* Tooltip Styles */
    .kpi-card {{
        position: relative;
        cursor: help;
    }}
    
    .kpi-card::after {{
        content: attr(data-tooltip);
        position: absolute;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 5, 160, 0.95);
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 12px;
        line-height: 1.3;
        white-space: nowrap;
        max-width: 250px;
        white-space: normal;
        text-align: center;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s, visibility 0.3s;
        z-index: 1000;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }}
    
    .kpi-card::before {{
        content: '';
        position: absolute;
        bottom: 118%;
        left: 50%;
        transform: translateX(-50%);
        border: 5px solid transparent;
        border-top-color: rgba(15, 5, 160, 0.95);
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s, visibility 0.3s;
        z-index: 1000;
    }}
    
    .kpi-card:hover::after,
    .kpi-card:hover::before {{
        opacity: 1;
        visibility: visible;
    }}
    </style>
    """
    st.markdown(additional_kpi_html, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    # Daily Traffic Volume (title removed)
    dates_ts = days_in_week if days_in_week else [selected_week_dict["start_date"] + timedelta(days=i) for i in range(7)]
    
    # German weekday mapping
    german_weekdays = {
        'Monday': 'Mo', 'Tuesday': 'Di', 'Wednesday': 'Mi', 
        'Thursday': 'Do', 'Friday': 'Fr', 'Saturday': 'Sa', 'Sunday': 'So'
    }
    
    daily_totals_ts = []
    if base_osm_segments: # Only calculate if we have segments
        daily_totals_ts = [
            sum(
                get_traffic_data(dt.strftime("%Y-%m-%d"), hr, project, base_osm_segments)["stats"]["total_traffic"]
                for hr in range(start_hour, end_hour + 1)
            ) for dt in dates_ts
        ]
    else: # Provide zeros or placeholder if no segments
        daily_totals_ts = [0] * len(dates_ts)

    # Create German formatted date labels
    x_labels = []
    for d in dates_ts:
        english_day = d.strftime("%A")
        german_day = german_weekdays.get(english_day, d.strftime("%a"))
        x_labels.append(f"{german_day}, {d.strftime('%d.%m')}")

    fig_daily = go.Figure(data=[go.Bar(x=x_labels, y=daily_totals_ts, name="Total Daily Traffic", marker_color="#0F05A0")])
    fig_daily.update_layout(
        xaxis_title=None,
        xaxis=dict(tickfont=dict(color='#0F05A0')),
        yaxis_title="Fahrzeuge insgesamt",
        yaxis=dict(tickfont=dict(color='#0F05A0'), titlefont=dict(color='#0F05A0')),
        margin=dict(l=10, r=10, t=30, b=10),
        height=220,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#0F05A0')
    )
    st.plotly_chart(fig_daily, use_container_width=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Hourly Analysis (title removed)
    hours_list_hr = [f"{h}:00" for h in range(start_hour, end_hour + 1)]
    
    hourly_traffic_hr = []
    hourly_congestion_hr = []
    hourly_deliveries_hr = []

    if base_osm_segments: # Only calculate if we have segments
        for h_loop in range(start_hour, end_hour + 1):
            hourly_data = get_traffic_data(selected_date_str_for_map, h_loop, project, base_osm_segments)
            hourly_traffic_hr.append(hourly_data["stats"]["total_traffic"])
            hourly_congestion_hr.append(hourly_data["stats"]["average_congestion"])
            hourly_deliveries_hr.append(hourly_data["stats"]["deliveries_count"])
    else: # Provide zeros or placeholder if no segments
        hourly_traffic_hr = [0] * len(hours_list_hr)
        hourly_congestion_hr = [0] * len(hours_list_hr)
        hourly_deliveries_hr = [0] * len(hours_list_hr)
    
    fig_hourly = go.Figure()
    fig_hourly.add_trace(go.Bar(x=hours_list_hr, y=hourly_traffic_hr, name="Verkehrsaufkommen", marker_color="#0F05A0", opacity=0.7))
    fig_hourly.add_trace(go.Scatter(x=hours_list_hr, y=hourly_congestion_hr, mode="lines+markers", name="Verkehrsbelastung", line=dict(color="#d62728"), yaxis="y2"))
    fig_hourly.add_trace(go.Scatter(x=hours_list_hr, y=hourly_deliveries_hr, mode="lines+markers", name="Lieferungen", line=dict(color="#2ca02c", dash="dot"), marker=dict(size=7), yaxis="y3"))
    fig_hourly.update_layout(
        xaxis=dict(title="Stunde des ausgewählten Tages"),
        yaxis=dict(title="Verkehrsaufkommen", titlefont=dict(color="#0F05A0"), tickfont=dict(color="#0F05A0"), side="left"),
        yaxis2=dict(title="Verkehrsbelastung", titlefont=dict(color="#d62728"), tickfont=dict(color="#d62728"), anchor="x", overlaying="y", side="right", range=[0, 1]),
        yaxis3=dict(title="Lieferungen", titlefont=dict(color="#2ca02c"), tickfont=dict(color="#2ca02c"), anchor="free", overlaying="y", side="right", position=0.85, showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5),
        margin=dict(l=10,r=10,t=50,b=10), 
        height=280,
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#0F05A0'
    )
    st.plotly_chart(fig_hourly, use_container_width=True)

    # --- Update PyDeck Map Layers ---
    layers_for_pydeck = []
    
    # 1. Project Polygon Layer
    project_polygon_data = project.get("polygon", {})
    if "coordinates" in project_polygon_data and project_polygon_data["coordinates"]:
        polygon_feature = create_geojson_feature(project_polygon_data, {"name": "Baustelle"})
        polygon_layer = create_pydeck_geojson_layer(
            data=[polygon_feature], 
            layer_id="dashboard_project_polygon", 
            fill_color=[70, 130, 180, 160], 
            line_color=[70, 130, 180, 160],
            get_line_width=20,
            line_width_min_pixels=2,
            pickable=True, 
            tooltip_html="<b>Baustelle</b><br/>{properties.name}"
        )
        layers_for_pydeck.append(polygon_layer)

    # 1b. Access Route Layer (violet, wider)
    if project.get("access_routes"):
        access_route_layer = create_pydeck_access_route_layer(
            project["access_routes"],
            layer_id="dashboard_access_route",
        )
        if access_route_layer:
            layers_for_pydeck.append(access_route_layer)

    # 2. Traffic Segments Layer (cached)
    # Build or retrieve cache for the selected date
    cache_key_hourly = f"hourly_layers_{selected_date_str_for_map}_{project.get('id')}"
    if cache_key_hourly not in st.session_state:
        st.session_state[cache_key_hourly] = build_hourly_layer_cache(
            start_hour,
            end_hour,
            project,
            base_osm_segments,
            selected_date_str_for_map,
            get_traffic_data,
        )

    segments_data = st.session_state[cache_key_hourly].get(selected_hour_for_map, [])

    if segments_data:
        traffic_layer = create_pydeck_path_layer(
            data=segments_data,
            layer_id="dashboard_traffic_paths",
            pickable=True,
            tooltip_html="<b>{name}</b><br/>Type: {highway_type}<br/>Volume: {traffic_volume}<br/>Congestion: {congestion:.2f}",
        )
        layers_for_pydeck.append(traffic_layer)

    # Update map layers in session state (replace completely)
    st.session_state.map_layers = layers_for_pydeck
    
    # Trigger animation loop only when feature flag is active
    if ENABLE_ANIMATION and st.session_state.get("animation_running", False):
        animation_step()
        time.sleep(0.5)
        st.rerun()

    # Additional CSS tweaks: smaller metric values
    st.markdown("""
    <style>
        /* Smaller metric value font */
        div[data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
        }

        /* Style selectboxes to resemble KPI cards */
        div[data-baseweb="select"] {
            background: #F4F6FF !important;
            padding: 6px 8px !important;
            border-radius: 8px !important;
            border: 1px solid #E1E4F2 !important;
        }
        /* Reduce label spacing */
        label[data-testid="stSelectboxLabel"] {
            margin-bottom: 2px !important;
        }

        /* --- Triple-select row (year / week / day) ---------------------------------- */
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            gap: 8px !important;
            flex-wrap: nowrap !important; /* prevent line-break */
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            flex: 0 0 33% !important;  /* fixed one-third */
            max-width: 33% !important;
        }
        /* ensure internal width 100% so select fills the card */
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div {
            width: 100% !important;
        }
        /* override BaseWeb select min-width so it can shrink */
        div[data-baseweb="select"] {
            min-width: 0 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # If needed by other pages, they can still access the cached hourly layer dict via the cache key.
    # We no longer push data for a custom JS component here to keep the original PyDeck map.

def sanitize_counter(counter):
    """Remove extra quotes from counter ID and direction"""
    if counter and 'id' in counter and isinstance(counter['id'], str):
        counter['id'] = counter['id'].strip('"\'')
    if counter and 'direction' in counter and isinstance(counter['direction'], str):
        counter['direction'] = counter['direction'].strip('"\'')
    if counter and 'name' in counter and isinstance(counter['name'], str):
        counter['name'] = counter['name'].strip('"\'')
    if counter and 'display_name' in counter and isinstance(counter['display_name'], str):
        counter['display_name'] = counter['display_name'].strip('"\'')
    # Parse coordinates if they're a string representation
    if counter and 'coordinates' in counter:
        if isinstance(counter['coordinates'], str):
            try:
                # Handle JSON string format "[lat,lon]"
                if counter['coordinates'].startswith('[') and counter['coordinates'].endswith(']'):
                    coords_str = counter['coordinates'].strip('[]')
                    lat, lon = map(float, coords_str.split(','))
                    counter['coordinates'] = [lat, lon]
                    if DEBUG_COORDS:
                        st.write(f"DEBUG: Parsed string coordinates: {counter['coordinates']}")
            except Exception as e:
                if DEBUG_COORDS:
                    st.write(f"DEBUG: Error parsing coordinates: {e}")
    return counter

def sanitize_counters(counters):
    """Remove extra quotes from a list of counters"""
    if not counters:
        return counters
    return [sanitize_counter(dict(counter)) for counter in counters]

def ensure_profile_coordinates():
    """Ensure all counter profiles have coordinates by copying from selected_counters if needed"""
    if "counter_profiles" not in st.session_state or "selected_counters" not in st.session_state:
        return
        
    sanitized_selected_counters = sanitize_counters(st.session_state.selected_counters)
    primary_counter_sanitized = sanitize_counter(dict(st.session_state.primary_counter)) if st.session_state.primary_counter else None

    if DEBUG_COORDS:
        st.sidebar.write("DEBUG (ensure_profile_coordinates): Starting coordinate check")

    counter_coords = {} # Stores as [lat,lon] from counters
    for counter in sanitized_selected_counters:
        if 'coordinates' in counter and counter['coordinates']: # Assuming [lat,lon]
            key = f"{counter['id']}_{counter['direction']}"
            counter_coords[key] = counter['coordinates']
            if DEBUG_COORDS:
                st.sidebar.write(f"DEBUG: Found coordinates for {key}: {counter_coords[key]}")
        else:
            if DEBUG_COORDS:
                st.sidebar.write(f"DEBUG: No coordinates for {counter['id']}_{counter['direction']}")
    
    for profile_id, profile in st.session_state.counter_profiles.items():
        if DEBUG_COORDS:
            st.sidebar.write(f"DEBUG: Checking profile {profile_id} - current coords: {profile.get('coordinates')}")
        if 'coordinates' not in profile or not profile['coordinates']:
            if profile_id in counter_coords:
                if DEBUG_COORDS:
                    st.sidebar.write(f"DEBUG: Setting coords from counter_coords: {counter_coords[profile_id]}")
                profile['coordinates'] = counter_coords[profile_id] # [lat,lon]
            elif primary_counter_sanitized and 'coordinates' in primary_counter_sanitized:
                if DEBUG_COORDS:
                    st.sidebar.write(f"DEBUG: Setting coords from primary: {primary_counter_sanitized['coordinates']}")
                profile['coordinates'] = primary_counter_sanitized['coordinates'] # [lat,lon]
            else:
                if DEBUG_COORDS:
                    st.sidebar.write(f"DEBUG: Setting default coords")
                profile['coordinates'] = [47.376888, 8.541694] # Default [lat,lon]

def load_counter_coordinates():
    """Load coordinates from counters.csv to be used as a canonical data source. Returns [lat,lon]."""
    coordinates_by_id = {}
    try:
        counters_file = "data/prepared/counters.csv"
        if os.path.exists(counters_file):
            df = pd.read_csv(counters_file)
            
            for _, row in df.iterrows():
                profile_id = row['profile_id']
                
                if 'lat' in df.columns and 'lon' in df.columns and not pd.isna(row['lat']) and not pd.isna(row['lon']):
                    coordinates_by_id[profile_id] = [float(row['lat']), float(row['lon'])]
                elif 'coordinates' in df.columns and not pd.isna(row['coordinates']):
                    coords_str = str(row['coordinates'])
                    if coords_str.startswith('[') and coords_str.endswith(']'):
                        coords_str = coords_str.strip('[]')
                        lat, lon = map(float, coords_str.split(','))
                        coordinates_by_id[profile_id] = [lat, lon]
                elif 'x_coord' in df.columns and 'y_coord' in df.columns: # Assuming these might be LV03 or similar, not directly usable for [lat,lon] easily
                    coordinates_by_id[profile_id] = [47.376888, 8.541694] # Default
            
        return coordinates_by_id
    except Exception as e:
        if DEBUG_COORDS:
            st.sidebar.write(f"DEBUG: Error loading counter coordinates: {str(e)}")
        return {}

def load_profiles_for_counters(project):
    """Load profiles for the selected counters from files. Coordinates are [lat,lon]."""
    if "selected_counters" not in st.session_state or not st.session_state.selected_counters:
        return
    
    st.session_state.counter_profiles = {}
    debug_mode = st.session_state.get('debug_mode', False)
    if DEBUG_COORDS or debug_mode:
        st.sidebar.write("DEBUG (load_profiles): Loading profiles...")

    counter_coordinates_map = load_counter_coordinates() # This loads [lat,lon]

    sanitized_selected_counters = sanitize_counters(st.session_state.selected_counters)
    primary_counter_sanitized = sanitize_counter(dict(st.session_state.primary_counter)) if st.session_state.primary_counter else None

    updated_counters_for_project = []
    coordinates_updated_in_project_counters = False
    
    for counter_in_project in sanitized_selected_counters:
        updated_counter_entry = counter_in_project.copy()
        profile_id_key = f"{counter_in_project['id']}_{counter_in_project['direction']}"
        
        if (not counter_in_project.get('coordinates')) and profile_id_key in counter_coordinates_map:
            updated_counter_entry['coordinates'] = counter_coordinates_map[profile_id_key] # [lat,lon]
            coordinates_updated_in_project_counters = True
            
        updated_counters_for_project.append(updated_counter_entry)
    
    if coordinates_updated_in_project_counters:
        st.session_state.selected_counters = updated_counters_for_project
        if "current_project" in st.session_state and st.session_state.current_project and \
           "selected_counters" in st.session_state.current_project:
            st.session_state.current_project["selected_counters"] = updated_counters_for_project

    for selected_counter_data in st.session_state.selected_counters: # Use the potentially updated list
        station_id = selected_counter_data['id']
        direction = selected_counter_data['direction']
        is_primary = False
        if primary_counter_sanitized:
            is_primary = (station_id == primary_counter_sanitized['id'] and direction == primary_counter_sanitized['direction'])
        
        profile_id_key = f"{station_id}_{direction}"
        profile_file_path = f"data/prepared/profiles/{profile_id_key}.csv"
        
        if os.path.exists(profile_file_path):
            profile_data_df = pd.read_csv(profile_file_path)
            
            # Use coordinates from the selected_counter_data (which might have been enriched from counters.csv)
            # If still not present, fallback to default.
            current_counter_coords = selected_counter_data.get('coordinates', counter_coordinates_map.get(profile_id_key, [47.376888, 8.541694]))
            
            st.session_state.counter_profiles[profile_id_key] = {
                'id': station_id,
                'direction': direction,
                'name': selected_counter_data.get('name', ''),
                'display_name': selected_counter_data.get('display_name', ''),
                'is_primary': is_primary,
                'coordinates': current_counter_coords, # This is [lat,lon]
                'data': profile_data_df
            }
            if DEBUG_COORDS or debug_mode:
                st.sidebar.write(f"DEBUG: Loaded {profile_id_key} - stored coords: {st.session_state.counter_profiles[profile_id_key].get('coordinates')}")
        else:
            st.warning(f"Profile file not found: {profile_file_path}")

    if st.session_state.counter_profiles:
        st.session_state.global_counter_profiles = st.session_state.counter_profiles # Unsure if this global one is still needed
        if DEBUG_COORDS or debug_mode:
            st.sidebar.write(f"DEBUG: Successfully loaded {len(st.session_state.counter_profiles)} profiles.")
    elif debug_mode:
        st.write("DEBUG (load_profiles): No profiles were loaded.")


def get_base_osm_segments(project):
    """Returns base_osm_segments. Segments have 'coordinates' as list of [lon, lat] tuples."""
    if "base_osm_segments" not in st.session_state or \
       st.session_state.get("current_project_id_for_osm", None) != project.get("id"):
        
        map_bounds = project.get("map_bounds") # Expected GeoJSON format (lon,lat)
        project_id = project.get("id", "default_project") 

        if DEBUG_OSM:
            st.sidebar.info(f"OSM: Generating base OSM segments for project: {project_id}")
            if not map_bounds or 'coordinates' not in map_bounds or not map_bounds['coordinates']:
                 st.sidebar.warning("OSM: Project map_bounds are missing or invalid for get_base_osm_segments.")
            else:
                 st.sidebar.write(f"OSM: Map bounds for {project_id}: {map_bounds['coordinates'][0][:2]}...") 

        st.session_state.base_osm_segments = generate_osm_traffic_segments(map_bounds, project_id)
        st.session_state.current_project_id_for_osm = project_id
        if DEBUG_OSM:
            st.sidebar.info(f"OSM: Stored {len(st.session_state.base_osm_segments)} base segments in session state.")
    return st.session_state.base_osm_segments

def generate_osm_traffic_segments(project_map_bounds, project_id):
    """
    Fetches road network data from OpenStreetMap within the given map_bounds,
    processes it into traffic segments with estimated capacities, and caches the result.
    Coordinates are returned as [[lon, lat], [lon, lat], ...].
    """
    if not project_map_bounds or 'coordinates' not in project_map_bounds or not project_map_bounds['coordinates']:
        if DEBUG_OSM: st.sidebar.warning("OSM: Project map bounds are missing or invalid.")
        return []

    bounds_coords_str = json.dumps(project_map_bounds['coordinates'][0], sort_keys=True)
    cache_key_input = f"{project_id}_{bounds_coords_str}"
    cache_filename_base = hashlib.md5(cache_key_input.encode()).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"osm_segments_{cache_filename_base}.gpkg")
    lock = FileLock(cache_file + ".lock")

    with lock:
        if os.path.exists(cache_file):
            if DEBUG_OSM: st.sidebar.info(f"OSM: Loading cached road segments from {cache_file}")
            try:
                segments_gdf = gpd.read_file(cache_file)
                if segments_gdf.empty:
                    if DEBUG_OSM: st.sidebar.warning(f"OSM: Cache file {cache_file} is empty. Refetching.")
                    os.remove(cache_file) 
                else:
                    processed_segments = []
                    for idx, row in segments_gdf.iterrows(): 
                        coords_lon_lat = list(row.geometry.coords) if row.geometry and row.geometry.geom_type == 'LineString' else (list(row.geometry.geoms[0].coords) if row.geometry and row.geometry.geom_type == 'MultiLineString' and len(row.geometry.geoms) > 0 else [])
                        highway_type = row.get('highway', 'unknown')
                        highway_type = highway_type[0] if isinstance(highway_type, list) and highway_type else highway_type
                        processed_segments.append({
                            'segment_id': str(row.get('osmid', f"cached_seg_{idx}")),
                            'coordinates': coords_lon_lat,
                            'name': str(row.get('name', '')),
                            'highway_type': highway_type,
                            'length': float(row.get('length', 0.0)),
                            'capacity': int(row.get('capacity', DEFAULT_CAPACITY))
                        })
                    if DEBUG_OSM: st.sidebar.info(f"OSM: Loaded {len(processed_segments)} segments from cache.")
                    return processed_segments
            except Exception as e:
                if DEBUG_OSM: st.sidebar.error(f"OSM: Error loading GDF cache: {e}. Refetching.")
                if os.path.exists(cache_file):
                    try: os.remove(cache_file); 
                    except: pass
    if DEBUG_OSM: st.sidebar.info("OSM: No valid cache. Fetching network...")
    try:
        shapely_poly_coords = project_map_bounds['coordinates'][0]
        if not shapely_poly_coords or len(shapely_poly_coords) < 3: return []
        map_boundary_polygon_shapely = ShapelyPolygon(shapely_poly_coords)
        try:
            poly_gdf = gpd.GeoDataFrame([{'id':1, 'geometry': map_boundary_polygon_shapely}], crs="EPSG:4326")
            G = ox.graph_from_polygon(poly_gdf.iloc[0]['geometry'], network_type='drive_service', truncate_by_edge=True, retain_all=False, simplify=True)
            if G.number_of_edges() == 0: raise ValueError("No roads from graph_from_polygon")
            G_proj = ox.project_graph(G)
            segments_gdf_proj = ox.graph_to_gdfs(G_proj, nodes=False, edges=True, fill_edge_geometry=True)
            segments_gdf = segments_gdf_proj.to_crs("EPSG:4326")
        except Exception as e_poly:
            if DEBUG_OSM: st.sidebar.warning(f"OSM (poly fail): {e_poly}. Fallback to bbox.")
            min_lon, min_lat, max_lon, max_lat = map_boundary_polygon_shapely.bounds
            buffer = 0.008
            G_bbox = ox.graph_from_bbox(max_lat+buffer, min_lat-buffer, max_lon+buffer, min_lon-buffer, network_type='drive_service',truncate_by_edge=True,retain_all=False,simplify=True)
            if G_bbox.number_of_edges() == 0: return []
            G_proj = ox.project_graph(G_bbox)
            segments_gdf_proj = ox.graph_to_gdfs(G_proj, nodes=False, edges=True, fill_edge_geometry=True)
            map_boundary_gdf_proj = gpd.GeoDataFrame([{'geometry': map_boundary_polygon_shapely}], crs="EPSG:4326").to_crs(segments_gdf_proj.crs)
            clipped_segments_proj = gpd.clip(segments_gdf_proj, map_boundary_gdf_proj.iloc[0].geometry)
            if clipped_segments_proj.empty: return []
            segments_gdf = clipped_segments_proj.to_crs("EPSG:4326")
        if segments_gdf.empty: return []
        existing_cols = [col for col in ['osmid', 'name', 'highway', 'length', 'geometry'] if col in segments_gdf.columns]
        segments_gdf = segments_gdf[existing_cols].copy()
        def get_cap(ht): return CAPACITY_MAP[ht[0]] if isinstance(ht, list) and ht and ht[0] in CAPACITY_MAP else (CAPACITY_MAP[ht] if ht in CAPACITY_MAP else DEFAULT_CAPACITY)
        segments_gdf['capacity'] = segments_gdf['highway'].apply(get_cap)
        if 'osmid' not in segments_gdf.columns or segments_gdf['osmid'].isnull().all(): segments_gdf['osmid'] = [f"seg_idx_{i}" for i in range(len(segments_gdf))]
        else: segments_gdf['osmid'] = segments_gdf['osmid'].apply(lambda x: x[0] if isinstance(x, list) and x else x).fillna(pd.Series([f"gen_seg_fill_{i}" for i in range(len(segments_gdf))]))
        if 'length' in segments_gdf: segments_gdf['length'] = segments_gdf['length'].astype(float)
        if 'highway' in segments_gdf: segments_gdf['highway'] = segments_gdf['highway'].apply(lambda x: x[0] if isinstance(x,list) and x else str(x) if pd.notnull(x) else 'unknown')
        if not segments_gdf.empty:
            # write cache atomically within lock
            with lock:
                segments_gdf.to_file(cache_file, driver="GPKG")
        else: return []
        processed_segments = []
        for _, row in segments_gdf.iterrows():
            coords_lon_lat_list = [list(coord) for coord in row.geometry.coords] if row.geometry and row.geometry.geom_type == 'LineString' else ([list(coord) for coord in row.geometry.geoms[0].coords] if row.geometry and row.geometry.geom_type == 'MultiLineString' and len(row.geometry.geoms) > 0 else [])
            processed_segments.append({
                'segment_id': str(row.get('osmid')),
                'coordinates': coords_lon_lat_list,
                'name': str(row.get('name', '')),
                'highway_type': str(row.get('highway', 'unknown')),
                'length': float(row.get('length', 0.0)),
                'capacity': int(row.get('capacity', DEFAULT_CAPACITY))
            })
        if DEBUG_OSM: st.sidebar.info(f"OSM: Processed {len(processed_segments)} new segments.")
        return processed_segments
    except Exception as e:
        if DEBUG_OSM: st.sidebar.error(f"OSM: General fail in fetch/process: {str(e)}"); import traceback; st.sidebar.text(traceback.format_exc())
        return []

def preload_traffic_data_for_week(selected_week_dict, project, base_osm_segments=None):
    if DEBUG_OSM: st.sidebar.info(f"OSM: Preloading data for week {selected_week_dict['year']}-{selected_week_dict['week']}")
    delivery_days_names = project.get("delivery_days", ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"])
    days_in_week = get_days_in_week(selected_week_dict["year"], selected_week_dict["week"], delivery_days_names)
    delivery_hours = project.get("delivery_hours", {})
    start_hour = parse_time_from_string(delivery_hours.get("start", "06:00"), dt_time(6,0)).hour
    end_hour = parse_time_from_string(delivery_hours.get("end", "18:00"), dt_time(18,0)).hour
    total_calculations = len(days_in_week) * (end_hour - start_hour + 1)
    progress_bar = None
    if total_calculations > 0 and not st.session_state.get("suppress_dashboard_progress", False):
        progress_bar = st.progress(0.0, text="Daten für Woche werden geladen...")
    week_cache_key = f"traffic_data_week_{selected_week_dict['year']}_{selected_week_dict['week']}_{project.get('id', 'default')}"
    if week_cache_key in st.session_state:
        if DEBUG_OSM: st.sidebar.info(f"OSM: Using cached week data for {week_cache_key}")
        if progress_bar: progress_bar.progress(1.0, text="Daten bereits geladen!"); time.sleep(0.5); progress_bar.empty()
        return st.session_state[week_cache_key]
    week_data = {}
    calculation_count = 0
    for day_obj in days_in_week:
        day_str_format = day_obj.strftime("%Y-%m-%d")
        week_data[day_str_format] = {}
        for hour_val in range(start_hour, end_hour + 1):
            traffic_data_point = get_traffic_data(day_str_format, hour_val, project, base_osm_segments, skip_cached=True)
            week_data[day_str_format][hour_val] = traffic_data_point
            calculation_count += 1
            if progress_bar: progress_bar.progress(calculation_count/total_calculations, text=f"Lade Daten: {day_obj.strftime('%a')} {hour_val}:00 ({calculation_count}/{total_calculations})")
    st.session_state[week_cache_key] = week_data
    if progress_bar: progress_bar.progress(1.0, text="Verkehrsdaten für die Woche geladen!"); time.sleep(0.5); progress_bar.empty()
    if DEBUG_OSM: st.sidebar.info(f"OSM: Week data preloaded and cached: {week_cache_key}")
    return week_data

def load_csv_data(file_path):
    """Load CSV data and print column names for debugging."""
    try:
        data_df = pd.read_csv(file_path)
        # Strip spaces from column names
        data_df.columns = data_df.columns.str.strip()
        print("CSV Columns:", data_df.columns)  # Debugging line to print column names
        return data_df
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return None

def _load_construction_schedule(project):
    """Load and cache the construction delivery schedule for a project as a DataFrame."""
    cache_key = f"construction_schedule_{project.get('id', 'default')}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    schedule_df = None
    # Prefer explicit file_path if provided
    file_path = project.get("file_path")
    if file_path and os.path.exists(file_path):
        schedule_df = pd.read_csv(file_path)
    else:
        # Fallback: assemble from name + file_name (legacy fields)
        proj_name = project.get("name", "")
        file_name = project.get("file_name", "Material_Lieferungen.csv")
        potential_path = os.path.join("data", "projects", proj_name, file_name)
        if os.path.exists(potential_path):
            schedule_df = pd.read_csv(potential_path)

    if schedule_df is None:
        schedule_df = pd.DataFrame()  # empty placeholder

    # Tidy column names
    schedule_df.columns = schedule_df.columns.str.strip()
    st.session_state[cache_key] = schedule_df
    return schedule_df

def _preprocess_schedule_df(schedule_df):
    """Ensure helper columns (_anfang_date, _anfang_hour) exist for fast filtering."""
    if schedule_df.empty:
        return schedule_df
    if "_anfang_date" not in schedule_df.columns or "_anfang_hour" not in schedule_df.columns:
        schedule_df["_anfang_date"] = schedule_df["Anfangstermin"].astype(str).str.split().str[0]
        schedule_df["_anfang_hour"] = (
            schedule_df["Anfangstermin"].astype(str)
            .str.split()
            .str[1]
            .fillna("00:00")
            .str.slice(0, 2)
            .astype(int)
        )
    return schedule_df

# Get daily deliveries (integer) according to 1 + ceil(material/10) rule
def _daily_deliveries_total(date_str: str, project) -> int:
    aggr = _daily_schedule_aggregates(project)
    row = aggr[aggr["date"] == date_str]
    if row.empty:
        return 0
    return int(row.iloc[0]["deliveries"])

# Pre-defined hourly weight distribution (07-17) – two peaks at 10 & 14, zero at 12
_HOURLY_WEIGHTS_RAW = {
    7: 1,
    8: 2,
    9: 5,
    10: 5,  # first peak
    11: 3,
    12: 0,  # lunch break – no deliveries
    13: 0,
    14: 5,  # second peak
    15: 5,
    16: 2,
    17: 1,
}
_WEIGHT_SUM = sum(_HOURLY_WEIGHTS_RAW.values()) if _HOURLY_WEIGHTS_RAW else 1
_HOURLY_WEIGHTS = {h: w / _WEIGHT_SUM for h, w in _HOURLY_WEIGHTS_RAW.items()}


# Cache per-day allocation so results stay constant in a session
def _get_cached_hourly_allocation(date_str: str, project):
    cache_key = f"hourly_delivery_allocation_{project.get('id','default')}_{date_str}"
    return st.session_state.get(cache_key)


def _store_hourly_allocation(date_str: str, project, alloc_dict):
    cache_key = f"hourly_delivery_allocation_{project.get('id','default')}_{date_str}"
    st.session_state[cache_key] = alloc_dict


def _allocate_deliveries_random(total_int: int, project, date_str: str):
    """Randomly allocate integer deliveries to hours according to weights (multinomial)."""
    # Prepare probability vector in fixed hour order 7-17
    hours_order = sorted(_HOURLY_WEIGHTS.keys())
    probs = np.array([_HOURLY_WEIGHTS[h] for h in hours_order])
    # Seed RNG with stable seed based on date + project id so result reproducible in a session
    seed_val = abs(hash(f"{project.get('id','p')}::{date_str}")) % (2**32)
    rng = np.random.default_rng(seed_val)
    allocation = rng.multinomial(total_int, probs)
    return {h: int(allocation[i]) for i, h in enumerate(hours_order)}


def get_hourly_construction_deliveries(date_str: str, hour: int, project) -> float:
    """Return deliveries for the specified hour by distributing daily total over a bivariate pattern."""
    total_deliveries_day = _daily_deliveries_total(date_str, project)
    if total_deliveries_day == 0:
        return 0

    # Use cached allocation if exists
    cached = _get_cached_hourly_allocation(date_str, project)
    if cached is None:
        alloc = _allocate_deliveries_random(total_deliveries_day, project, date_str)
        _store_hourly_allocation(date_str, project, alloc)
    else:
        alloc = cached

    return alloc.get(hour, 0)

def get_traffic_data(date_str, hour, project, base_osm_segments=None, skip_cached=False):
    """Get traffic data for a specific date and hour.
    Uses counter profiles for statistical summaries and
    simulates traffic on OpenStreetMap segments for map visualization.
    
    Args:
        date_str: Date string in format "YYYY-MM-DD"
        hour: Hour of the day (0-23)
        project: The current project data
        base_osm_segments: The road segments from OSM
        skip_cached: If True, skip checking the weekly cache (to avoid recursion during preloading)
    
    Returns:
        Dictionary with traffic data
    """
    # First check if we have this data cached in the weekly preloaded data
    if not skip_cached:
        # Determine which week this date belongs to
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            year, week_num, _ = date_obj.isocalendar()
            week_cache_key = f"traffic_data_week_{year}_{week_num}_{project.get('id', 'default')}"
            
            if week_cache_key in st.session_state and date_str in st.session_state[week_cache_key] and hour in st.session_state[week_cache_key][date_str]:
                if DEBUG_OSM: st.sidebar.info(f"OSM: Using cached traffic data for {date_str} {hour}:00 from week store")
                return st.session_state[week_cache_key][date_str][hour]
        except Exception as e_cache:
            if DEBUG_OSM: st.sidebar.warning(f"OSM: Error checking weekly cache: {e_cache}. Recalculating.")
            # Continue with direct calculation if any error in cache lookup
    
    # Ensure counter profiles are loaded if they are supposed to be the basis for stats
    # This check is important if `base_osm_segments` might be present but counters are not yet loaded.
    # However, load_profiles_for_counters is called early in show_dashboard.
    # A safeguard:
    if "counter_profiles" not in st.session_state or not st.session_state.counter_profiles:
        if "selected_counters" in st.session_state and st.session_state.selected_counters and project:
            if DEBUG_OSM: st.sidebar.info("OSM (get_traffic_data): Triggering profile load.")
            st.session_state.suppress_dashboard_progress = True
            load_profiles_for_counters(project)
            del st.session_state.suppress_dashboard_progress
    simulated_osm_segments_for_pydeck = []
    if "counter_profiles" not in st.session_state or not st.session_state.counter_profiles:
        if DEBUG_OSM: st.sidebar.warning("OSM (GTD): No counter profiles. Defaulting OSM data.")
        if base_osm_segments:
            time_factor_default = 0.3 
            if 7 <= hour <= 9 or 16 <= hour <= 18: time_factor_default = 0.6
            elif 10 <= hour <= 15: time_factor_default = 0.4
            for osm_segment_item in base_osm_segments:
                try: seg_hash_rand = (int(hashlib.md5(str(osm_segment_item["segment_id"]).encode()).hexdigest(),16)%50+10)/100.0
                except: seg_hash_rand = np.random.uniform(0.1,0.6)
                sim_vol = osm_segment_item["capacity"] * seg_hash_rand * time_factor_default
                sim_vol = min(sim_vol, osm_segment_item["capacity"] * 1.2)
                cong_default = (min(1.0, sim_vol / osm_segment_item["capacity"]) if osm_segment_item["capacity"] > 0 else 0)
                coords_for_pydeck_default = osm_segment_item.get("coordinates", [])
                simulated_osm_segments_for_pydeck.append({
                    "segment_id": osm_segment_item["segment_id"], "coordinates": coords_for_pydeck_default,
                    "traffic_volume": int(sim_vol), "congestion_level": cong_default,
                    "name": osm_segment_item.get("name", "N/A"), "highway_type": osm_segment_item.get("highway_type", "N/A"),
                })
        return {"date": date_str, "hour": hour, "traffic_segments": simulated_osm_segments_for_pydeck, "congestion_points": [], "stats": {"total_traffic": 0, "average_congestion": 0, "deliveries_count": 0, "access_traffic": 0, "construction_traffic": 0, "construction_share_pct": 0}}
    current_date_obj_calc = datetime.strptime(date_str, "%Y-%m-%d").date()
    total_traffic_counters, weighted_cong_sum_counters, num_primary_c, num_secondary_c = 0,0,0,0
    for profile_id_calc, profile_meta_calc in st.session_state.counter_profiles.items():
        vehicles_calc = get_station_traffic(profile_meta_calc, current_date_obj_calc, hour)
        total_traffic_counters += vehicles_calc
        station_cap = 500 if profile_meta_calc.get('is_primary') else 400
        cong_station = min(1.0, vehicles_calc / station_cap) if station_cap > 0 else 0
        if profile_meta_calc.get('is_primary'): weighted_cong_sum_counters += cong_station * 1.5; num_primary_c +=1
        else: weighted_cong_sum_counters += cong_station; num_secondary_c += 1
    avg_cong_counters = (weighted_cong_sum_counters / ((num_primary_c*1.5)+num_secondary_c)) if ((num_primary_c*1.5)+num_secondary_c) > 0 else 0.0
    # --- Real deliveries from schedule (no simulation) ---
    deliveries_calc = int(get_hourly_construction_deliveries(date_str, hour, project))
    if base_osm_segments:
        time_factor_base = 0.15
        if 7<=hour<=9: time_factor_curr=time_factor_base+0.65+(avg_cong_counters*0.4)
        elif 16<=hour<=18: time_factor_curr=time_factor_base+0.60+(avg_cong_counters*0.4)
        elif 10<=hour<=15: time_factor_curr=time_factor_base+0.25+(avg_cong_counters*0.25)
        else: time_factor_curr=time_factor_base+0.1+(avg_cong_counters*0.15)
        time_factor_curr = max(0.05, min(time_factor_curr, 1.0))
        util_factors = {'motorway':(0.30,0.85),'trunk':(0.30,0.85),'primary':(0.30,0.85),'secondary':(0.20,0.70),'tertiary':(0.20,0.70),'residential':(0.03,0.25),'living_street':(0.01,0.15),'service':(0.02,0.20),'unclassified':(0.1,0.4),'road':(0.1,0.4)}
        default_util = (0.05,0.20); max_flow_res=30; max_flow_serv_liv=15

        # --- NEW: determine which segments belong to the project's access route(s) ---
        access_route_ids = _get_access_route_segment_ids(project, base_osm_segments)
        access_traffic_hour = 0  # aggregated traffic for access route this hour

        for osm_seg_item in base_osm_segments:
            seg_cap = osm_seg_item.get('capacity',DEFAULT_CAPACITY); seg_cap = DEFAULT_CAPACITY if seg_cap==0 else seg_cap
            min_u,max_u=util_factors.get(osm_seg_item['highway_type'],default_util)
            hourly_driven_u=min_u+(max_u-min_u)*time_factor_curr
            try: seg_hash_rand_f=(int(hashlib.md5(str(osm_seg_item['segment_id']).encode()).hexdigest(),16)%71+30)/100.0
            except: seg_hash_rand_f=np.random.uniform(0.6,0.9)
            final_u_rate=hourly_driven_u*seg_hash_rand_f; final_u_rate=max(0.005,min(final_u_rate,1.0))
            sim_volume_calc=seg_cap*final_u_rate
            current_hw_type=osm_seg_item['highway_type']
            if current_hw_type=='residential': sim_volume_calc=min(sim_volume_calc,max_flow_res*seg_hash_rand_f*time_factor_curr)
            elif current_hw_type in ['service','living_street','track','path']: sim_volume_calc=min(sim_volume_calc,max_flow_serv_liv*seg_hash_rand_f*time_factor_curr)
            sim_volume_calc=max(0,min(sim_volume_calc,seg_cap*1.5))

            # ---- NEW: add construction-site traffic on the access route ----
            extra_construct = 0
            if access_route_ids and osm_seg_item['segment_id'] in access_route_ids:
                extra_construct = (deliveries_calc * 2) / max(1, len(access_route_ids))
                sim_volume_calc += extra_construct

            congestion_calc=min(1.0,sim_volume_calc/seg_cap) if seg_cap > 0 else 0.0
            coords_for_pydeck=osm_seg_item.get('coordinates',[])
            simulated_osm_segments_for_pydeck.append({
                "segment_id": osm_seg_item['segment_id'],
                "coordinates": coords_for_pydeck,
                "traffic_volume": int(sim_volume_calc),
                "congestion_level": congestion_calc,
                "name": osm_seg_item.get('name','N/A'),
                "highway_type": current_hw_type,
                "capacity": int(seg_cap),
                "construction_traffic": int(extra_construct)
            })

            if osm_seg_item['segment_id'] in access_route_ids:
                access_traffic_hour += int(sim_volume_calc)

    # Calculate total construction traffic for the day from schedule (real data, not simulated)
    total_construction_traffic = int(round(get_hourly_construction_deliveries(date_str, hour, project)))

    return {"date": date_str, "hour": hour, "traffic_segments": simulated_osm_segments_for_pydeck, "congestion_points": [], "stats": {"total_traffic": int(total_traffic_counters), "average_congestion": avg_cong_counters, "deliveries_count": deliveries_calc, "access_traffic": access_traffic_hour, "construction_traffic": total_construction_traffic, "construction_share_pct": (deliveries_calc * 2 / access_traffic_hour * 100) if access_traffic_hour else 0}}

def get_station_traffic(profile_meta, date_obj, hour):
    """Get traffic count for a specific station, date and hour from its profile data."""
    if 'data' not in profile_meta:
        return 0 
    data_df = profile_meta['data']; weekday_str = date_obj.strftime("%A"); month_val = date_obj.month
    filtered_df = data_df[(data_df['weekday'] == weekday_str) & (data_df['month'] == month_val) & (data_df['hour'] == hour)]
    if not filtered_df.empty: return int(round(filtered_df.iloc[0]['vehicles']))
    else: fallback_df = data_df[(data_df['month'] == month_val) & (data_df['hour'] == hour)]; return int(round(fallback_df['vehicles'].mean())) if not fallback_df.empty else 0


def generate_congestion_points(segments):
    """Generate congestion hotspots based on traffic segments (now expects OSM segments)"""
    congestion_points = []
    
    # Look for highly congested segments
    for segment in segments:
        if segment["congestion_level"] >= 0.7:
            # Calculate a point along the segment
            if len(segment["coordinates"]) >= 2:
                # Take a point 1/3 along the segment
                idx = max(1, len(segment["coordinates"]) // 3)
                point = segment["coordinates"][idx]
                
                congestion_points.append({
                    "segment_id": segment["segment_id"],
                    "congestion_level": segment["congestion_level"],
                    "coordinates": [point]  # Single point
                })
    
    return congestion_points

# Helper: cache and retrieve OSM segment ids that belong to the project's access route(s)

def _get_access_route_segment_ids(project, base_osm_segments, tol=0.0005):
    """Return a set of OSM segment_ids that spatially match the access routes of the project.

    Parameters
    ----------
    project : dict
        The current project dictionary (must contain key 'access_routes').
    base_osm_segments : list[dict]
        List with OSM segment dictionaries as produced by `generate_osm_traffic_segments`.
    tol : float
        Distance tolerance (in degrees) for matching a segment to a route.
    """
    cache_key = f"access_route_seg_ids_{project.get('id', 'default')}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    # Build shapely objects for the routes first
    route_geoms = []
    for route in project.get("access_routes", []):
        if not route or "coordinates" not in route:
            continue
        try:
            if route.get("type") == "LineString":
                route_geoms.append(LineString(route["coordinates"]))
            elif route.get("type") == "Polygon":  # take exterior ring as line
                route_geoms.append(LineString(route["coordinates"][0]))
        except Exception:
            # Skip invalid geometries silently
            continue

    seg_ids = set()
    if route_geoms and base_osm_segments:
        for seg in base_osm_segments:
            coords = seg.get("coordinates", [])
            if len(coords) < 2:
                continue
            try:
                seg_line = LineString(coords)
            except Exception:
                continue
            for rline in route_geoms:
                if seg_line.distance(rline) <= tol:
                    seg_ids.add(seg["segment_id"])
                    break

    st.session_state[cache_key] = seg_ids
    return seg_ids

def _get_access_osm_segments(project, base_osm_segments, tol=0.0005):
    """Return a list of OSM segment dictionaries that overlap with the project's access route.

    This function re-uses `_get_access_route_segment_ids` to identify relevant
    segment IDs and then filters `base_osm_segments`.  The result is cached in
    `st.session_state` so that the spatial comparison is only executed once per
    project (or until `base_osm_segments` is refreshed).
    """
    cache_key = f"access_osm_segments_{project.get('id', 'default')}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    if not base_osm_segments:
        st.session_state[cache_key] = []
        return []

    access_route_ids = _get_access_route_segment_ids(project, base_osm_segments, tol)
    filtered_segments = [seg for seg in base_osm_segments if seg.get('segment_id') in access_route_ids]

    st.session_state[cache_key] = filtered_segments
    return filtered_segments

# ---------------------------------------------------------------------------
# Construction-stats tab helpers
# ---------------------------------------------------------------------------


def _daily_schedule_aggregates(project):
    """Return DataFrame with columns date, persons, material, deliveries aggregated per day (cached)."""
    cache_key = f"schedule_daily_aggr_{project.get('id','default')}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    sched = _load_construction_schedule(project)
    if sched.empty or "Anfangstermin" not in sched.columns:
        df_out = pd.DataFrame(columns=["date", "persons", "material", "deliveries"])
        st.session_state[cache_key] = df_out
        return df_out

    sched = _preprocess_schedule_df(sched)

    # Helper to compute deliveries per row
    def _row_deliveries(mat):
        try:
            # Strip any non-numeric parts (like 21Kran1211510 -> 21)
            mat_str = str(mat)
            # Extract numeric prefix if it exists
            numeric_part = re.match(r'^\d+', mat_str)
            if numeric_part:
                mat_val = float(numeric_part.group(0))
            else:
                # Try direct conversion, will raise ValueError if not possible
                mat_val = float(mat_str)
        except Exception:
            mat_val = 0.0
        return max(1, int(np.ceil(mat_val / 10.0))) if mat_val > 0 else 0

    # Convert Material to numeric safely, coercing errors to NaN
    sched["_material_numeric"] = pd.to_numeric(sched["Material"], errors="coerce")
    # Fill NaN with 0
    sched["_material_numeric"] = sched["_material_numeric"].fillna(0.0)
    # Calculate deliveries
    sched["_deliveries_row"] = sched["Material"].apply(_row_deliveries)
    
    # Safe conversion for Personen column too
    sched["_persons_numeric"] = pd.to_numeric(sched["Personen"], errors="coerce").fillna(0.0)

    aggr = (
        sched.groupby("_anfang_date")
        .agg(
            persons=("_persons_numeric", "sum"),
            material=("_material_numeric", "sum"),
            deliveries=("_deliveries_row", "sum"),
        )
        .reset_index()
        .rename(columns={"_anfang_date": "date"})
    )

    # Ensure correct dtypes
    aggr["material"] = aggr["material"].astype(float)
    aggr["persons"] = aggr["persons"].astype(float)
    aggr["deliveries"] = aggr["deliveries"].astype(int)

    st.session_state[cache_key] = aggr
    return aggr


def _render_construction_stats_tab(project):
    """Render the second tab with three time-series histograms."""
    aggr_df = _daily_schedule_aggregates(project)
    if aggr_df.empty:
        st.warning("Keine Daten im Bauzeitplan gefunden.")
        return

    # Convert date col to datetime for Plotly
    aggr_df["date_dt"] = pd.to_datetime(aggr_df["date"])

    # Common layout tweaks
    def _base_bar(x, y, name, color):
        fig = go.Figure(data=[go.Bar(x=x, y=y, marker_color=color, width=24 * 60 * 60 * 1000 * 0.7)])
        fig.update_layout(
            xaxis=dict(rangeslider=dict(visible=True), type="date"),
            yaxis_title=name,
            height=250,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    st.subheader("Personen auf der Baustelle (pro Tag)")
    st.plotly_chart(_base_bar(aggr_df["date_dt"], aggr_df["persons"], "Personen", "#1f77b4"), use_container_width=True)

    st.subheader("Material (Einheiten) pro Tag")
    st.plotly_chart(_base_bar(aggr_df["date_dt"], aggr_df["material"], "Material", "#2ca02c"), use_container_width=True)

    st.subheader("Lieferungen pro Tag")
    st.plotly_chart(_base_bar(aggr_df["date_dt"], aggr_df["deliveries"], "Lieferungen", "#d62728"), use_container_width=True)

def show_dashboard(project):
    """Show the dashboard for visualizing traffic simulation results"""
    # Set widget width for dashboard - now handled in streamlit_app.py
    # st.session_state.widget_width_percent = 35
    
    # Apply chart styling for this page
    apply_chart_styling()
    
    # --- Tab structure -------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["Verkehr", "Baustellenstatistiken", "Andere"])
    
    with tab1:
        _render_traffic_tab(project)
    
    with tab2:
        _render_construction_stats_tab(project)
    
    with tab3:
        st.info("Platzhalter für zukünftige Inhalte …")