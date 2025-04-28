from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime, time, timedelta

from app.models.simulation import SimulationRequest, SimulationResult
from app.services.simulation_service import run_simulation, get_simulation_results

router = APIRouter()

@router.post("/run", response_model=SimulationResult)
async def run_simulation_endpoint(request: SimulationRequest):
    """Run a traffic simulation for a construction site project"""
    try:
        return run_simulation(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

@router.get("/{project_id}/results", response_model=SimulationResult)
async def get_simulation_results_endpoint(
    project_id: str,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    hour: Optional[int] = Query(None, description="Hour of the day (0-23)")
):
    """Get simulation results for a project, optionally filtered by date and hour"""
    try:
        # Parse date if provided
        parsed_date = None
        if date:
            try:
                parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Validate hour if provided
        if hour is not None and (hour < 0 or hour > 23):
            raise HTTPException(status_code=400, detail="Hour must be between 0 and 23")
            
        return get_simulation_results(project_id, parsed_date, hour)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve simulation results: {str(e)}")

@router.get("/{project_id}/daily-traffic", response_model=Dict[str, Any])
async def get_daily_traffic_endpoint(
    project_id: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    """Get hourly traffic data for a specific day"""
    try:
        # Parse date
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            
        # Get hourly results for the entire day
        results = {}
        for hour in range(24):
            hour_results = get_simulation_results(project_id, parsed_date, hour)
            if hour_results:
                results[hour] = hour_results
                
        return {
            "project_id": project_id,
            "date": date,
            "hourly_traffic": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve daily traffic data: {str(e)}")

@router.get("/{project_id}/weekly-traffic", response_model=Dict[str, Any])
async def get_weekly_traffic_endpoint(
    project_id: str,
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format")
):
    """Get daily traffic data for a week starting from the given date"""
    try:
        # Parse start date
        try:
            parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            
        # Get daily results for the week
        results = {}
        for day_offset in range(7):
            current_date = parsed_start_date + timedelta(days=day_offset)
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Calculate daily traffic stats
            daily_stats = {
                "total_vehicles": 0,
                "peak_hour": None,
                "peak_traffic": 0,
                "hourly_data": {}
            }
            
            for hour in range(6, 19):  # 6 AM to 6 PM
                hour_results = get_simulation_results(project_id, current_date, hour)
                if hour_results:
                    traffic_volume = sum(hour_results.get("traffic_volumes", {}).values())
                    daily_stats["hourly_data"][hour] = traffic_volume
                    daily_stats["total_vehicles"] += traffic_volume
                    
                    if traffic_volume > daily_stats["peak_traffic"]:
                        daily_stats["peak_traffic"] = traffic_volume
                        daily_stats["peak_hour"] = hour
            
            results[date_str] = daily_stats
                
        return {
            "project_id": project_id,
            "start_date": start_date,
            "end_date": (parsed_start_date + timedelta(days=6)).strftime("%Y-%m-%d"),
            "daily_traffic": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve weekly traffic data: {str(e)}") 