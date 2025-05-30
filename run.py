import subprocess
import sys
import time
import webbrowser
import os
from threading import Thread

def run_backend():
    """Run the FastAPI backend server"""
    print("FastAPI Backend wird gestartet...")
    subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"])

def run_frontend():
    """Run the Streamlit frontend"""
    print("Streamlit Frontend wird gestartet...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "streamlit_app.py"])

def open_browser():
    """Open web browser after a short delay"""
    time.sleep(3)  # Give servers time to start
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    # Create necessary directories if they don't exist
    os.makedirs("data/projects", exist_ok=True)
    os.makedirs("data/simulations", exist_ok=True)
    os.makedirs("data/reports", exist_ok=True)
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1].lower() == "backend":
            run_backend()
        elif sys.argv[1].lower() == "frontend":
            run_frontend()
        else:
            print(f"Unbekanntes Argument: {sys.argv[1]}")
            print("Verwendung: python run.py [backend|frontend]")
    else:
        # Run both in separate threads
        backend_thread = Thread(target=run_backend)
        frontend_thread = Thread(target=run_frontend)

        
        backend_thread.daemon = True
        frontend_thread.daemon = True

        
        print("Baustellenverkehrs-Management-System wird gestartet...")
        
        backend_thread.start()
        time.sleep(2)  # Give backend time to start before frontend
        frontend_thread.start()
        
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nSystem wird heruntergefahren...")
        finally:
            print("Anwendung gestoppt.") 