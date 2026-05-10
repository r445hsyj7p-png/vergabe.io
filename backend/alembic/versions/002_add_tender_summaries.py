"""add tender_summaries table

Revision ID: 002
Revises: 001
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tender_summaries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tender_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenders.id', ondelete='CASCADE'),
                  unique=True, nullable=False),
        sa.Column('summary_text', sa.Text, nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100)),
        sa.Column('cost_cents', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_summaries_tender_id', 'tender_summaries', ['tender_id'])


def downgrade() -> None:
    op.drop_table('tender_summaries')
