import streamlit as st
import pandas as pd
import json
import requests
import os
from datetime import datetime
import folium
from streamlit_folium import folium_static
import numpy as np
from io import BytesIO
import math
# Import folium plugins properly
from folium import plugins
# Import folium GeoJsonPopup directly
from folium.features import GeoJsonPopup

# Define API URL
API_URL = "http://localhost:8000"

def show_project_setup():
    """Show the project setup page"""
    # Create tabs for the project setup steps
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Upload File", 
        "2. Project Name", 
        "3. Define Area", 
        "4. Define Routes", 
        "5. Define Map Bounds"
    ])
    
    # Step 1: Upload file (CSV or Excel)
    with tab1:
        st.subheader("Upload Project File")
        
        # Help text
        st.markdown("""
        ### Datei-Anforderungen
        
        Bitte laden Sie eine CSV- oder Excel-Datei (.csv oder .xlsx) mit folgenden Spalten hoch:
        
        - **Vorgangsname**: Name des Vorgangs/der Aktivität 
        - **Anfangstermin**: Startdatum des Vorgangs (gültiges Datum)
        - **Endtermin**: Enddatum des Vorgangs (gültiges Datum)
        - **Material**: Materialmenge (numerischer Wert)
        
        Die Anzahl der Lastwagen wird automatisch basierend auf der Materialmenge berechnet.
        """)
        
        # Get truck divisor from session state or set default
        if "truck_divisor" not in st.session_state:
            st.session_state.truck_divisor = 20
            
        divisor = st.number_input(
            "Materialmenge pro LKW (Divisor für Berechnung)", 
            value=st.session_state.truck_divisor, 
            min_value=1, 
            help="Materialmenge, die ein LKW transportieren kann. Wird zur Berechnung der Anzahl Lastwagen verwendet."
        )
        st.session_state.truck_divisor = divisor
            
        uploaded_file = st.file_uploader("Datei hochladen", type=["csv", "xlsx"])
        
        if uploaded_file is not None:
            try:
                # Detect file format
                file_extension = uploaded_file.name.split(".")[-1].lower()
                
                # Read file based on extension
                if file_extension == "csv":
                    df = pd.read_csv(uploaded_file, delimiter=",")
                elif file_extension == "xlsx":
                    df = pd.read_excel(uploaded_file)
                
                # Reset the position to allow rereading
                uploaded_file.seek(0)
                
                # Validate required columns
                required_columns = ["vorgangsname", "anfangstermin", "endtermin", "material"]
                df_columns_lower = [col.lower() for col in df.columns]
                
                # Check if all required columns exist
                missing_columns = [col for col in required_columns if col not in df_columns_lower]
                
                if missing_columns:
                    st.error(f"Fehlende Spalten: {', '.join(missing_columns)}")
                    st.markdown("Bitte stellen Sie sicher, dass Ihre Datei folgende Spalten enthält: Vorgangsname, Anfangstermin, Endtermin, Material")
                    return
                
                # Create a mapping from actual columns to required columns
                column_mapping = {}
                for req_col in required_columns:
                    actual_col = df.columns[df_columns_lower.index(req_col)]
                    column_mapping[actual_col] = req_col
                
                # Rename columns to standard names
                df_standardized = df.rename(columns=column_mapping)
                
                # Validate date columns
                try:
                    df_standardized['anfangstermin'] = pd.to_datetime(df_standardized['anfangstermin'])
                    df_standardized['endtermin'] = pd.to_datetime(df_standardized['endtermin'])
                except Exception as e:
                    st.error(f"Fehler bei der Konvertierung der Datumsspalten: {str(e)}")
                    st.markdown("Bitte stellen Sie sicher, dass 'Anfangstermin' und 'Endtermin' gültige Datumsformate haben.")
                    return
                
                # Validate material column is numeric
                try:
                    df_standardized['material'] = pd.to_numeric(df_standardized['material'])
                except Exception as e:
                    st.error(f"Fehler bei der Konvertierung der Materialmenge: {str(e)}")
                    st.markdown("Bitte stellen Sie sicher, dass 'Material' numerische Werte enthält.")
                    return
                
                # Calculate number of trucks
                df_standardized['anzahl_lastwagen'] = df_standardized['material'].apply(
                    lambda x: math.ceil(x / st.session_state.truck_divisor)
                )
                
                # Show preview of the standardized data
                st.subheader("Datenvorschau")
                st.dataframe(df_standardized)
                
                # Summary statistics
                st.subheader("Zusammenfassung")
                total_material = df_standardized['material'].sum()
                total_trucks = df_standardized['anzahl_lastwagen'].sum()
                earliest_date = df_standardized['anfangstermin'].min()
                latest_date = df_standardized['endtermin'].max()
                
                col1, col2 = st.columns(2)
                col1.metric("Gesamtmaterial", f"{total_material:,.0f}")
                col2.metric("Gesamt LKWs", f"{total_trucks:,.0f}")
                
                col1, col2 = st.columns(2)
                col1.metric("Frühestes Datum", earliest_date.strftime("%d.%m.%Y"))
                col2.metric("Spätestes Datum", latest_date.strftime("%d.%m.%Y"))
                
                # Store the processed dataframe in session state
                st.session_state.processed_df = df_standardized
                st.session_state.import_file = uploaded_file
                
                # Confirmation button
                if st.button("Daten übernehmen und fortfahren"):
                    st.session_state.excel_file = uploaded_file
                    st.success("Datei erfolgreich validiert und verarbeitet! Fahren Sie mit dem nächsten Schritt fort.")
                
            except Exception as e:
                st.error(f"Fehler beim Verarbeiten der Datei: {str(e)}")
        
        # Next step button
        if "excel_file" in st.session_state:
            if st.button("Weiter: Projektname definieren"):
                # Automatically switch to next tab
                pass
    
    # Step 2: Define project name
    with tab2:
        st.subheader("Define Project Name")
        
        # Only allow if Excel is uploaded
        if "excel_file" not in st.session_state:
            st.info("Please upload a file in the previous step first.")
        else:
            project_name = st.text_input("Project Name", value="", key="project_name_input")
            
            if project_name:
                # Store the project name in session state
                st.session_state.project_name = project_name
                st.success(f"Project name set to: {project_name}")
            
            # Next step button
            if "project_name" in st.session_state:
                if st.button("Next: Define Construction Site Area"):
                    # Automatically switch to next tab
                    pass
    
    # Step 3: Define construction site polygon
    with tab3:
        st.subheader("Define Construction Site Area")
        
        # Only allow if previous steps are completed
        if "excel_file" not in st.session_state or "project_name" not in st.session_state:
            st.info("Please complete the previous steps first.")
        else:
            st.markdown("""
            Draw a polygon on the map to define the construction site area:
            
            1. Click the polygon tool (shape icon) in the map
            2. Click on the map to add points for your polygon
            3. Close the polygon by clicking on the first point
            4. Click "Save Polygon" when you're done
            """)
            
            # Initialize or get the map center
            if "map_center" not in st.session_state:
                st.session_state.map_center = [47.3769, 8.5417]  # Default: Zurich
            
            # Create a map centered on the location
            m = folium.Map(location=st.session_state.map_center, zoom_start=15)
            
            # Add the draw control for polygon
            draw_options = {
                'polyline': False,
                'rectangle': False,
                'circle': False,
                'marker': False,
                'circlemarker': False,
                'polygon': True
            }
            
            draw = folium.plugins.Draw(
                export=True,
                position='topleft',
                draw_options=draw_options,
            )
            draw.add_to(m)
            
            # Display the map
            folium_static(m)
            
            # Input for manually entering GeoJSON
            st.markdown("### Or paste GeoJSON polygon data:")
            geojson_input = st.text_area("GeoJSON Polygon", value="", height=150)
            
            # Save button for the polygon
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Save Polygon"):
                    # In a real implementation, we would capture the drawn polygon
                    # For now, we'll use a sample polygon if none is provided
                    if geojson_input:
                        try:
                            polygon_data = json.loads(geojson_input)
                            st.session_state.polygon = polygon_data
                            st.success("Polygon saved successfully!")
                        except json.JSONDecodeError:
                            st.error("Invalid GeoJSON format. Please check your input.")
                    else:
                        # Sample polygon if none is provided
                        sample_polygon = {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [8.54, 47.375],
                                    [8.542, 47.375],
                                    [8.542, 47.378],
                                    [8.54, 47.378],
                                    [8.54, 47.375]
                                ]
                            ]
                        }
                        st.session_state.polygon = sample_polygon
                        st.success("Sample polygon saved successfully! You can edit it later.")
            
            # Next step button
            if "polygon" in st.session_state:
                with col2:
                    if st.button("Next: Define Routes & Waiting Areas"):
                        # Automatically switch to next tab
                        pass
    
    # Step 4: Define routes and waiting areas
    with tab4:
        st.subheader("Define Routes & Waiting Areas")
        
        # Only allow if previous steps are completed
        if ("excel_file" not in st.session_state or 
            "project_name" not in st.session_state or 
            "polygon" not in st.session_state):
            st.info("Please complete the previous steps first.")
        else:
            st.markdown("""
            Draw waiting areas and access routes on the map:
            
            1. Use the polyline tool to draw access routes
            2. Use the polygon tool to draw waiting areas
            3. Click "Save Routes & Areas" when you're done
            """)
            
            # Create a map centered on the polygon centroid
            polygon_coords = st.session_state.polygon["coordinates"][0]
            centroid_lon = sum(p[0] for p in polygon_coords) / len(polygon_coords)
            centroid_lat = sum(p[1] for p in polygon_coords) / len(polygon_coords)
            
            m = folium.Map(location=[centroid_lat, centroid_lon], zoom_start=15)
            
            # Add the existing construction site polygon
            folium.GeoJson(
                st.session_state.polygon,
                name="Construction Site",
                style_function=lambda x: {"fillColor": "red", "color": "red", "weight": 2, "fillOpacity": 0.4}
            ).add_to(m)
            
            # Add the draw control for routes and areas
            draw_options = {
                'polyline': True,
                'rectangle': False,
                'circle': False,
                'marker': False,
                'circlemarker': False,
                'polygon': True
            }
            
            draw = folium.plugins.Draw(
                export=True,
                position='topleft',
                draw_options=draw_options,
            )
            draw.add_to(m)
            
            # Display the map
            folium_static(m)
            
            # Input for manually entering GeoJSON
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Waiting Areas GeoJSON:")
                waiting_areas_input = st.text_area("GeoJSON for Waiting Areas", value="", height=150)
            
            with col2:
                st.markdown("### Access Routes GeoJSON:")
                access_routes_input = st.text_area("GeoJSON for Access Routes", value="", height=150)
            
            # Save button for routes and areas
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Save Routes & Areas"):
                    # In a real implementation, we would capture the drawn shapes
                    # For now, we'll use sample data if none is provided
                    
                    # Process waiting areas input
                    if waiting_areas_input:
                        try:
                            waiting_areas_data = json.loads(waiting_areas_input)
                            st.session_state.waiting_areas = waiting_areas_data
                        except json.JSONDecodeError:
                            st.error("Invalid GeoJSON format for waiting areas. Please check your input.")
                            waiting_areas_data = None
                    else:
                        # Sample waiting area if none is provided
                        waiting_areas_data = [{
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [centroid_lon + 0.002, centroid_lat - 0.001],
                                    [centroid_lon + 0.003, centroid_lat - 0.001],
                                    [centroid_lon + 0.003, centroid_lat],
                                    [centroid_lon + 0.002, centroid_lat],
                                    [centroid_lon + 0.002, centroid_lat - 0.001]
                                ]
                            ]
                        }]
                    
                    # Process access routes input
                    if access_routes_input:
                        try:
                            access_routes_data = json.loads(access_routes_input)
                            st.session_state.access_routes = access_routes_data
                        except json.JSONDecodeError:
                            st.error("Invalid GeoJSON format for access routes. Please check your input.")
                            access_routes_data = None
                    else:
                        # Sample access route if none is provided
                        access_routes_data = [{
                            "type": "LineString",
                            "coordinates": [
                                [centroid_lon - 0.005, centroid_lat - 0.005],
                                [centroid_lon - 0.002, centroid_lat - 0.002],
                                [centroid_lon, centroid_lat]
                            ]
                        }]
                    
                    # Save the data
                    if waiting_areas_data:
                        st.session_state.waiting_areas = waiting_areas_data
                    if access_routes_data:
                        st.session_state.access_routes = access_routes_data
                    
                    st.success("Routes and waiting areas saved successfully!")
            
            # Next step button
            if "waiting_areas" in st.session_state and "access_routes" in st.session_state:
                with col2:
                    if st.button("Next: Define Map Bounds"):
                        # Automatically switch to next tab
                        pass
    
    # Step 5: Define map bounds for simulation
    with tab5:
        st.subheader("Define Map Bounds for Simulation")
        
        # Only allow if previous steps are completed
        if ("excel_file" not in st.session_state or 
            "project_name" not in st.session_state or 
            "polygon" not in st.session_state or
            "waiting_areas" not in st.session_state or 
            "access_routes" not in st.session_state):
            st.info("Please complete the previous steps first.")
        else:
            st.markdown("""
            Define the map area for traffic simulation:
            
            1. Use the rectangle tool to draw the bounds
            2. Click "Save Bounds" when you're done
            """)
            
            # Create a map centered on the polygon centroid
            polygon_coords = st.session_state.polygon["coordinates"][0]
            centroid_lon = sum(p[0] for p in polygon_coords) / len(polygon_coords)
            centroid_lat = sum(p[1] for p in polygon_coords) / len(polygon_coords)
            
            m = folium.Map(location=[centroid_lat, centroid_lon], zoom_start=14)
            
            # Add the existing construction site polygon
            folium.GeoJson(
                st.session_state.polygon,
                name="Construction Site",
                style_function=lambda x: {"fillColor": "red", "color": "red", "weight": 2, "fillOpacity": 0.4}
            ).add_to(m)
            
            # Add waiting areas
            for i, area in enumerate(st.session_state.waiting_areas):
                folium.GeoJson(
                    area,
                    name=f"Waiting Area {i+1}",
                    style_function=lambda x: {"fillColor": "blue", "color": "blue", "weight": 2, "fillOpacity": 0.4}
                ).add_to(m)
            
            # Add access routes
            for i, route in enumerate(st.session_state.access_routes):
                folium.GeoJson(
                    route,
                    name=f"Access Route {i+1}",
                    style_function=lambda x: {"color": "green", "weight": 4}
                ).add_to(m)
            
            # Add the draw control for bounds
            draw_options = {
                'polyline': False,
                'rectangle': True,
                'circle': False,
                'marker': False,
                'circlemarker': False,
                'polygon': False
            }
            
            draw = folium.plugins.Draw(
                export=True,
                position='topleft',
                draw_options=draw_options,
            )
            draw.add_to(m)
            
            # Display the map
            folium_static(m)
            
            # Input for manually entering GeoJSON
            st.markdown("### Map Bounds GeoJSON:")
            map_bounds_input = st.text_area("GeoJSON for Map Bounds", value="", height=150)
            
            # Save button for bounds
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Save Bounds"):
                    # In a real implementation, we would capture the drawn rectangle
                    # For now, we'll use a sample rectangle if none is provided
                    if map_bounds_input:
                        try:
                            map_bounds_data = json.loads(map_bounds_input)
                            st.session_state.map_bounds = map_bounds_data
                            st.success("Map bounds saved successfully!")
                        except json.JSONDecodeError:
                            st.error("Invalid GeoJSON format. Please check your input.")
                    else:
                        # Sample bounds if none is provided
                        sample_bounds = {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [centroid_lon - 0.01, centroid_lat + 0.01],
                                    [centroid_lon + 0.01, centroid_lat + 0.01],
                                    [centroid_lon + 0.01, centroid_lat - 0.01],
                                    [centroid_lon - 0.01, centroid_lat - 0.01],
                                    [centroid_lon - 0.01, centroid_lat + 0.01]
                                ]
                            ]
                        }
                        st.session_state.map_bounds = sample_bounds
                        st.success("Sample map bounds saved successfully! You can edit it later.")
            
            # Create project button
            if "map_bounds" in st.session_state:
                with col2:
                    if st.button("Create Project"):
                        create_project()

