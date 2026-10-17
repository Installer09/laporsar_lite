"""
Spatial Hotspot Service — PostGIS & PgVector SAR Vulnerability Analysis
========================================================================
Provides automated spatial hotspot clustering using PostGIS (ST_ClusterDBSCAN),
vulnerability score calculations, hybrid spatial-vector search, and GeoJSON output.
"""

import json
import logging
import math
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.models.report import Report

logger = logging.getLogger(__name__)


def calculate_risk_score(
    incident_count: int,
    total_meninggal: int,
    total_hilang: int,
    total_selamat: int,
    jenis_kejadian_list: List[str]
) -> Dict[str, Any]:
    """
    Calculate Vulnerability Risk Score (0 - 100) for a spatial cluster.
    Weights:
    - Incident Frequency (max 35 pts)
    - Fatalities (10 pts per casualty, max 30 pts)
    - Missing Persons (7 pts per missing person, max 20 pts)
    - Severity Multiplier by Incident Category (max 15 pts)
    """
    # 1. Incident Frequency score (cap at 10 incidents = 35 pts)
    freq_score = min(incident_count * 3.5, 35.0)

    # 2. Fatalities score (cap at 3 casualties = 30 pts)
    fatal_score = min(total_meninggal * 10.0, 30.0)

    # 3. Missing persons score (cap at 3 persons = 20 pts)
    missing_score = min(total_hilang * 7.0, 20.0)

    # 4. Severity by category
    high_risk_types = {"Kecelakaan Kapal", "Banjir", "Tanah Longsor", "Kecelakaan Pesawat"}
    severity_count = sum(1 for j in jenis_kejadian_list if any(h in str(j) for h in high_risk_types))
    severity_score = min(severity_count * 5.0, 15.0)

    total_score = round(min(freq_score + fatal_score + missing_score + severity_score, 100.0), 1)

    if total_score >= 65.0:
        level = "HIGH"
        label = "Zona Merah (Kerawanan Tinggi)"
        color = "#EF4444"
    elif total_score >= 35.0:
        level = "MEDIUM"
        label = "Zona Oranye (Kerawanan Sedang)"
        color = "#F59E0B"
    else:
        level = "LOW"
        label = "Zona Kuning (Kerawanan Rendah)"
        color = "#EAB308"

    return {
        "score": total_score,
        "level": level,
        "label": label,
        "color": color
    }


