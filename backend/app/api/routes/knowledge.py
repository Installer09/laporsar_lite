from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func as sa_func, delete
from typing import List, Optional
import os
import uuid
from datetime import datetime
import logging
import csv
import io
import json
import enum
from app.services.rule_extractor import RuleExtractor
from app.services.ai_providers import ai_provider_manager
from app.services.llm_rag import llm_rag_service

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.models.knowledge_models import DictionaryWord, DictionaryStatus, SOPDocument, SOPDocStatus
from app.schemas.knowledge_schemas import (
    DictionaryWordCreate, DictionaryWordUpdate, DictionaryWordResponse,
    DictionaryBulkAction, SOPDocumentResponse
)
from app.core.security import verify_jwt, verify_admin, verify_operator_or_admin
from app.core.rate_limiter import sanitize_csv_cell

router = APIRouter()

# ============================================================
# DICTIONARY ENDPOINTS
# ============================================================

@router.get("/dictionary/stats", dependencies=[Depends(verify_operator_or_admin)])
async def get_dictionary_stats(db: AsyncSession = Depends(get_db)):
    """Get summary statistics for the dictionary in a single query."""
    if not db:
        return {"total": 0, "pending": 0, "approved": 0}
    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    master_words = []
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(select(DictionaryWord))
                master_words = m_res.scalars().all()
        except Exception as e:
            logger.warning(f"Failed to fetch global dictionary for stats: {e}")

    tenant_words = []
    try:
        t_res = await db.execute(select(DictionaryWord))
        tenant_words = t_res.scalars().all()
    except Exception as e:
        logger.warning(f"Failed to fetch tenant dictionary for stats: {e}")

    # Merge
    merged = {}
    for w in master_words:
        if w.word:
            merged[w.word.lower().strip()] = w
    for w in tenant_words:
        if w.word:
            merged[w.word.lower().strip()] = w

    total = len(merged)
    pending = sum(1 for w in merged.values() if w.status == DictionaryStatus.PENDING)
    approved = sum(1 for w in merged.values() if w.status == DictionaryStatus.APPROVED)
    
    return {"total": total, "pending": pending, "approved": approved}


