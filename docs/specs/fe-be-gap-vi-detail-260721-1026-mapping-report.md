# Báo cáo chi tiết: Gap giữa Frontend và Backend — APS MVP

**Ngày:** 2026-07-21
**Ngữ cảnh:** FE (Vue 3 + TypeScript) đã hoàn thiện khung UI, dùng mock data. BE (FastAPI + SQLAlchemy) mới có ~11 endpoint sống, phần lớn phục vụ KPI dashboard + work-plan list. Cần xác định:
- Business logic nào FE đang gánh mà đáng lẽ phải nằm ở BE
- API nào FE trông đợi mà BE chưa có / chưa đúng shape
- Cần bổ sung / chỉnh sửa gì để FE bỏ mock

Report là source of truth cho quyết định implement. Dư thừa BE (dead tables, `/workorder`, `/llm`) không bàn — user tự xử lý.

---

## 1. Bối cảnh nhanh

### FE stack hiện tại

- `aps-frontend/src/api/mock-server.ts` — giả lập toàn bộ API server, có state trong memory.
- `aps-frontend/src/mocks/master-data.ts` — dữ liệu cứng master (work centers, items, routings, BOM, inventory).
- `aps-frontend/src/mocks/mps-data.ts` — dữ liệu cứng MPS + work orders.
- `aps-frontend/src/mocks/mock-scheduler.ts` — **thuật toán scheduler thực tế** đang chạy client-side.
- `aps-frontend/src/stores/aps-store.ts` — Pinia store, chỉ gọi `mockServer`.
- `aps-frontend/src/types/{aps,enums,master,planning}.ts` — DTO/enum, đây là **contract** FE mong đợi từ BE.
- `aps-frontend/src/views/{aps,masters,mps}/` — 3 nhóm view chính.

Chưa import `axios`/`fetch` nào — chuyển sang gọi BE thật là one-shot: thay `mockServer` bằng service HTTP.

---

## 2. Business logic FE đang gánh (5 khối chính — cần đưa về BE)

### 2.1. Backward-fill scheduling (lập lịch lùi từ ngày giao)
- **Vị trí:** `mocks/mock-scheduler.ts:35-63`
- **Mô tả:** Cho order có `qty`, `end_date`, `work_center`, tính `standard_time × qty` → tổng phút, phân bổ ngược từ `end_date` về hôm nay, tôn trọng capacity. Output `dailyPlans: [{date, qty, minutes}]` cho mỗi WorkPlan.
- **Vì sao BE:** persist, audit, re-run/undo, DRY dùng chung `/aps/run` + `/aps/adjust`.

### 2.2. Material shortage detection
- **Vị trí:** `mock-scheduler.ts:73-101`
- **Mô tả:** Duyệt order theo `delivery_date` tăng dần. Tra BOM → component + qty cần. Trừ khỏi running balance inventory. Flag `shortageQty` + set `riskType = MATERIAL_SHORT` khi thiếu.
- **Vì sao BE:** inventory là shared state — nhiều order tranh cùng stock.

### 2.3. Load cell status classification (5 trạng thái)
- **Vị trí:** `mock-scheduler.ts:103-180`
- **Mô tả:** Tổng hợp `dailyPlans` theo `(workcenter, date)` → `minutesLoaded` vs `minutesCapacity` + material shortage → phân 5 trạng thái: `EMPTY / NORMAL / OVERLOAD / MATERIAL_SHORT / OVERLOAD_AND_MATERIAL_SHORT`.
- **Vì sao BE:** rule engine tập trung, nhiều consumer (dashboard, gantt, alert).

### 2.4. Work plan risk re-evaluation khi adjust
- **Vị trí:** `mock-server.ts:110-222` (`applyPending`)
- **Mô tả:** Khi user đổi `newStart/newEnd`, chạy lại pipeline: backward-fill → load cells → material shortage → cập nhật `riskType` cho plan bị ảnh hưởng (có thể cascade).
- **Vì sao BE:** stateful (audit revert), transactional, cascade.

