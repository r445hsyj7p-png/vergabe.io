"""add app_settings table

Revision ID: 002
Revises: 001
Create Date: 2025-01-02
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key   VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_settings")
