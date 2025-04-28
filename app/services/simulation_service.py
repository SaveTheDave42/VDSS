import os
import json
import pandas as pd
import geopandas as gpd
import numpy as np
import osmnx as ox
from shapely.geometry import Point, LineString, Polygon
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Any, Optional, Tuple

from app.models.simulation import SimulationRequest, SimulationResult, TrafficSegment, SimulationTimeStep
from app.services.project_service import get_project

# In-memory storage for simulation results
# Structure: project_id -> date -> hour -> SimulationResult
SIMULATION_RESULTS = {}

def run_simulation(request: SimulationRequest) -> SimulationResult:
    """
    Run a traffic simulation for a construction site project.
    
    Args:
        request: SimulationRequest with simulation parameters
        
    Returns:
        SimulationResult with the results of the simulation
        
    Raises:
        ValueError: If the project is not found or there's an issue with the input
    """
    # Get the project
    project = get_project(request.project_id)
    if not project:
        raise ValueError(f"Project {request.project_id} not found")
    
    # Validate dates
    if request.end_date < request.start_date:
        raise ValueError("End date must be after start date")
    
    # Load the Excel data
    excel_data = pd.read_excel(project.file_path)
    
    # Parse time interval
    interval_hours = _parse_time_interval(request.time_interval)
    
    # Create simulation results
    simulation_results = _simulate_traffic(
        project_id=request.project_id,
        polygon=project.polygon,
        waiting_areas=project.waiting_areas,
        access_routes=project.access_routes,
        map_bounds=project.map_bounds,
        deliveries=pd.read_excel(project.file_path, sheet_name="Deliveries"),
        vehicles=pd.read_excel(project.file_path, sheet_name="Vehicles"),
        schedule=pd.read_excel(project.file_path, sheet_name="Schedule"),
        start_date=request.start_date,
        end_date=request.end_date,
        interval_hours=interval_hours
    )
    
    # Store the results in memory
    for result in simulation_results:
        result_date = result.time_steps[0].time.date()
        result_hour = result.time_steps[0].time.hour
        
        if request.project_id not in SIMULATION_RESULTS:
            SIMULATION_RESULTS[request.project_id] = {}
        
        if result_date not in SIMULATION_RESULTS[request.project_id]:
            SIMULATION_RESULTS[request.project_id][result_date] = {}
        
        SIMULATION_RESULTS[request.project_id][result_date][result_hour] = result
    
    # Save the results to disk
    _save_simulation_results_to_disk(request.project_id)
    
    # For simplicity, return the first result
    # In a real application, you might return a summary or a specific time step
    return simulation_results[0] if simulation_results else None

def get_simulation_results(
    project_id: str,
    simulation_date: Optional[date] = None,
    hour: Optional[int] = None
) -> Optional[SimulationResult]:
    """
    Get simulation results for a project, optionally filtered by date and hour.
    
    Args:
        project_id: ID of the project
        simulation_date: Date to filter results
        hour: Hour to filter results
        
    Returns:
        SimulationResult if found, None otherwise
    """
    if project_id not in SIMULATION_RESULTS:
        # Try loading from disk first
        _load_simulation_results_from_disk(project_id)
        
        if project_id not in SIMULATION_RESULTS:
            return None
    
    # If no date specified, return the most recent result
    if simulation_date is None:
        if not SIMULATION_RESULTS[project_id]:
            return None
        
        # Get the most recent date
        most_recent_date = max(SIMULATION_RESULTS[project_id].keys())
        
        if hour is None:
            # Get the most recent hour
            most_recent_hour = max(SIMULATION_RESULTS[project_id][most_recent_date].keys())
            return SIMULATION_RESULTS[project_id][most_recent_date][most_recent_hour]
        else:
            # Get the specified hour
            if hour in SIMULATION_RESULTS[project_id][most_recent_date]:
                return SIMULATION_RESULTS[project_id][most_recent_date][hour]
            else:
                return None
    
    # If date is specified but doesn't exist
    if simulation_date not in SIMULATION_RESULTS[project_id]:
        return None
    
    # If hour is not specified, return the first hour
    if hour is None:
        if not SIMULATION_RESULTS[project_id][simulation_date]:
            return None
        first_hour = min(SIMULATION_RESULTS[project_id][simulation_date].keys())
        return SIMULATION_RESULTS[project_id][simulation_date][first_hour]
    
    # If hour is specified but doesn't exist
    if hour not in SIMULATION_RESULTS[project_id][simulation_date]:
        return None
    
    return SIMULATION_RESULTS[project_id][simulation_date][hour]

