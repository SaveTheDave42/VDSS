#!/usr/bin/env python3
"""
Skript zum Vorberechnen von Verkehrsprofilen für verschiedene Wochentage und Monate.
Die vorberechneten Profile werden als CSV-Dateien gespeichert, um sie schnell
in der Anwendung laden zu können.
"""

import pandas as pd
import os
import numpy as np
from datetime import datetime
import holidays
import time
import csv
import sys
import re
from pyproj import Transformer  # Coordinate transformation LV95->WGS84

def sanitize_filename_component(text):
    """
    Bereinigt einen String-Teil für die Verwendung in Dateinamen.
    Entfernt Anführungszeichen und ersetzt ungültige Zeichen.
    """
    if text is None:
        return "unknown"
    text = str(text).strip('"\'') # Äußere Anführungszeichen entfernen
    text = re.sub(r'[\\/*?:"<>|]', '_', text) # Ungültige Zeichen ersetzen
    return text.strip()

def create_profile_id(station_id, direction):
    """
    Erzeugt eine einheitliche Profil-ID, die für Dateinamen verwendet wird.
    Format: ZXX_richtung (bereinigt für Dateisysteme)
    """
    clean_station_id = sanitize_filename_component(station_id)
    clean_direction = sanitize_filename_component(direction)
    return f"{clean_station_id}_{clean_direction}"

