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
def normalize_slot(v):
    """1, '1', 1.0 → '1' に統一（文字列）"""
    if v is None:
        return ""
    try:
        n = int(float(v))
        return str(n)
    except Exception:
        s = str(v).strip()
        # もし '1.0' みたいなのが来たら '1' に寄せる
        try:
            n = int(float(s))
            return str(n)
        except Exception:
            return s

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




def format_slot_label(x, slot_label_map):
    """selectbox の format_func 用"""
    try:
        k = int(float(x))
        return slot_label_map.get(k, str(k))
    except Exception:
        return str(x)


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


def build_kentei_hint(judge, grade):
    judge_str = str(judge).strip()
    grade_str = str(grade).strip()

    if not judge_str or judge_str.lower() == "nan":
        return ""
    if not grade_str or grade_str.lower() == "nan" or grade_str == "不明":
        return judge_str
    return f"{judge_str} / {grade_str}"


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
PROGRESS_SKIP_OK_CSV = DATA_DIR / "progress_skip_ok.csv"
PREP_MEMO_CSV = DATA_DIR / "prep_memo.csv"

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

def save_progress_skip_ok(df: pd.DataFrame) -> None:
    for c in ["date", "student_id", "note"]:
        if c not in df.columns:
            df[c] = ""
    df = df[["date", "student_id", "note"]].copy()
    write_csv_atomic(df, PROGRESS_SKIP_OK_CSV)

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




def save_prep_memo(df: pd.DataFrame) -> None:
    for c in ["student_id", "memo"]:
        if c not in df.columns:
            df[c] = ""
    df = df[["student_id", "memo"]].copy()
    write_csv_atomic(df, PREP_MEMO_CSV)




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




def build_today_task_status(att_done: bool, prog_done: bool) -> str:
    if att_done and prog_done:
        return "✅ 出欠済 / 進捗済"
    if (not att_done) and (not prog_done):
        return "🚨 出欠未 / 進捗未"
    if not att_done:
        return "⚠ 出欠未"
    return "⚠ 進捗未"


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
   #show_message: bool = True,
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

    # =========================================================
    # 閲覧内の表示切替（現在タブを変数で持つ）
    # =========================================================
    view_tab = st.radio(
        "表示切替",
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
        key="view_tab"
    )


    # =========================================================
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


    student_names = sorted(
        [
            str(n).strip()
            for n in students_for_filter.get("display_name", pd.Series(dtype=str)).fillna("").astype(str)
            if str(n).strip()
        ]
    )


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


    is_log_tab = view_tab in [
        "コース別（件数）",
        "Scratch検定一覧",
        "生徒ごと一覧",
        "生徒別（done）",
        "詳細（最新状態）",
    ]


    # =========================
    # 対象
    # =========================
    st.sidebar.markdown("### 対象")


    selected_student = st.sidebar.selectbox(
        "👤 生徒",
        ["（全員）"] + student_names,
        key="sidebar_student",
    )


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
        "今日の生徒だけ表示",
        value=False,
        key="today_only",
    )


    include_inactive = st.sidebar.checkbox(
        "退会した生徒も含める",
        value=include_inactive,
        key="include_inactive",
    )


    selected_curriculum = st.sidebar.selectbox(
        "カリキュラム（ログ表示）",
        ["（全て）"] + curriculum_list,
        key="sidebar_curriculum",
        disabled=not is_log_tab,
    )


    selected_status = st.sidebar.selectbox(
        "状態（詳細表示用）",
        ["（全て）"] + status_list,
        key="sidebar_status",
        disabled=not is_log_tab,
    )


    if not is_log_tab:
        st.sidebar.caption("※ この表示では「カリキュラム / 状態」フィルタは使いません")


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
    # Scratch最高級（唯一の正: kentei_results.csv）
    # =========================================================
    kentei_results = load_kentei_results().copy()


    scratch_best = pd.DataFrame(columns=["student_id", "grade", "display_name", "item"])


    if not kentei_results.empty:
        kentei_results["student_id"] = kentei_results["student_id"].fillna("").astype(str).str.strip()
        kentei_results["grade"] = kentei_results["grade"].fillna("").astype(str).str.strip()


        # 数字が小さいほど上位級
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

    if view_tab == "カリキュラム課題":
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
                    p = p[(p["student_id"].astype(str).str.strip() == student_id) & (p["course_id"].astype(str).str.strip() == str(selected_course_id).strip())].copy()
                    done_map = {str(r["task_id"]).strip(): (str(r["is_done"]).strip().lower() == "true") for _, r in p.iterrows()}
                    done_date_map = {
                        str(r["task_id"]).strip(): str(r.get("done_date", "")).strip()
                        for _, r in p.iterrows()
                        if str(r["student_id"]).strip() == str(student_id).strip()
                        and str(r["course_id"]).strip() == str(selected_course_id).strip()
                    }

                    st.markdown("### 課題一覧")
                    updated_rows = []

                    for _, row in t.iterrows():
                        task_id = str(row["task_id"]).strip()
                        task_name = str(row["task_name"]).strip()
                        was_done = bool(done_map.get(task_id, False))
                        prev_done_date = str(done_date_map.get(task_id, "")).strip()
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
                            "done_date": (
                                dt.date.today().isoformat()
                                if checked and not was_done
                                else prev_done_date
                            ) if checked else "",
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
    
    if view_tab == "検定課題":
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
            done_date_map = {
                str(r["task_id"]).strip(): str(r.get("done_date", "")).strip()
                for _, r in prog.iterrows()
            }

            st.markdown("### 課題一覧")
            updated = []

            for _, row in tasks.iterrows():
                task_id = str(row["task_id"]).strip()
                was_done = bool(done_map.get(task_id, False))
                prev_done_date = str(done_date_map.get(task_id, "")).strip()
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
                    "done_date": (
                        dt.date.today().isoformat()
                        if checked and not was_done
                        else prev_done_date
                    ),
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

    if view_tab == "コース別（件数）":
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

    if view_tab == "Scratch検定一覧":
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

    if view_tab == "生徒ごと一覧":

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



    if view_tab == "生徒別（done）":

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


    if view_tab == "詳細（最新状態）":
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

else:
    # 管理画面中は、左サイドバーの閲覧フィルタを無効化
    st.sidebar.header("管理")
    override_passed_lock = st.session_state.get("override_passed_lock", False)  # (v6.5.5) 2重生成防止

    # NOTE: 閲覧側の sidebar checkbox(key="override_done_lock") とは別keyで表示する。
    # widget key を後から直接書き換えると StreamlitAPIException になるため、
    # 管理側ではローカル変数としてだけ使う。
    override_done_lock_admin = st.sidebar.checkbox(
        "⚠ 完了済み課題を編集する（通常はOFF）",
        key="override_done_lock_admin",
        value=st.session_state.get("override_done_lock_admin", False),
    )
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
                                sslots.loc[sel_idx, "slot"] = normalize_slot(e_slot)
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