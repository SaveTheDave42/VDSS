"""
Custom styling for Streamlit that cannot be handled by the theme config.toml.
This contains only the CSS overrides that are still needed after moving basic
colors and fonts to the central theme.
"""
import streamlit as st

def apply_custom_styles():
    """Apply custom CSS that's needed in addition to the theme"""
    st.markdown("""
    <style>
    /* --- Button styling --- */
    .stButton button {
        border-radius: 4px;
        padding: 0.25rem 1rem;
        font-weight: 600;
        border: none;
    }
    
    /* --- Metric components --- */
    div[data-testid="stMetricValue"] {
        font-size: 1.4rem;
        color: #0F05A0;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #495057;
    }
    
    /* --- Form styling --- */
    [data-testid="stForm"] {
        border-color: #E7EDFF;
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* --- Expander styling --- */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #0F05A0;
        background-color: rgba(15, 5, 160, 0.05);
        border-radius: 4px;
    }
    
    /* --- Input & Textarea --- */
    div[data-baseweb="input"] input,
    div[data-baseweb="input"] textarea,
    div[data-baseweb="input"] select,
    div[data-baseweb="input"] div[data-baseweb="base-input"] {
        border: 1px solid #0F05A0 !important;
        border-radius: 4px !important;
    }
    
    /* --- Remove default focus styling --- */
    div[data-baseweb="input"] input:focus,
    div[data-baseweb="input"] textarea:focus,
    div[data-baseweb="input"] select:focus,
    div[data-baseweb="input"] div[data-baseweb="base-input"]:focus-within {
        border-color: #0F05A0 !important;
        box-shadow: none !important;
        outline: none !important;
    }
    
    /* --- Multiselect --- */
    div[data-baseweb="select"] span[data-baseweb="tag"] {
        background-color: #0F05A0 !important;
        color: #FFFFFF !important;
        border-radius: 4px !important;
    }
    
    /* --- File Uploader --- */
    section[data-testid='stFileUploadDropzone'] {
        border: 1px dashed #0F05A0 !important;
    }
    
    section[data-testid='stFileUploadDropzone'] button {
        border: 1px solid #0F05A0 !important;
        border-radius: 4px !important;
    }
    
    /* --- DataFrame --- */
    div.glideDataEditor {
        --gdg-bg-cell: #FFFFFF;
        --gdg-bg-header: #FFFFFF;
        --gdg-text-dark: #0F05A0;
        --gdg-text-medium: #0F05A0;
        --gdg-text-header: #0F05A0;
        --gdg-border-color: #0F05A0;
        --gdg-accent-color: #0F05A0;
        --gdg-accent-light: rgba(15, 5, 160, 0.1);
    }
    
    /* --- Tab styling --- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255, 255, 255, 0.05);
        padding: 10px 10px 0 10px;
        border-radius: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 4px 4px 0px 0px;
        margin-right: 4px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.15) !important;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

def apply_chart_styling():
    """Apply styling specific to charts"""
    st.markdown("""
    <style>
    /* Plotly chart background */
    .js-plotly-plot .plotly .main-svg {
        background-color: transparent !important;
    }
    
    /* Turn Plotly grid lines more subtle */
    .js-plotly-plot .plotly .gridlayer path {
        opacity: 0.2 !important;
    }
    
    /* Ensure Plotly text is legible */
    .js-plotly-plot .plotly .gtitle, 
    .js-plotly-plot .plotly .xtitle, 
    .js-plotly-plot .plotly .ytitle {
        fill: #212529 !important;
    }
    </style>
    """, unsafe_allow_html=True)

def apply_map_layout():
    """Apply styling specific to map layout"""
    st.markdown("""
    <style>
    /* Remove all default Streamlit margins and padding for fullscreen map */
    .main > div.block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
        width: 100% !important;
    }
    
    /* Main container should fill viewport */
    .main {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Ensure Streamlit's content container takes full space */
    .stApp > header {
        background: transparent !important;
    }
    
    .stApp {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Make ALL map elements correctly fill the column in height */
    div[data-testid='stDeckGlJsonChart'] {
        height: calc(100vh - 80px) !important;
        width: 100% !important;
        position: relative !important;
        overflow: hidden !important;
    }
    
    /* Force all map container and canvas elements to full height */
    #deckgl-wrapper {
        height: 100% !important;
        min-height: calc(100vh - 80px) !important;
        width: 100% !important;
        position: relative !important;
    }
    
    /* Ensure mapbox container takes full height */
    #view-default-view {
        height: 100% !important;
        min-height: calc(100vh - 80px) !important;
        width: 100% !important;
        position: relative !important;
    }
    
    /* Force mapbox canvas to fill available space */
    .mapboxgl-canvas-container, .mapboxgl-canvas, .mapboxgl-map {
        height: 100% !important;
        min-height: calc(100vh - 80px) !important;
        width: 100% !important;
    }
    
    /* Fix for pydeck chart container */
    div[data-testid='stDeckGlJsonChart'] > div {
        height: 100% !important;
        width: 100% !important;
    }
    
    /* Ensure proper z-index for map elements */
    .mapboxgl-map {
        z-index: 1 !important;
    }
    
    /* Hide scrollbars on map containers */
    #deckgl-wrapper,
    #view-default-view,
    div[data-testid='stDeckGlJsonChart'] {
        overflow: hidden !important;
    }
    </style>
    """, unsafe_allow_html=True)

def apply_widget_panel_layout(widget_width_percent=35):
    """Apply styling for the floating widget panel with dynamic width
    
    Args:
        widget_width_percent: Width of the widget panel as percentage
    """
    st.markdown(f"""
    <style>
    /* Hide the main block-container padding to make map fullscreen */
    section.main .block-container {{
        padding-top: 0 !important;
        padding-right: 0 !important;
        padding-left: 0 !important;
        padding-bottom: 0 !important;
        max-width: 100% !important;
        width: 100% !important;
    }}
    
    /* Make the main content area fill the entire viewport */
    .main .block-container > div:first-child {{
        width: 100% !important;
        max-width: 100% !important;
    }}
    
    /* Map column takes full width and height */
    div[data-testid='column']:nth-of-type(1),
    div[data-testid='column']:first-child {{
        width: 100% !important;
        height: 100vh !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    /* Map column inner elements */
    div[data-testid='column']:nth-of-type(1) > div,
    div[data-testid='column']:first-child > div {{
        padding: 0 !important;
        margin: 0 !important;
        width: 100% !important;
        height: 100% !important;
    }}
    
    /* Floating widget panel - more robust selectors */
    div[data-testid='column']:nth-of-type(2),
    div[data-testid='column']:last-child,
    div[data-testid='column']:nth-child(2) {{
        position: fixed !important;
        top: 70px !important;
        right: 20px !important;
        width: {widget_width_percent}% !important;
        max-width: {widget_width_percent}% !important;
        min-width: 300px !important;
        max-height: calc(100vh - 100px) !important;
        overflow-y: auto !important;
        background: rgba(246, 247, 250, 0.97) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        padding: 20px 16px 12px 16px !important;
        border-radius: 10px !important;
        z-index: 1000 !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }}
    
    /* Ensure the widget content doesn't break the layout */
    div[data-testid='column']:nth-of-type(2) > div,
    div[data-testid='column']:last-child > div,
    div[data-testid='column']:nth-child(2) > div {{
        width: 100% !important;
        overflow-x: hidden !important;
    }}
    
    /* Force map elements to use full space */
    div[data-testid='stDeckGlJsonChart'] {{
        height: calc(100vh - 80px) !important;
        width: 100% !important;
        position: relative !important;
    }}
    
    /* Pydeck/Mapbox container fixes */
    #deckgl-wrapper {{
        height: 100% !important;
        min-height: calc(100vh - 80px) !important;
        width: 100% !important;
    }}
    
    #view-default-view {{
        height: 100% !important;
        min-height: calc(100vh - 80px) !important;
        width: 100% !important;
    }}
    
    .mapboxgl-canvas-container, 
    .mapboxgl-canvas, 
    .mapboxgl-map {{
        height: 100% !important;
        min-height: calc(100vh - 80px) !important;
        width: 100% !important;
    }}
    
    /* Responsive adjustments for smaller screens */
    @media (max-width: 1200px) {{
        div[data-testid='column']:nth-of-type(2),
        div[data-testid='column']:last-child,
        div[data-testid='column']:nth-child(2) {{
            width: 40% !important;
            max-width: 40% !important;
        }}
    }}
    
    @media (max-width: 768px) {{
        div[data-testid='column']:nth-of-type(2),
        div[data-testid='column']:last-child,
        div[data-testid='column']:nth-child(2) {{
            width: 90% !important;
            max-width: 90% !important;
            right: 5% !important;
            top: 80px !important;
            max-height: calc(100vh - 120px) !important;
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

def apply_kpi_styles():
    """Apply reusable CSS styles for KPI flex containers (white background, blue border/text)."""
    st.markdown("""
    <style>
    .kpi-wrapper {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        margin-top: 10px;
    }
    .kpi-card {
        flex: 1;
        background: #FFFFFF;
        border: 1px solid #0F05A0;
        border-radius: 6px;
        padding: 8px 4px 6px 4px;
        text-align: center;
    }
    .kpi-card h4 {
        font-size: 0.8rem;
        font-weight: 600;
        color: #0F05A0;
        margin: 0;
    }
    .kpi-card p {
        font-size: 1.2rem;
        font-weight: 700;
        color: #0F05A0;
        margin: 2px 0 0 0;
    }
    </style>
    """, unsafe_allow_html=True)

def apply_streamlit_cloud_fixes():
    """Apply specific fixes for Streamlit Cloud deployment issues"""
    st.markdown("""
    <style>
    /* Streamlit Cloud specific fixes */
    
    /* Force remove all inherited padding and margins */
    .stApp, .main, section.main, .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
        width: 100% !important;
    }
    
    /* Ensure the root app container fills the viewport */
    #root {
        width: 100% !important;
        height: 100vh !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Override any Streamlit Cloud specific styling that breaks layout */
    .css-1d391kg, .css-18e3th9, .css-1y4p8pa {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    /* Force column layout to work properly */
    .row-widget.stHorizontal {
        width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Ensure columns container spans full width */
    div[data-testid="column"]:first-child,
    div[data-testid="column"]:last-child {
        position: relative !important;
    }
    
    /* Map column absolute positioning */
    div[data-testid="column"]:first-child {
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100vh !important;
        z-index: 1 !important;
    }
    
    /* Widget panel fixed positioning with higher z-index */
    div[data-testid="column"]:last-child {
        position: fixed !important;
        z-index: 999 !important;
    }
    
    /* Hide any potential overflow issues */
    body {
        overflow-x: hidden !important;
    }
    
    /* Force specific Streamlit elements to not interfere */
    .css-1y4p8pa, .css-18e3th9, .css-1d391kg {
        width: 100% !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    
    /* Ensure sidebar doesn't interfere with map */
    section[data-testid="stSidebar"] {
        z-index: 1001 !important;
    }
    </style>
    """, unsafe_allow_html=True) 