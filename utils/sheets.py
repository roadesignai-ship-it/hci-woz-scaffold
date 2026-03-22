import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "HCII2026_Experiment_Data"
WORKSHEET_NAME = "responses"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUMNS = [
    "timestamp", "participant_id", "student_name", "student_number",
    "condition", "task_number",
    "pre_framing_text", "pre_framing_length",
    "ai_response_original", "ai_response_displayed",
    "woz_error1_original", "woz_error1_modified", "woz_error2_inserted",
    "confidence_score", "verification_text",
    "counterfactual_text", "reflection_text", "final_output_text",
    "uar_score", "vaf_score", "ri_score", "cag_score",
    "session_duration_seconds",
    "post_q1", "post_q2", "post_q3", "post_q4", "post_q5", "post_q6",
]


@st.cache_resource
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    try:
        ws = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(WORKSHEET_NAME, rows=500, cols=len(COLUMNS))
        ws.append_row(COLUMNS)
    return ws


def save_to_sheets(row: dict):
    """row dict를 Google Sheets에 한 행으로 저장"""
    ws = get_sheet()
    # 헤더 순서에 맞춰 값 추출
    values = [str(row.get(col, "")) for col in COLUMNS]
    ws.append_row(values, value_input_option="USER_ENTERED")


def load_all_data() -> list[dict]:
    """분석용: 전체 데이터를 dict 리스트로 반환"""
    ws = get_sheet()
    records = ws.get_all_records()
    return records


def update_post_survey(participant_id: int, task_number: int,
                       q1: int, q2: int, q3: int, q4: int, q5: int, q6: str):
    """사후 질문 응답을 해당 행에 업데이트"""
    ws = get_sheet()
    records = ws.get_all_records()
    for i, row in enumerate(records):
        if (str(row.get("participant_id")) == str(participant_id) and
                str(row.get("task_number")) == str(task_number)):
            row_index = i + 2  # 헤더 포함 1-indexed
            # 사후질문 컬럼 위치 찾기
            header = ws.row_values(1)
            updates = {
                "post_q1": q1, "post_q2": q2, "post_q3": q3,
                "post_q4": q4, "post_q5": q5, "post_q6": q6
            }
            for col_name, val in updates.items():
                if col_name in header:
                    col_idx = header.index(col_name) + 1
                    ws.update_cell(row_index, col_idx, str(val))
            break
