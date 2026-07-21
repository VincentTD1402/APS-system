# API Contract Convention

Đây là hợp đồng chung BE ↔ FE. **Source of truth chi tiết endpoint**: `docs/api-spec.md`. File này chỉ định nghĩa **quy tắc** để đảm bảo cả 2 phía nói cùng ngôn ngữ.

## 1. Base

- Prefix: `/api/v1` (config `API_VERSION=v1` trong `.env`).
- Swagger UI: `http://<host>:8001/docs`. OpenAPI JSON: `/openapi.json`.
- CORS: `http://localhost:5173`, `http://localhost:5174` — chỉnh trong `main.py` khi thêm origin.
- Middleware `X-Request-ID` tự stamp mọi request → expose header response.

## 2. URL style

**RESTful cho resource CRUD**:

```text
GET    /api/v1/purchase-requests           # list
GET    /api/v1/purchase-requests/{id}      # detail
POST   /api/v1/purchase-requests           # create
PUT    /api/v1/purchase-requests/{id}      # replace
DELETE /api/v1/purchase-requests/{id}      # delete
```

**Action verb chấp nhận** khi endpoint không phải CRUD:

```text
POST /api/v1/gsystem/run
POST /api/v1/kpi-summary/daily-plan/rebuild
POST /api/v1/workorder/preview
POST /api/v1/workorder/save
POST /api/v1/workorder/delete           # delete có body (bulk) → POST, không DELETE
```

**Nguyên tắc**:

- Path segment `kebab-case`, không `snake_case` hay `camelCase`.
- Số nhiều cho collection, số ít cho action (`/purchase-requests`, `/daily-plan/rebuild`).
- Path param dùng `{id}` (integer) hoặc `{job_id}` (uuid string) — không đặt tên chung chung như `{key}`.
- Query param `snake_case`: `?workcenter_id=1&start_date=2026-08-01`.
- Không nhúng version bên trong path segment khác `/api/v1`.

## 3. Request

- **Query**: filter, pagination, sort. Type ép qua `Query(..., description=...)`.
- **Body JSON**: create/update, camelCase không bắt buộc — theo Pydantic default (snake_case). FE map field khi cần.
- **Header**: chuẩn HTTP + `X-Request-ID` (tự sinh nếu client không gửi).
- **Content-Type**: `application/json` cho mọi non-GET.

Ví dụ query pagination:

```text
GET /api/v1/purchase-requests?scenario_id=abc&limit=100&sync_status=SUCCESS
```

## 4. Response — Success

Trả **Pydantic model trực tiếp**, không bọc envelope `{success, data}`:

```json
{
  "kpi_name": "delivery_compliance_rate",
  "kpi_value": 87.5,
  "total_orders": 40,
  "on_time_orders": 35,
  "delayed_orders": 5,
  "risk_triggered": true,
  "delayed_order_details": [ /* ... */ ]
}
```

FE parse trực tiếp bằng type interface. Không có `.data.data`.

**Status codes**:

- `200 OK` — success với body.
- `201 Created` — POST tạo resource (hiếm, MVP ít dùng — hầu hết là 200).
- `202 Accepted` — async job accepted (kèm `{job_id, status: "accepted"}`).
- `204 No Content` — success không body (delete).

## 5. Response — Error

Dùng `HTTPException` — FastAPI serialize thành `{detail: ...}`:

```json
{ "detail": "Job not found" }
```

Với structured error:

```json
{ "detail": { "job_id": "abc-123", "status": "running" } }
```

**Status codes**:

- `400 Bad Request` — validation fail, missing required.
- `404 Not Found` — resource không tồn tại.
- `409 Conflict` — conflict state (job đã chạy, unique constraint).
- `422 Unprocessable Entity` — FastAPI auto cho Pydantic validation error.
- `502 Bad Gateway` — external service (G-System, LLM) lỗi.
- `500 Internal Server Error` — unexpected, tự log stack trace.

FE **không** parse `.detail.message` — parse thẳng `.detail` (có thể là string hoặc object).

## 6. Async job pattern

Áp dụng cho task > 5 giây (sync G-System, rebuild pipeline lớn):

```text
POST /api/v1/gsystem/run              → 202 {job_id, status: "accepted"}
GET  /api/v1/gsystem/jobs/{job_id}    → 202 {detail: {job_id, status: "running"}}
                                      → 200 {SyncRunResponse ...}     khi xong
                                      → 404 nếu không tìm thấy
```

**Rules**:

- Response 202 phải có `job_id` để poll.
- Poll interval FE ≥ 2 giây (không hammer).
- Job status persist vào DB (`aps_result.gsystem_sync_job` etc.) để restart API vẫn poll được.
- Guard chỉ 1 job/lúc bằng `threading.Event` (không phải lock file).

## 7. Pagination

Simple limit/offset khi cần (chưa dùng nhiều ở MVP):

```text
GET /api/v1/purchase-requests?limit=100&offset=0
```

Response trả list phẳng `[...]`. Nếu cần meta (total, next), bọc:

```json
{ "items": [...], "total": 250, "limit": 100, "offset": 0 }
```

Không dùng cursor pagination cho MVP.

## 8. Filtering & sorting

- Filter: query param từng field, AND logic mặc định: `?workcenter_id=1&start_date=2026-08-01`.
- Sort: mặc định trong service (`ORDER BY created_at DESC`), chưa expose sort qua query.

## 9. Versioning & deprecation

- **1 version tại 1 thời điểm** (`v1`). Không nhân `v2` trước khi cần thật sự.
- Đổi shape response = **breaking**: coordinate BE↔FE cùng PR, hoặc bump minor path segment (`/kpi-summary/delivery` v.s. `/kpi-summary/v2/delivery` — hiếm khi).
- Route bị xóa: **note trong `docs/api-spec.md`** section "Đã gỡ bỏ" để FE biết. Không giữ route zombie.
- Route ẩn khỏi Swagger (`include_in_schema=False`) vẫn active — dùng khi WIP hoặc internal.

## 10. Documentation obligation

Mỗi PR đổi API phải:

- [ ] Cập nhật `docs/api-spec.md` (path, params, request/response shape).
- [ ] Cập nhật `docs/api-usage-mapping.md` (trạng thái FE dùng chưa).
- [ ] Thêm `summary=` + `description=` trong `@router.<method>(...)`.
- [ ] Field `Field(..., description="...")` cho mọi field trong response Pydantic.

Không cần Postman collection — Swagger UI đủ.

## 11. FE gọi API — checklist

Trước khi thêm 1 API call:

- [ ] Endpoint đã có trong `docs/api-spec.md`?
- [ ] File `api/<domain>.api.ts` đã có method tương ứng?
- [ ] Type response đã declare trong `types/`?
- [ ] Store là nơi duy nhất gọi API? (không component gọi trực tiếp)
- [ ] Xử lý error: toast + fallback UI?
- [ ] Loading state?

## 12. Bilingual response (KO/VI)

BE **không** dịch — trả label gốc (thường Korean từ G-System) hoặc key.

FE tự dịch qua `t('key')` với 2 file `i18n/{ko,vi}.json`.

Ngoại lệ: LLM `alerts` có field `level: "주의"|"경고"|"🔴"|"🟠"` — BE trả nguyên bản, FE map sang màu/icon.

## 13. Không thay đổi contract mà không có approval

Đổi API shape, xóa endpoint, đổi status code = **user decision** — cần bàn với team trước khi implement. Đừng silently update.
