import pandas as pd
import locale
from datetime import datetime

def get_max_hierarchy_level(df):
    return max(len(str(psp).split('.')) for psp in df['PSP_Code'].dropna())

def convert_date_format(date_str):
    if pd.isna(date_str):
        return date_str
    
    # Map German month names to numbers
    german_months = {
        'Januar': '01', 'Februar': '02', 'März': '03', 'April': '04',
        'Mai': '05', 'Juni': '06', 'Juli': '07', 'August': '08',
        'September': '09', 'Oktober': '10', 'November': '11', 'Dezember': '12'
    }
    
    try:
        # Format: "13 Dezember 2021 08:00"
        parts = date_str.split()
        if len(parts) >= 4:
            day = parts[0].zfill(2)
            month = german_months[parts[1]]
            year = parts[2]
            time = parts[3]
            
            # Create ISO format: YYYY-MM-DD HH:MM
            return f"{year}-{month}-{day} {time}"
        return date_str
    except Exception:
        # Return original if conversion fails
        return date_str

def get_hierarchical_info(df):
    df_new = df.copy()
    max_level = get_max_hierarchy_level(df)
    
    # Neue Spalten für Hierarchieebene und Subtitel
    df_new['Hierarchieebene'] = ''
    df_new['Subtitel'] = ''
    
    # Hierarchien und Ebenen füllen
    for idx, row in df_new.iterrows():
        if pd.isna(row['PSP_Code']):
            continue
            
        psp_parts = str(row['PSP_Code']).split('.')
        current_level = len(psp_parts) - 1
        
        # Hierarchie-Level setzen
        next_level_exists = False
        for other_psp in df_new['PSP_Code'].dropna():
            if str(other_psp).startswith(str(row['PSP_Code']) + '.'):
                next_level_exists = True
                break
                
        if not next_level_exists:
            df_new.at[idx, 'Hierarchieebene'] = 'Vorgang'
        else:
            df_new.at[idx, 'Hierarchieebene'] = f'Subtitel {current_level}'
        
        # Übergeordnete Vorgänge in einer Spalte mit "-" Trennzeichen sammeln
        subtitles = []
        for level in range(len(psp_parts) - 1):
            parent_psp = '.'.join(psp_parts[:level + 1])
            parent_row = df_new[df_new['PSP_Code'] == parent_psp]
            if not parent_row.empty:
                subtitles.append(parent_row.iloc[0]['Vorgangsname'])
        
        # Subtitel mit "-" verbinden
        df_new.at[idx, 'Subtitel'] = ' - '.join(subtitles) if subtitles else ''
    
    # Spalten sortieren
    cols_order = ['PSP_Code', 'Hierarchieebene', 'Vorgangsname', 'Subtitel'] + [col for col in df_new.columns if col not in ['PSP_Code', 'Hierarchieebene', 'Vorgangsname', 'Subtitel']]
    df_new = df_new[cols_order]
    
    return df_new

# Ausführung
df = pd.read_excel('Terminprogramm_20240923.xlsx')
df_cleaned = get_hierarchical_info(df)

# Datumsformate konvertieren
if 'Anfangstermin' in df_cleaned.columns:
    df_cleaned['Anfangstermin'] = df_cleaned['Anfangstermin'].apply(convert_date_format)
if 'Endtermin' in df_cleaned.columns:
    df_cleaned['Endtermin'] = df_cleaned['Endtermin'].apply(convert_date_format)

# Nur Zeilen mit Material behalten
if 'Material' or 'Personen' in df_cleaned.columns:
    df_filtered = df_cleaned[df_cleaned['Material'].notna() & (df_cleaned['Material'] != '')]
else:
    df_filtered = df_cleaned
    print("Warnung: Spalte 'Material' nicht gefunden!")

# Nur relevante Spalten behalten
relevant_columns = ['Einmalige_NR', 'Vorgangsname', 'Anfangstermin', 'Endtermin', 'Material', 'Personen', 'Geschoss']
available_columns = [col for col in relevant_columns if col in df_filtered.columns]

if len(available_columns) < len(relevant_columns):
    missing_columns = set(relevant_columns) - set(available_columns)
    print(f"Warnung: Folgende Spalten wurden nicht gefunden: {', '.join(missing_columns)}")

df_result = df_filtered[available_columns]

# In CSV speichern
df_result.to_csv('Material_Lieferungen.csv', index=False)

# Debug-Ausgabe
print(f"Anzahl Zeilen mit Material: {len(df_result)}")
print(df_result.head(10))