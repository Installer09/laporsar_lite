import asyncio
import sys
import os

# Ensure the app package is discoverable
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from app.db.session import get_tenant_sessionmaker

async def migrate():
    print("Memulai migrasi kolom 'icon' pada tabel 'locations'...")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL is not set.")
        return
    session_maker = get_tenant_sessionmaker(db_url)
    async with session_maker() as db:
        try:
            # Pengecekan kolom di PostgreSQL
            query = text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='locations' AND column_name='icon'"
            )
            res = await db.execute(query)
            exists = res.scalar()
            
            if not exists:
                print("Kolom 'icon' belum ada. Menambahkan kolom...")
                await db.execute(text("ALTER TABLE locations ADD COLUMN icon VARCHAR(50)"))
                await db.commit()
                print("Kolom 'icon' berhasil ditambahkan ke tabel 'locations'!")
            else:
                print("Kolom 'icon' sudah ada di tabel 'locations'. Tidak ada tindakan diperlukan.")
        except Exception as e:
            await db.rollback()
            print(f"Terjadi kesalahan saat migrasi: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(migrate())
