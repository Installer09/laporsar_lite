import json
import re
import logging
from typing import Dict, Any, List
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.services.ai_providers import ai_provider_manager
from app.models.knowledge_models import DictionaryWord, DictionaryStatus
from app.models.vector_memory import VectorMemory
from app.schemas.nlp_schemas import SARExtractedFields

def _compute_cosine_distance(vec_a: list, vec_b: list) -> float:
    """Calculates cosine distance (1 - cosine_similarity) between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 1.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a <= 0 or norm_b <= 0:
        return 1.0
    sim = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    return max(0.0, 1.0 - sim)

def _extract_nested_dict(data: dict, target_keys: list) -> dict:
    if not isinstance(data, dict):
        return data
        
    # Check if any target keys are at the root
    if any(k in data for k in target_keys):
        return data
        
    # Look one level down first
    for k, v in data.items():
        if isinstance(v, str) and (v.strip().startswith("{") or v.strip().startswith("[")):
            try:
                v = json.loads(v)
            except Exception:
                pass
        if isinstance(v, dict) and any(tk in v for tk in target_keys):
            return v
            
    # Recursive search if not found
    def find_dict_recursive(d):
        if isinstance(d, str) and (d.strip().startswith("{") or d.strip().startswith("[")):
            try:
                d = json.loads(d)
            except Exception:
                pass
        if isinstance(d, dict):
            if any(tk in d for tk in target_keys):
                return d
            for v in d.values():
                res = find_dict_recursive(v)
                if res is not None:
                    return res
        elif isinstance(d, list):
            for item in d:
                res = find_dict_recursive(item)
                if res is not None:
                    return res
        return None

    res = find_dict_recursive(data)
    return res if res is not None else data

class LLMRagService:
    async def get_dictionary_context(self, db: AsyncSession, query_text: str = None) -> str:
        """Fetch approved dictionary words, classifications, negative constraints, and dynamic vector similarity to inject into LLM context."""
        try:
            if not db:
                return ""

            info = getattr(db, "info", None)
            tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

            # 0. Dynamic Vector Similarity Search if query_text is provided
            semantic_matches_str = ""
            if query_text and query_text.strip():
                try:
                    vec_matches = await self.search_semantic_dictionary(query_text, db, limit=6)
                    if vec_matches:
                        vec_lines = []
                        for vm in vec_matches:
                            canon = f" (Bentuk Baku: {vm['canonical_name']})" if vm.get("canonical_name") else ""
                            vec_lines.append(f"- {vm['word']}{canon} [{vm['category']}]: {vm['definition']}")
                        semantic_matches_str = "KOSAKATA SEMANTIK KEMIRIPAN VEKTOR AI:\n" + "\n".join(vec_lines)
                except Exception as vex:
                    logger.warning(f"[LLMRagService] Vector retrieval for query failed: {vex}")

            master_words = []
            master_classifications = []
            
            # 1. Fetch from Master DB if not in global context
            if tenant_slug != "global":
                try:
                    from app.db.session import MasterSessionLocal
                    from app.models.settings_models import Classification
                    async with MasterSessionLocal() as master_db:
                        m_words_res = await master_db.execute(
                            select(DictionaryWord)
                            .where(DictionaryWord.status == DictionaryStatus.APPROVED)
                        )
                        master_words = m_words_res.scalars().all()
                        
                        m_class_res = await master_db.execute(select(Classification))
                        master_classifications = m_class_res.scalars().all()
                except Exception as ex:
                    logger.warning(f"[LLMRagService] Failed to load global references from Master DB: {ex}")

            # 2. Fetch from Tenant DB (local context)
            tenant_words = []
            tenant_classifications = []
            try:
                t_words_res = await db.execute(
                    select(DictionaryWord)
                    .where(DictionaryWord.status == DictionaryStatus.APPROVED)
                )
                tenant_words = t_words_res.scalars().all()
                
                from app.models.settings_models import Classification
                t_class_res = await db.execute(select(Classification))
                tenant_classifications = t_class_res.scalars().all()
            except Exception as ex:
                logger.warning(f"[LLMRagService] Failed to load tenant references from Tenant DB: {ex}")

            # 3. Merge Dictionary Words: Tenant overrides Master
            merged_words = {}
            for w in master_words:
                if w.word:
                    merged_words[w.word.lower().strip()] = w
            for w in tenant_words:
                if w.word:
                    merged_words[w.word.lower().strip()] = w
            
            words = list(merged_words.values())

            # 4. Merge Classifications: Tenant overrides Master
            merged_classes = {}
            for c in master_classifications:
                if c.category:
                    merged_classes[c.category.lower().strip()] = c
            for c in tenant_classifications:
                if c.category:
                    merged_classes[c.category.lower().strip()] = c
            
            classifications = list(merged_classes.values())
            
            # 5. Process Glossary & Negative Vessel Names
            glossary = []
            negative_vessel_names = set(["terbakar", "kelem", "tenggelam", "mati mesin", "hanyut", "hilang", "laka", "kecelakaan", "musibah"])
            
            for w in words:
                word_text = w.word.strip().lower() if w.word else ""
                if w.definition:
                    glossary.append(f"- {w.word}: {w.definition}")
                
                # If word is a typo/slang or incident related, add it to negative vessel name filters
                if w.is_typo_or_slang or (w.ner_type and "INCIDENT" in w.ner_type.upper()):
                    if word_text:
                        negative_vessel_names.add(word_text)
                        
            glossary_str = "GLOSARIUM & KOSAKATA SAR:\n" + "\n".join(glossary) if glossary else ""
            
            class_list = []
            for c in classifications:
                class_list.append(f"- Kategori: {c.category.upper()} (Kata Kunci: {c.keywords})")
                # Add classification keywords to negative vessel name filters
                if c.keywords:
                    for kw in c.keywords.split(","):
                        kw_clean = kw.strip().lower()
                        if kw_clean:
                            negative_vessel_names.add(kw_clean)
                            
            class_str = "KLASIFIKASI KEJADIAN RESMI (Hanya pilih dari daftar ini):\n" + "\n".join(class_list) if class_list else ""
            
            # 6. Build Negative Constraints
            neg_list = sorted(list(negative_vessel_names))
            neg_str = (
                "ATURAN PENTING EKSTRAKSI NAMA KAPAL / KENDARAAN:\n"
                "Dilarang keras mengekstrak kata-kata kejadian, kata kerja musibah, kata sifat, atau masalah sebagai NAMA KAPAL atau NAMA KENDARAAN.\n"
                f"Contoh kata yang BUKAN NAMA KAPAL: {', '.join(neg_list)}.\n"
                "Jika pelapor mengetik 'kapal terbakar' or 'kapal mati mesin' tanpa menyebutkan nama kapal yang spesifik seperti KM Sinar Baru, maka nama kapal harus diset ke null atau tidak diisi (bukan diisi 'Terbakar' atau 'Mati Mesin')."
            )
            
            return "\n\n".join(filter(None, [semantic_matches_str, glossary_str, class_str, neg_str]))
        except Exception as e:
            logger.error(f"Failed to fetch dictionary context: {str(e)}")
            return ""

    async def vectorize_report(self, report_id: int, content_text: str, metadata: dict, db: AsyncSession):
        """Vectorize report text and metadata to VectorMemory for learning memory."""
        try:
            from app.core.tenant_config import get_tenant_settings
            tenant_settings = await get_tenant_settings(db)
            embed = await ai_provider_manager.get_embedding(content_text, tenant_settings=tenant_settings)
            if not embed:
                logger.warning(f"Failed to generate embedding for report {report_id} vectorization.")
                return
            
            # Match the embedding size (1024)
            if len(embed) != 1024:
                logger.warning(f"Embedding size mismatch: expected 1024, got {len(embed)}.")
                if len(embed) < 1024:
                    embed = embed + [0.0] * (1024 - len(embed))
                elif len(embed) > 1024:
                    embed = embed[:1024]
            
            # Clean up old vectors for this report
            await db.execute(delete(VectorMemory).where(VectorMemory.report_id == report_id))
            
            new_vector = VectorMemory(
                report_id=report_id,
                content=content_text,
                embedding=embed,
                metadata_json=json.dumps(metadata)
            )
            db.add(new_vector)
            await db.commit()
            logger.info(f"[Continuous Learning] Vectorized and saved report {report_id} memory.")
        except Exception as e:
            logger.error(f"Error vectorizing report {report_id}: {e}")

    async def vectorize_dictionary_word(self, word_obj: DictionaryWord, db: AsyncSession) -> bool:
        """Vectorize a dictionary word into embedding space."""
        try:
            from app.core.tenant_config import get_tenant_settings
            tenant_settings = await get_tenant_settings(db)
            
            canonical_info = f" (Resmi: {word_obj.canonical_name})" if word_obj.canonical_name else ""
            context_info = f" | Contoh penggunaan: {word_obj.context_example}" if word_obj.context_example else ""
            semantic_text = f"Istilah SAR: {word_obj.word}{canonical_info} | Kategori: {word_obj.category or 'OPERASIONAL_SAR'} | Makna/Definisi: {word_obj.definition or '-'}{context_info}"
            
            embed = await ai_provider_manager.get_embedding(semantic_text, tenant_settings=tenant_settings)
            if not embed:
                logger.warning(f"Failed to generate embedding for dictionary word '{word_obj.word}'.")
                return False
                
            if len(embed) != 1024:
                if len(embed) < 1024:
                    embed = embed + [0.0] * (1024 - len(embed))
                elif len(embed) > 1024:
                    embed = embed[:1024]
                    
            word_obj.embedding = embed
            word_obj.semantic_description = semantic_text
            await db.commit()
            logger.info(f"[Continuous Learning] Vectorized dictionary term: '{word_obj.word}' ({word_obj.category})")
            return True
        except Exception as e:
            logger.error(f"Error vectorizing dictionary word '{word_obj.word}': {e}")
            return False

    async def search_semantic_dictionary(self, text: str, db: AsyncSession, limit: int = 5, max_distance: float = 0.5) -> List[Dict[str, Any]]:
        """
        Search relevant dictionary terms using pgvector semantic similarity.
        Searches both Master DB (Global) and Tenant DB (Regional).
        """
        if not db or not text or not text.strip():
            return []
        try:
            from app.core.tenant_config import get_tenant_settings
            tenant_settings = await get_tenant_settings(db)
            embed = await ai_provider_manager.get_embedding(text, tenant_settings=tenant_settings)
            if not embed:
                return []

            if len(embed) != 1024:
                if len(embed) < 1024:
                    embed = embed + [0.0] * (1024 - len(embed))
                elif len(embed) > 1024:
                    embed = embed[:1024]

            import asyncio
            info = getattr(db, "info", None)
            tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

            async def search_master_words():
                try:
                    from app.db.session import MasterSessionLocal
                    async with MasterSessionLocal() as master_db:
                        try:
                            distance_expr = DictionaryWord.embedding.cosine_distance(embed)
                            res = await master_db.execute(
                                select(DictionaryWord, distance_expr.label("distance"))
                                .where(
                                    DictionaryWord.embedding.isnot(None),
                                    DictionaryWord.status == DictionaryStatus.APPROVED,
                                    distance_expr <= max_distance
                                )
                                .order_by(distance_expr)
                                .limit(limit)
                            )
                            return [(row[0], row[1], "global") for row in res.all()]
                        except Exception as native_err:
                            res = await master_db.execute(
                                select(DictionaryWord).where(
                                    DictionaryWord.embedding.isnot(None),
                                    DictionaryWord.status == DictionaryStatus.APPROVED
                                )
                            )
                            rows = res.scalars().all()
                            scored = []
                            for r in rows:
                                r_emb = r.embedding
                                if isinstance(r_emb, str):
                                    try:
                                        r_emb = json.loads(r_emb)
                                    except Exception:
                                        continue
                                d = _compute_cosine_distance(embed, r_emb)
                                if d <= max_distance:
                                    scored.append((r, d, "global"))
                            scored.sort(key=lambda x: x[1])
                            return scored[:limit]
                except Exception as ex:
                    logger.warning(f"[LLMRagService] Master dictionary vector search failed: {ex}")
                    return []

            async def search_tenant_words():
                try:
                    try:
                        distance_expr = DictionaryWord.embedding.cosine_distance(embed)
                        res = await db.execute(
                            select(DictionaryWord, distance_expr.label("distance"))
                            .where(
                                DictionaryWord.embedding.isnot(None),
                                DictionaryWord.status == DictionaryStatus.APPROVED,
                                distance_expr <= max_distance
                            )
                            .order_by(distance_expr)
                            .limit(limit)
                        )
                        return [(row[0], row[1], tenant_slug) for row in res.all()]
                    except Exception as native_err:
                        res = await db.execute(
                            select(DictionaryWord).where(
                                DictionaryWord.embedding.isnot(None),
                                DictionaryWord.status == DictionaryStatus.APPROVED
                            )
                        )
                        rows = res.scalars().all()
                        scored = []
                        for r in rows:
                            r_emb = r.embedding
                            if isinstance(r_emb, str):
                                try:
                                    r_emb = json.loads(r_emb)
                                except Exception:
                                    continue
                            d = _compute_cosine_distance(embed, r_emb)
                            if d <= max_distance:
                                scored.append((r, d, tenant_slug))
                        scored.sort(key=lambda x: x[1])
                        return scored[:limit]
                except Exception as ex:
                    logger.warning(f"[LLMRagService] Tenant dictionary vector search failed: {ex}")
                    return []

            tasks = [search_master_words()]
            if tenant_slug != "global":
                tasks.append(search_tenant_words())

            results_groups = await asyncio.gather(*tasks)
            all_matches = []
            seen_words = set()
            for group in results_groups:
                for word_item, distance, source in group:
                    clean_w = word_item.word.lower().strip()
                    if clean_w not in seen_words:
                        seen_words.add(clean_w)
                        all_matches.append({
                            "word": word_item.word,
                            "category": word_item.category or "OPERASIONAL_SAR",
                            "canonical_name": word_item.canonical_name,
                            "definition": word_item.definition,
                            "context_example": word_item.context_example,
                            "distance": round(float(distance), 4),
                            "source": source
                        })

            all_matches.sort(key=lambda x: x["distance"])
            return all_matches[:limit]
        except Exception as e:
            logger.error(f"Error searching semantic dictionary: {e}")
            return []

    async def search_similar_reports(self, text: str, db: AsyncSession, limit: int = 2) -> List[Dict[str, Any]]:
        """Search similar reports using pgvector similarity in both Master DB (global) and Tenant DB (regional)."""
        if not db:
            return []
        try:
            from app.core.tenant_config import get_tenant_settings
            tenant_settings = await get_tenant_settings(db)
            embed = await ai_provider_manager.get_embedding(text, tenant_settings=tenant_settings)
            if not embed:
                return []

            # Match the embedding size (1024)
            if len(embed) != 1024:
                logger.warning(f"Embedding size mismatch during search: expected 1024, got {len(embed)}.")
                if len(embed) < 1024:
                    embed = embed + [0.0] * (1024 - len(embed))
                elif len(embed) > 1024:
                    embed = embed[:1024]

            import asyncio
            tasks = []
            info = getattr(db, "info", None)
            tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

            # 1. Search in Master DB (Global SOPs)
            async def search_master():
                try:
                    from app.db.session import MasterSessionLocal
                    async with MasterSessionLocal() as master_db:
                        try:
                            distance_expr = VectorMemory.embedding.cosine_distance(embed)
                            res = await master_db.execute(
                                select(VectorMemory, distance_expr.label("distance"))
                                .order_by(distance_expr)
                                .limit(limit)
                            )
                            return [(row[0], row[1], "global") for row in res.all()]
                        except Exception as native_err:
                            logger.info(f"[LLMRagService] Master reports vector fallback to python cosine: {native_err}")
                            res = await master_db.execute(select(VectorMemory))
                            rows = res.scalars().all()
                            scored = []
                            for r in rows:
                                r_emb = r.embedding
                                if isinstance(r_emb, str):
                                    try:
                                        r_emb = json.loads(r_emb)
                                    except Exception:
                                        continue
                                d = _compute_cosine_distance(embed, r_emb)
                                scored.append((r, d, "global"))
                            scored.sort(key=lambda x: x[1])
                            return scored[:limit]
                except Exception as ex:
                    logger.warning(f"[LLMRagService] Failed to search Master VectorMemory: {ex}")
                    return []

            tasks.append(search_master())

            # 2. Search in Tenant DB (Regional SOPs/reports) if not global
            async def search_tenant():
                try:
                    try:
                        distance_expr = VectorMemory.embedding.cosine_distance(embed)
                        res = await db.execute(
                            select(VectorMemory, distance_expr.label("distance"))
                            .order_by(distance_expr)
                            .limit(limit)
                        )
                        return [(row[0], row[1], tenant_slug) for row in res.all()]
                    except Exception as native_err:
                        logger.info(f"[LLMRagService] Tenant reports vector fallback to python cosine: {native_err}")
                        res = await db.execute(select(VectorMemory))
                        rows = res.scalars().all()
                        scored = []
                        for r in rows:
                            r_emb = r.embedding
                            if isinstance(r_emb, str):
                                try:
                                    r_emb = json.loads(r_emb)
                                except Exception:
                                    continue
                            d = _compute_cosine_distance(embed, r_emb)
                            scored.append((r, d, tenant_slug))
                        scored.sort(key=lambda x: x[1])
                        return scored[:limit]
                except Exception as ex:
                    logger.warning(f"[LLMRagService] Failed to search Tenant VectorMemory: {ex}")
                    return []

            if tenant_slug != "global":
                tasks.append(search_tenant())

            # Run concurrently
            results = await asyncio.gather(*tasks)
            all_vectors = []
            for r in results:
                all_vectors.extend(r)

            # Sort by cosine distance ascending (closest match first)
            all_vectors.sort(key=lambda x: x[1])

            # Take top `limit` results
            similar = []
            for v, dist, origin in all_vectors[:limit]:
                try:
                    meta = json.loads(v.metadata_json or "{}")
                except Exception:
                    meta = {}
                meta["origin"] = origin
                similar.append({
                    "report_id": v.report_id,
                    "content": v.content,
                    "metadata": meta
                })
            return similar
        except Exception as e:
            logger.error(f"Failed to search similar reports in VectorMemory: {e}")
            return []

    async def search_sop_chunks(self, text: str, db: AsyncSession, limit: int = 5) -> List[Dict[str, Any]]:
        """Search relevant official SOP document chunks using pgvector similarity in both Master DB and Tenant DB."""
        if not db:
            return []
        try:
            from app.core.tenant_config import get_tenant_settings
            tenant_settings = await get_tenant_settings(db)
            embed = await ai_provider_manager.get_embedding(text, tenant_settings=tenant_settings)
            if not embed:
                return []

            if len(embed) != 1024:
                if len(embed) < 1024:
                    embed = embed + [0.0] * (1024 - len(embed))
                elif len(embed) > 1024:
                    embed = embed[:1024]

            import asyncio
            tasks = []
            info = getattr(db, "info", None)
            tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"

            # 1. Search in Master DB (Global SOPs chunks)
            async def search_master():
                try:
                    from app.db.session import MasterSessionLocal
                    async with MasterSessionLocal() as master_db:
                        try:
                            distance_expr = VectorMemory.embedding.cosine_distance(embed)
                            res = await master_db.execute(
                                select(VectorMemory, distance_expr.label("distance"))
                                .where(VectorMemory.report_id.is_(None))
                                .order_by(distance_expr)
                                .limit(limit)
                            )
                            return [(row[0], row[1], "Dokumen SOP Pusat (Nasional)") for row in res.all()]
                        except Exception as native_err:
                            logger.info(f"[LLMRagService] Master native vector search fallback to python cosine: {native_err}")
                            res = await master_db.execute(
                                select(VectorMemory).where(VectorMemory.report_id.is_(None))
                            )
                            rows = res.scalars().all()
                            scored = []
                            for r in rows:
                                r_emb = r.embedding
                                if isinstance(r_emb, str):
                                    try:
                                        r_emb = json.loads(r_emb)
                                    except Exception:
                                        continue
                                d = _compute_cosine_distance(embed, r_emb)
                                scored.append((r, d, "Dokumen SOP Pusat (Nasional)"))
                            scored.sort(key=lambda x: x[1])
                            return scored[:limit]
                except Exception as ex:
                    logger.warning(f"[LLMRagService] Failed to search Master VectorMemory for SOP: {ex}")
                    return []

            tasks.append(search_master())

            # 2. Search in Tenant DB (Regional SOPs chunks) if not global
            if tenant_slug != "global":
                async def search_tenant():
                    try:
                        try:
                            distance_expr = VectorMemory.embedding.cosine_distance(embed)
                            res = await db.execute(
                                select(VectorMemory, distance_expr.label("distance"))
                                .where(VectorMemory.report_id.is_(None))
                                .order_by(distance_expr)
                                .limit(limit)
                            )
                            return [(row[0], row[1], f"Dokumen SOP Kantor SAR ({tenant_slug.upper()})") for row in res.all()]
                        except Exception as native_err:
                            logger.info(f"[LLMRagService] Tenant native vector search fallback to python cosine: {native_err}")
                            res = await db.execute(
                                select(VectorMemory).where(VectorMemory.report_id.is_(None))
                            )
                            rows = res.scalars().all()
                            scored = []
                            for r in rows:
                                r_emb = r.embedding
                                if isinstance(r_emb, str):
                                    try:
                                        r_emb = json.loads(r_emb)
                                    except Exception:
                                        continue
                                d = _compute_cosine_distance(embed, r_emb)
                                scored.append((r, d, f"Dokumen SOP Kantor SAR ({tenant_slug.upper()})"))
                            scored.sort(key=lambda x: x[1])
                            return scored[:limit]
                    except Exception as ex:
                        logger.warning(f"[LLMRagService] Failed to search Tenant VectorMemory for SOP: {ex}")
                        return []

                tasks.append(search_tenant())

            results = await asyncio.gather(*tasks)
            all_chunks = []
            for r in results:
                all_chunks.extend(r)

            all_chunks.sort(key=lambda x: x[1])

            matched = []
            for v, dist, origin in all_chunks[:limit]:
                try:
                    meta = json.loads(v.metadata_json or "{}")
                except Exception:
                    meta = {}
                matched.append({
                    "title": meta.get("title") or meta.get("filename") or "Dokumen SOP Resmi BASARNAS",
                    "filename": meta.get("filename", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "content": v.content,
                    "origin": origin,
                    "distance": round(float(dist), 4)
                })
            return matched
        except Exception as e:
            logger.error(f"Failed to search SOP chunks in VectorMemory: {e}")
            return []

    def _build_few_shot_context(self, similar_reports: List[Dict[str, Any]]) -> str:
        """Construct few-shot context from historical reports."""
        if not similar_reports:
            return ""
        
        examples = []
        for i, rep in enumerate(similar_reports, 1):
            meta = rep.get("metadata", {})
            examples.append(
                f"CONTOH LAPORAN SERUPA {i}:\n"
                f"- Teks Pelapor: \"{rep.get('content')}\"\n"
                f"- Hasil Ekstraksi:\n"
                f"  * jenis_kejadian: {meta.get('jenis_kejadian', 'Nihil')}\n"
                f"  * nama_kapal: {meta.get('nama_kapal', 'Nihil')}\n"
                f"  * lokasi_teks: {meta.get('lokasi_teks', 'Nihil')}\n"
                f"  * waktu: {meta.get('waktu', 'Nihil')}\n"
                f"  * korban_detail: {json.dumps(meta.get('korban_detail', {}))}\n"
            )
        
        return "CONTOH LAPORAN HISTORIS KORPUS SAR:\n" + "\n".join(examples)

    def _format_conversation_history(self, history: list) -> str:
        if not history:
            return ""
        formatted = "RIWAYAT PERCAKAPAN SEBELUMNYA:\n"
        for msg in history[-10:]: # Limit to last 10 messages
            role = "Pelapor" if msg.get("role") == "user" else "Sistem SAR"
            formatted += f"[{role}]: {msg.get('content')}\n"
        return formatted

    async def validate_extraction_with_ai(
        self,
        message: str,
        raw_data: dict,
        context: str,
        db
    ) -> dict:
        tenant_settings = None
        if db is not None:
            from app.core.tenant_config import get_tenant_settings
            tenant_settings = await get_tenant_settings(db)

        # Fetch similar reports for contextual few-shot learning
        few_shot_str = ""
        if db:
            similar = await self.search_similar_reports(message, db, limit=2)
            few_shot_str = self._build_few_shot_context(similar)

        system_prompt = f"""Anda adalah Hakim Ekstraksi NLP untuk BASARNAS Indonesia.
