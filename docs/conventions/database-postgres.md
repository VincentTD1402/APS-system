# Database Convention — PostgreSQL

## 1. Schema layout

Database `aps_db` có **2 schema chính**:

| Schema | Nội dung | Ghi bởi |
|---|---|---|
| `aps_input.*` | Dữ liệu **raw sync** từ G-System (item, workshop, routing, bom, mps_plan, stock, calendar, customer…). Read-only đối với logic APS. | `services/gsystem/*` |
| `aps_result.*` | Dữ liệu **tính toán** (daily_plan, material_shortage, purchase_request, work_order, workcenter_load, plan_impacted_order, sync_job, LLM cache…) | `services/{kpi_summary,scheduling,material_shortage,gsystem}` |

**Nguyên tắc**:

- Không ghi vào `aps_input` từ logic APS — chỉ sync service.
- Không đọc chéo schema mà không declare rõ ORM (`__table_args__ = {"schema": "..."}`).
- Extension `pg_trgm`, `uuid-ossp` bật ở `db/init.sql`.

## 2. Table naming

```text
aps_input.aps_item
aps_input.aps_workcenter
aps_input.aps_mps_plan
aps_input.aps_item_routing_spec
aps_input.aps_bom
aps_input.aps_stock

aps_result.aps_daily_plan
aps_result.aps_material_shortage
aps_result.purchase_request
aps_result.work_order
```

- **Prefix `aps_`** cho bảng thuộc domain APS (rõ nguồn gốc so với ERP source có sẵn).
- Tên bảng số ít (`aps_item`, không `aps_items`) — khớp convention SQLAlchemy default class → table.
- Bảng result đôi khi không có prefix `aps_` (`purchase_request`, `work_order`) do lịch sử — **không đổi tên**, chỉ apply cho bảng mới.

## 3. Column naming

| Loại | Style | Ví dụ |
|---|---|---|
| Column | `snake_case` | `plan_qty`, `work_date`, `material_shortage_qty` |
| Primary key | `id` (integer/serial) hoặc `<domain>_id` khi cần rõ | `id`, `impacted_id`, `load_id` |
| Foreign key | `<referenced_table_singular>_id` | `workcenter_id`, `mps_plan_id`, `item_routing_id` |
| Composite FK | ghép rõ ràng | `parent_item_id`, `raw_item_id` |
| Boolean | prefix `is_` / `has_` / suffix `_yn` (nếu khớp G-System) | `is_active`, `overloaded`, `daily_order_yn` |
| Timestamp | `_at` suffix | `created_at`, `finished_at`, `sent_at` |
| Date | `_date` suffix | `work_date`, `planned_ship_date`, `delivery_date` |
| Enum-like string | plain snake | `status`, `reason_type`, `sync_status` |
| Quantity | `_qty` suffix | `planned_qty`, `shortage_qty`, `daily_out_qty` |
| Minute/percent | `_minutes`, `_percent` | `used_minutes`, `capacity_minutes`, `load_percent` |

## 4. Audit columns

Mỗi bảng writable nên có (qua mixin `models/input/mixins.py`):

