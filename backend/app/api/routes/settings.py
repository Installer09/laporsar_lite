from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime
import httpx
import logging
import os
import uuid
import shutil
from pathlib import Path

from app.db.session import get_db, get_master_db, get_tenant, get_tenant_sessionmaker
from app.core.websocket import manager
from app.core.config import settings as app_settings
from app.core.security import verify_jwt, verify_admin, verify_operator_or_admin, verify_super_admin
from app.models.settings_models import SystemSetting, Location, Classification, User, FormatVariable, WidgetIntegrationRequest
from app.models.master_models import UserTenantMapping, Tenant
from app.schemas.settings_schemas import (
    SystemSettingBase, SystemSettingResponse, SystemSettingsBulkUpdate,
    LocationBase, LocationCreate, LocationResponse,
    ClassificationBase, ClassificationCreate, ClassificationResponse,
    UserBase, UserCreate, UserUpdate, UserResponse,
    FormatVariableBase, FormatVariableCreate, FormatVariableResponse,
    WidgetIntegrationRequestCreate, WidgetIntegrationRequestResponse,
    WidgetIntegrationRequestAdminCreate, WidgetIntegrationRequestUpdate
)

logger = logging.getLogger(__name__)
router = APIRouter(redirect_slashes=False)

# --- Settings ---
@router.get("/config", response_model=List[SystemSettingResponse], dependencies=[Depends(verify_admin)])
async def get_settings(db: AsyncSession = Depends(get_db)):
    app_settings.reload()
    result = await db.execute(select(SystemSetting))
    tenant_settings = {s.key: s for s in result.scalars().all()}
    
    tenant_slug = db.info.get("tenant_slug")
    if not tenant_slug:
        from app.db.session import tenant_context
        tenant_slug = tenant_context.get() or "pusat"

    # If tenant is not pusat, include inherited central AI settings if not customized locally
    if tenant_slug != "pusat":
        from app.core.tenant_config import get_pusat_settings, AI_SETTING_KEYS
        pusat_settings = await get_pusat_settings()
        for ai_key in AI_SETTING_KEYS:
            if ai_key not in tenant_settings and ai_key in pusat_settings:
                tenant_settings[ai_key] = SystemSetting(id=0, key=ai_key, value=pusat_settings[ai_key])

    # Fallback to runtime config / env for any keys not explicitly in DB (e.g. telegram_token, telegram_group)
    for db_key, env_attr in _ENV_TO_DB_MAP.items():
        if db_key not in tenant_settings and env_attr:
            val = getattr(app_settings, env_attr, "") or ""
            if val:
                tenant_settings[db_key] = SystemSetting(id=0, key=db_key, value=str(val))

    return list(tenant_settings.values())

@router.put("/config", response_model=dict)
async def update_settings(
    bulk_update: SystemSettingsBulkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_admin)
):
    from app.core.tenant_config import AI_SETTING_KEYS, invalidate_pusat_settings_cache

    is_super_admin = (
        current_user.get("role") == "Super Admin"
        or current_user.get("sub") == getattr(app_settings, "DEV_SUPERADMIN_USERNAME", "superadmin")
    )
    tenant_slug = db.info.get("tenant_slug") or current_user.get("tenant_slug") or "pusat"

    # Filter settings if user is not Super Admin (tenant admin cannot change central AI settings)
    settings_to_apply = []
    for s in bulk_update.settings:
        if s.key in AI_SETTING_KEYS and not is_super_admin:
            # Non-superadmin cannot overwrite central AI settings
            continue
        settings_to_apply.append(s)

    keys = [s.key for s in settings_to_apply]
    result = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(keys)))
    existing_settings = {s.key: s for s in result.scalars().all()}
    
    for setting_in in settings_to_apply:
        setting = existing_settings.get(setting_in.key)
        if setting:
            setting.value = setting_in.value
        else:
            new_setting = SystemSetting(key=setting_in.key, value=setting_in.value)
            db.add(new_setting)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

    # If pusat updated settings, invalidate cached AI settings for all tenants
    if tenant_slug == "pusat":
        invalidate_pusat_settings_cache()

    await manager.broadcast({"event": "settings_updated"}, db=db)
    return {"status": "success", "message": "Settings updated"}


# ---- Sync runtime config (.env) into the database ----

