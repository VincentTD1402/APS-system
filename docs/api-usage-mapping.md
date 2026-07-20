# API Usage Mapping — BE ↔ FE

Mục đích: cho FE biết API nào backend đã có sẵn, API nào FE đã gọi, API nào chưa gọi — dùng khi chuyển FE từ mock data (`aps-frontend/src/api/mock-server.ts`) sang gọi API thật.

Base path BE: `/api/v1`. Chi tiết request/response từng route xem `docs/api-spec.md`.

## Tình trạng hiện tại (2026-07-20)

**FE chưa gọi bất kỳ API backend nào.** `aps-frontend/src` không có `fetch(`/`axios` nào trỏ tới `aps-backend`; toàn bộ nghiệp vụ (RUN APS, KPI, purchase request, work order...) được tính/giả lập tại client qua:
- `aps-frontend/src/api/mock-server.ts`
- `aps-frontend/src/mocks/master-data.ts`, `mps-data.ts`, `mock-scheduler.ts`
- `aps-frontend/src/stores/aps-store.ts` (chỉ import `mockServer`)

Package `axios` có trong `package.json` nhưng chưa import ở đâu.

=> Toàn bộ bảng dưới đây là **danh sách API sẵn sàng để FE bắt đầu map**, không phải "API dư thừa".

## Danh sách API backend

### 0. Root / Health

| Method | Path | File | Trạng thái FE |
|---|---|---|---|
| GET | `/` | `aps-backend/app/main.py:69` | Chưa dùng |
| GET | `/health` | `aps-backend/app/main.py:76` | Chưa dùng |
| GET | `/metrics` | `aps-backend/app/main.py:82` | Chưa dùng |

### 1. G-System Sync — `/api/v1/gsystem`

| Method | Path | File | Trạng thái FE |
|---|---|---|---|
| POST | `/gsystem/run` | `gsystem_sync.py:110` | Chưa dùng |
| GET | `/gsystem/jobs/{job_id}` | `gsystem_sync.py:132` | Chưa dùng |

### 2. LLM — `/api/v1/llm`

| Method | Path | File | Trạng thái FE |
|---|---|---|---|
| POST | `/llm/suggestions` | `llm.py:27` | Chưa dùng |
| GET | `/llm/health` | `llm.py:67` | Chưa dùng |

### 3. KPI Summary — `/api/v1/kpi-summary`

| Method | Path | File | Trạng thái FE |
|---|---|---|---|
| GET | `/kpi-summary/delivery` | `kpi_summary.py:36` | Chưa dùng (2026-07-20: bỏ path param `scenario_id` — không dùng tới, đọc thẳng `aps_mps_plan`) |
| GET | `/kpi-summary/shortage` | `kpi_summary.py:58` | Chưa dùng (2026-07-20: bỏ `scenario_id`, đổi nguồn sang `aps_result.aps_material_shortage`, `kpi_value` = số item thiếu) |
| GET | `/kpi-summary/load` | `kpi_summary.py:85` | Chưa dùng (2026-07-20: bỏ `scenario_id`, đổi nguồn sang `aps_result.aps_daily_plan`, `kpi_value` = %WC vượt tải) |
| GET | `/kpi-summary/risk-count` | `kpi_summary.py:112` | Chưa dùng — **mới thêm 2026-07-20** (KPI4, kpi_value = R1+R2+R3) |
| POST | `/kpi-summary/daily-plan/rebuild` | `kpi_summary.py:134` | Chưa dùng — rebuild cả `aps_daily_plan` lẫn `aps_material_shortage` |
| GET | `/kpi-summary/daily-plan` | `kpi_summary.py:160` | Chưa dùng |
| GET | `/kpi-summary/daily-plan/workcenter-status` | `kpi_summary.py:216` | Chưa dùng |

### 4. Work Order — `/api/v1/workorder`

| Method | Path | File | Trạng thái FE |
|---|---|---|---|
| POST | `/workorder/preview` | `workorder.py:502` | Chưa dùng (ẩn khỏi Swagger, `include_in_schema=False`) |
| GET | `/workorder/list` | `workorder.py:537` | Chưa dùng (ẩn khỏi Swagger, `include_in_schema=False`) |
| POST | `/workorder/save` | `workorder.py:601` | Chưa dùng (ẩn khỏi Swagger, `include_in_schema=False`) |
| POST | `/workorder/delete` | `workorder.py:789` | Chưa dùng (ẩn khỏi Swagger, `include_in_schema=False`) |

### 5. Purchase Requests — `/api/v1/purchase-requests`

| Method | Path | File | Trạng thái FE |
|---|---|---|---|
| GET | `/purchase-requests` | `purchase_requests.py:26` | Chưa dùng |

### 6. Material Shortage — `/api/v1/material-shortage`

**Tắt lại (2026-07-20)**: router không mount trong `routes/__init__.py` (dòng include bị comment) — `POST /material-shortage/rebuild` dư thừa vì `POST /kpi-summary/daily-plan/rebuild` đã gọi `rebuild_material_shortage()` bên trong, và `GET /material-shortage` chưa ai dùng. Code `material_shortage.py` giữ nguyên, `rebuild_material_shortage()`/`apply_daily_material_shortage()` vẫn được gọi trực tiếp (không qua HTTP) từ `POST /kpi-summary/daily-plan/rebuild`.

## Route đã bị xóa khỏi backend (đừng map FE vào)

