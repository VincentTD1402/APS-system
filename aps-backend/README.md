# APS System Backend Core

Advanced Planning and Scheduling System — Core Module

---

## Quick Start (local dev)

Tất cả lệnh chạy **trong container** qua `docker compose exec`. Ở host chỉ cần `docker`, `just`, và file `.env`.

### 1. Prerequisites

- Docker Desktop (compose v2)
- [`just`](https://github.com/casey/just) — `brew install just` (macOS) hoặc `scoop install just` (Windows)
- VPN / network truy cập được G-System DB (host `192.168.205.231:5432`)

### 2. Setup env

```bash
cp .env.example .env
# Mở .env và điền: GSYSTEM_DB_USER, GSYSTEM_DB_PASSWORD (hỏi team lead)
```

### 3. Start services

```bash
just up-build              # lần đầu (build image)
# hoặc just up            # những lần sau
just ps                    # cả 3 container phải Healthy
```

3 services lên:
- `aps_core_api` — FastAPI (port **8001** ngoài → 8000 trong container)
- `aps_core_db` — PostgreSQL 15 (port **5433**)
- `aps_neo4j` — Neo4j 5 (port **7474** HTTP, **7687** Bolt)

### 4. Migrate DB

```bash
just migrate
```

Tương đương: `docker compose exec api alembic upgrade head`.
(`alembic.ini` hard-code host `db` — chỉ resolve được trong docker network nên **phải** chạy trong container.)

### 5. Seed data (G-System pipeline)

```bash
just seed
```

Tương đương: `docker compose exec api python app/scripts/run_pipeline.py`.

Pipeline gồm 4 phase:
1. **Sync G-System** → APS Postgres (9 entities)
2. **Build RDF ABox**
3. **Validate** OWL-RL + SHACL
4. **Import Neo4j** (~886 nodes / 1879 relationships)

Mất ~1–2 phút. Kết thúc log `── Pipeline complete ──` là OK.

#### Reseed bằng mock data (không cần G-System)

```bash
docker compose exec api python app/scripts/run_pipeline.py --use-mock --reset
```

### 6. Verify

| Endpoint | URL |
|---|---|
| Root | http://localhost:8001/ |
| Health | http://localhost:8001/health |
| Swagger UI | http://localhost:8001/docs |
| OpenAPI JSON | http://localhost:8001/openapi.json |
| Neo4j Browser | http://localhost:7474 (`neo4j` / xem `.env`) |

---

## Common chores

```bash
just logs                           # tail API log (default service=api)
just logs db                        # log của Postgres
just restart                        # restart api sau khi đổi code (có volume mount)
just down                           # stop services (giữ data)
just down-v                         # stop + xoá volume (mất DB — có confirm)
just sh                             # bash trong container api
just ps                             # status

just db-reset                       # soft reset: migrate + seed (giữ data cũ)
just db-wipe                        # FULL reset: wipe volumes → up → migrate → seed
just migration "add_xxx_table"      # tạo Alembic revision mới
just backup                         # dump Postgres + Neo4j
just check-format                   # black + flake8 + mypy
```

Xem hết recipes: `just` hoặc `just --list`.

---

## Service Details

### PostgreSQL (APS)
- Image: `postgres:15-alpine`
- Port host: **5433** (tránh đụng port 5432 của backend-ontology nếu có)
- Credentials xem `.env` (`APS_DB_URL`)
- Container name: `aps_core_db`

### Neo4j
- Image: `neo4j:5`
- HTTP: **7474** · Bolt: **7687**
- Credentials xem `.env` (`APS_NEO4J_*`)
- Container name: `aps_neo4j`

### G-System (external — không host)
- Host: `192.168.205.231:5432`
- Read-only source, cần VPN
- Config: `GSYSTEM_DB_*` trong `.env`

---

## App Structure

```
.
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── Justfile                 # task runner
├── alembic.ini              # uses docker service `db` → chạy trong container
├── migrations/              # Alembic revisions
├── app/
│   ├── main.py              # FastAPI entry
│   ├── api/v1/routes/       # REST endpoints
│   ├── config/              # Settings
│   ├── db/                  # SQLAlchemy session
│   ├── models/              # ORM models
│   ├── schemas/             # Pydantic
│   ├── services/            # Business logic (gsystem, ontology, neo4j, llm)
│   └── scripts/
│       ├── run_pipeline.py  # ← entry point seed (G-System hoặc --use-mock)
│       ├── dump_databases.py
│       └── ...
├── ontology/                # TBox (OWL) + SHACL shapes
├── new-frontend/            # Vue 3 dashboard (đang rebuild)
└── old-frontend/            # React dashboard (legacy)
```

---

## Troubleshooting

| Triệu chứng | Nguyên nhân | Fix |
|---|---|---|
| `could not translate host name "db"` khi chạy alembic | Chạy alembic từ host (không trong container) | Dùng `just migrate` (đã wrap docker exec) |
| `just seed` báo connection refused tới `192.168.205.231` | Không có VPN / G-System unreachable | Bật VPN hoặc dùng `--use-mock --reset` |
| Container `api` không healthy | Postgres chưa sẵn sàng | `docker compose restart api` sau khi `db` healthy |
| Port 5433 / 8001 / 7474 đã chiếm | Process khác đang dùng | `just kill-port 8001` (hoặc đổi mapping trong `docker-compose.yml`) |
| Neo4j báo lỗi auth | Sai password trong `.env` | Sync `APS_NEO4J_PASSWORD` với `NEO4J_AUTH` ở `docker-compose.yml` |

---

## Roadmap & Docs

- Roadmap: `docs/project-roadmap.md`
- System architecture: `docs/system-architecture.md`
- Pipeline overview: `docs/aps-pipeline-overview.md`
- API field reference: `docs/aps-gsystem-api-field-reference.md`
- LLM service: `docs/aps-llm-services-reference.md`
- Scheduling engine: `docs/aps-scheduling-engine-reference.md`
- Frontend rebuild plan: `plans/260509-1648-new-frontend-rebuild/plan.md`