# Map of DB setting keys → runtime config attribute names
_ENV_TO_DB_MAP = {
    "telegram_token": "TELEGRAM_BOT_TOKEN",
    "telegram_group": "TELEGRAM_SAR_GROUP_ID",
    "wa_token": "WHATSAPP_API_TOKEN",
    "wa_phone_id": "WHATSAPP_PHONE_NUMBER_ID",
    "wa_group": "WHATSAPP_SAR_GROUP_ID",
    "wa_verify_token": "WHATSAPP_VERIFY_TOKEN",
    # AI Engine — LLM
    "ai_llm_provider": "AI_LLM_PROVIDER",
    "ai_llm_model": "AI_LLM_MODEL",
    "ai_llm_base_url": "AI_LLM_BASE_URL",
    "ai_llm_api_key": "AI_LLM_API_KEY",
    # AI Engine — Embedding (RAG)
    "ai_embed_provider": "AI_EMBED_PROVIDER",
    "ai_embed_model": "AI_EMBED_MODEL",
    "ai_embed_api_key": "AI_EMBED_API_KEY",
    # AI Engine — STT (Audio Whisper)
    "ai_stt_provider": "AI_STT_PROVIDER",
    "ai_stt_model": "AI_STT_MODEL",
    "ai_stt_api_key": "AI_STT_API_KEY",
    "ai_stt_base_url": "AI_STT_BASE_URL",
}

# Old keys to migrate from (v2.4 → v2.5)
_OLD_TO_NEW_KEY_MAP = {
    "ai_provider": "ai_llm_provider",
    "ai_model": "ai_llm_model",
    "ai_base_url": "ai_llm_base_url",
    "ai_api_key": "ai_llm_api_key",
    "ai_stt_model": "ai_stt_model",  # same key, just keep
}


@router.post("/config/sync", dependencies=[Depends(verify_super_admin)])
async def sync_config_from_env(db: AsyncSession = Depends(get_db)):
    """
    Seed the system_settings table with actual runtime values from the
    .env / Pydantic Settings. This ensures the dashboard reflects the
    real running configuration. Only populates keys that are currently
    empty or missing in the database.

    Also migrates old v2.4 AI keys (ai_provider, ai_model, etc.) to
    new v2.5 keys (ai_llm_provider, ai_llm_model, etc.).
    """
    synced = []

    # Batch query all settings keys to optimize performance
    keys_to_query = list(_OLD_TO_NEW_KEY_MAP.keys()) + list(_OLD_TO_NEW_KEY_MAP.values()) + list(_ENV_TO_DB_MAP.keys())
    db_result = await db.execute(select(SystemSetting).where(SystemSetting.key.in_(keys_to_query)))
    existing_settings = {s.key: s for s in db_result.scalars().all()}

    # --- Step 0: Migrate old keys if they exist ---
    for old_key, new_key in _OLD_TO_NEW_KEY_MAP.items():
        try:
            old_setting = existing_settings.get(old_key)
            if old_setting and old_setting.value:
                # Check if new key already exists
                new_setting = existing_settings.get(new_key)
                if new_setting:
                    if not new_setting.value or new_setting.value.strip() == "":
                        new_setting.value = old_setting.value
                        synced.append(f"{old_key}->{new_key}")
                else:
                    new_row = SystemSetting(key=new_key, value=old_setting.value)
                    db.add(new_row)
                    existing_settings[new_key] = new_row
                    synced.append(f"{old_key}->{new_key}")
        except Exception as e:
            logger.warning(f"Migration of {old_key} failed: {e}")

    # --- Step 1: Seed from env ---
    for db_key, env_attr in _ENV_TO_DB_MAP.items():
        # Get the runtime value
        if env_attr:
            runtime_val = getattr(app_settings, env_attr, "") or ""
        else:
            runtime_val = ""

        # Check if already in DB
        existing = existing_settings.get(db_key)

        if existing:
            # Only update if DB value is empty and runtime has a value
            if (not existing.value or existing.value.strip() == "") and runtime_val:
                existing.value = runtime_val
                synced.append(db_key)
        else:
            # Insert new row
            if runtime_val:
                new_row = SystemSetting(key=db_key, value=runtime_val)
                db.add(new_row)
                existing_settings[db_key] = new_row
                synced.append(db_key)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to sync config: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")
    logger.info(f"Config sync: seeded {len(synced)} settings from env: {synced}")
    return {"status": "success", "synced_keys": synced, "count": len(synced)}


# ---- Live Status Checks ----

