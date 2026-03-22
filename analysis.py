import streamlit as st
import pandas as pd
from scipy.stats import mannwhitneyu
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'DejaVu Sans'

from utils.sheets import load_all_data
from utils.scoring import compute_scores_with_post

st.set_page_config(page_title="실험 결과 분석", layout="wide")
st.title("🔬 실험 결과 분석 — 연구자 전용")

# ── 비밀번호 보호 ──────────────────────────────────────
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    pw = st.text_input("비밀번호", type="password")
    if st.button("확인"):
        if pw == st.secrets.get("researcher_password", "researcher2026"):
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

# ── 데이터 로드 ────────────────────────────────────────
with st.spinner("데이터 로드 중..."):
    records = load_all_data()

if not records:
    st.warning("아직 수집된 데이터가 없습니다.")
    st.stop()

df = pd.DataFrame(records)
for col in ["participant_id", "confidence_score",
            "uar_score", "vaf_score", "ri_score", "cag_score",
            "session_duration_seconds", "pre_framing_length"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

n_total = len(df)
n_a = len(df[df["condition"] == "A"])
n_b = len(df[df["condition"] == "B"])

st.success(f"총 {n_total}개 응답 | Condition A (2반): {n_a}명 | Condition B (1반): {n_b}명")

# ── 원본 데이터 ────────────────────────────────────────
with st.expander("📋 원본 데이터 전체 보기"):
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📥 전체 CSV 다운로드", csv,
                       file_name="HCII2026_FastFashion_data.csv",
                       mime="text/csv")

st.divider()

# ── Between-subject 분석: Mann-Whitney U ──────────────
st.subheader("📊 Between-Subject 비교 분석 (Mann-Whitney U Test)")
st.caption("두 독립 집단(1반 vs 2반) 비교 | 비모수 검정 | 양측 검정")

metrics = {
    "UAR (무비판적 채택률)":  ("uar_score",  "낮을수록 좋음 ↓"),
    "VAF (검증 행동 빈도)":   ("vaf_score",  "높을수록 좋음 ↑"),
    "RI (리프레이밍 인스턴스)": ("ri_score",  "높을수록 좋음 ↑"),
    "CAG (신뢰-정확도 갭)":   ("cag_score",  "낮을수록 좋음 ↓"),
}

results = []
for label, (col, direction) in metrics.items():
    a_vals = df[df["condition"] == "A"][col].dropna()
    b_vals = df[df["condition"] == "B"][col].dropna()
    if len(a_vals) >= 3 and len(b_vals) >= 3:
        stat, p = mannwhitneyu(a_vals, b_vals, alternative="two-sided")
        results.append({
            "지표": label,
            "기대 방향": direction,
            "Condition A 중앙값\n(2반, Baseline)": round(a_vals.median(), 3),
            "Condition B 중앙값\n(1반, Scaffolded)": round(b_vals.median(), 3),
            "U 통계량": round(stat, 1),
            "p값": round(p, 4),
            "유의성": "✅ p<.05" if p < 0.05 else ("⚠️ p<.10" if p < 0.10 else "—"),
        })
    else:
        results.append({
            "지표": label,
            "기대 방향": direction,
            "Condition A 중앙값\n(2반, Baseline)": f"n={len(a_vals)}",
            "Condition B 중앙값\n(1반, Scaffolded)": f"n={len(b_vals)}",
            "U 통계량": "—",
            "p값": "—",
            "유의성": "데이터 부족",
        })

st.dataframe(pd.DataFrame(results), use_container_width=True)

st.divider()

# ── 박스플롯 ───────────────────────────────────────────
st.subheader("📈 지표별 분포 비교")

fig, axes = plt.subplots(1, 4, figsize=(16, 5))
color_a = "#5B8DB8"
color_b = "#1D9E75"

for ax, (label, (col, _)) in zip(axes, metrics.items()):
    data_a = df[df["condition"] == "A"][col].dropna()
    data_b = df[df["condition"] == "B"][col].dropna()
    bp = ax.boxplot(
        [data_a, data_b],
        labels=[f"A (Baseline)\nn={len(data_a)}", f"B (Scaffolded)\nn={len(data_b)}"],
        patch_artist=True,
        medianprops=dict(color="black", linewidth=2),
        widths=0.5,
    )
    bp["boxes"][0].set_facecolor(color_a)
    bp["boxes"][0].set_alpha(0.75)
    if len(bp["boxes"]) > 1:
        bp["boxes"][1].set_facecolor(color_b)
        bp["boxes"][1].set_alpha(0.75)
    short_label = label.split("(")[0].strip()
    ax.set_title(short_label, fontsize=11, pad=8)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

plt.suptitle("Condition A (2반) vs Condition B (1반)", fontsize=13, y=1.02)
plt.tight_layout()
st.pyplot(fig)

st.divider()

# ── 참가자 완료 현황 ───────────────────────────────────
st.subheader("👥 참가자 완료 현황")
col1, col2, col3 = st.columns(3)
col1.metric("전체 완료", f"{n_total}명", f"목표 38명 대비 {n_total/38*100:.0f}%")
col2.metric("1반 완료 (Condition B)", f"{n_b}명", f"목표 19명 대비 {n_b/19*100:.0f}%")
col3.metric("2반 완료 (Condition A)", f"{n_a}명", f"목표 19명 대비 {n_a/19*100:.0f}%")

summary = df.groupby("participant_id")["condition"].first().reset_index()
summary.columns = ["참가자 번호", "조건"]
summary["반"] = summary["참가자 번호"].apply(lambda x: "1반 (B)" if x <= 19 else "2반 (A)")
st.dataframe(summary.sort_values("참가자 번호"), use_container_width=True)
