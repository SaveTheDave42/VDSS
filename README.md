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
git clone https://github.com/yourusername/construction-traffic-management.git
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

## License

MIT License