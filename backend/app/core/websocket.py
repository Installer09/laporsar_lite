import logging
from typing import List, Dict, Any
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Dictionary mapping tenant_slug -> list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, tenant_slug: str):
        await websocket.accept()
        # Attach tenant_slug to the websocket instance for disconnect identification
        websocket.tenant_slug = tenant_slug
        if tenant_slug not in self.active_connections:
            self.active_connections[tenant_slug] = []
        self.active_connections[tenant_slug].append(websocket)
        logger.info(f"WebSocket Client connected for tenant '{tenant_slug}'. Total connections: {self._get_total_connections()}")

    def disconnect(self, websocket: WebSocket):
        tenant_slug = getattr(websocket, "tenant_slug", "global")
        if tenant_slug in self.active_connections:
            if websocket in self.active_connections[tenant_slug]:
                self.active_connections[tenant_slug].remove(websocket)
                if not self.active_connections[tenant_slug]:
                    del self.active_connections[tenant_slug]
        logger.info(f"WebSocket Client disconnected for tenant '{tenant_slug}'. Total connections: {self._get_total_connections()}")

    async def broadcast(self, message: Dict[str, Any], db: Any = None, tenant_slug: str = None):
        """
        Broadcast updates strictly to clients of the same tenant.
        Resolves tenant_slug from database session if passed.
        """
        if not tenant_slug and db is not None:
            try:
                tenant_slug = db.info.get("tenant_slug")
            except Exception:
                pass
                
        if not tenant_slug:
            tenant_slug = "global"

        message_str = json.dumps(message)
        disconnected = []
        
        # Enforce tenant isolation: get clients of the matching tenant
        tenant_clients = self.active_connections.get(tenant_slug, [])
        # Also broadcast to global/dev-admin clients if any
        global_clients = self.active_connections.get("global", [])
        
        # Combine lists and remove duplicates
        target_clients = list(set(tenant_clients + global_clients))
        
        for connection in target_clients:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Error sending message to websocket: {e}")
                disconnected.append(connection)
        
        # Clean up dead connections
        for conn in disconnected:
            self.disconnect(conn)

    def _get_total_connections(self) -> int:
        return sum(len(v) for v in self.active_connections.values())

    async def graceful_disconnect_all(self, reason: str = "Server restarting for update"):
        """
        Gracefully notify all active WebSocket connections before server shutdown
        and close them with status code 1001 (Going Away) to encourage client reconnect.
        """
        all_connections = []
        for conns in list(self.active_connections.values()):
            all_connections.extend(conns)

        if not all_connections:
            return

        reload_notice = json.dumps({
            "type": "server_shutdown",
            "message": reason,
            "status": "reconnecting",
            "retry_delay_ms": 2000
        })

        for conn in all_connections:
            try:
                await conn.send_text(reload_notice)
                await conn.close(code=1001, reason=reason)
            except Exception as e:
                logger.debug(f"Error during graceful websocket disconnect: {e}")
        self.active_connections.clear()
        logger.info(f"Gracefully disconnected {len(all_connections)} WebSocket connections.")

manager = ConnectionManager()

