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
# Import folium features directly
from folium.features import GeoJsonPopup

# Define API URL
API_URL = "http://localhost:8000"

def show_project_setup():
    """Show the project setup page"""
    # Create tabs for the project setup steps
    tab1, tab2, tab3 = st.tabs([
        "1. Project Name", 
        "2. Upload File", 
        "3. Upload GeoJSON Data"
    ])
    
    # Step 1: Define project name (moved to first step)
    with tab1:
        st.subheader("Define Project Name")
        
        # Get project name with auto-check on Enter
        project_name = st.text_input("Project Name", value="", key="project_name_input", 
                                      help="Press Enter to set the project name")
        
        # If name was entered and Enter was pressed (detected by change in input value)
        if project_name:
            try:
                # Try to call API to check if project name exists
                response = requests.get(f"{API_URL}/api/projects/check_name/{project_name}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("exists", False):
                        st.error(f"A project with the name '{project_name}' already exists. Please choose a different name.")
                    else:
                        st.success(f"Project name '{project_name}' is available!")
                        # Store the project name in session state
                        st.session_state.project_name = project_name
                else:
                    # For development, proceed anyway if API endpoint doesn't exist yet
                    st.session_state.project_name = project_name
                    st.success(f"Project name set to: {project_name}")
                    st.info("Note: Project name uniqueness check not available.")
            except Exception as e:
                # If API call fails, still set the name but inform the user
                st.session_state.project_name = project_name
                st.success(f"Project name set to: {project_name}")
                st.info("Note: Could not verify if this name is already in use.")
        
        # Next step button
        if "project_name" in st.session_state:
            if st.button("Next: Upload Project File"):
                # Just for visual feedback
                pass
    
    # Step 2: Upload file (CSV or Excel) - kept as before
    with tab2:
        st.subheader("Upload Project File")
        
        # Only allow if project name is defined
        if "project_name" not in st.session_state:
            st.info("Please define a project name in the previous step first.")
            return
            
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
            if st.button("Weiter: GeoJSON Daten hochladen"):
                # Just for visual feedback
                pass
    
    # Step 3: Upload GeoJSON files (replaces drawing steps)
    with tab3:
        st.subheader("Upload GeoJSON Data")
        
        # Only allow if previous steps are completed
        if "project_name" not in st.session_state or "excel_file" not in st.session_state:
            st.info("Please complete the previous steps first.")
            return
            
        st.markdown("""
        ### GeoJSON Upload
        
        Bitte laden Sie die folgenden GeoJSON-Dateien hoch:
        
        1. **Baustelle**: Ein Polygon, das den Baustellen-Bereich definiert
        2. **Route**: LineString(s), die die Zufahrtswege definieren
        3. **Wartebereich**: Polygon(e), die die Wartebereiche definieren
        4. **Kartengrenzen**: Ein Polygon, das die Grenzen der Karte für die Simulation definiert
        """)
        
        # File uploaders for each GeoJSON
        construction_site_file = st.file_uploader("Baustelle (GeoJSON)", type=["json", "geojson"], key="construction_site_upload")
        routes_file = st.file_uploader("Route (GeoJSON)", type=["json", "geojson"], key="routes_upload")
        waiting_areas_file = st.file_uploader("Wartebereich (GeoJSON)", type=["json", "geojson"], key="waiting_areas_upload")
        map_bounds_file = st.file_uploader("Kartengrenzen (GeoJSON)", type=["json", "geojson"], key="map_bounds_upload")
        
        # Process and display GeoJSON files
        geojson_data = {}
        
        # Helper function to process GeoJSON files
        def process_geojson_file(file, key_name):
            if file is not None:
                try:
                    content = file.read()
                    # Reset file pointer for future reads
                    file.seek(0)
                    data = json.loads(content)
                    geojson_data[key_name] = data
                    return True
                except json.JSONDecodeError:
                    st.error(f"Invalid GeoJSON format in {key_name} file. Please check your file.")
                except Exception as e:
                    st.error(f"Error processing {key_name} file: {str(e)}")
            return False
        
        # Process each file
        site_loaded = process_geojson_file(construction_site_file, "polygon")
        routes_loaded = process_geojson_file(routes_file, "access_routes")
        waiting_loaded = process_geojson_file(waiting_areas_file, "waiting_areas")
        bounds_loaded = process_geojson_file(map_bounds_file, "map_bounds")
        
        # Display the map with loaded GeoJSON data
        if any([site_loaded, routes_loaded, waiting_loaded, bounds_loaded]):
            st.subheader("Preview Map")
            
            # Set default map center or use polygon center if available
            map_center = [47.3769, 8.5417]  # Default: Zurich
            if "polygon" in geojson_data:
                try:
                    # Try to calculate centroid from polygon
                    if geojson_data["polygon"]["type"] == "Polygon":
                        polygon_coords = geojson_data["polygon"]["coordinates"][0]
                        centroid_lon = sum(p[0] for p in polygon_coords) / len(polygon_coords)
                        centroid_lat = sum(p[1] for p in polygon_coords) / len(polygon_coords)
                        map_center = [centroid_lat, centroid_lon]
                except Exception:
                    # If anything goes wrong, use default center
                    pass
            
            m = folium.Map(location=map_center, zoom_start=14)
            
            # Add construction site polygon to map
            if "polygon" in geojson_data:
                folium.GeoJson(
                    geojson_data["polygon"],
                    name="Construction Site",
                    style_function=lambda x: {"fillColor": "red", "color": "red", "weight": 2, "fillOpacity": 0.4}
                ).add_to(m)
            
            # Add waiting areas to map
            if "waiting_areas" in geojson_data:
                folium.GeoJson(
                    geojson_data["waiting_areas"],
                    name="Waiting Areas",
                    style_function=lambda x: {"fillColor": "blue", "color": "blue", "weight": 2, "fillOpacity": 0.4}
                ).add_to(m)
            
            # Add access routes to map
            if "access_routes" in geojson_data:
                folium.GeoJson(
                    geojson_data["access_routes"],
                    name="Access Routes",
                    style_function=lambda x: {"color": "green", "weight": 4}
                ).add_to(m)
            
            # Add map bounds to map
            if "map_bounds" in geojson_data:
                folium.GeoJson(
                    geojson_data["map_bounds"],
                    name="Map Bounds",
                    style_function=lambda x: {"fillColor": "purple", "color": "purple", "weight": 2, "fillOpacity": 0.2}
                ).add_to(m)
            
            # Add layer control
            folium.LayerControl().add_to(m)
            
            # Display the map
            folium_static(m)
            
            # Save GeoJSON data to session state
            for key, data in geojson_data.items():
                st.session_state[key] = data
        
        # Create project button - only show if all required files are uploaded
        all_files_loaded = all([
            "project_name" in st.session_state,
            "excel_file" in st.session_state,
            "polygon" in st.session_state,
            "access_routes" in st.session_state,
            "waiting_areas" in st.session_state,
            "map_bounds" in st.session_state
        ])
        
        if all_files_loaded:
            if st.button("Create Project"):
                create_project()
        else:
            missing = []
            if "project_name" not in st.session_state:
                missing.append("Project Name")
            if "excel_file" not in st.session_state:
                missing.append("Project File")
            if "polygon" not in st.session_state:
                missing.append("Construction Site GeoJSON")
            if "access_routes" not in st.session_state:
                missing.append("Routes GeoJSON")
            if "waiting_areas" not in st.session_state:
                missing.append("Waiting Areas GeoJSON")
            if "map_bounds" not in st.session_state:
                missing.append("Map Bounds GeoJSON")
            
            st.warning(f"Please complete all required inputs before creating project. Missing: {', '.join(missing)}")

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
        # Get the original file object from session state
        file_obj = st.session_state.excel_file
        file_obj.seek(0)  # Reset file pointer to beginning
        
        # Get file extension to determine content type
        file_extension = file_obj.name.split(".")[-1].lower()
        
        if file_extension == "xlsx":
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif file_extension == "csv":
            content_type = "text/csv"
        else:
            st.error(f"Unsupported file type: {file_extension}")
            return
        
        # Create files dict with proper file handling
        files = {
            "file": (file_obj.name, file_obj.getvalue(), content_type)
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
                error_content = response.content.decode()
                st.error(error_content)
                
                # Log detailed error information for debugging
                try:
                    error_json = json.loads(error_content)
                    if "errors" in error_json:
                        for error in error_json["errors"]:
                            st.error(f"Detail: {error}")
                except:
                    pass
    
    except Exception as e:
        st.error(f"Error creating project: {str(e)}") 