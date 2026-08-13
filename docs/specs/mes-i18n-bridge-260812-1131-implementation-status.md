# MES → APS i18n bridge — implementation status

Nguồn: `docs/# [Bàn giao] MES → APS Đồng bộ đa ngôn ngữ qua iframe postMessage.txt`.
Mục tiêu: APS nhúng trong iframe MES đổi ngôn ngữ theo MES real-time, không reload iframe.

## Đã làm (260812)

Hướng đã chọn: **migrate khoá locale sang mã GSystem** (`10121001`...) làm khoá chính,
bỏ hẳn `'ko'/'vi'` ISO làm identifier — thay vì maintain song song 2 hệ khoá.

| File | Thay đổi |
|---|---|
| `aps-frontend/src/i18n/index.ts` | Khoá locale đổi từ `'ko'\|'vi'` → mã GSystem (`GSYSTEM_LOCALE.KO='10121001'`, `.VI='10121003'`). `ko.json`/`vi.json` (nhãn riêng APS) đăng ký dưới đúng mã đó. Thêm `applyLanguage(code)` (không throw nếu mã lạ), `registerGsystemMessages(messages)` (`mergeLocaleMessage` mỗi mã), `registerAvailableLocales(codes)` (đảm bảo mã MES công bố luôn "available" dù chưa có dict riêng của APS). `lang` attribute của `<html>` map riêng qua `HTML_LANG_BY_GSYSTEM` (chuyện hiển thị, không phải locale key). |
| `aps-frontend/src/services/mes-bridge.ts` (mới) | `MES_ORIGIN_PATTERNS = ['https://*.gsystem.ai']`, `isTrustedMesOrigin`/`resolveMesOrigin` (param `parentOrigin` ưu tiên, fallback `document.referrer`, đối chiếu whitelist pattern — đúng mẫu trong tài liệu). `initMesBridge()`: đọc `embed`/`lang` từ query lúc khởi động (set locale ngay, không chờ postMessage), gửi `APS_READY` tới `parent` nếu đang nhúng + origin tin cậy, lắng nghe `GSYSTEM_I18N_INIT`/`GSYSTEM_I18N_CHANGE`. Export `isEmbedded` ref cho UI dùng sau. |
| `aps-frontend/src/main.ts` | Gọi `initMesBridge()` — hiện TRƯỚC `app.use(router)`/`app.mount()` (xem mục "Test thật lần đầu" dưới, lúc đầu để sau mount gây bug mất query). |

Build + `vue-tsc --noEmit` pass. **Chưa test với MES thật** (chưa có môi trường nhúng
để verify handshake + áp dụng ngôn ngữ runtime).

## Test thật lần đầu (260812, sau khi lên `feat/count-risk`)

MES đã load APS thật qua TabManager (`[TabManager] activeTab changed: {from: 'Home',
to: 'https://aps-fe.gsystem.ai/aps'}`). Log `[mes-bridge]` cho thấy:

```
[mes-bridge] init — embed: false query:
[mes-bridge] không ở embed mode — bỏ qua handshake với MES
```

`location.search` RỖNG lúc `initMesBridge()` chạy → bridge tắt luôn, chưa từng gửi
`APS_READY`. Root cause tìm được (bug ở phía APS, không phải MES):

- Route `'/' → '/aps'` dùng redirect string đơn giản — vue-router resolve kiểu này
  KHÔNG tự forward query string. Nếu MES nhúng iframe ở path `/` (thay vì `/aps`
  thẳng) kèm `?embed=1&lang=...&parentOrigin=...`, redirect xoá mất param trước khi
  code nào đọc được.
- `initMesBridge()` cũ gọi SAU `app.mount()` → dù route đích đúng là `/aps` ngay từ
  đầu, thời điểm đọc `location.search` vẫn trễ hơn lúc router có thể đã
  `history.replaceState` xong.

