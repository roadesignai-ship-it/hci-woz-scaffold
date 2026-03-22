import re
import streamlit as st
import anthropic

# ── Task 1: VELOX (Fast Fashion) 시스템 프롬프트 ──────
SYSTEM_PROMPT_TASK1 = """당신은 패션 산업의 지속가능성 전문 컨설턴트입니다.
서비스 디자인 학생이 Fast Fashion 브랜드 VELOX의 핵심 지속가능성 문제를 정의하도록 돕고 있습니다.
다음 조건을 반드시 지키세요:
1. 응답에 구체적인 통계 수치를 반드시 3개 이상 포함하세요 (퍼센트, 톤, 달러 등).
2. 관련 보고서나 기관 데이터를 최소 1개 인용하세요.
3. 문제의 근거와 시급성을 이해관계자 관점에서 설명하세요.
4. 응답은 한국어로 작성하고 3~4개 단락으로 구성하세요.
5. 해결책이나 서비스 아이디어는 제시하지 말고, 문제 진단과 근거 제시에만 집중하세요."""

# ── Task 2: NOVA (E-Waste) 시스템 프롬프트 ───────────
SYSTEM_PROMPT_TASK2 = """당신은 전자 산업의 지속가능성 및 순환경제 전문 컨설턴트입니다.
서비스 디자인 학생이 전자기기 브랜드 NOVA의 핵심 전자 폐기물 문제를 정의하도록 돕고 있습니다.
다음 조건을 반드시 지키세요:
1. 응답에 구체적인 통계 수치를 반드시 3개 이상 포함하세요 (퍼센트, 톤, 점수 등).
2. 관련 보고서나 기관 데이터를 최소 1개 인용하세요.
3. 문제의 근거와 시급성을 이해관계자 관점에서 설명하세요.
4. 응답은 한국어로 작성하고 3~4개 단락으로 구성하세요.
5. 해결책이나 서비스 아이디어는 제시하지 말고, 문제 진단과 근거 제시에만 집중하세요."""

# ── 자유 탐색 대화 시스템 프롬프트 ───────────────────
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

# ── WoZ 오류 설정 ──────────────────────────────────────
# 오류1: 첫 번째 퍼센트 수치를 0.4배로 축소 (심각성 희석)
# 오류2: 허위 출처 삽입
FAKE_SOURCE = (
    "UNEP(유엔환경계획)의 『2023 글로벌 패션산업 지속가능성 백서 제3장』에 따르면, "
    "Fast Fashion 브랜드의 자발적 전환만으로는 산업 전체 탄소 감축 목표의 12%만 달성 가능하다고 분석됩니다. "
)

FAKE_SOURCE_TASK2 = (
    "국제전자산업협회(GESC)의 『2023 글로벌 전자 폐기물 현황 보고서 제5장』에 따르면, "
    "제조사의 자발적 수거 프로그램만으로는 전자 폐기물 감축 목표의 15%만 달성 가능하다고 분석됩니다. "
)


def get_ai_response(user_text: str, task_number: int = 1) -> str:
    """WoZ AI 응답 — task_number에 따라 system prompt 분기"""
    system = SYSTEM_PROMPT_TASK1 if task_number == 1 else SYSTEM_PROMPT_TASK2
    client = anthropic.Anthropic(api_key=st.secrets["anthropic_api_key"])
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": user_text}]
    )
    return message.content[0].text


def apply_woz(original: str, task_number: int = 1):
    """
    WoZ 후처리: 두 가지 오류 삽입.
    오류1: 첫 번째 퍼센트 수치를 0.4배로 축소
    오류2: 허위 출처 삽입

    Returns:
        displayed_text, e1_original, e1_modified, e2_inserted
    """
    text = original
    e1_original = ""
    e1_modified = ""
    e2_inserted = False

    # 오류1: 퍼센트 수치 축소
    pattern = r'(\d+(?:\.\d+)?)\s*(%|퍼센트)'
    match = re.search(pattern, text)
    if match:
        original_val_str = match.group(1)
        unit = match.group(2)
        original_val = float(original_val_str)
        modified_val = round(original_val * 0.4, 1)
        modified_str = str(int(modified_val)) if modified_val == int(modified_val) else str(modified_val)
        e1_original = f"{original_val_str}{unit}"
        e1_modified = f"{modified_str}{unit}"
        text = text[:match.start()] + modified_str + unit + text[match.end():]

    # 오류2: 허위 출처 삽입
    fake = FAKE_SOURCE if task_number == 1 else FAKE_SOURCE_TASK2
    paragraphs = text.strip().split('\n\n')
    if len(paragraphs) >= 2:
        paragraphs[1] = fake + paragraphs[1]
        text = '\n\n'.join(paragraphs)
        e2_inserted = True
    else:
        sentences = text.split('. ')
        mid = max(1, len(sentences) // 2)
        sentences.insert(mid, fake.rstrip())
        text = '. '.join(sentences)
        e2_inserted = True

    return text, e1_original, e1_modified, e2_inserted


def get_free_chat_response(
    chat_history: list,
    task_number: int = 1,
    pre_framing: str = ""
) -> str:
    """자유 탐색 대화 — WoZ 없는 실제 Claude 응답"""
    system = FREE_CHAT_SYSTEM_TASK1 if task_number == 1 else FREE_CHAT_SYSTEM_TASK2
    client = anthropic.Anthropic(api_key=st.secrets["anthropic_api_key"])

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

    messages.extend(chat_history)

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        system=system,
        messages=messages
    )
    return message.content[0].text
