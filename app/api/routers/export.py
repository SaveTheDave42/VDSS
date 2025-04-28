from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime, timedelta
import os

from app.services.pdf_service import generate_daily_report, generate_weekly_report

router = APIRouter()

@router.get("/daily-report")
async def export_daily_report(
    project_id: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    """Generate and download a PDF report for a specific day"""
    try:
        # Parse date
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Generate PDF report
        pdf_path = generate_daily_report(project_id, parsed_date)
        
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="Failed to generate PDF report")
        
        # Return the PDF file
        return FileResponse(
            path=pdf_path,
            filename=f"traffic_report_{project_id}_{date}.pdf",
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate daily report: {str(e)}")

@router.get("/weekly-report")
async def export_weekly_report(
    project_id: str,
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format")
):
    """Generate and download a PDF report for a week"""
    try:
        # Parse start date
        try:
            parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Calculate end date (start date + 6 days)
        end_date = parsed_start_date + timedelta(days=6)
        
        # Generate PDF report
        pdf_path = generate_weekly_report(project_id, parsed_start_date, end_date)
        
        if not pdf_path or not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="Failed to generate PDF report")
        
        # Return the PDF file
        return FileResponse(
            path=pdf_path,
            filename=f"weekly_traffic_report_{project_id}_{start_date}_to_{end_date.strftime('%Y-%m-%d')}.pdf",
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate weekly report: {str(e)}") 