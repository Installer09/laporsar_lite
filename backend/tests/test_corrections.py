import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models.chat_session import ChatSession
from app.engine.field_processors.waktu import WaktuFieldProcessor
from app.services.geocoding_service import geocoding_service
from app.engine.chatbot_engine import chatbot_engine


@pytest.mark.asyncio
async def test_waktu_calendar_flow():
    """Test that WaktuFieldProcessor correctly merges _temp_date with user time response."""
    processor = WaktuFieldProcessor()
    session = MagicMock(spec=ChatSession)
    session.state = "AWAITING_WAKTU"
    
    extracted_data = {"_temp_date": "2026-06-22"}
    mock_db = AsyncMock()
    
    is_valid, res = await processor.validate_and_extract(
        message="Jam 6 pagi",
        session=session,
        extracted_data=extracted_data,
        db=mock_db
    )
    
    assert is_valid is True
    # 2026-06-22 is a Monday (Senin)
    assert "Senin, 22 Juni 2026 pukul Jam 6 pagi" in res["waktu"]
    assert "_temp_date" not in res
    assert res["_explicit_waktu"] is True


@pytest.mark.asyncio
async def test_geocoding_service_water_heuristics():
    """Test that GeocodingService correctly detects water and enriches island names."""
    # 1. Close to Pulau Senua in the water
    lat_senua, lng_senua = 4.018, 108.425
    assert geocoding_service.is_coordinate_in_water(lat_senua, lng_senua) is True
    enriched = await geocoding_service.enrich_location_with_island(lat_senua, lng_senua, "Bunguran Timur")
    assert enriched == "Perairan Pulau Senua"
    
    # 2. Far east of Ranai (definitely in the sea)
    lat_sea, lng_sea = 3.960, 108.400
    assert geocoding_service.is_coordinate_in_water(lat_sea, lng_sea) is True
    enriched_sea = await geocoding_service.enrich_location_with_island(lat_sea, lng_sea, "Ranai")
    assert enriched_sea == "Perairan Ranai, Natuna"
    
    # 3. Land coordinate containing land keywords should NOT be enriched/overridden
    lat_land, lng_land = 3.955, 108.315
    enriched_land = await geocoding_service.enrich_location_with_island(lat_land, lng_land, "Desa Sepempang, Kecamatan Bunguran Timur")
    assert enriched_land == "Desa Sepempang, Kecamatan Bunguran Timur"


@pytest.mark.asyncio
async def test_chatbot_engine_water_coordinates_routing():
    """Test that ChatbotEngine correctly adds pakai_kapal to sequence when coordinates are in water."""
    session = MagicMock(spec=ChatSession)
    session.state = "AWAITING_REPORT"
    
    # Incident is KMM, location is "Ranai" (no water keywords), but coordinates are in the sea near Pulau Senua
    extracted_data = {
        "jenis_kejadian": "KMM",
        "lokasi_teks": "Ranai",
        "koordinat_lat": 4.018,
        "koordinat_lng": 108.425,
        "korban": "2 orang"
    }
    
    mock_db = AsyncMock()
    
    sequence = await chatbot_engine._get_full_question_sequence(session, extracted_data, mock_db)
    assert "pakai_kapal" in sequence
    
    # If coordinates are near Ranai mainland center (on land) and lokasi_teks has no water keywords, it should NOT ask pakai_kapal
    extracted_data_land = {
        "jenis_kejadian": "KMM",
        "lokasi_teks": "Ranai",
        "koordinat_lat": 3.945,
        "koordinat_lng": 108.348,
        "korban": "2 orang"
    }
    sequence_land = await chatbot_engine._get_full_question_sequence(session, extracted_data_land, mock_db)
    assert "pakai_kapal" not in sequence_land


@pytest.mark.asyncio
async def test_chatbot_engine_confirming_buttons():
    """Test that ChatbotEngine returns correct confirm buttons."""
    session = MagicMock(spec=ChatSession)
    session.state = "CONFIRMING"
    session.contact_name = "Pelapor"
    session.contact_phone = "08123456789"
    
    extracted_data = {
        "jenis_kejadian": "Kecelakaan Kapal",
        "waktu": "Hari ini pukul 10:00 WIB",
        "lokasi_teks": "Perairan Pulau Senua",
        "koordinat_lat": 4.015,
        "koordinat_lng": 108.423,
        "korban": "2 orang",
        "pelapor_nama": "Pelapor",
        "pelapor_hp": "08123456789",
        "pelapor_hubungan": "Saksi Mata",
        "is_current_location_shared": True
    }
    
    mock_db = AsyncMock()
    
    # Mock LLMRagService and other finalization methods
    with patch("app.services.llm_rag.LLMRagService.get_dictionary_context", new_callable=AsyncMock) as mock_context, \
         patch("app.services.llm_rag.LLMRagService.refine_full_report_draft", new_callable=AsyncMock) as mock_refine:
        
        mock_context.return_value = {}
        mock_refine.return_value = extracted_data
        
        res = await chatbot_engine._enter_confirming(session, extracted_data, mock_db, autopilot=True)
        
        assert "buttons" in res
        assert res["buttons"] == ["Ya", "Lengkapi", "Batalkan"]
