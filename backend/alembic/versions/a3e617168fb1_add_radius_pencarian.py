"""Add radius_pencarian Column

Revision ID: a3e617168fb1
Revises: 5f0ff10f8080
Create Date: 2026-05-29 21:57:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3e617168fb1'
down_revision: Union[str, Sequence[str], None] = '5f0ff10f8080'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch_alter_table or simply add_column (since we ran it already, this handles cases when recreating db)
    # Alembic handles safety if column exists, but to be safe:
    try:
        op.add_column('reports', sa.Column('radius_pencarian', sa.Float(), nullable=True, server_default='2.0'))
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_column('reports', 'radius_pencarian')
    except Exception:
        pass
