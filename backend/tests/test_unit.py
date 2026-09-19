import pytest
from app.services.message_formatter import message_formatter
from app.schemas.nlp_schemas import SARExtractedFields

def test_message_formatter_null_safety():
    """Test that message formatter safely handles missing/null values."""
    template = "INFO: {{WAKTU_KEJADIAN}} - {{LOKASI_KEJADIAN}}"
    
    # 1. Test missing keys entirely
    data = {}
    result = message_formatter.render(template, data)
    assert result == "INFO: Belum Diketahui - Belum Diketahui"
    
    # 2. Test None values
    data2 = {"WAKTU_KEJADIAN": None, "LOKASI_KEJADIAN": ""}
    result2 = message_formatter.render(template, data2)
    assert result2 == "INFO: Belum Diketahui - Belum Diketahui"

def test_message_formatter_korban_parsing():
    """Test that message formatter handles RINCIAN_KORBAN list conversion."""
    template = "{{RINCIAN_KORBAN}}"
    
    # 1. Test list input
    data = {
        "data_korban": [{"nama": "Budi", "umur": "25", "jenis_kelamin": "L", "alamat": "Jakarta", "kondisi": "Meninggal"}]
    }
    result = message_formatter.render(template, data)
    assert "- Nama : Budi (L/25 Thn)" in result
    assert "- Alamat : Jakarta" in result
    
    # 2. Test stringified list input
    data_str = {
        "data_korban": '[{"nama": "Andi"}]'
    }
    result_str = message_formatter.render(template, data_str)
    assert "- Nama : Andi" in result_str
    assert "- Alamat : " in result_str

def test_nlp_schema_strictness():
    """Test that SARExtractedFields handles weird null types from LLM."""
    
    # Simulate LLM returning literal "null", "-", or "unknown" strings
    mock_llm_output = {
        "waktu": "null",
        "lokasi_teks": "Unknown",
        "jenis_kejadian": "-",
        "korban": "Belum diketahui",
        "data_korban": []
    }
    
    validated = SARExtractedFields(**mock_llm_output)
    assert validated.waktu is None
    assert validated.lokasi_teks is None
    assert validated.jenis_kejadian is None
    assert validated.korban is None
    assert validated.data_korban == []

    # Simulate LLM putting dict/list into a string field
    mock_llm_output_list = {
        "waktu": "Sekarang",
        "korban": [{"nama": "Budi"}] # This is a list, but schema expects str
    }
    
    validated2 = SARExtractedFields(**mock_llm_output_list)
    assert validated2.waktu == "Sekarang"
    assert "Budi" in validated2.korban
    assert isinstance(validated2.korban, str) # It should stringify the list

@pytest.mark.asyncio
async def test_get_dictionary_context_merging():
    from app.services.llm_rag import LLMRagService
    from app.models.knowledge_models import DictionaryWord
    from app.models.settings_models import Classification
    from unittest.mock import AsyncMock, MagicMock, patch

    # Mock Tenant DB session
    tenant_db = AsyncMock()
    tenant_db.info = {"tenant_slug": "natuna"}

    # Mock tenant word & classification
    local_word = DictionaryWord(
        word="nelayan",
        definition="Pelaku penangkapan ikan di laut lokal Natuna",
        status="APPROVED",
        is_typo_or_slang=False
    )
    local_class = Classification(
        category="Kecelakaan Kapal",
        keywords="kapal tenggelam di laut natuna"
    )

    # Mock master word & classification
    global_word = DictionaryWord(
        word="nelayan",
        definition="Orang yang mata pencaharian utamanya adalah menangkap ikan (Global)",
        status="APPROVED",
        is_typo_or_slang=False
    )
    global_word_other = DictionaryWord(
        word="abk",
        definition="Anak Buah Kapal (Global)",
        status="APPROVED",
        is_typo_or_slang=False
    )
    global_class = Classification(
        category="Kecelakaan Kapal",
        keywords="kapal tenggelam global"
    )
    global_class_other = Classification(
        category="Bencana",
        keywords="gempa bumi, banjir"
    )

    # Setup tenant_db execution mock
    tenant_result_words = MagicMock()
    tenant_result_words.scalars.return_value.all.return_value = [local_word]
    tenant_result_class = MagicMock()
    tenant_result_class.scalars.return_value.all.return_value = [local_class]

    # Mock tenant_db execute calls
    tenant_db.execute.side_effect = [tenant_result_words, tenant_result_class]

    # Mock MasterSessionLocal context manager
    master_db = AsyncMock()
    master_result_words = MagicMock()
    master_result_words.scalars.return_value.all.return_value = [global_word, global_word_other]
    master_result_class = MagicMock()
    master_result_class.scalars.return_value.all.return_value = [global_class, global_class_other]
    master_db.execute.side_effect = [master_result_words, master_result_class]

    master_session_mock = MagicMock()
    master_session_mock.__aenter__ = AsyncMock(return_value=master_db)
    master_session_mock.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.MasterSessionLocal", return_value=master_session_mock):
        service = LLMRagService()
        context_str = await service.get_dictionary_context(tenant_db)
        
        # Verify merges and overrides
        assert "- nelayan: Pelaku penangkapan ikan di laut lokal Natuna" in context_str
        assert "- nelayan: Orang yang mata pencaharian utamanya" not in context_str
        assert "- abk: Anak Buah Kapal" in context_str
        
        assert "- Kategori: KECELAKAAN KAPAL (Kata Kunci: kapal tenggelam di laut natuna)" in context_str
        assert "kapal tenggelam global" not in context_str
        assert "BENCANA" in context_str