**Đã fix (commit `a754541`):**
- `router/index.ts`: redirect `/` → `/aps` đổi thành hàm `(to) => ({ path: '/aps',
  query: to.query, hash: to.hash })` — forward nguyên query/hash.
- `main.ts`: `initMesBridge()` dời lên gọi TRƯỚC `app.use(router)`/`app.mount()`,
  đọc URL gốc trước khi bất kỳ redirect nào kịp chạy.

**Chưa xác nhận lại** — cần MES load lại APS 1 lần nữa (test thật) để xem log
`[mes-bridge]` có báo `embed: true` và tiếp tục nhận được `GSYSTEM_I18N_INIT` hay
không. Nếu vẫn `embed: false` sau fix này → nghĩa là MES thực sự không gửi
`?embed=1&lang=...` (khác với tài liệu bàn giao mô tả), cần báo lại team MES kiểm
tra `src` của iframe/tab thật đang set (xem DOM `<iframe>`/tab config, không chỉ tin
vào log `[TabManager]` vì log đó có thể đã bỏ query khi hiển thị).

## Handshake xác nhận OK (260812, sau fix query-stripping)

User xác nhận "đã làm được rồi" — MES load APS đúng `embed=1`, `mes-bridge` gửi
`APS_READY` và nhận `GSYSTEM_I18N_INIT`/`CHANGE` thành công. Handshake postMessage
coi như xong, không còn mở.

## Wiring toàn bộ màn hình chính vào i18n + đăng ký msgCode (260813)

Phát hiện lúc làm: **chỉ 5 view Masters/MPS gọi `t()` thật** (`work-center-list-view`,
`item-list-view`, `bom-view`, `inventory-view`, `mps-list-view`, ~30 key). Màn hình
작업계획 chính (Action Panel, Work Plan List, Load Matrix, KPI Row, Filter Bar, AI
Panel, `aps-work-plan-view`) **hardcode chữ Hàn thẳng trong template**, không gọi
`t()` ở đâu — nên trước đây dù MES đổi ngôn ngữ, màn hình chính vẫn luôn tiếng Hàn.

**Đã làm:**
- Bổ sung `ko.json`/`vi.json` với toàn bộ key màn hình chính còn thiếu
  (`filterBar.*`, `loadMatrix.col.*`/`total`, `actionPanel.*`, `aiPanel.*`,
  `apsView.*` — toast/nút RUN/시뮬레이션/작업지시 생성, `badge.*`), sửa vài chỗ
  wording lệch giữa JSON cũ và text đang hiển thị thật (kpi.overloadWc/planRisk).
  Tổng **185 leaf key**, khớp 1:1 giữa 4 ngôn ngữ.
- **Tạo mới `en.json`/`zh.json`** (dịch đầy đủ 185 key) — APS giờ tự có fallback
  EN/ZH ngay cả khi MES chưa gửi msgCode tương ứng, không chỉ phụ thuộc MES.
  Đăng ký cả 4 vào `i18n/index.ts` (`GSYSTEM_LOCALE.KO/VI/EN/ZH`).
- Wire `t()` vào toàn bộ: `filter-bar.vue`, `load-matrix.vue`, `kpi-row.vue`,
  `work-plan-list.vue`, `action-panel.vue`, `badge-tag.vue`, `ai-panel.vue` (phần
  static — xem giới hạn dưới), `aps-work-plan-view.vue` (title, 3 nút, toàn bộ toast).
- Build + `vue-tsc --noEmit` pass.

**Giới hạn đã biết — KHÔNG dịch được (out of scope, không phải bug):**
- `ai-panel.vue`: `narrative.impactSummary`, `narrative.recommendations[].text`,
  `rootCauseText` là **văn xuôi do LLM sinh ra** (backend RiskDetailService), không
  phải static key — muốn dịch phải prompt LLM sinh bằng ngôn ngữ đích, việc khác hẳn,
  chưa làm.
