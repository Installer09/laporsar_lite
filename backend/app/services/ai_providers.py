"""
AI Provider Manager — Multi-Provider Abstraction Layer
=======================================================
Unified interface for LLM, Embedding, and STT (Speech-to-Text) across
multiple cloud and local AI providers.

Supported Providers:
  - Ollama  (local)   : LLM ✅  Embedding ✅  STT ✅
  - OpenAI  (cloud)   : LLM ✅  Embedding ✅  STT ✅
  - Gemini  (cloud)   : LLM ✅  Embedding ✅  STT ✅
  - Claude  (cloud)   : LLM ✅  Embedding ❌  STT ❌
  - Groq    (cloud)   : LLM ✅  Embedding ❌  STT ✅

All HTTP calls use httpx (already a project dependency).
No additional SDK packages are required.
"""

import os
import json
import base64
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# =====================================================================
# Provider Base URLs
# =====================================================================

PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "claude": "https://api.anthropic.com",
    "groq": "https://api.groq.com/openai",
}

# =====================================================================
# Helper — resolve internal Docker URLs for localhost
# =====================================================================

def _resolve_internal_url(url: str) -> str:
    if not url:
        return url
    url_str = str(url)
    if "localhost:8002" in url_str:
        return url_str.replace("localhost:8002", "whisper:8000")
    if "127.0.0.1:8002" in url_str:
        return url_str.replace("127.0.0.1:8002", "whisper:8000")
    if "localhost:11434" in url_str:
        return url_str.replace("localhost:11434", "ollama:11434")
    if "127.0.0.1:11434" in url_str:
        return url_str.replace("127.0.0.1:11434", "ollama:11434")
    return url_str

# =====================================================================
# Helper — resolve API key for an engine category
# =====================================================================

def _resolve_api_key(engine: str) -> str:
    """
    Resolve the API key for a given engine.
    Falls back to LLM key if the engine's own key is empty and the provider matches.
    Engine values: 'llm', 'embed', 'stt'
    """
    if engine == "llm":
        return settings.AI_LLM_API_KEY or ""
    elif engine == "embed":
        key = settings.AI_EMBED_API_KEY
        if not key and settings.AI_EMBED_PROVIDER == settings.AI_LLM_PROVIDER:
            key = settings.AI_LLM_API_KEY
        return key or ""
    elif engine == "stt":
        key = settings.AI_STT_API_KEY
        if not key and settings.AI_STT_PROVIDER == settings.AI_LLM_PROVIDER:
            key = settings.AI_LLM_API_KEY
        return key or ""
    return ""


# =====================================================================
# LLM Providers
# =====================================================================

async def _ollama_llm_generate(
    prompt: str,
    model: str,
    *,
    base_url: str = None,
    system_prompt: str = "",
    temperature: float = 0.0,
    json_mode: bool = False,
    timeout: float = 120.0,
) -> str:
    """Generate text via Ollama /api/generate."""
    final_base_url = _resolve_internal_url(base_url or settings.AI_LLM_BASE_URL or settings.OLLAMA_HOST or "http://localhost:11434")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system_prompt:
        payload["system"] = system_prompt
    if json_mode:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{base_url}/api/generate", json=payload)
        response.raise_for_status()
        res_data = response.json()
        final_text = res_data.get("response", "").strip()
        if not final_text:
            final_text = res_data.get("thinking", "").strip()
        return final_text


