import re
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Tender, SearchProfile, Notification, Tag
from ..core.config import settings


def _matches(tender: Tender, profile: SearchProfile) -> bool:
    combined = f"{tender.title} {tender.description or ''} {tender.contracting_authority or ''}"

    if profile.keywords:
        if not any(
            re.search(r"\b" + re.escape(kw) + r"\b", combined, re.IGNORECASE)
            for kw in profile.keywords
        ):
            return False

    if profile.cpv_codes and tender.cpv_codes:
        if not any(c in (tender.cpv_codes or []) for c in profile.cpv_codes):
            return False

    if profile.it_categories and tender.it_category:
        if tender.it_category not in profile.it_categories:
            return False

    if profile.regions and tender.region:
        if not any(r.lower() in (tender.region or "").lower() for r in profile.regions):
            return False

    if profile.min_value and tender.value_max:
        if tender.value_max < profile.min_value:
            return False

    return True


async def run_alert_engine(db: AsyncSession, since: datetime | None = None) -> int:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(hours=6)

    tenders = (await db.execute(
        select(Tender).where(Tender.created_at >= since)
    )).scalars().all()

    profiles = (await db.execute(
        select(SearchProfile).where(SearchProfile.is_active.is_(True))
    )).scalars().all()

    created = 0
    for profile in profiles:
        for tender in tenders:
            if not _matches(tender, profile):
                continue
            existing = (await db.execute(
                select(Notification).where(and_(
                    Notification.profile_id == profile.id,
                    Notification.tender_id == tender.id,
                    Notification.notification_type == "new_match",
                ))
            )).scalar_one_or_none()
            if not existing:
                db.add(Notification(
                    profile_id=profile.id,
                    tender_id=tender.id,
                    notification_type="new_match",
                ))
                created += 1

    await db.commit()
    return created


async def run_deadline_warnings(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    warning_days = [7, 3, 1]
    created = 0

    interest_tags = (await db.execute(
        select(Tag).where(Tag.status == "interest").options(selectinload(Tag.tender))
    )).scalars().all()

    profiles = (await db.execute(
        select(SearchProfile).where(SearchProfile.is_active.is_(True))
    )).scalars().all()

    for tag in interest_tags:
        t = tag.tender
        if not t or not t.deadline:
            continue
        days_left = (t.deadline - now).days
        if days_left not in warning_days:
            continue

        for profile in profiles:
            notif_type = f"deadline_warning_{days_left}d"
            existing = (await db.execute(
                select(Notification).where(and_(
                    Notification.profile_id == profile.id,
                    Notification.tender_id == t.id,
                    Notification.notification_type == notif_type,
                ))
            )).scalar_one_or_none()
            if not existing:
                db.add(Notification(
                    profile_id=profile.id,
                    tender_id=t.id,
                    notification_type=notif_type,
                ))
                created += 1

    await db.commit()
    return created
