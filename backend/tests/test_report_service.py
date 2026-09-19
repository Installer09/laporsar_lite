import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from app.services.report_service import ReportService
from app.models.report import Report, ReportSequence, ReportStatus
from app.schemas.report import ReportCreate, ReportUpdate

@pytest.fixture
def db_session():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db

@pytest.fixture
def mock_report_create():
    return ReportCreate(
        pelapor_nama="Budi",
        pelapor_nomor="081234567890",
        jenis_kejadian="Banjir",
        waktu="Sekarang",
        lokasi_teks="Jakarta",
        korban="1 orang",
        kronologi="Air naik"
    )

@pytest.mark.asyncio
class TestReportService:

    @patch('app.services.report_service.datetime')
    async def test_generate_no_laporan_first(self, mock_datetime, db_session):
        mock_datetime.now.return_value.strftime.return_value = "202401"
        
        # Mock empty sequence DB query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db_session.execute.return_value = mock_result
        
        no_laporan = await ReportService._generate_no_laporan(db_session)
        
        assert no_laporan == "SAR-202401-001"
        db_session.add.assert_called_once()
        args, kwargs = db_session.add.call_args
        seq = args[0]
        assert seq.year_month == "202401"
        assert seq.last_seq == 1

    @patch('app.services.report_service.datetime')
    async def test_generate_no_laporan_subsequent(self, mock_datetime, db_session):
        mock_datetime.now.return_value.strftime.return_value = "202401"
        
        # Mock existing sequence
        mock_seq = ReportSequence(year_month="202401", last_seq=5)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_seq
        db_session.execute.return_value = mock_result
        
        no_laporan = await ReportService._generate_no_laporan(db_session)
        
        assert no_laporan == "SAR-202401-006"
        assert mock_seq.last_seq == 6

    @patch('app.services.report_service.manager', new_callable=AsyncMock)
    @patch('app.services.report_service.ReportService.enrich_report_geo')
    @patch('app.services.report_service.ReportService._generate_no_laporan')
    async def test_create_report_success(self, mock_generate, mock_enrich, mock_manager, db_session, mock_report_create):
        mock_generate.return_value = "SAR-202401-001"
        
        # Mock add and flush
        def side_effect_add(obj):
            obj.id = 1
        db_session.add.side_effect = side_effect_add
        
        report = await ReportService.create_report(mock_report_create, db_session)
        
        assert report.no_laporan == "SAR-202401-001"
        assert report.pelapor_nama == "Budi"
        assert report.status == ReportStatus.PENDING
        mock_enrich.assert_awaited_once_with(report, db_session)
        db_session.add.assert_called_once()
        db_session.commit.assert_awaited_once()
        db_session.refresh.assert_awaited_once_with(report)
        mock_manager.broadcast.assert_awaited_once_with({"event": "new_report", "report_id": 1}, db=db_session)

    @patch('app.services.report_service.ReportService._generate_no_laporan')
    async def test_create_report_db_error(self, mock_generate, db_session, mock_report_create):
        mock_generate.return_value = "SAR-202401-001"
        db_session.commit.side_effect = Exception("DB Error")
        
        with pytest.raises(HTTPException) as exc:
            await ReportService.create_report(mock_report_create, db_session)
            
        assert exc.value.status_code == 500
        db_session.rollback.assert_awaited_once()

    @patch('app.services.report_service.manager', new_callable=AsyncMock)
    async def test_update_report_success(self, mock_manager, db_session):
        mock_report = Report(id=1, status=ReportStatus.PENDING)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        db_session.execute.return_value = mock_result
        
        update_data = ReportUpdate(status=ReportStatus.AKTIF)
        
        updated = await ReportService.update_report(1, update_data, db_session)
        
        assert updated.status == ReportStatus.AKTIF
        db_session.commit.assert_awaited_once()
        db_session.refresh.assert_awaited_once_with(mock_report)
        mock_manager.broadcast.assert_awaited_once_with({"event": "report_updated", "report_id": 1}, db=db_session)

    async def test_update_report_not_found(self, db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db_session.execute.return_value = mock_result
        
        update_data = ReportUpdate(status=ReportStatus.AKTIF)
        
        with pytest.raises(HTTPException) as exc:
            await ReportService.update_report(1, update_data, db_session)
            
        assert exc.value.status_code == 404

    @patch('app.services.report_service.parse_coordinates')
    @patch('app.services.report_service.find_nearest_location')
    async def test_enrich_report_geo_success(self, mock_find, mock_parse, db_session):
        mock_parse.return_value = (-6.2, 106.8)
        mock_find.return_value = {"name": "Pos SAR Jakarta", "distance_nm": 5.2, "heading": 180}
        
        mock_location_result = MagicMock()
        mock_location_result.scalars.return_value.all.return_value = [MagicMock()]
        db_session.execute.return_value = mock_location_result
        
        report = Report(lokasi_teks="-6.2, 106.8")
        
        await ReportService.enrich_report_geo(report, db_session)
        
        assert report.koordinat_lat == -6.2
        assert report.koordinat_lng == 106.8
        assert report.pos_sar_terdekat == "Pos SAR Jakarta"
        assert report.jarak_ke_lokasi == "5.2 Nm"
        assert report.heading_ke_lokasi == 180
        assert report.gmaps_link == "https://www.google.com/maps?q=-6.2,106.8"

    @patch('app.services.report_service.parse_coordinates')
    async def test_enrich_report_geo_no_coords(self, mock_parse, db_session):
        mock_parse.return_value = None
        report = Report(lokasi_teks="Jakarta")
        
        await ReportService.enrich_report_geo(report, db_session)
        
        assert report.koordinat_lat is None
        assert report.koordinat_lng is None
        assert report.pos_sar_terdekat is None

    @patch('app.services.report_service.manager', new_callable=AsyncMock)
    @patch('app.services.reply_dispatcher.reply_dispatcher')
    async def test_update_report_whatsapp_notification(self, mock_reply_dispatcher, mock_manager, db_session):
        from app.models.chat_session import ChatSession
        
        mock_report = Report(
            id=1,
            status=ReportStatus.PENDING,
            pelapor_nomor="081234567890",
            no_laporan="SAR-202401-001",
            jenis_kejadian="Banjir",
            pos_sar_terdekat="Pos SAR Jakarta"
        )
        
        mock_session = ChatSession(
            channel="whatsapp",
            contact_phone="081234567890",
            user_id="wa_081234567890"
        )
        
        mock_report_res = MagicMock()
        mock_report_res.scalar_one_or_none.return_value = mock_report
        
        mock_setting_res = MagicMock()
        mock_setting_res.scalars.return_value.all.return_value = []
        
        mock_session_res = MagicMock()
        mock_session_res.scalars.return_value.all.return_value = [mock_session]
        
        db_session.execute.side_effect = [mock_report_res, mock_setting_res, mock_session_res]
        
        mock_reply_dispatcher.send_whatsapp_reply = AsyncMock(return_value=True)
        
        update_data = ReportUpdate(status=ReportStatus.AKTIF)
        
        updated = await ReportService.update_report(1, update_data, db_session)
        
        assert updated.status == ReportStatus.AKTIF
        mock_reply_dispatcher.send_whatsapp_reply.assert_awaited_once()
        args, kwargs = mock_reply_dispatcher.send_whatsapp_reply.call_args
        assert kwargs["recipient_phone"] == "081234567890"
        assert "AKTIF" in kwargs["text"]
        assert "SAR-202401-001" in kwargs["text"]
        assert "alut" not in kwargs["text"].lower()

    @patch('app.services.report_service.manager', new_callable=AsyncMock)
    @patch('app.services.reply_dispatcher.reply_dispatcher')
    async def test_update_report_telegram_notification(self, mock_reply_dispatcher, mock_manager, db_session):
        from app.models.chat_session import ChatSession
        
        mock_report = Report(
            id=1,
            status=ReportStatus.PENDING,
            pelapor_nomor="081234567890",
            no_laporan="SAR-202401-001",
            jenis_kejadian="Banjir",
            pos_sar_terdekat="Pos SAR Jakarta"
        )
        
        mock_session = ChatSession(
            channel="telegram",
            contact_phone="081234567890",
            user_id="tg_123456789"
        )
        
        mock_report_res = MagicMock()
        mock_report_res.scalar_one_or_none.return_value = mock_report
        
        mock_setting_res = MagicMock()
        mock_setting_res.scalars.return_value.all.return_value = []
        
        mock_session_res = MagicMock()
        mock_session_res.scalars.return_value.all.return_value = [mock_session]
        
        db_session.execute.side_effect = [mock_report_res, mock_setting_res, mock_session_res]
        
        mock_reply_dispatcher.send_telegram_reply = AsyncMock(return_value=True)
        
        update_data = ReportUpdate(status=ReportStatus.AKTIF)
        
        updated = await ReportService.update_report(1, update_data, db_session)
        
        assert updated.status == ReportStatus.AKTIF
        mock_reply_dispatcher.send_telegram_reply.assert_awaited_once()
        args, kwargs = mock_reply_dispatcher.send_telegram_reply.call_args
        assert kwargs["chat_id"] == "123456789"
        assert "AKTIF" in kwargs["text"]
        assert "SAR-202401-001" in kwargs["text"]
        assert "alut" not in kwargs["text"].lower()

    @patch('app.services.report_service.manager', new_callable=AsyncMock)
    @patch('app.services.reply_dispatcher.reply_dispatcher')
    async def test_update_report_no_status_change_notification(self, mock_reply_dispatcher, mock_manager, db_session):
        mock_report = Report(
            id=1,
            status=ReportStatus.PENDING,
            pelapor_nomor="081234567890",
            no_laporan="SAR-202401-001",
            jenis_kejadian="Banjir"
        )
        
        mock_report_res = MagicMock()
        mock_report_res.scalar_one_or_none.return_value = mock_report
        
        db_session.execute.return_value = mock_report_res
        
        mock_reply_dispatcher.send_whatsapp_reply = AsyncMock()
        mock_reply_dispatcher.send_telegram_reply = AsyncMock()
        
        update_data = ReportUpdate(jenis_kejadian="Kecelakaan Kapal")
        
        updated = await ReportService.update_report(1, update_data, db_session)
        
        assert updated.jenis_kejadian == "Kecelakaan Kapal"
        mock_reply_dispatcher.send_whatsapp_reply.assert_not_called()
        mock_reply_dispatcher.send_telegram_reply.assert_not_called()

    async def test_enrich_report_geo_dynamic_radius(self, db_session):
        # 1. Test Sea terrain default radius
        rep_sea = Report(jenis_kejadian="Kecelakaan Kapal", lokasi_teks="Selat Lampa")
        await ReportService.enrich_report_geo(rep_sea, db_session)
        assert rep_sea.radius_pencarian == 3.704

        # 2. Test Mountain/Jungle terrain default radius
        rep_mt = Report(jenis_kejadian="KMM", lokasi_teks="Lereng Gunung Ranai")
        await ReportService.enrich_report_geo(rep_mt, db_session)
        assert rep_mt.radius_pencarian == 2.0

        # 3. Test other terrain default radius
        rep_other = Report(jenis_kejadian="Bencana", lokasi_teks="Desa Kelarik")
        await ReportService.enrich_report_geo(rep_other, db_session)
        assert rep_other.radius_pencarian == 1.0

        # 4. Test explicit radius extraction in km
        rep_km = Report(jenis_kejadian="Bencana", lokasi_teks="Desa Kelarik", kronologi="Korban hilang dalam radius 3.5 km dari rumah.")
        await ReportService.enrich_report_geo(rep_km, db_session)
        assert rep_km.radius_pencarian == 3.5

        # 5. Test explicit radius extraction in Nautical Miles (mil)
        rep_nm = Report(jenis_kejadian="Kecelakaan Kapal", lokasi_teks="Selat Lampa", kronologi="Kapal mati mesin sekitar 3 mil dari tanjung.")
        await ReportService.enrich_report_geo(rep_nm, db_session)
        assert abs(rep_nm.radius_pencarian - (3.0 * 1.852)) < 1e-4

class TestVesselExtraction:
    def test_extract_data_kapal_pompong_warne_biru(self):
        from app.services.rule_extractor import RuleExtractor
        from app.services.message_formatter import message_formatter
        
        # Test case 1: Pompong warne biru 3 Gt
        text = "Pompong warne biru 3 Gt"
        extracted = RuleExtractor.extract_data_kapal(text)
        
        # Format the result
        formatted = message_formatter.format_data_kapal(extracted)
        
        assert "JENIS KAPAL: Pompong (3 GT)" in formatted
        assert "WARNA KAPAL: Biru" in formatted
        assert "NAMA KAPAL: -" in formatted

    def test_extract_data_kapal_pompong_sri_rejeki(self):
        from app.services.rule_extractor import RuleExtractor
        from app.services.message_formatter import message_formatter
        
        # Test case 2: pompong sri rejeki warna biru 3 Gt
        text = "pompong sri rejeki warna biru 3 Gt"
        extracted = RuleExtractor.extract_data_kapal(text)
        
        # Format the result
        formatted = message_formatter.format_data_kapal(extracted)
        
        assert "JENIS KAPAL: Pompong (3 GT)" in formatted
        assert "WARNA KAPAL: Biru" in formatted
        assert "NAMA KAPAL: Sri Rejeki" in formatted
