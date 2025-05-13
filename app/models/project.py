from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, time
import uuid

class ProjectBase(BaseModel):
    """Base model for project data"""
    name: str
    polygon: Optional[Dict[str, Any]] = None
    waiting_areas: Optional[List[Dict[str, Any]]] = []
    access_routes: Optional[List[Dict[str, Any]]] = []
    map_bounds: Optional[Dict[str, Any]] = None
    
    # Simulation and traffic data
    simulation_start_time: Optional[str] = "06:00"
    simulation_end_time: Optional[str] = "18:00"
    simulation_interval: Optional[str] = "1h"
    
    primary_counter: Optional[Dict[str, Any]] = None
    selected_counters: Optional[List[Dict[str, Any]]] = []
    delivery_days: Optional[List[str]] = []
    delivery_hours: Optional[Dict[str, Any]] = {}
    
    # Ensure GeoJSON structures are valid upon creation/update
    @validator('polygon', 'map_bounds', pre=True, always=True)
    def validate_single_geojson(cls, value):
        if value is None:
            return {"type": "Polygon", "coordinates": []} # Default empty Polygon
        if not isinstance(value, dict) or "type" not in value or "coordinates" not in value:
            raise ValueError("GeoJSON must be a dictionary with 'type' and 'coordinates' keys")
        return value

    @validator('waiting_areas', 'access_routes', pre=True, always=True)
    def validate_geojson_list(cls, value):
        if value is None:
            return [] # Default empty list
        if not isinstance(value, list):
            raise ValueError("Waiting areas and access routes must be a list of GeoJSON objects")
        for item in value:
            if not isinstance(item, dict) or "type" not in item or "coordinates" not in item:
                raise ValueError("Each item in GeoJSON list must be a dictionary with 'type' and 'coordinates' keys")
        return value

class ProjectCreate(ProjectBase):
    """Model for creating a new project"""
    file_name: str
    created_at: datetime = Field(default_factory=datetime.now)
    # file_path will be set by the service, not the client

class ProjectUpdate(ProjectBase):
    """Model for updating an existing project"""
    name: Optional[str] = None # Make all fields optional for update
    file_name: Optional[str] = None
    # file_path will be updated by the service if file_name changes

class Project(ProjectBase):
    """Model for a project as stored in the database"""
    id: str
    file_name: str
    file_path: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True # Replaces orm_mode for Pydantic V2 