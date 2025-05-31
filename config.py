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

# Mock-Modus: Wenn True, funktioniert die App ohne Backend
# Wird automatisch aktiviert wenn Backend nicht erreichbar ist
MOCK_MODE = os.getenv("MOCK_MODE", "auto").lower()

def is_mock_mode_enabled():
    """Prüft ob Mock-Modus aktiviert werden soll"""
    if MOCK_MODE == "true":
        return True
    elif MOCK_MODE == "false":
        return False
    else:  # "auto"
        # Auto-detect: Prüfe ob Backend erreichbar ist
        try:
            import requests
            response = requests.get(f"{API_URL}/", timeout=3)
            return response.status_code != 200
        except:
            return True  # Backend nicht erreichbar -> Mock-Modus 