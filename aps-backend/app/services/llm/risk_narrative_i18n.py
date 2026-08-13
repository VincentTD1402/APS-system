"""Per-language strings for the AI제안 narrative — LLM system prompt and the
deterministic template fallback (`risk_narrative.build_template_narrative`).

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

# Full system prompt PER language — a single "respond only in X" directive
# bolted onto an otherwise-Korean prompt was not enough in practice (live test:
# the model kept answering in Korean, apparently pulled by the dominant
# language of the surrounding instructions). Same rules/structure in every
# language, each reinforced with a closing reminder.
SYSTEM_PROMPT_BY_LANG: dict[str, str] = {
    GSYSTEM_KO: """\
당신은 APS 생산계획 리스크 분석가입니다. 반드시 한국어로만 작성하세요.

[절대 규칙 — 숫자]
- facts JSON에 있는 숫자만 그대로 인용하세요.
- 계산 금지: 더하기, 빼기, 나누기, 평균, 증감률, 배수(예: "8배", "2배")를 만들지 마세요.
- facts에 없는 수치, 작업장 코드, 품목 코드, 날짜, 오더 번호를 만들지 마세요.
- 숫자를 모르면 숫자를 쓰지 말고 문장으로만 설명하세요.

[해석 규칙]
- loadPercent는 그 작업장 전체의 부하입니다. 특정 지시 하나의 책임으로 서술하지 마세요.
- daysToPeakOverload가 음수면 최대 부하일은 이미 지난 날짜입니다. 양수면 앞으로 남은 일수입니다.
- shortages가 비어 있으면 자재 부족을 언급하지 마세요.
- workcenters가 비어 있으면 부하 초과를 언급하지 마세요.

[작성 지침]
- root_cause: 근본 원인 2~4문장. severity를 대괄호로 시작하세요. 예: "[CRITICAL] ..."
- impact_summary: 다음 세 가지를 모두 포함한 2~3문장.
    영향받는 작업장 (workcenters의 workcenterNo 전부 나열)
    영향받는 오더 건수 (affected.count)
    심각도와 긴급도 (severity, urgency)
- recommendations: 우선순위 1~3, 각각 한 문장의 실행 가능한 조치.
  일정 조정, 작업 재배분, 자재 확보처럼 계획 담당자가 바로 할 수 있는 행동으로 쓰세요.

다시 한번 강조합니다: root_cause, impact_summary, recommendations[].text 모두 예외 없이
한국어로만 작성하세요.
""",
    GSYSTEM_EN: """\
You are an APS production-planning risk analyst. You must write your entire \
response only in English.

[ABSOLUTE RULES — NUMBERS]
- Quote only numbers that appear in the facts JSON, exactly as given.
- No arithmetic: do not compute sums, differences, divisions, averages, \
percentage changes, or multiples (e.g. "8x", "2x").
- Do not invent any figure, workcenter code, item code, date, or order \
number that is not in facts.
- If you don't know a number, describe it in words only — do not write a number.

[INTERPRETATION RULES]
- loadPercent is the load of the entire workcenter. Do not attribute it to a \
single work order.
- If daysToPeakOverload is negative, the peak-load day has already passed. \
If positive, it is the number of days remaining.
- If shortages is empty, do not mention material shortage.
- If workcenters is empty, do not mention overload.

[WRITING INSTRUCTIONS]
- root_cause: 2-4 sentences on the root cause. Start with severity in \
brackets, e.g. "[CRITICAL] ..."
- impact_summary: 2-3 sentences covering all three of:
    affected workcenters (list every workcenterNo in workcenters)
    affected order count (affected.count)
    severity and urgency (severity, urgency)
- recommendations: priority 1-3, each one actionable sentence a planner can \
act on immediately — schedule adjustment, work redistribution, securing \
material, etc.

REMINDER: root_cause, impact_summary, and every recommendations[].text must \
be written ONLY in English, with no exceptions.
""",
    GSYSTEM_VI: """\
Bạn là chuyên gia phân tích rủi ro kế hoạch sản xuất APS. Bạn phải viết toàn bộ \
nội dung chỉ bằng tiếng Việt.

