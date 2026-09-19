"""
Transcription Service
=====================
Converts voice/audio messages to text using speech-to-text models.
Supports downloading audio from Telegram and WhatsApp, then transcribing
via Ollama's whisper model or a fallback approach.
"""

import os
import logging

import httpx
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)

# Directory for temporary audio files
TEMP_AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "temp_audio"
TEMP_AUDIO_DIR.mkdir(exist_ok=True)


class TranscriptionService:
    """Download and transcribe voice/audio messages."""

    def __init__(self):
        pass

    @property
    def ollama_url(self):
        """Backward compat — returns Ollama base URL."""
        from app.core.config import settings as _s
        return _s.AI_LLM_BASE_URL or _s.OLLAMA_HOST

    @property
    def whisper_model(self):
        from app.core.config import settings as _s
        return _s.AI_STT_MODEL or _s.WHISPER_MODEL

    # ----------------------------------------------------------------
    # Audio Transcription via AI Provider Manager
    # ----------------------------------------------------------------

    async def transcribe_audio(self, file_path: str) -> str:
        """
        Transcribe an audio file to text using the configured STT provider.
        Supports: Local Whisper, Ollama (local), OpenAI Whisper, Groq Whisper, Gemini Multimodal.
        Falls back to Cloud STT if local Whisper fails.
        """
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return ""

        try:
            from app.services.ai_providers import ai_provider_manager

            # 1. Try configured STT provider
            logger.info(f"Attempting transcription using provider: {settings.AI_STT_PROVIDER}")
            result = await ai_provider_manager.transcribe_audio(
                file_path=file_path,
                language="id",
            )
            if result and result.strip():
                logger.info(f"Transcription successful using {settings.AI_STT_PROVIDER}: {len(result)} chars")
                return result

            # 2. Hybrid Fallback (if local Whisper fails or returns empty)
            if settings.AI_STT_PROVIDER == "local_whisper":
                fallback_provider = None
                # Check for Groq (very fast, preferred for STT)
                if settings.AI_STT_API_KEY and settings.AI_STT_PROVIDER == "groq":
                    fallback_provider = "groq"
                elif settings.AI_LLM_PROVIDER == "groq" and settings.AI_LLM_API_KEY:
                    fallback_provider = "groq"
                # Check for Gemini
                elif settings.AI_LLM_PROVIDER == "gemini" and settings.AI_LLM_API_KEY:
                    fallback_provider = "gemini"
                # Check for OpenAI
                elif settings.AI_STT_API_KEY and settings.AI_STT_PROVIDER == "openai":
                    fallback_provider = "openai"
                elif settings.AI_LLM_PROVIDER == "openai" and settings.AI_LLM_API_KEY:
                    fallback_provider = "openai"

                if fallback_provider:
                    logger.warning(f"Local Whisper failed or returned empty. Falling back to Cloud STT: {fallback_provider}")
                    fallback_model = "whisper-large-v3" if fallback_provider == "groq" else ("gemini-1.5-flash" if fallback_provider == "gemini" else "whisper-1")
                    
                    fallback_result = await ai_provider_manager.transcribe_audio(
                        file_path=file_path,
                        language="id",
                        provider_override=fallback_provider,
                        model_override=fallback_model
                    )
                    if fallback_result and fallback_result.strip():
                        logger.info(f"Fallback transcription successful using {fallback_provider}: {len(fallback_result)} chars")
                        return fallback_result

            logger.error("All transcription attempts returned empty result or failed.")
            return ""

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
        finally:
            # Clean up temporary audio file to prevent memory/disk bloat
            self._cleanup(file_path)

    # ----------------------------------------------------------------
    # Download from Telegram
    # ----------------------------------------------------------------

    async def download_telegram_voice(self, file_id: str, bot_token: str = None, ext: str = ".ogg") -> str:
        """
        Download a voice message from Telegram Bot API.
        Returns the local file path of the downloaded file.
        """
        token = bot_token or settings.TELEGRAM_BOT_TOKEN
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not configured")
            return ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: Get file path from Telegram
                resp = await client.get(
                    f"https://api.telegram.org/bot{token}/getFile",
                    params={"file_id": file_id},
                )
                resp.raise_for_status()
                file_info = resp.json()

                if not file_info.get("ok"):
                    logger.error(f"Telegram getFile failed: {file_info}")
                    return ""

                file_size = file_info["result"].get("file_size")
                if file_size and file_size > 15 * 1024 * 1024:
                    logger.warning(f"Telegram file {file_id} size {file_size} exceeds 15MB limit")
                    return "size_limit_exceeded"

                tg_file_path = file_info["result"]["file_path"]

                # Step 2: Download the actual file
                download_url = f"https://api.telegram.org/file/bot{token}/{tg_file_path}"
                file_resp = await client.get(download_url)
                file_resp.raise_for_status()

                # Save to temp directory
                local_path = str(TEMP_AUDIO_DIR / f"tg_{file_id}{ext}")
                with open(local_path, "wb") as f:
                    f.write(file_resp.content)

                logger.info(f"Downloaded Telegram voice to {local_path}")
                return local_path

        except Exception as e:
            logger.error(f"Failed to download Telegram voice: {e}")
            return ""

    # ----------------------------------------------------------------
    # Download from WhatsApp
    # ----------------------------------------------------------------

    async def download_whatsapp_audio(self, media_id: str, wa_token: str = None, ext: str = ".ogg") -> str:
        """
        Download an audio message from WhatsApp Cloud API (Meta Graph API).
        Returns the local file path of the downloaded audio file.
        """
        token = wa_token or settings.WHATSAPP_API_TOKEN
        if not token:
            logger.error("WHATSAPP_API_TOKEN not configured")
            return ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: Get media URL from Graph API
                resp = await client.get(
                    f"https://graph.facebook.com/v19.0/{media_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                media_data = resp.json()
                media_url = media_data.get("url")
                file_size = media_data.get("file_size")

                if file_size and file_size > 15 * 1024 * 1024:
                    logger.warning(f"WhatsApp media {media_id} size {file_size} exceeds 15MB limit")
                    return "size_limit_exceeded"

                if not media_url:
                    logger.error("No URL returned for WhatsApp media")
                    return ""

                # Step 2: Download the actual media file
                file_resp = await client.get(
                    media_url,
                    headers={"Authorization": f"Bearer {token}"},
                )
                file_resp.raise_for_status()

                # Save to temp directory
                local_path = str(TEMP_AUDIO_DIR / f"wa_{media_id}{ext}")
                with open(local_path, "wb") as f:
                    f.write(file_resp.content)

                logger.info(f"Downloaded WhatsApp audio to {local_path}")
                return local_path

        except Exception as e:
            logger.error(f"Failed to download WhatsApp audio: {e}")
            return ""

    # ----------------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------------

    @staticmethod
    def _cleanup(file_path: str):
        """Remove temporary audio file after transcription."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temp audio: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")


# Singleton
transcription_service = TranscriptionService()
