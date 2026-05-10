"""vergabe.io — FastAPI Backend"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from database import engine, Base
from config import settings
from api.tenders import router as tenders_router
from api.profiles import router as profiles_router
from api.notifications import router as notifications_router
from api.admin import router as admin_router
from api.summaries import router as summaries_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    print("Database connected.")
    yield
    await engine.dispose()


app = FastAPI(
    title="vergabe.io API",
    description="IT-Ausschreibungs-Aggregator für Deutschland, Österreich und Schweiz",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenders_router)
app.include_router(profiles_router)
app.include_router(notifications_router)
app.include_router(admin_router)
app.include_router(summaries_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "vergabe.io"}


@app.post("/auth/token")
async def login(password: str):
    if password == settings.admin_password:
        return {"access_token": settings.secret_key, "token_type": "bearer"}
    from fastapi import HTTPException
    raise HTTPException(401, "Invalid password")
