import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from main import app
from app.db.session import get_db
from app.models.settings_models import WidgetIntegrationRequest

@pytest.fixture
def mock_db_with_widget():
    db = MagicMock()
    db.execute = AsyncMock()
    
    # Create fake widgets
    approved_widget = WidgetIntegrationRequest(
        id=1,
        partner_name="Test Partner",
        website_url="http://example.com",
        official_email="partner@test.com",
        official_phone="0812345678",
        api_key="sar_approved_key_123",
        status="APPROVED"
    )
    
    pending_widget = WidgetIntegrationRequest(
        id=2,
        partner_name="Pending Partner",
        website_url="http://pending.com",
        official_email="pending@test.com",
        official_phone="0812345679",
        api_key="sar_pending_key_123",
        status="PENDING"
    )

    def execute_side_effect(query, *args, **kwargs):
        mock_result = MagicMock()
        try:
            params = query.compile().params
            param_vals = list(params.values())
        except Exception:
            param_vals = []
            
        # Only return the widget if the api_key matches and status is APPROVED.
        # Since the query checks status == "APPROVED", we only return the approved widget.
        if "sar_approved_key_123" in param_vals:
            mock_result.scalars.return_value.first.return_value = approved_widget
        else:
            mock_result.scalars.return_value.first.return_value = None
            
        mock_result.scalar_one_or_none.return_value = None
        return mock_result

    db.execute.side_effect = execute_side_effect
    return db

