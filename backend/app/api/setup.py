from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models import AppSetting
from ..core.password import hash_password

router = APIRouter(tags=["setup"])


class SetupRequest(BaseModel):
    name: str
    email: str
    password: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name darf nicht leer sein")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Ungültige E-Mail-Adresse")
        return v

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
    stmt = (
        pg_insert(AppSetting)
        .values(key="admin_password_hash", value=hash_password(body.password))
        .on_conflict_do_nothing(index_elements=["key"])
        .returning(AppSetting.key)
    )
    result = await db.execute(stmt)

    if result.fetchone() is None:
        await db.rollback()
        raise HTTPException(409, "Setup wurde bereits abgeschlossen")

    await db.execute(
        pg_insert(AppSetting)
        .values(key="admin_name", value=body.name)
        .on_conflict_do_update(index_elements=["key"], set_={"value": body.name})
    )
    await db.execute(
        pg_insert(AppSetting)
        .values(key="admin_email", value=body.email)
        .on_conflict_do_update(index_elements=["key"], set_={"value": body.email})
    )
    await db.commit()

    return {"ok": True}
