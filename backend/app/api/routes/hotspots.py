"""
Hotspots API Router — Spatial & Hybrid PgVector/PostGIS Endpoints
===================================================================
Provides endpoints for fetching disaster hotspot clusters, performing
semantic-spatial hybrid searches, and retrieving hotspot summary metrics.
"""

import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.db.session import get_db, get_redis
from app.core.security import verify_jwt
from app.services.spatial_hotspot_service import (
    get_spatial_hotspots,
    search_hybrid_vector_spatial,
    get_hotspots_summary
)

router = APIRouter(redirect_slashes=False)


class SemanticSearchRequest(BaseModel):
    query: str
    lat: float
    lng: float
    radius_km: Optional[float] = 50.0
    top_k: Optional[int] = 10


@router.get("", dependencies=[Depends(verify_jwt)])
async def fetch_hotspots(
    eps_km: float = Query(5.0, description="DBSCAN epsilon radius in kilometers"),
    min_samples: int = Query(2, description="Minimum incident count for a cluster"),
    jenis_kejadian: Optional[str] = Query(None, description="Filter by disaster category"),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """
    Fetch spatial disaster hotspots as a GeoJSON FeatureCollection.
    Uses PostGIS ST_ClusterDBSCAN or Haversine fallback. Cached in Redis for 60s.
    """
    tenant_slug = db.info.get("tenant_slug", "default") if hasattr(db, "info") and isinstance(db.info, dict) else "default"
    cache_key = f"cache:hotspots:{tenant_slug}:{eps_km}:{min_samples}:{jenis_kejadian or 'all'}"

    try:
        if redis and hasattr(redis, "get"):
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
    except Exception as e:
        logger.warning(f"Failed to read hotspots from Redis cache: {e}")

    result = await get_spatial_hotspots(
        db=db,
        eps_km=eps_km,
        min_samples=min_samples,
        jenis_kejadian=jenis_kejadian
    )

    try:
        if redis and hasattr(redis, "setex"):
            await redis.setex(cache_key, 60, json.dumps(result))
    except Exception as e:
        logger.warning(f"Failed to write hotspots to Redis cache: {e}")

    return result


@router.post("/semantic-search", dependencies=[Depends(verify_jwt)])
async def semantic_spatial_search(
    payload: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Perform hybrid vector-spatial search combining spatial radius with natural language query.
    """
    return await search_hybrid_vector_spatial(
        db=db,
        query_text=payload.query,
        center_lat=payload.lat,
        center_lng=payload.lng,
        radius_km=payload.radius_km or 50.0,
        top_k=payload.top_k or 10
    )


@router.get("/summary", dependencies=[Depends(verify_jwt)])
async def fetch_hotspot_summary(
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """
    Retrieve aggregated metrics for national dashboard hotspot cards.
    Cached in Redis for 60s.
    """
    tenant_slug = db.info.get("tenant_slug", "default") if hasattr(db, "info") and isinstance(db.info, dict) else "default"
    cache_key = f"cache:hotspot_summary:{tenant_slug}"

    try:
        if redis and hasattr(redis, "get"):
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
    except Exception as e:
        logger.warning(f"Failed to read hotspot summary from Redis cache: {e}")

    result = await get_hotspots_summary(db=db)

    try:
        if redis and hasattr(redis, "setex"):
            await redis.setex(cache_key, 60, json.dumps(result))
    except Exception as e:
        logger.warning(f"Failed to write hotspot summary to Redis cache: {e}")

    return result
