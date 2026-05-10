from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid

from database import get_db
from models import Source, CrawlLog, Tender, KomunenSource
from schemas import SourceOut, CrawlLogOut, AdminStats, KomunenSourceOut
from auth import require_auth

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
async def get_stats(db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    total = (await db.execute(select(func.count()).select_from(Tender))).scalar_one()
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = (await db.execute(
        select(func.count()).select_from(Tender).where(Tender.created_at >= today)
    )).scalar_one()
    active_sources = (await db.execute(
        select(func.count()).select_from(Source).where(Source.is_active == True)
    )).scalar_one()
    komunen = (await db.execute(select(func.count()).select_from(KomunenSource))).scalar_one()
    last_log = (await db.execute(
        select(CrawlLog.created_at).order_by(CrawlLog.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    return AdminStats(
        total_tenders=total,
        tenders_today=today_count,
        active_sources=active_sources,
        komunen_sources=komunen,
        duplicates_removed=0,
        last_crawl_at=last_log,
    )


@router.get("/sources", response_model=List[SourceOut])
async def list_sources(db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    result = await db.execute(select(Source).order_by(Source.name))
    return result.scalars().all()


@router.post("/sources/{source_id}/crawl")
async def trigger_crawl(source_id: uuid.UUID, db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")
    # Signal to scheduler via Redis (simplified: just log it)
    log = CrawlLog(source_id=source_id, level="info", message=f"Manual crawl triggered for {source.name}")
    db.add(log)
    await db.commit()
    return {"status": "triggered", "source": source.name}


@router.get("/crawl-logs", response_model=List[CrawlLogOut])
async def list_logs(limit: int = 100, db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    result = await db.execute(
        select(CrawlLog).order_by(CrawlLog.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/komunen/stats")
async def komunen_stats(db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    total = (await db.execute(select(func.count()).select_from(KomunenSource))).scalar_one()
    verified = (await db.execute(
        select(func.count()).select_from(KomunenSource).where(KomunenSource.status == "verified")
    )).scalar_one()
    pending = (await db.execute(
        select(func.count()).select_from(KomunenSource).where(KomunenSource.status == "pending_review")
    )).scalar_one()
    with_vergabe_url = (await db.execute(
        select(func.count()).select_from(KomunenSource).where(KomunenSource.vergabe_url.isnot(None))
    )).scalar_one()
    return {"total": total, "verified": verified, "pending_review": pending, "with_vergabe_url": with_vergabe_url}


@router.get("/komunen/queue", response_model=List[KomunenSourceOut])
async def komunen_queue(db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    result = await db.execute(
        select(KomunenSource)
        .where(KomunenSource.status == "pending_review")
        .order_by(KomunenSource.discovery_confidence.asc())
        .limit(50)
    )
    return result.scalars().all()


@router.patch("/komunen/{komunen_id}")
async def update_komunen(
    komunen_id: uuid.UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
    token=Depends(require_auth),
):
    result = await db.execute(select(KomunenSource).where(KomunenSource.id == komunen_id))
    k = result.scalar_one_or_none()
    if not k:
        raise HTTPException(404, "Not found")
    if status not in ("verified", "excluded", "auto", "pending_review"):
        raise HTTPException(400, "Invalid status")
    k.status = status
    await db.commit()
    return {"ok": True}


@router.post("/auth/token")
async def get_token(password: str):
    from config import settings
    if password == settings.admin_password:
        return {"token": settings.secret_key, "token_type": "bearer"}
    raise HTTPException(401, "Wrong password")


class KomunenCreate(BaseModel):
    name: str
    bundesland: Optional[str] = None
    einwohner: Optional[int] = None
    main_url: Optional[str] = None
    vergabe_url: Optional[str] = None
    ags: Optional[str] = None


@router.post("/komunen", response_model=KomunenSourceOut)
async def add_komunen(body: KomunenCreate, db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    """Manually add a new Gemeinde to the crawler queue."""
    import uuid as _uuid
    k = KomunenSource(
        id=_uuid.uuid4(),
        ags=body.ags,
        name=body.name,
        bundesland=body.bundesland,
        einwohner=body.einwohner,
        main_url=body.main_url,
        vergabe_url=body.vergabe_url,
        discovery_confidence=1.0 if body.vergabe_url else None,
        status="verified" if body.vergabe_url else "auto",
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@router.post("/komunen/sync-destatis")
async def trigger_destatis_sync(token=Depends(require_auth)):
    """Trigger manual Destatis sync (runs in background)."""
    import asyncio
    async def _run():
        import sys, os
        sys.path.insert(0, "/app")
        from crawler.komunen.destatis_sync import sync_from_destatis
        await sync_from_destatis()
    asyncio.create_task(_run())
    return {"status": "started", "message": "Destatis sync läuft im Hintergrund"}


@router.post("/komunen/sync-wikidata")
async def trigger_wikidata_sync(token=Depends(require_auth)):
    """Trigger manual Wikidata URL resolution."""
    import asyncio
    async def _run():
        from crawler.komunen.wikidata import resolve_wikidata_urls
        await resolve_wikidata_urls()
    asyncio.create_task(_run())
    return {"status": "started", "message": "Wikidata URL-Auflösung läuft im Hintergrund"}


@router.post("/komunen/run-discovery")
async def trigger_discovery(token=Depends(require_auth)):
    """Trigger manual URL verify + discovery for all pending Gemeinden."""
    import asyncio
    async def _run():
        from crawler.komunen.discovery import run_url_verify_job, run_discovery_job
        await run_url_verify_job()
        await run_discovery_job()
    asyncio.create_task(_run())
    return {"status": "started", "message": "URL-Verify + Discovery läuft im Hintergrund"}


@router.get("/summaries/stats")
async def summary_stats(db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    """Kosten- und Nutzungsstatistik für KI-Zusammenfassungen."""
    from models import TenderSummary
    from sqlalchemy import func as sqlfunc
    total = (await db.execute(select(sqlfunc.count()).select_from(TenderSummary))).scalar_one()
    total_cost = (await db.execute(select(sqlfunc.sum(TenderSummary.cost_cents)))).scalar_one() or 0
    by_provider = (await db.execute(
        select(TenderSummary.provider, sqlfunc.count(), sqlfunc.sum(TenderSummary.cost_cents))
        .group_by(TenderSummary.provider)
    )).all()
    return {
        "total_summaries": total,
        "total_cost_cents": total_cost,
        "total_cost_eur": round(total_cost / 100, 4),
        "by_provider": [
            {"provider": r[0], "count": r[1], "cost_cents": r[2] or 0}
            for r in by_provider
        ],
    }
