from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from pydantic import BaseModel, ConfigDict
import json
import logging
from datetime import datetime
from collections import defaultdict
import time

from app.db.session import get_db
from app.models.chat_session import ChatSession
from app.services.reply_dispatcher import ReplyDispatcher
from app.engine.chatbot_engine import chatbot_engine
from app.core.websocket import manager
from app.core.security import verify_jwt, verify_admin, verify_operator_or_admin
from app.core.widget_auth import verify_web_chat_access

router = APIRouter()
logger = logging.getLogger(__name__)

# --- IP-based Rate Limiter for Anonymous Web SOS Reports ---
IP_LIMITS = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 10  # requests per window


class ChatSessionResponse(BaseModel):
    id: int
    user_id: str
    channel: str
    state: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    platform_username: Optional[str] = None
    conversation_history: List[Dict[str, Any]]
    extracted_data: Dict[str, Any]
    autopilot: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class SendMessageRequest(BaseModel):
    message: str

class AutopilotToggleRequest(BaseModel):
    autopilot: bool

class WebMessageRequest(BaseModel):
    user_id: str
    message: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None

# --- Helper function to parse database fields ---

def format_session(session: ChatSession) -> ChatSessionResponse:
    try:
        history = json.loads(session.conversation_history) if session.conversation_history else []
    except Exception:
        history = []

    try:
        ext_data = json.loads(session.extracted_data) if session.extracted_data else {}
    except Exception:
        ext_data = {}

    autopilot = ext_data.get("_autopilot", True)

    return ChatSessionResponse(
        id=session.id,
        user_id=session.user_id,
        channel=session.channel,
        state=session.state,
        contact_name=session.contact_name,
        contact_phone=session.contact_phone,
        platform_username=session.platform_username,
        conversation_history=history,
        extracted_data=ext_data,
        autopilot=autopilot,
        created_at=session.created_at,
        updated_at=session.updated_at
    )

# --- API Endpoints ---

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(db: AsyncSession = Depends(get_db), current_user = Depends(verify_operator_or_admin)):
    """Retrieve all active chat sessions sorted by latest activity."""
    result = await db.execute(
        select(ChatSession).order_by(desc(ChatSession.updated_at))
    )
    sessions = result.scalars().all()
    # Include all sessions (including active web sessions) so operators can monitor and takeover
    filtered_sessions = sessions
    return [format_session(s) for s in filtered_sessions]

@router.get("/sessions/web/{user_id}", response_model=Optional[ChatSessionResponse])
async def get_web_chat_session(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    access = Depends(verify_web_chat_access)
):
    """Retrieve a single web chat session by user ID, accessible by the web widget."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.channel == "web"
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    return format_session(session)

@router.post("/sessions/web/message")
async def send_web_message(
    req: WebMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    access = Depends(verify_web_chat_access)
):
    """Simulate a message sent by a web user to test the chatbot engine directly."""
    # IP-based rate limiting for anonymous requests
    auth_header = request.headers.get("authorization")
    is_anonymous = not (auth_header and auth_header.lower().startswith("bearer "))
    
    if is_anonymous:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Clean up older timestamps
        IP_LIMITS[client_ip] = [ts for ts in IP_LIMITS[client_ip] if now - ts < RATE_LIMIT_WINDOW]
        if len(IP_LIMITS[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning(f"Rate limit exceeded for anonymous IP: {client_ip}")
            raise HTTPException(
                status_code=429,
                detail="Terlalu banyak permintaan. Silakan tunggu beberapa saat."
            )
        IP_LIMITS[client_ip].append(now)

    user_profile = {}
    if req.contact_name:
        user_profile["contact_name"] = req.contact_name
    if req.contact_phone:
        user_profile["contact_phone"] = req.contact_phone
        
    # Process message via chatbot engine
    response = await chatbot_engine.process_message(
        user_id=req.user_id,
        message_text=req.message,
        channel="web",
        db=db,
        user_profile=user_profile
    )
    
    # Retrieve updated session
    result = await db.execute(
        select(ChatSession).where(ChatSession.user_id == req.user_id)
    )
    session = result.scalar_one_or_none()
    
    return {
        "status": "success",
        "reply": response.get("text", ""),
        "session": format_session(session) if session else None
    }

@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(session_id: int, db: AsyncSession = Depends(get_db), current_user = Depends(verify_operator_or_admin)):
    """Retrieve a single chat session by ID."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan")
    return format_session(session)

