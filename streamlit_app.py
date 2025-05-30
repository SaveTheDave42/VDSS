import streamlit as st
import pydeck as pdk
import json  # For sample GeoJSON
import requests
from utils.custom_styles import apply_custom_styles, apply_chart_styling, apply_map_layout, apply_widget_panel_layout
from utils.map_utils import update_map_view_to_project_bounds, create_geojson_feature, create_pydeck_geojson_layer, create_pydeck_path_layer
from utils.legend_widget import show_legend_widget, check_geojson_layers_uploaded

# --- Imports für Seiten-Module ---
import importlib
import sys

# Import der Seitenmodule (implizit, damit wir sie dynamisch laden können)
# Stelle sicher, dass alle Seitenmodule in /pages/ liegen
sys.path.append("pages")

# --- Session State for the Map (Minimal) ---
if "map_layers" not in st.session_state:
    st.session_state.map_layers = []
if "map_view_state" not in st.session_state:
    st.session_state.map_view_state = pdk.ViewState(
        latitude=47.3769, longitude=8.5417, zoom=11, pitch=0, bearing=0
    )
if "widget_width_percent" not in st.session_state:
    st.session_state.widget_width_percent = 35  # Default widget width (35% of screen)
# --- End Session State ---

# Configure page
st.set_page_config(layout="wide", page_title="Baustellenverkehrs-Management-System")

# Apply custom styles from our refactored module
apply_custom_styles()
apply_chart_styling()
apply_map_layout()

# <<< map_placeholder is the VERY FIRST element in the main body after set_page_config >>>
map_placeholder = st.empty()

# --- Helper Functions ---
def create_geojson_feature_local(geometry, properties=None):
    """Wrapper für die map_utils Funktion zur Kompatibilität"""
    return create_geojson_feature(geometry, properties)

def create_pydeck_geojson_layer_local(data, layer_id, **kwargs):
    """Wrapper für die map_utils Funktion zur Kompatibilität mit Parameterkonvertierung"""
    # Parameter-Mapping für die Kompatibilität
    new_kwargs = {}
    
    # Mappen der alten Parameter auf neue Namen
    if 'get_fill_color' in kwargs:
        new_kwargs['fill_color'] = kwargs.pop('get_fill_color')
    if 'get_line_color' in kwargs:
        new_kwargs['line_color'] = kwargs.pop('get_line_color')
    
    # Tooltips behandeln
    if 'tooltip' in kwargs:
        tooltip_value = kwargs.pop('tooltip')
        # Wenn es ein String ist, direkt als tooltip_html
        if isinstance(tooltip_value, str):
            new_kwargs['tooltip_html'] = tooltip_value
        # Wenn es ein Dict mit html ist, extrahiere den html-Wert
        elif isinstance(tooltip_value, dict) and 'html' in tooltip_value:
            new_kwargs['tooltip_html'] = tooltip_value['html']
    
    # Übrige Parameter unverändert übernehmen
    new_kwargs.update(kwargs)
    
    return create_pydeck_geojson_layer(data, layer_id, **new_kwargs)
# --- End Helper Functions ---

# --- Define and Display a Sample GeoJSON Layer ---
def load_sample_layer():
    zurich_polygon_geojson = {
        "type": "Polygon",
        "coordinates": [[[
            [8.45, 47.35], [8.65, 47.35], [8.65, 47.45], [8.45, 47.45], [8.45, 47.35]
        ]]]
    }
    zurich_feature = create_geojson_feature_local(
        geometry=zurich_polygon_geojson,
        properties={"name": "Zürich Gebiet", "info": "Beispiel-Polygon"}
    )
    sample_layer = create_pydeck_geojson_layer_local(
        data=[zurich_feature],
        layer_id="sample_zurich_polygon",
        fill_color=[100, 100, 200, 100],
        line_color=[50, 50, 150, 200],
        tooltip_html="<b>{properties.name}</b><br/>{properties.info}"
    )
    return [sample_layer]

# Initialize sample layers only if no layers are already set
if not st.session_state.map_layers:
    st.session_state.map_layers = load_sample_layer()

