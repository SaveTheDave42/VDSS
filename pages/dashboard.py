import streamlit as st
import pandas as pd
import json
import requests
import os
from datetime import datetime, date, timedelta, time
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import numpy as np
import calendar # For week/weekday calculations
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Polygon as ShapelyPolygon
import hashlib

# Define API URL
API_URL = "http://localhost:8000"

# Set this to True to see debug info
DEBUG_COORDS = True # Temporarily True for debugging
DEBUG_OSM = True    # Temporarily True for debugging

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


def parse_time_from_string(time_input, default_time):
    """Parses a time string (HH:MM) or returns default if input is already a time object or invalid."""
    if isinstance(time_input, time):
        return time_input
    if isinstance(time_input, str):
        try:
            return datetime.strptime(time_input, "%H:%M").time()
        except ValueError:
            return default_time # Fallback to default if parsing fails
    return default_time # Fallback for other unexpected types

def get_week_options():
    """Generates a list of week options for the current and +/- 4 weeks."""
    today = date.today()
    options = []
    for i in range(-8, 9): # Extended range for more flexibility
        dt = today + timedelta(weeks=i)
        year, week_num, _ = dt.isocalendar()
        # Get the first day of that week (Monday)
        start_of_week = dt - timedelta(days=dt.weekday())
        # Get the last day of that week (Sunday)
        end_of_week = start_of_week + timedelta(days=6)
        options.append({
            "label": f"KW {week_num} ({year}) | {start_of_week.strftime('%d.%m')} - {end_of_week.strftime('%d.%m')}",
            "year": year,
            "week": week_num,
            "start_date": start_of_week,
            "end_date": end_of_week
        })
    return options

def get_days_in_week(year, week_num, delivery_days_filter):
    """Gets all dates for a given ISO week number and year, filtered by delivery days."""
    # Map German weekday names to ISO weekday numbers (Monday=0, Sunday=6)
    weekday_map_to_iso = {
        "Montag": 0, "Dienstag": 1, "Mittwoch": 2, 
        "Donnerstag": 3, "Freitag": 4, "Samstag": 5, "Sonntag": 6
    }
    allowed_iso_weekdays = [weekday_map_to_iso[day] for day in delivery_days_filter if day in weekday_map_to_iso]
    
    # First day of the year
    first_day_of_year = date(year, 1, 1)
    # First Monday of the year
    if first_day_of_year.weekday() > 3: # If Jan 1st is Fri, Sat, Sun, then week 1 starts next Mon
        first_monday_of_year = first_day_of_year + timedelta(days=(7 - first_day_of_year.weekday()))
    else: # Week 1 starts on or before Jan 1st
        first_monday_of_year = first_day_of_year - timedelta(days=first_day_of_year.weekday())
    
    # Start date of the target week
    current_date = first_monday_of_year + timedelta(weeks=week_num - 1)
    days = []
    for _ in range(7):
        if current_date.year == year and current_date.weekday() in allowed_iso_weekdays:
            days.append(current_date)
        current_date += timedelta(days=1)
    return days

