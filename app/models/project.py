from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

class ProjectBase(BaseModel):
    """Base model for project data"""
    name: str
    file_name: str
    polygon: Dict[str, Any]  # GeoJSON format
    waiting_areas: Optional[List[Dict[str, Any]]] = []  # GeoJSON format
    access_routes: Optional[List[Dict[str, Any]]] = []  # GeoJSON format
    map_bounds: Dict[str, Any]  # GeoJSON format
    simulation_start_time: str = "06:00"
    simulation_end_time: str = "18:00"
    simulation_interval: str = "1h"

class ProjectCreate(ProjectBase):
    """Model for creating a new project"""
    created_at: datetime = Field(default_factory=datetime.now)

class ProjectUpdate(BaseModel):
    """Model for updating a project"""
    name: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    polygon: Optional[Dict[str, Any]] = None
    waiting_areas: Optional[List[Dict[str, Any]]] = None
    access_routes: Optional[List[Dict[str, Any]]] = None
    map_bounds: Optional[Dict[str, Any]] = None
    simulation_start_time: Optional[str] = None
    simulation_end_time: Optional[str] = None
    simulation_interval: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.now)

class Project(ProjectBase):
    """Model for a complete project with ID and timestamps"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True 