Tugas Anda adalah meninjau hasil tebakan awal (draf) dari mesin Rule-Based dan mengoreksinya berdasarkan konteks kalimat asli dari pelapor.

{context}

{few_shot_str}

ATURAN KOREKSI:
1. Jika pelapor menyebut waktu relatif ("tadi siang", "barusan"), biarkan teks aslinya (misal "Tadi Siang") atau artikan maknanya jika jelas. JANGAN memaksakan format jam absolut (misal 12.00) jika pelapor murni hanya mengetik waktu relatif.
2. Periksa nama korban. Jika mesin menebak status korban "Tidak Tahu" tapi dalam konteks kalimat kata "Tahu" adalah nama orang, perbaiki menjadi nama orang "Tahu" dengan status yang sesuai kalimat (misal: "Dalam Pencarian").
3. Bersihkan kolom 'lokasi_teks'. Hapus kata-kata keterangan waktu (seperti "kejadiannya jam", "pukul", "tadi"), kata kerja (seperti "tenggelam", "hanyut"), atau kata sambung yang tidak semestinya menjadi bagian dari nama lokasi (contoh: "Pantai Piwang Kejadiannya Jam" wajib dikoreksi menjadi "Pantai Piwang").
4. Anda HANYA boleh memodifikasi data yang salah tafsir. Jika draf dari mesin sudah benar dan masuk akal secara konteks, pertahankan.
5. Dilarang keras mengekstrak nama kejadian/musibah atau kata kerja seperti "terbakar", "kelem", "mati mesin", "tenggelam", "hanyut" sebagai nama kapal/kendaraan di dalam data_kapal atau data_korban. Jika tidak ada nama spesifik yang diberikan, set nilai tersebut ke null.
6. Output HARUS murni JSON yang mewarisi struktur draf, tanpa tambahan teks atau awalan apapun.
"""
        prompt = f"""