def create_project():
    """Create a new project by sending data to the API"""
    try:
        # Prepare form data
        form_data = {
            "name": st.session_state.project_name,
            "polygon": json.dumps(st.session_state.polygon),
            "waiting_areas": json.dumps(st.session_state.waiting_areas),
            "access_routes": json.dumps(st.session_state.access_routes),
            "map_bounds": json.dumps(st.session_state.map_bounds)
        }
        
        # Prepare file data
        files = {
            "file": ("project_data.xlsx", st.session_state.excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }
        
        # Make the API request
        response = requests.post(
            f"{API_URL}/api/projects/",
            data=form_data,
            files=files
        )
        
        if response.status_code == 200:
            project_data = response.json()
            st.success(f"Project '{project_data['name']}' created successfully!")
            
            # Update session state
            st.session_state.current_project = project_data
            
            # Switch to admin page
            st.session_state.page = "admin"
            
            # Clear setup data
            for key in ["excel_file", "project_name", "polygon", "waiting_areas", "access_routes", "map_bounds"]:
                if key in st.session_state:
                    del st.session_state[key]
                    
            # Force page refresh
            st.experimental_rerun()
        else:
            st.error(f"Failed to create project: {response.status_code}")
            if response.content:
                st.error(response.content.decode())
    
    except Exception as e:
        st.error(f"Error creating project: {str(e)}") 