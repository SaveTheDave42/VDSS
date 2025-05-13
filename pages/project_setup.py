import streamlit as st
import pandas as pd
import json
import requests
import os
from datetime import datetime, time
import folium
from streamlit_folium import folium_static
import numpy as np
from io import BytesIO
import math
# Import folium plugins properly
from folium import plugins
# Import folium features directly
from folium.features import GeoJsonPopup
import holidays

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
        
        # Additional features after project name validation
        if "project_name" in st.session_state:
            st.markdown("---")
            
            # 1. Delivery days and hours
            st.subheader("Anliefertage und Anlieferzeiten")
            
            # Multiselect for weekdays
            weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"]
            default_days = weekdays[:-1]  # Monday to Friday by default
            
            selected_days = st.multiselect(
                "Anliefertage",
                options=weekdays,
                default=default_days
            )
            
            if selected_days:
                st.session_state.delivery_days = selected_days
            
            # Time input for delivery hours
            col1, col2 = st.columns(2)
            
            with col1:
                start_time = st.time_input(
                    "Lieferung ab",
                    value=time(7, 0)  # 7:00 AM default
                )
            
            with col2:
                end_time = st.time_input(
                    "Lieferung bis",
                    value=time(17, 0)  # 5:00 PM default
                )
            
            # Store delivery hours in session state
            st.session_state.delivery_hours = {
                "start": start_time,
                "end": end_time
            }
            
            # 2. Traffic counting stations from local CSV file
            st.markdown("---")
            st.subheader("Verkehrszählstellen")
            
            # Add info link about counting stations
            with st.expander("ℹ️ Informationen zu Zählstellen"):
                st.markdown("Die Verkehrszählstellen können auf dem [Stadtplan von Zürich](https://www.stadtplan.stadt-zuerich.ch/zueriplan3/stadtplan.aspx#route_visible=true&basemap=Basiskarte+(Geb%C3%A4udeschr%C3%A4gansicht)&map=&scale=8000&xkoord=2680153.2835917696&ykoord=1248850.403632357&lang=&layer=Z%C3%A4hlstelle+MIV%3A%3A0&window=&selectedObject=&selectedLayer=&toggleScreen=&legacyUrlState=&drawings=) eingesehen werden.")
            
            # Function to load counting stations from prepared file
            @st.cache_data(ttl=3600)  # Cache for 1 hour
            def load_counting_stations():
                try:
                    # Load the pre-processed counters file
                    counters_file = "data/prepared/counters.csv"
                    
                    if not os.path.exists(counters_file):
                        st.error(f"Die Datei {counters_file} wurde nicht gefunden. Bitte führen Sie zuerst src/prepare_counters.py aus.")
                        return []
                    
                    # Read the CSV file
                    df = pd.read_csv(counters_file)
                    
                    # Create list of stations with required format
                    stations = []
                    for _, row in df.iterrows():
                        stations.append({
                            'id': row['counter_id'],
                            'name': row['name'],
                            'direction': row['direction'],
                            'display_name': row['display_name'],
                            'coordinates': (
                                # Try to parse JSON coordinates column first if it exists
                                json.loads(row['coordinates']) if ('coordinates' in df.columns and not pd.isna(row['coordinates'])) else
                                # Fall back to lat/lon columns
                                [float(row['lat']), float(row['lon'])] if ('lat' in df.columns and 'lon' in df.columns 
                                                                            and not pd.isna(row['lat']) and not pd.isna(row['lon'])) else
                                # Fall back to LV95 conversion if needed (should never happen since we've precomputed)
                                [47.3769, 8.5417]  # Zurich center as last resort
                            )
                        })
                    
                    return stations
                except Exception as e:
                    st.error(f"Fehler beim Laden der Zählstellen: {str(e)}")
                    return []
                
            # Function to load pre-calculated traffic profiles
            @st.cache_data(ttl=3600)  # Cache for 1 hour
            def load_traffic_profiles():
                """Lädt die vorberechneten Verkehrsprofile und deren Metadaten."""
                try:
                    meta_file = "data/prepared/profiles/_metadata.csv"
                    if not os.path.exists(meta_file):
                        st.error(f"Metadaten-Datei {meta_file} nicht gefunden. Bitte src/prepare_profiles.py ausführen.")
                        return {}

                    meta_df = pd.read_csv(meta_file)
                    profiles = {}

                    for _, row in meta_df.iterrows():
                        # Verwende die bereits korrekt formatierte 'profile_id' aus der CSV als Schlüssel
                        profile_key = row['profile_id'] 
                        profile_file = row['file']

                        if not os.path.exists(profile_file):
                            st.warning(f"Profildatei {profile_file} nicht gefunden. Überspringe.")
                            continue
                        
                        # Lade die Profildaten
                        profile_data_df = pd.read_csv(profile_file)
                        
                        # Speichere das Profil unter der korrekten, bereinigten ID
                        profiles[profile_key] = {
                            'id': str(row['counter_id']).strip('"\''), # Bereinigte ID
                            'direction': str(row['direction']).strip('"\''), # Bereinigte Richtung
                            'name': str(row['display_name']).strip('"\''), # Bereinigter Anzeigename
                            'is_primary': False, # Wird später gesetzt
                            'data': profile_data_df
                        }
                    
                    # Debug-Ausgabe für das erste geladene Profil
                    if profiles and st.session_state.get('debug_mode', False):
                        first_key = next(iter(profiles))
                        first_profile = profiles[first_key]
                        st.write(f"Debug (load_traffic_profiles) - Erster Profilschlüssel: {first_key}")
                        st.write(f"Debug (load_traffic_profiles) - Inhalt: id={first_profile['id']}, direction={first_profile['direction']}")
                    
                    return profiles
                except Exception as e:
                    st.error(f"Fehler beim Laden der Verkehrsprofile: {str(e)}")
                    if st.session_state.get('debug_mode', False):
                        import traceback
                        st.write(f"Debug (load_traffic_profiles) - Fehlerdetails: {traceback.format_exc()}")
                    return {}
                
            # Load counting stations
            counting_stations = load_counting_stations()
            
            if counting_stations:
                # Initialize selected counters in session state if not exists
                if "selected_counters" not in st.session_state:
                    st.session_state.selected_counters = []
                
                if "primary_counter" not in st.session_state:
                    st.session_state.primary_counter = None
                
                # Create a map to display stations
                map_center = [47.3769, 8.5417]  # Zurich center
                m = folium.Map(location=map_center, zoom_start=13)
                
                # Add stations to map
                for station in counting_stations:
                    # Check if station is selected
                    is_selected = any(s['id'] == station['id'] and s['direction'] == station['direction'] 
                                    for s in st.session_state.selected_counters)
                    is_primary = (st.session_state.primary_counter and 
                                st.session_state.primary_counter['id'] == station['id'] and 
                                st.session_state.primary_counter['direction'] == station['direction'])
                    
                    # Create popup text
                    popup_text = f"{station['display_name']}"
                    
                    # Choose color based on selection status
                    if is_primary:
                        color = 'red'  # Primary station
                    elif is_selected:
                        color = 'green'  # Secondary station
                    else:
                        color = 'blue'  # Not selected
                    
                    # Add marker with popup
                    folium.Marker(
                        location=station['coordinates'],
                        popup=popup_text,
                        tooltip=popup_text,
                        icon=folium.Icon(color=color)
                    ).add_to(m)
                
                # Display the map
                st.write("Verfügbare Zählstellen (rot = primär, grün = sekundär):")
                folium_static(m)
                
                # Select primary counting station
                station_options = [s['display_name'] for s in counting_stations]
                
                # Get current primary selection
                current_primary = ""
                if st.session_state.primary_counter:
                    current_primary = st.session_state.primary_counter['display_name']
                
                # Dropdown for primary station selection
                st.subheader("Primäre Zählstelle")
                st.markdown("Wählen Sie die Zählstelle, die den größten Einfluss auf den Verkehr im Projektgebiet hat.")
                
                primary_station_name = st.selectbox(
                    "Primäre Zählstelle auswählen",
                    options=station_options,
                    index=station_options.index(current_primary) if current_primary in station_options else 0
                )
                
                # Update primary_counter in session state
                if primary_station_name:
                    for station in counting_stations:
                        if station['display_name'] == primary_station_name:
                            st.session_state.primary_counter = station
                            break
                
                # Get current secondary selections (exclude primary)
                secondary_options = [s for s in station_options if s != primary_station_name]
                current_secondary = []
                
                if st.session_state.selected_counters:
                    for s in st.session_state.selected_counters:
                        if (not st.session_state.primary_counter or 
                            s['id'] != st.session_state.primary_counter['id'] or 
                            s['direction'] != st.session_state.primary_counter['direction']):
                            current_secondary.append(s['display_name'])
                
                # Dropdown for secondary station selection
                st.subheader("Sekundäre Zählstellen")
                st.markdown("Wählen Sie bis zu 3 weitere Zählstellen, die für das Projekt relevant sind.")
                
                secondary_station_names = st.multiselect(
                    "Sekundäre Zählstellen auswählen",
                    options=secondary_options,
                    default=current_secondary,
                    max_selections=3
                )
                
                # Update selected_counters in session state (primary + secondary)
                st.session_state.selected_counters = []
                
                # Add primary counter first if selected
                if st.session_state.primary_counter:
                    st.session_state.selected_counters.append(st.session_state.primary_counter)
                
                # Add secondary stations
                for name in secondary_station_names:
                    for station in counting_stations:
                        if station['display_name'] == name:
                            st.session_state.selected_counters.append(station)
                            break
                
                # Load traffic profiles if stations are selected
                if st.session_state.selected_counters:
                    st.markdown("---")
                    st.subheader("Verkehrsdaten")
                    
                    # Load pre-calculated profiles
                    all_profiles = load_traffic_profiles()
                    
                    if not all_profiles:
                        st.error("Keine vorberechneten Verkehrsprofile gefunden. Bitte führen Sie zuerst src/prepare_profiles.py aus.")
                    else:
                        # Initialize counter_profiles in session state
                        if "counter_profiles" not in st.session_state:
                            st.session_state.counter_profiles = {}
                        
                        # Add selected profiles to session state
                        with st.spinner("Lade Verkehrsdaten..."):
                            # Clear previous profiles
                            st.session_state.counter_profiles = {}
                            
                            for station in st.session_state.selected_counters:
                                station_id = station['id']
                                station_direction = station['direction']
                                profile_id = f"{station_id}_{station_direction}"
                                
                                if profile_id in all_profiles:
                                    # Copy profile data
                                    profile = all_profiles[profile_id].copy()
                                    
                                    # Update is_primary flag
                                    profile['is_primary'] = (st.session_state.primary_counter and 
                                                          st.session_state.primary_counter['id'] == station_id and 
                                                          st.session_state.primary_counter['direction'] == station_direction)
                                    
                                    # Store in session state
                                    st.session_state.counter_profiles[profile_id] = profile
                                else:
                                    st.warning(f"Kein Profil für Zählstelle {station['display_name']} gefunden.")
                        
                        # 5. Show preview table of traffic data
                        if st.session_state.counter_profiles:
                            st.markdown("---")
                            st.subheader("Vorschau Verkehrsbelastung")
                            
                            # Get delivery hours
                            start_hour = st.session_state.delivery_hours['start'].hour
                            end_hour = st.session_state.delivery_hours['end'].hour
                            
                            # Get selected month
                            current_month = datetime.now().month
                            months = list(range(1, 13))
                            selected_month = st.selectbox(
                                "Monat für Vorschau",
                                options=months,
                                format_func=lambda x: datetime(2024, x, 1).strftime('%B'),
                                index=current_month-1
                            )
                            
                            # Get selected weekday
                            if st.session_state.delivery_days:
                                # Map German weekday names to English for filtering
                                weekday_map = {
                                    "Montag": "Monday",
                                    "Dienstag": "Tuesday",
                                    "Mittwoch": "Wednesday",
                                    "Donnerstag": "Thursday",
                                    "Freitag": "Friday",
                                    "Samstag": "Saturday",
                                    "Sonntag": "Sunday"
                                }
                                
                                # Reverse mapping for display
                                weekday_map_rev = {v: k for k, v in weekday_map.items()}
                                
                                selected_weekday = st.selectbox(
                                    "Wochentag für Vorschau",
                                    options=st.session_state.delivery_days
                                )
                                
                                english_weekday = weekday_map[selected_weekday]
                                
                                # Create preview dataframe
                                hours = list(range(start_hour, end_hour + 1))
                                preview_data = []
                                
                                for hour in hours:
                                    row = {'Stunde': f"{hour:02d}:00"}
                                    
                                    for key, profile in st.session_state.counter_profiles.items():
                                        # Add a marker for primary station
                                        station_name = profile['name']
                                        if profile['is_primary']:
                                            station_name = "🔴 " + station_name
                                        
                                        data = profile['data']
                                        
                                        # Filter for selected weekday, month and hour
                                        filtered = data[(data['weekday'] == english_weekday) & 
                                                        (data['month'] == selected_month) & 
                                                        (data['hour'] == hour)]
                                        
                                        if not filtered.empty:
                                            # Get the average vehicle count (should be in 'vehicles' after preparation)
                                            avg_vehicles = filtered.iloc[0]['vehicles']
                                            row[station_name] = int(round(avg_vehicles))
                                        else:
                                            row[station_name] = "N/A"
                                    
                                    preview_data.append(row)
                                
                                # Create dataframe and display
                                preview_df = pd.DataFrame(preview_data)
                                st.dataframe(preview_df.set_index('Stunde'), use_container_width=True)
                                
                                # Add note about data
                                st.info("Hinweis: Durchschnittliche Fahrzeuge pro Stunde, nur Werktage (exkl. Feiertage), Jahr 2024")
            else:
                st.error("Keine Zählstellen verfügbar. Bitte führen Sie zuerst src/prepare_counters.py aus.")
        
        # Next step button
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
        # Sicherstellen, dass Zählstellen-Daten bereinigt sind
        selected_counters_clean = []
        if "selected_counters" in st.session_state:
            for counter in st.session_state.selected_counters:
                selected_counters_clean.append({
                    "id": str(counter['id']).strip('"\''),
                    "name": str(counter['name']).strip('"\''),
                    "direction": str(counter['direction']).strip('"\''),
                    "profile_id": create_profile_id(counter['id'], counter['direction']),
                    "display_name": str(counter['display_name']).strip('"\''),
                    # Koordinaten sollten als Liste von Floats bleiben, nicht serialisieren
                    "coordinates": counter.get('coordinates') 
                })
        
        primary_counter_clean = None
        if "primary_counter" in st.session_state and st.session_state.primary_counter:
            pc = st.session_state.primary_counter
            primary_counter_clean = {
                "id": str(pc['id']).strip('"\''),
                "name": str(pc['name']).strip('"\''),
                "direction": str(pc['direction']).strip('"\''),
                "profile_id": create_profile_id(pc['id'], pc['direction']),
                "display_name": str(pc['display_name']).strip('"\''),
                "coordinates": pc.get('coordinates')
            }
        
        # Konvertiere delivery_hours zu Strings, falls es time-Objekte sind
        delivery_hours_to_send = {}
        if "delivery_hours" in st.session_state and st.session_state.delivery_hours:
            dh = st.session_state.delivery_hours
            delivery_hours_to_send["start"] = dh["start"].strftime("%H:%M") if isinstance(dh["start"], time) else dh["start"]
            delivery_hours_to_send["end"] = dh["end"].strftime("%H:%M") if isinstance(dh["end"], time) else dh["end"]

        # Prepare form data
        form_data = {
            "name": st.session_state.project_name,
            "polygon": json.dumps(st.session_state.polygon),
            "waiting_areas": json.dumps(st.session_state.waiting_areas),
            "access_routes": json.dumps(st.session_state.access_routes),
            "map_bounds": json.dumps(st.session_state.map_bounds),
            "primary_counter": json.dumps(primary_counter_clean) if primary_counter_clean else None,
            "selected_counters": json.dumps(selected_counters_clean) if selected_counters_clean else None,
            "delivery_days": json.dumps(st.session_state.get("delivery_days", [])),
            "delivery_hours": json.dumps(delivery_hours_to_send) # Sende die konvertierten Strings
        }
        
        # Prepare file data
        file_obj = st.session_state.excel_file
        file_obj.seek(0)  # Reset file pointer to beginning
        file_extension = file_obj.name.split(".")[-1].lower()
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_extension == "xlsx" else "text/csv"
        
        files = {"file": (file_obj.name, file_obj.getvalue(), content_type)}
        
        # Make the API request
        response = requests.post(f"{API_URL}/api/projects/", data=form_data, files=files)
        
        if response.status_code == 200:
            project_data = response.json()
            st.success(f"Project '{project_data['name']}' created successfully!")
            
            # counter_profiles müssen nicht erneut geladen werden, wenn sie schon da sind
            # und korrekt übergeben wurden.
            # Die API sollte das Projekt mit den übergebenen Zählstellen-Infos speichern.
            st.session_state.current_project = project_data # API response sollte das finale Projektobjekt sein
            st.session_state.page = "admin"
            
            # Setze globale states für Zählerdaten direkt aus dem erstellten Projekt
            st.session_state.global_selected_counters = project_data.get("selected_counters", [])
            st.session_state.global_primary_counter = project_data.get("primary_counter", None)
            # counter_profiles werden vom Dashboard geladen, basierend auf selected_counters
            if 'counter_profiles' in st.session_state: # Lösche alte, da Dashboard neu lädt
                 del st.session_state['counter_profiles']
            
            # Clear setup-specific session state keys
            keys_to_clear_from_setup = [
                "excel_file", "project_name", "polygon", "waiting_areas", 
                "access_routes", "map_bounds", "selected_counters", 
                "primary_counter", "delivery_days", "delivery_hours"
            ]
            if 'counter_profiles' in st.session_state: # Lösche dies nur wenn es explizit im Setup war
                 keys_to_clear_from_setup.append('counter_profiles')

            for key in keys_to_clear_from_setup:
                if key in st.session_state:
                    del st.session_state[key]
                    
            st.rerun()
        else:
            st.error(f"Failed to create project: {response.status_code} - {response.text}")
            try:
                error_json = response.json()
                if "detail" in error_json:
                    st.error(f"Detail: {error_json['detail']}")
                if "errors" in error_json:
                    for error in error_json["errors"]:
                        st.error(f"Field Error: {error}")
            except:
                pass # Kein JSON im Fehlerfall
    
    except Exception as e:
        st.error(f"Error creating project: {str(e)}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}") 