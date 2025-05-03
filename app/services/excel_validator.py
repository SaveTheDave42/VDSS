import pandas as pd
import io
from typing import Dict, List, Any

def validate_excel(file_content: bytes) -> Dict[str, Any]:
    """
    Validate Excel or CSV file
    """
    try:
        # Try to detect file type from first few bytes
        file_obj = io.BytesIO(file_content)
        
        # Try to read as Excel first
        try:
            df = pd.read_excel(file_obj, engine='openpyxl')
            file_format = "excel"
        except Exception as excel_err:
            # If Excel fails, try as CSV
            file_obj.seek(0)  # Reset file pointer
            try:
                df = pd.read_csv(file_obj)
                file_format = "csv"
            except Exception as csv_err:
                return {
                    "valid": False,
                    "errors": [
                        f"File is neither a valid Excel nor CSV file. Excel error: {str(excel_err)}. CSV error: {str(csv_err)}"
                    ]
                }
        
        # Lowercase column names for case-insensitive comparison
        df_columns_lower = [col.lower() for col in df.columns]
        
        # Required columns check
        required_columns = ["vorgangsname", "anfangstermin", "endtermin", "material"]
        missing_columns = [col for col in required_columns if col not in df_columns_lower]
        
        if missing_columns:
            return {
                "valid": False,
                "errors": [f"Missing required columns: {', '.join(missing_columns)}"]
            }
        
        # Map actual column names to required column names
        column_mapping = {}
        for req_col in required_columns:
            idx = df_columns_lower.index(req_col)
            actual_col = df.columns[idx]
            column_mapping[actual_col] = req_col
        
        # Rename columns to standardized names
        df_standardized = df.rename(columns=column_mapping)
        
        # Check date columns
        try:
            df_standardized['anfangstermin'] = pd.to_datetime(df_standardized['anfangstermin'])
            df_standardized['endtermin'] = pd.to_datetime(df_standardized['endtermin'])
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Invalid date format in 'anfangstermin' or 'endtermin' columns: {str(e)}"]
            }
        
        # Check material column is numeric
        try:
            df_standardized['material'] = pd.to_numeric(df_standardized['material'])
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Invalid numeric format in 'material' column: {str(e)}"]
            }
        
        return {
            "valid": True,
            "data": df_standardized,
            "format": file_format
        }
    
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Invalid file: {str(e)}"]
        } 