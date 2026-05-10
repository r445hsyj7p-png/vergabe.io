.PHONY: up down logs migrate seed shell-backend shell-db crawl-ted crawl-bund

up:
	cp -n .env.example .env 2>/dev/null || true
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python /app/../scripts/import_destatis.py

shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec postgres psql -U vergabe vergabe

crawl-ted:
	docker compose exec scheduler python -c "import asyncio; from scheduler.main import job_ted; asyncio.run(job_ted())"

crawl-bund:
	docker compose exec scheduler python -c "import asyncio; from scheduler.main import job_bund; asyncio.run(job_bund())"

restart-backend:
	docker compose restart backend scheduler

build:
	docker compose build

status:
	docker compose ps
