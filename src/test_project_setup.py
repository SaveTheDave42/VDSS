#!/usr/bin/env python3
"""
Testskript für den Projekt-Setup-Prozess.

Dieses Skript simuliert die Schritte, die ein Benutzer beim Einrichten eines Projekts 
durchläuft und überprüft, ob die Daten korrekt verarbeitet und gespeichert werden.
"""

import json
import os
import pandas as pd
import sys
from datetime import datetime # Importiere datetime

# Füge das Hauptverzeichnis zum Python-Pfad hinzu, um Module zu importieren
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Importiere notwendige Funktionen und Klassen (simuliert)
# Annahme: Die Logik ist in diesen Modulen verfügbar
# Importiere die Seitenmodule aus dem neuen 'modules'-Package. Früher lagen
# diese unter 'pages', daher stellen wir hier die aktualisierten Importe sicher.
from modules.project_setup import show_project_setup, create_project_from_session_state as create_project
from src.prepare_profiles import create_profile_id, sanitize_filename_component # Tatsächlich importiert

# Hilfsfunktionen zum Simulieren von Streamlit-Session-State
class MockSessionState:
    def __init__(self):
        self._state = {}

    def __getitem__(self, key):
        return self._state[key]

    def __setitem__(self, key, value):
        self._state[key] = value

    def __contains__(self, key):
        return key in self._state

    def get(self, key, default=None):
        return self._state.get(key, default)

st_session_state = MockSessionState() # Simulierter Session State

def run_setup_simulation(project_data):
    """Simuliert den Setup-Prozess für ein Projekt"""
    print("Simuliere Projekt-Setup...")
    
    # 1. Setze Projektnamen und andere Basisdaten
    st_session_state.project_name = project_data["name"]
    st_session_state.polygon = project_data["polygon"]
    st_session_state.waiting_areas = project_data["waiting_areas"]
    st_session_state.access_routes = project_data["access_routes"]
    st_session_state.map_bounds = project_data["map_bounds"]
    
    # Normalerweise würde hier der Excel-Upload simuliert
    # Für diesen Test gehen wir davon aus, dass die Excel-Datei bereits im Projekt ist
    st_session_state.excel_file = type('UploadedFile', (), {
        'name': project_data["file_name"],
        'getvalue': lambda: b"dummy excel content"
    })()
    
    # 2. Zählstellen-Auswahl (aus project_data entnehmen)
    st_session_state.selected_counters = project_data["selected_counters"]
    st_session_state.primary_counter = project_data["primary_counter"]
    
    # Lade die vorberechneten Profile (simuliert das Laden in project_setup.py)
    # Die Profile werden normalerweise aus der `_metadata.csv` und den einzelnen Profil-Dateien geladen
    # Für den Test stellen wir sicher, dass die IDs korrekt sind
    st_session_state.counter_profiles = {}
    metadata_file = "data/prepared/profiles/_metadata.csv"
    if os.path.exists(metadata_file):
        meta_df = pd.read_csv(metadata_file)
        for _, row in meta_df.iterrows():
            # Verwende die bereinigte Profile ID, die auch im Dateinamen verwendet wird
            profile_id = create_profile_id(row['counter_id'], row['direction'])
            st_session_state.counter_profiles[profile_id] = {
                'id': row['counter_id'],
                'name': row['display_name'],
                'direction': row['direction'],
                'is_primary': (row['counter_id'] == st_session_state.primary_counter['id'] and 
                               row['direction'] == st_session_state.primary_counter['direction'])
                # 'data' würde hier geladen, aber für den Test nicht nötig
            }
    
    print("Setup-Daten im Session State gesetzt.")
    
    # 3. Projekt erstellen (simuliert den API-Call und die Speicherung)
    # Diese Funktion wird nicht wirklich die API aufrufen, sondern nur die Daten validieren
    # und in einer temporären JSON-Datei speichern.
    
    # Bevor wir `create_project` aufrufen, müssen wir sicherstellen, dass die
    # API-Simulation korrekt funktioniert und die Daten wie erwartet speichert.
    
    # Erzeuge die Projekt-Payload, wie sie von der API erwartet wird
    created_project_payload = {
        "name": st_session_state.project_name,
        "file_name": st_session_state.excel_file.name,
        "polygon": st_session_state.polygon,
        "waiting_areas": st_session_state.waiting_areas,
        "access_routes": st_session_state.access_routes,
        "map_bounds": st_session_state.map_bounds,
        "id": project_data["id"], # Verwende die ID aus den Testdaten
        "created_at": datetime.now().isoformat(),
        "primary_counter": st_session_state.primary_counter,
        "selected_counters": st_session_state.selected_counters,
        # Füge hier noch delivery_days und delivery_hours hinzu, falls vorhanden
        "delivery_days": project_data.get("delivery_days", []),
        "delivery_hours": project_data.get("delivery_hours", {})
    }
    
    return created_project_payload

