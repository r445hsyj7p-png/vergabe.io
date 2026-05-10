from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid, os

from database import get_db
from models import Tender, TenderSummary
from auth import require_auth

router = APIRouter(prefix="/tenders", tags=["summaries"])


class SummaryOut(BaseModel):
    tender_id: uuid.UUID
    summary_text: str
    provider: str
    model: Optional[str]
    cost_cents: int
    created_at: datetime
    model_config = {"from_attributes": True}


class SummaryStatus(BaseModel):
    exists: bool
    summary: Optional[SummaryOut] = None
    provider_configured: str


@router.get("/{tender_id}/summary", response_model=SummaryStatus)
async def get_summary(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_auth),
):
    """Return cached summary if it exists, plus which provider is configured."""
    result = await db.execute(
        select(TenderSummary).where(TenderSummary.tender_id == tender_id)
    )
    summary = result.scalar_one_or_none()
    provider_name = os.environ.get("SUMMARY_PROVIDER", "anthropic")

    return SummaryStatus(
        exists=summary is not None,
        summary=SummaryOut.model_validate(summary) if summary else None,
        provider_configured=provider_name,
    )


@router.post("/{tender_id}/summary", response_model=SummaryOut)
async def generate_summary(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_auth),
):
    """
    Generate a summary for a tender on demand.
    Returns cached version immediately if it already exists.
    On first call: calls the configured LLM provider and caches result.
    """
    # Return cached if exists
    result = await db.execute(
        select(TenderSummary).where(TenderSummary.tender_id == tender_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return SummaryOut.model_validate(existing)

    # Load tender
    t_result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = t_result.scalar_one_or_none()
    if not tender:
        raise HTTPException(404, "Tender not found")

    # Format volume
    volume_str = None
    if tender.value_max:
        val = tender.value_max / 100
        if val >= 1_000_000:
            volume_str = f"{val/1_000_000:.1f} Mio {tender.currency}"
        else:
            volume_str = f"{val:,.0f} {tender.currency}"

    # Call LLM provider
    from services.summary_provider import get_provider
    provider = get_provider()
    provider_name = os.environ.get("SUMMARY_PROVIDER", "anthropic")

    try:
        summary_text, cost_cents = await provider.generate(
            title=tender.title,
            description=tender.description,
            authority=tender.contracting_authority,
            deadline=tender.deadline,
            volume=volume_str,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider error ({provider_name}): {str(e)}. "
                   f"Prüfe deine .env Konfiguration (SUMMARY_PROVIDER, API-Keys, OLLAMA_BASE_URL)."
        )

    if not summary_text:
        raise HTTPException(502, "LLM returned empty response")

    # Determine model name for logging
    model_name = _get_model_name(provider_name)

    # Store in DB
    summary = TenderSummary(
        tender_id=tender.id,
        summary_text=summary_text,
        provider=provider_name,
        model=model_name,
        cost_cents=cost_cents,
    )
    db.add(summary)
    await db.commit()
    await db.refresh(summary)

    return SummaryOut.model_validate(summary)


@router.delete("/{tender_id}/summary", status_code=204)
async def delete_summary(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_auth),
):
    """Delete cached summary (forces regeneration on next request)."""
    result = await db.execute(
        select(TenderSummary).where(TenderSummary.tender_id == tender_id)
    )
    summary = result.scalar_one_or_none()
    if summary:
        await db.delete(summary)
        await db.commit()


def _get_model_name(provider: str) -> str:
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    elif provider == "ollama":
        return os.environ.get("OLLAMA_MODEL", "llama3.2")
    elif provider == "openai":
        return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    return "unknown"
