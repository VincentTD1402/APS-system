# APS Engine — Ontology (`example.ttl`)

Tài liệu này giúp đọc hiểu **một file duy nhất** `example.ttl`: mô hình domain cho hệ **lập kế hoạch & điều độ sản xuất (APS)** dưới các ràng buộc **capacity**, **thời gian**, và **vật tư**.

| | |
|---|---|
| **Phiên bản ontology** | 1.3.0 (`owl:versionIRI`: `https://aps.engine/ontology/1.3.0`) |
| **Namespace thuật ngữ** | `https://aps.engine/ns#` (prefix `aps:`) |
| **Tài liệu ontology** | `https://aps.engine/ontology` |
| **Định dạng** | Turtle; gồm **OWL** (lớp & thuộc tính) và **SHACL** (kiểm tra dữ liệu) |

Đổi `https://aps.engine/...` sang **IRI tổ chức của bạn** khi triển khai thật.

---

## 1. Bảy khối dữ liệu cốt lõi (mapping suy nghĩ ↔ bảng)

| Khối | Class chính | Vai trò trong APS |
|------|-------------|-------------------|
| **ITEM** | `aps:Item` (+ `Product` / `SemiProduct` / `RawMaterial`) | Master mã hàng; NVL có thể **không** có routing xưởng. |
| **BOM** | `aps:BOM`, `aps:BOMComponent` | Định mức: một BOM → một thành phẩm; dòng BOM có vật tư, SL, hiệu lực. |
| **DEMAND** | `aps:Demand` | Nhu cầu / lệnh kế hoạch: item, SL, ngày; là đầu vào scheduling. |
| **ROUTING** | `aps:Routing` | Quy trình chế tạo: tập `Operation` có thứ tự. |
| **OPERATION** | `aps:Operation` | Công đoạn: gắn **work center**, `procSeq`, loại công đoạn. |
| **WORKCENTER** | `aps:WorkCenter` | Đơn vị capacity; gắn **calendar** để tính thời gian khả dụng. |
| **CALENDAR** | `aps:Calendar`, `aps:CalendarShift`, `aps:DayOfWeek` | Ca, ngày trong tuần — ràng buộc **thời gian**. |

Các lớp phụ trợ: `DemandStatus`, `ProcessType`, `RoutingType`, và các **individual** (enum ngày / loại công đoạn).

---

## 2. Ràng buộc OWL (mô hình & suy luận)

- **Phân loại item**: `Product` / `SemiProduct` bắt buộc có ít nhất một `hasRouting`; `RawMaterial` thì không.
- **BOM**: có ít nhất một `hasBOMComponent`; đúng một `producesItem`.
- **Routing / Operation / WorkCenter**: có `hasOperation`, `belongsToRouting`, `usesWorkCenter`, `hasCalendar` theo mô tả class.
- **Demand**: có `demandsItem` trỏ tới `Item`.
- **Sở hữu routing (quan trọng)**: `aps:hasRouting` là **`owl:InverseFunctionalProperty`** — cùng một **IRI routing** không được gắn cho hai item khác nhau (một routing thuộc đúng một chủ).
- **Demand ↔ routing kế hoạch**: `aps:plannedRouting` (Demand → Routing) kết hợp `aps:routingOfItem` (inverse `hasRouting`). Axiom **`owl:SubObjectPropertyOf`**:  
  `plannedRouting ∘ routingOfItem` **subpropertyOf** `demandsItem`  
  → nếu khai báo `plannedRouting`, luồng suy luận OWL buộc item của routing trùng với item được demand (khi dùng reasoner OWL DL phù hợp).
- **Tùy chọn thứ tự**: `aps:immediatelyPrecedes` giữa các `Operation` (cạnh bước kế tiếp); không bắt buộc nếu chỉ dùng `procSeq`.

**Giới hạn OWL**: OWL mô tả TBox; nhiều rule nghiệp vụ (so sánh số, trùng `procSeq` trong một routing) được chuyển sang **SHACL** bên dưới.

---

## 3. Ràng buộc SHACL (kiểm tra dữ liệu thực)

Các `sh:NodeShape` trong cùng file:

| Shape | Ý nghĩa |
|-------|---------|
| **DemandWithRoutingShape** | Có `plannedRouting` thì routing đó phải là một trong các `hasRouting` của `demandsItem`. |
| **OperationSequenceShape** | `procSeq` bắt buộc, kiểu integer, **không trùng** `procSeq` trong cùng một routing. |
| **ImmediatePrecedenceShape** | Nếu dùng `immediatelyPrecedes`: cùng routing; `procSeq(next) = procSeq(this) + 1`. |
| **BOMQuantityShape** | `quantity` trên dòng BOM **> 0** (vật tư có nghĩa cho lập kế hoạch). |
| **DemandPlanQtyShape** | Nếu có `planQty` thì **> 0**. |

SHACL bám **dữ liệu assert**; không thay thế engine tối ưu (solver) — chỉ giúp **từ chối graph RDF lỗi** trước khi vào APS.

---

## 4. Cách tự kiểm tra nhanh

**Parse cú pháp (đã dùng trong repo: `rdflib`):**

```bash
python -c "from rdflib import Graph; g=Graph(); g.parse('ontology/example.ttl', format='turtle'); print(len(g))"
```

**SHACL (cài thêm `pyshacl`):**

```bash
pip install pyshacl
python -c "import pyshacl; from rdflib import Graph; d=Graph(); d.parse('my-data.ttl', format='turtle'); s=Graph(); s.parse('ontology/example.ttl', format='turtle'); print(pyshacl.validate(d, shacl_graph=s, inference='none')[0])"
```

`my-data.ttl` là dữ liệu instance cần kiểm tra; shapes lấy từ `example.ttl`.

---

## 5. Đánh giá & hướng mở rộng (cho team)

- **Đủ cho mô tả domain APS cốt lõi**: item/BOM/demand/routing/operation/work center/calendar và liên kết ownership routing + sequencing cơ bản.
- **Chưa nằm trong file**: thời gian chuẩn từng công đoạn (cycle time), overlap, setup, thay đổi ca theo ngày cụ thể, đa nhà máy, BOM phantom — bổ sung bằng thuộc tính mới hoặc lớp mở rộng khi engine của bạn cần.
- **Đồng bộ DB**: map cột SQL ↔ `aps:*` một cách có kiểm soát; IRI instance nên ổn định (URI / URN nội bộ).
- **Reasoner OWL**: optional; pipeline thực tế thường **SHACL + ứng dụng** là đủ.

---

## 6. Lịch sử phiên bản (ngắn)

- **1.3.0**: `hasRouting` **InverseFunctional**; mở rộng `owl:disjointWith` cho Calendar/CalendarShift; SHACL `BOMQuantityShape`, `DemandPlanQtyShape`; tinh chỉnh mô tả ontology.

Nếu bạn chỉnh sửa ontology, hãy cập nhật `owl:versionInfo` / `owl:versionIRI` và mục này cho đồng bộ.
