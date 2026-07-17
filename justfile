set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set dotenv-load

compose := "docker compose"

backend-justfile := "aps-backend/Justfile"
frontend-justfile := "aps-frontend/Justfile"

# Import OS-specific recipes (auto-picked by [unix] / [windows] attributes)
import '.just/unix.just'
import '.just/windows.just'

# Default: list recipes with OS info
default:
    @just _banner
    @just --list

_banner:
    @echo "APS System · OS: {{os()}} · arch: {{arch()}}"

# ─── Docker compose (cross-platform) ───────────────────────────────────

# Start services. Usage: just up | just up -d | just up -d --build
up *args:
    {{compose}} up --build {{args}}

# Stop services (keep volumes)
down *args:
    {{compose}} down {{args}}

# Stop services AND wipe volumes (DESTROYS DB DATA)
[confirm("Wipe all volumes? This DELETES Postgres data! [y/N]")]
reset:
    {{compose}} down -v

# Show service status
ps:
    {{compose}} ps

# Tail logs. Usage: just logs | just logs backend | just logs frontend | just logs db
logs *args:
    {{compose}} logs -f {{args}}

# Rebuild images without cache
rebuild:
    {{compose}} build --no-cache

# Restart a service. Usage: just restart backend
restart service:
    {{compose}} restart {{service}}

# Open shell in a service (uses sh — bash may not exist on alpine images).
# Usage: just sh backend | just sh frontend | just sh db
sh service:
    {{compose}} exec {{service}} sh

# Psql into db. Usage: just psql | just psql postgres another_db
psql user=env_var_or_default("POSTGRES_USER", "aps") db=env_var_or_default("POSTGRES_DB", "aps"):
    {{compose}} exec db psql -U {{user}} -d {{db}}

# Full fresh start: reset → up → migrate → seed
[confirm("Full reset will DROP all DB data. Continue? [y/N]")]
bootstrap:
    {{compose}} down -v
    {{compose}} up -d --build
    just migrate
    just seed

# ─── Delegated to subprojects ──────────────────────────────────────────

# Apply migrations (delegates to backend)
migrate:
    just --justfile {{backend-justfile}} migrate

# Create new migration. Usage: just migration "add_xxx_table"
migration name:
    just --justfile {{backend-justfile}} migration "{{name}}"

# Roll back one migration step
downgrade:
    just --justfile {{backend-justfile}} downgrade

# Seed reference data
seed:
    just --justfile {{backend-justfile}} seed

# Lint backend + frontend
lint:
    just --justfile {{backend-justfile}} lint
    just --justfile {{frontend-justfile}} lint

# Type check backend + frontend
typecheck:
    just --justfile {{backend-justfile}} typecheck
    just --justfile {{frontend-justfile}} typecheck

# Run tests backend + frontend
test:
    just --justfile {{backend-justfile}} test
    just --justfile {{frontend-justfile}} test

# Format backend + frontend
fmt:
    just --justfile {{backend-justfile}} fmt
    just --justfile {{frontend-justfile}} fmt

# Full local CI: lint + typecheck + test + FE build
ci: lint typecheck test
    just --justfile {{frontend-justfile}} build

# Dev — chạy local (không Docker) cho hot-reload nhanh
dev:
    @echo "Backend dev:  just --justfile {{backend-justfile}} dev"
    @echo "Frontend dev: just --justfile {{frontend-justfile}} dev"
