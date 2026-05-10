from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from database import get_db
from models import SearchProfile
from schemas import SearchProfileCreate, SearchProfileOut
from auth import require_auth

router = APIRouter(prefix="/search-profiles", tags=["profiles"])


@router.get("", response_model=List[SearchProfileOut])
async def list_profiles(db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    result = await db.execute(select(SearchProfile).order_by(SearchProfile.created_at))
    return result.scalars().all()


@router.post("", response_model=SearchProfileOut)
async def create_profile(body: SearchProfileCreate, db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    profile = SearchProfile(**body.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.put("/{profile_id}", response_model=SearchProfileOut)
async def update_profile(profile_id: uuid.UUID, body: SearchProfileCreate, db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    result = await db.execute(select(SearchProfile).where(SearchProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")
    for k, v in body.model_dump().items():
        setattr(profile, k, v)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db), token=Depends(require_auth)):
    result = await db.execute(select(SearchProfile).where(SearchProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")
    await db.delete(profile)
    await db.commit()
