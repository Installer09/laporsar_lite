"""add postgis and location_geom spatial column

Revision ID: 9f99a8f27c3d
Revises: 44d8c47ed9ab
Create Date: 2026-07-21 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = '9f99a8f27c3d'
down_revision: Union[str, Sequence[str], None] = '44d8c47ed9ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure postgis extension is created
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    
    # Add location_geom column to reports
    try:
        op.add_column('reports', sa.Column('location_geom', Geometry(geometry_type='POINT', srid=4326), nullable=True))
    except Exception as e:
        print(f"Column location_geom add note: {e}")
        
    # Create GIST spatial index
    try:
        op.execute("CREATE INDEX IF NOT EXISTS idx_reports_location_geom ON reports USING GIST (location_geom);")
    except Exception as e:
        print(f"Spatial index creation note: {e}")

    # Populate location_geom for existing records with coordinates
    try:
        op.execute("""
            UPDATE reports 
            SET location_geom = ST_SetSRID(ST_MakePoint(koordinat_lng, koordinat_lat), 4326)
            WHERE koordinat_lat IS NOT NULL AND koordinat_lng IS NOT NULL AND location_geom IS NULL;
        """)
    except Exception as e:
        print(f"Data migration for location_geom note: {e}")


def downgrade() -> None:
    try:
        op.execute("DROP INDEX IF EXISTS idx_reports_location_geom;")
        op.drop_column('reports', 'location_geom')
    except Exception:
        pass
