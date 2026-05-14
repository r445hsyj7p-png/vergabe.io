import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import require_auth
from ..models import Tender, Source, CrawlLog, KomunenSource, TenderSummary
from ..schemas import (
    AdminStats, SourceOut, CrawlLogOut, KomunenOut, KomunenCreate, KomunenStats, SummaryStats
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
async def get_stats(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    total = (await db.execute(select(func.count(Tender.id)))).scalar_one()
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = (await db.execute(
        select(func.count(Tender.id)).where(Tender.created_at >= today)
    )).scalar_one()
    active_sources = (await db.execute(
        select(func.count(Source.id)).where(Source.is_active.is_(True))
    )).scalar_one()
    komunen = (await db.execute(select(func.count(KomunenSource.id)))).scalar_one()
    last_log = (await db.execute(
        select(CrawlLog.created_at).order_by(CrawlLog.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    return AdminStats(
        total_tenders=total,
        tenders_today=today_count,
        active_sources=active_sources,
        komunen_sources=komunen,
        last_crawl_at=last_log,
    )


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    rows = (await db.execute(select(Source).order_by(Source.name))).scalars().all()
    return rows


@router.post("/sources/{source_id}/crawl")
async def trigger_crawl(
    source_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    source = (await db.execute(select(Source).where(Source.id == source_id))).scalar_one_or_none()
    if not source:
        from fastapi import HTTPException
        raise HTTPException(404, "Source not found")

    async def run():
        from ..crawler.sources.ted import TedCrawler
        from ..crawler.sources.bund_rss import BundRssCrawler
        crawlers = {"ted": TedCrawler, "bund": BundRssCrawler}
        cls = crawlers.get(source.slug)
        if cls:
            await cls().run()

    background_tasks.add_task(run)
    return {"message": f"Crawl für {source.name} gestartet"}


@router.get("/crawl-logs", response_model=list[CrawlLogOut])
async def list_logs(
    limit: int = Query(100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    rows = (await db.execute(
        select(CrawlLog).order_by(CrawlLog.created_at.desc()).limit(limit)
    )).scalars().all()
    return rows


# ── Kommunen ─────────────────────────────────────────────────────────────

@router.get("/komunen/stats", response_model=KomunenStats)
async def komunen_stats(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    total = (await db.execute(select(func.count(KomunenSource.id)))).scalar_one()
    verified = (await db.execute(
        select(func.count(KomunenSource.id)).where(KomunenSource.status == "verified")
    )).scalar_one()
    pending = (await db.execute(
        select(func.count(KomunenSource.id)).where(KomunenSource.status == "pending_review")
    )).scalar_one()
    with_url = (await db.execute(
        select(func.count(KomunenSource.id)).where(KomunenSource.vergabe_url.isnot(None))
    )).scalar_one()
    return KomunenStats(total=total, verified=verified, pending_review=pending, with_vergabe_url=with_url)


@router.get("/komunen/queue", response_model=list[KomunenOut])
async def komunen_queue(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    rows = (await db.execute(
        select(KomunenSource).where(KomunenSource.status == "pending_review")
        .order_by(KomunenSource.discovery_confidence.desc().nulls_last())
        .limit(50)
    )).scalars().all()
    return rows


@router.patch("/komunen/{komunen_id}", response_model=KomunenOut)
async def update_komunen(
    komunen_id: str,
    status: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    k = (await db.execute(select(KomunenSource).where(KomunenSource.id == komunen_id))).scalar_one_or_none()
    if not k:
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    k.status = status
    await db.commit()
    await db.refresh(k)
    return k


@router.post("/komunen", response_model=KomunenOut, status_code=201)
async def add_komunen(body: KomunenCreate, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    k = KomunenSource(**body.model_dump(), status="pending_review")
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@router.post("/komunen/sync-destatis")
async def sync_destatis(background_tasks: BackgroundTasks, _: str = Depends(require_auth)):
    async def run():
        from ..crawler.komunen.destatis import sync_from_destatis
        from ..core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await sync_from_destatis(db)

    background_tasks.add_task(run)
    return {"message": "Destatis-Sync gestartet"}


@router.post("/komunen/sync-wikidata")
async def sync_wikidata(background_tasks: BackgroundTasks, _: str = Depends(require_auth)):
    async def run():
        from ..crawler.komunen.wikidata import resolve_wikidata_urls
        from ..core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await resolve_wikidata_urls(db)

    background_tasks.add_task(run)
    return {"message": "Wikidata-Sync gestartet"}


@router.post("/komunen/run-discovery")
async def run_discovery(background_tasks: BackgroundTasks, _: str = Depends(require_auth)):
    async def run():
        from ..crawler.komunen.discovery import run_discovery_pipeline
        from ..core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await run_discovery_pipeline(db)

    background_tasks.add_task(run)
    return {"message": "Discovery gestartet"}


# ── AI Summaries ──────────────────────────────────────────────────────────

@router.get("/summaries/stats", response_model=SummaryStats)
async def summary_stats(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    total = (await db.execute(select(func.count(TenderSummary.id)))).scalar_one()
    total_cost = (await db.execute(select(func.sum(TenderSummary.cost_cents)))).scalar_one() or 0
    by_provider_rows = (await db.execute(
        select(TenderSummary.provider, func.count().label("cnt"), func.sum(TenderSummary.cost_cents).label("cost"))
        .group_by(TenderSummary.provider)
    )).all()
    return SummaryStats(
        total_summaries=total,
        total_cost_eur=total_cost / 100,
        by_provider=[{"provider": r.provider, "count": r.cnt, "cost_eur": (r.cost or 0) / 100}
                     for r in by_provider_rows],
    )
