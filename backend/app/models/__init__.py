import uuid
import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Text, Integer, BigInteger, Boolean, DateTime,
    ForeignKey, Float, UniqueConstraint, Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..core.database import Base


class TenderStatus(str, enum.Enum):
    open = "open"
    closed = "closed"
    cancelled = "cancelled"


class TagStatus(str, enum.Enum):
    interest = "interest"
    ignore = "ignore"


class SourceStatus(str, enum.Enum):
    ok = "ok"
    warn = "warn"
    error = "error"
    inactive = "inactive"


class KomunenStatus(str, enum.Enum):
    auto = "auto"
    verified = "verified"
    excluded = "excluded"
    pending_review = "pending_review"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    source_type: Mapped[str] = mapped_column(String(50))
    base_url: Mapped[Optional[str]] = mapped_column(Text)
    scraper_class: Mapped[Optional[str]] = mapped_column(String(100))
    config: Mapped[Optional[dict]] = mapped_column(JSONB)
    interval_hours: Mapped[int] = mapped_column(Integer, default=6)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(
        SAEnum(SourceStatus, name="source_status"), default=SourceStatus.ok
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_run_entries: Mapped[int] = mapped_column(Integer, default=0)

    tender_sources: Mapped[List["TenderSource"]] = relationship(back_populates="source")
    crawl_logs: Mapped[List["CrawlLog"]] = relationship(back_populates="source")


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    contracting_authority: Mapped[Optional[str]] = mapped_column(String(500))
    authority_address: Mapped[Optional[str]] = mapped_column(Text)
    authority_email: Mapped[Optional[str]] = mapped_column(String(300))
    authority_phone: Mapped[Optional[str]] = mapped_column(String(100))
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    value_min: Mapped[Optional[int]] = mapped_column(BigInteger)
    value_max: Mapped[Optional[int]] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    cpv_codes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    it_category: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(200))
    country: Mapped[str] = mapped_column(String(10), default="DE")
    procedure_type: Mapped[Optional[str]] = mapped_column(String(200))
    tender_status: Mapped[str] = mapped_column(
        SAEnum(TenderStatus, name="tender_status"), default=TenderStatus.open
    )
    fulfillment_location: Mapped[Optional[str]] = mapped_column(String(300))
    external_id: Mapped[Optional[str]] = mapped_column(String(300))
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sources: Mapped[List["TenderSource"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    lots: Mapped[List["Lot"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    tags: Mapped[List["Tag"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="tender", cascade="all, delete-orphan")
    summary: Mapped[Optional["TenderSummary"]] = relationship(back_populates="tender", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tenders_deadline", "deadline"),
        Index("ix_tenders_it_category", "it_category"),
        Index("ix_tenders_status", "tender_status"),
        Index("ix_tenders_created_at", "created_at"),
    )


class TenderSource(Base):
    __tablename__ = "tender_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"))
    external_url: Mapped[Optional[str]] = mapped_column(Text)
    external_id: Mapped[Optional[str]] = mapped_column(String(300))
    platform_name: Mapped[Optional[str]] = mapped_column(String(200))
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tender: Mapped["Tender"] = relationship(back_populates="sources")
    source: Mapped["Source"] = relationship(back_populates="tender_sources")

    __table_args__ = (UniqueConstraint("tender_id", "source_id"),)


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"))
    lot_number: Mapped[Optional[str]] = mapped_column(String(50))
    title: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    value_min: Mapped[Optional[int]] = mapped_column(BigInteger)
    value_max: Mapped[Optional[int]] = mapped_column(BigInteger)
    cpv_codes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))

    tender: Mapped["Tender"] = relationship(back_populates="lots")


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    cpv_codes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    regions: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    it_categories: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    min_value: Mapped[Optional[int]] = mapped_column(BigInteger)
    deadline_days: Mapped[Optional[int]] = mapped_column(Integer)
    email: Mapped[Optional[str]] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    notifications: Mapped[List["Notification"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(SAEnum(TagStatus, name="tag_status"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tender: Mapped["Tender"] = relationship(back_populates="tags")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("search_profiles.id", ondelete="CASCADE"))
    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_type: Mapped[str] = mapped_column(String(50))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["SearchProfile"] = relationship(back_populates="notifications")
    tender: Mapped["Tender"] = relationship(back_populates="notifications")

    __table_args__ = (UniqueConstraint("profile_id", "tender_id", "notification_type"),)


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    level: Mapped[str] = mapped_column(String(10), default="info")
    message: Mapped[str] = mapped_column(Text)
    entries_processed: Mapped[int] = mapped_column(Integer, default=0)
    entries_new: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Optional["Source"]] = relationship(back_populates="crawl_logs")


class KomunenSource(Base):
    __tablename__ = "komunen_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ags: Mapped[Optional[str]] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(300))
    bundesland: Mapped[Optional[str]] = mapped_column(String(100))
    einwohner: Mapped[Optional[int]] = mapped_column(Integer)
    main_url: Mapped[Optional[str]] = mapped_column(Text)
    vergabe_url: Mapped[Optional[str]] = mapped_column(Text)
    discovery_confidence: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        SAEnum(KomunenStatus, name="komunen_status"), default=KomunenStatus.auto
    )
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_komunen_status", "status"),
        Index("ix_komunen_bundesland", "bundesland"),
    )


class TenderSummary(Base):
    __tablename__ = "tender_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), unique=True)
    summary_text: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tender: Mapped["Tender"] = relationship(back_populates="summary")
