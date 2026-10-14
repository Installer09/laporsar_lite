import logging
import httpx
import json
import os
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, get_tenant
from app.core.config import settings
from app.core.security import verify_admin
from app.models.master_models import Tenant
from app.engine.chatbot_engine import chatbot_engine
from app.services.reply_dispatcher import reply_dispatcher
from app.services.telegram_calendar import (
    create_calendar, 
    WEEKDAYS_FULL, 
    MONTH_NAMES_ID
)

router = APIRouter()
logger = logging.getLogger(__name__)

async def answer_callback_query(callback_query_id: str, token: str, text: str = None) -> bool:
    """Notify Telegram that callback was processed to stop loading spinner on the button."""
    if not token:
        return False
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json=payload
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Failed to answer callback query: {e}")
        return False

async def edit_message_reply_markup(chat_id: str, message_id: int, token: str, inline_keyboard: list = None) -> bool:
    """Edit the inline keyboard of an existing message in place."""
    if not token:
        return False
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": inline_keyboard} if inline_keyboard else {"inline_keyboard": []}
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/editMessageReplyMarkup",
                json=payload
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Failed to edit message reply markup: {e}")
        return False

async def edit_message_text(chat_id: str, message_id: int, text: str, token: str, inline_keyboard: list = None) -> bool:
    """Edit the text and inline keyboard of an existing message."""
    if not token:
        return False
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if inline_keyboard:
        payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/editMessageText",
                json=payload
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Failed to edit message text: {e}")
        return False

# In-memory fallback cache for Telegram update IDs to prevent concurrent processing of retries.
import asyncio
import redis.asyncio as aioredis

processed_update_ids = set()
update_id_lock = asyncio.Lock()

async def is_duplicate_update(update_id: int) -> bool:
    """Check if the update_id has already been processed or is being processed."""
    try:
        if settings.REDIS_URL:
            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            async with redis_client:
                success = await redis_client.set(f"tg_update:{update_id}", "1", ex=300, nx=True)
                if success is not None:
                    return True if not success else False
                else:
                    return True
    except Exception as e:
        logger.warning(f"Redis deduplication check failed: {e}. Falling back to in-memory cache.")

    async with update_id_lock:
        if update_id in processed_update_ids:
            return True
        processed_update_ids.add(update_id)
        if len(processed_update_ids) > 1000:
            lst = list(processed_update_ids)
            processed_update_ids.clear()
            processed_update_ids.update(lst[200:])
        return False

from app.core.tenant_config import get_tenant_settings
from app.models.master_models import Tenant

