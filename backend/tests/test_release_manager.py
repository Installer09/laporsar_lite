import pytest
import os
import sys
import json
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

# Ensure repository root is in sys.path for scripts import
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from main import app
from app.core.websocket import ConnectionManager
from safe_migration import SafeMigrationRunner


@pytest.fixture
async def client(mock_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestReleaseManagerEndpoints:
    """Test suite for health check probes and release readiness endpoints."""

    async def test_health_check_version_3_0(self, client: AsyncClient):
        """Verify basic /health returns version 3.0.0 and healthy status."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "3.0.0"
        assert "storage" in data

    async def test_liveness_probe(self, client: AsyncClient):
        """Verify Kubernetes/Docker liveness probe /health/live."""
        response = await client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert data["version"] == "3.0.0"

    async def test_readiness_probe_healthy(self, client: AsyncClient):
        """Verify /health/ready returns 200 when database and redis are healthy."""
        with patch("app.db.session.SessionLocal") as mock_session_local:
            mock_session = AsyncMock()
            mock_session.execute.return_value = MagicMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            with patch("main.check_redis_health", new_callable=AsyncMock) as mock_check_redis:
                mock_check_redis.return_value = True

                response = await client.get("/health/ready")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ready"
                assert data["version"] == "3.0.0"
                assert "database" in data["checks"]
                assert "redis" in data["checks"]
                assert "storage" in data["checks"]
                assert data["checks"]["database"] == "healthy"
                assert data["checks"]["redis"] == "healthy"

    async def test_readiness_probe_db_failure(self, client: AsyncClient):
        """Verify /health/ready returns 503 when Master DB check throws an exception."""
        with patch("app.db.session.SessionLocal") as mock_session_local:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Connection refused to postgres:5432")
            mock_session_local.return_value.__aenter__.return_value = mock_session

            with patch("main.check_redis_health", new_callable=AsyncMock) as mock_check_redis:
                mock_check_redis.return_value = True

                response = await client.get("/health/ready")
                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "degraded"
                assert "unhealthy" in data["checks"]["database"]

    async def test_readiness_probe_redis_failure(self, client: AsyncClient):
        """Verify /health/ready returns 503 when Redis check throws an exception."""
        with patch("app.db.session.SessionLocal") as mock_session_local:
            mock_session = AsyncMock()
            mock_session.execute.return_value = MagicMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session

            with patch("main.check_redis_health", new_callable=AsyncMock) as mock_check_redis:
                mock_check_redis.side_effect = Exception("Redis connection timeout")

                response = await client.get("/health/ready")
                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "degraded"
                assert "unhealthy" in data["checks"]["redis"]
                assert data["status"] == "degraded"
                assert "unhealthy" in data["checks"]["redis"]


@pytest.mark.asyncio
class TestGracefulShutdownWebSocket:
    """Verify zero-downtime WebSocket graceful disconnection with code 1001."""

    async def test_graceful_disconnect_all(self):
        cm = ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await cm.connect(mock_ws1, "tenant1")
        await cm.connect(mock_ws2, "tenant2")
        assert cm._get_total_connections() == 2

        await cm.graceful_disconnect_all(reason="Server is restarting for update")

        # Verify notification message sent
        assert mock_ws1.send_text.called
        sent_msg_raw = mock_ws1.send_text.call_args[0][0]
        sent_msg = json.loads(sent_msg_raw)
        assert sent_msg["type"] == "server_shutdown"
        assert sent_msg["status"] == "reconnecting"

        # Verify closed with code 1001 (Going Away)
        mock_ws1.close.assert_called_with(code=1001, reason="Server is restarting for update")
        mock_ws2.close.assert_called_with(code=1001, reason="Server is restarting for update")

        # Verify connection pools cleared
        assert cm._get_total_connections() == 0


@pytest.mark.asyncio
class TestSafeMigrationRunner:
    """Test suite for automated pre-migration backups and guarded migration runs."""

    async def test_preflight_check_healthy(self):
        runner = SafeMigrationRunner()
        mock_sess = AsyncMock()
        mock_sess.execute.return_value = MagicMock()
        runner.session_factory = MagicMock()
        runner.session_factory.return_value.__aenter__.return_value = mock_sess

        with patch.object(runner, "get_active_tenants", new_callable=AsyncMock) as mock_get_t:
            mock_tenant = MagicMock()
            mock_tenant.slug = "natuna"
            mock_tenant.name = "Kantor SAR Natuna"
            mock_tenant.db_url = "postgresql+asyncpg://user:pass@localhost/db"
            mock_get_t.return_value = [mock_tenant]

            with patch.object(runner, "get_alembic_current_rev", new_callable=AsyncMock) as mock_rev:
                mock_rev.return_value = "8a19e5a506f0"

                with patch("app.db.session.get_tenant_sessionmaker") as mock_sm:
                    mock_tenant_sess = AsyncMock()
                    mock_sm.return_value.return_value.__aenter__.return_value = mock_tenant_sess

                    report = await runner.preflight_check()
                    assert report["master_db"] == "healthy"
                    assert len(report["tenants"]) == 1
                    assert report["tenants"][0]["slug"] == "natuna"
        await runner.close()

    async def test_create_pre_migration_backup(self):
        runner = SafeMigrationRunner()
        mock_sess = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = []
        mock_sess.execute.return_value = mock_res
        runner.session_factory = MagicMock()
        runner.session_factory.return_value.__aenter__.return_value = mock_sess

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(runner, "get_active_tenants", new_callable=AsyncMock) as mock_get_t:
                mock_get_t.return_value = []

                backup_path = await runner.create_pre_migration_backup(custom_dir=temp_dir)
                assert backup_path == temp_dir
                manifest_file = os.path.join(temp_dir, "manifest.json")
                assert os.path.exists(manifest_file)

                with open(manifest_file, "r") as f:
                    manifest = json.load(f)
                assert manifest["status"] == "success"
                assert "timestamp" in manifest
        await runner.close()

    async def test_dry_run_execution(self):
        runner = SafeMigrationRunner()
        with patch.object(runner, "preflight_check", new_callable=AsyncMock) as mock_pre:
            mock_pre.return_value = {"status": "ok", "master_db": "healthy", "tenants": []}

            result = await runner.execute_migrations(backup_first=False, dry_run=True)
            assert result["status"] == "dry_run_complete"
        await runner.close()


class TestReleaseScripts:
    """Verify CLI orchestration scripts for Blue-Green and Instant Rollback."""

    def test_slot_switching_and_state(self, tmp_path):
        from scripts import deploy_bluegreen
        original_state = deploy_bluegreen.STATE_FILE
        original_conf = deploy_bluegreen.UPSTREAM_CONF

        test_state = tmp_path / ".active_slot"
        test_conf = tmp_path / "upstream_active.conf"

        deploy_bluegreen.STATE_FILE = test_state
        deploy_bluegreen.UPSTREAM_CONF = test_conf

        try:
            deploy_bluegreen.set_active_slot("green")
            assert deploy_bluegreen.get_active_slot() == "green"
            assert "backend_green" in test_conf.read_text()

            deploy_bluegreen.set_active_slot("blue")
            assert deploy_bluegreen.get_active_slot() == "blue"
            assert "backend_blue" in test_conf.read_text()
        finally:
            deploy_bluegreen.STATE_FILE = original_state
            deploy_bluegreen.UPSTREAM_CONF = original_conf

    def test_rollback_dry_run(self):
        from scripts.rollback import rollback
        # Must not raise exceptions
        rollback(dry_run=True)

    def test_deploy_dry_run(self):
        from scripts.deploy_bluegreen import deploy
        # Must not raise exceptions
        deploy(dry_run=True)