def _parse_time_interval(interval: str) -> float:
    """Parse a time interval string (e.g., "1h", "30m") to hours."""
    if interval.endswith("h"):
        return float(interval[:-1])
    elif interval.endswith("m"):
        return float(interval[:-1]) / 60
    else:
        try:
            return float(interval)
        except ValueError:
            return 1.0  # Default to 1 hour

def _simulate_traffic(
    project_id: str,
    polygon: Dict[str, Any],
    waiting_areas: List[Dict[str, Any]],
    access_routes: List[Dict[str, Any]],
    map_bounds: Dict[str, Any],
    deliveries: pd.DataFrame,
    vehicles: pd.DataFrame,
    schedule: pd.DataFrame,
    start_date: date,
    end_date: date,
    interval_hours: float
) -> List[SimulationResult]:
    """
    Simulate traffic based on project data and deliveries.
    
    This is a simplified simulation for demonstration purposes.
    In a production environment, you would use SUMO or a more sophisticated traffic simulator.
    
    Returns:
        List of SimulationResult objects
    """
    results = []
    
    # Convert polygon to shapely geometry
    site_polygon = _geojson_to_polygon(polygon)
    
    # Get the map data using OSMnx
    try:
        # Get network around the construction site
        center_point = site_polygon.centroid
        
        # Extract the bounding box coordinates
        north = map_bounds["coordinates"][0][0][1]
        south = map_bounds["coordinates"][0][2][1]
        east = map_bounds["coordinates"][0][1][0]
        west = map_bounds["coordinates"][0][0][0]
        
        # Get the road network
        G = ox.graph_from_bbox(north, south, east, west, network_type="drive")
        
        # Convert to GeoDataFrame for easier processing
        nodes, edges = ox.graph_to_gdfs(G)
        
        # Calculate current date
        current_date = start_date
        while current_date <= end_date:
            # Filter deliveries for the current date
            date_deliveries = deliveries[deliveries['Date'] == pd.Timestamp(current_date)]
            
            # Get the active construction phase
            active_phase = schedule[(schedule['StartDate'] <= pd.Timestamp(current_date)) & 
                                  (schedule['EndDate'] >= pd.Timestamp(current_date))]
            
            if active_phase.empty:
                current_date += timedelta(days=1)
                continue
            
            # For each hour of the day (6:00 to 18:00)
            for hour in range(6, 19):
                # Create a datetime for this simulation step
                sim_datetime = datetime.combine(current_date, time(hour=hour))
                
                # Filter deliveries for this time window
                # Assuming TimeWindow is stored as strings like "08:00-10:00"
                hour_deliveries = date_deliveries[date_deliveries['TimeWindow'].apply(
                    lambda x: hour >= int(x.split('-')[0].split(':')[0]) and 
                              hour <= int(x.split('-')[1].split(':')[0])
                )]
                
                # Count deliveries by vehicle type
                vehicle_counts = hour_deliveries['VehicleType'].value_counts().to_dict()
                
                # Simulate traffic on each road segment
                traffic_segments = []
                
                for idx, edge in edges.iterrows():
                    # Basic traffic formula:
                    # - Base traffic (higher during peak hours)
                    # - Additional traffic from construction deliveries
                    # - Congestion factor based on proximity to construction site
                    
                    # Calculate base traffic (simplified model)
                    if 7 <= hour <= 9 or 16 <= hour <= 18:  # Peak hours
                        base_traffic = np.random.randint(50, 200)  # Higher during peak
                    else:
                        base_traffic = np.random.randint(20, 100)
                    
                    # Calculate distance factor (traffic drops with distance from site)
                    edge_line = edge['geometry']
                    distance_to_site = edge_line.distance(site_polygon)
                    distance_factor = max(0.1, min(1.0, 1.0 / (0.1 + distance_factor)))
                    
                    # Calculate additional traffic from deliveries
                    delivery_traffic = sum(vehicle_counts.values()) * distance_factor * 2  # Each delivery is entry + exit
                    
                    # Total traffic
                    total_traffic = int(base_traffic + delivery_traffic)
                    
                    # Calculate congestion level (0.0 to 1.0)
                    # Simplified: assume capacity is proportional to road length
                    capacity = edge_line.length * 5  # Simplified capacity model
                    congestion_level = min(1.0, total_traffic / capacity) if capacity > 0 else 0.0
                    
                    # Create a TrafficSegment
                    segment = TrafficSegment(
                        segment_id=f"{idx[0]}_{idx[1]}",
                        start_node=str(idx[0]),
                        end_node=str(idx[1]),
                        length=edge_line.length,
                        speed_limit=edge.get('speed_kph', 50),
                        traffic_volume=total_traffic,
                        congestion_level=congestion_level,
                        coordinates=[[p[0], p[1]] for p in edge_line.coords]
                    )
                    
                    traffic_segments.append(segment)
                
                # Calculate waiting area status
                waiting_areas_status = {}
                for i, area in enumerate(waiting_areas):
                    # Simulate random occupancy
                    capacity = 5  # Assumed capacity
                    occupied = min(capacity, np.random.poisson(len(hour_deliveries) * 0.3))
                    
                    waiting_areas_status[f"area_{i}"] = {
                        "capacity": capacity,
                        "occupied": occupied,
                        "available": capacity - occupied
                    }
                
                # Create a time step
                time_step = SimulationTimeStep(
                    time=sim_datetime,
                    traffic_segments=traffic_segments,
                    waiting_areas_status=waiting_areas_status
                )
                
                # Create traffic volumes summary
                traffic_volumes = {}
                congestion_points = []
                
                for segment in traffic_segments:
                    traffic_volumes[segment.segment_id] = segment.traffic_volume
                    
                    if segment.congestion_level > 0.8:  # High congestion
                        congestion_points.append({
                            "segment_id": segment.segment_id,
                            "congestion_level": segment.congestion_level,
                            "coordinates": segment.coordinates
                        })
                
                # Calculate summary statistics
                stats = {
                    "total_traffic": sum(traffic_volumes.values()),
                    "average_congestion": sum(s.congestion_level for s in traffic_segments) / len(traffic_segments) if traffic_segments else 0,
                    "deliveries_count": len(hour_deliveries),
                    "construction_phase": active_phase.iloc[0]['Phase'] if not active_phase.empty else None
                }
                
                # Create a simulation result
                result = SimulationResult(
                    id=f"{project_id}_{current_date.isoformat()}_{hour}",
                    project_id=project_id,
                    execution_time=datetime.now(),
                    time_steps=[time_step],
                    traffic_volumes=traffic_volumes,
                    congestion_points=congestion_points,
                    stats=stats
                )
                
                results.append(result)
            
            # Move to the next day
            current_date += timedelta(days=1)
    
    except Exception as e:
        # In a production system, you would log this error
        print(f"Error in traffic simulation: {str(e)}")
        # Fallback to a very simple simulation if OSMnx fails
        results = _simple_fallback_simulation(
            project_id, start_date, end_date, deliveries
        )
    
    return results