async def process_telegram_background(tenant_slug: str, db_url: str, s3_bucket: str, token: str, data: dict):
    from app.db.session import get_tenant_sessionmaker
    from app.services.transcription import transcription_service
    from app.services.storage_service import storage_service
    from app.models.attachment_model import Attachment
    from app.services.telegram_calendar import create_calendar
    from app.engine.chatbot_engine import chatbot_engine
    from app.services.reply_dispatcher import reply_dispatcher
    from app.models.report import ReportStatus

    session_maker = get_tenant_sessionmaker(db_url)
    async with session_maker() as db:
        db.info["tenant_slug"] = tenant_slug
        try:
            # 1. Check if update contains callback_query (inline buttons)
            if "callback_query" in data:
                cb = data["callback_query"]
                cb_id = cb["id"]
                chat_id = str(cb["message"]["chat"]["id"])
                message_id = cb["message"]["message_id"]
                cb_data = cb.get("data", "")
                
                logger.info(f"Received Telegram Callback: {cb_data} from chat {chat_id}")
                
                # Answer callback query to stop loading spinner
                await answer_callback_query(cb_id, token=token)
                
                if cb_data == "calendar_ignore":
                    return
                    
                if cb_data == "calendar_cancel":
                    await edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ *Pilihan kalender dibatalkan.*\n\nAnda dapat mengetikkan perkiraan waktu kejadian secara manual (contoh: _Pukul 08.00 WIB_, _tadi pagi_, _10 menit yang lalu_).",
                        token=token
                    )
                    return
                    
                if cb_data.startswith("calendar_week_prev:") or cb_data.startswith("calendar_week_next:"):
                    nav_target = cb_data.split(":")[1]
                    kb = create_calendar(nav_target)
                    await edit_message_reply_markup(chat_id, message_id, token=token, inline_keyboard=kb)
                    return
                    
                if cb_data.startswith("calendar_date:"):
                    date_str = cb_data.split(":")[1]
                    
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                        day_name = WEEKDAYS_FULL[dt.weekday()]
                        month_name = MONTH_NAMES_ID[dt.month]
                        formatted_date = f"{day_name}, {dt.day} {month_name} {dt.year}"
                    except Exception:
                        formatted_date = date_str
                    
                    session = await chatbot_engine.get_or_create_session(f"tg_{chat_id}", "telegram", db)
                    try:
                        ext_data = json.loads(session.extracted_data)
                    except Exception:
                        ext_data = {}
                    ext_data["_temp_date"] = date_str
                    session.extracted_data = json.dumps(ext_data)
                    await db.commit()
                    
                    prompt_text = (
                        f"📅 *Tanggal Kejadian Terpilih:* {formatted_date}\n\n"
                        f"⏰ *Pukul berapa kejadian tersebut berlangsung?*\n"
                        f"Silakan ketik perkiraan jam kejadian secara bebas (contoh: _Pukul 08.00 WIB_, _1 jam yang lalu_, _tadi pagi_, _semalam_)."
                    )
                    await edit_message_text(chat_id, message_id, text=prompt_text, token=token)
                    return
     
            # 2. Check if update contains a regular chat message
            if "message" in data:
                message = data["message"]
                chat_id = str(message["chat"]["id"])

                # Check if message originated from a Telegram Group / Supergroup
                from app.services.group_listener_service import group_listener_service
                if group_listener_service.is_group_chat(message):
                    logger.info(f"Received message from Telegram Group {chat_id}, routing to GroupListenerService")
                    await group_listener_service.process_telegram_group_message(message, token=token, db=db)
                    return

                text = message.get("text", "")
                is_voice = False
                
                # Check if Telegram user shared voice note or audio
                if "voice" in message or "audio" in message:
                    audio_obj = message.get("voice") or message.get("audio")
                    file_id = audio_obj.get("file_id")
                    if file_id:
                        try:
                            if token:
                                async with httpx.AsyncClient(timeout=5.0) as client:
                                    await client.post(
                                        f"https://api.telegram.org/bot{token}/sendChatAction",
                                        json={"chat_id": chat_id, "action": "typing"}
                                    )
                        except Exception:
                            pass
                            
                        local_path = await transcription_service.download_telegram_voice(file_id, bot_token=token)
                        if local_path == "size_limit_exceeded":
                            await reply_dispatcher.send_telegram_reply(
                                chat_id=chat_id,
                                text="⚠️ *Rekaman Suara Terlalu Besar*\n\nUkuran rekaman suara Anda melebihi batas maksimum 15MB.",
                                bot_token=token
                            )
                            return
                        if local_path:
                            transcribed_text = await transcription_service.transcribe_audio(local_path)
                            if transcribed_text and transcribed_text.strip():
                                logger.info(f"Telegram voice transcribed successfully: '{transcribed_text}'")
                                text = transcribed_text
                                is_voice = True
                            else:
                                logger.warning("Telegram voice transcription returned empty result.")
                                await reply_dispatcher.send_telegram_reply(
                                    chat_id=chat_id,
                                    text="⚠️ *Pesan Suara Kurang Jelas*\n\nSistem kami tidak dapat mendeteksi ucapan pada rekaman suara Anda dengan jelas. Silakan kirim pesan suara baru atau ketik pesan Anda secara manual.",
                                    bot_token=token
                                )
                                return
                        else:
                            logger.error("Failed to download Telegram voice note.")
                            await reply_dispatcher.send_telegram_reply(
                                chat_id=chat_id,
                                text="⚠️ *Koneksi Bermasalah*\n\nGagal mengunduh rekaman suara Anda. Silakan kirim ulang pesan suara atau ketik pesan secara manual.",
                                bot_token=token
                            )
                            return
                
                # Check if Telegram user shared photo, document, or video
                elif "photo" in message or "document" in message or "video" in message:
                    file_id = None
                    file_size = None
                    file_type = "document"
                    mime_type = "application/octet-stream"
                    original_filename = "attachment"
                    
                    if "photo" in message:
                        photo_sizes = message.get("photo")
                        if photo_sizes:
                            largest = photo_sizes[-1]
                            file_id = largest.get("file_id")
                            file_size = largest.get("file_size")
                            file_type = "photo"
                            mime_type = "image/jpeg"
                            original_filename = f"photo_{file_id}.jpg"
                    elif "document" in message:
                        doc = message.get("document")
                        file_id = doc.get("file_id")
                        file_size = doc.get("file_size")
                        mime_type = doc.get("mime_type", "application/octet-stream")
                        original_filename = doc.get("file_name", f"doc_{file_id}")
                        if mime_type.startswith("image/"):
                            file_type = "photo"
                        elif mime_type.startswith("video/"):
                            file_type = "video"
                        elif mime_type.startswith("audio/"):
                            file_type = "audio"
                        else:
                            file_type = "document"
                    elif "video" in message:
                        vid = message.get("video")
                        file_id = vid.get("file_id")
                        file_size = vid.get("file_size")
                        mime_type = vid.get("mime_type", "video/mp4")
                        original_filename = f"video_{file_id}.mp4"
                        file_type = "video"
     
                    if file_id:
                        if file_size and file_size > 15 * 1024 * 1024:
                            await reply_dispatcher.send_telegram_reply(
                                chat_id=chat_id,
                                text="⚠️ *Berkas Terlalu Besar*\n\nUkuran berkas Anda melebihi batas maksimum 15MB. Silakan kirim berkas dengan ukuran yang lebih kecil.",
                                bot_token=token
                            )
                            return

                        try:
                            if token:
                                async with httpx.AsyncClient(timeout=5.0) as client:
                                    await client.post(
                                        f"https://api.telegram.org/bot{token}/sendChatAction",
                                        json={"chat_id": chat_id, "action": "upload_document"}
                                    )
                        except Exception:
                            pass
     
                        ext = os.path.splitext(original_filename)[1] or ".ogg"
                        local_path = await transcription_service.download_telegram_voice(file_id, bot_token=token, ext=ext)
                        if local_path == "size_limit_exceeded":
                            await reply_dispatcher.send_telegram_reply(
                                chat_id=chat_id,
                                text="⚠️ *Berkas Terlalu Besar*\n\nUkuran berkas Anda melebihi batas maksimum 15MB. Silakan kirim berkas dengan ukuran yang lebih kecil.",
                                bot_token=token
                            )
                            return
                        if local_path and os.path.exists(local_path):
                            try:
                                with open(local_path, "rb") as f:
                                    file_bytes = f.read()
                                
                                try:
                                    os.remove(local_path)
                                except Exception:
                                    pass
     
                                bucket_name = s3_bucket or settings.MINIO_BUCKET_ATTACHMENTS
                                file_key = await storage_service.upload_file(
                                    file_data=file_bytes,
                                    original_filename=original_filename,
                                    mime_type=mime_type,
                                    file_type=file_type,
                                    user_id=f"tg_{chat_id}",
                                    channel="telegram",
                                    bucket_name=bucket_name,
                                    tenant_slug=tenant_slug
                                )
                                
                                if file_key:
                                    new_attachment = Attachment(
                                        user_id=f"tg_{chat_id}",
                                        channel="telegram",
                                        file_key=file_key,
                                        bucket=bucket_name,
                                        original_filename=original_filename,
                                        mime_type=mime_type,
                                        file_size=file_size or len(file_bytes),
                                        file_type=file_type
                                    )
                                    try:
                                        db.add(new_attachment)
                                        await db.commit()
                                    except Exception as db_err:
                                        await db.rollback()
                                        logger.error(f"Failed to save Telegram attachment to DB: {db_err}")
                                        raise
                                    logger.info(f"Successfully processed and saved Telegram attachment {original_filename} to MinIO bucket {bucket_name}.")
                                    
                                    text = "Ada Dokumen/Foto Terlampir"
                                else:
                                    logger.error("Failed to upload attachment to MinIO.")
                                    text = "Ada Dokumen/Foto Terlampir (Upload Gagal)"
                            except Exception as attach_err:
                                logger.error(f"Error saving attachment: {attach_err}")
                                text = "Ada Dokumen/Foto Terlampir (Simpan Gagal)"
                        else:
                            logger.error("Failed to download Telegram attachment.")
                            text = "Ada Dokumen/Foto Terlampir (Download Gagal)"
                
                # Check if Telegram user shared location
                elif "location" in message:
                    lat = message["location"]["latitude"]
                    lng = message["location"]["longitude"]
                    text = f"Lokasi GPS: {lat}, {lng}"
                
                # Handle user details
                username = message["chat"].get("username", "")
                first_name = message["chat"].get("first_name", "")
                last_name = message["chat"].get("last_name", "")
                
                contact_name = f"{first_name or ''} {last_name or ''}".strip()
                if not contact_name:
                    contact_name = username or f"Telegram User {chat_id}"
                    
                user_profile = {
                    "contact_name": contact_name,
                    "platform_username": f"@{username}" if username else None
                }
                
                # Process incoming message via centralized chatbot engine
                response = await chatbot_engine.process_message(
                    user_id=f"tg_{chat_id}",
                    message_text=text,
                    channel="telegram",
                    db=db,
                    user_profile=user_profile
                )
                
                # Prepend transcription feedback to the response text if it was a voice message
                if is_voice and response and "text" in response:
                    response["text"] = f"🗣️ *[Transkripsi Voice Note]:*\n_\"{text}\"_\n\n{response['text']}"
                
                # Dispatch the reply back to Telegram
                if response and "text" in response:
                    session = await chatbot_engine.get_or_create_session(f"tg_{chat_id}", "telegram", db)
                    if session.state == "AWAITING_WAKTU":
                        try:
                            ext_data = json.loads(session.extracted_data) if session.extracted_data else {}
                        except Exception:
                            ext_data = {}
                        
                        if not ext_data.get("_temp_date"):
                            inline_kb = create_calendar()
                            await reply_dispatcher.send_telegram_reply(
                                chat_id=chat_id,
                                text=response["text"],
                                inline_keyboard=inline_kb,
                                bot_token=token
                            )
                        else:
                            await reply_dispatcher.send_telegram_reply(
                                chat_id=chat_id,
                                text=response["text"],
                                buttons=[],
                                bot_token=token
                            )
                    else:
                        await reply_dispatcher.send_telegram_reply(
                            chat_id=chat_id,
                            text=response["text"],
                            buttons=response.get("buttons"),
                            bot_token=token
                        )
        except Exception as e:
            logger.error(f"Error processing Telegram message in background: {e}", exc_info=True)

