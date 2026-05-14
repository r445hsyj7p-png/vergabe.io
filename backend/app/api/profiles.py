import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import require_auth
from ..models import SearchProfile
from ..schemas import ProfileCreate, ProfileOut

router = APIRouter(prefix="/search-profiles", tags=["profiles"])


@router.get("", response_model=list[ProfileOut])
async def list_profiles(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    rows = (await db.execute(select(SearchProfile).order_by(SearchProfile.created_at))).scalars().all()
    return rows


@router.post("", response_model=ProfileOut, status_code=201)
async def create_profile(body: ProfileCreate, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    p = SearchProfile(**body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@router.put("/{profile_id}", response_model=ProfileOut)
async def update_profile(profile_id: uuid.UUID, body: ProfileCreate, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    p = (await db.execute(select(SearchProfile).where(SearchProfile.id == profile_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Profile not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return p


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    p = (await db.execute(select(SearchProfile).where(SearchProfile.id == profile_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Profile not found")
    db.delete(p)
    await db.commit()
