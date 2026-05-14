import csv
import io
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_, or_, cast, String
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import require_auth
from ..models import Tender, Tag, TenderSource, Source
from ..schemas import TenderOut, TenderDetailOut, TenderPage, TenderSourceOut, TagRequest

router = APIRouter(prefix="/tenders", tags=["tenders"])


def _build_filter(q, stmt):
    if q.q:
        term = f"%{q.q}%"
        stmt = stmt.where(
            or_(Tender.title.ilike(term), Tender.contracting_authority.ilike(term),
                Tender.description.ilike(term))
        )
    if q.cpv:
        stmt = stmt.where(cast(Tender.cpv_codes, String).ilike(f"%{q.cpv}%"))
    if q.region:
        stmt = stmt.where(Tender.region.ilike(f"%{q.region}%"))
    if q.auftraggeber:
        stmt = stmt.where(Tender.contracting_authority.ilike(f"%{q.auftraggeber}%"))
    if q.it_category:
        stmt = stmt.where(Tender.it_category == q.it_category)
    if q.status and q.status != "all":
        stmt = stmt.where(Tender.tender_status == q.status)
    if q.min_value:
        stmt = stmt.where(Tender.value_max >= q.min_value)
    return stmt


@router.get("", response_model=TenderPage)
async def list_tenders(
    q: Optional[str] = None,
    cpv: Optional[str] = None,
    region: Optional[str] = None,
    auftraggeber: Optional[str] = None,
    it_category: Optional[str] = None,
    status: Optional[str] = "open",
    min_value: Optional[int] = None,
    tag_status: Optional[str] = None,
    profile_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    class Params:
        pass
    p = Params()
    p.q, p.cpv, p.region, p.auftraggeber = q, cpv, region, auftraggeber
    p.it_category, p.status, p.min_value = it_category, status, min_value

    stmt = select(Tender).options(
        selectinload(Tender.sources).selectinload(TenderSource.source),
        selectinload(Tender.tags),
    )
    stmt = _build_filter(p, stmt)

    if tag_status:
        stmt = stmt.join(Tag, and_(Tag.tender_id == Tender.id, Tag.status == tag_status))
    elif profile_id:
        pass

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Tender.deadline.asc().nulls_last(), Tender.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    items = []
    for t in rows:
        out = TenderOut.model_validate(t)
        out.tag_status = t.tags[0].status if t.tags else None
        out.sources = [TenderSourceOut.model_validate(ts) for ts in t.sources]
        items.append(out)

    return TenderPage(items=items, total=total, page=page, page_size=page_size, has_more=total > page * page_size)


@router.get("/export")
async def export_tenders(
    q: Optional[str] = None,
    status: Optional[str] = "open",
    it_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    class Params:
        pass
    p = Params()
    p.q, p.cpv, p.region, p.auftraggeber = q, None, None, None
    p.it_category, p.status, p.min_value = it_category, status, None

    stmt = select(Tender)
    stmt = _build_filter(p, stmt)
    stmt = stmt.order_by(Tender.deadline.asc().nulls_last()).limit(1000)
    rows = (await db.execute(stmt)).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Titel", "Auftraggeber", "Deadline", "Wert (€)", "Region", "IT-Kategorie", "URL"])
    for t in rows:
        writer.writerow([
            str(t.id), t.title, t.contracting_authority or "",
            t.deadline.date().isoformat() if t.deadline else "",
            (t.value_max or 0) // 100,
            t.region or "", t.it_category or "", t.source_url or "",
        ])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ausschreibungen.csv"})


@router.get("/{tender_id}", response_model=TenderDetailOut)
async def get_tender(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    stmt = select(Tender).where(Tender.id == tender_id).options(
        selectinload(Tender.sources).selectinload(TenderSource.source),
        selectinload(Tender.tags),
        selectinload(Tender.lots),
    )
    t = (await db.execute(stmt)).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tender not found")

    out = TenderDetailOut.model_validate(t)
    out.tag_status = t.tags[0].status if t.tags else None
    out.sources = [TenderSourceOut.model_validate(ts) for ts in t.sources]
    return out


@router.post("/{tender_id}/tags", status_code=204)
async def set_tag(
    tender_id: uuid.UUID,
    body: TagRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    existing = (await db.execute(select(Tag).where(Tag.tender_id == tender_id))).scalar_one_or_none()
    if existing:
        existing.status = body.status
    else:
        db.add(Tag(tender_id=tender_id, status=body.status))
    await db.commit()


@router.delete("/{tender_id}/tags", status_code=204)
async def remove_tag(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    tag = (await db.execute(select(Tag).where(Tag.tender_id == tender_id))).scalar_one_or_none()
    if tag:
        db.delete(tag)
        await db.commit()


@router.get("/{tender_id}/summary")
async def get_summary_status(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    from ..models import TenderSummary
    from ..core.config import settings
    from ..schemas import SummaryStatus, SummaryOut

    s = (await db.execute(select(TenderSummary).where(TenderSummary.tender_id == tender_id))).scalar_one_or_none()
    return SummaryStatus(
        exists=s is not None,
        summary=SummaryOut.model_validate(s) if s else None,
        provider_configured=settings.summary_provider,
    )


@router.post("/{tender_id}/summary")
async def generate_summary(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    from ..services.summary import generate_and_store
    from ..schemas import SummaryOut

    result = await generate_and_store(tender_id, db)
    return SummaryOut.model_validate(result)


@router.delete("/{tender_id}/summary", status_code=204)
async def delete_summary(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    from ..models import TenderSummary

    s = (await db.execute(select(TenderSummary).where(TenderSummary.tender_id == tender_id))).scalar_one_or_none()
    if s:
        db.delete(s)
        await db.commit()