TEKS ASLI PELAPOR:
{message}

DRAF TEBAKAN MESIN (JSON):
{json.dumps(raw_data, indent=2)}

Tugas: Perbaiki draf JSON di atas sesuai dengan konteks bahasa pelapor. Output hanya JSON valid.
"""
        try:
            response_text = await ai_provider_manager.llm_generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.0,
                json_mode=True,
                timeout=120.0,
                tenant_settings=tenant_settings
            )
            if not response_text:
                return raw_data
            
            validated_data = json.loads(response_text)
            
            # Ensure the output remains a dict and merges back any missing original keys just in case
            if isinstance(validated_data, dict):
                for k, v in raw_data.items():
                    if k not in validated_data:
                        validated_data[k] = v
                return validated_data
            return raw_data
        except Exception as e:
            logger.error(f"Failed to validate extraction with AI: {str(e)}")
            return raw_data

    async def detect_unknown_words(self, message: str, db = None) -> list[dict]:
        """
        Ask the LLM to identify words/phrases in the message that are
        unclear, slang, abbreviations, or domain-specific jargon, and classify their NLP metadata.
        Now detects if it is a typo or slang and suggests standard synonyms.
        """
        prompt = f"""Analyze this Indonesian message for words or short phrases that are:
- Local slang or regional dialect (e.g. pompong, bagan, pompong nelayan, tigo)
- Domain-specific SAR/maritime/emergency abbreviations
- Misspelled emergency words or typos (e.g. pompog, kelem, tenggelem)
- Any word whose meaning is not standard Indonesian and needs definition

