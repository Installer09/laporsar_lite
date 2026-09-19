import pytest
from app.services.autocorrect_service import AutoCorrectService

def test_autocorrect_clean_message_basic():
    """Test basic word replacement with exact and case-insensitive matches."""
    # 1. Setup mock mappings in AutoCorrectService
    AutoCorrectService._synonym_mappings = {
        "pompog": "pompong",
        "kelem": "tenggelam",
        "senoa": "Pulau Senoa",
        "tigo": "3"
    }
    
    # 2. Test exact match replacement
    msg = "ada pompog mati mesin dekat senoa"
    cleaned = AutoCorrectService.clean_message(msg)
    assert cleaned == "ada pompong mati mesin dekat Pulau Senoa"

    # 3. Test case-insensitive replacement
    msg_case = "Ada Pompog Mati Mesin dekat Senoa"
    cleaned_case = AutoCorrectService.clean_message(msg_case)
    assert cleaned_case == "Ada pompong Mati Mesin dekat Pulau Senoa"

def test_autocorrect_word_boundaries():
    """Test that only whole words are replaced and partial words inside others are ignored."""
    AutoCorrectService._synonym_mappings = {
        "pompog": "pompong",
        "kelem": "tenggelam"
    }
    
    # "pompogan" should NOT be replaced, but "pompog" should
    msg = "pompog di perairan pompogan"
    cleaned = AutoCorrectService.clean_message(msg)
    assert cleaned == "pompong di perairan pompogan"

    # "kelem" should be replaced, "kelempang" or "mengelem" should not
    msg2 = "kapal kelem saat mereka mengelem barang"
    cleaned2 = AutoCorrectService.clean_message(msg2)
    assert cleaned2 == "kapal tenggelam saat mereka mengelem barang"

def test_autocorrect_empty_or_no_mappings():
    """Test safety with empty inputs or when mappings are empty."""
    AutoCorrectService._synonym_mappings = {}
    
    msg = "ada pompog kelem"
    cleaned = AutoCorrectService.clean_message(msg)
    assert cleaned == msg
    
    cleaned_none = AutoCorrectService.clean_message(None)
    assert cleaned_none is None
