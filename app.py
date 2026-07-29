import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import datetime as dt

# ------------------------------------------------------------------
# 페이지 설정
# ------------------------------------------------------------------
st.set_page_config(page_title="장비 예약 시스템", layout="wide")

# ------------------------------------------------------------------
# 장비 목록
# ------------------------------------------------------------------
EQUIPMENT = [
    ("HPLC_1", "HPLC 1"),
    ("HPLC_2", "HPLC 2"),
    ("HPLC_3", "HPLC 3"),
    ("GC_1", "GC 1"),
    ("GC_2", "GC 2"),
    ("IC", "IC"),
    ("LCMSMS_1", "LC-MS/MS 1"),
    ("LCMSMS_2", "LC-MS/MS 2"),
]

DOW_KR = ["월", "화", "수", "목", "금", "토", "일"]

# ------------------------------------------------------------------
# Google Sheets 연결
# ------------------------------------------------------------------
@st.cache_resource
def get_gsheet_connection():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
    client = gspread.authorize(credentials)
    sheet_id = st.secrets["spreadsheet"]["sheet_id"]
    spreadsheet = client.open_by_key(sheet_id)
    return spreadsheet

def get_worksheet():
    spreadsheet = get_gsheet_connection()
    try:
        worksheet = spreadsheet.worksheet("bookings")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="bookings", rows=1000, cols=6)
        worksheet.append_row(["id", "equipment_id", "date", "start", "end", "name"])
    return worksheet

# ------------------------------------------------------------------
# 데이터 함수
# ------------------------------------------------------------------
def fetch_all_bookings():
    ws = get_worksheet()
    records = ws.get_all_records()
    return records

def fetch_bookings_for_week(monday: dt.date):
    all_bookings = fetch_all_bookings()
    week_dates = [(monday + dt.timedelta(days=i)).isoformat() for i in range(7)]

    result = {}
    for equip_id, _ in EQUIPMENT:
        for date_str in week_dates:
            key = f"{equip_id}|{date_str}"
            result[key] = []

    for b in all_bookings:
        key = f"{b['equipment_id']}|{b['date']}"
        if key in result:
            result[key].append(b)

    return result

def fetch_bookings_for_cell(equip_id: str, date_str: str):
    all_bookings = fetch_all_bookings()
    return [b for b in all_bookings if b["equipment_id"] == equip_id and b["date"] == date_str]

def add_booking(equip_id: str, date_str: str, start: str, end: str, name: str):
    ws = get_worksheet()
    booking_id = dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
    ws.append_row([booking_id, equip_id, date_str, start, end, name])
    st.cache_resource.clear()

def delete_booking(booking_id: str):
    ws = get_worksheet()
    records = ws.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record["id"]) == str(booking_id):
            ws.delete_rows(idx)
            st.cache_resource.clear()
            return True
    return False

# ------------------------------------------------------------------
# 유틸리티
# ------------------------------------------------------------------
def time_to_minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)

def has_overlap(equip_id: str, date_str: str, start: str, end: str) -> bool:
    existing = fetch_bookings_for_cell(equip_id, date_str)
    s, e = time_to_minutes(start), time_to_minutes(end)
    for b in existing:
        bs, be = time_to_minutes(b["start"]), time_to_minutes(b["end"])
        if s < be and e > bs:
            return True
    return False

# ------------------------------------------------------------------
# 세션 상태 초기화
# ------------------------------------------------------------------
if "monday" not in st.session_state:
    today = dt.date.today()
    st.session_state.monday = today - dt.timedelta(days=today.weekday())
if "selected_cell" not in st.session_state:
    st.session_state.selected_cell = None

# ------------------------------------------------------------------
# 헤더
# ------------------------------------------------------------------
st.title("🔬 분석연구팀 장비 예약 시스템")
st.caption("장비 × 날짜 칸의 **'+ 예약'** 버튼을 눌러 담당자 이름과 사용 시간(09:00~18:00)을 등록하세요.")
st.divider()

# ------------------------------------------------------------------
# 주간 네비게이션
# ------------------------------------------------------------------
nav1, nav2, nav3 = st.columns([1, 1, 3])
with nav1:
    if st.button("◀ 이전 주", use_container_width=True):
        st.session_state.monday -= dt.timedelta(days=7)
        st.session_state.selected_cell = None
