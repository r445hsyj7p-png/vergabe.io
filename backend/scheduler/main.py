"""Scheduler — runs all crawl jobs on cron schedules."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from database import AsyncSessionLocal
from models import Source


async def get_source_id(slug: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Source).where(Source.slug == slug))
        source = result.scalar_one_or_none()
        return source.id if source else None


async def job_ted():
    print(f"[{datetime.now()}] Running TED fetcher...")
    from crawler.sources.ted import run_ted_fetcher
    source_id = await get_source_id("ted")
    if source_id:
        n = await run_ted_fetcher(source_id)
        print(f"[TED] {n} new entries")
        await job_alert_engine()


async def job_bund():
    print(f"[{datetime.now()}] Running bund.de RSS fetcher...")
    from crawler.sources.bund_rss import run_bund_rss_fetcher
    source_id = await get_source_id("bund")
    if source_id:
        n = await run_bund_rss_fetcher(source_id)
        print(f"[bund.de] {n} new entries")
        await job_alert_engine()


async def job_alert_engine():
    from pipeline.alert_engine import run_alert_engine
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    async with AsyncSessionLocal() as db:
        n = await run_alert_engine(db, since)
        if n:
            print(f"[AlertEngine] {n} new notifications")


async def job_deadline_warnings():
    from pipeline.alert_engine import run_deadline_warnings
    async with AsyncSessionLocal() as db:
        await run_deadline_warnings(db)
    print(f"[DeadlineWarnings] Done")


async def check_and_run_initial_crawl():
    """If setup requested an initial crawl, run it now."""
    from database import AsyncSessionLocal
    from models import CrawlLog
    from sqlalchemy import select, and_
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CrawlLog).where(
                and_(CrawlLog.message == "setup:initial_crawl_requested", CrawlLog.level == "info")
            )
        )
        marker = result.scalar_one_or_none()
        if not marker:
            return
        # Check if we already ran initial crawl (more than 1 log entry)
        count_result = await db.execute(select(func.count()).select_from(CrawlLog))
        count = count_result.scalar_one()
        if count > 1:
            return  # already ran

    print("[Scheduler] First start detected — running initial crawl…")
    await job_ted()
    await job_bund()
    print("[Scheduler] Initial crawl complete.")


from sqlalchemy import func


def main():
    scheduler = AsyncIOScheduler(timezone="UTC")

    # TED every 4 hours
    scheduler.add_job(job_ted, CronTrigger(hour="*/4", minute=5))

    # bund.de every 2 hours
    scheduler.add_job(job_bund, CronTrigger(hour="*/2", minute=15))

    # Deadline warnings daily at 06:00
    scheduler.add_job(job_deadline_warnings, CronTrigger(hour=6, minute=0))

    # Kommunen: täglich URL-Verify + Discovery um 03:00
    scheduler.add_job(job_komunen_verify, CronTrigger(hour=3, minute=0))

    # Kommunen: wöchentlich Wikidata URL-Auflösung (Montag 04:00)
    scheduler.add_job(job_wikidata_urls, CronTrigger(day_of_week="mon", hour=4, minute=0))

    # Kommunen: quartalsweise Destatis-Sync (1. Jan/Apr/Jul/Okt, 05:00)
    scheduler.add_job(job_destatis_sync, CronTrigger(month="1,4,7,10", day=1, hour=5, minute=0))

    scheduler.start()
    print(f"Scheduler started. Jobs: {len(scheduler.get_jobs())}")

    loop = asyncio.get_event_loop()

    # Run initial crawl if this is first start
    loop.run_until_complete(check_and_run_initial_crawl())

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    main()


# ── Kommunen-Pipeline ────────────────────────────────────────────────────

async def job_destatis_sync():
    """Quarterly: sync German municipality list from Destatis."""
    print(f"[{datetime.now()}] Running Destatis sync…")
    from crawler.komunen.destatis_sync import sync_from_destatis
    await sync_from_destatis()


async def job_wikidata_urls():
    """Weekly: resolve main URLs for Gemeinden via Wikidata SPARQL."""
    print(f"[{datetime.now()}] Running Wikidata URL resolution…")
    from crawler.komunen.wikidata import resolve_wikidata_urls
    await resolve_wikidata_urls()


async def job_komunen_verify():
    """Daily: HTTP-verify komunen URLs and discover vergabe pages."""
    print(f"[{datetime.now()}] Running Kommunen URL verify + discovery…")
    from crawler.komunen.discovery import (
        run_url_verify_job, run_discovery_job, run_maintenance_job
    )
    await run_url_verify_job()
    await run_discovery_job()
    await run_maintenance_job()