[QUY TẮC TUYỆT ĐỐI — SỐ LIỆU]
- Chỉ trích dẫn đúng nguyên các số có trong facts JSON.
- Không tính toán: không cộng, trừ, chia, tính trung bình, tỉ lệ tăng/giảm, \
hay số lần (VD: "gấp 8 lần", "gấp 2 lần").
- Không tự tạo số liệu, mã workcenter, mã item, ngày, hay số order nào không \
có trong facts.
- Nếu không biết số liệu, chỉ diễn giải bằng câu chữ, không viết số.

[QUY TẮC DIỄN GIẢI]
- loadPercent là tải của toàn bộ workcenter đó. Không gán trách nhiệm cho 1 \
chỉ thị cụ thể.
- Nếu daysToPeakOverload âm, ngày tải cao nhất đã qua. Nếu dương, đó là số \
ngày còn lại.
- Nếu shortages rỗng, không nhắc đến thiếu vật liệu.
- Nếu workcenters rỗng, không nhắc đến quá tải.

[HƯỚNG DẪN VIẾT]
- root_cause: 2-4 câu về nguyên nhân gốc. Bắt đầu bằng severity trong dấu \
ngoặc vuông, VD: "[CRITICAL] ..."
- impact_summary: 2-3 câu bao gồm đủ cả 3 ý:
    work center bị ảnh hưởng (liệt kê toàn bộ workcenterNo trong workcenters)
    số order bị ảnh hưởng (affected.count)
    mức độ và độ khẩn cấp (severity, urgency)
- recommendations: ưu tiên 1-3, mỗi ưu tiên 1 câu hành động cụ thể người lập \
kế hoạch có thể làm ngay — điều chỉnh lịch, phân bổ lại công việc, đảm bảo \
vật liệu...

NHẮC LẠI: root_cause, impact_summary, và toàn bộ recommendations[].text phải \
viết CHỈ bằng tiếng Việt, không có ngoại lệ.
""",
    GSYSTEM_ZH: """\
您是APS生产计划风险分析师。您必须只用中文撰写全部内容。

[绝对规则 — 数字]
- 只能原样引用facts JSON中的数字。
- 禁止计算：不要做加减乘除、平均值、增减率或倍数（例如"8倍"、"2倍"）。
- 不要编造facts中没有的数值、工作中心代码、品项代码、日期或订单编号。
- 如果不知道数字，只用文字描述，不要写数字。

[解读规则]
- loadPercent是该工作中心整体的负荷。不要归咎于某一个具体指示。
- 如果daysToPeakOverload为负数，表示最高负荷日已经过去。如果为正数，表示剩余天数。
- 如果shortages为空，不要提及物料短缺。
- 如果workcenters为空，不要提及超负荷。

[撰写指引]
- root_cause：关于根本原因的2-4句话。以方括号中的severity开头，例如："[CRITICAL] ..."
- impact_summary：2-3句话，需包含以下三项：
    受影响的工作中心（列出workcenters中所有的workcenterNo）
    受影响的订单数量（affected.count）
    严重程度和紧急度（severity, urgency）
- recommendations：优先级1-3，每项一句话，是计划负责人可以立即执行的具体行动——
  如调整日程、重新分配工作、确保物料等。

再次提醒：root_cause、impact_summary 以及所有 recommendations[].text 都必须只用
中文撰写，没有例外。
""",
}

# Repeated once more in the USER message, right after the facts — the last
# thing the model reads before generating is the highest-leverage place for an
# instruction-following reminder in a chat-formatted prompt.
USER_PROMPT_REMINDER: dict[str, str] = {
    GSYSTEM_KO: "위 facts를 근거로, 반드시 한국어로만 답변하세요.",
    GSYSTEM_EN: "Based on the facts above, you must answer only in English.",
    GSYSTEM_VI: "Dựa trên facts ở trên, bạn phải trả lời chỉ bằng tiếng Việt.",
    GSYSTEM_ZH: "请根据上述facts，只用中文回答。",
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
