import pytest
import os
import uuid
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.settings_models import User, SystemSetting
from app.services.message_formatter import message_formatter
from app.api.routes.identitas import DEFAULT_IDENTITAS

# =====================================================================
# 1. Test Otentikasi dan Otorisasi Rute API (SEC-01, SEC-02, SEC-03)
# =====================================================================

@pytest.mark.asyncio
async def test_unauthorized_endpoints_access():
    """
    Memverifikasi bahwa seluruh endpoint konfigurasi, pengguna, dan kontak
    darurat menolak akses anonim (tanpa JWT valid).
    """
    from main import app
    from unittest.mock import patch, MagicMock
    from app.db.session import get_db
    
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    try:
        with patch("app.core.security.settings.DEV_ADMIN_ENABLED", False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # SEC-01: Settings & Config
                resp_config = await ac.get("/api/settings/config")
                assert resp_config.status_code == status.HTTP_401_UNAUTHORIZED
                
                resp_users = await ac.get("/api/settings/users")
                assert resp_users.status_code == status.HTTP_401_UNAUTHORIZED

                # SEC-02: ContactsDarurat
                resp_contacts = await ac.get("/api/contacts")
                assert resp_contacts.status_code == status.HTTP_401_UNAUTHORIZED

                # SEC-03: Knowledge & SOP Documents
                resp_sop = await ac.get("/api/knowledge/sop")
                assert resp_sop.status_code == status.HTTP_401_UNAUTHORIZED
    finally:
        app.dependency_overrides.clear()


# =====================================================================
# 2. Test Penutupan Celah Path Traversal KML Upload (SEC-04)
# =====================================================================

@pytest.mark.asyncio
async def test_kml_upload_path_traversal_mitigated():
    """
    Memverifikasi bahwa rute unggah KML mensterilkan nama berkas masukan
    dan mencegah Path Traversal (Arbitrary File Overwrite).
    """
    from main import app
    import jwt
    from app.core.config import settings
    from unittest.mock import MagicMock, AsyncMock
    from app.db.session import get_db
    
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    try:
        # 1. Generate a valid admin token in-memory
        token = jwt.encode(
            {"sub": "test_admin", "role": "admin"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        headers = {"Authorization": f"Bearer {token}"}
    
        # 2. Attempt Path Traversal file upload (e.g. filename = '../../dangerous.kml')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            traversal_filename = "../../dangerous.kml"
            file_payload = {"file": (traversal_filename, b"<kml>mock</kml>", "application/vnd.google-earth.kml+xml")}
            
            upload_resp = await ac.post(
                "/api/settings/identity/kml",
                files=file_payload,
                headers=headers
            )
            assert upload_resp.status_code == 200
            uploaded_path = upload_resp.json()["path"]
            
            # Ensure the filename is completely randomized and DOES NOT contain path traversal sequences
            assert "dangerous" not in uploaded_path
            assert ".." not in uploaded_path
            assert "uploads/maps/batas_wilayah_" in uploaded_path
            
            # Clean up physical file
            if os.path.exists(uploaded_path):
                os.remove(uploaded_path)
    finally:
        app.dependency_overrides.clear()


# =====================================================================
# 3. Test Integrasi Identitas Dinamis Laporan Info Awal
# =====================================================================

def test_dynamic_identity_rendering():
    """
    Memverifikasi bahwa pemformat pesan merender kop laporan dan motto
    secara dinamis jika data identitas disediakan oleh caller.
    """
    data = {
        "KLASIFIKASI": "Kecelakaan Kapal",
        "jenis_kejadian": "Kapal Mati Mesin",
        "LOKASI_KEJADIAN": "Perairan Bunguran",
        "WAKTU_KEJADIAN": "0530 1000 G",
        "KOORDINAT": "3°55'N 108°23'E",
        "JUMLAH_KORBAN_TOTAL": "1",
        "korban_selamat": "1",
        "korban_meninggal": "0",
        "korban_hilang": "0",
        "data_korban": [],
        
        # Dynamic Office Identity parameters
        "NAMA_INSTANSI": "Kantor Pencarian dan Pertolongan Pekanbaru",
        "MOTTO_INSTANSI": "Avignam Jagat Samagram\nCepat - Tepat - Handal",
        "TTD_KEPALA": "PEKANBARU 01"
    }
    
    report_text = message_formatter.render(None, data)
    
    # Verify custom office name, formatted motto with asterisks, and TTD are rendered
    assert "Kantor Pencarian dan Pertolongan Pekanbaru" in report_text
    assert "*Avignam Jagat Samagram*" in report_text
    assert "*Cepat - Tepat - Handal*" in report_text
    assert "PEKANBARU 01" in report_text
    
    # Ensure the default Natuna office is NOT in the rendered report
    assert "Kantor Pencarian dan Pertolongan Natuna" not in report_text
    assert "We Are Family" not in report_text


# =====================================================================
# 4. Test Modul Chat & Kontak Security Hardening (Pilar 1)
# =====================================================================

@pytest.mark.asyncio
async def test_chat_endpoints_unauthorized_access():
    """
    Memverifikasi bahwa seluruh endpoint chat menolak akses anonim (tanpa JWT valid).
    """
    from main import app
    from unittest.mock import patch, MagicMock
    from app.db.session import get_db
    
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    try:
        with patch("app.core.security.settings.DEV_ADMIN_ENABLED", False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # Panggilan ke modul chat harus ditolak 401
                resp_sessions = await ac.get("/api/chat/sessions")
                assert resp_sessions.status_code == status.HTTP_401_UNAUTHORIZED

                resp_get_session = await ac.get("/api/chat/sessions/999")
                assert resp_get_session.status_code == status.HTTP_401_UNAUTHORIZED

                resp_post_msg = await ac.post("/api/chat/sessions/999/message", json={"message": "Halo"})
                assert resp_post_msg.status_code == status.HTTP_401_UNAUTHORIZED
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_session_deletion_restricted_to_admin():
    """
    Memverifikasi bahwa penghapusan sesi chat hanya diperbolehkan untuk peran Admin
    dan memblokir peran User biasa maupun anonim.
    """
    from main import app
    import jwt
    from app.core.config import settings
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.db.session import get_db

    # 1. Generate token untuk User biasa (non-admin)
    user_token = jwt.encode(
        {"sub": "regular_user", "role": "User"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # 2. Generate token untuk Admin
    admin_token = jwt.encode(
        {"sub": "test_admin", "role": "admin"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Mock DB dependency
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("app.core.security.settings.DEV_ADMIN_ENABLED", False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # A. Tanpa token (Anonim) -> 401 Unauthorized
                resp_anon = await ac.delete("/api/chat/sessions/999")
                assert resp_anon.status_code == status.HTTP_401_UNAUTHORIZED

                # B. Dengan token User biasa -> 403 Forbidden
                resp_user = await ac.delete("/api/chat/sessions/999", headers=user_headers)
                assert resp_user.status_code == status.HTTP_403_FORBIDDEN

                # C. Dengan token Admin -> melewari auth (lanjut ke DB query, menghasilkan 404 Not Found)
                resp_admin = await ac.delete("/api/chat/sessions/999", headers=admin_headers)
                assert resp_admin.status_code == status.HTTP_404_NOT_FOUND
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_contact_deletion_restricted_to_admin():
    """
    Memverifikasi bahwa penghapusan kontak darurat hanya diperbolehkan untuk peran Admin
    dan memblokir peran User biasa maupun anonim.
    """
    from main import app
    import jwt
    from app.core.config import settings
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.db.session import get_db

    # 1. Generate token untuk User biasa (non-admin)
    user_token = jwt.encode(
        {"sub": "regular_user", "role": "User"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # 2. Generate token untuk Admin
    admin_token = jwt.encode(
        {"sub": "test_admin", "role": "admin"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Mock DB dependency
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("app.core.security.settings.DEV_ADMIN_ENABLED", False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # A. Tanpa token (Anonim) -> 401 Unauthorized
                resp_anon = await ac.delete("/api/contacts/999")
                assert resp_anon.status_code == status.HTTP_401_UNAUTHORIZED

                # B. Dengan token User biasa -> 403 Forbidden
                resp_user = await ac.delete("/api/contacts/999", headers=user_headers)
                assert resp_user.status_code == status.HTTP_403_FORBIDDEN

                # C. Dengan token Admin -> melewati auth (lanjut ke DB query, menghasilkan 404 Not Found)
                resp_admin = await ac.delete("/api/contacts/999", headers=admin_headers)
                assert resp_admin.status_code == status.HTTP_404_NOT_FOUND
    finally:
        app.dependency_overrides.clear()

