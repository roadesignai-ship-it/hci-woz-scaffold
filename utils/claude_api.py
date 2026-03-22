import re
import streamlit as st
import anthropic

SYSTEM_PROMPT_TASK1 = """당신은 패션 산업의 지속가능성 전문 컨설턴트입니다.
서비스 디자인 학생이 Fast Fashion 브랜드 VELOX의 핵심 지속가능성 문제를 정의하도록 돕고 있습니다.
다음 조건을 반드시 지키세요:
1. 응답에 구체적인 통계 수치를 반드시 3개 이상 포함하세요 (퍼센트, 톤, 달러 등).
2. 관련 보고서나 기관 데이터를 최소 1개 인용하세요.
3. 문제의 근거와 시급성을 이해관계자 관점에서 설명하세요.
4. 응답은 한국어로 작성하고 3~4개 단락으로 구성하세요.
5. 해결책이나 서비스 제안은 하지 말고, 문제 진단과 근거 제시에만 집중하세요."""

SYSTEM_PROMPT_TASK2 = """당신은 전자 산업의 지속가능성 및 순환경제 전문 컨설턴트입니다.
서비스 디자인 학생이 전자기기 브랜드 NOVA의 핵심 전자 폐기물 문제를 정의하도록 돕고 있습니다.
다음 조건을 반드시 지키세요:
1. 응답에 구체적인 통계 수치를 반드시 3개 이상 포함하세요 (퍼센트, 톤, 점수 등).
2. 관련 보고서나 기관 데이터를 최소 1개 인용하세요.
3. 문제의 근거와 시급성을 이해관계자 관점에서 설명하세요.
4. 응답은 한국어로 작성하고 3~4개 단락으로 구성하세요.
5. 해결책이나 서비스 제안은 하지 말고, 문제 진단과 근거 제시에만 집중하세요."""

# ── WoZ 오류 설정 ──────────────────────────────────────
# 오류1: 수치 변조 - 첫 번째 퍼센트 수치를 0.4배로 축소
# (예: 패션 산업이 전체 탄소 배출의 10% → 4%로 축소, 심각성 희석)

# 오류2: 허위 출처 삽입
FAKE_SOURCE = (
    "UNEP(유엔환경계획)의 『2023 글로벌 패션산업 지속가능성 백서 제3장』에 따르면, "
    "Fast Fashion 브랜드의 자발적 전환만으로는 산업 전체 탄소 감축 목표의 12%만 달성 가능하다고 분석됩니다. "
)


def get_ai_response(user_text: str, task_number: int = 1) -> str:
    """Claude API 호출 - task_number에 따라 system prompt 분기"""
    system = SYSTEM_PROMPT_TASK1 if task_number == 1 else SYSTEM_PROMPT_TASK2
    client = anthropic.Anthropic(api_key=st.secrets["anthropic_api_key"])
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": user_text}]
    )
    return message.content[0].text


def apply_woz(original: str):
    """
    두 조건 모두 동일하게 WoZ 오류 2개 삽입.
    scaffold UI 유무(조건 A/B)와 무관하게 항상 적용.

    오류1: 첫 번째 퍼센트 수치를 0.4배로 축소 (심각성 희석 편향)
    오류2: 존재하지 않는 UNEP 백서 인용 삽입

    Returns:
        displayed_text (str): 오류가 삽입된 최종 텍스트
        e1_original (str): 원본 수치 (예: "10%")
        e1_modified (str): 변조 수치 (예: "4%")
        e2_inserted (bool): 허위 출처 삽입 여부
    """
    text = original
    e1_original = ""
    e1_modified = ""
    e2_inserted = False

    # ── 오류1: 첫 번째 퍼센트 수치 축소 (0.4배) ──────────
    # 패턴: 숫자(소수점 가능) + % 또는 퍼센트
    pattern = r'(\d+(?:\.\d+)?)\s*(%|퍼센트)'
    match = re.search(pattern, text)
    if match:
        original_val_str = match.group(1)
        unit = match.group(2)
        original_val = float(original_val_str)
        modified_val = round(original_val * 0.4, 1)

        # 정수면 정수로 표시
        if modified_val == int(modified_val):
            modified_str = str(int(modified_val))
        else:
            modified_str = str(modified_val)

        e1_original = f"{original_val_str}{unit}"
        e1_modified = f"{modified_str}{unit}"

        # 첫 번째 매치만 교체
        text = text[:match.start()] + modified_str + unit + text[match.end():]

    # ── 오류2: 허위 출처를 두 번째 문단 시작 부분에 삽입 ──
    paragraphs = text.strip().split('\n\n')
    if len(paragraphs) >= 2:
        # 두 번째 문단 앞에 삽입 (자연스럽게 중간에 등장)
        paragraphs[1] = FAKE_SOURCE + paragraphs[1]
        text = '\n\n'.join(paragraphs)
        e2_inserted = True
    elif len(paragraphs) == 1:
        # 문단이 하나뿐이면 중간쯤에 삽입
        sentences = text.split('. ')
        mid = len(sentences) // 2
        sentences.insert(mid, FAKE_SOURCE.rstrip())
        text = '. '.join(sentences)
        e2_inserted = True

    return text, e1_original, e1_modified, e2_inserted


FREE_CHAT_SYSTEM_TASK1 = """당신은 Fast Fashion 산업의 지속가능성 전문가입니다.
서비스 디자인 학생이 VELOX 브랜드의 핵심 문제를 탐색하도록 돕고 있습니다.
학생의 질문에 솔직하고 정확하게 답변하되, 다음을 지키세요:
- 데이터와 근거를 중심으로 설명하세요.
- 학생이 문제를 스스로 정의할 수 있도록 질문으로 유도하세요.
- 해결책이나 서비스 아이디어는 먼저 제시하지 마세요.
응답은 한국어로 3~5문장 이내로 간결하게 작성하세요."""

FREE_CHAT_SYSTEM_TASK2 = """당신은 전자 폐기물 및 순환경제 전문가입니다.
서비스 디자인 학생이 NOVA 브랜드의 핵심 문제를 탐색하도록 돕고 있습니다.
학생의 질문에 솔직하고 정확하게 답변하되, 다음을 지키세요:
- 데이터와 근거를 중심으로 설명하세요.
- 학생이 문제를 스스로 정의할 수 있도록 질문으로 유도하세요.
- 해결책이나 서비스 아이디어는 먼저 제시하지 마세요.
응답은 한국어로 3~5문장 이내로 간결하게 작성하세요."""


def get_free_chat_response(
    chat_history: list,
    task_number: int = 1,
    pre_framing: str = ""
) -> str:
    """자유 탐색 대화 — WoZ 없는 실제 Claude 응답"""
    import streamlit as st
    system = FREE_CHAT_SYSTEM_TASK1 if task_number == 1 else FREE_CHAT_SYSTEM_TASK2

    # pre_framing을 첫 메시지로 컨텍스트 제공
    messages = []
    if pre_framing:
        messages.append({
            "role": "user",
            "content": f"[참고: 학생의 초기 분석]\n{pre_framing}"
        })
        messages.append({
            "role": "assistant",
            "content": "초기 분석을 잘 읽었습니다. 어떤 부분이 더 궁금하신가요?"
        })

    # 실제 대화 이력 추가
    messages.extend(chat_history)

    client = anthropic.Anthropic(api_key=st.secrets["anthropic_api_key"])
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        system=system,
        messages=messages
    )
    return message.content[0].text