@router.get("/config/live-status", dependencies=[Depends(verify_admin)])
async def get_live_status(db: AsyncSession = Depends(get_db)):
    """
    Return real-time connectivity status for all integrations.
    Checks Ollama, Telegram bot, WhatsApp API, and Whisper STT.
    """
    from app.core.tenant_config import get_tenant_settings
    
    app_settings.reload()
    tenant_settings = await get_tenant_settings(db)
    
    status_result = {
        "ollama": {"connected": False, "models": [], "url": "", "error": ""},
        "ai_engine": {"connected": False, "provider": "", "model": "", "error": ""},
        "telegram": {"connected": False, "bot_name": "", "error": ""},
        "whatsapp": {"connected": False, "error": ""},
        "whisper": {"connected": False, "provider": "", "model": "", "error": ""},
    }

    from app.services.ai_providers import _resolve_internal_url

    # --- AI Engine (LLM & RAG) ---
    llm_provider = tenant_settings.AI_LLM_PROVIDER or "gemini"
    llm_model = tenant_settings.AI_LLM_MODEL or "gemini-1.5-flash"
    status_result["ai_engine"]["provider"] = llm_provider
    status_result["ai_engine"]["model"] = llm_model

    if llm_provider in ("gemini", "groq", "openai", "claude"):
        api_key = tenant_settings.AI_LLM_API_KEY
        if api_key:
            status_result["ai_engine"]["connected"] = True
            # Backward compatibility with existing frontend ollama status key
            status_result["ollama"]["connected"] = True
            status_result["ollama"]["models"] = [llm_model]
        else:
            status_result["ai_engine"]["error"] = "API Key belum dikonfigurasi"
    elif llm_provider == "ollama":
        ollama_url = tenant_settings.AI_LLM_BASE_URL or tenant_settings.OLLAMA_HOST or "http://localhost:11434"
        status_result["ollama"]["url"] = ollama_url
        resolved_ollama_url = _resolve_internal_url(ollama_url)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{resolved_ollama_url.rstrip('/')}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                status_result["ollama"]["connected"] = True
                status_result["ollama"]["models"] = models
                status_result["ai_engine"]["connected"] = True
        except Exception as e:
            status_result["ollama"]["error"] = str(e)
            status_result["ai_engine"]["error"] = str(e)

    # --- Telegram ---
    tg_token = tenant_settings.TELEGRAM_BOT_TOKEN
    if tg_token:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://api.telegram.org/bot{tg_token}/getMe"
                )
                if resp.status_code == 200:
                    bot_data = resp.json().get("result", {})
                    status_result["telegram"]["connected"] = True
                    status_result["telegram"]["bot_name"] = (
                        f"@{bot_data.get('username', '')}  ({bot_data.get('first_name', '')})"
                    )
                else:
                    status_result["telegram"]["error"] = f"HTTP {resp.status_code}"
        except Exception as e:
            status_result["telegram"]["error"] = str(e)
    else:
        status_result["telegram"]["error"] = "Token belum dikonfigurasi"

    # --- WhatsApp ---
    wa_token = tenant_settings.WHATSAPP_API_TOKEN
    wa_phone_id = tenant_settings.WHATSAPP_PHONE_NUMBER_ID
    if wa_token and wa_phone_id:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://graph.facebook.com/v19.0/{wa_phone_id}",
                    headers={"Authorization": f"Bearer {wa_token}"},
                )
                status_result["whatsapp"]["connected"] = resp.status_code == 200
                if resp.status_code != 200:
                    status_result["whatsapp"]["error"] = f"HTTP {resp.status_code}"
        except Exception as e:
            status_result["whatsapp"]["error"] = str(e)
    else:
        status_result["whatsapp"]["error"] = "Token/Phone ID belum dikonfigurasi"

    # --- Whisper (STT) ---
    stt_provider = tenant_settings.AI_STT_PROVIDER or "ollama"
    stt_model = tenant_settings.AI_STT_MODEL or "whisper"
    status_result["whisper"]["provider"] = stt_provider
    status_result["whisper"]["model"] = stt_model

    if stt_provider == "local_whisper":
        whisper_url = tenant_settings.AI_STT_BASE_URL or "http://localhost:8002"
        resolved_whisper_url = _resolve_internal_url(whisper_url)
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{resolved_whisper_url.rstrip('/')}/v1/models")
                status_result["whisper"]["connected"] = resp.status_code == 200
                if resp.status_code != 200:
                    status_result["whisper"]["error"] = f"HTTP {resp.status_code}"
        except Exception as e:
            status_result["whisper"]["error"] = str(e)
    elif stt_provider == "ollama":
        status_result["whisper"]["connected"] = status_result["ollama"]["connected"]
        status_result["whisper"]["error"] = status_result["ollama"]["error"]
    elif stt_provider in ("openai", "groq", "gemini"):
        stt_key = tenant_settings.AI_STT_API_KEY
        if not stt_key and stt_provider == tenant_settings.AI_LLM_PROVIDER:
            stt_key = tenant_settings.AI_LLM_API_KEY
        if stt_key:
            status_result["whisper"]["connected"] = True
        else:
            status_result["whisper"]["error"] = "API Key belum dikonfigurasi"

    return status_result


