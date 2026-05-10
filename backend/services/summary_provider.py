"""
Summary Provider — austauschbare LLM-Abstraktion für Ausschreibungs-Zusammenfassungen.

Wähle Provider via ENV:
  SUMMARY_PROVIDER=anthropic   # Anthropic API (claude-haiku)
  SUMMARY_PROVIDER=ollama      # Lokales LLM via Ollama
  SUMMARY_PROVIDER=openai      # OpenAI API (gpt-4o-mini)
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime


SUMMARY_PROMPT = """Du bist ein Assistent für öffentliche Ausschreibungen im IT-Bereich.

Erstelle eine prägnante Zusammenfassung der folgenden Ausschreibung auf Deutsch.
Beantworte dabei genau diese drei Fragen in 2-3 Sätzen gesamt:
1. Was wird konkret gesucht/beschafft?
2. Für wen ist diese Ausschreibung besonders relevant?
3. Was ist der wichtigste Aspekt (Deadline, Volumen, Besonderheit)?

Sei direkt und vermeide Floskeln. Keine Aufzählungen, nur Fließtext.

Ausschreibung:
Titel: {title}
Auftraggeber: {authority}
Frist: {deadline}
Volumen: {volume}
Beschreibung: {description}

Zusammenfassung:"""


class SummaryProvider(ABC):
    """Gemeinsames Interface für alle LLM-Provider."""

    @abstractmethod
    async def generate(
        self,
        title: str,
        description: Optional[str],
        authority: Optional[str],
        deadline: Optional[datetime],
        volume: Optional[str],
    ) -> tuple[str, int]:
        """
        Generiert eine Zusammenfassung.
        Returns: (summary_text, cost_in_cents)
        """
        ...

    def _build_prompt(
        self,
        title: str,
        description: Optional[str],
        authority: Optional[str],
        deadline: Optional[datetime],
        volume: Optional[str],
    ) -> str:
        return SUMMARY_PROMPT.format(
            title=title[:300],
            authority=authority or "Nicht angegeben",
            deadline=deadline.strftime("%d.%m.%Y") if deadline else "Nicht angegeben",
            volume=volume or "Nicht angegeben",
            description=(description or "Keine Beschreibung verfügbar")[:1500],
        )


class AnthropicProvider(SummaryProvider):
    """claude-haiku — ~0,001 € pro Summary."""

    def __init__(self):
        import anthropic as _anthropic
        self._client = _anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self._model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    async def generate(self, title, description, authority, deadline, volume) -> tuple[str, int]:
        prompt = self._build_prompt(title, description, authority, deadline, volume)
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Cost estimate: haiku input ~$0.25/MTok, output ~$1.25/MTok
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = (input_tokens * 0.00000025) + (output_tokens * 0.00000125)
        cost_cents = max(1, round(cost_usd * 100))
        return text, cost_cents


class OllamaProvider(SummaryProvider):
    """Lokales LLM via Ollama — kostenfrei."""

    def __init__(self):
        import httpx
        self._base = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self._model = os.environ.get("OLLAMA_MODEL", "llama3.2")
        self._client = httpx.AsyncClient(timeout=120)

    async def generate(self, title, description, authority, deadline, volume) -> tuple[str, int]:
        import httpx
        prompt = self._build_prompt(title, description, authority, deadline, volume)
        response = await self._client.post(
            f"{self._base}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 300, "temperature": 0.3},
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("response", "").strip()
        return text, 0  # kostenlos


class OpenAIProvider(SummaryProvider):
    """OpenAI gpt-4o-mini — ~0,0005 € pro Summary."""

    def __init__(self):
        import openai as _openai
        self._client = _openai.AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", "")
        )
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    async def generate(self, title, description, authority, deadline, volume) -> tuple[str, int]:
        prompt = self._build_prompt(title, description, authority, deadline, volume)
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=300,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        # Cost estimate: gpt-4o-mini $0.15/MTok input, $0.60/MTok output
        usage = response.usage
        cost_usd = (usage.prompt_tokens * 0.00000015) + (usage.completion_tokens * 0.0000006)
        cost_cents = max(1, round(cost_usd * 100))
        return text, cost_cents


def get_provider() -> SummaryProvider:
    """Factory — wählt Provider aus ENV."""
    provider_name = os.environ.get("SUMMARY_PROVIDER", "anthropic").lower()
    if provider_name == "ollama":
        return OllamaProvider()
    elif provider_name == "openai":
        return OpenAIProvider()
    else:
        return AnthropicProvider()
