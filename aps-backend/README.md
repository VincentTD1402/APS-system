# APS System Backend Core

Advanced Planning and Scheduling System — Core Module (FastAPI).

Toàn bộ orchestration (docker compose, migrate, seed, lint, test…) chạy qua **root Justfile** — file này chỉ mô tả riêng backend.

Xem `../justfile` (root) và `../docs/` cho quick start + API contract.

---

## Bố cục thư mục

```
aps-backend/
├── .env.example          # tham chiếu, .env thật ở root
├── Dockerfile            # image runtime (python 3.11-slim + uv)
├── alembic.ini           # hard-code host `db` — chỉ resolve trong docker network
├── pyproject.toml        # deps quản lý bằng uv
├── uv.lock
├── migrations/           # Alembic revisions
├── ontology/             # OWL TBox + SHACL shapes (dành cho AI/graph pipeline sau)
└── app/
    ├── main.py           # FastAPI entry
    ├── api/v1/routes/    # REST endpoints (chi tiết: ../docs/api-spec.md)
    ├── config/           # pydantic-settings (đọc env APS_* / GSYSTEM_* / LLM_*)
    ├── db/               # SQLAlchemy session
    ├── models/           # ORM models (input/ vs output/)
    ├── schemas/          # Pydantic response schemas
    ├── services/         # gsystem / kpi_summary / material_shortage / scheduling / llm / neo4j / ontology
    ├── scheduler/        # APScheduler cron cho G-System sync
    └── scripts/
        ├── run_pipeline.py         # entry point seed (G-System hoặc --use-mock)
        ├── dump_databases.py
        └── ...
```

---

## Quick start (từ project root)

```bash
cd ..                             # về project root
cp .env.example .env              # điền GSYSTEM_DB_USER/PASSWORD khi cần dữ liệu thật
just up -d                        # start 4 container: db, neo4j, backend, frontend
just migrate                      # alembic upgrade head
just seed                         # mock G-System pipeline (thêm --use-mock trong recipe)
just ps                           # cả 4 container Healthy
```

Verify:

| Endpoint | URL |
|---|---|
| Root | http://localhost:8001/ |
| Health | http://localhost:8001/health |
| Swagger UI | http://localhost:8001/docs |
| OpenAPI JSON | http://localhost:8001/openapi.json |
| Neo4j Browser | http://localhost:7474 |

Recipe khác: `just --list` ở root.

---

## Env vars backend đọc

Full list trong `../.env.example`. Nhóm chính:

- `APS_DB_URL`, `APS_DB_USER/PASSWORD/NAME` — Postgres (in-container hostname `db`)
- `APS_NEO4J_URI`, `APS_NEO4J_USER/PASSWORD/DATABASE` — Neo4j (giữ cho AI/graph platform, APS không query)
- `GSYSTEM_DB_URL`, `GSYSTEM_DB_USER/PASSWORD` — external ERP source DB (VPN required)
- `GSYSTEM_BASE_URL`, `GSYSTEM_API_KEY` — G-System REST API
- `GSYSTEM_SYNC_CRON_ENABLED`, `GSYSTEM_SYNC_CRON`, `GSYSTEM_SYNC_CRON_TIMEZONE` — APScheduler
- `LLM_LLM_CONFIGS__THINK__*`, `..._NO_THINK__*` — Qwen3-8B via OpenAI-compatible API
- `API_VERSION`, `DEBUG`, `LOG_LEVEL`, `APS_CALENDAR_TIMEZONE`

Env code path: `app/config/config.py` (pydantic-settings).

---

## Pipeline seed

`app/scripts/run_pipeline.py` gồm 4 phase:

1. **Sync G-System** → `aps_input.*` (9 entities)
2. **Build RDF ABox** (ontology)
3. **Validate** OWL-RL + SHACL
4. **Import Neo4j** (~886 nodes / 1879 relationships)

Recipe:

- `just seed` → `run_pipeline.py --use-mock --reset` (không cần VPN)
- `just seed-real` → `run_pipeline.py` (yêu cầu VPN + `GSYSTEM_DB_*`)

Phase 02-04 hiện chưa được API dùng (API-spec: `neo4j_nodes/relationships/rdf_triples` luôn = 0). Neo4j giữ nguyên cho platform AI về sau.

---

## Troubleshooting

| Triệu chứng | Nguyên nhân | Fix |
|---|---|---|
| `could not translate host name "db"` khi chạy alembic từ host | alembic.ini hard-code hostname `db` | Dùng `just migrate` (đã wrap `docker compose exec backend`) |
| `just seed` báo connection refused tới G-System | Không có VPN | Dùng `just seed` mặc định (mock), hoặc bật VPN + `just seed-real` |
| Container `backend` không healthy | Postgres chưa sẵn sàng | `just restart backend` sau khi `db` healthy |
| Port 5433/8001/7474/5173 đã bị chiếm | Process khác | `just kill-port 8001` hoặc đổi `.env` (`APS_API_PORT` etc.) |
| Neo4j báo lỗi auth | Sai password | Sync `APS_NEO4J_PASSWORD` với `NEO4J_AUTH` trong compose (cả 2 đọc từ `.env`) |

---

## Docs & Contracts

Tất cả docs/plans nằm ở **root** — không có `aps-backend/docs/` hay `aps-backend/plans/`.

- API spec (BE ↔ FE contract): `../docs/api-spec.md`
- API usage mapping (FE integration status): `../docs/api-usage-mapping.md`
- FE mock data explanation: `../docs/fe-mock-data-explanation-vi.md`
- Code conventions: `../docs/convention-code.md`
- Ontology / Neo4j overview: `../docs/ontology/`
- Original specs (Korean): `../docs/specs/`
- Plans: `../plans/`
