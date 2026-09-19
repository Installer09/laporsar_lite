import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.engine.field_processors.base import BaseFieldProcessor

logger = logging.getLogger(__name__)

class LokasiFieldProcessor(BaseFieldProcessor):
    """Processes and validates the incident location ('lokasi_teks') field."""

    async def validate_and_extract(
        self, message: str, session: ChatSession, extracted_data: dict, db: AsyncSession
    ) -> tuple[bool, dict | str]:
        answer_clean = message.strip()
        
        from app.services.rule_extractor import RuleExtractor
        coords = RuleExtractor.extract_koordinat(answer_clean)
        
        if coords:
            extracted_data["koordinat_lat"] = coords[0]
            extracted_data["koordinat_lng"] = coords[1]
            extracted_data["_explicit_koordinat"] = True
            try:
                from app.services.geocoding_service import geocoding_service
                resolved_name = await geocoding_service.reverse_geocode(coords[0], coords[1])
                if resolved_name:
                    enriched_lokasi = await geocoding_service.enrich_location_with_island(
                        coords[0], coords[1], resolved_name
                    )
                    extracted_data["lokasi_teks"] = enriched_lokasi
                else:
                    extracted_data["lokasi_teks"] = f"Koordinat {coords[0]:.4f}, {coords[1]:.4f}"
            except Exception as e:
                logger.warning(f"Reverse-geocoding failed: {e}")
                extracted_data["lokasi_teks"] = f"Koordinat {coords[0]:.4f}, {coords[1]:.4f}"
        else:
            # Island proximity -> Perairan format
            normalized_lokasi = answer_clean
            islands = ["senoa", "jemaja", "subi", "midai", "serasan", "panjang", "tiga", "sedanau", "laut", "pulau"]
            
            match_dekat = re.search(r'\b(?:di\s+)?dekat\s+([a-zA-Z0-9\s]+)', answer_clean, re.IGNORECASE)
            if match_dekat:
                place = match_dekat.group(1).strip()
                if any(isl in place.lower() for isl in islands):
                    normalized_lokasi = re.sub(
                        r'\b(?:di\s+)?dekat\s+' + re.escape(place),
                        f"Perairan {place}",
                        answer_clean,
                        flags=re.IGNORECASE
                    )
            
            extracted_data["lokasi_teks"] = normalized_lokasi
            
            # Geocode location name automatically
            try:
                from app.services.geocoding_service import geocoding_service
                geo = await geocoding_service.geocode_location(normalized_lokasi, db=db)
                if geo:
                    extracted_data["koordinat_lat"] = geo[0]
                    extracted_data["koordinat_lng"] = geo[1]
            except Exception as e:
                logger.warning(f"Auto-geocoding failed for {normalized_lokasi}: {e}")
                
        return True, extracted_data

    def get_question(self, session: ChatSession, extracted_data: dict) -> tuple[str, list]:
        q_text = (
            "📍 *Di mana lokasi kejadiannya?*\n"
            "Sebutkan nama pantai, laut, desa, atau patokan terdekat yang Anda ketahui."
        )
        return q_text, ["Belum Tahu"]
