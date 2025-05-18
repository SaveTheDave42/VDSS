import streamlit as st
import pydeck as pdk

def update_map_view_to_project_bounds(project_map_bounds):
    '''Helper function to update st.session_state.map_view_state to fit project_map_bounds.'''
    if not project_map_bounds or "coordinates" not in project_map_bounds or \
       not project_map_bounds["coordinates"] or not project_map_bounds["coordinates"][0]:
        st.session_state.map_view_state = pdk.ViewState(
            longitude=8.5417, latitude=47.3769, zoom=11, pitch=50, bearing=0, transition_duration=1000
        )
        return
    bounds_coords_list = project_map_bounds["coordinates"][0]
    if not bounds_coords_list or len(bounds_coords_list) < 3:
        st.session_state.map_view_state = pdk.ViewState(
            longitude=8.5417, latitude=47.3769, zoom=11, pitch=50, bearing=0, transition_duration=1000
        )
        return
    try:
        min_lon = min(p[0] for p in bounds_coords_list)
        max_lon = max(p[0] for p in bounds_coords_list)
        min_lat = min(p[1] for p in bounds_coords_list)
        max_lat = max(p[1] for p in bounds_coords_list)
        if min_lat == max_lat or min_lon == max_lon:
            center_lon = (min_lon + max_lon) / 2
            center_lat = (min_lat + max_lat) / 2
            zoom = 15
        else:
            center_lon = (min_lon + max_lon) / 2
            center_lat = (min_lat + max_lat) / 2
            lon_diff = abs(max_lon - min_lon)
            lat_diff = abs(max_lat - min_lat)
            max_diff = max(lon_diff, lat_diff)
            if max_diff == 0: zoom = 15
            elif max_diff < 0.01: zoom = 16
            elif max_diff < 0.02: zoom = 15
            elif max_diff < 0.05: zoom = 14
            elif max_diff < 0.1: zoom = 13
            elif max_diff < 0.2: zoom = 12
            elif max_diff < 0.5: zoom = 11
            else: zoom = 10
        st.session_state.map_view_state = pdk.ViewState(
            longitude=center_lon, latitude=center_lat, zoom=zoom, pitch=50, bearing=0, transition_duration=1000
        )
    except (TypeError, ValueError, IndexError) as e:
        st.session_state.map_view_state = pdk.ViewState(
            longitude=8.5417, latitude=47.3769, zoom=11, pitch=50, bearing=0, transition_duration=1000
        )

def create_geojson_feature(geometry, properties=None):
    '''Wraps a GeoJSON geometry into a GeoJSON Feature structure.'''
    if properties is None: properties = {}
    return {"type": "Feature", "geometry": geometry, "properties": properties}

def create_pydeck_geojson_layer(
    data, layer_id, fill_color=[255, 255, 255, 100], line_color=[0, 0, 0, 200],
    line_width_min_pixels=1, get_line_width=10, opacity=0.5, stroked=True, filled=True,
    extruded=False, wireframe=True, pickable=False, tooltip_html=None, auto_highlight=True,
    highlight_color=[0, 0, 128, 128]
):
    '''Creates a PyDeck GeoJsonLayer with specified parameters.'''
    layer_config = {
        "id": layer_id, "data": data, "opacity": opacity, "stroked": stroked, "filled": filled,
        "extruded": extruded, "wireframe": wireframe, "get_fill_color": fill_color,
        "get_line_color": line_color, "get_line_width": get_line_width,
        "line_width_min_pixels": line_width_min_pixels, "pickable": pickable,
        "auto_highlight": auto_highlight, "highlight_color": highlight_color
    }
    if tooltip_html and pickable: layer_config["tooltip"] = {"html": tooltip_html}
    return pdk.Layer("GeoJsonLayer", **layer_config)

def create_pydeck_path_layer(
    data, layer_id, get_path="path", get_color="color", get_width="width",
    width_scale=1, width_min_pixels=2, width_max_pixels=10, pickable=False, tooltip_html=None,
    auto_highlight=True, highlight_color=[0,0,128,128]
):
    '''Creates a PyDeck PathLayer.'''
    layer_config = {
        "id": layer_id, "data": data, "pickable": pickable, "get_path": get_path,
        "get_color": get_color, "get_width": get_width, "width_scale": width_scale,
        "width_min_pixels": width_min_pixels, "width_max_pixels": width_max_pixels,
        "auto_highlight": auto_highlight, "highlight_color": highlight_color
    }
    if tooltip_html and pickable: layer_config["tooltip"] = {"html": tooltip_html}
    return pdk.Layer("PathLayer", **layer_config) 