set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set dotenv-load

compose := "docker compose"

# Default: list recipes
default:
    @echo 'OS: {{os()}}'
    @just --list

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

# Open shell in a service. Usage: just sh backend | just sh frontend | just sh db
sh service:
    {{compose}} exec {{service}} bash

# Psql into db (override: `just psql aps aps`)
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
    just --justfile backend/Justfile migrate

# Create new migration. Usage: just migration "add_xxx_table"
migration name:
    just --justfile backend/Justfile migration "{{name}}"

# Roll back one migration step
downgrade:
    just --justfile backend/Justfile downgrade

# Seed reference data
seed:
    just --justfile backend/Justfile seed

# Lint backend + frontend
lint:
    just --justfile backend/Justfile lint
    just --justfile frontend/Justfile lint

# Type check backend + frontend
typecheck:
    just --justfile backend/Justfile typecheck
    just --justfile frontend/Justfile typecheck

# Run tests backend + frontend
test:
    just --justfile backend/Justfile test
    just --justfile frontend/Justfile test

# Format backend + frontend
fmt:
    just --justfile backend/Justfile fmt
    just --justfile frontend/Justfile fmt

# Full local CI: lint + typecheck + test + FE build
ci: lint typecheck test
    just --justfile frontend/Justfile build

# Dev (informational — run inside subproject for local hot-reload without Docker)
dev:
    @echo "Backend dev:  just --justfile backend/Justfile dev"
    @echo "Frontend dev: just --justfile frontend/Justfile dev"
