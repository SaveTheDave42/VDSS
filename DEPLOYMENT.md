# Deployment Anleitung

## Problem: API-Verbindung bei Online-Deployment

Wenn die Streamlit-App online deployed wird, kann sie nicht mehr auf `localhost:8000` zugreifen. Die App benötigt eine externe API-URL.

## Lösung: Konfigurierbare API-URL

Die App wurde so umgebaut, dass sie die API-URL über Konfiguration bezieht:

### 1. Lokale Entwicklung
Für lokale Entwicklung funktioniert alles wie bisher:
```bash
# Backend starten
python run.py
# oder
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend starten
streamlit run streamlit_app.py
```

### 2. Streamlit Cloud Deployment

#### Option A: Backend auch deployen (Empfohlen)
1. **Backend deployen** auf einer Platform wie:
   - Heroku: `https://your-app.herokuapp.com`
   - Render: `https://your-app.onrender.com` 
   - Railway: `https://your-app.railway.app`
   - Google Cloud Run, AWS Lambda, etc.

2. **API-URL in Streamlit Cloud konfigurieren**:
   - Gehe zu deiner App in Streamlit Cloud
   - Klicke auf "Settings" > "Secrets"
   - Füge hinzu:
   ```toml
   STREAMLIT_API_URL = "https://your-backend-url.com"
   ```

#### Option B: Mock-Modus (Fallback)
Falls das Backend nicht online verfügbar ist, zeigt die App bereits synthetische Daten an und funktioniert im "Demo-Modus".

### 3. Environment Variable (Alternative)
Du kannst auch eine Environment Variable setzen:
```bash
export STREAMLIT_API_URL="https://your-backend-url.com"
streamlit run streamlit_app.py
```

## Backend Deployment Guide

### Heroku Deployment
1. Erstelle eine `Procfile`:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

2. Runtime spezifizieren in `runtime.txt`:
```
python-3.11
```

3. Deploy:
```bash
heroku create your-app-name
git push heroku main
```

### Render Deployment
1. Erstelle einen neuen Web Service
2. Verwende diese Build Command: `pip install -r requirements.txt`
3. Verwende diesen Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Railway Deployment
1. Verbinde dein GitHub Repository
2. Railway erkennt automatisch die FastAPI App
3. Deployment wird automatisch gestartet

## Trouble-Shooting

### API-URL testen
Du kannst die konfigurierte URL in der Streamlit App sehen, indem du temporär folgendes hinzufügst:
```python
st.write(f"Current API URL: {API_URL}")
```

### CORS Probleme
Stelle sicher, dass dein Backend CORS konfiguriert hat:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Für Production spezifischer konfigurieren
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### SSL/HTTPS
Verwende für Production-Deployments immer HTTPS URLs für die API. 