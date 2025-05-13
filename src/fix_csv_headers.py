#!/usr/bin/env python3
"""
Dieses Skript korrigiert den Header einer CSV-Datei, die falsch formatierte Anführungszeichen hat.
Es erstellt eine neue, bereinigte CSV-Datei mit korrekt formatierten Spaltenüberschriften.
"""

import os
import sys
import pandas as pd

def fix_csv_header(input_file, output_file=None):
    """Korrigiert den Header einer CSV-Datei mit falschen Anführungszeichen"""
    if not os.path.exists(input_file):
        print(f"Fehler: Datei '{input_file}' nicht gefunden.")
        return False
    
    # Bestimme den Ausgabedateinamen, falls nicht angegeben
    if output_file is None:
        basename = os.path.basename(input_file)
        dirname = os.path.dirname(input_file)
        name_parts = os.path.splitext(basename)
        output_file = os.path.join(dirname, f"{name_parts[0]}_fixed{name_parts[1]}")
    
    print(f"Verarbeite CSV-Datei: {input_file}")
    print(f"Ausgabe wird in: {output_file} gespeichert")
    
    # Lese die erste Zeile, um das Format zu bestimmen
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            header_line = f.readline().strip()
            
            # Bestimme das Trennzeichen
            if ',' in header_line and ';' not in header_line:
                sep = ','
            elif ';' in header_line and ',' not in header_line:
                sep = ';'
            else:
                # Wenn beides vorkommt, prüfe welches häufiger ist
                comma_count = header_line.count(',')
                semicolon_count = header_line.count(';')
                sep = ',' if comma_count > semicolon_count else ';'
            
            print(f"Erkanntes Trennzeichen: '{sep}'")
            
            # Extrahiere Spaltenheader
            if '","' in header_line:
                # Format: "col1","col2","col3"
                fields = header_line.split('","')
                if fields[0].startswith('"'):
                    fields[0] = fields[0][1:]
                if fields[-1].endswith('"'):
                    fields[-1] = fields[-1][:-1]
                print("Format erkannt: Spalten in Anführungszeichen")
            else:
                fields = header_line.split(sep)
                print("Format erkannt: Einfache Trennung durch Separator")
            
            # Bereinige Anführungszeichen aus allen Spalten
            clean_fields = [field.strip('"') for field in fields]
            
            print(f"Original-Header ({len(fields)} Spalten): {header_line[:100]}...")
            print(f"Bereinigter Header ({len(clean_fields)} Spalten): {sep.join(clean_fields)[:100]}...")
            
            # Lese den Rest der Datei
            data_lines = f.readlines()
    except Exception as e:
        print(f"Fehler beim Lesen der Datei: {str(e)}")
        return False
    
    # Schreibe die korrigierte Datei
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Schreibe den bereinigten Header
            f.write(sep.join(clean_fields) + '\n')
            
            # Schreibe den Rest der Datei unverändert
            f.writelines(data_lines)
        
        print(f"Korrigierte CSV-Datei gespeichert als: {output_file}")
        print(f"Die Datei enthält {len(data_lines) + 1} Zeilen.")
        return True
    except Exception as e:
        print(f"Fehler beim Schreiben der Ausgabedatei: {str(e)}")
        return False

def main():
    # Pfad zur CSV-Datei
    input_file = "data/imports/raw/verkehr_2024.csv"
    output_file = "data/imports/raw/verkehr_2024_fixed.csv"
    
    # Kommandozeilenargumente prüfen
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    # Führe die Header-Korrektur durch
    if fix_csv_header(input_file, output_file):
        print("Header-Korrektur erfolgreich abgeschlossen.")
        
        # Versuche, die korrigierte Datei zu lesen, um zu prüfen, ob sie korrekt ist
        try:
            print("Teste das Einlesen der korrigierten Datei...")
            # Bestimme das Trennzeichen neu, um sicherzustellen, dass wir dasselbe verwenden
            with open(output_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if ',' in first_line and ';' not in first_line:
                    sep = ','
                elif ';' in first_line and ',' not in first_line:
                    sep = ';'
                else:
                    sep = ',' if first_line.count(',') > first_line.count(';') else ';'
            
            df = pd.read_csv(output_file, sep=sep, nrows=5)
            print(f"Erfolg! Die korrigierte Datei konnte gelesen werden.")
            print(f"Erkannte Spalten ({len(df.columns)}):")
            for col in df.columns:
                print(f"  - {col}")
        except Exception as e:
            print(f"Warnung: Die korrigierte Datei konnte nicht gelesen werden: {str(e)}")
    else:
        print("Header-Korrektur fehlgeschlagen.")

if __name__ == "__main__":
    main() 