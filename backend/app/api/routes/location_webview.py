import logging
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.models.chat_session import ChatSession
from app.engine.chatbot_engine import chatbot_engine
from app.services.reply_dispatcher import ReplyDispatcher

logger = logging.getLogger(__name__)
router = APIRouter()

class WebviewLocationSubmit(BaseModel):
    koordinat_lat: float = Field(..., ge=-90, le=90)
    koordinat_lng: float = Field(..., ge=-180, le=180)
    lokasi_teks: Optional[str] = Field(None, max_length=255)

@router.get("/webview-session/{session_id}")
async def get_webview_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve session details for the location webview map."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")
        
    try:
        extracted_data = json.loads(session.extracted_data) if session.extracted_data else {}
    except Exception:
        extracted_data = {}
        
    return {
        "session_id": session.id,
        "state": session.state,
        "channel": session.channel,
        "koordinat_lat": extracted_data.get("koordinat_lat"),
        "koordinat_lng": extracted_data.get("koordinat_lng"),
        "lokasi_teks": extracted_data.get("lokasi_teks")
    }

@router.post("/webview-session/{session_id}/location")
async def submit_webview_location(
    session_id: int,
    payload: WebviewLocationSubmit,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit coordinates from the map webview.
    Saves incident coordinates, checks victim status, advances the chat state, 
    and sends the next message to the user on Telegram/WhatsApp.
    """
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")
        
    try:
        extracted_data = json.loads(session.extracted_data) if session.extracted_data else {}
    except Exception:
        extracted_data = {}
        
    # 1. Update incident location details
    extracted_data["koordinat_lat"] = payload.koordinat_lat
    extracted_data["koordinat_lng"] = payload.koordinat_lng
    extracted_data["_explicit_koordinat"] = True
    
    if payload.lokasi_teks:
        from app.services.geocoding_service import geocoding_service
        enriched_lokasi = await geocoding_service.enrich_location_with_island(
            payload.koordinat_lat, payload.koordinat_lng, payload.lokasi_teks
        )
        extracted_data["lokasi_teks"] = enriched_lokasi
        
    # 2. Logic: If the reporter is the victim, automatically synchronize reporter_location
    if extracted_data.get("pelapor_hubungan") == "Korban":
        extracted_data["pelapor_lat"] = payload.koordinat_lat
        extracted_data["pelapor_lng"] = payload.koordinat_lng
        extracted_data["is_current_location_shared"] = True
        extracted_data["reporter_location"] = "Sudah terverifikasi (Pelapor adalah Korban)"
        
    session.extracted_data = json.dumps(extracted_data)
    
    # 3. Dynamic routing to get the next state and next question
    # We pass autopilot = True to advance automatically
    route_res = await chatbot_engine._validate_and_route(session, extracted_data, db, autopilot=True)
    next_question = route_res.get("text", "")
    
    # Commit session updates to database
    await db.commit()
    
    # 4. Notify user on Telegram/WhatsApp asynchronously
    dispatch_msg = (
        "📍 *Lokasi kejadian berhasil disimpan melalui Peta Lapor SAR.*\n\n"
        f"{next_question}"
    )
    
    from app.core.tenant_config import get_tenant_settings
    try:
        tenant_settings = await get_tenant_settings(db)
    except Exception as tse:
        logger.error(f"Failed to load tenant settings in location webview: {tse}")
        tenant_settings = None
        
    dispatch_success = True
    if session.channel == "telegram":
        chat_id = session.user_id.replace("tg_", "")
        bot_token = tenant_settings.TELEGRAM_BOT_TOKEN if tenant_settings else None
        dispatch_success = await ReplyDispatcher.send_telegram_reply(chat_id, dispatch_msg, bot_token=bot_token)
    elif session.channel == "whatsapp":
        phone_number = session.user_id.replace("wa_", "")
        wa_token = tenant_settings.WHATSAPP_API_TOKEN if tenant_settings else None
        phone_id = tenant_settings.WHATSAPP_PHONE_NUMBER_ID if tenant_settings else None
        dispatch_success = await ReplyDispatcher.send_whatsapp_reply(
            phone_number, dispatch_msg, wa_token=wa_token, phone_id=phone_id
        )
        
    return {
        "status": "success" if dispatch_success else "partially_failed",
        "message": "Koordinat lokasi berhasil dikirim dan sesi obrolan telah diperbarui",
        "next_state": session.state
    }
