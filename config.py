import os
import streamlit as st

# API Configuration
# Priorität: 1. Streamlit Secrets, 2. Environment Variable, 3. Default localhost
def get_api_url():
    # Versuche zuerst Streamlit Secrets zu lesen
    try:
        # Prüfe ob st.secrets verfügbar ist und die URL enthält
        if hasattr(st, 'secrets') and hasattr(st.secrets, 'get'):
            api_url = st.secrets.get('STREAMLIT_API_URL')
            if api_url and api_url.strip():
                return api_url.strip()
        
        # Alternative Methode für Streamlit Secrets
        if hasattr(st, 'secrets') and 'STREAMLIT_API_URL' in st.secrets:
            api_url = st.secrets['STREAMLIT_API_URL']
            if api_url and api_url.strip():
                return api_url.strip()
    except Exception as e:
        # Bei Problemen mit Secrets - weiter zu Environment Variable
        print(f"Fehler beim Lesen der Streamlit Secrets: {e}")
        pass
    
    # Fallback auf Umgebungsvariable
    api_url = os.getenv("STREAMLIT_API_URL")
    if api_url and api_url.strip():
        return api_url.strip()
    
    # Zusätzlicher Fallback: Prüfe ob wir in einer Cloud-Umgebung sind
    # und verwende eine bekannte Backend-URL
    if os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_CLOUD"):
        # Für Streamlit Cloud Deployment - verwende die bekannte Backend URL
        return "https://vdss-4ovd.onrender.com"
    
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