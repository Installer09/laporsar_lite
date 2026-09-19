import os
import uuid
import simplekml
import math
from typing import Optional

def calculate_circle_points(lat: float, lng: float, radius_km: float, num_points: int = 72):
    """
    Calculates coordinates (longitude, latitude) of a circle around a center coordinate
    based on spherical Earth geometry.
    """
    points = []
    r_earth = 6371.0  # Earth's radius in km
    d_div_r = radius_km / r_earth
    
    lat_rad = math.radians(lat)
    lng_rad = math.radians(lng)
    
    for i in range(num_points + 1):  # Loop back to close the polygon
        bearing = math.radians((i * 360.0) / num_points)
        
        lat_out_rad = math.asin(
            math.sin(lat_rad) * math.cos(d_div_r) +
            math.cos(lat_rad) * math.sin(d_div_r) * math.cos(bearing)
        )
        
        lng_out_rad = lng_rad + math.atan2(
            math.sin(bearing) * math.sin(d_div_r) * math.cos(lat_rad),
            math.cos(d_div_r) - math.sin(lat_rad) * math.sin(lat_out_rad)
        )
        
        points.append((math.degrees(lng_out_rad), math.degrees(lat_out_rad)))
        
    return points

def generate_incident_kml(
    report_id: str,
    incident_name: str,
    incident_lat: float,
    incident_lng: float,
    nearest_post_name: Optional[str] = None,
    nearest_post_lat: Optional[float] = None,
    nearest_post_lng: Optional[float] = None,
    radius_km: Optional[float] = None,
    output_dir: str = "/tmp"
) -> str:
    """
    Generates a KML file containing the incident location, optionally the nearest SAR post,
    and a search/incident radius circle if provided.
    Returns the absolute path to the generated KML file.
    """
    kml = simplekml.Kml()
    
    # 1. Add Incident Point
    inc_point = kml.newpoint(name=f"Insiden: {incident_name}", coords=[(incident_lng, incident_lat)])
    inc_point.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"
    inc_point.style.labelstyle.scale = 1.5
    inc_point.description = f"Lokasi Insiden\nLat: {incident_lat}\nLng: {incident_lng}"

    # 2. Add Search Radius Circle if provided
    if radius_km is not None and radius_km > 0:
        points = calculate_circle_points(incident_lat, incident_lng, radius_km)
        poly = kml.newpolygon(name=f"Radius Pencarian ({radius_km} km)")
        poly.outerboundaryis = points
        
        # Style the polygon (transparent orange fill with red border)
        poly.style.polystyle.color = "330055ff"  # 20% alpha, orange/red fill (ABGR: a=33, b=00, g=55, r=ff)
        poly.style.linestyle.color = "ff0000ff"  # 100% alpha, red border
        poly.style.linestyle.width = 2

    # 3. Add Nearest Post Point & Line if available
    if nearest_post_name and nearest_post_lat is not None and nearest_post_lng is not None:
        post_point = kml.newpoint(name=f"Pos SAR: {nearest_post_name}", coords=[(nearest_post_lng, nearest_post_lat)])
        post_point.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/shapes/info-i.png"
        post_point.description = f"Pos SAR Terdekat\nLat: {nearest_post_lat}\nLng: {nearest_post_lng}"
        
        # Add a line between them
        linestring = kml.newlinestring(name="Jarak ke Pos SAR")
        linestring.coords = [(nearest_post_lng, nearest_post_lat), (incident_lng, incident_lat)]
        linestring.style.linestyle.color = simplekml.Color.blue
        linestring.style.linestyle.width = 3

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"Insiden_{report_id}_{uuid.uuid4().hex[:6]}.kml"
    filepath = os.path.join(output_dir, filename)
    
    kml.save(filepath)
    return filepath
