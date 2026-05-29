"""add app_settings table

Revision ID: 002
Revises: 001
Create Date: 2025-01-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa_inspect(op.get_bind()).has_table("app_settings"):
        op.create_table(
            "app_settings",
            sa.Column("key", sa.String(100), primary_key=True),
            sa.Column("value", sa.Text, nullable=False),
        )


def downgrade() -> None:
    op.drop_table("app_settings")