- Xóa trước đây: `/actions/*`, `/plan-versions/*`, `/history/*`, `/schedule/*`, `/llm/plans/*` (plan detail), `/kpi-summary/{scenario_id}/risks` (KPI4 risk-count).
- **Xóa 2026-07-20** khỏi `kpi_summary.py` (đã xóa code, không chỉ ẩn):
  - `GET /kpi-summary/{scenario_id}/workcenter-schedule` (Gantt chart data)
  - `GET /kpi-summary/{scenario_id}/workcenter-load-db` (workcenter load DB, grouped)
  - `GET /kpi-summary/{scenario_id}/plan-impacted-orders` (plan impacted orders DB)
  - `GET /kpi-summary/{scenario_id}/impacted-orders` (impacted orders)
  - `GET /kpi-summary/daily-plan/material-shortage-summary` (thay thế bởi KPI2 mới, đọc từ `aps_material_shortage`)
  - `GET /kpi-summary/daily-plan/load-average` (thay thế bởi KPI3 mới, đọc từ `aps_daily_plan` rollup)

## KPI2/KPI3 đổi nguồn dữ liệu (2026-07-20)

Trước đây KPI2 (`plan_shortage`) và KPI3 (`plan_utilization`/`workcenter_load`) đọc từ các bảng **không còn ai ghi dữ liệu** (scheduler tạo ra chúng đã bị xóa khỏi backend) — API chạy được nhưng luôn trả rỗng. Đã đổi:

- **KPI2** (`GET /kpi-summary/shortage`, không còn `scenario_id`): đọc `aps_result.aps_material_shortage`. `shortage_items` giữ nguyên breakdown `item_no/required_qty/available_qty/shortage_qty` theo đúng schema cũ.
  - **2026-07-20 (sửa lại ý nghĩa)**: `kpi_value` = **số lượng item bị thiếu** (`items_with_shortage`, khớp card FE "공정 두입 자재 부족" kiểu "6건"), không phải tổng `shortage_qty` như trước. `total_shortage_qty` vẫn giữ làm field phụ.
- **KPI3** (`GET /kpi-summary/load`, không còn `scenario_id`): đọc `aps_result.aps_daily_plan` (cùng nguồn với `workcenter-status`). `entries`/`overloaded_slots` giữ nguyên schema `WorkcenterLoadEntry` cũ (map field từ rollup, `operation_count` luôn = 0 vì daily-plan không đếm theo operation).
  - **2026-07-20 (sửa lại ý nghĩa)**: `kpi_value` = **% số workcenter vượt tải** (`overloaded_wc_count / total_wc_count × 100`, khớp card FE "공정부하율 초과" kiểu "5%WC"), không phải avg/max/min load theo slot như trước. Một WC tính là "vượt tải" nếu có **ít nhất 1 ngày** status `overload`/`urgent` trong toàn bộ lịch đã rebuild. `total_wc_count` đếm từ bảng `aps_workcenter` (toàn bộ WC, kể cả không có kế hoạch). `avg_load`/`max_load`/`min_load` (theo slot) vẫn giữ làm field phụ.
- **Gộp rebuild (2026-07-20)**: `POST /kpi-summary/daily-plan/rebuild` giờ rebuild **cả 2 bảng** trong 1 lần gọi — `aps_daily_plan` (cho KPI3) và `aps_material_shortage` (cho KPI2, gọi `rebuild_material_shortage()` từ `shortage_builder.py`). FE chỉ cần gọi 1 API rebuild này trước khi đọc KPI2/KPI3. Do đó router `/material-shortage` (mục 6) không còn cần mount riêng — đã tắt lại.
- Cả 2 API **không còn theo scenario** (giống KPI1) — gọi thẳng không cần tham số.
- Logic dùng chung được tách sang `app/services/kpi_summary/daily_plan_rollup.py` (dùng lại bởi KPI3, `daily-plan/rebuild`, `daily-plan/workcenter-status`).

## KPI4 — Total Risk Count (mới thêm 2026-07-20)

`GET /kpi-summary/risk-count` — khớp card FE "계획 수립 예상 리스크" (kiểu "20건"). `kpi_value` = `KPI1.delayed_orders + KPI2.items_with_shortage + KPI3.overloaded_wc_count` — chỉ gọi lại 3 KPI đã có, không query thêm. Response: `{kpi_name, kpi_value, r1_delayed_orders, r2_shortage_items, r3_overloaded_wc, risk_triggered}`. Cần gọi `POST /kpi-summary/daily-plan/rebuild` trước để KPI2/KPI3 (và do đó KPI4) có dữ liệu mới.

## Gợi ý mapping cho FE (theo mock hiện có → API thay thế)

| Mock hiện tại (`aps-frontend/src`) | API thay thế đề xuất |
|---|---|
| `mock-scheduler.ts` (chạy scheduler giả lập) | `POST /gsystem/run` (sync data) + `POST /kpi-summary/daily-plan/rebuild` (tính lại plan) + `POST /material-shortage/rebuild` (tính lại shortage) |
| KPI cards (delivery/shortage/load/risk) | `GET /kpi-summary/delivery`, `/shortage`, `/load`, `/risk-count` (không cần `scenario_id` nữa) |
| Bảng tô màu workcenter theo ngày | `GET /kpi-summary/daily-plan/workcenter-status` |
| Purchase request giả lập | `GET /purchase-requests` |
| Tạo/xóa work order | `POST /workorder/preview` → `POST /workorder/save` / `POST /workorder/delete` (đang ẩn khỏi Swagger) |
| Gợi ý AI (nếu có) | `POST /llm/suggestions` (đang ẩn khỏi Swagger) |

## Câu hỏi chưa giải quyết

- Có kế hoạch/timeline cụ thể để thay `mock-server.ts` bằng service gọi API thật chưa?
- `axios` đã cài trong `package.json` nhưng chưa dùng — giữ lại cho việc tích hợp sắp tới hay gỡ bỏ?
