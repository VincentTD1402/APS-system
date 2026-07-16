# APS Backend API Spec

Nguồn: tạo từ OpenAPI schema thật của `aps-backend` (2026-07-16, sau khi dọn bỏ scheduler/action/plan-version). Dùng file này làm hợp đồng chung giữa backend (implement) và frontend (mapping) — mọi thay đổi route phải update lại file này.

Base path: **`/api/v1`**. Swagger UI: **`/docs`**. OpenAPI JSON: **`/openapi.json`**.

> **Đã gỡ bỏ khỏi backend** (không còn tồn tại, đừng map FE vào các route này nữa): `/actions/*`, `/plan-versions/*`, `/history/*`, `/schedule/*`, `/llm/plans/*` (plan detail), `/kpi-summary/{scenario_id}/risks` (KPI4 risk-count). Toàn bộ tính năng tạo lịch/scheduler, action execution, plan version history đã bị xóa khỏi backend.

---

## 0. Root / health / metrics

| Method | Path | Response | Ghi chú |
|---|---|---|---|
| GET | `/` | `{message, version, docs}` | Landing check |
| GET | `/health` | `{status}` | Liveness probe, không chạm DB/LLM |
| GET | `/metrics` | in-flight LLM ops + p50/p95 per route | Nội bộ, theo dõi hiệu năng |

---

## 1. G-System sync — `/api/v1/gsystem`

Đồng bộ dữ liệu GSystem → `aps_input.*` (Phase 01 only — không còn build RDF/Neo4j).

### `POST /run`
Khởi chạy sync nền, chỉ 1 sync chạy 1 lúc.

- **202** `{ job_id: string, status: "accepted" }` → FE lưu `job_id`, poll job.
- **409** sync khác đang chạy.

### `GET /jobs/{job_id}`
Poll kết quả. **202** khi đang chạy (`{detail:{job_id, status:"running"}}`), **200** khi xong, **404** không tìm thấy.

**`SyncRunResponse`** (200):

| Field | Kiểu | Ghi chú |
|---|---|---|
| `started_at`, `finished_at` | datetime | |
| `success` | bool | |
| `error` | string\|null | |
| `counts` | `{entity: {synced, skipped}}` | thống kê từng entity (item, workshop, routing, bom, prod_plan, item_process, calendar, stock, customer, routing_item, routing_process, process) |
| `calendar_synced` | int | |
| `neo4j_nodes`, `neo4j_relationships`, `rdf_triples` | int | **luôn = 0** — Phase 02-04 đã tắt, field giữ lại chỉ để không breaking response shape |

---

## 2. LLM — `/api/v1/llm`

### `POST /suggestions`
Sinh gợi ý hành động AI từ context KPI. Cache theo `scenario_id`.

**Request (`SuggestionRequest`):**

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `context_type` | string | ✓ | vd `workcenter`/`kpi`/`risk` |
| `scenario_id` | string\|null | | dùng để cache |
| `workcenter_id` | string\|null | | |
| `affected_items` | string[] | | |
| `kpi_summary` | object | | context tự do FE truyền vào |
| `max_suggestions` | int | | default 3 |

**Response (`SuggestionResponse`):** `{ alerts: AlertItemOut[], context_type, config_used }`
`AlertItemOut`: `{ level: "주의"|"경고"|"🔴"|"🟠", message, context: object, ai_insight, priority: "high"|"medium"|"low" }`

### `GET /health`
`{ status: "healthy"|"degraded", configs: {...} }` — health check LLM backend (no_think/think).

---

## 3. KPI Summary — `/api/v1/kpi-summary`

### `GET /{scenario_id}/delivery` — KPI1 Tỷ lệ giao hàng đúng hạn
Đọc trực tiếp `aps_input.aps_mps_plan` × `aps_input.aps_item` — **không phụ thuộc scenario** (tham số giữ để tương thích interface).

