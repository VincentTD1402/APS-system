# APS Backend API Spec

Nguồn: cập nhật thủ công theo thay đổi thực tế trong `aps-backend` (2026-07-20). Dùng file này làm hợp đồng chung giữa backend (implement) và frontend (mapping) — mọi thay đổi route phải update lại file này.

Base path: **`/api/v1`**. Swagger UI: **`/docs`**. OpenAPI JSON: **`/openapi.json`**.

> **Đã gỡ bỏ khỏi backend** (không còn tồn tại trong code, đừng map FE vào các route này): `/actions/*`, `/plan-versions/*`, `/history/*`, `/schedule/*`, `/llm/plans/*` (plan detail), `/kpi-summary/{scenario_id}/risks` (KPI4 cũ, đã thay bằng `/kpi-summary/risk-count` mới — xem mục 3.4), `/kpi-summary/{scenario_id}/workcenter-schedule`, `/kpi-summary/{scenario_id}/workcenter-load-db`, `/kpi-summary/{scenario_id}/plan-impacted-orders`, `/kpi-summary/{scenario_id}/impacted-orders`, `/kpi-summary/daily-plan/material-shortage-summary`, `/kpi-summary/daily-plan/load-average`.
>
> **Ẩn khỏi Swagger** (`include_in_schema=False` — route vẫn hoạt động, chỉ không hiện trong `/docs`): toàn bộ `/llm/*`, toàn bộ `/workorder/*`.
>
> **Router tắt hẳn** (không mount, code giữ nguyên): `/material-shortage/*` (module 6) — dư thừa vì `POST /kpi-summary/daily-plan/rebuild` đã gọi `rebuild_material_shortage()` bên trong.

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

## 2. LLM — `/api/v1/llm` (ẩn khỏi Swagger)

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

**Không còn theo `scenario_id`** (bỏ path param ở tất cả KPI1-4, 2026-07-20) — mỗi KPI đọc 1 snapshot dữ liệu duy nhất (không phân theo scenario). Gọi thẳng không cần tham số nào.

### 3.1 `GET /delivery` — KPI1 Tỷ lệ giao hàng đúng hạn
Đọc trực tiếp `aps_input.aps_mps_plan` × `aps_input.aps_item`.

`KPI1DeliveryResponse`: `{ kpi_name, kpi_value(0-100, %), total_orders, on_time_orders, delayed_orders, risk_triggered, delayed_order_details: DelayedOrderDetail[] }`

### 3.2 `GET /shortage` — KPI2 Thiếu vật tư
Đọc `aps_result.aps_material_shortage` (BOM `aps_bom` × tồn kho `aps_stock`, xem `POST /daily-plan/rebuild` bên dưới để refresh). `kpi_value` = **số lượng item bị thiếu** (`items_with_shortage`), không phải tổng số lượng thiếu.

`KPI2ShortageResponse`: `{ kpi_name, kpi_value(=items_with_shortage), total_shortage_qty, items_with_shortage, risk_triggered, shortage_items: ShortageItemDetail[] }`
`ShortageItemDetail`: `{ item_id, item_no, item_name, required_qty, available_qty, shortage_qty, shortage_percent }`

### 3.3 `GET /load` — KPI3 Tỷ lệ workcenter vượt tải
Đọc rollup của `aps_result.aps_daily_plan` (cùng nguồn `GET /daily-plan/workcenter-status`). `kpi_value` = **% số workcenter có ≥1 ngày vượt tải** trong toàn bộ lịch đã rebuild (`overloaded_wc_count / total_wc_count × 100`), khớp card FE "공정부하율 초과" kiểu "5%WC" — không phải avg/max/min load theo slot.

`KPI3LoadResponse`: `{ kpi_name, kpi_value(%WC), overloaded_wc_count, total_wc_count, avg_load, max_load, min_load, risk_triggered, entries: WorkcenterLoadEntry[], overloaded_slots: WorkcenterLoadEntry[] }`
`WorkcenterLoadEntry`: `{ workcenter_id, workcenter_code, workcenter_name, plan_date, total_load_minutes, capacity_minutes, load_percent, operation_count(luôn=0), overloaded }`

### 3.4 `GET /risk-count` — KPI4 Tổng số rủi ro (mới 2026-07-20)
`kpi_value` = `KPI1.delayed_orders + KPI2.items_with_shortage + KPI3.overloaded_wc_count` — gọi lại KPI1/2/3 nội bộ, không query thêm. Khớp card FE "계획 수립 예상 리스크" kiểu "20건".

`KPI4RiskCountResponse`: `{ kpi_name, kpi_value, r1_delayed_orders, r2_shortage_items, r3_overloaded_wc, risk_triggered }`

### `POST /daily-plan/rebuild`
Tính lại **2 bảng cùng lúc**:
1. `aps_result.aps_daily_plan` từ `aps_mps_plan` × `aps_item_routing_spec` (backward-fill) + backward material-shortage pass (`apply_daily_material_shortage`) — nguồn cho KPI3.
2. `aps_result.aps_material_shortage` từ `aps_bom` × `aps_stock` (`rebuild_material_shortage`) — nguồn cho KPI2.

Phải gọi API này trước khi đọc KPI2/KPI3/KPI4 để có dữ liệu mới.