### 2.5. KPI calculation
- **Vị trí:** `mock-scheduler.ts:225-242`
- **Mô tả:** 4 KPI: on-time rate `%`, số item thiếu, `%` WC vượt tải, total risk = R1+R2+R3.
- **Trạng thái BE:** ✅ **Đã có** — 4 endpoint `/kpi-summary/{delivery,shortage,load,risk-count}`. Đảm bảo `POST /aps/run` rebuild `aps_daily_plan` + `aps_material_shortage` cùng transaction để KPI đọc ra đúng.

---

## 3. Inventory BE hiện tại

### 3.1. Route đang mount (active)

| Method | Path | File:Line | Mục đích |
|---|---|---|---|
| POST | `/api/v1/gsystem/run` | `gsystem_sync.py:110` | Kick off sync G-System → DB |
| GET | `/api/v1/gsystem/jobs/{job_id}` | `gsystem_sync.py:132` | Poll trạng thái sync |
| GET | `/api/v1/kpi-summary/delivery` | `kpi_summary.py:36` | KPI1 — % on-time |
| GET | `/api/v1/kpi-summary/shortage` | `kpi_summary.py:58` | KPI2 — số item thiếu |
| GET | `/api/v1/kpi-summary/load` | `kpi_summary.py:85` | KPI3 — % WC vượt tải |
| GET | `/api/v1/kpi-summary/risk-count` | `kpi_summary.py:112` | KPI4 — R1+R2+R3 |
| POST | `/api/v1/kpi-summary/daily-plan/rebuild` | `kpi_summary.py:134` | Rebuild `aps_daily_plan` + `aps_material_shortage` |
| GET | `/api/v1/kpi-summary/daily-plan` | `kpi_summary.py:160` | List daily plan rows |
| GET | `/api/v1/kpi-summary/daily-plan/workcenter-status` | `kpi_summary.py:216` | Rollup (WC, date) |
| GET | `/api/v1/purchase-requests` | `purchase_requests.py:17` | List PR |
| **GET** | **`/api/v1/work-plan/list`** ⭐ | `work_plan.py:20` | **[NEW branch `feat/workplan-api`]** Hybrid WO+MPS list, filter + pagination + `X-Total-Count` |

### 3.2. Route ẩn (`include_in_schema=False`, dead)

| Method | Path | Ghi chú |
|---|---|---|
| POST | `/api/v1/workorder/{preview,save,delete}` | Raise RuntimeError — bảng dead |
| GET | `/api/v1/workorder/list` | Raise RuntimeError |
| POST | `/api/v1/llm/suggestions` | Đọc bảng dead |
| GET | `/api/v1/llm/health` | Không dùng |

### 3.3. Bảng DB đã có sẵn

- `aps_input.aps_workcenter`, `aps_equipment`, `aps_item`, `aps_bom`, `aps_item_routing_spec`, `aps_stock`, `aps_mps_plan`, `work_order`
- `aps_result.aps_daily_plan`, `aps_material_shortage`, `purchase_request`

Phần lớn endpoint cần chỉ là wrapper đọc bảng có sẵn.

---

## 4. Contract FE mong đợi

### 4.1. Enum (từ `types/enums.ts`)

```ts
RiskType         = 'NORMAL' | 'MATERIAL_SHORT' | 'OVERLOAD' | 'MATERIAL_AND_OVERLOAD'
LoadCellStatus   = 'EMPTY' | 'NORMAL' | 'MATERIAL_SHORT' | 'OVERLOAD' | 'OVERLOAD_AND_MATERIAL_SHORT'
MpsStatus        = 'DRAFT' | 'CONFIRMED' | 'CANCELLED'
WorkOrderStatus  = 'PENDING' | 'DONE'
WorkPlanSourceType = 'FROM_WORK_ORDER' | 'FROM_MPS'
ErpOutboxAction  = 'CREATE_WORK_ORDER' | 'CREATE_PURCHASE_REQUEST'
ErpOutboxStatus  = 'PENDING' | 'PUSHED' | 'FAILED'
```

### 4.2. Endpoint FE trông đợi

**A. Master data (5 endpoint đọc)**