@router.get("/dictionary", response_model=List[DictionaryWordResponse], dependencies=[Depends(verify_operator_or_admin)])
async def get_dictionary(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, APPROVED, REJECTED"),
    search: Optional[str] = Query(None, description="Search by word"),
    category: Optional[str] = Query(None, description="Filter by category: SARANA_ALUT, JENIS_INSIDEN, KONDISI_KORBAN, MEDAN_PERAIRAN, OPERASIONAL_SAR, SLANG_DIALEK"),
    word_type: Optional[str] = Query(None, description="Filter by type: ABBREVIATION, JARGON, GENERAL"),
    auto_only: Optional[bool] = Query(None, description="True = only auto-detected terms"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Pagination limit"),
    db: AsyncSession = Depends(get_db)
):
    """List all dictionary words with optional filtering."""
    if not isinstance(skip, int):
        skip = 0
    if not isinstance(limit, int):
        limit = 100

    if not db:
        return []
    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    master_words = []
    
    # Query builder helper
    def build_query():
        query = select(DictionaryWord).order_by(DictionaryWord.created_at.desc())
        if status and isinstance(status, str):
            query = query.where(DictionaryWord.status == status)
        if search and isinstance(search, str):
            query = query.where(DictionaryWord.word.ilike(f"%{search}%"))
        if category and isinstance(category, str) and category != "ALL":
            query = query.where(DictionaryWord.category == category)
        if word_type and isinstance(word_type, str):
            query = query.where(DictionaryWord.word_type == word_type.upper())
        if auto_only is not None and isinstance(auto_only, bool):
            query = query.where(DictionaryWord.is_auto_detected == auto_only)
        return query

    # 1. Fetch from Master DB if tenant is not global
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(build_query())
                m_words = m_res.scalars().all()
                for w in m_words:
                    w.is_global = True
                    w.has_vector = bool(w.embedding is not None)
                    master_words.append(w)
        except Exception as e:
            logger.warning(f"Failed to fetch global dictionary from Master DB: {e}")

    # 2. Fetch from Tenant DB
    tenant_words = []
    try:
        t_res = await db.execute(build_query())
        t_words = t_res.scalars().all()
        for w in t_words:
            w.is_global = False
            w.has_vector = bool(w.embedding is not None)
            tenant_words.append(w)
    except Exception as e:
        logger.warning(f"Failed to fetch tenant dictionary from Tenant DB: {e}")

    # 3. Merge: Tenant overrides Master
    merged = {}
    for w in master_words:
        if w.word:
            merged[w.word.lower().strip()] = w
    for w in tenant_words:
        if w.word:
            merged[w.word.lower().strip()] = w

    # Sort merged results by created_at desc
    sorted_list = sorted(
        list(merged.values()),
        key=lambda x: x.created_at or datetime.min,
        reverse=True
    )

    for item in sorted_list:
        item.has_vector = bool(getattr(item, "embedding", None) is not None)

    # Apply pagination offset and limit
    return sorted_list[skip:skip+limit]


@router.get("/dictionary/export")
async def export_dictionary(
    db: AsyncSession = Depends(get_db)
):
    """Export the merged dictionary words as a CSV file."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    master_words = []
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(select(DictionaryWord).order_by(DictionaryWord.word.asc()))
                master_words = m_res.scalars().all()
                for w in master_words:
                    w.is_global = True
        except Exception as e:
            logger.warning(f"Failed to fetch global dictionary for export: {e}")

    tenant_words = []
    try:
        t_res = await db.execute(select(DictionaryWord).order_by(DictionaryWord.word.asc()))
        tenant_words = t_res.scalars().all()
        for w in tenant_words:
            w.is_global = False
    except Exception as e:
        logger.warning(f"Failed to fetch tenant dictionary for export: {e}")

    merged = {}
    for w in master_words:
        if w.word:
            merged[w.word.lower().strip()] = w
    for w in tenant_words:
        if w.word:
            merged[w.word.lower().strip()] = w

    sorted_words = sorted(list(merged.values()), key=lambda x: (x.word or "").lower())

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';', lineterminator='\n')
    
    writer.writerow([
        "Kata", "Definisi", "Contoh Kalimat", "Tipe Kata", 
        "Sinonim Target", "Apakah Typo/Slang", "Tipe NER", 
        "Target NER", "Status", "Tingkat"
    ])
    
    for item in sorted_words:
        writer.writerow([
            sanitize_csv_cell(item.word),
            sanitize_csv_cell(item.definition),
            sanitize_csv_cell(item.context_example),
            sanitize_csv_cell(item.word_type or "GENERAL"),
            sanitize_csv_cell(item.synonym_target),
            "YA" if item.is_typo_or_slang else "TIDAK",
            sanitize_csv_cell(item.ner_type),
            sanitize_csv_cell(item.ner_target),
            sanitize_csv_cell(item.status.value if isinstance(item.status, enum.Enum) else str(item.status or "APPROVED")),
            "Pusat" if item.is_global else "Lokal"
        ])
        
    csv_data = output.getvalue()
    output.close()
    
    filename = f"sarbot_kamus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_data.encode('utf-8-sig'),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.post("/dictionary/import")
async def import_dictionary(
    file: UploadFile = File(...),
    is_global: bool = Query(False, description="True untuk menyimpan di kamus dasar nasional (Pusat)"),
    db: AsyncSession = Depends(get_db)
):
    """Import dictionary words from an uploaded CSV file."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File harus berformat .csv")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    if is_global and tenant_slug not in ("pusat", "global"):
        raise HTTPException(status_code=403, detail="Hanya UPT Pusat yang dapat mengimpor ke kamus dasar nasional")

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8-sig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {str(e)}")

    first_line = content_str.split("\n")[0] if content_str else ""
    delimiter = ";" if ";" in first_line else ","

    reader = csv.reader(io.StringIO(content_str), delimiter=delimiter)

    try:
        headers = next(reader)
    except StopIteration:
        raise HTTPException(status_code=400, detail="File CSV kosong")

    header_map = {
        "word": ["kata", "word", "kosakata", "term"],
        "definition": ["definisi", "definition", "arti", "makna"],
        "context_example": ["contoh kalimat", "context example", "contoh", "example"],
        "word_type": ["tipe kata", "word type", "tipe", "type"],
        "synonym_target": ["synonym target", "sinonim target", "sinonim", "synonym"],
        "is_typo_or_slang": ["apakah typo/slang", "is typo or slang", "typo", "slang", "typo/slang"],
        "ner_type": ["tipe ner", "ner type", "ner_type"],
        "ner_target": ["target ner", "ner target", "ner_target"],
        "status": ["status"]
    }

    pos = {}
    for i, h in enumerate(headers):
        h_clean = h.strip().lower()
        for field, synonyms in header_map.items():
            if h_clean in synonyms:
                pos[field] = i
                break

    if "word" not in pos:
        raise HTTPException(
            status_code=400,
            detail="Kolom 'Kata' atau 'Word' tidak ditemukan dalam file CSV"
        )

    created_count = 0
    updated_count = 0
    failed_rows = []

    import difflib

    async def process_row(session, row, row_idx):
        nonlocal created_count, updated_count
        
        def get_val(field):
            if field in pos and pos[field] < len(row):
                return row[pos[field]].strip()
            return None

        word = get_val("word")
        definition = get_val("definition")
        context_example = get_val("context_example")
        word_type_raw = get_val("word_type") or "GENERAL"
        synonym_target = get_val("synonym_target")
        typo_raw = get_val("is_typo_or_slang")
        ner_type = get_val("ner_type")
        ner_target = get_val("ner_target")
        status_raw = get_val("status")

        if not word:
            failed_rows.append({"row": row_idx, "reason": "Kosakata kosong"})
            return

        word_clean = word.strip()
        word_type = word_type_raw.upper()
        if word_type not in ("GENERAL", "ABBREVIATION", "JARGON"):
            word_type = "GENERAL"

        is_typo_or_slang = False
        if typo_raw:
            typo_clean = typo_raw.strip().lower()
            if typo_clean in ("true", "1", "ya", "yes", "t", "y"):
                is_typo_or_slang = True

        similarity_score = None
        if synonym_target:
            syn_clean = synonym_target.strip()
            similarity_score = difflib.SequenceMatcher(None, word_clean.lower(), syn_clean.lower()).ratio()

        status = DictionaryStatus.APPROVED
        if status_raw:
            stat_clean = status_raw.strip().upper()
            if stat_clean in [s.value for s in DictionaryStatus]:
                status = DictionaryStatus(stat_clean)
            elif stat_clean == "AKTIF":
                status = DictionaryStatus.APPROVED

        if ner_type:
            ner_type = ner_type.strip().upper()
            if ner_type not in ("INCIDENT_KEYWORD", "LOCATION", "TIME_MARKER", "VICTIM_STATUS"):
                ner_type = None
        if ner_target:
            ner_target = ner_target.strip()

        result = await session.execute(
            select(DictionaryWord).where(sa_func.lower(DictionaryWord.word) == word_clean.lower())
        )
        db_word = result.scalar_one_or_none()

        if db_word:
            if definition is not None:
                db_word.definition = definition
            if context_example is not None:
                db_word.context_example = context_example
            db_word.word_type = word_type
            if synonym_target is not None:
                db_word.synonym_target = synonym_target
                db_word.similarity_score = similarity_score
            db_word.is_typo_or_slang = is_typo_or_slang
            if ner_type is not None:
                db_word.ner_type = ner_type
            if ner_target is not None:
                db_word.ner_target = ner_target
            db_word.status = status
            updated_count += 1
        else:
            new_word = DictionaryWord(
                word=word_clean,
                definition=definition,
                context_example=context_example,
                source_message="CSV Import",
                source_user="admin",
                word_type=word_type,
                is_auto_detected=False,
                status=status,
                synonym_target=synonym_target,
                is_typo_or_slang=is_typo_or_slang,
                similarity_score=similarity_score,
                ner_type=ner_type,
                ner_target=ner_target
            )
            session.add(new_word)
            created_count += 1

    if is_global:
        from app.db.session import MasterSessionLocal
        async with MasterSessionLocal() as master_db:
            for row_idx, row in enumerate(reader, start=2):
                if not row or all(not cell.strip() for cell in row):
                    continue
                try:
                    await process_row(master_db, row, row_idx)
                except Exception as e:
                    failed_rows.append({"row": row_idx, "reason": f"Error: {str(e)}"})
            try:
                await master_db.commit()
            except Exception as e:
                await master_db.rollback()
                raise HTTPException(status_code=500, detail=f"Gagal menyimpan ke database pusat: {str(e)}")
    else:
        for row_idx, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            try:
                await process_row(db, row, row_idx)
            except Exception as e:
                failed_rows.append({"row": row_idx, "reason": f"Error: {str(e)}"})
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan ke database lokal: {str(e)}")

    try:
        RuleExtractor._cache_loaded = False
        from app.services.autocorrect_service import AutoCorrectService
        AutoCorrectService._cache_loaded = False
    except Exception as e:
        logger.warning(f"Failed to reset autocorrect cache after import: {e}")

    return {
        "status": "success",
        "created": created_count,
        "updated": updated_count,
        "failed_count": len(failed_rows),
        "failed_details": failed_rows
    }


