from __future__ import annotations

from pathlib import Path
import datetime as dt
from datetime import date
import os

import pandas as pd

import pandas as pd

def ui_str(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    s = str(x).strip()
    return "" if s.lower() in ["nan", "none"] else s


def sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize NaN/None/'nan' strings to empty strings for safe UI display."""
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    for c in df.columns:
        # Keep numeric columns as-is if possible; only coerce object-like to strings
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        df[c] = df[c].astype(str).replace({"nan": "", "NaN": "", "None": ""}).str.strip()
    return df

import re
import streamlit as st

# =========================================================
# Page
# =========================================================
st.set_page_config(page_title="Curriculum Dashboard", layout="wide")
st.title("📚 Curriculum Dashboard（ローカル）")

# =========================================================
# Mode (Viewer / Admin) - UI統合版
# - Streamlitの制約：widget生成後に同じkeyのsession_stateは変更できない
#   → 内部状態(page_state) と widget(key=page_widget) を分離して安全にページ遷移する
# =========================================================
PAGE_OPTIONS = ["閲覧", "管理（入力）"]

if "page_state" not in st.session_state:
    st.session_state.page_state = "閲覧"

# 他の場所のボタンからページ遷移したい時は pending_page に入れて rerun
if "pending_page" in st.session_state:
    st.session_state.page_state = st.session_state.pop("pending_page")

# ロック解除フラグ（未定義で落ちるのを防ぐ）
st.session_state.setdefault("override_passed_lock", False)
st.session_state.setdefault("override_done_lock", False)

override_passed_lock = st.session_state["override_passed_lock"]
override_done_lock = st.session_state["override_done_lock"]

page = st.radio(
    "画面",
    PAGE_OPTIONS,
    horizontal=True,
    index=PAGE_OPTIONS.index(st.session_state.page_state) if st.session_state.page_state in PAGE_OPTIONS else 0,
    key="page_widget",
)

# radioの選択を内部状態に反映
st.session_state.page_state = page
admin_mode = (page == "管理（入力）")


# =========================================================
# Simple Login (optional)
# - Priority:
#   1) st.secrets["DASHBOARD_PASSWORD"]
#   2) Environment variable DASHBOARD_PASSWORD
# If neither exists -> allow access but show warning.
# =========================================================
def _get_password() -> str | None:
    try:
        pw = st.secrets.get("DASHBOARD_PASSWORD")  # type: ignore[attr-defined]
        if pw:
            return str(pw)
    except Exception:
        pass
    pw2 = os.environ.get("DASHBOARD_PASSWORD")
    return str(pw2) if pw2 else None


def require_login() -> None:
    pw = _get_password()
    if not pw:
        st.warning("ログインパスワードが未設定です（secrets または 環境変数 DASHBOARD_PASSWORD を設定すると有効になります）")
        return

    if st.session_state.get("auth_ok") is True:
        return

    with st.container():
        st.subheader("🔐 ログイン")
        input_pw = st.text_input("パスワード", type="password")
        if st.button("ログイン"):
            if input_pw == pw:
                st.session_state["auth_ok"] = True
                st.success("ログインしました。")
                st.rerun()
            else:
                st.error("パスワードが違います。")

    st.stop()


require_login()

# =========================================================
# Paths
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# =========================================================
# 🎓 検定 合格結果（kentei_results.csv）: v6.5 B方式（シンプル運用）
#   - 合格判定の唯一の正（Single Source of Truth）
# =========================================================
KENTEI_RESULTS_CSV = os.path.join(DATA_DIR, "kentei_results.csv")

def load_kentei_results() -> pd.DataFrame:
    """Load (or create) kentei_results.csv."""
    if os.path.exists(KENTEI_RESULTS_CSV):
        try:
            df = pd.read_csv(KENTEI_RESULTS_CSV)
            # 空行・空文字行を除外（誤って1行だけ空データが入っても合格扱いにならないように）
            for col in ["student_id", "grade", "score", "pass_date", "memo"]:
                if col not in df.columns:
                    df[col] = ""
            df = df.fillna("")
            df["student_id"] = df["student_id"].astype(str).str.strip()
            df["grade"] = df["grade"].astype(str).str.strip()
            df = df[(df["student_id"] != "") & (df["grade"] != "")]
            return df
        except Exception:
            df = pd.DataFrame(columns=["student_id", "grade", "score", "pass_date", "memo"])
            write_csv_atomic(df, KENTEI_RESULTS_CSV)
            return df
    df = pd.DataFrame(columns=["student_id", "grade", "score", "pass_date", "memo"])
    write_csv_atomic(df, KENTEI_RESULTS_CSV)
    return df

def save_kentei_results(df: pd.DataFrame) -> None:
    write_csv_atomic(df, KENTEI_RESULTS_CSV)

def is_kentei_passed(student_id: str, grade: str) -> bool:
    df = load_kentei_results()
    if df.empty:
        return False
    sid = str(student_id).strip()
    g = str(grade).strip()
    m = (
        df["student_id"].astype(str).str.strip().eq(sid)
        & df["grade"].astype(str).str.strip().eq(g)
    )
    return bool(m.any())

# =========================================================
# ✅ 出席ログ（attendance_log.csv）: v6.6.3
#   - 予定ではなく「実績」を1回だけ記録（授業/自習）
#   - date × student_id は 1日1レコード（重複防止）
# =========================================================
ATTENDANCE_LOG_CSV = DATA_DIR / "attendance_log.csv"

def load_attendance_log() -> pd.DataFrame:
    if ATTENDANCE_LOG_CSV.exists():
        df = pd.read_csv(ATTENDANCE_LOG_CSV, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=["date", "student_id", "kind", "memo"])
        write_csv_atomic(df, ATTENDANCE_LOG_CSV)
        return df

    # normalize
    for c in ["date", "student_id", "kind", "memo"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str).fillna("").str.strip()
    return df[["date", "student_id", "kind", "memo"]]

def save_attendance_log(df: pd.DataFrame) -> None:
    # keep columns
    for c in ["date", "student_id", "kind", "memo"]:
        if c not in df.columns:
            df[c] = ""
    df = df[["date", "student_id", "kind", "memo"]].copy()
    write_csv_atomic(df, ATTENDANCE_LOG_CSV)

def get_attendance_today(df: pd.DataFrame, student_id: str, d: date) -> dict | None:
    if df.empty:
        return None
    sid = str(student_id).strip()
    ds = str(d)
    hit = df[(df["student_id"].astype(str).str.strip() == sid) & (df["date"].astype(str).str.strip() == ds)]
    if hit.empty:
        return None
    r = hit.iloc[-1].to_dict()
    return r

def upsert_attendance(df: pd.DataFrame, student_id: str, d: date, kind: str, memo: str = "", count: int = 1) -> pd.DataFrame:
    sid = str(student_id).strip()
    ds = str(d)
    kind = str(kind).strip()
    memo = str(memo).strip()

    try:
        count_n = int(count)
    except Exception:
        count_n = 1
    if count_n < 1:
        count_n = 1
    if count_n > 10:
        count_n = 10

    # 同日分はいったん全削除（回数を“再保存”で確定させる）
    if not df.empty:
        mask = (df["student_id"].astype(str).str.strip() == sid) & (df["date"].astype(str).str.strip() == ds)
        df = df.loc[~mask].copy()

    new_rows = pd.DataFrame([{"date": ds, "student_id": sid, "kind": kind, "memo": memo}] * count_n)
    df = pd.concat([df, new_rows], ignore_index=True)
    return df
def delete_attendance(df: pd.DataFrame, student_id: str, d: date) -> pd.DataFrame:
    if df.empty:
        return df
    sid = str(student_id).strip()
    ds = str(d)
    mask = (df["student_id"].astype(str).str.strip() == sid) & (df["date"].astype(str).str.strip() == ds)
    return df.loc[~mask].copy()

def count_month_lessons(df: pd.DataFrame, student_id: str, d: date) -> int:
    if df.empty:
        return 0
    sid = str(student_id).strip()
    ym = d.strftime("%Y-%m")
    tmp = df.copy()
    tmp["__ym"] = tmp["date"].astype(str).str.slice(0, 7)
    tmp = tmp[(tmp["student_id"].astype(str).str.strip() == sid) & (tmp["__ym"] == ym)]
    tmp = tmp[tmp["kind"].astype(str).str.strip().isin(["lesson", "授業"])]
    return int(len(tmp))



STUDENTS_CSV = DATA_DIR / "students.csv"
PROGRESS_LOG_CSV = DATA_DIR / "progress_log.csv"

STUDENT_SCHEDULE_CSV = DATA_DIR / "student_schedule.csv"
TIMESLOTS_CSV = DATA_DIR / "timeslots.csv"
SCHEDULE_OVERRIDES_CSV = DATA_DIR / "schedule_overrides.csv"

CURRICULUM_COURSES_CSV = DATA_DIR / "curriculum_courses.csv"
CURRICULUM_TASKS_CSV = DATA_DIR / "curriculum_tasks.csv"
CURRICULUM_PROGRESS_CSV = DATA_DIR / "curriculum_progress.csv"

KENTEI_TASKS_CSV = DATA_DIR / "kentei_tasks.csv"
KENTEI_PROGRESS_CSV = DATA_DIR / "kentei_progress.csv"

# Optional (if exists): upcoming exams
KENTEI_EXAM_SCHEDULE_CSV = DATA_DIR / "kentei_exam_schedule.csv"

# =========================================================
# Helpers
# =========================================================

def ensure_student_scoped_defaults(student_id: str, key: str, value):
    """Reset widget state when student changes. Must be called BEFORE the widget is created."""
    sid = str(student_id or "")
    tracker_key = f"__last_student_for__{key}"
    if tracker_key not in st.session_state:
        st.session_state[tracker_key] = sid
        if key not in st.session_state:
            st.session_state[key] = value
        return
    if st.session_state[tracker_key] != sid:
        st.session_state[tracker_key] = sid
        st.session_state[key] = value


# -----------------------------
# UI Option helpers (v6.1)
# -----------------------------
GRADE_PRESETS = [
    "",  # 空(未設定)
    "幼稚園",
    "小1","小2","小3","小4","小5","小6",
    "中1","中2","中3",
    "高1","高2","高3",
    "大学","短大","専門学校",
    "その他学校",
    "社会人",
    "一般",
    "その他（自由入力）",
]

WEEKDAY_PRESETS = ["", "月", "火", "水", "木", "金", "土", "日", "その他（自由入力）"]

def _unique_str_list(series):
    try:
        vals = [str(x).strip() for x in series.dropna().tolist()]
        vals = [v for v in vals if v != ""]
        seen = set()
        out = []
        for v in vals:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out
    except Exception:
        return []

def build_grade_options(students_df):
    existing = _unique_str_list(students_df.get("grade", pd.Series(dtype=str))) if students_df is not None else []
    base = [g for g in GRADE_PRESETS if g not in ("", "その他（自由入力）")]
    merged = base[:]
    for g in existing:
        if g not in merged:
            merged.append(g)
    return [""] + merged + ["その他（自由入力）"]

def build_weekday_options(students_df, schedule_df):
    existing = []
    if students_df is not None and "weekday" in students_df.columns:
        existing += _unique_str_list(students_df["weekday"])
    if schedule_df is not None and "weekday" in schedule_df.columns:
        existing += _unique_str_list(schedule_df["weekday"])
    base = [d for d in WEEKDAY_PRESETS if d not in ("", "その他（自由入力）")]
    merged = [""] + base
    for d in existing:
        if d not in merged and d != "その他（自由入力）":
            merged.append(d)
    if "その他（自由入力）" not in merged:
        merged.append("その他（自由入力）")
    return merged

def build_slot_options(timeslots_df, schedule_df, students_df):
    existing = []
    if timeslots_df is not None and "slot" in timeslots_df.columns:
        existing += _unique_str_list(timeslots_df["slot"])
    if schedule_df is not None and "slot" in schedule_df.columns:
        existing += _unique_str_list(schedule_df["slot"])
    if students_df is not None and "slot" in students_df.columns:
        existing += _unique_str_list(students_df["slot"])
    # numeric sort if possible
    def sort_key(v):
        try:
            return (0, float(v))
        except Exception:
            return (1, v)
    existing = sorted(list(dict.fromkeys(existing)), key=sort_key)
    return [""] + existing + ["その他（自由入力）"]

# -----------------------------
# Smart defaults / ordering (v6.2)
# -----------------------------
def today_weekday_jp() -> str:
    jp = ["月", "火", "水", "木", "金", "土", "日"]
    return jp[date.today().weekday()]

def parse_date_like(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except Exception:
            pass
    try:
        return pd.to_datetime(s, errors="coerce").to_pydatetime()
    except Exception:
        return None

def get_today_student_ids(schedule_df: pd.DataFrame, overrides_df: pd.DataFrame):
    """今日予定がある生徒IDの集合（ベース時間割＋例外を反映）"""
    counts = {}
    w = today_weekday_jp()

    # base schedule
    if schedule_df is not None and not schedule_df.empty:
        if "weekday" in schedule_df.columns and "student_id" in schedule_df.columns:
            base = schedule_df[schedule_df["weekday"].astype(str).str.strip() == w]
            for sid in base.get("student_id", pd.Series(dtype=str)).dropna().astype(str):
                counts[sid] = counts.get(sid, 0) + 1

    # overrides today
    if overrides_df is not None and not overrides_df.empty:
        if "date" in overrides_df.columns and "student_id" in overrides_df.columns:
            today_str = date.today().isoformat()
            od = overrides_df[overrides_df["date"].astype(str).str.strip() == today_str]
            for _, r in od.iterrows():
                sid = str(r.get("student_id", "")).strip()
                if not sid:
                    continue
                action = str(r.get("action", "")).strip().lower()
                if action in ("add", "move"):
                    counts[sid] = counts.get(sid, 0) + 1
                elif action == "cancel":
                    counts[sid] = counts.get(sid, 0) - 1

    return {sid for sid, c in counts.items() if c > 0}

def latest_course_for_student(student_id: str, progress_df: pd.DataFrame):
    """進捗CSVからその生徒の直近コースを推定（方法A: 最新更新）"""
    if progress_df is None or progress_df.empty:
        return None
    if "student_id" not in progress_df.columns or "course_id" not in progress_df.columns:
        return None
    df = progress_df[progress_df["student_id"].astype(str) == str(student_id)]
    if df.empty:
        return None

    for col in ["updated_at", "updated", "saved_at", "timestamp", "date"]:
        if col in df.columns:
            ts = df[col].apply(parse_date_like)
            if ts.notna().any():
                df2 = df.assign(__ts=ts).sort_values("__ts", ascending=False)
                return str(df2.iloc[0]["course_id"])
    return str(df.iloc[-1]["course_id"])


def safe_read_csv(
    path,
    required_cols=None,
    *,
    stop_on_missing: bool = False,
    show_message: bool = True,
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """CSVを安全に読み込むヘルパー。

    - ファイル無し -> 空DF（show_messageならwarning）
    - required_cols不足 -> 空DF（warning） / stop_on_missing=Trueなら st.stop()
    """
    path = Path(path)

    if not path.exists():
        if show_message:
            st.warning(f"CSVが見つかりません: {path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(path, encoding=encoding)
    except UnicodeDecodeError:
        # WindowsのCSV(cp932)も吸収
        df = pd.read_csv(path, encoding="cp932")
    except Exception as e:
        if show_message:
            st.error(f"CSV読み込みエラー: {path}\n{e}")
        return pd.DataFrame()

    if required_cols:
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            msg = (
                f"CSVに必要な列がありません: {path} 不足:{missing} "
                f"(現在の列:{list(df.columns)})"
            )
            if show_message:
                st.warning(msg)
            if stop_on_missing:
                st.stop()
            return pd.DataFrame()

    return df


def norm_lower(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.lower()


def ensure_students_optional_cols(students: pd.DataFrame) -> pd.DataFrame:
    students = students.copy()
    students.columns = students.columns.astype(str).str.strip()

    for col in [
        "grade", "number_of_times", "join_date", "is_active", "leave_date", "note",
        "weekday", "slot"
    ]:
        if col not in students.columns:
            students[col] = ""

    students["is_active"] = (
        students["is_active"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "true")
        .str.lower()
    )
    students["join_date"] = pd.to_datetime(students["join_date"], errors="coerce")

    return students


def session_mark(v: str) -> str:
    if str(v).strip().lower() == "self":
        return "(自)"
    return ""


def write_csv_atomic(df: pd.DataFrame, path: Path) -> None:
    # path は str で渡されることもあるので Path に正規化
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(path)


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def show_saved(message: str = "保存しました。") -> None:
    """Show a consistent save message after user actions."""
    st.success(message)

# =========================================================
# Load data
# =========================================================
students = safe_read_csv(STUDENTS_CSV, ["student_id", "display_name"])
students = sanitize_df(students)

students = ensure_students_optional_cols(students)

log = safe_read_csv(PROGRESS_LOG_CSV, ["date", "student_id", "curriculum", "item", "status", "note"])

student_schedule = safe_read_csv(
    STUDENT_SCHEDULE_CSV,
    ["student_id", "weekday", "slot", "session_type"],
    stop_on_missing=False,
)

timeslots = safe_read_csv(
    TIMESLOTS_CSV,
    ["weekday", "slot", "start", "end"],
    stop_on_missing=False,
)

# schedule overrides: optional (today exceptions)
schedule_overrides = safe_read_csv(
    SCHEDULE_OVERRIDES_CSV,
    ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"],
    stop_on_missing=False,
)

curr_courses = safe_read_csv(
    CURRICULUM_COURSES_CSV,
    ["course_id", "genre_id", "genre_name", "course_name", "course_order", "is_active"],
    stop_on_missing=False,
)

curr_tasks = safe_read_csv(
    CURRICULUM_TASKS_CSV,
    ["course_id", "task_id", "task_name", "order", "is_active", "student_id"],
    stop_on_missing=False,
)

curr_prog = safe_read_csv(
    CURRICULUM_PROGRESS_CSV,
    ["student_id", "course_id", "task_id", "is_done", "done_date", "note"],
    stop_on_missing=False,
)

kentei_tasks = safe_read_csv(
    KENTEI_TASKS_CSV,
    ["grade", "task_id", "task_name", "order", "student_id"],
    stop_on_missing=False,
)

kentei_prog = safe_read_csv(
    KENTEI_PROGRESS_CSV,
    ["student_id", "grade", "task_id", "is_done", "done_date", "note"],
    stop_on_missing=False,
)

kentei_exam = safe_read_csv(
    KENTEI_EXAM_SCHEDULE_CSV,
    ["student_id", "exam_date", "exam_type", "grade", "note"],
    stop_on_missing=False,
)

# =========================================================
# Merge logs (for display)
# =========================================================
log_all = log.merge(students, on="student_id", how="left")
for c in ["display_name", "grade", "number_of_times", "join_date", "is_active"]:
    if c not in log_all.columns:
        log_all[c] = ""

log_done = log_all[norm_lower(log_all["status"]) == "done"].copy()

# =========================================================
if page == "閲覧":
    # Sidebar filters
    # =========================================================
    st.sidebar.header("フィルタ")
    override_passed_lock = st.sidebar.checkbox("⚠ 合格済み検定課題を編集する（通常はOFF）", key="override_passed_lock")
    # 閲覧側はこのkeyを正とする（管理側は別keyで表示し、ここへ同期する）
    override_done_lock = st.sidebar.checkbox("⚠ 完了済み課題を編集する（通常はOFF）", key="override_done_lock")
    st.sidebar.caption("※ 合格済み/完了済みの編集を一時的に許可したい時だけONにしてください")
    include_inactive = st.sidebar.checkbox("退会した生徒も含める", value=False)

    grade_list = sorted(
        students["grade"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
        .tolist()
    )
    selected_grade = st.sidebar.selectbox("学年", ["（全て）"] + grade_list)

    students_view = students.copy()
    if not include_inactive:
        students_view = students_view[students_view["is_active"] == "true"].copy()

    # Student selector: 今日の予定を上に（🔔表示）
    today_ids = get_today_student_ids(student_schedule, schedule_overrides)
    students_view_sorted = students_view.copy()
    if "student_id" in students_view_sorted.columns:
        students_view_sorted["__priority"] = students_view_sorted["student_id"].astype(str).apply(lambda x: 0 if x in today_ids else 1)
    else:
        students_view_sorted["__priority"] = 1

    students_view_sorted = students_view_sorted.sort_values(by=["__priority", "join_date", "display_name"], na_position="last")

    # options are display_name (既存ロジック互換)
    student_names = students_view_sorted["display_name"].fillna("").astype(str).str.strip().tolist()
    name_to_id = dict(zip(students_view_sorted["display_name"].astype(str), students_view_sorted.get("student_id", pd.Series(dtype=str)).astype(str)))

    def _student_label(opt):
        if opt == "（全員）":
            return opt
        sid = name_to_id.get(opt, "")
        return ("🔔 " if sid in today_ids else "") + opt

    selected_student = st.sidebar.selectbox(
        "生徒",
        ["（全員）"] + [n for n in student_names if n],
        format_func=_student_label,
        key="sidebar_student",
    )

    # Course/genre ordering (optional)
    course_order_map: dict[str, int] = {}
    if not curr_courses.empty and "course_order" in curr_courses.columns:
        tmp = curr_courses.copy()
        tmp["course_order_num"] = pd.to_numeric(tmp["course_order"], errors="coerce").fillna(9999).astype(int)
        for _, r in tmp.iterrows():
            course_order_map[str(r["course_id"]).strip()] = int(r["course_order_num"])

    # Curriculum list from logs (stable) + optional course genres (nice)
    curriculum_list = sorted(
        log_all["curriculum"].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
    )
    if "Scratch" not in curriculum_list:
        curriculum_list = ["Scratch"] + curriculum_list

    selected_curriculum = st.sidebar.selectbox("カリキュラム（ログ表示）", ["（全て）"] + curriculum_list)
    selected_status = st.sidebar.selectbox("状態（詳細表示用）", ["（全て）", "done", "in_progress", "paused", "retry"])

    st.sidebar.divider()

    with st.sidebar.expander("⚠ ロック解除（誤操作防止のため普段は触らない）", expanded=False):
        st.caption("⚠ 合格済み検定課題の編集ロックは、左サイドバーのスイッチで切替します。")
        st.caption("⚠ 完了済み課題の編集ロックは、左サイドバーのスイッチで切替します。")

    # Log side also respects active filter
    if not include_inactive and "is_active" in log_all.columns:
        log_all = log_all[log_all["is_active"] == "true"].copy()
        log_done = log_done[log_done["is_active"] == "true"].copy()

    # =========================================================
    # Apply filters (logs)
    # =========================================================
    filtered_done = log_done.copy()
    if selected_grade != "（全て）":
        filtered_done = filtered_done[filtered_done["grade"] == selected_grade]
    if selected_student != "（全員）":
        filtered_done = filtered_done[filtered_done["display_name"] == selected_student]
    if selected_curriculum != "（全て）":
        filtered_done = filtered_done[filtered_done["curriculum"] == selected_curriculum]

    filtered_all = log_all.copy()
    if selected_grade != "（全て）":
        filtered_all = filtered_all[filtered_all["grade"] == selected_grade]
    if selected_student != "（全員）":
        filtered_all = filtered_all[filtered_all["display_name"] == selected_student]
    if selected_curriculum != "（全て）":
        filtered_all = filtered_all[filtered_all["curriculum"] == selected_curriculum]
    if selected_status != "（全て）":
        filtered_all = filtered_all[norm_lower(filtered_all["status"]) == selected_status]

    # =========================================================
    # Top metrics
    # =========================================================
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("生徒数", int(len(students)))
    col2.metric("ログ総数", int(len(log_all)))
    col3.metric("完了ログ（done）", int(len(log_done)))
    col4.metric("表示中（done）", int(len(filtered_done)))
    st.divider()

    # =========================================================
    # Current per student: prefer non-done (latest), else latest row
    # =========================================================
    def normalize_bool(v) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        s = str(v).strip().lower()
        return s in ("1", "true", "t", "yes", "y", "on")


    def next_student_id(existing_ids) -> str:
        """IDs like S001, S002 ..."""
        max_n = 0
        for sid in existing_ids:
            if sid is None:
                continue
            m = re.match(r"^S?(\d+)$", str(sid).strip(), flags=re.IGNORECASE)
            if m:
                max_n = max(max_n, int(m.group(1)))
        return f"S{max_n+1:03d}"


    def safe_read_csv(path: Path, required_cols=None,stop_on_missing=False) -> pd.DataFrame:
        required_cols = required_cols or []
        if not path.exists():
            return pd.DataFrame(columns=required_cols)
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
        except Exception:
            # fallback (encoding issues etc)
            df = pd.read_csv(path, dtype=str, encoding="utf-8", errors="ignore").fillna("")
        # ensure required columns
        for c in required_cols:
            if c not in df.columns:
                df[c] = ""
        return df


    def safe_write_csv(df: pd.DataFrame, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        write_csv_atomic(df, path)


    def ensure_csv_headers(path: Path, headers: list[str]):
        if path.exists():
            return
        df = pd.DataFrame(columns=headers)
        safe_write_csv(df, path)

    def build_current_per_student(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["student_id", "現在コース", "現在項目", "状態", "date_dt"])

        x = df.copy()
        x["date_dt"] = pd.to_datetime(x["date"], errors="coerce")
        x = x.dropna(subset=["date_dt"]).copy()
        if x.empty:
            return pd.DataFrame(columns=["student_id", "現在コース", "現在項目", "状態", "date_dt"])

        x["status_l"] = norm_lower(x["status"])
        x = x.sort_values(by=["student_id", "date_dt"], ascending=[True, False])

        rows = []
        for sid, g in x.groupby("student_id", sort=False):
            g2 = g[g["status_l"] != "done"]
            pick = g2.head(1) if not g2.empty else g.head(1)
            r = pick.iloc[0]
            rows.append({
                "student_id": sid,
                "現在コース": str(r.get("curriculum", "")).strip(),
                "現在項目": str(r.get("item", "")).strip(),
                "状態": str(r.get("status", "")).strip(),
                "date_dt": r["date_dt"],
            })
        return pd.DataFrame(rows)

    current_per_student = build_current_per_student(log_all)

    # =========================================================
    # Upcoming exams (top)
    # =========================================================
    st.subheader("📌 検定予定（直近）")
    if kentei_exam.empty:
        st.caption("検定予定はまだ登録されていません。（data/kentei_exam_schedule.csv を置くと表示されます）")
        today_exam_ids = set()
    else:
        exam_view = kentei_exam.copy()

        # normalize
        for c in ["student_id", "exam_type", "grade", "note", "exam_date"]:
            if c in exam_view.columns:
                exam_view[c] = exam_view[c].fillna("").astype(str).str.strip()

        # active filter
        if not include_inactive:
            active_ids = set(students[students["is_active"] == "true"]["student_id"].astype(str))
            exam_view = exam_view[exam_view["student_id"].astype(str).isin(active_ids)].copy()

        exam_view["exam_date_dt"] = pd.to_datetime(exam_view["exam_date"], errors="coerce")
        exam_view = exam_view.dropna(subset=["exam_date_dt"]).copy()
        today_dt = pd.to_datetime(dt.date.today())
        exam_view = exam_view[exam_view["exam_date_dt"] >= today_dt].copy()

        # name merge
        exam_view = exam_view.merge(students[["student_id", "display_name"]], on="student_id", how="left")
        exam_view["日付"] = exam_view["exam_date_dt"].dt.strftime("%Y-%m-%d")
        exam_view["生徒"] = exam_view["display_name"].fillna("")

        exam_view = exam_view.sort_values(by=["exam_date_dt", "生徒"], na_position="last")

        # dedupe per student (earliest upcoming)
        exam_view = exam_view.drop_duplicates(subset=["student_id"], keep="first")

                # --- 今日の検定（強調：背景うすピンク + 🔴印） ---
        today_str = dt.date.today().strftime("%Y-%m-%d")
        exam_tbl = exam_view[["日付", "生徒", "exam_type", "grade", "note", "student_id"]].rename(
            columns={"exam_type": "検定", "grade": "級", "note": "メモ"}
        )

        # 🔴印（名前そのものの色は変えない）
        today_exam_ids = set(exam_tbl.loc[exam_tbl["日付"] == today_str, "student_id"].astype(str))
        exam_tbl["生徒"] = exam_tbl.apply(
            lambda r: ("🔴 " + str(r["生徒"]).strip()) if str(r["student_id"]) in today_exam_ids and str(r["日付"]) == today_str else str(r["生徒"]).strip(),
            axis=1,
        )

        def _pink_today_row(row: pd.Series):
            if str(row.get("日付", "")) == today_str:
                return ["background-color: #fff0f5"] * len(row)  # うすピンク
            return [""] * len(row)

        show_tbl = exam_tbl.drop(columns=["student_id"])
        st.dataframe(
            show_tbl.style.apply(_pink_today_row, axis=1),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # =========================================================
    # Today schedule (top)
    # =========================================================
    weekday_map = ["月", "火", "水", "木", "金", "土", "日"]
    today = dt.date.today()
    today_wd = weekday_map[today.weekday()]

    st.subheader(f"🗓 今日（{today.strftime('%Y-%m-%d')}・{today_wd}）の予定")


    if student_schedule.empty:
        st.info("student_schedule.csv が無い/空なので、今日の予定は表示できません。")
    else:
        # --- 正規化（重複の原因を潰す） ---
        sched = student_schedule.copy()
        for c in ["student_id", "weekday", "slot", "session_type"]:
            if c in sched.columns:
                sched[c] = sched[c].fillna("").astype(str).str.strip()
        # 同じ student_id/weekday/slot が複数あると表示が増殖するので潰す
        sched = sched.drop_duplicates(subset=["student_id", "weekday", "slot"], keep="first")

        ts = timeslots.copy()
        for c in ["weekday", "slot", "start", "end"]:
            if c in ts.columns:
                ts[c] = ts[c].fillna("").astype(str).str.strip()
        ts = ts.drop_duplicates(subset=["weekday", "slot"], keep="first")

        sched_today = sched[sched["weekday"] == today_wd].copy()

        base_students = students.copy()
        if not include_inactive:
            base_students = base_students[base_students["is_active"] == "true"].copy()

        # ベース（固定）スケジュール
        today_view = sched_today.merge(
            base_students[["student_id", "display_name", "grade", "number_of_times", "join_date"]],
            on="student_id",
            how="left",
        )

        if not ts.empty:
            today_view = today_view.merge(ts, on=["weekday", "slot"], how="left")
        else:
            today_view["start"] = ""
            today_view["end"] = ""

        # =====================================================
        # 例外（schedule_overrides.csv）を適用
        # =====================================================
        # schedule_overrides.csv は「日付ベース」で add/cancel を入れる
        ov = schedule_overrides.copy()
        if not ov.empty:
            for c in ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]:
                if c in ov.columns:
                    ov[c] = ov[c].fillna("").astype(str).str.strip()

            ov_today = ov[ov["date"] == today.strftime("%Y-%m-%d")].copy()
        else:
            ov_today = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"])

        # cancel: ベースから消す（同じ生徒×同じコマ）
        if not ov_today.empty:
            cancel_df = ov_today[norm_lower(ov_today["action"]) == "cancel"].copy()
            if not cancel_df.empty:
                cancel_keys = set(zip(cancel_df["student_id"], cancel_df["slot"]))
                today_view = today_view[~today_view.apply(lambda r: (str(r.get("student_id","")).strip(), str(r.get("slot","")).strip()) in cancel_keys, axis=1)].copy()

            # add: 追加（必要ならベースを置き換え）
            add_df = ov_today[norm_lower(ov_today["action"]) == "add"].copy()
            if not add_df.empty:
                # 置き換え（同じ student_id×slot はベースを消す）
                add_keys = set(zip(add_df["student_id"], add_df["slot"]))
                today_view = today_view[~today_view.apply(lambda r: (str(r.get("student_id","")).strip(), str(r.get("slot","")).strip()) in add_keys, axis=1)].copy()

                add_view = add_df.copy()
                add_view["weekday"] = today_wd

                # start/end が空なら timeslots から補完
                if not ts.empty:
                    add_view = add_view.merge(ts, on=["weekday", "slot"], how="left", suffixes=("", "_ts"))
                    add_view["start"] = add_view["start"].replace("", pd.NA)
                    add_view["end"] = add_view["end"].replace("", pd.NA)
                    add_view["start"] = add_view["start"].fillna(add_view.get("start_ts", ""))
                    add_view["end"] = add_view["end"].fillna(add_view.get("end_ts", ""))
                    for c in ["start_ts", "end_ts"]:
                        if c in add_view.columns:
                            add_view = add_view.drop(columns=[c])

                # 生徒情報を結合
                add_view = add_view.merge(
                    base_students[["student_id", "display_name", "grade", "number_of_times", "join_date"]],
                    on="student_id",
                    how="left",
                )

                # session_type（空なら lesson）
                add_view["session_type"] = add_view["session_type"].replace("", "lesson")

                # ベースと列合わせ
                for c in ["note"]:
                    if c not in today_view.columns:
                        today_view[c] = ""
                # add_view の note は上書き表示用
                add_view["note"] = add_view["note"].fillna("").astype(str)

                today_view = pd.concat([today_view, add_view], ignore_index=True)

        # current merge（最新ログの「done以外」を優先）
        today_view = today_view.merge(
            current_per_student[["student_id", "現在コース", "現在項目", "状態"]],
            on="student_id",
            how="left",
        )

        # 表示用
        today_view["種別"] = today_view["session_type"].apply(session_mark)
        today_view["slot_num"] = pd.to_numeric(today_view["slot"], errors="coerce")

        today_view["コマ"] = today_view["slot"]
        today_view["生徒"] = today_view["display_name"].fillna("").astype(str)
      # =====================================================
        # 今日の予定に「今月の回数」を表示
        # 例: 3/4 山田花子
        # =====================================================
        att_df_for_count = load_attendance_log().copy()


        # 今月の「今日より前」の授業回数
        month_done_map = {}
        if not att_df_for_count.empty and {"student_id", "date", "kind"}.issubset(att_df_for_count.columns):
            tmp_att = att_df_for_count.copy()
            tmp_att["student_id"] = tmp_att["student_id"].fillna("").astype(str).str.strip()
            tmp_att["date"] = tmp_att["date"].fillna("").astype(str).str.strip()
            tmp_att["kind"] = tmp_att["kind"].fillna("").astype(str).str.strip()


            ym = today.strftime("%Y-%m")
            today_str = str(today)


            tmp_att["__ym"] = tmp_att["date"].str.slice(0, 7)
            tmp_att = tmp_att[
                (tmp_att["__ym"] == ym)
                & (tmp_att["date"] < today_str)
                & (tmp_att["kind"].isin(["lesson", "授業"]))
            ]


            if not tmp_att.empty:
                month_done_map = (
                    tmp_att.groupby("student_id")
                    .size()
                    .astype(int)
                    .to_dict()
                )


        # 月回数（students.number_of_times）
        month_target_map = {}
        if {"student_id", "number_of_times"}.issubset(students.columns):
            tmp_stu = students[["student_id", "number_of_times"]].copy()
            tmp_stu["student_id"] = tmp_stu["student_id"].fillna("").astype(str).str.strip()
            tmp_stu["number_of_times_num"] = pd.to_numeric(tmp_stu["number_of_times"], errors="coerce")
            tmp_stu = tmp_stu.dropna(subset=["number_of_times_num"]).copy()


            if not tmp_stu.empty:
                month_target_map = dict(
                    zip(
                        tmp_stu["student_id"],
                        tmp_stu["number_of_times_num"].astype(int)
                    )
                )


        # 今日の中で、その授業が何回目か（同日に2コマある子に対応）
        today_view["_is_lesson"] = ~today_view["session_type"].fillna("").astype(str).str.strip().str.lower().isin(
            ["self", "selfstudy", "自習"]
        )
        today_view["_today_lesson_seq"] = 0


        lesson_mask = today_view["_is_lesson"] == True
        if lesson_mask.any():
            seq_df = today_view.loc[lesson_mask].sort_values(["student_id", "slot_num"]).copy()
            seq_df["_today_lesson_seq"] = seq_df.groupby("student_id").cumcount() + 1
            today_view.loc[seq_df.index, "_today_lesson_seq"] = seq_df["_today_lesson_seq"]


        # 表示用の生徒名を作る
        def add_month_count_prefix(r: pd.Series) -> str:
            name = str(r.get("生徒", "")).strip()
            sid = str(r.get("student_id", "")).strip()


            if not name or not sid:
                return name


            # 自習は回数表示しない
            if not bool(r.get("_is_lesson", False)):
                return name


            target = month_target_map.get(sid)
            if target is None or target <= 0:
                return name


            done_before_today = int(month_done_map.get(sid, 0))
            seq_today = int(r.get("_today_lesson_seq", 1) or 1)


            current_num = done_before_today + seq_today
            return f"{current_num}/{target} {name}"


        today_view["生徒"] = today_view.apply(add_month_count_prefix, axis=1)

        # 今日が検定日の生徒には 🔴 印（文字色は変えない）
        if "student_id" in today_view.columns and isinstance(today_exam_ids, set) and len(today_exam_ids) > 0:
            today_view["生徒"] = today_view.apply(
                lambda r: ("🔴 " + str(r.get("生徒","")).strip()) if str(r.get("student_id","")) in today_exam_ids else str(r.get("生徒","")).strip(),
                axis=1,
            )

        for c in ["start", "end", "現在コース", "現在項目", "状態", "note"]:
            if c in today_view.columns:
                today_view[c] = today_view[c].fillna("").astype(str)

        # さらに保険：完全重複を潰す（増殖防止）
        today_view = today_view.drop_duplicates(subset=["student_id", "weekday", "slot", "session_type", "start", "end"], keep="first")

        today_view = today_view.sort_values(by=["slot_num", "join_date", "生徒"], na_position="last")

        if len(today_view) == 0:
            st.info("今日の予定はありません。（weekday/slot / overrides を確認してね）")
        else:
            view_mode = st.radio(
                "表示形式",
                ["B：コマごとにまとめる（おすすめ）", "A：1行=1件（詳細）"],
                horizontal=True,
                index=0,
            )

            if view_mode.startswith("A"):
                show_cols = ["コマ", "start", "end", "生徒", "種別", "現在コース", "現在項目", "状態", "note"]
                show_cols = [c for c in show_cols if c in today_view.columns]
                df_show = today_view[show_cols].copy()

                def _pink_today_exam_student(row: pd.Series):
                    # 検定予定の生徒は「うすピンク」で強調（既存仕様）
                    sid = ""
                    if "student_id" in today_view.columns:
                        try:
                            sid = str(today_view.loc[row.name, "student_id"])
                        except Exception:
                            sid = ""

                    if sid in today_exam_ids:
                        return ["background-color: #fff0f5"] * len(row)  # うすピンク

                    # A表示は「コマ」ごとに背景色（見やすさ優先）
                    slot_num = None
                    try:
                        if "slot_num" in today_view.columns:
                            slot_num = int(today_view.loc[row.name, "slot_num"])
                        else:
                            s = str(row.get("コマ", "")).strip()
                            if s.isdigit():
                                slot_num = int(s)
                    except Exception:
                        slot_num = None

                    palette = ["#f7f7ff", "#f3fbff", "#f4fff6", "#fff9f0", "#fff3f7", "#f6fffd", "#fffdf6", "#f5f0ff"]
                    if slot_num is None or slot_num <= 0:
                        return [""] * len(row)
                    color = palette[(slot_num - 1) % len(palette)]
                    return [f"background-color: {color}"] * len(row)

                st.dataframe(
                    df_show.style.apply(_pink_today_exam_student, axis=1),
                    use_container_width=True,
                    hide_index=True,
                )


            else:
                # --- B案：コマ（時間）ごとにまとめて、同じコマの生徒を縦に並べる ---
                def fmt_line(r: pd.Series) -> str:
                    # B案は「名前だけ」でスッキリ表示
                    name = str(r.get("生徒","")).strip()
                    mark = str(r.get("種別","")).strip()
                    return f"{name}{mark}".strip()

                gcols = ["slot_num", "コマ", "start", "end"]
                base = today_view.copy()
                base["line"] = base.apply(fmt_line, axis=1)

                grouped = (
                    base.sort_values(by=["slot_num", "生徒"], na_position="last")
                        .groupby(gcols, dropna=False)["line"]
                        .apply(lambda s: "\n".join([x for x in s.tolist() if str(x).strip()]))
                        .reset_index()
                )
                grouped = grouped.sort_values(by=["slot_num"], na_position="last")

                grouped = grouped.rename(columns={"line": "予定（生徒ごと）"})
                show_cols = ["コマ", "start", "end", "予定（生徒ごと）"]
                st.dataframe(grouped[show_cols], use_container_width=True, hide_index=True)


        # =====================================================
        # ✅ 出席ログ（授業/自習）: 予定ではなく実績を記録
        #    → 作業完了管理寄り（未確認を先に表示）
        # =====================================================
        with st.expander("✅ 出席記録（授業/自習）", expanded=False):
            st.caption("来たタイミングで『記録』を押すだけ。確認済みは下に分かれます。")
            att_df = load_attendance_log()


            # 今日の予定に出ている生徒（重複除去・表示順維持）
            ids_in_today = []
            if "student_id" in today_view.columns:
                for _sid in today_view["student_id"].astype(str).tolist():
                    _sid = str(_sid).strip()
                    if _sid and _sid not in ids_in_today:
                        ids_in_today.append(_sid)


            if not ids_in_today:
                st.info("今日の予定の生徒が見つからないため、出席記録は表示できません。")
            else:
                # id -> name
                name_map = {}
                if "student_id" in students.columns:
                    if "display_name" in students.columns:
                        name_map = dict(
                            zip(
                                students["student_id"].astype(str).str.strip(),
                                students["display_name"].astype(str).str.strip()
                            )
                        )
                    elif "name" in students.columns:
                        name_map = dict(
                            zip(
                                students["student_id"].astype(str).str.strip(),
                                students["name"].astype(str).str.strip()
                            )
                        )


                # 今日の予定を「未確認」「確認済み」に分ける
                pending_ids = []
                done_ids = []
                rec_map = {}


                for sid in ids_in_today:
                    rec = get_attendance_today(att_df, sid, today)
                    rec_map[sid] = rec
                    if rec is None:
                        pending_ids.append(sid)
                    else:
                        done_ids.append(sid)


                show_done = st.checkbox("確認済みも表示", value=False, key=f"att_show_done_{today}")


                st.markdown(f"**未確認：{len(pending_ids)}件**")
                target_ids = pending_ids if not show_done else ids_in_today


                if not target_ids:
                    st.success("未確認の出席記録はありません。")
                else:
                    for sid in target_ids:
                        nm = name_map.get(sid, "")
                        label = f"{sid}｜{nm}" if nm else sid


                        rec = rec_map.get(sid)
                        rec_kind = (rec.get("kind", "") if rec else "").strip()
                        rec_memo = (rec.get("memo", "") if rec else "").strip()


                        kind_options = [("lesson", "授業"), ("selfstudy", "自習")]
                        default_kind = "lesson"
                        if rec_kind in ["selfstudy", "自習"]:
                            default_kind = "selfstudy"


                        month_lesson_cnt = count_month_lessons(att_df, sid, today)


                        would_be = month_lesson_cnt
                        if rec is None:
                            would_be = month_lesson_cnt + 1


                        badge = f"今月の授業回数：{month_lesson_cnt}回"
                        if rec is None:
                            badge += f"（今日が授業なら {would_be}回目）"
                        else:
                            badge += "（本日は記録済み）"


                        with st.container():
                            st.markdown("---")
                            c1, c2, c3, c4 = st.columns([3, 2, 3, 2])


                            with c1:
                                prefix = "🟡 未確認" if rec is None else "✅ 確認済み"
                                st.markdown(f"**{prefix}｜👤 {label}**")
                                st.caption(badge)


                            with c2:
                                opt_labels = [x[1] for x in kind_options]
                                opt_vals = [x[0] for x in kind_options]
                                idx = opt_vals.index(default_kind) if default_kind in opt_vals else 0
                                picked = st.selectbox(
                                    "種別",
                                    opt_labels,
                                    index=idx,
                                    key=f"att_kind_{today}_{sid}"
                                )
                                picked_kind = kind_options[opt_labels.index(picked)][0]


                            with c3:
                                rec_count = 1
                                if rec and isinstance(rec, dict):
                                    try:
                                        sid2 = str(sid).strip()
                                        ds2 = str(today)
                                        rec_count = int(
                                            len(
                                                att_df[
                                                    (att_df["student_id"].astype(str).str.strip() == sid2)
                                                    & (att_df["date"].astype(str).str.strip() == ds2)
                                                ]
                                            )
                                        )
                                        rec_count = max(1, rec_count)
                                    except Exception:
                                        rec_count = 1


                                count = st.selectbox(
                                    "回数",
                                    [1, 2, 3, 4, 5],
                                    index=min(max(rec_count - 1, 0), 4),
                                    key=f"att_count_{today}_{sid}"
                                )
                                memo = st.text_input(
                                    "メモ（任意）",
                                    value=rec_memo,
                                    key=f"att_memo_{today}_{sid}"
                                )


                            with c4:
                                if st.button("✅ 記録/更新", key=f"att_save_{today}_{sid}"):
                                    att_df2 = upsert_attendance(att_df, sid, today, picked_kind, memo, count=count)
                                    save_attendance_log(att_df2)
                                    st.success("保存しました。")
                                    st.rerun()


                                if st.button("↩ 取消", key=f"att_del_{today}_{sid}"):
                                    att_df2 = delete_attendance(att_df, sid, today)
                                    save_attendance_log(att_df2)
                                    st.success("取り消しました。")
                                    st.rerun()


                # 確認済みを別枠で表示
                if done_ids:
                    with st.expander(f"✅ 確認済み（{len(done_ids)}件）", expanded=False):
                        for sid in done_ids:
                            nm = name_map.get(sid, "")
                            label = f"{sid}｜{nm}" if nm else sid
                            rec = rec_map.get(sid)
                            rec_kind = (rec.get("kind", "") if rec else "").strip()
                            rec_memo = (rec.get("memo", "") if rec else "").strip()


                            kind_label = "自習" if rec_kind in ["selfstudy", "自習"] else "授業"


                            st.markdown(f"- **{label}** ／ {kind_label}" + (f" ／ {rec_memo}" if rec_memo else ""))

        # =====================================================
        # 今日の例外入力UI（schedule_overrides.csv） ※ここだけ
        # - 「今日の予定の下」専用
        # - 管理画面の例外入力は将来的に削除予定（重複事故防止）
        # =====================================================
        with st.expander("📝 今日の例外（追加 / キャンセル / 時間変更）", expanded=False):
            st.caption("この画面だけで“今日のスケジュール例外”を登録します（schedule_overrides.csv）。")

            # 例外DF（ヘッダーは既存前提：safe_read_csvで列は揃っている想定）
            ov_df = schedule_overrides.copy()
            if ov_df.empty:
                ov_df = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"])

            # -----------------------------
            # 生徒候補（今日の予定の生徒を先頭に）
            # -----------------------------
            stu_for_pick = base_students[["student_id", "display_name"]].copy()
            stu_for_pick["student_id"] = stu_for_pick["student_id"].astype(str).str.strip()
            stu_for_pick["display_name"] = stu_for_pick["display_name"].astype(str).str.strip()

            ids_in_today = []
            if "student_id" in today_view.columns and not today_view.empty:
                for _sid in today_view["student_id"].astype(str).tolist():
                    _sid = str(_sid).strip()
                    if _sid and _sid not in ids_in_today:
                        ids_in_today.append(_sid)

            # 今日の予定にいない生徒は後ろ（表示名で安定ソート）
            rest_ids = [sid for sid in stu_for_pick["student_id"].tolist() if sid and sid not in ids_in_today]
            rest_ids_sorted = sorted(rest_ids, key=lambda s: str(stu_for_pick.loc[stu_for_pick["student_id"] == s, "display_name"].iloc[0] if (stu_for_pick["student_id"] == s).any() else s))

            ordered_ids = ids_in_today + rest_ids_sorted
            stu_for_pick = stu_for_pick.set_index("student_id").loc[ordered_ids].reset_index()

            name_map = dict(zip(stu_for_pick["student_id"], stu_for_pick["display_name"]))
            labels = [f"{sid} | {name_map.get(sid,'')}".strip(" |") for sid in stu_for_pick["student_id"].tolist()]

            if not labels:
                st.info("生徒が見つからないため、例外入力はできません。")
            else:
                # --- 今日の予定から、選択した生徒の「デフォルト値」を引く ---
                # ルール：
                #   1) 今日の予定に入っている生徒なら、その生徒の最初のコマをデフォルト
                #   2) start/end/session_type はその行の値を初期値に
                #
                # Streamlitの制約：widget生成後にsession_stateを書き換えられない
                # → 生徒選択(selectbox)の後、他widget生成の前にdefaultsをsession_stateへ流し込む


                # --- UI（フォームは使わない：生徒を選び直した時に即時で他項目が追従するように） ---
                c1, c2, c3, c4 = st.columns([3, 2, 2, 3])

                with c1:
                    picked_label = st.selectbox("生徒", labels, index=0, key="ov_student_label")
                    picked_sid = picked_label.split("|")[0].strip()

                # 今日の予定（その生徒）を抽出
                _stu_rows = pd.DataFrame()
                if "student_id" in today_view.columns and not today_view.empty:
                    _stu_rows = today_view[today_view["student_id"].astype(str).str.strip() == str(picked_sid).strip()].copy()

                # 候補slot（今日の予定のコマを初期値にしつつ、全コマ候補から選べるようにする）
                today_slot_candidates = []
                if not _stu_rows.empty and "slot" in _stu_rows.columns:
                    tmp_slots = pd.to_numeric(_stu_rows["slot"], errors="coerce").dropna().astype(int).tolist()
                    today_slot_candidates = sorted(list(dict.fromkeys(tmp_slots)))

                slot_candidates = []
                for _df in [timeslots, student_schedule, base_students]:
                    if _df is None or "slot" not in _df.columns:
                        continue
                    try:
                        _slots = pd.to_numeric(_df["slot"], errors="coerce").dropna().astype(int).tolist()
                    except Exception:
                        _slots = []
                    for _s in _slots:
                        if int(_s) not in slot_candidates:
                            slot_candidates.append(int(_s))
                slot_candidates = sorted(slot_candidates)
                if not slot_candidates:
                    slot_candidates = list(range(1, 9))

                default_slot = today_slot_candidates[0] if today_slot_candidates else slot_candidates[0]

                # 生徒が変わったら slot を初期化（widget生成前に）
                ensure_student_scoped_defaults(picked_sid, "ov_slot", default_slot)

                try:
                    _slot_state = int(st.session_state.get("ov_slot", default_slot))
                except Exception:
                    _slot_state = default_slot
                if _slot_state not in slot_candidates:
                    slot_candidates.append(_slot_state)
                    slot_candidates = sorted(slot_candidates)
                _slot_index = slot_candidates.index(_slot_state) if _slot_state in slot_candidates else 0

                with c2:
                    picked_slot = st.selectbox("コマ番号", slot_candidates, index=_slot_index, key="ov_slot")

                with c3:
                    picked_action = st.selectbox("種別", ["cancel", "add"], index=0, key="ov_action")

                # 選択中のslotに応じたデフォルト（start/end/session_type）
                try:
                    cur_slot = int(st.session_state.get("ov_slot", default_slot))
                except Exception:
                    cur_slot = default_slot

                default_start = ""
                default_end = ""
                default_session_type = ""
                if not _stu_rows.empty and "slot" in _stu_rows.columns:
                    _rslot = _stu_rows[pd.to_numeric(_stu_rows["slot"], errors="coerce") == cur_slot]
                    if not _rslot.empty:
                        rr = _rslot.iloc[0].to_dict()
                        default_start = str(rr.get("start", "") or "").strip()
                        default_end = str(rr.get("end", "") or "").strip()
                        default_session_type = str(rr.get("session_type", "") or "").strip()

                # ★重要：start/end/type/note は「生徒+slot」スコープのkeyにする
                scoped_prefix = f"{str(picked_sid).strip()}_{int(cur_slot)}"
                k_type = f"ov_session_type__{scoped_prefix}"
                k_start = f"ov_start__{scoped_prefix}"
                k_end = f"ov_end__{scoped_prefix}"
                k_note = f"ov_note__{scoped_prefix}"

                # 初期値を流し込み（widget生成前）
                if k_type not in st.session_state:
                    st.session_state[k_type] = default_session_type
                if k_start not in st.session_state:
                    st.session_state[k_start] = default_start
                if k_end not in st.session_state:
                    st.session_state[k_end] = default_end
                if k_note not in st.session_state:
                    st.session_state[k_note] = ""

                # 重要：このコマが「授業」か「自習」かは準備に直結するので、明示的に選べるようにする
                cur_type_disp = (default_session_type or st.session_state.get(k_type, "") or "").strip()
                if cur_type_disp:
                    st.markdown(f"**このコマの種別： `{cur_type_disp}`**")
                else:
                    st.markdown("**このコマの種別： `未設定`（必ず設定してください）**")

                with c4:
                    type_options = ["授業", "自習", "検定", "その他（自由入力）"]
                    _default = (st.session_state.get(k_type, "") or default_session_type or "").strip()

                    if _default in type_options:
                        _idx = type_options.index(_default)
                    elif _default:
                        _idx = type_options.index("その他（自由入力）")
                    else:
                        # 安全側：未設定なら「授業」をデフォルト
                        _idx = 0

                    picked_type_choice = st.selectbox("種別（重要）", type_options, index=_idx, key=f"{k_type}__choice")

                    if picked_type_choice == "その他（自由入力）":
                        picked_session_type = st.text_input(
                            "種別（自由入力）",
                            value=_default if _default and _default not in type_options else "",
                            placeholder="例）振替授業 / 面談 / 体験 など",
                            key=k_type,
                        ).strip()
                    else:
                        picked_session_type = picked_type_choice
                        # k_type の永続値としても保持（次回同slotを開いた時の初期値）
                        st.session_state[k_type] = picked_session_type

                if picked_session_type == "授業":
                    st.warning("⚠️ このコマは **授業** です（準備が必要）")
                elif picked_session_type == "自習":
                    st.info("🟦 このコマは **自習** です")

                c5, c6, c7 = st.columns([2, 2, 6])
                with c5:
                    picked_start = st.text_input("開始（任意）", placeholder="例）17:00", key=k_start)
                with c6:
                    picked_end = st.text_input("終了（任意）", placeholder="例）18:00", key=k_end)
                with c7:
                    picked_note = st.text_input("メモ（任意）", placeholder="例）振替 / 体調不良 / 時間変更 など", key=k_note)

                submitted = st.button("今日の例外として保存", key="ov_submit_btn")
                if submitted:
                    dstr = today.strftime("%Y-%m-%d")

                    new_row = {
                        "student_id": str(picked_sid).strip(),
                        "date": dstr,
                        "slot": str(int(picked_slot)),
                        "action": str(picked_action).strip(),
                        "start": str(picked_start).strip(),
                        "end": str(picked_end).strip(),
                        "session_type": str(picked_session_type).strip(),
                        "note": str(picked_note).strip(),
                    }

                    # 同じ (student_id, date, slot) が既にある場合は「置き換え」
                    ov2 = ov_df.copy()
                    for c in ["student_id", "date", "slot"]:
                        if c in ov2.columns:
                            ov2[c] = ov2[c].fillna("").astype(str).str.strip()
                    keymask = (
                        (ov2["student_id"] == new_row["student_id"])
                        & (ov2["date"] == new_row["date"])
                        & (ov2["slot"] == new_row["slot"])
                    )
                    ov2 = ov2[~keymask].copy()

                    ov2 = pd.concat([ov2, pd.DataFrame([new_row])], ignore_index=True)

                    # 保存（既存ヘッダー運用）
                    write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)
                    st.success("保存しました。今日の予定に反映されます。")
                    st.rerun()
            st.divider()

            # 今日の例外一覧（削除ボタン付き）
            dstr = today.strftime("%Y-%m-%d")
            ov_show = ov_df.copy()
            if not ov_show.empty:
                for c in ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]:
                    if c in ov_show.columns:
                        ov_show[c] = ov_show[c].fillna("").astype(str).str.strip()
                ov_today_list = ov_show[ov_show["date"] == dstr].copy()
            else:
                ov_today_list = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"])

            if ov_today_list.empty:
                st.info("今日の例外はまだありません。")
            else:
                # 表示用に名前を付与
                name_map = dict(zip(stu_for_pick["student_id"], stu_for_pick["display_name"]))
                ov_today_list["name"] = ov_today_list["student_id"].map(name_map).fillna("")
                ov_today_list["label"] = ov_today_list.apply(
                    lambda r: f'{r.get("student_id","")} | {r.get("name","")}'.strip(" |"),
                    axis=1,
                )

                show_cols = ["label", "slot", "action", "start", "end", "session_type", "note"]
                show_cols = [c for c in show_cols if c in ov_today_list.columns]
                st.dataframe(ov_today_list[show_cols], use_container_width=True, hide_index=True)

                st.caption("削除したい場合：下のボタンで“その行”を削除します。")
                for i, r in ov_today_list.reset_index(drop=True).iterrows():
                    sid = str(r.get("student_id","")).strip()
                    slot = str(r.get("slot","")).strip()
                    action = str(r.get("action","")).strip()
                    label = str(r.get("label","")).strip()
                    btn = f"🗑 削除：{label} / slot {slot} / {action}"
                    if st.button(btn, key=f"ov_del_{dstr}_{sid}_{slot}_{action}_{i}"):
                        ov2 = ov_df.copy()
                        for c in ["student_id", "date", "slot", "action"]:
                            if c in ov2.columns:
                                ov2[c] = ov2[c].fillna("").astype(str).str.strip()
                        mask = (
                            (ov2["student_id"] == sid)
                            & (ov2["date"] == dstr)
                            & (ov2["slot"] == slot)
                            & (ov2["action"] == action)
                        )
                        ov2 = ov2[~mask].copy()
                        write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)
                        st.success("削除しました。")
                        st.rerun()

    # =========================================================
    # Scratch最高級（唯一の正: kentei_results.csv）
    # =========================================================
    kentei_results = load_kentei_results().copy()


    scratch_best = pd.DataFrame(columns=["student_id", "grade", "display_name", "item"])


    if not kentei_results.empty:
        kentei_results["student_id"] = kentei_results["student_id"].fillna("").astype(str).str.strip()
        kentei_results["grade"] = kentei_results["grade"].fillna("").astype(str).str.strip()


        # 数字が小さいほど上位級（3級 > 4級 ではなく、3級の方が上）
        kentei_results["kentei_num"] = pd.to_numeric(kentei_results["grade"], errors="coerce")
        kentei_results = kentei_results.dropna(subset=["kentei_num"]).copy()
        kentei_results["kentei_num"] = kentei_results["kentei_num"].astype(int)


        # 生徒ごとに最上位（最小の数字）を採用
        scratch_best = (
            kentei_results.sort_values(by=["student_id", "kentei_num"], ascending=[True, True])
            .groupby("student_id", as_index=False)
            .first()
        )


        scratch_best = scratch_best.merge(
            students[["student_id", "display_name", "grade"]],
            on="student_id",
            how="left",
            suffixes=("", "_student")
        )


        # 表示用 item を作る
        scratch_best["item"] = "検定" + scratch_best["grade"].astype(str).str.strip() + "級"



    # =========================================================
    # Latest per item
    # =========================================================
    log_all_sorted = log_all.copy()
    log_all_sorted["date_dt"] = pd.to_datetime(log_all_sorted["date"], errors="coerce")
    log_all_sorted = log_all_sorted.dropna(subset=["date_dt"]).copy()
    log_all_sorted = log_all_sorted.sort_values(by=["student_id", "curriculum", "item", "date_dt"])
    latest = log_all_sorted.groupby(["student_id", "curriculum", "item"], as_index=False).tail(1)

    latest_filtered = latest.copy()
    if selected_grade != "（全て）":
        latest_filtered = latest_filtered[latest_filtered["grade"] == selected_grade]
    if selected_student != "（全員）":
        latest_filtered = latest_filtered[latest_filtered["display_name"] == selected_student]
    if selected_curriculum != "（全て）":
        latest_filtered = latest_filtered[latest_filtered["curriculum"] == selected_curriculum]
    if selected_status != "（全て）":
        latest_filtered = latest_filtered[norm_lower(latest_filtered["status"]) == selected_status]

    # =========================================================
    # Tabs
    # =========================================================
    tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
       # ['生徒ごと一覧', '生徒別（done）', 'コース別（件数）', 'Scratch最高級', '詳細（最新状態）', 'カリキュラム課題', '検定課題']
       ['カリキュラム課題', '検定課題','コース別（件数）',  'Scratch最高級','生徒ごと一覧', '生徒別（done）', '詳細（最新状態）', ]
    )

    with tab0:
         #カリキュラム課題
        st.subheader("✅ カリキュラム課題（進捗チェック）")

        st.caption("※ ここは『進捗チェック』です。課題そのものの登録/編集/削除は 管理（入力） → 📘 カリキュラム管理 で行います。")
        if st.button("📘 課題を登録・編集する（管理へ移動）", key="goto_admin_curr_from_view"):
            st.session_state["pending_page"] = "管理（入力）"
            st.rerun()

        #if curr_courses.empty or curr_tasks.empty or curr_prog.empty:
        #    st.info("curriculum_courses/tasks/progress のCSVが揃っていないため、この機能はスキップします。")
        #    st.stop()

        #if selected_student == "（全員）":
        #    st.info("左のフィルタから、生徒を1人選んでください。")
        #    st.stop()
        if curr_courses.empty or curr_tasks.empty or curr_prog.empty:
             st.info("curriculum_courses/tasks/progress のCSVが揃っていないため、この機能はスキップします。")
        elif selected_student == "（全員）":
             st.info("左のフィルタから、生徒を1人選んでください。")
        else:
             student_row = students[students["display_name"] == selected_student].head(1)

             if student_row.empty:
                st.warning("生徒情報が見つかりません。")
             else:
                student_id = str(student_row["student_id"].iloc[0]).strip()
                st.markdown(f"👤 **編集対象**：{student_id}｜{selected_student}")

                can_render_tab0 = True

                if curr_courses.empty or curr_tasks.empty or curr_prog.empty:
                    st.info("curriculum_courses/tasks/progress のCSVが揃っていないため、この機能はスキップします。")
                    can_render_tab0 = False

                if selected_student == "（全員）":
                    st.info("左のフィルタから、生徒を1人選んでください。")
                    can_render_tab0 = False

                if can_render_tab0:
                    student_row = students[students["display_name"] == selected_student].head(1)
                    if student_row.empty:
                        st.warning("生徒情報が見つかりません。")
                    else:
                        student_id = str(student_row["student_id"].iloc[0]).strip()
                       # st.markdown(f"👤 **編集対象**：{student_id}｜{selected_student}")

                        # ここから下の tab0 の残り処理をインデント1段下げて入れる

                    student_row = students[students["display_name"] == selected_student].head(1)
                    if student_row.empty:
                        st.warning("生徒情報が見つかりません。")
                        st.stop()
                    student_id = str(student_row["student_id"].iloc[0]).strip()
                  #  st.markdown(f"👤 **編集対象**：{student_id}｜{selected_student}")

                    # Course selector with order
                    cc = curr_courses.copy()
                    cc = cc[cc["is_active"].fillna("").astype(str).str.strip().str.lower().replace("", "true").isin(["true", "1", "yes"])].copy()
                    cc["order_num"] = pd.to_numeric(cc["course_order"], errors="coerce").fillna(9999).astype(int)
                    cc = cc.sort_values(by=["order_num", "genre_name", "course_name"], na_position="last")

                    course_labels = []
                    course_ids = []
                    for _, r in cc.iterrows():
                        cid = str(r["course_id"])
                        course_ids.append(cid)
                        course_labels.append(f"{r['genre_name']}｜{r['course_name']}  [{cid}]")

                    # 方法A：進捗CSVの最新更新コースをデフォルトにする
                    default_course_id = latest_course_for_student(student_id, curr_prog)
                    default_index = 0
                    if default_course_id and default_course_id in course_ids:
                        default_index = course_ids.index(default_course_id)

                    ensure_student_scoped_defaults(student_id, "progress_course", course_labels[default_index] if course_labels else "")

                    selected_course_label = st.selectbox("コース", course_labels, key="progress_course")
                    selected_course_id = selected_course_label.split("[")[-1].rstrip("]")

                    # Lock done tasks unless override
                    is_locked_done_tasks = (not override_done_lock)

                    # tasks for course (common + student-specific)
                    t = curr_tasks.copy()
                    t["student_id"] = t["student_id"].fillna("").astype(str).str.strip()
                    t = t[
                        (t["course_id"].astype(str).str.strip() == str(selected_course_id).strip())
                        & (
                            (t["student_id"] == "")
                            | (t["student_id"] == student_id)
                        )
                    ].copy()

                   # if t.empty:
                   #     st.info("このコースの課題が登録されていません。")
                   #     st.stop()

                    if t.empty:
                      st.info("このコースの課題が登録されていません。")
                    else:


                        t["order_num"] = pd.to_numeric(t["order"], errors="coerce")
                        t = t.sort_values(by=["order_num", "task_name"], na_position="last")


                    # --- コース完了(done) 登録 ---
                    # progress_log.csv に「この生徒はこのコースを完了した」を1行で保存します。
                    # 課題チェック（どこまで進んだか）は curriculum_progress.csv に保存するので役割を分離。
                    course_row = curr_courses[curr_courses["course_id"].astype(str).str.strip() == str(selected_course_id).strip()].copy()
                    genre_id = str(course_row["genre_id"].iloc[0]).strip() if not course_row.empty else ""
                    course_name = str(course_row["course_name"].iloc[0]).strip() if not course_row.empty else ""

                    st.markdown('---')
                    st.caption("コース完了（done）は、課題が全て終わっていなくても付けられます")

                    col_done1, col_done2 = st.columns([1, 2])
                    with col_done1:
                        mark_done = st.checkbox(
                            "このカリキュラムを完了にする",
                            value=False,
                            key=f"mark_course_done_{student_id}_{selected_course_id}",
                        )
                    with col_done2:
                        if st.button(
                            "完了を保存",
                            disabled=not mark_done,
                            key=f"save_course_done_{student_id}_{selected_course_id}",
                        ):
                            today_str = datetime.now().strftime('%Y-%m-%d')
                            new_row = {
                                'date': today_str,
                                'student_id': str(student_id).strip(),
                                'curriculum': str(genre_id).strip(),
                                'item': str(course_name).strip(),
                                'status': 'done',
                                'note': 'course_done',
                            }

                            df_log = log.copy()
                            if df_log.empty:
                                df_log = pd.DataFrame([new_row])
                            else:
                                mask = (
                                    df_log['student_id'].astype(str).str.strip() == str(student_id).strip()
                                ) & (
                                    df_log['curriculum'].astype(str).str.strip() == str(genre_id).strip()
                                ) & (
                                    df_log['item'].astype(str).str.strip() == str(course_name).strip()
                                )
                                if mask.any():
                                    df_log.loc[mask, 'date'] = today_str
                                    df_log.loc[mask, 'status'] = 'done'
                                    df_log.loc[mask, 'note'] = 'course_done'
                                else:
                                    df_log = pd.concat([df_log, pd.DataFrame([new_row])], ignore_index=True)

                            write_csv_atomic(df_log, PROGRESS_LOG_CSV)
                            st.success("保存しました（コース完了）")
                            st.rerun()

                    p = curr_prog.copy()
                    p = p[(p["student_id"].astype(str).str.strip() == student_id) & (p["course_id"].astype(str).str.strip() == str(selected_course_id).strip())].copy()
                    done_map = {str(r["task_id"]).strip(): (str(r["is_done"]).strip().lower() == "true") for _, r in p.iterrows()}

                    st.markdown("### 課題一覧")
                    updated_rows = []

                    for _, row in t.iterrows():
                        task_id = str(row["task_id"]).strip()
                        task_name = str(row["task_name"]).strip()
                        was_done = bool(done_map.get(task_id, False))
                        disabled = (was_done and is_locked_done_tasks)

                        checked = st.checkbox(
                            task_name,
                            value=was_done,
                            key=f"curr_{student_id}_{selected_course_id}_{task_id}",
                            disabled=disabled
                        )

                        updated_rows.append({
                            "student_id": student_id,
                            "course_id": str(selected_course_id).strip(),
                            "task_id": task_id,
                            "is_done": "true" if checked else "false",
                            "done_date": dt.date.today().isoformat() if checked else "",
                            "note": ""
                        })


                    if st.button("💾 保存（カリキュラム課題）"):
                        new_df = pd.DataFrame(updated_rows)

                        others = curr_prog[
                            ~(
                                (curr_prog["student_id"].astype(str).str.strip() == student_id)
                                & (curr_prog["course_id"].astype(str).str.strip() == str(selected_course_id).strip())
                            )
                        ].copy()

                        save_df = pd.concat([others, new_df], ignore_index=True)
                        write_csv_atomic(save_df, CURRICULUM_PROGRESS_CSV)
                        st.success("保存しました。")
                        st.rerun()

                    if is_locked_done_tasks:
                        st.caption("※ 完了済みの課題は誤操作防止のためロックしています（右の⚠で解除できます）。")
    with tab1:
        #検定課題

        st.subheader("📝 検定課題の進捗（チェック入力）")

        if kentei_tasks.empty or kentei_prog.empty:
             st.info("kentei_tasks / kentei_progress が揃っていないため、この機能はスキップします。")
        elif selected_student == "（全員）":
            st.info("左のフィルタから、生徒を1人選んでください。")
        else:
            student_row = students[students["display_name"] == selected_student].head(1)


            if student_row.empty:
                 st.warning("生徒情報が見つかりません。")
            else:
                 student_id = str(student_row["student_id"].iloc[0]).strip()
                 st.markdown(f"👤 **編集対象**：{student_id}｜{selected_student}")


            # ↓↓↓ ここから下を全部インデント1段下げる ↓↓↓
            if kentei_tasks.empty:
                st.info("この級の課題が登録されていません。")


      #  if kentei_tasks.empty or kentei_prog.empty:
      #      st.info("kentei_tasks / kentei_progress が揃っていないため、この機能はスキップします。")
      #      st.stop()

       # if selected_student == "（全員）":
       #     st.info("左のフィルタから、生徒を1人選んでください。")
       #     st.stop()

       # student_row = students[students["display_name"] == selected_student].head(1)
      #  if student_row.empty:
       #     st.warning("生徒情報が見つかりません。")
       #     st.stop()
       # student_id = str(student_row["student_id"].iloc[0]).strip()
       # st.markdown(f"👤 **編集対象**：{student_id}｜{selected_student}")

        # 生徒切替時：検定予定（kentei_exam_schedule.csv）から直近の級をデフォルトにする
            _default_k_grade = None
            try:
                if not kentei_exam.empty:
                    dfk = kentei_exam[kentei_exam["student_id"].astype(str).str.strip() == student_id].copy()
                    if not dfk.empty and "exam_date" in dfk.columns:
                        dfk["__d"] = pd.to_datetime(dfk["exam_date"], errors="coerce")
                        dfk = dfk.dropna(subset=["__d"]).sort_values("__d", ascending=True)
                    if not dfk.empty and "grade" in dfk.columns:
                        _default_k_grade = str(dfk.iloc[0]["grade"]).strip()
            except Exception:
                _default_k_grade = None

            grade_options = ["1", "2", "3", "4"]
            if _default_k_grade in grade_options:
                ensure_student_scoped_defaults(student_id, "kentei_grade", _default_k_grade)
            else:
                ensure_student_scoped_defaults(student_id, "kentei_grade", "4")  # よく使う級に寄せる（必要なら変更OK）

            grade_sel = st.selectbox("検定の級", grade_options, key="kentei_grade")

            # 合格ロック（判定は kentei_results.csv を唯一の正とする）
            passed_this_grade = is_kentei_passed(student_id, grade_sel)

            is_locked = passed_this_grade and (not st.session_state.get("override_passed_lock", False))

            if passed_this_grade and (not st.session_state.get("override_passed_lock", False)):
                st.info("この級は合格済みのため、通常は編集できません（左の⚠で解除できます）")
            elif passed_this_grade and st.session_state.get("override_passed_lock", False):
                st.warning("⚠ 合格済み級の編集モードです。保存内容に注意してください")

            # tasks: common + student-specific
            tasks = kentei_tasks.copy()
            tasks["student_id"] = tasks["student_id"].fillna("").astype(str).str.strip()
            tasks = tasks[
                (tasks["grade"].astype(str).str.strip() == grade_sel)
                & (
                    (tasks["student_id"] == "")
                    | (tasks["student_id"] == student_id)
                )
            ].copy()

            if tasks.empty:
                st.info("この級の課題が登録されていません。")
                st.stop()

            tasks["order_num"] = pd.to_numeric(tasks["order"], errors="coerce")
            tasks = tasks.sort_values(by=["order_num", "task_name"], na_position="last")

            prog = kentei_prog[
                (kentei_prog["student_id"].astype(str).str.strip() == student_id)
                & (kentei_prog["grade"].astype(str).str.strip() == grade_sel)
            ].copy()

            done_map = {str(r["task_id"]).strip(): (str(r["is_done"]).strip().lower() == "true") for _, r in prog.iterrows()}

            st.markdown("### 課題一覧")
            updated = []

            for _, row in tasks.iterrows():
                task_id = str(row["task_id"]).strip()
                checked = st.checkbox(
                    str(row["task_name"]).strip(),
                    value=bool(done_map.get(task_id, False)),
                    key=f"kentei_{student_id}_{grade_sel}_{task_id}",
                    disabled=is_locked
                )

                updated.append({
                    "student_id": student_id,
                    "grade": grade_sel,
                    "task_id": task_id,
                    "is_done": "true" if checked else "false",
                    "done_date": dt.date.today().isoformat() if checked else "",
                    "note": ""
                })

            if st.button("💾 保存（検定課題）", disabled=is_locked):
                new_df = pd.DataFrame(updated)

                others = kentei_prog[
                    ~(
                        (kentei_prog["student_id"].astype(str).str.strip() == student_id)
                        & (kentei_prog["grade"].astype(str).str.strip() == grade_sel)
                    )
                ].copy()

                save_df = pd.concat([others, new_df], ignore_index=True)
                write_csv_atomic(save_df, KENTEI_PROGRESS_CSV)
                st.success("保存しました。")
                st.rerun()

            # =========================================================
            # 🎓 検定 合格登録（B方式）
            #   ※ 合格判定は kentei_results.csv のみ（Single Source of Truth）
            # =========================================================
            with st.expander("🎓 検定 合格登録（B方式）", expanded=False):
                # kentei_results.csv を合格判定の唯一の正にする
                results_df = load_kentei_results().copy()

                # 対象生徒：左フィルタで選ばれていれば固定、なければ選択
                current_student = st.session_state.get("selected_student_id", None)
                if current_student:
                    student_for_pass = str(current_student).strip()
                    st.info(f"対象生徒: {student_for_pass}")
                else:
                    # 表示は「ID｜名前」
                    tmp = students.copy()
                    if "display_name" in tmp.columns:
                        tmp["_label"] = tmp["student_id"].astype(str).str.strip() + "｜" + tmp["display_name"].astype(str).str.strip()
                    else:
                        tmp["_label"] = tmp["student_id"].astype(str).str.strip()
                    labels = tmp["_label"].tolist()
                    picked = st.selectbox("生徒を選択", labels, key="pass_pick_student")
                    student_for_pass = str(picked).split("｜")[0].strip()

                st.markdown("### ✅ 新規登録")
                grade_for_pass = st.text_input("合格した級", value="", key="pass_new_grade")
                score_for_pass = st.text_input("点数（任意）", value="", key="pass_new_score")
                pass_date = st.date_input("合格日", value=date.today(), key="pass_new_date")
                pass_memo = st.text_area("メモ（任意）", value="", key="pass_new_memo")
                colA, colB = st.columns([1, 2])
                with colA:
                    if st.button("✅ 合格として登録", key="pass_add_btn"):
                        if grade_for_pass.strip() == "":
                            st.error("級を入力してください。")
                        else:
                            new_row = pd.DataFrame([{
                                "student_id": str(student_for_pass).strip(),
                                "grade": str(grade_for_pass).strip(),
                                "score": str(score_for_pass).strip(),
                                "pass_date": str(pass_date),
                                "memo": str(pass_memo).strip()
                            }])
                            results_df = pd.concat([results_df, new_row], ignore_index=True)
                            save_kentei_results(results_df)

                            # B方式：進捗側も一括合格反映（存在する場合のみ）
                            try:
                                if "kentei_prog" in globals():
                                    prog = kentei_prog
                                    if "student_id" in prog.columns and "grade" in prog.columns:
                                        mask = (
                                            prog["student_id"].astype(str).str.strip() == str(student_for_pass).strip()
                                        ) & (
                                            prog["grade"].astype(str).str.strip() == str(grade_for_pass).strip()
                                        )
                                        if "status" in prog.columns:
                                            prog.loc[mask, "status"] = "passed"
                                            write_csv_atomic(prog, KENTEI_PROGRESS_CSV)
                            except Exception:
                                st.warning("進捗一括更新でエラーが発生しましたが、合格登録自体は完了しています。")

                            st.success("保存しました。")
                            st.rerun()
                with colB:
                    st.caption("※ 間違えた場合は下の「修正／削除」から変更できます。")

                st.divider()
                st.markdown("### ✏️ 修正／削除（間違えたとき）")

                # 対象生徒の合格履歴だけに絞る
                df_s = results_df.copy()
                if not df_s.empty and "student_id" in df_s.columns:
                    df_s = df_s[df_s["student_id"].astype(str).str.strip() == str(student_for_pass).strip()].copy()
                else:
                    df_s = pd.DataFrame(columns=["student_id", "grade", "pass_date", "memo"])

                if df_s.empty:
                    st.info("この生徒の合格履歴はまだありません。")
                else:
                    # 表示用ラベル
                    def _mk_label(r):
                        g = str(r.get("grade", "")).strip()
                        d = str(r.get("pass_date", "")).strip()
                        m = str(r.get("memo", "")).strip()
                        if m:
                            m = m.replace("\n", " ")
                            m = (m[:30] + "…") if len(m) > 30 else m
                            return f"{d}｜{g}｜{m}"
                        return f"{d}｜{g}"

                    df_s = df_s.reset_index(drop=True)
                    df_s["_label"] = df_s.apply(_mk_label, axis=1)

                    picked_label = st.selectbox("修正したい行を選択", df_s["_label"].tolist(), key="pass_edit_pick")
                    row = df_s[df_s["_label"] == picked_label].iloc[0]

                    edit_grade = st.text_input("級（修正）", value=str(row.get("grade", "")), key="pass_edit_grade")
                    try:
                        _d = pd.to_datetime(row.get("pass_date", ""), errors="coerce")
                        _d = _d.date() if pd.notna(_d) else date.today()
                    except Exception:
                        _d = date.today()
                    edit_score = st.text_input("点数（修正）", value=str(row.get("score", "")), key="pass_edit_score")
                    edit_date = st.date_input("合格日（修正）", value=pd.to_datetime(row.get("pass_date", date.today())).date(), key="pass_edit_date")
                    edit_memo = st.text_area("メモ（修正）", value=str(row.get("memo", "")), key="pass_edit_memo")


                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if st.button("💾 修正を保存", key="pass_save_edit"):
                            sid = str(student_for_pass).strip()
                            old_g = str(row.get("grade", "")).strip()
                            old_d = str(row.get("pass_date", "")).strip()
                            old_m = str(row.get("memo", "")).strip()

                            mask = (
                                results_df["student_id"].astype(str).str.strip() == sid
                            ) & (
                                results_df["grade"].astype(str).str.strip() == old_g
                            ) & (
                                results_df["pass_date"].astype(str).str.strip() == old_d
                            ) & (
                                results_df["memo"].astype(str).str.strip() == old_m
                            )
                            idxs = results_df.index[mask].tolist()
                            if not idxs:
                                st.error("修正対象が見つかりませんでした（CSV手修正などで一致しない可能性）。")
                            else:
                                i = idxs[0]
                                results_df.loc[i, "grade"] = str(edit_grade).strip()
                                results_df.loc[i, "pass_date"] = str(edit_date)
                                results_df.loc[i, "memo"] = str(edit_memo).strip()
                                save_kentei_results(results_df)
                                st.success("修正しました。")
                                st.rerun()

                    with col2:
                        undo_progress = st.checkbox("進捗のpassedも戻す", value=False, key="pass_del_undo_progress")
                    with col3:
                        confirm = st.checkbox("削除してもOK（確認）", value=False, key="pass_del_confirm")
                        if st.button("🗑️ この合格記録を削除", disabled=(not confirm), key="pass_delete_btn"):
                            sid = str(student_for_pass).strip()
                            old_g = str(row.get("grade", "")).strip()
                            old_d = str(row.get("pass_date", "")).strip()
                            old_m = str(row.get("memo", "")).strip()

                            mask = (
                                results_df["student_id"].astype(str).str.strip() == sid
                            ) & (
                                results_df["grade"].astype(str).str.strip() == old_g
                            ) & (
                                results_df["pass_date"].astype(str).str.strip() == old_d
                            ) & (
                                results_df["memo"].astype(str).str.strip() == old_m
                            )
                            before = len(results_df)
                            results_df = results_df.loc[~mask].copy()
                            after = len(results_df)
                            save_kentei_results(results_df)

                            if undo_progress:
                                try:
                                    if "kentei_prog" in globals():
                                        prog = kentei_prog
                                        if "student_id" in prog.columns and "grade" in prog.columns and "status" in prog.columns:
                                            pmask = (
                                                prog["student_id"].astype(str).str.strip() == sid
                                            ) & (
                                                prog["grade"].astype(str).str.strip() == old_g
                                            )
                                            prog.loc[pmask, "status"] = ""
                                            write_csv_atomic(prog, KENTEI_PROGRESS_CSV)
                                except Exception:
                                    st.warning("進捗の戻しでエラーが出ました（合格記録の削除は完了しています）。")

                            st.success(f"削除しました（{before-after}件）。")
                            st.rerun()

    with tab2:
        #コース別（件数
        st.subheader("コース別：完了状況（ジャンル＋コース名）")

        logs_df = log.copy() if 'log' in globals() else pd.DataFrame()

        if logs_df.empty or students.empty or curr_courses.empty:
            st.info("表示できるデータがありません")
        else:
            active_students = students.copy()
            if 'is_active' in active_students.columns:
                try:
                    active_students = active_students[active_students['is_active'] == True]
                except Exception:
                    pass
            if active_students.empty:
                active_students = students.copy()

            active_students['label'] = active_students['student_id'].astype(str) + " | " + active_students['display_name'].astype(str)
            labels = active_students['label'].tolist()
            label_to_id = dict(zip(labels, active_students['student_id'].tolist()))

            selected_label = st.selectbox("生徒を選択", labels, key='course_done_student')
            sid = label_to_id.get(selected_label)

            student_done = logs_df[(logs_df['student_id'].astype(str) == str(sid)) & (logs_df['status'].astype(str) == 'done')].copy()
            done_set = set(zip(student_done['curriculum'].astype(str), student_done['item'].astype(str)))

            cc = curr_courses.copy()
            if 'course_order' in cc.columns:
                cc['course_order_num'] = pd.to_numeric(cc['course_order'], errors='coerce').fillna(9999)
            else:
                cc['course_order_num'] = 9999

            for (genre_id, genre_name), gdf in cc.groupby(['genre_id','genre_name'], dropna=False):
                gdf = gdf.sort_values(by=['course_order_num','course_name'], kind='stable')
                genre_has_done = any((str(genre_id), str(cn)) in done_set for cn in gdf['course_name'].astype(str).tolist())
                genre_mark = '⭕️' if genre_has_done else ''
                title = f"{genre_name} ({genre_id}) {genre_mark}" if str(genre_name).strip() not in ['nan','None',''] else f"{genre_id} {genre_mark}"

                with st.expander(title, expanded=False):
                    for _, row in gdf.iterrows():
                        course_name = str(row.get('course_name',''))
                        mark = '⭕️' if (str(genre_id), course_name) in done_set else ''
                        st.write(f"- {course_name} {mark}")


    with tab3:
       # st.write("DUBUG before= ", len(scratch_best_filtered))
        # ---- 背景色：級ごと（行全体）
        def color_by_grade(row):
            grade_val = ""
            #if "grade" in row:
            #    grade_val = str(row["grade"])
            #elif "item" in row:
            grade_val = str(row["item"])

            if "1" in grade_val:
                color = "#ffd700"      # ゴールド
            elif "2" in grade_val:
                color = "#ffcc80"      # オレンジ
            elif "3" in grade_val:
                color = "#b3e5fc"      # 水色
            elif "4" in grade_val:
                color = "#c8e6c9"      # 緑
            else:
                color = "#ffe6e6"      # 未取得

            return [f"background-color: {color}"] * len(row)

        # Scratch最高級
        st.subheader("Scratch検定：最高取得級（生徒ごと）")


        scratch_best_filtered = scratch_best.copy()


        # フィルタ
        if selected_grade != "（全て）":
            scratch_best_filtered = scratch_best_filtered[
                scratch_best_filtered["grade"] == selected_grade
            ]


        if selected_student != "（全員）":
            scratch_best_filtered = scratch_best_filtered[
                scratch_best_filtered["display_name"] == selected_student
            ]


        # 表示
        if scratch_best_filtered.empty:
            st.info("Scratch検定ログがまだありません。")
        else:


            # grade抽出（検定◯級 → ◯）
            scratch_best_filtered["grade_num"] = (
                scratch_best_filtered["item"]
                .str.extract(r"検定(\d+)級")[0]
                .astype(float)
            )


            # 生徒ごと最高級
            best = (
                scratch_best_filtered
                .sort_values("grade_num", ascending=True)
                .drop_duplicates("student_id", keep="first")
            )


            view = best[["grade", "display_name", "item"]].copy()


            styled = view.style.apply(color_by_grade, axis=1)


            st.dataframe(
                styled,
                use_container_width=True,
                hide_index=True
            )




    with tab4:

         #生徒ごと一覧
        st.subheader("生徒一覧：Scratch検定取得級＋月回数＋完了数（全コース合計）")

        done_counts = log_done.groupby("student_id").size().reset_index(name="done_total")

        if not scratch_best.empty:
            scratch_best_small = scratch_best[["student_id", "item"]].rename(columns={"item": "scratch_best"})
        else:
            scratch_best_small = pd.DataFrame(columns=["student_id", "scratch_best"])

        summary = students.copy()
        summary = summary.merge(done_counts, on="student_id", how="left")
        summary = summary.merge(scratch_best_small, on="student_id", how="left")

        summary["done_total"] = summary["done_total"].fillna(0).astype(int)
        summary["scratch_best"] = summary["scratch_best"].fillna("—")

        # Apply grade/student filters
        if selected_grade != "（全て）":
            summary = summary[summary["grade"] == selected_grade]
        if selected_student != "（全員）":
            summary = summary[summary["display_name"] == selected_student]

        show_cols = ["grade", "display_name", "number_of_times", "scratch_best", "done_total"]
        summary_show = summary.sort_values(by=["join_date", "display_name"], na_position="last")[show_cols]
        st.dataframe(summary_show, use_container_width=True, hide_index=True)
        st.caption("done_total は progress_log.csv の status=done の行数（全コース合計）です。")



    with tab5:

         #生徒別（done）
        st.subheader("生徒別：完了したもの（done）")
        cols = ["date", "grade", "display_name", "curriculum", "item", "note"]
        cols = [c for c in cols if c in filtered_done.columns]
        show = filtered_done[cols].sort_values(by=["grade", "display_name", "date", "curriculum", "item"])
        st.dataframe(show, use_container_width=True, hide_index=True)

    with tab6:
         #詳細（最新状態）
        st.subheader("項目ごとの最新状態（フィルタ反映）")
        cols = ["date", "grade", "display_name", "curriculum", "item", "status", "note"]
        cols = [c for c in cols if c in latest_filtered.columns]
        st.dataframe(
            latest_filtered[cols].sort_values(by=["grade", "display_name", "curriculum", "item"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("※ 同じ項目が複数回ログにあっても、最後の状態だけ表示します。")





else:
    # 管理画面中は、左サイドバーの閲覧フィルタを無効化
    st.sidebar.header("管理")
    override_passed_lock = st.session_state.get("override_passed_lock", False)  # (v6.5.5) 2重生成防止

    # NOTE: 閲覧側のサイドバーでも同じ設定をcheckboxとして生成している。
    # Streamlitは同一keyの要素を同一実行内で2回生成できないため、管理側は別keyで表示し、
    # 値だけを session_state["override_done_lock"] に同期する。
    override_done_lock_admin = st.sidebar.checkbox(
        "⚠ 完了済み課題を編集する（通常はOFF）",
        key="override_done_lock_admin",
        value=st.session_state.get("override_done_lock", False),
    )
    st.session_state["override_done_lock"] = override_done_lock_admin
    override_done_lock = override_done_lock_admin

    st.header("管理（入力）")
    st.caption("CSVを直接編集せずに、ここから追記・更新します。")

    sub_stu, sub_weekly, sub_kentei, sub_curr, sub_sys, sub_override, sub_info = st.tabs(
        ["👥 生徒管理", "📅 固定スケジュール（週次）", "🎫 検定予定登録", "📘 カリキュラム管理", "🛠 システム設定", "🗓️ スケジュール例外", "ℹ️ 運用メモ"]
    )

    # ---------------------------
    # 👥 生徒管理（追加・編集・退会）
    # ---------------------------
    with sub_stu:
        students = safe_read_csv(STUDENTS_CSV, required_cols=["student_id", "display_name"])

        # 次のID（S001形式）を自動提案
        def suggest_next_student_id(existing_ids: pd.Series) -> str:
            nums = []
            for s in existing_ids.dropna().astype(str):
                if s.startswith("S") and s[1:].isdigit():
                    nums.append(int(s[1:]))
            n = (max(nums) + 1) if nums else 1
            return f"S{n:03d}"

        colA, colB = st.columns(2)
        with colA:
            st.subheader("新規追加")

            # 候補作成用データ（未作成でもOK）
            sched_base = safe_read_csv(STUDENT_SCHEDULE_CSV, required_cols=["student_id", "weekday", "slot"], stop_on_missing=False)  # noqa: F821
            slots_base = safe_read_csv(TIMESLOTS_CSV, required_cols=["slot"], stop_on_missing=False)  # noqa: F821

            grade_options = build_grade_options(students)
            weekday_options = build_weekday_options(students, sched_base)
            slot_options = build_slot_options(slots_base, sched_base, students)

            next_id = suggest_next_student_id(students["student_id"])
            new_id = st.text_input("生徒ID（例: S001）", value=next_id, key="stu_add_id")
            new_name = st.text_input("表示名", value="", key="stu_add_name")

            # 学年：リスト＋自由入力
            new_grade_sel = st.selectbox("学年", options=grade_options, index=0, key="stu_add_grade_sel")
            new_grade_free = ""
            if new_grade_sel == "その他（自由入力）":
                new_grade_free = st.text_input("学年（自由入力）", value="", key="stu_add_grade_free")
            new_grade = new_grade_free if new_grade_sel == "その他（自由入力）" else new_grade_sel

            new_times = st.number_input("月回数", min_value=0, value=0, step=1, key="stu_add_times")
            new_join = st.date_input("入会日", value=date.today(), key="stu_add_join")  # noqa: F821

            # 曜日：リスト（任意）
            new_weekday_sel = st.selectbox("曜日（任意）", options=weekday_options, index=0, key="stu_add_weekday_sel")
            new_weekday_free = ""
            if new_weekday_sel == "その他（自由入力）":
                new_weekday_free = st.text_input("曜日（自由入力）", value="", key="stu_add_weekday_free")
            new_weekday = new_weekday_free if new_weekday_sel == "その他（自由入力）" else new_weekday_sel

            # コマ：timeslots/scheduleから候補（任意）
            new_slot_sel = st.selectbox("コマ（任意）", options=slot_options, index=0, key="stu_add_slot_sel")
            new_slot_free = ""
            if new_slot_sel == "その他（自由入力）":
                new_slot_free = st.text_input("コマ（自由入力）", value="", key="stu_add_slot_free")
            new_slot = new_slot_free if new_slot_sel == "その他（自由入力）" else new_slot_sel

            new_memo = st.text_area("メモ（補足）", value="", height=80, key="stu_add_memo")

            if st.button("追加", key="stu_add_btn"):
                new_id_s = str(new_id).strip()
                if not new_id_s:
                    st.error("生徒IDが空です。")
                elif new_id_s in set(students["student_id"].astype(str)):
                    st.error(f"同じ生徒IDが既にあります: {new_id_s}")
                elif not str(new_name).strip():
                    st.error("表示名が空です。")
                else:
                    # 既存列に合わせて追加（なければ列を増やす）
                    if "grade" not in students.columns:
                        students["grade"] = ""
                    if "number_of_times" not in students.columns:
                        students["number_of_times"] = 0
                    if "join_date" not in students.columns:
                        students["join_date"] = ""
                    if "is_active" not in students.columns:
                        students["is_active"] = True
                    if "weekday" not in students.columns:
                        students["weekday"] = ""
                    if "slot" not in students.columns:
                        students["slot"] = ""
                    if "memo" not in students.columns:
                        students["memo"] = ""

                    row = {
                        "student_id": new_id_s,
                        "display_name": str(new_name).strip(),
                        "grade": str(new_grade).strip(),
                        "number_of_times": int(new_times),
                        "join_date": str(new_join),
                        "is_active": True,
                        "weekday": str(new_weekday).strip(),
                        "slot": str(new_slot).strip(),
                        "memo": str(new_memo).strip(),
                    }
                    students = pd.concat([students, pd.DataFrame([row])], ignore_index=True)
                    write_csv(students, STUDENTS_CSV)  # noqa: F821
                    st.success(f"追加しました: {new_id_s} / {row['display_name']}")

        with colB:
            st.subheader("編集 / 退会")
            # 表示名で選べるように
            students_view = students.copy()
            students_view["label"] = students_view["student_id"].astype(str) + " | " + students_view["display_name"].astype(str)
            sel_label = st.selectbox("生徒を選択", students_view["label"].tolist(), key="stu_edit_sel")
            sel_id = sel_label.split("|")[0].strip()
            cur = students_view.loc[students_view["student_id"].astype(str) == sel_id].iloc[0]

            # (v6.7.1) 選択した生徒に合わせて、下の編集フォームを同期する
            # Streamlitは key を持つウィジェットの値が session_state に残るため、
            # 生徒を切り替えても前の値が残りやすい。ここで切替検知→各入力キーを更新→rerun。
            last_id = st.session_state.get("stu_edit_last_id")
            if last_id != sel_id:
                # まず last_id を更新してから rerun（無限ループ防止）
                st.session_state["stu_edit_last_id"] = sel_id

                # 表示名
                st.session_state["stu_edit_name"] = str(cur.get("display_name", "") or "")

                # 学年（select/free）
                grade_options_tmp = build_grade_options(students)
                cur_grade_tmp = str(cur.get("grade", "") or "").strip()
                if cur_grade_tmp and cur_grade_tmp not in grade_options_tmp:
                    st.session_state["stu_edit_grade_sel"] = "その他（自由入力）"
                    st.session_state["stu_edit_grade_free"] = cur_grade_tmp
                else:
                    st.session_state["stu_edit_grade_sel"] = cur_grade_tmp if cur_grade_tmp else ""
                    st.session_state["stu_edit_grade_free"] = ""

                # 月回数
                try:
                    st.session_state["stu_edit_times"] = int(cur.get("number_of_times", 0) or 0)
                except Exception:
                    st.session_state["stu_edit_times"] = 0

                # 入会日
                try:
                    _dt = pd.to_datetime(cur.get("join_date", ""), errors="coerce")
                    st.session_state["stu_edit_join"] = (_dt.date() if pd.notna(_dt) else date.today())
                except Exception:
                    st.session_state["stu_edit_join"] = date.today()

                # 在籍
                st.session_state["stu_edit_active"] = bool(cur.get("is_active", True))

                # 曜日・コマ
                st.session_state["stu_edit_weekday"] = str(cur.get("weekday", "") or "")
                st.session_state["stu_edit_slot"] = str(cur.get("slot", "") or "")

                # 変更を反映した状態で描画し直す
                st.rerun()

            e_name = st.text_input("表示名", value=str(cur.get("display_name", "")), key="stu_edit_name")
            # 候補用データ
            sched_base = safe_read_csv(STUDENT_SCHEDULE_CSV, required_cols=["student_id", "weekday", "slot"], stop_on_missing=False)  # noqa: F821
            slots_base = safe_read_csv(TIMESLOTS_CSV, required_cols=["slot"], stop_on_missing=False)  # noqa: F821
            grade_options = build_grade_options(students)
            weekday_options = build_weekday_options(students, sched_base)
            slot_options = build_slot_options(slots_base, sched_base, students)

            # 学年：リスト＋自由入力
            cur_grade = str(cur.get("grade", "") or "").strip()
            if cur_grade and cur_grade not in grade_options:
                grade_options = grade_options[:-1] + [cur_grade] + [grade_options[-1]]
            try:
                default_grade_index = grade_options.index(cur_grade) if cur_grade in grade_options else 0
            except Exception:
                default_grade_index = 0
            e_grade_sel = st.selectbox("学年", options=grade_options, index=default_grade_index, key="stu_edit_grade_sel")
            e_grade_free = ""
            if e_grade_sel == "その他（自由入力）":
                e_grade_free = st.text_input("学年（自由入力）", value=cur_grade, key="stu_edit_grade_free")
            e_grade = e_grade_free if e_grade_sel == "その他（自由入力）" else e_grade_sel
            e_times = st.number_input("月回数", min_value=0, value=int(cur.get("number_of_times", 0) or 0), step=1, key="stu_edit_times")

            # join_date は CSV によっては空文字/NaN
            try:
                default_join = pd.to_datetime(cur.get("join_date", ""), errors="coerce")
                default_join = default_join.date() if pd.notna(default_join) else date.today()  # noqa: F821
            except Exception:
                default_join = date.today()  # noqa: F821

            e_join = st.date_input("入会日", value=default_join, key="stu_edit_join")
            e_active = st.checkbox("在籍中（ON=在籍 / OFF=退会）", value=bool(cur.get("is_active", True)), key="stu_edit_active")

            e_weekday = st.text_input("曜日（任意）", value=str(cur.get("weekday", "")), key="stu_edit_weekday")
            e_slot = st.text_input("コマ（任意）", value=str(cur.get("slot", "")), key="stu_edit_slot")

            if st.button("保存（更新）", key="stu_edit_save"):
                mask = students["student_id"].astype(str) == sel_id
                if "grade" not in students.columns:
                    students["grade"] = ""
                if "number_of_times" not in students.columns:
                    students["number_of_times"] = 0
                if "join_date" not in students.columns:
                    students["join_date"] = ""
                if "is_active" not in students.columns:
                    students["is_active"] = True
                if "weekday" not in students.columns:
                    students["weekday"] = ""
                if "slot" not in students.columns:
                    students["slot"] = ""
                    if "memo" not in students.columns:
                        students["memo"] = ""

                students.loc[mask, "display_name"] = str(e_name).strip()
                students.loc[mask, "grade"] = str(e_grade).strip()
                students.loc[mask, "number_of_times"] = int(e_times)
                students.loc[mask, "join_date"] = str(e_join)
                students.loc[mask, "is_active"] = bool(e_active)
                students.loc[mask, "weekday"] = str(e_weekday).strip()
                students.loc[mask, "slot"] = str(e_slot).strip()
                students.loc[mask, "memo"] = str(e_memo).strip()

                write_csv(students, STUDENTS_CSV)  # noqa: F821
                st.success(f"更新しました: {sel_id}")


        # (週次スケジュールUIは『📅 固定スケジュール（週次）』タブへ移動しました)

    # ---------------------------
    # 📅 固定スケジュール（週次）
    # ---------------------------
    with sub_weekly:
        st.subheader("固定スケジュール（週次）")
        st.caption("週1回/週2回（例：月8回）など、毎週ほぼ固定で来る子はここに登録します。月2回など月ごと調整の子は基本的に入れません。")

        students_w = safe_read_csv(STUDENTS_CSV, required_cols=["student_id", "display_name"], stop_on_missing=True)
        students_w["label"] = students_w["student_id"].astype(str) + " | " + students_w["display_name"].astype(str)

        # 対象生徒
        target_label = st.selectbox("対象生徒", students_w["label"].tolist(), key="weekly_target")
        target_id = target_label.split("|")[0].strip()
        target_name = target_label.split("|", 1)[1].strip() if "|" in target_label else ""
        st.write(f"対象生徒: {target_id} | {target_name}")

        # student_schedule.csv を読み込み（同じstudent_idで複数行OK）
        student_schedule = safe_read_csv(STUDENT_SCHEDULE_CSV, required_cols=["student_id", "weekday", "slot", "session_type"])
        student_schedule = sanitize_df(student_schedule)

        cur_rows = student_schedule[student_schedule["student_id"].astype(str).str.strip() == str(target_id).strip()].copy()

        # 一覧
        if cur_rows.empty:
            st.info("週次スケジュールは未登録です。下の『追加』から登録できます。")
        else:
            show = cur_rows[["weekday", "slot", "session_type"]].copy()
            show["slot"] = show["slot"].apply(lambda x: str(int(float(x))) if str(x).replace(".","",1).isdigit() else str(x))
            st.dataframe(show, use_container_width=True, hide_index=True)

            st.caption("削除したい行のボタンを押してください（即反映）")
            for i, r in cur_rows.reset_index(drop=True).iterrows():
                c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
                with c1:
                    st.write(ui_str(r.get("weekday", "")) or "-")
                with c2:
                    st.write(ui_str(r.get("slot", "")) or "-")
                with c3:
                    st.write(ui_str(r.get("session_type", "")) or "-")
                with c4:
                    if st.button("この行を削除", key=f"weekly_del_{target_id}_{i}"):
                        mask = (
                            student_schedule["student_id"].astype(str).str.strip().eq(str(target_id).strip())
                            & student_schedule["weekday"].astype(str).str.strip().eq(str(r.get("weekday","")).strip())
                            & student_schedule["slot"].astype(str).str.strip().eq(str(r.get("slot","")).strip())
                            & student_schedule["session_type"].astype(str).str.strip().eq(str(r.get("session_type","")).strip())
                        )
                        student_schedule2 = student_schedule.loc[~mask].copy()
                        write_csv(student_schedule2, STUDENT_SCHEDULE_CSV)
                        st.success("削除しました。")
                        st.rerun()

        st.markdown("#### 追加")
        colA, colB, colC, colD = st.columns([1, 1, 2, 1])
        with colA:
            wday = st.selectbox("曜日", WEEKDAY_PRESETS, index=0, key=f"weekly_add_wday_{target_id}")
        with colB:
            slot_in = st.text_input("コマ", value="", placeholder="例）1", key=f"weekly_add_slot_{target_id}")
        with colC:
            stype = st.selectbox("種別", ["授業", "自習", "検定", "その他"], index=0, key=f"weekly_add_type_{target_id}")
        with colD:
            add_btn = st.button("追加", key=f"weekly_add_btn_{target_id}")

        if add_btn:
            w = str(wday).strip()
            s = str(slot_in).strip()
            t = str(stype).strip()
            if w == "" or w == "その他（自由入力）":
                st.error("曜日を選択してください。")
            elif s == "":
                st.error("コマを入力してください。")
            else:
                dup = (
                    student_schedule["student_id"].astype(str).str.strip().eq(str(target_id).strip())
                    & student_schedule["weekday"].astype(str).str.strip().eq(w)
                    & student_schedule["slot"].astype(str).str.strip().eq(s)
                )
                if dup.any():
                    st.warning("同じ曜日・コマが既に登録されています。")
                else:
                    new_row = pd.DataFrame([{
                        "student_id": str(target_id).strip(),
                        "weekday": w,
                        "slot": s,
                        "session_type": t if t != "その他" else ""
                    }])
                    out = pd.concat([student_schedule, new_row], ignore_index=True)
                    write_csv(out, STUDENT_SCHEDULE_CSV)
                    st.success("追加しました。")
                    st.rerun()

# ---------------------------
    # 🎫 検定予定登録（kentei_schedule.csv）
    # ---------------------------
    with sub_kentei:
        st.subheader("検定予定 登録")
        students = safe_read_csv(STUDENTS_CSV, required_cols=["student_id", "display_name"], stop_on_missing=True)

        students["label"] = students["student_id"].astype(str) + " | " + students["display_name"].astype(str)

        ks = safe_read_csv(KENTEI_EXAM_SCHEDULE_CSV, required_cols=["date", "student_id", "kentei", "grade", "note"], stop_on_missing=False)  # noqa: F821
        if ks.empty:
            ks = pd.DataFrame(columns=["date", "student_id", "kentei", "grade", "note"])

        k_date = st.date_input("日付", value=date.today(), key="kentei_date")  # noqa: F821
        k_student = st.selectbox("生徒", students["label"].tolist(), key="kentei_student")
        k_student_id = k_student.split("|")[0].strip()
        k_name = st.text_input("検定名（例: プログラミング検定）", value="プログラミング検定", key="kentei_name")
        k_grade = st.text_input("級（例: 4 / 3 / 2）", value="", key="kentei_grade_input")
        k_note = st.text_input("メモ（任意）", value="", key="kentei_note")

        #if st.button("保存（kentei_schedule.csv に追記）", key="kentei_save"):
        #    new_row = {
        #        "date": str(k_date),
        #        "student_id": k_student_id,
        #        "kentei": str(k_name).strip(),
        #        "grade": str(k_grade).strip(),
        #        "note": str(k_note).strip(),
        #    }
        #    ks = pd.concat([ks, pd.DataFrame([new_row])], ignore_index=True)
        #    write_csv(ks, KENTEI_EXAM_SCHEDULE_CSV)  # noqa: F821
        #    st.success("保存しました。")


        if st.button("保存（kentei_exam_schedule.csv に追記）", key="kentei_save_btn"):
            new_row = {
                "student_id": k_student_id,
                "exam_type": str(k_name).strip(),      # 例：プログラミング検定
                "grade": str(k_grade).strip(),         # 例：2
                "exam_date": str(k_date),              # 受験日（画面の日付）
                "note": str(k_note).strip(),           # メモ
                "date": str(date.today()),            # 登録日（空でもいいけど入れた方が整う）
                "kentei": str(k_name).strip(),         # 互換用（空でもいいが、入れると後で楽）
            }

            ks = pd.concat([ks, pd.DataFrame([new_row])], ignore_index=True)

            # 列順を固定（崩れ防止）
            cols = ["student_id","exam_type","grade","exam_date","note","date","kentei"]
            ks = ks.reindex(columns=cols)

            write_csv(ks, KENTEI_EXAM_SCHEDULE_CSV)
            st.success("保存しました。")


            st.divider()
            st.caption("登録済み（直近）")
            if not ks.empty:
                ks_view = ks.copy()
                ks_view["date"] = pd.to_datetime(ks_view["date"], errors="coerce")
                ks_view = ks_view.sort_values("date").tail(20)
                st.dataframe(ks_view, use_container_width=True)


        # ---------------------------
        # 📘 カリキュラム管理（追加・編集・削除）
        #   - curriculum_courses.csv
        #   - curriculum_tasks.csv
        # ---------------------------
    with sub_curr:
        st.subheader("📘 カリキュラム / 課題 管理")
        st.caption("カリキュラム（コース）と課題（タスク）を、CSVを直接触らずにUIから編集できます。保存時に自動バックアップも作ります。")

        def backup_file(path: Path):
            if not path.exists():
                return
            ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = path.with_suffix(path.suffix + f".bak_{ts}")
            try:
                bak.write_bytes(path.read_bytes())
            except Exception as e:
                st.warning(f"バックアップ作成に失敗しました: {path.name} / {e}")

        def normalize_bool_str(v):
            s = str(v).strip().lower()
            return s in ("1","true","t","yes","y","on")

        # ---------- Courses ----------
        st.markdown("### 1) コース（curriculum_courses.csv）")

        courses = safe_read_csv(
            CURRICULUM_COURSES_CSV,
            ["course_id", "genre_id", "genre_name", "course_name", "course_order", "is_active"],
            stop_on_missing=False,
            show_message=True,
        )
        if courses.empty:
            courses = pd.DataFrame(columns=["course_id","genre_id","genre_name","course_name","course_order","is_active"])

        # 表示用
        courses_view = courses.copy()
        if "course_order" in courses_view.columns:
            courses_view["course_order_num"] = pd.to_numeric(courses_view["course_order"], errors="coerce").fillna(9999).astype(int)
            courses_view = courses_view.sort_values(["course_order_num","course_id"], na_position="last").drop(columns=["course_order_num"])
        st.dataframe(courses_view, use_container_width=True, hide_index=True)

        colC1, colC2 = st.columns(2)

        with colC1:
            st.markdown("#### ➕ コース追加")
            add_course_id = st.text_input("course_id（例: PY-GAME-001）", key="c_add_course_id")
            add_genre_id = st.text_input("genre_id（例: PY / SCR など）", key="c_add_genre_id")
            add_genre_name = st.text_input("genre_name（例: Python / Scratch）", key="c_add_genre_name")
            add_course_name = st.text_input("course_name", key="c_add_course_name")
            add_course_order = st.number_input("course_order（表示順）", min_value=0, value=0, step=1, key="c_add_course_order")
            add_is_active = st.checkbox("is_active（ON=表示）", value=True, key="c_add_is_active")

            if st.button("コースを追加して保存", key="c_add_save"):
                cid = str(add_course_id).strip()
                if not cid:
                    st.error("course_id が空です。")
                elif cid in set(courses["course_id"].astype(str).str.strip()):
                    st.error("同じ course_id が既に存在します。")
                elif not str(add_course_name).strip():
                    st.error("course_name が空です。")
                else:
                    new_row = {
                        "course_id": cid,
                        "genre_id": str(add_genre_id).strip(),
                        "genre_name": str(add_genre_name).strip(),
                        "course_name": str(add_course_name).strip(),
                        "course_order": int(add_course_order),
                        "is_active": bool(add_is_active),
                    }
                    courses2 = pd.concat([courses, pd.DataFrame([new_row])], ignore_index=True)
                    backup_file(CURRICULUM_COURSES_CSV)
                    write_csv(courses2, CURRICULUM_COURSES_CSV)
                    st.success(f"追加しました: {cid}")
                    st.rerun()

        with colC2:
            st.markdown("#### ✏️ 編集 / 🗑️ 削除")
            if courses.empty:
                st.info("コースがありません。先に追加してください。")
            else:
                courses_sel = courses.copy()
                courses_sel["label"] = courses_sel["course_id"].astype(str) + " | " + courses_sel["course_name"].astype(str)
                sel = st.selectbox("編集するコース", courses_sel["label"].tolist(), key="c_edit_sel")
                sel_id = sel.split("|")[0].strip()
                cur = courses_sel.loc[courses_sel["course_id"].astype(str).str.strip() == sel_id].iloc[0]

                e_genre_id = st.text_input("genre_id", value=str(cur.get("genre_id","")), key="c_edit_genre_id")
                e_genre_name = st.text_input("genre_name", value=str(cur.get("genre_name","")), key="c_edit_genre_name")
                e_course_name = st.text_input("course_name", value=str(cur.get("course_name","")), key="c_edit_course_name")
                try:
                    default_order = int(float(cur.get("course_order", 0) or 0))
                except Exception:
                    default_order = 0
                e_course_order = st.number_input("course_order（表示順）", min_value=0, value=default_order, step=1, key="c_edit_course_order")
                e_is_active = st.checkbox("is_active（ON=表示）", value=normalize_bool_str(cur.get("is_active", True)), key="c_edit_is_active")

                colE1, colE2 = st.columns(2)
                with colE1:
                    if st.button("保存（更新）", key="c_edit_save"):
                        mask = courses["course_id"].astype(str).str.strip() == sel_id
                        courses2 = courses.copy()
                        courses2.loc[mask, "genre_id"] = str(e_genre_id).strip()
                        courses2.loc[mask, "genre_name"] = str(e_genre_name).strip()
                        courses2.loc[mask, "course_name"] = str(e_course_name).strip()
                        courses2.loc[mask, "course_order"] = int(e_course_order)
                        courses2.loc[mask, "is_active"] = bool(e_is_active)

                        backup_file(CURRICULUM_COURSES_CSV)
                        write_csv(courses2, CURRICULUM_COURSES_CSV)
                        st.success("保存しました。")
                        st.rerun()

                with colE2:
                    delete_also_tasks = st.checkbox("コース削除時に、このコースの課題も削除する", value=True, key="c_del_also_tasks")
                    confirm_del = st.checkbox("削除を有効にする（確認）", value=False, key="c_del_confirm")
                    if st.button("🗑️ このコースを削除", key="c_del_btn", disabled=not confirm_del):
                        courses2 = courses[courses["course_id"].astype(str).str.strip() != sel_id].copy()
                        backup_file(CURRICULUM_COURSES_CSV)
                        write_csv(courses2, CURRICULUM_COURSES_CSV)
                        show_saved()

                        if delete_also_tasks:
                            tasks_now = safe_read_csv(
                                CURRICULUM_TASKS_CSV,
                                ["course_id","task_id","task_name","order","is_active","student_id"],
                                stop_on_missing=False,
                                show_message=False,
                            )
                            if not tasks_now.empty:
                                tasks2 = tasks_now[tasks_now["course_id"].astype(str).str.strip() != sel_id].copy()
                                if len(tasks2) != len(tasks_now):
                                    backup_file(CURRICULUM_TASKS_CSV)
                                    write_csv(tasks2, CURRICULUM_TASKS_CSV)

                        st.success(f"削除しました: {sel_id}")
                        st.rerun()

        st.divider()

        # ---------- Tasks ----------
        st.markdown("### 2) 課題（curriculum_tasks.csv）")
        tasks = safe_read_csv(
            CURRICULUM_TASKS_CSV,
            ["course_id", "task_id", "task_name", "order", "is_active", "student_id"],
            stop_on_missing=False,
            show_message=True,
        )
        if tasks.empty:
            tasks = pd.DataFrame(columns=["course_id","task_id","task_name","order","is_active","student_id"])

        # course choices
        course_ids = []
        if not courses.empty:
            course_ids = sorted(courses["course_id"].astype(str).str.strip().unique().tolist())
        task_course = st.selectbox("表示するコース（課題）", ["（全て）"] + course_ids, key="t_course_filter")

        tasks_view = tasks.copy()
        if task_course != "（全て）":
            tasks_view = tasks_view[tasks_view["course_id"].astype(str).str.strip() == task_course].copy()

        # order sort
        if "order" in tasks_view.columns:
            tasks_view["order_num"] = pd.to_numeric(tasks_view["order"], errors="coerce").fillna(9999).astype(int)
            tasks_view = tasks_view.sort_values(["course_id","order_num","task_id"], na_position="last").drop(columns=["order_num"])

        st.dataframe(tasks_view, use_container_width=True, hide_index=True)

        colT1, colT2 = st.columns(2)

        def suggest_next_task_id(course_id: str) -> str:
            c = str(course_id).strip()
            if not c:
                return ""
            existing = tasks[tasks["course_id"].astype(str).str.strip() == c]
            nmax = 0
            for tid in existing.get("task_id", pd.Series(dtype=str)).astype(str):
                m = re.search(r"(\d+)$", tid.strip())
                if m:
                    nmax = max(nmax, int(m.group(1)))
            return f"{c}-T{nmax+1:03d}"

        with colT1:
            st.markdown("#### ➕ 課題追加")
            t_course_id = st.selectbox("course_id", course_ids if course_ids else ["（先にコースを追加）"], key="t_add_course_id")
            t_task_id = st.text_input("task_id（空なら自動提案）", value="", key="t_add_task_id")
            if course_ids and t_course_id and not t_task_id.strip():
                st.caption(f"提案 task_id: {suggest_next_task_id(t_course_id)}")

            t_task_name = st.text_input("task_name", key="t_add_task_name")
            t_order = st.number_input("order（並び順）", min_value=0, value=0, step=1, key="t_add_order")
            t_is_active = st.checkbox("is_active（ON=表示）", value=True, key="t_add_is_active")
            t_student_id = st.text_input("student_id（空=共通 / 入れる=個別課題）", value="", key="t_add_student_id")

            if st.button("課題を追加して保存", key="t_add_save"):
                cid = str(t_course_id).strip()
                if not cid or cid.startswith("（"):
                    st.error("course_id を選んでください。")
                else:
                    tid = str(t_task_id).strip() or suggest_next_task_id(cid)
                    if not tid:
                        st.error("task_id が作れませんでした。")
                    elif tid in set(tasks["task_id"].astype(str).str.strip()):
                        st.error("同じ task_id が既に存在します。")
                    elif not str(t_task_name).strip():
                        st.error("task_name が空です。")
                    else:
                        new_row = {
                            "course_id": cid,
                            "task_id": tid,
                            "task_name": str(t_task_name).strip(),
                            "order": int(t_order),
                            "is_active": bool(t_is_active),
                            "student_id": str(t_student_id).strip(),
                        }
                        tasks2 = pd.concat([tasks, pd.DataFrame([new_row])], ignore_index=True)
                        backup_file(CURRICULUM_TASKS_CSV)
                        write_csv(tasks2, CURRICULUM_TASKS_CSV)
                        st.success(f"追加しました: {tid}")
                        st.rerun()

        with colT2:
            st.markdown("#### ✏️ 編集 / 🗑️ 削除")
            if tasks.empty:
                st.info("課題がありません。")
            else:
                pick_df = tasks_view if task_course != "（全て）" else tasks
                if pick_df.empty:
                    st.info("このコースには課題がありません。")
                else:
                    pick_df2 = pick_df.copy()
                    pick_df2["label"] = pick_df2["task_id"].astype(str) + " | " + pick_df2["task_name"].astype(str)
                    sel_t = st.selectbox("編集する課題", pick_df2["label"].tolist(), key="t_edit_sel")
                    sel_tid = sel_t.split("|")[0].strip()
                    cur_t = pick_df2.loc[pick_df2["task_id"].astype(str).str.strip() == sel_tid].iloc[0]

                    cur_course = str(cur_t.get("course_id","")).strip()
                    course_index = course_ids.index(cur_course) if course_ids and cur_course in course_ids else 0
                    e_course_id = st.selectbox("course_id（変更可）", course_ids if course_ids else [cur_course], index=course_index, key="t_edit_course_id")
                    e_task_name = st.text_input("task_name", value=str(cur_t.get("task_name","")), key="t_edit_task_name")
                    try:
                        default_t_order = int(float(cur_t.get("order", 0) or 0))
                    except Exception:
                        default_t_order = 0
                    e_order = st.number_input("order（並び順）", min_value=0, value=default_t_order, step=1, key="t_edit_order")
                    e_is_active = st.checkbox("is_active（ON=表示）", value=normalize_bool_str(cur_t.get("is_active", True)), key="t_edit_is_active")
                    e_student_id = st.text_input("student_id（空=共通 / 入れる=個別課題）", value=str(cur_t.get("student_id","")), key="t_edit_student_id")

                    colTE1, colTE2 = st.columns(2)
                    with colTE1:
                        if st.button("保存（更新）", key="t_edit_save"):
                            mask = tasks["task_id"].astype(str).str.strip() == sel_tid
                            tasks2 = tasks.copy()
                            tasks2.loc[mask, "course_id"] = str(e_course_id).strip()
                            tasks2.loc[mask, "task_name"] = str(e_task_name).strip()
                            tasks2.loc[mask, "order"] = int(e_order)
                            tasks2.loc[mask, "is_active"] = bool(e_is_active)
                            tasks2.loc[mask, "student_id"] = str(e_student_id).strip()

                            backup_file(CURRICULUM_TASKS_CSV)
                            write_csv(tasks2, CURRICULUM_TASKS_CSV)
                            st.success("保存しました。")
                            st.rerun()
                    with colTE2:
                        confirm_del_t = st.checkbox("削除を有効にする（確認）", value=False, key="t_del_confirm")
                        if st.button("🗑️ この課題を削除", key="t_del_btn", disabled=not confirm_del_t):
                            tasks2 = tasks[tasks["task_id"].astype(str).str.strip() != sel_tid].copy()
                            backup_file(CURRICULUM_TASKS_CSV)
                            write_csv(tasks2, CURRICULUM_TASKS_CSV)
                            st.success(f"削除しました: {sel_tid}")
                            st.rerun()

    # ---------------------------
    # 🗓️ スケジュール例外（schedule_overrides.csv）
    # ---------------------------

    # ---------------------------
    # 🛠 システム設定（CSV手書きをゼロに近づける）
    #   - student_schedule.csv（通常の時間割）
    #   - timeslots.csv（コマ時間）
    # ---------------------------
    with sub_sys:
        st.subheader("🛠 システム設定")
        st.caption("CSVを探して手書きしなくても済むように、基本スケジュールとコマ時間をここで管理できます。保存時は自動バックアップを作成します。")

        def _backup(path: Path):
            if not path.exists():
                return
            ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = path.with_suffix(path.suffix + f".bak_{ts}")
            try:
                bak.write_bytes(path.read_bytes())
            except Exception as e:
                st.warning(f"バックアップ作成に失敗しました: {path.name} / {e}")

        tab_sched, tab_slots = st.tabs(["🗓️ 基本スケジュール（student_schedule）", "⏱ コマ時間（timeslots）"])

        # ===== student_schedule.csv =====
        with tab_sched:
            st.markdown("### 🗓️ 基本スケジュール（student_schedule.csv）")
            st.caption("曜日×コマの通常予定（毎週のベース）を登録します。欠席/振替など当日の変更は『スケジュール例外』で入力します。")

            sched = safe_read_csv(
                STUDENT_SCHEDULE_CSV,
                ["student_id", "weekday", "slot", "session_type"],
                stop_on_missing=False,
                show_message=False,
            )
            if sched.empty:
                sched = pd.DataFrame(columns=["student_id", "weekday", "slot", "session_type", "note"])

            # 列を揃える（将来拡張も壊れない）
            for c in ["note"]:
                if c not in sched.columns:
                    sched[c] = ""

            st.dataframe(
                sched.sort_values(["weekday", "slot", "student_id"], na_position="last"),
                use_container_width=True,
                hide_index=True,
            )

            st.divider()

            students2 = safe_read_csv(STUDENTS_CSV, ["student_id", "display_name"], show_message=False)
            if students2.empty:
                st.warning("students.csv が空です。先に『生徒管理』で生徒を登録してください。")
                st.stop()

            students2["label"] = students2["student_id"].astype(str) + " | " + students2["display_name"].astype(str)
            weekday_opts = ["月", "火", "水", "木", "金", "土", "日"]
            sess_type_opts = ["lesson", "kentei", "self"]

            colS1, colS2 = st.columns(2)

            with colS1:
                st.markdown("#### ➕ 追加")
                add_student = st.selectbox("生徒", students2["label"].tolist(), key="ss_add_student")
                add_student_id = add_student.split("|")[0].strip()
                add_weekday = st.selectbox("曜日", weekday_opts, key="ss_add_weekday")
                add_slot = st.number_input("コマ（数字）", min_value=1, value=1, step=1, key="ss_add_slot")
                add_sess = st.selectbox("種類（session_type）", sess_type_opts, key="ss_add_sess")
                add_note = st.text_input("メモ（任意）", value="", key="ss_add_note")

                if st.button("追加", key="ss_add_btn"):
                    # 重複（同一 生徒×曜日×コマ）を防ぐ
                    dup = (
                        (sched["student_id"].astype(str).str.strip() == add_student_id)
                        & (sched["weekday"].astype(str).str.strip() == str(add_weekday).strip())
                        & (pd.to_numeric(sched["slot"], errors="coerce").fillna(-1).astype(int) == int(add_slot))
                    )
                    if dup.any():
                        st.error("同じ（生徒×曜日×コマ）の行が既にあります。編集を使ってください。")
                    else:
                        new_row = {
                            "student_id": add_student_id,
                            "weekday": str(add_weekday).strip(),
                            "slot": int(add_slot),
                            "session_type": str(add_sess).strip(),
                            "note": str(add_note).strip(),
                        }
                        _backup(STUDENT_SCHEDULE_CSV)
                        sched2 = pd.concat([sched, pd.DataFrame([new_row])], ignore_index=True)
                        write_csv_atomic(sched2, STUDENT_SCHEDULE_CSV)
                        st.success("追加しました。")
                        st.rerun()

            with colS2:
                st.markdown("#### ✏️ 編集 / 🗑 削除")
                if sched.empty:
                    st.info("まだ行がありません。左で追加してください。")
                else:
                    sched2 = sched.copy()
                    # label 作成
                    sched2["slot_num"] = pd.to_numeric(sched2["slot"], errors="coerce").fillna(-1).astype(int)
                    sched2["label"] = (
                        sched2["student_id"].astype(str).str.strip()
                        + " | " + sched2["weekday"].astype(str).str.strip()
                        + " | " + sched2["slot_num"].astype(str)
                        + " | " + sched2["session_type"].astype(str).str.strip()
                    )
                    sel = st.selectbox("行を選択", sched2["label"].tolist(), key="ss_edit_sel")
                    sel_idx = int(sched2.index[sched2["label"] == sel][0])
                    row = sched.loc[sel_idx]

                    e_weekday = st.selectbox("曜日", weekday_opts, index=weekday_opts.index(str(row.get("weekday","月")).strip()) if str(row.get("weekday","月")).strip() in weekday_opts else 0, key="ss_edit_weekday")
                    e_slot = st.number_input("コマ", min_value=1, value=int(pd.to_numeric(row.get("slot",1), errors="coerce") or 1), step=1, key="ss_edit_slot")
                    e_sess = st.selectbox("種類（session_type）", sess_type_opts, index=sess_type_opts.index(str(row.get("session_type","lesson")).strip()) if str(row.get("session_type","lesson")).strip() in sess_type_opts else 0, key="ss_edit_sess")
                    e_note = st.text_input("メモ", value=str(row.get("note","")), key="ss_edit_note")

                    c3, c4 = st.columns(2)
                    with c3:
                        if st.button("保存（更新）", key="ss_edit_save"):
                            # 重複チェック（自分以外）
                            dup = (
                                (sched.index != sel_idx)
                                & (sched["student_id"].astype(str).str.strip() == str(row.get("student_id","")).strip())
                                & (sched["weekday"].astype(str).str.strip() == str(e_weekday).strip())
                                & (pd.to_numeric(sched["slot"], errors="coerce").fillna(-1).astype(int) == int(e_slot))
                            )
                            if dup.any():
                                st.error("更新後に（生徒×曜日×コマ）が他の行と重複します。")
                            else:
                                _backup(STUDENT_SCHEDULE_CSV)
                                sched.loc[sel_idx, "weekday"] = str(e_weekday).strip()
                                sched.loc[sel_idx, "slot"] = int(e_slot)
                                sched.loc[sel_idx, "session_type"] = str(e_sess).strip()
                                sched.loc[sel_idx, "note"] = str(e_note).strip()
                                write_csv_atomic(sched, STUDENT_SCHEDULE_CSV)
                                st.success("保存しました。")
                                st.rerun()

                    with c4:
                        if st.button("削除", key="ss_edit_del"):
                            _backup(STUDENT_SCHEDULE_CSV)
                            sched3 = sched.drop(index=sel_idx).reset_index(drop=True)
                            write_csv_atomic(sched3, STUDENT_SCHEDULE_CSV)
                            st.success("削除しました。")
                            st.rerun()

        # ===== timeslots.csv =====
        with tab_slots:
            st.markdown("### ⏱ コマ時間（timeslots.csv）")
            st.caption("曜日×コマの開始/終了時刻を設定します。時間割の見える化や印刷に使えます（任意機能）。")

            slots = safe_read_csv(
                TIMESLOTS_CSV,
                ["weekday", "slot", "start", "end"],
                stop_on_missing=False,
                show_message=False,
            )
            if slots.empty:
                slots = pd.DataFrame(columns=["weekday", "slot", "start", "end"])

            slots2 = slots.copy()
            slots2["slot_num"] = pd.to_numeric(slots2["slot"], errors="coerce").fillna(-1).astype(int)
            slots2 = slots2.sort_values(["weekday", "slot_num"], na_position="last").drop(columns=["slot_num"])
            st.dataframe(slots2, use_container_width=True, hide_index=True)

            st.divider()

            weekday_opts = ["月", "火", "水", "木", "金", "土", "日"]

            colT1, colT2 = st.columns(2)
            with colT1:
                st.markdown("#### ➕ 追加")
                t_wd = st.selectbox("曜日", weekday_opts, key="ts_add_wd")
                t_slot = st.number_input("コマ（数字）", min_value=1, value=1, step=1, key="ts_add_slot")
                t_start = st.text_input("開始（例 16:00）", value="", key="ts_add_start")
                t_end = st.text_input("終了（例 16:50）", value="", key="ts_add_end")

                if st.button("追加", key="ts_add_btn"):
                    dup = (
                        (slots["weekday"].astype(str).str.strip() == str(t_wd).strip())
                        & (pd.to_numeric(slots["slot"], errors="coerce").fillna(-1).astype(int) == int(t_slot))
                    )
                    if dup.any():
                        st.error("同じ（曜日×コマ）が既にあります。編集を使ってください。")
                    else:
                        new_row = {"weekday": str(t_wd).strip(), "slot": int(t_slot), "start": str(t_start).strip(), "end": str(t_end).strip()}
                        _backup(TIMESLOTS_CSV)
                        slots_new = pd.concat([slots, pd.DataFrame([new_row])], ignore_index=True)
                        write_csv_atomic(slots_new, TIMESLOTS_CSV)
                        st.success("追加しました。")
                        st.rerun()

            with colT2:
                st.markdown("#### ✏️ 編集 / 🗑 削除")
                if slots.empty:
                    st.info("まだ行がありません。左で追加してください。")
                else:
                    slots3 = slots.copy()
                    slots3["slot_num"] = pd.to_numeric(slots3["slot"], errors="coerce").fillna(-1).astype(int)
                    slots3["label"] = (
                        slots3["weekday"].astype(str).str.strip()
                        + " | " + slots3["slot_num"].astype(str)
                        + " | " + slots3["start"].astype(str).str.strip()
                        + "-" + slots3["end"].astype(str).str.strip()
                    )
                    sel = st.selectbox("行を選択", slots3["label"].tolist(), key="ts_edit_sel")
                    sel_idx = int(slots3.index[slots3["label"] == sel][0])
                    row = slots.loc[sel_idx]

                    e_wd = st.selectbox("曜日", weekday_opts, index=weekday_opts.index(str(row.get("weekday","月")).strip()) if str(row.get("weekday","月")).strip() in weekday_opts else 0, key="ts_edit_wd")
                    e_slot = st.number_input("コマ", min_value=1, value=int(pd.to_numeric(row.get("slot",1), errors="coerce") or 1), step=1, key="ts_edit_slot")
                    e_start = st.text_input("開始", value=str(row.get("start","")), key="ts_edit_start")
                    e_end = st.text_input("終了", value=str(row.get("end","")), key="ts_edit_end")

                    c5, c6 = st.columns(2)
                    with c5:
                        if st.button("保存（更新）", key="ts_edit_save"):
                            dup = (
                                (slots.index != sel_idx)
                                & (slots["weekday"].astype(str).str.strip() == str(e_wd).strip())
                                & (pd.to_numeric(slots["slot"], errors="coerce").fillna(-1).astype(int) == int(e_slot))
                            )
                            if dup.any():
                                st.error("更新後に（曜日×コマ）が他の行と重複します。")
                            else:
                                _backup(TIMESLOTS_CSV)
                                slots.loc[sel_idx, "weekday"] = str(e_wd).strip()
                                slots.loc[sel_idx, "slot"] = int(e_slot)
                                slots.loc[sel_idx, "start"] = str(e_start).strip()
                                slots.loc[sel_idx, "end"] = str(e_end).strip()
                                write_csv_atomic(slots, TIMESLOTS_CSV)
                                st.success("保存しました。")
                                st.rerun()

                    with c6:
                        if st.button("削除", key="ts_edit_del"):
                            _backup(TIMESLOTS_CSV)
                            slots_new = slots.drop(index=sel_idx).reset_index(drop=True)
                            write_csv_atomic(slots_new, TIMESLOTS_CSV)
                            st.success("削除しました。")
                            st.rerun()

    
    with sub_override:
            st.subheader("スケジュール例外（一覧）")
            st.caption("※ 例外の追加・変更は、閲覧画面の『今日の例外入力』から行う運用を推奨します。ここは一覧確認用です。")
    
            ov = safe_read_csv(
                SCHEDULE_OVERRIDES_CSV,
                required_cols=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"],
                stop_on_missing=False,
            )
            if ov.empty:
                ov = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"])
                st.info("スケジュール例外はまだありません。")
            else:
                # 見やすい順に並べる
                try:
                    ov["date"] = pd.to_datetime(ov["date"]).dt.date
                except Exception:
                    pass
                ov_show = ov.copy()
                # student名を付与（表示用）
                students_x = safe_read_csv(STUDENTS_CSV, required_cols=["student_id", "display_name"], stop_on_missing=False)
                if not students_x.empty:
                    name_map = dict(zip(students_x["student_id"].astype(str), students_x["display_name"].astype(str)))
                    ov_show["name"] = ov_show["student_id"].astype(str).map(name_map).fillna("")
                    ov_show = ov_show[["date", "student_id", "name", "slot", "action", "start", "end", "session_type", "note"]]
                ov_show = ov_show.sort_values(["date", "slot", "student_id"], kind="mergesort")
                st.dataframe(ov_show, use_container_width=True, hide_index=True)
with st.expander("ℹ️ 補足", expanded=False):
        st.markdown(
            """
    - **生徒追加**は「👥 生徒管理」から行えます（S001形式の次IDを自動提案）。
    - **検定予定**は `data/kentei_schedule.csv` に追記します。
    - **スケジュール例外**は `data/schedule_overrides.csv` に追記します。
    - Streamlitの「DuplicateElement」エラーが出たら、同じ画面内に同じウィジェットが複数作られている可能性があります。
      この画面では全て `key=` を付けて再発しにくくしています。
            """
        )