@router.post("/webhook")
@router.post("/webhook/")
@router.post("/webhook/{tenant_slug}")
@router.post("/webhook/{tenant_slug}/")
async def telegram_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    tenant_slug: str = "pusat",
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-API-Secret-Token"),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant)
):
    """
    Webhook endpoint for receiving messages and callback queries from Telegram Bot API.
    Verifies dynamic token and offloads heavy work to background tasks.
    """
    try:
        # Load dynamic tenant settings
        tenant_settings = await get_tenant_settings(db)
        token = tenant_settings.TELEGRAM_BOT_TOKEN
        
        # Verify secret token if configured
        secret_token = tenant_settings.TELEGRAM_SECRET_TOKEN
        if secret_token:
            if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != secret_token:
                logger.warning(f"Telegram webhook token verification failed for tenant {tenant_slug}: Secret token mismatch or missing")
                raise HTTPException(status_code=403, detail="Forbidden: Secret token mismatch")
                
            logger.info(f"Telegram webhook token verified successfully for tenant {tenant_slug}")

        data = await request.json()
        
        # Deduplication check using update_id
        update_id = data.get("update_id")
        if update_id is not None:
            if await is_duplicate_update(update_id):
                logger.info(f"Duplicate Telegram Update ID {update_id} ignored.")
                return {"status": "ok", "detail": "duplicate ignored"}
        
        logger.info(f"Received Telegram Webhook for tenant {tenant_slug} - queueing background task")
        
        # Queue the background task
        background_tasks.add_task(
            process_telegram_background,
            tenant_slug=tenant_slug,
            db_url=tenant.db_url,
            s3_bucket=tenant.s3_bucket,
            token=token,
            data=data
        )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling Telegram webhook: {e}", exc_info=True)
        
    return {"status": "ok"}


