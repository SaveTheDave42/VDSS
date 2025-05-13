#!/usr/bin/env python3
"""
Dieses Skript analysiert die CSV-Datei und zeigt Details zur Struktur an,
um Probleme mit dem Einlesen zu identifizieren.
"""

import pandas as pd
import csv
import os
import sys

def main():
    # Pfad zur CSV-Datei
    input_file = "data/imports/raw/verkehr_2024.csv"
    
    print(f"Analysiere CSV-Datei: {input_file}")
    print("-" * 50)
    
    if not os.path.exists(input_file):
        print(f"Fehler: Die Datei {input_file} existiert nicht.")
        return
    
    # 1. Einfache Datei-Info
    file_size = os.path.getsize(input_file) / (1024 * 1024)  # in MB
    print(f"Dateigröße: {file_size:.2f} MB")
    
    # 2. Erste Zeilen direkt lesen
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            print("\nErste 5 Zeilen der Datei:")
            for i, line in enumerate(f):
                if i >= 5:
                    break
                print(f"Zeile {i+1}: {line.strip()}")
                if i == 0:  # Header-Zeile
                    header = line.strip()
                    print(f"  - Länge: {len(header)} Zeichen")
                    print(f"  - Anzahl Kommas: {header.count(',')}")
                    print(f"  - Anzahl Semikolons: {header.count(';')}")
                    print(f"  - Anzahl Anführungszeichen: {header.count('"')}")
    except Exception as e:
        print(f"Fehler beim direkten Lesen: {str(e)}")
    
    # 3. Verschiedene Einlesemethoden versuchen
    print("\nVersuch 1: Standard pandas.read_csv mit Semikolon")
    try:
        df = pd.read_csv(input_file, sep=';', nrows=5)
        print(f"Erfolgreich! Gefundene Spalten ({len(df.columns)}):")
        for col in df.columns:
            print(f"  - {col}")
    except Exception as e:
        print(f"Fehler: {str(e)}")
    
    print("\nVersuch 2: pandas.read_csv mit Komma")
    try:
        df = pd.read_csv(input_file, sep=',', nrows=5)
        print(f"Erfolgreich! Gefundene Spalten ({len(df.columns)}):")
        for col in df.columns:
            print(f"  - {col}")
    except Exception as e:
        print(f"Fehler: {str(e)}")
    
    print("\nVersuch 3: pandas.read_csv mit Python-Engine")
    try:
        df = pd.read_csv(input_file, sep=None, engine='python', nrows=5)
        print(f"Erfolgreich! Gefundene Spalten ({len(df.columns)}):")
        for col in df.columns:
            print(f"  - {col}")
    except Exception as e:
        print(f"Fehler: {str(e)}")
    
    print("\nVersuch 4: pandas.read_csv mit Anführungszeichen-Handling")
    try:
        df = pd.read_csv(input_file, sep=';', quoting=csv.QUOTE_NONE, nrows=5, escapechar='\\')
        print(f"Erfolgreich! Gefundene Spalten ({len(df.columns)}):")
        for col in df.columns:
            print(f"  - {col}")
    except Exception as e:
        print(f"Fehler: {str(e)}")
    
    # 4. Manuelle Analyse des Headers
    print("\nManuelle Header-Analyse:")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            header_line = f.readline().strip()
            
            if ',' in header_line and ';' not in header_line:
                sep = ','
            elif ';' in header_line and ',' not in header_line:
                sep = ';'
            else:
                comma_count = header_line.count(',')
                semicolon_count = header_line.count(';')
                sep = ',' if comma_count > semicolon_count else ';'
            
            print(f"Erkanntes Trennzeichen: '{sep}'")
            
            if '","' in header_line:
                # Format: "col1","col2","col3"
                fields = header_line.split('","')
                if fields[0].startswith('"'):
                    fields[0] = fields[0][1:]
                if fields[-1].endswith('"'):
                    fields[-1] = fields[-1][:-1]
                print(f"Erkannt als Format: \"spalte1\",\"spalte2\",...")
            else:
                fields = header_line.split(sep)
                print(f"Erkannt als Format: spalte1{sep}spalte2{sep}...")
            
            print(f"Anzahl Felder im Header: {len(fields)}")
            print("Erste 5 Felder:")
            for i, field in enumerate(fields[:5]):
                print(f"  {i+1}. '{field}'")
    except Exception as e:
        print(f"Fehler bei Header-Analyse: {str(e)}")
    
    # 5. Versuch mit manuell bereinigtem Header
    print("\nVersuch mit manuell bereinigtem Header:")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            header_line = f.readline().strip()
            data_lines = [f.readline() for _ in range(5)]
        
        # Header bereinigen
        if header_line.startswith('"') and header_line.endswith('"'):
            header_line = header_line[1:-1]
        
        if '","' in header_line:
            fields = header_line.split('","')
        else:
            fields = header_line.split(sep)
        
        clean_fields = [field.strip('"') for field in fields]
        print(f"Bereinigte Felder ({len(clean_fields)}):")
        for i, field in enumerate(clean_fields[:10]):
            print(f"  {i+1}. '{field}'")
        
        # Temporäre Datei mit bereinigtem Header erstellen
        temp_file = input_file + ".clean"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(sep.join(clean_fields) + '\n')
            for line in data_lines:
                f.write(line)
        
        # Versuche, die bereinigte Datei zu lesen
        df = pd.read_csv(temp_file, sep=sep, nrows=5)
        print(f"Erfolgreich! Gefundene Spalten nach Bereinigung ({len(df.columns)}):")
        for col in df.columns:
            print(f"  - {col}")
        
        # Lösche temporäre Datei
        os.remove(temp_file)
    except Exception as e:
        print(f"Fehler bei Bereinigungsversuch: {str(e)}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    main() 