@pytest.fixture
async def client(mock_db_with_widget):
    app.dependency_overrides[get_db] = lambda: mock_db_with_widget
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
class TestWidgetAuth:
    
    async def test_web_message_no_auth(self, client):
        """Test that sending a message without widget key header or JWT yields 403."""
        response = await client.post(
            "/api/chat/sessions/web/message",
            json={"user_id": "web_test_123", "message": "Halo"}
        )
        assert response.status_code == 403
        assert "Missing Widget API Key." in response.json()["detail"]

    async def test_web_message_invalid_key(self, client):
        """Test that sending a message with an invalid API Key yields 403."""
        response = await client.post(
            "/api/chat/sessions/web/message",
            json={"user_id": "web_test_123", "message": "Halo"},
            headers={"X-Widget-API-Key": "sar_invalid_key"}
        )
        assert response.status_code == 403
        assert "Invalid or unapproved Widget API Key." in response.json()["detail"]

    async def test_web_message_pending_key(self, client):
        """Test that sending a message with a pending API Key yields 403."""
        response = await client.post(
            "/api/chat/sessions/web/message",
            json={"user_id": "web_test_123", "message": "Halo"},
            headers={"X-Widget-API-Key": "sar_pending_key_123"}
        )
        assert response.status_code == 403
        assert "Invalid or unapproved Widget API Key." in response.json()["detail"]

    async def test_web_message_approved_key_missing_origin(self, client):
        """Test that sending a message with approved key but missing Origin yields 403."""
        response = await client.post(
            "/api/chat/sessions/web/message",
            json={"user_id": "web_test_123", "message": "Halo"},
            headers={"X-Widget-API-Key": "sar_approved_key_123"}
        )
        assert response.status_code == 403
        assert "Domain origin verification failed. Request lacks Origin or Referer." in response.json()["detail"]

    async def test_web_message_approved_key_wrong_origin(self, client):
        """Test that sending a message with approved key but wrong Origin yields 403."""
        response = await client.post(
            "/api/chat/sessions/web/message",
            json={"user_id": "web_test_123", "message": "Halo"},
            headers={
                "X-Widget-API-Key": "sar_approved_key_123",
                "Origin": "http://wrong-domain.com"
            }
        )
        assert response.status_code == 403
        assert "Domain origin verification failed." in response.json()["detail"]

    async def test_web_message_approved_key_correct_origin(self, client):
        """Test that sending a message with approved key and correct Origin passes authorization."""
        from unittest.mock import patch
        
        with patch("app.api.routes.chat.chatbot_engine.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"text": "Halo, ada yang bisa dibantu?"}
            
            response = await client.post(
                "/api/chat/sessions/web/message",
                json={"user_id": "web_test_123", "message": "Halo"},
                headers={
                    "X-Widget-API-Key": "sar_approved_key_123",
                    "Origin": "http://example.com"
                }
            )
            assert response.status_code == 200
            assert response.json()["reply"] == "Halo, ada yang bisa dibantu?"


from app.core.security import verify_jwt, verify_admin

@pytest.fixture
async def admin_client(mock_db_with_widget):
    app.dependency_overrides[get_db] = lambda: mock_db_with_widget
    app.dependency_overrides[verify_jwt] = lambda: {"user_id": 1, "email": "admin@test.com", "role": "Super Admin"}
    app.dependency_overrides[verify_admin] = lambda: {"user_id": 1, "email": "admin@test.com", "role": "Super Admin"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestWidgetSettings:
    
    async def test_create_widget_request_admin(self, admin_client, mock_db_with_widget):
        """Test manually creating widget request as admin."""
        from datetime import datetime
        
        # Mock database commit and refresh
        mock_db_with_widget.commit = AsyncMock()
        
        def refresh_side_effect(obj):
            obj.id = 1
            obj.created_at = datetime.now()
            return obj
            
        mock_db_with_widget.refresh = AsyncMock(side_effect=refresh_side_effect)
        
        response = await admin_client.post(
            "/api/settings/widget-requests/admin",
            json={
                "partner_name": "Admin Registered",
                "website_url": "admin-site.com",
                "official_email": "admin@site.com",
                "official_phone": "0812345678",
                "status": "APPROVED"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["partner_name"] == "Admin Registered"
        assert data["status"] == "APPROVED"
        assert data["api_key"] is not None
        assert data["api_key"].startswith("sar_")

    async def test_update_widget_request(self, admin_client, mock_db_with_widget):
        """Test updating widget request status and info."""
        from datetime import datetime
        mock_db_with_widget.commit = AsyncMock()
        mock_db_with_widget.refresh = AsyncMock()
        
        # We need mock_db_with_widget.execute to return a request
        existing_widget = WidgetIntegrationRequest(
            id=1,
            partner_name="Old Partner",
            website_url="old-site.com",
            official_email="old@site.com",
            official_phone="0812345678",
            api_key=None,
            status="PENDING",
            created_at=datetime.now()
        )
        
        # Modify execute side effect to return existing_widget on query
        orig_side_effect = mock_db_with_widget.execute.side_effect
        def temp_side_effect(query, *args, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = existing_widget
            mock_result.scalars.return_value.first.return_value = None
            return mock_result
            
        mock_db_with_widget.execute.side_effect = temp_side_effect
        
        response = await admin_client.put(
            "/api/settings/widget-requests/1",
            json={
                "partner_name": "Updated Partner",
                "status": "APPROVED"
              }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["partner_name"] == "Updated Partner"
        assert data["status"] == "APPROVED"
        assert data["api_key"] is not None
        assert data["api_key"].startswith("sar_")
        
        # Restore mock side effect
        mock_db_with_widget.execute.side_effect = orig_side_effect

    async def test_delete_widget_request(self, admin_client, mock_db_with_widget):
        """Test deleting a widget request."""
        from datetime import datetime
        mock_db_with_widget.commit = AsyncMock()
        mock_db_with_widget.delete = AsyncMock()
        
        existing_widget = WidgetIntegrationRequest(
            id=1,
            partner_name="To Delete",
            website_url="delete.com",
            official_email="del@site.com",
            official_phone="0812345678",
            status="APPROVED",
            created_at=datetime.now()
        )
        
        orig_side_effect = mock_db_with_widget.execute.side_effect
        def temp_side_effect(query, *args, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = existing_widget
            return mock_result
            
        mock_db_with_widget.execute.side_effect = temp_side_effect
        
        response = await admin_client.delete("/api/settings/widget-requests/1")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        mock_db_with_widget.delete.assert_called_once_with(existing_widget)
        mock_db_with_widget.execute.side_effect = orig_side_effect

