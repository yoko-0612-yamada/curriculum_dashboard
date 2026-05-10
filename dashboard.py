from __future__ import annotations

from pathlib import Path
import datetime as dt
from datetime import date
import os

import pandas as pd
from datetime import datetime

import re
import streamlit as st

# --- slot ユーティリティ（統一用） ------------------------------
# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def normalize_slot(v):
    """1, '1', 1.0, '6 | 17:10〜18:10' → '1'/'6' に統一（文字列）"""
    if v is None:
        return ""


    s = str(v).strip()
    if s == "" or s.lower() in ["nan", "none"]:
        return ""


    # 先頭の数字だけ取り出す：例 '6 | 17:10〜18:10' → '6'
    m = re.match(r"^\s*(\d+)", s)
    if m:
        return str(int(m.group(1)))


    try:
        return str(int(float(s)))
    except Exception:
        return s


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def build_slot_label_map(timeslots_df):
    """
    timeslots から
    {1: '1｜16:00〜17:00', ...} を作る
    """
    m = {}
    if timeslots_df is None or "slot" not in timeslots_df.columns:
        return m

    for _, r in timeslots_df.iterrows():
        try:
            s = int(float(r.get("slot")))
        except Exception:
            continue

        start = str(r.get("start", "") or "").strip()
        end = str(r.get("end", "") or "").strip()

        if start or end:
            m[s] = f"{s}｜{start}〜{end}".strip("〜")
        else:
            m[s] = str(s)
    return m




# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def format_slot_label(x, slot_label_map):
    """selectbox の format_func 用"""
    try:
        k = int(float(x))
        return slot_label_map.get(k, str(k))
    except Exception:
        return str(x)


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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


def status_label(status: str) -> str:
    s = ui_str(status)
    if s == "完了":
        return "🟢 完了"
    if s == "未実施":
        return "🔴 未実施"
    if s == "スキップ":
        return "⚪ スキップ"
    return s


def status_badge_html(status: str) -> str:
    s = ui_str(status)
    if s == "完了":
        bg = "#d4edda"
        fg = "#155724"
        label = "🟢 完了"
    elif s == "未実施":
        bg = "#f8d7da"
        fg = "#721c24"
        label = "🔴 未実施"
    elif s == "スキップ":
        bg = "#e2e3e5"
        fg = "#383d41"
        label = "⚪ スキップ"
    else:
        bg = "#f8f9fa"
        fg = "#333333"
        label = s


    return f"""
    <div style="
        display:inline-block;
        padding:4px 10px;
        border-radius:8px;
        background:{bg};
        color:{fg};
        font-weight:700;
        font-size:0.95rem;
        margin:4px 0 10px 0;
    ">{label}</div>
    """

def unfinished_status_badge_html(status: str) -> str:
    s = ui_str(status)


    if "出欠未" in s and "進捗未" in s:
        bg = "#f8d7da"
        fg = "#721c24"
    elif "出欠未" in s:
        bg = "#fff3cd"
        fg = "#856404"
    elif "進捗未" in s:
        bg = "#ffe5d0"
        fg = "#8a3b12"
    else:
        bg = "#f8f9fa"
        fg = "#333333"


    return f"""
    <div style="
        display:inline-block;
        padding:4px 10px;
        border-radius:8px;
        background:{bg};
        color:{fg};
        font-weight:700;
        font-size:0.95rem;
        margin-top:4px;
    ">{s}</div>
    """

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def judge_next_step(score):
    try:
        s = int(score)
    except:
        return "不明"


    if s >= 80:
        return "🚀 次いける"
    elif s >= 70:
        return "👍 ほぼOK"
    else:
        return "⚠ 少しフォロー"



# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def get_next_grade(grade):
    g_str = str(grade).strip()
    if not g_str or g_str.lower() == "nan":
        return "不明"

    m = re.search(r"([1-4])\s*級", g_str)
    if not m:
        m = re.search(r"\b([1-4])\b", g_str)

    if not m:
        return "不明"

    g = int(m.group(1))

    if g <= 1:
        return "終了"
    return f"{g-1}級"


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def build_kentei_hint(judge, grade):
    judge_str = str(judge).strip()
    grade_str = str(grade).strip()

    if not judge_str or judge_str.lower() == "nan":
        return ""
    if not grade_str or grade_str.lower() == "nan" or grade_str == "不明":
        return judge_str
    return f"{judge_str} / {grade_str}"


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def colorize_kentei_hint(text):
    s = str(text).strip()
    if not s or s.lower() == "nan":
        return ""

    if "次いける" in s:
        return f"🟢 {s}"
    elif "ほぼOK" in s:
        return f"🟡 {s}"
    elif "少しフォロー" in s:
        return f"🔴 {s}"
    return s


# [CHECK 2026-04-23] このファイル内では定義のみを確認。参照未検出のため、削除候補として要確認。
def build_today_status(att_done, prog_done):
    if att_done and prog_done:
        return "🟢 完了"
    elif att_done and not prog_done:
        return "🟡 進捗待ち"
    elif not att_done:
        return "🔴 出欠未"
    return ""


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
PAGE_OPTIONS = ["閲覧", "座席", "管理（入力）"]

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
# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def _get_password() -> str | None:
    try:
        pw = st.secrets.get("DASHBOARD_PASSWORD")  # type: ignore[attr-defined]
        if pw:
            return str(pw)
    except Exception:
        pass
    pw2 = os.environ.get("DASHBOARD_PASSWORD")
    return str(pw2) if pw2 else None


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def save_kentei_results(df: pd.DataFrame) -> None:
    write_csv_atomic(df, KENTEI_RESULTS_CSV)

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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
PROGRESS_SKIP_OK_CSV = DATA_DIR / "progress_skip_ok.csv"
PREP_MEMO_CSV = DATA_DIR / "prep_memo.csv"

# [KEEP 2026-04-24] 座席表（今日の配置）の保存先。STEP1/2では読み込み・表示のみ。
SEAT_ASSIGNMENTS_CSV = DATA_DIR / "seat_assignments.csv"

DEFAULT_SEATS_CSV = DATA_DIR / "default_seats.csv"

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def save_attendance_log(df: pd.DataFrame) -> None:
    # keep columns
    for c in ["date", "student_id", "kind", "memo"]:
        if c not in df.columns:
            df[c] = ""
    df = df[["date", "student_id", "kind", "memo"]].copy()
    write_csv_atomic(df, ATTENDANCE_LOG_CSV)

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def load_progress_skip_ok() -> pd.DataFrame:
    if PROGRESS_SKIP_OK_CSV.exists():
        df = pd.read_csv(PROGRESS_SKIP_OK_CSV, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=["date", "student_id", "note"])
        write_csv_atomic(df, PROGRESS_SKIP_OK_CSV)
        return df


    for c in ["date", "student_id", "note"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str).fillna("").str.strip()


    return df[["date", "student_id", "note"]]

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def save_progress_skip_ok(df: pd.DataFrame) -> None:
    for c in ["date", "student_id", "note"]:
        if c not in df.columns:
            df[c] = ""
    df = df[["date", "student_id", "note"]].copy()
    write_csv_atomic(df, PROGRESS_SKIP_OK_CSV)

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def is_progress_skip_ok_today(df: pd.DataFrame, student_id: str, d: date) -> bool:
    if df is None or df.empty:
        return False

    sid = str(student_id).strip()
    ds = str(d)

    tmp = df.copy()
    tmp["student_id"] = tmp["student_id"].astype(str).fillna("").str.strip()
    tmp["date"] = tmp["date"].astype(str).fillna("").str.strip()

    m = (
        tmp["student_id"].eq(sid)
        & tmp["date"].eq(ds)
    )
    return bool(m.any())

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def upsert_progress_skip_ok(df: pd.DataFrame, student_id: str, d: date, note: str = "") -> pd.DataFrame:
    sid = str(student_id).strip()
    ds = str(d)
    note = str(note).strip()

    if not df.empty:
        mask = (
            df["student_id"].astype(str).str.strip().eq(sid)
            & df["date"].astype(str).str.strip().eq(ds)
        )
        df = df.loc[~mask].copy()

    new_row = pd.DataFrame([{
        "date": ds,
        "student_id": sid,
        "note": note,
    }])

    return pd.concat([df, new_row], ignore_index=True)

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def load_prep_memo() -> pd.DataFrame:
    if PREP_MEMO_CSV.exists():
        df = pd.read_csv(PREP_MEMO_CSV, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=["student_id", "memo"])
        write_csv_atomic(df, PREP_MEMO_CSV)
        return df


    for c in ["student_id", "memo"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str).fillna("").str.strip()


    return df[["student_id", "memo"]]




# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def save_prep_memo(df: pd.DataFrame) -> None:
    for c in ["student_id", "memo"]:
        if c not in df.columns:
            df[c] = ""
    df = df[["student_id", "memo"]].copy()
    write_csv_atomic(df, PREP_MEMO_CSV)




# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def upsert_prep_memo(df: pd.DataFrame, student_id: str, memo: str) -> pd.DataFrame:
    sid = str(student_id).strip()
    memo = str(memo).strip()


    if not df.empty:
        mask = df["student_id"].astype(str).str.strip().eq(sid)
        df = df.loc[~mask].copy()


    if memo == "":
        return df


    new_row = pd.DataFrame([{
        "student_id": sid,
        "memo": memo,
    }])


    return pd.concat([df, new_row], ignore_index=True)


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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
# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def delete_attendance(df: pd.DataFrame, student_id: str, d: date) -> pd.DataFrame:
    if df.empty:
        return df
    sid = str(student_id).strip()
    ds = str(d)
    mask = (df["student_id"].astype(str).str.strip() == sid) & (df["date"].astype(str).str.strip() == ds)
    return df.loc[~mask].copy()

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def is_attendance_done_today(att_df: pd.DataFrame, student_id: str, d: date) -> bool:
    if att_df is None or att_df.empty:
        return False
    sid = str(student_id).strip()
    ds = str(d)
    m = (
        att_df["student_id"].astype(str).str.strip().eq(sid)
        & att_df["date"].astype(str).str.strip().eq(ds)
    )
    return bool(m.any())

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def is_progress_task_completed(row) -> bool:
    is_done = str(row.get("is_done", "")).strip().lower() in ["true", "1", "yes"]
    return bool(is_done)


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def is_progress_done_today(progress_df: pd.DataFrame, student_id: str, d: date) -> bool:
    if progress_df is None or progress_df.empty:
        return False


    sid = str(student_id).strip()
    ds = str(d)


    tmp = progress_df.copy()


    if "student_id" not in tmp.columns:
        return False


    tmp["student_id"] = tmp["student_id"].astype(str).fillna("").str.strip()


    # done_date がある場合は、それを最優先で使う
    if "done_date" in tmp.columns:
        tmp["done_date"] = tmp["done_date"].astype(str).fillna("").str.strip()
        m = (
            tmp["student_id"].eq(sid)
            & tmp["done_date"].eq(ds)
        )
        if bool(m.any()):
            return True


    # date 列運用なら保険で対応
    if "date" in tmp.columns:
        tmp["date"] = tmp["date"].astype(str).fillna("").str.strip()
        m = (
            tmp["student_id"].eq(sid)
            & tmp["date"].eq(ds)
        )
        if bool(m.any()):
            return True


    return False


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def build_today_task_status(att_done: bool, prog_done: bool) -> str:
    if att_done and prog_done:
        return "✅ 出欠済 / 進捗済"
    if (not att_done) and (not prog_done):
        return "🚨 出欠未 / 進捗未"
    if not att_done:
        return "❗出欠"
    return "❗進捗"


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def build_overdue_urgency_mark(d_str: str, today_date: date) -> str:
    d_obj = pd.to_datetime(d_str, errors="coerce")
    if pd.isna(d_obj):
        return "🚨"


    days_diff = (today_date - d_obj.date()).days


    if days_diff >= 2:
        return "🔥"
    if days_diff == 1:
        return "🚨"
    return "⚠"



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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def build_grade_options(students_df):
    existing = _unique_str_list(students_df.get("grade", pd.Series(dtype=str))) if students_df is not None else []
    base = [g for g in GRADE_PRESETS if g not in ("", "その他（自由入力）")]
    merged = base[:]
    for g in existing:
        if g not in merged:
            merged.append(g)
    return [""] + merged + ["その他（自由入力）"]

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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
    normalized = []
    for v in existing:
        nv = normalize_slot(v)
        if nv != "":
            normalized.append(nv)


    existing = sorted(list(dict.fromkeys(normalized)), key=sort_key)
    return [""] + existing + ["その他（自由入力）"]


# -----------------------------
# Smart defaults / ordering (v6.2)
# -----------------------------
# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def today_weekday_jp() -> str:
    jp = ["月", "火", "水", "木", "金", "土", "日"]
    return jp[date.today().weekday()]

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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

# [CHECK 2026-04-23] このファイル内では定義のみを確認。参照未検出のため、削除候補として要確認。
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
                action = normalize_action_value(r.get("action", ""))
                if action in ("追加", "時間変更"):
                    counts[sid] = counts.get(sid, 0) + 1
                elif action == "キャンセル":
                    counts[sid] = counts.get(sid, 0) - 1

    return {sid for sid, c in counts.items() if c > 0}

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def norm_lower(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.lower()

def normalize_action_value(v):
    """schedule_overrides.csv の action 表記を内部判定用に統一する"""
    a = str(v).strip().lower()


    if a in ["add", "追加"]:
        return "追加"


    if a in ["cancel", "キャンセル"]:
        return "キャンセル"


    if a in ["move", "time_change", "時間変更"]:
        return "時間変更"


    if a in ["振替"]:
        return "追加"


    return str(v).strip()

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def format_override_action(action):
    return normalize_action_value(action)

# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def session_mark(v: str) -> str:
    if str(v).strip().lower() == "self":
        return "(自)"
    return ""


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def write_csv_atomic(df: pd.DataFrame, path: Path) -> None:
    # path は str で渡されることもあるので Path に正規化
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(path)


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
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
    ["student_id", "course_id", "task_id", "is_done", "is_skip", "done_date", "note"],
    stop_on_missing=False,
)


kentei_prog = safe_read_csv(
    KENTEI_PROGRESS_CSV,
    ["student_id", "grade", "task_id", "is_done", "is_skip", "done_date", "note"],
    stop_on_missing=False,
)

