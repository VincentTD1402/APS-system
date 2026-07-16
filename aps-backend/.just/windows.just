# platform/windows.just

# Create venv
[windows]
venv:
    uv venv

# Install dependencies
[windows]
install:
    uv sync

# Copy file .env from .env.example
[windows]
env:
    Copy-Item .env.example .env

# Create database (PostgreSQL)
[windows]
db-create name="app_db" user="postgres":
    createdb -U {{user}} {{name}}

# Drop database (PostgreSQL)
[windows]
[confirm("Drop database '{{name}}'? This cannot be undone! [y/N]")]
db-drop name="app_db" user="postgres":
    dropdb -U {{user}} {{name}}

# Run migrations (inside api container — alembic.ini uses docker service name `db`)
[windows]
migrate:
    docker compose exec api alembic upgrade head

# Create new migration (inside api container)
[windows]
migration name:
    docker compose exec api alembic revision --autogenerate -m "{{name}}"

# Seed data via G-System pipeline (sync → RDF → validate → Neo4j import)
[windows]
seed:
    docker compose exec api python app/scripts/run_pipeline.py

# Run server development
[windows]
run-dev port="8000":
    {{uvicorn}} app.main:app --reload --host 0.0.0.0 --port {{port}}

# Run server production
[windows]
run-prod port="8000":
    {{uvicorn}} app.main:app --host 0.0.0.0 --port {{port}}

# Format code
[windows]
fmt:
    {{black}} app

# Lint code
[windows]
lint:
    {{flake8}} app

# Type check code
[windows]
typecheck:
    {{mypy}} app

# Add dependencies into Huy dev
[windows]
add-huy *deps:
    uv add {{deps}} --group huy-dev
