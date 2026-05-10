from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from typing import List
import uuid

from database import get_db
from models import Notification, SearchProfile, Tender
from schemas import NotificationOut
from auth import require_auth

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    unread_only: bool = True,
    db: AsyncSession = Depends(get_db),
    token=Depends(require_auth),
):
    stmt = (
        select(Notification)
        .options(
            selectinload(Notification.tender),
            selectinload(Notification.profile),
        )
        .order_by(Notification.triggered_at.desc())
        .limit(50)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)

    result = await db.execute(stmt)
    notifications = result.scalars().all()

    out = []
    for n in notifications:
        item = NotificationOut.model_validate(n)
        if n.tender:
            from schemas import TenderListItem
            item.tender = TenderListItem.model_validate(n.tender)
        if n.profile:
            item.profile_name = n.profile.name
        out.append(item)
    return out


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token=Depends(require_auth),
):
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    n = result.scalar_one_or_none()
    if not n:
        raise HTTPException(404, "Not found")
    n.is_read = True
    await db.commit()
    await db.refresh(n)
    return n


@router.post("/mark-all-read", status_code=204)
async def mark_all_read(db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    await db.execute(update(Notification).values(is_read=True))
    await db.commit()