def _simple_fallback_simulation(
    project_id: str,
    start_date: date,
    end_date: date,
    deliveries: pd.DataFrame
) -> List[SimulationResult]:
    """
    A very simple fallback simulation if the OSMnx-based simulation fails.
    This creates synthetic data without using real road networks.
    """
    results = []
    
    # Calculate current date
    current_date = start_date
    while current_date <= end_date:
        # Filter deliveries for the current date
        date_deliveries = deliveries[deliveries['Date'] == pd.Timestamp(current_date)]
        
        # For each hour of the day (6:00 to 18:00)
        for hour in range(6, 19):
            # Create a datetime for this simulation step
            sim_datetime = datetime.combine(current_date, time(hour=hour))
            
            # Filter deliveries for this time window
            # Assuming TimeWindow is stored as strings like "08:00-10:00"
            hour_deliveries = date_deliveries[date_deliveries['TimeWindow'].apply(
                lambda x: hour >= int(x.split('-')[0].split(':')[0]) and 
                        hour <= int(x.split('-')[1].split(':')[0])
            )]
            
            # Create synthetic traffic segments
            traffic_segments = []
            for i in range(5):  # Create 5 synthetic road segments
                segment = TrafficSegment(
                    segment_id=f"synthetic_{i}",
                    start_node=f"node_a_{i}",
                    end_node=f"node_b_{i}",
                    length=100 + i * 50,  # Synthetic length
                    speed_limit=50,
                    traffic_volume=50 + len(hour_deliveries) * 2 + np.random.randint(0, 50),
                    congestion_level=min(1.0, (0.3 + len(hour_deliveries) * 0.05 + np.random.random() * 0.2)),
                    coordinates=[[0, 0], [100 + i * 50, 0]]  # Synthetic coordinates
                )
                traffic_segments.append(segment)
            
            # Create synthetic waiting area status
            waiting_areas_status = {
                "area_0": {
                    "capacity": 5,
                    "occupied": min(5, len(hour_deliveries)),
                    "available": max(0, 5 - len(hour_deliveries))
                }
            }
            
            # Create a time step
            time_step = SimulationTimeStep(
                time=sim_datetime,
                traffic_segments=traffic_segments,
                waiting_areas_status=waiting_areas_status
            )
            
            # Create traffic volumes summary
            traffic_volumes = {segment.segment_id: segment.traffic_volume for segment in traffic_segments}
            
            # Create congestion points
            congestion_points = [
                {
                    "segment_id": segment.segment_id,
                    "congestion_level": segment.congestion_level,
                    "coordinates": segment.coordinates
                }
                for segment in traffic_segments if segment.congestion_level > 0.7
            ]
            
            # Calculate summary statistics
            stats = {
                "total_traffic": sum(traffic_volumes.values()),
                "average_congestion": sum(s.congestion_level for s in traffic_segments) / len(traffic_segments),
                "deliveries_count": len(hour_deliveries),
                "construction_phase": "Unknown Phase"  # Since we don't have the schedule in this fallback
            }
            
            # Create a simulation result
            result = SimulationResult(
                id=f"{project_id}_{current_date.isoformat()}_{hour}",
                project_id=project_id,
                execution_time=datetime.now(),
                time_steps=[time_step],
                traffic_volumes=traffic_volumes,
                congestion_points=congestion_points,
                stats=stats
            )
            
            results.append(result)
        
        # Move to the next day
        current_date += timedelta(days=1)
    
    return results

