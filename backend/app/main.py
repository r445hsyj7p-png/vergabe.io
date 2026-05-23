import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import settings
from .core.auth import create_access_token
from .core.database import get_db
from .core.password import verify_password
from .models import AppSetting
from .schemas import LoginRequest, TokenResponse
from .api import tenders, profiles, notifications, admin
from .api.setup import router as setup_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

_login_attempts: dict[str, list[datetime]] = defaultdict(list)
_RATE_WINDOW = timedelta(minutes=1)
_RATE_LIMIT = 5
_MAX_TRACKED_IPS = 5_000


def _check_rate_limit(ip: str) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - _RATE_WINDOW
    if len(_login_attempts) > _MAX_TRACKED_IPS:
        _login_attempts.clear()
    recent = [t for t in _login_attempts[ip] if t > cutoff]
    _login_attempts[ip] = recent
    if len(recent) >= _RATE_LIMIT:
        return False
    recent.append(now)
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .services.seed import seed_all
    from .core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await seed_all(db)

    from .scheduler.jobs import start_scheduler
    scheduler = start_scheduler()

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="vergabe.io API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(setup_router)
app.include_router(tenders.router)
app.include_router(profiles.router)
app.include_router(notifications.router)
app.include_router(admin.router)


@app.post("/auth/token", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    if not _check_rate_limit(ip):
        raise HTTPException(429, "Too many login attempts, try again in a minute")

    row = (await db.execute(
        select(AppSetting).where(AppSetting.key == "admin_password_hash")
    )).scalar_one_or_none()

    if not row or not verify_password(body.password, row.value):
        raise HTTPException(401, "Invalid password")

    return TokenResponse(access_token=create_access_token())


@app.get("/health")
async def health():
    provider = settings.summary_provider
    key_configured = bool(
        (provider == "anthropic" and settings.anthropic_api_key) or
        (provider == "openai" and settings.openai_api_key) or
        provider == "ollama"
    )
    return {
        "status": "ok",
        "summary_provider": provider,
        "summary_api_key_set": key_configured,
    }
