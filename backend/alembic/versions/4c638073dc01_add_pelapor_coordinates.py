"""add_pelapor_coordinates

Revision ID: 4c638073dc01
Revises: be870f5c23af
Create Date: 2026-06-21 08:08:13.069668

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
"""add_pelapor_coordinates

Revision ID: 4c638073dc01
Revises: be870f5c23af
Create Date: 2026-06-21 08:08:13.069668

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c638073dc01'
down_revision: Union[str, Sequence[str], None] = 'be870f5c23af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reports', sa.Column('pelapor_lat', sa.Float(), nullable=True))
    op.add_column('reports', sa.Column('pelapor_lng', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reports', 'pelapor_lat')
    op.drop_column('reports', 'pelapor_lng')
