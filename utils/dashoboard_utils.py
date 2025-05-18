from datetime import date, timedelta, time
from datetime import datetime
import streamlit as st
import pydeck as pdk


def parse_time_from_string(time_input, default_time):
    """Parses a time string (HH:MM) or returns default if input is already a time object or invalid."""
    if isinstance(time_input, time):
        return time_input
    if isinstance(time_input, str):
        try:
            return datetime.strptime(time_input, "%H:%M").time()
        except ValueError:
            return default_time # Fallback to default if parsing fails
    return default_time # Fallback for other unexpected types

def get_week_options():
    """Generates a list of week options for the current and +/- 4 weeks."""
    today = date.today()
    options = []
    for i in range(-8, 9): # Extended range for more flexibility
        dt = today + timedelta(weeks=i)
        year, week_num, _ = dt.isocalendar()
        # Get the first day of that week (Monday)
        start_of_week = dt - timedelta(days=dt.weekday())
        # Get the last day of that week (Sunday)
        end_of_week = start_of_week + timedelta(days=6)
        options.append({
            "label": f"KW {week_num} ({year}) | {start_of_week.strftime('%d.%m')} - {end_of_week.strftime('%d.%m')}",
            "year": year,
            "week": week_num,
            "start_date": start_of_week,
            "end_date": end_of_week
        })
    return options

def get_days_in_week(year, week_num, delivery_days_filter):
    """Gets all dates for a given ISO week number and year, filtered by delivery days."""
    # Map German weekday names to ISO weekday numbers (Monday=0, Sunday=6)
    weekday_map_to_iso = {
        "Montag": 0, "Dienstag": 1, "Mittwoch": 2, 
        "Donnerstag": 3, "Freitag": 4, "Samstag": 5, "Sonntag": 6
    }
    allowed_iso_weekdays = [weekday_map_to_iso[day] for day in delivery_days_filter if day in weekday_map_to_iso]
    
    # First day of the year
    first_day_of_year = date(year, 1, 1)
    # First Monday of the year
    if first_day_of_year.weekday() > 3: # If Jan 1st is Fri, Sat, Sun, then week 1 starts next Mon
        first_monday_of_year = first_day_of_year + timedelta(days=(7 - first_day_of_year.weekday()))
    else: # Week 1 starts on or before Jan 1st
        first_monday_of_year = first_day_of_year - timedelta(days=first_day_of_year.weekday())
    
    # Start date of the target week
    current_date = first_monday_of_year + timedelta(weeks=week_num - 1)
    days = []
    for _ in range(7):
        if current_date.year == year and current_date.weekday() in allowed_iso_weekdays:
            days.append(current_date)
        current_date += timedelta(days=1)
    return days

def build_segments_for_hour(hour, project, base_osm_segments, date_str, get_traffic_data_func):
    """Return the list of PathLayer-compatible segment dicts for a specific hour.

    Parameters
    ----------
    hour : int
        Hour of day (0-23).
    project : dict
        Current project dict.
    base_osm_segments : list[dict]
        Base OSM segments as produced by `generate_osm_traffic_segments`.
    date_str : str
        Date in format YYYY-MM-DD.
    get_traffic_data_func : callable
        Reference to the existing `get_traffic_data` function so we avoid
        circular imports.
    """
    traffic_data = get_traffic_data_func(date_str, hour, project, base_osm_segments)
    segments_data = []

    if not traffic_data:
        return segments_data

    for segment in traffic_data.get("traffic_segments", []):
        congestion = segment.get("congestion_level", 0)
        # Colour depending on congestion
        if congestion >= 0.7:
            color = [220, 53, 69, 180]  # Red
        elif congestion >= 0.3:
            color = [255, 193, 7, 180]  # Yellow/Orange
        else:
            color = [40, 167, 69, 180]  # Green

        segments_data.append({
            "path": segment.get("coordinates", []),
            "name": segment.get("name", "Road"),
            "highway_type": segment.get("highway_type", "Unknown"),
            "traffic_volume": segment.get("traffic_volume", 0),
            "congestion": congestion,
            "color": color,
            # PathLayer width in px – narrower when high congestion
            "width": max(2, 8 - (congestion * 5))
        })

    return segments_data


def build_hourly_layer_cache(start_hour, end_hour, project, base_osm_segments, date_str, get_traffic_data_func):
    """Pre-compute PathLayer segment data for all hours in one dictionary."""
    return {
        h: build_segments_for_hour(h, project, base_osm_segments, date_str, get_traffic_data_func)
        for h in range(start_hour, end_hour + 1)
    }