`KPI1DeliveryResponse`: `{ kpi_name, kpi_value(0-100), total_orders, on_time_orders, delayed_orders, risk_triggered, delayed_order_details: DelayedOrderDetail[] }`

### `GET /{scenario_id}/shortage` — KPI2 Thiếu vật tư
`KPI2ShortageResponse`: `{ kpi_name, kpi_value, total_shortage_qty, items_with_shortage, risk_triggered, shortage_items: ShortageItemDetail[] }`

### `GET /{scenario_id}/load` — KPI3 Tải workcenter
`KPI3LoadResponse`: `{ kpi_name, avg_load, max_load, min_load, risk_triggered, entries: WorkcenterLoadEntry[], overloaded_slots: WorkcenterLoadEntry[] }`

### `POST /daily-plan/rebuild`
Tính lại `aps_result.aps_daily_plan` từ `aps_mps_plan` × `aps_item_routing_spec` (backward-fill). Gọi trước khi đọc các endpoint daily-plan bên dưới.
→ `DailyPlanRebuildResponse`: `{ rows_inserted }`

### `GET /daily-plan`
Query: `workcenter_id?`, `start_date?`, `end_date?` (YYYY-MM-DD) → `DailyPlanRow[]`

### `GET /daily-plan/workcenter-status`
Rollup theo (workcenter, ngày) — dùng để tô màu FE (`status`: `overload`/`normal`). Query như trên → `WorkcenterDailyStatus[]`

### `GET /{scenario_id}/workcenter-schedule`
Dữ liệu cho Gantt chart. Query: `start_date?`, `end_date?`, `workcenter_id?` → `WorkcenterLoadEntry[]`

### `GET /{scenario_id}/workcenter-load-db`
`workcenter_load` group theo workcenter. Query như trên → `WorkcenterLoadByWorkcenter[]` (mỗi item có `loads: WorkcenterLoadLineItem[]`)

### `GET /{scenario_id}/plan-impacted-orders`
Query: `plan_id?`, `reason_type?` (R1/R2/R3) → `PlanImpactedOrderRow[]`

### `GET /{scenario_id}/impacted-orders`
Query: `risk_type?` (R1/R2/R3) → `DelayedOrderDetail[]`

---

## 4. Work Order — `/api/v1/workorder`

Không có Pydantic response_model (trả `dict` tự do) — shape thật lấy trực tiếp từ code, liệt kê dưới đây.

### `POST /preview`
Query: `scenario_id` (bắt buộc, 400 nếu thiếu). Body (optional JSON): dùng để lọc workcenter — các key được đọc: `work_centers`, `responsible_work_centers`, `responsible_workcenter_ids`, `workcenter_ids`, `workcenter_id`, `workcenter_no` (chấp nhận string hoặc list).

Build danh sách work order preview từ `PlanOperation` của scenario (chưa gửi GSystem, chỉ xem trước).

**Response 200:**
```json
{ "scenario_id": "...", "count": 12, "items": [ WorkOrderPreviewItem, ... ] }
```

`WorkOrderPreviewItem` (1 work order, field theo đúng format GSystem `pd/workorder/aps/save` cần):

| Field | Kiểu | Nguồn |
|---|---|---|
| `planDate`, `workDate`, `workOrderDate`, `finishDate` | string (date) | `PlanOrder`/`PlanOperation` |
| `planNo` | string | `Demand.plan_no` hoặc `plan_id` |
| `workOrderNo` | string | tự sinh `WO-YYYYMMDD-<n>` |
| `workOrderSerl` | int | `PlanOperation.sequence` hoặc 1 |
| `itemId`, `itemNo`, `itemName`, `specification`, `masterPartNo` | | `Item` |
| `unit` | string | `Stock.unit_cd` mới nhất của item |
| `planQty`, `workQty`, `orderQty` | float | `Demand.plan_qty` |
| `processName`, `procId` | | `RoutingStep` (qua `PlanOperation.routing_step`) |
| `workCenter`, `workcenterId`, `workcenterNo`, `workcenterName`, `responsibleWorkcenterId`, `responsibleWorkcenterNo` | | `WorkCenter` |
| `scenarioId`, `planOpId` | | `PlanOperation` |
| `bizId`, `corpId`, `deptId` | int | default từ `settings.WORKORDER_DEFAULT_*` |
| `progressQty`, `goodQty`, `defectQty`, `dailyOrderQty` | 0 (placeholder, chưa có dữ liệu thực tế) | |
| `dailyOrderYn`, `inventoryManager`, `continuousProcessYn` | bool | mặc định `false` |
| `status` | `"A"` (fixed) | |

