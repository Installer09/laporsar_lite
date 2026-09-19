import logging
import json
from datetime import datetime
import jwt
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_master_db, get_tenant_sessionmaker
from app.models.master_models import Tenant
from app.models.chat_session import ChatSession
from app.models.contact import Contact
from app.models.report import Report
from app.core.security import verify_jwt
from app.engine.chatbot_engine import chatbot_engine
from app.core.config import settings as global_settings
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(redirect_slashes=False)

# Global dictionary to store active private mobile WebSockets: user_id -> WebSocket
active_mobile_connections = {}

# Dependency to check that the JWT belongs to a mobile reporter
async def verify_reporter(payload: dict = Depends(verify_jwt)) -> dict:
    if payload.get("role") != "reporter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak: Hanya diperbolehkan untuk Pelapor Mobile."
        )
    return payload

# Helper to get the pusat tenant database session
async def get_pusat_db(db_master: AsyncSession = Depends(get_master_db)) -> AsyncSession:
    result = await db_master.execute(
        select(Tenant).where(Tenant.slug == "pusat", Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=500,
            detail="Tenant 'pusat' tidak ditemukan atau tidak aktif."
        )
    session_maker = get_tenant_sessionmaker(tenant.db_url)
    async with session_maker() as session:
        session.info["tenant_slug"] = "pusat"
        yield session

class MobileMessageRequest(BaseModel):
    message: str

@router.get("/session")
async def get_mobile_session(
    db_pusat: AsyncSession = Depends(get_pusat_db),
    reporter: dict = Depends(verify_reporter)
):
    """
    Get or create the active chat session for the verified mobile reporter.
    """
    contact_id = reporter.get("contact_id")
    user_id = f"mobile_{contact_id}"
    
    # Retrieve contact details
    contact_res = await db_pusat.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = contact_res.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Profil kontak tidak ditemukan")

    session = await chatbot_engine.get_or_create_session(
        user_id=user_id,
        channel="mobile",
        db=db_pusat
    )
    
    # Ensure name and phone are populated
    session.contact_name = contact.name
    session.contact_phone = contact.phone_number
    await db_pusat.commit()

    try:
        history = json.loads(session.conversation_history) if session.conversation_history else []
    except Exception:
        history = []

    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "state": session.state,
        "contact_name": session.contact_name,
        "contact_phone": session.contact_phone,
        "conversation_history": history
    }

@router.post("/message")
async def send_mobile_message(
    req: MobileMessageRequest,
    db_pusat: AsyncSession = Depends(get_pusat_db),
    reporter: dict = Depends(verify_reporter)
):
    """
    Send a message from the mobile app to the chatbot engine.
    """
    contact_id = reporter.get("contact_id")
    user_id = f"mobile_{contact_id}"

    # Retrieve contact details
    contact_res = await db_pusat.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = contact_res.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Profil kontak tidak ditemukan")

    user_profile = {
        "contact_name": contact.name,
        "contact_phone": contact.phone_number
    }

    # Process message via chatbot engine
    response = await chatbot_engine.process_message(
        user_id=user_id,
        message_text=req.message,
        channel="mobile",
        db=db_pusat,
        user_profile=user_profile
    )

    # Retrieve updated session
    session_res = await db_pusat.execute(
        select(ChatSession).where(ChatSession.user_id == user_id)
    )
    session = session_res.scalar_one_or_none()
    
    try:
        history = json.loads(session.conversation_history) if session and session.conversation_history else []
    except Exception:
        history = []

    return {
        "status": "success",
        "reply": response.get("text", "") if response else "",
        "history": history
    }

@router.get("/reports")
async def get_mobile_reports(
    db_pusat: AsyncSession = Depends(get_pusat_db),
    reporter: dict = Depends(verify_reporter)
):
    """
    Get all reports submitted by the mobile reporter.
    """
    contact_id = reporter.get("contact_id")
    contact_res = await db_pusat.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = contact_res.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Profil kontak tidak ditemukan")
        
    reports_res = await db_pusat.execute(
        select(Report).where(Report.pelapor_nomor == contact.phone_number).order_by(Report.id.desc())
    )
    reports = reports_res.scalars().all()
    
    return [
        {
            "id": r.id,
            "no_laporan": r.no_laporan,
            "jenis_kejadian": r.jenis_kejadian,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "lokasi_teks": r.lokasi_teks,
            "pos_sar_terdekat": r.pos_sar_terdekat
        }
        for r in reports
    ]

@router.websocket("/ws")
async def mobile_websocket_endpoint(websocket: WebSocket, token: str = None):
    """
    Secure isolated WebSocket for mobile users to receive real-time updates.
    """
    if not token:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token required")
        return

    try:
        payload = jwt.decode(token, global_settings.SECRET_KEY, algorithms=[global_settings.ALGORITHM])
        if payload.get("role") != "reporter":
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized role")
            return
        user_id = f"mobile_{payload.get('contact_id')}"
    except Exception:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    await websocket.accept()
    active_mobile_connections[user_id] = websocket
    logger.info(f"Mobile WebSocket client connected for user {user_id}")

    try:
        while True:
            # Maintain connection; listen for client messages / pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        if user_id in active_mobile_connections:
            del active_mobile_connections[user_id]
        logger.info(f"Mobile WebSocket client disconnected for user {user_id}")
