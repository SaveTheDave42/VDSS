import streamlit as st

def inject_widget_override():
    """
    Inject CSS overrides for widgets to ensure consistent styling across all pages.
    This handles styling of widgets that may change due to Streamlit's dynamic CSS.
    """
    st.markdown("""
    <style>
        /* Enhanced styles for metric components */
        div[data-testid="stMetricValue"] {
            font-size: 1.4rem;
            color: #0F05A0; /* Zürich-Blau */
        }
        
        div[data-testid="stMetricLabel"] {
            font-size: 0.9rem;
            color: #495057; /* dunkles Grau */
        }
        
        /* General text coloring for dark background */
        .streamlit-expanderHeader, .streamlit-expanderContent {
            color: #212529; /* Grundtextfarbe */
        }
        
        /* Button styling */
        .stButton button {
            border-radius: 4px;
            padding: 0.25rem 1rem;
            font-weight: 600;
            background-color: #0F05A0;
            color: #FFFFFF;
            border: none;
        }
        
        /* Ensure value text inside selectboxes is Zurich blue */
        .stSelectbox div[data-baseweb='select'] .st-cb,
        .stSelectbox div[data-baseweb='select'] .st-cb * {
            color: #0F05A0 !important;
        }
        
        /* Style main tab elements to better fit the dark panel */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding: 8px 16px;
            border-radius: 4px 4px 0px 0px;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #0F05A0 !important;
            color: #FFFFFF !important;
            font-weight: 600;
        }
        
        /* Ensure text in tabs is visible over dark backgrounds */
        .stTabs [data-baseweb="tab-panel"] {
            color: white;
        }
        
        /* Slider color adjustments */
        .stSlider [data-baseweb="slider"] {
            margin-top: 10px;
            color: #0F05A0;
        }
        
        /* Form styling */
        [data-testid="stForm"] {
            border-color: #E7EDFF;
            border-radius: 8px;
            padding: 1rem;
            background-color: #F6F7FA;
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            font-weight: 600;
            color: #0F05A0;
            background-color: rgba(15, 5, 160, 0.05);
            border-radius: 4px;
        }
    </style>
    """, unsafe_allow_html=True)
    
def apply_special_chart_styling():
    """
    Apply styling specific to charts being shown in dark mode.
    Use for pages that have complex charts requiring extra attention.
    """
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
            fill: white !important;
        }
    </style>
    """, unsafe_allow_html=True) 