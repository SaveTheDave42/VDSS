#!/usr/bin/env python3
"""
HINWEIS: Dieses Skript wird nicht mehr benötigt, da prepare_profiles.py 
jetzt sowohl die Zählstellen extrahiert als auch die Profile berechnet.
Es wurde aus Kompatibilitätsgründen beibehalten.
"""

print("HINWEIS: Dieses Skript wird nicht mehr benötigt.")
print("Die Funktionalität wurde in prepare_profiles.py integriert.")
print("Bitte verwenden Sie direkt src/prepare_profiles.py")

# Der Rest des Skripts bleibt unverändert und wird nur aus Kompatibilitätsgründen beibehalten
import pandas as pd
import os
import numpy as np
import csv

def main():
    # Pfade definieren
    input_file = "data/imports/raw/verkehr_2024.csv"
    output_dir = "data/prepared"
    output_file = f"{output_dir}/counters.csv"
    
    print(f"Verarbeite Verkehrsdaten aus {input_file}...")
    
    # Ausgabeverzeichnis erstellen, falls nicht vorhanden
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Verzeichnis {output_dir} erstellt.")
    
    # CSV-Datei laden - zuerst das Format analysieren
    try:
        # Überprüfe die ersten paar Zeilen, um das Format zu bestimmen
        with open(input_file, 'r', encoding='utf-8') as f:
            sample = f.readline()
            print(f"Beispielzeile: {sample}")
            
            # Sehen Sie sich das tatsächliche Format an
            if ',' in sample and ';' not in sample:
                sep = ','
            elif ';' in sample and ',' not in sample:
                sep = ';'
            else:
                # Wenn beides vorkommt, prüfe welches häufiger ist
                comma_count = sample.count(',')
                semicolon_count = sample.count(';')
                sep = ',' if comma_count > semicolon_count else ';'
                
            print(f"Erkanntes Trennzeichen: '{sep}'")
            
            # Prüfe, ob die erste Zeile ein korrekter Header sein könnte
            header_issues = False
            if len(sample.split(sep)) == 1:
                print("Warnung: Header scheint nicht korrekt getrennt zu sein.")
                header_issues = True

        # Verschiedene Einleseoptionen basierend auf dem Format
        if header_issues:
            # Versuche, die Datei mit verschiedenen Einstellungen zu öffnen
            try:
                # Versuche mit pandas und explizitem Quoting-Modus
                df = pd.read_csv(input_file, sep=sep, quoting=csv.QUOTE_NONE, engine='python')
            except:
                try:
                    # Versuche mit pandas und anderem Quoting-Modus
                    df = pd.read_csv(input_file, sep=sep, quoting=csv.QUOTE_MINIMAL, engine='python')
                except:
                    # Letzter Versuch: Manuelles Parsen
                    with open(input_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    # Extrahiere den Header
                    header_line = lines[0].strip()
                    # Bereinige Anführungszeichen und Trennzeichen am Anfang/Ende
                    if header_line.startswith('"') and header_line.endswith('"'):
                        header_line = header_line[1:-1]
                    
                    # Finde alle Spalten im Header
                    if '","' in header_line:
                        # Format: "col1","col2","col3"
                        headers = header_line.split('","')
                        # Bereinige den ersten und letzten Eintrag
                        if headers[0].startswith('"'):
                            headers[0] = headers[0][1:]
                        if headers[-1].endswith('"'):
                            headers[-1] = headers[-1][:-1]
                    else:
                        # Versuche reguläre Trennung
                        headers = header_line.split(sep)
                    
                    print(f"Extrahierte Header: {headers}")
                    
                    # Erstelle einen neuen CSV-String mit korrekt getrennten Spalten
                    corrected_csv = sep.join(headers) + "\n"
                    
                    # Füge alle anderen Zeilen hinzu
                    for line in lines[1:]:
                        corrected_csv += line
                    
                    # Speichere den korrigierten CSV-String in eine temporäre Datei
                    temp_file = input_file + ".temp"
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write(corrected_csv)
                    
                    # Lese die korrigierte CSV-Datei
                    df = pd.read_csv(temp_file, sep=sep)
                    
                    # Lösche die temporäre Datei
                    os.remove(temp_file)
        else:
            # Normales Einlesen, wenn der Header korrekt aussieht
            df = pd.read_csv(input_file, sep=sep)
        
        print(f"Datei geladen: {len(df)} Zeilen")
        print(f"Spalten: {list(df.columns)}")
    except Exception as e:
        print(f"Fehler beim Laden der Datei: {str(e)}")
        
        # Versuche, die Datei direkt zu öffnen und zu untersuchen
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                first_lines = [next(f) for _ in range(5)]
            print("Erste 5 Zeilen der Datei:")
            for i, line in enumerate(first_lines):
                print(f"Zeile {i+1}: {line.strip()}")
        except Exception as e2:
            print(f"Fehler beim direkten Lesen der Datei: {str(e2)}")
        
        return
    
    # Spalten identifizieren
    zsid_col = None
    zsname_col = None
    richtung_col = None
    
    for col in df.columns:
        if 'ZSID' in col or 'zsid' in col.lower():
            zsid_col = col
        elif 'ZSName' in col or 'zsname' in col.lower():
            zsname_col = col
        elif 'Richtung' in col or 'richtung' in col.lower():
            richtung_col = col
    
    if not all([zsid_col, zsname_col, richtung_col]):
        print("Nicht alle erforderlichen Spalten wurden gefunden.")
        print(f"Verfügbare Spalten: {list(df.columns)}")
        
        # Versuche alternative Spaltennamen
        if not zsid_col:
            potential_zsid = [col for col in df.columns if 'id' in col.lower() and ('zs' in col.lower() or 'z_' in col.lower() or 'zaehlung' in col.lower())]
            if potential_zsid:
                zsid_col = potential_zsid[0]
                print(f"Alternative ZSID Spalte gefunden: {zsid_col}")
        
        if not zsname_col:
            potential_zsname = [col for col in df.columns if 'name' in col.lower() and ('zs' in col.lower() or 'zaehlung' in col.lower())]
            if potential_zsname:
                zsname_col = potential_zsname[0]
                print(f"Alternative ZSName Spalte gefunden: {zsname_col}")
                
        if not richtung_col:
            potential_richtung = [col for col in df.columns if 'richt' in col.lower() or 'direction' in col.lower()]
            if potential_richtung:
                richtung_col = potential_richtung[0]
                print(f"Alternative Richtung Spalte gefunden: {richtung_col}")
                
        if not all([zsid_col, zsname_col, richtung_col]):
            # Überprüfe, ob die Spalten möglicherweise in einer einzigen Spalte enthalten sind
            for col in df.columns:
                first_values = df[col].head(5).astype(str).tolist()
                print(f"Spalte '{col}' - Erste Werte: {first_values}")
            
            return
    
    print(f"Gefundene Spalten: ID={zsid_col}, Name={zsname_col}, Richtung={richtung_col}")
    
    # Eindeutige Zählstellen extrahieren
    counters_df = df[[zsid_col, zsname_col, richtung_col]].drop_duplicates()
    
    # Anzeigename hinzufügen
    counters_df['display_name'] = counters_df.apply(
        lambda row: f"{row[zsid_col]} - {row[zsname_col]} ({row[richtung_col]})", 
        axis=1
    )
    
    # Standardisierte Spaltennamen verwenden
    counters_df = counters_df.rename(columns={
        zsid_col: 'counter_id',
        zsname_col: 'name',
        richtung_col: 'direction'
    })
    
    # Zählstellen nach ID sortieren
    counters_df = counters_df.sort_values('counter_id')
    
    # Koordinaten laden (wenn vorhanden)
    try:
        # Versuche, Koordinaten aus der CSV zu extrahieren
        coords_cols = []
        for col in df.columns:
            if any(term in col.lower() for term in ['koorx', 'koord x', 'easting', 'east', 'ekoord']):
                coords_cols.append(col)
            if any(term in col.lower() for term in ['koory', 'koord y', 'northing', 'north', 'nkoord']):
                coords_cols.append(col)
        
        x_col = None
        y_col = None
        
        if len(coords_cols) >= 2:
            # Finde die passenden X und Y Spalten
            for col in coords_cols:
                if any(term in col.lower() for term in ['koorx', 'koord x', 'easting', 'east', 'ekoord']):
                    x_col = col
                if any(term in col.lower() for term in ['koory', 'koord y', 'northing', 'north', 'nkoord']):
                    y_col = col
            
            if x_col and y_col:
                print(f"Koordinatenspalten gefunden: X={x_col}, Y={y_col}")
                
                # Erste Koordinate für jede Zählstelle
                coords_df = df.groupby([zsid_col, richtung_col]).first().reset_index()
                coords_df = coords_df[[zsid_col, richtung_col, x_col, y_col]]
                
                # Koordinaten zu Zählstellen hinzufügen (Merge)
                counters_df = pd.merge(
                    counters_df,
                    coords_df.rename(columns={
                        zsid_col: 'counter_id',
                        richtung_col: 'direction',
                        x_col: 'x_coord',
                        y_col: 'y_coord'
                    }),
                    on=['counter_id', 'direction'],
                    how='left'
                )
            else:
                raise ValueError("Koordinatenspalten konnten nicht eindeutig identifiziert werden.")
        else:
            # Default-Koordinaten hinzufügen (Zürich Zentrum)
            counters_df['x_coord'] = 2683484.5  # Standardkoordinaten für Zürich (CH1903+ / LV95)
            counters_df['y_coord'] = 1247375.0
            print("Keine Koordinatenspalten gefunden. Verwende Standardkoordinaten.")
            
    except Exception as e:
        print(f"Fehler beim Verarbeiten der Koordinaten: {str(e)}")
        # Default-Koordinaten hinzufügen (Zürich Zentrum)
        counters_df['x_coord'] = 2683484.5
        counters_df['y_coord'] = 1247375.0
    
    # Als CSV speichern
    try:
        counters_df.to_csv(output_file, index=False)
        print(f"{len(counters_df)} Zählstellen wurden in {output_file} gespeichert.")
    except Exception as e:
        print(f"Fehler beim Speichern der Datei: {str(e)}")

if __name__ == "__main__":
    main() 