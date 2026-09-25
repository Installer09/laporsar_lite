import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.group_listener_service import GroupListenerService, group_listener_service
from app.models.report import Report, ReportStatus
from app.models.knowledge_models import DictionaryWord, DictionaryStatus


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    db.info = {"tenant_slug": "global"}
    return db


@pytest.fixture
def sample_report():
    return Report(
        id=42,
        no_laporan="KMM-202605-001",
        pelapor_nama="Pak Subur",
        pelapor_nomor="081234567890",
        jenis_kejadian="Kondisi Membahayakan Manusia",
        lokasi_teks="Pantai Pasir Padi",
        koordinat_lat=-2.1234,
        koordinat_lng=106.1234,
        korban="2 orang",
        korban_total=2,
        korban_selamat=0,
        korban_meninggal=0,
        korban_hilang=2,
        unsur_alut="Rescuer Kansar Pangkalpinang",
        kronologi="Dua nelayan terseret ombak saat memancing.",
        metadata_kejadian={"telegram_group_msg_id": 9999},
        status=ReportStatus.AKTIF
    )


@pytest.mark.asyncio
class TestGroupListenerService:

    async def test_is_group_chat(self):
        service = GroupListenerService()
        
        # Supergroup
        msg1 = {"chat": {"type": "supergroup", "id": -100123456789}}
        assert service.is_group_chat(msg1) is True

        # Regular group
        msg2 = {"chat": {"type": "group", "id": -987654}}
        assert service.is_group_chat(msg2) is True

        # Negative ID group
        msg3 = {"chat": {"type": "private", "id": -123456}}
        assert service.is_group_chat(msg3) is True

        # Private user chat
        msg4 = {"chat": {"type": "private", "id": 12345678}}
        assert service.is_group_chat(msg4) is False

    async def test_resolve_target_report_by_replied_msg_id(self, mock_db, sample_report):
        service = GroupListenerService()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_report
        mock_db.execute.return_value = mock_result

        incoming_msg = {
            "chat": {"id": -100123456789, "type": "supergroup"},
            "message_id": 10001,
            "reply_to_message": {
                "message_id": 9999,
                "text": "*INFO AWAL*\nMhn izin melaporkan musibah..."
            }
        }

        matched = await service.resolve_target_report(incoming_msg, "Update korban selamat 1 orang", mock_db)
        assert matched is not None
        assert matched.no_laporan == "KMM-202605-001"

    async def test_resolve_target_report_by_explicit_no_laporan(self, mock_db, sample_report):
        service = GroupListenerService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_report
        mock_db.execute.return_value = mock_result

        incoming_msg = {
            "chat": {"id": -100123456789, "type": "supergroup"},
            "message_id": 10002
        }

        matched = await service.resolve_target_report(
            incoming_msg, 
            "Perkembangan untuk KMM-202605-001 alut RIB 01 telah dikerahkan", 
            mock_db
        )
        assert matched is not None
        assert matched.no_laporan == "KMM-202605-001"

    async def test_resolve_target_report_sole_active_report(self, mock_db, sample_report):
        service = GroupListenerService()

        # Reply is empty and direct text has no regex, but DB returns 1 active report
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_report]
        mock_db.execute.return_value = mock_result

        incoming_msg = {
            "chat": {"id": -100123456789, "type": "supergroup"},
            "message_id": 10003
        }

        # Text contains SAR keywords (korban, selamat)
        matched = await service.resolve_target_report(
            incoming_msg, 
            "Update: 1 korban ditemukan selamat oleh tim SAR", 
            mock_db
        )
        assert matched is not None
        assert matched.no_laporan == "KMM-202605-001"

    async def test_resolve_target_report_ignores_casual_chat(self, mock_db, sample_report):
        service = GroupListenerService()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_report]
        mock_db.execute.return_value = mock_result

        incoming_msg = {
            "chat": {"id": -100123456789, "type": "supergroup"},
            "message_id": 10004
        }

        # Casual chat without SAR keywords
        matched = await service.resolve_target_report(
            incoming_msg, 
            "Selamat pagi rekan-rekan, jangan lupa apel pagi hari ini.", 
            mock_db
        )
        assert matched is None

    async def test_fallback_delta_extractor(self, sample_report):
        service = GroupListenerService()
        delta = service._fallback_delta_extractor(
            sample_report,
            "Update: 1 orang selamat ditemukan nelayan di Karang Ular, koordinat -2.1240, 106.1290"
        )
        assert delta["is_relevant_sar_update"] is True
        assert delta["fields_to_update"]["korban_selamat"] == 1
        assert delta["fields_to_update"]["koordinat_lat"] == -2.1240
        assert delta["fields_to_update"]["koordinat_lng"] == 106.1290
        assert len(delta["new_locations"]) > 0

    @patch('app.services.group_listener_service.ai_provider_manager.llm_generate')
    async def test_extract_delta_update_with_llm(self, mock_llm, mock_db, sample_report):
        mock_llm.return_value = '''{
            "is_relevant_sar_update": true,
            "summary_text": "1 korban ditemukan selamat di Pantai Batu Bedaun.",
            "fields_to_update": {
                "korban_selamat": 1,
                "korban_meninggal": 0,
                "korban_hilang": 1,
                "unsur_alut": "RIB 01 Pangkalpinang",
                "lokasi_teks": null,
                "koordinat_lat": null,
                "koordinat_lng": null,
                "status": null
            },
            "timeline_entry": "1 korban berhasil dievakuasi selamat di Pantai Batu Bedaun.",
            "new_locations": [
                {"word": "Pantai Batu Bedaun", "description": "Lokasi penemuan korban selamat"}
            ],
            "new_terms": []
        }'''

        service = GroupListenerService()
        delta = await service.extract_delta_update(sample_report, "Update 1 korban selamat di Pantai Batu Bedaun", mock_db)
        
        assert delta["is_relevant_sar_update"] is True
        assert delta["fields_to_update"]["korban_selamat"] == 1
        assert delta["fields_to_update"]["korban_hilang"] == 1
        assert len(delta["new_locations"]) == 1
        assert delta["new_locations"][0]["word"] == "Pantai Batu Bedaun"

    @patch('app.services.group_listener_service.manager.broadcast')
    async def test_apply_delta_update_and_learning(self, mock_broadcast, mock_db, sample_report):
        service = GroupListenerService()
        service.llm_rag.vectorize_report = AsyncMock()

        # Mock DB search for existing DictionaryWord
        mock_word_res = MagicMock()
        mock_word_res.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_word_res

        delta = {
            "summary_text": "1 korban selamat ditemukan, alut RIB 01 merapat",
            "fields_to_update": {
                "korban_selamat": 1,
                "korban_hilang": 1,
                "unsur_alut": "RIB 01 Kansar"
            },
            "timeline_entry": "1 korban dievakuasi selamat ke RSUD.",
            "new_locations": [
                {"word": "Tanjung Berikat", "description": "Lokasi pemantauan laut"}
            ]
        }

        updated_rep, summary = await service.apply_delta_update(sample_report, delta, mock_db)

        # Assert victim fields updated
        assert updated_rep.korban_selamat == 1
        assert updated_rep.korban_hilang == 1
        assert updated_rep.korban_total == 2
        assert "RIB 01 Kansar" in updated_rep.unsur_alut
        assert "1 korban dievakuasi selamat ke RSUD" in updated_rep.kronologi

        # Assert DictionaryWord added for Tanjung Berikat
        mock_db.add.assert_called()
        added_objs = [call_arg[0][0] for call_arg in mock_db.add.call_args_list]
        dict_words = [o for o in added_objs if isinstance(o, DictionaryWord)]
        assert len(dict_words) == 1
        assert dict_words[0].word == "Tanjung Berikat"
        assert dict_words[0].ner_type == "LOCATION"
        assert dict_words[0].status == DictionaryStatus.APPROVED

        # Assert vector memory re-vectorized
        service.llm_rag.vectorize_report.assert_called_once()

        # Assert WebSocket broadcast was triggered
        mock_broadcast.assert_called_once()
