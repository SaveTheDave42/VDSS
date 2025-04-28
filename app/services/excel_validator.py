import pandas as pd
import io
from typing import Dict, List, Any, Optional

def validate_excel(excel_data: bytes) -> Dict[str, Any]:
    """
    Validates the structure and content of the construction site Excel file.
    
    Args:
        excel_data: Bytes of the uploaded Excel file
        
    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "errors": List[str],
            "data": Optional[Dict[str, Any]]  # Extracted data if valid
        }
    """
    try:
        # Try to read the Excel file
        excel_buffer = io.BytesIO(excel_data)
        
        # Check if the file can be opened as Excel
        try:
            xls = pd.ExcelFile(excel_buffer)
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Invalid Excel file: {str(e)}"],
                "data": None
            }
        
        # Expected sheets
        required_sheets = ["Deliveries", "Schedule", "Vehicles"]
        missing_sheets = [sheet for sheet in required_sheets if sheet not in xls.sheet_names]
        
        if missing_sheets:
            return {
                "valid": False,
                "errors": [f"Missing required sheets: {', '.join(missing_sheets)}"],
                "data": None
            }
        
        # Validate the Deliveries sheet
        deliveries_df = pd.read_excel(excel_buffer, sheet_name="Deliveries")
        
        # Check required columns
        required_delivery_columns = ["DeliveryID", "Date", "TimeWindow", "VehicleType", "Weight"]
        missing_delivery_columns = [col for col in required_delivery_columns if col not in deliveries_df.columns]
        
        if missing_delivery_columns:
            return {
                "valid": False,
                "errors": [f"Missing required columns in Deliveries sheet: {', '.join(missing_delivery_columns)}"],
                "data": None
            }
        
        # Validate the Schedule sheet
        schedule_df = pd.read_excel(excel_buffer, sheet_name="Schedule")
        
        # Check required columns
        required_schedule_columns = ["Phase", "StartDate", "EndDate", "Description"]
        missing_schedule_columns = [col for col in required_schedule_columns if col not in schedule_df.columns]
        
        if missing_schedule_columns:
            return {
                "valid": False,
                "errors": [f"Missing required columns in Schedule sheet: {', '.join(missing_schedule_columns)}"],
                "data": None
            }
        
        # Validate the Vehicles sheet
        vehicles_df = pd.read_excel(excel_buffer, sheet_name="Vehicles")
        
        # Check required columns
        required_vehicle_columns = ["VehicleType", "Length", "Width", "Weight"]
        missing_vehicle_columns = [col for col in required_vehicle_columns if col not in vehicles_df.columns]
        
        if missing_vehicle_columns:
            return {
                "valid": False,
                "errors": [f"Missing required columns in Vehicles sheet: {', '.join(missing_vehicle_columns)}"],
                "data": None
            }
        
        # If we made it here, the Excel file is valid
        extracted_data = {
            "deliveries": deliveries_df.to_dict(orient="records"),
            "schedule": schedule_df.to_dict(orient="records"),
            "vehicles": vehicles_df.to_dict(orient="records")
        }
        
        return {
            "valid": True,
            "errors": [],
            "data": extracted_data
        }
        
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Error validating Excel file: {str(e)}"],
            "data": None
        } 