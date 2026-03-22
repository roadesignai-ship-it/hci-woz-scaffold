import difflib


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def compute_scores(
    condition: str,
    ai_displayed: str,
    pre_framing: str,
    final_output: str,
    confidence_score: int,
    verification_text: str,
    counterfactual_text: str,
    reflection_text: str,
    woz_error1_modified: str,
    woz_error2_inserted: bool,
) -> dict:
    """
    실험 직후 행동 지표 자동 계산.
    사후 질문 기반 보정은 update_post_survey 후 analysis.py에서 수행.

    UAR (0~1): AI 채택률 — 문자열 유사도
    VAF (0~4): 검증 행동 빈도
    RI  (0~2): 리프레이밍 인스턴스
    CAG (float): 신뢰-의심 갭
    """

    # ── UAR ────────────────────────────────────────────
    uar = round(similarity(final_output, ai_displayed), 3)

    # ── VAF ────────────────────────────────────────────
    vaf = 0

    if condition == "B":
        # Condition B: 라디오(gate1/gate2) + 서술형(counterfactual)
        if str(verification_text).startswith("있다"):  # gate1: 검색 의향 있음
            vaf += 1
        if reflection_text in ("일부 의심된다", "신뢰하지 않는다"):  # gate2
            vaf += 1
        if confidence_score <= 2:
            vaf += 1
    else:
        # Condition A: 자유 텍스트 기반
        if len(str(verification_text)) >= 20:
            vaf += 1
        if len(str(reflection_text)) >= 20:
            vaf += 1
        if confidence_score <= 2:
            vaf += 1

    # 공통: counterfactual에 AI와 다른 고유 키워드 3개 이상
    if counterfactual_text:
        ai_words = set(ai_displayed.split())
        counter_words = set(str(counterfactual_text).split())
        if len(counter_words - ai_words) >= 3:
            vaf += 1

    # ── RI ─────────────────────────────────────────────
    ri = 0
    if len(str(counterfactual_text)) >= 50:
        ri += 1
    # final이 AI보다 pre_framing에 더 가까우면 자기 사고 반영
    sim_to_pre = similarity(final_output, pre_framing)
    sim_to_ai  = similarity(final_output, ai_displayed)
    if sim_to_pre > sim_to_ai:
        ri += 1

    # ── CAG: 신뢰-의심 갭 ──────────────────────────────
    # 행동 기반 의심 지수 (0~1 정규화)
    suspicion_score = 0
    suspicion_max = 3

    if condition == "B":
        if verification_text in ("yes", "unsure"):
            suspicion_score += 1
        if reflection_text == "yes":
            suspicion_score += 1
    else:
        if len(str(verification_text)) >= 20:
            suspicion_score += 1
        if len(str(reflection_text)) >= 20:
            suspicion_score += 1

    # 서술형 텍스트에서 의심 키워드 감지
    q6_text = str(verification_text) + " " + str(reflection_text) + " " + str(counterfactual_text) + " " + str(final_output)
    doubt_keywords = ["의심", "확인", "출처", "검증", "틀린", "잘못", "수정",
                      "다른", "맞나", "맞는지", "이상", "근거"]
    if any(kw in q6_text for kw in doubt_keywords):
        suspicion_score += 1

    suspicion_norm = round(suspicion_score / suspicion_max, 3)
    trust_norm = round(confidence_score / 5, 3)

    # CAG = 신뢰도 - 의심행동지수
    # 양수: 신뢰했지만 의심 안함 (과신)
    # 0 또는 음수: 신뢰 낮거나 의심 행동 있음 (잘 교정됨)
    cag = round(trust_norm - suspicion_norm, 3)

    return {"uar": uar, "vaf": vaf, "ri": ri, "cag": cag}


def compute_scores_with_post(behavior_scores: dict,
                              post_q1: int, post_q2: int,
                              post_q3: int, post_q4: int,
                              post_q5: int) -> dict:
    """
    사후 질문 응답을 결합한 보정 지표.
    analysis.py에서 호출.

    post_q1: AI 수치 신뢰도 (1~5)
    post_q2: AI 출처 신뢰도 (1~5)
    post_q3: 검증 필요 느낌 (1~5)
    post_q4: 최종 제안 수정 정도 (1~5)
    post_q5: AI vs 내 분석 가까움 (1~5, 5=내 분석)
    """
    uar_b = behavior_scores["uar"]
    vaf_b = behavior_scores["vaf"]
    ri_b  = behavior_scores["ri"]

    # UAR 보정: 행동(문자열유사도) 50% + 자기보고(Q4 역산) 50%
    uar_post = round(1 - (post_q4 / 5), 3)  # Q4 높을수록 수정 많이 함 → UAR 낮음
    uar_combined = round(uar_b * 0.5 + uar_post * 0.5, 3)

    # VAF 보정: 행동 50% + 자기보고(Q3 정규화) 50%
    vaf_post = round(post_q3 / 5, 3)
    vaf_combined = round((vaf_b / 4) * 0.5 + vaf_post * 0.5, 3)

    # RI 보정: 행동 50% + 자기보고(Q5 정규화) 50%
    ri_post = round(post_q5 / 5, 3)
    ri_combined = round((ri_b / 2) * 0.5 + ri_post * 0.5, 3)

    # CAG 보정: (Q1+Q2)/2 신뢰도 - Q3 의심 행동
    trust_post = round(((post_q1 + post_q2) / 2) / 5, 3)
    suspicion_post = round(post_q3 / 5, 3)
    cag_combined = round(trust_post - suspicion_post, 3)

    return {
        "uar_combined": uar_combined,
        "vaf_combined": vaf_combined,
        "ri_combined":  ri_combined,
        "cag_combined": cag_combined,
        "trust_post":   trust_post,
        "suspicion_post": suspicion_post,
    }
