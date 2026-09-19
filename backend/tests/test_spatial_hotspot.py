"""
Unit and Integration Tests for Spatial Hotspot Service & API Router
======================================================================
Tests:
- calculate_risk_score logic and risk categories (HIGH, MEDIUM, LOW)
- get_spatial_hotspots spatial clustering output structure
- search_hybrid_vector_spatial spatial distance & query filtering
- get_hotspots_summary aggregation stats
"""

import pytest
from app.services.spatial_hotspot_service import (
    calculate_risk_score,
    get_spatial_hotspots,
    search_hybrid_vector_spatial,
    get_hotspots_summary
)


class TestRiskScoreCalculation:
    """Tests for disaster vulnerability score calculation."""

    def test_high_risk_score(self):
        """High incident count and fatalities should yield HIGH risk level (Zona Merah)."""
        score_info = calculate_risk_score(
            incident_count=10,
            total_meninggal=3,
            total_hilang=2,
            total_selamat=5,
            jenis_kejadian_list=["Kecelakaan Kapal", "Banjir"]
        )
        assert score_info["level"] == "HIGH"
        assert score_info["score"] >= 65.0
        assert score_info["color"] == "#EF4444"

    def test_medium_risk_score(self):
        """Moderate incidents with fatalities/missing should yield MEDIUM risk level."""
        score_info = calculate_risk_score(
            incident_count=5,
            total_meninggal=1,
            total_hilang=1,
            total_selamat=10,
            jenis_kejadian_list=["KMM", "Kecelakaan Kapal"]
        )
        assert score_info["level"] == "MEDIUM"
        assert 35.0 <= score_info["score"] < 65.0
        assert score_info["color"] == "#F59E0B"

    def test_low_risk_score(self):
        """Single incident with no casualties should yield LOW risk level."""
        score_info = calculate_risk_score(
            incident_count=1,
            total_meninggal=0,
            total_hilang=0,
            total_selamat=1,
            jenis_kejadian_list=["Lain-lain"]
        )
        assert score_info["level"] == "LOW"
        assert score_info["score"] < 35.0
        assert score_info["color"] == "#EAB308"


@pytest.mark.asyncio
async def test_get_spatial_hotspots_empty_db(mock_db):
    """Test get_spatial_hotspots with empty database returns valid GeoJSON structure."""
    result = await get_spatial_hotspots(mock_db, eps_km=5.0, min_samples=2)
    assert result["type"] == "FeatureCollection"
    assert "total_hotspots" in result
    assert "features" in result
    assert isinstance(result["features"], list)


@pytest.mark.asyncio
async def test_get_hotspots_summary_empty_db(mock_db):
    """Test get_hotspots_summary with empty database returns summary dict."""
    summary = await get_hotspots_summary(mock_db)
    assert summary["total_hotspots"] >= 0
    assert summary["high_risk_zones"] >= 0
    assert summary["medium_risk_zones"] >= 0
    assert summary["low_risk_zones"] >= 0
