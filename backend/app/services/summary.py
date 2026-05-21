import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Tender, TenderSummary
from ..core.config import settings

logger = logging.getLogger(__name__)

PROMPT = """Du bist ein Experte für öffentliche Vergabe in Deutschland.
Fasse die folgende Ausschreibung in 2-3 prägnanten Sätzen auf Deutsch zusammen.
Betone: Was wird gesucht? Wer schreibt aus? Welches Volumen / Deadline?

Ausschreibung:
Titel: {title}
Auftraggeber: {authority}
Beschreibung: {description}
"""


async def generate_and_store(tender_id: uuid.UUID, db: AsyncSession) -> TenderSummary:
    t = (await db.execute(select(Tender).where(Tender.id == tender_id))).scalar_one_or_none()
    if not t:
        logger.warning("Summary requested for unknown tender %s", tender_id)
        raise HTTPException(404, "Ausschreibung nicht gefunden")

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
    logger.info("Generating summary for tender %s via provider=%s", tender_id, provider)

    try:
        if provider == "anthropic":
            summary_text, model_name, cost_cents = await _anthropic(prompt)
        elif provider == "ollama":
            summary_text, model_name, cost_cents = await _ollama(prompt)
        elif provider == "openai":
            summary_text, model_name, cost_cents = await _openai(prompt)
        else:
            raise HTTPException(400, f"Unbekannter Provider: {provider}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error generating summary via %s: %s", provider, exc)
        raise HTTPException(502, f"KI-Provider ({provider}) hat einen unerwarteten Fehler zurückgegeben: {type(exc).__name__}")

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
    logger.info("Summary stored for tender %s (model=%s, cost=%d ct)", tender_id, model_name, cost_cents)
    return s


async def _anthropic(prompt: str):
    import anthropic

    if not settings.anthropic_api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY nicht konfiguriert — bitte in der .env-Datei setzen")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    model = "claude-haiku-4-5-20251001"

    try:
        msg = await client.messages.create(
            model=model, max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as exc:
        logger.error("Anthropic authentication failed: %s", exc)
        raise HTTPException(401, "Anthropic API-Key ungültig oder abgelaufen — ANTHROPIC_API_KEY prüfen")
    except anthropic.RateLimitError as exc:
        logger.warning("Anthropic rate limit hit: %s", exc)
        raise HTTPException(429, "Anthropic Rate-Limit erreicht — bitte kurz warten und erneut versuchen")
    except anthropic.APIConnectionError as exc:
        logger.error("Anthropic connection error: %s", exc)
        raise HTTPException(502, "Verbindung zur Anthropic API fehlgeschlagen — Netzwerk oder API nicht erreichbar")
    except anthropic.APIStatusError as exc:
        logger.error("Anthropic API error %s: %s", exc.status_code, exc.message)
        raise HTTPException(502, f"Anthropic API Fehler {exc.status_code}: {exc.message}")

    text = msg.content[0].text
    cost = int((msg.usage.input_tokens * 0.025 + msg.usage.output_tokens * 0.125) / 1000 * 100)
    return text, model, cost


async def _ollama(prompt: str):
    import httpx

    model = settings.ollama_model
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
    except httpx.ConnectError as exc:
        logger.error("Ollama connection failed at %s: %s", settings.ollama_base_url, exc)
        raise HTTPException(502, f"Ollama nicht erreichbar unter {settings.ollama_base_url} — läuft der Ollama-Server?")
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama HTTP error %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(502, f"Ollama Fehler {exc.response.status_code}: {exc.response.text[:200]}")
    except httpx.TimeoutException:
        logger.error("Ollama request timed out (model=%s)", model)
        raise HTTPException(504, f"Ollama hat nicht rechtzeitig geantwortet (Modell: {model})")

    return r.json()["response"], model, 0


async def _openai(prompt: str):
    import openai

    if not settings.openai_api_key:
        raise HTTPException(400, "OPENAI_API_KEY nicht konfiguriert — bitte in der .env-Datei setzen")

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    model = "gpt-4o-mini"

    try:
        resp = await client.chat.completions.create(
            model=model, max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
    except openai.AuthenticationError as exc:
        logger.error("OpenAI authentication failed: %s", exc)
        raise HTTPException(401, "OpenAI API-Key ungültig oder abgelaufen — OPENAI_API_KEY prüfen")
    except openai.RateLimitError as exc:
        logger.warning("OpenAI rate limit hit: %s", exc)
        raise HTTPException(429, "OpenAI Rate-Limit erreicht — bitte kurz warten und erneut versuchen")
    except openai.APIConnectionError as exc:
        logger.error("OpenAI connection error: %s", exc)
        raise HTTPException(502, "Verbindung zur OpenAI API fehlgeschlagen — Netzwerk oder API nicht erreichbar")
    except openai.APIStatusError as exc:
        logger.error("OpenAI API error %s: %s", exc.status_code, exc.message)
        raise HTTPException(502, f"OpenAI API Fehler {exc.status_code}: {exc.message}")

    text = resp.choices[0].message.content or ""
    cost = int((resp.usage.prompt_tokens * 0.015 + resp.usage.completion_tokens * 0.06) / 1000 * 100)
    return text, model, cost
