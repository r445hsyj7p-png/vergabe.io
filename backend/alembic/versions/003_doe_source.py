"""seed all sources (doe, nrw, berlin)

Revision ID: 003
Revises: 002
Create Date: 2025-05-30
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO sources (name, slug, source_type, is_active)
        VALUES
            ('TED Europa',                       'ted',    'api', true),
            ('service.bund.de',                  'bund',   'rss', true),
            ('Datenservice Öffentlicher Einkauf', 'doe',    'api', true),
            ('Vergabemarktplatz NRW',             'nrw',    'api', true),
            ('Vergabeplattform Berlin',           'berlin', 'rss', true)
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM sources WHERE slug IN ('doe', 'nrw', 'berlin')")
