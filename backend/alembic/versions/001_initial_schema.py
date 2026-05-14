"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Enums
    op.execute("CREATE TYPE source_status AS ENUM ('ok', 'warn', 'error', 'inactive')")
    op.execute("CREATE TYPE tender_status AS ENUM ('open', 'closed', 'cancelled')")
    op.execute("CREATE TYPE tag_status AS ENUM ('interest', 'ignore')")
    op.execute("CREATE TYPE komunen_status AS ENUM ('auto', 'verified', 'excluded', 'pending_review')")

    op.create_table("sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("base_url", sa.Text),
        sa.Column("scraper_class", sa.String(100)),
        sa.Column("config", postgresql.JSONB),
        sa.Column("interval_hours", sa.Integer, server_default="6"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("status", sa.Text, server_default="'ok'"),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_entries", sa.Integer, server_default="0"),
    )

    op.create_table("tenders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("contracting_authority", sa.String(500)),
        sa.Column("authority_address", sa.Text),
        sa.Column("authority_email", sa.String(300)),
        sa.Column("authority_phone", sa.String(100)),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("publication_date", sa.DateTime(timezone=True)),
        sa.Column("value_min", sa.BigInteger),
        sa.Column("value_max", sa.BigInteger),
        sa.Column("currency", sa.String(10), server_default="'EUR'"),
        sa.Column("cpv_codes", postgresql.ARRAY(sa.String)),
        sa.Column("it_category", sa.String(100)),
        sa.Column("region", sa.String(200)),
        sa.Column("country", sa.String(10), server_default="'DE'"),
        sa.Column("procedure_type", sa.String(200)),
        sa.Column("tender_status", sa.Text, server_default="'open'"),
        sa.Column("fulfillment_location", sa.String(300)),
        sa.Column("external_id", sa.String(300)),
        sa.Column("source_url", sa.Text),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("raw_data", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenders_deadline", "tenders", ["deadline"])
    op.create_index("ix_tenders_it_category", "tenders", ["it_category"])
    op.create_index("ix_tenders_status", "tenders", ["tender_status"])
    op.create_index("ix_tenders_created_at", "tenders", ["created_at"])

    op.create_table("tender_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_url", sa.Text),
        sa.Column("external_id", sa.String(300)),
        sa.Column("platform_name", sa.String(200)),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tender_id", "source_id"),
    )

    op.create_table("lots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lot_number", sa.String(50)),
        sa.Column("title", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("value_min", sa.BigInteger),
        sa.Column("value_max", sa.BigInteger),
        sa.Column("cpv_codes", postgresql.ARRAY(sa.String)),
    )

    op.create_table("search_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.Text)),
        sa.Column("cpv_codes", postgresql.ARRAY(sa.String)),
        sa.Column("regions", postgresql.ARRAY(sa.String)),
        sa.Column("it_categories", postgresql.ARRAY(sa.String)),
        sa.Column("min_value", sa.BigInteger),
        sa.Column("deadline_days", sa.Integer),
        sa.Column("email", sa.String(300)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "tender_id", "notification_type"),
    )

    op.create_table("crawl_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("level", sa.String(10), server_default="'info'"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("entries_processed", sa.Integer, server_default="0"),
        sa.Column("entries_new", sa.Integer, server_default="0"),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("komunen_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ags", sa.String(20)),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("bundesland", sa.String(100)),
        sa.Column("einwohner", sa.Integer),
        sa.Column("main_url", sa.Text),
        sa.Column("vergabe_url", sa.Text),
        sa.Column("discovery_confidence", sa.Float),
        sa.Column("status", sa.Text, server_default="'auto'"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_komunen_status", "komunen_sources", ["status"])
    op.create_index("ix_komunen_bundesland", "komunen_sources", ["bundesland"])

    op.create_table("tender_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("summary_text", sa.Text, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100)),
        sa.Column("cost_cents", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tender_summaries")
    op.drop_table("komunen_sources")
    op.drop_table("crawl_logs")
    op.drop_table("notifications")
    op.drop_table("tags")
    op.drop_table("search_profiles")
    op.drop_table("lots")
    op.drop_table("tender_sources")
    op.drop_table("tenders")
    op.drop_table("sources")
    op.execute("DROP TYPE IF EXISTS komunen_status")
    op.execute("DROP TYPE IF EXISTS tag_status")
    op.execute("DROP TYPE IF EXISTS tender_status")
    op.execute("DROP TYPE IF EXISTS source_status")
