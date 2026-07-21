# Backend Convention — FastAPI

## 1. Cấu trúc thư mục

```text
aps-backend/
├── app/
│   ├── main.py                # FastAPI entry, middleware, lifespan
│   ├── api/v1/routes/         # REST endpoints, mỗi file = 1 router group
│   ├── config/                # settings (pydantic-settings) + logger
│   ├── db/                    # SQLAlchemy session, get_db()
│   ├── models/
│   │   ├── input/             # ORM cho aps_input.* (raw sync từ G-System)
│   │   └── output/            # ORM cho aps_result.* (dữ liệu do BE tính)
│   ├── schemas/               # Pydantic request/response, mỗi topic 1 file
│   ├── services/              # Business logic, chia theo domain
│   │   ├── gsystem/           # sync G-System → aps_input
│   │   ├── kpi_summary/       # KPI 1-4 calculator + rollup
│   │   ├── material_shortage/ # BOM × stock shortage
│   │   ├── scheduling/        # backward-fill daily plan
│   │   ├── llm/               # Qwen3 client, concurrency, cache
│   │   ├── neo4j/             # graph importer (dormant)
│   │   └── ontology/          # RDF ABox builder (dormant)
│   ├── scheduler/             # APScheduler cron
│   └── scripts/               # run_pipeline.py, dump, seed, verify
├── migrations/versions/       # Alembic revisions
├── ontology/                  # OWL TBox + SHACL shapes
├── pyproject.toml             # deps (uv-managed), tool config
├── uv.lock
├── alembic.ini
└── Dockerfile
```

**Nguyên tắc**: không tạo `domain/` / `infrastructure/` / `repositories/` — dự án đủ nhỏ, service call SQLAlchemy trực tiếp. Chỉ tách thêm khi 1 service có > 500 dòng và logic clear.

## 2. Naming

| Loại | Style | Ví dụ |
|---|---|---|
| File `.py` | `snake_case` | `kpi_calculator.py`, `daily_plan_builder.py` |
| Class | `PascalCase` | `KPISummaryService`, `SyncResult` |
| Function / method | `snake_case` | `calculate_kpi1_delivery()`, `rebuild_daily_plan()` |
| Variable | `snake_case` | `plan_id`, `workcenter_ids` |
| Constant module-level | `UPPER_SNAKE` | `DEFAULT_SHIFT_MINUTES = 480` |
| ORM class | `PascalCase` + `__tablename__ = "aps_..."` | `class DailyPlan: __tablename__ = "aps_daily_plan"` |
| Pydantic response | `PascalCase` + suffix `Response` / `Row` / `Detail` | `KPI1DeliveryResponse`, `DailyPlanRow`, `ShortageItemDetail` |
| Enum-like string literal | `snake_case` (khớp DB) | `status = "overload" \| "material-shortage" \| "urgent" \| "normal"` |

## 3. Layer & ownership

```text
Route (api/v1/routes/*.py)
  ├── validate query/body qua Pydantic
  ├── dispatch Session (Depends(get_db))
  └── call service → return Pydantic response
        │
        ▼
Service (services/<domain>/*.py)
  ├── business logic
  ├── query SQLAlchemy (không tách Repository)
  └── commit/rollback transaction
        │
        ▼
Model (models/input hoặc models/output)
  └── định nghĩa ORM, không chứa logic
```

Cấm:

- Business logic trong route file — chỉ orchestration.
- Query SQLAlchemy trong Pydantic schema.
- Import ngược: `models/` không được import `services/` hoặc `api/`.

## 4. Route pattern

```python
router = APIRouter()


@router.get(
    "/delivery",
    response_model=KPI1DeliveryResponse,
    summary="KPI 1 – Delivery Compliance Rate",
    description="Ngắn gọn 1-2 câu — mô tả nguồn dữ liệu + risk trigger.",
)
def get_delivery_kpi(db: Session = Depends(get_db)) -> KPI1DeliveryResponse:
    service = KPISummaryService(db, scenario_id="")
    return service.calculate_kpi1_delivery()
```

**Bắt buộc**:

- `response_model=` (không trả `dict` tự do, trừ endpoint ẩn khỏi Swagger).
- `summary=` ngắn, `description=` giải thích nguồn + tác dụng.
- Type hint đầy đủ tham số + return.
- Không `async def` nếu handler không await gì — dùng `def` để chạy trên threadpool.

## 5. Response & Error

**Success** — trả Pydantic model trực tiếp, không bọc envelope:

```python
return DailyPlanRebuildResponse(rows_inserted=42, daily_status=[...])
```

**Error** — dùng `HTTPException`, để FastAPI serialize `{detail: ...}`:

```python
if not job:
    raise HTTPException(status_code=404, detail="Job not found")

if not _try_acquire_sync():
    raise HTTPException(status_code=409, detail="A sync is already running")
```

