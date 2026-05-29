"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01
"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE source_status AS ENUM ('ok', 'warn', 'error', 'inactive');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tender_status AS ENUM ('open', 'closed', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tag_status AS ENUM ('interest', 'ignore');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE komunen_status AS ENUM ('auto', 'verified', 'excluded', 'pending_review');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name          VARCHAR(200) NOT NULL,
            slug          VARCHAR(100) NOT NULL UNIQUE,
            source_type   VARCHAR(50)  NOT NULL,
            base_url      TEXT,
            scraper_class VARCHAR(100),
            config        JSONB,
            interval_hours INTEGER NOT NULL DEFAULT 6,
            is_active     BOOLEAN NOT NULL DEFAULT true,
            status        source_status NOT NULL DEFAULT 'ok',
            last_run_at   TIMESTAMPTZ,
            last_run_entries INTEGER NOT NULL DEFAULT 0
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tenders (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            canonical_id          UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
            title                 TEXT NOT NULL,
            description           TEXT,
            contracting_authority VARCHAR(500),
            authority_address     TEXT,
            authority_email       VARCHAR(300),
            authority_phone       VARCHAR(100),
            deadline              TIMESTAMPTZ,
            publication_date      TIMESTAMPTZ,
            value_min             BIGINT,
            value_max             BIGINT,
            currency              VARCHAR(10)  NOT NULL DEFAULT 'EUR',
            cpv_codes             VARCHAR[],
            it_category           VARCHAR(100),
            region                VARCHAR(200),
            country               VARCHAR(10)  NOT NULL DEFAULT 'DE',
            procedure_type        VARCHAR(200),
            tender_status         tender_status NOT NULL DEFAULT 'open',
            fulfillment_location  VARCHAR(300),
            external_id           VARCHAR(300),
            source_url            TEXT,
            content_hash          VARCHAR(64),
            raw_data              JSONB,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenders_deadline    ON tenders (deadline)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenders_it_category ON tenders (it_category)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenders_status      ON tenders (tender_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenders_created_at  ON tenders (created_at)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS tender_sources (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tender_id    UUID NOT NULL REFERENCES tenders(id)  ON DELETE CASCADE,
            source_id    UUID NOT NULL REFERENCES sources(id)  ON DELETE CASCADE,
            external_url TEXT,
            external_id  VARCHAR(300),
            platform_name VARCHAR(200),
            scraped_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tender_id, source_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS lots (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tender_id  UUID NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
            lot_number VARCHAR(50),
            title      TEXT,
            description TEXT,
            value_min  BIGINT,
            value_max  BIGINT,
            cpv_codes  VARCHAR[]
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS search_profiles (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name          VARCHAR(200) NOT NULL,
            keywords      TEXT[],
            cpv_codes     VARCHAR[],
            regions       VARCHAR[],
            it_categories VARCHAR[],
            min_value     BIGINT,
            deadline_days INTEGER,
            email         VARCHAR(300),
            is_active     BOOLEAN NOT NULL DEFAULT true,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tender_id  UUID NOT NULL UNIQUE REFERENCES tenders(id) ON DELETE CASCADE,
            status     tag_status NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            profile_id        UUID NOT NULL REFERENCES search_profiles(id) ON DELETE CASCADE,
            tender_id         UUID NOT NULL REFERENCES tenders(id)         ON DELETE CASCADE,
            is_read           BOOLEAN NOT NULL DEFAULT false,
            notification_type VARCHAR(50) NOT NULL,
            triggered_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (profile_id, tender_id, notification_type)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS crawl_logs (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id        UUID REFERENCES sources(id) ON DELETE SET NULL,
            level            VARCHAR(10)  NOT NULL DEFAULT 'info',
            message          TEXT NOT NULL,
            entries_processed INTEGER NOT NULL DEFAULT 0,
            entries_new       INTEGER NOT NULL DEFAULT 0,
            duration_ms       INTEGER,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS komunen_sources (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ags                  VARCHAR(20),
            name                 VARCHAR(300) NOT NULL,
            bundesland           VARCHAR(100),
            einwohner            INTEGER,
            main_url             TEXT,
            vergabe_url          TEXT,
            discovery_confidence FLOAT,
            status               komunen_status NOT NULL DEFAULT 'auto',
            last_verified_at     TIMESTAMPTZ,
            last_scraped_at      TIMESTAMPTZ,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_komunen_status     ON komunen_sources (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_komunen_bundesland ON komunen_sources (bundesland)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS tender_summaries (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tender_id    UUID NOT NULL UNIQUE REFERENCES tenders(id) ON DELETE CASCADE,
            summary_text TEXT NOT NULL,
            provider     VARCHAR(50)  NOT NULL,
            model        VARCHAR(100),
            cost_cents   INTEGER NOT NULL DEFAULT 0,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tender_summaries")
    op.execute("DROP TABLE IF EXISTS komunen_sources")
    op.execute("DROP TABLE IF EXISTS crawl_logs")
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS tags")
    op.execute("DROP TABLE IF EXISTS search_profiles")
    op.execute("DROP TABLE IF EXISTS lots")
    op.execute("DROP TABLE IF EXISTS tender_sources")
    op.execute("DROP TABLE IF EXISTS tenders")
    op.execute("DROP TABLE IF EXISTS sources")
    op.execute("DROP TYPE IF EXISTS komunen_status")
    op.execute("DROP TYPE IF EXISTS tag_status")
    op.execute("DROP TYPE IF EXISTS tender_status")
    op.execute("DROP TYPE IF EXISTS source_status")