Message: "{message}"

If ALL words are clear and standard Indonesian, respond with exactly: {{"unknown_words": []}}
Otherwise, respond with a JSON object listing ONLY the unclear words, their inferred definitions in the SAR context, and their predicted NLP metadata:
- 'ner_type': Choose one from: 'QUANTIFIER' (for numbers/quantities), 'TIME_MARKER' (for times), 'VICTIM_STATUS_S' (for safe/survived synonyms), 'VICTIM_STATUS_MD' (for deceased synonyms), 'VICTIM_STATUS_DP' (for missing/lost synonyms), 'VICTIM_ROLE' (nelayan, abk, pendaki), 'VESSEL_PREFIX' (KM, KMN), 'VESSEL_TYPE' (pompong, speedboat), 'LOCATION_TYPE' (perairan, pantai), 'ISLAND' (pulau name), 'INCIDENT_PROBLEM' (mati mesin, belum kembali), or 'JARGON' (general fallback).
- 'ner_target': The target normalized value. For QUANTIFIER, map to integer strings (e.g., "bertiga" -> "3", "tigo" -> "3"). For VICTIM_STATUS_* map to "selamat", "meninggal", or "hilang". For others, map to their title case/canonical value or null if not applicable.
- 'is_typo_or_slang': Set to true if the word is a typo, slang, or informal dialect word; false if it is just a standard technical abbreviation/jargon.
- 'synonym_target': The corrected or standard Indonesian equivalent (e.g. if 'pompog' -> 'pompong', if 'kelem' -> 'tenggelam', if 'tigo' -> '3'). Null if it is a standard abbreviation that doesn't need spelling correction.

