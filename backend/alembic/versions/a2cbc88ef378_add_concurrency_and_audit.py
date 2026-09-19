"""add_concurrency_and_audit

Revision ID: a2cbc88ef378
Revises: 44d8c47ed9ab
Create Date: 2026-06-15 11:25:06.950452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a2cbc88ef378'
down_revision: Union[str, Sequence[str], None] = '44d8c47ed9ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create audit_logs table
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('target_id', sa.String(length=100), nullable=True),
    sa.Column('before_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('ip_address', sa.String(length=50), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_target_id'), 'audit_logs', ['target_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    
    # 2. Add version_id column to reports (with default value 1 for existing rows)
    op.add_column('reports', sa.Column('version_id', sa.Integer(), nullable=False, server_default='1'))
    op.alter_column('reports', 'version_id', server_default=None)

    # 3. Create composite indexes on reports
    op.create_index('idx_reports_jenis_created', 'reports', ['jenis_kejadian', 'created_at'], unique=False)
    op.create_index('idx_reports_status_created', 'reports', ['status', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop composite indexes
    op.drop_index('idx_reports_status_created', table_name='reports')
    op.drop_index('idx_reports_jenis_created', table_name='reports')

    # 2. Drop version_id column
    op.drop_column('reports', 'version_id')

    # 3. Drop audit_logs table and its indexes
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_timestamp'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_target_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')
