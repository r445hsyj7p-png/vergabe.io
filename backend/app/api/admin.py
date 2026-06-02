import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import require_auth
from ..models import Tender, Source, CrawlLog, KomunenSource, TenderSummary
from ..schemas import (
    AdminStats, SourceOut, CrawlLogOut, KomunenOut, KomunenCreate, KomunenStats, SummaryStats,
    KomunenListResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Live-Crawler-State (in-memory, pro Prozess) ───────────────────────────

@dataclass
class _RunState:
    running: bool = True
    processed: int = 0
    new_count: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

_run_state: dict[str, _RunState] = {}

_CRAWLERS = {
    "ted": "..crawler.sources.ted.TedCrawler",
    "bund": "..crawler.sources.bund_rss.BundRssCrawler",
    "doe": "..crawler.sources.doe.DoeCrawler",
    "nrw": "..crawler.sources.nrw.NrwCrawler",
    "berlin": "..crawler.sources.berlin.BerlinCrawler",
    "sachsen": "..crawler.sources.sachsen.SachsenCrawler",
    "had": "..crawler.sources.had.HadCrawler",
}


async def _run_crawler(slug: str) -> None:
    """Führt einen Crawler aus und pflegt dabei _run_state + Live-Progress."""
    from ..crawler.pipeline.entity_resolution import _progress_cb

    state = _RunState()
    _run_state[slug] = state

    def _cb(processed_delta: int, new_delta: int) -> None:
        state.processed += processed_delta
        state.new_count += new_delta

    token = _progress_cb.set(_cb)
    try:
        from ..crawler.sources.ted import TedCrawler
        from ..crawler.sources.bund_rss import BundRssCrawler
        from ..crawler.sources.doe import DoeCrawler
        from ..crawler.sources.nrw import NrwCrawler
        from ..crawler.sources.berlin import BerlinCrawler
        from ..crawler.sources.sachsen import SachsenCrawler
        from ..crawler.sources.had import HadCrawler
        crawlers = {
            "ted": TedCrawler, "bund": BundRssCrawler, "doe": DoeCrawler,
            "nrw": NrwCrawler, "berlin": BerlinCrawler,
            "sachsen": SachsenCrawler, "had": HadCrawler,
        }
        cls = crawlers.get(slug)
        if cls:
            await cls().run()
    except Exception as e:
        state.error = str(e)
    finally:
        _progress_cb.reset(token)
        state.running = False
        state.finished_at = datetime.now(timezone.utc)


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


@router.get("/crawlers/live")
async def crawlers_live(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    """Live-Status aller Crawler: running-Flag + Progress aus ContextVar + letzter CrawlLog."""
    sources = (await db.execute(select(Source).order_by(Source.name))).scalars().all()

    # Letzten CrawlLog pro Source in einem Query
    from sqlalchemy import distinct
    subq = (
        select(CrawlLog.source_id, func.max(CrawlLog.created_at).label("max_at"))
        .group_by(CrawlLog.source_id)
        .subquery()
    )
    log_rows = (await db.execute(
        select(CrawlLog).join(subq, (CrawlLog.source_id == subq.c.source_id) & (CrawlLog.created_at == subq.c.max_at))
    )).scalars().all()
    latest_log: dict[uuid.UUID, CrawlLog] = {lg.source_id: lg for lg in log_rows}

    result = []
    for s in sources:
        state = _run_state.get(s.slug)
        lg = latest_log.get(s.id)
        result.append({
            "id": str(s.id),
            "slug": s.slug,
            "name": s.name,
            "source_type": s.source_type,
            "interval_hours": s.interval_hours,
            "status": s.status,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            # Live-Run-Daten
            "running": bool(state and state.running),
            "started_at": state.started_at.isoformat() if (state and state.running) else None,
            "run_processed": state.processed if state else None,
            "run_new": state.new_count if state else None,
            "run_error": state.error if state else None,
            # Letzter abgeschlossener Log
            "last_log_processed": lg.entries_processed if lg else None,
            "last_log_new": lg.entries_new if lg else None,
            "last_log_level": lg.level if lg else None,
            "last_log_message": lg.message if lg else None,
            "last_log_details": lg.details if lg else None,
            "last_log_at": lg.created_at.isoformat() if lg else None,
        })
    return result


@router.post("/sources/{source_id}/crawl")
async def trigger_crawl(
    source_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    source = (await db.execute(select(Source).where(Source.id == source_id))).scalar_one_or_none()
    if not source:
        from fastapi import HTTPException
        raise HTTPException(404, "Source not found")
    if _run_state.get(source.slug) and _run_state[source.slug].running:
        return {"message": f"{source.name} läuft bereits"}
    background_tasks.add_task(_run_crawler, source.slug)
    return {"message": f"Crawl für {source.name} gestartet"}


@router.post("/crawlers/run-all")
async def run_all_crawlers(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    sources = (await db.execute(select(Source).where(Source.is_active.is_(True)))).scalars().all()
    started = []
    for s in sources:
        if not (_run_state.get(s.slug) and _run_state[s.slug].running):
            background_tasks.add_task(_run_crawler, s.slug)
            started.append(s.slug)
    return {"message": f"{len(started)} Crawler gestartet", "started": started}


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

@router.get("/komunen", response_model=KomunenListResponse)
async def list_komunen(
    status: Optional[str] = Query(None),
    bundesland: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    stmt = select(KomunenSource)
    count_stmt = select(func.count(KomunenSource.id))
    filters = []
    if status:
        filters.append(KomunenSource.status == status)
    if bundesland:
        filters.append(KomunenSource.bundesland == bundesland)
    if q:
        like = f"%{q}%"
        filters.append(or_(
            KomunenSource.name.ilike(like),
            KomunenSource.vergabe_url.ilike(like),
            KomunenSource.main_url.ilike(like),
        ))
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(
        stmt.order_by(KomunenSource.name).offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    return KomunenListResponse(items=list(rows), total=total, page=page, per_page=per_page)


@router.get("/komunen/distinct-bundeslaender")
async def distinct_bundeslaender(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    rows = (await db.execute(
        select(KomunenSource.bundesland).where(KomunenSource.bundesland.isnot(None)).distinct().order_by(KomunenSource.bundesland)
    )).scalars().all()
    return rows


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
    komunen_id: uuid.UUID,
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