async def _openai_compatible_llm_generate(
    prompt: str,
    model: str,
    api_key: str,
    base_url: str,
    *,
    system_prompt: str = "",
    temperature: float = 0.0,
    json_mode: bool = False,
    timeout: float = 120.0,
) -> str:
    """Generate text via OpenAI-compatible /v1/chat/completions (OpenAI, Groq)."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


async def _gemini_llm_generate(
    prompt: str,
    model: str,
    api_key: str,
    *,
    system_prompt: str = "",
    temperature: float = 0.0,
    json_mode: bool = False,
    timeout: float = 120.0,
) -> str:
    """Generate text via Google Gemini generateContent REST API."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    contents = []
    if system_prompt:
        contents.append({"role": "user", "parts": [{"text": system_prompt}]})
        contents.append({"role": "model", "parts": [{"text": "Understood. I will follow those instructions."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
        },
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        return ""


async def _claude_llm_generate(
    prompt: str,
    model: str,
    api_key: str,
    *,
    system_prompt: str = "",
    temperature: float = 0.0,
    json_mode: bool = False,
    timeout: float = 120.0,
) -> str:
    """Generate text via Anthropic Claude Messages API."""
    url = "https://api.anthropic.com/v1/messages"
    messages = [{"role": "user", "content": prompt}]

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": messages,
        "temperature": temperature,
    }
    if system_prompt:
        payload["system"] = system_prompt

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        content_blocks = data.get("content", [])
        text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]
        return "\n".join(text_parts).strip()


# =====================================================================
# Embedding Providers
# =====================================================================

async def _ollama_get_embedding(text: str, model: str, base_url: str = None) -> list[float]:
    """Get embedding via Ollama /api/embeddings."""
    final_base_url = _resolve_internal_url(base_url or settings.AI_LLM_BASE_URL or settings.OLLAMA_HOST or "http://localhost:11434")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{final_base_url.rstrip('/')}/api/embeddings",
            json={"model": model, "prompt": text},
        )
        response.raise_for_status()
        return response.json().get("embedding", [])


async def _openai_get_embedding(text: str, model: str, api_key: str, base_url: str = "https://api.openai.com/v1/embeddings") -> list[float]:
    """Get embedding via OpenAI-compatible endpoint."""
    if not api_key:
        raise ValueError("API Key OpenAI/Groq belum dikonfigurasi untuk Embedding")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            base_url,
            json={"model": model, "input": text},
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


async def _gemini_get_embedding(text: str, model: str, api_key: str) -> list[float]:
    """Get embedding via Gemini embedContent REST API."""
    if not api_key:
        raise ValueError("API Key Google Gemini belum dikonfigurasi untuk Embedding")
    clean_model = model.replace("models/", "") if model else "gemini-embedding-2"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}"
        f":embedContent?key={api_key}"
    )
    payload = {
        "model": f"models/{clean_model}",
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": 1024,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", {}).get("values", [])


async def _gemini_get_embeddings_batch(texts: list[str], model: str, api_key: str) -> list[list[float]]:
    """Get batch embeddings via Gemini batchEmbedContents REST API (up to 100 items per call)."""
    if not api_key:
        raise ValueError("API Key Google Gemini belum dikonfigurasi untuk Embedding")
    if not texts:
        return []
    clean_model = model.replace("models/", "") if model else "gemini-embedding-2"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}"
        f":batchEmbedContents?key={api_key}"
    )
    requests = [
        {
            "model": f"models/{clean_model}",
            "content": {"parts": [{"text": t}]},
            "outputDimensionality": 1024,
        }
        for t in texts
    ]
    payload = {"requests": requests}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings", [])
        return [e.get("values", []) for e in embeddings]


# =====================================================================
# STT (Speech-to-Text) Providers
# =====================================================================

async def _ollama_transcribe(file_path: str, model: str, base_url: str = None) -> str:
    """Transcribe audio via Ollama — try multimodal then OpenAI-compat endpoint."""
    final_base_url = _resolve_internal_url(base_url or settings.AI_LLM_BASE_URL or settings.OLLAMA_HOST or "http://localhost:11434")

    # Try 1: Ollama multimodal generate with audio bytes
    try:
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Transcribe the following audio to Indonesian text.",
                    "images": [audio_b64],
                    "stream": False,
                },
            )
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                if result:
                    return result
    except Exception as e:
        logger.warning(f"[Ollama STT] Multimodal attempt failed: {e}")

    # Try 2: OpenAI-compatible /v1/audio/transcriptions
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, "rb") as f:
                response = await client.post(
                    f"{base_url}/v1/audio/transcriptions",
                    files={"file": (os.path.basename(file_path), f, "audio/ogg")},
                    data={"model": model, "language": "id"},
                )
            if response.status_code == 200:
                text = response.json().get("text", "").strip()
                if text:
                    return text
    except Exception as e:
        logger.warning(f"[Ollama STT] OpenAI-compat endpoint failed: {e}")

    return ""


async def _openai_compatible_transcribe(
    file_path: str, model: str, api_key: str, base_url: str
) -> str:
    """Transcribe audio via OpenAI-compatible /v1/audio/transcriptions (OpenAI, Groq)."""
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(file_path, "rb") as f:
            response = await client.post(
                f"{base_url}/v1/audio/transcriptions",
                files={"file": (os.path.basename(file_path), f, "audio/ogg")},
                data={"model": model, "language": "id"},
                headers=headers,
            )
        response.raise_for_status()
        return response.json().get("text", "").strip()