```python
created_at: Mapped[datetime] = mapped_column(default=func.now())
updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

`created_by` / `updated_by` **chưa dùng** ở MVP (không có auth). Thêm khi có auth.

## 5. Enum-like string columns

Dùng string column với check ở service, **không** dùng Postgres ENUM (khó migrate).

Values chuẩn cho các field đã có:

| Column | Values | File tham chiếu |
|---|---|---|
| `aps_daily_plan.status` | `normal`, `overload`, `material-shortage`, `urgent` | `schemas/kpi_summary.py` |
| `plan_impacted_order.reason_type` | tự do, string | `models/output/plan_impacted_order.py` |
| `gsystem_sync_job.status` | `running`, `completed`, `failed` | `models/output/gsystem_sync_job.py` |
| `purchase_request.sync_status` | `SUCCESS`, `FAILED`, `ERROR`, `SIMULATED` | `schemas/purchase_request.py` |

Ghi rõ **values chấp nhận** trong docstring của ORM model và Pydantic schema.

## 6. Alembic migrations

**Vị trí**: `aps-backend/migrations/versions/<hash>_<slug>.py`.

**Tạo mới**:

```bash
just migration "add_material_shortage_qty_to_daily_plan"
```

Command wrap `alembic revision --autogenerate -m "..."` inside container. Tên slug **kebab-case** mô tả **invariant/behavior** — không plan ID, không phase number, không audit finding code.

✅ Good:

- `add_material_shortage_qty_to_daily_plan`
- `align_demand_overlay_with_calendar_key`
- `drop_orphaned_evaluation_material_...`
- `merge_bom_tables_add_qty2`

❌ Bad:

- `phase_04_add_column` (phase reference)
- `fix_p2_bug` (plan reference)
- `apply_review_finding_r3` (audit label)

**Rules**:

- Không sửa revision đã merge — tạo revision mới.
- Migration destructive (drop column/table): tách 2 revision:
  1. Deprecate + backfill nếu cần.
  2. Drop.
  Không merge cả 2 trong cùng PR khi có deploy giữa 2 bước.
- Merge conflict giữa heads → tạo `<hash>_merge_heads.py` (Alembic auto), không sửa file cũ.
- Autogenerate xong **phải review file `.py`** — Alembic đôi khi miss constraint hoặc gen order sai.

**Apply**:

```bash
just migrate            # upgrade head
just downgrade          # revert 1 step
```

## 7. Indexes & constraints

- Index FK column khi query `WHERE fk_id = ?` thường xuyên (Postgres không tự index FK).
- Composite index cho query filter nhiều column: `(workcenter_id, work_date)`.
- Unique constraint đặt tên rõ: `uq_aps_daily_plan__mps_plan__work_date`.
- FK constraint đặt tên: `fk_aps_daily_plan__workcenter_id__aps_workcenter`.

Cấu hình Alembic để dùng naming convention chung — xem `alembic/env.py`.

## 8. Query pattern (trong service)

Prefer `select()` builder + typed result:

```python
from sqlalchemy import select
from app.models import DailyPlan, WorkCenter

stmt = (
    select(DailyPlan, WorkCenter)
    .join(WorkCenter, DailyPlan.workcenter_id == WorkCenter.id)
    .where(DailyPlan.work_date >= start_date)
    .order_by(DailyPlan.work_date)
)
results = db.execute(stmt).all()
```

Cấm:

- SQL string ghép chuỗi: `f"SELECT * FROM aps_daily_plan WHERE id = {user_id}"` → SQL injection.
- `db.execute("SELECT ...")` với concat → dùng `text()` + bind params khi cần raw.
- Query trong route handler — dồn vào service.

## 9. Transaction

Commit ở tầng service hoặc route, tùy scope:

```python
# route
def rebuild_daily_plan_endpoint(db: Session = Depends(get_db)):
    rows = rebuild_daily_plan(db)
    apply_daily_material_shortage(db)
    rebuild_material_shortage(db)
    db.commit()                    # 1 commit cho toàn bộ orchestration
    return {...}
```

Rollback trong `try/except`:

```python
try:
    ...
    db.commit()
except Exception:
    db.rollback()
    logger.exception("Failed to persist X")
    raise
```

`get_db()` dependency đã tự close session ở finally.

## 10. Seed & reset

- Seed pipeline: `just seed` → `python app/scripts/run_pipeline.py --use-mock --reset` (mock G-System). `just seed-real` cho VPN + G-System thật.
- Wipe volume: `just reset` (confirm gate) hoặc `just bootstrap` (wipe + migrate + seed).
- Không viết seed script inline SQL — dùng ORM để đồng bộ với model.

## 11. Timezone

- Postgres set `TZ=Asia/Seoul`, `PGTZ=Asia/Seoul` trong compose.
- Column `TIMESTAMP WITHOUT TIME ZONE` cho `created_at/updated_at` — Postgres tự dùng session TZ.
- Business date (work_date, delivery_date) là `DATE` — không timezone.

## 12. Neo4j (dormant)

- Không query từ APS API — giữ container `aps-neo4j` cho AI/graph platform sau.
- Import pipeline `services/neo4j/graph_importer.py` chạy được nhưng response API luôn trả `neo4j_nodes/relationships/rdf_triples = 0` (phase 02-04 tắt).
- Khi enable lại: mở migrate flow riêng, không đụng schema Postgres.