def main():
    # Pfade definieren
    input_file = "data/imports/raw/verkehr_2024.csv"
    output_dir = "data/prepared/profiles"
    counters_file = "data/prepared/counters.csv" # Wird jetzt auch hier generiert
    metadata_file = f"{output_dir}/_metadata.csv"
    
    print(f"Vorberechnung der Verkehrsprofile aus {input_file}...")
    start_time = time.time()
    
    # Ausgabeverzeichnisse erstellen, falls nicht vorhanden
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Verzeichnis {output_dir} erstellt.")
    if not os.path.exists(os.path.dirname(counters_file)):
        os.makedirs(os.path.dirname(counters_file))
        print(f"Verzeichnis {os.path.dirname(counters_file)} erstellt.")
    
    print("Lade Verkehrsdaten...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            header_line = f.readline().strip()
        
        if ',' in header_line and ';' not in header_line:
            sep = ','
        else:
            sep = ';'
        
        if '"' in header_line:
            header_line = header_line.replace('"', '')
            columns = header_line.split(sep)
        else:
            columns = header_line.split(sep)
            
        columns = [col.strip() for col in columns]
        print(f"Erkanntes Trennzeichen: '{sep}', Gefundene Spalten: {len(columns)}")
        
        df = pd.read_csv(input_file, sep=sep, names=columns, skiprows=1, 
                         quoting=csv.QUOTE_NONE, encoding='utf-8',
                         on_bad_lines='warn', low_memory=False)
        print(f"Daten geladen: {len(df)} Zeilen")

        zsid_col = next((col for col in df.columns if 'ZSID' in col), None)
        zsname_col = next((col for col in df.columns if 'ZSName' in col), None)
        richtung_col = next((col for col in df.columns if 'Richtung' in col), None)
        datum_col = next((col for col in df.columns if 'MessungDatZeit' in col), None)
        fahrzeuge_col = next((col for col in df.columns if 'AnzFahrzeuge' in col), None)
        ekoord_col = next((col for col in df.columns if any(term in col for term in ['KOORX', 'EKoord'])), None)
        nkoord_col = next((col for col in df.columns if any(term in col for term in ['KOORY', 'NKoord'])), None)

        if not all([zsid_col, richtung_col, datum_col, fahrzeuge_col]):
            print("FEHLER: Nicht alle erforderlichen Kernspalten (ZSID, Richtung, MessungDatZeit, AnzFahrzeuge) gefunden!")
            return
        if not zsname_col:
            print("WARNUNG: Spalte 'ZSName' nicht gefunden. Stationsnamen werden generisch sein.")

        print("Konvertiere Datum...")
        if df[datum_col].dtype == 'object':
            df[datum_col] = df[datum_col].astype(str).str.strip('"\'')
        df['datetime'] = pd.to_datetime(df[datum_col], format='%Y-%m-%dT%H:%M:%S', errors='coerce')
        
        invalid_dates_count = df['datetime'].isna().sum()
        if invalid_dates_count > 0:
            print(f"Entferne {invalid_dates_count} Zeilen mit ungültigem Datum.")
            df = df.dropna(subset=['datetime'])

        df['date'] = df['datetime'].dt.date
        df['hour'] = df['datetime'].dt.hour
        df['weekday'] = df['datetime'].dt.day_name()
        df['month'] = df['datetime'].dt.month
        df['year'] = df['datetime'].dt.year
        
        print("Konvertiere Fahrzeugzahlen...")
        if df[fahrzeuge_col].dtype == 'object':
            df[fahrzeuge_col] = df[fahrzeuge_col].astype(str).str.strip('"\'')
        df[fahrzeuge_col] = pd.to_numeric(df[fahrzeuge_col], errors='coerce')
        df = df.dropna(subset=[fahrzeuge_col])
        
        print("Filtere Daten...")
        ch_holidays = holidays.CH(prov='ZH', years=2024)
        df['is_holiday'] = df['date'].apply(lambda x: x in ch_holidays)
        df['is_weekend'] = df['weekday'].isin(['Saturday', 'Sunday'])
        
        data_for_profiles = df[
            (df['year'] == 2024) &
            (~df['is_holiday']) &
            (~df['is_weekend'])
        ].copy()
        print(f"Daten für Profile (Werktage 2024): {len(data_for_profiles)} Zeilen")

        if len(data_for_profiles) == 0:
            print("FEHLER: Keine Daten für Profilerstellung nach Filterung übrig!")
            return

        print("Extrahiere und speichere Zählstelleninformationen...")
        # Verwende ursprüngliches df für Zählstellen, um alle Stationen zu erfassen
        unique_stations_raw = df.groupby([zsid_col, richtung_col]).first().reset_index()
        stations_list = []
        # Prepare transformer once
        transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
        for _, row in unique_stations_raw.iterrows():
            station_id_raw = str(row[zsid_col]).strip('"\'')
            direction_raw = str(row[richtung_col]).strip('"\'')
            
            profile_id = create_profile_id(station_id_raw, direction_raw) # Für Dateinamen und Metadaten-Schlüssel
            
            name = str(row[zsname_col]).strip('"\'') if zsname_col and pd.notna(row[zsname_col]) else f"Station {station_id_raw}"
            display_name = f"{station_id_raw} - {name} ({direction_raw})"
            
            x_coord = row[ekoord_col] if ekoord_col and pd.notna(row[ekoord_col]) else 2683484.5
            y_coord = row[nkoord_col] if nkoord_col and pd.notna(row[nkoord_col]) else 1247375.0
            
            # Convert to WGS-84 once during preprocessing
            try:
                lon_wgs84, lat_wgs84 = transformer.transform(float(x_coord), float(y_coord))
            except Exception:
                # Fallback to Zurich centre if conversion fails
                lat_wgs84, lon_wgs84 = 47.376888, 8.541694
            
            stations_list.append({
                'profile_id': profile_id, # Schlüssel für Metadaten und Dateiname
                'counter_id': station_id_raw, # Originale, bereinigte ID
                'name': name, # Bereinigter Name
                'direction': direction_raw, # Originale, bereinigte Richtung
                'display_name': display_name, # Originalgetreuer Anzeigename
                'x_coord': x_coord,
                'y_coord': y_coord,
                'lat': lat_wgs84,
                'lon': lon_wgs84,
                'coordinates': [lat_wgs84, lon_wgs84],  # Store as proper Python list for JSON serialization
                'file': f"{output_dir}/{profile_id}.csv" # Dateipfad zum Profil
            })
        
        counters_df = pd.DataFrame(stations_list)
        counters_df = counters_df.sort_values('profile_id')
        counters_df.to_csv(counters_file, index=False)
        print(f"Zählstellen gespeichert: {len(counters_df)} Einträge in {counters_file}")

        weekday_map_de = {
            'Monday': 'Montag', 'Tuesday': 'Dienstag', 'Wednesday': 'Mittwoch',
            'Thursday': 'Donnerstag', 'Friday': 'Freitag', 'Saturday': 'Samstag', 'Sunday': 'Sonntag'
        }
        month_names = {i: datetime(2024, i, 1).strftime('%B') for i in range(1, 13)}

        all_profiles_metadata = []
        print(f"Berechne Profile für {len(counters_df)} Zählstellen...")
        successful_counters = 0

        for idx, counter_meta_row in counters_df.iterrows():
            current_counter_id = counter_meta_row['counter_id']
            current_direction = counter_meta_row['direction']
            current_profile_id = counter_meta_row['profile_id']
            current_display_name = counter_meta_row['display_name']
            
            print(f"Verarbeite Zählstelle {idx+1}/{len(counters_df)}: {current_display_name} (ID: {current_profile_id})")
            
            counter_data_for_profile = data_for_profiles[
                (data_for_profiles[zsid_col].astype(str).str.strip('"\'') == current_counter_id) &
                (data_for_profiles[richtung_col].astype(str).str.strip('"\'') == current_direction)
            ].copy()
            
            if counter_data_for_profile.empty:
                print(f"  Keine Daten für diese Zählstelle ({current_display_name}) für Profilerstellung gefunden. Überspringe.")
                continue
                
            try:
                profile_df = counter_data_for_profile.groupby(['weekday', 'month', 'hour'])[fahrzeuge_col].mean().reset_index()
                profile_df = profile_df.rename(columns={fahrzeuge_col: 'vehicles'})
                profile_df['weekday_de'] = profile_df['weekday'].map(weekday_map_de)
                profile_df['month_name'] = profile_df['month'].map(month_names)
                
                output_profile_file = counter_meta_row['file'] # Verwende den Dateipfad aus den Metadaten
                profile_df.to_csv(output_profile_file, index=False)
                
                # Füge nur die relevanten Spalten zu den Metadaten hinzu
                all_profiles_metadata.append({
                    'profile_id': current_profile_id,
                    'counter_id': current_counter_id,
                    'direction': current_direction,
                    'display_name': current_display_name,
                    'file': output_profile_file,
                    'lat': counter_meta_row['lat'],
                    'lon': counter_meta_row['lon'],
                    'data_points': len(profile_df)
                })
                print(f"  Profil gespeichert: {len(profile_df)} Datenpunkte in {output_profile_file}")
                successful_counters += 1
            except Exception as e:
                print(f"  Fehler beim Erstellen des Profils für {current_display_name}: {str(e)}")
                continue
        
        if all_profiles_metadata:
            meta_df_final = pd.DataFrame(all_profiles_metadata)
            # Stelle sicher, dass die Spaltenreihenfolge konsistent ist
            meta_df_final = meta_df_final[['profile_id', 'counter_id', 'direction', 'display_name', 'file', 'lat', 'lon', 'data_points']]
            meta_df_final.to_csv(metadata_file, index=False)
            
            end_time = time.time()
            duration = end_time - start_time
            print(f"\nVorberechnung abgeschlossen in {duration:.1f} Sekunden")
            print(f"Erstellt: {len(all_profiles_metadata)} Profile von {len(counters_df)} Zählstellen ({successful_counters} erfolgreich)")
            print(f"Metadaten gespeichert in: {metadata_file}")
        else:
            print("\nEs konnten keine Profile erstellt oder Metadaten gespeichert werden.")
    
    except Exception as e:
        print(f"FEHLER im Hauptprozess: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 