async def _gemini_transcribe(file_path: str, model: str, api_key: str) -> str:
    """Transcribe audio via Gemini multimodal (send audio as inline data)."""
    with open(file_path, "rb") as f:
        audio_bytes = f.read()
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    # Detect MIME type from extension
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".ogg": "audio/ogg", ".mp3": "audio/mp3", ".wav": "audio/wav",
        ".m4a": "audio/mp4", ".flac": "audio/flac", ".webm": "audio/webm",
    }
    mime_type = mime_map.get(ext, "audio/ogg")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    payload = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": audio_b64,
                    }
                },
                {
                    "text": (
                        "Transcribe the audio above to Indonesian text. "
                        "Return ONLY the transcription text, no explanations."
                    )
                },
            ]
        }],
        "generationConfig": {"temperature": 0.0},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
    return ""


async def _local_whisper_transcribe(file_path: str, model: str, base_url: str = None, prompt: str = "") -> str:
    """
    Transcribe audio via local/external Whisper service (fedirz/faster-whisper-server).
    Uses standard OpenAI-compatible audio transcription endpoint.
    """
    final_base_url = _resolve_internal_url(base_url or settings.AI_STT_BASE_URL or "http://whisper:8000")
    
    headers = {}
    payload_data = {
        "model": model,
        "language": "id"
    }
    if prompt:
        payload_data["prompt"] = prompt

    async with httpx.AsyncClient(timeout=90.0) as client:
        with open(file_path, "rb") as f:
            response = await client.post(
                f"{base_url.rstrip('/')}/v1/audio/transcriptions",
                files={"file": (os.path.basename(file_path), f, "audio/ogg")},
                data=payload_data,
                headers=headers,
            )
        response.raise_for_status()
        return response.json().get("text", "").strip()


# =====================================================================
# AI Provider Manager — Main Interface
# =====================================================================

