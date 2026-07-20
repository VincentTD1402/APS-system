set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set dotenv-load

compose := "docker compose"
be := "docker compose exec backend"
fe := "docker compose exec frontend"

# Import OS-specific recipes (auto-picked by [unix] / [windows] attributes)
import '.just/unix.just'
import '.just/windows.just'

# Default: banner + recipe list
default:
    @just _banner
    @just --list

_banner:
    @echo "APS System · OS: {{os()}} · arch: {{arch()}}"

# ─── Docker compose ────────────────────────────────────────────────────

# Start services. Usage: just up | just up -d | just up -d --build
up *args:
    {{compose}} up --build {{args}}

# Stop services (keep volumes)
down *args:
    {{compose}} down {{args}}

# Stop services AND wipe volumes (DESTROYS Postgres + Neo4j DATA)
[confirm("Wipe all volumes? This DELETES DB data! [y/N]")]
reset:
    {{compose}} down -v

# Show service status
ps:
    {{compose}} ps

# Tail logs. Usage: just logs | just logs backend | just logs frontend | just logs db | just logs neo4j
logs *args:
    {{compose}} logs -f {{args}}

# Rebuild images without cache
rebuild:
    {{compose}} build --no-cache

# Restart a service. Usage: just restart backend
restart service:
    {{compose}} restart {{service}}

# Open shell in a service (uses sh — bash may not exist on alpine images).
# Usage: just sh backend | just sh frontend | just sh db | just sh neo4j
sh service:
    {{compose}} exec {{service}} sh

# Psql into APS db. Usage: just psql | just psql <user> <db>
psql user=env_var_or_default("APS_DB_USER", "aps_user") db=env_var_or_default("APS_DB_NAME", "aps_db"):
    {{compose}} exec db psql -U {{user}} -d {{db}}

# Full fresh start: reset → up → migrate → seed (mock G-System)
[confirm("Full reset will DROP all DB data. Continue? [y/N]")]
bootstrap:
    {{compose}} down -v
    {{compose}} up -d --build
    just migrate
    just seed

# ─── Backend (runs inside `backend` container) ────────────────────────

# Apply pending migrations
migrate:
    {{be}} alembic upgrade head

# Create new migration. Usage: just migration "add_xxx_table"
migration name:
    {{be}} alembic revision --autogenerate -m "{{name}}"

# Roll back one migration step
downgrade:
    {{be}} alembic downgrade -1

# Seed via G-System pipeline (mock mode + wipe existing data)
seed:
    {{be}} python app/scripts/run_pipeline.py --use-mock --reset

# Seed via real G-System (requires VPN + GSYSTEM_DB_* configured)
seed-real:
    {{be}} python app/scripts/run_pipeline.py

# Lint backend (ruff)
lint-be:
    {{be}} uv run ruff check app

# Type check backend (mypy)
typecheck-be:
    {{be}} uv run mypy app

# Test backend (pytest)
test-be *args:
    {{be}} uv run pytest {{args}}

# Format backend (ruff format + fix)
fmt-be:
    {{be}} uv run ruff format app
    {{be}} uv run ruff check --fix app

# ─── Frontend (runs inside `frontend` container) ──────────────────────

# Lint frontend
lint-fe:
    {{fe}} pnpm lint

# Type check frontend
typecheck-fe:
    {{fe}} pnpm typecheck

# Test frontend (Vitest)
test-fe *args:
    {{fe}} pnpm test {{args}}

# Format frontend (prettier)
fmt-fe:
    {{fe}} pnpm exec prettier --write "src/**/*.{ts,vue,json,css}"

# Build frontend for production
build-fe:
    {{fe}} pnpm build

# ─── Combined (backend + frontend) ────────────────────────────────────

lint: lint-be lint-fe
typecheck: typecheck-be typecheck-fe
test: test-be test-fe
fmt: fmt-be fmt-fe

# Full local CI: lint + typecheck + test + FE build
ci: lint typecheck test build-fe

# ─── Dependency management (runs on host — needs uv/pnpm installed) ──

# Add backend runtime dep. Usage: just be-add fastapi
be-add *deps:
    uv --directory aps-backend add {{deps}}

# Remove backend dep. Usage: just be-remove neo4j
be-remove *deps:
    uv --directory aps-backend remove {{deps}}

# Add frontend dep. Usage: just fe-add axios | just fe-add -D vitest
fe-add *deps:
    pnpm --dir aps-frontend add {{deps}}

# Remove frontend dep
fe-remove *deps:
    pnpm --dir aps-frontend remove {{deps}}
