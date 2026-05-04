# OptiGrade

OptiGrade is an academic planning system for public universities. It optimizes semester course offerings by combining institutional constraints, teacher availability, room capacity, student demand, course equivalence and automatic enrollment.

The current pilot is modeled for UFPel engineering and computing programs. Demand forecasting and ML-based prediction are intentionally out of scope for the MVP.

## What It Solves

University course planning is usually fragmented, manual and hard to audit. OptiGrade turns the process into a repeatable workflow:

1. Students submit the courses they want for the next semester, including ordered alternatives such as "I want X, otherwise Y, otherwise Z".
2. The system compares student choices with regular curriculum flow, prerequisites, equivalences and completed history.
3. The optimizer builds course offerings by campus, course context, teacher constraints, rooms and time windows.
4. The administrator starts one run and receives a ready result: timetable plus automatic enrollment.
5. Students later see what was allocated, waitlisted or blocked.

## MVP Status

Implemented:

- FastAPI backend with SQLAlchemy, Alembic and PostgreSQL.
- Next.js frontend with Better Auth cookie sessions and organization-aware authorization.
- Separate CRUD pages for campus, degree programs, courses, restrictions, students, teachers, rooms and time slots.
- Teacher portal for complex constraints in natural language and structured form.
- Borrowed teachers with semester-specific reduced availability.
- Course context equivalence, including shared offerings across compatible programs.
- Course workload split into theoretical and practical hours.
- Student history, prerequisites, suggestions and ordered course request queues.
- Demand-driven timetable generation from eligible student requests.
- Automatic enrollment rounds with score-based allocation.
- Fully asynchronous optimization runs; API requests enqueue jobs and return immediately.
- Routed academic presentation at `/trabalho`, with admin-only slides and temporary QR codes.
- Kubernetes manifests for Traefik and the pilot domain.
- Full academic documentation in Markdown.

Not implemented yet:

- Demand prediction / ML forecasting.
- Full genetic algorithm with population, crossover and mutation.
- Real-time streaming progress for long optimization runs.
- Production-grade audit exports and institutional SSO.

## Optimization Portfolio

The MVP does not depend on a single solver. A run can combine:

- deterministic precheck for impossible scenarios;
- CP-SAT baseline with OR-Tools;
- multi-start greedy construction with parallel seeds;
- local search for reallocating sessions;
- optional Rust optimizer bridge;
- Pareto-style ranking and weighted scoring;
- automatic enrollment scoring after timetable generation.

`POST /optimization/runs` and `POST /optimization/runs/{id}/reoptimize` are asynchronous. They return an `OptimizationRun` in `pending` or `running` state, and clients poll `GET /optimization/runs/{id}` plus `GET /optimization/runs/{id}/assignments` for the final timetable.

Current hard constraints include teacher double-booking, room double-booking, room capacity, compatible campus, teacher qualification, lab requirements, course regular time windows and teacher maximum workload.

Teacher minimum workload is a soft warning. In a public university, a teacher can still fulfill institutional work hours outside classroom allocation, so low classroom load should be avoided but must not make a timetable infeasible.

## Pilot Benchmark

Latest Kubernetes pilot run for `balanced`, semester `2026/2`, demand-driven mode:

- Total flow time: 23min28s.
- Optimizer time: 23min12s.
- Hard conflicts: 0.
- Student requests allocated: 699 / 699.
- Waitlisted students: 0.
- Blocked students: 0.
- Minimum-load warnings: 5.
- Minimum-load shortfall: 8.33h.

This benchmark is hardware- and dataset-dependent. It is useful as a pilot reference, not as a universal performance guarantee.

## Architecture

```text
apps/web      Next.js App Router, Tailwind, Better Auth, BFF routes
apps/api      FastAPI, SQLAlchemy, Alembic, optimizer and enrollment services
apps/worker   Ray worker placeholder for future async jobs
crates/       Optional Rust optimizer bridge
docs/         PRD, architecture, API, optimization and academic documentation
k8s/          Kubernetes manifests for PostgreSQL, API, Web and Traefik ingress
sample-data/  Small CSV and JSON examples
scripts/      Pilot smoke checks
```

Runtime flow:

```text
Browser
  -> Next.js app
  -> Better Auth session / authorization
  -> Next.js BFF
  -> FastAPI internal API
  -> PostgreSQL
  -> optimizer / enrollment services
```

## Requirements

