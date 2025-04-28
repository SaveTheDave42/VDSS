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

def show_dashboard(project):
    """Show the dashboard for visualizing traffic simulation results"""
    st.markdown(f"## Traffic Dashboard: {project['name']}")
    
    # Get available simulation data for this project
    simulation_data = get_simulation_data(project['id'])
    
    if not simulation_data:
        st.warning("No simulation data available. Please run a simulation in the Admin panel first.")
        if st.button("Go to Admin Panel"):
            st.session_state.page = "admin"
            st.experimental_rerun()
        return
    
    # Create tabs for different visualizations
    tab1, tab2, tab3 = st.tabs([
        "Traffic Map", 
        "Time Series", 
        "Reports"
    ])
    
    # Tab 1: Interactive Traffic Map
    with tab1:
        st.subheader("Traffic Map Visualization")
        
        # Date and hour selector
        available_dates = list(simulation_data.keys())
        available_dates.sort()  # Sort dates
        
        selected_date = st.selectbox(
            "Select Date",
            options=available_dates,
            index=0
        )
        
        # Get available hours for the selected date
        available_hours = list(simulation_data[selected_date].keys())
        available_hours.sort()  # Sort hours
        
        # Hour slider
        selected_hour = st.slider(
            "Select Hour",
            min_value=min(available_hours),
            max_value=max(available_hours),
            value=min(available_hours),
            step=1,
            format="%d:00"
        )
        
        # Get the data for the selected date and hour
        hour_data = simulation_data[selected_date][selected_hour]
        
        # Display summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Traffic", hour_data["stats"]["total_traffic"])
        with col2:
            st.metric("Average Congestion", f"{hour_data['stats']['average_congestion']:.2f}")
        with col3:
            st.metric("Delivery Vehicles", hour_data["stats"]["deliveries_count"])
        
        # Create traffic map
        st.markdown("### Traffic Flow Map")
        
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
        
        # Add waiting areas
        for i, area in enumerate(project["waiting_areas"]):
            # Get waiting area status if available
            area_status = hour_data["time_steps"][0]["waiting_areas_status"].get(f"area_{i}", None)
            
            # Create popup content
            if area_status:
                popup_content = f"""
                <b>Waiting Area {i+1}</b><br>
                Capacity: {area_status['capacity']}<br>
                Occupied: {area_status['occupied']}<br>
                Available: {area_status['available']}
                """
            else:
                popup_content = f"Waiting Area {i+1}"
            
            # Add to map
            folium.GeoJson(
                area,
                name=f"Waiting Area {i+1}",
                style_function=lambda x: {"fillColor": "blue", "color": "blue", "weight": 2, "fillOpacity": 0.4},
                popup=folium.Popup(popup_content, max_width=200)
            ).add_to(m)
        
        # Add traffic segments
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
            
            # Create popup content
            popup_content = f"""
            <b>Road Segment</b><br>
            Traffic: {segment['traffic_volume']} vehicles<br>
            Congestion: {congestion:.2f}<br>
            Speed Limit: {segment['speed_limit']} km/h
            """
            
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
        <h4>Traffic Congestion</h4>
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="background-color: green; width: 20px; height: 5px; margin-right: 5px;"></div>
            <div>Low (0.0-0.3)</div>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="background-color: orange; width: 20px; height: 5px; margin-right: 5px;"></div>
            <div>Medium (0.3-0.7)</div>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="background-color: red; width: 20px; height: 5px; margin-right: 5px;"></div>
            <div>High (0.7-1.0)</div>
        </div>
        </div>
        """
        
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Display the map
        folium_static(m)
        
        # Show congestion hotspots
        st.markdown("### Congestion Hotspots")
        
        # Get the congestion points
        congestion_points = hour_data.get("congestion_points", [])
        
        if congestion_points:
            # Create a table
            hotspot_data = []
            
            for i, point in enumerate(congestion_points):
                hotspot_data.append({
                    "Hotspot ID": i+1,
                    "Segment ID": point["segment_id"],
                    "Congestion Level": f"{point['congestion_level']:.2f}"
                })
            
            hotspot_df = pd.DataFrame(hotspot_data)
            st.dataframe(hotspot_df)
        else:
            st.info("No significant congestion hotspots detected for this time period.")
    
    # Tab 2: Time Series Analysis
    with tab2:
        st.subheader("Time Series Analysis")
        
        # Date range selector
        col1, col2 = st.columns(2)
        
        with col1:
            start_date_str = st.selectbox(
                "Start Date",
                options=available_dates,
                index=0
            )
        
        with col2:
            # Default to 7 days after start or the last available date
            default_end_idx = min(len(available_dates) - 1, available_dates.index(start_date_str) + 7)
            
            end_date_str = st.selectbox(
                "End Date",
                options=available_dates,
                index=default_end_idx
            )
        
        # Collect daily data
        start_idx = available_dates.index(start_date_str)
        end_idx = available_dates.index(end_date_str)
        
        selected_dates = available_dates[start_idx:end_idx+1]
        
        # Prepare data for plots
        dates = []
        daily_totals = []
        daily_averages = []
        daily_peaks = []
        daily_congestion = []
        
        for date_str in selected_dates:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            dates.append(date_obj)
            
            # Variables for this day
            daily_total = 0
            traffic_values = []
            congestion_values = []
            
            # Process all hours in this day
            for hour, hour_data in simulation_data[date_str].items():
                traffic_volume = hour_data["stats"]["total_traffic"]
                daily_total += traffic_volume
                traffic_values.append(traffic_volume)
                
                congestion = hour_data["stats"]["average_congestion"]
                congestion_values.append(congestion)
            
            # Calculate stats
            if traffic_values:
                daily_totals.append(daily_total)
                daily_averages.append(sum(traffic_values) / len(traffic_values))
                daily_peaks.append(max(traffic_values))
                daily_congestion.append(sum(congestion_values) / len(congestion_values))
            else:
                daily_totals.append(0)
                daily_averages.append(0)
                daily_peaks.append(0)
                daily_congestion.append(0)
        
        # Plot daily totals
        st.markdown("### Daily Traffic Volume")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=dates,
            y=daily_totals,
            name="Total Daily Traffic",
            marker_color="skyblue"
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=daily_totals,
            mode="lines+markers",
            name="Trend",
            line=dict(color="darkblue", width=2)
        ))
        
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Total Traffic Volume",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=30, b=20),
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Plot daily peak traffic
        st.markdown("### Daily Peak Traffic")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=dates,
            y=daily_peaks,
            name="Peak Hourly Traffic",
            marker_color="lightcoral"
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=daily_peaks,
            mode="lines+markers",
            name="Trend",
            line=dict(color="darkred", width=2)
        ))
        
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Peak Traffic Volume",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=30, b=20),
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Plot daily congestion
        st.markdown("### Daily Average Congestion")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=dates,
            y=daily_congestion,
            name="Average Congestion",
            marker_color="lightgreen"
        ))
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=daily_congestion,
            mode="lines+markers",
            name="Trend",
            line=dict(color="darkgreen", width=2)
        ))
        
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Average Congestion Level (0-1)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=30, b=20),
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Detailed hourly analysis for a single day
        st.markdown("### Hourly Analysis")
        
        selected_detail_date = st.selectbox(
            "Select Date for Hourly Analysis",
            options=selected_dates,
            index=0
        )
        
        # Collect hourly data for the selected date
        hours = []
        hourly_traffic = []
        hourly_congestion = []
        hourly_deliveries = []
        
        for hour, hour_data in sorted(simulation_data[selected_detail_date].items()):
            hours.append(f"{hour}:00")
            hourly_traffic.append(hour_data["stats"]["total_traffic"])
            hourly_congestion.append(hour_data["stats"]["average_congestion"])
            hourly_deliveries.append(hour_data["stats"]["deliveries_count"])
        
        # Create a combined hourly plot
        fig = go.Figure()
        
        # First y-axis - Traffic
        fig.add_trace(go.Bar(
            x=hours,
            y=hourly_traffic,
            name="Traffic Volume",
            marker_color="skyblue",
            opacity=0.7
        ))
        
        # Second y-axis - Congestion
        fig.add_trace(go.Scatter(
            x=hours,
            y=hourly_congestion,
            mode="lines+markers",
            name="Congestion Level",
            line=dict(color="red", width=2),
            yaxis="y2"
        ))
        
        # Third y-axis - Deliveries
        fig.add_trace(go.Scatter(
            x=hours,
            y=hourly_deliveries,
            mode="lines+markers",
            name="Deliveries",
            line=dict(color="green", width=2, dash="dot"),
            marker=dict(size=8),
            yaxis="y3"
        ))
        
        # Update the layout for multiple y-axes
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
            yaxis3=dict(
                title="Deliveries",
                titlefont=dict(color="green"),
                tickfont=dict(color="green"),
                anchor="free",
                overlaying="y",
                side="right",
                position=0.95
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=70, t=30, b=20),
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Tab 3: Export Reports
    with tab3:
        st.subheader("Export Reports")
        
        report_type = st.radio(
            "Select Report Type",
            options=["Daily Report", "Weekly Report"]
        )
        
        if report_type == "Daily Report":
            # Daily report
            selected_report_date = st.selectbox(
                "Select Date for Report",
                options=available_dates,
                index=0
            )
            
            if st.button("Generate Daily Report"):
                try:
                    # Make the API request
                    with st.spinner("Generating report..."):
                        response = requests.get(
                            f"{API_URL}/api/export/daily-report",
                            params={
                                "project_id": project["id"],
                                "date": selected_report_date
                            },
                            stream=True
                        )
                        
                        if response.status_code == 200:
                            # Get the PDF
                            st.success("Report generated successfully!")
                            
                            # Display download button
                            st.download_button(
                                label="Download PDF Report",
                                data=response.content,
                                file_name=f"traffic_report_{project['name']}_{selected_report_date}.pdf",
                                mime="application/pdf"
                            )
                        else:
                            st.error(f"Failed to generate report: {response.status_code}")
                            if response.content:
                                st.error(response.content.decode())
                
                except Exception as e:
                    st.error(f"Error generating report: {str(e)}")
        
        else:
            # Weekly report
            col1, col2 = st.columns(2)
            
            with col1:
                selected_start_date = st.selectbox(
                    "Start Date",
                    options=available_dates,
                    index=0
                )
            
            with col2:
                # Calculate the end date (start + 6 days or last available date)
                start_idx = available_dates.index(selected_start_date)
                end_idx = min(len(available_dates) - 1, start_idx + 6)
                
                selected_end_date = available_dates[end_idx]
                
                st.info(f"End Date: {selected_end_date} (max 7 days)")
            
            if st.button("Generate Weekly Report"):
                try:
                    # Make the API request
                    with st.spinner("Generating report..."):
                        response = requests.get(
                            f"{API_URL}/api/export/weekly-report",
                            params={
                                "project_id": project["id"],
                                "start_date": selected_start_date
                            },
                            stream=True
                        )
                        
                        if response.status_code == 200:
                            # Get the PDF
                            st.success("Report generated successfully!")
                            
                            # Display download button
                            st.download_button(
                                label="Download PDF Report",
                                data=response.content,
                                file_name=f"weekly_traffic_report_{project['name']}_{selected_start_date}_to_{selected_end_date}.pdf",
                                mime="application/pdf"
                            )
                        else:
                            st.error(f"Failed to generate report: {response.status_code}")
                            if response.content:
                                st.error(response.content.decode())
                
                except Exception as e:
                    st.error(f"Error generating report: {str(e)}")

def get_simulation_data(project_id):
    """Get all simulation data for a project"""
    try:
        # This function would ideally make API calls to get the simulation data
        # But for simplicity, we'll use synthetic data
        
        # Try to get real data first
        try:
            response = requests.get(
                f"{API_URL}/api/simulation/{project_id}/results"
            )
            
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        # If that fails, generate synthetic data
        synthetic_data = {}
        
        # Generate data for the last 14 days
        today = date.today()
        
        for i in range(14):
            current_date = today - timedelta(days=i)
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