def _geojson_to_polygon(geojson: Dict[str, Any]) -> Polygon:
    """Convert a GeoJSON polygon to a shapely Polygon."""
    if geojson["type"] == "Polygon":
        return Polygon(geojson["coordinates"][0])
    elif geojson["type"] == "Feature" and geojson["geometry"]["type"] == "Polygon":
        return Polygon(geojson["geometry"]["coordinates"][0])
    else:
        raise ValueError(f"Unsupported GeoJSON type: {geojson['type']}")

def _save_simulation_results_to_disk(project_id: str) -> None:
    """Save simulation results to disk"""
    try:
        if project_id not in SIMULATION_RESULTS:
            return
        
        # Create directory structure
        sim_dir = f"data/simulations/{project_id}"
        os.makedirs(sim_dir, exist_ok=True)
        
        # Save each date's results
        for date_str, hours in SIMULATION_RESULTS[project_id].items():
            date_dir = f"{sim_dir}/{date_str}"
            os.makedirs(date_dir, exist_ok=True)
            
            for hour, result in hours.items():
                file_path = f"{date_dir}/{hour}.json"
                with open(file_path, "w") as f:
                    # Convert to dict and serialize
                    json.dump(result.dict(), f, default=str, indent=2)
        
    except Exception as e:
        print(f"Error saving simulation results: {str(e)}")

def _load_simulation_results_from_disk(project_id: str) -> None:
    """Load simulation results from disk"""
    try:
        # Check if the directory exists
        sim_dir = f"data/simulations/{project_id}"
        if not os.path.exists(sim_dir):
            return
        
        # Initialize the project
        SIMULATION_RESULTS[project_id] = {}
        
        # Iterate through date directories
        for date_dir in os.listdir(sim_dir):
            date_path = os.path.join(sim_dir, date_dir)
            
            if os.path.isdir(date_path):
                try:
                    # Parse the date
                    current_date = datetime.strptime(date_dir, "%Y-%m-%d").date()
                    SIMULATION_RESULTS[project_id][current_date] = {}
                    
                    # Iterate through hour files
                    for hour_file in os.listdir(date_path):
                        if hour_file.endswith(".json"):
                            hour = int(hour_file.split(".")[0])
                            file_path = os.path.join(date_path, hour_file)
                            
                            with open(file_path, "r") as f:
                                result_dict = json.load(f)
                                result = SimulationResult(**result_dict)
                                SIMULATION_RESULTS[project_id][current_date][hour] = result
                                
                except ValueError:
                    # Skip if directory name is not a valid date
                    continue
        
    except Exception as e:
        print(f"Error loading simulation results: {str(e)}") 