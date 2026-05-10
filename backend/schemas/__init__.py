from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class LotOut(BaseModel):
    id: UUID
    lot_number: Optional[str]
    title: Optional[str]
    description: Optional[str]
    value_min: Optional[int]
    value_max: Optional[int]
    cpv_codes: Optional[List[str]]
    model_config = {"from_attributes": True}


class TenderSourceOut(BaseModel):
    source_id: UUID
    external_url: Optional[str]
    platform_name: Optional[str]
    scraped_at: datetime
    model_config = {"from_attributes": True}


class TenderListItem(BaseModel):
    id: UUID
    canonical_id: UUID
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


class TenderDetail(TenderListItem):
    description: Optional[str]
    fulfillment_location: Optional[str]
    authority_address: Optional[str]
    authority_email: Optional[str]
    authority_phone: Optional[str]
    lots: List[LotOut] = []
    created_at: datetime
    updated_at: datetime


class TenderPage(BaseModel):
    items: List[TenderListItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class TagCreate(BaseModel):
    status: str = Field(..., pattern="^(interest|ignore)$")


class TagOut(BaseModel):
    id: UUID
    tender_id: UUID
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SearchProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    keywords: Optional[List[str]] = None
    cpv_codes: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    it_categories: Optional[List[str]] = None
    min_value: Optional[int] = None
    deadline_days: Optional[int] = None
    email: Optional[str] = None
    is_active: bool = True


class SearchProfileOut(SearchProfileCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: UUID
    profile_id: UUID
    tender_id: UUID
    is_read: bool
    notification_type: str
    triggered_at: datetime
    tender: Optional[TenderListItem] = None
    profile_name: Optional[str] = None
    model_config = {"from_attributes": True}


class SourceOut(BaseModel):
    id: UUID
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


class CrawlLogOut(BaseModel):
    id: UUID
    source_id: Optional[UUID]
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
    duplicates_removed: int
    last_crawl_at: Optional[datetime]


class KomunenSourceOut(BaseModel):
    id: UUID
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
