import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_rag import LLMRagService

@pytest.mark.asyncio
async def test_answer_bantuan_sar_format_and_sources():
    rag_service = LLMRagService()
    mock_db = AsyncMock()
    mock_db.info = {"tenant_slug": "global"}
    
    mock_chunks = [
        {
            "title": "SOP Penyelamatan Korban Tenggelam di Laut",
            "filename": "SOP_KMM_TENGGELAM_2024.pdf",
            "chunk_index": 1,
            "content": "Prosedur pertolongan: Amankan diri, lemparkan ring buoy, dekati korban dari arah belakang.",
            "origin": "Dokumen SOP Pusat (Nasional)",
            "distance": 0.12
        }
    ]

    with patch.object(rag_service, "get_dictionary_context", new_callable=AsyncMock) as mock_dict, \
         patch.object(rag_service, "search_sop_chunks", new_callable=AsyncMock) as mock_search_sop, \
         patch("app.services.ai_providers.ai_provider_manager.llm_generate", new_callable=AsyncMock) as mock_llm:
        
        mock_dict.return_value = "KOSAKATA: Ring Buoy = Pelampung penolong berbentuk cincin"
        mock_search_sop.return_value = mock_chunks
        mock_llm.return_value = (
            "Prosedur pertolongan orang tenggelam meliputi:\n"
            "1. Menghubungi siaga SAR 115.\n"
            "2. Menggunakan pelampung penolong (Ring Buoy).\n\n"
            "📚 **Referensi Dokumen & Sumber Resmi:**\n"
            "• *SOP Penyelamatan Korban Tenggelam di Laut* - Bab III Prosedur Penyelamatan Air\n"
            "• *Undang-Undang RI Nomor 29 Tahun 2014* - Pasal 34 Penyelenggaraan Operasi SAR\n"
            "• *Peraturan Badan Nasional Pencarian dan Pertolongan tentang Siaga SAR*"
        )

        res = await rag_service.answer_bantuan_sar("Bagaimana SOP pertolongan orang tenggelam?", mock_db)
        
        assert "Prosedur pertolongan" in res
        assert "Referensi Dokumen & Sumber Resmi" in res
        assert "Undang-Undang RI Nomor 29 Tahun 2014" in res
        assert "SOP Penyelamatan Korban Tenggelam" in res
        
        # Verify AI slop icons are stripped
        for slop_icon in ["📞", "🚨", "📚", "ℹ️", "ℹ"]:
            assert slop_icon not in res
        
        # Verify prompt had the official citation and no-emoji instruction
        call_args = mock_llm.call_args[1]
        assert "TANPA EMOJI ATAU IKON DEKORATIF" in call_args["prompt"]
        assert "LEBIH BANYAK SUMBER LEBIH BAGUS" in call_args["prompt"]
