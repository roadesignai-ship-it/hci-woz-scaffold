import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "HCII2026_Experiment_Data"
WORKSHEET_NAME = "responses"
WORKSHEET_ANON  = "responses_anon"   # 분석용 익명 시트

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── 원본 시트 컬럼 (실명/학번 포함) ──────────────────────
COLUMNS = [
    "timestamp", "participant_id", "student_name", "student_number",
    "condition", "condition_order", "task_number", "task_domain",
    "pre_framing_text", "pre_framing_length",
    "ai_response_original", "ai_response_displayed",
    "woz_error1_original", "woz_error1_modified", "woz_error2_inserted",
    "confidence_score", "verification_text",
    "counterfactual_text", "reflection_text", "final_output_text",
    "uar_score", "vaf_score", "ri_score", "csg_score",
    "session_duration_seconds",
    "post_q1", "post_q2", "post_q3", "post_q4", "post_q5", "post_q6",
]

# ── 분석용 익명 시트 컬럼 (실명/학번 제거) ───────────────
COLUMNS_ANON = [
    "timestamp", "participant_id",
    "condition", "condition_order", "task_number", "task_domain",
    "pre_framing_text", "pre_framing_length",
    "ai_response_original", "ai_response_displayed",
    "woz_error1_original", "woz_error1_modified", "woz_error2_inserted",
    "verification_text", "counterfactual_text", "reflection_text",
    "final_output_text",
    "uar_score", "vaf_score", "ri_score", "csg_score",
    "session_duration_seconds",
    "post_q1", "post_q2", "post_q3", "post_q4", "post_q5", "post_q6",
]


@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)

    # 원본 시트
    try:
        ws = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(WORKSHEET_NAME, rows=500, cols=len(COLUMNS))
        ws.append_row(COLUMNS)

    # 익명 분석 시트
    try:
        spreadsheet.worksheet(WORKSHEET_ANON)
    except gspread.WorksheetNotFound:
        ws_anon = spreadsheet.add_worksheet(WORKSHEET_ANON, rows=500, cols=len(COLUMNS_ANON))
        ws_anon.append_row(COLUMNS_ANON)

    return ws


def _get_anon_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    return spreadsheet.worksheet(WORKSHEET_ANON)


def save_to_sheets(row: dict):
    """원본 시트 + 익명 분석 시트 양쪽에 저장"""
    ws = get_sheet()
    # 원본
    values = [str(row.get(col, "")) for col in COLUMNS]
    ws.append_row(values, value_input_option="USER_ENTERED")
    # 익명
    try:
        ws_anon = _get_anon_sheet()
        anon_values = [str(row.get(col, "")) for col in COLUMNS_ANON]
        ws_anon.append_row(anon_values, value_input_option="USER_ENTERED")
    except Exception:
        pass  # 익명 시트 실패해도 원본은 보존


def load_all_data() -> list[dict]:
    """분석용: 익명 시트에서 전체 데이터 반환"""
    try:
        ws_anon = _get_anon_sheet()
        return ws_anon.get_all_records()
    except Exception:
        ws = get_sheet()
        return ws.get_all_records()


def update_post_survey(participant_id: int, task_number: int,
                       q1: int, q2: int, q3: int, q4: int, q5: int, q6: str):
    """사후 질문 응답을 원본 + 익명 시트 양쪽 업데이트"""
    updates = {
        "post_q1": q1, "post_q2": q2, "post_q3": q3,
        "post_q4": q4, "post_q5": q5, "post_q6": q6
    }
    for ws in [get_sheet(), _get_anon_sheet()]:
        try:
            records = ws.get_all_records()
            header = ws.row_values(1)
            for i, row in enumerate(records):
                if (str(row.get("participant_id")) == str(participant_id) and
                        str(row.get("task_number")) == str(task_number)):
                    row_index = i + 2
                    for col_name, val in updates.items():
                        if col_name in header:
                            col_idx = header.index(col_name) + 1
                            ws.update_cell(row_index, col_idx, str(val))
                    break
        except Exception:
            pass