with nav2:
    if st.button("다음 주 ▶", use_container_width=True):
        st.session_state.monday += dt.timedelta(days=7)
        st.session_state.selected_cell = None
with nav3:
    monday = st.session_state.monday
    sunday = monday + dt.timedelta(days=6)
    st.markdown(
        f"<div style='text-align:center;font-size:1.2rem;padding-top:0.4rem;'>"
        f"<b>{monday.strftime('%Y년 %m월 %d일')} ~ {sunday.strftime('%m월 %d일')}</b></div>",
        unsafe_allow_html=True
    )

st.divider()

# 새로고침 버튼
if st.button("🔄 새로고침", help="최신 예약 현황을 불러옵니다"):
    st.cache_resource.clear()
    st.rerun()

# ------------------------------------------------------------------
# 주간 그리드
# ------------------------------------------------------------------
monday = st.session_state.monday
week_dates = [monday + dt.timedelta(days=i) for i in range(7)]
bookings_map = fetch_bookings_for_week(monday)
today_str = dt.date.today().isoformat()

header_cols = st.columns([1.3] + [1] * 7)
header_cols[0].markdown("**장비**")
for i, d in enumerate(week_dates):
    header_cols[i + 1].markdown(f"**{d.strftime('%m/%d')} ({DOW_KR[d.weekday()]})**")

for equip_id, equip_name in EQUIPMENT:
    cols = st.columns([1.3] + [1] * 7)
    # 장비명을 굵게 표시 (수정됨)
    cols[0].markdown(f"**{equip_name}**") 
    
    for i, d in enumerate(week_dates):
        date_str = d.isoformat()
        key = f"{equip_id}|{date_str}"
        cell_bookings = bookings_map.get(key, [])

        with cols[i + 1]:
            for b in cell_bookings:
                st.markdown(
                    f"<small style='background:#e0f2fe;padding:2px 6px;border-radius:4px;'>"
                    f"{b['start']}~{b['end']} {b['name']}</small>",
                    unsafe_allow_html=True
                )
            
            btn_key = f"btn_{equip_id}_{date_str}"
            if st.button("+ 예약", key=btn_key, use_container_width=True):
                st.session_state.selected_cell = (equip_id, equip_name, d)
                st.rerun()

    # ★ 중요: 루프 안쪽, 가장 마지막 줄에 이 코드를 한 줄 추가합니다.
    st.divider() 


# ------------------------------------------------------------------
# 예약 모달
# ------------------------------------------------------------------
if st.session_state.selected_cell:
    equip_id, equip_name, d = st.session_state.selected_cell
    date_str = d.isoformat()

    st.divider()
    st.subheader(f"📅 {equip_name} · {date_str} ({DOW_KR[d.weekday()]})")

    existing = fetch_bookings_for_cell(equip_id, date_str)
    if existing:
        st.markdown("**등록된 예약**")
        for b in existing:
            c1, c2 = st.columns([4, 1])
            c1.write(f"{b['start']} ~ {b['end']}  —  {b['name']}")
            if c2.button("삭제", key=f"del_{b['id']}"):
                delete_booking(str(b["id"]))
                st.rerun()
    else:
        st.caption("이 날짜에 등록된 예약이 없습니다.")

    st.markdown("**새 예약 추가**")
    with st.form(key="booking_form"):
        name = st.text_input("담당자 이름")
        time_options = [f"{h:02d}:{m:02d}" for h in range(9, 19) for m in (0, 30)]

        col1, col2 = st.columns(2)
        with col1:
            start = st.selectbox("시작 시간", time_options, index=0)
        with col2:
            end = st.selectbox("종료 시간", time_options, index=2)

        submitted = st.form_submit_button("예약 등록", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("이름을 입력해주세요.")
            elif time_to_minutes(start) >= time_to_minutes(end):
                st.error("종료 시간은 시작 시간보다 늦어야 합니다.")
            elif has_overlap(equip_id, date_str, start, end):
                st.error("해당 시간대는 이미 다른 예약과 겹칩니다.")
            else:
                add_booking(equip_id, date_str, start, end, name.strip())
                st.success("예약이 등록되었습니다!")
                st.session_state.selected_cell = None
                st.rerun()

    if st.button("닫기"):
        st.session_state.selected_cell = None
        st.rerun()