### `GET /list`
Query: `scenario_id?` (nếu rỗng → trả `{"items": []}` ngay, không query DB), `plan_no?`, `work_order_no?`, `item_no?` (match `ilike`), `start_date?`, `end_date?` (lọc theo `work_date`).

**Response 200:** `{ "items": [WorkOrderPreviewItem-like, ...] }` — đọc từ bảng `aps_result.work_order` đã lưu (`WorkOrder.payload_json` merge với dữ liệu tính lại từ `PlanOperation`), tối đa 500 dòng, sort theo `work_date, id`.

### `POST /save`
Query: `scenario_id?` (dùng khi body rỗng/không hợp lệ JSON, để tự build payload từ scenario). Body: 1 object hoặc mảng object work order (theo shape `WorkOrderPreviewItem`, bắt buộc có `planDate`, `planNo`, `orderQty`/`qty`).

Forward từng work order tới GSystem `POST /pd/workorder/aps/save`, rồi lưu/upsert vào `aps_result.work_order`.

**Response 200:**
- Nếu gửi 1 work order: trả thẳng JSON response của GSystem cho work order đó.
- Nếu gửi nhiều: `{ "sent_count": n, "results": [{ "request": {...}, "response": {...GSystem response...} }, ...] }`

**400** thiếu field bắt buộc / JSON không hợp lệ. **502** GSystem lỗi (rollback DB).

### `POST /delete`
Body: 1 object, mảng object, hoặc `{"items": [...]}`. Mỗi item cần `workOrderNo` (bắt buộc, 400 nếu thiếu), tùy chọn `workOrderSerl` (default 1), `bizId`/`corpId` (default `settings.WORKORDER_DEFAULT_*`).

Forward `POST /pd/workorder/aps/delete` tới GSystem, xóa khớp trong `aps_result.work_order` theo `(work_order_no, work_order_serl)`, trả thẳng JSON response của GSystem. **502** nếu GSystem lỗi (rollback DB, không xóa local).

---

## 5. Purchase Requests — `/api/v1/purchase-requests`

### `GET /`
Query: `scenario_id?`, `item_id?`, `sync_status?` (`SUCCESS`/`FAILED`/`ERROR`/`SIMULATED`), `limit` (default 100, max 500)
→ `PurchaseRequestRow[]`: `{ id, scenario_id, item_id, shortage_qty, need_date, source_type, status, sync_status, ext_status, ext_id, req_no, corp_id, biz_id, sent_at, created_at }`

FE đọc `sync_status` để hiển thị kết quả action (đã đồng bộ GSystem hay chưa).

---

## Bảng tên (đổi tên 2026-07-16 — FE lưu ý nếu có mapping cứng theo tên bảng)

| Tên cũ | Tên mới |
|---|---|
| `aps_operation` | `aps_routing_step` |
| `aps_item_routing` | `aps_item_routing_spec` |
| `aps_item_process` | `aps_item_process_step` |

Xem `docs/routing-vs-item-process-data-model.md` (trong `aps-backend/docs/`) để hiểu rõ 2 nhóm bảng routing-level vs item-level.

## Unresolved / cần FE xác nhận
- `neo4j_nodes/neo4j_relationships/rdf_triples` trong `SyncRunResponse` luôn 0 — FE nên bỏ hiển thị các field này nếu đang dùng.
