import logging
import re
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Tender, SearchProfile, Notification, Tag
from ..core.config import settings

logger = logging.getLogger(__name__)


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


def _format_digest(profile_name: str, tenders: list[Tender]) -> str:
    lines = [f'Neue Ausschreibungen für Ihr Suchprofil "{profile_name}":', ""]
    for t in tenders[:10]:
        deadline = t.deadline.strftime("%d.%m.%Y") if t.deadline else "—"
        value = f"€{(t.value_max or 0) // 100:,}" if t.value_max else "—"
        lines += [
            f"• {t.title}",
            f"  Auftraggeber: {t.contracting_authority or '—'}",
            f"  Frist: {deadline} | Wert: {value}",
            f"  URL: {t.source_url or '—'}",
            "",
        ]
    if len(tenders) > 10:
        lines.append(f"… und {len(tenders) - 10} weitere.")
    return "\n".join(lines)


def _send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        return
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if settings.smtp_user:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.smtp_from, [to], msg.as_string())
    except Exception as exc:
        logger.warning("Failed to send email to %s: %s", to, exc)


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
        new_tenders: list[Tender] = []
        for tender in tenders:
            if not _matches(tender, profile):
                continue
            result = await db.execute(
                pg_insert(Notification)
                .values(
                    profile_id=profile.id,
                    tender_id=tender.id,
                    notification_type="new_match",
                )
                .on_conflict_do_nothing()
                .returning(Notification.id)
            )
            if result.scalar_one_or_none() is not None:
                created += 1
                new_tenders.append(tender)

        if profile.email and new_tenders:
            _send_email(
                to=profile.email,
                subject=f"[vergabe.io] {len(new_tenders)} neue Ausschreibung(en) für „{profile.name}"",
                body=_format_digest(profile.name, new_tenders),
            )

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

        notified_profiles: list[SearchProfile] = []
        for profile in profiles:
            notif_type = f"deadline_warning_{days_left}d"
            result = await db.execute(
                pg_insert(Notification)
                .values(
                    profile_id=profile.id,
                    tender_id=t.id,
                    notification_type=notif_type,
                )
                .on_conflict_do_nothing()
                .returning(Notification.id)
            )
            if result.scalar_one_or_none() is not None:
                created += 1
                notified_profiles.append(profile)

        for profile in notified_profiles:
            if profile.email:
                deadline_str = t.deadline.strftime("%d.%m.%Y")
                _send_email(
                    to=profile.email,
                    subject=f"[vergabe.io] Frist in {days_left} Tag(en): {t.title[:60]}",
                    body=(
                        f"Erinnerung: Die Einreichungsfrist endet am {deadline_str}.\n\n"
                        f"Ausschreibung: {t.title}\n"
                        f"Auftraggeber: {t.contracting_authority or '—'}\n"
                        f"URL: {t.source_url or '—'}\n"
                    ),
                )

    await db.commit()
    return created
