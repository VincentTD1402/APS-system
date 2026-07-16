# platform/unix.just

# Create venv
[unix]
venv:
    uv venv

# Install dependencies 
[unix]
install:
    uv sync

# Add dependencies
[unix]
add *deps:
    uv add {{deps}}
    uv lock

# Add dev dependencies
[unix]
add-dev *deps:
    uv add --dev {{deps}}
    uv lock

# Remove dependencies
[unix]
remove *deps:
    uv remove {{deps}}
    uv lock

# Copy file .env from .env.example
[unix]
env:
    cp .env.example .env

# Run python file
[unix]
run file *flags:
    {{python}} {{file}} {{flags}}

# Create database (PostgreSQL)
[unix]
db-create name="app_db":
    createdb {{name}}

# Drop database (PostgreSQL)
[unix]
[confirm("Drop database '{{name}}'? This cannot be undone! [y/N]")]
db-drop name="app_db":
    dropdb {{name}}

# Run migrations (inside api container — alembic.ini uses docker service name `db`)
[unix]
migrate:
    docker compose exec api alembic upgrade head

# Create new migration (inside api container)
[unix]
migration name:
    docker compose exec api alembic revision --autogenerate -m "{{name}}"

# Seed data via G-System pipeline (sync → RDF → validate → Neo4j import)
[unix]
seed:
    docker compose exec api python app/scripts/run_pipeline.py

# Run server development
[unix]
run-dev port="8000":
    {{uvicorn}} app.main:app --reload --host 0.0.0.0 --port {{port}}

# Run server production
[unix]
run-prod port="8000":
    {{uvicorn}} app.main:app --host 0.0.0.0 --port {{port}}

# Find port
[unix]
find-port port="8000":
    lsof -i tcp:{{port}}

# Kill port (show processes first, then confirm)
[unix]
kill-port port="8000":
    #!/usr/bin/env bash
    echo "Processes on port {{port}}:"
    lsof -i tcp:{{port}} || { echo "No process found on port {{port}}"; exit 0; }
    echo ""
    read -p "Kill these processes? [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        kill $(lsof -t -i tcp:{{port}})
        echo "Killed."
    else
        echo "Cancelled."
    fi

# Format code
[unix]
fmt:
    {{black}} app

# Lint code
[unix]
lint:
    {{flake8}} app

# Type check code
[unix]
typecheck:
    {{mypy}} app

# Check port
[unix]
check-port port:
    lsof -i tcp:{{port}}

# Dump PostgreSQL + Neo4j databases (also cleans files older than 60 days)
[unix]
backup:
    {{python}} app/scripts/dump_databases.py --clean

# Delete backup files older than 60 days
[unix]
backup-clean:
    {{python}} app/scripts/dump_databases.py --clean-only
