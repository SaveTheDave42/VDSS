# Construction Site Traffic Management System

A comprehensive application for managing and visualizing traffic around construction sites.

## Features

- **Project Setup**: Create new construction site projects by uploading Excel files and defining geographical areas
- **Admin Panel**: Manage existing projects, update data, and run traffic simulations
- **Dashboard**: Visualize traffic conditions with interactive maps and charts
- **Resident Information**: Simplified view for residents affected by construction

## Technology Stack

- **Backend**: FastAPI (Python)
- **Data Processing**: Pandas, GeoPandas
- **Map Data**: OpenStreetMap via OSMnx
- **Traffic Simulation**: Python-based approximation
- **Frontend**: Streamlit
- **PDF Export**: ReportLab

## Project Structure

```
├── app/                  # FastAPI backend
│   ├── api/              # API endpoints
│   │   └── routers/      # Router modules
│   ├── core/             # Core functionality
│   ├── models/           # Data models
│   ├── services/         # Business logic
│   ├── utils/            # Utility functions
│   ├── static/           # Static files
│   └── templates/        # Template files
├── data/                 # Data storage directory
│   ├── projects/         # Project files
│   ├── simulations/      # Simulation results
│   └── reports/          # Generated reports
├── pages/                # Streamlit page modules
├── streamlit_app.py      # Streamlit frontend
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## Installation

1. Clone the repository:

```bash
git clone https://github.com/
cd construction-traffic-management
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

### Start the FastAPI Backend

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

### Start the Streamlit Frontend

```bash
streamlit run streamlit_app.py
```

The web application will open automatically in your browser at http://localhost:8501

## API Documentation

FastAPI automatically generates API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Data Format

### Excel File Structure

The application expects an Excel file with the following sheets and columns:

1. **Deliveries sheet**:
   - DeliveryID
   - Date
   - TimeWindow
   - VehicleType
   - Weight

2. **Schedule sheet**:
   - Phase
   - StartDate
   - EndDate
   - Description

3. **Vehicles sheet**:
   - VehicleType
   - Length
   - Width
   - Weight

## Traffic Simulation Logic

The application simulates traffic flow on OpenStreetMap (OSM) road segments within a project's defined `map_bounds`. The goal is to provide a plausible visualization of traffic density and congestion levels, influenced by both general hourly patterns and, if available, data from real-world traffic counters.

### 1. Data Acquisition and Preparation

- **OSM Road Network**: Using the `OSMnx` library, the system fetches drivable road segments (network_type='drive_service') within the project's `map_bounds`. This data is cached locally (as a GeoPackage file in `data/prepared/osm_cache/`) to speed up subsequent loads and reduce API calls to OpenStreetMap. The cache key is based on the project ID and the specific map_bounds coordinates.
- **Base Capacity Assignment**: Each fetched OSM segment is assigned a base `capacity` (vehicles per hour, vph) based on its `highway` tag (e.g., 'primary', 'secondary', 'residential'). A predefined `CAPACITY_MAP` in `pages/dashboard.py` holds these default capacities. For example, a 'primary' road might have a capacity of 1500 vph, while a 'residential' road might have 400 vph.

### 2. Hourly Traffic Volume Simulation

For each OSM segment and for each hour selected by the user, the system simulates the traffic volume. This simulation considers several factors:

- **Overall Hourly Busyness (`time_factor_current_hour`)**: 
    - A global factor (ranging roughly from 0.05 to 0.95) is calculated for the current simulation hour.
    - This factor has a base value and is increased during typical peak hours (e.g., 7-9 AM, 4-6 PM) and moderately during mid-day.
    - Crucially, if data from traffic counting stations (`counter_profiles`) is available for the project, the `average_congestion_from_counters` for that specific hour influences this `time_factor_current_hour`. Higher real-world congestion leads to a higher `time_factor_current_hour`, increasing the overall simulated traffic across all OSM segments.

- **Typical Utilization Bands per Road Type (`utilization_factors`)**:
    - A dictionary `utilization_factors` (in `pages/dashboard.py`) defines a typical *minimum* and *maximum* percentage of capacity that a road of a certain `highway_type` is expected to utilize. 
    - Example: `'residential': (0.03, 0.25)` means residential roads typically use between 3% and 25% of their assigned base capacity.
    - `'primary': (0.30, 0.85)` means primary roads typically use between 30% and 85% of their base capacity.

- **Hourly Driven Utilization**: 
    - The `time_factor_current_hour` (overall busyness) determines where, within the `[min_util, max_util]` band of its type, a road segment's current utilization lies. 
    - If `time_factor_current_hour` is low (e.g., off-peak, low counter congestion), the utilization will be closer to `min_util` for that road type. If high, it will be closer to `max_util`.
    - Formula sketch: `hourly_driven_utilization = min_util + (max_util - min_util) * time_factor_current_hour`

- **Per-Segment Random Variability (`segment_hash_random_factor`)**: 
    - To ensure not all roads of the same type look identical, a stable random factor (between 0.3 and 1.0, derived from a hash of the segment's ID) is calculated for each segment.
    - This factor then scales the `hourly_driven_utilization` to provide inherent variability. Some residential roads will naturally be a bit busier or quieter than others, even under the same general hourly demand.
    - Formula sketch: `final_utilization_rate = hourly_driven_utilization * segment_hash_random_factor` (clamped between a minimum like 0.5% and maximum 100%).

- **Simulated Volume Calculation**: 
    - The `simulated_volume` for a segment is then `segment_capacity * final_utilization_rate`.

- **Special Override for Low-Traffic Roads**:
    - For road types like 'residential', 'service', and 'living_street', simply applying a percentage of their (potentially already low) capacity might still lead to unrealistically high or low absolute traffic numbers if the `time_factor_current_hour` is at an extreme.
    - To make these more plausible, a maximum typical hourly flow is defined (e.g., `max_hourly_flow_residential = 30` vph, `max_hourly_flow_service_living = 15` vph).
    - The actual flow for these road types is then calculated as: `absolute_flow = max_flow_for_type * segment_hash_random_factor * time_factor_current_hour`.
    - The final `simulated_volume` for these types is then the *minimum* of the capacity-percentage-based calculation and this absolute flow-based calculation, ensuring it doesn't exceed realistic small-street throughputs while still reacting to hourly demand.

- **Caps and Floors**: 
    - The `simulated_volume` is capped at 150% of the segment's base capacity to prevent extreme, unrealistic overflow in this simplified model.
    - Volume is also ensured to be non-negative.

### 3. Congestion Level Calculation

- The `congestion_level` for each segment is calculated as:
  `congestion = min(1.0, simulated_volume / segment_capacity)` (if capacity > 0).
- This results in a value between 0.0 (no congestion) and 1.0 (at or over capacity).

### 4. Visualization

- The `congestion_level` is then used to color-code the road segments on the Folium map in the dashboard (e.g., green for low, yellow for medium, red for high congestion).
- When the user moves the hour slider or uses the play/pause animation feature, these calculations are re-run for the selected hour, and the map updates to reflect the simulated traffic conditions.

This multi-factor approach aims to provide a more nuanced and plausible representation of traffic dynamics than a simple, uniform distribution, while still being a manageable simulation for a web application.

## PDF Export