# done_date の表記ゆれ対策（Excel編集後でも YYYY-MM-DD にそろえる）
if "done_date" in curr_prog.columns:
    curr_prog["done_date"] = pd.to_datetime(curr_prog["done_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    curr_prog["done_date"] = curr_prog["done_date"].fillna("")


if "done_date" in kentei_prog.columns:
    kentei_prog["done_date"] = pd.to_datetime(kentei_prog["done_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    kentei_prog["done_date"] = kentei_prog["done_date"].fillna("")

kentei_tasks = safe_read_csv(
    KENTEI_TASKS_CSV,
    ["grade", "task_id", "task_name", "order", "student_id"],
    stop_on_missing=False,
)

kentei_exam = safe_read_csv(
    KENTEI_EXAM_SCHEDULE_CSV,
    ["student_id", "exam_date", "exam_type", "grade", "note"],
    stop_on_missing=False,
)

# =========================================================
# 🪑 座席表（今日の配置）: STEP1/2
#   - まずはCSVを作成・読み込み・一覧表示できる状態にする
#   - UIからの登録/編集は次ステップで追加する
# =========================================================
SEAT_ASSIGNMENT_COLS = ["date", "slot", "seat_no", "student_id", "note"]
if not SEAT_ASSIGNMENTS_CSV.exists():
    write_csv_atomic(pd.DataFrame(columns=SEAT_ASSIGNMENT_COLS), SEAT_ASSIGNMENTS_CSV)

seat_assignments = safe_read_csv(
    SEAT_ASSIGNMENTS_CSV,
    SEAT_ASSIGNMENT_COLS,
    stop_on_missing=False,
)

# =========================================================
# 🪑 基本席マスタ
# =========================================================
DEFAULT_SEAT_COLS = ["student_id", "default_seat_no", "note"]


if not DEFAULT_SEATS_CSV.exists():
    write_csv_atomic(pd.DataFrame(columns=DEFAULT_SEAT_COLS), DEFAULT_SEATS_CSV)


default_seats = safe_read_csv(
    DEFAULT_SEATS_CSV,
    DEFAULT_SEAT_COLS,
    stop_on_missing=False,
)


if default_seats.empty:
    default_seats = pd.DataFrame(columns=DEFAULT_SEAT_COLS)
else:
    for c in DEFAULT_SEAT_COLS:
        if c not in default_seats.columns:
            default_seats[c] = ""
    default_seats = default_seats[DEFAULT_SEAT_COLS].fillna("")
    default_seats["student_id"] = default_seats["student_id"].astype(str).str.strip()
    default_seats["default_seat_no"] = default_seats["default_seat_no"].astype(str).str.strip()
    default_seats["note"] = default_seats["note"].astype(str).str.strip()


if seat_assignments.empty:
    seat_assignments = pd.DataFrame(columns=SEAT_ASSIGNMENT_COLS)
else:
    for c in SEAT_ASSIGNMENT_COLS:
        if c not in seat_assignments.columns:
            seat_assignments[c] = ""
    seat_assignments = seat_assignments[SEAT_ASSIGNMENT_COLS].fillna("")
    seat_assignments["date"] = pd.to_datetime(seat_assignments["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    seat_assignments["slot"] = seat_assignments["slot"].astype(str).str.strip()
    seat_assignments["seat_no"] = seat_assignments["seat_no"].astype(str).str.strip()
    seat_assignments["student_id"] = seat_assignments["student_id"].astype(str).str.strip()
    seat_assignments["note"] = seat_assignments["note"].astype(str).str.strip()

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
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] label {
        margin-bottom: -6px;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] {
        margin-bottom: 0.4rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # =========================
    # タブ状態（初期）
    # =========================
    is_log_tab = False

    st.sidebar.header("フィルタ")


    # =========================
    # フィルタ候補を作る
    # =========================
    include_inactive = st.session_state.get("include_inactive", False)


    students_for_filter = students.copy()
    if (not include_inactive) and ("is_active" in students_for_filter.columns):
        students_for_filter = students_for_filter[
            students_for_filter["is_active"].astype(str).str.strip().str.lower() == "true"
        ].copy()


    student_rows = students_for_filter.copy()
    student_rows["display_name"] = student_rows["display_name"].fillna("").astype(str).str.strip()
    student_rows["is_active_norm"] = (
        student_rows.get("is_active", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )


    active_base_student_names = sorted(
        [n for n in student_rows.loc[student_rows["is_active_norm"] == "true", "display_name"].tolist() if n]
    )


    inactive_base_student_names = sorted(
        [n for n in student_rows.loc[student_rows["is_active_norm"] != "true", "display_name"].tolist() if n]
    )


    # 重複除去
    active_base_student_names = list(dict.fromkeys(active_base_student_names))
    inactive_base_student_names = list(dict.fromkeys(inactive_base_student_names))


    priority_student_names = st.session_state.get("sidebar_student_priority_order", [])


    student_names = []
    used_names = set()


    # まず優先順（在籍中のみ）
    for name in priority_student_names:
        n = str(name).strip()
        if n and n in active_base_student_names and n not in used_names:
            student_names.append(n)
            used_names.add(n)


    # 次に在籍中の残り
    for name in active_base_student_names:
        if name not in used_names:
            student_names.append(name)
            used_names.add(name)


    # 最後に退会済み（表示だけ「（退会）」を付ける）
    for name in inactive_base_student_names:
        if name not in used_names:
            label = f"{name}（退会）"
            student_names.append(label)
            used_names.add(name)

    # 次に在籍中の残り
    for name in active_base_student_names:
        if name not in used_names:
            student_names.append(name)
            used_names.add(name)


    # 最後に退会済み
    for name in inactive_base_student_names:
        if name not in used_names:
            student_names.append(name)
            used_names.add(name)




    grade_list = sorted(
        [
            str(g).strip()
            for g in students_for_filter.get("grade", pd.Series(dtype=str)).fillna("").astype(str)
            if str(g).strip()
        ]
    )


    curriculum_list = sorted(
        [
            str(c).strip()
            for c in log_all.get("curriculum", pd.Series(dtype=str)).fillna("").astype(str)
            if str(c).strip()
        ]
    )


    status_list = sorted(
        list(
            {
                str(s).strip().lower()
                for s in log_all.get("status", pd.Series(dtype=str)).fillna("").astype(str)
                if str(s).strip()
            }
        )
    )


    # =========================
    # フィルタ活性条件
    # =========================
    current_student = st.session_state.get("sidebar_student", "（全員）")
    is_single_student = current_student != "（全員）"


    # 「閲覧」ではログ表示系は使える
    is_log_view = True


    # =========================
    # 対象
    # =========================
    st.sidebar.markdown("### 対象")

    if "pending_sidebar_student" in st.session_state:
        st.session_state["sidebar_student"] = st.session_state.pop("pending_sidebar_student")

    selected_student = st.sidebar.selectbox(
        "👤 生徒",
        ["（全員）"] + student_names,
        key="sidebar_student",
    )
    
    selected_student_raw = selected_student.replace("（退会）", "")

    selected_grade = st.sidebar.selectbox(
        "学年",
        ["（全て）"] + grade_list,
        key="sidebar_grade",
        disabled=is_single_student,
    )
    if is_single_student:
        st.sidebar.caption("※ 生徒を選択中のため、学年フィルタは無効です")


    # =========================
    # 表示
    # =========================
    st.sidebar.markdown("### 表示")


    show_today_only = st.sidebar.checkbox(
        "表示を今日の生徒だけにする",
        value=False,
        key="today_only",
    )


    include_inactive = st.sidebar.checkbox(
        "生徒候補に退会済みも含める",
        value=include_inactive,
        key="include_inactive",
    )
    
    selected_curriculum = st.sidebar.selectbox(
        "カリキュラム（ログ表示）",
        ["（全て）"] + curriculum_list,
        key="sidebar_curriculum",
    )


    selected_status = st.sidebar.selectbox(
        "状態（詳細表示用）",
        ["（全て）"] + status_list,
        key="sidebar_status",
    )

    # =========================
    # 編集ロック解除
    # =========================
    st.sidebar.markdown("### 編集ロック解除")


    override_passed_lock = st.sidebar.checkbox(
        "⚠ 合格済み検定課題を編集する（通常はOFF）",
        key="override_passed_lock"
    )


    override_done_lock = st.sidebar.checkbox(
        "⚠ 完了済み課題を編集する（通常はOFF）",
        key="override_done_lock"
    )

    st.sidebar.caption("※ 合格済み/完了済みの編集を一時的に許可したい時だけONにしてください")
    # =========================================================
    # Apply filters (logs)
    # =========================================================
    filtered_done = log_done.copy()
    if selected_grade != "（全て）":
        filtered_done = filtered_done[filtered_done["grade"] == selected_grade]
    if selected_student != "（全員）":
        filtered_done = filtered_done[filtered_done["display_name"] == selected_student_raw]
    if selected_curriculum != "（全て）":
        filtered_done = filtered_done[filtered_done["curriculum"] == selected_curriculum]


    filtered_all = log_all.copy()
    if selected_grade != "（全て）":
        filtered_all = filtered_all[filtered_all["grade"] == selected_grade]
    if selected_student != "（全員）":
        filtered_all = filtered_all[filtered_all["display_name"] == selected_student_raw]
    if selected_curriculum != "（全て）":
        filtered_all = filtered_all[filtered_all["curriculum"] == selected_curriculum]
    if selected_status != "（全て）":
        filtered_all = filtered_all[norm_lower(filtered_all["status"]) == selected_status]


    # =========================================================
    # Top metrics
    # =========================================================
    col1, col2, col3, col4 = st.columns(4)
    active_students_count = len(
        students[
            students["is_active"].fillna("").astype(str).str.strip().str.lower().replace("", "true").isin(["true", "1", "yes"])
        ]
    )
    col1.metric("生徒数", int(active_students_count))

  #  col2.metric("ログ総数", int(len(log_all)))
  #  col3.metric("完了ログ（done）", int(len(log_done)))
  #  col4.metric("表示中（done）", int(len(filtered_done)))
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

    # 不要なメソッド？
    def safe_read_csv_local(path: Path, required_cols=None,stop_on_missing=False) -> pd.DataFrame:
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
    
    
    # ⚠ 検定結果未登録アラート
    # =========================================================


    kentei_alert_rows = []
    
    name_map = {
        str(r["student_id"]).strip(): str(r["display_name"]).strip()
        for _, r in students.iterrows()
    }

    exam_sched = safe_read_csv(
        KENTEI_EXAM_SCHEDULE_CSV,
        required_cols=["student_id", "grade", "exam_date", "exam_type", "kentei"]
    ).copy() 

    if not exam_sched.empty:
        for c in ["student_id", "grade", "exam_date", "exam_type", "kentei"]:
            if c not in exam_sched.columns:
                exam_sched[c] = ""
            exam_sched[c] = exam_sched[c].fillna("").astype(str).str.strip()


        # 受験日が入っている予定だけ対象
        exam_sched = exam_sched[exam_sched["exam_date"] != ""].copy()

        # 結果側
        kentei_df = load_kentei_results().copy()
        if not kentei_df.empty:
            for c in ["student_id", "grade", "pass_date"]:
                if c not in kentei_df.columns:
                    kentei_df[c] = ""
                kentei_df[c] = kentei_df[c].fillna("").astype(str).str.strip()


        today_str = date.today().strftime("%Y-%m-%d")


        for _, r in exam_sched.iterrows():
            sid = str(r.get("student_id", "")).strip()
            grade = str(r.get("grade", "")).strip()
            exam_date = str(r.get("exam_date", "")).strip()


            if sid == "" or grade == "" or exam_date == "":
                continue


            # 今日以前だけ
            if exam_date > today_str:
                continue


            # student_id + grade で結果を確認
            has_result = False
            if not kentei_df.empty:
                chk = kentei_df[
                    (kentei_df["student_id"].astype(str).str.strip() == sid) &
                    (kentei_df["grade"].astype(str).str.strip() == grade)
                ]
                if not chk.empty:
                    has_result = True


            if not has_result:
                kentei_alert_rows.append({
                    "student_id": sid,
                    "grade": grade,
                    "受験日": exam_date
                })


    # 表示
    if kentei_alert_rows:
        k_df = pd.DataFrame(kentei_alert_rows).drop_duplicates()


        st.warning(f"⚠ 検定結果未登録：{len(k_df)}件あります")


        for _, row in k_df.iterrows():
            sid = row["student_id"]
            grade = row["grade"]
            exam_date = row["受験日"]

            name = name_map.get(str(sid).strip(), sid)
            st.write(f"{name}（{sid}） / {grade}級 / 受験日: {exam_date}")


    # =========================================================
    # 🚨 未完了タスク（昨日以前）
    # 予定があったのに attendance_log が無いものを出す
    # 判定単位：date × student_id
    # =========================================================
    #st.subheader("🚨 未完了タスク（昨日以前）")

    att_df_check = load_attendance_log().copy()
    prog_skip_df = load_progress_skip_ok().copy()

    # 出席ログ正規化
    if att_df_check.empty:
        att_df_check = pd.DataFrame(columns=["date", "student_id", "kind", "memo"])
    else:
        for c in ["date", "student_id", "kind", "memo"]:
            if c not in att_df_check.columns:
                att_df_check[c] = ""
            att_df_check[c] = att_df_check[c].fillna("").astype(str).str.strip()


    # スケジュール正規化
    sched_check = student_schedule.copy()
    if not sched_check.empty:
        for c in ["student_id", "weekday", "slot", "session_type"]:
            if c not in sched_check.columns:
                sched_check[c] = ""
            sched_check[c] = sched_check[c].fillna("").astype(str).str.strip()
        sched_check = sched_check.drop_duplicates(subset=["student_id", "weekday", "slot"], keep="first")


    ov_check = schedule_overrides.copy()
    if not ov_check.empty:
        for c in ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]:
            if c not in ov_check.columns:
                ov_check[c] = ""
            ov_check[c] = ov_check[c].fillna("").astype(str).str.strip()


    ts_check = timeslots.copy()
    if not ts_check.empty:
        for c in ["weekday", "slot", "start", "end"]:
            if c not in ts_check.columns:
                ts_check[c] = ""
            ts_check[c] = ts_check[c].fillna("").astype(str).str.strip()
        ts_check = ts_check.drop_duplicates(subset=["weekday", "slot"], keep="first")


    students_check = students.copy()
    if not include_inactive and "is_active" in students_check.columns:
        students_check = students_check[students_check["is_active"] == "true"].copy()


    # 生徒ID→名前
    student_name_map = {}
    if not students_check.empty and {"student_id", "display_name"}.issubset(students_check.columns):
        student_name_map = dict(
            zip(
                students_check["student_id"].astype(str).str.strip(),
                students_check["display_name"].fillna("").astype(str).str.strip()
            )
        )
        
    kentei_hint_map = {}
    try:
        kentei_df = load_kentei_results()
        if not kentei_df.empty:
            score_src = kentei_df.copy()


            if "score" in score_src.columns:
                score_src["score_num"] = pd.to_numeric(score_src["score"], errors="coerce")
            else:
                score_src["score_num"] = np.nan


            score_src["item"] = score_src["grade"].astype(str).str.strip() + "級"


            scratch_best = (
                score_src.dropna(subset=["grade"])
                .copy()
                .assign(grade_num=pd.to_numeric(score_src["grade"], errors="coerce"))
                .sort_values(["student_id", "grade_num"], ascending=[True, True])
                .drop_duplicates(subset=["student_id"], keep="first")
            )


            if not scratch_best.empty:
                scratch_best_small = scratch_best[["student_id", "item"]].rename(columns={"item": "scratch_best"})
            else:
                scratch_best_small = pd.DataFrame(columns=["student_id", "scratch_best"])


            best_score_small = (
                score_src.groupby("student_id", as_index=False)["score_num"]
                .max()
                .rename(columns={"score_num": "best_score"})
            )


            kentei_view = students.copy()
            kentei_view = kentei_view.merge(scratch_best_small, on="student_id", how="left")
            kentei_view = kentei_view.merge(best_score_small, on="student_id", how="left")
            kentei_view["次の判断"] = kentei_view["best_score"].apply(judge_next_step)
            kentei_view["次の級"] = kentei_view["scratch_best"].apply(get_next_grade)
            kentei_view["検定目安"] = kentei_view.apply(
                lambda r: build_kentei_hint(r.get("次の判断", ""), r.get("次の級", "")),
                axis=1
            )


            kentei_hint_map = dict(
                zip(
                    kentei_view["student_id"].astype(str).str.strip(),
                    kentei_view["検定目安"].fillna("").astype(str)
                )
            )
    except Exception:
        kentei_hint_map = {}


    active_ids = set(student_name_map.keys()) if student_name_map else set()

    today_rows = []
    overdue_rows = []

    # 今月1日〜今日までを対象
    first_day = today.replace(day=1)
    today_str = today.strftime("%Y-%m-%d")
    check_days = pd.date_range(first_day, today, freq="D")
    
    show_progress_warning = False

    for d in check_days:
        d_date = d.date()
        d_str = d_date.strftime("%Y-%m-%d")
        d_wd = weekday_map[d_date.weekday()]


        # その日のベース予定
        if sched_check.empty:
            base_day = pd.DataFrame(columns=["student_id", "weekday", "slot", "session_type"])
        else:
            base_day = sched_check[sched_check["weekday"] == d_wd].copy()


        if active_ids:
            base_day = base_day[base_day["student_id"].astype(str).str.strip().isin(active_ids)].copy()


        # その日の overrides
        if ov_check.empty:
            ov_day = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"])
        else:
            ov_day = ov_check[ov_check["date"] == d_str].copy()


        # cancel 適用
        if not ov_day.empty:
            cancel_day = ov_day[
                ov_day["action"].map(normalize_action_value) == "キャンセル"
            ].copy()

            if not cancel_day.empty:
                cancel_day["student_id_key"] = cancel_day["student_id"].astype(str).str.strip()
                cancel_day["slot_key"] = cancel_day["slot"].astype(str).str.strip().map(normalize_slot)


                cancel_keys = set(zip(cancel_day["student_id_key"], cancel_day["slot_key"]))


                base_day["student_id_key"] = base_day["student_id"].astype(str).str.strip()
                base_day["slot_key"] = base_day["slot"].astype(str).str.strip().map(normalize_slot)


                base_day = base_day[
                    ~base_day.apply(
                        lambda r: (
                            str(r.get("student_id_key", "")).strip(),
                            str(r.get("slot_key", "")).strip()
                        ) in cancel_keys,
                        axis=1
                    )
                ].copy()


                base_day = base_day.drop(columns=["student_id_key", "slot_key"], errors="ignore")

                cancel_day["slot_key"] = cancel_day["slot"].astype(str).str.strip().map(normalize_slot)


                cancel_keys = set(zip(cancel_day["student_id_key"], cancel_day["slot_key"]))


                base_day = base_day[
                    ~base_day.apply(
                        lambda r: (
                            str(r.get("student_id", "")).strip(),
                            normalize_slot(r.get("slot", ""))
                        ) in cancel_keys,
                        axis=1
                    )
                ].copy()



        # add 適用
        add_rows = []
        if not ov_day.empty:
            add_day = ov_day[
                ov_day["action"].map(normalize_action_value) == "追加"
            ].copy()
            if not add_day.empty:
                for _, r in add_day.iterrows():
                    sid = str(r.get("student_id", "")).strip()
                    if active_ids and sid not in active_ids:
                        continue
                    add_rows.append({
                        "student_id": sid,
                        "weekday": d_wd,
                        "slot": str(r.get("slot", "")).strip(),
                        "session_type": str(r.get("session_type", "")).strip() or "lesson",
                    })


        add_day_df = pd.DataFrame(add_rows)


        # その日の予定を統合
        plan_day = pd.concat([base_day, add_day_df], ignore_index=True) if not add_day_df.empty else base_day.copy()


        # 例外追加分も含めて、キャンセル済み予定を除外する
        if not plan_day.empty and not ov_day.empty:
            cancel_day_for_plan = ov_day[
                ov_day["action"].map(normalize_action_value) == "キャンセル"
            ].copy()


            if not cancel_day_for_plan.empty:
                cancel_day_for_plan["student_id_key"] = cancel_day_for_plan["student_id"].astype(str).str.strip()
                cancel_day_for_plan["slot_key"] = cancel_day_for_plan["slot"].astype(str).str.strip().map(normalize_slot)


                cancel_keys_for_plan = set(
                    zip(
                        cancel_day_for_plan["student_id_key"],
                        cancel_day_for_plan["slot_key"],
                    )
                )


                plan_day["student_id_key"] = plan_day["student_id"].astype(str).str.strip()
                plan_day["slot_key"] = plan_day["slot"].astype(str).str.strip().map(normalize_slot)


                plan_day = plan_day[
                    ~plan_day.apply(
                        lambda r: (
                            str(r.get("student_id_key", "")).strip(),
                            str(r.get("slot_key", "")).strip(),
                        ) in cancel_keys_for_plan,
                        axis=1,
                    )
                ].copy()


                plan_day = plan_day.drop(columns=["student_id_key", "slot_key"], errors="ignore")




        if plan_day.empty:
            continue


        plan_day = plan_day.drop_duplicates(subset=["student_id", "slot"], keep="first").copy()


        # timeslots を結合して start/end を補完
        if not ts_check.empty:
            plan_day = plan_day.merge(ts_check, on=["weekday", "slot"], how="left")


        # 名前付与
        plan_day["display_name"] = (
            plan_day["student_id"].astype(str).map(student_name_map).fillna(plan_day["student_id"].astype(str))
        )


        # -------------------------------------------------
        # 未完了判定用に「1日1生徒1件」にまとめる
        # 判定単位：date × student_id
        # -------------------------------------------------
        def pick_session_label(series):
            vals = [str(v).strip().lower() for v in series if str(v).strip() != ""]
            if any(v in ["self", "selfstudy", "自習"] for v in vals):
                return "自習"
            return "授業"


        def join_slots(series):
            vals = []
            for v in series:
                s = str(v).strip()
                if s and s not in vals:
                    vals.append(s)
            return " / ".join(vals)


        plan_day_unit = (
            plan_day.groupby("student_id", as_index=False)
            .agg({
                "display_name": "first",
                "slot": join_slots,
                "session_type": pick_session_label,
            })
            .rename(columns={
                "display_name": "display_name",
                "slot": "slot_label",
                "session_type": "session_label",
            })
        )


        # attendance の date × student_id があるか
        done_keys = set(
            zip(
                att_df_check["date"].astype(str).str.strip(),
                att_df_check["student_id"].astype(str).str.strip()
            )
        )

        for _, r in plan_day_unit.iterrows():
            sid = str(r.get("student_id", "")).strip()
            if sid == "":
                continue

            att_done = (d_str, sid) in done_keys

            curr_done = is_progress_done_today(
                curr_prog[curr_prog.apply(is_progress_task_completed, axis=1)].copy(),
                sid,
                d_date
            )


            kentei_done = is_progress_done_today(
                kentei_prog[kentei_prog.apply(is_progress_task_completed, axis=1)].copy(),
                sid,
                d_date
            )

            skip_done = is_progress_skip_ok_today(prog_skip_df, sid, d_date)

            # まず予定の種別
            session_type = str(r.get("session_label", "")).strip()

            # その日の出欠実績があれば、実績の kind を優先する
            actual_kind = ""
            att_row = att_df_check[
                (att_df_check["date"].astype(str).str.strip() == d_str) &
                (att_df_check["student_id"].astype(str).str.strip() == sid)
            ]

            if not att_row.empty:
                actual_kind = str(att_row.iloc[-1].get("kind", "")).strip().lower()

            if actual_kind in ["lesson", "授業", ""]:
                effective_kind = "lesson"
                session_mark_text = "授業"
            elif actual_kind in ["self", "selfstudy", "自習"]:
                effective_kind = "self"
                session_mark_text = "自習"
            elif actual_kind in ["absence", "欠席"]:
                effective_kind = "absence"
                session_mark_text = "欠席"
            elif actual_kind in ["cancel", "キャンセル"]:
                effective_kind = "cancel"
                session_mark_text = "キャンセル"
            else:
                # 出欠実績が無いときだけ予定の種別を使う
                if session_type in ["lesson", "授業", ""]:
                    effective_kind = "lesson"
                    session_mark_text = "授業"
                else:
                    effective_kind = "self"
                    session_mark_text = "自習"

            # 進捗対象は授業だけ
            if effective_kind != "lesson":
                prog_done = True
            else:
                prog_done = bool(curr_done or kentei_done or skip_done)

            # 出欠済みだけど進捗未なら警告
            if att_done and (not prog_done):
                show_progress_warning = True

            # 出欠も進捗も済んでいるなら未完了ではない
            if att_done and prog_done:
                continue

            row_data = {
                "日付": d_str,
                "student_id": sid,
                "生徒": str(r.get("display_name", "")).strip(),
                "コマ": str(r.get("slot_label", "")).strip(),
                "種別": session_mark_text,
                "状態": build_today_task_status(att_done, prog_done),
                "未完了状態": build_today_task_status(att_done, prog_done),
                "検定目安": colorize_kentei_hint(
                    kentei_hint_map.get(str(sid).strip(), "")
                )
            }

            # 今日の未完了は、出欠未 または 進捗未 を広く検出する
            # ミス防止のため、どちらか未完了なら表示する
            if d_str == today_str:
                if (not att_done) or (not prog_done):
                    today_rows.append(row_data)

            else:
                # 一時停止：
                # 昨日以前の未完了は、現在の固定スケジュールで過去を再計算してしまうため、
                # 日別予定スナップショット方式に直すまで表示しない。
                pass

                    
    if show_progress_warning:
        st.warning("⚠ 進捗登録がまだです")

    def render_unfinished_section(title: str, df: pd.DataFrame, key_prefix: str):
        st.subheader(title)


        if df.empty:
            return

        show_df = df.copy()

        priority_map = {
            "🚨 出欠未 / 進捗未": 0,
            "❗出欠": 1,
            "❗進捗": 2,
        }

        if "状態" in show_df.columns:
            show_df["priority"] = show_df["状態"].map(priority_map).fillna(99)
        else:
            show_df["priority"] = 99


        sort_cols = ["priority"]
        for col in ["日付", "コマ", "生徒"]:
            if col in show_df.columns:
                sort_cols.append(col)


        show_df = show_df.sort_values(
            by=sort_cols,
            na_position="last"
        ).reset_index(drop=True)


        st.caption("未完了タスクから、そのまま出席登録できます。")


        for i, row in show_df.iterrows():

            d_str = str(row.get("日付", "")).strip()
            sid = str(row.get("student_id", "")).strip()
            slot = str(row.get("コマ", "")).strip()
            name = str(row.get("生徒", "")).strip()
            kind_label = str(row.get("種別", "")).strip()
            status = str(row.get("状態", "")).strip()
            attendance_done = "出欠未" not in status
            progress_done = "進捗未" not in status

            display_status = status
            if key_prefix == "overdue":
                urgency_mark = build_overdue_urgency_mark(d_str, today)
                if status:
                    display_status = f"{urgency_mark} {status}"


            c1, c2, c3, c4, c5, c6, c7 = st.columns([3.0, 1.0, 1.0, 1.0, 1.2, 1.6, 1.2])

            with c1:
                st.markdown(
                    f"**{d_str} / {slot}限 / {name} / {kind_label}**<br>{unfinished_status_badge_html(display_status)}",
                    unsafe_allow_html=True
                )

            with c2:
                if st.button(
                    "授業で記録",
                    key=f"{key_prefix}_lesson_{d_str}_{sid}_{slot}_{i}",
                    disabled=attendance_done
                ):
                    att_df = load_attendance_log().copy()
                    d_obj = pd.to_datetime(d_str, errors="coerce")
                    if pd.notna(d_obj):
                        att_df = upsert_attendance(
                            att_df,
                            student_id=sid,
                            d=d_obj.date(),
                            kind="lesson",
                            memo="未完了タスクから登録"
                        )
                        save_attendance_log(att_df)
                        st.success(f"{name} を授業で記録しました。")
                        st.rerun()
                    else:
                        st.error("日付の変換に失敗しました。")


            with c3:
                if st.button(
                    "自習で記録",
                    key=f"{key_prefix}_self_{d_str}_{sid}_{slot}_{i}",
                    disabled=attendance_done
                ):
                    att_df = load_attendance_log().copy()
                    d_obj = pd.to_datetime(d_str, errors="coerce")
                    if pd.notna(d_obj):
                        att_df = upsert_attendance(
                            att_df,
                            student_id=sid,
                            d=d_obj.date(),
                            kind="self",
                            memo="未完了タスクから登録"
                        )
                        save_attendance_log(att_df)
                        st.success(f"{name} を自習で記録しました。")
                        st.rerun()
                    else:
                        st.error("日付の変換に失敗しました。")


            with c4:
                if st.button(
                    "欠席で記録",
                    key=f"{key_prefix}_absence_{d_str}_{sid}_{slot}_{i}",
                    disabled=attendance_done
                ):
                    att_df = load_attendance_log().copy()
                    d_obj = pd.to_datetime(d_str, errors="coerce")
                    if pd.notna(d_obj):
                        att_df = upsert_attendance(
                            att_df,
                            student_id=sid,
                            d=d_obj.date(),
                            kind="absence",
                            memo="未完了タスクから欠席登録"
                        )
                        save_attendance_log(att_df)
                        st.success(f"{name} を欠席で記録しました。")
                        st.rerun()
                    else:
                        st.error("日付の変換に失敗しました。")


            with c5:
                if st.button(
                    "キャンセルで記録",
                    key=f"{key_prefix}_cancel_{d_str}_{sid}_{slot}_{i}",
                    disabled=attendance_done
                ):
                    att_df = load_attendance_log().copy()
                    d_obj = pd.to_datetime(d_str, errors="coerce")
                    if pd.notna(d_obj):
                        att_df = upsert_attendance(
                            att_df,
                            student_id=sid,
                            d=d_obj.date(),
                            kind="cancel",
                            memo="未完了タスクからキャンセル登録"
                        )
                        save_attendance_log(att_df)
                        st.success(f"{name} をキャンセルで記録しました。")
                        st.rerun()
                    else:
                        st.error("日付の変換に失敗しました。")


            with c6:
                if st.button(
                    "進捗なしで完了",
                    key=f"{key_prefix}_no_progress_{d_str}_{sid}_{slot}_{i}",
                    disabled=progress_done
                ):
                    d_obj = pd.to_datetime(d_str, errors="coerce")
                    if pd.notna(d_obj):
                        prog_skip_df2 = load_progress_skip_ok().copy()
                        prog_skip_df2 = upsert_progress_skip_ok(
                            prog_skip_df2,
                            student_id=sid,
                            d=d_obj.date(),
                            note="未完了タスクから進捗なしで完了"
                        )
                        save_progress_skip_ok(prog_skip_df2)
                        st.success(f"{name} を『進捗なしで完了』にしました。")
                        st.rerun()
                    else:
                        st.error("日付の変換に失敗しました。")

            with c7:
                if st.button(
                    "この生徒",
                    key=f"{key_prefix}_focus_{d_str}_{sid}_{slot}_{i}"
                ):
                    target_name = name if name else sid
                    st.session_state["sidebar_student_pending"] = target_name
                    st.rerun()

    today_df = pd.DataFrame(today_rows)
    today_count = len(today_df)

    if today_count > 0:
        st.warning(f"⚠️ 今日の未完了タスク：{today_count}件あります（最優先）")
        st.markdown(f"### ⚠ 今日の未完了：**{today_count}件**")

        today_show = today_df.copy()
        if not today_show.empty:
            today_show = today_df[["生徒", "状態"]].copy()
            today_show = today_show.drop_duplicates().reset_index(drop=True)


            summary_rows = []
            for name, group in today_show.groupby("生徒", dropna=False):
                states = list(dict.fromkeys(group["状態"].astype(str).tolist()))


                if "🚨 出欠未 / 進捗未" in states:
                    merged_status = "🚨 出欠未 / 進捗未あり"
                else:
                    parts = []
                    if "❗出欠" in states:
                        parts.append("出欠未")
                    if "❗進捗" in states:
                        parts.append("進捗未")

                    if parts:
                        merged_status = "⚠ " + "・".join(parts)
                    else:
                        merged_status = ""

                summary_rows.append({
                    "生徒": str(name).strip(),
                    "状態": merged_status,
                })


            today_show = pd.DataFrame(summary_rows)


            priority_map = {
                "🚨 出欠未 / 進捗未あり": 0,
                "❗出欠・進捗": 0,
                "❗出欠": 1,
                "❗進捗": 2,
            }


            today_show["priority"] = today_show["状態"].map(priority_map).fillna(99)
            today_show = today_show.sort_values(["priority", "生徒"]).reset_index(drop=True)


            for _, r in today_show.iterrows():
                label = str(r.get("生徒", "")).strip()
                status = str(r.get("状態", "")).strip()
                st.write(f"• {label} / {status}")

    else:
        st.success("✅ 今日の未完了タスクはありません")


    st.divider()


    overdue_df = pd.DataFrame(overdue_rows)
    
    if overdue_rows:
        debug_overdue = pd.DataFrame(overdue_rows)
        st.write("昨日以前の未完了 確認用")
        show_cols = [c for c in ["日付", "student_id", "生徒", "コマ", "種別", "状態"] if c in debug_overdue.columns]
        st.dataframe(debug_overdue[show_cols], use_container_width=True)


    overdue_count = len(overdue_df)
    if overdue_count > 0:
        st.error(f"🚨 未完了タスク（昨日以前）：{overdue_count}件あります（優先的に対応してください）")
        render_unfinished_section("🚨 未完了タスク（昨日以前）", overdue_df, "overdue")
    else:
        st.success("✅ 未完了タスク（昨日以前）はありません")

    st.divider()

    st.subheader(f"🗓 今日（{today.strftime('%Y-%m-%d')}・{today_wd}）の予定")
    st.caption("※ 記録後でも「取消」で元に戻せます")
    #st.info("⚠ 授業が終わったら『進捗登録』または『進捗なしで完了』を必ず押してください")
    st.warning("授業が終わったら、出欠を記録してください。進捗がある場合は下のカリキュラム課題 / 検定課題で登録してください。進捗が無い場合だけ「進捗なしで完了」を押してください。")

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

        if "is_active" in base_students.columns:
            base_students = base_students[
                base_students["is_active"].fillna("").astype(str).str.strip().str.lower().replace("", "true").isin(["true", "1", "yes"])
            ].copy()


        # ベース（固定）スケジュール
        today_view = sched_today.merge(
            base_students[["student_id", "display_name", "grade", "number_of_times", "join_date"]],
            on="student_id",
            how="inner",
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
            cancel_df = ov_today[
                ov_today["action"].map(normalize_action_value) == "キャンセル"
            ].copy()
            if not cancel_df.empty:
                cancel_df["student_id_key"] = cancel_df["student_id"].astype(str).str.strip()
                cancel_df["slot_key"] = cancel_df["slot"].astype(str).str.strip().map(normalize_slot)


                cancel_keys = set(zip(cancel_df["student_id_key"], cancel_df["slot_key"]))


                today_view = today_view[
                    ~today_view.apply(
                        lambda r: (
                            str(r.get("student_id", "")).strip(),
                            normalize_slot(r.get("slot", ""))
                        ) in cancel_keys,
                        axis=1
                    )
                ].copy()

            # add: 追加（必要ならベースを置き換え）
            add_df = ov_today[
                ov_today["action"].map(normalize_action_value) == "追加"
            ].copy()
            if not add_df.empty:
                # 置き換え（同じ student_id×slot はベースを消す）
                add_keys = set(zip(
                    add_df["student_id"].astype(str).str.strip(),
                    add_df["slot"].astype(str).str.strip().map(normalize_slot),
                ))
                today_view = today_view[
                    ~today_view.apply(
                        lambda r: (
                            str(r.get("student_id", "")).strip(),
                            normalize_slot(r.get("slot", ""))
                        ) in add_keys,
                        axis=1,
                    )
                ].copy()


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


                # 生徒情報を結合 ← ここが重要
                add_view = add_view.merge(
                    base_students[["student_id", "display_name", "grade", "number_of_times", "join_date"]],
                    on="student_id",
                    how="left",
                )


                # session_type（空なら lesson）
                if "session_type" not in add_view.columns:
                    add_view["session_type"] = "lesson"
                add_view["session_type"] = add_view["session_type"].replace("", "lesson").fillna("lesson")


                # 表示に必要な列を安全に補う
                for c in ["display_name", "grade", "number_of_times", "join_date", "note", "start", "end"]:
                    if c not in add_view.columns:
                        add_view[c] = ""


                for c in ["note"]:
                    if c not in today_view.columns:
                        today_view[c] = ""


                add_view["display_name"] = add_view["display_name"].fillna("").astype(str).str.strip()
                add_view["note"] = add_view["note"].fillna("").astype(str)


                today_view = pd.concat([today_view, add_view], ignore_index=True)

        # =====================================================
        # 今日キャンセル済みの予定を today_view から完全に除外する
        # ※ 未完了・次に見る候補・A/B表示の元データをここで整える
        # =====================================================
        if not ov_today.empty and not today_view.empty:
            cancel_df = ov_today[
                ov_today["action"].map(normalize_action_value) == "キャンセル"
            ].copy()


            if not cancel_df.empty:
                cancel_df["student_id_key"] = cancel_df["student_id"].astype(str).str.strip()
                cancel_df["slot_key"] = cancel_df["slot"].astype(str).str.strip().map(normalize_slot)


                cancel_keys = set(zip(cancel_df["student_id_key"], cancel_df["slot_key"]))


                today_view["student_id_key"] = today_view["student_id"].astype(str).str.strip()
                today_view["slot_key"] = today_view["slot"].astype(str).str.strip().map(normalize_slot)


                today_view = today_view[
                    ~today_view.apply(
                        lambda r: (
                            str(r.get("student_id_key", "")).strip(),
                            str(r.get("slot_key", "")).strip(),
                        ) in cancel_keys,
                        axis=1,
                    )
                ].copy()


                today_view = today_view.drop(columns=["student_id_key", "slot_key"], errors="ignore")

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
        if "display_name" not in today_view.columns:
            today_view["display_name"] = ""
        today_view["display_name"] = today_view["display_name"].fillna("").astype(str).str.strip()
        today_view["生徒"] = today_view["display_name"]

        
        today_view["検定目安"] = today_view["student_id"].astype(str).str.strip().map(
            lambda sid: colorize_kentei_hint(kentei_hint_map.get(sid, ""))
        )

        att_df_for_status = load_attendance_log().copy()
        prog_skip_df_for_status = load_progress_skip_ok().copy()


        curr_done_df = curr_prog[curr_prog.apply(is_progress_task_completed, axis=1)].copy()
        kentei_done_df = kentei_prog[kentei_prog.apply(is_progress_task_completed, axis=1)].copy()

        def get_today_attendance_kind(att_df: pd.DataFrame, student_id: str, d: date) -> str:
            if att_df is None or att_df.empty:
                return ""
            sid = str(student_id).strip()
            ds = str(d)


            tmp = att_df.copy()
            tmp["student_id"] = tmp["student_id"].astype(str).fillna("").str.strip()
            tmp["date"] = tmp["date"].astype(str).fillna("").str.strip()
            if "kind" not in tmp.columns:
                return ""
            tmp["kind"] = tmp["kind"].astype(str).fillna("").str.strip().str.lower()


            hit = tmp[(tmp["student_id"] == sid) & (tmp["date"] == ds)]
            if hit.empty:
                return ""
            return str(hit.iloc[-1]["kind"]).strip().lower()


        today_view["出欠完了"] = today_view["student_id"].apply(
            lambda sid: is_attendance_done_today(att_df_for_status, sid, today)
        )


        def calc_today_progress_done(sid: str) -> bool:
            actual_kind = get_today_attendance_kind(att_df_for_status, sid, today)


            # 授業以外は進捗不要
            if actual_kind in ["self", "selfstudy", "自習", "absence", "欠席", "cancel", "キャンセル"]:
                return True


            # 授業のときだけ進捗判定
            curr_done = is_progress_done_today(curr_done_df, sid, today)
            kentei_done = is_progress_done_today(kentei_done_df, sid, today)
            skip_done = is_progress_skip_ok_today(prog_skip_df_for_status, sid, today)


            return bool(curr_done or kentei_done or skip_done)


        today_view["進捗完了"] = today_view["student_id"].apply(calc_today_progress_done)


        today_view["状態"] = today_view.apply(
            lambda r: build_today_task_status(
                bool(r.get("出欠完了", False)),
                bool(r.get("進捗完了", False))
            ),
            axis=1
        )

        # =====================================================
        # 次に見る候補
        # =====================================================
        next_candidates = today_view.copy()


        # 表示名が空でも落ちないように保険
        if "display_name" not in next_candidates.columns:
            next_candidates["display_name"] = next_candidates["student_id"].astype(str)


        # 優先度
        # 0: 出欠済み & 進捗未
        # 1: 未着席
        # 2: それ以外
        def calc_priority(r):
            attended = bool(r.get("出欠完了", False))
            progressed = bool(r.get("進捗完了", False))
            if attended and not progressed:
                return 0
            elif not attended:
                return 1
            return 2


        next_candidates["priority"] = next_candidates.apply(calc_priority, axis=1)


        # 候補だけ残す
        next_candidates = next_candidates[next_candidates["priority"] < 2].copy()


        # 並び順
        if "slot_num" not in next_candidates.columns:
            next_candidates["slot_num"] = pd.to_numeric(next_candidates["slot"], errors="coerce")


        next_candidates = next_candidates.sort_values(
            by=["priority", "slot_num", "display_name"],
            na_position="last"
        )

        # 左フィルタ用に「次に見る候補」優先順を保存
        candidate_names = [
            str(x).strip()
            for x in next_candidates["display_name"].fillna("").astype(str).tolist()
            if str(x).strip()
        ]


        today_names = []
        if "display_name" in today_view.columns:
            tmp_today = today_view.copy()
            if "slot_num" in tmp_today.columns:
                tmp_today = tmp_today.sort_values(by=["slot_num", "display_name"], na_position="last")
            today_names = [
                str(x).strip()
                for x in tmp_today["display_name"].fillna("").astype(str).tolist()
                if str(x).strip()
            ]


        priority_order = []
        used_names = set()


        for name in candidate_names + today_names:
            if name and name not in used_names:
                priority_order.append(name)
                used_names.add(name)


        st.session_state["sidebar_student_priority_order"] = priority_order
        
        prev = st.session_state.get("_sidebar_priority_applied", [])

        if prev != priority_order:
            st.session_state["_sidebar_priority_applied"] = priority_order.copy()
            st.rerun()



        # =====================================================
        # 📅 今月回数一覧
        # =====================================================
        with st.expander("📅 今月回数一覧", expanded=False):



            attendance_count_map = {}


            att_df = load_attendance_log().copy()

            if not att_df.empty:
                if "date" in att_df.columns:
                    att_df["date_dt"] = pd.to_datetime(att_df["date"], errors="coerce")


                    today_dt = pd.Timestamp(dt.date.today())
                    att_df = att_df[
                        (att_df["date_dt"].dt.year == today_dt.year)
                        & (att_df["date_dt"].dt.month == today_dt.month)
                    ].copy()


                    if "status" in att_df.columns:
                        att_df = att_df[
                            att_df["status"].astype(str).str.strip() == "出席"
                        ].copy()


                    if "student_id" in att_df.columns:
                        attendance_count_map = (
                            att_df["student_id"].astype(str).str.strip()
                            .value_counts()
                            .to_dict()
                        )


            month_rows = []


            if not students.empty:
                students_for_month = students.copy()


                if "is_active" in students_for_month.columns:
                    students_for_month = students_for_month[
                        students_for_month["is_active"]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .replace("", "true")
                        .isin(["true", "1", "yes"])
                    ].copy()


                for _, r in students_for_month.iterrows():
                    sid = str(r.get("student_id", "")).strip()
                    name = str(r.get("display_name", "")).strip()
                    target = str(r.get("number_of_times", "")).strip()

                    current_count = attendance_count_map.get(sid, 0)

                    try:
                        target_num = int(float(target)) if target else 0
                    except Exception:
                        target_num = 0

                    if target_num <= 0:
                        diff_label = ""
                    elif current_count < target_num:
                        diff_label = f"あと{target_num - current_count}回"
                    elif current_count == target_num:
                        diff_label = "OK"
                    else:
                        diff_label = f"+{current_count - target_num}回"

                    month_rows.append({
                        "生徒": name,
                        "今月回数": f"{current_count} / {target}" if target else str(current_count),
                        "不足": diff_label,
                    })

            if month_rows:
                month_df = pd.DataFrame(month_rows)
                show_only_shortage = st.checkbox(
                    "不足がある生徒だけ表示",
                    value=False,
                    key="show_only_shortage_month_count",
                )

                if show_only_shortage:
                    month_df = month_df[
                        month_df["不足"].astype(str).str.startswith("あと")
                    ].copy()

                month_df = month_df.sort_values("生徒")

                st.dataframe(
                    month_df,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("表示できる生徒がいません。")

        st.subheader("👀 次に見る候補")


        if next_candidates.empty:
            st.caption("候補なし")
        else:
            for i, (_, r) in enumerate(next_candidates.head(5).iterrows(), start=1):
                name = str(r.get("display_name", "")).strip()
                sid = str(r.get("student_id", "")).strip()
                status = str(r.get("状態", "")).strip()
                slot = str(r.get("slot", "")).strip()

                if not name:
                    name = sid

                prep_df = load_prep_memo().copy()
                memo_row = prep_df[prep_df["student_id"].astype(str).str.strip() == sid]


                if not memo_row.empty:
                    memo = str(memo_row.iloc[0]["memo"]).strip()
                else:
                    memo = ""    


                st.write(f"{i}. {slot}限 / {name} / {status}")

                if memo:
                    st.caption(f"📝 {memo}")


            st.divider()

        # =====================================================
        # 次の準備メモ（簡易版）
        # =====================================================
        st.subheader("📝 次の準備メモ")
        prep_df = load_prep_memo().copy()


        # 今日の生徒候補
        prep_candidates = base_students.copy()
        if "display_name" not in prep_candidates.columns:
            prep_candidates["display_name"] = prep_candidates["student_id"].astype(str)


        prep_candidates["student_id"] = prep_candidates["student_id"].astype(str).str.strip()
        prep_candidates["display_name"] = prep_candidates["display_name"].astype(str).str.strip()
        prep_candidates["label"] = prep_candidates["student_id"] + "｜" + prep_candidates["display_name"]


        prep_labels = prep_candidates["label"].dropna().tolist()


        if prep_labels:
            c_p1, c_p2 = st.columns([3, 2])


            with c_p1:
                prep_label = st.selectbox(
                    "対象生徒",
                    prep_labels,
                    key="prep_target_student"
                )

            with c_p2:
                prep_text = st.text_input(
                    "内容",
                    placeholder="例）次はHTML課題3を準備",
                    key="prep_text_input"
                )


            c_p3, c_p4 = st.columns([1, 5])


            
            with c_p3:
                if st.button("追加", key="prep_add_btn"):
                    sid = prep_label.split("｜", 1)[0].strip()
                    txt = str(st.session_state.get("prep_text_input", "")).strip()
                    if txt:
                        prep_df2 = upsert_prep_memo(prep_df, sid, txt)
                        save_prep_memo(prep_df2)
                        st.rerun()


            with c_p4:
                st.caption("授業中に『あとで準備』と思ったことを一時メモできます")


            prep_map = dict(
                    zip(
                        prep_df["student_id"].astype(str).str.strip(),
                        prep_df["memo"].astype(str).str.strip()
                    )
                )



            if prep_map:
                st.markdown("**現在のメモ**")
                for _, r in prep_candidates.iterrows():
                    sid = str(r.get("student_id", "")).strip()
                    name = str(r.get("display_name", "")).strip() or sid
                    memo = prep_map.get(sid, "").strip()
                    if memo:
                        c_m1, c_m2 = st.columns([6, 1])
                        with c_m1:
                            st.write(f"- {sid}｜{name}：{memo}")
                        with c_m2:
                            if st.button("削除", key=f"prep_del_{sid}"):
                                prep_df2 = upsert_prep_memo(prep_df, sid, "")
                                save_prep_memo(prep_df2)
                                st.rerun()

            else:
                st.caption("メモなし")
        else:
            st.caption("今日の生徒がいないため、準備メモは表示されません。")


        st.divider()


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
        
        # 今日の予定に座席番号を表示する
        # seat_assignments.csv と today_view を date + slot + student_id で結合する
        today_view["席"] = ""


        if not seat_assignments.empty:
            seat_today = seat_assignments.copy()


            for c in ["date", "slot", "seat_no", "student_id"]:
                if c not in seat_today.columns:
                    seat_today[c] = ""


            # 今日の座席だけに絞る
            seat_today = seat_today[
                seat_today["date"].astype(str).str.strip() == today.strftime("%Y-%m-%d")
            ].copy()


            if not seat_today.empty:
                seat_today["student_id_key"] = seat_today["student_id"].astype(str).str.strip()
                seat_today["slot_key"] = seat_today["slot"].astype(str).str.strip().map(normalize_slot)
                seat_today["seat_no"] = seat_today["seat_no"].astype(str).str.strip()


                seat_today = seat_today[
                    ["student_id_key", "slot_key", "seat_no"]
                ].drop_duplicates(
                    subset=["student_id_key", "slot_key"],
                    keep="last"
                )


                today_view["student_id_key"] = today_view["student_id"].astype(str).str.strip()


                if "slot" in today_view.columns:
                    today_view["slot_key"] = today_view["slot"].astype(str).str.strip().map(normalize_slot)
                else:
                    today_view["slot_key"] = today_view["コマ"].astype(str).str.strip().map(normalize_slot)


                today_view = today_view.merge(
                    seat_today,
                    on=["student_id_key", "slot_key"],
                    how="left"
                )


                today_view["seat_no"] = today_view["seat_no"].fillna("").astype(str).str.strip()
                today_view["席"] = today_view["seat_no"].apply(lambda x: f"席{x}" if x else "")


                today_view = today_view.drop(columns=["student_id_key", "slot_key", "seat_no"], errors="ignore")

        

        # =====================================================
        # 🪑 今日の座席ミニ一覧
        # ※ seat_assignments.csv に保存済みの「今日の席」を直接表示する
        # ※ today_view["席"] が空でも、保存済み座席を確認できるようにする
        # =====================================================
        seat_mini_rows = []

        if not seat_assignments.empty:
            seat_mini_src = seat_assignments.copy()

            for c in ["date", "slot", "seat_no", "student_id", "note"]:
                if c not in seat_mini_src.columns:
                    seat_mini_src[c] = ""

            seat_mini_src = seat_mini_src[
                seat_mini_src["date"].astype(str).str.strip() == today.strftime("%Y-%m-%d")
            ].copy()

            if not seat_mini_src.empty:
                seat_mini_src["slot_norm"] = seat_mini_src["slot"].astype(str).str.strip().map(normalize_slot)
                seat_mini_src["seat_no"] = seat_mini_src["seat_no"].astype(str).str.strip()
                seat_mini_src["student_id"] = seat_mini_src["student_id"].astype(str).str.strip()
                seat_mini_src["note"] = seat_mini_src["note"].astype(str).str.strip()

                # 生徒名マップ
                if not students.empty and "student_id" in students.columns and "display_name" in students.columns:
                    _seat_name_map = dict(
                        zip(
                            students["student_id"].astype(str).str.strip(),
                            students["display_name"].astype(str).str.strip(),
                        )
                    )
                
                else:
                    _seat_name_map = {}

                # 今日の予定側の状態マップ（取れれば表示する）
                _today_status_map = {}
                if "student_id" in today_view.columns and "slot" in today_view.columns:
                    _tmp_tv = today_view.copy()
                    _tmp_tv["student_id"] = _tmp_tv["student_id"].astype(str).str.strip()
                    _tmp_tv["slot_norm"] = _tmp_tv["slot"].astype(str).str.strip().map(normalize_slot)
                    for _, _r in _tmp_tv.iterrows():
                        _key = (str(_r.get("student_id", "")).strip(), str(_r.get("slot_norm", "")).strip())
                        _today_status_map[_key] = str(_r.get("状態", "")).strip()

                for _, _r in seat_mini_src.iterrows():
                    _sid = str(_r.get("student_id", "")).strip()
                    _slot = str(_r.get("slot_norm", "")).strip()
                    _seat_no = str(_r.get("seat_no", "")).strip()
                    if not _sid or not _seat_no:
                        continue

                    seat_mini_rows.append({
                        "コマ": _slot,
                        "席": f"席{_seat_no}",
                        "生徒": _seat_name_map.get(_sid, _sid),
                        "状態": _today_status_map.get((_sid, _slot), ""),
                        "メモ": str(_r.get("note", "")).strip(),
                        "_slot_num": pd.to_numeric(_slot, errors="coerce"),
                        "_seat_num": pd.to_numeric(_seat_no, errors="coerce"),
                    })

        if seat_mini_rows:
            seat_mini = pd.DataFrame(seat_mini_rows)
            seat_mini = seat_mini.sort_values(by=["_slot_num", "_seat_num", "生徒"], na_position="last")

            st.subheader("🪑 今日の座席")
            show_mini_cols = ["コマ", "席", "生徒", "状態", "メモ"]
            show_mini_cols = [c for c in show_mini_cols if c in seat_mini.columns]
            st.dataframe(
                seat_mini[show_mini_cols],
                use_container_width=True,
                hide_index=True,
            )
            
        # =====================================================
        # ⚠ 今日の予定にいるが、座席未登録の生徒を警告
        # =====================================================
        seat_assigned_keys = set()


        if not seat_assignments.empty:
            _seat_check = seat_assignments.copy()


            for c in ["date", "slot", "student_id"]:
                if c not in _seat_check.columns:
                    _seat_check[c] = ""


            _seat_check = _seat_check[
                _seat_check["date"].astype(str).str.strip() == today.strftime("%Y-%m-%d")
            ].copy()


            if not _seat_check.empty:
                _seat_check["student_id"] = _seat_check["student_id"].astype(str).str.strip()
                _seat_check["slot_norm"] = _seat_check["slot"].astype(str).str.strip().map(normalize_slot)


                seat_assigned_keys = set(
                    zip(
                        _seat_check["student_id"],
                        _seat_check["slot_norm"],
                    )
                )

        # 今日キャンセル済みの予定は、座席未登録チェックから除外する
        seat_cancel_keys = set()


        if not schedule_overrides.empty:
            _ov_cancel = schedule_overrides.copy()


            for c in ["date", "slot", "student_id", "action"]:
                if c not in _ov_cancel.columns:
                    _ov_cancel[c] = ""


            _ov_cancel["date"] = _ov_cancel["date"].astype(str).str.strip()
            _ov_cancel["slot_norm"] = _ov_cancel["slot"].astype(str).str.strip().map(normalize_slot)
            _ov_cancel["student_id"] = _ov_cancel["student_id"].astype(str).str.strip()
            _ov_cancel["action_norm"] = _ov_cancel["action"].map(normalize_action_value)


            _ov_cancel = _ov_cancel[
                (_ov_cancel["date"] == today.strftime("%Y-%m-%d"))
                & (_ov_cancel["action_norm"] == "キャンセル")
            ].copy()


            seat_cancel_keys = set(
                zip(
                    _ov_cancel["student_id"],
                    _ov_cancel["slot_norm"],
                )
            )

        missing_seat_rows = []


        if not today_view.empty:
            _tv_seat_check = today_view.copy()


            if "student_id" in _tv_seat_check.columns and "slot" in _tv_seat_check.columns:
                _tv_seat_check["student_id"] = _tv_seat_check["student_id"].astype(str).str.strip()
                _tv_seat_check["slot_norm"] = _tv_seat_check["slot"].astype(str).str.strip().map(normalize_slot)


                for _, _r in _tv_seat_check.iterrows():
                    _sid = str(_r.get("student_id", "")).strip()
                    _slot = str(_r.get("slot_norm", "")).strip()

                    if not _sid:
                        continue

                    # キャンセル済みの予定は、座席未登録に出さない
                    if (_sid, _slot) in seat_cancel_keys:
                        continue
                    
                    if (_sid, _slot) not in seat_assigned_keys:
                        missing_seat_rows.append({
                            "コマ": _slot,
                            "生徒": str(_r.get("生徒", "")).strip(),
                            "状態": str(_r.get("状態", "")).strip(),
                        })

        if missing_seat_rows:
            missing_seat_df = pd.DataFrame(missing_seat_rows)
            missing_seat_df = missing_seat_df.drop_duplicates(subset=["コマ", "生徒"], keep="first")


            st.warning(f"⚠ 座席未登録の予定が {len(missing_seat_df)} 件あります。")
            st.dataframe(
                missing_seat_df,
                use_container_width=True,
                hide_index=True,
            )

        today_view["_pending_mark"] = ""
        today_view["_missing_mark"] = ""

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


        # =====================================================
        # ✅ 出席ログ（授業/自習）: 予定ではなく実績を記録
        #    → 作業完了管理寄り（未確認を先に表示）
        # =====================================================
        with st.expander("✅ 出席記録（授業/自習）", expanded=True):
            st.caption("来たタイミングで『記録』を押すだけ。確認済みは下に分かれます。")
            att_df = load_attendance_log()

            curr_prog_df = safe_read_csv(
                CURRICULUM_PROGRESS_CSV,
                required_cols=["student_id", "done_date"],
                stop_on_missing=False
            )
            curr_prog_df = sanitize_df(curr_prog_df)
            kentei_prog_df = safe_read_csv(
                KENTEI_PROGRESS_CSV,
                required_cols=["student_id", "done_date"],
                stop_on_missing=False
            )
            kentei_prog_df = sanitize_df(kentei_prog_df)

            prog_skip_df = load_progress_skip_ok().copy()
            
            prog_skip_today_ids = set()

            if not prog_skip_df.empty and {"student_id", "date"}.issubset(prog_skip_df.columns):
                prog_skip_today = prog_skip_df[
                    prog_skip_df["date"].astype(str).str.strip() == str(today)
                ].copy()

                prog_skip_today_ids = set(
                    prog_skip_today["student_id"].astype(str).str.strip().tolist()
                )

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

                # 今日の予定から、生徒ごとの予定種別を拾う
                # ルール:
                #   - 今日の予定に selfstudy が1件でもあれば selfstudy
                #   - それ以外は lesson
                planned_kind_map = {}
                if not today_view.empty and {"student_id", "session_type"}.issubset(today_view.columns):
                    tmp_tv = today_view[["student_id", "session_type"]].copy()
                    tmp_tv["student_id"] = tmp_tv["student_id"].fillna("").astype(str).str.strip()
                    tmp_tv["session_type"] = tmp_tv["session_type"].fillna("").astype(str).str.strip().str.lower()


                    for sid2, g in tmp_tv.groupby("student_id"):
                        vals = set(g["session_type"].tolist())
                        if "selfstudy" in vals or "自習" in vals:
                            planned_kind_map[sid2] = "selfstudy"
                        else:
                            planned_kind_map[sid2] = "lesson"

                # 今日の予定を「未確認」「確認済み」に分ける
                pending_ids = []
                done_ids = []
                rec_map = {}

                prog_today_ids = set()

                if not curr_prog_df.empty and {"student_id", "done_date"}.issubset(curr_prog_df.columns):
                    curr_prog_today = curr_prog_df[
                        curr_prog_df["done_date"].astype(str).str.strip() == str(today)
                    ].copy()


                    prog_today_ids.update(
                        curr_prog_today["student_id"].astype(str).str.strip().tolist()
                    )


                if not kentei_prog_df.empty and {"student_id", "done_date"}.issubset(kentei_prog_df.columns):
                    kentei_prog_today = kentei_prog_df[
                        kentei_prog_df["done_date"].astype(str).str.strip() == str(today)
                    ].copy()


                    prog_today_ids.update(
                        kentei_prog_today["student_id"].astype(str).str.strip().tolist()
                    )


                for sid in ids_in_today:
                    rec = get_attendance_today(att_df, sid, today)
                    rec_map[sid] = rec
                    if rec is None:
                        pending_ids.append(sid)
                    else:
                        done_ids.append(sid)
                
                
                if pending_ids:
                    st.markdown("### 🚨 最優先：出欠未登録")
                    st.error(f"{len(pending_ids)} 件あります")

                    for sid in pending_ids:
                        nm = name_map.get(sid, "")
                        label = f"{sid}｜{nm}" if nm else sid


                        st.write(f"・{label}")


                    st.caption("※ 下の『出席記録』で記録してください")

                missing_progress_ids = [
                    sid for sid in done_ids
                    if (sid not in prog_today_ids) and (sid not in prog_skip_today_ids)
                ]
                
                pending_count = len(pending_ids)
                missing_count = len(missing_progress_ids)
                unfinished_count = pending_count + missing_count
                
                if (not pending_ids) and (not missing_progress_ids):
                    st.success("🎉 未完了タスクはありません")
                else:
                    st.info(
                        f"未完了：{unfinished_count}件（出欠 {pending_count} / 要対応 {missing_count}）"
                    )

                pending_set = set(pending_ids)
                missing_set = set(missing_progress_ids)


                if "student_id" in today_view.columns:
                    today_view["_pending_mark"] = today_view["student_id"].astype(str).apply(
                        lambda sid: "❗出欠" if sid in pending_set else ""
                    )
                    today_view["_missing_mark"] = today_view["student_id"].astype(str).apply(
                        lambda sid: "❗要対応" if sid in missing_set else ""
                    )


                    today_view["生徒"] = today_view.apply(
                        lambda r: (
                            f"{str(r['生徒']).strip()} "
                            + " ".join([x for x in [r.get("_pending_mark", ""), r.get("_missing_mark", "")] if str(x).strip()])
                        ).strip(),
                        axis=1
                    )
                    
                    today_view.drop(columns=["_pending_mark", "_missing_mark"], errors="ignore", inplace=True)

                if missing_progress_ids:
                    st.markdown("### ⚠ 最優先：進捗未登録")
                    st.warning(f"{len(missing_progress_ids)} 件あります")

                    for sid in missing_progress_ids:
                        nm = name_map.get(sid, "")
                        label = f"{sid}｜{nm}" if nm else sid

                        if st.button(f"⚠ {label} を開く", key=f"jump_missing_{sid}"):
                            if nm:
                                st.session_state["pending_sidebar_student"] = nm
                                st.rerun()
                                
                show_done = st.checkbox("確認済み（取消で復活できる）を表示", value=False, key=f"att_show_done_{today}")
                                
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


                        # 初期値の優先順
                        # 1) 既存の出席記録
                        # 2) 今日の予定の種別（例外を含む）
                        # 3) lesson
                        default_kind = "lesson"


                        if rec_kind in ["selfstudy", "自習"]:
                            default_kind = "selfstudy"
                        elif sid in planned_kind_map:
                            default_kind = planned_kind_map[sid]



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
                            c1, c2, c3, c4, c5 = st.columns([3, 2, 3, 3, 2])


                            with c1:
                                prefix = "🟡 未確認" if rec is None else "✅ 確認済み"
                                kind_badge = "📘 授業" if default_kind == "lesson" else "🟡 自習"
                                st.markdown(f"**{prefix}｜{kind_badge}｜👤 {label}**")
                                st.caption(badge)

                               # 準備メモ表示
                                prep_df_card = load_prep_memo().copy()
                                sid_str = str(sid).strip()

                                memo_row = prep_df_card[
                                    prep_df_card["student_id"].astype(str).str.strip() == sid_str
                                ]

                                memo = ""
                                if not memo_row.empty:
                                    memo = str(memo_row.iloc[0]["memo"]).strip()

                                if memo:
                                    st.info(f"📝 次の準備：{memo}")



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
                                default_progress_index = 0
                                if session_type == "自習":
                                    default_progress_index = 1

                                no_progress_done = st.checkbox(
                                    "進捗なしで完了にする",key=f"no_progress_done_{d_str}_{sid}_{slot}_{i}"
                                )


                            with c5:
                                if st.button("✅ 記録/更新", key=f"att_save_{today}_{sid}"):
                                    att_df2 = upsert_attendance(att_df, sid, today, picked_kind, memo, count=count)
                                    save_attendance_log(att_df2)

                                    # 進捗状態を保存
                                    if no_progress_done:
                                        prog_skip_df2 = load_progress_skip_ok().copy()
                                        prog_skip_df2 = upsert_progress_skip_ok(
                                            prog_skip_df2,
                                            student_id=sid,
                                            d=today,
                                            note="出席記録画面から進捗なしで完了"
                                        )
                                        save_progress_skip_ok(prog_skip_df2)

                                    st.success("保存しました。")
                                    
                                    if nm:
                                        st.session_state["pending_sidebar_student"] = nm

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
        # =====================================================
        # 🚫 今日の予定からワンクリックでキャンセル
        # =====================================================
        with st.expander("🚫 今日の予定をキャンセル", expanded=False):
            st.caption("月2回の子など、今日は来ない予定をここからすぐキャンセルできます。")


            if today_view.empty:
                st.info("今日の予定がないため、キャンセル対象はありません。")
            else:
                cancel_src = today_view.copy()


                # 表示用に重複を抑える（同じ生徒×同じコマ）
                cancel_src["student_id"] = cancel_src["student_id"].astype(str).str.strip()
                cancel_src["slot"] = cancel_src["slot"].astype(str).str.strip()
                cancel_src["display_name"] = cancel_src["display_name"].fillna("").astype(str).str.strip()
                cancel_src = cancel_src.drop_duplicates(subset=["student_id", "slot"], keep="first").copy()


                # すでに今日 cancel 済みのものは除外
                ov_cancel_today = schedule_overrides.copy()
                if not ov_cancel_today.empty:
                    for c in ["student_id", "date", "slot", "action"]:
                        if c in ov_cancel_today.columns:
                            ov_cancel_today[c] = ov_cancel_today[c].fillna("").astype(str).str.strip()


                    ov_cancel_today = ov_cancel_today[
                        (ov_cancel_today["date"] == today.strftime("%Y-%m-%d"))
                        & (ov_cancel_today["action"].map(normalize_action_value) == "キャンセル")
                    ].copy()


                    canceled_keys = set(zip(
                        ov_cancel_today["student_id"].astype(str).str.strip(),
                        ov_cancel_today["slot"].astype(str).str.strip().map(normalize_slot),
                    ))
                else:
                    canceled_keys = set()


                cancel_src = cancel_src[
                    ~cancel_src.apply(
                        lambda r: (str(r.get("student_id", "")).strip(), normalize_slot(r.get("slot", ""))) in canceled_keys,
                        axis=1
                    )
                ].copy()


                if cancel_src.empty:
                    st.success("キャンセルできる予定はありません。")
                else:
                    for i, r in cancel_src.reset_index(drop=True).iterrows():
                        sid = str(r.get("student_id", "")).strip()
                        name = str(r.get("display_name", "")).strip()
                        slot = str(r.get("slot", "")).strip()
                        start = str(r.get("start", "")).strip()
                        end = str(r.get("end", "")).strip()


                        c1, c2, c3 = st.columns([4, 2, 2])


                        with c1:
                            label = f"{sid}｜{name}" if name else sid
                            time_label = f"{slot}コマ"
                            if start or end:
                                time_label += f"（{start}〜{end}）".strip("〜")
                            st.write(f"{label} / {time_label}")


                        with c2:
                            st.write(str(r.get("session_type", "")).strip() or "-")


                        with c3:
                            if st.button("キャンセル", key=f"quick_cancel_{today}_{sid}_{slot}_{i}"):
                                ov2 = schedule_overrides.copy()
                                if ov2.empty:
                                    ov2 = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"])
                                else:
                                    for c in ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]:
                                        if c not in ov2.columns:
                                            ov2[c] = ""
                                        ov2[c] = ov2[c].fillna("").astype(str).str.strip()


                                new_row = {
                                    "student_id": sid,
                                    "date": today.strftime("%Y-%m-%d"),
                                    "slot": slot,
                                    "action": "キャンセル",
                                    "start": "",
                                    "end": "",
                                    "session_type": "",
                                    "note": "今日の予定からワンクリックでキャンセル",
                                }


                                # 同じ student_id × date × slot × action は重複させない
                                keymask = (
                                    (ov2["student_id"] == new_row["student_id"])
                                    & (ov2["date"] == new_row["date"])
                                    & (ov2["slot"] == new_row["slot"])
                                    & (ov2["action"] == new_row["action"])
                                )
                                ov2 = ov2[~keymask].copy()
                                ov2 = pd.concat([ov2, pd.DataFrame([new_row])], ignore_index=True)
                                
                                # schedule_overrides.csv にキャンセルを保存
                                write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)


                                # キャンセルした生徒の「今日・そのコマ」の座席を空席にする
                                cancel_date = today.strftime("%Y-%m-%d")
                                cancel_student_id = str(sid).strip()
                                cancel_slot = str(slot).strip()


                                seat_assignments2 = seat_assignments.copy()


                                for c in ["date", "slot", "student_id"]:
                                    if c not in seat_assignments2.columns:
                                        seat_assignments2[c] = ""
                                    seat_assignments2[c] = seat_assignments2[c].fillna("").astype(str).str.strip()


                                seat_assignments2 = seat_assignments2[
                                    ~(
                                        (seat_assignments2["date"] == cancel_date)
                                        & (seat_assignments2["slot"].astype(str).str.strip().map(normalize_slot) == normalize_slot(cancel_slot))
                                        & (seat_assignments2["student_id"] == cancel_student_id)
                                    )
                                ].copy()


                                seat_assignments2 = seat_assignments2[SEAT_ASSIGNMENT_COLS].fillna("")
                                write_csv_atomic(seat_assignments2, SEAT_ASSIGNMENTS_CSV)


                                st.success("キャンセルしました。座席も空席にしました。")
                                st.rerun()


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
            
            active_ids = set(
                students[
                    students["is_active"].fillna("").astype(str).str.strip().str.lower().replace("", "true").isin(["true", "1", "yes"])
                ]["student_id"].astype(str).str.strip().tolist()
            )

            ids_in_today = [sid for sid in ids_in_today if sid in active_ids]

            if "student_id" in today_view.columns and not today_view.empty:
                for _sid in today_view["student_id"].astype(str).tolist():
                    _sid = str(_sid).strip()
                    if _sid and _sid not in ids_in_today:
                        ids_in_today.append(_sid)

            # 今日の予定にいない生徒は後ろ（表示名で安定ソート）
            rest_ids = [sid for sid in stu_for_pick["student_id"].tolist() if sid and sid not in ids_in_today]
            rest_ids_sorted = sorted(rest_ids, key=lambda s: str(stu_for_pick.loc[stu_for_pick["student_id"] == s, "display_name"].iloc[0] if (stu_for_pick["student_id"] == s).any() else s))

            ordered_ids = ids_in_today + rest_ids_sorted
            valid_ids = [sid for sid in ordered_ids if sid in stu_for_pick["student_id"].tolist()]
            stu_for_pick = stu_for_pick.set_index("student_id").loc[valid_ids].reset_index()

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

                # コマ番号ごとの表示名を作る（共通関数を使用）
                slot_label_map = build_slot_label_map(timeslots)


                # 今日の予定に start/end がある場合は、そちらを優先して上書き
                if not _stu_rows.empty and "slot" in _stu_rows.columns:
                    for _, _r in _stu_rows.iterrows():
                        _s_norm = normalize_slot(_r.get("slot", ""))
                        if not _s_norm:
                            continue
                        try:
                            _s_int = int(_s_normp)
                        except Exception:
                            continue


                        _start = str(_r.get("start", "") or "").strip()
                        _end = str(_r.get("end", "") or "").strip()
                        if _start or _end:
                            slot_label_map[_s_int] = f"{_s_int}｜{_start}〜{_end}".strip("〜")


                with c2:
                    picked_slot = st.selectbox(
                        "コマ番号",
                        slot_candidates,
                        index=_slot_index,
                        key="ov_slot",
                        format_func=lambda x: format_slot_label(x, slot_label_map)
                    )

                with c3:
                    action_options = ["キャンセル", "追加"]

                    picked_action = st.selectbox(
                        "種別",
                        action_options,
                        index=1,
                        key="override_action",
                    )

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
                ov_today_list["種別"] = ov_today_list["action"].apply(format_override_action)
                show_cols = ["label", "slot", "種別", "start", "end", "session_type", "note"]
                show_cols = [c for c in show_cols if c in ov_today_list.columns]
                st.dataframe(ov_today_list[show_cols], use_container_width=True, hide_index=True)

                st.caption("削除したい場合：下のボタンで“その行”を削除します。")
                for i, r in ov_today_list.reset_index(drop=True).iterrows():
                    sid = str(r.get("student_id","")).strip()
                    slot = str(r.get("slot","")).strip()
                    action = str(r.get("action","")).strip()
                    label = str(r.get("label","")).strip()
                    action_label = format_override_action(action)
                    btn = f"🗑 削除：{label} / slot {slot} / {action_label}"
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
        latest_filtered = latest_filtered[latest_filtered["display_name"] == selected_student_raw]
    if selected_curriculum != "（全て）":
        latest_filtered = latest_filtered[latest_filtered["curriculum"] == selected_curriculum]
    if selected_status != "（全て）":
        latest_filtered = latest_filtered[norm_lower(latest_filtered["status"]) == selected_status]
        
        
    # =========================================================
    # 表示切替（試験）
    # =========================================================
    sidebar_view_mode = st.radio(
        "表示切替（試験）",
        [
            "カリキュラム課題",
            "検定課題",
            "コース別（件数）",
            "Scratch検定一覧",
            "生徒ごと一覧",
            "生徒別（done）",
            "詳細（最新状態）",
        ],
        horizontal=True,
        key="view_mode_trial"
    )

    is_log_view = sidebar_view_mode in [
        "コース別（件数）",
        "Scratch検定一覧",
        "生徒ごと一覧",
        "生徒別（done）",
        "詳細（最新状態）",
    ]


    # =========================================================
    # Tabs
    # =========================================================
    #tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
       # ['生徒ごと一覧', '生徒別（done）', 'コース別（件数）', 'Scratch最高級', '詳細（最新状態）', 'カリキュラム課題', '検定課題']
    #   ['カリキュラム課題', '検定課題','コース別（件数）',  'Scratch検定一覧','生徒ごと一覧', '生徒別（done）', '詳細（最新状態）', ]
   # )
    if sidebar_view_mode == "カリキュラム課題":
        #with tab0:
        #カリキュラム課題
        st.subheader("✅ カリキュラム課題（進捗チェック）")

        st.caption("※ ここは『進捗チェック』です。課題そのものの登録/編集/削除は 管理（入力） → 📘 カリキュラム管理 で行います。")
        if st.button("📘 課題を登録・編集する（管理へ移動）", key="goto_admin_curr_from_view"):
            st.session_state["pending_page"] = "管理（入力）"
            st.rerun()

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
                    
                    course_done_mask = (
                        log["student_id"].astype(str).str.strip() == str(student_id).strip()
                    ) & (
                        log["curriculum"].astype(str).str.strip() == str(genre_id).strip()
                    ) & (
                        log["item"].astype(str).str.strip() == str(course_name).strip()
                    ) & (
                        log["status"].astype(str).str.strip() == "done"
                    )


                    is_course_done = bool(course_done_mask.any())


                    col_done1, col_done2 = st.columns([1, 2])

                    with col_done1:
                        if is_course_done:
                            st.success("✅ 完了済みです")
                            mark_done = False
                        else:
                            mark_done = st.checkbox(
                                "このカリキュラムを完了にする",
                                value=False,
                                key=f"mark_course_done_{student_id}_{selected_course_id}",
                            )

                    with col_done2:
                        if not is_course_done:
                            if st.button(
                                "完了を保存",
                                disabled=(not mark_done),
                                key=f"save_course_done_{student_id}_{selected_course_id}",
                            ):
                                # 保存処理

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
                    p = p[
                        (p["student_id"].astype(str).str.strip() == student_id)
                        & (p["course_id"].astype(str).str.strip() == str(selected_course_id).strip())
                    ].copy()


                    done_map = {
                        str(r["task_id"]).strip(): (str(r.get("is_done", "")).strip().lower() == "true")
                        for _, r in p.iterrows()
                    }
                    skip_map = {
                        str(r["task_id"]).strip(): (str(r.get("is_skip", "")).strip().lower() == "true")
                        for _, r in p.iterrows()
                    }
                    done_date_map = {
                        str(r["task_id"]).strip(): str(r.get("done_date", "")).strip()
                        for _, r in p.iterrows()
                        if str(r["student_id"]).strip() == str(student_id).strip()
                        and str(r["course_id"]).strip() == str(selected_course_id).strip()
                    }


                    st.markdown("### 課題一覧")
                    updated_rows = []

                    state_options = ["未実施", "完了", "スキップ"]

                    for _, row in t.iterrows():
                        task_id = str(row["task_id"]).strip()
                        task_name = str(row["task_name"]).strip()
                        was_done = bool(done_map.get(task_id, False))
                        was_skip = bool(skip_map.get(task_id, False))
                        prev_done_date = str(done_date_map.get(task_id, "")).strip()


                        if was_done:
                            default_state = "完了"
                        elif was_skip:
                            default_state = "スキップ"
                        else:
                            default_state = "未実施"


                        disabled = (was_done and is_locked_done_tasks)


                        selected_state = st.selectbox(
                            task_name,
                            state_options,
                            index=state_options.index(default_state),
                            key=f"curr_state_{student_id}_{selected_course_id}_{task_id}",
                            disabled=disabled,
                            format_func=status_label
                        )

                        updated_rows.append({
                            "student_id": student_id,
                            "course_id": str(selected_course_id).strip(),
                            "task_id": task_id,
                            "is_done": "true" if selected_state == "完了" else "false",
                            "is_skip": "true" if selected_state == "スキップ" else "false",
                            "done_date": (
                                dt.date.today().isoformat()
                                if selected_state in ["完了", "スキップ"] and default_state == "未実施"
                                else prev_done_date
                            ) if selected_state in ["完了", "スキップ"] else "",
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


                        if "is_skip" not in others.columns:
                            others["is_skip"] = "false"


                        save_df = pd.concat([others, new_df], ignore_index=True)
                        write_csv_atomic(save_df, CURRICULUM_PROGRESS_CSV)

                        st.success("保存しました。")
                        st.rerun()

                    if is_locked_done_tasks:
                        st.caption("※ 完了済みの課題は誤操作防止のためロックしています（右の⚠で解除できます）。")
    
    
    if sidebar_view_mode == "検定課題":
        #with tab1:
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

            done_map = {
                str(r["task_id"]).strip(): (str(r.get("is_done", "")).strip().lower() == "true")
                for _, r in prog.iterrows()
            }
            skip_map = {
                str(r["task_id"]).strip(): (str(r.get("is_skip", "")).strip().lower() == "true")
                for _, r in prog.iterrows()
            }
            done_date_map = {
                str(r["task_id"]).strip(): str(r.get("done_date", "")).strip()
                for _, r in prog.iterrows()
            }


            st.markdown("### 課題一覧")
            updated = []


            state_options = ["未実施", "完了", "スキップ"]


            for _, row in tasks.iterrows():
                task_id = str(row["task_id"]).strip()
                task_name = str(row["task_name"]).strip()
                was_done = bool(done_map.get(task_id, False))
                was_skip = bool(skip_map.get(task_id, False))
                prev_done_date = str(done_date_map.get(task_id, "")).strip()


                if was_done:
                    default_state = "完了"
                elif was_skip:
                    default_state = "スキップ"
                else:
                    default_state = "未実施"

                disabled = is_locked or (was_done and not override_done_lock)

                selected_state = st.selectbox(
                    task_name,
                    state_options,
                    index=state_options.index(default_state),
                    key=f"kentei_state_{student_id}_{grade_sel}_{task_id}",
                    disabled=disabled,
                    format_func=status_label
                )

                updated.append({
                    "student_id": student_id,
                    "grade": grade_sel,
                    "task_id": task_id,
                    "is_done": "true" if selected_state == "完了" else "false",
                    "is_skip": "true" if selected_state == "スキップ" else "false",
                    "done_date": (
                        dt.date.today().isoformat()
                        if selected_state in ["完了", "スキップ"] and default_state == "未実施"
                        else prev_done_date
                    ) if selected_state in ["完了", "スキップ"] else "",
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


                if "is_skip" not in others.columns:
                    others["is_skip"] = "false"


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
                if selected_student == "（全員）":
                    st.info("左のフィルタから、生徒を1人選んでください。")
                    st.stop()


                student_for_pass = str(student_id).strip()
                st.info(f"対象生徒: {student_for_pass}｜{selected_student}")

                st.markdown("### ✅ 新規登録")
                grade_for_pass = st.text_input("合格した級", value="", key="pass_new_grade")
                score_for_pass = st.text_input("点数（任意）", value="", key="pass_new_score")
                pass_date = st.date_input("受験日", value=date.today(), key="pass_new_date")
                pass_memo = st.text_area("メモ（任意）", value="", key="pass_new_memo")
                colA, colB = st.columns([1, 2])
                with colA:
                    if st.button("✅ 合格として登録", key="pass_add_btn"):


                        if grade_for_pass.strip() == "":
                            st.error("級を入力してください。")


                        else:
                            # 同じ生徒＋同じ級を削除（ここでやる）
                            results_df = results_df[
                                ~(
                                    (results_df["student_id"].astype(str).str.strip() == str(student_for_pass))
                                    &
                                    (results_df["grade"].astype(str).str.strip() == str(grade_for_pass))
                                )
                            ]


                            new_row = pd.DataFrame([{
                                "student_id": str(student_for_pass).strip(),
                                "grade": str(grade_for_pass).strip(),
                                "score": str(score_for_pass).strip(),
                                "pass_date": str(pass_date),
                                "memo": str(pass_memo).strip()
                            }])


                            results_df = pd.concat([results_df, new_row], ignore_index=True)


                            save_kentei_results(results_df)


                            st.success("合格登録しました")

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

                    picked_label = st.selectbox(
                        "修正したい行を選択",
                        df_s["_label"].tolist(),
                        key="pass_edit_pick"
                    )

                    row = df_s[df_s["_label"] == picked_label].iloc[0]

                    # 行ごとに一意なキーを作る
                    edit_key_base = (
                        f"{student_for_pass}_"
                        f"{str(row.get('grade', '')).strip()}_"
                        f"{str(row.get('pass_date', '')).strip()}_"
                        f"{row.name}"
                    )


                    try:
                        _d = pd.to_datetime(row.get("pass_date", ""), errors="coerce")
                        _d = _d.date() if pd.notna(_d) else date.today()
                    except Exception:
                        _d = date.today()


                    edit_grade = st.text_input(
                        "級（修正）",
                        value=str(row.get("grade", "")),
                        key=f"pass_edit_grade_{edit_key_base}"
                    )


                    edit_score = st.text_input(
                        "点数（修正）",
                        value=str(row.get("score", "")),
                        key=f"pass_edit_score_{edit_key_base}"
                    )


                    edit_date = st.date_input(
                        "受験日（修正）",
                        value=_d,
                        key=f"pass_edit_date_{edit_key_base}"
                    )


                    edit_memo = st.text_area(
                        "メモ（修正）",
                        value=str(row.get("memo", "")),
                        key=f"pass_edit_memo_{edit_key_base}"
                    )



                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if st.button("💾 修正を保存", key=f"pass_save_edit_{edit_key_base}"):
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
                                results_df.loc[i, "score"] = str(edit_score).strip()
                                results_df.loc[i, "pass_date"] = str(edit_date)
                                results_df.loc[i, "memo"] = str(edit_memo).strip()
                                save_kentei_results(results_df)
                                st.success("修正しました。")
                                st.rerun()

                    with col2:
                        undo_progress = st.checkbox(
                            "進捗のpassedも戻す",
                            value=False,
                            key=f"pass_del_undo_progress_{edit_key_base}"
                        )

                    with col3:
                        confirm = st.checkbox(
                            "削除してもOK（確認）",
                            value=False,
                            key=f"pass_del_confirm_{edit_key_base}"
                        )
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


    if sidebar_view_mode == "コース別（件数）":
        #with tab2:
        is_log_tab = True
        # コース別（件数）
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


            active_students["student_id"] = active_students["student_id"].astype(str).str.strip()
            active_students["display_name"] = active_students["display_name"].astype(str).str.strip()
            active_students["label"] = active_students["student_id"] + " | " + active_students["display_name"]


            labels = active_students["label"].tolist()
            label_to_id = dict(zip(labels, active_students["student_id"].tolist()))


            # 左フィルタで生徒が選ばれているときは、それを優先する
            if selected_student != "（全員）":
                student_row = active_students[active_students["display_name"] == str(selected_student).strip()].head(1)
                if student_row.empty:
                    st.info("左の生徒フィルタに該当する生徒が見つかりません。")
                    sid = None
                else:
                    sid = str(student_row.iloc[0]["student_id"]).strip()
                    st.caption(f"対象生徒：{sid} | {selected_student}")
            else:
                selected_label = st.selectbox("生徒を選択", labels, key="course_done_student")
                sid = label_to_id.get(selected_label)


            if sid:
                student_done = logs_df[
                    (logs_df["student_id"].astype(str).str.strip() == str(sid).strip()) &
                    (logs_df["status"].astype(str).str.strip() == "done")
                ].copy()


                student_done["curriculum"] = student_done["curriculum"].astype(str).str.strip()
                student_done["item"] = student_done["item"].astype(str).str.strip()


                done_set = set(zip(student_done["curriculum"], student_done["item"]))
                done_curriculum_set = set(student_done["curriculum"])


                cc = curr_courses.copy()
                if "course_order" in cc.columns:
                    cc["course_order_num"] = pd.to_numeric(cc["course_order"], errors="coerce").fillna(9999)
                else:
                    cc["course_order_num"] = 9999


                for (genre_id, genre_name), gdf in cc.groupby(["genre_id", "genre_name"], dropna=False):
                    gdf = gdf.sort_values(by=["course_order_num", "course_name"], kind="stable")
                    genre_id_str = str(genre_id).strip()


                    # ジャンル単位で done があれば、タイトルには○をつける
                    genre_has_done = genre_id_str in done_curriculum_set
                    genre_mark = "⭕️" if genre_has_done else ""
                    title = (
                        f"{genre_name} ({genre_id}) {genre_mark}"
                        if str(genre_name).strip() not in ["nan", "None", ""]
                        else f"{genre_id} {genre_mark}"
                    )


                    with st.expander(title, expanded=False):
                        single_course_genre = len(gdf) == 1


                        for _, row in gdf.iterrows():
                            course_name = str(row.get("course_name", "")).strip()


                            # 通常は curriculum + item 完全一致で判定
                            exact_done = (genre_id_str, course_name) in done_set


                            # HTML など単一コースのジャンルは、旧名称が混ざっていても
                            # curriculum が done なら ○ を出す
                            fallback_done = single_course_genre and (genre_id_str in done_curriculum_set)


                            mark = "⭕️" if (exact_done or fallback_done) else ""
                            st.write(f"- {course_name} {mark}")


    if sidebar_view_mode == "Scratch検定一覧":
    #with tab3:
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


        # Scratch検定専用画面
        is_log_tab = True
        st.subheader("Scratch検定一覧（生徒ごと）")

        # 級フィルタ
        grade_filter = st.selectbox(
            "級フィルタ",
            ["（全て）", "4級", "3級", "2級", "1級"],
            key="scratch_grade_filter"
        )


        if kentei_results.empty:
            st.info("Scratch検定ログがまだありません。")
        else:
            # 元データを整える
            score_src = kentei_results.copy()
            score_src["student_id"] = score_src["student_id"].fillna("").astype(str).str.strip()
            score_src["grade"] = score_src["grade"].fillna("").astype(str).str.strip()
            score_src["score_num"] = pd.to_numeric(score_src["score"], errors="coerce")


            # 4級 / 3級 / 2級 / 1級 の列を作る
            score_src["grade_col"] = score_src["grade"] + "級"


            score_pivot = (
                score_src.pivot_table(
                    index="student_id",
                    columns="grade_col",
                    values="score_num",
                    aggfunc="max"
                )
                .reset_index()
            )


            # 必要な列を必ず揃える
            for col in ["4級", "3級", "2級", "1級"]:
                if col not in score_pivot.columns:
                    score_pivot[col] = np.nan


            # 最高級
            if not scratch_best.empty:
                scratch_best_small = scratch_best[["student_id", "item"]].rename(columns={"item": "scratch_best"})
            else:
                scratch_best_small = pd.DataFrame(columns=["student_id", "scratch_best"])

            # 最高点
            best_score_small = (
                score_src.groupby("student_id", as_index=False)["score_num"]
                .max()
                .rename(columns={"score_num": "best_score"})
            )
            
            # ベースは students
            scratch_view = students.copy()
            scratch_view = scratch_view.merge(scratch_best_small, on="student_id", how="left")
            scratch_view = scratch_view.merge(score_pivot, on="student_id", how="left")
            scratch_view = scratch_view.merge(best_score_small, on="student_id", how="left")
            scratch_view["次の判断"] = scratch_view["best_score"].apply(judge_next_step)
            scratch_view["次の級"] = scratch_view["scratch_best"].apply(get_next_grade)

            # Scratch検定が1件もない生徒は除外
            scratch_view = scratch_view[
                scratch_view["scratch_best"].notna()
                | scratch_view["4級"].notna()
                | scratch_view["3級"].notna()
                | scratch_view["2級"].notna()
                | scratch_view["1級"].notna()
            ].copy()


            # フィルタ反映
            if selected_grade != "（全て）":
                scratch_view = scratch_view[scratch_view["grade"] == selected_grade]

            if selected_student != "（全員）":
                scratch_view = scratch_view[scratch_view["display_name"] == selected_student]

            if show_today_only:
                scratch_view = scratch_view[
                    scratch_view["student_id"].astype(str).isin(today_ids)
                ]


        # 級フィルタ適用
            if grade_filter != "（全て）":

                # その級の点数が入っている生徒だけ残す
                scratch_view = scratch_view[scratch_view[grade_filter].notna()].copy()

                # 点数でソート（高い順）
                scratch_view = scratch_view.sort_values(
                    by=grade_filter,
                    ascending=False,
                    na_position="last"
                )

            if scratch_view.empty:
                st.info("該当するScratch検定データがありません。")
            else:
                scratch_view["scratch_best"] = scratch_view["scratch_best"].fillna("—")

                # ソート用に数値コピー
                for col in ["4級", "3級", "2級", "1級"]:
                    scratch_view[col] = pd.to_numeric(scratch_view[col], errors="coerce")

                for col in ["4級", "3級", "2級", "1級", "best_score"]:
                    scratch_view[col] = scratch_view[col].apply(
                        lambda x: "—" if pd.isna(x) else str(int(x)) if float(x).is_integer() else str(x)
                    )


                show_cols = ["grade", "display_name", "4級", "3級", "2級", "1級", "scratch_best", "best_score", "次の判断","次の級"]

                st.dataframe(
                    scratch_view.sort_values(by=["grade", "display_name"], na_position="last")[show_cols],
                    use_container_width=True,
                    hide_index=True
                )


    if sidebar_view_mode == "生徒ごと一覧":
        #with tab4:

        is_log_tab = True
        #生徒ごと一覧
        st.subheader("生徒一覧：Scratch検定取得級＋月回数＋完了数（全コース合計）")

        done_counts = log_done.groupby("student_id").size().reset_index(name="done_total")
        if not kentei_results.empty:
            best_score_small = (
                kentei_results[["student_id", "score"]]
                .copy()
            )
            best_score_small["student_id"] = best_score_small["student_id"].fillna("").astype(str).str.strip()
            best_score_small["score_num"] = pd.to_numeric(best_score_small["score"], errors="coerce")
            best_score_small = (
                best_score_small.sort_values(by=["student_id", "score_num"], ascending=[True, False])
                .drop_duplicates(subset=["student_id"], keep="first")
                [["student_id", "score_num"]]
                .rename(columns={"score_num": "best_score"})
            )
        else:
            best_score_small = pd.DataFrame(columns=["student_id", "best_score"])


        if not scratch_best.empty:
            scratch_best_small = scratch_best[["student_id", "item"]].rename(columns={"item": "scratch_best"})
        else:
            scratch_best_small = pd.DataFrame(columns=["student_id", "scratch_best"])

        summary = students.copy()
        summary = summary.merge(done_counts, on="student_id", how="left")
        summary = summary.merge(scratch_best_small, on="student_id", how="left")
        summary = summary.merge(best_score_small, on="student_id", how="left")

        summary["done_total"] = summary["done_total"].fillna(0).astype(int)
        summary["scratch_best"] = summary["scratch_best"].fillna("—")
        summary["best_score"] = summary["best_score"].fillna("—")

        # Apply grade/student filters
        if selected_grade != "（全て）":
            summary = summary[summary["grade"] == selected_grade]
        if selected_student != "（全員）":
            summary = summary[summary["display_name"] == selected_student]

            show_cols = ["grade", "display_name", "number_of_times", "scratch_best", "best_score", "done_total"]
            summary_show = summary.sort_values(by=["join_date", "display_name"], na_position="last")[show_cols]
            st.dataframe(summary_show, use_container_width=True, hide_index=True)
            st.caption("done_total は progress_log.csv の status=done の行数（全コース合計）です。")

        if show_today_only:
                summary = summary[
                    summary["student_id"].astype(str).isin(today_ids)
                ]


    if sidebar_view_mode == "生徒別（done）":
        #with tab5:

        is_log_tab = True
        #生徒別（done）
        st.subheader("生徒別：完了したもの（done）")
        cols = ["date", "grade", "display_name", "curriculum", "item", "note"]
        cols = [c for c in cols if c in filtered_done.columns]
        done_view = filtered_done.copy()
        if show_today_only and "student_id" in done_view.columns:
            done_view = done_view[done_view["student_id"].astype(str).str.strip().isin(today_student_ids)].copy()



        show = done_view[cols].sort_values(by=["grade", "display_name", "date", "curriculum", "item"])
        st.dataframe(show, use_container_width=True, hide_index=True)

    if sidebar_view_mode == "詳細（最新状態）":
        #with tab6:
        is_log_tab = True
        #詳細（最新状態）
        st.subheader("項目ごとの最新状態（フィルタ反映）")
        cols = ["date", "grade", "display_name", "curriculum", "item", "status", "note"]
        cols = [c for c in cols if c in latest_filtered.columns]
        latest_view = latest_filtered.copy()
        if show_today_only and "student_id" in latest_view.columns:
            latest_view = latest_view[latest_view["student_id"].astype(str).str.strip().isin(today_student_ids)].copy()



        st.dataframe(
            latest_view[cols].sort_values(by=["grade", "display_name", "curriculum", "item"]),
            use_container_width=True,
            hide_index=True,
        )

        st.caption("※ 同じ項目が複数回ログにあっても、最後の状態だけ表示します。")

elif page == "管理（入力）":
    # 管理画面中は、左サイドバーの閲覧フィルタを無効化
    st.sidebar.header("管理")
    admin_include_inactive = st.sidebar.checkbox(
        "生徒候補に退会済みも含める",
        value=False,
        key="admin_include_inactive",
    )
    admin_students_for_pick = students.copy()


    if (not admin_include_inactive) and ("is_active" in admin_students_for_pick.columns):
        admin_students_for_pick = admin_students_for_pick[
            admin_students_for_pick["is_active"].fillna("").astype(str).str.strip().str.lower().replace("", "true").isin(["true", "1", "yes"])
        ].copy()

    override_passed_lock = st.session_state.get("override_passed_lock", False)  # (v6.5.5) 2重生成防止

    # NOTE: 閲覧側の sidebar checkbox(key="override_done_lock") とは別keyで表示する。
    # widget key を後から直接書き換えると StreamlitAPIException になるため、
    # 管理画面内のみで使用（カリキュラム管理用）
    
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
            slot_label_map = build_slot_label_map(timeslots)


            new_slot_sel = st.selectbox(
                "コマ（任意）",
                options=slot_options,
                index=0,
                key="stu_add_slot_sel",
                format_func=lambda x: "その他（自由入力）" if str(x) == "その他（自由入力）" else format_slot_label(x, slot_label_map)
            )


            new_slot_free = ""
            if new_slot_sel == "その他（自由入力）":
                new_slot_free = st.text_input("コマ（自由入力）", value="", key="stu_add_slot_free")


            new_slot = new_slot_free if new_slot_sel == "その他（自由入力）" else normalize_slot(new_slot_sel)


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
            students_view = admin_students_for_pick.copy()
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
                st.session_state["stu_edit_active"] = str(cur.get("is_active", "")).strip().lower() in ["true", "1", "yes"]

                # 曜日・コマ
                st.session_state["stu_edit_weekday"] = str(cur.get("weekday", "") or "")
                st.session_state["stu_edit_memo"] = ui_str(cur.get("memo", ""))
                cur_slot_tmp = normalize_slot(cur.get("slot", ""))
                st.session_state["stu_edit_slot_sel"] = cur_slot_tmp if cur_slot_tmp else ""
                st.session_state["stu_edit_slot_free"] = cur_slot_tmp if cur_slot_tmp else ""

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
            e_active = st.checkbox("在籍中（ON=在籍 / OFF=退会）", value=str(cur.get("is_active", "")).strip().lower() in ["true", "1", "yes"], key="stu_edit_active")

            e_weekday = st.text_input("曜日（任意）", value=str(cur.get("weekday", "")), key="stu_edit_weekday")
            e_memo = st.text_area("メモ（補足）", value=ui_str(cur.get("memo", "")), key="stu_edit_memo")

            # コマ：リスト＋自由入力（追加時と同じ形式）
            cur_slot = normalize_slot(cur.get("slot", ""))
            if cur_slot and cur_slot not in slot_options and cur_slot != "その他（自由入力）":
                slot_options = slot_options[:-1] + [cur_slot] + [slot_options[-1]]


            try:
                default_slot_index = slot_options.index(cur_slot) if cur_slot in slot_options else 0
            except Exception:
                default_slot_index = 0

            slot_label_map = build_slot_label_map(slots_base)

            e_slot_sel = st.selectbox(
                "コマ（任意）",
                options=slot_options,
                index=default_slot_index,
                key="stu_edit_slot_sel",
                format_func=lambda x: "その他（自由入力）" if str(x) == "その他（自由入力）" else format_slot_label(x, slot_label_map)
            )


            e_slot_free = ""
            if e_slot_sel == "その他（自由入力）":
                e_slot_free = st.text_input("コマ（自由入力）", value=cur_slot, key="stu_edit_slot_free")


            e_slot = e_slot_free if e_slot_sel == "その他（自由入力）" else normalize_slot(e_slot_sel)


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

        students_w = admin_students_for_pick.copy()
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
            # コマ：リスト＋自由入力（統一フォーマット）
            cur_slot = normalize_slot("")
            fs_slot_options = slot_options.copy()


            slot_label_map = build_slot_label_map(timeslots)


            fs_slot_sel = st.selectbox(
                "コマ",
                options=fs_slot_options,
                index=0,
                key="fs_slot_sel",
                format_func=lambda x: "その他（自由入力）" if str(x) == "その他（自由入力）" else format_slot_label(x, slot_label_map)
            )


            fs_slot_free = ""
            if fs_slot_sel == "その他（自由入力）":
                fs_slot_free = st.text_input("コマ（自由入力）", value="", key="fs_slot_free")


            slot_in = fs_slot_free if fs_slot_sel == "その他（自由入力）" else normalize_slot(fs_slot_sel)
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
        
        students_k = admin_students_for_pick.copy()
        students_k["label"] = students_k["student_id"].astype(str) + " | " + students_k["display_name"].astype(str)

        ks = safe_read_csv(KENTEI_EXAM_SCHEDULE_CSV, required_cols=["date", "student_id", "kentei", "grade", "note"], stop_on_missing=False)  # noqa: F821
        if ks.empty:
            ks = pd.DataFrame(columns=["date", "student_id", "kentei", "grade", "note"])
        if "pending_kentei_student" in st.session_state:
            st.session_state["kentei_student"] = st.session_state.pop("pending_kentei_student")
            
        if "pending_kentei_date" in st.session_state:
            st.session_state["kentei_date"] = st.session_state.pop("pending_kentei_date")


        if "pending_kentei_name" in st.session_state:
            st.session_state["kentei_name"] = st.session_state.pop("pending_kentei_name")


        if "pending_kentei_grade_input" in st.session_state:
            st.session_state["kentei_grade_input"] = st.session_state.pop("pending_kentei_grade_input")


        if "pending_kentei_note" in st.session_state:
            st.session_state["kentei_note"] = st.session_state.pop("pending_kentei_note")
        k_date = st.date_input("日付", value=date.today(), key="kentei_date")  # noqa: F821
        k_student = st.selectbox("生徒", students_k["label"].tolist(), key="kentei_student")
        k_student_id = k_student.split("|")[0].strip()
        k_name = st.text_input("検定名（例: プログラミング検定）", value="プログラミング検定", key="kentei_name")
        k_grade = st.text_input("級（例: 4 / 3 / 2）", value="", key="kentei_grade_input")
        k_note = st.text_input("メモ（任意）", value="", key="kentei_note")

        st.markdown("#### 編集 / 削除する予定を選ぶ")
        show_past_kentei = st.checkbox("過去のデータも表示", value=False, key="show_past_kentei")
        ks_edit_base = ks.copy()

        if "exam_date" in ks_edit_base.columns:
            ks_edit_base["exam_date"] = pd.to_datetime(ks_edit_base["exam_date"], errors="coerce")
        if "date" in ks_edit_base.columns:
            ks_edit_base["date"] = pd.to_datetime(ks_edit_base["date"], errors="coerce")

        today_ts = pd.Timestamp(date.today())

        if not show_past_kentei and "exam_date" in ks_edit_base.columns:
            ks_edit_base = ks_edit_base[
                ks_edit_base["exam_date"].notna() & (ks_edit_base["exam_date"] >= today_ts)
            ].copy()

        sort_col = "exam_date" if "exam_date" in ks_edit_base.columns else "date"
        ks_edit_base = ks_edit_base.sort_values(sort_col, na_position="last").tail(20).copy()


        name_map_k = dict(
            zip(
                students_k["student_id"].astype(str).str.strip(),
                students_k["display_name"].astype(str).str.strip()
            )
        )
        ks_edit_base["display_name"] = ks_edit_base["student_id"].astype(str).str.strip().map(name_map_k).fillna("")


        ks_edit_base["edit_label"] = ks_edit_base.apply(
            lambda r: (
                f"{str(r.get('exam_date', '')).split(' ')[0]} | "
                f"{str(r.get('student_id', '')).strip()} | "
                f"{str(r.get('display_name', '')).strip()} | "
                f"{str(r.get('exam_type', r.get('kentei', ''))).strip()} | "
                f"{str(r.get('grade', '')).strip()}"
            ),
            axis=1
        )


        edit_options = ["（新規のまま）"] + ks_edit_base["edit_label"].tolist()
        selected_edit_label = st.selectbox("編集対象", edit_options, key="kentei_edit_target")
        
        last_edit_label = st.session_state.get("kentei_edit_last_label")

        selected_edit_row = None


        if selected_edit_label != "（新規のまま）":
            selected_edit_row = ks_edit_base.loc[ks_edit_base["edit_label"] == selected_edit_label].iloc[0]


        if selected_edit_label != "（新規のまま）" and selected_edit_label != last_edit_label:
            st.session_state["kentei_edit_last_label"] = selected_edit_label


            try:
                selected_date = pd.to_datetime(selected_edit_row.get("exam_date", ""), errors="coerce")
                if pd.notna(selected_date):
                    st.session_state["pending_kentei_date"] = selected_date.date()
            except Exception:
                pass


            selected_sid = str(selected_edit_row.get("student_id", "")).strip()
            selected_name = name_map_k.get(selected_sid, "")
            selected_label = f"{selected_sid} | {selected_name}" if selected_name else selected_sid
            if selected_label in students_k["label"].tolist():
                st.session_state["pending_kentei_student"] = selected_label


            st.session_state["pending_kentei_name"] = str(
                selected_edit_row.get("exam_type", selected_edit_row.get("kentei", ""))
            ).strip()
            st.session_state["pending_kentei_grade_input"] = str(selected_edit_row.get("grade", "")).strip()
            st.session_state["pending_kentei_note"] = ui_str(selected_edit_row.get("note", ""))

            st.rerun()


        save_label = "保存（新規追加）" if selected_edit_label == "（新規のまま）" else "保存（上書き）"
        if st.button(save_label, key="kentei_save_btn"):
            new_row = {
                "student_id": k_student_id,
                "exam_type": str(k_name).strip(),
                "grade": str(k_grade).strip(),
                "exam_date": str(k_date),
                "note": str(k_note).strip(),
                "date": str(date.today()),
                "kentei": str(k_name).strip(),
            }

            if selected_edit_label == "（新規のまま）":
                ks = pd.concat([ks, pd.DataFrame([new_row])], ignore_index=True)
            else:
                edit_idx = int(selected_edit_row.name)
                for col, val in new_row.items():
                    ks.loc[edit_idx, col] = val

            # 列順を固定（崩れ防止）
            cols = ["student_id","exam_type","grade","exam_date","note","date","kentei"]
            ks = ks.reindex(columns=cols)

            write_csv(ks, KENTEI_EXAM_SCHEDULE_CSV)
            st.success("保存しました。")

        st.divider()
        st.caption("登録済み（直近）")

        if not ks.empty:
            ks_view = ks.copy()


            # 表示用の日付列をそろえる
            if "exam_date" in ks_view.columns:
                ks_view["exam_date"] = pd.to_datetime(ks_view["exam_date"], errors="coerce")
            if "date" in ks_view.columns:
                ks_view["date"] = pd.to_datetime(ks_view["date"], errors="coerce")


            # 直近20件だけ表示
            sort_col = "exam_date" if "exam_date" in ks_view.columns else "date"
            ks_view = ks_view.sort_values(sort_col, na_position="last").tail(20).copy()


            # 表示名を作る
            name_map_k = dict(
                zip(
                    students_k["student_id"].astype(str).str.strip(),
                    students_k["display_name"].astype(str).str.strip()
                )
            )
            ks_view["display_name"] = ks_view["student_id"].astype(str).str.strip().map(name_map_k).fillna("")


            # 一覧表示
            show_cols = [c for c in ["exam_date", "student_id", "display_name", "exam_type", "grade", "note"] if c in ks_view.columns]
            st.dataframe(ks_view[show_cols], use_container_width=True, hide_index=True)


            st.caption("削除したい予定のボタンを押してください（即反映）")


            for i, r in ks_view.reset_index().iterrows():
                row_index = int(r["index"])


                sid = str(r.get("student_id", "")).strip()
                nm = str(r.get("display_name", "")).strip()
                exam_type = str(r.get("exam_type", r.get("kentei", ""))).strip()
                grade = str(r.get("grade", "")).strip()
                exam_date = str(r.get("exam_date", "")).strip()


                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])
                with c1:
                    st.write(exam_date or "-")
                with c2:
                    st.write(f"{sid} | {nm}" if nm else sid)
                with c3:
                    st.write(exam_type or "-")
                with c4:
                    st.write(grade or "-")
                with c5:
                    if st.button("この予定を削除", key=f"kentei_del_{row_index}"):
                        ks2 = ks.drop(index=row_index).reset_index(drop=True)


                        cols = ["student_id", "exam_type", "grade", "exam_date", "note", "date", "kentei"]
                        ks2 = ks2.reindex(columns=cols)


                        write_csv(ks2, KENTEI_EXAM_SCHEDULE_CSV)
                        st.success("削除しました。")
                        st.rerun()


        # ---------------------------
        # 📘 カリキュラム管理（追加・編集・削除）
        #   - curriculum_courses.csv
        #   - curriculum_tasks.csv
        # ---------------------------
    with sub_curr:
        st.subheader("📘 カリキュラム / 課題 管理")
        st.caption("カリキュラム（コース）と課題（タスク）を、CSVを直接触らずにUIから編集できます。保存時に自動バックアップも作ります。")
        
        override_done_lock = st.checkbox(
            "⚠ 完了済み課題を編集する（通常はOFF）",
            key="override_done_lock_admin",
            value=st.session_state.get("override_done_lock_admin", False),
        )
        st.caption("※ 完了済み課題を一時的に編集したい時だけONにしてください")

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
          #  show_message=True,
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

                # 選択したコースに合わせて編集フォームを同期
                last_course_id = st.session_state.get("c_edit_last_id")
                if last_course_id != sel_id:
                    st.session_state["c_edit_last_id"] = sel_id


                    st.session_state["c_edit_genre_id"] = str(cur.get("genre_id", "") or "")
                    st.session_state["c_edit_genre_name"] = str(cur.get("genre_name", "") or "")
                    st.session_state["c_edit_course_name"] = str(cur.get("course_name", "") or "")


                    try:
                        st.session_state["c_edit_course_order"] = int(float(cur.get("course_order", 0) or 0))
                    except Exception:
                        st.session_state["c_edit_course_order"] = 0


                    st.session_state["c_edit_is_active"] = normalize_bool_str(cur.get("is_active", True))
                    st.rerun()


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
                             #   show_message=False,
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
         #   show_message=True,
        )
        if tasks.empty:
            tasks = pd.DataFrame(columns=["course_id","task_id","task_name","order","is_active","student_id"])

        # course choices
        course_ids = []
        if not courses.empty:
            course_ids = sorted(courses["course_id"].astype(str).str.strip().unique().tolist())
        
        task_course = st.session_state.get("t_course_filter", "（全て）")


        tasks_view = tasks.copy()
        if task_course != "（全て）":
            tasks_view = tasks_view[
                tasks_view["course_id"].astype(str).str.strip() == task_course
            ].copy()

        if "order" in tasks_view.columns:
            tasks_view["order_num"] = pd.to_numeric(tasks_view["order"], errors="coerce").fillna(9999).astype(int)
            tasks_view = tasks_view.sort_values(["course_id", "order_num", "task_id"], na_position="last").drop(columns=["order_num"])


        st.dataframe(tasks_view, use_container_width=True, hide_index=True)


        st.selectbox(
            "編集対象のコースで絞り込み",
            ["（全て）"] + course_ids,
            key="t_course_filter"
        )



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
                    # 選択した課題に合わせて編集フォームを同期
                    last_task_id = st.session_state.get("t_edit_last_id")
                    if last_task_id != sel_tid:
                        st.session_state["t_edit_last_id"] = sel_tid

                        st.session_state["t_edit_course_id"] = str(cur_t.get("course_id", "") or "")
                        st.session_state["t_edit_task_name"] = str(cur_t.get("task_name", "") or "")

                        try:
                            st.session_state["t_edit_order"] = int(float(cur_t.get("order", 0) or 0))
                        except Exception:
                            st.session_state["t_edit_order"] = 0


                        st.session_state["t_edit_is_active"] = normalize_bool_str(cur_t.get("is_active", True))
                        raw_sid = cur_t.get("student_id", "")
                        if pd.isna(raw_sid):
                            raw_sid = ""
                        st.session_state["t_edit_student_id"] = str(raw_sid).strip()

                        st.rerun()

                    cur_course = str(cur_t.get("course_id","")).strip()
                    edit_course_options = course_ids if course_ids else [cur_course]
                    if "t_edit_course_id" in st.session_state and st.session_state["t_edit_course_id"] in edit_course_options:
                        course_index = edit_course_options.index(st.session_state["t_edit_course_id"])
                    else:
                        course_index = edit_course_options.index(cur_course) if cur_course in edit_course_options else 0


                    e_course_id = st.selectbox("course_id（変更可）", edit_course_options, index=course_index, key="t_edit_course_id")

                    e_task_name = st.text_input("task_name", value=str(cur_t.get("task_name","")), key="t_edit_task_name")
                    try:
                        default_t_order = int(float(cur_t.get("order", 0) or 0))
                    except Exception:
                        default_t_order = 0
                    e_order = st.number_input("order（並び順）", min_value=0, value=default_t_order, step=1, key="t_edit_order")
                    e_is_active = st.checkbox("is_active（ON=表示）", value=normalize_bool_str(cur_t.get("is_active", True)), key="t_edit_is_active")
                    raw_sid = cur_t.get("student_id", "")
                    if pd.isna(raw_sid):
                        raw_sid = ""


                    raw_sid = cur_t.get("student_id", "")
                    if pd.isna(raw_sid):
                        raw_sid = ""


                    e_student_id = st.text_input(
                        "student_id（空=共通 / 入れる=個別課題）",
                        value=str(raw_sid).strip(),
                        key="t_edit_student_id"
                    )


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
            #    show_message=False,
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

            students2 = safe_read_csv(STUDENTS_CSV, ["student_id", "display_name"])
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
               # コマ：リスト＋自由入力
                ss_slot_label_map = build_slot_label_map(timeslots)
                ss_slot_options = [str(k) for k in sorted(ss_slot_label_map.keys())] + ["その他（自由入力）"]


                add_slot_sel = st.selectbox(
                    "コマ（数字）",
                    options=ss_slot_options,
                    index=0,
                    key="ss_add_slot_sel",
                    format_func=lambda x: "その他（自由入力）" if str(x) == "その他（自由入力）" else format_slot_label(x, ss_slot_label_map)
                )


                add_slot_free = ""
                if add_slot_sel == "その他（自由入力）":
                    add_slot_free = st.text_input("コマ（自由入力）", value="", key="ss_add_slot_free")


                add_slot = add_slot_free if add_slot_sel == "その他（自由入力）" else normalize_slot(add_slot_sel)

                add_sess = st.selectbox("種類（session_type）", sess_type_opts, key="ss_add_sess")
                add_note = st.text_input("メモ（任意）", value="", key="ss_add_note")

                if st.button("追加", key="ss_add_btn"):
                    # 重複（同一 生徒×曜日×コマ）を防ぐ
                    dup = (
                        (sched["student_id"].astype(str).str.strip() == add_student_id)
                        & (sched["weekday"].astype(str).str.strip() == str(add_weekday).strip())
                        & (sched["slot"].astype(str).str.strip().map(normalize_slot) == normalize_slot(add_slot))
                    )
                    if dup.any():
                        st.error("同じ（生徒×曜日×コマ）の行が既にあります。編集を使ってください。")
                    else:
                        new_row = {
                            "student_id": add_student_id,
                            "weekday": str(add_weekday).strip(),
                            "slot": normalize_slot(add_slot),  
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
                    # コマ：リスト＋自由入力
                    cur_slot = normalize_slot(row.get("slot", ""))
                    ss_edit_slot_label_map = build_slot_label_map(timeslots)
                    ss_edit_slot_options = [str(k) for k in sorted(ss_edit_slot_label_map.keys())] + ["その他（自由入力）"]


                    if cur_slot and cur_slot not in ss_edit_slot_options and cur_slot != "その他（自由入力）":
                        ss_edit_slot_options = ss_edit_slot_options[:-1] + [cur_slot] + [ss_edit_slot_options[-1]]


                    try:
                        ss_edit_slot_index = ss_edit_slot_options.index(cur_slot) if cur_slot in ss_edit_slot_options else 0
                    except Exception:
                        ss_edit_slot_index = 0


                    e_slot_sel = st.selectbox(
                        "コマ",
                        options=ss_edit_slot_options,
                        index=ss_edit_slot_index,
                        key="ss_edit_slot_sel",
                        format_func=lambda x: "その他（自由入力）" if str(x) == "その他（自由入力）" else format_slot_label(x, ss_edit_slot_label_map)
                    )


                    e_slot_free = ""
                    if e_slot_sel == "その他（自由入力）":
                        e_slot_free = st.text_input("コマ（自由入力）", value=cur_slot, key="ss_edit_slot_free")


                    e_slot = e_slot_free if e_slot_sel == "その他（自由入力）" else normalize_slot(e_slot_sel)       

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
                                & (sched["slot"].astype(str).str.strip().map(normalize_slot) == normalize_slot(e_slot))

                            )
                            if dup.any():
                                st.error("更新後に（生徒×曜日×コマ）が他の行と重複します。")
                            else:
                                _backup(STUDENT_SCHEDULE_CSV)
                                sched.loc[sel_idx, "weekday"] = str(e_weekday).strip()
                                sched.loc[sel_idx, "slot"] = normalize_slot(e_slot)
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
                #show_message=False,
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


                ts_slot_label_map = build_slot_label_map(timeslots)
                ts_slot_options = [str(k) for k in sorted(ts_slot_label_map.keys())] + ["その他（自由入力）"]


                t_slot_sel = st.selectbox(
                    "コマ（数字）",
                    options=ts_slot_options,
                    index=0,
                    key="ts_add_slot_sel",
                    format_func=lambda x: "その他（自由入力）" if str(x) == "その他（自由入力）" else format_slot_label(x, ts_slot_label_map)
                )


                t_slot_free = ""
                if t_slot_sel == "その他（自由入力）":
                    t_slot_free = st.text_input("コマ（自由入力）", value="", key="ts_add_slot_free")


                t_slot = t_slot_free if t_slot_sel == "その他（自由入力）" else normalize_slot(t_slot_sel)


                t_start = st.text_input("開始（例 16:00）", value="", key="ts_add_start")
                t_end = st.text_input("終了（例 16:50）", value="", key="ts_add_end")

                if st.button("追加", key="ts_add_btn"):
                    dup = (
                        (slots["weekday"].astype(str).str.strip() == str(t_wd).strip())
                        & (slots["slot"].astype(str).str.strip().map(normalize_slot) == normalize_slot(t_slot))
                    )
                    if dup.any():
                        st.error("同じ（曜日×コマ）が既にあります。編集を使ってください。")
                    else:
                        new_row = {"weekday": str(t_wd).strip(), "slot": normalize_slot(t_slot), "start": str(t_start).strip(), "end": str(t_end).strip()}
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

                    e_wd = st.selectbox(
                        "曜日",
                        weekday_opts,
                        index=weekday_opts.index(str(row.get("weekday", "月")).strip()) if str(row.get("weekday", "月")).strip() in weekday_opts else 0,
                        key="ts_edit_wd"
                    )
                    cur_slot = normalize_slot(row.get("slot", ""))
                    ts_edit_slot_label_map = build_slot_label_map(timeslots)
                    ts_edit_slot_options = [str(k) for k in sorted(ts_edit_slot_label_map.keys())] + ["その他（自由入力）"]


                    if cur_slot and cur_slot not in ts_edit_slot_options and cur_slot != "その他（自由入力）":
                        ts_edit_slot_options = ts_edit_slot_options[:-1] + [cur_slot] + [ts_edit_slot_options[-1]]


                    try:
                        ts_edit_slot_index = ts_edit_slot_options.index(cur_slot) if cur_slot in ts_edit_slot_options else 0
                    except Exception:
                        ts_edit_slot_index = 0


                    e_slot_sel = st.selectbox(
                        "コマ",
                        options=ts_edit_slot_options,
                        index=ts_edit_slot_index,
                        key="ts_edit_slot_sel",
                        format_func=lambda x: "その他（自由入力）" if str(x) == "その他（自由入力）" else format_slot_label(x, ts_edit_slot_label_map)
                    )


                    e_slot_free = ""
                    if e_slot_sel == "その他（自由入力）":
                        e_slot_free = st.text_input("コマ（自由入力）", value=cur_slot, key="ts_edit_slot_free")


                    e_slot = e_slot_free if e_slot_sel == "その他（自由入力）" else normalize_slot(e_slot_sel)


                    e_start = st.text_input("開始", value=str(row.get("start", "")), key="ts_edit_start")
                    e_end = st.text_input("終了", value=str(row.get("end", "")), key="ts_edit_end")


                    c5, c6 = st.columns(2)
                    with c5:
                        if st.button("保存（更新）", key="ts_edit_save"):
                            dup = (
                                (slots.index != sel_idx)
                                & (slots["weekday"].astype(str).str.strip() == str(e_wd).strip())
                                 & (slots["slot"].astype(str).str.strip().map(normalize_slot) == normalize_slot(e_slot))
                            )
                            if dup.any():
                                st.error("更新後に（曜日×コマ）が他の行と重複します。")
                            else:
                                _backup(TIMESLOTS_CSV)
                                slots.loc[sel_idx, "weekday"] = str(e_wd).strip()
                                slots.loc[sel_idx, "slot"] = normalize_slot(e_slot)
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
                
                
elif page == "座席":
    st.subheader("🪑 座席表（今日の配置）")
    st.markdown("### 今日の座席配置")

    today = dt.date.today().isoformat()

    seat_slot_label_map = build_slot_label_map(timeslots)
    seat_display_slot_options = ["1", "2", "3", "4", "5", "6", "7"]


    # 現在時刻に合うコマを初期選択する
    default_seat_slot = "1"


    now_time = dt.datetime.now().time()


    if not timeslots.empty:
        ts_for_now = timeslots.copy()


        for _, r in ts_for_now.iterrows():
            slot_val = normalize_slot(r.get("slot", ""))
            start_s = str(r.get("start", "")).strip()
            end_s = str(r.get("end", "")).strip()


            if not slot_val or not start_s or not end_s:
                continue


            try:
                start_t = dt.datetime.strptime(start_s, "%H:%M").time()
                end_t = dt.datetime.strptime(end_s, "%H:%M").time()
            except Exception:
                continue


            if start_t <= now_time <= end_t:
                default_seat_slot = slot_val
                break


    if "seat_display_slot" in st.session_state:
        default_seat_slot = str(st.session_state.get("seat_display_slot", default_seat_slot))


    default_index = (
        seat_display_slot_options.index(default_seat_slot)
        if default_seat_slot in seat_display_slot_options
        else 0
    )


    seat_slot_sel = st.selectbox(
        "座席図に表示するコマ",
        seat_display_slot_options,
        index=default_index,
        key="seat_display_slot",
        format_func=lambda x: format_slot_label(x, seat_slot_label_map),
    )


    today_seats = seat_assignments[
        (seat_assignments["date"].astype(str).str.strip() == today)
        & (seat_assignments["slot"].astype(str).str.strip() == str(seat_slot_sel).strip())
    ].copy()


    seat_map = {}
    for _, r in today_seats.iterrows():
        seat_no = str(r.get("seat_no", "")).strip()
        sid = str(r.get("student_id", "")).strip()
        if seat_no and sid:
            seat_map[seat_no] = sid


    if not students.empty and "student_id" in students.columns and "display_name" in students.columns:
        student_name_map = dict(
            zip(
                students["student_id"].astype(str).str.strip(),
                students["display_name"].astype(str).str.strip()
            )
        )
    else:
        student_name_map = {}


    def seat_display(seat_no: str) -> str:
        sid = seat_map.get(str(seat_no), "")
        if not sid:
            return "空席"
        return student_name_map.get(sid, sid)


    def seat_box(seat_no: str):
        name = seat_display(seat_no)
        st.markdown(
            f"""
            <div style="
                border:2px solid #333;
                border-radius:8px;
                padding:18px 8px;
                min-height:70px;
                text-align:center;
                font-weight:700;
                background:#ffffff;
            ">
                <div style="font-size:1.1rem;">席{seat_no}</div>
                <div style="font-size:1rem; margin-top:8px;">{name}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


    top_left, top_mid, top_right = st.columns([1, 1, 1])
    with top_mid:
        seat_box("3")
    with top_right:
        seat_box("4")


    mid_left, mid_mid, mid_right = st.columns([1, 1.5, 1])
    with mid_left:
        seat_box("5")
    #with mid_right:
    #    st.markdown(
    #        """
    #        <div style="
    #            border:2px solid #333;
    #            border-radius:8px;
    #            padding:18px 8px;
    #            min-height:70px;
    #            text-align:center;
    #            font-weight:700;
    #            background:#ffffff;
    #        ">
    #            先生
    #        </div>
    #        """,
    #        unsafe_allow_html=True
    #    )


    bottom_left, bottom_mid, bottom_right = st.columns([1, 1, 1])
    with bottom_mid:
        seat_box("2")
    with bottom_right:
        seat_box("1")


    monitor_left, monitor_mid, monitor_right = st.columns([1, 1, 1])
    with monitor_mid:
        st.markdown(
            """
            <div style="
                border:2px solid #555;
                border-radius:8px;
                padding:10px 8px;
                min-height:38px;
                text-align:center;
                background:#f7f7f7;
                font-weight:700;
            ">
                モニター
            </div>
            """,
            unsafe_allow_html=True
        )
        
    st.divider()
    
    with st.expander("補助：1コマずつ席を登録する", expanded=False):

        st.markdown("### 今日の席を登録")
        
        seat_slot_label_map = build_slot_label_map(timeslots)
        seat_register_slot_options = ["1", "2", "3", "4", "5", "6", "7"]


        seat_register_slot = st.selectbox(
            "登録するコマ",
            seat_register_slot_options,
            key="seat_register_slot",
            format_func=lambda x: format_slot_label(x, seat_slot_label_map),
        )

        registration_today_seats = seat_assignments[
            (seat_assignments["date"].astype(str).str.strip() == today)
            & (seat_assignments["slot"].astype(str).str.strip() == str(seat_register_slot).strip())
        ].copy()



        # 今日の予定の生徒だけを候補にする
        today_student_ids = set()


        today_wd = ["月", "火", "水", "木", "金", "土", "日"][dt.date.today().weekday()]


        # 基本スケジュールから「今日の生徒」を取得
        if not student_schedule.empty:
            sched_for_seat = student_schedule.copy()


            for c in ["student_id", "weekday"]:
                if c not in sched_for_seat.columns:
                    sched_for_seat[c] = ""


            sched_for_seat = sched_for_seat[
                sched_for_seat["weekday"].astype(str).str.strip() == today_wd
            ].copy()


            today_student_ids |= set(
                sched_for_seat["student_id"].astype(str).str.strip().tolist()
            )


        # 今日の例外：追加・振替を候補に足す
        if not schedule_overrides.empty:
            ov_for_seat = schedule_overrides.copy()


            for c in ["student_id", "date", "action"]:
                if c not in ov_for_seat.columns:
                    ov_for_seat[c] = ""


            ov_for_seat["date"] = ov_for_seat["date"].astype(str).str.strip()
            ov_for_seat["action_norm"] = ov_for_seat["action"].map(normalize_action_value)


            add_for_seat = ov_for_seat[
                (ov_for_seat["date"] == today)
                & (ov_for_seat["action_norm"]== "追加")
            ].copy()


            today_student_ids |= set(
                add_for_seat["student_id"].astype(str).str.strip().tolist()
            )


            # 今日の例外：キャンセルは候補から外す
            cancel_for_seat = ov_for_seat[
                (ov_for_seat["date"] == today)
                & (ov_for_seat["action_norm"]==  "キャンセル")
            ].copy()


            today_student_ids -= set(
                cancel_for_seat["student_id"].astype(str).str.strip().tolist()
            )


        # すでに登録するコマに座席登録済みの生徒も候補に残す
        if not registration_today_seats.empty and "student_id" in registration_today_seats.columns:
            today_student_ids |= set(
                registration_today_seats["student_id"].astype(str).str.strip().tolist()
            )


        today_student_ids = {sid for sid in today_student_ids if sid}


        active_students_for_seat = students.copy()


        if today_student_ids:
            active_students_for_seat = active_students_for_seat[
                active_students_for_seat["student_id"].astype(str).str.strip().isin(today_student_ids)
            ].copy()
        else:
            active_students_for_seat = active_students_for_seat.iloc[0:0].copy()


        if "status" in active_students_for_seat.columns:
            active_students_for_seat = active_students_for_seat[
                active_students_for_seat["status"].astype(str).str.strip() != "退会"
            ].copy()


        if "is_active" in active_students_for_seat.columns:
            active_students_for_seat = active_students_for_seat[
                active_students_for_seat["is_active"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
                .replace("", "true")
                .isin(["true", "1", "yes"])
            ].copy()


        seat_student_options = [("", "空席")]


        if not active_students_for_seat.empty:
            active_students_for_seat = active_students_for_seat.sort_values("display_name")


            for _, r in active_students_for_seat.iterrows():
                sid = str(r.get("student_id", "")).strip()
                name = str(r.get("display_name", "")).strip()
                if sid:
                    seat_student_options.append((sid, name if name else sid))


        seat_student_ids = [x[0] for x in seat_student_options]
        seat_student_labels = {sid: label for sid, label in seat_student_options}


        current_by_seat = {}
        for _, r in registration_today_seats.iterrows():
            current_by_seat[str(r.get("seat_no", "")).strip()] = str(r.get("student_id", "")).strip()



        new_seat_rows = []


        for seat_no in ["1", "2", "3", "4", "5"]:
            current_sid = current_by_seat.get(seat_no, "")
            default_index = seat_student_ids.index(current_sid) if current_sid in seat_student_ids else 0

            selected_sid = st.selectbox(
                f"席{seat_no}",
                seat_student_ids,
                index=default_index,
                key=f"seat_assign_{today}_{seat_register_slot}_{seat_no}",
                format_func=lambda sid: seat_student_labels.get(sid, sid)
            )


            note = st.text_input(
                f"席{seat_no} メモ",
                value="",
                key=f"seat_note_{today}_{seat_register_slot}_{seat_no}",
                placeholder="例：2コマ連続、自習あり、準備済み など"
            )


            if selected_sid:
                new_seat_rows.append({
                    "date": today,
                    "slot": str(seat_register_slot).strip(),
                    "seat_no": seat_no,
                    "student_id": selected_sid,
                    "note": note.strip(),
                })


        if st.button("💾 今日の席を保存", key=f"save_seats_{today}_{seat_register_slot}"):
            # =========================================
            # 重複チェック（同じコマで同じ生徒が複数席）
            # =========================================
            duplicate_errors = []


            for slot, seat_map in seat_input_map.items():
                seen = set()
                for seat_no, sid in seat_map.items():
                    sid = str(sid).strip()
                    if not sid:
                        continue
                    if sid in seen:
                        duplicate_errors.append(f"{slot}コマで同じ生徒が複数席に入っています")
                    seen.add(sid)


            if duplicate_errors:
                st.error("⚠ 入力エラーがあります\n" + "\n".join(duplicate_errors))
                st.stop()

            target_date = today
            target_slot = str(seat_register_slot).strip()


            others = seat_assignments[
                ~(
                    (seat_assignments["date"].astype(str).str.strip() == target_date)
                    & (seat_assignments["slot"].astype(str).str.strip() == target_slot)
                )
            ].copy()


            new_df = pd.DataFrame(new_seat_rows, columns=SEAT_ASSIGNMENT_COLS)


            save_df = pd.concat([others, new_df], ignore_index=True)
            save_df = save_df[SEAT_ASSIGNMENT_COLS].fillna("")


            write_csv_atomic(save_df, SEAT_ASSIGNMENTS_CSV)


            st.success("今日の席を保存しました。")
            st.rerun()
        
    st.divider()
    # =====================================================
    # 📋 今日の予定（座席登録用ミニ一覧）
    # ※座席画面内で、student_schedule + schedule_overrides から作る
    # =====================================================
    st.markdown("### 📋 今日の予定（座席確認）")
    
    seat_today_rows = []
    today_str = str(today)
    today_wd = ["月", "火", "水", "木", "金", "土", "日"][dt.date.today().weekday()]


    # 生徒名マップ
    student_name_map = {}
    if not students.empty and {"student_id", "display_name"}.issubset(students.columns):
        student_name_map = dict(
            zip(
                students["student_id"].astype(str).str.strip(),
                students["display_name"].astype(str).str.strip()
            )
        )
    # 在籍中の生徒IDだけを座席確認に出す
    active_student_ids_for_seat = set()


    if not students.empty and "student_id" in students.columns:
        students_active_for_seat = students.copy()


        if "is_active" in students_active_for_seat.columns:
            students_active_for_seat = students_active_for_seat[
                students_active_for_seat["is_active"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
                .replace("", "true")
                .isin(["true", "1", "yes"])
            ].copy()


        active_student_ids_for_seat = set(
            students_active_for_seat["student_id"].astype(str).str.strip()
        )


    # コマ時間マップ
    slot_time_map = {}
    if not timeslots.empty:
        ts_for_seat = timeslots.copy()
        for c in ["weekday", "slot", "start", "end"]:
            if c not in ts_for_seat.columns:
                ts_for_seat[c] = ""


        ts_for_seat = ts_for_seat[
            ts_for_seat["weekday"].astype(str).str.strip() == today_wd
        ].copy()


        for _, r in ts_for_seat.iterrows():
            slot_key = normalize_slot(r.get("slot", ""))
            slot_time_map[slot_key] = (
                str(r.get("start", "")).strip(),
                str(r.get("end", "")).strip()
            )


    # 基本スケジュール
    if not student_schedule.empty:
        sched_for_today = student_schedule.copy()


        for c in ["student_id", "weekday", "slot", "session_type"]:
            if c not in sched_for_today.columns:
                sched_for_today[c] = ""


        sched_for_today = sched_for_today[
            sched_for_today["weekday"].astype(str).str.strip() == today_wd
        ].copy()


        for _, r in sched_for_today.iterrows():
            sid = str(r.get("student_id", "")).strip()
            slot = normalize_slot(r.get("slot", ""))
            if not sid or not slot:
                continue

            if active_student_ids_for_seat and sid not in active_student_ids_for_seat:
                continue

            start, end = slot_time_map.get(slot, ("", ""))


            seat_today_rows.append({
                "student_id": sid,
                "コマ": slot,
                "start": start,
                "end": end,
                "生徒": student_name_map.get(sid, sid),
                "種別": str(r.get("session_type", "")).strip(),
            })


    # 今日の例外：追加
    if not schedule_overrides.empty:
        ov_for_today = schedule_overrides.copy()


        for c in ["student_id", "date", "slot", "action", "start", "end", "session_type"]:
            if c not in ov_for_today.columns:
                ov_for_today[c] = ""


        ov_for_today["date"] = ov_for_today["date"].astype(str).str.strip()
        ov_for_today["action_norm"] = ov_for_today["action"].map(normalize_action_value)

        add_rows = ov_for_today[
            (ov_for_today["date"] == today_str)
            & (ov_for_today["action_norm"] == "追加")
        ].copy()


        for _, r in add_rows.iterrows():
            sid = str(r.get("student_id", "")).strip()
            slot = normalize_slot(r.get("slot", ""))
            if not sid or not slot:
                continue

            if active_student_ids_for_seat and sid not in active_student_ids_for_seat:
                continue

            start_raw = r.get("start", "")
            end_raw = r.get("end", "")

            start = "" if pd.isna(start_raw) else str(start_raw).strip()
            end   = "" if pd.isna(end_raw) else str(end_raw).strip()

            if not start and not end:
                start, end = slot_time_map.get(slot, ("", ""))

            seat_today_rows.append({
                "student_id": sid,
                "コマ": slot,
                "start": start,
                "end": end,
                "生徒": student_name_map.get(sid, sid),
                "種別": str(r.get("session_type", "")).strip(),
            })


    # 今日の例外：キャンセルを除外
    cancel_keys = set()
    if not schedule_overrides.empty:
        ov_cancel = schedule_overrides.copy()


        for c in ["student_id", "date", "slot", "action"]:
            if c not in ov_cancel.columns:
                ov_cancel[c] = ""


        ov_cancel["date"] = ov_cancel["date"].astype(str).str.strip()
        ov_cancel["action_norm"] = ov_cancel["action"].map(normalize_action_value)


        cancel_rows = ov_cancel[
            (ov_cancel["date"] == today_str)
            & (ov_cancel["action_norm"] == "キャンセル")
        ].copy()


        for _, r in cancel_rows.iterrows():
            cancel_keys.add((
                str(r.get("student_id", "")).strip(),
                normalize_slot(r.get("slot", "")),
            ))


    seat_today_rows = [
        r for r in seat_today_rows
        if (str(r.get("student_id", "")).strip(), normalize_slot(r.get("コマ", ""))) not in cancel_keys
    ]


    # 座席登録済みマップ
    seat_map_for_today = {}
    if not seat_assignments.empty:
        seat_for_today = seat_assignments.copy()


        for c in ["date", "slot", "student_id", "seat_no"]:
            if c not in seat_for_today.columns:
                seat_for_today[c] = ""


        seat_for_today = seat_for_today[
            seat_for_today["date"].astype(str).str.strip() == today_str
        ].copy()


        for _, r in seat_for_today.iterrows():
            sid = str(r.get("student_id", "")).strip()
            slot = normalize_slot(r.get("slot", ""))
            seat_no = str(r.get("seat_no", "")).strip()
            if sid and slot and seat_no:
                seat_map_for_today[(sid, slot)] = f"席{seat_no}"


    # 表示用
    for r in seat_today_rows:
        sid = str(r.get("student_id", "")).strip()
        slot = normalize_slot(r.get("コマ", ""))
        r["席"] = seat_map_for_today.get((sid, slot), "⚠ 未配置")
        r["_slot_num"] = pd.to_numeric(slot, errors="coerce")
        
    # 未配置があるコマを記録
    missing_slots = set()
    missing_students = []
    
    # =========================================
    # 🪑 重複席チェック
    # =========================================
    duplicate_slots = set()


    seat_check = {}


    for r in seat_assignments.iterrows():
        row = r[1]


        if str(row.get("date", "")).strip() != str(today).strip():
            continue


        slot = normalize_slot(row.get("slot", ""))
        seat = str(row.get("seat_no", "")).strip()


        if not slot or not seat:
            continue


        key = (slot, seat)


        if key in seat_check:
            duplicate_slots.add(slot)
        else:
            seat_check[key] = True



    for r in seat_today_rows:
        if str(r.get("席", "")).strip() == "⚠ 未配置":
            slot = normalize_slot(r.get("コマ", ""))
            missing_slots.add(slot)

            student_name = str(r.get("生徒", "")).strip()

            if student_name:
                missing_students.append(
                    f"{student_name}（{slot}コマ）"
                )


    # 未配置件数カウント
    missing_count = 0
    for r in seat_today_rows:
        if str(r.get("席", "")).strip() == "⚠ 未配置":
            missing_count += 1

    if seat_today_rows:
        if missing_count > 0:
            st.warning(f"⚠ 未配置の生徒が {missing_count} 人います")
        else:
            st.success("全員配置されています")

    if seat_today_rows:
        seat_today_df = pd.DataFrame(seat_today_rows)
        seat_today_df = seat_today_df.sort_values(
            by=["_slot_num", "生徒"],
            na_position="last"
        )


        show_cols = ["コマ", "start", "end", "席", "生徒", "種別"]
        show_cols = [c for c in show_cols if c in seat_today_df.columns]


        seat_today_display = seat_today_df[show_cols].copy()


        def highlight_missing_seat(row):
            seat_value = str(row.get("席", "")).strip()
            if seat_value == "⚠ 未配置":
                return ["background-color: #ffe5e5; color: #8a1f1f; font-weight: 700"] * len(row)
            return [""] * len(row)


        st.dataframe(
            seat_today_display.style.apply(highlight_missing_seat, axis=1),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("今日の予定はありません")
        
   
    with st.expander("⚙️ 基本席の登録・修正・削除", expanded=False):
        st.caption("生徒ごとの基本席を登録します。今日の自動配置の土台になります。")


        active_students = students.copy()


        if "is_active" in active_students.columns:
            active_students = active_students[
                active_students["is_active"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
                .replace("", "true")
                .isin(["true", "1", "yes"])
            ].copy()


        active_students = active_students.sort_values("display_name")


        student_options = active_students["student_id"].astype(str).str.strip().tolist()
        student_label_map = dict(
            zip(
                active_students["student_id"].astype(str).str.strip(),
                active_students["display_name"].astype(str).str.strip(),
            )
        )


        default_map = dict(
            zip(
                default_seats["student_id"].astype(str).str.strip(),
                default_seats["default_seat_no"].astype(str).str.strip(),
            )
        )


        if student_options:
            target_sid = st.selectbox(
                "生徒",
                student_options,
                format_func=lambda sid: f"{sid} | {student_label_map.get(sid, sid)}",
                key="default_seat_student",
            )


            current_seat = default_map.get(target_sid, "")
            seat_options = ["", "1", "2", "3", "4", "5"]
            default_index = seat_options.index(current_seat) if current_seat in seat_options else 0


            default_seat_no = st.selectbox(
                "基本席",
                seat_options,
                index=default_index,
                format_func=lambda x: "未設定" if x == "" else f"席{x}",
                key="default_seat_no",
            )


            note = st.text_input(
                "メモ",
                value="",
                placeholder="例：基本は席3、2コマ連続多め など",
                key="default_seat_note",
            )


            col1, col2 = st.columns(2)


            with col1:
                if st.button("💾 基本席を保存", key="save_default_seat"):
                    df = default_seats.copy()
                    df = df[df["student_id"].astype(str).str.strip() != target_sid].copy()


                    if default_seat_no:
                        df = pd.concat([
                            df,
                            pd.DataFrame([{
                                "student_id": target_sid,
                                "default_seat_no": default_seat_no,
                                "note": note,
                            }])
                        ], ignore_index=True)


                    df = df[DEFAULT_SEAT_COLS].fillna("")
                    write_csv_atomic(df, DEFAULT_SEATS_CSV)
                    st.success("基本席を保存しました。")
                    st.rerun()


            with col2:
                if st.button("🗑 基本席を削除", key="delete_default_seat"):
                    df = default_seats.copy()
                    df = df[df["student_id"].astype(str).str.strip() != target_sid].copy()
                    df = df[DEFAULT_SEAT_COLS].fillna("")
                    write_csv_atomic(df, DEFAULT_SEATS_CSV)
                    st.success("基本席を削除しました。")
                    st.rerun()


        if not default_seats.empty:
            show_default = default_seats.copy()
            show_default["生徒"] = show_default["student_id"].map(student_label_map).fillna(show_default["student_id"])
            show_default["基本席"] = show_default["default_seat_no"].apply(lambda x: f"席{x}" if str(x).strip() else "未設定")


            st.dataframe(
                show_default[["student_id", "生徒", "基本席", "note"]],
                use_container_width=True,
                hide_index=True,
            )
   

    # =====================================================
    # 🪑 基本席から今日の座席を自動配置
    # =====================================================
    st.markdown("### 🪄 基本席から自動配置")


    st.caption("基本席が登録されている生徒を、今日の予定に合わせて空いている席へ自動配置します。重複がある場合は配置しません。")


    if st.button("🪄 基本席で自動配置する", key=f"auto_assign_default_seats_{today}"):
        default_map_auto = dict(
            zip(
                default_seats["student_id"].astype(str).str.strip(),
                default_seats["default_seat_no"].astype(str).str.strip(),
            )
        )

        existing_keys = set()
        existing_student_slot_keys = set()


        if not seat_assignments.empty:
            _existing = seat_assignments.copy()


            for c in ["date", "slot", "seat_no", "student_id"]:
                if c not in _existing.columns:
                    _existing[c] = ""


            _existing = _existing[
                _existing["date"].astype(str).str.strip() == str(today).strip()
            ].copy()


            for _, r in _existing.iterrows():
                _slot = normalize_slot(r.get("slot", ""))
                _seat = str(r.get("seat_no", "")).strip()
                _sid = str(r.get("student_id", "")).strip()


                if _slot and _seat:
                    existing_keys.add((_slot, _seat))


                if _slot and _sid:
                    existing_student_slot_keys.add((_sid, _slot))


        candidates = {}


        for r in seat_today_rows:
            sid = str(r.get("student_id", "")).strip()
            slot = normalize_slot(r.get("コマ", ""))


            if not sid or not slot:
                continue


            # すでにその生徒がそのコマで配置済みなら何もしない
            if (sid, slot) in existing_student_slot_keys:
                continue


            seat_no = default_map_auto.get(sid, "")


            if not seat_no:
                continue


            key = (slot, seat_no)
            candidates.setdefault(key, []).append(sid)


        auto_rows = []
        conflict_messages = []

        # 重複している席だけスキップし、重複していない席は自動配置する
        for (slot, seat_no), sids in candidates.items():
            if len(sids) >= 2:
                names = [student_name_map.get(sid, sid) for sid in sids]
                conflict_messages.append(
                    f"{slot}コマ 席{seat_no} が重複：{', '.join(names)}"
                )
                continue


            sid = sids[0]


            # すでに誰かが座っている席には自動配置しない
            if (slot, seat_no) in existing_keys:
                conflict_messages.append(
                    f"{slot}コマ 席{seat_no} はすでに使用中：{student_name_map.get(sid, sid)} は自動配置しません"
                )
                continue


            auto_rows.append({
                "date": str(today),
                "slot": slot,
                "seat_no": seat_no,
                "student_id": sid,
                "note": "基本席から自動配置",
            })




        if conflict_messages:
            st.session_state["seat_auto_conflict_messages"] = conflict_messages
        else:
            st.session_state["seat_auto_conflict_messages"] = []
            
        if auto_rows:
            applied = 0


            for r in auto_rows:
                slot = normalize_slot(r["slot"])
                seat_no = str(r["seat_no"]).strip()
                sid = str(r["student_id"]).strip()


                key = f"seat_grid_{today}_{slot}_{seat_no}"
                st.session_state[key] = sid
                applied += 1


            st.success(f"{applied}件を画面に反映しました（まだ保存されていません）")
            st.rerun()
        else:
            st.info("自動配置できる座席はありませんでした。")
            
    conflict_messages_saved = st.session_state.get("seat_auto_conflict_messages", [])

    if conflict_messages_saved:
        st.error("⚠ 基本席の重複があります。手動で配置してください。")
        for msg in conflict_messages_saved:
            st.write(f"- {msg}")
            
    if missing_students:
        st.warning("⚠ 未配置の生徒がいます")


    for msg in missing_students:
        st.write(f"・{msg}")

    st.markdown("### 🪑 今日の配置表")
    st.caption("縦＝コマ、横＝席1〜5で、今日1日の座席をまとめて登録します。")


    # 今日の予定に出てくる生徒だけを候補にする
    today_student_ids_for_grid = set()


    today_wd_for_grid = ["月", "火", "水", "木", "金", "土", "日"][dt.date.today().weekday()]


    if not student_schedule.empty:
        grid_sched = student_schedule.copy()


        for c in ["student_id", "weekday"]:
            if c not in grid_sched.columns:
                grid_sched[c] = ""


        grid_sched = grid_sched[
            grid_sched["weekday"].astype(str).str.strip() == today_wd_for_grid
        ].copy()


        today_student_ids_for_grid |= set(
            grid_sched["student_id"].astype(str).str.strip().tolist()
        )


    if not schedule_overrides.empty:
        grid_ov = schedule_overrides.copy()


        for c in ["student_id", "date", "action"]:
            if c not in grid_ov.columns:
                grid_ov[c] = ""


        grid_ov["date"] = grid_ov["date"].astype(str).str.strip()
        grid_ov["action_norm"] = grid_ov["action"].map(normalize_action_value)


        grid_add = grid_ov[
            (grid_ov["date"] == today)
            & (grid_ov["action_norm"]=="追加")
        ].copy()


        today_student_ids_for_grid |= set(
            grid_add["student_id"].astype(str).str.strip().tolist()
        )


        grid_cancel = grid_ov[
            (grid_ov["date"] == today)
            & (grid_ov["action_norm"]=="キャンセル")
        ].copy()


        today_student_ids_for_grid -= set(
            grid_cancel["student_id"].astype(str).str.strip().tolist()
        )


    today_student_ids_for_grid = {sid for sid in today_student_ids_for_grid if sid}


    grid_students = students.copy()


    if today_student_ids_for_grid:
        grid_students = grid_students[
            grid_students["student_id"].astype(str).str.strip().isin(today_student_ids_for_grid)
        ].copy()
    else:
        grid_students = grid_students.iloc[0:0].copy()


    if "status" in grid_students.columns:
        grid_students = grid_students[
            grid_students["status"].astype(str).str.strip() != "退会"
        ].copy()


    if "is_active" in grid_students.columns:
        grid_students = grid_students[
            grid_students["is_active"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .replace("", "true")
            .isin(["true", "1", "yes"])
        ].copy()

  
    grid_options = [("", "空席"), ("__RESERVED__", "使用予定")]

    if not grid_students.empty:
        grid_students = grid_students.sort_values("display_name")


        for _, r in grid_students.iterrows():
            sid = str(r.get("student_id", "")).strip()
            name = str(r.get("display_name", "")).strip()
                            
            if sid:
                grid_options.append((sid, name if name else sid))
                             
        grid_student_ids = [x[0] for x in grid_options]
        grid_student_labels = {sid: label for sid, label in grid_options}
            
    # 既存の座席登録を初期値として読む
    existing_grid = {}


    if not seat_assignments.empty:
        grid_existing = seat_assignments.copy()


        for c in ["date", "slot", "seat_no", "student_id"]:
            if c not in grid_existing.columns:
                grid_existing[c] = ""


        grid_existing = grid_existing[
            grid_existing["date"].astype(str).str.strip() == today
        ].copy()


        for _, r in grid_existing.iterrows():
            slot = str(r.get("slot", "")).strip()
            seat_no = str(r.get("seat_no", "")).strip()
            sid = str(r.get("student_id", "")).strip()
            if slot and seat_no:
                existing_grid[(slot, seat_no)] = sid


    slot_rows = ["1", "2", "3", "4", "5", "6", "7"]
    seat_cols = ["1", "2", "3", "4", "5"]
    
    unsaved_changes = False

    for slot in slot_rows:
        for seat_no in seat_cols:
            widget_key = f"seat_grid_{today}_{slot}_{seat_no}"


            current_sid = str(
                st.session_state.get(
                    widget_key,
                    existing_grid.get((slot, seat_no), "")
                )
            ).strip()

            saved_sid = str(existing_grid.get((slot, seat_no), "")).strip()

            if current_sid != saved_sid:
                unsaved_changes = True
                break

        if unsaved_changes:
            break


    if unsaved_changes:
        st.warning("⚠ 保存されていない変更があります")



    grid_rows_to_save = []


    st.markdown("#### 配置入力")


    header_cols = st.columns([0.6, 1, 1, 1, 1, 1])
    with header_cols[0]:
        st.markdown("**コマ**")
        
    seat_colors = {
        "1": "#e8d9f3",
        "2": "#d9f0f3",
        "3": "#fff7d6",
        "4": "#fff0e5",
        "5": "#e9f8ee",
    }

    for i, seat_no in enumerate(seat_cols, start=1):
        with header_cols[i]:
            seat_bg = seat_colors.get(str(seat_no), "#ffffff")
            
            st.markdown(
                f"""
                <div style="
                    background:{seat_bg};
                    padding:8px 10px;
                    border-radius:8px;
                    text-align:center;
                    font-weight:700;
                ">
                    席{seat_no}
                </div>
                """,
                unsafe_allow_html=True,
            )

    slot_bg = {
        "1": "#f4f0ff",
        "2": "#e8fbff",
        "3": "#fff7d6",
        "4": "#fff0e5",
        "5": "#e9f8ee",
        "6": "#fdebf3",
        "7": "#f4f4f4",
    }
    

    for slot in slot_rows:
        
        bg = slot_bg.get(slot, "#ffffff")
        
        slot_start, slot_end = slot_time_map.get(str(slot).strip(), ("", ""))
        slot_time_label = f"（{slot_start}〜{slot_end}）" if slot_start and slot_end else ""

        slot_count = 0
        selected_seat_keys = set()
        duplicate_in_current_slot = False


        for seat_no in seat_cols:
            key = f"seat_grid_{today}_{slot}_{seat_no}"
            sid = str(st.session_state.get(key, existing_grid.get((slot, seat_no), ""))).strip()


            if sid:
                slot_count += 1


            # 画面上の現在の選択状態で「同じ席の重複」を見る
            # ただし通常UIでは1席に1つしか選べないので、ここでは保存済みCSV側の重複補助用
            seat_key = str(seat_no).strip()
            if sid and seat_key in selected_seat_keys:
                duplicate_in_current_slot = True
            selected_seat_keys.add(seat_key)


        # 人数に応じた強調色
        if slot_count == 0:
            bg = "#eeeeee"
        elif slot_count == 4:
            bg = "#fff3cd"
        elif slot_count >= 5:
            bg = "#d4edda"


        # 未配置または重複があるコマは最優先で赤系にする
        if str(slot).strip() in missing_slots or str(slot).strip() in duplicate_slots or duplicate_in_current_slot:
            bg = "#f8d7da"


   
        st.markdown(
            f"""
            <div style="
                background:{bg};
                padding:6px 10px;
                border-radius:8px;
                margin-top:8px;
                font-weight:700;
            ">
                {slot}コマ {slot_time_label}

            </div>
            """,
            unsafe_allow_html=True
        )

        cols = st.columns([0.6, 1, 1, 1, 1, 1])


        with cols[0]:
            st.markdown(f"**{slot}コマ（{slot_count}人 / 5席）**")

        selected_in_slot = []


        for i, seat_no in enumerate(seat_cols, start=1):
            widget_key = f"seat_grid_{today}_{slot}_{seat_no}"


            current_sid = str(
                st.session_state.get(
                    widget_key,
                    existing_grid.get((slot, seat_no), "")
                )
            ).strip()


            default_index = grid_student_ids.index(current_sid) if current_sid in grid_student_ids else 0


            with cols[i]:
                seat_bg = seat_colors.get(str(seat_no), "#ffffff")
                
                saved_sid = str(
                    existing_grid.get((slot, seat_no), "")
                ).strip()

                is_changed = current_sid != saved_sid

                if is_changed:
                    seat_bg = "#fff4cc"
                    border_style = "3px solid #f0a000"
                else:
                    border_style = "1px solid transparent"


                st.markdown(
                    f"""
                    <div style="
                        background:{seat_bg};
                        padding:8px;
                        border-radius:8px;
                        border:{border_style};
                    ">
                    """,
                    unsafe_allow_html=True
                )


                selected_sid = st.selectbox(
                    f"{slot}コマ 席{seat_no}",
                    grid_student_ids,
                    index=default_index,
                    key=widget_key,
                    format_func=lambda sid: grid_student_labels.get(sid, sid),
                    label_visibility="collapsed",
                )


                # selectboxで選ばれている値を、その場で表示する
                selected_label = grid_student_labels.get(selected_sid, selected_sid)


                if selected_sid == "":
                    st.caption("△ 空席")
                elif selected_sid == "__RESERVED__":
                    st.markdown(
                        "<span style='color:#f0a000; font-weight:700;'>● 使用予定</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<span style='color:#00a6d6; font-weight:700;'>● {selected_label}</span>",
                        unsafe_allow_html=True,
                    )


                st.markdown("</div>", unsafe_allow_html=True)



            if selected_sid:
                selected_in_slot.append(selected_sid)
                grid_rows_to_save.append({
                    "date": today,
                    "slot": slot,
                    "seat_no": seat_no,
                    "student_id": selected_sid,
                    "note": "",
                })


        dup_students = {
            sid for sid in selected_in_slot
            if sid and sid != "__RESERVED__" and selected_in_slot.count(sid) > 1
        }

        if dup_students:
            dup_names = [grid_student_labels.get(sid, sid) for sid in dup_students]
            st.warning(f"{slot}コマで同じ生徒が複数席に入っています：{', '.join(dup_names)}")
            
    if st.button("💾 今日の配置表を保存", key=f"save_seat_grid_{today}"):
        others = seat_assignments[
            seat_assignments["date"].astype(str).str.strip() != today
        ].copy()

        new_df = pd.DataFrame(grid_rows_to_save, columns=SEAT_ASSIGNMENT_COLS)


        save_df = pd.concat([others, new_df], ignore_index=True)
        save_df = save_df[SEAT_ASSIGNMENT_COLS].fillna("")


        write_csv_atomic(save_df, SEAT_ASSIGNMENTS_CSV)


        st.success("今日の配置表を保存しました。")
        st.rerun()

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
