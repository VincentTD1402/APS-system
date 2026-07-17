# FE Mock Data — Giải thích cách data được tạo ra

> Đối tượng: dev, planner, tester đang tương tác với FE MVP để verify hành vi.
> Toàn bộ mock nằm trong 4 file, được ghép nối theo đúng luồng thật của APS (import G-System → nhập MPS → RUN APS). Không có data cứng — matrix và risk đều **tự tính** từ master + MPS.

---

## 1. Master data — `frontend/src/mocks/master-data.ts`

Đây là "dữ liệu bên G-System sẽ đẩy sang", được hard-code theo đúng ví dụ trong CSV spec (`docs/specs/Đã dịch_APS개발의뢰_20260707/개발의뢰-Table 1.csv`).

### Work Center + Equipment (mỗi WC có nhiều máy, mỗi máy có ST환산율)

```
WC001 (조립 · Lắp ráp)
  ├─ 설비001-1 · ST환산율 = 0.80  → 480 × 0.80 = 384 phút/ngày
  └─ 설비001-2 · ST환산율 = 1.30  → 480 × 1.30 = 624 phút/ngày
  Tổng WC001 = 1008 phút/ngày   ← ĐÂY LÀ CAPACITY

WC002 (사출 · Ép)
  ├─ 설비002-1 · 1.00 → 480
  └─ 설비002-2 · 1.10 → 528
  Tổng = 1008 phút/ngày

WC003 (도장 · Sơn)
  ├─ 설비003-1 · 0.90 → 432
  └─ 설비003-2 · 1.20 → 576
  Tổng = 1008 phút/ngày
```

`totalRuntimeMin: 1008` là **capacity** để so sánh với `minutes_loaded` mỗi ngày → quyết định ô 🟠 quá tải hay 🟢 bình thường.

### Item + Routing (mỗi item chạy 1 WC, có standard S/T)

| Item | WC | Standard S/T (phút/EA) | Ý nghĩa |
|---|---|---|---|
| 제품1 | WC001 | 6.0 | mỗi EA cần 6 phút gia công |
| 제품2 | WC002 | 10.5 | mỗi EA cần 10.5 phút |
| 제품3 | WC003 | 18.33 | mỗi EA cần 18.33 phút |
| 자재-A, 자재-B | — | — | raw material, không có routing |

Từ đây tính được **daily capacity theo Item**:

- 제품1: `1008 / 6.0 = 168 EA/ngày` (khớp spec)
- 제품2: `1008 / 10.5 ≈ 96 EA/ngày` (khớp spec)
- 제품3: `1008 / 18.33 ≈ 55 EA/ngày` (khớp spec)

### BOM (1 finished cần bao nhiêu raw)

```
제품1  →  자재-A × 2                      (spec P5: 2:1)
제품2  →  자재-A × 1 + 자재-B × 3          (2 nhánh để test BOM đa raw)
제품3  →  자재-B × 1
```

### Inventory (tồn kho theo warehouse — theo validation session 1)

```
자재-A ở WH01: 1500
자재-A ở WH02: 1164   → tổng aggregate = 2664 (khớp spec P5)
자재-B ở WH01: 500
```

---

## 2. MPS orders — `frontend/src/mocks/mps-data.ts`

5 order **đúng dòng 76-80** trong CSV spec:

| Order | Item | Qty | end_date | work_start / work_end (spec hint) |
|---|---|---|---|---|
| PO-2026-001 | 제품1 | 500 | 2026-08-11 | 08-09 / 08-11 |
| PO-2026-002 | 제품1 | 1000 | 2026-08-15 | 08-10 / 08-15 |
| PO-2026-003 | 제품2 | 1200 | 2026-08-20 | 08-08 / 08-20 |
| PO-2026-004 | 제품3 | 800 | 2026-08-19 | 08-04 / 08-19 |
| PO-2026-005 | 제품3 | 170 | 2026-08-05 | 08-02 / 08-05 |

+ 1 WorkOrder pending (`WO-2026-0001` cho 제품2 200 EA end 08-04) — để bạn thấy cột `작업지시번호` có giá trị khi source là `FROM_WORK_ORDER`.

**Today reference cứng = `2026-08-01`** trong `MOCK_TODAY`. Đổi ngày này matrix sẽ dịch theo.

---

## 3. Mock scheduler — `frontend/src/mocks/mock-scheduler.ts`

Khi bạn bấm nút `RUN APS`, hàm `runMockAps()` chạy 7 bước:

### Bước 1 — Build task list

Ghép WorkOrder pending + MPS DRAFT thành list `ScheduleTask[]`. Mỗi task có Item + WC + qty + end_date.

### Bước 2 — Backward schedule cho từng task

Với mỗi task, gọi `backwardSchedule(qty, end_date, today, daily_capacity_EA)`:

```
Ví dụ: 제품3, 170 EA, end=08-05, today=08-01, cap=55/ngày
  → cursor=08-05: 55@08-05, remain=115
  → cursor=08-04: 55@08-04, remain=60
  → cursor=08-03: 55@08-03, remain=5
  → cursor=08-02: 5@08-02, remain=0
  → Output: [08-02:5, 08-03:55, 08-04:55, 08-05:55]
             (đúng khớp spec CSV dòng 80)
```

Nếu `remaining > 0` khi đã đến today → dồn hết vào today (rule spec P3).

Sau khi có `daily_plans`, tính `minutes_loaded = qty × standard_S_T`.

### Bước 3 — Aggregate load matrix

