from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager
from app.api.routes import reports, chat, telegram, whatsapp, auth, settings, knowledge, wa_widget, attachments, stats, identitas, contacts, system, admin, public, national_reports, location_webview, mobile_auth, mobile_chat, hotspots, storage

from app.db.session import master_engine as engine, Base
from app.models import report
from app.models.contact import Contact
from app.models.vector_memory import VectorMemory
from app.services.storage_service import storage_service
from app.core.websocket import manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Security check for default secret key
    from app.core.config import settings as config_settings
    default_dev_keys = (
        "sarbot-dev-secret-key-change-in-production",
        "laporsar-dev-secret-key-change-in-production",
    )
    if config_settings.SECRET_KEY in default_dev_keys:
        logger.warning("=" * 60)
        logger.warning("SECURITY WARNING: Using default SECRET_KEY in production is unsafe!")
        logger.warning("Please set SECRET_KEY to a strong random value via .env immediately.")
        logger.warning("=" * 60)

    # Initialize Master DB schema (creates all operational tables automatically)
    import app.models.master_models
    import app.models.knowledge_models
    import app.models.settings_models
    import app.models.report
    import app.models.contact
    import app.models.chat_session
    import app.models.attachment_model
    import app.models.audit_log

    import asyncio
    from sqlalchemy import text

    # Resilient Database Connection with Retries (waits for Postgres init)
    db_connected = False
    for attempt in range(1, 16):
        try:
            # 1. Safely probe extension availability without opening a transaction
            has_vector = False
            has_postgis = False
            async with engine.connect() as check_conn:
                res_pg = await check_conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'postgis';"))
                if res_pg.scalar():
                    has_postgis = True
                res_vec = await check_conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector';"))
                if res_vec.scalar():
                    has_vector = True

            from app.db.session import set_vector_extension_available
            set_vector_extension_available(has_vector)

            # 2. If vector extension is absent, fallback embedding columns to TEXT
            if not has_vector:
                from app.models.knowledge_models import DictionaryWord
                from app.models.vector_memory import VectorMemory
                from sqlalchemy import Text
                if "embedding" in DictionaryWord.__table__.columns:
                    DictionaryWord.__table__.columns["embedding"].type = Text()
                if "embedding" in VectorMemory.__table__.columns:
                    VectorMemory.__table__.columns["embedding"].type = Text()

            # 3. Create extensions and tables in transaction
            async with engine.begin() as conn:
                if has_postgis:
                    try:
                        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                    except Exception as e:
                        logger.warning(f"PostGIS extension note: {e}")

                if has_vector:
                    try:
                        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                        logger.info("Vector extension enabled successfully in PostgreSQL.")
                    except Exception as e:
                        logger.warning(f"Vector extension note: {e}")

                # Create all tables (vector_memory will use Vector if has_vector, else Text)
                await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn))

            db_connected = True
            logger.info("Database connection and schema initialization successful.")
            break
        except Exception as e:
            logger.warning(f"Database not ready yet (attempt {attempt}/15): {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2)

    if not db_connected:
        logger.error("Failed to connect to PostgreSQL after 15 attempts. Exiting startup.")
        raise RuntimeError("PostgreSQL database unavailable")

    # Ensure Master Default Tenant 'pusat' exists
    try:
        from app.db.session import SessionLocal
        from sqlalchemy.future import select
        from app.models.master_models import Tenant
        from app.db.provision_tenant import provision_tenant_db

        async with SessionLocal() as db_master:
            res = await db_master.execute(select(Tenant).where(Tenant.slug == "pusat"))
            pusat_tenant = res.scalar_one_or_none()
            admin_user = getattr(config_settings, "DEV_ADMIN_USERNAME", "admin") or "admin"
            admin_pwd = getattr(config_settings, "DEV_ADMIN_PASSWORD", "admin") or "admin"

            if not pusat_tenant:
                base_db_url = config_settings.DATABASE_URL
                pusat_tenant = Tenant(
                    name="Basarnas Pusat Command Center",
                    slug="pusat",
                    db_url=base_db_url,
                    s3_bucket="laporsar-attachments",
                    is_active=True,
                    admin_name="Admin Pusat BASARNAS",
                    admin_email=admin_user
                )
                db_master.add(pusat_tenant)
                await db_master.commit()
                await db_master.refresh(pusat_tenant)
                logger.info("Master Tenant 'pusat' seeded successfully")

            # Provision pusat tenant (ensures operational schema, dictionary, classifications, and admin user)
            try:
                await provision_tenant_db(pusat_tenant, admin_password=admin_pwd, db_master=db_master)
            except Exception as prov_err:
                logger.warning(f"Auto-provision note for tenant 'pusat': {prov_err}")
    except Exception as e:
        logger.error(f"Failed to seed/provision Master Tenant pusat: {e}")

    # Seed Master Dictionary Words
    try:
        from app.db.seed_dictionary import seed_default_dictionary
        from app.db.session import SessionLocal
        async with SessionLocal() as db_master:
            await seed_default_dictionary(db_master)
        logger.info("Master Dictionary seeded successfully")
    except Exception as e:
        logger.error(f"Failed to seed Master Dictionary: {e}")

    # Pre-warm RuleExtractor and AutoCorrectService caches
    try:
        from app.services.rule_extractor import RuleExtractor
        from app.services.autocorrect_service import AutoCorrectService
        from app.db.session import SessionLocal
        async with SessionLocal() as db:
            # Add tenant_slug="pusat" to session info for pre-warming fallback
            db.info["tenant_slug"] = "pusat"
            await RuleExtractor.load_cache(db)
            await AutoCorrectService.load_cache(db)
        logger.info("RuleExtractor and AutoCorrectService caches pre-warmed successfully")
    except Exception as e:
        logger.error(f"Dictionary caches pre-warming failed: {e}")
    
    # Ensure temp_audio directory exists for voice message processing
    # Try relative to the backend directory (when running from backend/)
    alt_temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_audio")
    os.makedirs(alt_temp_dir, exist_ok=True)

    # Initialize MinIO storage service (creates buckets)
    try:
        await storage_service.initialize()
        logger.info("MinIO storage service initialized")
    except Exception as e:
        logger.warning(f"MinIO storage service init failed (non-fatal): {e}")
    
    # Start background job scheduler
    try:
        from app.services.scheduler_service import start_scheduler, shutdown_scheduler
        start_scheduler()
    except Exception as e:
        logger.error(f"Failed to start background scheduler: {e}")

    logger.info("Lapor SAR Lite started — AI Cloud & Storage Engine ready")
    yield
    # Graceful Shutdown logic for Zero-Downtime rollouts
    try:
        shutdown_scheduler()
    except Exception as e:
        logger.error(f"Failed to shutdown background scheduler: {e}")

    try:
        await manager.graceful_disconnect_all(reason="Server restarting for update")
    except Exception as e:
        logger.error(f"Failed to gracefully disconnect WebSockets: {e}")

    try:
        from app.db.session import tenant_engines
        for t_eng in list(tenant_engines.values()):
            try:
                await t_eng.dispose()
            except Exception:
                pass
        await engine.dispose()
        logger.info("Database connection pools disposed successfully.")
    except Exception as e:
        logger.error(f"Failed to dispose database engines: {e}")

app = FastAPI(
    title="Lapor SAR API",
    description="Backend API for Lapor SAR Emergency Reporting & AI Processing Platform",
    version="3.1.0-lite",
    lifespan=lifespan,
    redirect_slashes=False
)

from app.core.config import settings as config_settings

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
import jwt

# Configure CORS — restrict to known frontend origins
_allowed_origins = [
    config_settings.FRONTEND_URL,           # e.g. http://laporsar.lan
    "http://localhost:3000",                # Next.js dev server
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
    "http://laporsar.lan",
    "https://laporsar.lan",
    "http://192.168.70.20",
    "https://192.168.70.20",
]

# Support subdomains dynamically on localhost, LAN, IP, and production frontend URL
import re
frontend_url = config_settings.FRONTEND_URL.rstrip('/')
_origin_regexes = [
    r"https?://([a-zA-Z0-9-]+\.)*localhost(:[0-9]+)?",
    r"https?://([a-zA-Z0-9-]+\.)*127\.0\.0\.1(:[0-9]+)?",
    r"https?://([a-zA-Z0-9-]+\.)*laporsar\.lan(:[0-9]+)?",
    r"https?://([a-zA-Z0-9-]+\.)*laporsar\.basarnas\.go\.id(:[0-9]+)?",
    r"https?://192\.168\.70\.20(:[0-9]+)?",
    r"https?://([a-zA-Z0-9-]+\.)*trycloudflare\.com",
]

match = re.match(r'(https?://)(.*)', frontend_url)
if match:
    protocol, domain = match.groups()
    escaped_domain = re.escape(domain)
    _origin_regexes.append(f"{protocol}([a-zA-Z0-9-]+\\.)*{escaped_domain}(:[0-9]+)?")

allow_origin_regex = "^(" + "|".join(_origin_regexes) + ")$"

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(self), microphone=(self), camera=()")
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(mobile_auth.router, prefix="/api/auth/mobile", tags=["Mobile App Authentication"])
app.include_router(mobile_chat.router, prefix="/api/chat/mobile", tags=["Mobile App Chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["Super Admin"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat Webhook"])
app.include_router(telegram.router, prefix="/api/telegram", tags=["Telegram Webhook"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp Webhook"])
app.include_router(wa_widget.router, prefix="/api/wa-widget", tags=["WhatsApp Widget"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(identitas.router, prefix="/api/settings", tags=["Identitas & Wilayah"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge Base"])
app.include_router(attachments.router, prefix="/api/attachments", tags=["Attachments"])
app.include_router(stats.router, prefix="/api/stats", tags=["Dashboard Stats"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["Contacts"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(public.router, prefix="/api/public", tags=["Public API"])
app.include_router(location_webview.router, prefix="/api/public", tags=["Location Webview"])
app.include_router(national_reports.router, prefix="/api", tags=["National Dashboard & Monitoring"])
app.include_router(hotspots.router, prefix="/api/hotspots", tags=["Spatial Hotspots"])
app.include_router(storage.router, prefix="/api/storage", tags=["Storage Manager"])
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response, FileResponse

class SecureStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        if isinstance(response, FileResponse):
            filename = response.path.lower()
            if filename.endswith(('.html', '.htm', '.svg', '.xml')):
                response.headers["Content-Disposition"] = f"attachment; filename={os.path.basename(response.path)}"
                response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox;"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

# Ensure uploads directory exists
os.makedirs("uploads/maps", exist_ok=True)
app.mount("/uploads", SecureStaticFiles(directory="uploads"), name="uploads")

@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": "3.1.0-lite",
        "storage": "available" if storage_service.is_available() else "unavailable",
    }

@app.get("/api/v1/system/info")
@app.get("/api/system/info")
async def system_info():
    """System info endpoint for monitoring."""
    from app.db.session import SessionLocal
    from sqlalchemy.future import select
    from app.models.master_models import Tenant
    tenants_list = ["pusat"]
    try:
        async with SessionLocal() as db_master:
            res = await db_master.execute(select(Tenant.slug).where(Tenant.is_active == True))
            slugs = res.scalars().all()
            if slugs:
                tenants_list = list(slugs)
    except Exception:
        pass

    return {
        "project": "Lapor SAR Lite",
        "version": "3.1.0-lite",
        "status": "operational",
        "ai_engine": "cloud_multi_provider",
        "storage": "available" if storage_service.is_available() else "unavailable",
        "tenants": tenants_list
    }

@app.get("/health/live")
@app.get("/api/health/live")
async def liveness_check():
    """Kubernetes/Docker liveness probe to verify server process is up."""
    return {"status": "alive", "version": "3.1.0-lite"}

async def check_redis_health() -> bool:
    """Helper to check Redis connectivity for readiness probes."""
    from app.db.session import REDIS_URL
    import redis.asyncio as aioredis
    client = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2.0)
    try:
        await client.ping()
        return True
    finally:
        await client.aclose()

@app.get("/health/ready")
@app.get("/api/health/ready")
async def readiness_check():
    """
    Deep readiness check for load balancers (Nginx / Cloud LB) before traffic routing.
    Verifies PostgreSQL Master DB connectivity and Redis connectivity.
    Returns HTTP 200 if ready to serve, or HTTP 503 Service Unavailable if degraded.
    """
    readiness = {
        "status": "ready",
        "version": "3.0.0",
        "checks": {
            "database": "unknown",
            "redis": "unknown",
            "storage": "available" if storage_service.is_available() else "unavailable"
        },
        "latency_ms": {}
    }
    all_healthy = True

    # 1. Check PostgreSQL Master DB
    t0 = time.perf_counter()
    try:
        from sqlalchemy import text
        from app.db.session import SessionLocal
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        readiness["checks"]["database"] = "healthy"
        readiness["latency_ms"]["database"] = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        readiness["checks"]["database"] = f"unhealthy: {str(e)}"
        all_healthy = False

    # 2. Check Redis
    t0 = time.perf_counter()
    try:
        await check_redis_health()
        readiness["checks"]["redis"] = "healthy"
        readiness["latency_ms"]["redis"] = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        readiness["checks"]["redis"] = f"unhealthy: {str(e)}"
        all_healthy = False

    if not all_healthy:
        readiness["status"] = "degraded"
        return JSONResponse(status_code=503, content=readiness)

    return readiness

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    is_authenticated = False
    token_tenant_slug = None
    if token:
        try:
            payload = jwt.decode(token, config_settings.SECRET_KEY, algorithms=[config_settings.ALGORITHM])
            is_authenticated = True
            token_tenant_slug = payload.get("tenant_slug")
        except jwt.PyJWTError:
            pass

    if not is_authenticated and config_settings.DEV_ADMIN_ENABLED:
        is_authenticated = True

    if not is_authenticated:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
        return

    # Resolve tenant scope
    tenant_slug = token_tenant_slug
    if not tenant_slug:
        tenant_slug = (
            websocket.query_params.get("tenant") or 
            websocket.query_params.get("tenant_slug") or 
            websocket.headers.get("x-tenant-slug") or 
            websocket.headers.get("X-Tenant-Slug") or
            "global"
        )

    await manager.connect(websocket, tenant_slug)
    try:
        while True:
            # Keep the connection open and listen for disconnects
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
