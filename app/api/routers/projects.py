from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import json
import os
from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, LineString

from app.models.project import Project, ProjectCreate, ProjectUpdate
from app.services.excel_validator import validate_excel
from app.services.project_service import create_project, get_project, update_project, get_all_projects, delete_project

router = APIRouter()

def process_geojson(geojson_data):
    """
    Process GeoJSON data to ensure it's in the expected format.
    Extracts geometry from FeatureCollection and ensures coordinates are preserved.
    """
    if not geojson_data:
        return None # Return None if no data
        
    # Check if it's a FeatureCollection
    if isinstance(geojson_data, dict) and geojson_data.get('type') == 'FeatureCollection':
        # Get the first feature's geometry if available
        if geojson_data.get('features') and len(geojson_data['features']) > 0:
            feature = geojson_data['features'][0]
            if 'geometry' in feature:
                # Return the geometry directly to preserve coordinates
                return feature['geometry']
        # Return None if no features
        return None
    
    # If it's already a geometry with coordinates, return as is
    elif isinstance(geojson_data, dict) and 'type' in geojson_data and 'coordinates' in geojson_data:
        return geojson_data
    
    # If it's a list, check if it's a list of geometries
    elif isinstance(geojson_data, list):
        # If it's a list of geometries, return the first one
        if geojson_data and isinstance(geojson_data[0], dict) and 'type' in geojson_data[0] and 'coordinates' in geojson_data[0]:
            return geojson_data[0]
        # Otherwise, return empty list (for waiting_areas/access_routes) or None for single geometries
        return [] 
    
    # Return None for invalid data
    return None

@router.post("/", response_model=Project)
async def create_project_endpoint(
    file: UploadFile = File(...),
    name: str = Form(...),
    polygon: str = Form(...), # GeoJSON
    waiting_areas: Optional[str] = Form(None), # GeoJSON
    access_routes: Optional[str] = Form(None), # GeoJSON
    map_bounds: str = Form(...), # GeoJSON
    # Add traffic data fields
    primary_counter: Optional[str] = Form(None), # JSON string of primary counter object
    selected_counters: Optional[str] = Form(None), # JSON string of list of selected counter objects
    delivery_days: Optional[str] = Form(None), # JSON string of list of delivery days
    delivery_hours: Optional[str] = Form(None) # JSON string of delivery hours dict
):
    """Create a new construction site project"""
    try:
        # Get file content
        file_content = await file.read()
        
        # Determine file extension
        file_extension = file.filename.split(".")[-1].lower()
        
        # Validate the file (Excel or CSV)
        validation_result = validate_excel(file_content)
        
        if not validation_result["valid"]:
            return JSONResponse(
                status_code=400,
                content={"message": "Invalid file", "errors": validation_result["errors"]}
            )
        
        # Parse and process GeoJSON data to ensure correct format
        polygon_data = process_geojson(json.loads(polygon))
        map_bounds_data = process_geojson(json.loads(map_bounds))
        
        # Waiting areas and access routes are processed differently
        waiting_areas_json = json.loads(waiting_areas) if waiting_areas else []
        access_routes_json = json.loads(access_routes) if access_routes else []
        
        waiting_areas_data = []
        if waiting_areas_json:
            if isinstance(waiting_areas_json, dict) and waiting_areas_json.get('type') == 'FeatureCollection':
                for feature in waiting_areas_json.get('features', []):
                    if 'geometry' in feature:
                        waiting_areas_data.append(feature['geometry'])
            elif isinstance(waiting_areas_json, list): # Handle list of geometries
                waiting_areas_data = waiting_areas_json
            else: # Single geometry
                waiting_areas_data = [waiting_areas_json]
        
        access_routes_data = []
        if access_routes_json:
            if isinstance(access_routes_json, dict) and access_routes_json.get('type') == 'FeatureCollection':
                for feature in access_routes_json.get('features', []):
                    if 'geometry' in feature:
                        access_routes_data.append(feature['geometry'])
            elif isinstance(access_routes_json, list): # Handle list of geometries
                access_routes_data = access_routes_json
            else: # Single geometry
                access_routes_data = [access_routes_json]

        # Parse traffic data from JSON strings
        primary_counter_data = json.loads(primary_counter) if primary_counter else None
        selected_counters_data = json.loads(selected_counters) if selected_counters else []
        delivery_days_data = json.loads(delivery_days) if delivery_days else []
        delivery_hours_data = json.loads(delivery_hours) if delivery_hours else {}
        
        # Create project
        project_data = ProjectCreate(
            name=name,
            file_name=file.filename,
            polygon=polygon_data,
            waiting_areas=waiting_areas_data,
            access_routes=access_routes_data,
            map_bounds=map_bounds_data,
            simulation_start_time="06:00",
            simulation_end_time="18:00",
            simulation_interval="1h",
            created_at=datetime.now(),
            # Add traffic data to ProjectCreate model
            primary_counter=primary_counter_data,
            selected_counters=selected_counters_data,
            delivery_days=delivery_days_data,
            delivery_hours=delivery_hours_data
        )
        
        # Save file to disk
        file_path = f"data/projects/{name}/{file.filename}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return create_project(project_data, file_path)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.get("/", response_model=List[Project])