@router.post("/sessions/{session_id}/message")
async def send_operator_message(
    session_id: int,
    req: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(verify_operator_or_admin)
):
    """Send a manual message from the operator/dashboard to a chat session."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan")

    # Update conversation history
    try:
        history = json.loads(session.conversation_history)
    except Exception:
        history = []

    history.append({
        "role": "assistant", 
        "content": req.message,
        "timestamp": datetime.now().isoformat(),
        "sender": "operator"
    })
    session.conversation_history = json.dumps(history)
    
    # Save to db to trigger updated_at
    session.updated_at = datetime.now()
    await db.commit()
    await db.refresh(session)

    # Dispatch to channel if channel is external
    dispatch_success = True
    if session.channel == "telegram":
        chat_id = session.user_id.replace("tg_", "")
        dispatch_success = await ReplyDispatcher.send_telegram_reply(chat_id, req.message)
    elif session.channel == "whatsapp":
        phone_number = session.user_id.replace("wa_", "")
        dispatch_success = await ReplyDispatcher.send_whatsapp_reply(phone_number, req.message)
    elif session.channel == "mobile":
        from app.api.routes.mobile_chat import active_mobile_connections
        ws = active_mobile_connections.get(session.user_id)
        if ws:
            try:
                await ws.send_json({
                    "type": "operator_message",
                    "message": req.message,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as ws_err:
                logger.error(f"Failed to send real-time message to mobile WebSocket: {ws_err}")
                dispatch_success = False
        else:
            # WebSocket not active (app closed)
            dispatch_success = False

    # Broadcast updated session details via WebSocket so dashboard updates instantly
    formatted = format_session(session)
    await manager.broadcast({
        "type": "chat_message",
        "session_id": session.id,
        "user_id": session.user_id,
        "channel": session.channel,
        "state": session.state,
        "contact_name": session.contact_name,
        "contact_phone": session.contact_phone,
        "conversation_history": formatted.conversation_history,
        "extracted_data": formatted.extracted_data,
        "autopilot": formatted.autopilot,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None
    }, db=db)

    return {
        "status": "success" if dispatch_success else "partially_failed",
        "message": "Pesan operator berhasil dikirim dan disinkronkan",
        "session": formatted
    }

@router.put("/sessions/{session_id}/autopilot")
async def toggle_autopilot(
    session_id: int,
    req: AutopilotToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(verify_operator_or_admin)
):
    """Toggle the bot's auto-pilot status (enabled/disabled) for a chat session."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan")

    try:
        ext_data = json.loads(session.extracted_data)
    except Exception:
        ext_data = {}

    # Set the hidden autopilot flag
    ext_data["_autopilot"] = req.autopilot
    session.extracted_data = json.dumps(ext_data)
    
    session.updated_at = datetime.now()
    await db.commit()
    await db.refresh(session)

    formatted = format_session(session)
    
    # Broadcast status change via WebSocket
    await manager.broadcast({
        "type": "chat_message",
        "session_id": session.id,
        "user_id": session.user_id,
        "channel": session.channel,
        "state": session.state,
        "contact_name": session.contact_name,
        "contact_phone": session.contact_phone,
        "conversation_history": formatted.conversation_history,
        "extracted_data": formatted.extracted_data,
        "autopilot": formatted.autopilot,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None
    }, db=db)

    return {
        "status": "success",
        "autopilot": req.autopilot,
        "session": formatted
    }

@router.delete("/sessions/{session_id}", status_code=204, dependencies=[Depends(verify_admin)])
async def delete_chat_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a chat session and clear its history."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan")
        
    try:
        await db.delete(session)
        await db.commit()
        await manager.broadcast({
            "type": "chat_session_deleted",
            "session_id": session_id
        }, db=db)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete chat session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Gagal menghapus sesi chat")


