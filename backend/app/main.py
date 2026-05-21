from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.auth import create_access_token, require_auth
from .schemas import LoginRequest, TokenResponse
from .api import tenders, profiles, notifications, admin

_login_attempts: dict[str, list[datetime]] = defaultdict(list)
_RATE_WINDOW = timedelta(minutes=1)
_RATE_LIMIT = 5


def _check_rate_limit(ip: str) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - _RATE_WINDOW
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

app.include_router(tenders.router)
app.include_router(profiles.router)
app.include_router(notifications.router)
app.include_router(admin.router)


@app.post("/auth/token", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    if not _check_rate_limit(ip):
        raise HTTPException(429, "Too many login attempts, try again in a minute")
    if body.password != settings.admin_password:
        raise HTTPException(401, "Invalid password")
    return TokenResponse(access_token=create_access_token())


@app.get("/health")
async def health():
    return {"status": "ok"}