@router.get("/ollama-models", dependencies=[Depends(verify_admin)])
async def get_ollama_models(base_url: str = Query(None)):
    """Get list of available Ollama models. Falls back to AI_LLM_BASE_URL from env."""
    from app.services.ai_providers import _resolve_internal_url
    app_settings.reload()
    url = base_url or app_settings.AI_LLM_BASE_URL or app_settings.OLLAMA_HOST or "http://localhost:11434"
    resolved_url = _resolve_internal_url(url)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{resolved_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            return {"models": models, "url": url}
    except Exception as e:
        return {"models": [], "error": str(e), "url": url}


@router.post("/ai-test-connection", dependencies=[Depends(verify_admin)])
async def test_ai_connection(payload: dict):
    """
    Test connectivity to a specific AI provider.
    Payload: {"provider": "openai", "api_key": "sk-...", "base_url": "..."}
    Returns: {"connected": bool, "message": str, "models": list}
    """
    from app.services.ai_providers import ai_provider_manager

    provider = payload.get("provider", "ollama")
    api_key = payload.get("api_key", "")
    base_url = payload.get("base_url", "")
    engine_type = payload.get("engine_type", "llm")

    result = await ai_provider_manager.test_connection(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        engine_type=engine_type,
    )
    return result


# --- Locations ---
@router.get("/locations", response_model=List[LocationResponse], dependencies=[Depends(verify_jwt)])
async def get_locations(
    db: AsyncSession = Depends(get_db),
    db_master: AsyncSession = Depends(get_master_db),
    tenant = Depends(get_tenant)
):
    if tenant and tenant.slug == "pusat":
        # Aggregate from all active tenants
        result_tenants = await db_master.execute(
            select(Tenant).where(Tenant.is_active == True)
        )
        tenants = result_tenants.scalars().all()
        
        all_locations = []
        import asyncio
        
        async def fetch_tenant_locations(t):
            locs = []
            try:
                session_maker = get_tenant_sessionmaker(t.db_url)
                async with session_maker() as tenant_db:
                    res = await tenant_db.execute(select(Location))
                    db_locs = res.scalars().all()
                    for loc in db_locs:
                        loc_dict = {
                            "id": t.id * 10000 + loc.id,
                            "name": loc.name,
                            "type": loc.type,
                            "lat": loc.lat,
                            "lng": loc.lng,
                            "address": loc.address,
                            "unsur": loc.unsur,
                            "alut": loc.alut,
                            "icon": loc.icon,
                            "tenant_name": t.name,
                            "tenant_slug": t.slug
                        }
                        locs.append(loc_dict)
            except Exception as e:
                logger.error(f"Failed to fetch locations for tenant {t.slug}: {e}")
            return locs

        results = await asyncio.gather(*[fetch_tenant_locations(t) for t in tenants])
        for r in results:
            all_locations.extend(r)
            
        return all_locations
    else:
        result = await db.execute(select(Location))
        return result.scalars().all()

@router.post("/locations", response_model=LocationResponse, dependencies=[Depends(verify_admin)])
async def create_location(location: LocationCreate, db: AsyncSession = Depends(get_db)):
    new_location = Location(**location.model_dump())
    db.add(new_location)
    try:
        await db.commit()
        await db.refresh(new_location)
        return new_location
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create location: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

@router.put("/locations/{location_id}", response_model=LocationResponse, dependencies=[Depends(verify_admin)])
async def update_location(
    location_id: int, 
    location_update: LocationCreate, 
    db: AsyncSession = Depends(get_db),
    db_master: AsyncSession = Depends(get_master_db),
    tenant = Depends(get_tenant)
):
    target_db = db
    target_loc_id = location_id
    external_session = None
    t = None

    if tenant and tenant.slug == "pusat" and location_id >= 10000:
        tenant_id = location_id // 10000
        target_loc_id = location_id % 10000
        
        result_tenant = await db_master.execute(select(Tenant).where(Tenant.id == tenant_id))
        t = result_tenant.scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Tenant not found for this location")
            
        session_maker = get_tenant_sessionmaker(t.db_url)
        external_session = session_maker()
        target_db = external_session

    try:
        result = await target_db.execute(select(Location).where(Location.id == target_loc_id))
        db_location = result.scalar_one_or_none()
        if not db_location:
            raise HTTPException(status_code=404, detail="Location not found")
        
        for key, value in location_update.model_dump().items():
            setattr(db_location, key, value)
        
        await target_db.commit()
        await target_db.refresh(db_location)
        
        if external_session:
            response_data = {
                "id": location_id,
                "name": db_location.name,
                "type": db_location.type,
                "lat": db_location.lat,
                "lng": db_location.lng,
                "address": db_location.address,
                "unsur": db_location.unsur,
                "alut": db_location.alut,
                "icon": db_location.icon,
                "tenant_name": t.name,
                "tenant_slug": t.slug
            }
            return response_data
            
        return db_location
    except Exception as e:
        await target_db.rollback()
        logger.error(f"Failed to update location: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")
    finally:
        if external_session:
            await external_session.close()

@router.delete("/locations/{location_id}", dependencies=[Depends(verify_admin)])
async def delete_location(
    location_id: int, 
    db: AsyncSession = Depends(get_db),
    db_master: AsyncSession = Depends(get_master_db),
    tenant = Depends(get_tenant)
):
    target_db = db
    target_loc_id = location_id
    external_session = None

    if tenant and tenant.slug == "pusat" and location_id >= 10000:
        tenant_id = location_id // 10000
        target_loc_id = location_id % 10000
        
        result_tenant = await db_master.execute(select(Tenant).where(Tenant.id == tenant_id))
        t = result_tenant.scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Tenant not found for this location")
            
        session_maker = get_tenant_sessionmaker(t.db_url)
        external_session = session_maker()
        target_db = external_session

    try:
        result = await target_db.execute(select(Location).where(Location.id == target_loc_id))
        db_location = result.scalar_one_or_none()
        if not db_location:
            raise HTTPException(status_code=404, detail="Location not found")
        
        await target_db.delete(db_location)
        await target_db.commit()
        return {"status": "success", "message": "Location deleted"}
    except Exception as e:
        await target_db.rollback()
        logger.error(f"Failed to delete location: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")
    finally:
        if external_session:
            await external_session.close()

# --- Location Icon Upload ---
ICON_UPLOAD_DIR = Path("uploads/i")
ICON_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/locations/icon", dependencies=[Depends(verify_admin)])
async def upload_location_icon(file: UploadFile = File(...)):
    """Upload custom image icon for POS/Unit SAR."""
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hanya file gambar (.png, .jpg, .jpeg, .gif, .svg, .webp) yang didukung"
        )
        
    ext = Path(file.filename).suffix.lower()
    safe_name = f"icon_{uuid.uuid4().hex[:12]}{ext}"
    file_path = ICON_UPLOAD_DIR / safe_name
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    path_str = f"uploads/i/{safe_name}"
    return {"status": "success", "url": path_str}

