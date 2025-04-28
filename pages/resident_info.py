import streamlit as st
import pandas as pd
import json
import requests
import os
from datetime import datetime, date, timedelta
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import numpy as np

# Define API URL
API_URL = "http://localhost:8000"

def show_resident_info(project):
    """Show the resident information page with simplified traffic information"""
    st.markdown(f"## Construction Site Traffic Information: {project['name']}")
    
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
    st.markdown("## Today's Traffic Conditions")
    
    if today_str in simulation_data:
        # Get the current hour (or nearest available)
        current_hour = datetime.now().hour
        available_hours = list(simulation_data[today_str].keys())
        
        if not available_hours:
            st.info("No traffic data available for today.")
        else:
            # Find closest available hour
            available_hours.sort()
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
            
            # Create a simplified traffic map
            st.markdown("### Traffic Map")
            
            # Extract coordinates for map centering
            polygon_coords = project["polygon"]["coordinates"][0]
            centroid_lon = sum(p[0] for p in polygon_coords) / len(polygon_coords)
            centroid_lat = sum(p[1] for p in polygon_coords) / len(polygon_coords)
            
            # Create map
            m = folium.Map(location=[centroid_lat, centroid_lon], zoom_start=14)
            
            # Add construction site polygon
            folium.GeoJson(
                project["polygon"],
                name="Construction Site",
                style_function=lambda x: {"fillColor": "red", "color": "red", "weight": 2, "fillOpacity": 0.4}
            ).add_to(m)
            
            # Add traffic segments with simplified colors
            traffic_segments = hour_data["time_steps"][0]["traffic_segments"]
            
            for segment in traffic_segments:
                # Calculate color based on congestion
                congestion = segment["congestion_level"]
                
                if congestion < 0.3:
                    color = "green"
                elif congestion < 0.7:
                    color = "orange"
                else:
                    color = "red"
                
                # Create simple popup content
                popup_content = f"Traffic Level: {congestion:.1f}/1.0"
                
                # Create line
                points = [(coord[1], coord[0]) for coord in segment["coordinates"]]
                
                folium.PolyLine(
                    points,
                    color=color,
                    weight=5,
                    opacity=0.8,
                    popup=folium.Popup(popup_content, max_width=200)
                ).add_to(m)
            
            # Add legend
            legend_html = """
            <div style="position: fixed; bottom: 50px; left: 50px; z-index:1000; padding: 10px; background-color: white; border: 2px solid grey; border-radius: 5px">
            <h4>Traffic Level</h4>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="background-color: green; width: 20px; height: 5px; margin-right: 5px;"></div>
                <div>Low</div>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="background-color: orange; width: 20px; height: 5px; margin-right: 5px;"></div>
                <div>Medium</div>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="background-color: red; width: 20px; height: 5px; margin-right: 5px;"></div>
                <div>High</div>
            </div>
            </div>
            """
            
            m.get_root().html.add_child(folium.Element(legend_html))
            
            # Display the map
            folium_static(m)
    else:
        st.info("No traffic data available for today.")
    
    # Show forecast for coming days
    st.markdown("## Traffic Forecast")
    
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
                            titlefont=dict(color="black"),
                            tickfont=dict(color="black")
                        ),
                        yaxis=dict(
                            title="Traffic Volume",
                            titlefont=dict(color="blue"),
                            tickfont=dict(color="blue"),
                            side="left"
                        ),
                        yaxis2=dict(
                            title="Congestion Level",
                            titlefont=dict(color="red"),
                            tickfont=dict(color="red"),
                            anchor="x",
                            overlaying="y",
                            side="right",
                            range=[0, 1]
                        ),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        margin=dict(l=20, r=70, t=30, b=20),
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Calculate peak and low traffic times
                    congestion_with_hour = [(hour, cong) for hour, cong in zip(hours, hourly_congestion)]
                    congestion_with_hour.sort(key=lambda x: x[1])
                    
                    low_traffic_times = [t[0] for t in congestion_with_hour[:3]]
                    peak_traffic_times = [t[0] for t in congestion_with_hour[-3:]]
                    
                    # Show recommendations
                    st.markdown("### Travel Recommendations")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### Best Times to Travel")
                        for time in low_traffic_times:
                            st.markdown(f"- {time}")
                    
                    with col2:
                        st.markdown("#### Avoid Travel During")
                        for time in peak_traffic_times:
                            st.markdown(f"- {time}")
                else:
                    st.info("No traffic data available for this day.")
    else:
        st.info("No forecast data available for upcoming days.")
    
    # Email notifications section
    st.markdown("## Stay Informed")
    
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
        
        # If that fails, use the same synthetic data generator as in dashboard.py
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
                    "time_steps": [
                        {
                            "time": f"{date_str}T{hour:02d}:00:00",
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
                            }
                        }
                    ],
                    "traffic_volumes": {
                        f"segment_{j}": int(50 + np.random.randint(0, 100) * (1 + 0.5 * (j % 3)))
                        for j in range(10)
                    },
                    "congestion_points": [
                        {
                            "segment_id": f"segment_{j}",
                            "congestion_level": 0.8 + np.random.random() * 0.2,
                            "coordinates": [
                                [8.54 + (j % 3) * 0.005, 47.375 + (j // 3) * 0.005],
                                [8.54 + (j % 3) * 0.005 + 0.002, 47.375 + (j // 3) * 0.005 + 0.002]
                            ]
                        } for j in range(3) if np.random.random() > 0.7  # Random congestion points
                    ],
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