async def get_spatial_hotspots(
    db: AsyncSession,
    eps_km: float = 5.0,
    min_samples: int = 2,
    jenis_kejadian: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch spatial hotspots using PostGIS ST_ClusterDBSCAN or Python Haversine fallback.
    Returns GeoJSON FeatureCollection.
    """
    eps_deg = eps_km / 111.0  # Approx conversion km to degrees latitude
    eps_m = eps_km * 1000.0

    features = []

    # Try executing PostGIS ST_ClusterDBSCAN spatial query
    try:
        sql = text("""
            WITH clustered AS (
                SELECT 
                    id,
                    no_laporan,
                    jenis_kejadian,
                    koordinat_lat,
                    koordinat_lng,
                    korban_total,
                    korban_meninggal,
                    korban_hilang,
                    korban_selamat,
                    created_at,
                    location_geom,
                    ST_ClusterDBSCAN(
                        COALESCE(location_geom, ST_SetSRID(ST_MakePoint(koordinat_lng, koordinat_lat), 4326)), 
                        eps := :eps_deg, 
                        minpoints := :min_samples
                    ) OVER () AS cluster_id
                FROM reports
                WHERE (location_geom IS NOT NULL OR (koordinat_lat IS NOT NULL AND koordinat_lng IS NOT NULL))
                  AND (:jenis_kejadian IS NULL OR jenis_kejadian = :jenis_kejadian)
            )
            SELECT 
                cluster_id,
                COUNT(*) AS total_incidents,
                SUM(COALESCE(korban_total, 0)) AS total_korban,
                SUM(COALESCE(korban_meninggal, 0)) AS total_meninggal,
                SUM(COALESCE(korban_hilang, 0)) AS total_hilang,
                SUM(COALESCE(korban_selamat, 0)) AS total_selamat,
                ST_Y(ST_Centroid(ST_Collect(COALESCE(location_geom, ST_SetSRID(ST_MakePoint(koordinat_lng, koordinat_lat), 4326))))) AS centroid_lat,
                ST_X(ST_Centroid(ST_Collect(COALESCE(location_geom, ST_SetSRID(ST_MakePoint(koordinat_lng, koordinat_lat), 4326))))) AS centroid_lng,
                ST_AsGeoJSON(ST_ConvexHull(ST_Collect(COALESCE(location_geom, ST_SetSRID(ST_MakePoint(koordinat_lng, koordinat_lat), 4326))))) AS hull_geojson,
                json_agg(json_build_object(
                    'id', id, 
                    'no_laporan', no_laporan, 
                    'jenis_kejadian', jenis_kejadian,
                    'lat', koordinat_lat,
                    'lng', koordinat_lng,
                    'created_at', created_at
                )) AS incident_list
            FROM clustered
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id;
        """)

        result = await db.execute(sql, {
            "eps_deg": eps_deg,
            "min_samples": min_samples,
            "jenis_kejadian": jenis_kejadian
        })
        rows = result.fetchall()

        for idx, row in enumerate(rows):
            incident_list = row.incident_list or []
            jenis_list = [i.get("jenis_kejadian") for i in incident_list if i.get("jenis_kejadian")]
            
            risk_info = calculate_risk_score(
                incident_count=row.total_incidents,
                total_meninggal=int(row.total_meninggal or 0),
                total_hilang=int(row.total_hilang or 0),
                total_selamat=int(row.total_selamat or 0),
                jenis_kejadian_list=jenis_list
            )

            # Hull geometry or fallback point geometry
            geometry = None
            if row.hull_geojson:
                try:
                    geometry = json.loads(row.hull_geojson)
                except Exception:
                    pass

            if not geometry or geometry.get("type") == "Point":
                # Fallback circle center
                geometry = {
                    "type": "Point",
                    "coordinates": [float(row.centroid_lng), float(row.centroid_lat)]
                }

            features.append({
                "type": "Feature",
                "id": f"hotspot-{row.cluster_id}",
                "geometry": geometry,
                "properties": {
                    "cluster_id": int(row.cluster_id),
                    "centroid": [float(row.centroid_lat), float(row.centroid_lng)],
                    "total_incidents": int(row.total_incidents),
                    "total_korban": int(row.total_korban),
                    "total_meninggal": int(row.total_meninggal),
                    "total_hilang": int(row.total_hilang),
                    "total_selamat": int(row.total_selamat),
                    "risk_score": risk_info["score"],
                    "risk_level": risk_info["level"],
                    "risk_label": risk_info["label"],
                    "color": risk_info["color"],
                    "incidents": incident_list,
                    "radius_km": eps_km
                }
            })

    except Exception as e:
        logger.warning(f"PostGIS ST_ClusterDBSCAN query skipped/failed ({e}). Running Python spatial fallback.")
        try:
            await db.rollback()
        except Exception:
            pass
        features = await _python_spatial_clustering_fallback(db, eps_km, min_samples, jenis_kejadian)

    return {
        "type": "FeatureCollection",
        "total_hotspots": len(features),
        "features": features
    }


async def _python_spatial_clustering_fallback(
    db: AsyncSession,
    eps_km: float,
    min_samples: int,
    jenis_kejadian: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Fallback Haversine spatial clustering algorithm for environments without PostGIS active.
    """
    stmt = select(Report).where(Report.latitude.isnot(None), Report.longitude.isnot(None))
    if jenis_kejadian:
        stmt = stmt.where(Report.incident_type == jenis_kejadian)
        
    res = await db.execute(stmt)
    reports = res.scalars().all()

    if not reports:
        return []

    # Simple Distance-based clustering
    visited = set()
    clusters = []

    def haversine_km(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    for r in reports:
        if r.id in visited:
            continue

        # Find neighbors within eps_km
        neighbors = [
            other for other in reports 
            if haversine_km(r.koordinat_lat, r.koordinat_lng, other.koordinat_lat, other.koordinat_lng) <= eps_km
        ]

        if len(neighbors) >= min_samples:
            cluster_items = neighbors
            for item in cluster_items:
                visited.add(item.id)

            lats = [i.koordinat_lat for i in cluster_items]
            lngs = [i.koordinat_lng for i in cluster_items]
            c_lat = sum(lats) / len(lats)
            c_lng = sum(lngs) / len(lngs)

            meninggal = sum(i.korban_meninggal or 0 for i in cluster_items)
            hilang = sum(i.korban_hilang or 0 for i in cluster_items)
            selamat = sum(i.korban_selamat or 0 for i in cluster_items)
            total = sum(i.korban_total or 0 for i in cluster_items)
            jenis_list = [i.jenis_kejadian for i in cluster_items if i.jenis_kejadian]

            risk_info = calculate_risk_score(len(cluster_items), meninggal, hilang, selamat, jenis_list)

            incidents = [
                {
                    "id": i.id,
                    "no_laporan": i.no_laporan,
                    "jenis_kejadian": i.jenis_kejadian,
                    "lat": i.koordinat_lat,
                    "lng": i.koordinat_lng,
                    "created_at": i.created_at.isoformat() if i.created_at else None
                }
                for i in cluster_items
            ]

            clusters.append({
                "type": "Feature",
                "id": f"hotspot-{len(clusters)}",
                "geometry": {
                    "type": "Point",
                    "coordinates": [c_lng, c_lat]
                },
                "properties": {
                    "cluster_id": len(clusters),
                    "centroid": [c_lat, c_lng],
                    "total_incidents": len(cluster_items),
                    "total_korban": total,
                    "total_meninggal": meninggal,
                    "total_hilang": hilang,
                    "total_selamat": selamat,
                    "risk_score": risk_info["score"],
                    "risk_level": risk_info["level"],
                    "risk_label": risk_info["label"],
                    "color": risk_info["color"],
                    "incidents": incidents,
                    "radius_km": eps_km
                }
            })

    return clusters


async def search_hybrid_vector_spatial(
    db: AsyncSession,
    query_text: str,
    center_lat: float,
    center_lng: float,
    radius_km: float = 50.0,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Perform hybrid vector-spatial search combining spatial radius constraints
    with text/vector similarity matching.
    """
    radius_m = radius_km * 1000.0

    try:
        sql = text("""
            SELECT 
                r.id,
                r.no_laporan,
                r.jenis_kejadian,
                r.lokasi_teks,
                r.koordinat_lat,
                r.koordinat_lng,
                r.kronologi,
                ST_Distance(
                    COALESCE(r.location_geom, ST_SetSRID(ST_MakePoint(r.koordinat_lng, r.koordinat_lat), 4326))::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                ) AS distance_meters
            FROM reports r
            WHERE ST_DWithin(
                COALESCE(r.location_geom, ST_SetSRID(ST_MakePoint(r.koordinat_lng, r.koordinat_lat), 4326))::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius_m
            )
            AND (:query IS NULL OR r.kronologi ILIKE '%' || :query || '%' OR r.jenis_kejadian ILIKE '%' || :query || '%')
            ORDER BY distance_meters ASC
            LIMIT :top_k;
        """)

        res = await db.execute(sql, {
            "lat": center_lat,
            "lng": center_lng,
            "radius_m": radius_m,
            "query": query_text,
            "top_k": top_k
        })
        rows = res.fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row.id,
                "no_laporan": row.no_laporan,
                "jenis_kejadian": row.jenis_kejadian,
                "lokasi_teks": row.lokasi_teks,
                "lat": row.koordinat_lat,
                "lng": row.koordinat_lng,
                "kronologi": row.kronologi,
                "distance_km": round(row.distance_meters / 1000.0, 2)
            })

        return results

    except Exception as e:
        logger.warning(f"PostGIS spatial query fallback ({e})")
        # Python fallback
        stmt = select(Report).where(Report.latitude.isnot(None), Report.longitude.isnot(None))
        res = await db.execute(stmt)
        reports = res.scalars().all()

        results = []
        for r in reports:
            # Haversine check
            R = 6371.0
            dlat = math.radians(r.koordinat_lat - center_lat)
            dlon = math.radians(r.koordinat_lng - center_lng)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(center_lat)) * math.cos(math.radians(r.koordinat_lat)) * math.sin(dlon/2)**2
            dist_km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

            if dist_km <= radius_km:
                if not query_text or query_text.lower() in (r.kronologi or "").lower() or query_text.lower() in (r.jenis_kejadian or "").lower():
                    results.append({
                        "id": r.id,
                        "no_laporan": r.no_laporan,
                        "jenis_kejadian": r.jenis_kejadian,
                        "lokasi_teks": r.lokasi_teks,
                        "lat": r.koordinat_lat,
                        "lng": r.koordinat_lng,
                        "kronologi": r.kronologi,
                        "distance_km": round(dist_km, 2)
                    })

        results.sort(key=lambda x: x["distance_km"])
        return results[:top_k]


async def get_hotspots_summary(db: AsyncSession) -> Dict[str, Any]:
    """
    Generate summary statistics of active disaster hotspots for national dashboard.
    """
    hotspot_data = await get_spatial_hotspots(db, eps_km=5.0, min_samples=2)
    features = hotspot_data.get("features", [])

    total_hotspots = len(features)
    high_risk = sum(1 for f in features if f["properties"]["risk_level"] == "HIGH")
    medium_risk = sum(1 for f in features if f["properties"]["risk_level"] == "MEDIUM")
    low_risk = sum(1 for f in features if f["properties"]["risk_level"] == "LOW")
    total_incidents_in_hotspots = sum(f["properties"]["total_incidents"] for f in features)

    return {
        "total_hotspots": total_hotspots,
        "high_risk_zones": high_risk,
        "medium_risk_zones": medium_risk,
        "low_risk_zones": low_risk,
        "total_incidents_in_hotspots": total_incidents_in_hotspots
    }
