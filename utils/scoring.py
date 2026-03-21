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
    woz_error1_modified: str,
    woz_error2_inserted: bool,
) -> dict:
    """
    4개 지표 자동 계산 (Fast Fashion 버전)

    UAR (0~1): final_output이 ai_displayed를 얼마나 그대로 썼는가
               높을수록 무비판적 채택
    VAF (0~3): 검증 행동 빈도 합산
    RI  (0~2): 리프레이밍 인스턴스
    CAG (float or None): Condition A/B 모두 측정 가능
                         (두 조건 모두 WoZ 오류 포함)
    """

    # ── UAR ────────────────────────────────────────────
    uar = round(similarity(final_output, ai_displayed), 3)

    # ── VAF ────────────────────────────────────────────
    vaf = 0
    # 검증 텍스트 20자 이상
    if len(verification_text) > 20:
        vaf += 1
    # 신뢰도 낮음 (2점 이하)
    if confidence_score <= 2:
        vaf += 1
    # counterfactual에 AI 응답에 없는 고유 키워드 3개 이상
    if counterfactual_text:
        ai_words = set(ai_displayed.split())
        counter_words = set(counterfactual_text.split())
        unique = counter_words - ai_words
        if len(unique) >= 3:
            vaf += 1

    # ── RI ─────────────────────────────────────────────
    ri = 0
    if len(counterfactual_text) >= 50:
        ri += 1
    # final이 AI보다 pre_framing에 더 가까우면
    # 참가자 자신의 사고를 더 많이 반영한 것
    if similarity(final_output, pre_framing) > similarity(final_output, ai_displayed):
        ri += 1

    # ── CAG: 두 조건 모두 측정 가능 ────────────────────
    # WoZ 오류 감지 키워드
    detection_targets = []
    if woz_error1_modified:
        # 변조된 수치 (예: "4%")
        detection_targets.append(woz_error1_modified.replace(" ", ""))
    if woz_error2_inserted:
        # 허위 출처 핵심 키워드
        detection_targets.append("UNEP")
        detection_targets.append("2023 글로벌 패션")
        detection_targets.append("백서")

    combined = (final_output + " " + verification_text).lower()
    detected = any(kw.lower() in combined for kw in detection_targets if kw)
    woz_detection = 1 if detected else 0

    # CAG = 신뢰도(정규화 0~1) - 오류 탐지 여부(0 or 1)
    # 양수: 신뢰했지만 오류를 못 잡음 (과신)
    # 0 또는 음수: 신뢰도 낮거나 오류 감지 (잘 교정됨)
    cag = round((confidence_score / 5) - woz_detection, 3)

    return {"uar": uar, "vaf": vaf, "ri": ri, "cag": cag}
