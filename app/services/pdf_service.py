import os
import io
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm

# Import our services
from app.services.project_service import get_project
from app.services.simulation_service import get_simulation_results

def generate_daily_report(project_id: str, report_date: date) -> Optional[str]:
    """
    Generate a PDF report for a specific day.
    
    Args:
        project_id: ID of the project
        report_date: Date for the report
        
    Returns:
        Path to the generated PDF file, or None if generation failed
    """
    try:
        # Get project data
        project = get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Create reports directory
        reports_dir = f"data/reports/{project_id}"
        os.makedirs(reports_dir, exist_ok=True)
        
        # Define output path
        output_path = f"{reports_dir}/daily_report_{report_date.isoformat()}.pdf"
        
        # Create a PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Container for PDF elements
        elements = []
        
        # Add styles
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        heading1_style = styles['Heading1']
        heading2_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # Add title
        elements.append(Paragraph(f"Traffic Report: {project.name}", title_style))
        elements.append(Paragraph(f"Date: {report_date.strftime('%d %B %Y')}", heading1_style))
        elements.append(Spacer(1, 0.5*inch))
        
        # Add project details
        elements.append(Paragraph("Project Details", heading2_style))
        elements.append(Paragraph(f"Project Name: {project.name}", normal_style))
        elements.append(Paragraph(f"Report Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}", normal_style))
        elements.append(Spacer(1, 0.5*inch))
        
        # Add traffic overview
        elements.append(Paragraph("Traffic Overview", heading2_style))
        
        # Collect hourly data
        hours = list(range(6, 19))  # 6 AM to 6 PM
        traffic_data = []
        peak_hour = 6
        peak_traffic = 0
        total_traffic = 0
        congestion_levels = []
        
        for hour in hours:
            # Get simulation results for this hour
            sim_result = get_simulation_results(project_id, report_date, hour)
            
            if sim_result:
                # Extract traffic volume
                traffic_volume = sim_result.stats.get("total_traffic", 0)
                traffic_data.append(traffic_volume)
                total_traffic += traffic_volume
                
                # Track peak hour
                if traffic_volume > peak_traffic:
                    peak_traffic = traffic_volume
                    peak_hour = hour
                
                # Extract congestion level
                congestion_level = sim_result.stats.get("average_congestion", 0)
                congestion_levels.append(congestion_level)
            else:
                traffic_data.append(0)
                congestion_levels.append(0)
        
        # Create a traffic chart
        plt.figure(figsize=(8, 5))
        plt.bar(hours, traffic_data, color='skyblue')
        plt.plot(hours, traffic_data, 'ro-')
        plt.xlabel('Hour of Day')
        plt.ylabel('Traffic Volume')
        plt.title('Hourly Traffic Volume')
        plt.grid(True, alpha=0.3)
        plt.xticks(hours)
        
        # Save the chart to a buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300)
        buffer.seek(0)
        plt.close()
        
        # Add the chart to the PDF
        img = Image(buffer)
        img.drawHeight = 3*inch
        img.drawWidth = 6*inch
        elements.append(img)
        elements.append(Spacer(1, 0.2*inch))
        
        # Add traffic statistics
        elements.append(Paragraph("Traffic Statistics", heading2_style))
        
        # Create a table for statistics
        data = [
            ["Metric", "Value"],
            ["Total Traffic Volume", f"{total_traffic} vehicles"],
            ["Peak Hour", f"{peak_hour}:00 ({peak_traffic} vehicles)"],
            ["Average Congestion Level", f"{sum(congestion_levels) / len(congestion_levels):.2f} (0-1 scale)"]
        ]
        
        # Get peak hour simulation for detailed info
        peak_sim = get_simulation_results(project_id, report_date, peak_hour)
        if peak_sim:
            data.append(["Delivery Vehicles", f"{peak_sim.stats.get('deliveries_count', 0)} vehicles"])
            data.append(["Construction Phase", peak_sim.stats.get('construction_phase', 'Unknown')])
        
        # Create table
        table = Table(data, colWidths=[3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Add congestion chart
        plt.figure(figsize=(8, 5))
        plt.plot(hours, congestion_levels, 'go-')
        plt.fill_between(hours, congestion_levels, alpha=0.3, color='green')
        plt.xlabel('Hour of Day')
        plt.ylabel('Congestion Level (0-1)')
        plt.title('Hourly Congestion Levels')
        plt.grid(True, alpha=0.3)
        plt.xticks(hours)
        plt.ylim(0, max(max(congestion_levels) + 0.1, 1.0))
        
        # Save the congestion chart
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300)
        buffer.seek(0)
        plt.close()
        
        # Add the chart to the PDF
        img = Image(buffer)
        img.drawHeight = 3*inch
        img.drawWidth = 6*inch
        elements.append(Paragraph("Congestion Levels", heading2_style))
        elements.append(img)
        
        # Add recommendations section
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("Recommendations", heading2_style))
        
        # Simple recommendations based on data
        if peak_traffic > 500:
            elements.append(Paragraph("- Traffic volume is very high. Consider rescheduling deliveries to less busy hours.", normal_style))
        elif peak_traffic > 300:
            elements.append(Paragraph("- Traffic volume is moderately high. Monitor congestion levels in peak hours.", normal_style))
        else:
            elements.append(Paragraph("- Traffic volume is within acceptable limits.", normal_style))
            
        if max(congestion_levels) > 0.8:
            elements.append(Paragraph("- Congestion levels are critical in some hours. Consider alternative routes or traffic management measures.", normal_style))
        elif max(congestion_levels) > 0.5:
            elements.append(Paragraph("- Moderate congestion detected. Monitor for potential issues.", normal_style))
        else:
            elements.append(Paragraph("- Congestion levels are low.", normal_style))
        
        # Build the PDF
        doc.build(elements)
        
        return output_path
    
    except Exception as e:
        print(f"Error generating daily report: {str(e)}")
        return None