async def get_projects():
    """Get all projects"""
    return get_all_projects()

@router.get("/{project_id}", response_model=Project)
async def get_project_by_id(project_id: str):
    """Get a project by ID"""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project

@router.put("/{project_id}", response_model=Project)
async def update_project_endpoint(
    project_id: str,
    file: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    polygon: Optional[str] = Form(None),
    waiting_areas: Optional[str] = Form(None),
    access_routes: Optional[str] = Form(None),
    map_bounds: Optional[str] = Form(None),
    simulation_start_time: Optional[str] = Form(None),
    simulation_end_time: Optional[str] = Form(None),
    simulation_interval: Optional[str] = Form(None)
):
    """Update a project"""
    try:
        # Get existing project
        existing_project = get_project(project_id)
        if not existing_project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        
        # Prepare update data
        update_data = {}
        
        if name:
            update_data["name"] = name
        
        # Process new file if uploaded
        if file:
            file_content = await file.read()
            validation_result = validate_excel(file_content)
            
            if not validation_result["valid"]:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Invalid file", "errors": validation_result["errors"]}
                )
            
            # Save new file
            project_name = name or existing_project.name
            file_path = f"data/projects/{project_name}/{file.filename}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            update_data["file_name"] = file.filename
            update_data["file_path"] = file_path
        
        # Process GeoJSON data
        if polygon:
            update_data["polygon"] = process_geojson(json.loads(polygon))
        
        if map_bounds:
            update_data["map_bounds"] = process_geojson(json.loads(map_bounds))
        
        # Special handling for waiting areas and access routes
        if waiting_areas:
            waiting_areas_json = json.loads(waiting_areas)
            if isinstance(waiting_areas_json, dict) and waiting_areas_json.get('type') == 'FeatureCollection':
                # Get all geometries from features
                waiting_areas_data = []
                for feature in waiting_areas_json.get('features', []):
                    if 'geometry' in feature:
                        waiting_areas_data.append(feature['geometry'])
                update_data["waiting_areas"] = waiting_areas_data
            else:
                update_data["waiting_areas"] = [waiting_areas_json] if waiting_areas_json else []
        
        if access_routes:
            access_routes_json = json.loads(access_routes)
            if isinstance(access_routes_json, dict) and access_routes_json.get('type') == 'FeatureCollection':
                # Get all geometries from features
                access_routes_data = []
                for feature in access_routes_json.get('features', []):
                    if 'geometry' in feature:
                        access_routes_data.append(feature['geometry'])
                update_data["access_routes"] = access_routes_data
            else:
                update_data["access_routes"] = [access_routes_json] if access_routes_json else []
        
        # Process simulation parameters
        if simulation_start_time:
            update_data["simulation_start_time"] = simulation_start_time
        
        if simulation_end_time:
            update_data["simulation_end_time"] = simulation_end_time
        
        if simulation_interval:
            update_data["simulation_interval"] = simulation_interval
        
        # Update project
        project_update = ProjectUpdate(**update_data)
        return update_project(project_id, project_update)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")

@router.delete("/{project_id}")
async def delete_project_endpoint(project_id: str):
    """Delete a project"""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    delete_project(project_id)
    return {"message": f"Project {project_id} deleted successfully"} 