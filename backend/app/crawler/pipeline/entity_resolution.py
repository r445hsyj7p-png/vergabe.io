import uuid
from datetime import timedelta
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Tender, TenderSource, Source, Lot
from .normalizer import NormalizedTender


async def resolve(norm: NormalizedTender, db: AsyncSession) -> tuple[Tender, bool]:
    """Find existing tender or create new one. Returns (tender, is_new)."""
    source = (await db.execute(select(Source).where(Source.slug == norm.source_slug))).scalar_one_or_none()

    # Stage 1: hard match
    if norm.source_url:
        existing = (await db.execute(
            select(Tender).where(Tender.source_url == norm.source_url)
        )).scalar_one_or_none()
        if existing:
            await _update_source_link(existing, source, norm, db)
            return existing, False

    if norm.external_id:
        existing = (await db.execute(
            select(Tender).where(Tender.external_id == norm.external_id)
        )).scalar_one_or_none()
        if existing:
            await _update_source_link(existing, source, norm, db)
            return existing, False

    # Stage 2: fuzzy match on title + authority + deadline proximity
    if norm.contracting_authority and norm.deadline:
        window_start = norm.deadline - timedelta(days=3)
        window_end = norm.deadline + timedelta(days=3)
        candidates = (await db.execute(
            select(Tender).where(
                Tender.contracting_authority == norm.contracting_authority,
                Tender.deadline >= window_start,
                Tender.deadline <= window_end,
            )
        )).scalars().all()
        for c in candidates:
            if _title_similarity(c.title, norm.title) > 0.8:
                await _update_source_link(c, source, norm, db)
                return c, False

    # Create new tender
    tender = Tender(
        id=uuid.uuid4(),
        canonical_id=uuid.uuid4(),
        title=norm.title,
        description=norm.description,
        contracting_authority=norm.contracting_authority,
        authority_address=norm.authority_address,
        authority_email=norm.authority_email,
        authority_phone=norm.authority_phone,
        deadline=norm.deadline,
        publication_date=norm.publication_date,
        value_min=norm.value_min,
        value_max=norm.value_max,
        currency=norm.currency,
        cpv_codes=norm.cpv_codes or None,
        it_category=norm.it_category,
        region=norm.region,
        country=norm.country,
        procedure_type=norm.procedure_type,
        fulfillment_location=norm.fulfillment_location,
        external_id=norm.external_id,
        source_url=norm.source_url,
        content_hash=norm.hash,
        raw_data=norm.raw_data,
    )
    db.add(tender)
    await db.flush()

    if source:
        db.add(TenderSource(
            id=uuid.uuid4(),
            tender_id=tender.id,
            source_id=source.id,
            external_url=norm.source_url,
            external_id=norm.external_id,
            platform_name=norm.platform_name or source.name,
        ))

    for lot_data in (norm.lots or []):
        db.add(Lot(
            id=uuid.uuid4(),
            tender_id=tender.id,
            lot_number=str(lot_data.get("number", "")),
            title=lot_data.get("title"),
            description=lot_data.get("description"),
            value_min=lot_data.get("value_min"),
            value_max=lot_data.get("value_max"),
            cpv_codes=lot_data.get("cpv_codes"),
        ))

    return tender, True


async def _update_source_link(tender: Tender, source, norm: NormalizedTender, db: AsyncSession):
    if source is None:
        return
    existing_link = (await db.execute(
        select(TenderSource).where(
            TenderSource.tender_id == tender.id,
            TenderSource.source_id == source.id,
        )
    )).scalar_one_or_none()
    if not existing_link:
        db.add(TenderSource(
            id=uuid.uuid4(),
            tender_id=tender.id,
            source_id=source.id,
            external_url=norm.source_url,
            external_id=norm.external_id,
            platform_name=norm.platform_name or source.name,
        ))


def _title_similarity(a: str, b: str) -> float:
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)