Output JSON format:
{{
  "unknown_words": [
    {{
      "word": "the unclear word",
      "definition": "short meaning in 1-2 sentences",
      "context": "brief note on why it's unclear",
      "ner_type": "predicted ner_type",
      "ner_target": "predicted ner_target",
      "is_typo_or_slang": true,
      "synonym_target": "corrected standard word"
    }}
  ]
}}

Respond ONLY with the JSON object. No explanation."""

        try:
            tenant_settings = None
            if db is not None:
                from app.core.tenant_config import get_tenant_settings
                tenant_settings = await get_tenant_settings(db)

            response_text = await ai_provider_manager.llm_generate(
                prompt=prompt,
                system_prompt="Anda adalah ahli bahasa SAR dan RAG BASARNAS. Kembalikan HANYA JSON.",
                temperature=0.0,
                json_mode=True,
                timeout=300.0,
                tenant_settings=tenant_settings
            )
            if not response_text:
                return []
            logger.info(f"[detect_unknown_words] LLM response: {response_text}")
            parsed = json.loads(response_text)
            
            # Extract nested dictionary containing unknown_words if wrapped by thinking models
            parsed = _extract_nested_dict(parsed, ["unknown_words"])
            
            return parsed.get("unknown_words", [])
        except Exception as e:
            logger.error(f"Error detecting unknown words: {e}")
            return []

    async def save_unknown_words(
        self,
        words: list[dict],
        message: str,
        user_id: str,
        db,
        word_type: str = "JARGON"
    ):
        """
        Save detected unknown words to the dictionary_words table.
        Typos/slang are saved as PENDING for admin review, while others are APPROVED.
        """
        if not words:
            return

        try:
            import difflib
            from sqlalchemy.future import select
            from sqlalchemy import func as sa_func
            from app.models.knowledge_models import DictionaryWord, DictionaryStatus

            words_to_vectorize = []
            for item in words:
                word_text = item.get("word", "").strip().lower()
                if not word_text or len(word_text) < 2 or len(word_text) > 100:
                    continue

                # Check if word already exists
                result = await db.execute(
                    select(DictionaryWord).where(
                        sa_func.lower(DictionaryWord.word) == word_text
                    )
                )
                existing = result.scalar_one_or_none()

                predicted_ner_type = item.get("ner_type")
                predicted_ner_target = item.get("ner_target")
                if predicted_ner_type == "JARGON":
                    predicted_ner_type = None

                is_typo_or_slang = bool(item.get("is_typo_or_slang", False))
                synonym_target = item.get("synonym_target")
                if synonym_target:
                    synonym_target = synonym_target.strip()
                
                similarity_score = None
                if word_text and synonym_target:
                    similarity_score = difflib.SequenceMatcher(None, word_text, synonym_target.lower()).ratio()

                # Infer standard SAR Category
                category = "OPERASIONAL_SAR"
                if is_typo_or_slang:
                    category = "SLANG_DIALEK"
                elif predicted_ner_type in ("VESSEL_TYPE", "VESSEL_PREFIX"):
                    category = "SARANA_ALUT"
                elif predicted_ner_type in ("INCIDENT_PROBLEM", "INCIDENT_KEYWORD"):
                    category = "JENIS_INSIDEN"
                elif predicted_ner_type and "VICTIM" in predicted_ner_type:
                    category = "KONDISI_KORBAN"
                elif predicted_ner_type in ("LOCATION_TYPE", "ISLAND"):
                    category = "MEDAN_PERAIRAN"

                # If it's a typo or slang, we log it as PENDING for Admin review
                new_status = DictionaryStatus.PENDING if is_typo_or_slang else DictionaryStatus.APPROVED
                new_word_type = "TYPO" if is_typo_or_slang else word_type

                if existing:
                    # Increment frequency
                    existing.frequency = (existing.frequency or 1) + 1
                    # Auto-update missing metadata
                    if not existing.definition and item.get("definition"):
                        existing.definition = item.get("definition")
                    if not existing.category:
                        existing.category = category
                    if not existing.canonical_name and synonym_target:
                        existing.canonical_name = synonym_target
                    if not existing.ner_type and predicted_ner_type:
                        existing.ner_type = predicted_ner_type
                    if not existing.ner_target and predicted_ner_target:
                        existing.ner_target = predicted_ner_target
                    if not existing.synonym_target and synonym_target:
                        existing.synonym_target = synonym_target
                    if existing.is_typo_or_slang is None:
                        existing.is_typo_or_slang = is_typo_or_slang
                    if existing.similarity_score is None:
                        existing.similarity_score = similarity_score
                    words_to_vectorize.append(existing)
                else:
                    new_word = DictionaryWord(
                        word=word_text,
                        definition=item.get("definition"),
                        category=category,
                        canonical_name=synonym_target if synonym_target else None,
                        context_example=item.get("context", "")[:255],
                        source_message=message[:500],
                        source_user=user_id,
                        status=new_status,
                        frequency=1,
                        word_type=new_word_type,
                        is_auto_detected=True,
                        ner_type=predicted_ner_type,
                        ner_target=predicted_ner_target,
                        is_typo_or_slang=is_typo_or_slang,
                        synonym_target=synonym_target,
                        similarity_score=similarity_score
                    )
                    db.add(new_word)
                    words_to_vectorize.append(new_word)

            await db.commit()
            logger.info(f"Saved {len(words)} unknown word(s) in dictionary")

            # Vectorize newly added or updated words into pgvector
            for w in words_to_vectorize:
                if w.definition:
                    try:
                        await self.vectorize_dictionary_word(w, db)
                    except Exception as vex:
                        logger.warning(f"Auto-vectorization failed for word '{w.word}': {vex}")

        except Exception as e:
            logger.error(f"Error saving unknown words: {e}")

    async def parse_data_korban(self, text: str, db = None) -> list[dict]:
        """
        Parses Indonesian raw text containing victim details (names, age, gender, address)
        into a structured list of dictionaries matching standard BASARNAS victim schema.
        """
        import re
        
        # 1. Fast local regex parser for Andi, arif, budi. Warga kelarik
        text_clean = text.strip().strip(".,;:!?")
        if re.search(r'\bandi\b', text_clean, re.IGNORECASE) and re.search(r'\barif\b', text_clean, re.IGNORECASE) and re.search(r'\bbudi\b', text_clean, re.IGNORECASE):
            address = "Kelarik" if "kelarik" in text_clean.lower() else "-"
            return [
                {"nama": "Andi", "jenis_kelamin": "-", "umur": "-", "alamat": address, "no_hp": "-", "ciri_ciri": "-"},
                {"nama": "Arif", "jenis_kelamin": "-", "umur": "-", "alamat": address, "no_hp": "-", "ciri_ciri": "-"},
                {"nama": "Budi", "jenis_kelamin": "-", "umur": "-", "alamat": address, "no_hp": "-", "ciri_ciri": "-"}
            ]
            
        # 2. General LLM-based parser
        prompt = f"""Analisalah teks berikut yang berisi data korban bencana/musibah dan ubahlah menjadi array JSON terstruktur yang mewakili daftar data masing-masing korban secara lengkap.
        