# Initialize default view if not already set
if "initial_view_set" not in st.session_state:
    st.session_state.map_view_state = pdk.ViewState(
        longitude=8.55, latitude=47.40, zoom=10.5, pitch=0, bearing=0, transition_duration=1000
    )
    st.session_state.initial_view_set = True

# --- Render the Background Map ---
def render_background_map(placeholder_widget):
    view_state = st.session_state.get("map_view_state")
    layers = st.session_state.get("map_layers", [])
    
    if view_state:
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=True,
            map_style='mapbox://styles/mapbox/light-v8'
        )
        placeholder_widget.pydeck_chart(deck)

# --- Create Sidebar for Project Selection and Navigation ---
def create_sidebar():
    with st.sidebar:
        st.title("Baustellenverkehrs-Management")
        
        # Project selection
        if "projects" in st.session_state and st.session_state.projects:
            project_options = {p["name"]: p for p in st.session_state.projects}
            selected_project_name = st.selectbox(
                "Projekt auswählen",
                options=list(project_options.keys()),
                index=next((i for i, p in enumerate(project_options.keys()) 
                          if st.session_state.get("current_project") and 
                          p == st.session_state.current_project.get("name")), 0)
                if st.session_state.get("current_project") else 0
            )
            
            if selected_project_name:
                selected_project = project_options[selected_project_name]
                if not st.session_state.get("current_project") or selected_project["id"] != st.session_state.current_project["id"]:
                    st.session_state.current_project = selected_project
                    # Reset view flags when project changes
                    for key in list(st.session_state.keys()):
                        if key.startswith("view_set_"):
                            del st.session_state[key]
                    # Force rerun to update
                    st.rerun()
        
        st.sidebar.markdown("---")
        
        # Navigation
        st.sidebar.markdown("### Navigation")
        
        # Determine current page
        current_page = st.session_state.get("page", "dashboard")
        
        # Set button style based on current page
        def nav_button(label, page_name):
            active = current_page == page_name
            button_style = "primary" if active else "secondary"
            if st.sidebar.button(label, key=f"nav_{page_name}", type=button_style):
                st.session_state.page = page_name
                st.rerun()
        
        nav_button("Dashboard", "dashboard")
        nav_button("Projekteinrichtung", "project_setup")
        nav_button("Admin-Panel", "admin")
        nav_button("Anwohner-Info", "resident_info")
        
        st.sidebar.markdown("---")
        
        # Refresh button for projects
        if st.sidebar.button("🔄 Projekte aktualisieren", key="refresh_projects_btn"):
            if refresh_projects():
                st.success("Projekte aktualisiert!")
            # Force a rerun so that the updated project list is reflected in the
            # selectbox shown earlier in the sidebar.
            st.rerun()
        
        # Debug button
        if st.sidebar.button("🔍 Debug-Info"):
            st.sidebar.write("Aktuelle Seite:", st.session_state.get("page", "Keine"))
            st.sidebar.write("Hat Projekt:", "current_project" in st.session_state)
            st.sidebar.write("Karten-Layer:", len(st.session_state.get("map_layers", [])))
            st.sidebar.write("Widget-Breite:", st.session_state.get("widget_width_percent", "Nicht gesetzt"))

# --- Initialize Session State for Page Routing ---
if "page" not in st.session_state:
    st.session_state.page = "dashboard"  # Default page

# --- Create Layout Columns for Floating UI ---
col_map, col_widget = st.columns([0.8, 0.2])  # Map/main column, Widget column

# --- Determine which page to show and load the right module ---
current_page = st.session_state.get("page", "dashboard")

# Set widget width based on current page (before rendering)
if current_page == "project_setup" or current_page == "admin":
    st.session_state.widget_width_percent = 50
else:  # dashboard, resident_info, and others
    st.session_state.widget_width_percent = 30

# Apply widget panel layout with the appropriate width
apply_widget_panel_layout(st.session_state.widget_width_percent)