| Method | Path | Response |
|---|---|---|
| GET | `/master/work-centers` | `WorkCenter[]` — `{code, nameKo, defaultRuntimeMin, totalRuntimeMin, equipments}` |
| GET | `/master/items` | `Item[]` — `{code, nameKo, uom}` |
| GET | `/master/routings` | `Routing[]` — `{itemCode, wcCode, stepNo, processNameKo, standardStMin}` |
| GET | `/master/bom` | `BomComponent[]` — `{parentItemCode, childItemCode, qtyPer, scrapRate}` |
| GET | `/master/inventory` | `InventoryRow[]` — `{itemCode, warehouseCode, onHand, asOfDate}` |

**B. Planning (2 endpoint đọc)**

| Method | Path | Response |
|---|---|---|
| GET | `/planning/mps` | `Mps[]` — `{id, orderNo, itemCode, planQty, endDate, workStartDate, workEndDate, status}` |
| GET | `/planning/work-orders` | `WorkOrder[]` — `{id, woNo, mpsId, itemCode, wcCode, planQty, planStartDate, planEndDate, status}` |

**C. APS execution (2 endpoint — trái tim MVP)**

```ts
POST /aps/run           → ApsRunResult
POST /aps/adjust  body: { runId, adjustments: [{planId, newStart, newEnd}] }  → ApsRunResult

ApsRunResult = {
  run: { id, startedAt, finishedAt },
  workPlans: WorkPlan[],
  loadCells: LoadCell[],
  kpi: KpiSnapshot
}
WorkPlan = { id, runId, sourceType, workOrderNo, tmpPlanNo, orderNo,
             itemCode, itemNameKo, wcCode, processNameKo,
             planQty, planStartDate, planEndDate, deliveryDate,
             riskType, shortageQty,
             adjusted, originalStart, originalEnd,
             dailyPlans: [{ date, qty, minutes }] }
LoadCell = { wcCode, cellDate, minutesLoaded, minutesCapacity, status }
KpiSnapshot = { onTimeRatePct, materialShortageCount, overloadWcPct, planningRiskCount }
```