- `work-plan-list.vue`/`load-matrix.vue`: giá trị data thật (`itemName`,
  `workcenterName`, `procName`, `sourceType`...) lấy từ G-System, không phải label
  tĩnh — muốn đa ngôn ngữ phải qua multilingual field của item/workcenter trong
  G-System, không phải việc của `ko.json`/`vi.json`.

**Bảng đăng ký msgCode cho GSystem admin:**
`docs/specs/aps-msgcode-register-260813.csv` — 740 dòng (185 key × 4 ngôn ngữ:
한국어/영어/베트남어/중국어), cột `Module Category` để cứng `APS` (bạn xác nhận
"giữ nguyên" — hiểu là tự chọn/tạo giá trị đúng khi nhập vào GSystem admin, KHÔNG
lấy nguyên "AI챗봇" trong ảnh ví dụ; đổi lại cột này trong CSV nếu team GSystem cho
biết giá trị/khoá khác). `Message Category` để cứng `라벨` theo đúng ảnh ví dụ —
một số dòng thực ra là **toast/thông báo động có `{placeholder}`** (`apsView.toast*`,
`aiPanel.*Line`) không hẳn là "label" tĩnh, kiểm tra xem GSystem có category riêng
cho message/thông báo không, đổi lại nếu cần. `Message Code` = `aps_` + key JSON
(thay `.` bằng `_`), cột cuối `Source Key` chỉ để đối chiếu, không nhập vào GSystem.
**740 dòng nhập tay là rất nhiều** — hỏi GSystem admin có hỗ trợ import CSV/Excel
bulk không, đừng nhập tay từng dòng nếu tránh được.

## Tồn đọng — cần làm tiếp

1. **Nhập 740 dòng vào GSystem admin** (hoặc bulk import) — chưa làm, đây là thao
   tác tay/ngoài code.
2. **Xác nhận lại `Module Category` giá trị đúng** trước khi nhập — xem mục ngay
   trên, tôi để `APS` làm placeholder trong CSV, chưa được GSystem admin xác nhận.
3. **`ja.json` (일본어) chưa có** — GSYSTEM_LOCALE.JA chưa có dict riêng của APS,
   vẫn fallback về `10121001` (Korean) nếu MES chọn tiếng Nhật. Không nằm trong ảnh
   ví dụ (chỉ có 4 ngôn ngữ: 한국어/영어/베트남어/중국어) nên tạm bỏ qua, làm sau
   nếu cần.
4. **`isEmbedded` chưa được dùng ở UI** — layout hiện tại (`default-layout.vue`)
   không có header/nav/dropdown ngôn ngữ nào để ẩn khi `embed=1` (đã kiểm tra, chưa
   tồn tại). Nếu sau này thêm UI chọn ngôn ngữ riêng cho APS, phải bọc bằng
   `v-if="!isEmbedded"` (import từ `@/services/mes-bridge`).
5. **Domain dev cụ thể** — nếu APS test qua `localhost`/IP nội bộ (ngoài `*.gsystem.ai`),
   cần thêm origin đó vào `MES_ORIGIN_PATTERNS` trong `mes-bridge.ts`.
6. **Chưa báo ngược cho team MES** (mục 8 trong tài liệu bàn giao):
   - Origin thật của APS ở dev/staging/prod.
   - Xác nhận pattern `https://*.gsystem.ai` đủ dùng 2 chiều.
   - Ngôn ngữ fallback đã chọn: `10121001` (한국어).
   - Danh sách msgCode APS cần bổ sung — chính là file CSV ở trên, sau khi chốt
     `Module Category`.

## Cách resume nếu có lỗi

- Đọc lại tài liệu gốc: `docs/# [Bàn giao] MES → APS Đồng bộ đa ngôn ngữ qua iframe postMessage.txt`.
- Code liên quan: `aps-frontend/src/i18n/index.ts`, `aps-frontend/src/services/mes-bridge.ts`,
  `aps-frontend/src/main.ts`.
- Checklist nghiệm thu đầy đủ nằm ở mục 4 của tài liệu gốc — chưa tick được cái nào
  vì chưa có môi trường MES thật để test.
