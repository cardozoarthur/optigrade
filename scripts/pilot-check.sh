#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="${API_URL:-http://127.0.0.1:8002}"
WEB_URL="${WEB_URL:-http://127.0.0.1:3301}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"
export API_URL

cd "$ROOT_DIR"

printf "\n== Toolchain ==\n"
bash scripts/dev-check.sh

printf "\n== Database migrations ==\n"
(
  cd apps/api
  uv run alembic upgrade head
)

printf "\n== Backend checks ==\n"
python3.11 -m compileall apps/api/app
(
  cd apps/api
  uv run ruff check app tests alembic
  uv run pytest
)

printf "\n== Frontend checks ==\n"
pnpm --filter @optigrade/web exec tsc --noEmit
pnpm --filter @optigrade/web test
NEXT_DIST_DIR=.next-pilot-build pnpm --filter @optigrade/web build
sed -i 's#./.next-pilot-build/types/routes.d.ts#./.next/types/routes.d.ts#' apps/web/next-env.d.ts

printf "\n== Optimizer checks ==\n"
cargo test --manifest-path crates/optimizer/Cargo.toml

printf "\n== Running services ==\n"
curl -fsS "$API_URL/health" >/dev/null
curl -fsS "$API_URL/readiness" >/dev/null
curl -fsS "$WEB_URL" >/dev/null
printf "API ok: %s\n" "$API_URL"
printf "Web ok: %s\n" "$WEB_URL"

printf "\n== Pilot smoke flow ==\n"
node scripts/pilot-smoke.mjs

printf "\nPilot check completed.\n"
