import streamlit as st
import pandas as pd
import json
import requests
import os
from datetime import datetime, date
import folium
from streamlit_folium import folium_static
import plotly.express as px
from io import BytesIO

# Define API URL
API_URL = "http://localhost:8000"

def show_admin_panel(project):
    """Show the admin panel for managing an existing project"""
    st.markdown(f"## Project: {project['name']}")
    
    # Create tabs for different admin functions
    tab1, tab2, tab3 = st.tabs([
        "Edit Project", 
        "Update Excel", 
        "Simulation Settings"
    ])
    
    # Tab 1: Edit Project (edit geometries, name, etc.)
    with tab1:
        st.subheader("Edit Project Details")
        
        # Edit project name
        new_name = st.text_input("Project Name", value=project["name"])
        
        # Create a map centered on the project polygon
        st.subheader("Edit Geometries")
        st.markdown("The map below shows the current project geometries. To edit them, use the text areas below.")
        
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
            folium.GeoJson(
                area,
                name=f"Waiting Area {i+1}",
                style_function=lambda x: {"fillColor": "blue", "color": "blue", "weight": 2, "fillOpacity": 0.4}
            ).add_to(m)
        
        # Add access routes
        for i, route in enumerate(project["access_routes"]):
            folium.GeoJson(
                route,
                name=f"Access Route {i+1}",
                style_function=lambda x: {"color": "green", "weight": 4}
            ).add_to(m)
        
        # Add map bounds
        folium.GeoJson(
            project["map_bounds"],
            name="Map Bounds",
            style_function=lambda x: {"fillColor": "purple", "color": "purple", "weight": 2, "fillOpacity": 0.2}
        ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Display the map
        folium_static(m)
        
        # Edit geometries via JSON
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Construction Site Polygon:")
            polygon_json = st.text_area(
                "GeoJSON for Construction Site", 
                value=json.dumps(project["polygon"], indent=2),
                height=200
            )
            
            st.markdown("### Waiting Areas:")
            waiting_areas_json = st.text_area(
                "GeoJSON for Waiting Areas", 
                value=json.dumps(project["waiting_areas"], indent=2),
                height=200
            )
        
        with col2:
            st.markdown("### Access Routes:")
            access_routes_json = st.text_area(
                "GeoJSON for Access Routes", 
                value=json.dumps(project["access_routes"], indent=2),
                height=200
            )
            
            st.markdown("### Map Bounds:")
            map_bounds_json = st.text_area(
                "GeoJSON for Map Bounds", 
                value=json.dumps(project["map_bounds"], indent=2),
                height=200
            )
        
        # Update button
        if st.button("Update Project Details"):
            try:
                # Parse JSON inputs
                try:
                    polygon_data = json.loads(polygon_json)
                    waiting_areas_data = json.loads(waiting_areas_json)
                    access_routes_data = json.loads(access_routes_json)
                    map_bounds_data = json.loads(map_bounds_json)
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON format: {str(e)}")
                    st.stop()
                
                # Prepare form data
                form_data = {
                    "name": new_name,
                    "polygon": json.dumps(polygon_data),
                    "waiting_areas": json.dumps(waiting_areas_data),
                    "access_routes": json.dumps(access_routes_data),
                    "map_bounds": json.dumps(map_bounds_data)
                }
                
                # Make the API request
                response = requests.put(
                    f"{API_URL}/api/projects/{project['id']}",
                    data=form_data
                )
                
                if response.status_code == 200:
                    updated_project = response.json()
                    st.success("Project updated successfully!")
                    
                    # Update session state
                    st.session_state.current_project = updated_project
                    
                    # Refresh the projects list
                    refresh_projects()
                    
                    # Force page refresh
                    st.experimental_rerun()
                else:
                    st.error(f"Failed to update project: {response.status_code}")
                    if response.content:
                        st.error(response.content.decode())
            
            except Exception as e:
                st.error(f"Error updating project: {str(e)}")
    
    # Tab 2: Update Excel data
    with tab2:
        st.subheader("Update Excel Data")
        
        # Display current Excel info
        st.info(f"Current Excel file: {project['file_name']}")
        
        # Upload new Excel file
        uploaded_file = st.file_uploader("Choose a new Excel file", type=["xlsx"])
        
        if uploaded_file is not None:
            # Show preview of the data
            try:
                st.subheader("Data Preview")
                
                # Read the Excel file
                deliveries_df = pd.read_excel(uploaded_file, sheet_name="Deliveries")
                schedule_df = pd.read_excel(uploaded_file, sheet_name="Schedule")
                vehicles_df = pd.read_excel(uploaded_file, sheet_name="Vehicles")
                
                # Reset the position to allow rereading
                uploaded_file.seek(0)
                
                # Show previews
                with st.expander("Deliveries Preview"):
                    st.dataframe(deliveries_df.head())
                
                with st.expander("Schedule Preview"):
                    st.dataframe(schedule_df.head())
                
                with st.expander("Vehicles Preview"):
                    st.dataframe(vehicles_df.head())
                
                # Update button
                if st.button("Update Excel Data"):
                    try:
                        # Prepare file data
                        files = {
                            "file": (uploaded_file.name, uploaded_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        }
                        
                        # Make the API request
                        response = requests.put(
                            f"{API_URL}/api/projects/{project['id']}",
                            files=files
                        )
                        
                        if response.status_code == 200:
                            updated_project = response.json()
                            st.success("Excel data updated successfully!")
                            
                            # Update session state
                            st.session_state.current_project = updated_project
                            
                            # Refresh the projects list
                            refresh_projects()
                            
                            # Force page refresh
                            st.experimental_rerun()
                        else:
                            st.error(f"Failed to update Excel data: {response.status_code}")
                            if response.content:
                                st.error(response.content.decode())
                    
                    except Exception as e:
                        st.error(f"Error updating Excel data: {str(e)}")
                
            except Exception as e:
                st.error(f"Error reading Excel file: {str(e)}")
    
    # Tab 3: Simulation Settings
    with tab3:
        st.subheader("Simulation Settings")
        
        # Display current simulation settings
        st.info(f"""
        Current simulation settings:
        - Start time: {project.get('simulation_start_time', '06:00')}
        - End time: {project.get('simulation_end_time', '18:00')}
        - Interval: {project.get('simulation_interval', '1h')}
        """)
        
        # Edit simulation settings
        col1, col2, col3 = st.columns(3)
        
        with col1:
            start_time = st.text_input("Start Time (HH:MM)", value=project.get('simulation_start_time', '06:00'))
        
        with col2:
            end_time = st.text_input("End Time (HH:MM)", value=project.get('simulation_end_time', '18:00'))
        
        with col3:
            interval = st.selectbox(
                "Interval",
                options=["15m", "30m", "1h", "2h", "4h"],
                index=2  # Default to 1h
            )
        
        # Update button
        if st.button("Update Simulation Settings"):
            try:
                # Prepare form data
                form_data = {
                    "simulation_start_time": start_time,
                    "simulation_end_time": end_time,
                    "simulation_interval": interval
                }
                
                # Make the API request
                response = requests.put(
                    f"{API_URL}/api/projects/{project['id']}",
                    data=form_data
                )
                
                if response.status_code == 200:
                    updated_project = response.json()
                    st.success("Simulation settings updated successfully!")
                    
                    # Update session state
                    st.session_state.current_project = updated_project
                    
                    # Refresh the projects list
                    refresh_projects()
                    
                    # Force page refresh
                    st.experimental_rerun()
                else:
                    st.error(f"Failed to update simulation settings: {response.status_code}")
                    if response.content:
                        st.error(response.content.decode())
            
            except Exception as e:
                st.error(f"Error updating simulation settings: {str(e)}")
        
        # Run simulation section
        st.subheader("Run Simulation")
        
        # Date range selection for simulation
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input("Start Date", value=date.today())
        
        with col2:
            end_date = st.date_input("End Date", value=date.today() + pd.Timedelta(days=7))
        
        # Run simulation button
        if st.button("Run Simulation"):
            try:
                # Prepare request data
                simulation_request = {
                    "project_id": project["id"],
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "time_interval": interval
                }
                
                # Show a spinner while the simulation runs
                with st.spinner("Running simulation... This may take a few minutes."):
                    # Make the API request
                    response = requests.post(
                        f"{API_URL}/api/simulation/run",
                        json=simulation_request
                    )
                    
                    if response.status_code == 200:
                        simulation_result = response.json()
                        st.success("Simulation completed successfully!")
                        
                        # Show a summary of the results
                        st.subheader("Simulation Summary")
                        st.json(simulation_result["stats"])
                        
                        # Provide a link to the dashboard
                        st.info("View detailed results in the Dashboard page")
                        
                        if st.button("Go to Dashboard"):
                            st.session_state.page = "dashboard"
                            st.experimental_rerun()
                    else:
                        st.error(f"Failed to run simulation: {response.status_code}")
                        if response.content:
                            st.error(response.content.decode())
            
            except Exception as e:
                st.error(f"Error running simulation: {str(e)}")

def refresh_projects():
    """Refresh the projects list in the session state"""
    try:
        response = requests.get(f"{API_URL}/api/projects/")
        if response.status_code == 200:
            st.session_state.projects = response.json()
            return True
        else:
            st.error(f"Failed to refresh projects: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return False 