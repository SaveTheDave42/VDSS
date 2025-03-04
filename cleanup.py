import pandas as pd

def get_max_hierarchy_level(df):
    return max(len(str(psp).split('.')) for psp in df['PSP_Code'].dropna())

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
df_cleaned.to_excel('Bauprogramm_bereinigt_hierarchie.xlsx', index=False)

# Debug-Ausgabe
print(df_cleaned[['PSP_Code', 'Hierarchieebene', 'Vorgangsname', 'Subtitel']].head(15))