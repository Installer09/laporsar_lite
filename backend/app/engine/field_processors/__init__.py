from app.engine.field_processors.base import BaseFieldProcessor
from app.engine.field_processors.time import WaktuFieldProcessor as TimeFieldProcessor
from app.engine.field_processors.location import LokasiFieldProcessor as LocationFieldProcessor
from app.engine.field_processors.victim import KorbanFieldProcessor as VictimFieldProcessor
from app.engine.field_processors.victim_condition import KorbanKondisiFieldProcessor as VictimConditionFieldProcessor
from app.engine.field_processors.victim_data import DataKorbanFieldProcessor as VictimDataFieldProcessor
from app.engine.field_processors.coordinate import KoordinatFieldProcessor as CoordinateFieldProcessor
from app.engine.field_processors.reporter_location import ReporterLocationFieldProcessor
from app.engine.field_processors.vehicle import VehicleFieldProcessor
from app.engine.field_processors.default import DefaultFieldProcessor

# Backward compatibility class aliases
WaktuFieldProcessor = TimeFieldProcessor
LokasiFieldProcessor = LocationFieldProcessor
KorbanFieldProcessor = VictimFieldProcessor
KorbanKondisiFieldProcessor = VictimConditionFieldProcessor
DataKorbanFieldProcessor = VictimDataFieldProcessor
KoordinatFieldProcessor = CoordinateFieldProcessor

def get_field_processor(field_name: str) -> BaseFieldProcessor:
    """Registry function to resolve a field name to its corresponding FieldProcessor."""
    norm = (field_name or "").lower().strip()
    if norm in ("waktu", "incident_time", "time"):
        return TimeFieldProcessor()
    elif norm in ("lokasi_teks", "location_text", "lokasi", "location"):
        return LocationFieldProcessor()
    elif norm in ("korban", "victim_summary", "victim"):
        return VictimFieldProcessor()
    elif norm in ("korban_kondisi", "victim_condition"):
        return VictimConditionFieldProcessor()
    elif norm in ("data_korban", "victim_data"):
        return VictimDataFieldProcessor()
    elif norm in ("koordinat", "coordinate", "coordinates"):
        return CoordinateFieldProcessor()
    elif norm in ("reporter_location", "lokasi_pelapor"):
        return ReporterLocationFieldProcessor()
    elif norm in ("data_kapal", "data_pesawat", "data_alat", "vehicle_data", "vehicle"):
        return VehicleFieldProcessor(field_name)
    else:
        return DefaultFieldProcessor(field_name)
