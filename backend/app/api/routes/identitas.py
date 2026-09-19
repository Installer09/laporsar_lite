from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import os
import shutil
from pathlib import Path
import uuid
import logging
from app.core.security import verify_admin

logger = logging.getLogger(__name__)

from app.db.session import get_db, get_tenant
from app.models.settings_models import SystemSetting
from app.core.websocket import manager

router = APIRouter(redirect_slashes=False)

# KML/KMZ Upload directory
UPLOAD_DIR = Path("uploads/maps")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOGO_DIR = Path("uploads/identity")
LOGO_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_IDENTITAS = {
    "identitas_nama_instansi": "Kantor Pencarian dan Pertolongan Natuna",
    "identitas_motto": "We Are Family\nProfesional - Modern - Teruji",
    "identitas_wilayah_kerja": "Kabupaten Natuna, Kepulauan Riau, Indonesia",
    "identitas_kml_path": "",
    "identitas_logo_path": ""
}

@router.get("/identity")
async def get_identity(db: AsyncSession = Depends(get_db), tenant = Depends(get_tenant)):
    """Get the current identity and working area settings."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(DEFAULT_IDENTITAS.keys()))
    )
    settings = result.scalars().all()
    
    # Merge with defaults
    data = DEFAULT_IDENTITAS.copy()
    
    # Dynamic defaults based on active tenant name/slug
    if tenant:
        data["identitas_nama_instansi"] = tenant.name
        if tenant.slug == "pusat":
            data["identitas_wilayah_kerja"] = "Republik Indonesia"
            data["identitas_motto"] = "Avignam Jagat Samagram\nSelamatlah Alam Semesta"
            
    for setting in settings:
        if setting.value is not None and setting.value.strip() != "":
            data[setting.key] = setting.value
            
    # Self-healing KML path check
    kml_path = data.get("identitas_kml_path")
    if not kml_path or not os.path.exists(kml_path):
        # Stored file not found or empty. Scan for any existing KML/KMZ files in UPLOAD_DIR
        kml_files = list(UPLOAD_DIR.glob("batas_wilayah_*"))
        if not kml_files:
            kml_files = list(UPLOAD_DIR.glob("*.kml")) + list(UPLOAD_DIR.glob("*.kmz"))
            
        if kml_files:
            # Sort by modification time to get the newest file if there are multiple
            kml_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            actual_path = str(kml_files[0]).replace("\\", "/")
            logger.info(f"Self-healing KML path: Stored '{kml_path}' is empty or not found. Restoring path to existing file '{actual_path}'")
            
            result_kml = await db.execute(select(SystemSetting).where(SystemSetting.key == "identitas_kml_path"))
            setting_kml = result_kml.scalar_one_or_none()
            if setting_kml:
                setting_kml.value = actual_path
            else:
                setting_kml = SystemSetting(key="identitas_kml_path", value=actual_path)
                db.add(setting_kml)
                
            data["identitas_kml_path"] = actual_path
            try:
                await db.commit()
            except Exception as commit_err:
                await db.rollback()
                logger.error(f"Failed to commit self-healed KML path: {commit_err}")
                
    return data

@router.put("/identity", dependencies=[Depends(verify_admin)])
async def update_identity(payload: dict, db: AsyncSession = Depends(get_db)):
    """Update identity and working area settings."""
    for key, value in payload.items():
        if key not in DEFAULT_IDENTITAS:
            continue
            
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = str(value)
        else:
            new_setting = SystemSetting(key=key, value=str(value))
            db.add(new_setting)
            
    try:
        await db.commit()
        await manager.broadcast({"event": "identity_updated"}, db=db)
        return {"status": "success", "message": "Identitas berhasil diperbarui"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database transaction failed")

@router.post("/identity/kml", dependencies=[Depends(verify_admin)])
async def upload_kml(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload KML/KMZ file for map overlay."""
    if not file.filename.lower().endswith(('.kml', '.kmz')):
        raise HTTPException(status_code=400, detail="Hanya file .kml dan .kmz yang didukung")
        
    ext = ".kml" if file.filename.lower().endswith('.kml') else ".kmz"
    
    # Clean up existing KML/KMZ files first to prevent clutter
    for old_file in UPLOAD_DIR.glob("batas_wilayah_*"):
        try:
            os.remove(old_file)
        except Exception:
            pass
            
    safe_name = f"batas_wilayah_{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / safe_name
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Save path to settings
    path_str = str(file_path).replace("\\", "/")
    
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == "identitas_kml_path"))
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = path_str
    else:
        new_setting = SystemSetting(key="identitas_kml_path", value=path_str)
        db.add(new_setting)
        
    try:
        await db.commit()
        return {"status": "success", "message": "File batas wilayah berhasil diunggah", "path": path_str}
    except Exception as e:
        await db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Database transaction failed")

@router.delete("/identity/kml", dependencies=[Depends(verify_admin)])
async def delete_kml(db: AsyncSession = Depends(get_db)):
    """Remove KML/KMZ file."""
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == "identitas_kml_path"))
    setting = result.scalar_one_or_none()
    
    if setting and setting.value:
        try:
            # Delete physical file
            if os.path.exists(setting.value):
                os.remove(setting.value)
        except Exception as e:
            pass # Ignore if file missing
            
        setting.value = ""
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail="Database transaction failed")
        
    return {"status": "success", "message": "File batas wilayah berhasil dihapus"}

@router.post("/identity/logo", dependencies=[Depends(verify_admin)])
async def upload_logo(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload logo image for tenant identity."""
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Hanya file gambar (.png, .jpg, .jpeg) yang didukung")
        
    ext = Path(file.filename).suffix
    
    # Clean up existing logo files to prevent clutter
    for old_file in LOGO_DIR.glob("logo_*"):
        try:
            os.remove(old_file)
        except Exception:
            pass
            
    safe_name = f"logo_{uuid.uuid4().hex}{ext}"
    file_path = LOGO_DIR / safe_name
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    path_str = str(file_path).replace("\\", "/")
    
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == "identitas_logo_path"))
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = path_str
    else:
        new_setting = SystemSetting(key="identitas_logo_path", value=path_str)
        db.add(new_setting)
        
    try:
        await db.commit()
        await manager.broadcast({"event": "identity_updated"}, db=db)
        return {"status": "success", "message": "Logo berhasil diunggah", "path": path_str}
    except Exception as e:
        await db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Database transaction failed")

@router.delete("/identity/logo", dependencies=[Depends(verify_admin)])
async def delete_logo(db: AsyncSession = Depends(get_db)):
    """Remove custom logo."""
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == "identitas_logo_path"))
    setting = result.scalar_one_or_none()
    
    if setting and setting.value:
        try:
            if os.path.exists(setting.value):
                os.remove(setting.value)
        except Exception:
            pass
            
        setting.value = ""
        try:
            await db.commit()
            await manager.broadcast({"event": "identity_updated"}, db=db)
        except Exception:
            await db.rollback()
            raise HTTPException(status_code=500, detail="Database transaction failed")
            
    return {"status": "success", "message": "Logo berhasil dihapus"}