- Node.js 24+
- pnpm 10+
- Python 3.11+
- uv
- Docker or a local PostgreSQL 16 instance
- Optional: Rust toolchain for the optimizer bridge

## Local Setup

Create the environment file:

```bash
cp .env.example .env
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Install frontend dependencies:

```bash
pnpm install
```

Prepare the API:

```bash
cd apps/api
UV_CACHE_DIR=.uv-cache uv sync
UV_CACHE_DIR=.uv-cache uv run alembic upgrade head
UV_CACHE_DIR=.uv-cache uv run python -m app.seed
```

Run the API:

```bash
cd apps/api
UV_CACHE_DIR=.uv-cache uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the web app in another terminal:

```bash
pnpm dev:web
```

Open:

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- First admin setup: http://localhost:3000/setup
- Academic presentation: http://localhost:3000/trabalho

The presentation uses routed slides such as `/trabalho/apresentacao` and aliases like `/trabalho/slide1`.

## Pilot Data

Seed base data:

```bash
pnpm seed
```

Seed the UFPel pilot dataset:

```bash
cd apps/api
UV_CACHE_DIR=.uv-cache uv run python -m app.ufpel_pilot_seed
```

The UFPel pilot includes institutional-style course, teacher, campus and timetable data plus synthetic students and synthetic academic history. Synthetic student data does not represent real UFPel students.

## Tests

API lint:

```bash
cd apps/api
UV_CACHE_DIR=.uv-cache uv run ruff check app tests alembic
```

API tests:

```bash
cd apps/api
UV_CACHE_DIR=.uv-cache uv run pytest -q
```

Frontend typecheck and tests:

```bash
pnpm --filter @optigrade/web exec tsc --noEmit
pnpm --filter @optigrade/web test
```

Presentation walkthrough videos:

```bash
pnpm videos:trabalho
```

Full local check:

```bash
pnpm test
```

Pilot smoke check against a running API:

```bash
API_URL=http://127.0.0.1:8000 pnpm pilot:smoke
```

## Kubernetes

Manifests live in `k8s/optigrade`.

The deployment expects a secret named `optigrade-secrets` with:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DATABASE_URL`
- `BETTER_AUTH_DATABASE_URL`
- `BETTER_AUTH_SECRET`
- `OPTIGRADE_INTERNAL_API_SECRET`

In Kubernetes, `OPTIGRADE_REQUIRE_INTERNAL_SECRET=true` is set by default. The API will reject every non-health request unless the BFF sends `x-optigrade-internal-secret`, so `OPTIGRADE_INTERNAL_API_SECRET` must be present in the secret.

Apply the namespace, config, database, API, web and ingress:

```bash
kubectl apply -f k8s/optigrade/namespace.yaml
kubectl apply -f k8s/optigrade/config.yaml
kubectl apply -f k8s/optigrade/postgres.yaml
kubectl apply -f k8s/optigrade/api.yaml
kubectl apply -f k8s/optigrade/web.yaml
kubectl apply -f k8s/optigrade/ingress.yaml
```

Current pilot domain:

```text
https://optgrade.digital-directive.com
```

## Documentation

- [Academic documentation](docs/DOCUMENTACAO_ACADEMICA.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Optimization model](docs/OPTIMIZATION.md)
- [API](docs/API.md)
- [Pilot notes](docs/PILOTO.md)
- [UFPel pilot data](docs/UFPEL_PILOTO_DADOS.md)
- [Original PRD](docs/PRD.md)

## Security Notes

- `.env` and local secret files are ignored.
- Kubernetes secrets are not versioned.
- Production builds fail closed when `BETTER_AUTH_SECRET` is missing.
- The FastAPI service can require `OPTIGRADE_INTERNAL_API_SECRET` for every non-health request.
- Better Auth uses cookie sessions and organization-aware access control.
- The browser talks to FastAPI through the Next.js BFF, not directly in authenticated flows.
- OpenAI integration is optional. If `OPENAI_API_KEY` is absent, the system continues with deterministic structured rules.

## Roadmap

Near term:

- stream optimizer progress to the admin UI;
- persist run-level audit reports;
- add a true genetic algorithm / NSGA-II module;
- tune optimization weights with Optuna;
- improve manual adjustment and partial reoptimization UX.

Later:

- demand prediction;
- academic system integration;
- teacher-facing preference review;
- student-facing schedule preview after allocation;
- institutional SSO.

## License

This project is licensed under the [MIT License](LICENSE).
