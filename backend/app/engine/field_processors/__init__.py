from app.engine.field_processors.base import BaseFieldProcessor
from app.engine.field_processors.waktu import WaktuFieldProcessor
from app.engine.field_processors.lokasi import LokasiFieldProcessor
from app.engine.field_processors.korban import KorbanFieldProcessor
from app.engine.field_processors.korban_kondisi import KorbanKondisiFieldProcessor
from app.engine.field_processors.data_korban import DataKorbanFieldProcessor
from app.engine.field_processors.koordinat import KoordinatFieldProcessor
from app.engine.field_processors.reporter_location import ReporterLocationFieldProcessor
from app.engine.field_processors.vehicle import VehicleFieldProcessor
from app.engine.field_processors.default import DefaultFieldProcessor

def get_field_processor(field_name: str) -> BaseFieldProcessor:
    """Registry function to resolve a field name to its corresponding FieldProcessor."""
    if field_name == "waktu":
        return WaktuFieldProcessor()
    elif field_name == "lokasi_teks":
        return LokasiFieldProcessor()
    elif field_name == "korban":
        return KorbanFieldProcessor()
    elif field_name == "korban_kondisi":
        return KorbanKondisiFieldProcessor()
    elif field_name == "data_korban":
        return DataKorbanFieldProcessor()
    elif field_name == "koordinat":
        return KoordinatFieldProcessor()
    elif field_name == "reporter_location":
        return ReporterLocationFieldProcessor()
    elif field_name in ("data_kapal", "data_pesawat", "data_alat"):
        return VehicleFieldProcessor(field_name)
    else:
        return DefaultFieldProcessor(field_name)