class AIProviderManager:
    """
    Central manager that routes AI requests to the correct provider
    based on the current system configuration.

    Usage:
        from app.services.ai_providers import ai_provider_manager
        result = await ai_provider_manager.llm_generate(prompt="Hello")
        embedding = await ai_provider_manager.get_embedding("text")
        transcript = await ai_provider_manager.transcribe_audio("/path/to/file.ogg")
    """

    # =================================================================
    # LLM — Text Generation
    # =================================================================

    async def llm_generate(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.0,
        json_mode: bool = False,
        timeout: float = 120.0,
        model_override: str = "",
        tenant_settings = None,
    ) -> str:
        """
        Generate text using the configured LLM provider.
        Falls back to returning empty string on error.
        """
        cfg = tenant_settings if tenant_settings is not None else settings
        provider = cfg.AI_LLM_PROVIDER or "ollama"
        model = model_override or cfg.AI_LLM_MODEL or cfg.LLM_MODEL or "llama3.1"
        api_key = cfg.AI_LLM_API_KEY or ""
        base_url = cfg.AI_LLM_BASE_URL or ""

        try:
            if provider == "ollama":
                return await _ollama_llm_generate(
                    prompt, model,
                    base_url=base_url,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    timeout=timeout,
                )
            elif provider == "openai":
                return await _openai_compatible_llm_generate(
                    prompt, model, api_key,
                    PROVIDER_BASE_URLS["openai"],
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    timeout=timeout,
                )
            elif provider == "gemini":
                return await _gemini_llm_generate(
                    prompt, model, api_key,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    timeout=timeout,
                )
            elif provider == "claude":
                return await _claude_llm_generate(
                    prompt, model, api_key,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    timeout=timeout,
                )
            elif provider == "groq":
                return await _openai_compatible_llm_generate(
                    prompt, model, api_key,
                    PROVIDER_BASE_URLS["groq"],
                    system_prompt=system_prompt,
                    temperature=temperature,
                    json_mode=json_mode,
                    timeout=timeout,
                )
            else:
                logger.error(f"[AIProvider] Unknown LLM provider: {provider}")
                return ""

        except Exception as e:
            import traceback
            logger.error(f"[AIProvider] LLM generate failed (provider={provider}, model={model}): {e}\n{traceback.format_exc()}")
            return ""

    # =================================================================
    # Embedding — Vector Embedding for RAG
    # =================================================================

    async def get_embedding(self, text: str, tenant_settings = None, raise_on_error: bool = False) -> list[float]:
        """
        Get text embedding using the configured embedding provider.
        Falls back to returning empty list on error unless raise_on_error=True.
        """
        cfg = tenant_settings if tenant_settings is not None else settings
        provider = cfg.AI_EMBED_PROVIDER or "ollama"
        model = cfg.AI_EMBED_MODEL or "nomic-embed-text"
        base_url = cfg.AI_LLM_BASE_URL or ""
        
        # Resolve key
        api_key = cfg.AI_EMBED_API_KEY
        if not api_key and (cfg.AI_EMBED_PROVIDER == cfg.AI_LLM_PROVIDER or cfg.AI_EMBED_PROVIDER in ("gemini", "openai", "groq")):
            api_key = cfg.AI_LLM_API_KEY
        api_key = api_key or ""

        try:
            if provider == "ollama":
                return await _ollama_get_embedding(text, model, base_url=base_url)
            elif provider == "openai":
                return await _openai_get_embedding(text, model, api_key)
            elif provider == "groq":
                return await _openai_get_embedding(text, model, api_key, "https://api.groq.com/openai/v1/embeddings")
            elif provider == "gemini":
                return await _gemini_get_embedding(text, model, api_key)
            else:
                err_msg = f"Unknown embedding provider: {provider}"
                logger.error(f"[AIProvider] {err_msg}")
                if raise_on_error:
                    raise ValueError(err_msg)
                return []

        except Exception as e:
            logger.error(f"[AIProvider] Embedding failed (provider={provider}, model={model}): {e}")
            if raise_on_error:
                raise
            return []

    async def get_embeddings_batch(
        self,
        texts: list[str],
        tenant_settings = None,
        raise_on_error: bool = False,
    ) -> list[list[float]]:
        """
        Get batch embeddings for a list of texts.
        Optimized for Gemini and OpenAI using their batch endpoints.
        Falls back to sequential get_embedding for other providers.
        """
        if not texts:
            return []

        cfg = tenant_settings if tenant_settings is not None else settings
        provider = cfg.AI_EMBED_PROVIDER or "ollama"
        model = cfg.AI_EMBED_MODEL or "gemini-embedding-2"
        api_key = cfg.AI_EMBED_API_KEY
        if not api_key and (cfg.AI_EMBED_PROVIDER == cfg.AI_LLM_PROVIDER or cfg.AI_EMBED_PROVIDER in ("gemini", "openai", "groq")):
            api_key = cfg.AI_LLM_API_KEY
        api_key = api_key or ""

        try:
            if provider == "gemini":
                all_results = []
                batch_size = 50
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i + batch_size]
                    batch_embeds = await _gemini_get_embeddings_batch(batch_texts, model, api_key)
                    all_results.extend(batch_embeds)
                return all_results
            elif provider == "openai":
                # OpenAI /v1/embeddings accepts list of strings in input
                if not api_key:
                    raise ValueError("API Key OpenAI belum dikonfigurasi untuk Embedding")
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                all_results = []
                batch_size = 50
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i + batch_size]
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        response = await client.post(
                            "https://api.openai.com/v1/embeddings",
                            json={"model": model or "text-embedding-3-small", "input": batch_texts},
                            headers=headers,
                        )
                        response.raise_for_status()
                        items = response.json().get("data", [])
                        all_results.extend([item["embedding"] for item in items])
                return all_results
            else:
                # Fallback to sequential for Ollama, Groq, etc.
                results = []
                for t in texts:
                    emb = await self.get_embedding(t, tenant_settings=tenant_settings, raise_on_error=raise_on_error)
                    results.append(emb)
                return results

        except Exception as e:
            logger.error(f"[AIProvider] Batch embedding failed (provider={provider}, model={model}): {e}")
            if raise_on_error:
                raise
            return []

    # =================================================================
    # STT — Speech-to-Text (Audio Whisper)
    # =================================================================

    async def transcribe_audio(
        self,
        file_path: str,
        language: str = "id",
        provider_override: str = "",
        model_override: str = "",
        tenant_settings = None,
    ) -> str:
        """
        Transcribe an audio file using the configured STT provider.
        Falls back to returning empty string on error.
        """
        if not os.path.exists(file_path):
            logger.error(f"[AIProvider] Audio file not found: {file_path}")
            return ""

        cfg = tenant_settings if tenant_settings is not None else settings
        provider = provider_override or cfg.AI_STT_PROVIDER or "ollama"
        model = model_override or cfg.AI_STT_MODEL or cfg.WHISPER_MODEL or "whisper"
        base_url = cfg.AI_STT_BASE_URL or ""
        
        # Resolve key
        api_key = cfg.AI_STT_API_KEY
        if not api_key and cfg.AI_STT_PROVIDER == cfg.AI_LLM_PROVIDER:
            api_key = cfg.AI_LLM_API_KEY
        api_key = api_key or ""

        # Resolve generic or empty model names to provider-specific models
        if provider == "groq" and not (model and "whisper" in model.lower()):
            model = "whisper-large-v3"
        elif provider == "openai" and not (model and "whisper" in model.lower()):
            model = "whisper-1"
        elif provider == "gemini" and not (model and any(kw in model.lower() for kw in ("flash", "pro"))):
            model = "gemini-1.5-flash"

        # Build dynamic prompt from RuleExtractor dictionary cache to guide Whisper spelling
        prompt = ""
        if provider in ("local_whisper", "openai", "groq"):
            try:
                from app.services.rule_extractor import RuleExtractor
                prompt_words = []
                if hasattr(RuleExtractor, "_dictionary_cache") and RuleExtractor._dictionary_cache:
                    for cat, items in RuleExtractor._dictionary_cache.items():
                        for item in items:
                            w = item.get("word", "").strip()
                            if w and len(w) > 2 and w not in prompt_words:
                                prompt_words.append(w)
                if prompt_words:
                    std_hotwords = ["BASARNAS", "Kantor SAR", "Laka Kapal", "KMM", "Laka Air", "Kecelakaan Laut", "Kapal Tenggelam", "Perahu Terbalik"]
                    prompt_words = std_hotwords + [w for w in prompt_words if w not in std_hotwords]
                    prompt = ", ".join(prompt_words[:100])
            except Exception as cache_err:
                logger.warning(f"[AIProvider] Failed to extract dictionary cache for Whisper prompt: {cache_err}")

        try:
            if provider == "local_whisper":
                return await _local_whisper_transcribe(file_path, model, base_url=base_url, prompt=prompt)
            elif provider == "ollama":
                return await _ollama_transcribe(file_path, model, base_url=base_url)
            elif provider == "openai":
                return await _openai_compatible_transcribe(
                    file_path, model, api_key,
                    PROVIDER_BASE_URLS["openai"],
                )
            elif provider == "groq":
                return await _openai_compatible_transcribe(
                    file_path, model, api_key,
                    PROVIDER_BASE_URLS["groq"],
                )
            elif provider == "gemini":
                return await _gemini_transcribe(file_path, model, api_key)
            else:
                logger.error(f"[AIProvider] Unknown STT provider: {provider}")
                return ""

        except Exception as e:
            logger.error(f"[AIProvider] STT failed (provider={provider}, model={model}): {e}")
            return ""

    # =================================================================
    # Utility — Test Connection
    # =================================================================

    async def test_connection(
        self,
        provider: str,
        api_key: str = "",
        base_url: str = "",
        engine_type: str = "llm",
    ) -> dict:
        """
        Test connectivity to a specific provider.
        engine_type: "llm" | "embed" | "stt"
        Returns {"connected": bool, "message": str, "models": list}
        """
        try:
            if provider == "ollama":
                # Guard against incorrect base_url (like Whisper port 8002) passed for Ollama STT
                test_url = base_url
                if test_url and ("8002" in test_url or "whisper" in test_url):
                    test_url = settings.AI_LLM_BASE_URL or settings.OLLAMA_HOST or "http://localhost:11434"
                url = _resolve_internal_url(test_url or settings.AI_LLM_BASE_URL or settings.OLLAMA_HOST)
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{url.rstrip('/')}/api/tags")
                    resp.raise_for_status()
                    all_models = [m["name"] for m in resp.json().get("models", [])]
                    if engine_type == "embed":
                        embed_models = [m for m in all_models if any(kw in m.lower() for kw in ("embed", "bge", "nomic", "minilm"))]
                        models = embed_models if embed_models else all_models
                    else:
                        models = all_models
                    return {
                        "connected": True,
                        "message": f"Ollama terhubung, {len(models)} model tersedia",
                        "models": models,
                    }

            elif provider == "openai":
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    resp.raise_for_status()
                    all_models = [m["id"] for m in resp.json().get("data", [])]
                    all_models.sort()
                    if engine_type == "embed":
                        embed_models = [m for m in all_models if "embedding" in m.lower()]
                        models = embed_models if embed_models else ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]
                    elif engine_type == "stt":
                        stt_models = [m for m in all_models if "whisper" in m.lower()]
                        models = stt_models if stt_models else ["whisper-1"]
                    else:
                        models = all_models
                    return {
                        "connected": True,
                        "message": f"OpenAI API terhubung, {len(models)} model tersedia",
                        "models": models,
                    }

            elif provider == "gemini":
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                    )
                    resp.raise_for_status()
                    raw_models = resp.json().get("models", [])
                    all_models = [m["name"].replace("models/", "") for m in raw_models]
                    all_models.sort()
                    if engine_type == "embed":
                        embed_models = [
                            m["name"].replace("models/", "") 
                            for m in raw_models 
                            if "embedContent" in m.get("supportedGenerationMethods", []) or "embed" in m.get("name", "").lower()
                        ]
                        embed_models.sort()
                        models = embed_models if embed_models else ["gemini-embedding-2", "gemini-embedding-001", "gemini-embedding-2-preview"]
                    elif engine_type == "stt":
                        # Gemini audio / multimodal capable models
                        stt_models = [m for m in all_models if any(kw in m.lower() for kw in ("flash", "pro")) and not any(kw in m.lower() for kw in ("embed", "tts", "image", "imagen"))]
                        models = stt_models if stt_models else ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
                    else:
                        models = all_models
                    return {
                        "connected": True,
                        "message": f"Gemini API terhubung, {len(models)} model tersedia",
                        "models": models,
                    }

            elif provider == "claude":
                # Claude doesn't have a simple list-models endpoint,
                # so we do a minimal message request to test auth.
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "claude-3-5-haiku-20241022",
                            "max_tokens": 10,
                            "messages": [{"role": "user", "content": "Hi"}],
                        },
                    )
                    if resp.status_code in (200, 201):
                        return {
                            "connected": True,
                            "message": "Claude API terhubung",
                            "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"] if engine_type == "llm" else [],
                        }
                    elif resp.status_code == 401:
                        return {
                            "connected": False,
                            "message": "API Key tidak valid",
                            "models": [],
                        }
                    else:
                        return {
                            "connected": True,
                            "message": f"Claude API terhubung (status {resp.status_code})",
                            "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"] if engine_type == "llm" else [],
                        }

            elif provider == "groq":
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        "https://api.groq.com/openai/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    resp.raise_for_status()
                    all_models = [m["id"] for m in resp.json().get("data", [])]
                    all_models.sort()
                    if engine_type == "stt":
                        stt_models = [m for m in all_models if "whisper" in m.lower()]
                        models = stt_models if stt_models else ["whisper-large-v3", "whisper-large-v3-turbo"]
                    elif engine_type == "embed":
                        embed_models = [m for m in all_models if any(kw in m.lower() for kw in ("embed", "bge"))]
                        models = embed_models if embed_models else ["bge-large-en-v1.5"]
                    else:
                        models = all_models
                    return {
                        "connected": True,
                        "message": f"Groq API terhubung, {len(models)} model tersedia",
                        "models": models,
                    }

            elif provider == "local_whisper":
                url = _resolve_internal_url(base_url or settings.AI_STT_BASE_URL or "http://localhost:8002")
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{url.rstrip('/')}/v1/models")
                    if resp.status_code == 200:
                        data = resp.json()
                        models = [m["id"] for m in data.get("data", [])]
                        return {
                            "connected": True,
                            "message": f"Whisper Server terhubung, {len(models)} model tersedia",
                            "models": models,
                        }
                    else:
                        return {
                            "connected": False,
                            "message": f"Gagal tersambung ke Whisper (status {resp.status_code})",
                            "models": [],
                        }

            else:
                return {
                    "connected": False,
                    "message": f"Provider tidak dikenal: {provider}",
                    "models": [],
                }

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 401:
                msg = "API Key tidak valid (401 Unauthorized)"
            elif status == 403:
                msg = "Akses ditolak (403 Forbidden)"
            else:
                msg = f"HTTP Error {status}"
            return {"connected": False, "message": msg, "models": []}

        except Exception as e:
            return {"connected": False, "message": str(e), "models": []}


# Singleton
ai_provider_manager = AIProviderManager()
