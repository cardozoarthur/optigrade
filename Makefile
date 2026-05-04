.PHONY: check postgres api web seed migrate optimizer worker test pilot-check pilot-smoke

check:
	bash scripts/dev-check.sh

postgres:
	docker compose up -d postgres

migrate:
	cd apps/api && UV_CACHE_DIR=.uv-cache uv run alembic upgrade head

seed:
	cd apps/api && UV_CACHE_DIR=.uv-cache uv run python -m app.seed

api:
	cd apps/api && UV_CACHE_DIR=.uv-cache uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:
	pnpm --filter @optigrade/web dev

worker:
	cd apps/worker && UV_CACHE_DIR=.uv-cache uv run python -m app.main

optimizer:
	cargo build --manifest-path crates/optimizer/Cargo.toml --release

test:
	pnpm test

pilot-check:
	bash scripts/pilot-check.sh

pilot-smoke:
	node scripts/pilot-smoke.mjs
