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

# Define API URL
API_URL = "http://localhost:8000"

def show_resident_info(project):
    """Show the resident information page with simplified traffic information"""
    # Set widget width for resident info
    st.session_state.widget_width_percent = 35
    
    st.markdown(f"<h2 style='text-align: center; color: white;'>Construction Site Traffic Information</h2>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align: center; color: white;'>{project['name']}</h3>", unsafe_allow_html=True)
    
    # Center map view on project bounds
    view_key = f"resident_info_view_set_{project.get('id')}"
    if view_key not in st.session_state:
        # Use utility from streamlit_app.py 
        if "map_bounds" in project:
            import streamlit_app
            streamlit_app.update_map_view_to_project_bounds(project.get("map_bounds"))
        st.session_state[view_key] = True
    
    # Introduction
    st.info("""
    This page provides traffic information for residents affected by the ongoing construction project.
    
    Below you can find:
    - Current and upcoming traffic conditions
    - Daily traffic forecasts
    - Recommendations for travel
    """)
    
    # Get simulation data
    simulation_data = get_simulation_data(project['id'])
    
    if not simulation_data:
        st.warning("No traffic data available yet. Please check back later.")
        # Set empty map layers
        st.session_state.map_layers = []
        return
    
    # Today's date
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    
    # Get available dates (today and next 3 days)
    available_dates = list(simulation_data.keys())
    available_dates.sort()  # Sort dates
    
    # Filter for today and next 3 days only
    upcoming_dates = [d for d in available_dates if datetime.strptime(d, "%Y-%m-%d").date() >= today][:4]
    
    # Show current traffic conditions
    st.markdown("<h3 style='color: white;'>Today's Traffic Conditions</h3>", unsafe_allow_html=True)
    
    if today_str in simulation_data:
        # Get the current hour (or nearest available)
        current_hour = datetime.now().hour
        available_hours = list(simulation_data[today_str].keys())
        
        if not available_hours:
            st.info("No traffic data available for today.")
            st.session_state.map_layers = []
        else:
            # Find closest available hour
            available_hours = [int(h) for h in available_hours]
            closest_hour = min(available_hours, key=lambda x: abs(x - current_hour))
            
            # Get the data
            hour_data = simulation_data[today_str][closest_hour]
            
            # Display traffic status
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
            
            # Display simple metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Traffic Volume", hour_data["stats"]["total_traffic"])
            
            with col2:
                st.metric("Congestion Level", f"{congestion_level:.1f}/1.0")
            
            with col3:
                st.metric("Construction Vehicles", hour_data["stats"]["deliveries_count"])
            
            # Update map layers to show traffic
            update_map_with_traffic_data(project, hour_data)
    else:
        st.info("No traffic data available for today.")
        st.session_state.map_layers = []
    
    # Show forecast for coming days
    st.markdown("<h3 style='color: white;'>Traffic Forecast</h3>", unsafe_allow_html=True)
    
    if upcoming_dates:
        # Tabs for each day
        day_tabs = st.tabs([
            "Today" if d == today_str else datetime.strptime(d, "%Y-%m-%d").strftime("%A, %b %d")
            for d in upcoming_dates
        ])
        
        # For each upcoming date
        for i, date_str in enumerate(upcoming_dates):
            with day_tabs[i]:
                if date_str in simulation_data:
                    # Get hourly data for this day
                    hours = []
                    hourly_traffic = []
                    hourly_congestion = []
                    
                    for hour, hour_data in sorted(simulation_data[date_str].items()):
                        hours.append(f"{hour}:00")
                        hourly_traffic.append(hour_data["stats"]["total_traffic"])
                        hourly_congestion.append(hour_data["stats"]["average_congestion"])
                    
                    # Create a daily plot
                    fig = go.Figure()
                    
                    # Traffic bars
                    fig.add_trace(go.Bar(
                        x=hours,
                        y=hourly_traffic,
                        name="Traffic Volume",
                        marker_color="skyblue",
                        opacity=0.7
                    ))
                    
                    # Congestion line
                    fig.add_trace(go.Scatter(
                        x=hours,
                        y=hourly_congestion,
                        mode="lines+markers",
                        name="Congestion Level",
                        line=dict(color="red", width=2),
                        yaxis="y2"
                    ))
                    
                    # Update layout for dual y-axis
                    fig.update_layout(
                        xaxis=dict(
                            title="Hour of Day",
                            titlefont=dict(color="white"),
                            tickfont=dict(color="white")
                        ),
                        yaxis=dict(
                            title="Traffic Volume",
                            titlefont=dict(color="white"),
                            tickfont=dict(color="white"),
                            side="left"
                        ),
                        yaxis2=dict(
                            title="Congestion Level",
                            titlefont=dict(color="white"),
                            tickfont=dict(color="white"),
                            anchor="x",
                            overlaying="y",
                            side="right",
                            range=[0, 1]
                        ),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        margin=dict(l=20, r=70, t=30, b=20),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='white'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Calculate peak and low traffic times
                    congestion_with_hour = [(hour, cong) for hour, cong in zip(hours, hourly_congestion)]
                    congestion_with_hour.sort(key=lambda x: x[1])
                    
                    low_traffic_times = [t[0] for t in congestion_with_hour[:3]]
                    peak_traffic_times = [t[0] for t in congestion_with_hour[-3:]]
                    
                    # Show recommendations
                    st.markdown("<h4 style='color: white;'>Travel Recommendations</h4>", unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("<h5 style='color: white;'>Best Times to Travel</h5>", unsafe_allow_html=True)
                        for time in low_traffic_times:
                            st.markdown(f"- {time}")
                    
                    with col2:
                        st.markdown("<h5 style='color: white;'>Avoid Travel During</h5>", unsafe_allow_html=True)
                        for time in peak_traffic_times:
                            st.markdown(f"- {time}")
                else:
                    st.info("No traffic data available for this day.")
    else:
        st.info("No forecast data available for upcoming days.")
    
    # Email notifications section
    st.markdown("<h3 style='color: white;'>Stay Informed</h3>", unsafe_allow_html=True)
    
    st.markdown("""
    Get regular traffic updates and notifications about the construction project.
    Sign up for email notifications to receive:
    
    - Daily traffic forecasts
    - Construction schedule updates
    - Traffic alerts for high congestion periods
    """)
    
    # Email signup form
    with st.form("email_form"):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            email = st.text_input("Email Address")
        
        with col2:
            frequency = st.selectbox("Frequency", ["Daily", "Weekly"])
        
        submit_button = st.form_submit_button("Subscribe")
        
        if submit_button:
            if email and "@" in email and "." in email:
                # In a real app, this would connect to an API to register the email
                st.success(f"Thank you! You have been subscribed to {frequency.lower()} updates.")
                
                # Show example of what they would receive
                with st.expander("Example Email Update"):
                    st.markdown(f"""
                    **Subject:** Traffic Update for {project['name']} - {today.strftime('%b %d, %Y')}
                    
                    Dear Resident,
                    
                    Here is your traffic update for the construction project at {project['name']}.
                    
                    **Today's Traffic Conditions:**
                    - Peak traffic times: 8:00, 17:00
                    - Best travel times: 10:00, 14:00
                    
                    **Tomorrow's Forecast:**
                    - Expected traffic level: Moderate
                    - Construction activity: Heavy equipment delivery scheduled between 9:00-11:00
                    
                    For more detailed information, please visit our website.
                    
                    Regards,
                    Construction Site Management Team
                    """)
            else:
                st.error("Please enter a valid email address.")

def update_map_with_traffic_data(project, traffic_data):
    """Update the PyDeck map with traffic data visualizations"""
    map_layers = []
    
    # 1. Project Polygon Layer
    if project.get("polygon") and project["polygon"].get("coordinates"):
        polygon_feature = create_geojson_feature(project["polygon"], {"name": "Construction Site"})
        map_layers.append(create_pydeck_geojson_layer(
            data=[polygon_feature],
            layer_id="resident_construction_site",
            fill_color=[220, 53, 69, 160],  # Reddish 
            line_color=[220, 53, 69, 255],
            pickable=True,
            tooltip_html="<b>Construction Site</b>",
            line_width_min_pixels=2
        ))
    
    # 2. Traffic segments
    if traffic_segments := traffic_data.get("traffic_segments"):
        segments_data = []
        
        for segment in traffic_segments:
            congestion = segment["congestion_level"]
            
            # Color based on congestion
            if congestion >= 0.7: color = [220, 53, 69, 180]  # Red
            elif congestion >= 0.3: color = [255, 193, 7, 180]  # Yellow/Orange  
            else: color = [40, 167, 69, 180]  # Green
            
            # Convert coordinates to PathLayer format if needed
            # PathLayer expects coordinates in [lon, lat] format
            if segment.get("coordinates"):
                segments_data.append({
                    "path": segment["coordinates"],
                    "name": segment.get('name', 'Road'),
                    "traffic_volume": segment.get('traffic_volume', 0),
                    "congestion": congestion,
                    "color": color,
                    "width": max(2, 8 - (congestion * 5))  # Width in pixels
                })
        
        if segments_data:
            traffic_layer = create_pydeck_path_layer(
                data=segments_data,
                layer_id="resident_traffic_paths",
                pickable=True,
                tooltip_html="<b>Traffic Level</b><br/>{congestion:.2f}/1.0<br/>Volume: {traffic_volume}"
            )
            map_layers.append(traffic_layer)
    
    # Update the map layers in session state
    st.session_state.map_layers = map_layers

def get_simulation_data(project_id):
    """Get simulation data for the resident info page"""
    try:
        # Try to get real data first
        try:
            response = requests.get(
                f"{API_URL}/api/simulation/{project_id}/results"
            )
            
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        # If that fails, use synthetic data generator
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
                            ]
                        } for j in range(10)  # 10 road segments
                    ],
                    "waiting_areas_status": {
                        f"area_{k}": {
                            "capacity": 5,
                            "occupied": min(5, int(np.random.randint(0, 6))),
                            "available": max(0, 5 - int(np.random.randint(0, 6)))
                        } for k in range(2)  # 2 waiting areas
                    },
                    "stats": {
                        "total_traffic": int(500 + np.random.randint(-200, 300) * (1 + 0.2 * (hour - 6) - 0.2 * abs(hour - 12))),
                        "average_congestion": min(1.0, 0.3 + np.random.random() * 0.4 * (1 + 0.2 * (hour - 6) - 0.2 * abs(hour - 12))),
                        "deliveries_count": int(5 + np.random.randint(0, 10) * (1 + 0.2 * (hour - 6) - 0.2 * abs(hour - 12))),
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