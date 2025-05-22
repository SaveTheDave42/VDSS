import streamlit as st
import pandas as pd
import json
import requests
import os
from datetime import datetime, date, timedelta
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from utils.map_utils import (
    update_map_view_to_project_bounds,
    create_geojson_feature,
    create_pydeck_geojson_layer,
    create_pydeck_path_layer,
    create_pydeck_access_route_layer,
)
from utils.dashoboard_utils import build_segments_for_hour, build_hourly_layer_cache, render_hourly_traffic_component, get_week_options, get_days_in_week
from utils.custom_styles import apply_chart_styling
import streamlit.components.v1 as components
import pages.dashboard as _dash

# Define API URL
API_URL = "http://localhost:8000"

def show_resident_info(project):
    """Show the resident information page with simplified traffic information"""
    # Set widget width for resident info
    st.session_state.widget_width_percent = 35
    
    # Apply chart styling for this page
    apply_chart_styling()
    
    st.markdown(f"<h2 style='text-align: center;'>Construction Site Traffic Information</h2>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align: center;'>{project['name']}</h3>", unsafe_allow_html=True)
    
    # Center map view on project bounds
    view_key = f"resident_info_view_set_{project.get('id')}"
    if view_key not in st.session_state:
        if "map_bounds" in project:
            update_map_view_to_project_bounds(project.get("map_bounds"))
        st.session_state[view_key] = True
    
    # ------------------------------------------------------------------
    # We no longer rely on simulation results from the backend. Instead we
    # reuse the same on-the-fly OSM simulation that the dashboard uses.
    # ------------------------------------------------------------------

    # Pre-compute base OSM segments once
    base_osm_segments = _dash.get_base_osm_segments(project)
    if not base_osm_segments:
        st.warning("No traffic data available yet. Please check back later.")
        st.session_state.map_layers = []
        return
    
    # 1. Select day dropdown (similar to dashboard)
    # Determine if today is Saturday (5) or Sunday (6)
    today = date.today()
    is_weekend = today.weekday() >= 5  # If today is Saturday or Sunday

    # Get week options
    week_options = get_week_options()
    today_cal = date.today().isocalendar()
    
    # Default to current week, or next week if it's the weekend
    default_week_index = next(
        (i for i, option in enumerate(week_options) 
         if (option["year"] == today_cal[0] and option["week"] == (today_cal[1] + 1 if is_weekend else today_cal[1]))), 
        len(week_options) // 2
    )
    
    current_week_key = f"current_resident_week_{project.get('id', 'default')}"
    if current_week_key not in st.session_state:
        st.session_state[current_week_key] = None
    
    selected_week_dict = st.selectbox("Select Week", options=week_options, index=default_week_index, 
                                      format_func=lambda x: x["label"], key="week_resident_ctrl")
    
    selected_week_id = f"{selected_week_dict['year']}_{selected_week_dict['week']}"
    if st.session_state[current_week_key] != selected_week_id:
        st.session_state[current_week_key] = selected_week_id
    
    # Get delivery days from project
    delivery_days_names = project.get("delivery_days", ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"])
    days_in_week = get_days_in_week(selected_week_dict["year"], selected_week_dict["week"], delivery_days_names)
    
    # Default to today if it's in the list, otherwise first day of the week
    default_day_index = next((i for i, d in enumerate(days_in_week) if d == today), 0)
    
    # --- Unified Date Selector -------------------------------------------------
    # Determine selectable range from project start/end dates (if provided)
    min_date, max_date = date(2024, 9, 5), date(2025, 10, 30)
    if "dates" in project:
        if "start_date" in project["dates"]:
            min_date = datetime.fromisoformat(project["dates"]["start_date"]).date()
        if "end_date" in project["dates"]:
            max_date = datetime.fromisoformat(project["dates"]["end_date"]).date()

    selected_date_for_map = st.date_input(
        "Date",
        value=date.today(),
        min_value=min_date,
        max_value=max_date,
        key="date_resident_ctrl",
    )

    selected_date_str = selected_date_for_map.strftime("%Y-%m-%d")
    
    # 2. Traffic condition warning panel (Daily Traffic Conditions)
    st.markdown("<h3>Daily Traffic Conditions</h3>", unsafe_allow_html=True)
    
    # ---- Obtain hourly traffic data via dashboard logic ----
    delivery_hours_cfg = project.get("delivery_hours", {})
    dh_start = delivery_hours_cfg.get("start", "06:00")
    dh_end   = delivery_hours_cfg.get("end", "18:00")

    start_hour_int = int(dh_start.split(":")[0]) if ":" in dh_start else 6
    end_hour_int   = int(dh_end.split(":")[0])   if ":" in dh_end else 18

    available_hours = list(range(start_hour_int, end_hour_int+1))

    current_hour = datetime.now().hour
    closest_hour = min(available_hours, key=lambda x: abs(x - current_hour))

    hour_data = _dash.get_traffic_data(selected_date_str, closest_hour, project, base_osm_segments)
    if not hour_data:
        hour_data = {"traffic_segments": [], "stats": {"total_traffic": 0, "average_congestion": 0, "deliveries_count": 0}}
    
    # Display traffic status
    hour_data["stats"]["average_congestion"] = hour_data["stats"].get("average_congestion", 0)
    congestion_level = hour_data["stats"]["average_congestion"]
    
    if congestion_level < 0.3:
        status = "Low Traffic"
        color = "green"
    elif congestion_level < 0.7:
        status = "Moderate Traffic"
        color = "orange"
    else:
        status = "Heavy Traffic"
        color = "red"
    
    # Show status card
    st.markdown(f"""
    <div style="padding: 20px; border-radius: 10px; background-color: {color}; color: white; text-align: center; margin-bottom: 20px;">
        <h3 style="margin: 0;">{status}</h3>
        <p style="margin: 10px 0 0 0;">Current traffic level around the construction site</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Hour slider to select which hour to visualise
    selected_hour_for_map = st.slider(
        "Hour",
        min_value=start_hour_int,
        max_value=end_hour_int,
        value=closest_hour,
        step=1,
        format="%d:00",
        key=f"resident_hour_slider_{selected_date_str}"
    )
    
    # Get bounds for rendering the map correctly
    if "map_view_state" in st.session_state:
        initial_view_state = {
            "longitude": st.session_state.map_view_state.longitude,
            "latitude": st.session_state.map_view_state.latitude,
            "zoom": st.session_state.map_view_state.zoom,
            "pitch": 0,
            "bearing": 0
        }
    else:
        # Default view state if not set
        initial_view_state = {
            "longitude": 8.5417, 
            "latitude": 47.3769, 
            "zoom": 12,
            "pitch": 0,
            "bearing": 0
        }
    
    # Helper function to get traffic data for a specific hour
    def get_hour_data(date_str, hour_int):
        return _dash.get_traffic_data(date_str, hour_int, project, base_osm_segments)
    
    # ---- Prepare map layers like dashboard.py ----
    layers_for_pydeck = []
    
    # 1. Project Polygon Layer
    project_polygon_data = project.get("polygon", {})
    if "coordinates" in project_polygon_data and project_polygon_data["coordinates"]:
        polygon_feature = create_geojson_feature(project_polygon_data, {"name": "Construction Site"})
        polygon_layer = create_pydeck_geojson_layer(
            data=[polygon_feature], 
            layer_id="resident_project_polygon", 
            fill_color=[70, 130, 180, 160], 
            line_color=[70, 130, 180, 160],
            get_line_width=20,
            line_width_min_pixels=2,
            pickable=True, 
            tooltip_html="<b>Construction Site</b><br/>{properties.name}"
        )
        layers_for_pydeck.append(polygon_layer)
    
    # 1b. Access Route Layer (violet, wider)
    if project.get("access_routes"):
        access_route_layer = create_pydeck_access_route_layer(
            project["access_routes"],
            layer_id="resident_access_route",
        )
        if access_route_layer:
            layers_for_pydeck.append(access_route_layer)
    
    # 2. Traffic Segments Layer
    # Get the traffic data for the selected hour
    current_traffic_data = get_hour_data(selected_date_str, selected_hour_for_map)
    
    if current_traffic_data and "traffic_segments" in current_traffic_data:
        segments_data = []
        
        for segment in current_traffic_data["traffic_segments"]:
            congestion = segment.get("congestion_level", 0)
            # Colour depending on congestion
            if congestion >= 0.7:
                color = [220, 53, 69, 180]  # Red
            elif congestion >= 0.3:
                color = [255, 193, 7, 180]  # Yellow/Orange
            else:
                color = [40, 167, 69, 180]  # Green
            
            segments_data.append({
                "path": segment.get("coordinates", []),
                "name": segment.get("name", "Road"),
                "highway_type": segment.get("highway_type", "Unknown"),
                "traffic_volume": segment.get("traffic_volume", 0),
                "congestion": congestion,
                "color": color,
                # PathLayer width in px – narrower when high congestion
                "width": max(2, 8 - (congestion * 5))
            })
        
        if segments_data:
            traffic_layer = create_pydeck_path_layer(
                data=segments_data,
                layer_id="resident_traffic_paths",
                pickable=True,
                tooltip_html="<b>{name}</b><br/>Volume: {traffic_volume}<br/>Congestion: {congestion:.2f}"
            )
            layers_for_pydeck.append(traffic_layer)
    
    # Update map layers in session state
    st.session_state.map_layers = layers_for_pydeck
    
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # --- Fine-tune just the necessary element spacing ----------------------------------
    st.markdown("""
    <style>
        /* Push first metric row a bit downward so it doesn't hug the top edge */
        div[data-testid='stMetric']:first-of-type {
            margin-top: 12px !important;
        }

        /* Reduce extra gap before the hour slider */
        .stSlider [data-baseweb='slider'] {
            margin-top: 4px !important;
        }
    </style>
    """, unsafe_allow_html=True)

def get_simulation_data(project_id):
    """Get simulation data for the resident info page"""
    try:
        # Versuchen, echte Daten von der API zu erhalten
        api_result = None
        try:
            response = requests.get(
                f"{API_URL}/api/simulation/{project_id}/results"
            )
            
            if response.status_code == 200 and response.text and response.text != "null":
                api_result = response.json()
                if api_result:
                    return api_result
        except Exception as e:
            print(f"API request failed: {str(e)}")  # Log to console instead of UI
        
        # Wenn API-Anfrage fehlschlägt oder leere Daten zurückgibt, synthetische Daten erzeugen
        st.info("Using synthetic data for visualization (API data not available).")
        synthetic_data = {}
        
        # Generate data for the last 7 days and next 7 days
        today = date.today()
        
        for i in range(-3, 4):  # -3 to +3 days
            current_date = today + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            
            synthetic_data[date_str] = {}
            
            # Generate hourly data for each day (6am to 6pm)
            for hour in range(6, 19):
                # Create hourly data with random values
                hourly_data = {
                    "id": f"{project_id}_{date_str}_{hour}",
                    "project_id": project_id,
                    "execution_time": datetime.now().isoformat(),
                    "traffic_segments": [
                        {
                            "segment_id": f"segment_{j}",
                            "start_node": f"node_a_{j}",
                            "end_node": f"node_b_{j}",
                            "length": 100 + j * 50,
                            "speed_limit": 50,
                            "traffic_volume": int(50 + np.random.randint(0, 100) * (1 + 0.5 * (j % 3))),
                            "congestion_level": min(1.0, 0.2 + np.random.random() * 0.6 * (1 + 0.2 * (j % 3))),
                            "coordinates": [
                                # Generate some coordinates that spread out from a center point
                                [8.54 + (j % 3) * 0.005, 47.375 + (j // 3) * 0.005],
                                [8.54 + (j % 3) * 0.005 + 0.002, 47.375 + (j // 3) * 0.005 + 0.002]
                            ],
                            "name": f"Road {j}"
                        } for j in range(10)  # 10 road segments
                    ],
                    "waiting_areas_status": {
                        "area_0": {
                            "capacity": 10,
                            "occupied": min(10, int(np.random.randint(0, 8))),
                            "available": max(0, 10 - int(np.random.randint(0, 8)))
                        }
                    },
                    "stats": {
                        "total_traffic": int(500 + np.random.randint(-100, 200) * (1 + 0.2 * (hour - 6) - 0.2 * abs(hour - 12))),
                        "average_congestion": min(0.9, max(0.1, 0.3 + np.random.random() * 0.4 * (1 + 0.2 * (hour - 6) - 0.2 * abs(hour - 12)))),
                        "deliveries_count": int(3 + np.random.randint(0, 8) * (1 + 0.2 * (hour - 6) - 0.2 * abs(hour - 12))),
                        "construction_phase": "Phase 1"
                    }
                }
                
                synthetic_data[date_str][hour] = hourly_data
        
        return synthetic_data
    
    except Exception as e:
        st.error(f"Error getting simulation data: {str(e)}")
        return None

def create_geojson_feature(geometry, properties=None):
    '''Wraps a GeoJSON geometry into a GeoJSON Feature structure.'''
    if properties is None: properties = {}
    return {"type": "Feature", "geometry": geometry, "properties": properties}

def create_pydeck_geojson_layer(
    data, layer_id, fill_color=[255, 255, 255, 100], line_color=[0, 0, 0, 200],
    line_width_min_pixels=1, get_line_width=10, opacity=0.5, stroked=True, filled=True,
    extruded=False, wireframe=True, pickable=False, tooltip_html=None, auto_highlight=True,
    highlight_color=[0, 0, 128, 128]
):
    '''Creates a PyDeck GeoJsonLayer with specified parameters.'''
    layer_config = {
        "id": layer_id, "data": data, "opacity": opacity, "stroked": stroked, "filled": filled,
        "extruded": extruded, "wireframe": wireframe, "get_fill_color": fill_color,
        "get_line_color": line_color, "get_line_width": get_line_width,
        "line_width_min_pixels": line_width_min_pixels, "pickable": pickable,
        "auto_highlight": auto_highlight, "highlight_color": highlight_color
    }
    if tooltip_html and pickable: layer_config["tooltip"] = {"html": tooltip_html}
    return pdk.Layer("GeoJsonLayer", **layer_config)

def create_pydeck_path_layer(
    data, layer_id, get_path="path", get_color="color", get_width="width",
    width_scale=1, width_min_pixels=2, width_max_pixels=10, pickable=False, tooltip_html=None,
    auto_highlight=True, highlight_color=[0,0,128,128]
):
    '''Creates a PyDeck PathLayer.'''
    layer_config = {
        "id": layer_id, "data": data, "pickable": pickable, "get_path": get_path,
        "get_color": get_color, "get_width": get_width, "width_scale": width_scale,
        "width_min_pixels": width_min_pixels, "width_max_pixels": width_max_pixels,
        "auto_highlight": auto_highlight, "highlight_color": highlight_color
    }
    if tooltip_html and pickable: layer_config["tooltip"] = {"html": tooltip_html}
    return pdk.Layer("PathLayer", **layer_config) 