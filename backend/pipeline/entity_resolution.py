"""
Entity Resolution — 3-stage SSOT deduplication
Stage 1: Hard match (URL / external_id / content_hash)
Stage 2: Rule match (authority + CPV + deadline window)
Stage 3: Review queue for low-confidence matches
"""
from datetime import timedelta
from typing import Optional, Tuple
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from rapidfuzz import fuzz

from models import Tender, TenderSource, CrawlLog
from pipeline.normalizer import NormalizedTender


CONFIDENCE_THRESHOLD = 0.85


def _norm_name(name: str) -> str:
    if not name:
        return ""
    import re
    name = name.lower()
    for stop in ["gmbh", "ag", "e.v.", "ev", "gbr", "mbh", "kg", "& co", " und ", " und", "& ", "- ","ug "]:
        name = name.replace(stop, " ")
    return re.sub(r"\s+", " ", name).strip()


def _score(t1: Tender, t2: NormalizedTender) -> float:
    """Compute match score between existing tender and normalized candidate."""
    score = 0.0

    # Authority name similarity (0–0.4)
    if t1.contracting_authority and t2.contracting_authority:
        ratio = fuzz.token_sort_ratio(
            _norm_name(t1.contracting_authority),
            _norm_name(t2.contracting_authority),
        ) / 100.0
        score += ratio * 0.4

    # CPV overlap (0–0.4)
    if t1.cpv_codes and t2.cpv_codes:
        s1, s2 = set(t1.cpv_codes), set(t2.cpv_codes)
        overlap = len(s1 & s2) / max(len(s1), len(s2))
        score += overlap * 0.4
    elif not t1.cpv_codes and not t2.cpv_codes:
        score += 0.2  # partial credit when both missing

    # Deadline proximity (0–0.2)
    if t1.deadline and t2.deadline:
        diff_days = abs((t1.deadline - t2.deadline).days)
        if diff_days <= 3:
            score += 0.2
        elif diff_days <= 7:
            score += 0.1

    return score


async def resolve(
    db: AsyncSession,
    normalized: NormalizedTender,
    source_id: uuid.UUID,
) -> Tuple[Tender, bool]:
    """
    Returns (tender, is_new).
    Side-effect: upserts TenderSource.
    """

    # Stage 1: Hard match
    candidates = []
    if normalized.source_url:
        r = await db.execute(select(Tender).where(Tender.source_url == normalized.source_url))
        c = r.scalar_one_or_none()
        if c:
            await _upsert_source(db, c, normalized, source_id)
            return c, False

    if normalized.external_id:
        r = await db.execute(select(Tender).where(Tender.external_id == normalized.external_id))
        c = r.scalar_one_or_none()
        if c:
            await _upsert_source(db, c, normalized, source_id)
            return c, False

    if normalized.content_hash:
        r = await db.execute(select(Tender).where(Tender.content_hash == normalized.content_hash))
        c = r.scalar_one_or_none()
        if c:
            await _upsert_source(db, c, normalized, source_id)
            return c, False

    # Stage 2: Rule match — find candidates with same authority
    if normalized.contracting_authority:
        r = await db.execute(
            select(Tender).where(
                and_(
                    Tender.contracting_authority.ilike(f"%{normalized.contracting_authority[:30]}%"),
                    Tender.deadline.isnot(None) if normalized.deadline else True,
                )
            ).limit(10)
        )
        candidates = r.scalars().all()

    best_score = 0.0
    best_match: Optional[Tender] = None
    for candidate in candidates:
        s = _score(candidate, normalized)
        if s > best_score:
            best_score = s
            best_match = candidate

    if best_match and best_score >= CONFIDENCE_THRESHOLD:
        await _upsert_source(db, best_match, normalized, source_id)
        return best_match, False

    # No match → create new
    tender = Tender(
        canonical_id=uuid.uuid4(),
        title=normalized.title,
        description=normalized.description,
        contracting_authority=normalized.contracting_authority,
        authority_address=normalized.authority_address,
        authority_email=normalized.authority_email,
        authority_phone=normalized.authority_phone,
        deadline=normalized.deadline,
        publication_date=normalized.publication_date,
        value_min=normalized.value_min,
        value_max=normalized.value_max,
        currency=normalized.currency,
        cpv_codes=normalized.cpv_codes or [],
        it_category=normalized.it_category,
        region=normalized.region,
        country=normalized.country,
        procedure_type=normalized.procedure_type,
        fulfillment_location=normalized.fulfillment_location,
        external_id=normalized.external_id,
        source_url=normalized.source_url,
        content_hash=normalized.content_hash,
        raw_data=normalized.raw_data,
        tender_status="open",
    )
    db.add(tender)
    await db.flush()
    await _upsert_source(db, tender, normalized, source_id)
    return tender, True


async def _upsert_source(
    db: AsyncSession,
    tender: Tender,
    normalized: NormalizedTender,
    source_id: uuid.UUID,
):
    """Ensure TenderSource record exists."""
    r = await db.execute(
        select(TenderSource).where(
            and_(TenderSource.tender_id == tender.id, TenderSource.source_id == source_id)
        )
    )
    if not r.scalar_one_or_none():
        ts = TenderSource(
            tender_id=tender.id,
            source_id=source_id,
            external_url=normalized.source_url,
            external_id=normalized.external_id,
            platform_name=normalized.platform_name,
        )
        db.add(ts)
