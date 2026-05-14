from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.auth import create_access_token, require_auth
from .schemas import LoginRequest, TokenResponse
from .api import tenders, profiles, notifications, admin


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
async def login(body: LoginRequest):
    if body.password != settings.admin_password:
        raise HTTPException(401, "Invalid password")
    return TokenResponse(access_token=create_access_token())


@app.get("/health")
async def health():
    return {"status": "ok"}
