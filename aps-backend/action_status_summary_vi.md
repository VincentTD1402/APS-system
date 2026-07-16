# Tóm tắt trạng thái các `action_type` (Tiếng Việt)

Ngày: 2026-05-03

Mục đích: Báo cáo một trang gọn nhưng chi tiết về tình trạng các `action_type`, khả năng chạy ở chế độ simulation, và đề xuất tiếp theo.

Chú giải
- ✅: Đã triển khai và an toàn trong simulation (ghi lên overlay hoặc insert có scope)
- ⚠️: Đã triển khai nhưng cần lưu ý / hỗ trợ một phần
- ❌: Không an toàn trong simulation hoặc chưa triển khai

Tóm tắt nhanh

- **CHANGE_DELIVERY_DATE**: ✅ — Trong simulation ghi `DemandOverlay.delivery_date`; baseline không thay đổi. Hỗ trợ auto-reschedule.
- **APPLY_OVERTIME**: ✅ — Trong simulation ghi `WorkCenterOverlay.std_capa`; baseline không thay đổi. Hỗ trợ auto-reschedule.
- **SUBSTITUTE_MATERIAL**: ✅ — Trong simulation ghi `BOMComponentOverlay`; baseline không thay đổi.
- **CREATE_PURCHASE_REQUEST**: ✅ — Thêm bản ghi có `scenario_id`; an toàn cho simulation.
- **CHANGE_PRIORITY**: ✅ — Đã chuyển sang ghi `PlanOrderOverlay.priority_score` trong simulation; baseline không thay đổi.
- **REALLOCATE_INVENTORY**: ✅ — Đã chuyển sang ghi `PlanMaterialOverlay.allocated_qty` (nguồn + đích) trong simulation; baseline không thay đổi.
- **SHIFT_SCHEDULE**: ❌ — KHÔNG an toàn trong simulation. Thay đổi thời gian `PlanOperation` là thay đổi cấu trúc lịch, cần xác thực ràng buộc và re-planning.
- **LINE_BALANCE**: ❌ — KHÔNG an toàn trong simulation. Thay đổi `PlanOperation.workcenter_id` cần kiểm tra routing/capa/lead-time và thường yêu cầu re-plan.

Tại sao `SHIFT_SCHEDULE` và `LINE_BALANCE` khác biệt

- Hai action này thay đổi cấu trúc lịch (thời gian hoặc phân công tài nguyên), không chỉ metadata hay số lượng.
- Một thay đổi cấu trúc có thể gây cascade: ảnh hưởng các operation downstream, tải máy, thời điểm nguyên vật liệu, v.v.
- Để đảm bảo tính hợp lệ, bắt buộc phải chạy lại bộ solver (re-plan) hoặc thực hiện validator + partial-replan phức tạp.
- Nếu chỉ ghi overlay mà không re-plan → schedule có thể trở nên không hợp lệ (resource conflict, dependency broken).

Khuyến nghị ngay lập tức (thực tiễn)

- Ngắn hạn (khuyến nghị): **Không cho phép** `SHIFT_SCHEDULE` và `LINE_BALANCE` trong chế độ simulation. Trả về lỗi giải thích rõ ràng cho người dùng.
  - Thực hiện: thêm guard trong `app/services/action/action_executor.py` để từ chối khi `resolver.is_simulation_scenario(session, scenario_id)` trả true.
  - Lợi ích: an toàn, nhanh, tránh schedule invalid.

- Trung/ Dài hạn (nếu cần): hỗ trợ re-plan khi apply hai action này trong simulation.
  - Phương án 1: Khi user apply → ghi overlay cho thay đổi operation → kích hoạt chạy solver cho `scenario_id` (solver rebuild PlanOperation dựa trên overlay + input overlays) → cần logic merge/retain overlay khác.
  - Phương án 2: Thiết kế `PlanOperationOverlay` + validator + partial replan (phức tạp, nhiều rủi ro).
  - Hạn chế: tốn thời gian, latency cao, phức tạp khi hợp nhất nhiều overlay.

Checklist vận hành để triển khai phương án ngắn hạn

- Thêm guard từ chối `SHIFT_SCHEDULE` và `LINE_BALANCE` trong `app/services/action/action_executor.py` khi là simulation.
- UI/API: disable action cards tương ứng khi đang xem simulation và hiển thị lý do.
- Cập nhật tài liệu (ví dụ `docs/Báo cáo Kiến trúc Action Card (4).md`) để nêu rõ giới hạn.

Các file liên quan

- Resolver & overlay: `app/services/input_state/resolver.py`
- Action handlers: `app/services/action/action_executor.py`
- Model overlay kết quả: `app/models/output/overlay.py`
- Migration tạo overlay kết quả: `migrations/versions/c2d3e4f5a6b7_create_result_overlay.py`
- Báo cáo thiết kế: `docs/Báo cáo Kiến trúc Action Card (4).md`

Đề xuất bước tiếp theo (chọn 1)

- **A — Nhanh (khuyến nghị):** Triển khai guard để từ chối `SHIFT_SCHEDULE` & `LINE_BALANCE` trong simulation (5–15 phút).  
- **B — Trung:** Khi apply hai action này trong simulation, trigger full solver re-plan và thiết kế cách merge overlays (cần phân tích kỹ, 2–5 ngày).  
- **C — Nâng cao:** Thiết kế `PlanOperationOverlay` + validator + partial replan engine (nghiên cứu & implement, nhiều tuần).

Bạn muốn tôi thực hiện phương án nào tiếp theo? Nếu chọn **A**, tôi sẽ cập nhật code ngay và thêm test + message API/UX.