def show_dashboard(project):
    """Show the dashboard for visualizing traffic simulation results"""
    # Remove dashboard title (no headings required in the new design)

    # Inject custom CSS: hide headings and float widget panel on the right over the map
    st.markdown("""
    <style>
        /* Only hide default Streamlit headings (not our custom ones) */
        .main .block-container h1, 
        .main .block-container h2:not([style]), 
        .main .block-container h3:not([style]), 
        .main .block-container h4, 
        .main .block-container h5, 
        .main .block-container h6 {
            display: none;
        }

        /* Make first column (map) span the whole width */
        div[data-testid='column']:nth-of-type(1) {
            width: 100% !important;
        }

        /* Float second column (controls & charts) on the right */
        div[data-testid='column']:nth-of-type(2) {
            position: fixed !important;
            top: 70px; /* Increased from 60px to 70px for more space at top */
            right: 20px;
            width: 360px !important;
            max-height: 85vh;
            overflow-y: auto;
            background: rgba(33, 37, 41, 0.9);
            padding: 20px 16px 12px 16px; /* Increased top padding */
            border-radius: 8px;
            z-index: 1000;
        }

        /* Ensure metrics row spacing is correct */
        div[data-testid="metric-container"] {
            margin-bottom: 10px !important;
            padding: 5px !important;
        }

        /* Remove padding around map column */
        div[data-testid='column']:nth-of-type(1) > div {
            padding: 0 !important;
            margin: 0 !important;
        }

        /* Remove padding/margins of the main Streamlit block-container and allow full width */
        section.main > div.block-container {
            padding-top: 0 !important;
            padding-right: 0 !important;
            padding-left: 0 !important;
            padding-bottom: 0 !important;
            max-width: 100% !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Session state checks and data loading
    if "selected_counters" not in st.session_state and "selected_counters" in project:
        # Parse counter coordinates from project which might be loaded from JSON
        if DEBUG_COORDS:
            st.sidebar.write("DEBUG: Processing project selected_counters: ")
            st.sidebar.write(f"  - Type: {type(project['selected_counters'])}")
            if len(project['selected_counters']) > 0:
                st.sidebar.write(f"  - First item type: {type(project['selected_counters'][0])}")
                if 'coordinates' in project['selected_counters'][0]:
                    st.sidebar.write(f"  - First coords type: {type(project['selected_counters'][0]['coordinates'])}")
                    st.sidebar.write(f"  - First coords: {project['selected_counters'][0]['coordinates']}")
        
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
                                st.sidebar.write(f"DEBUG: Parsed project coords for {parsed_counter.get('id')}: {parsed_counter['coordinates']}")
                    except Exception as e:
                        if DEBUG_COORDS:
                            st.sidebar.write(f"DEBUG: Failed to parse coords: {e}")
            parsed_counters.append(parsed_counter)
        
        # Set the parsed counters in session state
        st.session_state.selected_counters = parsed_counters
        if DEBUG_COORDS:
            st.sidebar.write("DEBUG: selected_counters loaded from project:")
            for i, counter in enumerate(st.session_state.selected_counters[:2]):  # Show first 2 only
                st.sidebar.write(f"{i}: {counter.get('id')} - coords: {counter.get('coordinates')}")
    if "primary_counter" not in st.session_state and "primary_counter" in project:
        st.session_state.primary_counter = project["primary_counter"]
    if ("counter_profiles" not in st.session_state or not st.session_state.counter_profiles) and \
       ("selected_counters" in st.session_state and st.session_state.selected_counters):
        load_profiles_for_counters(project)
    if "counter_profiles" not in st.session_state or not st.session_state.counter_profiles:
        st.warning("No traffic counting stations selected or profiles could not be loaded. Please go to Project Setup.")
        if st.button("Go to Project Setup"):
            st.session_state.page = "project_setup"
            st.rerun()
        return
    ensure_profile_coordinates()
    if DEBUG_COORDS:
        st.sidebar.write("DEBUG: After ensure_profile_coordinates:")
        for i, (pid, profile) in enumerate(list(st.session_state.counter_profiles.items())[:2]):  # First 2
            st.sidebar.write(f"{i}: {pid} - coords: {profile.get('coordinates')}")
    sanitize_counters(st.session_state.get("selected_counters", []))
    sanitize_counter(st.session_state.get("primary_counter", None))

    # --- Layout Columns ---
    # Define columns with map first (will take full width) and widget panel second (floating)
    col2, col1 = st.columns([0.8, 0.2])  # Map column (col2) | Widget column (col1)

    # Ensure project data is available
    if not project or "id" not in project:
        st.error("Project data is not loaded correctly.")
        return

    # Get base OSM segments (cached or fetched)
    base_osm_segments = get_base_osm_segments(project)
    if not base_osm_segments and DEBUG_OSM: # Only show warning if in debug, otherwise it might be alarming
        st.sidebar.warning("OSM: No base OSM segments could be generated. Map may not show traffic routes.")

    # Initialize animation state
    if "animation_running" not in st.session_state:
        st.session_state.animation_running = False
    if "animation_current_hour" not in st.session_state:
        st.session_state.animation_current_hour = (project.get("delivery_hours", {}).get("start", "06:00"))

    with col1:
        # Add title at the top
        st.markdown("<h2 style='text-align: center; color: white;'>Traffic Dashboard</h2>", unsafe_allow_html=True)
        
        # Controls
        # --- Date & Time Selection --- 
        week_options = get_week_options()
        today_cal = date.today().isocalendar()
        default_week_index = next((i for i, option in enumerate(week_options) if option["year"] == today_cal[0] and option["week"] == today_cal[1]), len(week_options) // 2)
        selected_week_dict = st.selectbox("Select Week", options=week_options, index=default_week_index, format_func=lambda x: x["label"], key="week_dashboard_ctrl")
        
        delivery_days_names = project.get("delivery_days", ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"])
        days_in_week = get_days_in_week(selected_week_dict["year"], selected_week_dict["week"], delivery_days_names)
        selected_date_for_map = st.selectbox("Select Day", options=days_in_week, format_func=lambda d: f"{d.strftime('%A, %d.%m.%Y')}", key="day_dashboard_ctrl") if days_in_week else date.today()
        
        delivery_hours = project.get("delivery_hours", {})
        start_hour_str = delivery_hours.get("start", "06:00")
        end_hour_str = delivery_hours.get("end", "18:00")
        start_hour = parse_time_from_string(start_hour_str, time(6,0)).hour
        end_hour = parse_time_from_string(end_hour_str, time(18,0)).hour

        # Initialize animation_current_hour if it's the first run or project changes, or date changes
        # This ensures the animation starts from the beginning of the selected day's range.
        if "last_selected_date_for_animation_init" not in st.session_state or \
           st.session_state.last_selected_date_for_animation_init != selected_date_for_map or \
           "animation_current_hour_value" not in st.session_state:
            st.session_state.animation_current_hour_value = start_hour
            st.session_state.last_selected_date_for_animation_init = selected_date_for_map

        def animation_step():
            if st.session_state.animation_running:
                current_val = st.session_state.animation_current_hour_value
                next_val = current_val + 1
                if next_val > end_hour:
                    next_val = start_hour # Loop back
                st.session_state.animation_current_hour_value = next_val

        # Slider for hour selection
        if not st.session_state.get("animation_running", False): # Show slider if animation is NOT running
            selected_hour_for_map = st.slider("Select Hour", \
                                              min_value=start_hour, \
                                              max_value=end_hour, \
                                              value=st.session_state.animation_current_hour_value, \
                                              step=1, \
                                              format="%d:00", \
                                              key="hour_dashboard_ctrl_manual")
            # Update animation_current_hour_value if slider is moved manually
            st.session_state.animation_current_hour_value = selected_hour_for_map
        else: # Animation is running
            selected_hour_for_map = st.session_state.animation_current_hour_value
            # Display the current hour when animating, but disable direct interaction with a slider
            st.markdown(f"<p style='color:white; text-align:center;'>Animating Hour: {selected_hour_for_map:02d}:00</p>", unsafe_allow_html=True)

        # Play/Pause Button
        button_text = "Pause Animation" if st.session_state.get("animation_running", False) else "Play Animation"
        if st.button(button_text, key="play_pause_animation"):
            st.session_state.animation_running = not st.session_state.animation_running
            if st.session_state.animation_running:
                # If starting animation, ensure the current slider value (from manual or last anim state) is used
                # No, selected_hour_for_map might be from the slider if it was just visible
                # We should use animation_current_hour_value as the consistent state for the hour
                pass # animation_current_hour_value is already up-to-date
            st.rerun() # Rerun to update button text and either start/stop animation loop or show/hide slider

        selected_date_str_for_map = selected_date_for_map.strftime("%Y-%m-%d")

        st.markdown("<hr>", unsafe_allow_html=True)

        # Key Metrics - moved to after time selection to ensure proper spacing
        # Pass base_osm_segments to get_traffic_data
        current_traffic_data = get_traffic_data(selected_date_str_for_map, selected_hour_for_map, project, base_osm_segments)
        avg_cong_display = "N/A"
        if current_traffic_data and current_traffic_data["stats"]["average_congestion"] is not None:
            avg_cong = current_traffic_data['stats']['average_congestion']
            avg_cong_display = 'Low' if avg_cong < 0.3 else 'Medium' if avg_cong < 0.7 else 'High'
        
        # Display metrics with clear labels
        st.markdown("<h3 style='text-align: left; color: white; margin-top: 15px;'>Key Metrics</h3>", unsafe_allow_html=True)
        
        # Total Traffic
        st.metric("Total Traffic", current_traffic_data["stats"]["total_traffic"] if current_traffic_data else "N/A")
        
        # Deliveries
        st.metric("Deliveries", current_traffic_data["stats"]["deliveries_count"] if current_traffic_data else "N/A")
        
        # Congestion
        st.metric("Congestion", avg_cong_display)
        
        st.markdown("<hr>", unsafe_allow_html=True)

        # Daily Traffic Volume (title removed)
        dates_ts = days_in_week if days_in_week else [selected_week_dict["start_date"] + timedelta(days=i) for i in range(7)]
        
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

        fig_daily = go.Figure(data=[go.Bar(x=[d.strftime("%a, %d.%m") for d in dates_ts], y=daily_totals_ts, name="Total Daily Traffic", marker_color="#1f77b4")])
        fig_daily.update_layout(xaxis_title=None, yaxis_title="Total Vehicles", margin=dict(l=10,r=10,t=30,b=10), height=220)
        st.plotly_chart(fig_daily, use_container_width=True)
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # Hourly Analysis (title removed)
        # st.subheader(f"Hourly Analysis for {selected_date_for_map.strftime('%A, %d.%m')}")
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
        fig_hourly.add_trace(go.Bar(x=hours_list_hr, y=hourly_traffic_hr, name="Traffic Volume", marker_color="#1f77b4", opacity=0.7))
        fig_hourly.add_trace(go.Scatter(x=hours_list_hr, y=hourly_congestion_hr, mode="lines+markers", name="Congestion", line=dict(color="#d62728"), yaxis="y2"))
        fig_hourly.add_trace(go.Scatter(x=hours_list_hr, y=hourly_deliveries_hr, mode="lines+markers", name="Deliveries", line=dict(color="#2ca02c", dash="dot"), marker=dict(size=7), yaxis="y3"))
        fig_hourly.update_layout(
            xaxis=dict(title="Hour of Selected Day"),
            yaxis=dict(title="Traffic Volume", titlefont=dict(color="#1f77b4"), tickfont=dict(color="#1f77b4"), side="left"),
            yaxis2=dict(title="Congestion", titlefont=dict(color="#d62728"), tickfont=dict(color="#d62728"), anchor="x", overlaying="y", side="right", range=[0, 1]),
            yaxis3=dict(title="Deliveries", titlefont=dict(color="#2ca02c"), tickfont=dict(color="#2ca02c"), anchor="free", overlaying="y", side="right", position=0.85, showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5),
            margin=dict(l=10,r=10,t=50,b=10), height=280
        )
        st.plotly_chart(fig_hourly, use_container_width=True)

    # --- Map Display (Right Column) ---
    with col2:
        # Traffic Map (title removed)
        
        # Determine initial map location and zoom
        initial_location = [47.3769, 8.5417] # Default: Zurich center
        initial_zoom = 12

        # Try to use project polygon centroid as a fallback if map_bounds isn't primary
        project_polygon_data = project.get("polygon", {})
        if "coordinates" in project_polygon_data and project_polygon_data["coordinates"] and project_polygon_data["coordinates"][0]:
            polygon_coords_for_centroid = project_polygon_data["coordinates"][0]
            if polygon_coords_for_centroid: # Ensure list is not empty
                try:
                    centroid_lon = sum(p[0] for p in polygon_coords_for_centroid) / len(polygon_coords_for_centroid)
                    centroid_lat = sum(p[1] for p in polygon_coords_for_centroid) / len(polygon_coords_for_centroid)
                    initial_location = [centroid_lat, centroid_lon]
                    initial_zoom = 14
                except (TypeError, ZeroDivisionError, IndexError):
                    # Handle cases where polygon_coords_for_centroid might be malformed or empty
                    if DEBUG_COORDS:
                        st.sidebar.write("DEBUG: Error calculating centroid from polygon.")
                    pass # Keep default Zurich center

        m = folium.Map(location=initial_location, zoom_start=initial_zoom, tiles="cartodbpositron")

        # Fit to map_bounds if available in the project data
        map_bounds_data = project.get("map_bounds", {})
        if "coordinates" in map_bounds_data and map_bounds_data["coordinates"] and map_bounds_data["coordinates"][0]:
            bounds_coords_list = map_bounds_data["coordinates"][0]
            if bounds_coords_list and len(bounds_coords_list) > 1: # Ensure there are points to form bounds
                try:
                    # Coords are [lon, lat]
                    min_lon = min(p[0] for p in bounds_coords_list)
                    max_lon = max(p[0] for p in bounds_coords_list)
                    min_lat = min(p[1] for p in bounds_coords_list)
                    max_lat = max(p[1] for p in bounds_coords_list)
                    
                    # folium fit_bounds takes [[south, west], [north, east]]
                    # which is [[min_lat, min_lon], [max_lat, max_lon]]
                    if min_lat != max_lat or min_lon != max_lon: # Avoid fitting to a single point or line if possible
                        m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], max_zoom=16)
                    # If it's a single point, the initial_location based on centroid or default will be used, 
                    # or map will center on this single point from bounds if fit_bounds is still called.
                    # Current logic relies on initial_location if bounds are degenerate.
                except (TypeError, ValueError, IndexError):
                     if DEBUG_COORDS:
                        st.sidebar.write("DEBUG: Error processing map_bounds.")
                     # Fallback to initial_location and initial_zoom already set if bounds are problematic
                     pass


        # Add project polygon to the map
        if "polygon" in project and "coordinates" in project["polygon"]: # Re-check for safety
            folium.GeoJson(
                project["polygon"], 
                name="Construction Site", 
                style_function=lambda x: {"fillColor": "#dc3545", "color": "#dc3545", "weight": 2, "fillOpacity": 0.5}
            ).add_to(m)

        # Get fresh traffic data for the map using the selected hour and base_osm_segments
        map_traffic_data_osm = get_traffic_data(selected_date_str_for_map, selected_hour_for_map, project, base_osm_segments)

        if map_traffic_data_osm and map_traffic_data_osm.get("traffic_segments"):
            if DEBUG_OSM or DEBUG_COORDS:
                st.sidebar.write(f"OSM: Drawing {len(map_traffic_data_osm['traffic_segments'])} traffic segments on map.")
            for segment in map_traffic_data_osm["traffic_segments"]:
                congestion = segment["congestion_level"]
                color = "#dc3545" if congestion >= 0.7 else "#ffc107" if congestion >= 0.3 else "#28a745"
                
                # Coordinates are already [lat, lon] from `get_traffic_data`
                # segment['coordinates'] from generate_osm_traffic_segments are (lon,lat)
                # they are flipped in get_traffic_data
                folium_coords = segment["coordinates"] # Should be [[lat, lon], ...]

                if folium_coords and len(folium_coords) >= 2:
                    folium.PolyLine(
                        locations=folium_coords,
                        color=color,
                        weight=max(2, 8 - (congestion * 5)), # Thicker for less congestion, thinner for more (or vice-versa)
                        opacity=0.7,
                        tooltip=f"Name: {segment.get('name', 'N/A')}<br>Type: {segment.get('highway_type', 'N/A')}<br>Vol: {segment.get('traffic_volume', 'N/A')}<br>Cong: {congestion:.2f}"
                    ).add_to(m)
                elif (DEBUG_OSM or DEBUG_COORDS):
                    st.sidebar.warning(f"OSM: Segment {segment.get('segment_id')} has invalid coordinates for PolyLine: {folium_coords}")
        elif DEBUG_OSM or DEBUG_COORDS:
            st.sidebar.warning("OSM: No OSM traffic_segments to draw on map for current selection.")
        
        folium_static(m, width=None, height=950)  # Increased height for larger visible map

    # Trigger next animation step if running
    if st.session_state.get("animation_running", False):
        animation_step() # Advances the hour
        time.sleep(0.5) # Control animation speed (seconds per frame)
        st.rerun()

    # Additional CSS tweaks: smaller metric values & remove map padding
    st.markdown("""
    <style>
        /* Smaller metric value font */
        div[data-testid="stMetricValue"] {
            font-size: 1.3rem !important; /* approx. 2/3 default */
        }
    </style>
    """, unsafe_allow_html=True)

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
                        st.sidebar.write(f"DEBUG: Parsed string coordinates: {counter['coordinates']}")
            except Exception as e:
                if DEBUG_COORDS:
                    st.sidebar.write(f"DEBUG: Error parsing coordinates: {e}")
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

    counter_coords = {}
    for counter in sanitized_selected_counters:
        if 'coordinates' in counter and counter['coordinates']:
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
                profile['coordinates'] = counter_coords[profile_id]
            elif primary_counter_sanitized and 'coordinates' in primary_counter_sanitized:
                if DEBUG_COORDS:
                    st.sidebar.write(f"DEBUG: Setting coords from primary: {primary_counter_sanitized['coordinates']}")
                profile['coordinates'] = primary_counter_sanitized['coordinates']
            else:
                if DEBUG_COORDS:
                    st.sidebar.write(f"DEBUG: Setting default coords")
                profile['coordinates'] = [47.376888, 8.541694]

def load_counter_coordinates():
    """Load coordinates from counters.csv to be used as a canonical data source."""
    coordinates_by_id = {}
    try:
        counters_file = "data/prepared/counters.csv"
        if os.path.exists(counters_file):
            df = pd.read_csv(counters_file)
            
            for _, row in df.iterrows():
                profile_id = row['profile_id']
                
                # Try different coordinate sources in order of preference
                if 'lat' in df.columns and 'lon' in df.columns and not pd.isna(row['lat']) and not pd.isna(row['lon']):
                    coordinates_by_id[profile_id] = [float(row['lat']), float(row['lon'])]
                elif 'coordinates' in df.columns and not pd.isna(row['coordinates']):
                    # Parse string coordinates if present
                    coords_str = str(row['coordinates'])
                    if coords_str.startswith('[') and coords_str.endswith(']'):
                        coords_str = coords_str.strip('[]')
                        lat, lon = map(float, coords_str.split(','))
                        coordinates_by_id[profile_id] = [lat, lon]
                elif 'x_coord' in df.columns and 'y_coord' in df.columns:
                    # Default to Zurich center if no proper coordinates found
                    coordinates_by_id[profile_id] = [47.376888, 8.541694]
            
        return coordinates_by_id
    except Exception as e:
        if DEBUG_COORDS:
            st.sidebar.write(f"DEBUG: Error loading counter coordinates: {str(e)}")
        return {}

def load_profiles_for_counters(project):
    """Load profiles for the selected counters from files"""
    if "selected_counters" not in st.session_state or not st.session_state.selected_counters:
        return
    
    st.session_state.counter_profiles = {}
    debug_mode = st.session_state.get('debug_mode', False)
    if DEBUG_COORDS or debug_mode:
        st.sidebar.write("DEBUG (load_profiles): Loading profiles...")

    # Load coordinates from the canonical source (counters.csv)
    counter_coordinates = load_counter_coordinates()

    sanitized_selected_counters = sanitize_counters(st.session_state.selected_counters)
    primary_counter_sanitized = sanitize_counter(dict(st.session_state.primary_counter)) if st.session_state.primary_counter else None

    # Update selected_counters with coordinates if they're missing (to save back to project)
    updated_counters = []
    coordinates_updated = False
    
    for counter in sanitized_selected_counters:
        updated_counter = counter.copy()
        profile_id = f"{counter['id']}_{counter['direction']}"
        
        # Add coordinates from canonical source if missing in project data
        if (not counter.get('coordinates')) and profile_id in counter_coordinates:
            updated_counter['coordinates'] = counter_coordinates[profile_id]
            coordinates_updated = True
            
        updated_counters.append(updated_counter)
    
    # Update session state with the coordinates-enriched counters
    if coordinates_updated:
        st.session_state.selected_counters = updated_counters
        # If current_project exists, update it too so coordinates persist
        if "current_project" in st.session_state and "selected_counters" in st.session_state.current_project:
            st.session_state.current_project["selected_counters"] = updated_counters

    for counter in sanitized_selected_counters:
        station_id = counter['id']
        direction = counter['direction']
        is_primary = False
        if primary_counter_sanitized:
            is_primary = (station_id == primary_counter_sanitized['id'] and direction == primary_counter_sanitized['direction'])
        
        profile_id = f"{station_id}_{direction}"
        profile_file = f"data/prepared/profiles/{profile_id}.csv"
        
        if DEBUG_COORDS or debug_mode:
            st.sidebar.write(f"DEBUG: Processing {profile_id} - coords: {counter.get('coordinates')}")
            
        if os.path.exists(profile_file):
            profile_data = pd.read_csv(profile_file)
            
            # Use coordinates from canonical source if available
            coordinates = counter_coordinates.get(profile_id, [47.376888, 8.541694]) 
            
            st.session_state.counter_profiles[profile_id] = {
                'id': station_id,
                'direction': direction,
                'name': counter.get('name', ''),
                'display_name': counter.get('display_name', ''),
                'is_primary': is_primary,
                'coordinates': coordinates,
                'data': profile_data
            }
            if DEBUG_COORDS or debug_mode:
                st.sidebar.write(f"DEBUG: Loaded {profile_id} - stored coords: {st.session_state.counter_profiles[profile_id].get('coordinates')}")
        else:
            st.warning(f"Profile file not found: {profile_file}")

    if st.session_state.counter_profiles:
        st.session_state.global_counter_profiles = st.session_state.counter_profiles
        if DEBUG_COORDS or debug_mode:
            st.sidebar.write(f"DEBUG: Successfully loaded {len(st.session_state.counter_profiles)} profiles.")
    elif debug_mode:
        st.write("DEBUG (load_profiles): No profiles were loaded.")

def get_base_osm_segments(project):
    if "base_osm_segments" not in st.session_state or \
       st.session_state.get("current_project_id_for_osm", None) != project.get("id"):
        
        map_bounds = project.get("map_bounds")
        project_id = project.get("id", "default_project") # Use a default if id is missing

        if DEBUG_OSM:
            st.sidebar.info(f"OSM: Generating base OSM segments for project: {project_id}")
            if not map_bounds or 'coordinates' not in map_bounds or not map_bounds['coordinates']:
                 st.sidebar.warning("OSM: Project map_bounds are missing or invalid for get_base_osm_segments.")
            else:
                 st.sidebar.write(f"OSM: Map bounds for {project_id}: {map_bounds['coordinates'][0][:2]}...") # Show first 2 coords

        st.session_state.base_osm_segments = generate_osm_traffic_segments(map_bounds, project_id)
        st.session_state.current_project_id_for_osm = project_id
        if DEBUG_OSM:
            st.sidebar.info(f"OSM: Stored {len(st.session_state.base_osm_segments)} base segments in session state.")
    return st.session_state.base_osm_segments

def generate_osm_traffic_segments(project_map_bounds, project_id):
    """
    Fetches road network data from OpenStreetMap within the given map_bounds,
    processes it into traffic segments with estimated capacities, and caches the result.
    """
    if not project_map_bounds or 'coordinates' not in project_map_bounds or not project_map_bounds['coordinates']:
        if DEBUG_OSM:
            st.sidebar.warning("OSM: Project map bounds are missing or invalid.")
        return []

    # Create a stable cache key from map_bounds coordinates
    # Using project_id as part of the cache key ensures specificity per project
    bounds_coords_str = json.dumps(project_map_bounds['coordinates'][0], sort_keys=True)
    cache_key_input = f"{project_id}_{bounds_coords_str}"
    cache_filename_base = hashlib.md5(cache_key_input.encode()).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"osm_segments_{cache_filename_base}.gpkg")

    if os.path.exists(cache_file):
        if DEBUG_OSM:
            st.sidebar.info(f"OSM: Loading cached road segments from {cache_file}")
        try:
            segments_gdf = gpd.read_file(cache_file)
            if segments_gdf.empty:
                if DEBUG_OSM: st.sidebar.warning(f"OSM: Cache file {cache_file} is empty. Refetching.")
                os.remove(cache_file) # Remove empty cache file
                # Fall through to refetch by not returning here
            else:
                # Convert geometry to list of coordinates for consistent processing later
                # Ensure coordinates are in [lon, lat] for internal consistency before flipping for Folium
                processed_segments = []
                for idx, row in segments_gdf.iterrows(): # Changed _ to idx for clarity in logging
                    coords = []
                    if row.geometry:
                        coords = list(row.geometry.coords) # list of (lon, lat) tuples
                    
                    highway_type = row.get('highway', 'unknown')
                    if isinstance(highway_type, list):
                        highway_type = highway_type[0] if highway_type else 'unknown'

                    segment_id_val = str(row.get('osmid', f"cached_segment_{idx}"))
                    capacity_val = int(row.get('capacity', DEFAULT_CAPACITY))
                    length_val = float(row.get('length', 0.0))
                    name_val = str(row.get('name', ''))

                    # if DEBUG_OSM and idx < 2: # Log first 2 segments from cache
                    #    st.sidebar.write(f"  Cache Seg {segment_id_val}: HW={highway_type}, Cap={capacity_val}, Len={length_val:.2f}")

                    processed_segments.append({
                        'segment_id': segment_id_val,
                        'coordinates': coords, 
                        'name': name_val,
                        'highway_type': highway_type,
                        'length': length_val,
                        'capacity': capacity_val
                    })
                if DEBUG_OSM:
                    st.sidebar.info(f"OSM: Loaded {len(processed_segments)} segments from cache.")
                return processed_segments
        except Exception as e:
            if DEBUG_OSM:
                st.sidebar.error(f"OSM: Error loading cached GDF: {e}. Refetching.")
            if os.path.exists(cache_file): # Ensure corrupted cache is removed
                try: os.remove(cache_file)
                except: pass
            # Fall through to refetch if cache is corrupted

    if DEBUG_OSM:
        st.sidebar.info("OSM: No valid cache. Fetching road network from OSM...")

    try:
        shapely_poly_coords = project_map_bounds['coordinates'][0]
        if not shapely_poly_coords or len(shapely_poly_coords) < 3:
            if DEBUG_OSM: st.sidebar.warning("OSM: Invalid polygon coordinates for fetching.")
            return []

        map_boundary_polygon_shapely = ShapelyPolygon(shapely_poly_coords) # Needs (lon, lat)
        if DEBUG_OSM:
            st.sidebar.write(f"OSM: Polygon for fetching/clipping (Shapely): {map_boundary_polygon_shapely.exterior.coords[:]}")

        # Method 1: Graph from polygon directly (preferred if it works well with network types)
        if DEBUG_OSM: st.sidebar.info("OSM: Attempting ox.graph_from_polygon...")
        try:
            # OSMnx graph_from_polygon uses the polygon directly. 
            # It internally handles reprojection if the polygon CRS is set.
            # Create a GeoDataFrame from the polygon to set its CRS to EPSG:4326
            poly_gdf = gpd.GeoDataFrame([{'id':1, 'geometry': map_boundary_polygon_shapely}], crs="EPSG:4326")
            
            G = ox.graph_from_polygon(poly_gdf.iloc[0]['geometry'], 
                                       network_type='drive_service', 
                                       truncate_by_edge=True, 
                                       retain_all=False, # Changed from True to False, usually better with truncate_by_edge
                                       simplify=True)
            if DEBUG_OSM: st.sidebar.info(f"OSM (graph_from_polygon): Found {G.number_of_edges()} edges.")

            if G.number_of_edges() == 0:
                 if DEBUG_OSM: st.sidebar.warning("OSM (graph_from_polygon): No roads found. Trying bbox method...")
                 raise ValueError("No roads from graph_from_polygon") # Force fallback
            
            # If graph_from_polygon worked, we still project for consistent length/attributes
            G_proj = ox.project_graph(G)
            segments_gdf_proj = ox.graph_to_gdfs(G_proj, nodes=False, edges=True, fill_edge_geometry=True)
            segments_gdf = segments_gdf_proj.to_crs("EPSG:4326") # Back to WGS84 for storage
            if DEBUG_OSM: st.sidebar.info(f"OSM (graph_from_polygon): Converted to {len(segments_gdf)} GDF segments.")

        except Exception as e_poly:
            if DEBUG_OSM: st.sidebar.warning(f"OSM (graph_from_polygon) failed: {e_poly}. Falling back to bbox & clip.")
            # Fallback to BBOX method
            min_lon = map_boundary_polygon_shapely.bounds[0]
            min_lat = map_boundary_polygon_shapely.bounds[1]
            max_lon = map_boundary_polygon_shapely.bounds[2]
            max_lat = map_boundary_polygon_shapely.bounds[3]
            buffer = 0.008 # Slightly increased buffer for bbox, just in case
            if DEBUG_OSM:
                st.sidebar.info(f"OSM (BBox Fallback): Fetching for bbox: N={max_lat + buffer}, S={min_lat - buffer}, E={max_lon + buffer}, W={min_lon - buffer}")
            
            G_bbox = ox.graph_from_bbox(max_lat + buffer, min_lat - buffer, max_lon + buffer, min_lon - buffer, 
                                   network_type='drive_service',
                                   truncate_by_edge=True, retain_all=False, simplify=True)
            if DEBUG_OSM: st.sidebar.info(f"OSM (BBox Fallback): Found {G_bbox.number_of_edges()} edges before clipping.")

            if G_bbox.number_of_edges() == 0:
                if DEBUG_OSM: st.sidebar.warning("OSM (BBox Fallback): No roads found in bbox either.")
                return []
            
            G_proj = ox.project_graph(G_bbox)
            segments_gdf_proj = ox.graph_to_gdfs(G_proj, nodes=False, edges=True, fill_edge_geometry=True)
            if DEBUG_OSM:
                st.sidebar.info(f"OSM (BBox Fallback): {len(segments_gdf_proj)} segments from G_bbox before clip. CRS: {segments_gdf_proj.crs}")

            map_boundary_gdf_proj = gpd.GeoDataFrame([{'geometry': map_boundary_polygon_shapely}], crs="EPSG:4326").to_crs(segments_gdf_proj.crs)
            if DEBUG_OSM: st.sidebar.info(f"OSM (BBox Fallback): Clipping polygon CRS: {map_boundary_gdf_proj.crs}")

            clipped_segments_proj = gpd.clip(segments_gdf_proj, map_boundary_gdf_proj.iloc[0].geometry)
            if DEBUG_OSM: st.sidebar.info(f"OSM (BBox Fallback): Found {len(clipped_segments_proj)} segments after clipping.")
            
            if clipped_segments_proj.empty:
                if DEBUG_OSM: st.sidebar.warning("OSM (BBox Fallback): No segments after clipping either.")
                return []
            segments_gdf = clipped_segments_proj.to_crs("EPSG:4326")

        if segments_gdf.empty:
            if DEBUG_OSM: st.sidebar.warning("OSM: Resulting GDF is empty before processing attributes.")
            return []

        # Attribute processing (common for both methods if successful)
        columns_to_keep = ['osmid', 'name', 'highway', 'length', 'geometry']
        existing_cols_to_keep = [col for col in columns_to_keep if col in segments_gdf.columns]
        segments_gdf = segments_gdf[existing_cols_to_keep].copy() # Use .copy() to avoid SettingWithCopyWarning

        def get_capacity(highway_type_val):
            if isinstance(highway_type_val, list):
                for ht in highway_type_val:
                    if ht in CAPACITY_MAP:
                        return CAPACITY_MAP[ht]
                return DEFAULT_CAPACITY 
            return CAPACITY_MAP.get(highway_type_val, DEFAULT_CAPACITY)

        segments_gdf.loc[:, 'capacity'] = segments_gdf['highway'].apply(get_capacity)
        
        if 'osmid' not in segments_gdf.columns or segments_gdf['osmid'].isnull().any():
            segments_gdf.loc[:, 'osmid'] = [f"segment_idx_{i}" for i in range(len(segments_gdf))]
        else:
             segments_gdf.loc[:, 'osmid'] = segments_gdf['osmid'].apply(lambda x: x[0] if isinstance(x, list) else x if pd.notnull(x) else None)
             segments_gdf.loc[:, 'osmid'] = segments_gdf['osmid'].fillna(pd.Series([f"gen_segment_fill_{i}" for i in range(len(segments_gdf))]))

        # Ensure length is float and highway is string
        if 'length' in segments_gdf.columns:
            segments_gdf.loc[:, 'length'] = segments_gdf['length'].astype(float)
        if 'highway' in segments_gdf.columns:
            segments_gdf.loc[:, 'highway'] = segments_gdf['highway'].apply(lambda x: x[0] if isinstance(x, list) and x else str(x) if pd.notnull(x) else 'unknown')

        # Save to cache if we have segments
        if not segments_gdf.empty:
            segments_gdf.to_file(cache_file, driver="GPKG")
            if DEBUG_OSM: st.sidebar.info(f"OSM: Saved {len(segments_gdf)} segments to cache: {cache_file}")
        else:
            if DEBUG_OSM: st.sidebar.warning("OSM: No segments to save to cache.")
            return [] # Return empty if GDF became empty during attribute processing

        processed_segments = []
        for idx, row in segments_gdf.iterrows():
            coords = []
            if row.geometry and row.geometry.geom_type == 'LineString':
                coords = list(row.geometry.coords) 
            elif row.geometry and row.geometry.geom_type == 'MultiLineString':
                # Take the first LineString from MultiLineString, or handle as needed
                if len(row.geometry.geoms) > 0:
                    coords = list(row.geometry.geoms[0].coords)
                if DEBUG_OSM and idx < 5: st.sidebar.write(f"  OSM Seg {row.get('osmid')}: Converted MultiLineString to LineString for coords.")
            
            segment_id_val = str(row.get('osmid'))
            highway_type = str(row.get('highway', 'unknown'))
            capacity_val = int(row.get('capacity', DEFAULT_CAPACITY))
            length_val = float(row.get('length', 0.0))
            name_val = str(row.get('name', ''))

            # if DEBUG_OSM and idx < 2: # Log first 2 successfully processed new segments
            #    st.sidebar.write(f"  New Seg {segment_id_val}: HW={highway_type}, Cap={capacity_val}, Len={length_val:.2f}")

            processed_segments.append({
                'segment_id': segment_id_val,
                'coordinates': coords, 
                'name': name_val,
                'highway_type': highway_type,
                'length': length_val,
                'capacity': capacity_val
            })
        if DEBUG_OSM:
            st.sidebar.info(f"OSM: Processed {len(processed_segments)} new segments.")
        return processed_segments

    except Exception as e:
        if DEBUG_OSM:
            st.sidebar.error(f"OSM: General fail in fetch/process: {str(e)}")
            import traceback
            st.sidebar.text(traceback.format_exc())
        return []

def get_traffic_data(date_str, hour, project, base_osm_segments=None):
    """Get traffic data for a specific date and hour.
    Uses counter profiles for statistical summaries and
    simulates traffic on OpenStreetMap segments for map visualization.
    """
    # Ensure counter profiles are loaded if they are supposed to be the basis for stats
    # This check is important if `base_osm_segments` might be present but counters are not yet loaded.
    # However, load_profiles_for_counters is called early in show_dashboard.
    # A safeguard:
    if "counter_profiles" not in st.session_state or not st.session_state.counter_profiles:
        if "selected_counters" in st.session_state and st.session_state.selected_counters and project:
            if DEBUG_OSM: st.sidebar.info("OSM (get_traffic_data): Triggering profile load as profiles are missing.")
            load_profiles_for_counters(project) # project here is passed as an argument

    # Fallback if still no counter profiles after attempting load
    if "counter_profiles" not in st.session_state or not st.session_state.counter_profiles:
        if DEBUG_OSM:
            st.sidebar.warning("OSM (get_traffic_data): No counter profiles available. Stats will be zero. Map might show base roads.")
        # If no counter data, we can still try to show OSM roads with some default traffic
        simulated_osm_segments_default = []
        if base_osm_segments:
            time_factor_default = 0.3  # Generic off-peak factor
            if 7 <= hour <= 9 or 16 <= hour <= 18:
                time_factor_default = 0.6
            elif 10 <= hour <= 15:
                time_factor_default = 0.4

            for osm_segment in base_osm_segments:
                try:
                    seg_hash_rand = (
                        int(hashlib.md5(str(osm_segment["segment_id"]).encode()).hexdigest(), 16) % 50 + 10
                    ) / 100.0
                except Exception:
                    seg_hash_rand = np.random.uniform(0.1, 0.6)

                sim_vol = osm_segment["capacity"] * seg_hash_rand * time_factor_default
                sim_vol = min(sim_vol, osm_segment["capacity"] * 1.2)
                cong = (
                    min(1.0, sim_vol / osm_segment["capacity"])
                    if osm_segment["capacity"] > 0
                    else 0
                )
                folium_coords_def = (
                    [[pt[1], pt[0]] for pt in osm_segment["coordinates"]]
                    if osm_segment.get("coordinates")
                    else []
                )
                simulated_osm_segments_default.append(
                    {
                        "segment_id": osm_segment["segment_id"],
                        "coordinates": folium_coords_def,
                        "traffic_volume": int(sim_vol),
                        "congestion_level": cong,
                        "name": osm_segment.get("name", "N/A"),
                        "highway_type": osm_segment.get("highway_type", "N/A"),
                    }
                )

        return {
            "date": date_str,
            "hour": hour,
            "traffic_segments": simulated_osm_segments_default,
            "congestion_points": [],
            "stats": {"total_traffic": 0, "average_congestion": 0, "deliveries_count": 0},
        }

    # --- Proceed with counter-based stats and OSM simulation ---
    current_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    total_traffic_from_counters = 0
    weighted_congestion_sum_counters = 0
    num_primary_counters = 0
    num_secondary_counters = 0

    for profile_id, profile_meta in st.session_state.counter_profiles.items():
        vehicles = get_station_traffic(profile_meta, current_date_obj, hour)
        total_traffic_from_counters += vehicles
        primary_capacity = 500 
        secondary_capacity = 400
        station_capacity = primary_capacity if profile_meta.get('is_primary') else secondary_capacity
        
        congestion_for_station = min(1.0, vehicles / station_capacity) if station_capacity > 0 else 0
        
        if profile_meta.get('is_primary'):
            weighted_congestion_sum_counters += congestion_for_station * 1.5
            num_primary_counters +=1
        else:
            weighted_congestion_sum_counters += congestion_for_station
            num_secondary_counters += 1
    
    total_weight_counters = (num_primary_counters * 1.5) + num_secondary_counters
    average_congestion_from_counters = weighted_congestion_sum_counters / total_weight_counters if total_weight_counters > 0 else 0.0

    delivery_weight = 1.0
    if hour < 8 or hour > 16: delivery_weight = 0.3
    elif 10 <= hour <= 14: delivery_weight = 1.5
    deliveries_count_calc = int(5 * delivery_weight * (1 + 0.3 * average_congestion_from_counters))

    processed_osm_segments = []
    if base_osm_segments:
        # Overall busyness factor based on hour and counter data (already calculated)
        time_factor_base = 0.15 # Etwas niedrigere Basis, um den Spitzen deutlicher zu machen
        if 7 <= hour <= 9: # Morning peak
            time_factor_current_hour = time_factor_base + 0.65 + (average_congestion_from_counters * 0.4) # Stärkerer Peak, stärkerer Counter-Einfluss
        elif 16 <= hour <= 18: # Evening peak
            time_factor_current_hour = time_factor_base + 0.60 + (average_congestion_from_counters * 0.4) # Stärkerer Peak, stärkerer Counter-Einfluss
        elif 10 <= hour <= 15: # Mid-day
            time_factor_current_hour = time_factor_base + 0.25 + (average_congestion_from_counters * 0.25)
        else: # Off-peak
            time_factor_current_hour = time_factor_base + 0.1 + (average_congestion_from_counters * 0.15) # Auch Off-Peak etwas reaktiver
        time_factor_current_hour = max(0.05, min(time_factor_current_hour, 1.0)) # Obergrenze leicht auf 1.0 erhöht

        # Define base utilization factors per highway type (min_util, max_util)
        utilization_factors = {
            'motorway': (0.30, 0.85), 'trunk': (0.30, 0.85), 'primary': (0.30, 0.85),
            'secondary': (0.20, 0.70), 'tertiary': (0.20, 0.70),
            'motorway_link': (0.15, 0.60), 'trunk_link': (0.15, 0.60), 
            'primary_link': (0.15, 0.60), 'secondary_link': (0.15, 0.60), 'tertiary_link': (0.15, 0.60),
            'residential': (0.03, 0.25),
            'living_street': (0.01, 0.15),
            'service': (0.02, 0.20), 
            'unclassified': (0.1, 0.4), 'road': (0.1, 0.4),
            # Add other types if they appear and need specific handling
        }
        default_utilization = (0.05, 0.20) # Fallback for unknown types

        max_hourly_flow_residential = 30
        max_hourly_flow_service_living = 15 # For service and living_street

        for osm_segment in base_osm_segments:
            segment_capacity = osm_segment.get('capacity', DEFAULT_CAPACITY)
            if segment_capacity == 0: # Avoid division by zero for congestion
                segment_capacity = DEFAULT_CAPACITY # or some other small positive number

            min_util, max_util = utilization_factors.get(osm_segment['highway_type'], default_utilization)
            
            # Determine the typical utilization for this road type based on the hour's general busyness (time_factor_current_hour)
            hourly_driven_utilization = min_util + (max_util - min_util) * time_factor_current_hour

            try:
                # segment_hash_random_factor: 0.3 to 1.0 - segment specific base multiplier for inherent variability
                segment_hash_random_factor = (int(hashlib.md5(str(osm_segment['segment_id']).encode()).hexdigest(), 16) % 71 + 30) / 100.0  # Range 0.30 to 1.00
            except: 
                segment_hash_random_factor = np.random.uniform(0.6, 0.9) # Fallback
            
            # Apply this inherent variability to the hourly_driven_utilization
            # This means some streets of a type are naturally busier than others, scaled by the hour's demand
            final_utilization_rate = hourly_driven_utilization * segment_hash_random_factor
            final_utilization_rate = max(0.005, min(final_utilization_rate, 1.0)) # Clamp utilization

            simulated_volume = segment_capacity * final_utilization_rate

            # Specific override for very low capacity roads / low traffic road types
            current_highway_type = osm_segment['highway_type']
            if current_highway_type == 'residential':
                # Base flow for residential, scaled by its own random factor and the general hourly demand
                abs_flow = max_hourly_flow_residential * segment_hash_random_factor * time_factor_current_hour
                simulated_volume = min(simulated_volume, abs_flow) # Take the lower of the two calculated volumes
            elif current_highway_type in ['service', 'living_street', 'track', 'path']:
                abs_flow = max_hourly_flow_service_living * segment_hash_random_factor * time_factor_current_hour
                simulated_volume = min(simulated_volume, abs_flow)

            simulated_volume = min(simulated_volume, segment_capacity * 1.5) # Overall cap based on capacity
            simulated_volume = max(0, simulated_volume) # Ensure non-negative volume
            
            congestion = min(1.0, simulated_volume / segment_capacity) if segment_capacity > 0 else 0.0
            
            folium_coords = []
            if osm_segment.get('coordinates') and isinstance(osm_segment['coordinates'], list):
                 folium_coords = [[pt[1], pt[0]] for pt in osm_segment['coordinates'] if isinstance(pt, (list, tuple)) and len(pt) == 2]

            processed_osm_segments.append({
                "segment_id": osm_segment['segment_id'],
                "coordinates": folium_coords, 
                "traffic_volume": int(simulated_volume),
                "congestion_level": congestion,
                "name": osm_segment.get('name', 'N/A'),
                "highway_type": current_highway_type,
                "capacity": int(segment_capacity) # Pass through actual capacity used
            })
    
    if DEBUG_OSM and processed_osm_segments: # Add this block for debugging
        st.sidebar.markdown("--- DEBUG: Congestion Levels ---")
        st.sidebar.write(f"Date: {date_str}, Hour: {hour}")
        for i, seg in enumerate(processed_osm_segments[:5]): # Log first 5 segments
            # st.sidebar.write(f"Seg {seg['segment_id']}: Vol={seg['traffic_volume']}, Cap={seg['capacity']}, Cong={seg['congestion_level']:.2f}") # Auskommentiert wegen KeyError
            pass # Placeholder if a log was intended here and is now commented out
        st.sidebar.markdown("-----------------------------")

    return {
        "date": date_str,
        "hour": hour,
        "traffic_segments": processed_osm_segments,
        "congestion_points": [], # generate_congestion_points(processed_osm_segments) if adapted
        "stats": {
            "total_traffic": int(total_traffic_from_counters),
            "average_congestion": average_congestion_from_counters,
            "deliveries_count": deliveries_count_calc
        }
    }

def get_station_traffic(profile_meta, date_obj, hour):
    """Get traffic count for a specific station, date and hour from its profile data."""
    if 'data' not in profile_meta:
        return 0 
    data_df = profile_meta['data']
    weekday = date_obj.strftime("%A")
    month = date_obj.month
    
    filtered = data_df[(data_df['weekday'] == weekday) & (data_df['month'] == month) & (data_df['hour'] == hour)]
    if not filtered.empty:
        return int(round(filtered.iloc[0]['vehicles']))
    else:
        fallback = data_df[(data_df['month'] == month) & (data_df['hour'] == hour)]
        return int(round(fallback['vehicles'].mean())) if not fallback.empty else 0

def generate_traffic_segments(date_str, hour):
    """
    DEPRECATED / Placeholder: Original function to generate mock traffic segments.
    This is now replaced by fetching OSM data and simulating traffic on it.
    Kept for reference or if direct mock data is ever needed without OSM.
    """
    segments = []
    # try:
    #     # Centroid of the map (Zurich)
    #     zurich_center = [8.541694, 47.376888]
        
    #     # Generate segments from / to each counting station
    #     if "counter_profiles" in st.session_state and st.session_state.counter_profiles: # Check if profiles exist
    #         for profile_id, profile in st.session_state.counter_profiles.items():
    #             # Skip if no coordinates
    #             if 'coordinates' not in profile or not profile['coordinates']:
    #                 st.write(f"Debug: Profile missing coordinates: {profile_id}")
    #                 continue
                    
    #             # Get coordinates for this station
    #             station_coords = profile['coordinates']
    #             # Convert from [lat, lon] to [lon, lat] format
    #             station_coords = [station_coords[1], station_coords[0]]
                
    #             # Get traffic volume
    #             current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    #             traffic = get_station_traffic(profile, current_date, hour)
                
    #             # Create a segment from center to station
    #             congestion = min(1.0, traffic / (400 if not profile.get('is_primary', False) else 500))
                
    #             # Create the segment
    #             segment = {
    #                 "segment_id": f"segment_{profile_id}",
    #                 "start_node": "zurich_center",
    #                 "end_node": profile_id,
    #                 "length": 2000,  # Example length in meters
    #                 "speed_limit": 50,
    #                 "traffic_volume": traffic,
    #                 "congestion_level": congestion,
    #                 "coordinates": [
    #                     zurich_center,
    #                     station_coords
    #                 ]
    #             }
                
    #             segments.append(segment)
                                
    #             # Create variation segment if this is a primary station (for visual interest)
    #             if profile.get('is_primary', False):
    #                 # Create a segment that detours a bit
    #                 midpoint = [
    #                     (zurich_center[0] + station_coords[0]) / 2 + 0.005,
    #                     (zurich_center[1] + station_coords[1]) / 2 - 0.005
    #                 ]
                    
    #                 segment_alt = {
    #                     "segment_id": f"segment_{profile_id}_alt",
    #                     "start_node": "zurich_center",
    #                     "end_node": profile_id,
    #                     "length": 2500,  # Longer route
    #                     "speed_limit": 50,
    #                     "traffic_volume": int(traffic * 0.7),  # Less traffic on alt route
    #                     "congestion_level": congestion * 0.7,
    #                     "coordinates": [
    #                         zurich_center,
    #                         midpoint,
    #                         station_coords
    #                     ]
    #                 }
                    
    #                 segments.append(segment_alt)
    #     else:
    #         if st.session_state.get("debug_mode", False):
    #              st.write("Debug (generate_traffic_segments): No counter_profiles in session_state to generate segments from.")

    # except Exception as e:
    #     st.error(f"Error generating traffic segments: {str(e)}")
    #     import traceback
    #     st.write(f"Debug: Error details: {traceback.format_exc()}")
    
    return segments

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