**D. ERP action (3 endpoint)**

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/erp/purchase-requests` | `{planId, qty, note}` | `ErpOutboxRow` |
| POST | `/erp/work-orders` | `{planId}` | `ErpOutboxRow` |
| GET | `/erp/outbox` | — | `ErpOutboxRow[]` |

`ErpOutboxRow = { id, runId, action, payload, status, createdAt, pushedAt, error }`

---

## 4bis. Đánh giá endpoint mới `GET /api/v1/work-plan/list` (branch `feat/workplan-api`)

### Response `WorkPlanRow`

```json
{
  "source_type": "WO | MPS",
  "work_order_no": "string | null",
  "tmp_plan_no": "string | null",
  "order_no": "string | null",
  "item_no": "string | null",
  "item_name": "string | null",
  "workcenter_no": "string | null",
  "workcenter_name": "string | null",
  "proc_name": "string | null",
  "planned_qty": 0.0,
  "plan_start": "YYYY-MM-DD | null",
  "plan_end": "YYYY-MM-DD | null",
  "delivery_date": "YYYY-MM-DD | null",
  "risk_types": ["overload", "material_short"]
}
```

Query params: `workcenter_no`, `item_no`, `risk_type`, `plan_no`, `date_from`, `date_to`, `limit` (1-500), `offset`. Total pre-slice count trong header `X-Total-Count`.

Grain: 1 row / `(work_order, item_routing)`. `WO` khi có confirmed work order, `MPS` khi chỉ có MPS chưa gửi. `risk_types` đọc từ `aps_daily_plan.status` — cần gọi `POST /kpi-summary/daily-plan/rebuild` trước.

### Đối chiếu với FE `WorkPlan`

**Match:** `sourceType`, `workOrderNo`, `tmpPlanNo`, `orderNo`, `itemCode`, `itemNameKo`, `wcCode`, `processNameKo`, `planQty`, `planStartDate/EndDate`, `deliveryDate`, `riskType`.

**Cần map:** `WO/MPS → FROM_WORK_ORDER/FROM_MPS`. `risk_types` list → `RiskType` scalar (`["overload","material_short"] → MATERIAL_AND_OVERLOAD`). Snake_case → camelCase.

**Còn thiếu:** `id` (FE reference cho action), `shortageQty` scalar, `dailyPlans[]` nested. `adjusted/originalStart/originalEnd` defer Tier 3.

### Đánh giá

**✅ Dùng được:** table Work Plan list (thay #7 gap matrix), một phần #6 (rows MPS chưa có WO).

**❌ Chưa đủ:** `POST /aps/run` (thiếu `loadCells[]` + `kpi` + nested `dailyPlans[]`), vẽ Gantt daily, action theo plan (thiếu `id`).

### Đề xuất bổ sung

1. Thêm `id` (synthetic từ `work_order.id + item_routing_id`), `shortage_qty`, `daily_plans[]` vào `WorkPlanRow`.
2. Chuẩn hoá camelCase (`ConfigDict(alias_generator=to_camel, populate_by_name=True)`).
3. Vẫn cần `POST /aps/run` mới trả `ApsRunResult` đầy đủ.

---

## 5. Ma trận gap

| # | FE endpoint | BE hiện tại | Trạng thái | Action |
|---|---|---|---|---|
| 1 | `GET /master/work-centers` | — | ❌ Missing | Add — read `aps_workcenter` + join `aps_equipment` |
| 2 | `GET /master/items` | — | ❌ Missing | Add — read `aps_item` (cần cột mới `uom`) |
| 3 | `GET /master/routings` | — | ❌ Missing | Add — read `aps_item_routing_spec` |
| 4 | `GET /master/bom` | — | ❌ Missing | Add — read `aps_bom` (cần cột mới `scrap_rate`) |
| 5 | `GET /master/inventory` | — | ❌ Missing | Add — read `aps_stock` |
| 6 | `GET /planning/mps` | — | ❌ Missing | Add — read `aps_mps_plan` |
| 7 | `GET /planning/work-orders` | `GET /work-plan/list` (branch `feat/workplan-api`) | ⚠️ Partial | Bổ sung field còn thiếu — xem mục 4bis |
| 8 | `POST /aps/run` | `POST /kpi-summary/daily-plan/rebuild` (sai shape) | ⚠️ Misaligned | Thêm route mới `/aps/run` trả `ApsRunResult` đầy đủ |
| 9 | `POST /aps/adjust` | — | ❌ Missing | Add — port thuật toán từ `mock-scheduler.ts` (Tier 3) |
| 10 | `POST /erp/purchase-requests` | `GET /purchase-requests` (chỉ read) | ⚠️ Thiếu POST | Add POST — insert vào `purchase_request` |
| 11 | `POST /erp/work-orders` | — | ❌ Missing | Add — insert vào `work_order` |
| 12 | `GET /erp/outbox` | — | ❌ Missing | Defer (FE không display) hoặc union query |

### 5.1. Response JSON FE mong đợi (chi tiết)

#### #1. `GET /master/work-centers`

```json
[{
  "code": "WC-001", "nameKo": "가공1라인",
  "defaultRuntimeMin": 480, "totalRuntimeMin": 960,
  "equipments": [
    { "code": "EQ-001", "wcCode": "WC-001", "nameKo": "선반 A", "stRate": 1.0 }
  ]
}]
```

#### #2. `GET /master/items`
```json
[{ "code": "ITEM-001", "nameKo": "완제품 A", "uom": "EA" }]
```

#### #3. `GET /master/routings`
```json
[{ "id": "RT-001", "itemCode": "ITEM-001", "stepNo": 1, "wcCode": "WC-001",
   "processNameKo": "가공", "standardStMin": 12.5 }]
```

#### #4. `GET /master/bom`
```json
[{ "id": "BOM-001", "parentItemCode": "ITEM-001", "childItemCode": "MAT-001",
   "qtyPer": 2.0, "scrapRate": 0.05 }]