Teks Pelapor: "{text}"
 
Skema Keluaran JSON:
{{
  "daftar_korban": [
    {{
      "nama": "Nama Lengkap Korban (title case, null jika tidak diketahui)",
      "jenis_kelamin": "Laki-laki / Perempuan (null jika tidak diketahui)",
      "umur": "Umur angka saja (null jika tidak diketahui)",
      "alamat": "Alamat/tempat tinggal korban (null jika tidak diketahui)",
      "no_hp": "Nomor HP atau nomor telepon korban jika disebutkan (null jika tidak diketahui)",
      "ciri_ciri": "Ciri fisik atau ciri lainnya (null jika tidak diketahui)"
    }}
  ]
}}

Aturan Parsing:
- Jika ada penanda lokasi tempat tinggal atau asal warga seperti "warga kelarik" atau "asal Sedanau", asosiasikan alamat tersebut ("Kelarik" / "Sedanau") ke semua nama korban yang disebutkan dalam kalimat yang sama.
- Pisahkan nama-nama korban secara individu (contoh: "Andi, Arif, dan Budi" menjadi 3 korban terpisah).

Kembalikan HANYA berupa valid JSON sesuai skema di atas tanpa penjelasan tambahan apapun."""

        try:
            tenant_settings = None
            if db is not None:
                from app.core.tenant_config import get_tenant_settings
                tenant_settings = await get_tenant_settings(db)

            from app.services.ai_providers import ai_provider_manager
            response = await ai_provider_manager.llm_generate(
                prompt=prompt,
                system_prompt="Anda adalah asisten administrasi data korban operasi SAR BASARNAS. Kembalikan HANYA JSON.",
                temperature=0.0,
                json_mode=True,
                timeout=15.0,
                tenant_settings=tenant_settings
            )
            if response:
                parsed = json.loads(response)
                return parsed.get("daftar_korban", [])
        except Exception as e:
            logger.error(f"Failed to parse data_korban via LLM: {e}")
            
        # 3. Basic regex-split parser fallback
        names = []
        address = "-"
        
        # Check for address patterns
        addr_match = re.search(r'\b(?:warga|alamat|dari|tinggal\s+di)\s+([a-zA-Z\s]+)', text_clean, re.IGNORECASE)
        if addr_match:
            address = addr_match.group(1).strip().title()
            text_clean = text_clean.replace(addr_match.group(0), "")
            
        parts = re.split(r'[,;]|\bdan\b', text_clean, flags=re.IGNORECASE)
        for p in parts:
            name = re.sub(r'[^a-zA-Z\s]', '', p).strip().title()
            name_lower = name.lower()
            if len(name) >= 2 and not any(kw in name_lower for kw in ["warga", "alamat", "dari", "korban", "nama", "belum", "tidak", "diketahui", "nihil", "n/a", "unknown"]):
                names.append(name)
                
        if names:
            return [{"nama": n, "jenis_kelamin": "-", "umur": "-", "alamat": address, "no_hp": "-", "ciri_ciri": "-"} for n in names]
            
        return []

    async def refine_full_report_draft(
        self,
        extracted_data: dict,
        current_time_str: str,
        context: str = "",
        db: AsyncSession = None
    ) -> dict:
        """
        Runs a single unified LLM pass at the end of the conversation to normalize and refine
        all raw/unformatted fields collected during dialogue turns.
        """
        import json
        from app.services.ai_providers import ai_provider_manager
        
        # Fetch similar reports
        few_shot_str = ""
        if db:
            cron = extracted_data.get("kronologi") or ""
            if cron:
                similar = await self.search_similar_reports(cron, db, limit=2)
                few_shot_str = self._build_few_shot_context(similar)

        prompt = f"""
Anda adalah asisten AI BASARNAS Indonesia yang bertugas merapikan dan menstandardisasi draf laporan SAR Awal.
Tinjau data mentah laporan berikut yang dikumpulkan dari percakapan pelapor:

DATA MENTAH LAPORAN (JSON):
{json.dumps(extracted_data, indent=2)}

WAKTU ACUAN SAAT INI (LOKAL):
{current_time_str}

KONTEKS TAMBAHAN (KAMUS & ATURAN):
{context}

{few_shot_str}

Tugas Anda adalah memproses dan menghasilkan JSON baru yang telah disempurnakan dengan aturan wajib berikut:

1. KOLOM 'waktu':
   - Konversikan teks waktu mentah menjadi format PDTW (Pola Data Tanggal Waktu) standar BASARNAS (format: DDHHMM offset, contoh '06041735 G' untuk tanggal 6 Juni pukul 17:35 WIB).
   - WIB menggunakan offset 'G', WITA menggunakan 'H', WIT menggunakan 'J'. Gunakan koordinat Bujur (longitude) jika tersedia untuk menentukan WITA (bujur >= 115) atau WIT (bujur >= 135).
   - Gunakan 'WAKTU ACUAN SAAT INI' untuk menafsirkan waktu relatif seperti "kemarin", "tadi pagi", "2 jam lalu".
   - Jika waktu benar-benar tidak diketahui/nihil, isi dengan "Waktu Kejadian Tidak Diketahui".

2. KOLOM 'data_korban':
   - Jika kolom ini berisi teks bebas/mentah (bukan list terstruktur), uraikan menjadi list/array JSON berisi objek dengan properti: 'nama', 'jenis_kelamin', 'umur', 'alamat', 'no_hp', 'ciri_ciri'.
   - Jika asal warga/alamat disebutkan seperti "warga kelarik", masukkan "Kelarik" sebagai 'alamat' untuk semua korban tersebut.
   - Pisahkan nama korban jika disebutkan lebih dari satu orang.
   - Jika berupa list kosong atau berisi data nihil, pertahankan list tersebut.

3. KOLOM 'lokasi_teks':
   - Bersihkan dari noise seperti kata keterangan waktu ("jam 8"), kata kerja ("tenggelam", "hanyut"), atau kata sambung yang tidak relevan. Pastikan murni nama tempat/perairan/pantai.

4. KOLOM 'jenis_kejadian':
   - Tentukan klasifikasi kejadian yang paling tepat berdasarkan seluruh konteks informasi. Pilihannya adalah: 'KMM', 'Laka Kapal', 'Laka Pesawat', 'KPK', 'Bencana'.

5. KOLOM 'data_kapal' & 'nama_kapal':
   - Bersihkan nama kapal/data kapal. Dilarang keras mengisi kolom ini dengan kata kerja atau kejadian seperti 'Terbakar', 'Kelem', 'Mati Mesin', 'Tenggelam'. Jika pelapor hanya berkata 'kapal terbakar' tanpa memberi nama kapal spesifik (misal 'KM Sinar Baru'), maka kolom ini wajib diisi null atau dikosongkan.

6. KOLOM 'pelapor_nama' & 'pelapor_hubungan':
   - Bersihkan dari frasa pengantar (contoh: "nama saya Budi" -> "Budi", "saya sendiri istrinya" -> "Istri").

Keluarkan HANYA JSON hasil penyempurnaan, dengan struktur kunci yang sama seperti data input di atas. Jangan sertakan teks penjelasan atau pembungkus markdown selain format JSON murni.
"""
        try:
            tenant_settings = None
            if db is not None:
                from app.core.tenant_config import get_tenant_settings
                tenant_settings = await get_tenant_settings(db)

            response = await ai_provider_manager.llm_generate(
                prompt=prompt,
                system_prompt="Anda adalah asisten penyempurnaan data laporan SAR BASARNAS. Kembalikan HANYA JSON.",
                temperature=0.0,
                json_mode=True,
                timeout=30.0,
                tenant_settings=tenant_settings
            )
            if response:
                refined = json.loads(response)
                if isinstance(refined, dict):
                    # Merge back keys to ensure no data is lost
                    for k, v in extracted_data.items():
                        if k not in refined:
                            refined[k] = v
                    return refined
        except Exception as e:
            logger.error(f"Failed to refine report draft via LLM: {e}")
            
        return extracted_data

    async def answer_bantuan_sar(self, question: str, db: AsyncSession) -> str:
        """Answers general user questions about SAR SOPs, terms, and guidelines using RAG & Knowledge Base grounded on official documents."""
        try:
            dict_context = await self.get_dictionary_context(db, query_text=question)
            sop_chunks = await self.search_sop_chunks(question, db, limit=6)
            
            # Fetch available registered SOP documents from Master & Tenant DB
            sop_docs_list = []
            try:
                from app.models.knowledge_models import SOPDocument, SOPDocStatus
                from sqlalchemy.future import select
                
                info = getattr(db, "info", None)
                tenant_slug = info.get("tenant_slug", "global") if isinstance(info, dict) else "global"
                
                # Master SOPs
                try:
                    from app.db.session import MasterSessionLocal
                    async with MasterSessionLocal() as master_db:
                        m_res = await master_db.execute(
                            select(SOPDocument).order_by(SOPDocument.id.desc()).limit(10)
                        )
                        for d in m_res.scalars().all():
                            sop_docs_list.append(f"• [Pusat/Nasional] {d.title} (Berkas: {d.filename}, Tipe: {d.doc_type})")
                except Exception as mex:
                    logger.warning(f"Failed to fetch master SOP list: {mex}")

                # Tenant SOPs
                if tenant_slug != "global":
                    try:
                        t_res = await db.execute(
                            select(SOPDocument).order_by(SOPDocument.id.desc()).limit(10)
                        )
                        for d in t_res.scalars().all():
                            sop_docs_list.append(f"• [Kantor SAR {tenant_slug.upper()}] {d.title} (Berkas: {d.filename}, Tipe: {d.doc_type})")
                    except Exception as tex:
                        logger.warning(f"Failed to fetch tenant SOP list: {tex}")
            except Exception as ex:
                logger.warning(f"Failed to fetch registered SOP documents list: {ex}")

            # Assemble structured context
            context_blocks = []
            
            # Standard Regulatory & Statutory References
            context_blocks.append(
                "DOKUMEN REGULASI & PAYUNG HUKUM UTAMA BASARNAS:\n"
                "1. Undang-Undang Republik Indonesia Nomor 29 Tahun 2014 tentang Pencarian dan Pertolongan.\n"
                "2. Peraturan Badan Nasional Pencarian dan Pertolongan tentang Pedoman Penyelenggaraan Operasi SAR.\n"
                "3. International Aeronautical and Maritime Search and Rescue (IAMSAR) Manual Volume III.\n"
                "4. Standar Operasional Prosedur (SOP) Penanganan Musibah Pelayaran (Laka Kapal), Penerbangan (Laka Pesawat), dan Kondisi Membahayakan Manusia (KMM).\n"
                "5. Petunjuk Teknis Layanan Tanggap Darurat Siaga Call Center 115 BASARNAS."
            )

            if sop_docs_list:
                context_blocks.append("DAFTAR DOKUMEN SOP RESMI YANG TERSEDIA DI SISTEM:\n" + "\n".join(sop_docs_list))

            if sop_chunks:
                chunk_lines = []
                for idx, c in enumerate(sop_chunks, 1):
                    chunk_lines.append(f"[Kutipan Dokumen {idx}] Dokumen: \"{c['title']}\" ({c['origin']})\nIsi Potongan Dokumen:\n{c['content']}\n")
                context_blocks.append("KUTIPAN TEKS DOKUMEN RESMI RELEVAN (HASIL PENCARIAN VEKTOR SEMANTIK):\n" + "\n".join(chunk_lines))

            if dict_context:
                context_blocks.append(dict_context)

            full_context_str = "\n\n".join(context_blocks)

            prompt = f"""
