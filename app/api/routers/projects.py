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

@router.post("/", response_model=Project)
async def create_project_endpoint(
    file: UploadFile = File(...),
    name: str = Form(...),
    polygon: str = Form(...), # GeoJSON
    waiting_areas: Optional[str] = Form(None), # GeoJSON
    access_routes: Optional[str] = Form(None), # GeoJSON
    map_bounds: str = Form(...) # GeoJSON
):
    """Create a new construction site project"""
    try:
        # Validate the Excel file
        excel_data = await file.read()
        validation_result = validate_excel(excel_data)
        
        if not validation_result["valid"]:
            return JSONResponse(
                status_code=400,
                content={"message": "Invalid Excel file", "errors": validation_result["errors"]}
            )
        
        # Parse GeoJSON data
        polygon_data = json.loads(polygon)
        map_bounds_data = json.loads(map_bounds)
        
        waiting_areas_data = json.loads(waiting_areas) if waiting_areas else []
        access_routes_data = json.loads(access_routes) if access_routes else []
        
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
            created_at=datetime.now()
        )
        
        # Save Excel data to disk
        file_path = f"data/projects/{name}/{file.filename}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, "wb") as f:
            # Go back to the beginning of the file
            await file.seek(0)
            f.write(await file.read())
        
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
        
        # Process new Excel file if uploaded
        if file:
            excel_data = await file.read()
            validation_result = validate_excel(excel_data)
            
            if not validation_result["valid"]:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Invalid Excel file", "errors": validation_result["errors"]}
                )
            
            # Save new file
            project_name = name or existing_project.name
            file_path = f"data/projects/{project_name}/{file.filename}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, "wb") as f:
                # Go back to the beginning of the file
                await file.seek(0)
                f.write(await file.read())
            
            update_data["file_name"] = file.filename
            update_data["file_path"] = file_path
        
        # Process GeoJSON data
        if polygon:
            update_data["polygon"] = json.loads(polygon)
        
        if waiting_areas:
            update_data["waiting_areas"] = json.loads(waiting_areas)
        
        if access_routes:
            update_data["access_routes"] = json.loads(access_routes)
        
        if map_bounds:
            update_data["map_bounds"] = json.loads(map_bounds)
        
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