```

#### #5. `GET /master/inventory`
```json
[{ "id": "INV-001", "itemCode": "MAT-001", "warehouseCode": "WH-A",
   "onHand": 1000.0, "asOfDate": "2026-07-21" }]
```

#### #6. `GET /planning/mps`
```json
[{ "id": "MPS-001", "orderNo": "SO-2026-0001", "itemCode": "ITEM-001",
   "planQty": 500, "endDate": "2026-08-15",
   "workStartDate": "2026-08-01", "workEndDate": "2026-08-14", "status": "CONFIRMED" }]
```

#### #7. `GET /planning/work-orders` — dùng `WorkPlanRow` từ `/work-plan/list`, bổ sung `id + shortageQty + dailyPlans[]`.

#### #8. `POST /aps/run`
```json
{
  "run": { "id": "RUN-a1b2c3d4",
           "startedAt": "2026-07-21T09:00:00Z",
           "finishedAt": "2026-07-21T09:00:03Z" },
  "workPlans": [{
    "id": "WP-a1b2c3d4", "runId": "RUN-a1b2c3d4",
    "sourceType": "FROM_WORK_ORDER",
    "workOrderNo": "WO-2026-0001", "tmpPlanNo": "TMP-001", "orderNo": "SO-2026-0001",
    "itemCode": "ITEM-001", "itemNameKo": "완제품 A",
    "wcCode": "WC-001", "processNameKo": "가공",
    "planQty": 500,
    "planStartDate": "2026-08-01", "planEndDate": "2026-08-05",
    "deliveryDate": "2026-08-15",
    "riskType": "NORMAL", "shortageQty": 0,
    "adjusted": false, "originalStart": null, "originalEnd": null,
    "dailyPlans": [
      { "date": "2026-08-01", "qty": 100, "minutes": 480 },
      { "date": "2026-08-02", "qty": 100, "minutes": 480 }
    ]
  }],
  "loadCells": [{
    "wcCode": "WC-001", "cellDate": "2026-08-01",
    "minutesLoaded": 480, "minutesCapacity": 960, "status": "NORMAL"
  }],
  "kpi": {
    "onTimeRatePct": 95.5, "materialShortageCount": 2,
    "overloadWcPct": 15.0, "planningRiskCount": 8
  }
}
```

- Cả 3 mảng `workPlans/loadCells` cùng ref về `run.id`.
- Date-only field `YYYY-MM-DD`. Datetime ISO 8601 UTC.
- `originalStart/End` `null` khi `adjusted=false`.

#### #9. `POST /aps/adjust`

Request:
```json
{ "runId": "RUN-a1b2c3d4",
  "adjustments": [{ "planId": "WP-a1b2c3d4", "newStart": "2026-08-02", "newEnd": "2026-08-06" }] }
```

Response: cùng shape `ApsRunResult` (#8). Plan bị đổi có `adjusted=true`, `originalStart/End` giữ giá trị cũ. Trả **toàn bộ** workPlans/loadCells (không delta).

#### #10. `POST /erp/purchase-requests`
Request: `{ "planId": "WP-a1b2c3d4", "qty": 100, "note": "Gấp cho SO-2026-0001" }`

Response:
```json
{ "id": "OUT-a1b2c3d4", "runId": "RUN-a1b2c3d4",
  "action": "CREATE_PURCHASE_REQUEST",
  "payload": { "planId": "WP-a1b2c3d4", "qty": 100, "note": "..." },
  "status": "PENDING",
  "createdAt": "2026-07-21T09:15:00Z", "pushedAt": null, "error": null }