# --- Classifications ---
@router.get("/classifications", response_model=List[ClassificationResponse], dependencies=[Depends(verify_jwt)])
async def get_classifications(db: AsyncSession = Depends(get_db)):
    if not db:
        return []
    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    master_classifications = []
    
    # 1. Fetch from Master DB if tenant is not global
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(select(Classification))
                m_classes = m_res.scalars().all()
                for c in m_classes:
                    c.is_global = True
                    master_classifications.append(c)
        except Exception as e:
            logger.warning(f"Failed to fetch global classifications from Master DB: {e}")

    # 2. Fetch from Tenant DB
    tenant_classifications = []
    try:
        t_res = await db.execute(select(Classification))
        t_classes = t_res.scalars().all()
        for c in t_classes:
            c.is_global = False
            tenant_classifications.append(c)
    except Exception as e:
        logger.warning(f"Failed to fetch tenant classifications from Tenant DB: {e}")

    # 3. Merge: Tenant overrides Master
    merged = {}
    for c in master_classifications:
        if c.category:
            merged[c.category.lower().strip()] = c
    for c in tenant_classifications:
        if c.category:
            merged[c.category.lower().strip()] = c

    # Sort merged results by category
    sorted_list = sorted(list(merged.values()), key=lambda x: x.category or "")
    return sorted_list

@router.post("/classifications", response_model=ClassificationResponse, dependencies=[Depends(verify_admin)])
async def create_classification(classification: ClassificationCreate, db: AsyncSession = Depends(get_db)):
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")
    new_class = Classification(**classification.model_dump())
    db.add(new_class)
    try:
        await db.commit()
        await db.refresh(new_class)
        new_class.is_global = False
        return new_class
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create classification: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

