from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models import AppSetting
from ..core.password import hash_password

router = APIRouter(tags=["setup"])


class SetupRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen haben")
        return v


@router.get("/setup")
async def setup_status(db: AsyncSession = Depends(get_db)):
    row = (await db.execute(
        select(AppSetting).where(AppSetting.key == "admin_password_hash")
    )).scalar_one_or_none()
    return {"setup_required": row is None}


@router.post("/setup", status_code=201)
async def complete_setup(body: SetupRequest, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(
        select(AppSetting).where(AppSetting.key == "admin_password_hash")
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Setup wurde bereits abgeschlossen")

    db.add(AppSetting(key="admin_password_hash", value=hash_password(body.password)))
    await db.commit()
    return {"ok": True}
