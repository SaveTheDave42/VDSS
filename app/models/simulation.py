from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid

class SimulationRequest(BaseModel):
    """Model for simulation request parameters"""
    project_id: str
    start_date: date
    end_date: date
    time_interval: str = "1h"  # e.g., "1h", "30m"
    
class TrafficSegment(BaseModel):
    """Model for a road segment with traffic data"""
    segment_id: str
    start_node: str
    end_node: str
    length: float
    speed_limit: float
    traffic_volume: int
    congestion_level: float  # 0.0 - 1.0
    coordinates: List[List[float]]  # [[lon1, lat1], [lon2, lat2], ...]
    
class SimulationTimeStep(BaseModel):
    """Model for simulation data at a specific time step"""
    time: datetime
    traffic_segments: List[TrafficSegment]
    waiting_areas_status: Dict[str, Any]  # Occupancy stats for waiting areas
    
class SimulationResult(BaseModel):
    """Model for complete simulation results"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    execution_time: datetime = Field(default_factory=datetime.now)
    time_steps: List[SimulationTimeStep]
    traffic_volumes: Dict[str, int]  # road_id -> vehicle count
    congestion_points: List[Dict[str, Any]]  # List of highly congested areas
    stats: Dict[str, Any]  # Summary statistics

class SimulationSummary(BaseModel):
    """Summary model for simulation results"""
    id: str
    project_id: str
    execution_time: datetime
    date: date
    peak_hour: int
    peak_traffic_volume: int
    average_congestion: float
    congestion_hotspots: List[str] 