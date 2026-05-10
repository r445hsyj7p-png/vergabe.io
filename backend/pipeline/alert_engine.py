"""Alert engine — matches new tenders against active search profiles."""
from datetime import datetime, timezone, timedelta
from typing import List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from models import Tender, SearchProfile, Notification, Tag
from config import settings


async def run_alert_engine(db: AsyncSession, since: datetime):
    """Match new tenders (created since `since`) against all active profiles."""
    # Load new tenders
    result = await db.execute(
        select(Tender).where(Tender.created_at >= since)
    )
    new_tenders = result.scalars().all()
    if not new_tenders:
        return 0

    # Load active profiles
    result = await db.execute(
        select(SearchProfile).where(SearchProfile.is_active == True)
    )
    profiles = result.scalars().all()

    matches_created = 0
    for profile in profiles:
        matched = _match_tenders(new_tenders, profile)
        for tender in matched:
            # Check if notification already exists
            r = await db.execute(
                select(Notification).where(
                    and_(
                        Notification.profile_id == profile.id,
                        Notification.tender_id == tender.id,
                        Notification.notification_type == "new_match",
                    )
                )
            )
            if r.scalar_one_or_none():
                continue

            notif = Notification(
                profile_id=profile.id,
                tender_id=tender.id,
                notification_type="new_match",
            )
            db.add(notif)
            matches_created += 1

    await db.commit()

    # Send email digests
    if matches_created > 0:
        await _send_email_digests(db, since)

    return matches_created


async def run_deadline_warnings(db: AsyncSession):
    """Create deadline warnings for interest-tagged tenders."""
    now = datetime.now(timezone.utc)
    warning_days = [7, 3, 1]

    for days in warning_days:
        target_date = now + timedelta(days=days)
        window_start = target_date.replace(hour=0, minute=0, second=0)
        window_end = target_date.replace(hour=23, minute=59, second=59)

        # Find tenders with deadline in this window and interest tag
        result = await db.execute(
            select(Tender)
            .join(Tag, Tag.tender_id == Tender.id)
            .where(
                and_(
                    Tag.status == "interest",
                    Tender.deadline >= window_start,
                    Tender.deadline <= window_end,
                )
            )
        )
        tenders = result.scalars().all()

        for tender in tenders:
            # Create notification for all active profiles
            r = await db.execute(
                select(SearchProfile).where(SearchProfile.is_active == True)
            )
            profiles = r.scalars().all()
            for profile in profiles:
                r2 = await db.execute(
                    select(Notification).where(
                        and_(
                            Notification.tender_id == tender.id,
                            Notification.notification_type == f"deadline_{days}d",
                        )
                    )
                )
                if r2.scalar_one_or_none():
                    continue
                notif = Notification(
                    profile_id=profile.id,
                    tender_id=tender.id,
                    notification_type=f"deadline_{days}d",
                )
                db.add(notif)

    await db.commit()


def _match_tenders(tenders: List[Tender], profile: SearchProfile) -> List[Tender]:
    """Filter tenders matching a profile's criteria."""
    matched = []
    for tender in tenders:
        if _matches(tender, profile):
            matched.append(tender)
    return matched


def _matches(tender: Tender, profile: SearchProfile) -> bool:
    combined = f"{tender.title or ''} {tender.description or ''}".lower()

    # Keyword match
    if profile.keywords:
        if not any(kw.lower() in combined for kw in profile.keywords):
            return False

    # CPV match
    if profile.cpv_codes and tender.cpv_codes:
        if not any(cpv in tender.cpv_codes for cpv in profile.cpv_codes):
            return False

    # Region match
    if profile.regions and tender.region:
        if not any(r.lower() in (tender.region or "").lower() for r in profile.regions):
            return False

    # Category match
    if profile.it_categories and tender.it_category:
        if tender.it_category not in profile.it_categories:
            return False

    # Min value
    if profile.min_value and tender.value_max:
        if tender.value_max < profile.min_value:
            return False

    # Deadline filter
    if profile.deadline_days and tender.deadline:
        cutoff = datetime.now(timezone.utc) + timedelta(days=profile.deadline_days)
        if tender.deadline > cutoff:
            return False

    return True


async def _send_email_digests(db: AsyncSession, since: datetime):
    """Send email for profiles with new matches."""
    if not settings.smtp_host:
        return

    result = await db.execute(
        select(SearchProfile).where(
            and_(SearchProfile.is_active == True, SearchProfile.email.isnot(None))
        )
    )
    profiles = result.scalars().all()

    for profile in profiles:
        result = await db.execute(
            select(Notification)
            .options(selectinload(Notification.tender))
            .where(
                and_(
                    Notification.profile_id == profile.id,
                    Notification.triggered_at >= since,
                    Notification.notification_type == "new_match",
                )
            )
        )
        notifications = result.scalars().all()
        if not notifications:
            continue

        _send_email(profile.email, profile.name, [n.tender for n in notifications if n.tender])


def _send_email(to_email: str, profile_name: str, tenders: list):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"vergabe.io — {len(tenders)} neue Ausschreibung(en) für „{profile_name}""
        msg["From"] = settings.smtp_from
        msg["To"] = to_email

        rows = ""
        for t in tenders[:20]:
            deadline = t.deadline.strftime("%d.%m.%Y") if t.deadline else "—"
            rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #eee"><strong>{t.title[:80]}</strong><br>
                <small style="color:#666">{t.contracting_authority or ''}</small></td>
                <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">{deadline}</td>
                <td style="padding:8px;border-bottom:1px solid #eee">
                    <a href="{t.source_url or '#'}" style="color:#1a56db">Ansehen →</a>
                </td>
            </tr>"""

        html = f"""<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
        <h2 style="color:#1a1917">vergabe.io</h2>
        <p>Neues für Ihr Suchprofil <strong>{profile_name}</strong>:</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
        <thead><tr>
            <th style="padding:8px;text-align:left;border-bottom:2px solid #eee">Ausschreibung</th>
            <th style="padding:8px;text-align:left;border-bottom:2px solid #eee">Frist</th>
            <th style="padding:8px;text-align:left;border-bottom:2px solid #eee"></th>
        </tr></thead>
        <tbody>{rows}</tbody>
        </table>
        <p style="color:#888;font-size:12px;margin-top:20px">vergabe.io Benachrichtigung</p>
        </body></html>"""

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, to_email, msg.as_string())
    except Exception as e:
        print(f"Email send failed to {to_email}: {e}")
