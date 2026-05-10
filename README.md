# vergabe.io

IT-Ausschreibungs-Aggregator für Deutschland, Österreich und Schweiz.

## Starten — lokale Entwicklung (OrbStack)

```bash
# 1. OrbStack installieren (macOS)
brew install orbstack

# 2. Repo entpacken und starten
cd vergabe
docker compose up
```

**Beim ersten Start erscheint automatisch:**

```
╔══════════════════════════════╗
║   vergabe.io — Setup         ║
╚══════════════════════════════╝

▶  Running database migrations…
▶  Seeding default data sources…
▶  Seeding starter Kommunen list…

══════════════════════════════════════════════════
  vergabe.io — Erster Start: Admin einrichten
══════════════════════════════════════════════════
  Admin-Passwort: ████████
  Passwort bestätigen: ████████

✓  Admin-Passwort gespeichert.
✓  Setup abgeschlossen. App startet…
```

Danach starten alle Services automatisch und der erste Crawl beginnt.

**App:** http://localhost:5173  
**API Docs:** http://localhost:8000/docs

## Zweiter Start (danach)

```bash
docker compose up
```

Kein Eingriff nötig — Setup erkennt, dass Admin bereits eingerichtet ist und überspringt die Passwort-Abfrage.

## Konfiguration (.env — optional)

Die `.env`-Datei ist nur für optionale Dienste nötig:

```env
# E-Mail-Alerts (optional)
SMTP_HOST=smtp.resend.com
SMTP_PASSWORD=re_...
SMTP_FROM=vergabe@domain.de

# LLM-Fallback (optional)
ANTHROPIC_API_KEY=sk-ant-...
```

Das Admin-Passwort wird **nie** in `.env` gespeichert — nur im Docker Volume `app_data`.

## Produktion

```bash
# Server: Ubuntu 24.04, Docker installiert
cp .env.example .env
nano infra/Caddyfile   # Domain anpassen

docker compose -f docker-compose.prod.yml up
# → Passwort-Dialog erscheint wie beim ersten lokalen Start
```

## Passwort zurücksetzen

```bash
# Volume löschen → beim nächsten Start neu abfragen
docker compose down
docker volume rm vergabe_app_data
docker compose up
```

## Stack

| Schicht | Technologie |
|---|---|
| Backend | FastAPI + SQLAlchemy async + PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Scheduler | APScheduler (TED 4h, bund.de 2h, Deadline-Warnings täglich) |
| Crawler | httpx + Playwright + feedparser |
| Frontend | React 18 + TypeScript + Vite |
| Proxy (Prod) | Caddy 2 (auto-HTTPS) |
| Runtime | Docker + OrbStack |
