"""Per-language strings for the AI제안 narrative — LLM output-language directive
and the deterministic template fallback (`risk_narrative.build_template_narrative`).

Keyed by GSystem language code (same identifiers the MES i18n bridge uses —
`docs/# [Bàn giao] MES → APS Đồng bộ đa ngôn ngữ qua iframe postMessage.txt`),
not ISO, so the FE only ever has to forward the locale it already tracks.
"""
from __future__ import annotations

GSYSTEM_KO = "10121001"
GSYSTEM_EN = "10121002"
GSYSTEM_VI = "10121003"
GSYSTEM_ZH = "10121004"

DEFAULT_LANG = GSYSTEM_KO

# Injected into the system prompt as an explicit output-language directive —
# the rest of the prompt (rules, field names) stays Korean; models follow an
# explicit "respond only in X" instruction reliably regardless of the
# surrounding instruction language.
LANGUAGE_DIRECTIVE: dict[str, str] = {
    GSYSTEM_KO: "반드시 한국어로만 작성하세요.",
    GSYSTEM_EN: "You must write your entire response only in English.",
    GSYSTEM_VI: "Bạn phải viết toàn bộ nội dung chỉ bằng tiếng Việt.",
    GSYSTEM_ZH: "你必须只用中文撰写全部内容。",
}

SEVERITY_LABEL: dict[str, dict[str, str]] = {
    GSYSTEM_KO: {"CRITICAL": "심각", "WARNING": "주의", "NORMAL": "정상"},
    GSYSTEM_EN: {"CRITICAL": "Critical", "WARNING": "Warning", "NORMAL": "Normal"},
    GSYSTEM_VI: {"CRITICAL": "Nghiêm trọng", "WARNING": "Cảnh báo", "NORMAL": "Bình thường"},
    GSYSTEM_ZH: {"CRITICAL": "严重", "WARNING": "警告", "NORMAL": "正常"},
}


def severity_label(severity: str, lang: str) -> str:
    return SEVERITY_LABEL.get(lang, SEVERITY_LABEL[DEFAULT_LANG]).get(severity, severity)


# Template fallback strings — used only when the LLM is unreachable/rejected
# (see risk_narrative.build_template_narrative). `{...}` placeholders filled by
# str.format() with facts already computed server-side (language-agnostic).
TEMPLATE: dict[str, dict[str, str]] = {
    GSYSTEM_KO: {
        "no_risk_root_cause": "[정상] 현재 조회 범위에서 즉시 조치가 필요한 생산 리스크가 없습니다.",
        "no_risk_impact": "영향받는 작업지시가 없습니다.",
        "risk_detected": "[{severity}] 계획 리스크가 확인되었습니다.",
        "overload_cause": "작업장 {wc}의 {day} 부하율이 {pct}%로 허용량을 초과했습니다.",
        "shortage_cause": "자재 {item}의 현재고는 {available}이며 {shortage}만큼 부족합니다.",
        "impact_summary": "영향받는 작업장: {wc_list}. 영향받는 작업지시: {count}건. 심각도: {severity} (긴급도: {urgency}).",
        "no_wc": "없음",
        "rec_overload": "과부하 작업장의 작업 일정을 조정하거나 여유 있는 작업장으로 재배분하십시오.",
        "rec_shortage": "부족 자재의 구매 요청 또는 대체 자재 가능 여부를 확인하십시오.",
        "rec_priority": "납기가 임박한 작업지시부터 우선순위를 재검토하십시오.",
    },
    GSYSTEM_EN: {
        "no_risk_root_cause": "[Normal] No production risk requiring immediate action was found in the current scope.",
        "no_risk_impact": "No work orders are affected.",
        "risk_detected": "[{severity}] A planning risk was identified.",
        "overload_cause": "Workcenter {wc}'s load on {day} exceeded capacity at {pct}%.",
        "shortage_cause": "Material {item} currently has {available} on hand and is short by {shortage}.",
        "impact_summary": "Affected workcenters: {wc_list}. Affected work orders: {count}. Severity: {severity} (Urgency: {urgency}).",
        "no_wc": "none",
        "rec_overload": "Adjust the schedule of the overloaded workcenter or redistribute work to a workcenter with spare capacity.",
        "rec_shortage": "Request a purchase for the shortage material or check whether a substitute material is available.",
        "rec_priority": "Re-review priority starting with the work orders closest to their delivery date.",
    },
    GSYSTEM_VI: {
        "no_risk_root_cause": "[Bình thường] Không có rủi ro sản xuất cần xử lý ngay trong phạm vi hiện tại.",
        "no_risk_impact": "Không có chỉ thị sản xuất nào bị ảnh hưởng.",
        "risk_detected": "[{severity}] Đã phát hiện rủi ro kế hoạch.",
        "overload_cause": "Tải của work center {wc} vào ngày {day} vượt {pct}% so với công suất cho phép.",
        "shortage_cause": "Vật liệu {item} hiện còn {available} và đang thiếu {shortage}.",
        "impact_summary": "Work center bị ảnh hưởng: {wc_list}. Chỉ thị sản xuất bị ảnh hưởng: {count}. Mức độ: {severity} (Khẩn cấp: {urgency}).",
        "no_wc": "không có",
        "rec_overload": "Điều chỉnh lịch của work center quá tải hoặc phân bổ lại sang work center còn dư công suất.",
        "rec_shortage": "Tạo yêu cầu mua vật liệu đang thiếu hoặc kiểm tra khả năng thay thế bằng vật liệu khác.",
        "rec_priority": "Xem lại thứ tự ưu tiên, bắt đầu từ các chỉ thị sản xuất gần ngày giao nhất.",
    },
    GSYSTEM_ZH: {
        "no_risk_root_cause": "[正常] 当前查询范围内没有需要立即处理的生产风险。",
        "no_risk_impact": "没有受影响的作业指示。",
        "risk_detected": "[{severity}] 已确认存在计划风险。",
        "overload_cause": "工作中心 {wc} 在 {day} 的负荷率达到 {pct}%，超过允许量。",
        "shortage_cause": "物料 {item} 当前库存为 {available}，短缺 {shortage}。",
        "impact_summary": "受影响的工作中心：{wc_list}。受影响的作业指示：{count}件。严重程度：{severity}（紧急度：{urgency}）。",
        "no_wc": "无",
        "rec_overload": "请调整超负荷工作中心的作业日程，或重新分配到有余量的工作中心。",
        "rec_shortage": "请为短缺物料创建采购请求，或确认是否可用替代物料。",
        "rec_priority": "请从交货期最近的作业指示开始重新审视优先级。",
    },
}


def template_strings(lang: str) -> dict[str, str]:
    return TEMPLATE.get(lang, TEMPLATE[DEFAULT_LANG])
