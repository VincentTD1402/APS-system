# DevOps & Workflow Convention

## 1. Docker Compose

**Vị trí**: **duy nhất 1 file** `docker-compose.yml` ở root. Không tạo compose riêng trong `aps-backend/` hay `aps-frontend/`.

**Services**:

| Service | Container | Image | Host port | Internal | Vai trò |
|---|---|---|---|---|---|
| `db` | `aps-db` | `postgres:15-alpine` | `5433` | `5432` | Postgres chính (APS) |
| `neo4j` | `aps-neo4j` | `neo4j:5` | `7474 / 7687` | same | Graph DB (dormant, giữ cho AI platform) |
| `backend` | `aps-backend` | build `./aps-backend` | `8001` | `8000` | FastAPI |
| `frontend` | `aps-frontend` | build `./aps-frontend` | `5173` | `5173` | Vue + Vite dev server |

**Nguyên tắc**:

- Container name **kebab-case** với prefix `aps-`.
- Service name **ngắn** (`db`, `backend`, …) — khớp `docker compose exec <service>` command trong justfile.
- Port host luôn khác internal khi có thể (5433 vs 5432) → tránh đụng với Postgres local dev.
- Env truyền qua `env_file: .env` + explicit `environment:` khi cần override in-container (VD: `APS_DB_URL` phải trỏ `db:5432` không phải `localhost:5433`).
- Volume mount code `./aps-backend:/app` cho hot reload; `/app/node_modules` anonymous volume cho FE để không đè node_modules host lên container.
- Healthcheck cho `db`, `neo4j`, `backend` — dùng `depends_on: condition: service_healthy` cho backend chờ db+neo4j.

**Không**:

- Đặt secrets trong `docker-compose.yml` — luôn qua `${VAR}` interpolation.
- Tạo compose `docker-compose.prod.yml` khi chưa có deploy target thật.
- Chạy `--reload` trong compose (starves worker khi có UI traffic). Hot reload nhờ bind mount + uvicorn reload script chạy dev-only.

## 2. Justfile

**Vị trí**: **duy nhất 1 file** `justfile` ở root. Không nested justfile.

**Cấu trúc**:

```
justfile                          # root — mọi recipe
.just/
├── unix.just                     # recipes [unix] (env, find-port, kill-port, open)
└── windows.just                  # recipes [windows] tương ứng
```

**Nguyên tắc**:

- Recipe **cross-platform** dùng `docker compose ...` hoặc `uv --directory ... / pnpm --dir ...` (không `cd` + `&&`).
- Recipe OS-specific tag `[unix]` hoặc `[windows]` trong `.just/*.just` — `just` tự pick theo `os()`.
- BE/FE recipe chạy trong container: `docker compose exec backend uv run pytest`, `docker compose exec frontend pnpm build`.
- Dep management host-side: `just be-add`, `just fe-add` — dùng `uv --directory aps-backend` / `pnpm --dir aps-frontend`.
- Recipe destructive (`reset`, `bootstrap`) phải có `[confirm(...)]` gate.
- Đặt tên recipe kebab-case: `test-be`, `build-fe`, `kill-port`.

**Xem `just --list`** để nắm toàn bộ recipe.

## 3. Environment variables

**Vị trí**:

- `.env.example` ở root — template, commit vào git.
- `.env` ở root — thật, **gitignore**, mỗi dev tự copy.
- `aps-frontend/.env.example` — chỉ `VITE_API_BASE_URL` cho FE dev outside docker.

**Naming convention**:

| Prefix | Ý nghĩa | Ví dụ |
|---|---|---|
| `APS_*` | APS system config | `APS_DB_URL`, `APS_TIMEZONE`, `APS_NEO4J_URI` |
| `GSYSTEM_*` | G-System integration | `GSYSTEM_DB_URL`, `GSYSTEM_API_KEY` |
| `LLM_LLM_CONFIGS__<KEY>__<FIELD>` | LLM nested (pydantic-settings syntax) | `LLM_LLM_CONFIGS__THINK__MODEL_NAME` |
| `VITE_*` | Frontend build-time (Vite embed) | `VITE_API_BASE_URL` |
| `API_VERSION`, `DEBUG`, `LOG_LEVEL` | Runtime flags | — |

**Nguyên tắc**:

- **Không commit** `.env` — dù chỉ dev.
- Mọi biến trong `.env.example` phải được đọc ở **1 nơi cụ thể** — grep trước khi thêm.
- Không đặt secret vào default `${VAR:-<value>}` trong compose — default chỉ cho non-secret.
- Nested pydantic-settings config: `LLM_LLM_CONFIGS__THINK__*` → BE parse thành `settings.LLM_CONFIGS.think.*`.

## 4. Git

### 4.1 Branch

```text
main                            # branch chính, luôn deployable
feat/<slug>                     # feature mới
fix/<slug>                      # bug fix
chore/<slug>                    # config, docs, build
refactor/<slug>                 # đổi structure không đổi behavior
```

Slug **kebab-case**, ngắn nhưng gợi nhớ: `feat/kpi4-risk-count`, `fix/backward-fill-overflow`.

### 4.2 Commit message

Conventional Commit **bắt buộc**:

