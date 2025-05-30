import streamlit as st

def show_legend_widget(current_page, show_geojson_layers=False):
    """
    Display a legend widget that explains the colors on the map.
    
    Args:
        current_page: The current page being displayed
        show_geojson_layers: Whether to show GeoJSON layer legends (for project_setup)
    """
    
    # Determine which legends to show based on the current page
    show_traffic = current_page in ["dashboard", "resident_info"]
    show_geojson = current_page in ["admin"] or (current_page == "project_setup" and show_geojson_layers)
    
    if not show_traffic and not show_geojson and current_page != "dashboard" and current_page != "resident_info":
        return  # Don't show legend if nothing to display
    
    # Calculate the right position based on widget width
    widget_width = st.session_state.get("widget_width_percent", 30)
    
    # Build CSS and initial div without leading spaces
    legend_html = (
        "<style>"
        " .legend-overlay{position:fixed;bottom:40px;left:50%;transform:translateX(-50%);"
        "background:rgba(255,255,255,0.96);backdrop-filter:blur(8px);padding:12px 24px;"
        "border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.15);display:flex;"
        "align-items:center;gap:30px;z-index:999;}"
        " .legend-overlay .sec{display:flex;align-items:center;gap:20px;}"
        " .legend-overlay .item{display:flex;align-items:center;gap:6px;font-size:12px;color:#6b7280;}"
        " .legend-overlay .box{width:16px;height:16px;border-radius:3px;border:1px solid #e5e7eb;display:inline-block;}"
        " .legend-overlay .title{font-weight:500;font-size:13px;color:#374151;}"
        " .legend-overlay .divider{width:1px;height:20px;background:#e5e7eb;margin:0 15px;}"
        "</style>"
        "<div class='legend-overlay'>"
    )
    
    # GeoJSON section
    if show_geojson or current_page in ["dashboard", "resident_info"]:
        legend_html += (
            "<div class='sec'>"
            "<span class='title'>Bereiche:</span>"
            "<span class='item'><span class='box' style='background:rgba(70,130,180,0.63)'></span>Baustelle</span>"
            "<span class='item'><span class='box' style='background:rgba(148,0,211,0.3)'></span>Zufahrtsroute</span>"
            "</div>"
        )
        if show_traffic:
            legend_html += "<div class='divider'></div>"
    
    # Traffic section
    if show_traffic:
        legend_html += (
            "<div class='sec'>"
            "<span class='title'>Verkehrsaufkommen:</span>"
            "<span class='item'><span class='box' style='background:rgba(40,167,69,0.71)'></span>Niedrig</span>"
            "<span class='item'><span class='box' style='background:rgba(255,193,7,0.71)'></span>Mittel</span>"
            "<span class='item'><span class='box' style='background:rgba(220,53,69,0.71)'></span>Hoch</span>"
            "</div>"
        )
    
    legend_html += "</div>"
    
    st.markdown(legend_html, unsafe_allow_html=True)

def check_geojson_layers_uploaded():
    """
    Check if GeoJSON layers have been uploaded in project setup.
    Returns True if both construction site and delivery route are present.
    """
    if "current_project" not in st.session_state:
        return False
    
    project = st.session_state.current_project
    has_construction_site = bool(project.get("polygon"))
    has_access_routes = bool(project.get("access_routes"))
    
    return has_construction_site and has_access_routes 