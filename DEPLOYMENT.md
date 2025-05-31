# Deployment-Anleitung

## Problem: API-Verbindung beim Deployment

Die Streamlit-App versucht sich mit `localhost:8000` zu verbinden, was beim Deployment nicht funktioniert.

## Lösung: API-URL konfigurieren

### 1. Streamlit Cloud

Wenn du auf Streamlit Cloud deployst:

1. Gehe zu deiner App in Streamlit Cloud
2. Klicke auf "Settings" → "Secrets"
3. Füge folgende Zeile hinzu:
   ```toml
   STREAMLIT_API_URL = "https://vdss-4ovd.onrender.com"
   ```

### 2. Environment Variable

Alternativ kannst du die Umgebungsvariable setzen:
```bash
export STREAMLIT_API_URL="https://vdss-4ovd.onrender.com"
```

### 3. Debug-Modus aktivieren

Um zu überprüfen, welche API-URL verwendet wird:
```bash
export DEBUG=true
streamlit run streamlit_app.py
```

## Konfigurationsreihenfolge

Die App verwendet diese Priorität:
1. **Streamlit Secrets** (`st.secrets['STREAMLIT_API_URL']`)
2. **Environment Variable** (`STREAMLIT_API_URL`)
3. **Cloud Auto-Detection** (falls Cloud-Umgebung erkannt wird)
4. **Localhost Fallback** (`http://localhost:8000`)

## Backend-URLs

- **Production:** `https://vdss-4ovd.onrender.com`
- **Local Development:** `http://localhost:8000`

## Troubleshooting

### Fehler: "Connection refused"
- Überprüfe ob die Backend-URL korrekt ist
- Stelle sicher, dass das Backend läuft
- Aktiviere Debug-Modus um die verwendete URL zu sehen

### Secrets werden nicht gelesen
- Stelle sicher, dass die Secrets in Streamlit Cloud korrekt konfiguriert sind
- Format: `STREAMLIT_API_URL = "https://..."` (ohne Anführungszeichen um den Key)

### Mock-Modus wird aktiviert
- Wenn das Backend nicht erreichbar ist, schaltet die App automatisch in den Mock-Modus
- Du kannst das mit `MOCK_MODE=false` deaktivieren 