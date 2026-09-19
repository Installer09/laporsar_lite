"""
Reply Dispatcher
================
Abstraction layer for sending bot replies back to the correct channel.
Supports Telegram Bot API and WhatsApp Cloud API (Meta Graph API).
Also handles forwarding completed reports to the internal SAR command group.
"""

import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


def _sanitize_telegram_markdown(text: str) -> str:
    """
    Sanitize text for Telegram Markdown V1 by ensuring special
    characters (*, _, `) are properly paired. Removes unpaired
    markers that would cause Telegram's parser to reject the message.
    """
    result = text
    for char in ('*', '_', '`'):
        count = result.count(char)
        if count % 2 != 0:
            # Remove the LAST occurrence of the unpaired marker
            idx = result.rfind(char)
            result = result[:idx] + result[idx + 1:]
    return result


class ReplyDispatcher:
    """Send messages to Telegram, WhatsApp, or SAR command group."""

    # ----------------------------------------------------------------
    # Telegram
    # ----------------------------------------------------------------

    @staticmethod
    async def send_telegram_reply(
        chat_id: str, text: str, buttons: list = None, inline_keyboard: list = None, bot_token: str = None
    ) -> bool:
        """
        Send a text reply to a Telegram chat using the Bot API.
        Supports markdown formatting, reply buttons, or inline keyboards.
        """
        token = bot_token or settings.TELEGRAM_BOT_TOKEN
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not configured — cannot send reply")
            return False

        try:
            safe_text = _sanitize_telegram_markdown(text)
            payload = {
                "chat_id": chat_id,
                "text": safe_text,
                "parse_mode": "Markdown",
            }

            if inline_keyboard:
                payload["reply_markup"] = {
                    "inline_keyboard": inline_keyboard
                }
            elif buttons is not None:
                if len(buttons) == 0:
                    payload["reply_markup"] = {
                        "remove_keyboard": True
                    }
                else:
                    keyboard_row = []
                    for b in buttons:
                        if isinstance(b, dict):
                            keyboard_row.append(b)
                        else:
                            keyboard_row.append({"text": b})

                    payload["reply_markup"] = {
                        "keyboard": [keyboard_row],
                        "one_time_keyboard": True,
                        "resize_keyboard": True,
                    }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json=payload,
                )
                if resp.status_code == 200:
                    logger.info(f"Telegram reply sent to {chat_id}")
                    return True

                # Markdown parse error → retry without parse_mode
                if resp.status_code == 400 and "parse entities" in resp.text:
                    logger.warning(
                        f"Telegram Markdown parse error, retrying without parse_mode"
                    )
                    payload["text"] = text  # original text, no markdown
                    payload.pop("parse_mode", None)
                    resp2 = await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json=payload,
                    )
                    if resp2.status_code == 200:
                        logger.info(f"Telegram reply sent (plain) to {chat_id}")
                        return True
                    logger.error(
                        f"Telegram plain fallback also failed [{resp2.status_code}]: {resp2.text}"
                    )
                    return False

                logger.error(
                    f"Telegram sendMessage failed [{resp.status_code}]: {resp.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Failed to send Telegram reply: {e}")
            return False

    # ----------------------------------------------------------------
    # WhatsApp (Meta Cloud API)
    # ----------------------------------------------------------------

    @staticmethod
    async def send_whatsapp_reply(
        recipient_phone: str, text: str, buttons: list[str] = None, wa_token: str = None, phone_id: str = None
    ) -> bool:
        """
        Send a text reply to a WhatsApp user via Meta Cloud API.
        Supports interactive buttons if provided.
        """
        token = wa_token or settings.WHATSAPP_API_TOKEN
        phone_id = phone_id or settings.WHATSAPP_PHONE_NUMBER_ID

        if not token or not phone_id:
            logger.warning(
                "WhatsApp API not configured (missing token or phone_number_id)"
            )
            return False

        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient_phone,
            }

            if buttons:
                payload["type"] = "interactive"
                
                if len(buttons) > 3:
                    # Meta Cloud API List Message (Dropdown) - Max 10 items
                    action_btn_text = "Pilih Opsi"
                    lower_text = text.lower()
                    if "waktu" in lower_text or "kapan" in lower_text:
                        action_btn_text = "Pilih Waktu"
                    elif "jenis" in lower_text or "klasifikasi" in lower_text:
                        action_btn_text = "Pilih Jenis"
                    elif "korban" in lower_text:
                        action_btn_text = "Pilih Korban"
                    elif "pelapor" in lower_text:
                        action_btn_text = "Pilih Hubungan"

                    rows = []
                    for i, b in enumerate(buttons[:10]):
                        title_text = b.get("text") if isinstance(b, dict) else b
                        # Meta limit: title must be <= 24 characters
                        title_text = title_text[:24]
                        rows.append({
                            "id": f"list_opt_{i}",
                            "title": title_text
                        })

                    payload["interactive"] = {
                        "type": "list",
                        "header": {
                            "type": "text",
                            "text": "📋 PILIHAN RESPONS"
                        },
                        "body": {"text": text},
                        "action": {
                            "button": action_btn_text,
                            "sections": [
                                {
                                    "title": "Daftar Opsi",
                                    "rows": rows
                                }
                            ]
                        }
                    }
                else:
                    # Meta Cloud API Button Message (Interactive) - Max 3 buttons
                    payload["interactive"] = {
                        "type": "button",
                        "body": {"text": text},
                        "action": {
                            "buttons": [
                                {
                                    "type": "reply",
                                    "reply": {"id": f"btn_{i}", "title": b.get("text") if isinstance(b, dict) else b},
                                }
                                for i, b in enumerate(buttons[:3])
                            ]
                        },
                    }
            else:
                payload["type"] = "text"
                payload["text"] = {"body": text}

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v19.0/{phone_id}/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code == 200:
                    logger.info(f"WhatsApp reply sent to {recipient_phone}")
                    return True
                else:
                    logger.error(
                        f"WhatsApp send failed [{resp.status_code}]: {resp.text}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Failed to send WhatsApp reply: {e}")
            return False

    # ----------------------------------------------------------------
    # Forward to SAR Command Group (Telegram)
    # ----------------------------------------------------------------

    @staticmethod
    async def forward_to_sar_group(report_text: str, bot_token: str = None, group_id: str = None) -> bool:
        """
        Forward a completed Info Awal report to the SAR command group
        on Telegram. Uses the group_id and bot_token.
        """
        token = bot_token or settings.TELEGRAM_BOT_TOKEN
        group = group_id or settings.TELEGRAM_SAR_GROUP_ID

        if not token or not group:
            logger.warning(
                "Cannot forward to Telegram SAR group: bot_token or group_id not configured"
            )
            return False

        try:
            safe_text = _sanitize_telegram_markdown(report_text)
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id": group,
                        "text": safe_text,
                        "parse_mode": "Markdown",
                    },
                )
                if resp.status_code == 200:
                    logger.info(f"Report forwarded to Telegram SAR group {group}")
                    return True

                # Markdown parse error → retry as plain text
                if resp.status_code == 400 and "parse entities" in resp.text:
                    logger.warning(
                        "SAR group forward Markdown error, retrying as plain text"
                    )
                    resp2 = await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={
                            "chat_id": group,
                            "text": report_text,
                        },
                    )
                    if resp2.status_code == 200:
                        logger.info(
                            f"Report forwarded (plain) to Telegram SAR group {group}"
                        )
                        return True
                    logger.error(
                        f"SAR group plain fallback failed [{resp2.status_code}]: {resp2.text}"
                    )
                    return False

                logger.error(
                    f"Forward to Telegram SAR group failed [{resp.status_code}]: {resp.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Failed to forward report to Telegram SAR group: {e}")
            return False

    # ----------------------------------------------------------------
    # Forward to SAR Command Group (WhatsApp)
    # ----------------------------------------------------------------

    @staticmethod
    async def forward_to_whatsapp_sar_group(report_text: str, wa_token: str = None, phone_id: str = None, group_id: str = None) -> bool:
        """
        Forward a completed Info Awal report to the WhatsApp SAR group.
        Uses WHATSAPP_SAR_GROUP_ID — this is the phone number or group
        participant ID configured for receiving formal reports.
        """
        token = wa_token or settings.WHATSAPP_API_TOKEN
        phone = phone_id or settings.WHATSAPP_PHONE_NUMBER_ID
        group = group_id or settings.WHATSAPP_SAR_GROUP_ID

        if not token or not phone or not group:
            logger.warning(
                "Cannot forward to WhatsApp SAR group: "
                "wa_token, phone_id, or group_id not configured"
            )
            return False

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v19.0/{phone}/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": group,
                        "type": "text",
                        "text": {"body": report_text},
                    },
                )
                if resp.status_code == 200:
                    logger.info(f"Report forwarded to WhatsApp SAR group {group}")
                    return True
                else:
                    logger.error(
                        f"Forward to WhatsApp SAR group failed [{resp.status_code}]: {resp.text}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Failed to forward report to WhatsApp SAR group: {e}")
            return False

    # ----------------------------------------------------------------
    # Forward Files to SAR Command Group (Telegram & WhatsApp)
    # ----------------------------------------------------------------

    @staticmethod
    async def forward_file_to_telegram_sar_group(file_bytes: bytes, filename: str, caption: str = "", bot_token: str = None, group_id: str = None) -> bool:
        token = bot_token or settings.TELEGRAM_BOT_TOKEN
        group = group_id or settings.TELEGRAM_SAR_GROUP_ID
        if not token or not group:
            return False

        try:
            safe_text = _sanitize_telegram_markdown(caption) if caption else ""
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"document": (filename, file_bytes)}
                data = {"chat_id": group}
                if safe_text:
                    data["caption"] = safe_text
                    data["parse_mode"] = "Markdown"
                
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendDocument",
                    data=data,
                    files=files
                )
                if resp.status_code == 200:
                    logger.info(f"File {filename} forwarded to Telegram SAR group")
                    return True
                
                # Markdown parse error → retry as plain text
                if resp.status_code == 400 and "parse entities" in resp.text:
                    data["caption"] = caption
                    data.pop("parse_mode", None)
                    resp2 = await client.post(
                        f"https://api.telegram.org/bot{token}/sendDocument",
                        data=data,
                        files=files
                    )
                    if resp2.status_code == 200:
                        logger.info(f"File {filename} forwarded (plain) to Telegram SAR group")
                        return True
                        
                logger.error(f"Telegram file forward failed [{resp.status_code}]: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to forward file {filename} to Telegram SAR group: {e}")
            return False

    @staticmethod
    async def forward_file_to_whatsapp_sar_group(file_bytes: bytes, filename: str, mime_type: str, caption: str = "", wa_token: str = None, phone_id: str = None, group_id: str = None) -> bool:
        token = wa_token or settings.WHATSAPP_API_TOKEN
        phone = phone_id or settings.WHATSAPP_PHONE_NUMBER_ID
        group = group_id or settings.WHATSAPP_SAR_GROUP_ID

        if not token or not phone or not group:
            return False

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Upload media
                upload_resp = await client.post(
                    f"https://graph.facebook.com/v19.0/{phone}/media",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"messaging_product": "whatsapp"},
                    files={"file": (filename, file_bytes, mime_type)}
                )
                
                if upload_resp.status_code != 200:
                    logger.error(f"WhatsApp media upload failed [{upload_resp.status_code}]: {upload_resp.text}")
                    return False
                    
                media_id = upload_resp.json().get("id")
                if not media_id:
                    return False

                # 2. Send message with media_id
                doc_payload = {"id": media_id, "filename": filename}
                if caption:
                    doc_payload["caption"] = caption
                    
                send_resp = await client.post(
                    f"https://graph.facebook.com/v19.0/{phone}/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": group,
                        "type": "document",
                        "document": doc_payload,
                    },
                )
                if send_resp.status_code == 200:
                    logger.info(f"File {filename} forwarded to WhatsApp SAR group")
                    return True
                else:
                    logger.error(f"WhatsApp file forward failed [{send_resp.status_code}]: {send_resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to forward file {filename} to WhatsApp SAR group: {e}")
            return False

    # ----------------------------------------------------------------
    # Forward to ALL SAR groups (Telegram + WhatsApp)
    # ----------------------------------------------------------------

    @staticmethod
    async def forward_report_to_all_groups(
        report_text: str,
        bot_token: str = None,
        tg_group_id: str = None,
        wa_token: str = None,
        wa_phone_id: str = None,
        wa_group_id: str = None
    ) -> dict:
        """
        Forward a completed report to both Telegram and WhatsApp SAR
        command groups simultaneously. Returns a dict with the result
        of each channel.
        """
        import asyncio

        tg_task = asyncio.create_task(
            ReplyDispatcher.forward_to_sar_group(report_text, bot_token=bot_token, group_id=tg_group_id)
        )
        wa_task = asyncio.create_task(
            ReplyDispatcher.forward_to_whatsapp_sar_group(
                report_text,
                wa_token=wa_token,
                phone_id=wa_phone_id,
                group_id=wa_group_id
            )
        )

        tg_ok, wa_ok = await asyncio.gather(tg_task, wa_task, return_exceptions=True)

        # Handle exceptions returned by gather
        if isinstance(tg_ok, Exception):
            logger.error(f"Telegram SAR group forward exception: {tg_ok}")
            tg_ok = False
        if isinstance(wa_ok, Exception):
            logger.error(f"WhatsApp SAR group forward exception: {wa_ok}")
            wa_ok = False

        logger.info(
            f"Report forwarded — Telegram: {'OK' if tg_ok else 'FAIL'}, "
            f"WhatsApp: {'OK' if wa_ok else 'FAIL'}"
        )

        return {"telegram": bool(tg_ok), "whatsapp": bool(wa_ok)}


# Singleton
reply_dispatcher = ReplyDispatcher()