`DailyPlanRebuildResponse`: `{ rows_inserted, daily_status: WorkcenterDailyStatus[] }` — `daily_status` cùng shape với `GET /daily-plan/workcenter-status`, phản ánh đúng các dòng vừa rebuild.

`WorkcenterDailyStatus`: `{ work_date, workcenter_id, workcenter_no, workcenter_name, planned_qty_total, daily_out_qty, used_minutes, capacity_minutes, load_percent, material_shortage_qty, status, statuses }`

### `GET /daily-plan`
Query: `workcenter_id?`, `start_date?`, `end_date?` (YYYY-MM-DD) → `DailyPlanRow[]`. `status` mỗi dòng đọc trực tiếp từ cột đã lưu `aps_daily_plan.status` (không tính lại).

### `GET /daily-plan/workcenter-status`
Rollup theo (workcenter, ngày) — dùng để tô màu FE (`status`: `normal`/`overload`/`material-shortage`/`urgent`). Query như trên → `WorkcenterDailyStatus[]`.

---

## 4. Work Order — `/api/v1/workorder` (ẩn khỏi Swagger)

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

## 6. Work Plan — `/api/v1/work-plan`

### `GET /list`
Danh sách kế hoạch sản xuất (작업계획 리스트) — **1 dòng / mỗi dòng `aps_input.aps_mps_plan`** (tất cả, không lọc status). `aps_result.work_order` chỉ dùng để tra cứu.

**Định danh dòng** (đúng 1 trong 2, cùng mang giá trị `plan_no`): nếu `mps.plan_no` có trong `work_order` → `work_order_no = plan_no`, `tmp_plan_no=null`, `source_type="WO"`; ngược lại `tmp_plan_no = plan_no`, `work_order_no=null`, `source_type="MPS"`.

Derive các cột (thiếu data → `null`, không fallback):
- `order_no` = `mps.po_no` (오더=PO NO).
- `item_no`/`item_name` = `aps_item` qua `mps.item_id`.
- `workcenter_no`/`_name` = `aps_item_routing_spec` (`item_id`+`routing_id`, có `workcenter_id`) → `aps_workcenter`.
- `proc_name` = `aps_item_process_step`(`item_id`,`routing_id`)→`proc_sno`, rồi `aps_item_routing_spec`(`item_id`,`routing_id`,`proc_sno`)→`proc_name`.
- `plan_start`/`plan_end`/`delivery_date` = `mps.plan_start_date`/`plan_end_date`/`delivery_date` (thô).

Query (optional): `workcenter_no?`, `item_no?`, `risk_type?` (vd `overload`), `plan_no?` (khớp `tmp_plan_no`/`work_order_no`/`order_no`), `date_from?`/`date_to?` (`YYYY-MM-DD`, lọc theo `plan_end`/`plan_start`).
→ `WorkPlanRow[]`: `{ source_type ("WO"|"MPS"), work_order_no, tmp_plan_no, order_no, item_no, item_name, workcenter_no, workcenter_name, proc_name, planned_qty, plan_start, plan_end, delivery_date, risk_types[] }`

Ghi chú: `risk_types` là tổ hợp con của `{"overload","material_short"}` (rỗng → `["normal"]`). `overload` = có ≥1 dòng `aps_daily_plan.status='overload'` cho `mps_plan_id` đó (gọi `POST /kpi-summary/daily-plan/rebuild` trước). `material_short` (자재부족, bản rút gọn) = có ≥1 component trong BOM (1 cấp) mà `plan_qty × (bom.qty1/qty2) > Σ able_qty` (tồn tháng mới nhất, join `aps_stock.item_id = aps_item.gsystem_id`) — công thức đầy đủ theo ngày chờ data 미입고/입고예정. Data hiện tại: `workcenter`/`proc_name` phần lớn `null` vì `aps_item_process_step.routing_id` và `aps_item_routing_spec.routing_id` chưa được nạp (data gap nguồn, không phải lỗi).

---

## 7. Material Shortage — `/api/v1/material-shortage` (router tắt, không mount)

Code giữ nguyên trong `material_shortage.py`, nhưng không đăng ký vào `api_router` — 2 hàm dùng trực tiếp (không qua HTTP) bởi `POST /kpi-summary/daily-plan/rebuild`:

- `rebuild_material_shortage(session)` — wipe + rebuild `aps_result.aps_material_shortage` từ `aps_bom` × `aps_stock` (required = `plan_qty × qty1/qty2`, available = `Σ aps_stock.in_qty`, shortage = `max(0, required − available)`). Chỉ raw material (`asset_type == "RawMaterial"`), BOM 1 cấp.
- `apply_daily_material_shortage(session)` — set `aps_daily_plan.material_shortage_qty` theo backward stock balance, chạy sau `rebuild_daily_plan`.

Nếu cần gọi độc lập qua HTTP (không qua daily-plan/rebuild), uncomment `api_router.include_router(material_shortage.router, ...)` trong `routes/__init__.py`.

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
- KPI2/KPI3/KPI4 phụ thuộc dữ liệu đã rebuild qua `POST /daily-plan/rebuild` — nếu chưa gọi trước, các API này trả 0/rỗng. Có cần backend tự động rebuild khi dữ liệu cũ/rỗng thay vì bắt FE gọi thủ công không?