Cộng dồn `minutes_loaded` theo `(wc_code, date)`:

```
Ví dụ WC001 ngày 08-10:
  MPS-1 (제품1 500)  có 168@08-10 → 168 × 6 = 1008 phút
  MPS-2 (제품1 1000) có 168@08-10 → 168 × 6 = 1008 phút
  Tổng cell WC001|08-10 = 2016 phút
  Capacity WC001        = 1008 phút
  → 2016 > 1008 → OVERLOAD → ô cam 🟠
```

Đây là lý do bạn thấy WC001 các ngày 08-10, 08-11 có ô cam/đỏ.

### Bước 4 — Material shortage check

Với mỗi task (sort theo `delivery_date ASC` — task giao gấp được ưu tiên):

```
For task in sorted_tasks:
    For each raw R in BOM(task.item):
        need = task.qty × qty_per
        if inventory[R] < need:
            shortage += need - inventory[R]
            inventory[R] = 0   ← trừ dần, task sau không thấy stock ảo
        else:
            inventory[R] -= need
```

Ví dụ với 자재-A (stock đầu = 2664):

- MPS-5 (제품3 170) không dùng 자재-A → bỏ qua
- MPS-1 (제품1 500, delivery 08-11): cần 500 × 2 = 1000 → stock còn 2664 − 1000 = **1664**, OK
- MPS-3 (제품2 1200, delivery 08-20): cần 1200 × 1 = 1200 → stock còn 1664 − 1200 = **464**, OK
- MPS-2 (제품1 1000, delivery 08-15): cần 1000 × 2 = 2000 → stock 464 không đủ → **thiếu 1536 EA** → MATERIAL_SHORT → 🔵

Bạn thấy MPS-2 (제품1 1000) có chip `자재부족` màu xanh dương chính là vì logic này.

### Bước 5 — Risk classification per plan

```
material_ok  = từ bước 4
overload_cell = có bất kỳ ngày nào cell.minutes > capacity không?

if material_short && overload   → MATERIAL_AND_OVERLOAD  🔴
elif material_short             → MATERIAL_SHORT          🔵
elif overload                   → OVERLOAD                🟠
else                            → NORMAL                  🟢
```

### Bước 6 — Risk classification per cell (matrix)

```
For each (wc, date):
  loaded           = tổng minutes
  hasMaterialShort = có plan MATERIAL_SHORT nào hit ngày này không?
  overload         = loaded > capacity

  status =
    loaded == 0                      → EMPTY (ô rỗng dashed)
    overload && hasMaterialShort     → 🔴 both
    overload                         → 🟠 orange
    hasMaterialShort                 → 🔵 blue
    else                             → 🟢 green
```

### Bước 7 — KPI

Tính 4 KPI từ result:

- `onTimeRate` = %WorkPlan có `plan_end ≤ delivery_date`
- `materialShortageCount` = count plan có material short
- `overloadWcPct` = %WC có ít nhất 1 cell overload
- `planningRiskCount` = count plan có `risk != NORMAL`

---

## 4. Mock server — `frontend/src/api/mock-server.ts`

Wrapper API trong browser, delay 200-600ms để giả cảm giác call BE:

```typescript
mockServer.runAps()                    // chạy scheduler, cache last run
mockServer.adjustPlan(...)             // sửa start/end, mark adjusted=true
mockServer.restoreAll()                // revert original_start/end
mockServer.createPurchaseRequest(...)  // push vào state.outbox
mockServer.createWorkOrder(...)        // push vào state.outbox
mockServer.listOutbox()                // xem lịch sử
```

Khi BE có API thật, chỉ đổi body các hàm này thành `axios.get(...)` là xong — signature không đổi, store + component không phải sửa.

---

## Bạn có thể tự chỉnh gì để test

| Muốn thay đổi | Sửa file |
|---|---|
| Thêm/bớt Item, WC, thiết bị | `frontend/src/mocks/master-data.ts` |
| Thêm/bớt MPS order, đổi qty, đổi end_date | `frontend/src/mocks/mps-data.ts` |
| Đổi tồn kho để tạo/xóa material shortage | `master-data.ts` → `MOCK_INVENTORY` |
| Đổi capacity WC (thêm/xóa Equipment ST rate) | `master-data.ts` → `MOCK_EQUIPMENTS` |
| Đổi standard S/T để tăng/giảm daily cap | `master-data.ts` → `MOCK_ROUTINGS` |
| Đổi ngày Today | `master-data.ts` → `MOCK_TODAY` |

Sau khi sửa: refresh trang → tự động chạy `runAps()` lần đầu → matrix + list + KPI tính lại theo data mới.

## Ví dụ thử tay

**Muốn xóa material shortage của 제품1 1000?**
→ Vào `master-data.ts` đổi `자재-A WH02` on_hand từ `1164` thành `3000` → tổng 4500 → đủ cho cả 3 order → chip xanh 🟢 hết.

**Muốn tạo overload WC003?**
→ Thêm 1 MPS 제품3 với qty 500 end_date 08-05 (chỉ 3 ngày sản xuất, cần 500×18.33/1008 ≈ 9 ngày) → capacity không đủ → ô cam WC003 08-01 → 08-05.

**Muốn thấy plan 🔴 both (material + overload)?**
→ Đổi 자재-B WH01 on_hand từ 500 xuống 50 → 제품3 800 EA cần 800 raw → thiếu → MATERIAL_SHORT. Kết hợp với overload sẵn có của WC003 → 🔴.