@router.post("/dictionary", response_model=DictionaryWordResponse, dependencies=[Depends(verify_operator_or_admin)])
async def create_dictionary_word(
    word_in: DictionaryWordCreate,
    db: AsyncSession = Depends(get_db)
):
    """Manually add a word to the dictionary."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    if word_in.is_global:
        if tenant_slug not in ("pusat", "global"):
            raise HTTPException(status_code=403, detail="Hanya UPT Pusat yang dapat membuat kamus dasar nasional")
        
        # Check in Master DB
        from app.db.session import MasterSessionLocal
        async with MasterSessionLocal() as master_db:
            existing = await master_db.execute(
                select(DictionaryWord).where(
                    sa_func.lower(DictionaryWord.word) == word_in.word.strip().lower()
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=409, detail=f"Kata '{word_in.word}' sudah ada di kamus dasar nasional")
            
            similarity_score = word_in.similarity_score
            if word_in.synonym_target and not similarity_score:
                import difflib
                similarity_score = difflib.SequenceMatcher(None, word_in.word.strip().lower(), word_in.synonym_target.strip().lower()).ratio()

            new_word = DictionaryWord(
                word=word_in.word.strip(),
                definition=word_in.definition,
                context_example=word_in.context_example,
                category=word_in.category or "OPERASIONAL_SAR",
                canonical_name=word_in.canonical_name,
                semantic_description=word_in.semantic_description,
                source_message="Manual entry",
                source_user="admin",
                word_type=(word_in.word_type or "GENERAL").upper(),
                ner_type=word_in.ner_type,
                ner_target=word_in.ner_target,
                is_auto_detected=False,
                status=DictionaryStatus.APPROVED if word_in.definition else DictionaryStatus.PENDING,
                synonym_target=word_in.synonym_target,
                is_typo_or_slang=word_in.is_typo_or_slang,
                similarity_score=similarity_score
            )
            master_db.add(new_word)
            try:
                await master_db.commit()
                RuleExtractor._cache_loaded = False
                from app.services.autocorrect_service import AutoCorrectService
                AutoCorrectService._cache_loaded = False
                await master_db.refresh(new_word)
                if new_word.status == DictionaryStatus.APPROVED and new_word.definition:
                    await llm_rag_service.vectorize_dictionary_word(new_word, master_db)
                new_word.is_global = True
                new_word.has_vector = bool(getattr(new_word, "embedding", None) is not None)
                return new_word
            except Exception as e:
                await master_db.rollback()
                logger.error(f"Failed to add global word {word_in.word}: {e}")
                raise HTTPException(status_code=500, detail="Database transaction failed")

    # Check if word already exists in local DB
    existing = await db.execute(
        select(DictionaryWord).where(
            sa_func.lower(DictionaryWord.word) == word_in.word.strip().lower()
        )
    )

    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Kata '{word_in.word}' sudah ada di kamus")

    similarity_score = word_in.similarity_score
    if word_in.synonym_target and not similarity_score:
        import difflib
        similarity_score = difflib.SequenceMatcher(None, word_in.word.strip().lower(), word_in.synonym_target.strip().lower()).ratio()

    new_word = DictionaryWord(
        word=word_in.word.strip(),
        definition=word_in.definition,
        context_example=word_in.context_example,
        category=word_in.category or "OPERASIONAL_SAR",
        canonical_name=word_in.canonical_name,
        semantic_description=word_in.semantic_description,
        source_message="Manual entry",
        source_user="admin",
        word_type=(word_in.word_type or "GENERAL").upper(),
        ner_type=word_in.ner_type,
        ner_target=word_in.ner_target,
        is_auto_detected=False,
        status=DictionaryStatus.APPROVED if word_in.definition else DictionaryStatus.PENDING,
        synonym_target=word_in.synonym_target,
        is_typo_or_slang=word_in.is_typo_or_slang,
        similarity_score=similarity_score
    )
    db.add(new_word)
    try:
        await db.commit()
        RuleExtractor._cache_loaded = False
        from app.services.autocorrect_service import AutoCorrectService
        AutoCorrectService._cache_loaded = False
        await db.refresh(new_word)
        if new_word.status == DictionaryStatus.APPROVED and new_word.definition:
            await llm_rag_service.vectorize_dictionary_word(new_word, db)
        new_word.is_global = False
        new_word.has_vector = bool(getattr(new_word, "embedding", None) is not None)
        return new_word
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to add word {word_in.word}: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")


@router.put("/dictionary/{word_id}", response_model=DictionaryWordResponse, dependencies=[Depends(verify_operator_or_admin)])
async def update_dictionary_word(
    word_id: int,
    word_update: DictionaryWordUpdate,
    is_global: bool = Query(False, description="True untuk mengubah kamus dasar nasional"),
    db: AsyncSession = Depends(get_db)
):
    """Update a dictionary word's definition or status."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    if is_global:
        if tenant_slug not in ("pusat", "global"):
            raise HTTPException(status_code=403, detail="Hanya UPT Pusat yang dapat mengubah kamus dasar nasional")
            
        from app.db.session import MasterSessionLocal
        async with MasterSessionLocal() as master_db:
            result = await master_db.execute(select(DictionaryWord).where(DictionaryWord.id == word_id))
            db_word = result.scalar_one_or_none()
            if not db_word:
                raise HTTPException(status_code=404, detail="Word not found in master database")
                
            if word_update.definition is not None:
                db_word.definition = word_update.definition
            if word_update.context_example is not None:
                db_word.context_example = word_update.context_example
            if word_update.category is not None:
                db_word.category = word_update.category
            if word_update.canonical_name is not None:
                db_word.canonical_name = word_update.canonical_name
            if word_update.semantic_description is not None:
                db_word.semantic_description = word_update.semantic_description
            if word_update.word_type is not None:
                db_word.word_type = word_update.word_type
            if word_update.ner_type is not None:
                db_word.ner_type = word_update.ner_type
            if word_update.ner_target is not None:
                db_word.ner_target = word_update.ner_target
            if word_update.status is not None:
                if word_update.status not in [s.value for s in DictionaryStatus]:
                    raise HTTPException(status_code=400, detail="Invalid status value")
                db_word.status = word_update.status
            if word_update.synonym_target is not None:
                db_word.synonym_target = word_update.synonym_target
                if db_word.word and db_word.synonym_target:
                    import difflib
                    db_word.similarity_score = difflib.SequenceMatcher(None, db_word.word.lower(), db_word.synonym_target.lower()).ratio()
            if word_update.is_typo_or_slang is not None:
                db_word.is_typo_or_slang = word_update.is_typo_or_slang
            if word_update.similarity_score is not None:
                db_word.similarity_score = word_update.similarity_score
                
            try:
                await master_db.commit()
                RuleExtractor._cache_loaded = False
                from app.services.autocorrect_service import AutoCorrectService
                AutoCorrectService._cache_loaded = False
                await master_db.refresh(db_word)
                if db_word.status == DictionaryStatus.APPROVED and db_word.definition:
                    await llm_rag_service.vectorize_dictionary_word(db_word, master_db)
                db_word.is_global = True
                db_word.has_vector = bool(getattr(db_word, "embedding", None) is not None)
                return db_word
            except Exception as e:
                await master_db.rollback()
                logger.error(f"Failed to update global word: {e}")
                raise HTTPException(status_code=500, detail="Database transaction failed")

    # Block direct modifications on global words if they exist in Master DB
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(
                    select(DictionaryWord).where(DictionaryWord.id == word_id)
                )
                if m_res.scalar_one_or_none():
                    raise HTTPException(
                        status_code=403, 
                        detail="Kata pusat bersifat Read-Only. Untuk menyesuaikan, tambahkan kata baru dengan nama yang sama secara lokal."
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking global dictionary word: {e}")

    result = await db.execute(select(DictionaryWord).where(DictionaryWord.id == word_id))
    db_word = result.scalar_one_or_none()
    if not db_word:
        raise HTTPException(status_code=404, detail="Word not found in tenant database")

    if word_update.definition is not None:
        db_word.definition = word_update.definition
    if word_update.context_example is not None:
        db_word.context_example = word_update.context_example
    if word_update.category is not None:
        db_word.category = word_update.category
    if word_update.canonical_name is not None:
        db_word.canonical_name = word_update.canonical_name
    if word_update.semantic_description is not None:
        db_word.semantic_description = word_update.semantic_description
    if word_update.word_type is not None:
        db_word.word_type = word_update.word_type
    if word_update.ner_type is not None:
        db_word.ner_type = word_update.ner_type
    if word_update.ner_target is not None:
        db_word.ner_target = word_update.ner_target
    if word_update.status is not None:
        if word_update.status not in [s.value for s in DictionaryStatus]:
            raise HTTPException(status_code=400, detail="Invalid status value")
        db_word.status = word_update.status
    if word_update.synonym_target is not None:
        db_word.synonym_target = word_update.synonym_target
        if db_word.word and db_word.synonym_target:
            import difflib
            db_word.similarity_score = difflib.SequenceMatcher(None, db_word.word.lower(), db_word.synonym_target.lower()).ratio()
    if word_update.is_typo_or_slang is not None:
        db_word.is_typo_or_slang = word_update.is_typo_or_slang
    if word_update.similarity_score is not None:
        db_word.similarity_score = word_update.similarity_score

    try:
        await db.commit()
        RuleExtractor._cache_loaded = False
        from app.services.autocorrect_service import AutoCorrectService
        AutoCorrectService._cache_loaded = False
        await db.refresh(db_word)
        if db_word.status == DictionaryStatus.APPROVED and db_word.definition:
            await llm_rag_service.vectorize_dictionary_word(db_word, db)
        db_word.is_global = False
        db_word.has_vector = bool(getattr(db_word, "embedding", None) is not None)
        return db_word
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update word: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")


@router.post("/dictionary/vectorize-all", dependencies=[Depends(verify_operator_or_admin)])
async def vectorize_all_dictionary_words(
    force_all: bool = Query(False, description="Re-generate vektor semua kata termasuk yang sudah ada"),
    db: AsyncSession = Depends(get_db)
):
    """Generate vector embeddings for all approved dictionary words."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    query = select(DictionaryWord).where(
        DictionaryWord.status == DictionaryStatus.APPROVED,
        DictionaryWord.definition.isnot(None)
    )
    if not force_all:
        query = query.where(DictionaryWord.embedding.is_(None))

    res = await db.execute(query)
    words = res.scalars().all()

    success = 0
    failed = 0
    for w in words:
        ok = await llm_rag_service.vectorize_dictionary_word(w, db)
        if ok:
            success += 1
        else:
            failed += 1

    return {
        "status": "success",
        "total_queued": len(words),
        "success_count": success,
        "failed_count": failed
    }


@router.delete("/dictionary/{word_id}", dependencies=[Depends(verify_operator_or_admin)])
async def delete_dictionary_word(
    word_id: int,
    is_global: bool = Query(False, description="True untuk menghapus kamus dasar nasional"),
    db: AsyncSession = Depends(get_db)
):
    """Delete a word from the dictionary."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    if is_global:
        if tenant_slug not in ("pusat", "global"):
            raise HTTPException(status_code=403, detail="Hanya UPT Pusat yang dapat menghapus kamus dasar nasional")
            
        from app.db.session import MasterSessionLocal
        async with MasterSessionLocal() as master_db:
            result = await master_db.execute(select(DictionaryWord).where(DictionaryWord.id == word_id))
            db_word = result.scalar_one_or_none()
            if not db_word:
                raise HTTPException(status_code=404, detail="Word not found in master database")
                
            await master_db.delete(db_word)
            try:
                await master_db.commit()
                RuleExtractor._cache_loaded = False
                return {"status": "success", "message": f"Kata dasar '{db_word.word}' berhasil dihapus"}
            except Exception as e:
                await master_db.rollback()
                logger.error(f"Failed to delete global word: {e}")
                raise HTTPException(status_code=500, detail="Database transaction failed")

    # Block direct deletion on global words if they exist in Master DB
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(
                    select(DictionaryWord).where(DictionaryWord.id == word_id)
                )
                if m_res.scalar_one_or_none():
                    raise HTTPException(
                        status_code=403, 
                        detail="Kata pusat bersifat Read-Only dan tidak dapat dihapus."
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking global dictionary word: {e}")

    result = await db.execute(select(DictionaryWord).where(DictionaryWord.id == word_id))
    db_word = result.scalar_one_or_none()
    if not db_word:
        raise HTTPException(status_code=404, detail="Word not found in tenant database")

    await db.delete(db_word)
    try:
        await db.commit()
        RuleExtractor._cache_loaded = False
        return {"status": "success", "message": f"Kata '{db_word.word}' berhasil dihapus"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete word: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")


@router.post("/dictionary/bulk-action", dependencies=[Depends(verify_operator_or_admin)])
async def bulk_action_dictionary(
    action: DictionaryBulkAction,
    db: AsyncSession = Depends(get_db)
):
    """Perform bulk approve/reject/delete on dictionary words."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    # Block direct bulk actions on global words
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(
                    select(DictionaryWord.id).where(DictionaryWord.id.in_(action.ids))
                )
                if m_res.scalars().all():
                    raise HTTPException(
                        status_code=403, 
                        detail="Beberapa kata terpilih berasal dari pusat (Read-Only) dan tidak dapat dimanipulasi."
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking global dictionary words in bulk: {e}")

    result = await db.execute(
        select(DictionaryWord).where(DictionaryWord.id.in_(action.ids))
    )
    words = result.scalars().all()

    if not words:
        raise HTTPException(status_code=404, detail="No words found with the given IDs in tenant database")

    if action.action == "approve":
        for w in words:
            w.status = DictionaryStatus.APPROVED
    elif action.action == "reject":
        for w in words:
            w.status = DictionaryStatus.REJECTED
    elif action.action == "delete":
        for w in words:
            await db.delete(w)
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use: approve, reject, delete")

    try:
        await db.commit()
        RuleExtractor._cache_loaded = False
        return {"status": "success", "message": f"{len(words)} kata berhasil di-{action.action}"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed bulk action {action.action}: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")


@router.get("/dictionary/export", dependencies=[Depends(verify_operator_or_admin)])
async def export_dictionary(db: AsyncSession = Depends(get_db)):
    """Export all APPROVED dictionary words as a JSON glossary."""
    result = await db.execute(
        select(DictionaryWord)
        .where(DictionaryWord.status == DictionaryStatus.APPROVED)
        .order_by(DictionaryWord.word)
    )
    words = result.scalars().all()
    glossary = {w.word: w.definition or "(belum ada definisi)" for w in words}
    return {"glossary": glossary, "count": len(glossary)}


@router.post("/glossary/seed", dependencies=[Depends(verify_admin)])
async def seed_sar_glossary(db: AsyncSession = Depends(get_db)):
    """
    Seed the built-in SAR abbreviation glossary into the dictionary.
    All seeded terms are set to APPROVED immediately.
    Terms that already exist are skipped (their definitions are updated if missing).
    """
    from app.services.term_extractor import seed_sar_glossary as do_seed
    result = await do_seed(db)
    RuleExtractor._cache_loaded = False
    return {
        "status": "success",
        "message": f"{result['inserted']} istilah baru ditambahkan, {result['skipped']} sudah ada di kamus.",
        "inserted": result["inserted"],
        "skipped": result["skipped"],
    }


@router.post("/dictionary/refresh-cache", dependencies=[Depends(verify_admin)])
async def refresh_kb_cache(db: AsyncSession = Depends(get_db)):
    """Force refresh the in-memory KB cache."""
    try:
        from app.services.kb_cache import kb_cache
        await kb_cache.force_refresh(db)
        RuleExtractor._cache_loaded = False
        return {"status": "success", "message": "KB cache berhasil di-refresh"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal refresh cache: {e}")


# ============================================================
# SOP DOCUMENT ENDPOINTS
# ============================================================

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "uploads", "sop")


@router.get("/sop", response_model=List[SOPDocumentResponse], dependencies=[Depends(verify_admin)])
async def get_sop_documents(db: AsyncSession = Depends(get_db)):
    """List all uploaded SOP documents."""
    if not db:
        return []
    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    master_sops = []
    if tenant_slug != "global":
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(select(SOPDocument).order_by(SOPDocument.created_at.desc()))
                m_docs = m_res.scalars().all()
                for doc in m_docs:
                    doc.is_global = True
                    master_sops.append(doc)
        except Exception as e:
            logger.warning(f"Failed to fetch global SOPs from Master DB: {e}")

    tenant_sops = []
    try:
        t_res = await db.execute(select(SOPDocument).order_by(SOPDocument.created_at.desc()))
        t_docs = t_res.scalars().all()
        for doc in t_docs:
            doc.is_global = False
            tenant_sops.append(doc)
    except Exception as e:
        logger.warning(f"Failed to fetch tenant SOPs from Tenant DB: {e}")

    # Merge by filename: Tenant overrides Master
    merged = {}
    for doc in master_sops:
        if doc.filename:
            merged[doc.filename.lower().strip()] = doc
    for doc in tenant_sops:
        if doc.filename:
            merged[doc.filename.lower().strip()] = doc

    sorted_list = sorted(
        list(merged.values()),
        key=lambda x: x.created_at or datetime.min,
        reverse=True
    )
    return sorted_list


@router.post("/sop/upload", response_model=SOPDocumentResponse, dependencies=[Depends(verify_admin)])
async def upload_sop_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form("SOP"),
    is_global: bool = Form(False, description="True untuk mengunggah sebagai SOP dasar nasional"),
    db: AsyncSession = Depends(get_db)
):
    """Upload a new SOP/Panduan document."""
    # Validate file type
    allowed_types = [
        "application/pdf",
        "text/plain",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Format file tidak didukung. Gunakan PDF, TXT, DOC, atau DOCX.")

    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file melebihi batas 10MB")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    if is_global and tenant_slug not in ("pusat", "global"):
        raise HTTPException(status_code=403, detail="Hanya UPT Pusat yang dapat mengunggah SOP dasar nasional")

    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Save file with unique name
    ext = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as f:
        f.write(contents)

    new_doc = SOPDocument(
        title=title.strip(),
        filename=file.filename or "unknown",
        file_path=file_path,
        file_size=len(contents),
        doc_type=doc_type,
        status=SOPDocStatus.UPLOADED
    )
    
    if is_global:
        from app.db.session import MasterSessionLocal
        async with MasterSessionLocal() as master_db:
            master_db.add(new_doc)
            try:
                await master_db.commit()
                await master_db.refresh(new_doc)
                new_doc.is_global = True
                return new_doc
            except Exception as e:
                await master_db.rollback()
                if os.path.exists(file_path):
                    os.remove(file_path)
                logger.error(f"Failed to upload global SOP document: {e}")
                raise HTTPException(status_code=500, detail="Database transaction failed")
    else:
        db.add(new_doc)
        try:
            await db.commit()
            await db.refresh(new_doc)
            new_doc.is_global = False
            return new_doc
        except Exception as e:
            await db.rollback()
            if os.path.exists(file_path):
                os.remove(file_path)
            logger.error(f"Failed to upload SOP document: {e}")
            raise HTTPException(status_code=500, detail="Database transaction failed")


@router.delete("/sop/{doc_id}", dependencies=[Depends(verify_admin)])
async def delete_sop_document(
    doc_id: int,
    is_global: bool = Query(False, description="True untuk menghapus SOP dasar nasional"),
    db: AsyncSession = Depends(get_db)
):
    """Delete a SOP document."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    if is_global:
        if tenant_slug not in ("pusat", "global"):
            raise HTTPException(status_code=403, detail="Hanya UPT Pusat yang dapat menghapus SOP dasar nasional")
            
        from app.db.session import MasterSessionLocal
        async with MasterSessionLocal() as master_db:
            result = await master_db.execute(select(SOPDocument).where(SOPDocument.id == doc_id))
            db_doc = result.scalar_one_or_none()
            if not db_doc:
                raise HTTPException(status_code=404, detail="Document not found in master database")
                
            # Remove physical file if it exists
            if db_doc.file_path and os.path.exists(db_doc.file_path):
                try:
                    os.remove(db_doc.file_path)
                except OSError:
                    pass
                    
            # Delete associated vectors from VectorMemory in Master DB
            try:
                from app.models.vector_memory import VectorMemory
                await master_db.execute(
                    delete(VectorMemory).where(
                        VectorMemory.metadata_json.like(f'%"doc_id": {doc_id}%')
                    )
                )
            except Exception as vec_err:
                logger.warning(f"Failed to delete associated global VectorMemory chunks: {vec_err}")
                
            await master_db.delete(db_doc)
            try:
                await master_db.commit()
                return {"status": "success", "message": f"Dokumen dasar '{db_doc.title}' berhasil dihapus"}
            except Exception as e:
                await master_db.rollback()
                logger.error(f"Failed to delete global SOP document: {e}")
                raise HTTPException(status_code=500, detail="Database transaction failed")

    # Block direct deletion on global SOPs if they exist in Master DB and caller is a regional tenant
    if tenant_slug not in ("pusat", "global"):
        try:
            from app.db.session import MasterSessionLocal
            async with MasterSessionLocal() as master_db:
                m_res = await master_db.execute(
                    select(SOPDocument).where(SOPDocument.id == doc_id)
                )
                if m_res.scalar_one_or_none():
                    raise HTTPException(
                        status_code=403, 
                        detail="Dokumen SOP pusat bersifat Read-Only dan tidak dapat dihapus oleh UPT cabang."
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Error checking global SOP document: {e}")

    result = await db.execute(select(SOPDocument).where(SOPDocument.id == doc_id))
    db_doc = result.scalar_one_or_none()
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found in tenant database")

    # Remove physical file if it exists
    if db_doc.file_path and os.path.exists(db_doc.file_path):
        try:
            os.remove(db_doc.file_path)
        except OSError:
            pass

    # Delete associated vectors from VectorMemory in Tenant DB
    try:
        from app.models.vector_memory import VectorMemory
        await db.execute(
            delete(VectorMemory).where(
                VectorMemory.metadata_json.like(f'%"doc_id": {doc_id}%')
            )
        )
    except Exception as vec_err:
        logger.warning(f"Failed to delete associated VectorMemory chunks: {vec_err}")

    await db.delete(db_doc)
    try:
        await db.commit()
        return {"status": "success", "message": f"Dokumen '{db_doc.title}' berhasil dihapus"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete SOP document: {e}")
        raise HTTPException(status_code=500, detail="Database transaction failed")


@router.post("/sop/{doc_id}/vectorize", dependencies=[Depends(verify_admin)])
async def vectorize_sop_document(
    doc_id: int,
    is_global: bool = Query(False, description="True untuk memvektorkan SOP dasar nasional"),
    db: AsyncSession = Depends(get_db)
):
    """Vectorize / index a SOP document into pgvector."""
    if not db:
        raise HTTPException(status_code=400, detail="No active database session")

    info = getattr(db, "info", None)
    tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

    if is_global:
        if tenant_slug not in ("pusat", "global"):
            raise HTTPException(status_code=403, detail="Hanya UPT Pusat yang dapat memvektorkan SOP dasar nasional")
            
        from app.db.session import MasterSessionLocal
        async with MasterSessionLocal() as master_db:
            result = await master_db.execute(select(SOPDocument).where(SOPDocument.id == doc_id))
            db_doc = result.scalar_one_or_none()
            if not db_doc:
                raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan di database master")
                
            if not db_doc.file_path or not os.path.exists(db_doc.file_path):
                db_doc.status = SOPDocStatus.FAILED
                await master_db.commit()
                raise HTTPException(status_code=404, detail="File dokumen fisik tidak ditemukan di server")
                
            # Extract text
            text_content = ""
            ext = os.path.splitext(db_doc.file_path)[1].lower()
            try:
                if ext == ".txt":
                    with open(db_doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
                elif ext == ".pdf":
                    import pypdf
                    reader = pypdf.PdfReader(db_doc.file_path)
                    pages_text = []
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            pages_text.append(t)
                    text_content = "\n".join(pages_text)
                elif ext in [".docx", ".doc"]:
                    import docx
                    doc = docx.Document(db_doc.file_path)
                    paragraphs_text = [p.text for p in doc.paragraphs if p.text]
                    text_content = "\n".join(paragraphs_text)
                else:
                    with open(db_doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
            except Exception as parse_err:
                db_doc.status = SOPDocStatus.FAILED
                await master_db.commit()
                logger.error(f"Failed to parse global document {db_doc.filename}: {parse_err}")
                raise HTTPException(status_code=500, detail=f"Gagal mengekstrak teks dari dokumen: {str(parse_err)}")
                
            if not text_content.strip():
                db_doc.status = SOPDocStatus.FAILED
                await master_db.commit()
                raise HTTPException(status_code=400, detail="Dokumen kosong atau tidak ada teks yang berhasil diekstrak")
                
            # Chunk text
            chunk_size = 800
            overlap = 150
            chunks = []
            start = 0
            text_len = len(text_content)
            while start < text_len:
                end = min(start + chunk_size, text_len)
                chunks.append(text_content[start:end])
                start += (chunk_size - overlap)
                
            if not chunks:
                db_doc.status = SOPDocStatus.FAILED
                await master_db.commit()
                raise HTTPException(status_code=400, detail="Gagal membagi dokumen menjadi potongan-potongan teks")
                
            from app.models.vector_memory import VectorMemory
            from app.core.tenant_config import get_tenant_settings
            tenant_settings = await get_tenant_settings(db)
            
            vectorized_count = 0
            last_embed_error = ""
            # Delete old chunks if any exist first
            try:
                await master_db.execute(
                    delete(VectorMemory).where(
                        VectorMemory.metadata_json.like(f'%"doc_id": {doc_id}%')
                    )
                )
            except Exception as d_err:
                logger.warning(f"Failed to delete old chunks for global SOP {doc_id}: {d_err}")
                
            for idx, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                try:
                    embed = await ai_provider_manager.get_embedding(chunk, tenant_settings=tenant_settings, raise_on_error=True)
                    if not embed:
                        continue
                    if len(embed) != 1024:
                        if len(embed) < 1024:
                            embed = embed + [0.0] * (1024 - len(embed))
                        elif len(embed) > 1024:
                            embed = embed[:1024]
                            
                    new_vector = VectorMemory(
                        report_id=None,
                        content=chunk,
                        embedding=embed,
                        metadata_json=json.dumps({
                            "doc_id": doc_id,
                            "title": db_doc.title,
                            "filename": db_doc.filename,
                            "chunk_index": idx
                        })
                    )
                    master_db.add(new_vector)
                    vectorized_count += 1
                except Exception as chunk_err:
                    last_embed_error = str(chunk_err)
                    logger.error(f"Failed to vectorize chunk {idx} of global document {doc_id}: {chunk_err}")
                    
            if vectorized_count == 0:
                db_doc.status = SOPDocStatus.FAILED
                await master_db.commit()
                err_detail = f"Gagal membuat embeddings: {last_embed_error}" if last_embed_error else "Gagal membuat embeddings untuk seluruh bagian dokumen. Periksa API Key dan Model Embedding di Pengaturan."
                raise HTTPException(status_code=500, detail=err_detail)
                
            db_doc.status = SOPDocStatus.INDEXED
            try:
                await master_db.commit()
                return {
                    "status": "success",
                    "message": f"Dokumen dasar '{db_doc.title}' berhasil divektorkan ke master DB!",
                    "chunks_count": len(chunks),
                    "vectorized_count": vectorized_count
                }
            except Exception as e:
                await master_db.rollback()
                logger.error(f"Failed to save global document status: {e}")
                raise HTTPException(status_code=500, detail="Gagal memperbarui status dokumen di database master")

    # Auto-detect if document exists in Master DB
    from app.db.session import MasterSessionLocal
    is_in_master = False
    try:
        async with MasterSessionLocal() as master_db:
            m_res = await master_db.execute(
                select(SOPDocument).where(SOPDocument.id == doc_id)
            )
            is_in_master = m_res.scalar_one_or_none() is not None
    except Exception as e:
        logger.warning(f"Error checking Master DB for SOP {doc_id}: {e}")

    # If document exists in Master DB:
    # 1. If caller is a regional branch tenant, block editing
    # 2. If caller is Pusat/Global, route to vectorize in Master DB
    if is_in_master:
        if tenant_slug not in ("pusat", "global"):
            raise HTTPException(
                status_code=403, 
                detail="Dokumen SOP pusat bersifat Read-Only bagi UPT cabang."
            )
        # Re-invoke global vectorization logic
        return await vectorize_sop_document(doc_id=doc_id, is_global=True, db=db)
    from app.core.config import settings as app_settings
    import logging
    logger = logging.getLogger(__name__)

    # 1. Fetch document from database
    result = await db.execute(select(SOPDocument).where(SOPDocument.id == doc_id))
    db_doc = result.scalar_one_or_none()
    if not db_doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")

    # 2. Check if file exists physically
    if not db_doc.file_path or not os.path.exists(db_doc.file_path):
        db_doc.status = SOPDocStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=404, detail="File dokumen fisik tidak ditemukan di server")

    # 3. Extract text from file
    text_content = ""
    ext = os.path.splitext(db_doc.file_path)[1].lower()
    
    try:
        if ext == ".txt":
            with open(db_doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                text_content = f.read()
        elif ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(db_doc.file_path)
            pages_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            text_content = "\n".join(pages_text)
        elif ext in [".docx", ".doc"]:
            import docx
            doc = docx.Document(db_doc.file_path)
            paragraphs_text = [p.text for p in doc.paragraphs if p.text]
            text_content = "\n".join(paragraphs_text)
        else:
            with open(db_doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                text_content = f.read()
    except Exception as parse_err:
        db_doc.status = SOPDocStatus.FAILED
        await db.commit()
        logger.error(f"Failed to parse document {db_doc.filename}: {parse_err}")
        raise HTTPException(status_code=500, detail=f"Gagal mengekstrak teks dari dokumen: {str(parse_err)}")

    if not text_content.strip():
        db_doc.status = SOPDocStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=400, detail="Dokumen kosong atau tidak ada teks yang berhasil diekstrak")

    # 4. Chunk text (800 characters chunks with 150 characters overlap)
    chunk_size = 800
    overlap = 150
    chunks = []
    start = 0
    text_len = len(text_content)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text_content[start:end])
        start += (chunk_size - overlap)

    if not chunks:
        db_doc.status = SOPDocStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=400, detail="Gagal membagi dokumen menjadi potongan-potongan teks")

    # 5. Generate embeddings and save to VectorMemory (pgvector)
    from app.services.ai_providers import ai_provider_manager
    from app.models.vector_memory import VectorMemory
    from app.core.tenant_config import get_tenant_settings
    import json
    
    tenant_settings = await get_tenant_settings(db)
    
    # Process each chunk
    vectorized_count = 0
    last_embed_error = ""
    for idx, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
            
        try:
            embed = await ai_provider_manager.get_embedding(chunk, tenant_settings=tenant_settings, raise_on_error=True)
            if not embed:
                continue

            # Match the embedding size (1024)
            if len(embed) != 1024:
                logger.warning(f"Embedding size mismatch: expected 1024, got {len(embed)}.")
                if len(embed) < 1024:
                    embed = embed + [0.0] * (1024 - len(embed))
                elif len(embed) > 1024:
                    embed = embed[:1024]

            # Save to PostgreSQL pgvector
            try:
                new_vector = VectorMemory(
                    report_id=None,
                    content=chunk,
                    embedding=embed,
                    metadata_json=json.dumps({
                        "doc_id": doc_id,
                        "title": db_doc.title,
                        "filename": db_doc.filename,
                        "chunk_index": idx
                    })
                )
                db.add(new_vector)
                vectorized_count += 1
            except Exception as pg_err:
                logger.error(f"Failed to save chunk {idx} to pgvector: {pg_err}")
            
        except Exception as chunk_err:
            last_embed_error = str(chunk_err)
            logger.error(f"Failed to vectorize chunk {idx} of document {doc_id}: {chunk_err}")

    if vectorized_count == 0:
        db_doc.status = SOPDocStatus.FAILED
        await db.commit()
        err_detail = f"Gagal membuat embeddings: {last_embed_error}" if last_embed_error else "Gagal membuat embeddings untuk seluruh bagian dokumen. Periksa API Key dan Model Embedding di Pengaturan."
        raise HTTPException(status_code=500, detail=err_detail)

    # 6. Update document status to INDEXED
    db_doc.status = SOPDocStatus.INDEXED
    try:
        await db.commit()
        return {
            "status": "success", 
            "message": f"Dokumen '{db_doc.title}' berhasil divektorkan!", 
            "chunks_count": len(chunks),
            "vectorized_count": vectorized_count
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save document status: {e}")
        raise HTTPException(status_code=500, detail="Gagal memperbarui status dokumen di database")
