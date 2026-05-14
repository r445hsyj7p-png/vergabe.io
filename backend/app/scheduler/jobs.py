from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..core.database import AsyncSessionLocal


async def _job_ted():
    from ..crawler.sources.ted import TedCrawler
    from ..services.alert_engine import run_alert_engine
    async with AsyncSessionLocal() as db:
        await TedCrawler()._crawl(db)
    async with AsyncSessionLocal() as db:
        await run_alert_engine(db)


async def _job_bund():
    from ..crawler.sources.bund_rss import BundRssCrawler
    from ..services.alert_engine import run_alert_engine
    await BundRssCrawler().run()
    async with AsyncSessionLocal() as db:
        await run_alert_engine(db)


async def _job_deadline_warnings():
    from ..services.alert_engine import run_deadline_warnings
    async with AsyncSessionLocal() as db:
        await run_deadline_warnings(db)


async def _job_komunen_daily():
    from ..crawler.komunen.discovery import run_discovery_pipeline
    async with AsyncSessionLocal() as db:
        await run_discovery_pipeline(db)


async def _job_wikidata():
    from ..crawler.komunen.wikidata import resolve_wikidata_urls
    async with AsyncSessionLocal() as db:
        await resolve_wikidata_urls(db)


async def _job_destatis():
    from ..crawler.komunen.destatis import sync_from_destatis
    async with AsyncSessionLocal() as db:
        await sync_from_destatis(db)


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

    scheduler.add_job(_job_ted, CronTrigger(hour="*/4", minute=5), id="ted", replace_existing=True)
    scheduler.add_job(_job_bund, CronTrigger(hour="*/2", minute=15), id="bund", replace_existing=True)
    scheduler.add_job(_job_deadline_warnings, CronTrigger(hour=6, minute=0), id="deadline_warnings", replace_existing=True)
    scheduler.add_job(_job_komunen_daily, CronTrigger(hour=3, minute=0), id="komunen_daily", replace_existing=True)
    scheduler.add_job(_job_wikidata, CronTrigger(day_of_week="mon", hour=4), id="wikidata", replace_existing=True)
    scheduler.add_job(_job_destatis, CronTrigger(month="1,4,7,10", day=1, hour=5), id="destatis", replace_existing=True)

    scheduler.start()
    return scheduler
