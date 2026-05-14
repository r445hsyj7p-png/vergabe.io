import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import require_auth
from ..models import Notification, SearchProfile, Tender
from ..schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(True),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    stmt = select(Notification).options(
        selectinload(Notification.tender),
        selectinload(Notification.profile),
    ).order_by(Notification.triggered_at.desc()).limit(limit)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    rows = (await db.execute(stmt)).scalars().all()
    result = []
    for n in rows:
        out = NotificationOut.model_validate(n)
        out.profile_name = n.profile.name if n.profile else None
        result.append(out)
    return result


@router.patch("/{notif_id}/read", status_code=204)
async def mark_read(notif_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    await db.execute(update(Notification).where(Notification.id == notif_id).values(is_read=True))
    await db.commit()


@router.post("/mark-all-read", status_code=204)
async def mark_all_read(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    await db.execute(update(Notification).values(is_read=True))
    await db.commit()
