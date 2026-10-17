from fastapi import APIRouter, Depends, Request, Query, HTTPException, Header, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import hmac
import hashlib
import json

from app.db.session import get_db, get_tenant
from app.core.config import settings
from app.engine.chatbot_engine import chatbot_engine
from app.services.reply_dispatcher import reply_dispatcher
from app.core.tenant_config import get_tenant_settings
from app.models.master_models import Tenant

router = APIRouter()
logger = logging.getLogger(__name__)

async def process_whatsapp_background(tenant_slug: str, db_url: str, s3_bucket: str, data: dict):
    from app.db.session import get_tenant_sessionmaker
    from app.core.tenant_config import get_tenant_settings
    from app.services.transcription import transcription_service
    from app.services.storage_service import storage_service
    from app.models.attachment_model import Attachment
    import os

    session_maker = get_tenant_sessionmaker(db_url)
    async with session_maker() as db:
        db.info["tenant_slug"] = tenant_slug
        try:
            tenant_settings = await get_tenant_settings(db)
            wa_token = tenant_settings.WHATSAPP_API_TOKEN
            phone_id = tenant_settings.WHATSAPP_PHONE_NUMBER_ID
            
            if "entry" in data:
                for entry in data["entry"]:
                    if "changes" in entry:
                        for change in entry["changes"]:
                            value = change.get("value", {})
                            if "messages" in value:
                                for msg in value["messages"]:
                                    from_phone = msg.get("from")
                                    msg_type = msg.get("type")
                                    
                                    text = ""
                                    is_voice = False
                                    if msg_type == "text":
                                        text = msg.get("text", {}).get("body", "")
                                    elif msg_type == "interactive":
                                        interactive_type = msg.get("interactive", {}).get("type")
                                        if interactive_type == "button_reply":
                                            text = msg.get("interactive", {}).get("button_reply", {}).get("title", "")
                                        elif interactive_type == "list_reply":
                                            text = msg.get("interactive", {}).get("list_reply", {}).get("title", "")
                                    elif msg_type == "location":
                                        loc = msg.get("location", {})
                                        lat = loc.get("latitude")
                                        lng = loc.get("longitude")
                                        if lat is not None and lng is not None:
                                            text = f"Lokasi GPS: {lat}, {lng}"
                                    elif msg_type == "audio":
                                        audio_obj = msg.get("audio", {})
                                        media_id = audio_obj.get("id")
                                        if media_id:
                                            local_path = await transcription_service.download_whatsapp_audio(media_id, wa_token=wa_token)
                                            if local_path == "size_limit_exceeded":
                                                logger.warning("WhatsApp audio size limit exceeded")
                                                await reply_dispatcher.send_whatsapp_reply(
                                                    recipient_phone=from_phone,
                                                    text="*Rekaman Suara Melebihi Batas*\n\nUkuran rekaman suara Anda melebihi batas maksimum 15MB.",
                                                    wa_token=wa_token,
                                                    phone_id=phone_id
                                                )
                                                continue
                                            if local_path:
                                                transcribed_text = await transcription_service.transcribe_audio(local_path)
                                                if transcribed_text and transcribed_text.strip():
                                                    logger.info(f"WhatsApp audio transcribed successfully: '{transcribed_text}'")
                                                    text = transcribed_text
                                                    is_voice = True
                                                else:
                                                    logger.warning("WhatsApp audio transcription returned empty result.")
                                                    await reply_dispatcher.send_whatsapp_reply(
                                                        recipient_phone=from_phone,
                                                        text="*Pesan Suara Kurang Jelas*\n\nSistem kami tidak dapat mendeteksi ucapan pada rekaman suara Anda dengan jelas. Silakan kirim pesan suara baru atau ketik pesan Anda secara manual.",
                                                        wa_token=wa_token,
                                                        phone_id=phone_id
                                                    )
                                                    continue
                                            else:
                                                logger.error("Failed to download WhatsApp audio.")
                                                await reply_dispatcher.send_whatsapp_reply(
                                                    recipient_phone=from_phone,
                                                    text="*Koneksi Bermasalah*\n\nGagal mengunduh rekaman suara Anda. Silakan kirim ulang pesan suara atau ketik pesan secara manual.",
                                                    wa_token=wa_token,
                                                    phone_id=phone_id
                                                )
                                                continue
                                    elif msg_type in ("image", "document", "video"):
                                        media_obj = msg.get(msg_type, {})
                                        media_id = media_obj.get("id")
                                        mime_type = media_obj.get("mime_type", "application/octet-stream")
                                        
                                        if msg_type == "image":
                                            file_type = "photo"
                                        else:
                                            file_type = msg_type
                                            
                                        original_filename = media_obj.get("filename", f"{msg_type}_{media_id}")
                                        if msg_type == "image" and not original_filename.lower().endswith((".jpg", ".jpeg")):
                                            original_filename += ".jpg"
                                            
                                        if media_id:
                                            ext = os.path.splitext(original_filename)[1] or ".ogg"
                                            local_path = await transcription_service.download_whatsapp_audio(media_id, wa_token=wa_token, ext=ext)
                                            if local_path == "size_limit_exceeded":
                                                logger.warning("WhatsApp attachment size limit exceeded")
                                                await reply_dispatcher.send_whatsapp_reply(
                                                    recipient_phone=from_phone,
                                                    text="*Berkas Melebihi Batas*\n\nUkuran berkas Anda melebihi batas maksimum 15MB. Silakan kirim berkas dengan ukuran yang lebih kecil.",
                                                    wa_token=wa_token,
                                                    phone_id=phone_id
                                                )
                                                continue
                                            if local_path:
                                                try:
                                                    with open(local_path, "rb") as f:
                                                        file_bytes = f.read()
                                                    
                                                    try:
                                                        os.remove(local_path)
                                                    except Exception:
                                                        pass
                                                        
                                                    bucket_name = s3_bucket or getattr(settings, "MINIO_BUCKET_ATTACHMENTS", None)
                                                    file_key = await storage_service.upload_file(
                                                        file_data=file_bytes,
                                                        original_filename=original_filename,
                                                        mime_type=mime_type,
                                                        file_type=file_type,
                                                        user_id=f"wa_{from_phone}",
                                                        channel="whatsapp",
                                                        bucket_name=bucket_name,
                                                        tenant_slug=tenant_slug
                                                    )
                                                    
                                                    if file_key:
                                                        new_attachment = Attachment(
                                                            user_id=f"wa_{from_phone}",
                                                            channel="whatsapp",
                                                            file_key=file_key,
                                                            bucket=bucket_name,
                                                            original_filename=original_filename,
                                                            mime_type=mime_type,
                                                            file_size=len(file_bytes),
                                                            file_type=file_type
                                                        )
                                                        try:
                                                            db.add(new_attachment)
                                                            await db.commit()
                                                        except Exception as db_err:
                                                            await db.rollback()
                                                            logger.error(f"Failed to save WhatsApp attachment to DB: {db_err}")
                                                            raise
                                                        logger.info(f"Successfully processed and saved WhatsApp attachment {original_filename} to MinIO bucket {bucket_name}.")
                                                        
                                                        text = "Ada Dokumen/Foto Terlampir"
                                                    else:
                                                        logger.error("Failed to upload WhatsApp attachment to MinIO.")
                                                        text = "Ada Dokumen/Foto Terlampir (Upload Gagal)"
                                                except Exception as attach_err:
                                                    logger.error(f"Error saving WhatsApp attachment: {attach_err}")
                                                    text = "Ada Dokumen/Foto Terlampir (Simpan Gagal)"
                                            else:
                                                logger.error("Failed to download WhatsApp attachment.")
                                                text = "Ada Dokumen/Foto Terlampir (Download Gagal)"
                                    
                                    if not text:
                                        logger.warning(f"Skipped WhatsApp message of type '{msg_type}' — No text payload")
                                        continue
                                    
                                    # Resolve contact info from metadata if available
                                    contacts = value.get("contacts", [])
                                    contact_name = f"WA User {from_phone}"
                                    if contacts:
                                        contact_name = contacts[0].get("profile", {}).get("name", contact_name)
                                        
                                    user_profile = {
                                        "contact_name": contact_name,
                                        "contact_phone": from_phone
                                    }
                                    
                                    # Process message via the Centralized Chatbot Engine
                                    response = await chatbot_engine.process_message(
                                        user_id=f"wa_{from_phone}",
                                        message_text=text,
                                        channel="whatsapp",
                                        db=db,
                                        user_profile=user_profile
                                    )
                                    
                                    # Prepend transcription feedback if it was a voice message
                                    if is_voice and response and "text" in response:
                                        response["text"] = f"*[Transkripsi Pesan Suara]:*\n_\"{text}\"_\n\n{response['text']}"
                                    
                                    # Send WhatsApp Reply
                                    if response and "text" in response:
                                        await reply_dispatcher.send_whatsapp_reply(
                                            recipient_phone=from_phone,
                                            text=response["text"],
                                            buttons=response.get("buttons"),
                                            wa_token=wa_token,
                                            phone_id=phone_id
                                        )
        except Exception as e:
            logger.error(f"Error processing WhatsApp message in background: {e}", exc_info=True)

