import os
import streamlit as st

# API Configuration
# Priorität: 1. Streamlit Secrets, 2. Environment Variable, 3. Default localhost
def get_api_url():
    # Versuche zuerst Streamlit Secrets zu lesen
    try:
        if hasattr(st, 'secrets') and 'STREAMLIT_API_URL' in st.secrets:
            return st.secrets['STREAMLIT_API_URL']
    except:
        pass
    
    # Fallback auf Umgebungsvariable
    api_url = os.getenv("STREAMLIT_API_URL")
    if api_url:
        return api_url
    
    # Standard-Fallback für lokale Entwicklung
    return "http://localhost:8000"

API_URL = get_api_url()

# Debug-Modus
DEBUG = os.getenv("DEBUG", "false").lower() == "true" 