@router.put("/classifications/{class_id}", response_model=ClassificationResponse, dependencies=[Depends(verify_admin)])
async def update_classification(class_id: int, class_update: ClassificationCreate, db: AsyncSession = Depends(get_db)):
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")
        
    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    # Block direct modifications of global classifications if they exist in Master DB
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(select(Classification).where(Classification.id == class_id))
                if m_res.scalar_one_or_none():
                    raise HTTPException(
                        status_code=403, 
                        detail="Klasifikasi pusat bersifat Read-Only. Untuk menyesuaikan, tambahkan klasifikasi baru dengan nama yang sama."
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking global classification: {e}")

    result = await db.execute(select(Classification).where(Classification.id == class_id))
    db_class = result.scalar_one_or_none()
    if not db_class:
        raise HTTPException(status_code=404, detail="Classification not found in tenant database")
    
    for key, value in class_update.model_dump().items():
        setattr(db_class, key, value)
    
    try:
        await db.commit()
        await db.refresh(db_class)
        db_class.is_global = False
        return db_class
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update classification: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

@router.delete("/classifications/{class_id}", dependencies=[Depends(verify_admin)])
async def delete_classification(class_id: int, db: AsyncSession = Depends(get_db)):
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")
        
    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    # Block direct deletion of global classifications if they exist in Master DB
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(select(Classification).where(Classification.id == class_id))
                if m_res.scalar_one_or_none():
                    raise HTTPException(
                        status_code=403, 
                        detail="Klasifikasi pusat bersifat Read-Only dan tidak dapat dihapus."
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking global classification: {e}")

    result = await db.execute(select(Classification).where(Classification.id == class_id))
    db_class = result.scalar_one_or_none()
    if not db_class:
        raise HTTPException(status_code=404, detail="Classification not found in tenant database")
    
    await db.delete(db_class)
    try:
        await db.commit()
        return {"status": "success", "message": "Classification deleted"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete classification: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")

# --- Users ---
@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(verify_admin)])
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()

@router.post("/users", response_model=UserResponse, dependencies=[Depends(verify_admin)])
async def create_user(
    user: UserCreate, 
    db: AsyncSession = Depends(get_db),
    db_master: AsyncSession = Depends(get_master_db),
    tenant = Depends(get_tenant)
):
    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant context missing")

    if user.role == "Super Admin" and tenant.slug != "pusat":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya Kantor SAR Pusat yang dapat menunjuk Super Admin."
        )

    email_clean = user.email.lower().strip()

    # Enforce global uniqueness in Master DB
    map_result = await db_master.execute(
        select(UserTenantMapping).where(UserTenantMapping.email == email_clean)
    )
    if map_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered globally")

    from app.core.security import get_password_hash
    hashed_pwd = get_password_hash(user.password)
    new_user = User(
        name=user.name, 
        email=user.email, 
        phone=user.phone,
        nip=user.nip,
        jabatan=user.jabatan,
        role=user.role, 
        hashed_password=hashed_pwd,
        is_active=True,
        is_verified=False
    )
    
    new_mapping = UserTenantMapping(
        email=email_clean,
        tenant_slug=tenant.slug
    )

    # Commit to master mapping registry first
    try:
        db_master.add(new_mapping)
        await db_master.commit()
    except Exception as master_err:
        await db_master.rollback()
        await db.rollback()
        logger.error(f"Failed to commit master mapping registry during user creation: {master_err}")
        raise HTTPException(status_code=500, detail="Database transaction failed on master registry")

    # Commit to tenant DB
    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user
    except Exception as tenant_err:
        await db.rollback()
        logger.error(f"Tenant DB commit failed during user creation, triggering compensator on master: {tenant_err}")
        
        # Compensating transaction to delete mapping from master DB
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as compensating_session:
                stmt = select(UserTenantMapping).where(
                    UserTenantMapping.email == email_clean
                )
                res = await compensating_session.execute(stmt)
                m = res.scalar_one_or_none()
                if m:
                    await compensating_session.delete(m)
                    await compensating_session.commit()
                    logger.info(f"Successfully cleaned up master mapping for {email_clean} after user create failure")
        except Exception as comp_err:
            logger.error(f"CRITICAL: Failed to clean up master registry mapping for {email_clean}: {comp_err}")
            
        raise HTTPException(status_code=500, detail="Database transaction failed on tenant database")

@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(verify_admin)])
async def update_user(
    user_id: int, 
    user_update: UserUpdate, 
    db: AsyncSession = Depends(get_db),
    db_master: AsyncSession = Depends(get_master_db),
    tenant = Depends(get_tenant)
):
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_email = db_user.email.lower().strip() if db_user.email else None
    new_email = user_update.email.lower().strip() if user_update.email else None

    # If email changes, check uniqueness and update master mapping
    if new_email and new_email != old_email:
        map_result = await db_master.execute(
            select(UserTenantMapping).where(UserTenantMapping.email == new_email)
        )
        if map_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered globally")
        
        # Update existing or create new mapping
        if old_email:
            old_map_result = await db_master.execute(
                select(UserTenantMapping).where(UserTenantMapping.email == old_email)
            )
            old_map = old_map_result.scalar_one_or_none()
            if old_map:
                old_map.email = new_email
            else:
                db_master.add(UserTenantMapping(email=new_email, tenant_slug=tenant.slug))
        else:
            db_master.add(UserTenantMapping(email=new_email, tenant_slug=tenant.slug))

    if user_update.name is not None: db_user.name = user_update.name
    if user_update.email is not None: db_user.email = user_update.email
    if user_update.phone is not None: db_user.phone = user_update.phone
    if user_update.nip is not None: db_user.nip = user_update.nip
    if user_update.jabatan is not None: db_user.jabatan = user_update.jabatan
    if user_update.role is not None: 
        if user_update.role == "Super Admin" and tenant.slug != "pusat":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hanya Kantor SAR Pusat yang dapat menunjuk Super Admin."
            )
        db_user.role = user_update.role
    if user_update.is_active is not None: db_user.is_active = user_update.is_active
    if user_update.is_verified is not None: db_user.is_verified = user_update.is_verified
    
    if user_update.password and user_update.password.strip(): 
        from app.core.security import get_password_hash
        db_user.hashed_password = get_password_hash(user_update.password.strip())
    
    # Commit to master mapping registry first
    try:
        await db_master.commit()
    except Exception as master_err:
        await db_master.rollback()
        await db.rollback()
        logger.error(f"Failed to commit master mapping registry during user update: {master_err}")
        raise HTTPException(status_code=500, detail="Database transaction failed on master registry")

    # Commit to tenant DB
    try:
        await db.commit()
        await db.refresh(db_user)
        return db_user
    except Exception as tenant_err:
        await db.rollback()
        logger.error(f"Tenant DB commit failed during user update, triggering compensator on master: {tenant_err}")
        
        # Compensating transaction to restore old email mapping in master DB
        if new_email and new_email != old_email:
            try:
                from app.db.session import MasterSessionLocal
                async with MasterSessionLocal() as compensating_session:
                    stmt = select(UserTenantMapping).where(
                        UserTenantMapping.email == new_email
                    )
                    res = await compensating_session.execute(stmt)
                    m = res.scalar_one_or_none()
                    if m:
                        if old_email:
                            m.email = old_email
                        else:
                            await compensating_session.delete(m)
                        await compensating_session.commit()
                        logger.info(f"Successfully restored master mapping back to {old_email or 'deleted'}")
            except Exception as comp_err:
                logger.error(f"CRITICAL: Failed to clean up master registry mapping during user update fallback: {comp_err}")
                
        raise HTTPException(status_code=500, detail="Database transaction failed on tenant database")