```text
feat: add KPI4 total risk count endpoint

- Aggregates KPI1 delayed + KPI2 shortage + KPI3 overloaded WC
- Adds risk-count route under /kpi-summary
```

**Types**: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`, `style`.

**Cấm**:

- Tham chiếu AI/Claude/Copilot/… trong message hoặc body.
- Commit message tiếng Việt (giữ English cho consistency + git tool hiển thị đúng).
- Message chung chung: `update`, `fix bug`, `wip`.
- Amend commit đã push (trừ khi bạn là owner duy nhất branch).

### 4.3 PR

- 1 PR = 1 topic. Tách nếu > ~500 dòng thay đổi non-trivial.
- Title theo conventional commit format.
- Body: what + why + test plan (checklist).
- **Merge policy**: squash + rebase (không merge commit) — giữ history phẳng trên `main`.
- Không force-push lên `main`.

### 4.4 Không skip hooks

`--no-verify`, `--no-gpg-sign` **không dùng** trừ khi debug hook rồi bàn với team. Fail thì fix root cause, không bypass.

## 5. Plans (kế hoạch làm việc)

**Vị trí duy nhất**: `plans/` ở root. Không tạo `aps-backend/plans/` hay `aps-frontend/plans/`.

**Cấu trúc thư mục plan**:

```text
plans/
├── <YYMMDD-HHMM>-<slug>/           # 1 plan = 1 folder
│   ├── plan.md                     # tóm tắt: status, phases, acceptance, dependencies
│   ├── phase-01-<name>.md          # chi tiết từng phase
│   ├── phase-02-<name>.md
│   └── reports/                    # audit, review, verification report
│       └── <type>-<slug>-report.md
├── reports/                        # report không thuộc plan cụ thể
├── templates/                      # template plan.md, phase.md
└── ...
```

**Nguyên tắc**:

- Timestamp `YYMMDD-HHMM` để sắp thứ tự chronological.
- Slug kebab-case ngắn (~4-6 từ).
- `plan.md` chỉ giữ status + link phase — không nhét chi tiết implementation vào đây.
- Report tên **mô tả rõ** (không `review.md`, `notes.md`) — theo pattern `<workflow>-<scope>-report.md`.

## 6. Docs (tài liệu)

**Vị trí duy nhất**: `docs/` ở root.

**Nội dung**:

- `docs/api-spec.md` — API contract (BE↔FE hợp đồng chi tiết).
- `docs/api-usage-mapping.md` — trạng thái FE map API.
- `docs/conventions/` — bộ file này.
- `docs/fe-mock-data-explanation-vi.md` — giải thích mock data cho FE demo.
- `docs/ontology/` — Neo4j + RDF overview (cho AI platform sau).
- `docs/specs/` — spec gốc từ khách hàng (Korean CSV, HTML template).

**Nguyên tắc**:

- File Markdown **kebab-case**, mô tả rõ scope: `api-spec.md`, `fe-mock-data-explanation-vi.md`.
- Suffix ngôn ngữ `-vi.md` / `-ko.md` khi doc chỉ 1 ngôn ngữ (đa số VI cho team, chỉ spec gốc là KO).
- Không tạo doc file ngoài `docs/` hay `plans/` (trừ `README.md` root và của mỗi subproject).
- Cập nhật doc **cùng PR** với code change tương ứng — không hứa "sẽ update sau".

## 7. Workflow chuẩn

Cho mỗi feature/fix:

1. **Understand** — đọc request + spec + code liên quan. Hỏi khi thiếu context.
2. **Plan** (nếu > 1 file / risky) — tạo `plans/<timestamp>-<slug>/`.
3. **Implement** — nhánh riêng, sửa/tạo file theo convention.
4. **Verify** — `just test-be` / `just test-fe` / `just lint` / `just typecheck` cho tầng động chạm.
5. **Doc** — update `docs/api-spec.md` nếu đổi contract; update convention docs nếu đổi convention.
6. **PR** — commit conventional, body theo template, link plan nếu có.

## 8. Destructive commands & confirmation

Không tự động chạy khi chưa được yêu cầu:

- `git reset --hard`, `git push --force`
- `docker compose down -v` (wipe volume)
- `alembic downgrade base`
- `rm -rf`, drop table, truncate

Recipe justfile đã `[confirm(...)]` các lệnh này. Không bypass confirm bằng `just -y ...`.

## 9. Ports & host conflicts

| Service | Port host | Chỉnh trong `.env` bằng |
|---|---|---|
| Postgres | 5433 | `APS_DB_PORT` |
| FastAPI | 8001 | `APS_API_PORT` |
| Frontend | 5173 | `APS_FE_PORT` |
| Neo4j HTTP | 7474 | `APS_NEO4J_HTTP_PORT` |
| Neo4j Bolt | 7687 | `APS_NEO4J_BOLT_PORT` |

Kiểm tra trước khi start: `just find-port 8001`. Kill nếu bị chiếm: `just kill-port 8001`.

## 10. Secrets & privacy

- Không log DB password, API key, LLM token.
- Không commit `.env`, `credentials.json`, `*.pem`, `id_rsa*`.
- Report bug với external system → tự redact URL/key trước khi paste.
- Personal data (nếu có tương lai): tuân thủ APS system compliance — chưa scope MVP.