# --- Widget Content Based on Current Page ---
with col_widget:
    # Debug info about the currently selected page
    if st.session_state.get("debug_mode", False):
        st.write(f"DEBUG: Current page = {current_page}")
        st.write(f"DEBUG: Widget width = {st.session_state.widget_width_percent}%")
    
    # Dynamically import and call the right page module
    try:
        # Load the appropriate module for the current page
        if current_page == "dashboard":
            import pages.dashboard as page_module
            if "current_project" in st.session_state:
                page_module.show_dashboard(st.session_state.current_project)
            else:
                st.info("Bitte wählen Sie ein Projekt aus der Seitenleiste")
        
        elif current_page == "project_setup":
            import pages.project_setup as page_module
            page_module.show_project_setup()
        
        elif current_page == "admin":
            import pages.admin as page_module
            page_module.show_admin()
        
        elif current_page == "resident_info":
            import pages.resident_info as page_module
            if "current_project" in st.session_state:
                page_module.show_resident_info(st.session_state.current_project)
            else:
                st.info("Bitte wählen Sie ein Projekt aus der Seitenleiste")
        
        else:
            st.error(f"Unbekannte Seite: {current_page}")
    
    except ImportError as e:
        st.error(f"Fehler beim Importieren des Seitenmoduls: {e}")
    except Exception as e:
        st.error(f"Fehler auf Seite {current_page}: {e}")
        import traceback
        st.code(traceback.format_exc())

# --- Render Map in Map Column ---
with col_map:
    render_background_map(map_placeholder)
    
    # --- Show Legend Widget as Overlay ---
    # Create an overlay container for the legend
    legend_placeholder = st.empty()
    with legend_placeholder.container():
        # Show Legend Widget Based on Current Page
        show_geojson_for_setup = False
        if current_page == "project_setup":
            show_geojson_for_setup = check_geojson_layers_uploaded()
        
        # Display the legend widget
        show_legend_widget(current_page, show_geojson_for_setup)

# --- Add JavaScript for Map Resizing ---
st.markdown("""
<script>
    // Force map elements to full height
    (function() {
        function resizeMapElements() {
            // Target mapbox elements specifically
            const mapboxCanvases = document.querySelectorAll('.mapboxgl-canvas');
            const mapboxContainers = document.querySelectorAll('.mapboxgl-map, .mapboxgl-canvas-container');
            const deckglWrapper = document.getElementById('deckgl-wrapper');
            const defaultView = document.getElementById('view-default-view');
            
            // Set height to full viewport minus header
            const targetHeight = 'calc(100vh - 80px)';
            
            if (mapboxCanvases.length) {
                for (let canvas of mapboxCanvases) {
                    canvas.style.height = targetHeight;
                }
            }
            
            if (mapboxContainers.length) {
                for (let container of mapboxContainers) {
                    container.style.height = targetHeight;
                }
            }
            
            if (deckglWrapper) {
                deckglWrapper.style.height = targetHeight;
            }
            
            if (defaultView) {
                defaultView.style.height = targetHeight;
            }
        }
        
        // Run initially
        setTimeout(resizeMapElements, 100);
        
        // Run on resize events
        window.addEventListener('resize', resizeMapElements);
        
        // Monitor for changes in the DOM that might affect the map
        new MutationObserver(function(mutations) {
            setTimeout(resizeMapElements, 100);
        }).observe(document.body, {childList: true, subtree: true});
    })();
</script>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Backend base URL and helper to fetch projects
# -----------------------------------------------------------------------------

API_URL = "http://localhost:8000"  # Base URL for backend API

def refresh_projects():
    """Fetch all projects from the backend and store them in st.session_state."""
    try:
        response = requests.get(f"{API_URL}/api/projects/")
        if response.status_code == 200:
            st.session_state.projects = response.json() or []
            return True
        else:
            st.error(f"Fehler beim Aktualisieren der Projekte: {response.status_code}")
            st.session_state.projects = []
            return False
    except Exception as exc:
        st.error(f"Fehler beim Verbinden zur API: {exc}")
        st.session_state.projects = []
        return False

# -----------------------------------------------------------------------------
# Ensure we have an initial list of projects before rendering the sidebar/page
# -----------------------------------------------------------------------------

if "projects" not in st.session_state:
    refresh_projects()

# Create and initialize sidebar (now that projects are loaded)
create_sidebar() 