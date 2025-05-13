import streamlit as st
import pandas as pd
import json
import requests
import os
from datetime import datetime, timedelta
import numpy as np
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import io
import base64

# Set page config
st.set_page_config(
    page_title="Construction Site Traffic Management",
    page_icon="🚧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define API URL
API_URL = "http://localhost:8000"

# Main title
st.title("Construction Site Traffic Management System")

# Initialize session state variables if they don't exist
if "page" not in st.session_state:
    st.session_state.page = "project_setup"

if "current_project" not in st.session_state:
    st.session_state.current_project = None

if "projects" not in st.session_state:
    st.session_state.projects = []

# Function to load projects from API
def load_projects():
    try:
        response = requests.get(f"{API_URL}/api/projects/")
        if response.status_code == 200:
            st.session_state.projects = response.json()
            return True
        else:
            st.error(f"Failed to load projects: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        return False

# Sidebar navigation
st.sidebar.title("Navigation")

# Project selection in sidebar if there are projects
if st.sidebar.button("Refresh Projects"):
    load_projects()

selected_page = st.sidebar.radio(
    "Select page",
    ["Project Setup", "Admin", "Dashboard", "Resident Info"]
)

# Update session state based on selection
if selected_page == "Project Setup":
    st.session_state.page = "project_setup"
elif selected_page == "Admin":
    st.session_state.page = "admin"
elif selected_page == "Dashboard":
    st.session_state.page = "dashboard"
elif selected_page == "Resident Info":
    st.session_state.page = "resident_info"

# If there are projects, show project selector in sidebar
if st.session_state.projects:
    project_names = [p["name"] for p in st.session_state.projects]
    selected_project_name = st.sidebar.selectbox(
        "Select Project",
        project_names
    )
    
    # Find the selected project
    selected_project = next(
        (p for p in st.session_state.projects if p["name"] == selected_project_name),
        None
    )
    
    if selected_project:
        st.session_state.current_project = selected_project

# About section in sidebar
with st.sidebar.expander("About"):
    st.write("""
    This application helps manage traffic around construction sites.
    It allows you to:
    - Set up new construction projects
    - Manage project settings
    - Visualize traffic simulations
    - Generate reports for residents
    """)

# Load projects on initial load
if "initial_load" not in st.session_state:
    load_projects()
    st.session_state.initial_load = True

# Main content based on selected page
if st.session_state.page == "project_setup":
    st.header("Project Setup")
    
    from pages.project_setup import show_project_setup
    show_project_setup()
    
elif st.session_state.page == "admin":
    # Use the new show_admin function
    from pages.admin import show_admin
    show_admin()
    
elif st.session_state.page == "dashboard":
    st.header("Traffic Dashboard")
    
    if st.session_state.current_project:
        from pages.dashboard import show_dashboard
        show_dashboard(st.session_state.current_project)
    else:
        st.info("Please select a project from the sidebar or create a new one in the Project Setup page.")
    
elif st.session_state.page == "resident_info":
    st.header("Resident Information")
    
    if st.session_state.current_project:
        from pages.resident_info import show_resident_info
        show_resident_info(st.session_state.current_project)
    else:
        st.info("Please select a project from the sidebar or create a new one in the Project Setup page.") 