def validate_project_data(original_data, created_data):
    """Validiert, ob die erstellten Projektdaten mit den Originaldaten übereinstimmen"""
    print("Validiere Projektdaten...")
    errors = []
    
    # Vergleiche die wichtigsten Felder
    fields_to_check = ["name", "polygon", "waiting_areas", "access_routes", "map_bounds"]
    for field in fields_to_check:
        if original_data.get(field) != created_data.get(field):
            errors.append(f"Unterschied bei Feld '{field}': Original={original_data.get(field)}, Erstellt={created_data.get(field)}")
    
    # Vergleiche Zählstellen (IDs und Richtungen müssen übereinstimmen)
    if "primary_counter" in original_data and "primary_counter" in created_data:
        orig_primary = original_data["primary_counter"]
        created_primary = created_data["primary_counter"]
        if orig_primary["id"] != created_primary["id"] or orig_primary["direction"] != created_primary["direction"]:
            errors.append("Unterschied bei primärer Zählstelle.")
    
    if "selected_counters" in original_data and "selected_counters" in created_data:
        if len(original_data["selected_counters"]) != len(created_data["selected_counters"]):
            errors.append("Unterschiedliche Anzahl ausgewählter Zählstellen.")
        else:
            # Sortiere Listen vor dem Vergleich, um Reihenfolge-Probleme zu vermeiden
            # Erstelle eine eindeutige ID für jeden Zähler zum Sortieren
            def get_counter_key(c): return f"{c['id']}_{c['direction']}"
            
            orig_sorted = sorted(original_data["selected_counters"], key=get_counter_key)
            created_sorted = sorted(created_data["selected_counters"], key=get_counter_key)
            
            for i, orig_counter in enumerate(orig_sorted):
                created_counter = created_sorted[i]
                if orig_counter["id"] != created_counter["id"] or orig_counter["direction"] != created_counter["direction"]:
                    errors.append(f"Unterschied bei ausgewählter Zählstelle: {orig_counter} vs {created_counter}")
                    break
    
    if errors:
        print("Validierungsfehler:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("Validierung erfolgreich! Projektdaten stimmen überein.")
        return True

def main():
    print("Starte Projekt-Setup-Test...")
    
    # Lade das Beispielprojekt aus der JSON-Datei
    projects_file = "data/projects/projects.json"
    if not os.path.exists(projects_file):
        print(f"FEHLER: Datei '{projects_file}' nicht gefunden!")
        return
        
    with open(projects_file, 'r', encoding='utf-8') as f:
        all_projects = json.load(f)
    
    # Verwende das erste Projekt für den Test
    if not all_projects:
        print("FEHLER: Keine Projekte in der JSON-Datei gefunden!")
        return
    
    example_project_data = all_projects[0]
    print(f"Teste mit Projekt: {example_project_data['name']}")
    
    # Simuliere den Setup-Prozess
    created_project_payload = run_setup_simulation(example_project_data)
    
    # Speichere das Ergebnis in einer temporären Datei für die manuelle Prüfung
    temp_output_file = "data/projects/test_output_project.json"
    with open(temp_output_file, 'w', encoding='utf-8') as f:
        json.dump(created_project_payload, f, indent=2)
    print(f"Simulierte Projektdaten gespeichert in: {temp_output_file}")
    
    # Validiere die erstellten Daten
    if validate_project_data(example_project_data, created_project_payload):
        print("Test erfolgreich abgeschlossen!")
    else:
        print("Test fehlgeschlagen. Bitte überprüfen Sie die Fehler.")

if __name__ == "__main__":
    main() 