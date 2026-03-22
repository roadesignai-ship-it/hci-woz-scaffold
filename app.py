import streamlit as st
import time
from datetime import datetime
from utils.claude_api import get_ai_response, apply_woz, get_free_chat_response
from utils.scoring import compute_scores
from utils.sheets import save_to_sheets

st.set_page_config(
    page_title="Fast Fashion 디자인 연구",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── 시간 설정 (분 단위 조정 가능) ─────────────────────
TASK_READ_SECONDS = 180   # 과제+배경자료 읽기: 3분
MIN_PRE_CHARS     = 80    # Pre-framing 최소 글자
MIN_FINAL_CHARS   = 80    # 최종 제안 최소 글자
MIN_VERIF_CHARS   = 20    # scaffold1 최소 글자
MIN_COUNTER_CHARS = 40    # scaffold2 최소 글자
MIN_REFLECT_CHARS = 20    # scaffold3 최소 글자

# ── 진행률 표시 ────────────────────────────────────────
STEPS = ["시작", "과제 설명", "사전 분석", "자유 탐색", "AI 피드백", "최종 제안", "사후 질문", "완료"]

def show_progress(step_index):
    st.progress(step_index / (len(STEPS) - 1))
    cols = st.columns(len(STEPS))
    for i, label in enumerate(STEPS):
        with cols[i]:
            if i < step_index:
                st.markdown(
                    f"<p style='text-align:center;color:#1D9E75;font-size:12px'>✓ {label}</p>",
                    unsafe_allow_html=True)
            elif i == step_index:
                st.markdown(
                    f"<p style='text-align:center;font-weight:bold;font-size:12px'>▶ {label}</p>",
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<p style='text-align:center;color:#aaa;font-size:12px'>{label}</p>",
                    unsafe_allow_html=True)
    st.divider()

# ── Within-subject 조건 및 과제 순서 결정 ──────────────
# 홀수 번호: Task1=VELOX(A) → Task2=NOVA(B)
# 짝수 번호: Task1=NOVA(B)  → Task2=VELOX(A)
def get_condition(pid: int, task_number: int) -> str:
    if pid % 2 == 1:  # 홀수
        return "A" if task_number == 1 else "B"
    else:             # 짝수
        return "B" if task_number == 1 else "A"

def get_brand(pid: int, task_number: int) -> str:
    """홀수: VELOX→NOVA / 짝수: NOVA→VELOX"""
    if pid % 2 == 1:
        return "VELOX" if task_number == 1 else "NOVA"
    else:
        return "NOVA" if task_number == 1 else "VELOX"

# ── session_state 초기화 ───────────────────────────────
defaults = {
    "step": "start",
    "participant_id": None,
    "student_name": "",
    "student_number": "",
    "task_number": 1,
    "condition": None,
    "pre_framing": "",
    "ai_response_original": "",
    "ai_response_displayed": "",
    "woz_error1_original": "",
    "woz_error1_modified": "",
    "woz_error2_inserted": False,
    "confidence_score": 3,
    "verification_text": "",
    "counterfactual_text": "",
    "reflection_text": "",
    "final_output": "",
    "task_start_time": None,
    "scaffold1_done": False,
    "scaffold2_done": False,
    "scaffold3_done": False,
    "chat_history": [],   # 자유 탐색 대화 로그
    "chat_count": 0,      # 주고받은 횟수
    # 사후 질문 (task마다 초기화)
    "post_q1": 3,   # AI 수치 신뢰도
    "post_q2": 3,   # AI 출처 신뢰도
    "post_q3": 3,   # 검증 필요 느낌
    "post_q4": 3,   # 최종 제안 수정 정도
    "post_q5": 3,   # AI vs 내 분석 가까움
    "post_q6": "",  # 의심스러운 부분 서술
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════
# STEP 1 — 시작 화면
# ══════════════════════════════════════════════════════
if st.session_state.step == "start":
    show_progress(0)
    st.title("👗 Fast Fashion & 지속가능한 서비스 디자인")

    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.markdown("""
        본 연구는 AI 도구를 활용한 서비스 디자인 과정을 탐구합니다.  
        수집된 데이터는 연구 목적으로만 사용되며 익명으로 처리됩니다.
        """)
        st.warning("⚠️ 실험 중 브라우저 뒤로가기 또는 새로고침을 하면 데이터가 초기화됩니다.")
    with col_r:
        st.info("⏱️ 예상 소요 시간: **20~25분**")

    with st.form("start_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("이름", placeholder="홍길동")
        with col2:
            student_num = st.text_input("학번", placeholder="20241234")
        pid = st.number_input(
            "참가자 번호 (연구자에게 배정받은 번호, 1~40)",
            min_value=1, max_value=40, step=1
        )
        agree = st.checkbox(
            "본 연구의 목적과 절차를 이해하였으며, 자발적으로 참여에 동의합니다."
        )
        submitted = st.form_submit_button("실험 시작 →", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("이름을 입력해 주세요.")
            elif not student_num.strip():
                st.error("학번을 입력해 주세요.")
            elif not agree:
                st.error("동의서에 체크해 주세요.")
            else:
                st.session_state.participant_id = int(pid)
                st.session_state.student_name = name.strip()
                st.session_state.student_number = student_num.strip()
                st.session_state.task_number = 1
                st.session_state.condition = get_condition(int(pid), 1)
                st.session_state.task_start_time = time.time()
                st.session_state.step = "task_intro"
                st.rerun()

# ══════════════════════════════════════════════════════
# STEP 2 — 과제 설명 (타이머 3분)
# ══════════════════════════════════════════════════════
elif st.session_state.step == "task_intro":
    show_progress(1)
    task_num = st.session_state.task_number
    cond = st.session_state.condition
    pid = st.session_state.participant_id
    brand_intro = get_brand(pid, task_num)
    st.subheader(f"📋 과제 {task_num}/2 안내 및 배경 자료")
    st.caption(f"{'첫 번째' if task_num == 1 else '두 번째'} 과제입니다. "
               f"조건: {'기본 인터페이스' if cond == 'A' else '심화 인터페이스'}")

    # ── 과제별 배경 자료 분기 ───────────────────────────
    if brand_intro == "VELOX":
        # VELOX (Fast Fashion)
        st.markdown("""
        #### 📰 [업계 리포트] VELOX, 성장의 이면에 드리운 지속가능성 위기
        *2024년 패션 산업 지속가능성 연구소(FSRI) 분기 보고서 요약*
        """)
        with st.expander("▶ 전체 기사 읽기 (클릭하여 펼치기)", expanded=True):
            st.markdown("""
            **글로벌 Fast Fashion 산업의 환경 위기**

            전 세계 패션 산업은 매년 약 920억 벌의 의류를 생산하며, 이 중 약 30%가 팔리지 않은 채 폐기된다.
            패션 산업이 배출하는 온실가스는 전 세계 총배출량의 약 10%에 달하며, 이는 국제 항공과 해운을 합친 것보다 많다.
            의류 1kg을 생산하는 데 평균 약 10,000리터의 물이 소비되고, 전 세계 폐수의 약 20%가 직물 염색 및 처리 과정에서 발생한다.
            패션 산업에서 사용되는 합성섬유는 세탁 시 매년 약 50만 톤의 미세플라스틱을 해양에 방류하는 것으로 추정된다.

            **VELOX의 현황과 사업 구조**

            VELOX는 2008년 설립된 가상의 글로벌 Fast Fashion 브랜드로, 연간 약 4,200만 벌의 의류를 생산한다.
            주요 소비층은 18~35세이며, 전체 매출의 72%가 온라인 채널에서 발생한다.
            생산 기지는 방글라데시, 베트남, 캄보디아에 집중되어 있으며, 협력 공장 노동자의 평균 시급은 약 0.85~1.2달러이다.
            VELOX의 컬렉션 출시 주기는 연 52회이며, 반품된 의류의 약 40%는 소각 또는 매립 처리된다.

            **이해관계자 반응과 압력**

            국제 환경단체 GreenWear는 VELOX를 상대로 대규모 캠페인을 전개했다.
            소비자 단체 설문에서 VELOX 주요 소비층의 61%가 환경 정책 미개선 시 구매를 줄이겠다고 응답했다.
            EU는 2025년부터 패션 기업의 제품 수명 주기 데이터 공개를 의무화한다.

            **VELOX의 현재 대응과 한계**

            VELOX는 2030년 탄소 중립을 선언했으나, 실제 탄소 배출량은 전년 대비 3% 증가했다.
            일부 제품 라인에 재활용 소재를 5~10% 혼합하는 수준으로 그린워싱 비판을 받고 있다.
            """)
        st.divider()
        st.markdown("**주요 이해관계자**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            - 💰 **소비자**: 가격 민감, 트렌드 추구, 환경 인식 증가
            - 🏭 **생산 노동자**: 저임금(시급 $0.85~1.2), 劣악한 환경
            """)
        with col2:
            st.markdown("""
            - 📣 **마케팅팀**: 매출 압박, 브랜드 이미지 위기
            - 🌿 **환경 NGO**: 투명성 요구, 그린워싱 비판
            """)
        st.divider()
        st.markdown("""
        ### 과제
        위 배경 자료를 바탕으로, AI의 데이터 분석을 참고하여
        **VELOX가 직면한 핵심 지속가능성 문제를 정의**하세요.

        좋은 문제 정의는 다음을 포함합니다:
        - 가장 중요한 문제가 무엇인지 명확히 진술
        - 데이터나 이해관계자 상황을 근거로 제시
        - 왜 지금 이 문제가 시급한지 설명
        """)

    else:
        # NOVA (전자 폐기물)
        st.markdown("""
        #### 📰 [업계 리포트] NOVA, 전자 폐기물의 그늘 속에서 성장하는 테크 브랜드
        *2024년 글로벌 전자산업 지속가능성 연구센터(GESC) 분기 보고서 요약*
        """)
        with st.expander("▶ 전체 기사 읽기 (클릭하여 펼치기)", expanded=True):
            st.markdown("""
            **글로벌 전자 폐기물(E-Waste) 위기**

            전 세계에서 매년 약 5,740만 톤의 전자 폐기물이 발생하며, 이는 역대 최고치다.
            전자 폐기물의 약 83%가 비공식 경로로 처리되며, 납·수은·카드뮴 등 유해물질이 토양과 수질을 오염시킨다.
            스마트폰 한 대를 생산하는 데 약 70kg의 원자재가 사용되며, 그 중 희토류는 채굴 과정에서 심각한 환경 파괴를 일으킨다.
            전자기기의 평균 사용 수명은 2000년 대비 절반 수준으로 단축되었으며, 계획적 진부화(planned obsolescence)가 주요 원인으로 지목된다.

            **NOVA의 현황과 사업 구조**

            NOVA는 2012년 설립된 가상의 소비자 전자기기 브랜드로, 연간 약 1,200만 대의 스마트폰·태블릿·노트북을 판매한다.
            주요 소비층은 20~40세 도시 직장인이며, 평균 제품 교체 주기는 18개월이다.
            부품 조립은 인도네시아, 멕시코, 폴란드의 협력 공장에서 이루어지며, 광물 채굴은 콩고민주공화국과 칠레에서 하청된다.
            NOVA 제품의 수리 가능성 점수(Repairability Index)는 10점 만점에 3.2점으로 업계 최하위권이다.
            회수된 기기의 재활용률은 약 18%에 불과하며, 나머지는 소비자가 임의 폐기한다.

            **이해관계자 반응과 압력**

            국제 환경단체 E-Watch는 NOVA를 "수리 불가능 설계로 폐기물을 양산하는 브랜드" 1위로 선정했다.
            EU 집행위원회는 2026년부터 전자기기 제조사에 10년간 부품 공급 의무와 수리권(Right to Repair)을 법제화할 예정이다.
            콩고민주공화국 광산 인근 주민 단체가 NOVA의 공급망 투명성 부재를 국제기구에 제소했다.
            소비자 조사에서 NOVA 구매자의 54%가 "수리 서비스가 있다면 기기를 3년 이상 사용하겠다"고 응답했다.

            **NOVA의 현재 대응과 한계**

            NOVA는 2023년 "GreenCircle" 프로그램을 출시하며 2035년까지 탄소 중립과 재활용률 50% 달성을 약속했다.
            그러나 현재 운영되는 공식 수거함은 전국 12개 매장에 불과하며, 실질적 재활용률 개선은 미미하다.
            수리 부품 공급을 의도적으로 제한하는 정책을 유지하고 있어 독립 수리업체와의 분쟁이 계속되고 있다.
            """)
        st.divider()
        st.markdown("**주요 이해관계자**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            - 💻 **소비자**: 최신 기기 선호, 수리 의향 있음
            - 🔧 **독립 수리업체**: 부품 공급 차단으로 생존 위협
            """)
        with col2:
            st.markdown("""
            - 📣 **마케팅팀**: 프리미엄 이미지, ESG 압박
            - 🌿 **환경 NGO**: 수리권 입법 요구, 공급망 투명성
            """)
        st.divider()
        st.markdown("""
        ### 과제
        위 배경 자료를 바탕으로, AI의 데이터 분석을 참고하여
        **NOVA가 직면한 핵심 전자 폐기물 문제를 정의**하세요.

        좋은 문제 정의는 다음을 포함합니다:
        - 가장 중요한 문제가 무엇인지 명확히 진술
        - 데이터나 이해관계자 상황을 근거로 제시
        - 왜 지금 이 문제가 시급한지 설명
        """)

    if "countdown_start" not in st.session_state:
        st.session_state.countdown_start = time.time()

    elapsed = int(time.time() - st.session_state.countdown_start)
    remaining = max(0, TASK_READ_SECONDS - elapsed)

    if remaining > 0:
        mins, secs = divmod(remaining, 60)
        st.info(f"⏱️ 배경 자료를 충분히 읽어 주세요. ({mins}분 {secs:02d}초 후 다음 단계 활성화)")
        time.sleep(1)
        st.rerun()
    else:
        if st.button("자료를 읽었습니다 → 초기 분석 작성", use_container_width=True, type="primary"):
            del st.session_state.countdown_start
            st.session_state.step = "pre_framing"
            st.rerun()

# ══════════════════════════════════════════════════════
# STEP 3 — Pre-AI Framing (목표 5분)
# ══════════════════════════════════════════════════════
elif st.session_state.step == "pre_framing":
    show_progress(2)
    task_num_pre = st.session_state.task_number
    brand_pre = get_brand(st.session_state.participant_id, task_num_pre)
    st.subheader("1단계: AI 피드백 전 초기 분석")
    st.markdown(f"""
    방금 읽은 배경 자료를 바탕으로, AI 피드백을 받기 **전에** {brand_pre}의 핵심 문제를 정의해 주세요. ({MIN_PRE_CHARS}자 이상)

    아래 질문을 참고하되, 자유롭게 서술해도 됩니다.
    - **{brand_pre}가 직면한 가장 핵심적인** 지속가능성 문제는 무엇인가요?
    - 그 문제의 **근거**(데이터, 이해관계자 영향)는 무엇인가요?
    - 왜 **지금** 이 문제를 해결해야 하나요?
    """)

    _placeholder_pre = (
        "예) VELOX의 핵심 문제는 과잉 생산으로 인한 탄소 배출 증가이며, "
        "소비자 행동 변화와 생산 구조 개혁이 동시에 필요한 구조적 문제입니다..."
        if brand_pre == "VELOX" else
        "예) NOVA의 핵심 문제는 수리 불가능 설계로 인한 전자 폐기물 급증이며, "
        "EU 수리권 법제화 압박과 소비자 인식 변화가 맞물린 구조적 전환점에 있습니다..."
    )
    text = st.text_area(
        f"초기 분석 ({MIN_PRE_CHARS}자 이상)",
        height=200,
        placeholder=_placeholder_pre,
        value=st.session_state.pre_framing
    )
    char_count = len(text)
    st.caption(f"현재 {char_count}자 / 최소 {MIN_PRE_CHARS}자")

    col1, col2 = st.columns([3, 1])
    with col2:
        elapsed = int(time.time() - st.session_state.task_start_time)
        st.caption(f"경과 시간: {elapsed//60}분 {elapsed%60:02d}초")

    if char_count >= MIN_PRE_CHARS:
        if st.button("AI 피드백 받기 →", use_container_width=True, type="primary"):
            st.session_state.pre_framing = text
            st.session_state.chat_history = []
            st.session_state.chat_count = 0
            st.session_state.step = "free_chat"
            st.rerun()
    else:
        st.button("AI 피드백 받기 →", disabled=True, use_container_width=True)

# ══════════════════════════════════════════════════════
# STEP 4 — AI 응답 + 조건별 Scaffold (목표 8분)
# ══════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════
# STEP FREE_CHAT — 자유 탐색 대화
# ══════════════════════════════════════════════════════
elif st.session_state.step == "free_chat":
    show_progress(3)
    task_num = st.session_state.task_number
    brand = get_brand(st.session_state.participant_id, task_num)
    CHAT_SECONDS = 120  # 자유 탐색 시간: 2분

    st.subheader(f"2단계: {brand} 자유 탐색 대화")
    st.markdown(f"""
    AI와 자유롭게 대화하며 **{brand}**의 문제를 더 깊이 탐색해 보세요.  
    배경 자료에서 궁금한 점, 데이터의 의미, 이해관계자 관계 등 무엇이든 질문할 수 있습니다.
    """)

    # 타이머 시작 시각 기록 (최초 1회만)
    if "chat_timer_start" not in st.session_state or st.session_state.get("chat_timer_task") != task_num:
        st.session_state.chat_timer_start = time.time()
        st.session_state.chat_timer_task = task_num  # task별 타이머 구분

    elapsed = int(time.time() - st.session_state.chat_timer_start)
    remaining = max(0, CHAT_SECONDS - elapsed)
    timer_done = remaining == 0

    # 타이머 상태 표시
    if not timer_done:
        mins, secs = divmod(remaining, 60)
        st.info(f"⏱️ 자유 탐색 시간: {mins}분 {secs:02d}초 남음 — 자유롭게 질문하세요.")
    else:
        st.success("✅ 탐색 시간이 완료되었습니다. 다음 단계로 이동할 수 있습니다.")

    # 대화 이력 표시
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 채팅 입력 (타이머 전후 모두 가능)
    user_input = st.chat_input("질문이나 아이디어를 입력하세요...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.session_state.chat_count += 1
        _free_task = 1 if get_brand(st.session_state.participant_id, task_num) == "VELOX" else 2
        with st.spinner("AI 응답 생성 중..."):
            reply = get_free_chat_response(
                st.session_state.chat_history,
                task_number=_free_task,
                pre_framing=st.session_state.pre_framing
            )
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()

    st.divider()

    # 다음 단계 버튼
    if timer_done:
        if st.button("탐색 완료 → AI 최종 분석 받기",
                     use_container_width=True, type="primary"):
            del st.session_state.chat_timer_start
            if "chat_timer_task" in st.session_state:
                del st.session_state.chat_timer_task
            with st.spinner("AI 최종 분석 생성 중..."):
                _api_task = 1 if get_brand(st.session_state.participant_id, task_num) == "VELOX" else 2
                original = get_ai_response(
                    st.session_state.pre_framing, _api_task)
                st.session_state.ai_response_original = original
                displayed, e1_orig, e1_mod, e2 = apply_woz(original, _api_task)
                st.session_state.ai_response_displayed = displayed
                st.session_state.woz_error1_original = e1_orig
                st.session_state.woz_error1_modified = e1_mod
                st.session_state.woz_error2_inserted = e2
            st.session_state.step = "ai_response"
            st.rerun()
    else:
        st.button("탐색 완료 → AI 최종 분석 받기",
                  disabled=True, use_container_width=True)
        st.caption(f"⚠️ {remaining}초 후 활성화됩니다.")
        # 타이머 자동 갱신 — 채팅 입력이 없을 때만
        if not user_input:
            time.sleep(1)
            st.rerun()

elif st.session_state.step == "ai_response":
    show_progress(3)
    condition = st.session_state.condition
    st.subheader("2단계: AI 피드백 검토")

    # ── Condition A: 일반 텍스트로 표시, scaffold 없음 ──
    if condition == "A":
        with st.expander("💬 AI 분석 결과", expanded=True):
            st.markdown(st.session_state.ai_response_displayed)
        st.divider()
        st.markdown("AI 분석을 검토한 후 최종 제안을 작성해 주세요.")
        if st.button("최종 제안 작성 →", use_container_width=True, type="primary"):
            st.session_state.step = "final_output"
            st.rerun()

    # ── Condition B: 인라인 friction — Streamlit 네이티브 ─
    else:
        import re
        ai_text = st.session_state.ai_response_displayed
        woz_num = st.session_state.woz_error1_modified

        # ① 변조 수치 하이라이트 (HTML 표시용)
        highlighted = ai_text
        if woz_num:
            highlighted = re.sub(
                re.escape(woz_num),
                f'<span style="background:#fff3cd;color:#856404;padding:1px 4px;'
                f'border-radius:3px;border-bottom:2px dashed #e6a817;">'
                f'⚠️ {woz_num}</span>',
                highlighted
            )

        # 단락 분리
        paragraphs = highlighted.strip().split('\n\n')
        mid = max(1, len(paragraphs) // 2)
        first_half = '<br><br>'.join(paragraphs[:mid])
        second_half = '<br><br>'.join(paragraphs[mid:])

        # AI 응답 전반부 표시
        st.markdown("**💬 AI 분석 결과**")
        st.markdown(
            f'<div style="background:#f8f9fa;border-left:3px solid #1D9E75;'
            f'border-radius:0 8px 8px 0;padding:16px 20px;line-height:1.75;">'
            f'{first_half}</div>',
            unsafe_allow_html=True
        )

        # ② friction 1 — 마이크로 프롬프트 (st.radio)
        st.markdown("")
        gate1 = st.radio(
            "💬 지금까지 읽은 내용에서 **의심되거나 확인이 필요한 부분**이 있나요?",
            ["선택하세요", "있다", "없다", "잘 모르겠다"],
            index=0,
            key="gate1_radio",
            horizontal=True
        )

        # gate1 답변 후 후반부 표시
        if gate1 != "선택하세요":
            st.session_state.verification_text = gate1

            st.markdown(
                f'<div style="background:#f8f9fa;border-left:3px solid #1D9E75;'
                f'border-radius:0 8px 8px 0;padding:16px 20px;line-height:1.75;">'
                f'{second_half}</div>',
                unsafe_allow_html=True
            )

            # ③ friction 2 — 출처 확인 의향 (st.radio)
            st.markdown("")
            gate2 = st.radio(
                "🔍 AI가 인용한 통계나 출처 중 **직접 검색해서 확인하고 싶은 것**이 있나요?",
                ["선택하세요", "있다", "없다"],
                index=0,
                key="gate2_radio",
                horizontal=True
            )

            if gate2 != "선택하세요":
                st.session_state.reflection_text = gate2
                st.session_state.scaffold1_done = True
                st.session_state.scaffold2_done = True
                st.session_state.scaffold3_done = True

        st.divider()
        if st.session_state.scaffold1_done:
            if st.button("최종 제안 작성 →", use_container_width=True, type="primary"):
                st.session_state.step = "final_output"
                st.rerun()
        else:
            st.button("최종 제안 작성 →", disabled=True, use_container_width=True)
            st.caption("⚠️ 두 질문에 모두 답변해야 다음 단계로 이동할 수 있습니다.")
# ══════════════════════════════════════════════════════
# STEP 5 — 최종 제안 작성 (목표 7분)
# ══════════════════════════════════════════════════════
elif st.session_state.step == "final_output":
    show_progress(4)
    task_num_f = st.session_state.task_number
    brand_f = get_brand(st.session_state.participant_id, task_num_f)
    st.subheader("3단계: 최종 문제 정의")
    st.markdown(f"""
    AI 피드백을 검토한 후, **{brand_f}의 핵심 문제를 최종적으로 정의**해 주세요. ({MIN_FINAL_CHARS}자 이상)

    다음 세 가지를 포함해 주세요:
    - **핵심 문제**: {brand_f}가 직면한 가장 중요한 문제는 무엇인가?
    - **근거**: 어떤 데이터나 이해관계자 상황이 이를 뒷받침하는가?
    - **시급성**: 왜 지금 이 문제를 해결해야 하는가?
    """)

    col1, col2 = st.columns([1, 1], gap="medium")
    with col1:
        st.markdown("##### 💬 AI 분석 (참고용)")
        st.markdown(
            f"<div style='padding:1rem;border-radius:8px;font-size:13px;"
            f"height:280px;overflow-y:auto;"
            f"border:1px solid var(--color-border-tertiary,#eee)'>"
            f"{st.session_state.ai_response_displayed}</div>",
            unsafe_allow_html=True
        )
    with col2:
        st.markdown("##### ✏️ 최종 제안")
        final = st.text_area(
            "최종 제안",
            height=280,
            placeholder=(
                "예) VELOX의 핵심 문제는 연간 4,200만 벌 생산 중 40%가 소각되는 "
                "과잉 생산 구조입니다. 이는 단순한 환경 문제가 아니라..."
                if brand_f == "VELOX" else
                "예) NOVA의 핵심 문제는 수리 불가능 설계로 연간 수백만 대가 조기 폐기되는 "
                "구조적 낭비입니다. 이는 제조사의 의도적 설계 선택과 맞닿아 있으며..."
            ),
            value=st.session_state.final_output,
            label_visibility="collapsed"
        )

    char_count = len(final)
    elapsed = int(time.time() - st.session_state.task_start_time)
    col_char, col_time = st.columns([3, 1])
    with col_char:
        st.caption(f"현재 {char_count}자 / 최소 {MIN_FINAL_CHARS}자")
    with col_time:
        st.caption(f"경과: {elapsed//60}분 {elapsed%60:02d}초")

    if char_count >= MIN_FINAL_CHARS:
        if st.button("제출하기 ✓", use_container_width=True, type="primary"):
            st.session_state.final_output = final
            duration = int(time.time() - st.session_state.task_start_time)

            scores = compute_scores(
                condition=st.session_state.condition,
                ai_displayed=st.session_state.ai_response_displayed,
                pre_framing=st.session_state.pre_framing,
                final_output=final,
                confidence_score=st.session_state.confidence_score,
                verification_text=st.session_state.verification_text,
                counterfactual_text=st.session_state.counterfactual_text,
                reflection_text=st.session_state.reflection_text,
                woz_error1_modified=st.session_state.woz_error1_modified,
                woz_error2_inserted=st.session_state.woz_error2_inserted,
            )

            row = {
                "timestamp": datetime.now().isoformat(),
                "participant_id": st.session_state.participant_id,
                "student_name": st.session_state.student_name,
                "student_number": st.session_state.student_number,
                "condition": st.session_state.condition,
                "task_number": st.session_state.task_number,
                "brand": get_brand(st.session_state.participant_id, st.session_state.task_number),
                "pre_framing_text": st.session_state.pre_framing,
                "pre_framing_length": len(st.session_state.pre_framing),
                "ai_response_original": st.session_state.ai_response_original,
                "ai_response_displayed": st.session_state.ai_response_displayed,
                "woz_error1_original": st.session_state.woz_error1_original,
                "woz_error1_modified": st.session_state.woz_error1_modified,
                "woz_error2_inserted": st.session_state.woz_error2_inserted,
                "confidence_score": st.session_state.confidence_score,
                "verification_text": st.session_state.verification_text,
                "counterfactual_text": st.session_state.counterfactual_text,
                "reflection_text": st.session_state.reflection_text,
                "final_output_text": final,
                "uar_score": scores["uar"],
                "vaf_score": scores["vaf"],
                "ri_score": scores["ri"],
                "cag_score": scores["cag"],
                "session_duration_seconds": duration,
            }

            with st.spinner("저장 중..."):
                save_to_sheets(row)

            # within-subject: Task1 완료 → Task2로 전환
            # 최종 제안 제출 후 → 사후 질문으로 이동
            st.session_state.step = "post_survey"
            st.rerun()
    else:
        st.button("문제 정의 제출 ✓", disabled=True, use_container_width=True)

# ══════════════════════════════════════════════════════
# STEP 6 — 사후 질문 (Task마다)
# ══════════════════════════════════════════════════════
elif st.session_state.step == "post_survey":
    show_progress(5)
    task_num = st.session_state.task_number
    cond = st.session_state.condition
    st.subheader(f"과제 {task_num} 사후 질문")
    _brand_post = get_brand(st.session_state.participant_id, task_num)
    st.markdown(f"방금 완료한 **{_brand_post} 과제**에 대해 솔직하게 답해주세요. (약 3분)")
    st.caption("1 = 전혀 그렇지 않다 / 5 = 매우 그렇다")
    st.divider()

    with st.form(f"post_survey_{task_num}"):
        st.markdown("**AI 응답 신뢰도**")
        q1 = st.slider("Q1. AI가 제시한 통계 수치를 신뢰했나요?",
                        1, 5, st.session_state.post_q1, key=f"q1_{task_num}")
        q2 = st.slider("Q2. AI가 인용한 보고서나 기관 출처를 신뢰했나요?",
                        1, 5, st.session_state.post_q2, key=f"q2_{task_num}")
        st.divider()
        st.markdown("**검증 및 비판적 사고**")
        q3 = st.slider("Q3. AI 응답을 읽으면서 직접 확인하고 싶은 내용이 생겼나요?",
                        1, 5, st.session_state.post_q3, key=f"q3_{task_num}")
        q4 = st.slider("Q4. 문제 정의 작성 시 AI 응답의 내용을 수정하거나 다르게 해석한 부분이 있었나요?",
                        1, 5, st.session_state.post_q4, key=f"q4_{task_num}")
        st.divider()
        st.markdown("**자기 주체성**")
        q5 = st.slider("Q5. 최종 문제 정의가 AI 응답보다 본인의 초기 분석에 더 가깝다고 생각하나요?",
                        1, 5, st.session_state.post_q5,
                        key=f"q5_{task_num}",
                        help="1 = AI 응답에 더 가깝다 / 5 = 내 초기 분석에 더 가깝다")
        st.divider()
        st.markdown("**서술형**")
        q6 = st.text_area(
            "Q6. AI가 제시한 데이터나 출처 중 의심스럽거나 직접 확인하고 싶었던 부분이 있었다면 적어주세요. (없으면 공란)",
            height=80,
            value=st.session_state.post_q6,
            key=f"q6_{task_num}"
        )

        submitted = st.form_submit_button("제출 →", use_container_width=True, type="primary")
        if submitted:
            st.session_state.post_q1 = q1
            st.session_state.post_q2 = q2
            st.session_state.post_q3 = q3
            st.session_state.post_q4 = q4
            st.session_state.post_q5 = q5
            st.session_state.post_q6 = q6

            # 사후 질문 데이터를 기존 row에 추가해서 Sheets 업데이트
            from utils.sheets import update_post_survey
            update_post_survey(
                participant_id=st.session_state.participant_id,
                task_number=task_num,
                q1=q1, q2=q2, q3=q3, q4=q4, q5=q5, q6=q6
            )

            # Task 전환 또는 완료
            if task_num == 1:
                st.session_state.task_number = 2
                st.session_state.condition = get_condition(
                    st.session_state.participant_id, 2)
                # chat_timer_start는 key-value reset 전에 별도 삭제
                if "chat_timer_start" in st.session_state:
                    del st.session_state.chat_timer_start
                if "chat_timer_task" in st.session_state:
                    del st.session_state.chat_timer_task
                for key in ["pre_framing", "ai_response_original",
                            "ai_response_displayed", "woz_error1_original",
                            "woz_error1_modified", "woz_error2_inserted",
                            "confidence_score", "verification_text",
                            "counterfactual_text", "reflection_text",
                            "final_output", "scaffold1_done",
                            "scaffold2_done", "scaffold3_done",
                            "chat_history", "chat_count",
                            "post_q1", "post_q2", "post_q3",
                            "post_q4", "post_q5", "post_q6"]:
                    st.session_state[key] = defaults[key]
                st.session_state.task_start_time = time.time()
                st.session_state.step = "task_intro"
            else:
                st.session_state.step = "done"
            st.rerun()

# ══════════════════════════════════════════════════════
# STEP 7 — 완료
# ══════════════════════════════════════════════════════
elif st.session_state.step == "done":
    show_progress(5)
    st.balloons()
    st.success("## 🎉 완료되었습니다!")
    duration = int(time.time() - st.session_state.task_start_time) if st.session_state.task_start_time else 0
    st.markdown(f"""
    **{st.session_state.student_name}** ({st.session_state.student_number}) — 두 과제를 모두 완료하셨습니다.  
    참가자 번호: {st.session_state.participant_id}번 / 총 소요 시간: **{duration//60}분 {duration%60:02d}초**  
    연구자에게 완료 사실을 알려주세요.
    """)
    if st.button("처음으로 (다음 참가자용)", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