@router.delete("/users/{user_id}", dependencies=[Depends(verify_admin)])
async def delete_user(
    user_id: int, 
    db: AsyncSession = Depends(get_db),
    db_master: AsyncSession = Depends(get_master_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    email_clean = db_user.email.lower().strip() if db_user.email else None
    
    try:
        # Commit tenant DB delete first
        await db.delete(db_user)
        await db.commit()
    except Exception as tenant_err:
        await db.rollback()
        await db_master.rollback()
        logger.error(f"Failed to delete user from tenant DB: {tenant_err}")
        raise HTTPException(status_code=500, detail="Failed to delete user from tenant database")

    # If tenant DB delete succeeds, proceed to delete master registry mapping
    if email_clean:
        try:
            map_result = await db_master.execute(
                select(UserTenantMapping).where(UserTenantMapping.email == email_clean)
            )
            mapping = map_result.scalar_one_or_none()
            if mapping:
                await db_master.delete(mapping)
                await db_master.commit()
        except Exception as master_err:
            await db_master.rollback()
            logger.error(f"CRITICAL: Failed to delete user mapping from master registry for {email_clean}: {master_err}")
            # Note: We don't raise error because tenant user is already deleted.
            # But we log the critical failure so super admins can prune manually.


# --- Widget Integration Requests ---

@router.post("/widget-requests", response_model=WidgetIntegrationRequestResponse)
async def create_widget_request(
    req: WidgetIntegrationRequestCreate,
    db: AsyncSession = Depends(get_db)
):
    """Public endpoint for external users/partners to submit a widget integration request."""
    check_query = select(WidgetIntegrationRequest).where(
        WidgetIntegrationRequest.website_url == req.website_url
    )
    result = await db.execute(check_query)
    existing = result.scalars().first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Sebuah pengajuan untuk domain website ini sudah ada."
        )

    db_req = WidgetIntegrationRequest(
        partner_name=req.partner_name,
        website_url=req.website_url,
        official_email=req.official_email,
        official_phone=req.official_phone,
        status="PENDING",
    )
    db.add(db_req)
    try:
        await db.commit()
        await db.refresh(db_req)
        return db_req
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create widget integration request: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan pengajuan")


@router.get("/widget-requests", response_model=List[WidgetIntegrationRequestResponse], dependencies=[Depends(verify_admin)])
async def get_widget_requests(db: AsyncSession = Depends(get_db)):
    """Admin/Operator endpoint to list all widget integration requests."""
    result = await db.execute(
        select(WidgetIntegrationRequest).order_by(WidgetIntegrationRequest.created_at.desc())
    )
    return result.scalars().all()


@router.post("/widget-requests/{request_id}/approve", response_model=WidgetIntegrationRequestResponse)
async def approve_widget_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(verify_admin)
):
    """Admin/Operator endpoint to approve a widget integration request and generate an API Key."""
    result = await db.execute(
        select(WidgetIntegrationRequest).where(WidgetIntegrationRequest.id == request_id)
    )
    db_req = result.scalar_one_or_none()
    if not db_req:
        raise HTTPException(status_code=404, detail="Pengajuan integrasi tidak ditemukan")

    if db_req.status != "PENDING":
        raise HTTPException(status_code=400, detail="Pengajuan sudah diproses")

    # Generate a unique secure API Key
    api_key = f"sar_{uuid.uuid4().hex}"
    
    db_req.api_key = api_key
    db_req.status = "APPROVED"
    db_req.verified_at = datetime.now()
    db_req.verified_by = current_user.get("user_id")

    try:
        await db.commit()
        await db.refresh(db_req)
        return db_req
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to approve widget request {request_id}: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyetujui pengajuan")


