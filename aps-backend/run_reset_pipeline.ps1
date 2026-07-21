$ErrorActionPreference = "Stop"

Write-Host "==> docker compose down -v"
docker compose down -v

Write-Host "==> docker compose up -d"
docker compose up -d

Write-Host "==> alembic upgrade head (inside aps-backend)"
docker exec -i aps-backend bash -lc "alembic upgrade head"

Write-Host "==> python app/scripts/run_pipeline.py (inside aps_core_api)"
docker exec -i aps-backend bash -lc "python app/scripts/run_pipeline.py"

Write-Host "Done."