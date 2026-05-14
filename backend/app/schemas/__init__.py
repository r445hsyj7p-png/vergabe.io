from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import uuid


# ── Auth ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Sources ───────────────────────────────────────────────────────────────

class SourceOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    source_type: str
    base_url: Optional[str]
    interval_hours: int
    is_active: bool
    status: str
    last_run_at: Optional[datetime]
    last_run_entries: int
    model_config = {"from_attributes": True}


# ── Tenders ───────────────────────────────────────────────────────────────

class TenderSourceOut(BaseModel):
    source_id: uuid.UUID
    external_url: Optional[str]
    platform_name: Optional[str]
    scraped_at: datetime
    model_config = {"from_attributes": True}


class LotOut(BaseModel):
    id: uuid.UUID
    lot_number: Optional[str]
    title: Optional[str]
    description: Optional[str]
    value_min: Optional[int]
    value_max: Optional[int]
    cpv_codes: Optional[List[str]]
    model_config = {"from_attributes": True}


class TenderOut(BaseModel):
    id: uuid.UUID
    canonical_id: uuid.UUID
    title: str
    contracting_authority: Optional[str]
    deadline: Optional[datetime]
    publication_date: Optional[datetime]
    value_min: Optional[int]
    value_max: Optional[int]
    currency: str
    cpv_codes: Optional[List[str]]
    it_category: Optional[str]
    region: Optional[str]
    country: str
    procedure_type: Optional[str]
    tender_status: str
    source_url: Optional[str]
    tag_status: Optional[str] = None
    sources: List[TenderSourceOut] = []
    model_config = {"from_attributes": True}


class TenderDetailOut(TenderOut):
    description: Optional[str]
    fulfillment_location: Optional[str]
    authority_address: Optional[str]
    authority_email: Optional[str]
    authority_phone: Optional[str]
    lots: List[LotOut] = []
    created_at: datetime
    updated_at: datetime


class TenderPage(BaseModel):
    items: List[TenderOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class TagRequest(BaseModel):
    status: str


# ── Profiles ──────────────────────────────────────────────────────────────

class ProfileCreate(BaseModel):
    name: str
    keywords: Optional[List[str]] = None
    cpv_codes: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    it_categories: Optional[List[str]] = None
    min_value: Optional[int] = None
    deadline_days: Optional[int] = None
    email: Optional[str] = None
    is_active: bool = True


class ProfileOut(ProfileCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Notifications ─────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    tender_id: uuid.UUID
    is_read: bool
    notification_type: str
    triggered_at: datetime
    tender: Optional[TenderOut] = None
    profile_name: Optional[str] = None
    model_config = {"from_attributes": True}


# ── Admin ─────────────────────────────────────────────────────────────────

class CrawlLogOut(BaseModel):
    id: uuid.UUID
    source_id: Optional[uuid.UUID]
    level: str
    message: str
    entries_processed: int
    entries_new: int
    duration_ms: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}


class AdminStats(BaseModel):
    total_tenders: int
    tenders_today: int
    active_sources: int
    komunen_sources: int
    last_crawl_at: Optional[datetime]


class KomunenOut(BaseModel):
    id: uuid.UUID
    ags: Optional[str]
    name: str
    bundesland: Optional[str]
    einwohner: Optional[int]
    main_url: Optional[str]
    vergabe_url: Optional[str]
    discovery_confidence: Optional[float]
    status: str
    last_verified_at: Optional[datetime]
    last_scraped_at: Optional[datetime]
    model_config = {"from_attributes": True}


class KomunenCreate(BaseModel):
    name: str
    bundesland: Optional[str] = None
    einwohner: Optional[int] = None
    main_url: Optional[str] = None
    vergabe_url: Optional[str] = None
    ags: Optional[str] = None


class KomunenStats(BaseModel):
    total: int
    verified: int
    pending_review: int
    with_vergabe_url: int


# ── Summaries ─────────────────────────────────────────────────────────────

class SummaryOut(BaseModel):
    tender_id: uuid.UUID
    summary_text: str
    provider: str
    model: Optional[str]
    cost_cents: int
    created_at: datetime
    model_config = {"from_attributes": True}


class SummaryStatus(BaseModel):
    exists: bool
    summary: Optional[SummaryOut]
    provider_configured: str


class SummaryStats(BaseModel):
    total_summaries: int
    total_cost_eur: float
    by_provider: List[dict]
