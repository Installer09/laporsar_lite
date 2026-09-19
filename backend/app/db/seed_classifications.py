import logging
import json
from sqlalchemy.future import select
from app.models.settings_models import Classification
from app.models.master_models import Tenant
from app.db.session import MasterSessionLocal, get_tenant_sessionmaker

logger = logging.getLogger(__name__)

# Fallback/default classifications if pusat database is not accessible
DEFAULT_CLASSIFICATIONS = [
    {
        "category": "Kecelakaan Kapal",
        "keywords": "Kecelakaan Kapal, Laka Kapal, kapal tenggelam, kapal tubrukan, kapal terbakar, kapal kandas, kapal mati mesin, kapal hilang kontak, kapal terbalik, orang jatuh dari kapal ke air, evakuasi medis terhadap orang di atas kapal, pompong mati mesin, pompong tenggelam, pompong terbalik, pompong kandas, perahu terbalik, perahu tenggelam, speedboat, pompong"
    },
    {
        "category": "Kecelakaan Pesawat",
        "keywords": "Kecelakaan Pesawat, Laka Pesawat, pesawat udara jatuh, pesawat udara terbakar, helikopter jatuh, helikopter terbakar, pesawat mendarat darurat, pesawat tergelincir, pesawat hilang kontak"
    },
    {
        "category": "Kondisi Membahayakan Manusia",
        "keywords": "Kondisi Membahayakan Manusia, KMM, orang tercebur, orang tenggelam, percobaan bunuh diri, terjebak di lift, terjebak di reruntuhan bangunan, tersesat di gunung, tersesat di hutan, terjebak dalam ruang terbatas, diterkam buaya, diserang hewan liar, hanyut di sungai, hanyut di pantai"
    },
    {
        "category": "Bencana",
        "keywords": "Bencana, tanah longsor, longsor, gagal teknologi, konflik sosial, kebakaran hutan, gempa bumi, gempa, tsunami, gunung meletus, banjir, angin topan, angin puting beliung"
    },
    {
        "category": "Kecelakaan dengan Penanganan Khusus",
        "keywords": "Kecelakaan dengan Penanganan Khusus, KPK, Laka Lantas, kecelakaan kereta api, kecelakaan kendaraan bermotor, kecelakaan mobil, kecelakaan motor, mobil tabrakan, motor tabrakan, mobil masuk jurang"
    }
]

async def sync_classifications_from_center(db):
    """
    Synchronizes basic classifications from the 'pusat' tenant to the target tenant database.
    If 'pusat' is not reachable or empty, seeds the default BASARNAS classifications.
    Additional classifications on the target tenant database remain untouched.
    """
    source_classifications = []
    
    # 1. Attempt to fetch classifications from the 'pusat' tenant database
    try:
        async with MasterSessionLocal() as master_db:
            result = await master_db.execute(select(Tenant).where(Tenant.slug == "pusat"))
            pusat_tenant = result.scalar_one_or_none()
            
        if pusat_tenant:
            pusat_session_maker = get_tenant_sessionmaker(pusat_tenant.db_url)
            async with pusat_session_maker() as pusat_db:
                res = await pusat_db.execute(select(Classification))
                source_classifications = res.scalars().all()
                if source_classifications:
                    logger.info(f"Retrieved {len(source_classifications)} classifications from 'pusat' database.")
    except Exception as ex:
        logger.warning(f"Could not fetch classifications from 'pusat' tenant database: {ex}. Falling back to default list.")
        
    # Convert retrieved classifications to a list of dicts
    if source_classifications:
        base_data = [
            {"category": c.category, "keywords": c.keywords}
            for c in source_classifications
        ]
    else:
        base_data = DEFAULT_CLASSIFICATIONS
        
    # 2. Sync into the target tenant database
    synced_count = 0
    added_count = 0
    for item in base_data:
        category_name = item["category"]
        keywords_str = item["keywords"]
        
        # Check if category already exists in target tenant
        res_target = await db.execute(select(Classification).where(Classification.category == category_name))
        existing = res_target.scalar_one_or_none()
        
        if not existing:
            new_cls = Classification(category=category_name, keywords=keywords_str)
            db.add(new_cls)
            added_count += 1
        else:
            # Update keywords if they are different to keep basic classifications in sync
            if existing.keywords != keywords_str:
                existing.keywords = keywords_str
                db.add(existing)
                synced_count += 1
                
    try:
        await db.commit()
        logger.info(f"Classifications sync complete: {added_count} categories added, {synced_count} categories updated.")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save synced classifications: {e}")
        raise e