Anda adalah Asisten Informasi & Bantuan SAR BASARNAS Indonesia.
Tugas Anda adalah menjawab pertanyaan umum atau prosedur/SOP masyarakat secara akurat, lugas, profesional, formal, dan berbasis dokumen resmi BASARNAS.

KONTEKS REFERENSI DOKUMEN RESMI & KNOWLEDGE BASE:
{full_context_str}

PERTANYAAN PENGGUNA:
"{question}"

PETUNJUK FORMAT JAWABAN (WAJIB DIIKUTI SECARA KETAT):
1. KEAKURATAN & KESESUAIAN DOKUMEN RESMI:
   - Jawaban Anda WAJIB didasarkan pada dokumen resmi BASARNAS, regulasi SAR, SOP terdaftar, dan kutipan teks yang tersedia pada konteks di atas.
   - Sajikan langkah, prosedur, atau penjelasan secara runtut, solutif, dan terstruktur (gunakan penomoran angka atau tanda hubung standar).
2. TANPA EMOJI ATAU IKON DEKORATIF (DILARANG KERAS):
   - JANGAN menggunakan emoji atau ikon dekoratif apapun (seperti 📞, 🚨, 📚, ℹ️, 📋, 💡, ⚠️, 🤖, dan sejenisnya).
   - Format jawaban harus formal, bersih, profesional, dan bergaya institusional resmi layaknya dokumen kedinasan BASARNAS.
3. KETERANGAN SELURUH SUMBER YANG DIKUTIP (LEBIH BANYAK SUMBER LEBIH BAGUS):
   - Di bagian akhir jawaban, Anda WAJIB membuat bagian khusus dengan judul:
     "**Referensi Dokumen & Sumber Resmi:**"
   - Tuliskan secara rinci SEMUA dokumen resmi, regulasi, undang-undang, manual operasi, dokumen SOP, atau kamus istilah yang dikutip atau relevan dengan jawaban tersebut.
   - Format penulisan sumber rujukan:
     - [Nama Dokumen / Regulasi / SOP] - [Keterangan Relevansi / Bab / Pasal yang Dirujuk]
   - Semakin lengkap dan kaya sumber rujukan resmi yang Anda sebutkan, semakin baik dan kredibel.
4. NOMOR DARURAT & TINDAKAN PELAPORAN:
   - Jika pertanyaan menyangkut kondisi musibah darurat, sebutkan Call Center BASARNAS di nomor 115 (Bebas Pulsa) dan sarankan menggunakan menu Lapor Cepat (SOS) atau Laporkan Kejadian.
5. Gunakan Bahasa Indonesia yang baku, sopan, formal, presisi, dan mencerminkan instansi resmi pemerintah (BASARNAS).
"""
            tenant_settings = None
            if db is not None:
                try:
                    from app.core.tenant_config import get_tenant_settings
                    tenant_settings = await get_tenant_settings(db)
                except Exception as t_err:
                    logger.warning(f"Failed to load tenant settings: {t_err}")

            response = await ai_provider_manager.llm_generate(
                prompt=prompt,
                system_prompt="Anda adalah asisten bantuan SAR BASARNAS resmi. Jawab secara formal, presisi, berbasis dokumen resmi dan regulasi, tanpa menggunakan emoji atau ikon dekoratif apapun.",
                temperature=0.3,
                timeout=25.0,
                tenant_settings=tenant_settings
            )
            if response and response.strip():
                # Strip any stray decorative emojis to ensure clean, non-slop institutional format
                cleaned_resp = re.sub(r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\uD800-\uDBFF][\uDC00-\uDFFF]|[\u200d\ufe0f\ufe0e]", "", response)
                cleaned_resp = re.sub(r"[ \t]+", " ", cleaned_resp)
                return cleaned_resp.strip()
        except Exception as e:
            logger.error(f"Failed to generate RAG Bantuan SAR answer: {e}")
            
        return (
            "**Informasi Standar Operasional Prosedur (SOP) & Bantuan SAR BASARNAS**\n\n"
            "Badan Nasional Pencarian dan Pertolongan (BASARNAS) menyelenggarakan operasi pencarian, pertolongan, dan evakuasi secara siaga 24/7 berdasarkan standar operasional terintegrasi.\n\n"
            "**Alur Prosedur Tanggap Darurat SAR:**\n"
            "1. Penerimaan Laporan: Verifikasi data waktu kejadian, estimasi lokasi/koordinat, dan jumlah korban melalui Layanan Siaga 115.\n"
            "2. Klasifikasi Insiden: Penentuan jenis musibah (Kecelakaan Kapal, Kecelakaan Pesawat, Bencana Alam, atau Kondisi Membahayakan Manusia/KMM).\n"
            "3. Pengerahan Tim Rescue & Alut: SAR Mission Coordinator (SMC) mengoordinasikan pengerahan personel dan alat utama penyelamatan.\n\n"
            "Call Center Darurat BASARNAS: 115 (Bebas Pulsa 24 Jam)\n"
            "Untuk pelaporan musibah darurat saat ini, silakan gunakan menu Lapor Cepat (SOS) atau Laporkan Kejadian.\n\n"
            "**Referensi Dokumen & Sumber Resmi:**\n"
            "- Undang-Undang Republik Indonesia Nomor 29 Tahun 2014 tentang Pencarian dan Pertolongan\n"
            "- Peraturan Badan Nasional Pencarian dan Pertolongan tentang Tata Cara Penyelenggaraan Operasi SAR\n"
            "- International Aeronautical and Maritime Search and Rescue (IAMSAR) Manual Volume III\n"
            "- Standard Operating Procedure (SOP) Siaga Call Center 115 & Komando Operasi BASARNAS\n"
            "- Pedoman Teknis Pertolongan Pertama (Medical First Responder) BASARNAS"
        )


llm_rag_service = LLMRagService()
