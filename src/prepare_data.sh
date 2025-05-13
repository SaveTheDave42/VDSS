#!/bin/bash
# Dieses Skript führt die Vorverarbeitungs-Skripte aus, um
# die Zählstellen und Verkehrsprofile zu extrahieren und zu berechnen.

echo "=== Verkehrsdaten Vorverarbeitung ==="
echo ""

# Verzeichnisse erstellen
if [ ! -d "data/prepared" ]; then
    mkdir -p data/prepared/profiles
    echo "Verzeichnis data/prepared erstellt."
fi

# 0. Analysiere die CSV-Datei
echo "0. Analyse der CSV-Datei..."
python src/analyze_csv.py
echo "   Analyse abgeschlossen."
echo ""

# 1. Korrigiere die CSV-Datei
echo "1. Korrigiere die CSV-Header..."
python src/fix_csv_headers.py
echo ""

# Frage, ob mit der Vorverarbeitung fortgefahren werden soll
read -p "Mit der Vorverarbeitung fortfahren? (j/n): " answer
if [ "$answer" != "j" ] && [ "$answer" != "J" ]; then
    echo "Vorverarbeitung abgebrochen."
    exit 0
fi

echo ""
echo "2. Zählstellen extrahieren..."
# Verwende die korrigierte Datei
python src/prepare_counters.py "data/imports/raw/verkehr_2024_fixed.csv"

echo ""
echo "3. Verkehrsprofile berechnen..."
# Verwende die korrigierte Datei
python src/prepare_profiles.py "data/imports/raw/verkehr_2024_fixed.csv"

echo ""
echo "Vorverarbeitung abgeschlossen!"
echo "Die Daten wurden in 'data/prepared/' gespeichert." 