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

## Tồn đọng — cần làm tiếp

1. **Re-test sau fix query-stripping** (xem mục ngay trên) — ưu tiên cao nhất, chưa
   biết còn lỗi khác phía sau (INIT/CHANGE) hay không vì chưa từng tới được đó.
2. **Domain dev cụ thể** — nếu APS test qua `localhost`/IP nội bộ (ngoài `*.gsystem.ai`),
   cần thêm origin đó vào `MES_ORIGIN_PATTERNS` trong `mes-bridge.ts` (dòng comment
   đã ghi rõ chỗ sửa). Hiện để đúng 1 dòng theo tài liệu, chưa thêm gì thêm.
3. **`isEmbedded` chưa được dùng ở UI** — layout hiện tại (`default-layout.vue`)
   không có header/nav/dropdown ngôn ngữ nào để ẩn khi `embed=1` (đã kiểm tra, chưa
   tồn tại). Nếu sau này thêm UI chọn ngôn ngữ riêng cho APS, phải bọc bằng
   `v-if="!isEmbedded"` (import từ `@/services/mes-bridge`).
4. **msgCode riêng của APS chưa đăng ký vào DB GSystem** — nhãn của APS
   (`nav.aps`, `common.*`, các label khác trong `ko.json`/`vi.json`) chỉ đổi theo
   MES khi mã là `10121001`(KO)/`10121003`(VI) — vì đó là 2 dict APS tự có. Với
   `10121002`(EN)/`10121004`(ZH)/`10121005`(JA), APS chỉ có đúng những gì MES gửi
   qua `GSYSTEM_I18N_INIT.messages`; nhãn riêng của APS không nằm trong bộ đó sẽ
   fallback về `10121001` (Korean, theo `FALLBACK_LOCALE`) — hiện KHÔNG fallback về
   tiếng Việt. Nếu cần APS hiển thị đủ EN/ZH/JA cho cả nhãn riêng, phải: (a) tự dịch
   thêm `en.json`/`zh.json`/`ja.json`, hoặc (b) đăng ký các msgCode đó vào DB
   GSystem để MES gửi sang — chưa chốt với team MES việc này (mục 8.4 trong tài
   liệu bàn giao).
5. **Chưa báo ngược cho team MES** (mục 8 trong tài liệu bàn giao):
   - Origin thật của APS ở dev/staging/prod.
   - Xác nhận pattern `https://*.gsystem.ai` đủ dùng 2 chiều.
   - Ngôn ngữ fallback đã chọn: `10121001` (한국어) — cần MES biết để không bất ngờ
     khi DB thiếu 1 ngôn ngữ nào đó.
   - Danh sách msgCode APS cần bổ sung (nếu chọn hướng (b) ở mục 4).

## Cách resume nếu có lỗi

- Đọc lại tài liệu gốc: `docs/# [Bàn giao] MES → APS Đồng bộ đa ngôn ngữ qua iframe postMessage.txt`.
- Code liên quan: `aps-frontend/src/i18n/index.ts`, `aps-frontend/src/services/mes-bridge.ts`,
  `aps-frontend/src/main.ts`.
- Checklist nghiệm thu đầy đủ nằm ở mục 4 của tài liệu gốc — chưa tick được cái nào
  vì chưa có môi trường MES thật để test.
