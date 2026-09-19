import pytest
from unittest.mock import AsyncMock, MagicMock
import json
from app.core.websocket import ConnectionManager

@pytest.fixture
def manager():
    return ConnectionManager()

@pytest.fixture
def mock_websocket():
    return AsyncMock()

@pytest.mark.asyncio
class TestConnectionManager:
    async def test_initial_state(self, manager):
        assert manager._get_total_connections() == 0

    async def test_connect_adds_websocket(self, manager, mock_websocket):
        await manager.connect(mock_websocket, "pusat")
        mock_websocket.accept.assert_awaited_once()
        assert manager._get_total_connections() == 1
        assert "pusat" in manager.active_connections
        assert mock_websocket in manager.active_connections["pusat"]

    async def test_connect_multiple(self, manager):
        ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()
        await manager.connect(ws1, "pusat")
        await manager.connect(ws2, "natuna")
        await manager.connect(ws3, "pusat")
        assert manager._get_total_connections() == 3
        assert len(manager.active_connections["pusat"]) == 2
        assert len(manager.active_connections["natuna"]) == 1

    async def test_disconnect_removes_websocket(self, manager, mock_websocket):
        await manager.connect(mock_websocket, "pusat")
        assert manager._get_total_connections() == 1
        manager.disconnect(mock_websocket)
        assert manager._get_total_connections() == 0
        assert "pusat" not in manager.active_connections

    async def test_disconnect_nonexistent_raises_error(self, manager, mock_websocket):
        # Should be safe, does not raise error
        manager.disconnect(mock_websocket)
        assert manager._get_total_connections() == 0

    async def test_broadcast_sends_to_same_tenant_and_global(self, manager):
        ws_pusat = AsyncMock()
        ws_natuna = AsyncMock()
        ws_global = AsyncMock()
        
        await manager.connect(ws_pusat, "pusat")
        await manager.connect(ws_natuna, "natuna")
        await manager.connect(ws_global, "global")
        
        message = {"event": "test"}
        message_str = json.dumps(message)
        
        # Broadcast to "pusat"
        await manager.broadcast(message, tenant_slug="pusat")
        
        ws_pusat.send_text.assert_awaited_once_with(message_str)
        ws_global.send_text.assert_awaited_once_with(message_str)
        ws_natuna.send_text.assert_not_awaited()

    async def test_broadcast_handles_exception(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1, "pusat")
        await manager.connect(ws2, "pusat")
        
        ws1.send_text.side_effect = Exception("Network error")
        message = {"event": "test"}
        
        # Should not raise exception
        await manager.broadcast(message, tenant_slug="pusat")
        
        ws1.send_text.assert_awaited_once_with(json.dumps(message))
        ws2.send_text.assert_awaited_once_with(json.dumps(message))
        # ws1 should be disconnected due to exception
        assert manager._get_total_connections() == 1
        assert ws1 not in manager.active_connections["pusat"]

    async def test_broadcast_no_connections(self, manager):
        # Should not raise exception
        await manager.broadcast({"event": "test"}, tenant_slug="pusat")

    async def test_broadcast_message_format(self, manager, mock_websocket):
        await manager.connect(mock_websocket, "pusat")
        message = {"key1": "value1", "key2": 123}
        await manager.broadcast(message, tenant_slug="pusat")
        mock_websocket.send_text.assert_awaited_once_with(json.dumps(message))

    async def test_multiple_connect_disconnect(self, manager):
        ws1, ws2 = AsyncMock(), AsyncMock()
        await manager.connect(ws1, "pusat")
        await manager.connect(ws2, "pusat")
        assert manager._get_total_connections() == 2
        
        manager.disconnect(ws1)
        assert manager._get_total_connections() == 1
        
        ws3 = AsyncMock()
        await manager.connect(ws3, "natuna")
        assert manager._get_total_connections() == 2

    async def test_broadcast_after_partial_disconnect(self, manager):
        ws1, ws2 = AsyncMock(), AsyncMock()
        await manager.connect(ws1, "pusat")
        await manager.connect(ws2, "pusat")
        
        manager.disconnect(ws1)
        
        message = {"event": "test"}
        await manager.broadcast(message, tenant_slug="pusat")
        
        ws1.send_text.assert_not_awaited()
        ws2.send_text.assert_awaited_once_with(json.dumps(message))

    async def test_empty_message_broadcast(self, manager, mock_websocket):
        await manager.connect(mock_websocket, "pusat")
        message = {}
        await manager.broadcast(message, tenant_slug="pusat")
        mock_websocket.send_text.assert_awaited_once_with(json.dumps(message))

    async def test_large_message_broadcast(self, manager, mock_websocket):
        await manager.connect(mock_websocket, "pusat")
        message = {"data": "A" * 10000}
        await manager.broadcast(message, tenant_slug="pusat")
        mock_websocket.send_text.assert_awaited_once_with(json.dumps(message))

    async def test_connection_count(self, manager):
        sockets = [AsyncMock() for _ in range(10)]
        for ws in sockets:
            await manager.connect(ws, "pusat")
        assert manager._get_total_connections() == 10
        
        for ws in sockets[:5]:
            manager.disconnect(ws)
        assert manager._get_total_connections() == 5

    async def test_thread_safety_sequential(self, manager):
        for i in range(100):
            ws = AsyncMock()
            await manager.connect(ws, "pusat")
            if i % 2 == 0:
                manager.disconnect(ws)
        assert manager._get_total_connections() == 50