@router.post("/widget-requests/{request_id}/reject", response_model=WidgetIntegrationRequestResponse)
async def reject_widget_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(verify_admin)
):
    """Admin/Operator endpoint to reject a widget integration request."""
    result = await db.execute(
        select(WidgetIntegrationRequest).where(WidgetIntegrationRequest.id == request_id)
    )
    db_req = result.scalar_one_or_none()
    if not db_req:
        raise HTTPException(status_code=404, detail="Pengajuan integrasi tidak ditemukan")

    if db_req.status != "PENDING":
        raise HTTPException(status_code=400, detail="Pengajuan sudah diproses")

    db_req.status = "REJECTED"
    db_req.verified_at = datetime.now()
    db_req.verified_by = current_user.get("user_id")

    try:
        await db.commit()
        await db.refresh(db_req)
        return db_req
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to reject widget request {request_id}: {e}")
        raise HTTPException(status_code=500, detail="Gagal menolak pengajuan")


@router.post("/widget-requests/admin", response_model=WidgetIntegrationRequestResponse)
async def create_widget_request_admin(
    req: WidgetIntegrationRequestAdminCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(verify_admin)
):
    """Admin/Operator endpoint to manually create a widget integration request."""
    check_query = select(WidgetIntegrationRequest).where(
        WidgetIntegrationRequest.website_url == req.website_url
    )
    result = await db.execute(check_query)
    existing = result.scalars().first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Sebuah pengajuan untuk domain website ini sudah ada."
        )

    db_req = WidgetIntegrationRequest(
        partner_name=req.partner_name,
        website_url=req.website_url,
        official_email=req.official_email,
        official_phone=req.official_phone,
        status=req.status,
    )
    
    if req.status == "APPROVED":
        db_req.api_key = f"sar_{uuid.uuid4().hex}"
        db_req.verified_at = datetime.now()
        db_req.verified_by = current_user.get("user_id")

    db.add(db_req)
    try:
        await db.commit()
        await db.refresh(db_req)
        return db_req
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create widget integration request by admin: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan pengajuan")


@router.put("/widget-requests/{request_id}", response_model=WidgetIntegrationRequestResponse)
async def update_widget_request(
    request_id: int,
    req_update: WidgetIntegrationRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(verify_admin)
):
    """Admin/Operator endpoint to update a widget integration request."""
    result = await db.execute(
        select(WidgetIntegrationRequest).where(WidgetIntegrationRequest.id == request_id)
    )
    db_req = result.scalar_one_or_none()
    if not db_req:
        raise HTTPException(status_code=404, detail="Pengajuan integrasi tidak ditemukan")

    # Update fields if provided
    if req_update.partner_name is not None:
        db_req.partner_name = req_update.partner_name
    if req_update.website_url is not None:
        # Check domain collision if domain changes
        if req_update.website_url != db_req.website_url:
            check_query = select(WidgetIntegrationRequest).where(
                WidgetIntegrationRequest.website_url == req_update.website_url
            )
            collision_result = await db.execute(check_query)
            collision = collision_result.scalars().first()
            if collision:
                raise HTTPException(
                    status_code=400,
                    detail="Sebuah pengajuan untuk domain website ini sudah ada."
                )
        db_req.website_url = req_update.website_url
    if req_update.official_email is not None:
        db_req.official_email = req_update.official_email
    if req_update.official_phone is not None:
        db_req.official_phone = req_update.official_phone
        
    if req_update.status is not None:
        new_status = req_update.status
        db_req.status = new_status
        
        if new_status == "APPROVED":
            if not db_req.api_key:
                db_req.api_key = f"sar_{uuid.uuid4().hex}"
            db_req.verified_at = datetime.now()
            db_req.verified_by = current_user.get("user_id")
        else:
            db_req.api_key = None
            db_req.verified_at = None
            db_req.verified_by = None

    try:
        await db.commit()
        await db.refresh(db_req)
        return db_req
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update widget request {request_id}: {e}")
        raise HTTPException(status_code=500, detail="Gagal memperbarui pengajuan")


@router.delete("/widget-requests/{request_id}", dependencies=[Depends(verify_admin)])
async def delete_widget_request(
    request_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Admin/Operator endpoint to delete/revoke a widget integration request."""
    result = await db.execute(
        select(WidgetIntegrationRequest).where(WidgetIntegrationRequest.id == request_id)
    )
    db_req = result.scalar_one_or_none()
    if not db_req:
        raise HTTPException(status_code=404, detail="Pengajuan integrasi tidak ditemukan")

    await db.delete(db_req)
    try:
        await db.commit()
        return {"status": "success", "message": "Widget integration request deleted"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete widget request {request_id}: {e}")
        raise HTTPException(status_code=500, detail="Gagal menghapus pengajuan")

