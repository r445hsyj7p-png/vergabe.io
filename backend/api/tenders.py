from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import csv, io, uuid

from database import get_db
from models import Tender, TenderSource, Tag, Source
from schemas import TenderPage, TenderListItem, TenderDetail, TagCreate, TagOut
from auth import require_auth

router = APIRouter(prefix="/tenders", tags=["tenders"])


def build_query(
    q: Optional[str],
    cpv: Optional[str],
    region: Optional[str],
    auftraggeber: Optional[str],
    it_category: Optional[str],
    status: Optional[str],
    deadline_before: Optional[datetime],
    deadline_after: Optional[datetime],
    min_value: Optional[int],
    profile_id: Optional[str],
    tag_status: Optional[str],
):
    stmt = select(Tender).options(
        selectinload(Tender.sources).selectinload(TenderSource.source),
        selectinload(Tender.tags),
    )

    filters = []

    if q:
        words = q.strip().split()
        for word in words[:10]:  # max 10 keywords
            filters.append(
                or_(
                    Tender.title.ilike(f"%{word}%"),
                    Tender.description.ilike(f"%{word}%"),
                    Tender.contracting_authority.ilike(f"%{word}%"),
                )
            )

    if cpv:
        filters.append(Tender.cpv_codes.any(cpv))

    if region:
        filters.append(Tender.region.ilike(f"%{region}%"))

    if auftraggeber:
        filters.append(Tender.contracting_authority.ilike(f"%{auftraggeber}%"))

    if it_category:
        filters.append(Tender.it_category == it_category)

    if status == "open":
        filters.append(Tender.tender_status == "open")
        filters.append(or_(Tender.deadline.is_(None), Tender.deadline >= datetime.now(timezone.utc)))
    elif status == "closed":
        filters.append(Tender.tender_status == "closed")

    if deadline_before:
        filters.append(Tender.deadline <= deadline_before)

    if deadline_after:
        filters.append(Tender.deadline >= deadline_after)

    if min_value:
        filters.append(Tender.value_max >= min_value)

    if filters:
        stmt = stmt.where(and_(*filters))

    return stmt


@router.get("", response_model=TenderPage)
async def list_tenders(
    q: Optional[str] = None,
    cpv: Optional[str] = None,
    region: Optional[str] = None,
    auftraggeber: Optional[str] = None,
    it_category: Optional[str] = None,
    status: Optional[str] = "open",
    deadline_before: Optional[datetime] = None,
    deadline_after: Optional[datetime] = None,
    min_value: Optional[int] = None,
    profile_id: Optional[str] = None,
    tag_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_auth),
):
    stmt = build_query(q, cpv, region, auftraggeber, it_category, status,
                       deadline_before, deadline_after, min_value, profile_id, tag_status)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Page
    stmt = stmt.order_by(Tender.deadline.asc().nulls_last(), Tender.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    tenders = result.scalars().unique().all()

    items = []
    for t in tenders:
        item = TenderListItem.model_validate(t)
        if t.tags:
            item.tag_status = t.tags[0].status
        item.sources = [TenderListItem.model_fields['sources'].annotation.__args__[0].model_validate(s) for s in t.sources]
        items.append(item)

    return TenderPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/export")
async def export_tenders(
    q: Optional[str] = None,
    status: Optional[str] = "open",
    it_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_auth),
):
    stmt = build_query(q, None, None, None, it_category, status, None, None, None, None, None)
    stmt = stmt.order_by(Tender.deadline.asc().nulls_last()).limit(1000)
    result = await db.execute(stmt)
    tenders = result.scalars().unique().all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Titel", "Auftraggeber", "Deadline", "CPV-Codes", "Kategorie", "Region", "Wert (€)", "Plattform-URL"])
        for t in tenders:
            writer.writerow([
                t.title,
                t.contracting_authority or "",
                t.deadline.strftime("%d.%m.%Y") if t.deadline else "",
                ", ".join(t.cpv_codes or []),
                t.it_category or "",
                t.region or "",
                f"{t.value_max / 100:.0f}" if t.value_max else "",
                t.source_url or "",
            ])
        yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ausschreibungen.csv"},
    )


@router.get("/{tender_id}", response_model=TenderDetail)
async def get_tender(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_auth),
):
    stmt = select(Tender).options(
        selectinload(Tender.sources).selectinload(TenderSource.source),
        selectinload(Tender.tags),
        selectinload(Tender.lots),
    ).where(Tender.id == tender_id)

    result = await db.execute(stmt)
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    detail = TenderDetail.model_validate(tender)
    if tender.tags:
        detail.tag_status = tender.tags[0].status
    return detail


@router.post("/{tender_id}/tags", response_model=TagOut)
async def set_tag(
    tender_id: uuid.UUID,
    body: TagCreate,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_auth),
):
    result = await db.execute(select(Tag).where(Tag.tender_id == tender_id))
    existing = result.scalar_one_or_none()

    if existing:
        existing.status = body.status
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        tag = Tag(tender_id=tender_id, status=body.status)
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return tag


@router.delete("/{tender_id}/tags", status_code=204)
async def remove_tag(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_auth),
):
    result = await db.execute(select(Tag).where(Tag.tender_id == tender_id))
    tag = result.scalar_one_or_none()
    if tag:
        await db.delete(tag)
        await db.commit()
