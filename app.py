import streamlit as st
import time
from datetime import datetime
from utils.claude_api import get_ai_response, apply_woz
from utils.scoring import compute_scores
from utils.sheets import save_to_sheets

st.set_page_config(
    page_title="Fast Fashion 디자인 연구",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── 시간 설정 (분 단위 조정 가능) ─────────────────────
TASK_READ_SECONDS = 180   # 과제 설명 읽기: 3분
MIN_PRE_CHARS     = 80    # Pre-framing 최소 글자
MIN_FINAL_CHARS   = 80    # 최종 제안 최소 글자
MIN_VERIF_CHARS   = 20    # scaffold1 최소 글자
MIN_COUNTER_CHARS = 40    # scaffold2 최소 글자
MIN_REFLECT_CHARS = 20    # scaffold3 최소 글자

# ── 진행률 표시 ────────────────────────────────────────
STEPS = ["시작", "과제 설명", "사전 분석", "AI 피드백", "최종 제안", "완료"]

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

# ── Between-subject 조건 결정 ──────────────────────────
# 1반 (번호 1~20)  → Condition B: Scaffolded
# 2반 (번호 21~40) → Condition A: Baseline
# 두 조건 모두 동일한 WoZ 오류 포함 AI 응답
def get_condition(pid: int) -> str:
    return "B" if pid <= 20 else "A"

# ── session_state 초기화 ───────────────────────────────
defaults = {
    "step": "start",
    "participant_id": None,
    "student_name": "",
    "student_number": "",
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
                st.session_state.condition = get_condition(int(pid))
                st.session_state.task_start_time = time.time()
                st.session_state.step = "task_intro"
                st.rerun()

# ══════════════════════════════════════════════════════
# STEP 2 — 과제 설명 (타이머 3분)
# ══════════════════════════════════════════════════════
elif st.session_state.step == "task_intro":
    show_progress(1)
    st.subheader("📋 과제 안내")

    st.markdown("""
    ### 시나리오

    당신은 가상의 Fast Fashion 브랜드 **"VELOX"** 의  
    지속가능성 전환 프로젝트에 참여한 서비스 디자인 컨설턴트입니다.

    **VELOX 브랜드 현황**
    - 연간 의류 생산량: 약 4,200만 벌
    - 주요 소비자: 18~35세, 온라인 구매 비중 72%
    - 생산 기지: 방글라데시, 베트남, 캄보디아
    - 최근 환경 단체로부터 과잉 생산 및 폐기 관련 비판 증가

    **주요 이해관계자**

    | 이해관계자 | 주요 관심사 |
    |---|---|
    | 💰 소비자 | 가격 민감, 트렌드 추구 |
    | 🏭 생산 노동자 | 저임금, 劣악한 작업 환경 |
    | 📣 브랜드 마케팅팀 | 매출 압박, 이미지 관리 |
    | 🌿 환경 NGO | 투명성 요구, 탄소 감축 압박 |

    ### 과제
    AI의 데이터 분석을 참고하여,  
    **VELOX가 지속가능성으로 전환하기 위한 서비스 시스템을 제안**하세요.
    """)

    if "countdown_start" not in st.session_state:
        st.session_state.countdown_start = time.time()

    elapsed = int(time.time() - st.session_state.countdown_start)
    remaining = max(0, TASK_READ_SECONDS - elapsed)

    if remaining > 0:
        mins, secs = divmod(remaining, 60)
        st.info(f"⏱️ 과제를 충분히 읽어 주세요. ({mins}분 {secs:02d}초 후 다음 단계 활성화)")
        time.sleep(1)
        st.rerun()
    else:
        if st.button("과제를 읽었습니다 → 다음", use_container_width=True, type="primary"):
            del st.session_state.countdown_start
            st.session_state.step = "pre_framing"
            st.rerun()

# ══════════════════════════════════════════════════════
# STEP 3 — Pre-AI Framing (목표 5분)
# ══════════════════════════════════════════════════════
elif st.session_state.step == "pre_framing":
    show_progress(2)
    st.subheader("1단계: AI 피드백 전 초기 분석")
    st.markdown(f"""
    AI 피드백을 받기 **전에**, 본인의 초기 분석을 작성해 주세요. ({MIN_PRE_CHARS}자 이상)

    - VELOX의 가장 핵심적인 지속가능성 문제는 무엇인가요?
    - 어떤 이해관계자부터 접근해야 할까요?
    - 어떤 서비스 개입이 효과적일 것 같나요?
    """)

    text = st.text_area(
        f"초기 분석 ({MIN_PRE_CHARS}자 이상)",
        height=200,
        placeholder="예) VELOX의 핵심 문제는 과잉 생산 구조에 있으며, 소비자와 생산자 양쪽에서...",
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
            with st.spinner("AI 분석 중... (10~20초 소요)"):
                original = get_ai_response(text)
                st.session_state.ai_response_original = original
                displayed, e1_orig, e1_mod, e2 = apply_woz(original)
                st.session_state.ai_response_displayed = displayed
                st.session_state.woz_error1_original = e1_orig
                st.session_state.woz_error1_modified = e1_mod
                st.session_state.woz_error2_inserted = e2
            st.session_state.step = "ai_response"
            st.rerun()
    else:
        st.button("AI 피드백 받기 →", disabled=True, use_container_width=True)

# ══════════════════════════════════════════════════════
# STEP 4 — AI 응답 + 조건별 Scaffold (목표 8분)
# ══════════════════════════════════════════════════════
elif st.session_state.step == "ai_response":
    show_progress(3)
    condition = st.session_state.condition
    st.subheader("2단계: AI 피드백 검토")

    with st.expander("💬 AI 분석 결과", expanded=True):
        st.markdown(st.session_state.ai_response_displayed)

    st.divider()

    # ── Condition A: scaffold 없이 바로 진행 ──────────
    if condition == "A":
        st.markdown("AI 분석을 검토한 후 최종 제안을 작성해 주세요.")
        if st.button("최종 제안 작성 →", use_container_width=True, type="primary"):
            st.session_state.step = "final_output"
            st.rerun()

    # ── Condition B: scaffold 3개 순서대로 ───────────
    else:
        st.markdown("#### 📝 아래 세 항목을 순서대로 완료해 주세요")

        # Scaffold 1 — Confidence Calibration
        with st.container(border=True):
            st.markdown("**[1/3] 신뢰도 평가**")
            conf = st.slider(
                "AI 분석을 얼마나 신뢰하시나요?",
                min_value=1, max_value=5,
                value=st.session_state.confidence_score,
                format="%d점"
            )
            st.caption("1 = 전혀 신뢰 안함 / 5 = 완전히 신뢰")
            verif = st.text_area(
                f"검증이 필요한 수치나 출처를 적어주세요 ({MIN_VERIF_CHARS}자 이상)",
                height=80,
                value=st.session_state.verification_text,
                key="verif_area"
            )
            if len(verif) >= MIN_VERIF_CHARS:
                st.session_state.confidence_score = conf
                st.session_state.verification_text = verif
                st.session_state.scaffold1_done = True
                st.success("✅ 완료")
            else:
                st.caption(f"{len(verif)}자 / {MIN_VERIF_CHARS}자")

        # Scaffold 2 — Counterfactual Challenge
        with st.container(border=True):
            st.markdown("**[2/3] 대안적 해석**")
            if not st.session_state.scaffold1_done:
                st.caption("⬆️ [1/3]을 먼저 완료해 주세요.")
            else:
                counter = st.text_area(
                    f"AI와 다른 대안적 서비스 방향을 작성해 주세요 ({MIN_COUNTER_CHARS}자 이상)",
                    height=100,
                    value=st.session_state.counterfactual_text,
                    key="counter_area"
                )
                if len(counter) >= MIN_COUNTER_CHARS:
                    st.session_state.counterfactual_text = counter
                    st.session_state.scaffold2_done = True
                    st.success("✅ 완료")
                else:
                    st.caption(f"{len(counter)}자 / {MIN_COUNTER_CHARS}자")

        # Scaffold 3 — Reflection
        with st.container(border=True):
            st.markdown("**[3/3] 비교 성찰**")
            if not st.session_state.scaffold2_done:
                st.caption("⬆️ [2/3]을 먼저 완료해 주세요.")
            else:
                reflection = st.text_area(
                    f"처음 분석과 AI 응답의 가장 큰 차이점은? ({MIN_REFLECT_CHARS}자 이상)",
                    height=80,
                    value=st.session_state.reflection_text,
                    key="reflect_area"
                )
                if len(reflection) >= MIN_REFLECT_CHARS:
                    st.session_state.reflection_text = reflection
                    st.session_state.scaffold3_done = True
                    st.success("✅ 완료")
                else:
                    st.caption(f"{len(reflection)}자 / {MIN_REFLECT_CHARS}자")

        st.divider()
        all_done = (st.session_state.scaffold1_done and
                    st.session_state.scaffold2_done and
                    st.session_state.scaffold3_done)
        if all_done:
            if st.button("최종 제안 작성 →", use_container_width=True, type="primary"):
                st.session_state.step = "final_output"
                st.rerun()
        else:
            st.button("최종 제안 작성 →", disabled=True, use_container_width=True)
            st.caption("⚠️ 세 항목을 모두 완료해야 합니다.")

# ══════════════════════════════════════════════════════
# STEP 5 — 최종 제안 작성 (목표 7분)
# ══════════════════════════════════════════════════════
elif st.session_state.step == "final_output":
    show_progress(4)
    st.subheader("3단계: 최종 서비스 디자인 제안")
    st.markdown(f"AI 피드백을 검토한 후, VELOX의 지속가능성 전환을 위한 최종 제안을 작성해 주세요. ({MIN_FINAL_CHARS}자 이상)")

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
            placeholder="AI 피드백을 검토한 후 최종 디자인 제안을 작성하세요...",
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
                woz_error1_modified=st.session_state.woz_error1_modified,
                woz_error2_inserted=st.session_state.woz_error2_inserted,
            )

            row = {
                "timestamp": datetime.now().isoformat(),
                "participant_id": st.session_state.participant_id,
                "student_name": st.session_state.student_name,
                "student_number": st.session_state.student_number,
                "condition": st.session_state.condition,
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

            st.session_state.step = "done"
            st.rerun()
    else:
        st.button("제출하기 ✓", disabled=True, use_container_width=True)

# ══════════════════════════════════════════════════════
# STEP 6 — 완료
# ══════════════════════════════════════════════════════
elif st.session_state.step == "done":
    show_progress(5)
    st.balloons()
    st.success("## 🎉 완료되었습니다!")
    duration = int(time.time() - st.session_state.task_start_time) if st.session_state.task_start_time else 0
    st.markdown(f"""
    **{st.session_state.student_name}** ({st.session_state.student_number}) — 실험을 완료하셨습니다.  
    참가자 번호: {st.session_state.participant_id}번 / 소요 시간: **{duration//60}분 {duration%60:02d}초**  
    연구자에게 완료 사실을 알려주세요.
    """)
    if st.button("처음으로 (다음 참가자용)", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
