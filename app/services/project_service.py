import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

from app.models.project import Project, ProjectCreate, ProjectUpdate

# In-memory store for development, could be replaced with a database
# Dictionary: project_id -> Project
PROJECTS = {}

def create_project(project_data: ProjectCreate, file_path: str) -> Project:
    """
    Create a new construction site project.
    
    Args:
        project_data: ProjectCreate model with project details
        file_path: Path to the saved Excel file
        
    Returns:
        The created Project
    """
    # Generate a unique ID
    project_id = str(uuid.uuid4())
    
    # Create the project
    project = Project(
        id=project_id,
        name=project_data.name,
        file_name=project_data.file_name,
        file_path=file_path,
        polygon=project_data.polygon,
        waiting_areas=project_data.waiting_areas,
        access_routes=project_data.access_routes,
        map_bounds=project_data.map_bounds,
        simulation_start_time=project_data.simulation_start_time,
        simulation_end_time=project_data.simulation_end_time,
        simulation_interval=project_data.simulation_interval,
        created_at=project_data.created_at,
        updated_at=None
    )
    
    # Save the project to our in-memory store
    PROJECTS[project_id] = project
    
    # Save to filesystem as well (for persistence)
    _save_projects_to_disk()
    
    return project

def get_project(project_id: str) -> Optional[Project]:
    """
    Get a project by ID.
    
    Args:
        project_id: The ID of the project to retrieve
        
    Returns:
        The Project if found, None otherwise
    """
    return PROJECTS.get(project_id)

def update_project(project_id: str, project_update: ProjectUpdate) -> Project:
    """
    Update a project.
    
    Args:
        project_id: The ID of the project to update
        project_update: ProjectUpdate model with fields to update
        
    Returns:
        The updated Project
        
    Raises:
        KeyError: If the project is not found
    """
    if project_id not in PROJECTS:
        raise KeyError(f"Project {project_id} not found")
    
    # Get the existing project
    project = PROJECTS[project_id]
    
    # Update fields if they exist in the update data
    update_data = project_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if value is not None:
            setattr(project, field, value)
    
    # Set the updated timestamp
    project.updated_at = datetime.now()
    
    # Save changes
    PROJECTS[project_id] = project
    _save_projects_to_disk()
    
    return project

def get_all_projects() -> List[Project]:
    """
    Get all projects.
    
    Returns:
        List of all projects
    """
    return list(PROJECTS.values())

def delete_project(project_id: str) -> None:
    """
    Delete a project.
    
    Args:
        project_id: The ID of the project to delete
        
    Raises:
        KeyError: If the project is not found
    """
    if project_id not in PROJECTS:
        raise KeyError(f"Project {project_id} not found")
    
    # Remove the project
    del PROJECTS[project_id]
    _save_projects_to_disk()

def _load_projects_from_disk() -> None:
    """Load projects from the disk storage"""
    try:
        projects_dir = "data/projects"
        os.makedirs(projects_dir, exist_ok=True)
        
        projects_file = os.path.join(projects_dir, "projects.json")
        
        if os.path.exists(projects_file):
            with open(projects_file, "r") as f:
                projects_data = json.load(f)
                
                for project_dict in projects_data:
                    # Convert dictionary to Project model
                    project = Project(**project_dict)
                    PROJECTS[project.id] = project
                    
    except Exception as e:
        print(f"Error loading projects from disk: {str(e)}")

def _save_projects_to_disk() -> None:
    """Save projects to disk storage"""
    try:
        projects_dir = "data/projects"
        os.makedirs(projects_dir, exist_ok=True)
        
        projects_file = os.path.join(projects_dir, "projects.json")
        
        projects_data = [project.dict() for project in PROJECTS.values()]
        
        with open(projects_file, "w") as f:
            json.dump(projects_data, f, default=str, indent=2)
            
    except Exception as e:
        print(f"Error saving projects to disk: {str(e)}")

# Load projects on module initialization
_load_projects_from_disk() 