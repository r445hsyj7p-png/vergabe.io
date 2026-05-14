from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Tender, TenderSummary
from ..core.config import settings

PROMPT = """Du bist ein Experte für öffentliche Vergabe in Deutschland.
Fasse die folgende Ausschreibung in 2-3 prägnanten Sätzen auf Deutsch zusammen.
Betone: Was wird gesucht? Wer schreibt aus? Welches Volumen / Deadline?

Ausschreibung:
Titel: {title}
Auftraggeber: {authority}
Beschreibung: {description}
"""


async def generate_and_store(tender_id: str, db: AsyncSession) -> TenderSummary:
    t = (await db.execute(select(Tender).where(Tender.id == tender_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tender not found")

    existing = (await db.execute(
        select(TenderSummary).where(TenderSummary.tender_id == tender_id)
    )).scalar_one_or_none()
    if existing:
        db.delete(existing)
        await db.flush()

    prompt = PROMPT.format(
        title=t.title,
        authority=t.contracting_authority or "Unbekannt",
        description=(t.description or "")[:1500],
    )

    provider = settings.summary_provider
    summary_text, model_name, cost_cents = "", "", 0

    if provider == "anthropic":
        summary_text, model_name, cost_cents = await _anthropic(prompt)
    elif provider == "ollama":
        summary_text, model_name, cost_cents = await _ollama(prompt)
    elif provider == "openai":
        summary_text, model_name, cost_cents = await _openai(prompt)
    else:
        raise HTTPException(400, f"Unknown provider: {provider}")

    s = TenderSummary(
        tender_id=tender_id,
        summary_text=summary_text,
        provider=provider,
        model=model_name,
        cost_cents=cost_cents,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _anthropic(prompt: str):
    if not settings.anthropic_api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY not configured")
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    model = "claude-haiku-4-5-20251001"
    msg = await client.messages.create(
        model=model, max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text
    cost = int((msg.usage.input_tokens * 0.025 + msg.usage.output_tokens * 0.125) / 1000 * 100)
    return text, model, cost


async def _ollama(prompt: str):
    import httpx
    model = settings.ollama_model
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        return r.json()["response"], model, 0


async def _openai(prompt: str):
    if not settings.openai_api_key:
        raise HTTPException(400, "OPENAI_API_KEY not configured")
    import openai
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    model = "gpt-4o-mini"
    resp = await client.chat.completions.create(
        model=model, max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content or ""
    cost = int((resp.usage.prompt_tokens * 0.015 + resp.usage.completion_tokens * 0.06) / 1000 * 100)
    return text, model, cost