```

#### #11. `POST /erp/work-orders`
Request: `{ "planId": "WP-a1b2c3d4" }`

Response: shape như #10, `action = CREATE_WORK_ORDER`, `payload = { "planId": "..." }`.

#### #12. `GET /erp/outbox`
Mảng `ErpOutboxRow[]` sort giảm dần theo `createdAt`. Union `purchase_request + work_order`.

### 5.2. Convention chung

- **camelCase** field. BE dùng `alias_generator=to_camel`.
- Date-only `YYYY-MM-DD`. Datetime ISO 8601 UTC `YYYY-MM-DDTHH:MM:SSZ`.
- ID trả string. Nullable trả `null`, không omit.
- KHÔNG bọc wrapper `{data, meta}` — FE đọc thẳng array/object.

### 5.3. Đối chiếu BE model vs FE fields — điểm cần đặc biệt lưu ý

Chỉ liệt kê mismatch cần map hoặc thiếu thật:

| Endpoint | FE field | Nguồn BE | Note |
|---|---|---|---|
| #1 wc | `totalRuntimeMin` | derive `std_capa × count(equipment)` | runtime, không cần cột |
| #1 wc | Equipment `stRate` | `efficiency_rate` hoặc `oee_rate` | confirm business |
| #2 item | `uom` | — | **cần thêm cột** `aps_item.uom` |
| #4 bom | `qtyPer` | `qty1` hoặc `qty2` | confirm business |
| #4 bom | `scrapRate` | — | **cần thêm cột** `aps_bom.scrap_rate` |
| #5 stock | `asOfDate` | `stk_ym` (`YYYYMM`) | map append `-01` → `YYYY-MM-DD` |
| #5 stock | `itemCode` | `gsystem_item_id` | nên join `aps_item.item_no` |
| #6 mps | `status` | `status_cd` | map service → `DRAFT/CONFIRMED/CANCELLED` |
| #6 mps | `endDate` | `delivery_date` hay `plan_end_date`? | confirm business |
| #7 wo | `id`, `shortageQty`, `dailyPlans[]` | derive từ `work_order` + `aps_daily_plan` | xem mục 4bis |
| #8 run | `run.id` | UUID ephemeral, không persist | không cần bảng |
| #8 wp | `sourceType`, `workOrderNo`, `tmpPlanNo` | query `work_order` cùng `(mps_plan, item_routing)` | derive runtime |
| #8 wp | `riskType` | agg `daily_plan.status` + `material_shortage_qty` | map service → 4 giá trị enum |
| #8 wp | `planStartDate/EndDate` | `min/max(aps_daily_plan.work_date)` | derive runtime |
| #8 lc | `status` | `daily_plan.status` (4 gt) | map service → 5 gt FE |
| #8 lc | `minutesLoaded` | `sum(planned_qty × item_routing_spec.work_time)` | derive runtime |
| #8 lc | `minutesCapacity` | `std_capa × count(equipment)` | confirm business |
| #10 pr | `status` | `purchase_request.status` (`APPLIED`) | map service → `PENDING/PUSHED/FAILED` |
| #10 pr | `pushedAt` | `sent_at` | rename |

---

## 6. Quyết định đã chốt (2026-07-21)

| # | Quyết định |
|---|---|
| Q1 | **Bỏ `nameVi`** — G-System chỉ có Korean. FE cập nhật type bỏ field. |
| Q2 | **Grain `WorkPlan` = `(mps_plan_id, item_routing_id)`, compute `planStart/End` runtime từ `aps_daily_plan`.** Không đổi grain `work_order`. |
| Q3 | **Không thêm bảng `aps_run` / `aps_erp_outbox`.** `runId` = UUID ephemeral. ERP action reuse `purchase_request` + `work_order`. `GET /erp/outbox` defer. |
| Q4 | **`LoadCellStatus` map ở service layer** — BE `daily_plan.status` giữ nguyên. |
| Q5 | **Nested `dailyPlans[]` assemble runtime ở service** — không đụng schema BE. |

### Grain mapping

| Cấp | BE | FE |
|---|---|---|
| Order | `aps_mps_plan` | `Mps` |
| Plan (derived) | `mps_plan × item_routing_spec` | `WorkPlan`. `id` = synthetic. `planStart/End` = `min/max(daily_plan.work_date)` fallback `mps_plan.plan_start/end_date`. |
| Daily | `aps_daily_plan` | `WorkPlanDaily` (nested trong `dailyPlans[]`) |
| Dispatch | `work_order` | Chỉ derive `sourceType`, `workOrderNo`, `tmpPlanNo` |

### Schema thay đổi cuối cùng

**MVP (bắt buộc) — 2 cột:**

| Cột | Bảng | Loại |
|---|---|---|
| `uom` | `aps_input.aps_item` | `String(20)` nullable |
| `scrap_rate` | `aps_input.aps_bom` | `Numeric(10,4)` nullable, default 0 |

**Tier 3 (chỉ khi làm `/aps/adjust`) — 3 cột audit trên `aps_result.aps_daily_plan`:**

| Cột | Loại |
|---|---|
| `adjusted` | `Boolean` default `false` |
| `original_work_date` | `Date` nullable |
| `original_planned_qty` | `Numeric(14,2)` nullable |

Audit ở `aps_daily_plan` (không `work_order`) vì user adjust ngày daily plan.

### Câu hỏi còn cần confirm business (không blocking schema, decide khi implement)

1. `Equipment.stRate` = `efficiency_rate` hay `oee_rate`?
2. `BomComponent.qtyPer` = `qty1` hay `qty2`?
3. `Mps.status` mapping code G-System → `DRAFT/CONFIRMED/CANCELLED`?
4. `Mps.endDate` = `delivery_date` hay `plan_end_date`?
5. `WorkCenter.totalRuntimeMin` — `std_capa × count(equipment)` hay `sum(equipment.normal_capacity_min)`?
6. `GET /erp/outbox` có làm hay defer?

---

## 7. Lộ trình ngắn hạn

### Tier 1 — Unblock FE bỏ mock master data (~1-2 ngày)

Chỉ đọc bảng có sẵn, effort mỗi endpoint 20-40 dòng.

1-5. `GET /master/{work-centers, items, routings, bom, inventory}` — cần migration 2 cột (`uom`, `scrap_rate`) cho #2 và #4.
6. `GET /planning/mps`
7. Bổ sung `id + shortageQty + dailyPlans[]` vào `GET /work-plan/list` (đã có sẵn — chỉ bổ sung).

FE bỏ `mocks/master-data.ts` + `mps-data.ts` + `mock-scheduler.ts` phần list.

### Tier 2 — APS run + ERP actions (~2-3 ngày)

8. Thêm `POST /aps/run` — trả `ApsRunResult` đầy đủ (assemble workPlans nested + loadCells + kpi từ `daily-plan/rebuild`).
9. `POST /erp/purchase-requests` — insert `purchase_request`.
10. `POST /erp/work-orders` — insert `work_order`.
11. `GET /erp/outbox` — defer hoặc union query.

### Tier 3 — Adjust logic (~2-3 ngày, phức tạp)

12. `POST /aps/adjust` — port thuật toán từ `mock-scheduler.ts`, transactional, cascade risk. Cần 3 cột audit ở `aps_daily_plan`.

FE có thể bỏ hoàn toàn `mock-server.ts` sau Tier 3.

---

## 8. Câu hỏi chưa giải quyết

1. **Multi-user concurrency:** 2 user chạy `/aps/run` cùng lúc — block hay song song? MVP có cần lo?
2. **ERP outbox actual push:** ai/cái gì đẩy `PENDING → PUSHED` sang ERP thật? MVP có scope?
3. **KPI cache invalidation:** sau `/aps/adjust`, có cache không?
4. **Frontend types sync sang BE:** manual hay generate?

---

## 9. Kết luận

- 5 khối business logic FE đang gánh → cần chuyển về BE (scheduling, shortage, load classification, risk re-eval; KPI đã có).
- 12 endpoint FE trông đợi — 7 missing, 1 partial (`/work-plan/list` mới), 2 misaligned/thiếu POST, 2 defer được.
- **Schema đổi tối thiểu:** 2 cột MVP (`uom`, `scrap_rate`) + 3 cột audit Tier 3.
- Còn lại map ở service layer (enum, snake_case → camelCase, ID convert, `stk_ym` format, ...).
- Lộ trình: Tier 1 zero-risk → Tier 2 trọng tâm MVP → Tier 3 phức tạp (defer được nếu timeline căng).