@router.get("/webhook/{tenant_slug}")
@router.get("/webhook/{tenant_slug}/")
async def test_webhook_get(tenant_slug: str, db: AsyncSession = Depends(get_db)):
    """
    GET endpoint for connectivity verification.
    Ensures that the endpoint is reachable and returns tenant status.
    """
    return {
        "status": "active",
        "message": f"Telegram Webhook for tenant '{tenant_slug}' is running. Use POST to submit updates.",
        "tenant_slug": tenant_slug
    }


class WebhookSetupRequest(BaseModel):
    base_url: Optional[str] = None
    bot_token: Optional[str] = None

@router.post("/setup-webhook", dependencies=[Depends(verify_admin)])
async def setup_telegram_webhook(
    payload: Optional[WebhookSetupRequest] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant)
):
    """
    Automatically registers the Telegram Webhook for this tenant with Telegram Bot API.
    Uses the request's base URL or the provided base URL to construct the webhook endpoint dynamically.
    """
    from app.core.tenant_config import get_tenant_settings
    from app.models.settings_models import SystemSetting
    
    tenant_settings = await get_tenant_settings(db)
    token = (payload.bot_token.strip() if payload and payload.bot_token and payload.bot_token.strip() else None) or tenant_settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token Telegram belum dikonfigurasi pada pengaturan instansi. Silakan isi token dan simpan pengaturan terlebih dahulu."
        )

    # If bot_token was explicitly provided in payload, ensure it is persisted in DB if not already set
    if payload and payload.bot_token and payload.bot_token.strip() and not tenant_settings.TELEGRAM_BOT_TOKEN:
        try:
            stmt = select(SystemSetting).where(SystemSetting.key == "telegram_token")
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.value = payload.bot_token.strip()
            else:
                db.add(SystemSetting(key="telegram_token", value=payload.bot_token.strip()))
            await db.commit()
        except Exception as e:
            logger.warning(f"Could not auto-persist telegram_token: {e}")

    # Use the custom base URL if provided in the payload, otherwise fall back to request base URL
    custom_base_url = payload.base_url if payload else None
    if custom_base_url:
        base_url = custom_base_url.rstrip('/')
    else:
        # Construct webhook URL based on the request's base URL
        # E.g. request.base_url is 'http://localhost:8000/' or 'https://natuna.laporsar.id/'
        base_url = str(request.base_url).rstrip('/') if request else ""
        
        # In some reverse proxy setups, request.base_url might be HTTP even if the external proxy is HTTPS.
        # Check X-Forwarded-Proto header to verify protocol
        x_forwarded_proto = request.headers.get("x-forwarded-proto") or request.headers.get("X-Forwarded-Proto") if request else None
        if x_forwarded_proto == "https" and base_url.startswith("http://"):
            base_url = base_url.replace("http://", "https://")

    webhook_url = f"{base_url}/api/telegram/webhook/{tenant.slug}"
    
    # We can also use a secret token for security if configured
    secret_token = tenant_settings.TELEGRAM_SECRET_TOKEN
    
    payload = {
        "url": webhook_url,
    }
    if secret_token:
        payload["secret_token"] = secret_token

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json=payload
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return {
                    "status": "success",
                    "message": "Webhook Telegram berhasil didaftarkan.",
                    "webhook_url": webhook_url,
                    "telegram_response": data
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Telegram API Error: {data.get('description', 'Unknown error')}"
                )
    except httpx.HTTPError as e:
        logger.error(f"Failed to register Telegram Webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Koneksi ke Telegram API gagal: {str(e)}"
        )