Không tự bọc `{success: false, message: ...}` — FE parse `detail`.

Async job pattern (long-running):

```python
# POST /run → 202 + {job_id}
# GET /jobs/{id} → 202 nếu running (detail = {job_id, status}), 200 khi xong
```

## 6. Logging

```python
from app.config import get_logger

logger = get_logger(__name__)

logger.info("Sync started job_id=%s", job_id)
logger.warning("Scheduled sync skipped: already running")
logger.exception("Failed to persist sync job %s", job_id)  # trong except block, tự thêm traceback
```

Cấm:

- `print()` để debug.
- `logger.error(str(e))` — dùng `logger.exception(...)` để có stack trace.
- `f"..."` khi logger tự support `%s` interpolation (tránh tính trước khi log level bỏ qua).

## 7. Exception handling

```python
try:
    result = risky_call()
except SpecificError as e:
    logger.exception("Failed doing X for %s", entity_id)
    raise HTTPException(status_code=502, detail=f"External call failed: {e}") from e
finally:
    _release_sync()
```

Cấm:

- `except:` (bare) hoặc `except Exception: pass`.
- Swallow error mà không log.
- Raise `Exception(...)` generic — dùng `HTTPException` hoặc subclass domain-specific.

## 8. Models (SQLAlchemy)

Split rõ:

- `models/input/*.py` — bảng `aps_input.*`, dữ liệu **read-only** từ G-System sync.
- `models/output/*.py` — bảng `aps_result.*`, do BE ghi (daily plan, purchase request, work order, KPI cache…).

Mixin dùng chung ở `models/input/mixins.py` cho `created_at/updated_at` etc.

Ví dụ:

```python
class DailyPlan(Base):
    __tablename__ = "aps_daily_plan"
    __table_args__ = {"schema": "aps_result"}

    id: Mapped[int] = mapped_column(primary_key=True)
    mps_plan_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_mps_plan.id"))
    work_date: Mapped[date]
    planned_qty: Mapped[Decimal]
    status: Mapped[str] = mapped_column(default="normal")
    material_shortage_qty: Mapped[Decimal | None]
```

## 9. Schemas (Pydantic)

- Mỗi topic 1 file (`kpi_summary.py`, `purchase_request.py`, `sync.py`).
- Dùng `Field(..., description="...")` cho **mọi field xuất ra Swagger** — giúp FE đọc.
- Không dùng `Optional[X]` — dùng `X | None` (Python 3.11+).
- `BaseModel` cho response; `default_factory=list` cho list, không `= []`.

```python
class KPI1DeliveryResponse(BaseModel):
    kpi_value: float = Field(..., ge=0.0, le=100.0, description="Compliance rate %")
    delayed_order_details: list[DelayedOrderDetail] = Field(default_factory=list)
```

## 10. Settings & env

- Định nghĩa tất cả biến trong `app/config/config.py` (pydantic-settings).
- Prefix theo domain: `APS_*`, `GSYSTEM_*`, `LLM_*`.
- Nested config qua `__` (double underscore): `LLM_LLM_CONFIGS__THINK__API_URL`.
- Không đọc env qua `os.environ` trực tiếp — luôn qua `settings`.

## 11. Migrations

Xem chi tiết ở [database-postgres.md](database-postgres.md). Tóm tắt:

- `just migration "add_xxx_table"` để autogenerate.
- Tên revision file: **không** chứa plan ID / phase / audit label. Mô tả invariant.
- Không sửa revision đã merge — tạo revision mới để rollback/fix.
- Với destructive change (drop column/table), 2 revision: (1) deprecate + backfill, (2) drop — không merge cả 2 cùng lúc.

## 12. Dependency management

```bash
just be-add fastapi              # thêm runtime dep
just be-add pytest-mock -D       # thêm dev dep (uv add --dev)
just be-remove neo4j             # xóa
```

Không sửa `pyproject.toml` bằng tay — dùng `uv` để lock cập nhật.

## 13. Async / threading

- Route handler mặc định **sync** (`def`), FastAPI chạy trên threadpool → OK cho SQLAlchemy sync.
- Chỉ `async def` khi thực sự có `await` (HTTP client, LLM stream).
- G-System sync chạy trong `BackgroundTasks` + `threading.Event` guard để chỉ 1 job/lúc.

## 14. Cấm liệt kê nhanh

- Business logic trong route.
- SQL raw string ghép chuỗi (dùng `select()` / `text()` với params).
- Trả `dict` thay vì Pydantic model (trừ route đã ẩn khỏi Swagger + có comment lý do).
- Hardcode DB URL / API key / secret.
- Import từ `services/*` sang `models/*` (ngược chiều).
- `time.sleep()` trong route — dùng scheduler.
