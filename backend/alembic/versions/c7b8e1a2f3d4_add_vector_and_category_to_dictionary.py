"""add_vector_and_category_to_dictionary

Revision ID: c7b8e1a2f3d4
Revises: 4c638073dc01, 9f99a8f27c3d
Create Date: 2026-10-02 15:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector


# revision identifiers, used by Alembic.
revision: str = 'c7b8e1a2f3d4'
down_revision: Union[str, Sequence[str], None] = ('4c638073dc01', '9f99a8f27c3d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension is created
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    except Exception:
        pass

    # Add new standardized columns to dictionary_words
    try:
        op.add_column('dictionary_words', sa.Column('category', sa.String(length=50), nullable=True, server_default='OPERASIONAL_SAR'))
        op.create_index(op.f('ix_dictionary_words_category'), 'dictionary_words', ['category'], unique=False)
    except Exception as e:
        print(f"Column category note: {e}")

    try:
        op.add_column('dictionary_words', sa.Column('canonical_name', sa.String(length=100), nullable=True))
    except Exception as e:
        print(f"Column canonical_name note: {e}")

    try:
        op.add_column('dictionary_words', sa.Column('semantic_description', sa.Text(), nullable=True))
    except Exception as e:
        print(f"Column semantic_description note: {e}")

    try:
        op.add_column('dictionary_words', sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True))
    except Exception as e:
        print(f"Column embedding note: {e}")


def downgrade() -> None:
    try:
        op.drop_column('dictionary_words', 'embedding')
        op.drop_column('dictionary_words', 'semantic_description')
        op.drop_column('dictionary_words', 'canonical_name')
        op.drop_index(op.f('ix_dictionary_words_category'), table_name='dictionary_words')
        op.drop_column('dictionary_words', 'category')
    except Exception as e:
        print(f"Downgrade note: {e}")
