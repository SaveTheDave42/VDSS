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
            color: #ffffff;
        }
        
        div[data-testid="stMetricLabel"] {
            font-size: 0.9rem;
            color: #d1d9e6;
        }
        
        /* General text coloring for dark background */
        .streamlit-expanderHeader, .streamlit-expanderContent {
            color: white;
        }
        
        /* Button styling */
        .stButton button {
            border-radius: 4px;
            padding: 0.25rem 1rem;
            font-weight: 600;
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
            background-color: rgba(255, 255, 255, 0.1) !important;
            font-weight: 600;
        }
        
        /* Ensure text in tabs is visible over dark backgrounds */
        .stTabs [data-baseweb="tab-panel"] {
            color: white;
        }
        
        /* Slider color adjustments */
        .stSlider [data-baseweb="slider"] {
            margin-top: 10px;
        }
        
        /* Form styling */
        [data-testid="stForm"] {
            border-color: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 1rem;
            background-color: rgba(255, 255, 255, 0.05);
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            font-weight: 600;
            color: white;
            background-color: rgba(255, 255, 255, 0.05);
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