@router.get("/webhook/{tenant_slug}")
async def verify_whatsapp(
    tenant_slug: str,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: int = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    db: AsyncSession = Depends(get_db)
):
    """
    Verification endpoint for Meta Cloud API Webhook handshake.
    """
    tenant_settings = await get_tenant_settings(db)
    verify_token = tenant_settings.WHATSAPP_VERIFY_TOKEN
    
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info(f"WhatsApp webhook verified successfully for tenant {tenant_slug}")
        return hub_challenge
    
    logger.warning(f"WhatsApp webhook verification failed for tenant {tenant_slug} - Token mismatch")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@router.post("/webhook/{tenant_slug}")
async def whatsapp_webhook(
    tenant_slug: str,
    request: Request, 
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant)
):
    """
    Webhook endpoint for receiving real-time events and messages from WhatsApp.
    Offloads heavy operations (media download, transcription, LLM processing) to background_tasks.
    """
    try:
        tenant_settings = await get_tenant_settings(db)
        app_secret = tenant_settings.WHATSAPP_APP_SECRET
        
        body_bytes = await request.body()
        
        # Verify signature if WHATSAPP_APP_SECRET is set
        if app_secret:
            if not x_hub_signature_256 or not x_hub_signature_256.startswith("sha256="):
                logger.warning("WhatsApp webhook signature verification failed: Header missing or invalid")
                raise HTTPException(status_code=401, detail="Signature missing or invalid")
                
            expected_sig = x_hub_signature_256[7:]
            computed_sig = hmac.new(
                app_secret.encode("utf-8"),
                body_bytes,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(computed_sig, expected_sig):
                logger.warning("WhatsApp webhook signature verification failed: Signature mismatch")
                raise HTTPException(status_code=401, detail="Signature mismatch")
                
            logger.info("WhatsApp webhook signature verified successfully")
            
        data = json.loads(body_bytes)
        logger.info(f"Received WhatsApp Webhook for tenant {tenant_slug} - queueing background task")
        
        # Schedule the background processing task
        background_tasks.add_task(
            process_whatsapp_background,
            tenant_slug=tenant_slug,
            db_url=tenant.db_url,
            s3_bucket=tenant.s3_bucket,
            data=data
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling WhatsApp webhook: {e}", exc_info=True)
        
    return {"status": "ok"}
