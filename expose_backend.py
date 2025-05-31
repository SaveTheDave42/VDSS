import subprocess
import sys
import time
import threading
from pyngrok import ngrok

def run_backend():
    """Starte das FastAPI Backend"""
    print("🚀 Starte FastAPI Backend...")
    subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"])

def main():
    print("🔧 Backend-Exposer für Streamlit Cloud")
    print("=" * 50)
    
    # Starte Backend in separatem Thread
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    
    # Warte kurz bis Backend startet
    print("⏳ Warte auf Backend-Start...")
    time.sleep(5)
    
    # Erstelle ngrok Tunnel
    print("🌐 Erstelle öffentlichen Tunnel...")
    tunnel = ngrok.connect(8000)
    public_url = tunnel.public_url
    
    print(f"""
✅ Backend ist jetzt öffentlich erreichbar!

📝 Konfiguration für Streamlit Cloud:
   Gehe zu deiner App → Settings → Secrets
   Füge hinzu:
   
   STREAMLIT_API_URL = "{public_url}"

🔗 Backend URL: {public_url}
🔗 API Docs: {public_url}/docs

⚡ Das Backend läuft jetzt öffentlich zugänglich!
   Drücke Ctrl+C zum Beenden.
""")
    
    try:
        # Halte das Script am Leben
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Backend wird beendet...")
        ngrok.disconnect(tunnel.public_url)

if __name__ == "__main__":
    main() 