def generate_weekly_report(project_id: str, start_date: date, end_date: date) -> Optional[str]:
    """
    Generate a PDF report for a week.
    
    Args:
        project_id: ID of the project
        start_date: Start date for the report
        end_date: End date for the report
        
    Returns:
        Path to the generated PDF file, or None if generation failed
    """
    try:
        # Get project data
        project = get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Validate date range
        if (end_date - start_date).days > 7:
            end_date = start_date + timedelta(days=6)  # Limit to one week
        
        # Create reports directory
        reports_dir = f"data/reports/{project_id}"
        os.makedirs(reports_dir, exist_ok=True)
        
        # Define output path
        output_path = f"{reports_dir}/weekly_report_{start_date.isoformat()}_to_{end_date.isoformat()}.pdf"
        
        # Create a PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Container for PDF elements
        elements = []
        
        # Add styles
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        heading1_style = styles['Heading1']
        heading2_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # Add title
        elements.append(Paragraph(f"Weekly Traffic Report: {project.name}", title_style))
        elements.append(Paragraph(f"Period: {start_date.strftime('%d %B %Y')} to {end_date.strftime('%d %B %Y')}", heading1_style))
        elements.append(Spacer(1, 0.5*inch))
        
        # Add project details
        elements.append(Paragraph("Project Details", heading2_style))
        elements.append(Paragraph(f"Project Name: {project.name}", normal_style))
        elements.append(Paragraph(f"Report Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}", normal_style))
        elements.append(Spacer(1, 0.5*inch))
        
        # Collect daily data
        days = []
        current_date = start_date
        daily_totals = []
        daily_peaks = []
        daily_congestion = []
        
        while current_date <= end_date:
            days.append(current_date.strftime("%a %d"))
            
            # Variables for this day
            daily_total = 0
            daily_peak = 0
            daily_avg_congestion = 0
            congestion_samples = 0
            
            # Collect hourly data for this day
            for hour in range(6, 19):  # 6 AM to 6 PM
                sim_result = get_simulation_results(project_id, current_date, hour)
                
                if sim_result:
                    traffic_volume = sim_result.stats.get("total_traffic", 0)
                    daily_total += traffic_volume
                    daily_peak = max(daily_peak, traffic_volume)
                    
                    congestion = sim_result.stats.get("average_congestion", 0)
                    daily_avg_congestion += congestion
                    congestion_samples += 1
            
            # Calculate average congestion
            if congestion_samples > 0:
                daily_avg_congestion /= congestion_samples
            
            # Store daily stats
            daily_totals.append(daily_total)
            daily_peaks.append(daily_peak)
            daily_congestion.append(daily_avg_congestion)
            
            # Move to next day
            current_date += timedelta(days=1)
        
        # Create daily traffic chart
        plt.figure(figsize=(10, 5))
        plt.bar(days, daily_totals, color='skyblue')
        plt.plot(days, daily_totals, 'ro-')
        plt.xlabel('Day')
        plt.ylabel('Total Daily Traffic')
        plt.title('Daily Traffic Volume')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        # Save the chart to a buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300)
        buffer.seek(0)
        plt.close()
        
        # Add the chart to the PDF
        img = Image(buffer)
        img.drawHeight = 3*inch
        img.drawWidth = 8*inch
        elements.append(Paragraph("Weekly Traffic Overview", heading2_style))
        elements.append(img)
        elements.append(Spacer(1, 0.2*inch))
        
        # Create daily peak chart
        plt.figure(figsize=(10, 5))
        plt.bar(days, daily_peaks, color='lightcoral')
        plt.plot(days, daily_peaks, 'bo-')
        plt.xlabel('Day')
        plt.ylabel('Peak Hourly Traffic')
        plt.title('Daily Peak Traffic')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        # Save the chart to a buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300)
        buffer.seek(0)
        plt.close()
        
        # Add the chart to the PDF
        img = Image(buffer)
        img.drawHeight = 3*inch
        img.drawWidth = 8*inch
        elements.append(Paragraph("Daily Peak Traffic", heading2_style))
        elements.append(img)
        elements.append(Spacer(1, 0.2*inch))
        
        # Create congestion chart
        plt.figure(figsize=(10, 5))
        plt.bar(days, daily_congestion, color='lightgreen')
        plt.plot(days, daily_congestion, 'go-')
        plt.xlabel('Day')
        plt.ylabel('Average Congestion Level (0-1)')
        plt.title('Daily Average Congestion')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        # Save the chart to a buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=300)
        buffer.seek(0)
        plt.close()
        
        # Add the chart to the PDF
        img = Image(buffer)
        img.drawHeight = 3*inch
        img.drawWidth = 8*inch
        elements.append(Paragraph("Daily Congestion Levels", heading2_style))
        elements.append(img)
        elements.append(Spacer(1, 0.5*inch))
        
        # Add weekly statistics table
        elements.append(Paragraph("Weekly Statistics", heading2_style))
        
        total_weekly_traffic = sum(daily_totals)
        avg_daily_traffic = total_weekly_traffic / len(days) if days else 0
        busiest_day_idx = daily_totals.index(max(daily_totals)) if daily_totals else 0
        busiest_day = days[busiest_day_idx] if days else "N/A"
        
        # Weekly stats table
        data = [
            ["Metric", "Value"],
            ["Total Weekly Traffic", f"{total_weekly_traffic} vehicles"],
            ["Average Daily Traffic", f"{avg_daily_traffic:.0f} vehicles"],
            ["Busiest Day", f"{busiest_day} ({max(daily_totals) if daily_totals else 0} vehicles)"],
            ["Average Congestion Level", f"{sum(daily_congestion) / len(daily_congestion) if daily_congestion else 0:.2f} (0-1 scale)"]
        ]
        
        # Create table
        table = Table(data, colWidths=[4*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Add recommendations section
        elements.append(Paragraph("Weekly Recommendations", heading2_style))
        
        # Generate recommendations based on data
        if avg_daily_traffic > 2000:
            elements.append(Paragraph("- Weekly traffic volume is very high. Consider revising the delivery schedule or implementing traffic management measures.", normal_style))
        elif avg_daily_traffic > 1000:
            elements.append(Paragraph("- Weekly traffic volume is moderately high. Monitor congestion and consider optimizing delivery schedules.", normal_style))
        else:
            elements.append(Paragraph("- Weekly traffic volume is within acceptable limits.", normal_style))
            
        if sum(daily_congestion) / len(daily_congestion) if daily_congestion else 0 > 0.7:
            elements.append(Paragraph("- Average congestion levels are high. Consider implementing traffic flow optimization or alternate routes.", normal_style))
        elif sum(daily_congestion) / len(daily_congestion) if daily_congestion else 0 > 0.4:
            elements.append(Paragraph("- Moderate congestion detected across the week. Monitor for potential issues during peak hours.", normal_style))
        else:
            elements.append(Paragraph("- Congestion levels are generally low throughout the week.", normal_style))
        
        # Build the PDF
        doc.build(elements)
        
        return output_path
    
    except Exception as e:
        print(f"Error generating weekly report: {str(e)}")
        return None 