@pytest.mark.asyncio
async def test_get_classifications_api_merging():
    from app.api.routes.settings import get_classifications
    from app.models.settings_models import Classification
    from unittest.mock import AsyncMock, MagicMock, patch

    # Mock Tenant DB
    tenant_db = AsyncMock()
    tenant_db.info = {"tenant_slug": "natuna"}

    local_class = Classification(category="Kecelakaan Kapal", keywords="kapal tenggelam lokal")
    global_class = Classification(category="Kecelakaan Kapal", keywords="kapal tenggelam global")
    global_class_other = Classification(category="Bencana", keywords="gempa bumi")

    tenant_result = MagicMock()
    tenant_result.scalars.return_value.all.return_value = [local_class]
    tenant_db.execute.return_value = tenant_result

    # Mock Master DB
    master_db = AsyncMock()
    master_result = MagicMock()
    master_result.scalars.return_value.all.return_value = [global_class, global_class_other]
    master_db.execute.return_value = master_result

    master_session_mock = MagicMock()
    master_session_mock.__aenter__ = AsyncMock(return_value=master_db)
    master_session_mock.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.MasterSessionLocal", return_value=master_session_mock):
        results = await get_classifications(tenant_db)
        
        # Verify merges: local overrides global
        assert len(results) == 2
        categories = {c.category: c for c in results}
        assert "Kecelakaan Kapal" in categories
        assert "Bencana" in categories
        
        # Kecelakaan Kapal is from tenant, so keywords should be "kapal tenggelam lokal" and is_global = False
        assert categories["Kecelakaan Kapal"].keywords == "kapal tenggelam lokal"
        assert categories["Kecelakaan Kapal"].is_global is False
        
        # Bencana is from master, so is_global = True
        assert categories["Bencana"].keywords == "gempa bumi"
        assert categories["Bencana"].is_global is True

@pytest.mark.asyncio
async def test_get_dictionary_api_merging():
    from app.api.routes.knowledge import get_dictionary
    from app.models.knowledge_models import DictionaryWord
    from unittest.mock import AsyncMock, MagicMock, patch

    tenant_db = AsyncMock()
    tenant_db.info = {"tenant_slug": "natuna"}

    local_word = DictionaryWord(word="nelayan", definition="lokal", created_at=None)
    global_word = DictionaryWord(word="nelayan", definition="global", created_at=None)
    global_word_other = DictionaryWord(word="abk", definition="global_abk", created_at=None)

    tenant_result = MagicMock()
    tenant_result.scalars.return_value.all.return_value = [local_word]
    tenant_db.execute.return_value = tenant_result

    master_db = AsyncMock()
    master_result = MagicMock()
    master_result.scalars.return_value.all.return_value = [global_word, global_word_other]
    master_db.execute.return_value = master_result

    master_session_mock = MagicMock()
    master_session_mock.__aenter__ = AsyncMock(return_value=master_db)
    master_session_mock.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.MasterSessionLocal", return_value=master_session_mock):
        results = await get_dictionary(db=tenant_db)
        assert len(results) == 2
        words = {w.word: w for w in results}
        assert "nelayan" in words
        assert "abk" in words
        assert words["nelayan"].definition == "lokal"
        assert words["nelayan"].is_global is False
        assert words["abk"].definition == "global_abk"
        assert words["abk"].is_global is True

