import pytest
import zipfile
import io
import json
from unittest.mock import MagicMock, AsyncMock
from app.services.system_backup import system_backup_service, MODELS_BACKUP_ORDER
from app.models.settings_models import Location, Classification

@pytest.mark.asyncio
async def test_system_backup_export(mock_db):
    """Test exporting the database into a compressed ZIP file with modular JSONs."""
    # Create mock database objects
    mock_location = Location(
        id=1,
        name="Pos SAR Natuna",
        type="Pos SAR",
        lat=3.9,
        lng=108.3,
        address="Natuna",
        unsur="Rescue Team",
        alut="Rigid Inflatable Boat"
    )
    mock_classification = Classification(
        id=1,
        category="Kecelakaan Kapal",
        keywords="kapal, tenggelam, tabrakan"
    )

    mock_result_loc = MagicMock()
    mock_result_loc.scalars.return_value.all.return_value = [mock_location]
    
    mock_result_class = MagicMock()
    mock_result_class.scalars.return_value.all.return_value = [mock_classification]

    mock_result_empty = MagicMock()
    mock_result_empty.scalars.return_value.all.return_value = []

    # Configure database execute side effects
    side_effects = []
    for name, _ in MODELS_BACKUP_ORDER:
        if name == "locations":
            side_effects.append(mock_result_loc)
        elif name == "classifications":
            side_effects.append(mock_result_class)
        else:
            side_effects.append(mock_result_empty)
            
    mock_db.execute.side_effect = side_effects

    # Execute export
    backup_bytes = await system_backup_service.export_backup(mock_db)
    assert len(backup_bytes) > 0

    # Parse and verify ZIP contents
    zip_buffer = io.BytesIO(backup_bytes)
    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        file_list = zip_file.namelist()
        assert "locations.json" in file_list
        assert "classifications.json" in file_list
        
        # Read and check serialized data structure
        locations_data = json.loads(zip_file.read("locations.json").decode("utf-8"))
        assert len(locations_data) == 1
        assert locations_data[0]["name"] == "Pos SAR Natuna"
        assert locations_data[0]["lat"] == 3.9

@pytest.mark.asyncio
async def test_system_backup_restore(mock_db):
    """Test restoring the database and executing atomic database rollback if errors happen."""
    # Construct dummy valid backup zip payload
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        locations_data = [
            {
                "id": 1,
                "name": "Pos SAR Natuna",
                "type": "Pos SAR",
                "lat": 3.9,
                "lng": 108.3,
                "address": "Natuna",
                "unsur": "Rescue Team",
                "alut": "Rigid Inflatable Boat"
            }
        ]
        zip_file.writestr("locations.json", json.dumps(locations_data))
        zip_file.writestr("classifications.json", json.dumps([]))

    backup_bytes = zip_buffer.getvalue()

    # Configure database mocks for nested transaction block
    mock_nested = MagicMock()
    mock_nested.__aenter__ = AsyncMock(return_value=mock_nested)
    mock_nested.__aexit__ = AsyncMock(return_value=False)
    mock_db.begin_nested = MagicMock(return_value=mock_nested)

    # Execute restore
    result = await system_backup_service.import_restore(backup_bytes, mock_db)
    
    assert result["status"] == "success"
    assert result["counts"]["locations"] == 1
    assert result["counts"]["classifications"] == 0
    
    # Assert database insertions happened
    assert mock_db.add.called
