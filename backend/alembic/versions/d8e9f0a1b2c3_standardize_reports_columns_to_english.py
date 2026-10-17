"""standardize_reports_columns_to_english

Revision ID: d8e9f0a1b2c3
Revises: c7b8e1a2f3d4
Create Date: 2026-10-17 18:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c7b8e1a2f3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMN_RENAMES = {
    "no_laporan": "report_number",
    "pelapor_nama": "reporter_name",
    "pelapor_nomor": "reporter_phone",
    "pelapor_lat": "reporter_lat",
    "pelapor_lng": "reporter_lng",
    "jenis_kejadian": "incident_type",
    "waktu": "incident_time",
    "lokasi_teks": "location_text",
    "koordinat_lat": "latitude",
    "koordinat_lng": "longitude",
    "pos_sar_terdekat": "nearest_sar_post",
    "jarak_nm": "distance_nm",
    "jarak_ke_lokasi": "distance_nm",
    "arah_derajat": "heading_degree",
    "heading_ke_lokasi": "heading_degree",
    "radius_pencarian": "search_radius_km",
    "korban": "victim_summary",
    "korban_total": "total_victims",
    "korban_selamat": "survived_victims",
    "korban_meninggal": "deceased_victims",
    "korban_hilang": "missing_victims",
    "data_korban": "victim_data",
    "metadata_kejadian": "incident_metadata",
    "unsur_alut": "resources_deployed",
    "kronologi": "chronology",
    "bukti_id": "evidence_id",
    "eviden_id": "evidence_id",
    "info_awal_text": "initial_report_text",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reports" not in inspector.get_table_names():
        return

    existing_cols = {col["name"] for col in inspector.get_columns("reports")}

    for old_col, new_col in COLUMN_RENAMES.items():
        if old_col in existing_cols and new_col not in existing_cols:
            op.alter_column("reports", old_col, new_column_name=new_col)
            existing_cols.remove(old_col)
            existing_cols.add(new_col)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reports" not in inspector.get_table_names():
        return

    existing_cols = {col["name"] for col in inspector.get_columns("reports")}
    reverse_renames = {
        "report_number": "no_laporan",
        "reporter_name": "pelapor_nama",
        "reporter_phone": "pelapor_nomor",
        "reporter_lat": "pelapor_lat",
        "reporter_lng": "pelapor_lng",
        "incident_type": "jenis_kejadian",
        "incident_time": "waktu",
        "location_text": "lokasi_teks",
        "latitude": "koordinat_lat",
        "longitude": "koordinat_lng",
        "nearest_sar_post": "pos_sar_terdekat",
        "distance_nm": "jarak_nm",
        "heading_degree": "arah_derajat",
        "search_radius_km": "radius_pencarian",
        "victim_summary": "korban",
        "total_victims": "korban_total",
        "survived_victims": "korban_selamat",
        "deceased_victims": "korban_meninggal",
        "missing_victims": "korban_hilang",
        "victim_data": "data_korban",
        "incident_metadata": "metadata_kejadian",
        "resources_deployed": "unsur_alut",
        "chronology": "kronologi",
        "evidence_id": "bukti_id",
        "initial_report_text": "info_awal_text",
    }

    for eng_col, id_col in reverse_renames.items():
        if eng_col in existing_cols and id_col not in existing_cols:
            op.alter_column("reports", eng_col, new_column_name=id_col)
            existing_cols.remove(eng_col)
            existing_cols.add(id_col)