@pytest.mark.asyncio
async def test_get_sop_api_merging():
    from app.api.routes.knowledge import get_sop_documents
    from app.models.knowledge_models import SOPDocument
    from unittest.mock import AsyncMock, MagicMock, patch

    tenant_db = AsyncMock()
    tenant_db.info = {"tenant_slug": "natuna"}

    local_sop = SOPDocument(title="SOP Natuna", filename="sop_natuna.pdf", created_at=None)
    global_sop = SOPDocument(title="SOP Nasional", filename="sop_nasional.pdf", created_at=None)

    tenant_result = MagicMock()
    tenant_result.scalars.return_value.all.return_value = [local_sop]
    tenant_db.execute.return_value = tenant_result

    master_db = AsyncMock()
    master_result = MagicMock()
    master_result.scalars.return_value.all.return_value = [global_sop]
    master_db.execute.return_value = master_result

    master_session_mock = MagicMock()
    master_session_mock.__aenter__ = AsyncMock(return_value=master_db)
    master_session_mock.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.MasterSessionLocal", return_value=master_session_mock):
        results = await get_sop_documents(db=tenant_db)
        assert len(results) == 2
        sops = {s.filename: s for s in results}
        assert "sop_natuna.pdf" in sops
        assert "sop_nasional.pdf" in sops
        assert sops["sop_natuna.pdf"].is_global is False
        assert sops["sop_nasional.pdf"].is_global is True

@pytest.mark.asyncio
async def test_write_protections_on_global_records():
    from app.api.routes.settings import update_classification, delete_classification
    from app.api.routes.knowledge import update_dictionary_word, delete_dictionary_word, delete_sop_document
    from fastapi import HTTPException
    from unittest.mock import AsyncMock, MagicMock, patch

    tenant_db = AsyncMock()
    tenant_db.info = {"tenant_slug": "natuna"}

    # Mock Master DB query returning a record to indicate that this ID is indeed global/master
    master_db = AsyncMock()
    master_result = MagicMock()
    master_result.scalar_one_or_none.return_value = MagicMock() # Mock returned global record
    master_db.execute.return_value = master_result

    master_session_mock = MagicMock()
    master_session_mock.__aenter__ = AsyncMock(return_value=master_db)
    master_session_mock.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.MasterSessionLocal", return_value=master_session_mock):
        # 1. Test update classification global
        from app.schemas.settings_schemas import ClassificationCreate
        try:
            await update_classification(class_id=1, class_update=ClassificationCreate(category="A", keywords="B"), db=tenant_db)
            assert False, "Should raise 403"
        except HTTPException as e:
            assert e.status_code == 403
            assert "Read-Only" in e.detail or "pusat" in e.detail

        # 2. Test delete classification global
        try:
            await delete_classification(class_id=1, db=tenant_db)
            assert False, "Should raise 403"
        except HTTPException as e:
            assert e.status_code == 403
            assert "Read-Only" in e.detail or "pusat" in e.detail

        # 3. Test update dictionary word global
        from app.schemas.knowledge_schemas import DictionaryWordUpdate
        try:
            await update_dictionary_word(word_id=1, word_update=DictionaryWordUpdate(definition="test"), db=tenant_db)
            assert False, "Should raise 403"
        except HTTPException as e:
            assert e.status_code == 403
            assert "read-only" in e.detail.lower() or "pusat" in e.detail.lower()

        # 4. Test delete dictionary word global
        try:
            await delete_dictionary_word(word_id=1, db=tenant_db)
            assert False, "Should raise 403"
        except HTTPException as e:
            assert e.status_code == 403
            assert "read-only" in e.detail.lower() or "pusat" in e.detail.lower()

        # 5. Test delete SOP document global
        try:
            await delete_sop_document(doc_id=1, db=tenant_db)
            assert False, "Should raise 403"
        except HTTPException as e:
            assert e.status_code == 403
            assert "read-only" in e.detail.lower() or "pusat" in e.detail.lower()
