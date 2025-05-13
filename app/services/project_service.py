import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

from app.models.project import Project, ProjectCreate, ProjectUpdate

# In-memory store for development, could be replaced with a database
# Dictionary: project_id -> Project
PROJECTS = {}

PROJECTS_FILE = "data/projects/projects.json"

def _load_projects() -> List[Dict[str, Any]]:
    """Load all projects from the JSON file"""
    if not os.path.exists(PROJECTS_FILE):
        return []
    with open(PROJECTS_FILE, "r", encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def _save_projects(projects: List[Dict[str, Any]]):
    """Save all projects to the JSON file"""
    os.makedirs(os.path.dirname(PROJECTS_FILE), exist_ok=True)
    with open(PROJECTS_FILE, "w", encoding='utf-8') as f:
        json.dump(projects, f, indent=2, default=str, ensure_ascii=False)

def create_project(project_data: ProjectCreate, file_path: str) -> Project:
    """
    Create a new construction site project.
    
    Args:
        project_data: ProjectCreate model with project details
        file_path: Path to the saved Excel file
        
    Returns:
        The created Project
    """
    projects = _load_projects()
    
    project_dict = project_data.model_dump() # Use model_dump for Pydantic V2
    project_dict["id"] = str(uuid.uuid4()) # Generate new ID
    project_dict["file_path"] = file_path
    project_dict["updated_at"] = None # Explicitly set to None
    
    # Ensure all fields from Project model are present
    # This will use defaults from ProjectBase if not provided in ProjectCreate
    full_project_data = Project(**project_dict) 
    
    projects.append(full_project_data.model_dump())
    _save_projects(projects)
    return full_project_data

def get_project(project_id: str) -> Optional[Project]:
    """
    Get a project by ID.
    
    Args:
        project_id: The ID of the project to retrieve
        
    Returns:
        The Project if found, None otherwise
    """
    projects = _load_projects()
    for proj_dict in projects:
        if proj_dict.get("id") == project_id:
            return Project(**proj_dict)
    return None

def update_project(project_id: str, project_update_data: ProjectUpdate) -> Optional[Project]:
    """
    Update a project.
    
    Args:
        project_id: The ID of the project to update
        project_update_data: ProjectUpdate model with fields to update
        
    Returns:
        The updated Project if found, None otherwise
        
    Raises:
        KeyError: If the project is not found
    """
    projects = _load_projects()
    project_index = -1
    
    for i, proj_dict in enumerate(projects):
        if proj_dict.get("id") == project_id:
            project_index = i
            break
            
    if project_index == -1:
        return None # Project not found

    # Get existing project data
    existing_project_dict = projects[project_index]
    
    # Update with new data, excluding unset fields to keep existing values
    update_data_dict = project_update_data.model_dump(exclude_unset=True)
    
    for key, value in update_data_dict.items():
        existing_project_dict[key] = value
    
    existing_project_dict["updated_at"] = datetime.now()
    
    # Validate and create the updated Project object
    updated_project = Project(**existing_project_dict)
    projects[project_index] = updated_project.model_dump()
    
    _save_projects(projects)
    return updated_project

def get_all_projects() -> List[Project]:
    """
    Get all projects.
    
    Returns:
        List of all projects
    """
    projects_data = _load_projects()
    return [Project(**proj) for proj in projects_data]

def delete_project(project_id: str) -> None:
    """
    Delete a project.
    
    Args:
        project_id: The ID of the project to delete
        
    Raises:
        KeyError: If the project is not found
    """
    projects = _load_projects()
    projects = [proj for proj in projects if proj.get("id") != project_id]
    _save_projects(projects)

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