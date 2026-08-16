# d332:
# 課題追加の「追加方法」に「最初に追加」を追加。
# 選択時は新規課題を order 1 にし、同じコースの既存課題を自動で +1 する。
# d331:
# 月スケジュールをカレンダー全幅表示へ変更。
# 左の操作サイドバーを廃止し、
# 既存予定の編集はポップアップ、新規追加もポップアップへ統一。
# 画面下の固定保存バーは維持。
# d330:
# 試用版：月カレンダーの予定編集を st.dialog のポップアップで開く。
# 未保存の月スケジュール変更がある間、保存バーを画面下へ固定表示する。
# 既存の左側編集欄は比較・保険のため残している。
# d329:
# 月スケジュール左操作パネルの実表示順を変更。
# 「🟠 選択中の予定を編集・取消・削除」を上、
# 「🟢 新しい予定を追加」を下へ、フォーム全体ごと入れ替えた。
# d327:
# 検定予定一覧を一括編集・一括保存方式へ変更。
# 検定結果を「合格／不合格／後で登録」で扱えるようにし、
# 不合格→再受験→合格の履歴を残す。
# 旧kentei_results.csvはresult空欄を合格として後方互換。
# d326:
# カリキュラム管理のコース部分を一括編集・一括保存方式へ変更。
# コース追加・編集・削除は編集用データへ反映し、
# 最後に1回だけ curriculum_courses.csv へ保存する。
# 削除時の関連課題削除、編集破棄、外部更新時の上書き防止を追加。
# d325:
# 生徒管理を「複数人編集して最後に一括保存」方式へ変更。
# 新規追加・情報更新・退会は編集用データへ反映し、
# 最後に1回だけstudents.csvへ保存する。
# 生徒ID固定、退会確認、基本席解除、外部更新時の上書き防止を維持。
# d324:
# 月カレンダーで予定を選択した時の二重再描画を修正。
# st.button の自動再実行に加えて選択処理内でも st.rerun() を呼んでいたため、
# 選択コールバック末尾の手動 rerun を削除。
# d323:
# 月スケジュール操作パネルの「新規追加」と「選択中の予定を編集・削除」を色分け。
# 新規追加は緑、編集・取消・削除はオレンジの見出しカードにして、
# 再描画後も操作中の役割を見失いにくくする。
# d322:
# 月スケジュールを「編集」「回数確認」「生成」の3モードへ分離。
# 選択したモード以外の重いUI・集計を描画しない。
# 週の開閉は状態を保持するtoggleへ変更し、再実行後も開いていた週を維持。
# 旧UIの1件編集は描画せず、カレンダー操作へ集約。
# d321:
# 月スケジュールを「編集して最後に一括保存」する方式へ変更。
# カレンダー操作、固定スケジュール反映、旧UIの追加・修正・削除は
# st.session_state の編集用データへ反映し、最後に1回だけCSVへ保存する。
# 未保存表示・編集破棄・外部更新時の上書き防止を追加。
# d320:
# 旧 student_schedule.csv との後方互換を修正。
# week_pattern は必須列として読み込まず、列がない場合は「毎週」を補完する。
# d319 の一括編集・一括保存機能はそのまま維持。
# d319:
# 固定スケジュールを「編集して最後に一括保存」する方式へ変更。
# 追加・削除は st.session_state の編集用データだけに反映し、
# 「固定スケジュールを保存」で1回だけCSVへ書き込む。
# 未保存表示・編集破棄・外部更新時の上書き防止を追加。
# d318:
# 固定スケジュールへ月内の週指定を追加。
# 「毎週」「第1・第3」「第2・第4」「第1～第5」を選択でき、
# 月スケジュール生成時は指定された週だけを反映する。
# 既存の week_pattern 空欄データは「毎週」として互換維持。
# d316:
# 出欠登録の操作案内を明確化。
# 授業・自習・欠席はすべて「出欠を保存／更新」で登録・上書きし、
# 欠席選択時に予定取消・座席解除が行われることを画面上に表示。
from __future__ import annotations

from pathlib import Path
import datetime as dt
import calendar as cal
from datetime import date
import os

import pandas as pd
import numpy as np
from datetime import datetime

import re
import streamlit as st
import textwrap

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
st.set_page_config(
    page_title="Curriculum Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)
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
# d295:
# 左サイドバーの扱い
# ---------------------------------------------------------
# Streamlitの initial_sidebar_state は「初回表示時だけ」の指定で、
# 画面切替ごとに閉じる/開く制御には弱い。
# そのため、閲覧ではサイドバーを使い、管理・座席では画面上から隠す。
# =========================================================
if page != "閲覧":
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }
        div[data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }
        button[data-testid="collapsedControl"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
            for col in [
                "student_id",
                "grade",
                "result",
                "score",
                "pass_date",
                "memo",
            ]:
                if col not in df.columns:
                    df[col] = ""
            df = df.fillna("")
            df["student_id"] = df["student_id"].astype(str).str.strip()
            df["grade"] = df["grade"].astype(str).str.strip()
            df["result"] = df["result"].astype(str).str.strip()
            # 旧データは合格記録として扱う。
            df.loc[df["result"].eq(""), "result"] = "合格"
            df = df[(df["student_id"] != "") & (df["grade"] != "")]
            return df[
                [
                    "student_id",
                    "grade",
                    "result",
                    "score",
                    "pass_date",
                    "memo",
                ]
            ]
        except Exception:
            df = pd.DataFrame(columns=["student_id", "grade", "result", "score", "pass_date", "memo"])
            write_csv_atomic(df, KENTEI_RESULTS_CSV)
            return df
    df = pd.DataFrame(columns=["student_id", "grade", "result", "score", "pass_date", "memo"])
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
    result_series = (
        df["result"].fillna("").astype(str).str.strip()
        if "result" in df.columns
        else pd.Series(["合格"] * len(df), index=df.index)
    )
    m = (
        df["student_id"].astype(str).str.strip().eq(sid)
        & df["grade"].astype(str).str.strip().eq(g)
        & result_series.isin(["合格", "pass", "passed"])
    )
    return bool(m.any())


# =========================================================
# 🎯 検定練習中フラグ（d250）
# =========================================================
KENTEI_TRAINING_STATUS_COLS = ["student_id", "is_training", "grade", "updated_at", "note"]

def load_kentei_training_status() -> pd.DataFrame:
    try:
        if Path(KENTEI_TRAINING_STATUS_CSV).exists():
            df = pd.read_csv(KENTEI_TRAINING_STATUS_CSV, dtype=str).fillna("")
        else:
            df = pd.DataFrame(columns=KENTEI_TRAINING_STATUS_COLS)
    except Exception:
        df = pd.DataFrame(columns=KENTEI_TRAINING_STATUS_COLS)

    for c in KENTEI_TRAINING_STATUS_COLS:
        if c not in df.columns:
            df[c] = ""
    return df[KENTEI_TRAINING_STATUS_COLS].fillna("")

def save_kentei_training_status(df: pd.DataFrame) -> None:
    df2 = df.copy() if df is not None else pd.DataFrame(columns=KENTEI_TRAINING_STATUS_COLS)
    for c in KENTEI_TRAINING_STATUS_COLS:
        if c not in df2.columns:
            df2[c] = ""
    write_csv_atomic(df2[KENTEI_TRAINING_STATUS_COLS].fillna(""), KENTEI_TRAINING_STATUS_CSV)

def is_kentei_training_active(student_id: str) -> bool:
    df = load_kentei_training_status()
    if df.empty:
        return False
    sid = str(student_id).strip()
    tmp = df[df["student_id"].astype(str).str.strip() == sid].copy()
    if tmp.empty:
        return False
    v = str(tmp.iloc[-1].get("is_training", "")).strip().lower()
    return v in ["true", "1", "yes", "on", "検定練習中"]

def get_kentei_training_grade(student_id: str) -> str:
    df = load_kentei_training_status()
    if df.empty:
        return ""
    sid = str(student_id).strip()
    tmp = df[df["student_id"].astype(str).str.strip() == sid].copy()
    if tmp.empty:
        return ""
    return str(tmp.iloc[-1].get("grade", "")).strip()

def upsert_kentei_training_status(student_id: str, is_training: bool, grade: str = "", note: str = "") -> None:
    df = load_kentei_training_status()
    sid = str(student_id).strip()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = {
        "student_id": sid,
        "is_training": "true" if is_training else "false",
        "grade": str(grade).strip(),
        "updated_at": now_str,
        "note": str(note).strip(),
    }
    if df.empty:
        df2 = pd.DataFrame([new_row])
    else:
        mask = df["student_id"].astype(str).str.strip() == sid
        if mask.any():
            df2 = df.copy()
            for k, v in new_row.items():
                df2.loc[mask, k] = v
        else:
            df2 = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_kentei_training_status(df2)

def has_unpassed_kentei_exam_schedule(student_id: str, exam_df: pd.DataFrame) -> bool:
    try:
        sid = str(student_id).strip()
        if exam_df is None or exam_df.empty:
            return False

        ex = exam_df.copy()
        for c in ["student_id", "grade"]:
            if c not in ex.columns:
                ex[c] = ""
            ex[c] = ex[c].fillna("").astype(str).str.strip()
        ex = ex[ex["student_id"].astype(str).str.strip() == sid].copy()
        if ex.empty:
            return False

        passed = set()
        try:
            res = load_kentei_results().copy()
            if not res.empty:
                for c in ["student_id", "grade"]:
                    if c not in res.columns:
                        res[c] = ""
                    res[c] = res[c].fillna("").astype(str).str.strip()
                if "result" not in res.columns:
                    res["result"] = "合格"
                _pass_rows = res[
                    (res["student_id"].astype(str).str.strip() == sid)
                    & (
                        res["result"]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        .isin(["合格", "pass", "passed"])
                    )
                ]
                passed = set(
                    _pass_rows["grade"]
                    .astype(str)
                    .str.strip()
                    .tolist()
                )
        except Exception:
            passed = set()

        ex = ex[~ex["grade"].astype(str).str.strip().isin(passed)].copy()
        return bool(not ex.empty)
    except Exception:
        return False

# =========================================================
# ✅ 出席ログ（attendance_log.csv）: v6.6.3
#   - 予定ではなく「実績」を1回だけ記録（授業/自習）
#   - date × student_id は 1日1レコード（重複防止）
# =========================================================
ATTENDANCE_LOG_CSV = DATA_DIR / "attendance_log.csv"
PROGRESS_SKIP_OK_CSV = DATA_DIR / "progress_skip_ok.csv"
PREP_MEMO_CSV = DATA_DIR / "prep_memo.csv"
PREPARATION_LOG_CSV = DATA_DIR / "preparation_log.csv"

# d296:
# 教室に来た生徒の「5分タイピング練習」を確認するログ。
# 出席登録済みの生徒を対象に、done / skip を1日1レコードで保存する。
TYPING_LOG_CSV = DATA_DIR / "typing_log.csv"

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

# =========================================================
# 🔒 出席済み予定の軽いロック（d206）
# ---------------------------------------------------------
# attendance_log.csv に「lesson / selfstudy / 授業 / 自習 / 出席」
# が入っている日×生徒は、月スケジュール上で誤って取消・削除しにくくする。
# 完全ロックではなく、画面上の「修正モード」チェックで解除できる。
# =========================================================
def _attendance_lock_date_str(v) -> str:
    try:
        if isinstance(v, dt.datetime):
            return v.date().isoformat()
        if isinstance(v, dt.date):
            return v.isoformat()
        ts = pd.to_datetime(str(v).strip(), errors="coerce")
        if pd.isna(ts):
            return str(v).strip()
        return ts.date().isoformat()
    except Exception:
        return str(v).strip()


def normalize_attendance_kind_for_lock(v) -> str:
    s = str(v or "").strip().lower()
    if s in ["lesson", "授業", "出席", "attend", "present"]:
        return "lesson"
    if s in ["self", "selfstudy", "自習"]:
        return "selfstudy"
    if s in ["absence", "欠席"]:
        return "absence"
    if s in ["cancel", "キャンセル"]:
        return "cancel"
    return s


def build_attended_student_date_keys(att_df: pd.DataFrame) -> set[tuple[str, str]]:
    """出席済みとして軽いロックをかける date×student_id の集合を作る。"""
    if att_df is None or att_df.empty:
        return set()

    df = att_df.copy()
    for c in ["date", "student_id", "kind"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    df["date_key"] = df["date"].map(_attendance_lock_date_str)
    df["student_id_key"] = df["student_id"].astype(str).str.strip()
    df["kind_norm"] = df["kind"].map(normalize_attendance_kind_for_lock)

    # 「出席済み」として扱うのは、授業・自習として確認済みの実績。
    # 欠席/キャンセルは修正が必要になる場面も多いため、ここではロック対象にしない。
    df = df[df["kind_norm"].isin(["lesson", "selfstudy"])].copy()
    df = df[(df["date_key"] != "") & (df["student_id_key"] != "")]
    return set(zip(df["date_key"], df["student_id_key"]))


def is_attendance_locked_plan(attended_keys: set[tuple[str, str]], student_id: str, d) -> bool:
    """月カレンダー上で、出席済み予定として軽くロックするか判定する。"""
    return (_attendance_lock_date_str(d), str(student_id).strip()) in (attended_keys or set())

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



# =========================================================
# 🧰 当日準備チェック（d314）
# =========================================================
PREPARATION_LOG_COLS = [
    "date", "student_id", "slot", "prepared", "prepared_at"
]


def load_preparation_log() -> pd.DataFrame:
    if PREPARATION_LOG_CSV.exists():
        try:
            df = pd.read_csv(PREPARATION_LOG_CSV, dtype=str).fillna("")
        except Exception:
            df = pd.DataFrame(columns=PREPARATION_LOG_COLS)
    else:
        df = pd.DataFrame(columns=PREPARATION_LOG_COLS)
        write_csv_atomic(df, PREPARATION_LOG_CSV)
        return df

    for c in PREPARATION_LOG_COLS:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()
    return df[PREPARATION_LOG_COLS].copy()


def save_preparation_log(df: pd.DataFrame) -> None:
    out = df.copy()
    for c in PREPARATION_LOG_COLS:
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].fillna("").astype(str).str.strip()
    write_csv_atomic(out[PREPARATION_LOG_COLS], PREPARATION_LOG_CSV)


def is_prepared_for_plan(prep_df, *, d, student_id, slot) -> bool:
    if prep_df is None or prep_df.empty:
        return False

    d_obj = pd.to_datetime(d, errors="coerce")
    dstr = d_obj.strftime("%Y-%m-%d") if pd.notna(d_obj) else str(d).strip()
    sid = str(student_id).strip()
    slot_norm = normalize_slot(slot)

    tmp = prep_df.copy()
    for c in PREPARATION_LOG_COLS:
        if c not in tmp.columns:
            tmp[c] = ""
        tmp[c] = tmp[c].fillna("").astype(str).str.strip()

    hit = tmp[
        (tmp["date"] == dstr)
        & (tmp["student_id"] == sid)
        & (tmp["slot"].map(normalize_slot) == slot_norm)
        & (tmp["prepared"].str.lower().isin(["true", "1", "yes", "済", "完了"]))
    ]
    return not hit.empty


def set_preparation_status(
    prep_df,
    *,
    d,
    student_id,
    slots,
    prepared: bool,
) -> pd.DataFrame:
    out = prep_df.copy() if prep_df is not None else pd.DataFrame(columns=PREPARATION_LOG_COLS)

    for c in PREPARATION_LOG_COLS:
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].fillna("").astype(str).str.strip()

    d_obj = pd.to_datetime(d, errors="coerce")
    dstr = d_obj.strftime("%Y-%m-%d") if pd.notna(d_obj) else str(d).strip()
    sid = str(student_id).strip()
    slot_list = [normalize_slot(x) for x in slots if normalize_slot(x)]

    remove_mask = (
        (out["date"] == dstr)
        & (out["student_id"] == sid)
        & (out["slot"].map(normalize_slot).isin(slot_list))
    )
    out = out.loc[~remove_mask].copy()

    if prepared:
        now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            {
                "date": dstr,
                "student_id": sid,
                "slot": slot_value,
                "prepared": "true",
                "prepared_at": now_str,
            }
            for slot_value in slot_list
        ]
        if rows:
            out = pd.concat([out, pd.DataFrame(rows)], ignore_index=True)

    return out[PREPARATION_LOG_COLS].fillna("")


# =========================================================
# ⌨️ タイピング5分チェック（d296）
# ---------------------------------------------------------
# 出席登録済みの生徒を対象に、5分タイピングを実施したかを記録する。
# 先生の記憶に頼らず、未完了の子が画面に残るようにする。
# =========================================================
TYPING_LOG_COLS = ["date", "student_id", "status", "completed_at", "note"]


def load_typing_log() -> pd.DataFrame:
    if TYPING_LOG_CSV.exists():
        try:
            df = pd.read_csv(TYPING_LOG_CSV, dtype=str).fillna("")
        except Exception:
            df = pd.DataFrame(columns=TYPING_LOG_COLS)
    else:
        df = pd.DataFrame(columns=TYPING_LOG_COLS)
        write_csv_atomic(df, TYPING_LOG_CSV)
        return df

    for c in TYPING_LOG_COLS:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d").fillna(df["date"])

    df["status"] = (
        df["status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )
    return df[TYPING_LOG_COLS].fillna("")


def save_typing_log(df: pd.DataFrame) -> None:
    df2 = df.copy() if df is not None else pd.DataFrame(columns=TYPING_LOG_COLS)
    for c in TYPING_LOG_COLS:
        if c not in df2.columns:
            df2[c] = ""
        df2[c] = df2[c].fillna("").astype(str).str.strip()
    write_csv_atomic(df2[TYPING_LOG_COLS].fillna(""), TYPING_LOG_CSV)


def get_typing_today(df: pd.DataFrame, student_id: str, d: date) -> dict | None:
    if df is None or df.empty:
        return None

    sid = str(student_id).strip()
    ds = str(d)

    tmp = df.copy()
    for c in TYPING_LOG_COLS:
        if c not in tmp.columns:
            tmp[c] = ""
        tmp[c] = tmp[c].fillna("").astype(str).str.strip()

    hit = tmp[
        tmp["student_id"].astype(str).str.strip().eq(sid)
        & tmp["date"].astype(str).str.strip().eq(ds)
    ].copy()

    if hit.empty:
        return None

    return hit.iloc[-1].to_dict()


def upsert_typing_log(
    df: pd.DataFrame,
    student_id: str,
    d: date,
    status: str,
    note: str = "",
) -> pd.DataFrame:
    sid = str(student_id).strip()
    ds = str(d)
    status = str(status).strip().lower()
    note = str(note).strip()

    if status not in ["done", "skip"]:
        status = "done"

    df2 = df.copy() if df is not None else pd.DataFrame(columns=TYPING_LOG_COLS)
    for c in TYPING_LOG_COLS:
        if c not in df2.columns:
            df2[c] = ""
        df2[c] = df2[c].fillna("").astype(str).str.strip()

    if not df2.empty:
        mask = (
            df2["student_id"].astype(str).str.strip().eq(sid)
            & df2["date"].astype(str).str.strip().eq(ds)
        )
        df2 = df2.loc[~mask].copy()

    new_row = {
        "date": ds,
        "student_id": sid,
        "status": status,
        "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
    }

    return pd.concat([df2, pd.DataFrame([new_row])], ignore_index=True)


def delete_typing_log(df: pd.DataFrame, student_id: str, d: date) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=TYPING_LOG_COLS)

    sid = str(student_id).strip()
    ds = str(d)

    df2 = df.copy()
    for c in TYPING_LOG_COLS:
        if c not in df2.columns:
            df2[c] = ""
        df2[c] = df2[c].fillna("").astype(str).str.strip()

    mask = (
        df2["student_id"].astype(str).str.strip().eq(sid)
        & df2["date"].astype(str).str.strip().eq(ds)
    )
    return df2.loc[~mask].copy()


def typing_status_label(status: str) -> str:
    s = str(status).strip().lower()
    if s == "done":
        return "✅ 完了"
    if s == "skip":
        return "⚪ 免除"
    return "未完了"


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


def is_progress_done_on_or_after(progress_df: pd.DataFrame, student_id: str, d: date) -> bool:
    """昨日以前の未完了用。

    カリキュラム進捗を翌日以降に登録した場合でも、
    対象日以降の done_date があれば「進捗対応済み」とみなす。
    今日の未完了判定は従来通り is_progress_done_today() を使う。
    """
    if progress_df is None or progress_df.empty:
        return False

    sid = str(student_id).strip()
    target_dt = pd.to_datetime(d, errors="coerce")
    if pd.isna(target_dt):
        return False

    tmp = progress_df.copy()
    if "student_id" not in tmp.columns:
        return False

    tmp["student_id"] = tmp["student_id"].astype(str).fillna("").str.strip()
    tmp = tmp[tmp["student_id"].eq(sid)].copy()
    if tmp.empty:
        return False

    # done_date を優先
    if "done_date" in tmp.columns:
        tmp["done_date_dt"] = pd.to_datetime(tmp["done_date"], errors="coerce")
        if bool((tmp["done_date_dt"] >= target_dt.normalize()).any()):
            return True

    # date 列運用なら保険で対応
    if "date" in tmp.columns:
        tmp["date_dt"] = pd.to_datetime(tmp["date"], errors="coerce")
        if bool((tmp["date_dt"] >= target_dt.normalize()).any()):
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

# [STEP 2026-05] 月単位で確定した予定を保存するCSV（固定スケジュールと当日例外の間の層）
MONTHLY_SCHEDULE_CSV = DATA_DIR / "monthly_schedule.csv"

CURRICULUM_COURSES_CSV = DATA_DIR / "curriculum_courses.csv"
CURRICULUM_TASKS_CSV = DATA_DIR / "curriculum_tasks.csv"
CURRICULUM_PROGRESS_CSV = DATA_DIR / "curriculum_progress.csv"

KENTEI_TASKS_CSV = DATA_DIR / "kentei_tasks.csv"
KENTEI_PROGRESS_CSV = DATA_DIR / "kentei_progress.csv"

# Optional (if exists): upcoming exams
KENTEI_EXAM_SCHEDULE_CSV = DATA_DIR / "kentei_exam_schedule.csv"

# d250:
# 検定練習中フラグ。
# 検定予定が未登録でも「今は検定課題を優先する」生徒を明示できるようにする。
KENTEI_TRAINING_STATUS_CSV = DATA_DIR / "kentei_training_status.csv"

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


# d318: 固定スケジュールの月内週指定
WEEK_PATTERN_OPTIONS = [
    "毎週",
    "第1・第3",
    "第2・第4",
    "第1",
    "第2",
    "第3",
    "第4",
    "第5",
]

WEEK_PATTERN_TO_NUMBERS = {
    "毎週": {1, 2, 3, 4, 5},
    "第1・第3": {1, 3},
    "第2・第4": {2, 4},
    "第1": {1},
    "第2": {2},
    "第3": {3},
    "第4": {4},
    "第5": {5},
}


def normalize_week_pattern(value) -> str:
    """空欄・旧データは毎週として扱う。"""
    s = str(value).strip() if value is not None else ""
    aliases = {
        "": "毎週",
        "全週": "毎週",
        "毎月毎週": "毎週",
        "1・3": "第1・第3",
        "1,3": "第1・第3",
        "第1第3": "第1・第3",
        "2・4": "第2・第4",
        "2,4": "第2・第4",
        "第2第4": "第2・第4",
    }
    s = aliases.get(s, s)
    return s if s in WEEK_PATTERN_TO_NUMBERS else "毎週"


def week_of_month(d) -> int:
    """日付が、その月の第何週に当たるか（1～5）を返す。"""
    try:
        day_num = int(getattr(d, "day"))
    except Exception:
        parsed = pd.to_datetime(d, errors="coerce")
        if pd.isna(parsed):
            return 0
        day_num = int(parsed.day)
    return ((day_num - 1) // 7) + 1


def matches_week_pattern(d, pattern) -> bool:
    """固定スケジュールの週指定に対象日が一致するか。"""
    normalized = normalize_week_pattern(pattern)
    return week_of_month(d) in WEEK_PATTERN_TO_NUMBERS.get(
        normalized,
        WEEK_PATTERN_TO_NUMBERS["毎週"],
    )


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
@st.cache_data(show_spinner=False)
def _read_csv_cached_core(
    path_str: str,
    encoding: str,
    mtime_ns: int,
    size: int,
) -> pd.DataFrame:
    """d298: CSV読み込みをキャッシュする内部関数。

    mtime_ns と size を引数に含めることで、ファイル更新時は自然に再読込する。
    """
    path = Path(path_str)
    try:
        return pd.read_csv(path, encoding=encoding)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp932")


def clear_csv_cache() -> None:
    """d298: CSV保存後に古い読み込みキャッシュを残さないためのクリア処理。"""
    try:
        _read_csv_cached_core.clear()
    except Exception:
        try:
            st.cache_data.clear()
        except Exception:
            pass


def safe_read_csv(
    path,
    required_cols=None,
    *,
    stop_on_missing: bool = False,
    show_message: bool = True,
    encoding: str = "utf-8",
) -> pd.DataFrame:
    """CSVを安全に読み込むヘルパー。

    d298:
    - Streamlitはボタン操作のたびに全体を再実行するため、CSV読み込みをキャッシュする。
    - ファイルの更新時刻とサイズが変わると自動で読み直す。
    - 保存時は write_csv / write_csv_atomic 側でキャッシュをクリアする。
    """
    path = Path(path)

    if not path.exists():
        if show_message:
            st.warning(f"CSVが見つかりません: {path}")
        return pd.DataFrame()

    try:
        stat = path.stat()
        df = _read_csv_cached_core(
            str(path),
            encoding,
            int(stat.st_mtime_ns),
            int(stat.st_size),
        ).copy()
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


def build_daily_plan_for_date(
    target_date,
    students_df: pd.DataFrame,
    student_schedule_df: pd.DataFrame,
    monthly_schedule_df: pd.DataFrame,
    schedule_overrides_df: pd.DataFrame,
    timeslots_df: pd.DataFrame,
    *,
    include_inactive: bool = False,
) -> pd.DataFrame:
    """
    date × student_id × slot の予定を1か所で作る共通関数。

    優先順位：
    1. monthly_schedule.csv に対象日の予定があれば、それをベースにする
    2. 対象日の月スケジュールが無い場合だけ、student_schedule.csv（固定週次）を使う
    3. schedule_overrides.csv の追加・キャンセル・時間変更を重ねる

    閲覧の今日の予定、未完了タスク、座席表が別々の予定ソースを見て
    食い違わないようにするための安全化。
    """
    weekday_map_local = ["月", "火", "水", "木", "金", "土", "日"]

    if isinstance(target_date, str):
        target_dt = pd.to_datetime(target_date, errors="coerce")
        if pd.isna(target_dt):
            return pd.DataFrame(columns=["date", "student_id", "weekday", "slot", "session_type", "start", "end", "display_name"])
        target_date_obj = target_dt.date()
    else:
        target_date_obj = target_date

    target_str = target_date_obj.strftime("%Y-%m-%d")
    target_wd = weekday_map_local[target_date_obj.weekday()]

    # 生徒マスタ（在籍中だけを基本にする）
    base_students = students_df.copy() if students_df is not None else pd.DataFrame()
    for c in ["student_id", "display_name", "grade", "number_of_times", "join_date", "is_active"]:
        if c not in base_students.columns:
            base_students[c] = ""
    base_students["student_id"] = base_students["student_id"].fillna("").astype(str).str.strip()
    base_students["display_name"] = base_students["display_name"].fillna("").astype(str).str.strip()

    if not include_inactive and "is_active" in base_students.columns:
        base_students = base_students[
            base_students["is_active"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .replace("", "true")
            .isin(["true", "1", "yes"])
        ].copy()

    active_ids = set(base_students["student_id"].astype(str).str.strip())

    # コマ時刻
    ts = timeslots_df.copy() if timeslots_df is not None else pd.DataFrame()
    for c in ["weekday", "slot", "start", "end"]:
        if c not in ts.columns:
            ts[c] = ""
        ts[c] = ts[c].fillna("").astype(str).str.strip()
    if not ts.empty:
        ts["slot"] = ts["slot"].map(normalize_slot)
        ts = ts.drop_duplicates(subset=["weekday", "slot"], keep="first")

    # まず月スケジュールを確認
    monthly = monthly_schedule_df.copy() if monthly_schedule_df is not None else pd.DataFrame()
    for c in ["date", "student_id", "slot", "session_type", "reason", "note", "source"]:
        if c not in monthly.columns:
            monthly[c] = ""
        monthly[c] = monthly[c].fillna("").astype(str).str.strip()

    if not monthly.empty:
        _monthly_date_raw = monthly["date"].fillna("").astype(str).str.strip()
        _monthly_date_norm = pd.to_datetime(_monthly_date_raw, errors="coerce").dt.strftime("%Y-%m-%d")
        monthly["date"] = _monthly_date_norm.fillna(_monthly_date_raw)

    monthly_day = monthly[monthly["date"] == target_str].copy() if not monthly.empty else pd.DataFrame()

    if not monthly_day.empty:
        plan = monthly_day.copy()
        plan["weekday"] = target_wd
        plan["slot"] = plan["slot"].map(normalize_slot)
        plan["session_type"] = plan["session_type"].replace("", "授業").fillna("授業")
        plan["date"] = target_str
    else:
        sched = student_schedule_df.copy() if student_schedule_df is not None else pd.DataFrame()
        for c in ["student_id", "weekday", "slot", "session_type"]:
            if c not in sched.columns:
                sched[c] = ""
            sched[c] = sched[c].fillna("").astype(str).str.strip()
        if sched.empty:
            plan = pd.DataFrame(columns=["date", "student_id", "weekday", "slot", "session_type", "note"])
        else:
            sched["slot"] = sched["slot"].map(normalize_slot)
            plan = sched[sched["weekday"] == target_wd].copy()
            plan["date"] = target_str
            if "note" not in plan.columns:
                plan["note"] = ""

    if not plan.empty:
        plan["student_id"] = plan["student_id"].fillna("").astype(str).str.strip()
        plan["slot"] = plan["slot"].fillna("").astype(str).str.strip().map(normalize_slot)
        plan = plan[(plan["student_id"] != "") & (plan["slot"] != "")].copy()
        if active_ids:
            plan = plan[plan["student_id"].isin(active_ids)].copy()
        plan = plan.drop_duplicates(subset=["student_id", "date", "slot"], keep="last")

    # 生徒情報を付ける
    student_cols = ["student_id", "display_name", "grade", "number_of_times", "join_date"]
    if not plan.empty:
        plan = plan.merge(base_students[student_cols], on="student_id", how="inner")
        if not ts.empty:
            plan = plan.merge(ts, on=["weekday", "slot"], how="left")
        else:
            plan["start"] = ""
            plan["end"] = ""
    else:
        plan = pd.DataFrame(columns=["date", "student_id", "weekday", "slot", "session_type", "display_name", "grade", "number_of_times", "join_date", "start", "end", "note"])

    # 日付例外を重ねる
    ov = schedule_overrides_df.copy() if schedule_overrides_df is not None else pd.DataFrame()
    for c in ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]:
        if c not in ov.columns:
            ov[c] = ""
        ov[c] = ov[c].fillna("").astype(str).str.strip()

    if not ov.empty:
        _ov_date_raw = ov["date"].fillna("").astype(str).str.strip()
        _ov_date_norm = pd.to_datetime(_ov_date_raw, errors="coerce").dt.strftime("%Y-%m-%d")
        ov["date"] = _ov_date_norm.fillna(_ov_date_raw)
        ov["slot"] = ov["slot"].map(normalize_slot)
        ov["action_norm"] = ov["action"].map(normalize_action_value)
        ov_day = ov[ov["date"] == target_str].copy()
    else:
        ov_day = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note", "action_norm"])

    if not ov_day.empty:
        # 追加・時間変更を先に反映し、最後にキャンセルを勝たせる。
        # d201ではキャンセル後に追加を足していたため、追加予定を後からキャンセルしにくかった。
        add_change_df = ov_day[ov_day["action_norm"].isin(["追加", "時間変更"])].copy()
        if not add_change_df.empty:
            add_change_df["student_id"] = add_change_df["student_id"].astype(str).str.strip()
            add_change_df["slot"] = add_change_df["slot"].map(normalize_slot)
            add_change_df = add_change_df[(add_change_df["student_id"] != "") & (add_change_df["slot"] != "")].copy()
            if active_ids:
                add_change_df = add_change_df[add_change_df["student_id"].isin(active_ids)].copy()

            if not add_change_df.empty:
                existing_student_ids = set()
                if not plan.empty and "student_id" in plan.columns:
                    existing_student_ids = set(plan["student_id"].astype(str).str.strip())

                # 「追加」でも、対象日に既存予定がある生徒は時間変更扱いにする。
                # 通常予定 + 当日追加が二重表示・二重カウントになる事故を防ぐため。
                note_for_extra = add_change_df.get("note", pd.Series([""] * len(add_change_df), index=add_change_df.index)).fillna("").astype(str)
                explicit_extra_mask = note_for_extra.str.contains("特別追加|追加で受講|2時間|連続", regex=True, na=False)
                implicit_change_mask = (
                    (add_change_df["action_norm"] == "追加")
                    & (add_change_df["student_id"].isin(existing_student_ids))
                    & (~explicit_extra_mask)
                )
                add_change_df.loc[implicit_change_mask, "action_norm"] = "時間変更"
                add_change_df.loc[implicit_change_mask, "action"] = "時間変更"
                add_change_df.loc[implicit_change_mask, "note"] = (
                    add_change_df.loc[implicit_change_mask, "note"].fillna("").astype(str).str.strip()
                    .apply(lambda x: (x + " / " if x else "") + "追加登録を時間変更として処理")
                )

                change_df = add_change_df[add_change_df["action_norm"] == "時間変更"].copy()
                add_df = add_change_df[add_change_df["action_norm"] == "追加"].copy()

                # 時間変更：その日のその生徒の既存予定を丸ごと置き換える
                if not change_df.empty and not plan.empty:
                    change_sids = set(change_df["student_id"].astype(str).str.strip())
                    plan = plan[~plan["student_id"].astype(str).str.strip().isin(change_sids)].copy()

                # 追加：同じ student_id × slot だけ置き換える
                if not add_df.empty and not plan.empty:
                    add_keys = set(zip(add_df["student_id"].astype(str).str.strip(), add_df["slot"].map(normalize_slot)))
                    plan["student_id_key"] = plan["student_id"].astype(str).str.strip()
                    plan["slot_key"] = plan["slot"].map(normalize_slot)
                    plan = plan[
                        ~plan.apply(lambda r: (r.get("student_id_key", ""), r.get("slot_key", "")) in add_keys, axis=1)
                    ].copy()
                    plan = plan.drop(columns=["student_id_key", "slot_key"], errors="ignore")

                add_view = pd.concat([change_df, add_df], ignore_index=True)
                if not add_view.empty:
                    add_view["weekday"] = target_wd
                    add_view["date"] = target_str
                    add_view["session_type"] = add_view["session_type"].replace("", "授業").fillna("授業")
                    add_view["reason"] = add_view["action_norm"].map({"時間変更": "時間変更", "追加": "当日追加"}).fillna("")
                    add_view["source"] = "schedule_overrides"

                    if not ts.empty:
                        add_view = add_view.merge(ts, on=["weekday", "slot"], how="left", suffixes=("", "_ts"))
                        for _c in ["start", "end"]:
                            if _c not in add_view.columns:
                                add_view[_c] = ""
                            add_view[_c] = add_view[_c].replace("", pd.NA)
                            add_view[_c] = add_view[_c].fillna(add_view.get(f"{_c}_ts", ""))
                        add_view = add_view.drop(columns=[c for c in ["start_ts", "end_ts"] if c in add_view.columns], errors="ignore")
                    else:
                        for _c in ["start", "end"]:
                            if _c not in add_view.columns:
                                add_view[_c] = ""

                    add_view = add_view.merge(base_students[student_cols], on="student_id", how="inner")
                    for _c in ["reason", "source"]:
                        if _c not in add_view.columns:
                            add_view[_c] = ""
                    plan = pd.concat([plan, add_view], ignore_index=True)

        # キャンセル：最後に反映する。同じ student_id × slot は最終的に消す。
        cancel_df = ov_day[ov_day["action_norm"] == "キャンセル"].copy()
        if not cancel_df.empty and not plan.empty:
            cancel_keys = set(zip(cancel_df["student_id"].astype(str).str.strip(), cancel_df["slot"].map(normalize_slot)))
            plan["student_id_key"] = plan["student_id"].astype(str).str.strip()
            plan["slot_key"] = plan["slot"].map(normalize_slot)
            plan = plan[
                ~plan.apply(lambda r: (r.get("student_id_key", ""), r.get("slot_key", "")) in cancel_keys, axis=1)
            ].copy()
            plan = plan.drop(columns=["student_id_key", "slot_key"], errors="ignore")

    for c in ["date", "student_id", "weekday", "slot", "session_type", "display_name", "grade", "number_of_times", "join_date", "start", "end", "note"]:
        if c not in plan.columns:
            plan[c] = ""
        plan[c] = plan[c].fillna("").astype(str).str.strip()

    if not plan.empty:
        plan["slot"] = plan["slot"].map(normalize_slot)
        plan = plan.drop_duplicates(subset=["student_id", "date", "slot"], keep="last")

    return plan

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
    if str(v).strip().lower() in ["self", "selfstudy", "自習"]:
        return "(自)"
    return ""


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def write_csv_atomic(df: pd.DataFrame, path: Path) -> None:
    # path は str で渡されることもあるので Path に正規化
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(path)
    clear_csv_cache()



# =========================================================
# 🧩 サブ課題管理（d287 試作版）
# =========================================================
SUB_CURRICULA_CSV = DATA_DIR / "sub_curricula.csv"
SUB_CURRICULUM_ITEMS_CSV = DATA_DIR / "sub_curriculum_items.csv"
STUDENT_SUB_PROGRESS_CSV = DATA_DIR / "student_sub_progress.csv"
SUB_PROGRESS_LOG_CSV = DATA_DIR / "sub_progress_log.csv"

# d300:
# 出席した日にサブ課題の完了確認を押し忘れても、翌日以降に残る日別確認ログ。
SUB_DAILY_CHECK_CSV = DATA_DIR / "sub_daily_check.csv"

SUB_CURRICULA_COLS = [
    "sub_id", "sub_name", "main_course_id",
    "is_active", "note", "created_at", "updated_at"
]
SUB_CURRICULUM_ITEMS_COLS = [
    "sub_id", "item_id", "item_name", "order", "is_active", "created_at", "updated_at"
]
STUDENT_SUB_PROGRESS_COLS = [
    "student_id", "sub_id", "current_item_id", "is_active", "updated_at", "note"
]
SUB_PROGRESS_LOG_COLS = [
    "student_id", "sub_id", "item_id", "completed_at", "note"
]
SUB_DAILY_CHECK_COLS = [
    "date", "student_id", "sub_id", "item_id",
    "status", "checked_at", "note"
]


def _load_or_empty_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    """サブ課題CSVを安全に読み込む。未作成時は空の表を返す。"""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=columns)

    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame(columns=columns)

    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns].fillna("")


def _save_sub_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df2 = df.copy() if df is not None else pd.DataFrame(columns=columns)
    for c in columns:
        if c not in df2.columns:
            df2[c] = ""
    write_csv_atomic(df2[columns].fillna(""), path)


def load_sub_curricula() -> pd.DataFrame:
    return _load_or_empty_csv(SUB_CURRICULA_CSV, SUB_CURRICULA_COLS)


def save_sub_curricula(df: pd.DataFrame) -> None:
    _save_sub_csv(df, SUB_CURRICULA_CSV, SUB_CURRICULA_COLS)


def load_sub_curriculum_items() -> pd.DataFrame:
    return _load_or_empty_csv(SUB_CURRICULUM_ITEMS_CSV, SUB_CURRICULUM_ITEMS_COLS)


def save_sub_curriculum_items(df: pd.DataFrame) -> None:
    _save_sub_csv(df, SUB_CURRICULUM_ITEMS_CSV, SUB_CURRICULUM_ITEMS_COLS)


def load_student_sub_progress() -> pd.DataFrame:
    return _load_or_empty_csv(STUDENT_SUB_PROGRESS_CSV, STUDENT_SUB_PROGRESS_COLS)


def save_student_sub_progress(df: pd.DataFrame) -> None:
    _save_sub_csv(df, STUDENT_SUB_PROGRESS_CSV, STUDENT_SUB_PROGRESS_COLS)


def load_sub_progress_log() -> pd.DataFrame:
    return _load_or_empty_csv(SUB_PROGRESS_LOG_CSV, SUB_PROGRESS_LOG_COLS)


def save_sub_progress_log(df: pd.DataFrame) -> None:
    _save_sub_csv(df, SUB_PROGRESS_LOG_CSV, SUB_PROGRESS_LOG_COLS)


def load_sub_daily_check() -> pd.DataFrame:
    return _load_or_empty_csv(SUB_DAILY_CHECK_CSV, SUB_DAILY_CHECK_COLS)


def save_sub_daily_check(df: pd.DataFrame) -> None:
    _save_sub_csv(df, SUB_DAILY_CHECK_CSV, SUB_DAILY_CHECK_COLS)


def _sub_check_date_str(d) -> str:
    ts = pd.to_datetime(d, errors="coerce")
    if pd.isna(ts):
        return str(d).strip()
    return ts.strftime("%Y-%m-%d")


def _active_sub_snapshot(student_id: str) -> dict:
    """進行中サブ課題の現在位置を日別確認用に返す。"""
    sid = str(student_id).strip()
    state = {
        "student_id": sid,
        "sub_id": "",
        "item_id": "",
        "is_active": False,
    }
    if not sid:
        return state

    progress = load_student_sub_progress()
    if progress.empty:
        return state

    hit = progress[
        progress["student_id"].astype(str).str.strip().eq(sid)
    ].copy()
    if hit.empty:
        return state

    row = hit.iloc[-1]
    state["sub_id"] = str(row.get("sub_id", "")).strip()
    state["item_id"] = str(row.get("current_item_id", "")).strip()
    state["is_active"] = (
        str(row.get("is_active", "")).strip().lower()
        in ["true", "1", "yes", "on"]
    )
    return state


def get_sub_daily_check_row(student_id: str, d) -> dict:
    """date×student_id の日別確認を1件返す。"""
    sid = str(student_id).strip()
    dstr = _sub_check_date_str(d)
    df = load_sub_daily_check()
    if df.empty:
        return {}

    hit = df[
        df["date"].astype(str).str.strip().eq(dstr)
        & df["student_id"].astype(str).str.strip().eq(sid)
    ].copy()
    if hit.empty:
        return {}
    return hit.iloc[-1].to_dict()


def upsert_sub_daily_check(
    student_id: str,
    d,
    status: str,
    *,
    sub_id: str = "",
    item_id: str = "",
    note: str = "",
) -> None:
    """サブ課題の日別確認を date×student_id で1件保存する。"""
    sid = str(student_id).strip()
    dstr = _sub_check_date_str(d)
    status_norm = str(status).strip().lower()
    if status_norm not in ["pending", "done", "skip"]:
        status_norm = "pending"

    snapshot = _active_sub_snapshot(sid)
    sub_id = str(sub_id).strip() or str(snapshot.get("sub_id", "")).strip()
    item_id = str(item_id).strip() or str(snapshot.get("item_id", "")).strip()

    df = load_sub_daily_check()
    if df.empty:
        df = pd.DataFrame(columns=SUB_DAILY_CHECK_COLS)

    mask = (
        df["date"].astype(str).str.strip().eq(dstr)
        & df["student_id"].astype(str).str.strip().eq(sid)
    )
    df = df[~mask].copy()

    row = {
        "date": dstr,
        "student_id": sid,
        "sub_id": sub_id,
        "item_id": item_id,
        "status": status_norm,
        "checked_at": (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if status_norm in ["done", "skip"]
            else ""
        ),
        "note": str(note).strip(),
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_sub_daily_check(df)


def _completion_exists_for_sub_check(
    log_df: pd.DataFrame,
    *,
    student_id: str,
    d,
    sub_id: str = "",
    item_id: str = "",
) -> bool:
    """指定日に対応するサブ課題完了ログがあるか確認する。"""
    if log_df is None or log_df.empty:
        return False

    sid = str(student_id).strip()
    dstr = _sub_check_date_str(d)
    df = log_df.copy()
    for c in ["student_id", "sub_id", "item_id", "completed_at"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    completed_date = pd.to_datetime(
        df["completed_at"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    mask = (
        df["student_id"].eq(sid)
        & completed_date.eq(dstr)
    )
    if str(sub_id).strip():
        mask = mask & df["sub_id"].eq(str(sub_id).strip())
    if str(item_id).strip():
        mask = mask & df["item_id"].eq(str(item_id).strip())
    return bool(mask.any())


def sync_sub_daily_pending_for_date(
    attendance_df: pd.DataFrame,
    d,
) -> int:
    """出席済み＋進行中サブ課題の生徒へ、未確認行を自動作成する。

    完了ログが同日に存在する場合は、自動的にdoneへ合わせる。
    過去日を一括生成せず、対象日だけを同期するため、導入前の誤警告を防ぐ。
    """
    dstr = _sub_check_date_str(d)
    if attendance_df is None or attendance_df.empty:
        return 0

    att = attendance_df.copy()
    for c in ["date", "student_id", "kind"]:
        if c not in att.columns:
            att[c] = ""
        att[c] = att[c].fillna("").astype(str).str.strip()

    att["kind_norm"] = att["kind"].map(normalize_attendance_kind_for_lock)
    attended_ids = (
        att[
            att["date"].eq(dstr)
            & att["kind_norm"].isin(["lesson", "selfstudy"])
        ]["student_id"]
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )
    if not attended_ids:
        return 0

    checks = load_sub_daily_check()
    if checks.empty:
        checks = pd.DataFrame(columns=SUB_DAILY_CHECK_COLS)

    completion_log = load_sub_progress_log()
    changed = False

    for sid in attended_ids:
        snapshot = _active_sub_snapshot(sid)
        if (
            not snapshot.get("is_active")
            or not str(snapshot.get("sub_id", "")).strip()
            or not str(snapshot.get("item_id", "")).strip()
        ):
            continue

        mask = (
            checks["date"].astype(str).str.strip().eq(dstr)
            & checks["student_id"].astype(str).str.strip().eq(sid)
        )
        if mask.any():
            idx = checks[mask].index[-1]
            existing_status = str(checks.loc[idx, "status"]).strip().lower()
            if (
                existing_status == "pending"
                and _completion_exists_for_sub_check(
                    completion_log,
                    student_id=sid,
                    d=dstr,
                    sub_id=str(checks.loc[idx, "sub_id"]).strip(),
                    item_id=str(checks.loc[idx, "item_id"]).strip(),
                )
            ):
                checks.loc[idx, "status"] = "done"
                checks.loc[idx, "checked_at"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                checks.loc[idx, "note"] = "完了ログから自動確認"
                changed = True
            continue

        completed = _completion_exists_for_sub_check(
            completion_log,
            student_id=sid,
            d=dstr,
            sub_id=str(snapshot.get("sub_id", "")).strip(),
            item_id=str(snapshot.get("item_id", "")).strip(),
        )
        checks = pd.concat(
            [
                checks,
                pd.DataFrame([{
                    "date": dstr,
                    "student_id": sid,
                    "sub_id": str(snapshot.get("sub_id", "")).strip(),
                    "item_id": str(snapshot.get("item_id", "")).strip(),
                    "status": "done" if completed else "pending",
                    "checked_at": (
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if completed else ""
                    ),
                    "note": "完了ログから自動確認" if completed else "",
                }]),
            ],
            ignore_index=True,
        )
        changed = True

    if changed:
        save_sub_daily_check(checks)

    latest = load_sub_daily_check()
    if latest.empty:
        return 0
    return int(
        (
            latest["date"].astype(str).str.strip().eq(dstr)
            & latest["status"].astype(str).str.strip().str.lower().eq("pending")
        ).sum()
    )


def complete_and_confirm_sub_daily(
    student_id: str,
    d,
) -> tuple[bool, str]:
    """サブ課題を完了して次へ進め、日別確認もdoneにする。"""
    sid = str(student_id).strip()
    dstr = _sub_check_date_str(d)
    daily_row = get_sub_daily_check_row(sid, dstr)
    snapshot = _active_sub_snapshot(sid)

    if not snapshot.get("is_active"):
        return False, "サブ課題進行中がOFFです。"

    current_sub = str(snapshot.get("sub_id", "")).strip()
    current_item = str(snapshot.get("item_id", "")).strip()
    saved_status = str(daily_row.get("status", "")).strip().lower()
    saved_sub = str(daily_row.get("sub_id", "")).strip()
    saved_item = str(daily_row.get("item_id", "")).strip()

    # 昨日以前の未確認は、当時の項目と現在位置が一致する時だけ自動完了する。
    if (
        daily_row
        and saved_status == "pending"
        and dstr < date.today().isoformat()
        and (saved_sub != current_sub or saved_item != current_item)
    ):
        return (
            False,
            "当時のサブ課題と現在位置が異なるため、自動完了できません。"
            "内容を確認し、必要なら「実施なしで確認」で未確認を閉じてください。",
        )

    before_sub = current_sub
    before_item = current_item
    ok, message = complete_and_advance_student_sub_task(sid)
    if ok:
        upsert_sub_daily_check(
            sid,
            dstr,
            "done",
            sub_id=before_sub,
            item_id=before_item,
            note="サブ課題完了登録",
        )
    return ok, message


def mark_sub_daily_skip(student_id: str, d) -> tuple[bool, str]:
    """対象日はサブ課題を実施しなかったことを確認済みにする。"""
    sid = str(student_id).strip()
    row = get_sub_daily_check_row(sid, d)
    snapshot = _active_sub_snapshot(sid)
    sub_id = str(row.get("sub_id", "")).strip() or str(snapshot.get("sub_id", "")).strip()
    item_id = str(row.get("item_id", "")).strip() or str(snapshot.get("item_id", "")).strip()

    if not sid or not sub_id:
        return False, "サブ課題の設定が見つかりません。"

    upsert_sub_daily_check(
        sid,
        d,
        "skip",
        sub_id=sub_id,
        item_id=item_id,
        note="この日はサブ課題を実施しない",
    )
    return True, "サブ課題を「実施なし」で確認済みにしました。"


def reconcile_sub_daily_after_undo(student_id: str, d) -> None:
    """完了取消後、同日の残り完了ログに合わせて日別確認を再判定する。"""
    sid = str(student_id).strip()
    dstr = _sub_check_date_str(d)
    row = get_sub_daily_check_row(sid, dstr)
    snapshot = _active_sub_snapshot(sid)
    sub_id = str(snapshot.get("sub_id", "")).strip() or str(row.get("sub_id", "")).strip()
    item_id = str(snapshot.get("item_id", "")).strip() or str(row.get("item_id", "")).strip()

    completion_log = load_sub_progress_log()
    if _completion_exists_for_sub_check(
        completion_log,
        student_id=sid,
        d=dstr,
    ):
        upsert_sub_daily_check(
            sid,
            dstr,
            "done",
            sub_id=sub_id,
            item_id=item_id,
            note="残っている完了ログから確認済み",
        )
        return

    att = load_attendance_log()
    attended = False
    if not att.empty:
        att2 = att.copy()
        for c in ["date", "student_id", "kind"]:
            if c not in att2.columns:
                att2[c] = ""
            att2[c] = att2[c].fillna("").astype(str).str.strip()
        att2["kind_norm"] = att2["kind"].map(normalize_attendance_kind_for_lock)
        attended = bool(
            (
                att2["date"].eq(dstr)
                & att2["student_id"].eq(sid)
                & att2["kind_norm"].isin(["lesson", "selfstudy"])
            ).any()
        )

    if attended and snapshot.get("is_active"):
        upsert_sub_daily_check(
            sid,
            dstr,
            "pending",
            sub_id=sub_id,
            item_id=item_id,
            note="完了取消により未確認へ戻す",
        )


def _next_prefixed_id(existing_values, prefix: str, width: int = 3) -> str:
    nums = []
    for raw in pd.Series(existing_values, dtype=str).fillna("").astype(str):
        s = str(raw).strip()
        if s.startswith(prefix) and s[len(prefix):].isdigit():
            nums.append(int(s[len(prefix):]))
    n = max(nums) + 1 if nums else 1
    return f"{prefix}{n:0{width}d}"



def get_main_course_label(course_id: str) -> str:
    """course_idから、画面表示用のコース名を返す。"""
    cid = str(course_id).strip()
    if not cid:
        return "紐づけなし"

    try:
        courses_df = curr_courses.copy()
    except Exception:
        return cid

    if courses_df.empty:
        return cid

    for c in ["course_id", "genre_name", "course_name"]:
        if c not in courses_df.columns:
            courses_df[c] = ""
        courses_df[c] = courses_df[c].fillna("").astype(str).str.strip()

    hit = courses_df[
        courses_df["course_id"].astype(str).str.strip() == cid
    ].copy()
    if hit.empty:
        return f"{cid}（見つかりません）"

    row = hit.iloc[-1]
    genre_name = str(row.get("genre_name", "")).strip()
    course_name = str(row.get("course_name", "")).strip()

    if genre_name and course_name and genre_name != course_name:
        return f"{genre_name} / {course_name}"
    return course_name or genre_name or cid


def get_student_main_course_status(student_id: str, course_id: str) -> dict:
    """生徒とメインコースの進捗を、未着手・進行中・完了で返す。

    完了判定:
      progress_log.csv の note=course_done を正とする。
    進行中判定:
      curriculum_progress.csv に完了またはスキップ済み課題が1件以上ある。
    """
    result = {
        "linked": False,
        "course_exists": False,
        "course_id": str(course_id).strip(),
        "course_name": "紐づけなし",
        "status": "紐づけなし",
        "status_detail": "紐づけなし",
        "completed_count": 0,
        "total_count": 0,
        "all_tasks_finished": False,
    }

    sid = str(student_id).strip()
    cid = str(course_id).strip()
    if not cid:
        return result

    result["linked"] = True
    result["course_name"] = get_main_course_label(cid)

    try:
        courses_df = curr_courses.copy()
    except Exception:
        courses_df = pd.DataFrame()

    if courses_df.empty:
        result["status"] = "コース不明"
        result["status_detail"] = "コース不明"
        return result

    for c in [
        "course_id", "genre_id", "genre_name",
        "course_name", "course_order", "is_active"
    ]:
        if c not in courses_df.columns:
            courses_df[c] = ""
        courses_df[c] = courses_df[c].fillna("").astype(str).str.strip()

    course_hit = courses_df[
        courses_df["course_id"].astype(str).str.strip() == cid
    ].copy()
    if course_hit.empty:
        result["status"] = "コース不明"
        result["status_detail"] = "コース不明"
        return result

    result["course_exists"] = True
    course_row = course_hit.iloc[-1]
    genre_id = str(course_row.get("genre_id", "")).strip()
    course_name = str(course_row.get("course_name", "")).strip()

    # メインコース完了は progress_log.csv の course_done を正とする。
    try:
        log_df = log.copy()
    except Exception:
        log_df = pd.DataFrame()

    is_course_done = False
    if not log_df.empty:
        for c in [
            "student_id", "curriculum", "item",
            "status", "note"
        ]:
            if c not in log_df.columns:
                log_df[c] = ""
            log_df[c] = log_df[c].fillna("").astype(str).str.strip()

        done_mask = (
            log_df["student_id"].astype(str).str.strip().eq(sid)
            & log_df["curriculum"].astype(str).str.strip().eq(genre_id)
            & log_df["item"].astype(str).str.strip().eq(course_name)
            & log_df["status"].astype(str).str.strip().str.lower().eq("done")
            & log_df["note"].astype(str).str.strip().eq("course_done")
        )
        is_course_done = bool(done_mask.any())

    # 対象生徒に適用される、使用中のメイン課題数
    try:
        tasks_df = curr_tasks.copy()
    except Exception:
        tasks_df = pd.DataFrame()

    relevant_task_ids = []
    if not tasks_df.empty:
        for c in [
            "course_id", "task_id", "task_name",
            "order", "is_active", "student_id"
        ]:
            if c not in tasks_df.columns:
                tasks_df[c] = ""
            tasks_df[c] = tasks_df[c].fillna("").astype(str).str.strip()

        active_task_mask = (
            tasks_df["is_active"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .replace("", "true")
            .isin(["true", "1", "yes", "on"])
        )
        applicable_student_mask = (
            tasks_df["student_id"].astype(str).str.strip().eq("")
            | tasks_df["student_id"].astype(str).str.strip().eq(sid)
        )
        relevant_tasks = tasks_df[
            tasks_df["course_id"].astype(str).str.strip().eq(cid)
            & active_task_mask
            & applicable_student_mask
        ].copy()

        relevant_task_ids = (
            relevant_tasks["task_id"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        relevant_task_ids = [
            x for x in relevant_task_ids.tolist() if x
        ]

    result["total_count"] = len(set(relevant_task_ids))

    # 完了またはスキップされた課題数
    try:
        prog_df = curr_prog.copy()
    except Exception:
        prog_df = pd.DataFrame()

    finished_ids = set()
    if not prog_df.empty:
        for c in [
            "student_id", "course_id", "task_id",
            "is_done", "is_skip", "done_date", "note"
        ]:
            if c not in prog_df.columns:
                prog_df[c] = ""
            prog_df[c] = prog_df[c].fillna("").astype(str).str.strip()

        target_prog = prog_df[
            prog_df["student_id"].astype(str).str.strip().eq(sid)
            & prog_df["course_id"].astype(str).str.strip().eq(cid)
        ].copy()

        if not target_prog.empty:
            done_bool = (
                target_prog["is_done"]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["true", "1", "yes", "on"])
            )
            skip_bool = (
                target_prog["is_skip"]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["true", "1", "yes", "on"])
            )
            finished_ids = set(
                target_prog.loc[
                    done_bool | skip_bool, "task_id"
                ].astype(str).str.strip()
            )
            finished_ids.discard("")

    if relevant_task_ids:
        finished_ids = finished_ids.intersection(set(relevant_task_ids))

    completed_count = len(finished_ids)
    total_count = result["total_count"]
    result["completed_count"] = completed_count
    result["all_tasks_finished"] = bool(
        total_count > 0 and completed_count >= total_count
    )

    if is_course_done:
        result["status"] = "完了"
        if total_count > 0:
            result["status_detail"] = f"完了（{completed_count}/{total_count}）"
        else:
            result["status_detail"] = "完了"
    elif result["all_tasks_finished"]:
        result["status"] = "進行中"
        result["status_detail"] = (
            f"進行中（{completed_count}/{total_count}・完了登録待ち）"
        )
    elif completed_count > 0:
        result["status"] = "進行中"
        if total_count > 0:
            result["status_detail"] = f"進行中（{completed_count}/{total_count}）"
        else:
            result["status_detail"] = f"進行中（{completed_count}項目）"
    else:
        result["status"] = "未着手"
        if total_count > 0:
            result["status_detail"] = f"未着手（0/{total_count}）"
        else:
            result["status_detail"] = "未着手"

    return result


def get_sub_main_course_id(sub_id: str) -> str:
    """サブ課題に紐づくメインコースIDを返す。"""
    sid = str(sub_id).strip()
    if not sid:
        return ""

    masters = load_sub_curricula()
    if masters.empty:
        return ""

    hit = masters[
        masters["sub_id"].astype(str).str.strip() == sid
    ].copy()
    if hit.empty:
        return ""

    return str(hit.iloc[-1].get("main_course_id", "")).strip()


def upsert_student_sub_progress(
    student_id: str,
    sub_id: str,
    current_item_id: str,
    is_active: bool,
    note: str = "",
) -> None:
    df = load_student_sub_progress()
    sid = str(student_id).strip()

    if not df.empty:
        df = df[df["student_id"].astype(str).str.strip() != sid].copy()

    row = {
        "student_id": sid,
        "sub_id": str(sub_id).strip(),
        "current_item_id": str(current_item_id).strip(),
        "is_active": "true" if is_active else "false",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": str(note).strip(),
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_student_sub_progress(df)



def complete_and_advance_student_sub_task(student_id: str) -> tuple[bool, str]:
    """現在のサブ課題を完了記録し、次の項目へ進める。

    最後の項目を完了した場合は、サブ課題進行中をOFFにする。
    """
    try:
        sid = str(student_id).strip()
        if not sid:
            return False, "生徒IDが見つかりません。"

        progress = load_student_sub_progress()
        if progress.empty:
            return False, "サブ課題の設定がありません。"

        row_df = progress[
            progress["student_id"].astype(str).str.strip() == sid
        ].copy()
        if row_df.empty:
            return False, "サブ課題の設定がありません。"

        row = row_df.iloc[-1]
        active = str(row.get("is_active", "")).strip().lower()
        if active not in ["true", "1", "yes", "on"]:
            return False, "サブ課題進行中がOFFです。"

        sub_id = str(row.get("sub_id", "")).strip()
        current_item_id = str(row.get("current_item_id", "")).strip()
        note = str(row.get("note", "")).strip()

        if not sub_id or not current_item_id:
            return False, "現在のサブ課題または項目が設定されていません。"

        masters = load_sub_curricula()
        items = load_sub_curriculum_items()

        sub_name = sub_id
        if not masters.empty:
            master_hit = masters[
                masters["sub_id"].astype(str).str.strip() == sub_id
            ].copy()
            if not master_hit.empty:
                sub_name = (
                    str(master_hit.iloc[-1].get("sub_name", "")).strip()
                    or sub_id
                )

        sub_items = items[
            items["sub_id"].astype(str).str.strip() == sub_id
        ].copy() if not items.empty else pd.DataFrame()

        if sub_items.empty:
            return False, f"{sub_name}に項目が登録されていません。"

        active_mask = (
            sub_items["is_active"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .replace("", "true")
            .isin(["true", "1", "yes", "on"])
        )
        sub_items = sub_items[active_mask].copy()
        sub_items["_order_num"] = pd.to_numeric(
            sub_items["order"], errors="coerce"
        ).fillna(9999)
        sub_items = sub_items.sort_values(
            ["_order_num", "item_name"], na_position="last"
        ).reset_index(drop=True)

        current_matches = sub_items.index[
            sub_items["item_id"].astype(str).str.strip() == current_item_id
        ].tolist()
        if not current_matches:
            return False, "現在の項目がサブ課題一覧に見つかりません。"

        current_index = int(current_matches[0])
        current_name = (
            str(sub_items.iloc[current_index].get("item_name", "")).strip()
            or current_item_id
        )

        # 完了履歴を保存。同じ項目の二重登録は避ける。
        log_df = load_sub_progress_log()
        duplicate = False
        if not log_df.empty:
            duplicate = bool(
                (
                    log_df["student_id"].astype(str).str.strip().eq(sid)
                    & log_df["sub_id"].astype(str).str.strip().eq(sub_id)
                    & log_df["item_id"].astype(str).str.strip().eq(current_item_id)
                ).any()
            )

        if not duplicate:
            log_row = {
                "student_id": sid,
                "sub_id": sub_id,
                "item_id": current_item_id,
                "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": "",
            }
            log_df = pd.concat(
                [log_df, pd.DataFrame([log_row])],
                ignore_index=True,
            )
            save_sub_progress_log(log_df)

        # 次の項目があれば進める。
        if current_index + 1 < len(sub_items):
            next_row = sub_items.iloc[current_index + 1]
            next_item_id = str(next_row.get("item_id", "")).strip()
            next_item_name = (
                str(next_row.get("item_name", "")).strip()
                or next_item_id
            )
            upsert_student_sub_progress(
                sid,
                sub_id,
                next_item_id,
                True,
                note,
            )
            return (
                True,
                f"{current_name}を完了しました。次は「{next_item_name}」です。",
            )

        # 最後の項目なら、現在位置を残したまま進行中をOFFにする。
        upsert_student_sub_progress(
            sid,
            sub_id,
            current_item_id,
            False,
            note,
        )
        return (
            True,
            f"{current_name}を完了しました。{sub_name}は最後まで完了したため停止しました。",
        )

    except Exception as e:
        return False, f"サブ課題の更新でエラーが発生しました：{e}"



def get_student_sub_ui_state(student_id: str) -> dict:
    """閲覧画面用に、サブ課題の現在位置・本日の登録・直前の完了をまとめる。"""
    state = {
        "configured": False,
        "is_active": False,
        "sub_id": "",
        "sub_name": "",
        "current_item_id": "",
        "current_item_name": "",
        "today_count": 0,
        "today_item_names": [],
        "latest_item_id": "",
        "latest_item_name": "",
        "latest_completed_at": "",
        "has_latest_completion": False,
    }

    try:
        sid = str(student_id).strip()
        if not sid:
            return state

        progress = load_student_sub_progress()
        if progress.empty:
            return state

        hit = progress[
            progress["student_id"].astype(str).str.strip() == sid
        ].copy()
        if hit.empty:
            return state

        row = hit.iloc[-1]
        sub_id = str(row.get("sub_id", "")).strip()
        current_item_id = str(row.get("current_item_id", "")).strip()
        if not sub_id:
            return state

        state["configured"] = True
        state["sub_id"] = sub_id
        state["current_item_id"] = current_item_id
        state["is_active"] = (
            str(row.get("is_active", "")).strip().lower()
            in ["true", "1", "yes", "on"]
        )

        masters = load_sub_curricula()
        items = load_sub_curriculum_items()

        sub_name = sub_id
        if not masters.empty:
            master_hit = masters[
                masters["sub_id"].astype(str).str.strip() == sub_id
            ].copy()
            if not master_hit.empty:
                sub_name = (
                    str(master_hit.iloc[-1].get("sub_name", "")).strip()
                    or sub_id
                )
        state["sub_name"] = sub_name

        item_name_map = {}
        if not items.empty:
            item_name_map = dict(
                zip(
                    items["item_id"].astype(str).str.strip(),
                    items["item_name"].astype(str).str.strip(),
                )
            )
        state["current_item_name"] = item_name_map.get(
            current_item_id, current_item_id
        )

        log_df = load_sub_progress_log()
        if log_df.empty:
            return state

        sub_log = log_df[
            (
                log_df["student_id"].astype(str).str.strip() == sid
            )
            & (
                log_df["sub_id"].astype(str).str.strip() == sub_id
            )
        ].copy()
        if sub_log.empty:
            return state

        sub_log["_completed_dt"] = pd.to_datetime(
            sub_log["completed_at"], errors="coerce"
        )
        sub_log["_row_order"] = range(len(sub_log))

        # 本日完了した項目
        today_iso = date.today().isoformat()
        today_log = sub_log[
            sub_log["_completed_dt"].dt.strftime("%Y-%m-%d") == today_iso
        ].copy()
        if not today_log.empty:
            today_log = today_log.sort_values(
                ["_completed_dt", "_row_order"],
                na_position="last",
            )
            today_names = [
                item_name_map.get(str(item_id).strip(), str(item_id).strip())
                for item_id in today_log["item_id"].tolist()
            ]
            state["today_count"] = len(today_names)
            state["today_item_names"] = [x for x in today_names if x]

        # 直前の完了
        valid_log = sub_log[sub_log["_completed_dt"].notna()].copy()
        if not valid_log.empty:
            latest = valid_log.sort_values(
                ["_completed_dt", "_row_order"]
            ).iloc[-1]
        else:
            latest = sub_log.sort_values("_row_order").iloc[-1]

        latest_item_id = str(latest.get("item_id", "")).strip()
        latest_completed_at = str(latest.get("completed_at", "")).strip()
        state["latest_item_id"] = latest_item_id
        state["latest_item_name"] = item_name_map.get(
            latest_item_id, latest_item_id
        )
        state["latest_completed_at"] = latest_completed_at
        state["has_latest_completion"] = bool(latest_item_id)

        return state

    except Exception:
        return state


def undo_latest_student_sub_completion(student_id: str) -> tuple[bool, str]:
    """直前のサブ課題完了を1件削除し、その項目を現在位置へ戻す。"""
    try:
        sid = str(student_id).strip()
        if not sid:
            return False, "生徒IDが見つかりません。"

        progress = load_student_sub_progress()
        if progress.empty:
            return False, "サブ課題の設定がありません。"

        progress_hit = progress[
            progress["student_id"].astype(str).str.strip() == sid
        ].copy()
        if progress_hit.empty:
            return False, "サブ課題の設定がありません。"

        progress_row = progress_hit.iloc[-1]
        sub_id = str(progress_row.get("sub_id", "")).strip()
        note = str(progress_row.get("note", "")).strip()
        if not sub_id:
            return False, "サブ課題が設定されていません。"

        log_df = load_sub_progress_log()
        if log_df.empty:
            return False, "取り消せる完了記録がありません。"

        mask = (
            log_df["student_id"].astype(str).str.strip().eq(sid)
            & log_df["sub_id"].astype(str).str.strip().eq(sub_id)
        )
        sub_log = log_df[mask].copy()
        if sub_log.empty:
            return False, "取り消せる完了記録がありません。"

        sub_log["_completed_dt"] = pd.to_datetime(
            sub_log["completed_at"], errors="coerce"
        )
        sub_log["_row_order"] = range(len(sub_log))

        valid_log = sub_log[sub_log["_completed_dt"].notna()].copy()
        if not valid_log.empty:
            latest_index = valid_log.sort_values(
                ["_completed_dt", "_row_order"]
            ).index[-1]
        else:
            latest_index = sub_log.sort_values("_row_order").index[-1]

        latest_row = log_df.loc[latest_index]
        item_id = str(latest_row.get("item_id", "")).strip()
        completed_at = str(latest_row.get("completed_at", "")).strip()
        if not item_id:
            return False, "直前の完了項目を特定できませんでした。"

        items = load_sub_curriculum_items()
        item_name = item_id
        if not items.empty:
            item_hit = items[
                items["item_id"].astype(str).str.strip() == item_id
            ].copy()
            if not item_hit.empty:
                item_name = (
                    str(item_hit.iloc[-1].get("item_name", "")).strip()
                    or item_id
                )

        # 完了履歴を1件だけ削除
        log_df = log_df.drop(index=latest_index).reset_index(drop=True)
        save_sub_progress_log(log_df)

        # 取り消した項目を再び「次にやる項目」にし、進行中をONへ戻す
        upsert_student_sub_progress(
            sid,
            sub_id,
            item_id,
            True,
            note,
        )

        when = f"（{completed_at}）" if completed_at else ""
        return True, f"「{item_name}」の完了{when}を取り消し、この項目へ戻しました。"

    except Exception as e:
        return False, f"完了の取り消しでエラーが発生しました：{e}"


def get_student_sub_task_hint(student_id: str) -> str:
    """進行中のサブ課題があれば「サブ：教材名 / 次の項目」を返す。"""
    try:
        sid = str(student_id).strip()
        if not sid:
            return ""

        progress = load_student_sub_progress()
        if progress.empty:
            return ""

        row_df = progress[
            progress["student_id"].astype(str).str.strip() == sid
        ].copy()
        if row_df.empty:
            return ""

        row = row_df.iloc[-1]
        active = str(row.get("is_active", "")).strip().lower()
        if active not in ["true", "1", "yes", "on"]:
            return ""

        sub_id = str(row.get("sub_id", "")).strip()
        item_id = str(row.get("current_item_id", "")).strip()
        if not sub_id:
            return ""

        masters = load_sub_curricula()
        items = load_sub_curriculum_items()

        sub_name = sub_id
        if not masters.empty:
            hit = masters[
                masters["sub_id"].astype(str).str.strip() == sub_id
            ].copy()
            if not hit.empty:
                sub_name = str(hit.iloc[-1].get("sub_name", "")).strip() or sub_id

        sub_items = items[
            items["sub_id"].astype(str).str.strip() == sub_id
        ].copy() if not items.empty else pd.DataFrame()

        if sub_items.empty:
            return f"サブ：{sub_name} / 項目未登録"

        active_mask = (
            sub_items["is_active"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .replace("", "true")
            .isin(["true", "1", "yes", "on"])
        )
        sub_items = sub_items[active_mask].copy()
        sub_items["_order_num"] = pd.to_numeric(
            sub_items["order"], errors="coerce"
        ).fillna(9999)
        sub_items = sub_items.sort_values(
            ["_order_num", "item_name"], na_position="last"
        )

        item_name = ""
        if item_id:
            item_hit = sub_items[
                sub_items["item_id"].astype(str).str.strip() == item_id
            ].copy()
            if not item_hit.empty:
                item_name = str(item_hit.iloc[0].get("item_name", "")).strip()

        # 保存済みの項目が無い・削除済みの場合は先頭項目を案内する。
        if not item_name and not sub_items.empty:
            item_name = str(sub_items.iloc[0].get("item_name", "")).strip()
            item_id = str(sub_items.iloc[0].get("item_id", "")).strip()

        return f"サブ：{sub_name} / {item_name or item_id or '次の項目未設定'}"
    except Exception as e:
        return f"サブ：確認エラー {e}"


def upsert_schedule_override_row(
    overrides_df: pd.DataFrame,
    *,
    student_id: str,
    d,
    slot,
    action: str,
    start: str = "",
    end: str = "",
    session_type: str = "",
    note: str = "",
) -> pd.DataFrame:
    """schedule_overrides.csv に1行を安全に登録する。

    d202方針:
    - キャンセルは同じ student_id × date × slot の既存例外を置き換える。
    - 時間変更は「その日のその生徒の予定を1件に置き換える」用途なので、
      同じ student_id × date の追加/時間変更系を整理してから保存する。
    - 追加は予定が無い生徒を入れる用途を基本にする。
    """
    cols = ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]
    df = overrides_df.copy() if overrides_df is not None else pd.DataFrame(columns=cols)
    if df.empty:
        df = pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    d_obj = pd.to_datetime(d, errors="coerce")
    dstr = d_obj.strftime("%Y-%m-%d") if pd.notna(d_obj) else str(d).strip()
    sid = str(student_id).strip()
    slot_norm = normalize_slot(slot)
    action_norm = normalize_action_value(action)

    # 既存の同一キーを整理
    df["_action_norm"] = df["action"].map(normalize_action_value)
    df["_slot_norm"] = df["slot"].map(normalize_slot)

    if action_norm == "時間変更":
        # d217:
        # 以前は「同じ日・同じ生徒」の追加/時間変更を全削除していたため、
        # 2コマ連続で登録した時に、後から入れた1コマだけが残ってしまった。
        # 時間変更の登録自体は同じ student_id × date × slot だけ置き換える。
        # 最終予定で「時間変更」が1つでもある場合は、build_daily_plan_for_date 側で
        # 元の通常予定だけを外し、追加/時間変更の複数コマは残す。
        mask = (
            (df["student_id"] == sid)
            & (df["date"] == dstr)
            & (df["_slot_norm"] == slot_norm)
            & (df["_action_norm"].isin(["追加", "時間変更"]))
        )
    elif action_norm == "キャンセル":
        # キャンセルは既存の追加/時間変更を消さず、最後に勝たせる。
        # これにより「追加予定をキャンセルしたら元の通常予定が復活する」事故を防ぐ。
        mask = (
            (df["student_id"] == sid)
            & (df["date"] == dstr)
            & (df["_slot_norm"] == slot_norm)
            & (df["_action_norm"] == "キャンセル")
        )
    else:
        # 追加は同じ生徒・日付・コマの追加/時間変更だけ整理する
        mask = (
            (df["student_id"] == sid)
            & (df["date"] == dstr)
            & (df["_slot_norm"] == slot_norm)
            & (df["_action_norm"].isin(["追加", "時間変更"]))
        )

    df = df[~mask].drop(columns=["_action_norm", "_slot_norm"], errors="ignore").copy()

    new_row = {
        "student_id": sid,
        "date": dstr,
        "slot": slot_norm,
        "action": action_norm,
        "start": str(start).strip(),
        "end": str(end).strip(),
        "session_type": str(session_type).strip(),
        "note": str(note).strip(),
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return df[cols].fillna("")


def remove_schedule_override_rows(
    overrides_df: pd.DataFrame,
    *,
    student_id: str,
    d,
    slot=None,
    action: str | None = None,
) -> pd.DataFrame:
    """schedule_overrides.csv から対象行を安全に削除する。

    d205方針:
    - キャンセル解除では、月スケジュール本体は消さず、
      schedule_overrides.csv のキャンセル行だけを削除する。
    - 登録ミスとして消す場合にも、CSVを直接触らず画面操作で削除できるようにする。
    """
    cols = ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]
    df = overrides_df.copy() if overrides_df is not None else pd.DataFrame(columns=cols)
    if df.empty:
        return pd.DataFrame(columns=cols)

    for c in cols:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    d_obj = pd.to_datetime(d, errors="coerce")
    dstr = d_obj.strftime("%Y-%m-%d") if pd.notna(d_obj) else str(d).strip()
    sid = str(student_id).strip()

    mask = (df["student_id"] == sid) & (df["date"] == dstr)

    if slot is not None:
        slot_norm = normalize_slot(slot)
        mask = mask & (df["slot"].map(normalize_slot) == slot_norm)

    if action is not None:
        action_norm = normalize_action_value(action)
        mask = mask & (df["action"].map(normalize_action_value) == action_norm)

    df = df[~mask].copy()
    return df[cols].fillna("")


def restore_cancelled_plan_and_clear_absence(
    overrides_df: pd.DataFrame,
    attendance_df: pd.DataFrame,
    *,
    student_id: str,
    d,
    slot,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """d312: 取消線解除と、欠席・取消の出欠ログ解除を整合させる。

    - 対象コマのキャンセル行を削除する。
    - 同じ日・同じ生徒に他のキャンセル予定が残っていない場合だけ、
      attendance_log の absence / cancel / 欠席 / キャンセル を削除する。
    - lesson / selfstudy / 授業 / 自習など、通常の出欠実績は消さない。
    """
    sid = str(student_id).strip()
    d_obj = pd.to_datetime(d, errors="coerce")
    dstr = (
        d_obj.strftime("%Y-%m-%d")
        if pd.notna(d_obj)
        else str(d).strip()
    )

    restored_overrides = remove_schedule_override_rows(
        overrides_df,
        student_id=sid,
        d=dstr,
        slot=slot,
        action="キャンセル",
    )

    # 同日・同一生徒に、別コマのキャンセルがまだ残っているか確認する。
    remaining_cancel = False
    if restored_overrides is not None and not restored_overrides.empty:
        _ov = restored_overrides.copy()
        for _c in ["student_id", "date", "action"]:
            if _c not in _ov.columns:
                _ov[_c] = ""
            _ov[_c] = _ov[_c].fillna("").astype(str).str.strip()

        remaining_cancel = bool(
            (
                (_ov["student_id"] == sid)
                & (_ov["date"] == dstr)
                & (
                    _ov["action"].map(normalize_action_value)
                    == "キャンセル"
                )
            ).any()
        )

    att = (
        attendance_df.copy()
        if attendance_df is not None
        else pd.DataFrame(
            columns=["date", "student_id", "kind", "memo"]
        )
    )
    for _c in ["date", "student_id", "kind", "memo"]:
        if _c not in att.columns:
            att[_c] = ""
        att[_c] = att[_c].fillna("").astype(str).str.strip()

    cleared_absence = False
    if not remaining_cancel and not att.empty:
        _kind_norm = att["kind"].map(
            normalize_attendance_kind_for_lock
        )
        _remove_mask = (
            (att["student_id"] == sid)
            & (att["date"] == dstr)
            & (_kind_norm.isin(["absence", "cancel"]))
        )
        cleared_absence = bool(_remove_mask.any())
        if cleared_absence:
            att = att.loc[~_remove_mask].copy()

    return (
        restored_overrides,
        att[["date", "student_id", "kind", "memo"]].fillna(""),
        cleared_absence,
    )


def remove_seat_assignment_for_plan(
    seat_df: pd.DataFrame,
    *,
    d,
    student_id: str,
    slot,
) -> pd.DataFrame:
    """対象日の student_id × slot の座席を外す。"""
    cols = ["date", "slot", "seat_no", "student_id", "note"]
    df = seat_df.copy() if seat_df is not None else pd.DataFrame(columns=cols)
    if df.empty:
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    d_obj = pd.to_datetime(d, errors="coerce")
    dstr = d_obj.strftime("%Y-%m-%d") if pd.notna(d_obj) else str(d).strip()
    sid = str(student_id).strip()
    slot_norm = normalize_slot(slot)

    df = df[
        ~(
            (df["date"] == dstr)
            & (df["student_id"] == sid)
            & (df["slot"].map(normalize_slot) == slot_norm)
        )
    ].copy()
    return df[cols].fillna("")


def collect_plan_slots_for_student(
    plan_df: pd.DataFrame,
    student_id: str,
) -> list[str]:
    """d298: 対象生徒の予定コマを、重複を除いて表示順で集める。"""
    if plan_df is None or plan_df.empty:
        return []

    df = plan_df.copy()
    for c in ["student_id", "slot"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    sid = str(student_id).strip()
    df = df[df["student_id"].astype(str).str.strip().eq(sid)].copy()
    if df.empty:
        return []

    if "slot_num" not in df.columns:
        df["slot_num"] = pd.to_numeric(df["slot"].map(normalize_slot), errors="coerce")
    df = df.sort_values(["slot_num", "slot"], na_position="last")

    slots: list[str] = []
    for raw_slot in df["slot"].astype(str).tolist():
        slot_norm = normalize_slot(raw_slot)
        if slot_norm and slot_norm not in slots:
            slots.append(slot_norm)

    return slots


def apply_absence_and_cancel_schedule(
    *,
    att_df: pd.DataFrame,
    overrides_df: pd.DataFrame,
    seat_df: pd.DataFrame,
    plan_df: pd.DataFrame,
    student_id: str,
    d,
    note: str = "欠席で登録（予定取消）",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    """d298: 欠席登録と、カレンダー取消・座席解除を同時に行う。

    欠席 = 出欠上は確認済み / カレンダー上はキャンセル / 座席は空席。
    """
    d_obj = pd.to_datetime(d, errors="coerce")
    target_date = d_obj.date() if pd.notna(d_obj) else d
    sid = str(student_id).strip()

    att2 = upsert_attendance(
        att_df,
        student_id=sid,
        d=target_date,
        kind="absence",
        memo=note,
    )

    ov2 = overrides_df.copy() if overrides_df is not None else pd.DataFrame()
    seat2 = seat_df.copy() if seat_df is not None else pd.DataFrame()

    slots = collect_plan_slots_for_student(plan_df, sid)

    for slot in slots:
        ov2 = upsert_schedule_override_row(
            ov2,
            student_id=sid,
            d=target_date,
            slot=slot,
            action="キャンセル",
            note=note,
        )
        seat2 = remove_seat_assignment_for_plan(
            seat2,
            d=target_date,
            student_id=sid,
            slot=slot,
        )

    return att2, ov2, seat2, len(slots)


# [KEEP 2026-04-23] このファイル内で参照あり。現時点では使用中として維持。
def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")
    clear_csv_cache()


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
for _c in ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]:
    if _c not in schedule_overrides.columns:
        schedule_overrides[_c] = ""
schedule_overrides = schedule_overrides[["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]].fillna("")
if not schedule_overrides.empty:
    _override_date_raw = schedule_overrides["date"].fillna("").astype(str).str.strip()
    _override_date_norm = pd.to_datetime(_override_date_raw, errors="coerce").dt.strftime("%Y-%m-%d")
    schedule_overrides["date"] = _override_date_norm.fillna(_override_date_raw)
    schedule_overrides["slot"] = schedule_overrides["slot"].astype(str).str.strip().map(normalize_slot)
    schedule_overrides["action"] = schedule_overrides["action"].map(normalize_action_value)

# monthly_schedule.csv: 固定スケジュールから生成した「その月の確定予定」
MONTHLY_SCHEDULE_COLS = ["date", "student_id", "slot", "session_type", "reason", "note", "source"]
monthly_schedule = safe_read_csv(
    MONTHLY_SCHEDULE_CSV,
    MONTHLY_SCHEDULE_COLS,
    stop_on_missing=False,
)
for _c in MONTHLY_SCHEDULE_COLS:
    if _c not in monthly_schedule.columns:
        monthly_schedule[_c] = ""
monthly_schedule = monthly_schedule[MONTHLY_SCHEDULE_COLS].fillna("")
if "date" in monthly_schedule.columns and not monthly_schedule.empty:
    _monthly_date_raw = monthly_schedule["date"].fillna("").astype(str).str.strip()
    _monthly_date_norm = pd.to_datetime(_monthly_date_raw, errors="coerce").dt.strftime("%Y-%m-%d")
    monthly_schedule["date"] = _monthly_date_norm.fillna(_monthly_date_raw)

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

# d300:
# 退会済み生徒が過去に基本席へ残っていても、自動配置や座席確認へ混ざらないよう整理する。
_active_ids_for_default_seat = set()
_can_cleanup_default_seats = (
    not students.empty and "student_id" in students.columns
)
if _can_cleanup_default_seats:
    _active_students_for_default_seat = students.copy()
    if "is_active" in _active_students_for_default_seat.columns:
        _active_students_for_default_seat = _active_students_for_default_seat[
            _active_students_for_default_seat["is_active"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .replace("", "true")
            .isin(["true", "1", "yes"])
        ].copy()
    _active_ids_for_default_seat = set(
        _active_students_for_default_seat["student_id"]
        .astype(str)
        .str.strip()
        .tolist()
    )

if _can_cleanup_default_seats and not default_seats.empty:
    _default_before_count = len(default_seats)
    default_seats = default_seats[
        default_seats["student_id"].astype(str).str.strip().isin(
            _active_ids_for_default_seat
        )
    ].copy()
    if len(default_seats) != _default_before_count:
        write_csv_atomic(
            default_seats[DEFAULT_SEAT_COLS].fillna(""),
            DEFAULT_SEATS_CSV,
        )


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
        today_exam_grade_map = {}
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

        # d286:
        # 今日が検定日の生徒IDと受験級を、座席表・次に見る候補でも使えるように保持する。
        _today_exam_rows = exam_tbl[exam_tbl["日付"] == today_str].copy()
        today_exam_ids = set(_today_exam_rows["student_id"].astype(str).str.strip())
        today_exam_grade_map = {
            str(_r.get("student_id", "")).strip(): str(_r.get("級", "")).strip()
            for _, _r in _today_exam_rows.iterrows()
            if str(_r.get("student_id", "")).strip()
        }

        # 🔴印（名前そのものの色は変えない）
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
                    "受験日": exam_date,
                    "検定": str(r.get("exam_type", "") or r.get("kentei", "")).strip(),
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
            exam_name = str(row.get("検定", "")).strip()
            exam_name_part = f" / {exam_name}" if exam_name else ""
            st.write(f"{name}（{sid}） / {grade}級 / 受験日: {exam_date}{exam_name_part}")


    # =========================================================
    # 🚨 未完了タスク（今日・昨日以前）
    # 予定があったのに attendance_log / 進捗登録が無いものを出す
    # 判定単位：date × student_id
    # d215: 昨日以前は current student_schedule.csv ではなく、保存済み monthly_schedule.csv を基準にする。
    # =========================================================
    #st.subheader("🚨 未完了タスク（昨日以前）")

    att_df_check = load_attendance_log().copy()
    prog_skip_df = load_progress_skip_ok().copy()

    # d300:
    # 今日出席済みで進行中サブ課題がある生徒には、日別の未確認行を自動作成する。
    # 何も押さずに閉じても、このpending行が翌日以降に残る。
    sync_sub_daily_pending_for_date(att_df_check, today)

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


        # その日の予定
        # d215方針：
        # - 今日の未完了は、従来どおり月スケジュール優先 + 固定スケジュールへのフォールバックを許可する。
        # - 昨日以前の未完了は、現在の固定スケジュールで過去を再計算しない。
        #   monthly_schedule.csv と schedule_overrides.csv だけを見て判定する。
        #   その日の月スケジュールが保存されていない場合は、過去未完了には出さない。
        if d_str == today_str:
            _schedule_for_unfinished = student_schedule
        else:
            _schedule_for_unfinished = pd.DataFrame(columns=list(student_schedule.columns) if student_schedule is not None else ["student_id", "weekday", "slot", "session_type"])

        plan_day = build_daily_plan_for_date(
            d_date,
            students,
            _schedule_for_unfinished,
            monthly_schedule,
            schedule_overrides,
            timeslots,
            include_inactive=include_inactive,
        )

        if plan_day.empty:
            continue

        plan_day = plan_day.drop_duplicates(subset=["student_id", "slot"], keep="first").copy()

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

            curr_done_src = curr_prog[curr_prog.apply(is_progress_task_completed, axis=1)].copy()
            kentei_done_src = kentei_prog[kentei_prog.apply(is_progress_task_completed, axis=1)].copy()

            if d_date < today:
                # 昨日以前の未完了は、あとから今日進捗登録した場合でも消えるように
                # 対象日以降の done_date を進捗対応済みとして扱う。
                curr_done = is_progress_done_on_or_after(curr_done_src, sid, d_date)
                kentei_done = is_progress_done_on_or_after(kentei_done_src, sid, d_date)
            else:
                curr_done = is_progress_done_today(curr_done_src, sid, d_date)
                kentei_done = is_progress_done_today(kentei_done_src, sid, d_date)

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
                # 昨日以前の未完了は、現在の固定スケジュールではなく
                # 保存済み月スケジュール + 例外反映後の予定だけで表示する。
                overdue_rows.append(row_data)

                    
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


        st.caption("未完了タスクから出欠登録できます。進捗を登録する場合は「この生徒」で対象生徒へ移動できます。")


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
                        # d300:
                        # 過去日の出欠を後から登録した場合も、その日のサブ課題確認を作る。
                        sync_sub_daily_pending_for_date(att_df, d_obj.date())
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
                        # d300:
                        # 過去日の自習登録でも、進行中サブ課題があれば確認対象として残す。
                        sync_sub_daily_pending_for_date(att_df, d_obj.date())
                        st.success(f"{name} を自習で記録しました。")
                        st.rerun()
                    else:
                        st.error("日付の変換に失敗しました。")


            with c4:
                if st.button(
                    "欠席で登録（予定取消）",
                    key=f"{key_prefix}_absence_{d_str}_{sid}_{slot}_{i}",
                    disabled=attendance_done,
                    help="欠席として出欠登録し、この予定をキャンセル扱いにして座席も外します。",
                ):
                    att_df = load_attendance_log().copy()
                    d_obj = pd.to_datetime(d_str, errors="coerce")
                    if pd.notna(d_obj):
                        _absence_plan_df = pd.DataFrame([{
                            "student_id": sid,
                            "slot": slot,
                        }])
                        att_df2, ov2, seat2, cancel_count = apply_absence_and_cancel_schedule(
                            att_df=att_df,
                            overrides_df=schedule_overrides,
                            seat_df=seat_assignments,
                            plan_df=_absence_plan_df,
                            student_id=sid,
                            d=d_obj.date(),
                            note="未完了タスクから欠席で登録（予定取消）",
                        )
                        save_attendance_log(att_df2)
                        write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)
                        write_csv_atomic(seat2, SEAT_ASSIGNMENTS_CSV)
                        st.success(f"{name} を欠席で登録し、予定と座席にも反映しました。")
                        st.rerun()
                    else:
                        st.error("日付の変換に失敗しました。")


            with c5:
                if st.button(
                    "キャンセル登録",
                    key=f"{key_prefix}_cancel_{d_str}_{sid}_{slot}_{i}",
                    disabled=attendance_done
                ):
                    att_df = load_attendance_log().copy()
                    d_obj = pd.to_datetime(d_str, errors="coerce")
                    if pd.notna(d_obj):
                        cancel_date = d_obj.date()

                        # schedule_overrides.csv にもキャンセルを登録する。
                        # これで過去分も、未完了一覧を見ながら直接キャンセルできる。
                        ov2 = upsert_schedule_override_row(
                            schedule_overrides,
                            student_id=sid,
                            d=cancel_date,
                            slot=slot,
                            action="キャンセル",
                            note="未完了タスクからキャンセル登録",
                        )
                        write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)

                        seat_assignments2 = remove_seat_assignment_for_plan(
                            seat_assignments,
                            d=cancel_date,
                            student_id=sid,
                            slot=slot,
                        )
                        write_csv_atomic(seat_assignments2, SEAT_ASSIGNMENTS_CSV)

                        att_df = upsert_attendance(
                            att_df,
                            student_id=sid,
                            d=cancel_date,
                            kind="cancel",
                            memo="未完了タスクからキャンセル登録"
                        )
                        save_attendance_log(att_df)
                        st.success(f"{name} をキャンセル登録しました。予定例外にも反映しました。")
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
                    # サイドバー側は pending_sidebar_student を見ているため、このキーに合わせる。
                    st.session_state["pending_sidebar_student"] = target_name
                    # d251:
                    # 「この生徒」から開く時も、検定練習中/未合格の検定予定があれば検定課題へ寄せる。
                    # それ以外は通常カリキュラム課題へ寄せる。
                    try:
                        if is_kentei_training_active(sid) or has_unpassed_kentei_exam_schedule(sid, kentei_exam):
                            st.session_state["sidebar_view_mode"] = "検定課題"
                        else:
                            st.session_state["sidebar_view_mode"] = "カリキュラム課題"
                    except Exception:
                        st.session_state["sidebar_view_mode"] = "カリキュラム課題"
                    st.rerun()

    today_df = pd.DataFrame(today_rows)
    today_count = len(today_df)

    if today_count > 0:
        st.warning(f"⚠️ 今日の未完了タスク：{today_count}件あります（最優先）")
        st.markdown(f"### ⚠ 今日の未完了：**{today_count}件**")

        today_show = today_df.copy()
        if not today_show.empty:
            # d259:
            # 今日の未完了の要約表示も、出欠未登録・次に見る候補と同じく
            # 「優先度 → コマが早い順 → 生徒名」で並べる。
            # 以前は生徒名と状態だけにまとめていたため、コマ情報が落ちて順番が分かりにくかった。
            _today_base_cols = [c for c in ["生徒", "状態", "コマ"] if c in today_df.columns]
            today_show = today_df[_today_base_cols].copy()
            if "コマ" not in today_show.columns:
                today_show["コマ"] = ""

            today_show["slot_num"] = pd.to_numeric(
                today_show["コマ"].astype(str).str.strip(),
                errors="coerce",
            ).fillna(9999)

            today_show = today_show.drop_duplicates().reset_index(drop=True)


            summary_rows = []
            for name, group in today_show.groupby("生徒", dropna=False):
                states = list(dict.fromkeys(group["状態"].astype(str).tolist()))
                min_slot_num = pd.to_numeric(group["slot_num"], errors="coerce").fillna(9999).min()


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
                    "slot_num": min_slot_num,
                })


            today_show = pd.DataFrame(summary_rows)


            priority_map = {
                "🚨 出欠未 / 進捗未あり": 0,
                "❗出欠・進捗": 0,
                "❗出欠": 1,
                "❗進捗": 2,
            }


            today_show["priority"] = today_show["状態"].map(priority_map).fillna(99)
            today_show = today_show.sort_values(["priority", "slot_num", "生徒"], na_position="last").reset_index(drop=True)


            for _, r in today_show.iterrows():
                label = str(r.get("生徒", "")).strip()
                status = str(r.get("状態", "")).strip()
                st.write(f"• {label} / {status}")

    else:
        st.success("✅ 今日の未完了タスクはありません")


    st.divider()


    overdue_df = pd.DataFrame(overdue_rows)
    
    if overdue_rows:
        with st.expander("昨日以前の未完了 確認用", expanded=False):
            st.caption("昨日以前は、保存済み月スケジュールとスケジュール例外だけを見て判定します。現在の固定スケジュール変更には引っ張られません。")
            debug_overdue = pd.DataFrame(overdue_rows)
            show_cols = [c for c in ["日付", "student_id", "生徒", "コマ", "種別", "状態"] if c in debug_overdue.columns]
            st.dataframe(debug_overdue[show_cols], use_container_width=True, hide_index=True)


    overdue_count = len(overdue_df)
    if overdue_count > 0:
        st.error(f"🚨 未完了タスク（昨日以前）：{overdue_count}件あります（優先的に対応してください）")
        render_unfinished_section("🚨 未完了タスク（昨日以前）", overdue_df, "overdue")
    else:
        st.success("✅ 未完了タスク（昨日以前）はありません")

    st.divider()

    # =====================================================
    # 🧩 サブ課題の日別確認（d300）
    # -----------------------------------------------------
    # 出席済みの日に「完了」または「実施なし」が押されなければpendingが残る。
    # 翌日以降もここへ表示し、登録忘れを見える化する。
    # =====================================================
    _sub_daily_flash = st.session_state.pop("sub_daily_flash", "")
    _sub_daily_flash_is_error = st.session_state.pop(
        "sub_daily_flash_is_error", False
    )
    if _sub_daily_flash:
        if _sub_daily_flash_is_error:
            st.error(_sub_daily_flash)
        else:
            st.success(_sub_daily_flash)

    sub_daily_df = load_sub_daily_check()
    pending_sub_daily = pd.DataFrame(columns=SUB_DAILY_CHECK_COLS)

    if not sub_daily_df.empty:
        sub_daily_df = sub_daily_df.copy()
        for _c in SUB_DAILY_CHECK_COLS:
            if _c not in sub_daily_df.columns:
                sub_daily_df[_c] = ""
            sub_daily_df[_c] = (
                sub_daily_df[_c].fillna("").astype(str).str.strip()
            )

        _active_ids_for_sub_daily = set()
        if not students.empty and "student_id" in students.columns:
            _active_sub_students = students.copy()
            if "is_active" in _active_sub_students.columns:
                _active_sub_students = _active_sub_students[
                    _active_sub_students["is_active"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .replace("", "true")
                    .isin(["true", "1", "yes"])
                ].copy()
            _active_ids_for_sub_daily = set(
                _active_sub_students["student_id"]
                .astype(str)
                .str.strip()
                .tolist()
            )

        pending_sub_daily = sub_daily_df[
            sub_daily_df["status"].str.lower().eq("pending")
            & sub_daily_df["student_id"].isin(_active_ids_for_sub_daily)
        ].copy()

    if pending_sub_daily.empty:
        st.success("✅ サブ課題の確認漏れはありません")
    else:
        _student_name_for_sub_daily = dict(
            zip(
                students["student_id"].astype(str).str.strip(),
                students["display_name"].fillna("").astype(str).str.strip(),
            )
        ) if not students.empty else {}
        _sub_master_daily_df = load_sub_curricula()
        _sub_items_daily_df = load_sub_curriculum_items()
        _sub_name_for_daily = dict(
            zip(
                _sub_master_daily_df["sub_id"].astype(str).str.strip(),
                _sub_master_daily_df["sub_name"].astype(str).str.strip(),
            )
        ) if not _sub_master_daily_df.empty else {}
        _item_name_for_daily = dict(
            zip(
                _sub_items_daily_df["item_id"].astype(str).str.strip(),
                _sub_items_daily_df["item_name"].astype(str).str.strip(),
            )
        ) if not _sub_items_daily_df.empty else {}

        pending_sub_daily["_date_dt"] = pd.to_datetime(
            pending_sub_daily["date"], errors="coerce"
        )
        pending_sub_daily = pending_sub_daily.sort_values(
            ["_date_dt", "student_id"],
            na_position="last",
        )

        _today_sub_pending_count = int(
            pending_sub_daily["date"].eq(str(today)).sum()
        )
        _past_sub_pending_count = int(
            (pending_sub_daily["date"] < str(today)).sum()
        )

        if _past_sub_pending_count:
            st.error(
                f"🚨 サブ課題確認未（昨日以前）："
                f"{_past_sub_pending_count}件あります"
            )
        if _today_sub_pending_count:
            st.warning(
                f"⚠ サブ課題確認未（今日）："
                f"{_today_sub_pending_count}件あります"
            )

        with st.expander(
            f"🧩 サブ課題確認未（{len(pending_sub_daily)}件）",
            expanded=bool(_past_sub_pending_count),
        ):
            st.caption(
                "実際に終わっている場合は「完了登録」、"
                "その日は取り組まなかった場合は「実施なし」で確認してください。"
            )

            for _idx, _row in pending_sub_daily.reset_index(drop=True).iterrows():
                _d = str(_row.get("date", "")).strip()
                _sid = str(_row.get("student_id", "")).strip()
                _sub_id = str(_row.get("sub_id", "")).strip()
                _item_id = str(_row.get("item_id", "")).strip()
                _student_label = _student_name_for_sub_daily.get(_sid, _sid)
                _sub_label = _sub_name_for_daily.get(_sub_id, _sub_id)
                _item_label = _item_name_for_daily.get(_item_id, _item_id)

                _sc1, _sc2, _sc3 = st.columns([5, 1.6, 1.6])
                with _sc1:
                    st.markdown(
                        f"**{_d}｜{_student_label}**  \n"
                        f"{_sub_label} / {_item_label}"
                    )
                with _sc2:
                    if st.button(
                        "✅ 完了登録",
                        key=f"sub_daily_done_{_d}_{_sid}_{_idx}",
                    ):
                        _ok, _message = complete_and_confirm_sub_daily(
                            _sid, _d
                        )
                        st.session_state["sub_daily_flash"] = _message
                        st.session_state[
                            "sub_daily_flash_is_error"
                        ] = not _ok
                        st.rerun()
                with _sc3:
                    _skip_label = (
                        "今日は実施なし"
                        if _d == str(today)
                        else "実施なしで確認"
                    )
                    if st.button(
                        _skip_label,
                        key=f"sub_daily_skip_{_d}_{_sid}_{_idx}",
                    ):
                        _ok, _message = mark_sub_daily_skip(_sid, _d)
                        st.session_state["sub_daily_flash"] = _message
                        st.session_state[
                            "sub_daily_flash_is_error"
                        ] = not _ok
                        st.rerun()

    st.divider()

    st.subheader(f"🗓 今日（{today.strftime('%Y-%m-%d')}・{today_wd}）の予定")
    st.caption("※ 記録後でも「取消」で元に戻せます")
    #st.info("⚠ 授業が終わったら『進捗登録』または『進捗なしで完了』を必ず押してください")
    st.warning("授業が終わったら、出欠を記録してください。進捗がある場合は下のカリキュラム課題 / 検定課題で登録してください。進捗が無い場合だけ「進捗なしで完了」を押してください。")

    # =====================================================
# 🧹整理候補
# d316以降は役割が重複している可能性あり。一定期間運用後に削除を検討。
    # d311: 🧹整理候補：今日の取消済み予定を復活
    # -----------------------------------------------------
    # 今日の予定が1人だけで、その予定を誤って取消した場合でも、
    # today_view が空になる前提に依存せず、ここから取消を解除できる。
    # =====================================================
    _today_cancel_rows = schedule_overrides.copy()
    for _c in ["student_id", "date", "slot", "action", "note"]:
        if _c not in _today_cancel_rows.columns:
            _today_cancel_rows[_c] = ""
        _today_cancel_rows[_c] = (
            _today_cancel_rows[_c]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    if not _today_cancel_rows.empty:
        _today_cancel_rows["_action_norm"] = (
            _today_cancel_rows["action"]
            .map(normalize_action_value)
        )
        _today_cancel_rows["_slot_norm"] = (
            _today_cancel_rows["slot"]
            .map(normalize_slot)
        )
        _today_cancel_rows = _today_cancel_rows[
            (
                _today_cancel_rows["date"]
                == today.strftime("%Y-%m-%d")
            )
            & (
                _today_cancel_rows["_action_norm"]
                == "キャンセル"
            )
        ].copy()

    if not _today_cancel_rows.empty:
        _restore_name_map = {}
        if (
            not students.empty
            and "student_id" in students.columns
            and "display_name" in students.columns
        ):
            _restore_name_map = dict(
                zip(
                    students["student_id"]
                    .astype(str)
                    .str.strip(),
                    students["display_name"]
                    .fillna("")
                    .astype(str)
                    .str.strip(),
                )
            )

        st.warning(
            f"今日の取消済み予定が"
            f"{len(_today_cancel_rows)}件あります。"
            "誤って取消した場合は、ここから復活できます。"
        )

        with st.expander(
            "↩ 🧹整理候補：🧹整理候補：今日の取消済み予定を復活",
            expanded=True,
        ):
            for _restore_idx, _restore_row in (
                _today_cancel_rows.iterrows()
            ):
                _restore_sid = str(
                    _restore_row.get("student_id", "")
                ).strip()
                _restore_slot = normalize_slot(
                    _restore_row.get("slot", "")
                )
                _restore_name = (
                    _restore_name_map.get(
                        _restore_sid,
                        _restore_sid,
                    )
                    or _restore_sid
                )
                _restore_note = str(
                    _restore_row.get("note", "")
                ).strip()

                _rc1, _rc2 = st.columns([4, 1.4])
                with _rc1:
                    _restore_text = (
                        f"{_restore_slot}コマ｜"
                        f"{_restore_name}"
                    )
                    if _restore_note:
                        _restore_text += (
                            f"｜{_restore_note}"
                        )
                    st.write(_restore_text)

                with _rc2:
                    if st.button(
                        "復活",
                        key=(
                            f"today_cancel_restore_"
                            f"{today}_"
                            f"{_restore_sid}_"
                            f"{_restore_slot}_"
                            f"{_restore_idx}"
                        ),
                        use_container_width=True,
                        help=(
                            "今日のキャンセルだけを解除し、"
                            "予定へ戻します。"
                        ),
                    ):
                        _attendance_before_restore = (
                            load_attendance_log().copy()
                        )
                        (
                            _restored_overrides,
                            _restored_attendance,
                            _cleared_absence,
                        ) = restore_cancelled_plan_and_clear_absence(
                            schedule_overrides,
                            _attendance_before_restore,
                            student_id=_restore_sid,
                            d=today,
                            slot=_restore_slot,
                        )
                        write_csv_atomic(
                            _restored_overrides,
                            SCHEDULE_OVERRIDES_CSV,
                        )
                        if _cleared_absence:
                            save_attendance_log(
                                _restored_attendance
                            )

                        _restore_message = (
                            f"{_restore_name}の"
                            f"{_restore_slot}コマを"
                            "今日の予定へ復活しました。"
                        )
                        if _cleared_absence:
                            _restore_message += (
                                " 欠席・取消の出欠記録も"
                                "未登録へ戻しました。"
                            )

                        st.session_state[
                            "today_restore_flash"
                        ] = _restore_message
                        st.rerun()

    _today_restore_flash = st.session_state.pop(
        "today_restore_flash",
        "",
    )
    if _today_restore_flash:
        st.success(_today_restore_flash)

    # =====================================================
    # 今日の予定の元データ
    # d202: 今日の予定・未完了・座席が同じ共通関数を見るように統一
    # =====================================================
    ts = timeslots.copy()
    for c in ["weekday", "slot", "start", "end"]:
        if c in ts.columns:
            ts[c] = ts[c].fillna("").astype(str).str.strip()
    if not ts.empty:
        ts["slot"] = ts["slot"].astype(str).str.strip().map(normalize_slot)
        ts = ts.drop_duplicates(subset=["weekday", "slot"], keep="first")

    base_students = students.copy()

    if "is_active" in base_students.columns:
        base_students = base_students[
            base_students["is_active"].fillna("").astype(str).str.strip().str.lower().replace("", "true").isin(["true", "1", "yes"])
        ].copy()

    today_view = build_daily_plan_for_date(
        today,
        students,
        student_schedule,
        monthly_schedule,
        schedule_overrides,
        timeslots,
        include_inactive=include_inactive,
    )

    if today_view.empty:
        st.info("今日の予定はありません。（月スケジュール / student_schedule.csv / schedule_overrides.csv を確認してね）")
    else:
        preparation_log_df = load_preparation_log().copy()

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

        today_view["準備"] = today_view.apply(
            lambda r: (
                "✅ 準備済"
                if is_prepared_for_plan(
                    preparation_log_df,
                    d=today,
                    student_id=r.get("student_id", ""),
                    slot=r.get("slot", ""),
                )
                else "⬜ 未準備"
            ),
            axis=1,
        )

        
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

        # d284:
        # 「準備しながら全員を確認したい」という運用に合わせ、
        # 自習を含む今日の予定全員を残す。
        # 以前の「確認が必要な授業だけ」という絞り込みは行わない。


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


        # d284:
        # 完了済みも含めて今日の予定全員を表示する。
        # priority は除外条件ではなく、確認しやすい並び順にだけ使う。


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

        # d267:
        # 「次に見る候補」は授業前準備にも使うため、今日の座席番号も一緒に出す。
        # 座席登録済みなら席番号、未配置なら「未配置」と表示する。
        def _seat_label_for_today_candidate(_sid: str, _slot: str) -> str:
            try:
                _sid = str(_sid).strip()
                _slot = normalize_slot(_slot)
                if not _sid or not _slot:
                    return "未配置"

                _seat_df = seat_assignments.copy()
                if _seat_df is None or _seat_df.empty:
                    return "未配置"

                for _c in ["date", "slot", "seat_no", "student_id"]:
                    if _c not in _seat_df.columns:
                        _seat_df[_c] = ""
                    _seat_df[_c] = _seat_df[_c].fillna("").astype(str).str.strip()

                _today_str = str(today)
                _seat_df["slot"] = _seat_df["slot"].map(normalize_slot)

                _hit = _seat_df[
                    (_seat_df["date"].astype(str).str.strip() == _today_str)
                    & (_seat_df["student_id"].astype(str).str.strip() == _sid)
                    & (_seat_df["slot"].astype(str).str.strip() == _slot)
                ].copy()

                if _hit.empty:
                    return "未配置"

                _seat_no = str(_hit.iloc[-1].get("seat_no", "")).strip()
                if not _seat_no:
                    return "未配置"
                if _seat_no == "__RESERVED__":
                    return "使用予定"
                return _seat_no
            except Exception:
                return "未配置"

        st.subheader("👀 次に見る候補")


        _sub_progress_flash = st.session_state.pop("sub_progress_flash", "")
        _sub_progress_flash_is_error = st.session_state.pop("sub_progress_flash_is_error", False)
        if _sub_progress_flash:
            if _sub_progress_flash_is_error:
                st.error(_sub_progress_flash)
            else:
                st.success(_sub_progress_flash)

        if next_candidates.empty:
            st.caption("候補なし")
        else:
            # d284:
            # 今日の予定にいる生徒を、自習・完了済みも含めて全員表示する。
            st.caption(f"今日の予定：{len(next_candidates)}人（自習・完了済みを含めて全員表示）")

            # 同じ生徒が複数コマにいる場合も、サブ課題の状態・操作は1回だけ表示する。
            _sub_progress_button_rendered = set()

            for i, (_, r) in enumerate(next_candidates.iterrows(), start=1):
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


                seat_label = _seat_label_for_today_candidate(sid, slot)
                _today_exam_grade = str(today_exam_grade_map.get(sid, "")).strip()
                _today_exam_mark = "🎫 " if sid in today_exam_ids else ""
                st.write(f"{i}. {slot}限 / 席：{seat_label} / {_today_exam_mark}{name} / {status}")

                # d245:
                # まずは「次に見る候補」に、今日やる候補を1行だけ表示して検証する。
                # 正しさの確認を優先し、細かい優先順位や例外処理は今後の違和感メモで調整する。
                def _next_curriculum_task_hint(_sid: str) -> str:
                    try:
                        _sid = str(_sid).strip()
                        if not _sid:
                            return ""

                        def _active_course_table():
                            _cc = curr_courses.copy()
                            for _c in ["course_id", "genre_id", "genre_name", "course_name", "course_order", "is_active"]:
                                if _c not in _cc.columns:
                                    _cc[_c] = ""
                                _cc[_c] = _cc[_c].fillna("").astype(str).str.strip()

                            _active = _cc["is_active"].astype(str).str.strip().str.lower()
                            _cc = _cc[_active.replace("", "true").isin(["true", "1", "yes"])].copy()
                            _cc["_order_num"] = pd.to_numeric(_cc["course_order"], errors="coerce").fillna(9999)

                            # 現場で見やすい順。d236の考え方に合わせる。
                            def _course_priority(_row):
                                _cid = str(_row.get("course_id", "")).strip().lower()
                                _cname = str(_row.get("course_name", "")).strip().lower()
                                _gname = str(_row.get("genre_name", "")).strip().lower()
                                _joined = f"{_cid} {_cname} {_gname}"
                                if _cid == "sc_l" or "sc_l" in _joined or "scratch_l" in _joined:
                                    return 0
                                if _cid == "sc_h" or "sc_h" in _joined or "scratch_h" in _joined:
                                    return 1
                                if "scratch" in _joined or "スクラッチ" in _joined:
                                    return 2
                                if "html" in _joined:
                                    return 10
                                if "javascript" in _joined or "java script" in _joined or _cid in ["js", "javascript"]:
                                    return 11
                                if "python" in _joined:
                                    return 20
                                if "unity" in _joined:
                                    return 21
                                return 99

                            _cc["_ui_priority"] = _cc.apply(_course_priority, axis=1)
                            return _cc.sort_values(
                                ["_ui_priority", "_order_num", "genre_name", "course_name"],
                                na_position="last"
                            ).copy()

                        def _course_name_for(_course_id: str) -> str:
                            _course_id = str(_course_id).strip()
                            _row = curr_courses[
                                curr_courses["course_id"].astype(str).str.strip() == _course_id
                            ].copy()
                            if _row.empty:
                                return _course_id
                            _cname = str(_row.iloc[0].get("course_name", "")).strip()
                            return _cname or _course_id

                        def _course_done_by_log(_course_id: str) -> bool:
                            try:
                                _course_id = str(_course_id).strip()
                                _course_row = curr_courses[
                                    curr_courses["course_id"].astype(str).str.strip() == _course_id
                                ].copy()
                                if _course_row.empty:
                                    return False

                                _genre_id = str(_course_row.iloc[0].get("genre_id", "")).strip()
                                _course_name = str(_course_row.iloc[0].get("course_name", "")).strip()

                                _log = log.copy()
                                if _log.empty:
                                    return False
                                for _c in ["student_id", "curriculum", "item", "status"]:
                                    if _c not in _log.columns:
                                        _log[_c] = ""
                                    _log[_c] = _log[_c].fillna("").astype(str).str.strip()

                                _mask = (
                                    (_log["student_id"].astype(str).str.strip() == _sid)
                                    & (_log["curriculum"].astype(str).str.strip() == _genre_id)
                                    & (_log["item"].astype(str).str.strip() == _course_name)
                                    & (_log["status"].astype(str).str.strip().str.lower() == "done")
                                )
                                return bool(_mask.any())
                            except Exception:
                                return False

                        def _next_task_for_course(_course_id: str):
                            _course_id = str(_course_id).strip()
                            if not _course_id:
                                return None

                            _tasks = curr_tasks.copy()
                            for _c in ["course_id", "task_id", "task_name", "order", "is_active", "student_id"]:
                                if _c not in _tasks.columns:
                                    _tasks[_c] = ""
                                _tasks[_c] = _tasks[_c].fillna("").astype(str).str.strip()

                            _tasks = _tasks[
                                (_tasks["course_id"].astype(str).str.strip() == _course_id)
                                & (
                                    (_tasks["student_id"].astype(str).str.strip() == "")
                                    | (_tasks["student_id"].astype(str).str.strip() == _sid)
                                )
                            ].copy()

                            if "is_active" in _tasks.columns:
                                _active = _tasks["is_active"].astype(str).str.strip().str.lower()
                                _tasks = _tasks[_active.replace("", "true").isin(["true", "1", "yes"])].copy()

                            if _tasks.empty:
                                return None

                            _tasks["_order_num"] = pd.to_numeric(_tasks["order"], errors="coerce").fillna(9999)
                            _tasks = _tasks.sort_values(["_order_num", "task_name"], na_position="last").copy()

                            _prog = curr_prog.copy()
                            for _c in ["student_id", "course_id", "task_id", "is_done", "is_skip"]:
                                if _c not in _prog.columns:
                                    _prog[_c] = ""
                                _prog[_c] = _prog[_c].fillna("").astype(str).str.strip()

                            _prog = _prog[
                                (_prog["student_id"].astype(str).str.strip() == _sid)
                                & (_prog["course_id"].astype(str).str.strip() == _course_id)
                            ].copy()

                            _done_map = {
                                str(_r.get("task_id", "")).strip(): str(_r.get("is_done", "")).strip().lower() == "true"
                                for _, _r in _prog.iterrows()
                            }
                            _skip_map = {
                                str(_r.get("task_id", "")).strip(): str(_r.get("is_skip", "")).strip().lower() == "true"
                                for _, _r in _prog.iterrows()
                            }

                            for _, _t in _tasks.iterrows():
                                _tid = str(_t.get("task_id", "")).strip()
                                _tname = str(_t.get("task_name", "")).strip()
                                if not _tid:
                                    continue
                                if not _done_map.get(_tid, False) and not _skip_map.get(_tid, False):
                                    return _tname or _tid

                            return None

                        _courses = _active_course_table()
                        if _courses.empty:
                            return ""

                        _latest_course_id = latest_course_for_student(_sid, curr_prog)
                        _latest_course_id = str(_latest_course_id).strip() if _latest_course_id else ""

                        # 候補順：
                        # 1) 最新コース
                        # 2) 最新コースの次以降
                        # 3) 念のため先頭から再確認
                        _ordered_course_ids = _courses["course_id"].astype(str).str.strip().tolist()
                        _candidate_course_ids = []

                        if _latest_course_id and _latest_course_id in _ordered_course_ids:
                            _idx = _ordered_course_ids.index(_latest_course_id)
                            _candidate_course_ids.extend(_ordered_course_ids[_idx:])
                            _candidate_course_ids.extend(_ordered_course_ids[:_idx])
                        else:
                            _candidate_course_ids.extend(_ordered_course_ids)

                        _seen = set()
                        _candidate_course_ids = [
                            _cid for _cid in _candidate_course_ids
                            if _cid and not (_cid in _seen or _seen.add(_cid))
                        ]

                        for _cid in _candidate_course_ids:
                            if _course_done_by_log(_cid):
                                continue
                            _task_name = _next_task_for_course(_cid)
                            if _task_name:
                                return f"通常：{_course_name_for(_cid)} / {_task_name}"

                        return "通常：未完了課題なし"
                    except Exception as _e:
                        return f"通常：次課題確認エラー {_e}"

                def _passed_kentei_grades_for_student(_sid: str) -> set:
                    try:
                        _res = load_kentei_results().copy()
                        if _res.empty:
                            return set()
                        for _c in ["student_id", "grade"]:
                            if _c not in _res.columns:
                                _res[_c] = ""
                            _res[_c] = _res[_c].fillna("").astype(str).str.strip()
                        return set(
                            _res[_res["student_id"].astype(str).str.strip() == str(_sid).strip()]["grade"]
                            .astype(str).str.strip().tolist()
                        )
                    except Exception:
                        return set()

                def _recommended_kentei_grade_for_candidate(_sid: str) -> str:
                    try:
                        _sid = str(_sid).strip()
                        _grade_options = ["1", "2", "3", "4"]
                        _grade_progress_order = ["4", "3", "2", "1"]
                        _passed = _passed_kentei_grades_for_student(_sid)

                        _exam = kentei_exam.copy()
                        if not _exam.empty:
                            for _c in ["student_id", "grade", "exam_date", "date"]:
                                if _c not in _exam.columns:
                                    _exam[_c] = ""
                                _exam[_c] = _exam[_c].fillna("").astype(str).str.strip()

                            _exam = _exam[_exam["student_id"].astype(str).str.strip() == _sid].copy()
                            if not _exam.empty:
                                _exam["__date_raw"] = _exam["exam_date"].where(
                                    _exam["exam_date"].astype(str).str.strip() != "",
                                    _exam["date"],
                                )
                                _exam["__d"] = pd.to_datetime(_exam["__date_raw"], errors="coerce")
                                _exam["grade"] = _exam["grade"].astype(str).str.strip()
                                _exam = _exam[_exam["grade"].isin(_grade_options)].copy()
                                _exam = _exam[~_exam["grade"].isin(_passed)].copy()

                                if not _exam.empty:
                                    _today_ts = pd.Timestamp(date.today()).normalize()
                                    _future = _exam[
                                        _exam["__d"].notna() & (_exam["__d"] >= _today_ts)
                                    ].sort_values("__d", ascending=True).copy()
                                    if not _future.empty:
                                        return str(_future.iloc[0].get("grade", "")).strip()

                        for _g in _grade_progress_order:
                            if _g not in _passed:
                                return _g
                        return ""
                    except Exception:
                        return ""

                def _next_kentei_task_hint(_sid: str, _grade: str) -> str:
                    try:
                        _sid = str(_sid).strip()
                        _grade = str(_grade).strip()
                        if not _sid or not _grade:
                            return ""

                        _tasks = kentei_tasks.copy()
                        for _c in ["grade", "task_id", "task_name", "order", "student_id"]:
                            if _c not in _tasks.columns:
                                _tasks[_c] = ""
                            _tasks[_c] = _tasks[_c].fillna("").astype(str).str.strip()

                        _tasks = _tasks[
                            (_tasks["grade"].astype(str).str.strip() == _grade)
                            & (
                                (_tasks["student_id"].astype(str).str.strip() == "")
                                | (_tasks["student_id"].astype(str).str.strip() == _sid)
                            )
                        ].copy()

                        if _tasks.empty:
                            return f"検定：{_grade}級 / 次課題未登録"

                        _tasks["_order_num"] = pd.to_numeric(_tasks["order"], errors="coerce").fillna(9999)
                        _tasks = _tasks.sort_values(["_order_num", "task_name"], na_position="last").copy()

                        _prog = kentei_prog.copy()
                        for _c in ["student_id", "grade", "task_id", "is_done", "is_skip"]:
                            if _c not in _prog.columns:
                                _prog[_c] = ""
                            _prog[_c] = _prog[_c].fillna("").astype(str).str.strip()

                        _prog = _prog[
                            (_prog["student_id"].astype(str).str.strip() == _sid)
                            & (_prog["grade"].astype(str).str.strip() == _grade)
                        ].copy()

                        _done_map = {
                            str(_r.get("task_id", "")).strip(): str(_r.get("is_done", "")).strip().lower() == "true"
                            for _, _r in _prog.iterrows()
                        }
                        _skip_map = {
                            str(_r.get("task_id", "")).strip(): str(_r.get("is_skip", "")).strip().lower() == "true"
                            for _, _r in _prog.iterrows()
                        }

                        for _, _t in _tasks.iterrows():
                            _tid = str(_t.get("task_id", "")).strip()
                            _tname = str(_t.get("task_name", "")).strip()
                            if not _tid:
                                continue
                            if not _done_map.get(_tid, False) and not _skip_map.get(_tid, False):
                                return f"検定：{_grade}級 / {_tname or _tid}"

                        return f"検定：{_grade}級 / 未完了課題なし"
                    except Exception as _e:
                        return f"検定：次課題確認エラー {_e}"

                def _today_task_hint(_sid: str) -> str:
                    # 検定練習中フラグON、または未合格の検定予定がある場合は検定を優先。
                    # それ以外は通常カリキュラムを表示する。
                    try:
                        _sid = str(_sid).strip()
                        _grade = _recommended_kentei_grade_for_candidate(_sid)

                        _is_training = is_kentei_training_active(_sid)
                        _training_grade = get_kentei_training_grade(_sid)
                        if _is_training and _training_grade:
                            _grade = _training_grade

                        _has_unpassed_exam_schedule = False
                        if _grade:
                            _passed = _passed_kentei_grades_for_student(_sid)
                            _exam = kentei_exam.copy()
                            if not _exam.empty:
                                for _c in ["student_id", "grade"]:
                                    if _c not in _exam.columns:
                                        _exam[_c] = ""
                                    _exam[_c] = _exam[_c].fillna("").astype(str).str.strip()
                                _has_unpassed_exam_schedule = bool(
                                    (
                                        (_exam["student_id"].astype(str).str.strip() == _sid)
                                        & (_exam["grade"].astype(str).str.strip() == _grade)
                                        & (~_exam["grade"].astype(str).str.strip().isin(_passed))
                                    ).any()
                                )

                        if _is_training or _has_unpassed_exam_schedule:
                            return _next_kentei_task_hint(_sid, _grade)

                        return _next_curriculum_task_hint(_sid)
                    except Exception as _e:
                        return f"今日やる候補確認エラー {_e}"

                _candidate_session_type = str(
                    r.get("session_type", r.get("種別", ""))
                ).strip().lower()
                _candidate_is_selfstudy = _candidate_session_type in [
                    "自習", "🟦 自習", "self", "selfstudy", "self-study", "自"
                ]

                # d286:
                # 今日が検定日の生徒は、通常カリキュラムや検定練習課題よりも
                # 「本日の検定」を最優先で表示する。
                if sid in today_exam_ids:
                    if _today_exam_grade:
                        st.caption(f"今日やる候補：🎫 検定（{_today_exam_grade}級）")
                    else:
                        st.caption("今日やる候補：🎫 検定")
                elif _candidate_is_selfstudy:
                    st.caption("今日やる候補：自習（通常課題の準備対象外）")
                else:
                    task_hint = _today_task_hint(sid)
                    if task_hint:
                        st.caption(f"今日やる候補：{task_hint}")

                # d300:
                # サブ課題の現在位置に加え、日別確認の pending / done / skip を表示する。
                sub_state = get_student_sub_ui_state(sid)
                sub_task_hint = get_student_sub_task_hint(sid)
                sub_daily_state = get_sub_daily_check_row(sid, today)
                sub_daily_status = str(
                    sub_daily_state.get("status", "")
                ).strip().lower()

                if sub_task_hint:
                    st.caption(sub_task_hint)
                elif (
                    sub_state.get("configured")
                    and sub_state.get("today_count", 0) > 0
                ):
                    # 最後の項目を完了して自動停止した後も、
                    # 本日の登録と取り消し操作を確認できるように残す。
                    _finished_sub_name = str(
                        sub_state.get("sub_name", "")
                    ).strip()
                    st.caption(
                        f"サブ：{_finished_sub_name} / 本日の項目を完了（停止中）"
                    )

                _show_sub_controls = bool(
                    sub_state.get("configured")
                    and (
                        sub_state.get("is_active")
                        or sub_state.get("today_count", 0) > 0
                    )
                )

                if (
                    _show_sub_controls
                    and sid not in _sub_progress_button_rendered
                ):
                    _sub_progress_button_rendered.add(sid)

                    _today_count = int(
                        sub_state.get("today_count", 0) or 0
                    )
                    _today_names = list(
                        sub_state.get("today_item_names", []) or []
                    )

                    if sub_daily_status == "skip":
                        st.caption("本日：－ サブ課題は実施なしで確認済み")
                    elif _today_count > 0 or sub_daily_status == "done":
                        _today_items_text = "、".join(_today_names)
                        st.caption(
                            f"本日：✅ {_today_count or 1}項目確認済み"
                            + (
                                f"（{_today_items_text}）"
                                if _today_items_text
                                else ""
                            )
                        )
                    elif sub_daily_status == "pending":
                        st.warning("本日：⚠ サブ課題確認未")
                    else:
                        st.caption("本日：出欠登録後に確認対象")

                    _confirm_key = f"sub_undo_confirm_{sid}"
                    _confirming_undo = bool(
                        st.session_state.get(_confirm_key, False)
                    )

                    if not _confirming_undo:
                        _sub_btn1, _sub_btn2, _sub_btn3 = st.columns(3)

                        with _sub_btn1:
                            if sub_state.get("is_active"):
                                if st.button(
                                    "✅ サブ課題完了 → 次へ",
                                    key=f"sub_progress_next_{sid}_{slot}_{i}",
                                    help="現在表示されているサブ課題を完了として記録し、日別確認も完了にします。",
                                ):
                                    _ok, _message = complete_and_confirm_sub_daily(
                                        sid, today
                                    )
                                    st.session_state["sub_progress_flash"] = _message
                                    st.session_state["sub_progress_flash_is_error"] = not _ok
                                    st.rerun()

                        with _sub_btn2:
                            if (
                                sub_state.get("is_active")
                                and sub_daily_status == "pending"
                            ):
                                if st.button(
                                    "今日は実施なし",
                                    key=f"sub_progress_skip_today_{sid}_{slot}_{i}",
                                    help="今日はサブ課題を行わなかったことを確認済みにします。",
                                ):
                                    _ok, _message = mark_sub_daily_skip(
                                        sid, today
                                    )
                                    st.session_state["sub_progress_flash"] = _message
                                    st.session_state["sub_progress_flash_is_error"] = not _ok
                                    st.rerun()

                        with _sub_btn3:
                            if sub_state.get("has_latest_completion"):
                                if st.button(
                                    "↩ 直前の完了を取り消す",
                                    key=f"sub_progress_undo_open_{sid}_{slot}_{i}",
                                    help="直前に完了したサブ課題を未完了へ戻します。確認後に実行されます。",
                                ):
                                    st.session_state[_confirm_key] = True
                                    st.rerun()

                    else:
                        _undo_item_name = str(
                            sub_state.get("latest_item_name", "")
                        ).strip()
                        _undo_completed_at = str(
                            sub_state.get("latest_completed_at", "")
                        ).strip()
                        _undo_when = (
                            f"（登録：{_undo_completed_at}）"
                            if _undo_completed_at
                            else ""
                        )

                        st.warning(
                            f"「{_undo_item_name}」の完了{_undo_when}を取り消し、"
                            "この項目へ戻します。"
                        )

                        _undo_confirm_col, _undo_cancel_col = st.columns(2)

                        with _undo_confirm_col:
                            if st.button(
                                "取り消して戻す",
                                key=f"sub_progress_undo_confirm_{sid}_{slot}_{i}",
                                type="primary",
                            ):
                                _latest_completed_at_before_undo = str(
                                    sub_state.get("latest_completed_at", "")
                                ).strip()
                                _ok, _message = undo_latest_student_sub_completion(sid)
                                if _ok and _latest_completed_at_before_undo:
                                    _undo_date = pd.to_datetime(
                                        _latest_completed_at_before_undo,
                                        errors="coerce",
                                    )
                                    if pd.notna(_undo_date):
                                        reconcile_sub_daily_after_undo(
                                            sid,
                                            _undo_date.strftime("%Y-%m-%d"),
                                        )
                                st.session_state[_confirm_key] = False
                                st.session_state["sub_progress_flash"] = _message
                                st.session_state["sub_progress_flash_is_error"] = not _ok
                                st.rerun()

                        with _undo_cancel_col:
                            if st.button(
                                "やめる",
                                key=f"sub_progress_undo_cancel_{sid}_{slot}_{i}",
                            ):
                                st.session_state[_confirm_key] = False
                                st.rerun()

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

                # d285:
                # 今日の予定側から「状態」と「授業 / 自習」を取得する。
                # 座席表では、名前の前に 📘（授業）/ 📝（自習）を付けて見分けやすくする。
                _today_status_map = {}
                _today_type_map = {}
                if "student_id" in today_view.columns and "slot" in today_view.columns:
                    _tmp_tv = today_view.copy()
                    _tmp_tv["student_id"] = _tmp_tv["student_id"].astype(str).str.strip()
                    _tmp_tv["slot_norm"] = _tmp_tv["slot"].astype(str).str.strip().map(normalize_slot)
                    for _, _r in _tmp_tv.iterrows():
                        _key = (str(_r.get("student_id", "")).strip(), str(_r.get("slot_norm", "")).strip())
                        _today_status_map[_key] = str(_r.get("状態", "")).strip()

                        _session_type = str(_r.get("session_type", "")).strip()
                        if not _session_type:
                            _session_type = str(_r.get("種別", "")).strip()
                        _today_type_map[_key] = "自習" if "自習" in _session_type else "授業"

                for _, _r in seat_mini_src.iterrows():
                    _sid = str(_r.get("student_id", "")).strip()
                    _slot = str(_r.get("slot_norm", "")).strip()
                    _seat_no = str(_r.get("seat_no", "")).strip()
                    if not _sid or not _seat_no:
                        continue

                    _seat_session_type = _today_type_map.get((_sid, _slot), "")
                    _seat_type_label = (
                        "📝 自習" if _seat_session_type == "自習"
                        else "📘 授業" if _seat_session_type == "授業"
                        else ""
                    )
                    _seat_exam_grade = str(today_exam_grade_map.get(_sid, "")).strip()
                    _seat_exam_label = (
                        f"🎫 {_seat_exam_grade}級"
                        if _sid in today_exam_ids and _seat_exam_grade
                        else "🎫 検定"
                        if _sid in today_exam_ids
                        else ""
                    )

                    seat_mini_rows.append({
                        "コマ": _slot,
                        "席": f"席{_seat_no}",
                        "生徒": _seat_name_map.get(_sid, _sid),
                        "種別": _seat_type_label,
                        "検定": _seat_exam_label,
                        "_session_type": _seat_session_type,
                        "_exam_grade": _seat_exam_grade if _sid in today_exam_ids else "",
                        "状態": _today_status_map.get((_sid, _slot), ""),
                        "メモ": str(_r.get("note", "")).strip(),
                        "_slot_num": pd.to_numeric(_slot, errors="coerce"),
                        "_seat_num": pd.to_numeric(_seat_no, errors="coerce"),
                    })

        if seat_mini_rows:
            seat_mini = pd.DataFrame(seat_mini_rows)
            seat_mini = seat_mini.sort_values(by=["_slot_num", "_seat_num", "生徒"], na_position="last")

            st.subheader("🪑 今日の座席")
            st.caption("横＝席、縦＝コマです。🎫＝検定 / 📘＝授業 / 📝＝自習")

            # d223:
            # 席ごとの縦カードではなく、コマ×席の表にする。
            # これで「このコマは席1と席4が空いている」などを見やすくする。
            try:
                _seat_slot_label_map = build_slot_label_map(timeslots)
            except Exception:
                _seat_slot_label_map = {}

            def _seat_table_slot_label(slot_value: str) -> str:
                slot_value = normalize_slot(slot_value)
                try:
                    # format_slot_label が使える環境では時間も含める
                    return format_slot_label(slot_value, _seat_slot_label_map)
                except Exception:
                    return f"{slot_value}コマ"

            seat_table_rows = []

            # 基本は1〜7コマを表示する。
            # 保存済み座席に想定外のコマがあれば、それも落とさず追加する。
            base_slots = ["1", "2", "3", "4", "5", "6", "7"]
            existing_slots = []
            if "コマ" in seat_mini.columns:
                existing_slots = [
                    normalize_slot(x)
                    for x in seat_mini["コマ"].astype(str).str.strip().tolist()
                    if normalize_slot(x)
                ]
            slot_options_for_table = []
            for _s in base_slots + existing_slots:
                _s = normalize_slot(_s)
                if _s and _s not in slot_options_for_table:
                    slot_options_for_table.append(_s)

            for _slot in slot_options_for_table:
                row = {"コマ": _seat_table_slot_label(_slot)}
                for _seat_no in ["1", "2", "3", "4", "5"]:
                    _seat_label = f"席{_seat_no}"
                    _cell_df = seat_mini[
                        (seat_mini["コマ"].astype(str).str.strip().map(normalize_slot) == _slot)
                        & (seat_mini["席"].astype(str).str.strip() == _seat_label)
                    ].copy()

                    if _cell_df.empty:
                        row[_seat_label] = "空席"
                    else:
                        names = []
                        for _, _sr in _cell_df.sort_values(by=["生徒"], na_position="last").iterrows():
                            _name = str(_sr.get("生徒", "")).strip()
                            _session_type = str(_sr.get("_session_type", "")).strip()
                            _exam_grade = str(_sr.get("_exam_grade", "")).strip()

                            _marks = []
                            if _exam_grade:
                                _marks.append("🎫")
                            if _session_type == "自習":
                                _marks.append("📝")
                            elif _session_type == "授業":
                                _marks.append("📘")

                            if _marks and _name:
                                _name = f"{' '.join(_marks)} {_name}"

                            _note = str(_sr.get("メモ", "")).strip()
                            if _note:
                                _name = f"{_name}\n({_note})"
                            if _name:
                                names.append(_name)
                        row[_seat_label] = "\n".join(names) if names else "空席"

                seat_table_rows.append(row)

            seat_table_df = pd.DataFrame(seat_table_rows)

            if not seat_table_df.empty:
                def _style_today_seat_table(val):
                    v = str(val).strip()
                    if v == "空席":
                        return "color: #999999; background-color: #f7f7f7;"
                    return "font-weight: 700;"

                st.dataframe(
                    seat_table_df.style.map(_style_today_seat_table, subset=["席1", "席2", "席3", "席4", "席5"]),
                    use_container_width=True,
                    hide_index=True,
                )

            with st.expander("一覧表で確認", expanded=False):
                show_mini_cols = ["コマ", "席", "生徒", "種別", "検定", "状態", "メモ"]
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
            st.caption("授業・自習・欠席を選び、「出欠を保存／更新」で保存します。確認済みの記録も同じ方法で上書きできます。")

            _prep_flash = st.session_state.pop("preparation_flash", "")
            if _prep_flash:
                st.success(_prep_flash)

            _prep_status_df = load_preparation_log().copy()
            _prep_total = len(today_view)
            _prep_done_count = int(
                (today_view["準備"].astype(str) == "✅ 準備済").sum()
            )
            _prep_pending_count = max(0, _prep_total - _prep_done_count)

            st.markdown("### 🧰 今日の準備チェック")
            if _prep_pending_count == 0:
                st.success(f"全員の準備が完了しています（{_prep_done_count}/{_prep_total}）")
            else:
                st.warning(
                    f"未準備 {_prep_pending_count}人／準備済み {_prep_done_count}人"
                )

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
                # d224:
                # 2コマ連続で「授業＋自習」が混ざる場合がある。
                # 以前は selfstudy が1件でもあると自習表示に寄っていたため、
                # 表示用ラベルは「授業＋自習」とし、記録の初期値は授業を優先する。
                planned_kind_map = {}
                planned_kind_label_map = {}
                if not today_view.empty and {"student_id", "session_type"}.issubset(today_view.columns):
                    tmp_tv = today_view[["student_id", "session_type"]].copy()
                    tmp_tv["student_id"] = tmp_tv["student_id"].fillna("").astype(str).str.strip()
                    tmp_tv["session_type"] = tmp_tv["session_type"].fillna("").astype(str).str.strip().str.lower()

                    for sid2, g in tmp_tv.groupby("student_id"):
                        vals = set(g["session_type"].tolist())
                        has_lesson = any(v in ["lesson", "授業", ""] for v in vals)
                        has_self = any(v in ["self", "selfstudy", "自習"] for v in vals)

                        if has_lesson and has_self:
                            planned_kind_map[sid2] = "lesson"
                            planned_kind_label_map[sid2] = "授業＋自習"
                        elif has_self:
                            planned_kind_map[sid2] = "selfstudy"
                            planned_kind_label_map[sid2] = "自習"
                        else:
                            planned_kind_map[sid2] = "lesson"
                            planned_kind_label_map[sid2] = "授業"

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

                # d298:
                # 欠席・キャンセルは「来なかった/予定取消」の処理済み扱い。
                # 進捗未登録としては出さない。
                missing_progress_ids = [
                    sid for sid in done_ids
                    if (sid not in prog_today_ids)
                    and (sid not in prog_skip_today_ids)
                    and normalize_attendance_kind_for_lock(
                        (rec_map.get(sid) or {}).get("kind", "")
                    ) not in ["absence", "cancel"]
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
                                
                # d315:
                # 確認済みの出欠も同じカードで編集し、「記録/更新」で上書きする。
                # 修正方法を統一するため、「未登録に戻す」操作は廃止した。
                show_done = st.checkbox(
                    "確認済みを表示（修正・上書き可能）",
                    value=False,
                    key=f"att_show_done_{today}",
                    help="ONにすると、記録済みの出欠を表示します。授業・自習・欠席を選び直して「出欠を保存／更新」を押すと上書きできます。",
                )

                # d299:
                # 出欠登録後に自動で生徒画面へ寄せると便利だが、
                # その分、課題画面の判定・表示切替も走りやすい。
                # 忙しい日はOFFのまま保存だけにすると体感が軽い。
                open_after_attendance_save = st.checkbox(
                    "出欠登録後にこの生徒を自動で開く",
                    value=False,
                    key=f"att_open_after_save_{today}",
                    help="通常OFF推奨。ONにすると、出欠登録後にその生徒の課題画面へ寄せます。",
                )

                st.markdown(f"**未確認：{len(pending_ids)}件**")
                target_ids = pending_ids if not show_done else (pending_ids + done_ids)


                if not target_ids:
                    st.success("未確認の出席記録はありません。")
                else:
                    for sid in target_ids:
                        nm = name_map.get(sid, "")
                        label = f"{sid}｜{nm}" if nm else sid


                        rec = rec_map.get(sid)
                        rec_kind = (rec.get("kind", "") if rec else "").strip()
                        rec_memo = (rec.get("memo", "") if rec else "").strip()


                        # d315: 授業・自習・欠席を同じ選択欄から登録／上書きする。
                        kind_options = [
                            ("lesson", "授業"),
                            ("selfstudy", "自習"),
                            ("absence", "欠席"),
                        ]


                        # 初期値の優先順
                        # 1) 授業＋自習予定なら、授業回数カウントを守るため lesson を優先
                        # 2) 既存の出席記録
                        # 3) 今日の予定の種別（例外を含む）
                        # 4) lesson
                        default_kind = "lesson"

                        planned_label = str(planned_kind_label_map.get(sid, "")).strip()
                        planned_kind_for_sid = str(planned_kind_map.get(sid, "")).strip()

                        # d256:
                        # 授業＋自習なのに過去/既存ログが selfstudy になっていると、
                        # 授業回数に入らず「0回→今日で1回目」のようなズレが出る。
                        # 予定上「授業＋自習」の日は、既存 rec_kind が selfstudy でも lesson を優先する。
                        is_lesson_and_selfstudy_plan = (
                            planned_label == "授業＋自習"
                            or (planned_kind_for_sid == "lesson" and rec_kind in ["selfstudy", "自習"])
                        )

                        if rec_kind in ["absence", "欠席", "cancel", "キャンセル"]:
                            default_kind = "absence"
                        elif is_lesson_and_selfstudy_plan:
                            default_kind = "lesson"
                        elif rec_kind in ["selfstudy", "自習"]:
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

                                if rec_kind in ["selfstudy", "self", "自習"]:
                                    kind_text = "自習"
                                elif rec_kind in ["absence", "欠席"]:
                                    kind_text = "欠席"
                                elif rec_kind in ["cancel", "キャンセル"]:
                                    kind_text = "キャンセル"
                                elif rec_kind in ["lesson", "授業"]:
                                    kind_text = "授業"
                                else:
                                    kind_text = planned_kind_label_map.get(sid, "授業" if default_kind == "lesson" else "自習")

                                kind_badge = f"📘 {kind_text}" if "授業" in kind_text else f"🟡 {kind_text}"
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

                                # d256:
                                # 既存の出欠ログが selfstudy だが、予定は授業＋自習の場合は警告する。
                                # 「記録/更新」を押すと、種別が lesson として保存され、授業回数に入る。
                                if (
                                    rec_kind in ["selfstudy", "自習"]
                                    and str(planned_kind_label_map.get(sid, "")).strip() == "授業＋自習"
                                ):
                                    st.warning("⚠ 授業＋自習予定ですが、出欠ログは自習として保存されています。記録/更新で授業扱いに直せます。")



                            with c2:
                                _plan_rows_for_prep = today_view[
                                    today_view["student_id"].astype(str).str.strip()
                                    == str(sid).strip()
                                ]
                                _prep_slots = [
                                    normalize_slot(x)
                                    for x in _plan_rows_for_prep["slot"].tolist()
                                    if normalize_slot(x)
                                ]
                                if not _prep_slots:
                                    _prep_slots = [""]

                                _prep_current = all(
                                    is_prepared_for_plan(
                                        _prep_status_df,
                                        d=today,
                                        student_id=sid,
                                        slot=_slot,
                                    )
                                    for _slot in _prep_slots
                                )

                                _prep_checked = st.checkbox(
                                    "🧰 準備完了",
                                    value=bool(_prep_current),
                                    key=f"prep_done_{today}_{sid}",
                                    help="準備が終わったらチェック。外すと未準備へ戻ります。",
                                )

                                if _prep_checked != _prep_current:
                                    _prep_updated = set_preparation_status(
                                        _prep_status_df,
                                        d=today,
                                        student_id=sid,
                                        slots=_prep_slots,
                                        prepared=_prep_checked,
                                    )
                                    save_preparation_log(_prep_updated)
                                    st.session_state["preparation_flash"] = (
                                        f"{label}を"
                                        + (
                                            "準備済みにしました。"
                                            if _prep_checked
                                            else "未準備に戻しました。"
                                        )
                                    )
                                    st.rerun()

                                opt_labels = [x[1] for x in kind_options]
                                opt_vals = [x[0] for x in kind_options]
                                idx = opt_vals.index(default_kind) if default_kind in opt_vals else 0
                                picked = st.selectbox(
                                    "記録する種別",
                                    opt_labels,
                                    index=idx,
                                    key=f"att_kind_{today}_{sid}",
                                    help="出席ログは1日1生徒につき1種類で保存します。授業＋自習が混在する日は、進捗確認が必要なため授業を優先して記録するのがおすすめです。"
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
                                # d253:
                                # 出欠種別に合わせて「進捗なしで完了」の初期値を変える。
                                # 自習だけの日は進捗登録不要なのでON。
                                # 授業・授業＋自習は進捗確認が必要なのでOFF。
                                # すでに「進捗なしで完了」済みの生徒はONで表示する。
                                _picked_kind_norm = str(picked_kind).strip().lower()
                                _no_progress_default = (
                                    _picked_kind_norm
                                    in [
                                        "selfstudy",
                                        "self",
                                        "自習",
                                        "absence",
                                        "欠席",
                                        "cancel",
                                        "キャンセル",
                                    ]
                                    or str(sid).strip() in prog_skip_today_ids
                                )
                                no_progress_done = st.checkbox(
                                    "進捗なしで完了にする",
                                    value=bool(_no_progress_default),
                                    key=f"no_progress_done_{today}_{sid}_{_picked_kind_norm}"
                                )


                            with c5:
                                if st.button("💾 出欠を保存／更新", key=f"att_save_{today}_{sid}"):
                                    # d315:
                                    # 授業・自習・欠席を同じボタンで登録／上書きする。
                                    # 欠席へ変更した場合は予定取消と座席解除も行う。
                                    # 欠席から授業・自習へ戻した場合は、欠席時の予定取消を解除する。
                                    save_kind = picked_kind
                                    if (
                                        save_kind != "absence"
                                        and str(
                                            planned_kind_label_map.get(sid, "")
                                        ).strip()
                                        == "授業＋自習"
                                    ):
                                        save_kind = "lesson"

                                    if save_kind == "absence":
                                        absence_note = (
                                            memo.strip()
                                            if str(memo).strip()
                                            else "出欠登録画面で欠席を保存（予定取消）"
                                        )
                                        (
                                            att_df2,
                                            ov2,
                                            seat2,
                                            cancel_count,
                                        ) = apply_absence_and_cancel_schedule(
                                            att_df=att_df,
                                            overrides_df=schedule_overrides,
                                            seat_df=seat_assignments,
                                            plan_df=today_view,
                                            student_id=sid,
                                            d=today,
                                            note=absence_note,
                                        )
                                        # 入力されたメモと回数を出欠ログへ反映する。
                                        att_df2 = upsert_attendance(
                                            att_df2,
                                            sid,
                                            today,
                                            "absence",
                                            memo,
                                            count=count,
                                        )
                                        save_attendance_log(att_df2)
                                        write_csv_atomic(
                                            ov2,
                                            SCHEDULE_OVERRIDES_CSV,
                                        )
                                        write_csv_atomic(
                                            seat2,
                                            SEAT_ASSIGNMENTS_CSV,
                                        )
                                        st.success(
                                            f"欠席で保存しました。予定 {cancel_count}件をキャンセルし、座席も外しました。"
                                        )
                                    else:
                                        # 以前の記録が欠席／キャンセルなら、
                                        # 同日の対象コマに付いた取消を解除してから通常出欠へ上書きする。
                                        ov2 = schedule_overrides.copy()
                                        att_base = att_df.copy()
                                        if normalize_attendance_kind_for_lock(
                                            rec_kind
                                        ) in ["absence", "cancel"]:
                                            for _slot in collect_plan_slots_for_student(
                                                today_view,
                                                sid,
                                            ):
                                                (
                                                    ov2,
                                                    att_base,
                                                    _,
                                                ) = restore_cancelled_plan_and_clear_absence(
                                                    ov2,
                                                    att_base,
                                                    student_id=sid,
                                                    d=today,
                                                    slot=_slot,
                                                )
                                            write_csv_atomic(
                                                ov2,
                                                SCHEDULE_OVERRIDES_CSV,
                                            )

                                        att_df2 = upsert_attendance(
                                            att_base,
                                            sid,
                                            today,
                                            save_kind,
                                            memo,
                                            count=count,
                                        )
                                        save_attendance_log(att_df2)
                                        st.success("出欠記録を上書き保存しました。")

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

                                    if open_after_attendance_save:
                                        if nm:
                                            st.session_state["pending_sidebar_student"] = nm

                                        # d299:
                                        # 自動ジャンプをONにした時だけ、検定/通常課題の寄せ先判定を行う。
                                        try:
                                            _picked_kind_for_view = str(save_kind).strip().lower()
                                            if _picked_kind_for_view not in ["selfstudy", "self", "自習"]:
                                                if is_kentei_training_active(sid) or has_unpassed_kentei_exam_schedule(sid, kentei_exam):
                                                    st.session_state["sidebar_view_mode"] = "検定課題"
                                                else:
                                                    st.session_state["sidebar_view_mode"] = "カリキュラム課題"
                                        except Exception:
                                            st.session_state["sidebar_view_mode"] = "カリキュラム課題"

                                    st.rerun()





                # d299:
                # 確認済みの簡易一覧も、必要時だけ描画する。
                # expanderは閉じていても中の処理が走るため、チェックでガードする。
                show_done_summary = st.checkbox(
                    "確認済みの簡易一覧を表示",
                    value=False,
                    key=f"att_show_done_summary_{today}",
                    help="確認済み一覧を見たい時だけONにします。通常OFFの方が軽くなります。",
                )

                if show_done_summary and done_ids:
                    with st.expander(f"✅ 確認済み（{len(done_ids)}件）", expanded=False):
                        for sid in done_ids:
                            nm = name_map.get(sid, "")
                            label = f"{sid}｜{nm}" if nm else sid
                            rec = rec_map.get(sid)
                            rec_kind = (rec.get("kind", "") if rec else "").strip()
                            rec_memo = (rec.get("memo", "") if rec else "").strip()


                            rec_kind_norm = normalize_attendance_kind_for_lock(rec_kind)
                            if rec_kind_norm == "selfstudy":
                                kind_label = "自習"
                            elif rec_kind_norm == "absence":
                                kind_label = "欠席"
                            elif rec_kind_norm == "cancel":
                                kind_label = "キャンセル"
                            else:
                                kind_label = "授業"


                            _summary_rows = today_view[
                                today_view["student_id"].astype(str).str.strip()
                                == str(sid).strip()
                            ]
                            _summary_prepared = (
                                not _summary_rows.empty
                                and (_summary_rows["準備"].astype(str) == "✅ 準備済").all()
                            )
                            _summary_prep_label = "✅ 準備済" if _summary_prepared else "⬜ 未準備"
                            st.markdown(
                                f"- **{label}** ／ {_summary_prep_label} ／ {kind_label}"
                                + (f" ／ {rec_memo}" if rec_memo else "")
                            )

        # =====================================================
        # ⌨️ タイピング5分チェック（d296）
        # -----------------------------------------------------
        # 出席登録済みの子だけを対象にする。
        # まだ来ていない子は未完了に出さず、来た子だけ残るようにする。
        # =====================================================
        with st.expander("⌨️ タイピング5分チェック", expanded=True):
            st.caption(
                "出席登録済みの生徒だけを対象にします。"
                "終わったら「完了」、今日は不要なら「免除」を押します。"
            )

            typing_df = load_typing_log()
            typing_att_df = load_attendance_log()

            typing_student_name_map = {}
            if not students.empty and {"student_id", "display_name"}.issubset(students.columns):
                _typing_students = students.copy()
                _typing_students["student_id"] = (
                    _typing_students["student_id"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
                _typing_students["display_name"] = (
                    _typing_students["display_name"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
                typing_student_name_map = dict(
                    zip(
                        _typing_students["student_id"],
                        _typing_students["display_name"],
                    )
                )

            # 今日出席登録済みの生徒を抽出
            typing_att_today = typing_att_df.copy()
            for _c in ["date", "student_id", "kind", "memo"]:
                if _c not in typing_att_today.columns:
                    typing_att_today[_c] = ""
                typing_att_today[_c] = (
                    typing_att_today[_c]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

            if not typing_att_today.empty:
                typing_att_today["kind_norm"] = typing_att_today["kind"].map(
                    normalize_attendance_kind_for_lock
                )
                typing_att_today = typing_att_today[
                    typing_att_today["date"].astype(str).str.strip().eq(str(today))
                    & typing_att_today["kind_norm"].isin(["lesson", "selfstudy"])
                ].copy()

            attended_ids_raw = []
            if not typing_att_today.empty:
                for _sid in typing_att_today["student_id"].astype(str).tolist():
                    _sid = str(_sid).strip()
                    if _sid and _sid not in attended_ids_raw:
                        attended_ids_raw.append(_sid)

            # 表示順は、今日の予定表の順番を優先する。
            planned_order_ids = []
            if "student_id" in today_view.columns and not today_view.empty:
                _typing_today_order = today_view.copy()
                if "slot_num" in _typing_today_order.columns:
                    _typing_today_order = _typing_today_order.sort_values(
                        ["slot_num", "display_name"],
                        na_position="last",
                    )
                for _sid in _typing_today_order["student_id"].astype(str).tolist():
                    _sid = str(_sid).strip()
                    if _sid and _sid not in planned_order_ids:
                        planned_order_ids.append(_sid)

            attended_set = set(attended_ids_raw)
            typing_target_ids = [
                _sid for _sid in planned_order_ids if _sid in attended_set
            ]
            for _sid in attended_ids_raw:
                if _sid not in typing_target_ids:
                    typing_target_ids.append(_sid)

            if not typing_target_ids:
                st.info("出席登録済みの生徒がまだいないため、タイピングチェック対象はありません。")
            else:
                typing_pending_ids = []
                typing_done_rows = []
                typing_skip_rows = []

                for _sid in typing_target_ids:
                    _rec = get_typing_today(typing_df, _sid, today)
                    _status = str((_rec or {}).get("status", "")).strip().lower()
                    if _status == "done":
                        typing_done_rows.append((_sid, _rec))
                    elif _status == "skip":
                        typing_skip_rows.append((_sid, _rec))
                    else:
                        typing_pending_ids.append(_sid)

                if typing_pending_ids:
                    st.error(f"タイピング未完了：{len(typing_pending_ids)}件")
                else:
                    st.success("出席登録済みの生徒は、全員タイピング完了または免除済みです。")

                st.markdown(f"**未完了：{len(typing_pending_ids)}件**")

                if typing_pending_ids:
                    for _sid in typing_pending_ids:
                        _name = typing_student_name_map.get(_sid, "")
                        _label = f"{_sid}｜{_name}" if _name else _sid

                        _att_rec = None
                        if not typing_att_today.empty:
                            _hit = typing_att_today[
                                typing_att_today["student_id"]
                                .astype(str)
                                .str.strip()
                                .eq(_sid)
                            ].copy()
                            if not _hit.empty:
                                _att_rec = _hit.iloc[-1].to_dict()

                        _kind_norm = str((_att_rec or {}).get("kind_norm", "")).strip()
                        _kind_label = "自習" if _kind_norm == "selfstudy" else "授業"

                        tc1, tc2, tc3 = st.columns([4, 1.5, 1.5])
                        with tc1:
                            st.write(f"・**{_label}** ／ {_kind_label}")
                        with tc2:
                            if st.button("✅ 完了", key=f"typing_done_{today}_{_sid}"):
                                typing_df2 = upsert_typing_log(
                                    typing_df,
                                    _sid,
                                    today,
                                    "done",
                                    "",
                                )
                                save_typing_log(typing_df2)
                                st.success(f"{_label} のタイピングを完了にしました。")
                                st.rerun()
                        with tc3:
                            if st.button("今日は免除", key=f"typing_skip_{today}_{_sid}"):
                                typing_df2 = upsert_typing_log(
                                    typing_df,
                                    _sid,
                                    today,
                                    "skip",
                                    "今日は免除",
                                )
                                save_typing_log(typing_df2)
                                st.success(f"{_label} を今日は免除にしました。")
                                st.rerun()
                else:
                    st.caption("未完了の生徒はいません。")

                completed_count = len(typing_done_rows) + len(typing_skip_rows)
                if completed_count:
                    show_typing_completed = st.checkbox(
                        f"完了・免除済み（{completed_count}件）を表示",
                        value=False,
                        key=f"typing_show_completed_{today}",
                        help="完了済み一覧を見たい時だけONにします。通常OFFの方が軽くなります。",
                    )
                    if show_typing_completed:
                        with st.expander(f"完了・免除済み（{completed_count}件）", expanded=True):
                            for _sid, _rec in typing_done_rows + typing_skip_rows:
                                _name = typing_student_name_map.get(_sid, "")
                                _label = f"{_sid}｜{_name}" if _name else _sid
                                _status = typing_status_label((_rec or {}).get("status", ""))
                                _completed_at = str((_rec or {}).get("completed_at", "")).strip()
                                _note = str((_rec or {}).get("note", "")).strip()

                                tc1, tc2 = st.columns([5, 1.5])
                                with tc1:
                                    line = f"・**{_label}** ／ {_status}"
                                    if _completed_at:
                                        line += f" ／ {_completed_at[11:16] if len(_completed_at) >= 16 else _completed_at}"
                                    if _note:
                                        line += f" ／ {_note}"
                                    st.markdown(line)
                                with tc2:
                                    if st.button("↩ 未完了へ戻す", key=f"typing_undo_{today}_{_sid}"):
                                        typing_df2 = delete_typing_log(
                                            typing_df,
                                            _sid,
                                            today,
                                        )
                                        save_typing_log(typing_df2)
                                        st.success(f"{_label} を未完了に戻しました。")
                                        st.rerun()


        # =====================================================
        # =====================================================
        # d237:
        # 閲覧側のワンクリック取消は、カレンダー操作と重複して混乱しやすいため通常非表示。
        # 予定の取消・解除・削除は月スケジュールカレンダーへ集約する。
        # =====================================================
        show_legacy_quick_cancel = st.checkbox(
            "旧UI：閲覧から予定取消を表示（通常OFF）",
            value=False,
            key=f"show_legacy_quick_cancel_{today}",
            help="通常は 管理（入力）→月スケジュールカレンダー の「取消」を使います。"
        )
        if show_legacy_quick_cancel:
            # =====================================================
            # ↩ 旧UI：今日の予定から取消
            # =====================================================
            with st.expander("↩ 旧UI：今日の予定から取消", expanded=False):
                st.caption("通常は月スケジュールカレンダーの「取消」を使います。必要時だけここを使います。")


                if today_view.empty:
                    st.info("今日の予定がないため、取消対象はありません。")
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
                        st.success("取消できる予定はありません。")
                    else:
                        # d294:
                        # 出欠登録済みの予定は、予定側から取消できないようにする。
                        # 実績登録済み ＞ 予定取消。
                        _quick_cancel_attended_keys = build_attended_student_date_keys(
                            load_attendance_log()
                        )

                        for i, r in cancel_src.reset_index(drop=True).iterrows():
                            sid = str(r.get("student_id", "")).strip()
                            name = str(r.get("display_name", "")).strip()
                            slot = str(r.get("slot", "")).strip()
                            start = str(r.get("start", "")).strip()
                            end = str(r.get("end", "")).strip()
                            _quick_attendance_locked = is_attendance_locked_plan(
                                _quick_cancel_attended_keys,
                                sid,
                                today,
                            )


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
                                if _quick_attendance_locked:
                                    st.caption("出欠登録済みのため取消不可")
                                if st.button(
                                    "取消",
                                    key=f"quick_cancel_{today}_{sid}_{slot}_{i}",
                                    disabled=_quick_attendance_locked,
                                    help=(
                                        "出欠登録済みの予定は、予定側から取消できません。"
                                        "先に出欠記録を未登録へ戻してください。"
                                        if _quick_attendance_locked
                                        else "この予定を取消します。"
                                    ),
                                ):
                                    ov2 = upsert_schedule_override_row(
                                        schedule_overrides,
                                        student_id=sid,
                                        d=today,
                                        slot=slot,
                                        action="キャンセル",
                                        note="旧UI：今日の予定から取消",
                                    )
                                    write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)

                                    seat_assignments2 = remove_seat_assignment_for_plan(
                                        seat_assignments,
                                        d=today,
                                        student_id=sid,
                                        slot=slot,
                                    )
                                    write_csv_atomic(seat_assignments2, SEAT_ASSIGNMENTS_CSV)

                                    st.success("取消しました。座席も空席にしました。")
                                    st.rerun()



        # 対象日の例外入力UI（schedule_overrides.csv） ※ここだけ
        # - 「対象日の予定の下」専用
        # - 管理画面の例外入力は将来的に削除予定（重複事故防止）
        # =====================================================
        # d299:
        # Streamlitのexpanderは閉じていても中身の処理が走るため、
        # 日付指定の例外修正はチェックON時だけ読み込む。
        show_date_override_panel = st.checkbox(
            "🧩 日付指定の例外修正を使う（必要時のみ）",
            value=False,
            key=f"show_date_override_panel_{today}",
            help="ONにした時だけ、対象日の予定を読み込みます。普段はOFFの方が軽くなります。",
        )
        if show_date_override_panel:
            st.caption("基本操作は月スケジュールカレンダーで行います。ここは過去日・未来日を日付指定で修正したい時だけ使います。取消＝取消線が残る操作です。")

            # 例外DF（ヘッダーは既存前提：safe_read_csvで列は揃っている想定）
            ov_df = schedule_overrides.copy()
            if ov_df.empty:
                ov_df = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"])

            picked_override_date = st.date_input(
                "対象日",
                value=today,
                key="ov_target_date",
                help="今日以外の日付も選べます。翌日に気づいたキャンセル・追加の修正に使います。",
            )
            picked_override_date_str = picked_override_date.strftime("%Y-%m-%d")

            override_target_view = build_daily_plan_for_date(
                picked_override_date,
                students,
                student_schedule,
                monthly_schedule,
                schedule_overrides,
                timeslots,
                include_inactive=include_inactive,
            )

            # 対象日の予定を見ながら、その場で取消できるようにする
            # d294:
            # 出欠登録済みの予定は取消不可にする。
            # 予定取消より、実績である出欠記録を優先する。
            _ov_attended_keys = build_attended_student_date_keys(
                load_attendance_log()
            )

            st.markdown("#### 対象日の予定")
            if override_target_view.empty:
                st.info("対象日の予定はありません。")
            else:
                _ov_plan = override_target_view.copy()
                for _c in ["slot", "start", "end", "display_name", "student_id", "session_type", "note"]:
                    if _c not in _ov_plan.columns:
                        _ov_plan[_c] = ""
                    _ov_plan[_c] = _ov_plan[_c].fillna("").astype(str).str.strip()
                _ov_plan["slot_num"] = pd.to_numeric(_ov_plan["slot"], errors="coerce")
                _ov_plan = _ov_plan.sort_values(["slot_num", "display_name"], na_position="last")

                for _i, _r in _ov_plan.reset_index(drop=True).iterrows():
                    _sid = str(_r.get("student_id", "")).strip()
                    _slot = normalize_slot(_r.get("slot", ""))
                    _name = str(_r.get("display_name", "")).strip() or _sid
                    _start = str(_r.get("start", "")).strip()
                    _end = str(_r.get("end", "")).strip()
                    _type = str(_r.get("session_type", "")).strip() or "授業"
                    _time = f"{_slot}コマ" + (f"（{_start}〜{_end}）" if (_start or _end) else "")
                    _ov_attendance_locked = is_attendance_locked_plan(
                        _ov_attended_keys,
                        _sid,
                        picked_override_date,
                    )

                    pc1, pc2 = st.columns([6, 1.5])
                    with pc1:
                        st.write(f"{_time} / {_name} / {_type}")
                        if _ov_attendance_locked:
                            st.caption("🔒 出欠登録済みのため、この画面からは取消できません。")
                    with pc2:
                        if st.button(
                            "この予定を取消",
                            key=f"ov_plan_cancel_{picked_override_date_str}_{_sid}_{_slot}_{_i}",
                            disabled=_ov_attendance_locked,
                            help=(
                                "出欠登録済みの予定は、予定側から取消できません。"
                                "先に出欠記録を未登録へ戻してください。"
                                if _ov_attendance_locked
                                else "この予定を取消線付きで取消します。"
                            ),
                        ):
                            ov2 = upsert_schedule_override_row(
                                ov_df,
                                student_id=_sid,
                                d=picked_override_date,
                                slot=_slot,
                                action="キャンセル",
                                note="日付指定の例外修正から取消",
                            )
                            write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)
                            seat2 = remove_seat_assignment_for_plan(
                                seat_assignments,
                                d=picked_override_date,
                                student_id=_sid,
                                slot=_slot,
                            )
                            write_csv_atomic(seat2, SEAT_ASSIGNMENTS_CSV)
                            st.success("取消しました。")
                            st.rerun()
            st.divider()

            # -----------------------------
            # 生徒候補（対象日の予定の生徒を先頭に）
            # -----------------------------
            stu_for_pick = base_students[["student_id", "display_name"]].copy()
            stu_for_pick["student_id"] = stu_for_pick["student_id"].astype(str).str.strip()
            stu_for_pick["display_name"] = stu_for_pick["display_name"].astype(str).str.strip()

            ids_in_target_day = []
            
            active_ids = set(
                students[
                    students["is_active"].fillna("").astype(str).str.strip().str.lower().replace("", "true").isin(["true", "1", "yes"])
                ]["student_id"].astype(str).str.strip().tolist()
            )

            ids_in_target_day = [sid for sid in ids_in_target_day if sid in active_ids]

            if "student_id" in override_target_view.columns and not override_target_view.empty:
                for _sid in override_target_view["student_id"].astype(str).tolist():
                    _sid = str(_sid).strip()
                    if _sid and _sid not in ids_in_target_day:
                        ids_in_target_day.append(_sid)

            # 対象日の予定にいない生徒は後ろ（表示名で安定ソート）
            rest_ids = [sid for sid in stu_for_pick["student_id"].tolist() if sid and sid not in ids_in_target_day]
            rest_ids_sorted = sorted(rest_ids, key=lambda s: str(stu_for_pick.loc[stu_for_pick["student_id"] == s, "display_name"].iloc[0] if (stu_for_pick["student_id"] == s).any() else s))

            ordered_ids = ids_in_target_day + rest_ids_sorted
            valid_ids = [sid for sid in ordered_ids if sid in stu_for_pick["student_id"].tolist()]
            stu_for_pick = stu_for_pick.set_index("student_id").loc[valid_ids].reset_index()

            name_map = dict(zip(stu_for_pick["student_id"], stu_for_pick["display_name"]))
            labels = [f"{sid} | {name_map.get(sid,'')}".strip(" |") for sid in stu_for_pick["student_id"].tolist()]

            if not labels:
                st.info("生徒が見つからないため、例外入力はできません。")
            else:
                # --- 対象日の予定から、選択した生徒の「デフォルト値」を引く ---
                # ルール：
                #   1) 対象日の予定に入っている生徒なら、その生徒の最初のコマをデフォルト
                #   2) start/end/session_type はその行の値を初期値に
                #
                # Streamlitの制約：widget生成後にsession_stateを書き換えられない
                # → 生徒選択(selectbox)の後、他widget生成の前にdefaultsをsession_stateへ流し込む


                # --- UI（フォームは使わない：生徒を選び直した時に即時で他項目が追従するように） ---
                c1, c2, c3, c4 = st.columns([3, 2, 2, 3])

                with c1:
                    picked_label = st.selectbox("生徒", labels, index=0, key="ov_student_label")
                    picked_sid = picked_label.split("|")[0].strip()

                # 対象日の予定（その生徒）を抽出
                _stu_rows = pd.DataFrame()
                if "student_id" in override_target_view.columns and not override_target_view.empty:
                    _stu_rows = override_target_view[override_target_view["student_id"].astype(str).str.strip() == str(picked_sid).strip()].copy()

                # 候補slot（対象日の予定のコマを初期値にしつつ、全コマ候補から選べるようにする）
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

                # d311:
                # 固定スケジュール画面専用の変数へ依存しない。
                # 閲覧画面内で timeslots から表示名を作る。
                slot_label_map = build_slot_label_map(timeslots)


                # 対象日の予定に start/end がある場合は、そちらを優先して上書き
                if not _stu_rows.empty and "slot" in _stu_rows.columns:
                    for _, _r in _stu_rows.iterrows():
                        _s_norm = normalize_slot(_r.get("slot", ""))
                        if not _s_norm:
                            continue
                        try:
                            _s_int = int(_s_norm)
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
                    # 既にその日に予定がある生徒は、二重表示を避けるため「時間変更」を初期値にする
                    has_target_plan = not _stu_rows.empty
                    action_options = ["時間変更", "取消", "追加", "特別追加"]
                    default_action_index = 0 if has_target_plan else 2

                    picked_action = st.selectbox(
                        "操作",
                        action_options,
                        index=default_action_index,
                        key="override_action",
                        help="取消＝キャンセル記録を残します。時間変更＝その日の通常予定を置き換えます。追加/特別追加＝2コマ連続・振替追加など、本当に予定を増やす時に使います。",
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
                scoped_prefix = f"{picked_override_date_str}_{str(picked_sid).strip()}_{int(cur_slot)}"
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

                submitted = st.button("対象日の例外として保存", key="ov_submit_btn")
                if submitted:
                    dstr = picked_override_date_str

                    save_action = str(picked_action).strip()
                    save_note = str(picked_note).strip()
                    if save_action == "取消":
                        save_action = "キャンセル"
                    if save_action == "特別追加":
                        # 2時間連続など、本当に予定を増やす時だけ使う
                        save_action = "追加"
                        save_note = (save_note + " / " if save_note else "") + "特別追加"
                    elif save_action == "追加" and not _stu_rows.empty:
                        # d217:
                        # 予定がある生徒に対して、ユーザーが明示的に「追加」を選んだ場合は
                        # 2コマ連続・振替追加など「本当に増やす」意図として扱う。
                        # 以前のように時間変更へ自動変換すると、2コマ連続が1コマに上書きされる。
                        save_action = "追加"
                        save_note = (save_note + " / " if save_note else "") + "特別追加"

                    ov2 = upsert_schedule_override_row(
                        ov_df,
                        student_id=str(picked_sid).strip(),
                        d=dstr,
                        slot=str(int(picked_slot)),
                        action=save_action,
                        start=str(picked_start).strip(),
                        end=str(picked_end).strip(),
                        session_type=str(picked_session_type).strip(),
                        note=save_note,
                    )

                    write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)
                    st.success("保存しました。対象日の予定に反映されます。")
                    st.rerun()
            st.divider()

            # 対象日の例外一覧（削除ボタン付き）
            dstr = picked_override_date_str
            ov_show = ov_df.copy()
            if not ov_show.empty:
                for c in ["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]:
                    if c in ov_show.columns:
                        ov_show[c] = ov_show[c].fillna("").astype(str).str.strip()
                ov_today_list = ov_show[ov_show["date"] == dstr].copy()
            else:
                ov_today_list = pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"])

            if ov_today_list.empty:
                st.info("対象日の例外はまだありません。")
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

                st.caption("取消行は「解除」で戻せます。追加・時間変更などの例外行は、登録ミスとして削除できます。")
                for i, r in ov_today_list.reset_index(drop=True).iterrows():
                    sid = str(r.get("student_id","")).strip()
                    slot = str(r.get("slot","")).strip()
                    action = str(r.get("action","")).strip()
                    label = str(r.get("label","")).strip()
                    action_label = format_override_action(action)
                    if normalize_action_value(action) == "キャンセル":
                        btn = f"↩ 解除：{label} / slot {slot}"
                    else:
                        btn = f"🗑 登録ミスとして削除：{label} / slot {slot} / {action_label}"
                    if st.button(btn, key=f"ov_del_{dstr}_{sid}_{slot}_{action}_{i}"):
                        ov2 = ov_df.copy()
                        for c in ["student_id", "date", "slot", "action"]:
                            if c in ov2.columns:
                                ov2[c] = ov2[c].fillna("").astype(str).str.strip()
                        mask = (
                            (ov2["student_id"] == sid)
                            & (ov2["date"] == dstr)
                            & (ov2["slot"].map(normalize_slot) == normalize_slot(slot))
                            & (ov2["action"].map(normalize_action_value) == normalize_action_value(action))
                        )
                        ov2 = ov2[~mask].copy()
                        write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)
                        if normalize_action_value(action) == "キャンセル":
                            st.success("取消を解除しました。")
                        else:
                            st.success("登録ミスとして削除しました。")
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
    # 表示切替（整理版）
    # ---------------------------------------------------------
    # d225:
    # 毎日使う「進捗登録」と、たまに見る「確認・一覧」を分ける。
    # 機能本体はそのままに、迷いにくい導線へ整理する。
    # =========================================================
    daily_view_options = ["カリキュラム課題", "検定課題"]
    check_view_options = [
        "コース別（件数）",
        "Scratch検定一覧",
        "生徒ごと一覧",
        "生徒別（done）",
        "詳細（最新状態）",
    ]
    all_view_options = daily_view_options + check_view_options

    # 他ボタンから「カリキュラム課題へ寄せる」などが来た場合に反映
    pending_view_mode = str(st.session_state.pop("sidebar_view_mode", "") or "").strip()
    if pending_view_mode in all_view_options:
        st.session_state["view_mode_trial"] = pending_view_mode
        st.session_state["view_mode_group"] = (
            "毎日使う：進捗登録" if pending_view_mode in daily_view_options else "たまに見る：確認・一覧"
        )

    current_view_mode = str(st.session_state.get("view_mode_trial", "カリキュラム課題"))
    default_group = "毎日使う：進捗登録" if current_view_mode in daily_view_options else "たまに見る：確認・一覧"

    st.markdown("### 表示切替")
    view_group = st.radio(
        "用途",
        ["毎日使う：進捗登録", "たまに見る：確認・一覧"],
        index=0 if default_group == "毎日使う：進捗登録" else 1,
        horizontal=True,
        key="view_mode_group",
    )

    if view_group == "毎日使う：進捗登録":
        view_options = daily_view_options
        st.caption("出席後に進捗を登録する時に使う画面です。")
    else:
        view_options = check_view_options
        st.caption("状況確認・一覧・分析寄りの画面です。必要な時だけ開きます。")

    # グループを切り替えた時に、前回の選択が候補外なら先頭へ戻す
    if str(st.session_state.get("view_mode_trial", "")) not in view_options:
        st.session_state["view_mode_trial"] = view_options[0]

    sidebar_view_mode = st.radio(
        "表示内容",
        view_options,
        horizontal=True,
        key="view_mode_trial",
    )

    is_log_view = sidebar_view_mode in check_view_options


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
            st.session_state["pending_admin_section"] = "📘 カリキュラム管理"
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

                    # d236:
                    # カリキュラム課題のコース一覧を現場で見やすい順に整える。
                    # まずScratch系（sc_l / sc_h）を上に置き、その後HTML、JavaScript系を優先する。
                    def _curriculum_course_priority(row):
                        cid = str(row.get("course_id", "")).strip().lower()
                        cname = str(row.get("course_name", "")).strip().lower()
                        gname = str(row.get("genre_name", "")).strip().lower()
                        joined = f"{cid} {cname} {gname}"

                        if cid == "sc_l" or "sc_l" in joined or "scratch_l" in joined:
                            return 0
                        if cid == "sc_h" or "sc_h" in joined or "scratch_h" in joined:
                            return 1
                        if "scratch" in joined or "スクラッチ" in joined:
                            return 2
                        if "html" in joined:
                            return 10
                        if "javascript" in joined or "java script" in joined or cid in ["js", "javascript"]:
                            return 11
                        if "python" in joined:
                            return 20
                        if "unity" in joined:
                            return 21
                        return 99

                    cc["_ui_priority"] = cc.apply(_curriculum_course_priority, axis=1)
                    cc = cc.sort_values(by=["_ui_priority", "order_num", "genre_name", "course_name"], na_position="last")

                    course_labels = []
                    course_ids = []
                    course_label_by_id = {}
                    for _, r in cc.iterrows():
                        cid = str(r["course_id"]).strip()
                        label = f"{r['genre_name']}｜{r['course_name']}  [{cid}]"
                        course_ids.append(cid)
                        course_labels.append(label)
                        course_label_by_id[cid] = label

                    # d247:
                    # 進捗登録画面のコース選択も「今日やる候補」と同じ考え方へ寄せる。
                    # 最新コースがコース完了済みなら、次の未完了課題があるコースを推奨する。
                    def _course_done_by_log_for_progress(_sid: str, _course_id: str) -> bool:
                        try:
                            _sid = str(_sid).strip()
                            _course_id = str(_course_id).strip()

                            _course_row = curr_courses[
                                curr_courses["course_id"].astype(str).str.strip() == _course_id
                            ].copy()
                            if _course_row.empty:
                                return False

                            _genre_id = str(_course_row.iloc[0].get("genre_id", "")).strip()
                            _course_name = str(_course_row.iloc[0].get("course_name", "")).strip()

                            _log = log.copy()
                            if _log.empty:
                                return False
                            for _c in ["student_id", "curriculum", "item", "status"]:
                                if _c not in _log.columns:
                                    _log[_c] = ""
                                _log[_c] = _log[_c].fillna("").astype(str).str.strip()

                            _mask = (
                                (_log["student_id"].astype(str).str.strip() == _sid)
                                & (_log["curriculum"].astype(str).str.strip() == _genre_id)
                                & (_log["item"].astype(str).str.strip() == _course_name)
                                & (_log["status"].astype(str).str.strip().str.lower() == "done")
                            )
                            return bool(_mask.any())
                        except Exception:
                            return False

                    def _has_unfinished_task_for_progress(_sid: str, _course_id: str) -> bool:
                        try:
                            _sid = str(_sid).strip()
                            _course_id = str(_course_id).strip()
                            if not _sid or not _course_id:
                                return False

                            _tasks = curr_tasks.copy()
                            for _c in ["course_id", "task_id", "task_name", "order", "is_active", "student_id"]:
                                if _c not in _tasks.columns:
                                    _tasks[_c] = ""
                                _tasks[_c] = _tasks[_c].fillna("").astype(str).str.strip()

                            _tasks = _tasks[
                                (_tasks["course_id"].astype(str).str.strip() == _course_id)
                                & (
                                    (_tasks["student_id"].astype(str).str.strip() == "")
                                    | (_tasks["student_id"].astype(str).str.strip() == _sid)
                                )
                            ].copy()

                            if "is_active" in _tasks.columns:
                                _active = _tasks["is_active"].astype(str).str.strip().str.lower()
                                _tasks = _tasks[_active.replace("", "true").isin(["true", "1", "yes"])].copy()

                            if _tasks.empty:
                                return False

                            _prog = curr_prog.copy()
                            for _c in ["student_id", "course_id", "task_id", "is_done", "is_skip"]:
                                if _c not in _prog.columns:
                                    _prog[_c] = ""
                                _prog[_c] = _prog[_c].fillna("").astype(str).str.strip()

                            _prog = _prog[
                                (_prog["student_id"].astype(str).str.strip() == _sid)
                                & (_prog["course_id"].astype(str).str.strip() == _course_id)
                            ].copy()

                            _done_map = {
                                str(_r.get("task_id", "")).strip(): str(_r.get("is_done", "")).strip().lower() == "true"
                                for _, _r in _prog.iterrows()
                            }
                            _skip_map = {
                                str(_r.get("task_id", "")).strip(): str(_r.get("is_skip", "")).strip().lower() == "true"
                                for _, _r in _prog.iterrows()
                            }

                            for _, _t in _tasks.iterrows():
                                _tid = str(_t.get("task_id", "")).strip()
                                if not _tid:
                                    continue
                                if not _done_map.get(_tid, False) and not _skip_map.get(_tid, False):
                                    return True

                            return False
                        except Exception:
                            return False

                    def _recommend_progress_course_id(_sid: str) -> tuple[str, str]:
                        _sid = str(_sid).strip()
                        if not course_ids:
                            return "", "表示できるコースがありません。"

                        _latest_course_id = latest_course_for_student(_sid, curr_prog)
                        _latest_course_id = str(_latest_course_id).strip() if _latest_course_id else ""

                        _ordered_course_ids = [str(x).strip() for x in course_ids if str(x).strip()]
                        _candidate_course_ids = []

                        if _latest_course_id and _latest_course_id in _ordered_course_ids:
                            _idx = _ordered_course_ids.index(_latest_course_id)
                            _candidate_course_ids.extend(_ordered_course_ids[_idx:])
                            _candidate_course_ids.extend(_ordered_course_ids[:_idx])
                        else:
                            _candidate_course_ids.extend(_ordered_course_ids)

                        _seen = set()
                        _candidate_course_ids = [
                            _cid for _cid in _candidate_course_ids
                            if _cid and not (_cid in _seen or _seen.add(_cid))
                        ]

                        for _cid in _candidate_course_ids:
                            if _course_done_by_log_for_progress(_sid, _cid):
                                continue
                            if _has_unfinished_task_for_progress(_sid, _cid):
                                if _cid == _latest_course_id:
                                    return _cid, "この生徒の最新カリキュラム進捗から選択しています。"
                                return _cid, "最新コースが完了済み、または未完了課題がないため、次の未完了課題があるコースを選択しています。"

                        # 全部完了/未登録の場合は、手動確認できるよう最新コースか先頭へ戻す
                        if _latest_course_id and _latest_course_id in _ordered_course_ids:
                            return _latest_course_id, "未完了課題が見つからないため、最新コースを表示しています。"
                        return _ordered_course_ids[0], "未完了課題が見つからないため、先頭コースを表示しています。"

                    default_course_id, progress_course_reason = _recommend_progress_course_id(student_id)
                    if default_course_id not in course_ids:
                        default_course_id = course_ids[0] if course_ids else ""

                    recommended_course_label = course_label_by_id.get(default_course_id, course_labels[0] if course_labels else "")
                    progress_course_key = f"progress_course_{student_id}"
                    progress_course_recommend_key = f"progress_course_recommended_{student_id}"

                    if st.session_state.get(progress_course_recommend_key) != recommended_course_label:
                        st.session_state[progress_course_key] = recommended_course_label
                        st.session_state[progress_course_recommend_key] = recommended_course_label
                    elif progress_course_key not in st.session_state:
                        st.session_state[progress_course_key] = recommended_course_label

                    selected_course_label = st.selectbox(
                        "コース",
                        course_labels,
                        key=progress_course_key,
                        help="完了済みコースを避け、次に未完了課題があるコースを推奨表示します。必要なら手動で変更できます。",
                    )
                    selected_course_id = selected_course_label.split("[")[-1].rstrip("]")

                    if selected_course_label == recommended_course_label:
                        st.caption(f"現在表示中：{selected_course_id}｜判定理由：{progress_course_reason}")
                    else:
                        st.warning(f"現在表示中：{selected_course_id}｜推奨は {default_course_id} です。必要なら手動変更のままでOKです。")

                    # d252:
                    # 「推奨コースに戻す」ボタンは削除。
                    # selectbox生成後に同じsession_stateを書き換えるとStreamlitでエラーになりやすく、
                    # プルダウンで手動選択できるため、ボタンは置かない。

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
                    
                    # d272:
                    # コース完了は、progress_log.csv の note=course_done の行だけで判定する。
                    # 通常の課題完了ログと混ざらないようにする。
                    for _c in ["student_id", "curriculum", "item", "status", "note"]:
                        if _c not in log.columns:
                            log[_c] = ""
                        log[_c] = log[_c].fillna("").astype(str).str.strip()

                    course_done_mask = (
                        log["student_id"].astype(str).str.strip() == str(student_id).strip()
                    ) & (
                        log["curriculum"].astype(str).str.strip() == str(genre_id).strip()
                    ) & (
                        log["item"].astype(str).str.strip() == str(course_name).strip()
                    ) & (
                        log["status"].astype(str).str.strip().str.lower() == "done"
                    ) & (
                        log["note"].astype(str).str.strip() == "course_done"
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
                        if is_course_done:
                            if override_done_lock:
                                st.warning("編集ロック解除中：コース完了を取り消せます。")
                                confirm_cancel_course_done_here = st.checkbox(
                                    "本当にこのコース完了だけを取り消す",
                                    value=False,
                                    key=f"confirm_cancel_course_done_here_{student_id}_{selected_course_id}",
                                )
                                if st.button(
                                    "↩ コース完了を取り消す",
                                    disabled=not confirm_cancel_course_done_here,
                                    key=f"cancel_course_done_here_{student_id}_{selected_course_id}",
                                ):
                                    df_log = log.copy()
                                    for _c in ["student_id", "curriculum", "item", "status", "note"]:
                                        if _c not in df_log.columns:
                                            df_log[_c] = ""
                                        df_log[_c] = df_log[_c].fillna("").astype(str).str.strip()

                                    cancel_mask = (
                                        (df_log["student_id"].astype(str).str.strip() == str(student_id).strip())
                                        & (df_log["curriculum"].astype(str).str.strip() == str(genre_id).strip())
                                        & (df_log["item"].astype(str).str.strip() == str(course_name).strip())
                                        & (df_log["status"].astype(str).str.strip().str.lower() == "done")
                                        & (df_log["note"].astype(str).str.strip() == "course_done")
                                    )
                                    df_log = df_log.loc[~cancel_mask].reset_index(drop=True)
                                    write_csv_atomic(df_log, PROGRESS_LOG_CSV)
                                    st.success("コース完了を取り消しました。課題ごとの完了・スキップ記録は残っています。")
                                    st.rerun()
                            else:
                                st.caption("コース完了を取り消す場合は、左の『完了済み課題を編集する』をONにしてください。")

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
                    if override_done_lock:
                        st.warning("⚠ 完了済み課題の編集ロックを解除中です。完了済みのプルダウンも変更できます。")
                    updated_rows = []

                    state_options = ["未実施", "完了", "スキップ"]

                    for _, row in t.iterrows():
                        task_id = str(row["task_id"]).strip()
                        task_name = str(row["task_name"]).strip()
                        task_display_name = task_name if task_name else f"{task_id}｜（課題名未設定）"
                        was_done = bool(done_map.get(task_id, False))
                        was_skip = bool(skip_map.get(task_id, False))
                        prev_done_date = str(done_date_map.get(task_id, "")).strip()
                        task_label = (
                            f"{task_display_name}　（完了日：{prev_done_date}）"
                            if was_done and prev_done_date
                            else task_display_name
                        )


                        if was_done:
                            default_state = "完了"
                        elif was_skip:
                            default_state = "スキップ"
                        else:
                            default_state = "未実施"


                        disabled = (was_done and is_locked_done_tasks)

                        # d272:
                        # Streamlitは同じkeyのselectbox状態を保持するため、
                        # CSV上は完了になっていても、画面だけ古い「未実施」のまま残ることがある。
                        # 元データ由来のdefault_stateが変わった時だけ、widget状態を同期する。
                        state_key = f"curr_state_{student_id}_{selected_course_id}_{task_id}"
                        source_key = f"{state_key}__source_default"
                        if st.session_state.get(source_key) != default_state:
                            st.session_state[state_key] = default_state
                            st.session_state[source_key] = default_state


                        selected_state = st.selectbox(
                            task_label,
                            state_options,
                            index=state_options.index(default_state),
                            key=state_key,
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
                                if selected_state == "完了" and default_state != "完了"
                                else prev_done_date
                            ) if selected_state == "完了" else "",
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

                        # d272:
                        # 保存後は、次回表示時にCSV側の状態を正としてプルダウンを再同期する。
                        for _r in updated_rows:
                            _tid = str(_r.get("task_id", "")).strip()
                            _k = f"curr_state_{student_id}_{selected_course_id}_{_tid}"
                            st.session_state.pop(f"{_k}__source_default", None)

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


        # d235:
        # 検定課題で表示する級を安定化する。
        # - exam_date が空なら date を見る
        # - 合格済み級は推奨から外す
        # - 選択状態を生徒ごとのkeyに分け、他の操作後に級が揺れにくくする
        # 優先順位：
        #   1) 今日以降の検定予定のうち、未合格で一番近い級
        #   2) 検定予定が合格済み級だけなら、次の未合格級
        #   3) 予定がなければ、次の未合格級
        #   4) 全級合格済みなら1級
            grade_options = ["1", "2", "3", "4"]
            grade_progress_order = ["4", "3", "2", "1"]

            # 合格済み級を取得
            _passed_grades = set()
            try:
                _results_for_grade = load_kentei_results().copy()
                if not _results_for_grade.empty:
                    for _c in ["student_id", "grade"]:
                        if _c not in _results_for_grade.columns:
                            _results_for_grade[_c] = ""
                        _results_for_grade[_c] = _results_for_grade[_c].fillna("").astype(str).str.strip()
                    _passed_grades = set(
                        _results_for_grade[
                            _results_for_grade["student_id"].astype(str).str.strip() == student_id
                        ]["grade"].astype(str).str.strip().tolist()
                    )
            except Exception:
                _passed_grades = set()

            def _next_unpassed_kentei_grade():
                for _g in grade_progress_order:
                    if _g not in _passed_grades:
                        return _g
                return "1"

            _recommended_k_grade = None
            _recommended_k_reason = ""
            _recommended_k_exam_date = ""
            _passed_schedule_notes = []

            try:
                if not kentei_exam.empty:
                    dfk = kentei_exam.copy()
                    for _c in ["student_id", "grade", "exam_date", "date", "kentei", "exam_type", "note"]:
                        if _c not in dfk.columns:
                            dfk[_c] = ""
                        dfk[_c] = dfk[_c].fillna("").astype(str).str.strip()

                    dfk = dfk[dfk["student_id"].astype(str).str.strip() == student_id].copy()

                    if not dfk.empty:
                        dfk["__date_raw"] = dfk["exam_date"].where(
                            dfk["exam_date"].astype(str).str.strip() != "",
                            dfk["date"],
                        )
                        dfk["__d"] = pd.to_datetime(dfk["__date_raw"], errors="coerce")
                        dfk["grade"] = dfk["grade"].astype(str).str.strip()
                        dfk = dfk[dfk["grade"].isin(grade_options)].copy()

                        if not dfk.empty:
                            _passed_sched = dfk[dfk["grade"].isin(_passed_grades)].copy()
                            if not _passed_sched.empty:
                                _passed_schedule_notes = [
                                    f"{str(_r.get('grade', '')).strip()}級（{str(_r.get('__date_raw', '')).strip() or '日付なし'}）"
                                    for _, _r in _passed_sched.iterrows()
                                ]

                            dfk_unpassed = dfk[~dfk["grade"].isin(_passed_grades)].copy()

                            today_ts_for_grade = pd.Timestamp(date.today()).normalize()
                            future_dfk = dfk_unpassed[
                                dfk_unpassed["__d"].notna() & (dfk_unpassed["__d"] >= today_ts_for_grade)
                            ].sort_values("__d", ascending=True).copy()

                            if not future_dfk.empty:
                                picked_row = future_dfk.iloc[0]
                                _recommended_k_grade = str(picked_row.get("grade", "")).strip()
                                _recommended_k_exam_date = str(picked_row.get("__date_raw", "")).strip()
                                _recommended_k_reason = f"未合格の検定予定で一番近い級（{_recommended_k_exam_date}）を表示しています。"
                            elif not dfk_unpassed.empty:
                                dated_dfk = dfk_unpassed[dfk_unpassed["__d"].notna()].sort_values("__d", ascending=False).copy()
                                if not dated_dfk.empty:
                                    picked_row = dated_dfk.iloc[0]
                                else:
                                    picked_row = dfk_unpassed.iloc[0]
                                _recommended_k_grade = str(picked_row.get("grade", "")).strip()
                                _recommended_k_exam_date = str(picked_row.get("__date_raw", "")).strip()
                                _recommended_k_reason = "今日以降の未合格検定予定がないため、この生徒の未合格の検定予定から級を表示しています。"
            except Exception as _e:
                _recommended_k_grade = None
                _recommended_k_reason = f"検定予定の読み取りで確認が必要です：{_e}"

            if _recommended_k_grade not in grade_options:
                _recommended_k_grade = _next_unpassed_kentei_grade()
                if _passed_schedule_notes:
                    _recommended_k_reason = "検定予定が合格済み級だけのため、次の未合格級を表示しています。"
                else:
                    _recommended_k_reason = "未合格の検定予定がないため、次の未合格級を表示しています。"

            # d250:
            # 検定練習中フラグがONで級が保存されている場合は、その級を推奨級として扱う。
            _training_active_for_student = is_kentei_training_active(student_id)
            _training_grade_for_student = get_kentei_training_grade(student_id)
            if _training_active_for_student and _training_grade_for_student in grade_options:
                _recommended_k_grade = _training_grade_for_student
                _recommended_k_reason = "検定練習中フラグがONのため、この級を表示しています。"

            _grade_key = f"kentei_grade_{student_id}"
            _grade_recommend_key = f"kentei_grade_recommended_{student_id}"

            # 推奨級が変わった時だけ、その生徒の選択状態を推奨級へ戻す。
            if st.session_state.get(_grade_recommend_key) != _recommended_k_grade:
                st.session_state[_grade_key] = _recommended_k_grade
                st.session_state[_grade_recommend_key] = _recommended_k_grade

            current_grade_value = st.session_state.get(_grade_key, _recommended_k_grade)
            current_grade_index = grade_options.index(current_grade_value) if current_grade_value in grade_options else grade_options.index(_recommended_k_grade)

            grade_sel = st.selectbox(
                "検定の級",
                grade_options,
                index=current_grade_index,
                key=_grade_key,
                help="推奨級は、未合格の検定予定を優先して自動判定します。手動変更もできます。"
            )

            if grade_sel == _recommended_k_grade:
                st.caption(f"現在表示中：{grade_sel}級｜判定理由：{_recommended_k_reason}")
            else:
                st.warning(f"現在表示中：{grade_sel}級｜推奨は {_recommended_k_grade}級 です。理由：{_recommended_k_reason}")

            if _passed_schedule_notes:
                st.warning(
                    "合格済み級の検定予定が残っています："
                    + "、".join(_passed_schedule_notes)
                    + "。必要なら管理（入力）→検定予定登録で予定を整理してください。"
                )

            # d250:
            # このチェックがONなら、次に見る候補・出欠後の動線で検定課題を優先する。
            _training_before = is_kentei_training_active(student_id)
            _training_now = st.checkbox(
                "この子は検定練習中（次に見る候補で検定課題を優先）",
                value=_training_before,
                key=f"kentei_training_flag_{student_id}",
                help="ONにすると、検定予定が未登録でもこの生徒は検定課題を優先表示します。",
            )
            if _training_now != _training_before:
                upsert_kentei_training_status(
                    student_id=student_id,
                    is_training=bool(_training_now),
                    grade=grade_sel if _training_now else "",
                    note="検定課題画面から更新",
                )
                st.success("検定練習中フラグを更新しました。")
                st.rerun()

            if _training_now:
                _saved_training_grade = get_kentei_training_grade(student_id)
                if _saved_training_grade and _saved_training_grade != str(grade_sel):
                    st.warning(f"検定練習中の保存級は {_saved_training_grade}級 です。現在表示中は {grade_sel}級 です。")
                    if st.button("この級を検定練習中に更新", key=f"kentei_training_update_grade_{student_id}_{grade_sel}"):
                        upsert_kentei_training_status(
                            student_id=student_id,
                            is_training=True,
                            grade=grade_sel,
                            note="検定課題画面から対象級を更新",
                        )
                        st.success(f"検定練習中の対象級を {grade_sel}級 に更新しました。")
                        st.rerun()
                else:
                    st.caption(f"検定練習中：{grade_sel}級を優先表示します。")

            # d249:
            # 「推奨級に戻す」ボタンは、selectbox生成後に同じsession_stateを書き換えて
            # StreamlitAPIException が出ることがあるため削除。
            # 推奨級と違う級を見ている場合は、上のプルダウンから手動で推奨級を選び直す運用にする。

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
                task_label = (
                    f"{task_name}　（完了日：{prev_done_date}）"
                    if was_done and prev_done_date
                    else task_name
                )


                if was_done:
                    default_state = "完了"
                elif was_skip:
                    default_state = "スキップ"
                else:
                    default_state = "未実施"

                disabled = is_locked or (was_done and not override_done_lock)

                selected_state = st.selectbox(
                    task_label,
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
                        if selected_state == "完了" and default_state != "完了"
                        else prev_done_date
                    ) if selected_state == "完了" else "",
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
            with st.expander("🎓 検定 合格登録（B方式）", expanded=True):
                # kentei_results.csv を合格判定の唯一の正にする
                results_df = load_kentei_results().copy()

                # 対象生徒：左フィルタで選ばれていれば固定、なければ選択
                if selected_student == "（全員）":
                    st.info("左のフィルタから、生徒を1人選んでください。")
                    st.stop()


                student_for_pass = str(student_id).strip()
                st.info(f"対象生徒: {student_for_pass}｜{selected_student}")

                # =====================================================
                # 🎫 検定予定から結果登録
                # -----------------------------------------------------
                # 予定のある子は、予定日・級を先に選んでから結果登録できるようにする。
                # ボタンを押すと、下の新規登録フォームへ級・受験日・メモを自動入力する。
                # =====================================================
                st.markdown("### 🎫 検定予定から結果登録")

                _exam_for_pass = kentei_exam.copy() if 'kentei_exam' in globals() else pd.DataFrame()
                if _exam_for_pass.empty:
                    st.caption("この生徒の検定予定はまだありません。下の手動登録を使えます。")
                else:
                    for _c in ["student_id", "exam_date", "date", "exam_type", "kentei", "grade", "note"]:
                        if _c not in _exam_for_pass.columns:
                            _exam_for_pass[_c] = ""
                        _exam_for_pass[_c] = _exam_for_pass[_c].fillna("").astype(str).str.strip()

                    _exam_for_pass = _exam_for_pass[
                        _exam_for_pass["student_id"].astype(str).str.strip() == student_for_pass
                    ].copy()

                    if _exam_for_pass.empty:
                        st.caption("この生徒の検定予定はまだありません。下の手動登録を使えます。")
                    else:
                        _exam_for_pass["_exam_date_raw"] = _exam_for_pass["exam_date"].where(
                            _exam_for_pass["exam_date"].astype(str).str.strip() != "",
                            _exam_for_pass["date"],
                        )
                        _exam_for_pass["_exam_dt"] = pd.to_datetime(_exam_for_pass["_exam_date_raw"], errors="coerce")
                        _exam_for_pass["_exam_date_str"] = _exam_for_pass["_exam_dt"].dt.strftime("%Y-%m-%d")
                        _exam_for_pass["_exam_date_str"] = _exam_for_pass["_exam_date_str"].fillna(_exam_for_pass["_exam_date_raw"])
                        _exam_for_pass["_exam_name"] = _exam_for_pass["exam_type"].where(
                            _exam_for_pass["exam_type"].astype(str).str.strip() != "",
                            _exam_for_pass["kentei"],
                        )

                        _results_chk = results_df.copy()
                        for _c in ["student_id", "grade", "result", "pass_date"]:
                            if _c not in _results_chk.columns:
                                _results_chk[_c] = ""
                            _results_chk[_c] = (
                                _results_chk[_c]
                                .fillna("")
                                .astype(str)
                                .str.strip()
                            )
                        _results_chk.loc[
                            _results_chk["result"].eq(""),
                            "result",
                        ] = "合格"

                        def _kentei_result_status(_r):
                            _g = str(_r.get("grade", "")).strip()
                            _d = str(_r.get("_exam_date_str", "")).strip()
                            if not _g:
                                return "級未設定"
                            if _results_chk.empty:
                                return "未登録"
                            _same_grade = _results_chk[
                                (_results_chk["student_id"].astype(str).str.strip() == student_for_pass)
                                & (_results_chk["grade"].astype(str).str.strip() == _g)
                            ].copy()
                            if _same_grade.empty:
                                return "未登録"
                            if _d:
                                _same_date = _same_grade[
                                    _same_grade["pass_date"]
                                    .astype(str)
                                    .str.strip()
                                    .eq(_d)
                                ]
                                if not _same_date.empty:
                                    _result_value = str(
                                        _same_date.iloc[-1].get(
                                            "result",
                                            "合格",
                                        )
                                    ).strip() or "合格"
                                    return f"登録済み（{_result_value}）"
                            return "同じ級の受験履歴あり"

                        _exam_for_pass["状態"] = _exam_for_pass.apply(_kentei_result_status, axis=1)

                        # =====================================================
                        # ⚠ 検定結果 未登録アラート
                        # -----------------------------------------------------
                        # 予定日が今日以前で、まだ結果登録が必要なものを
                        # 予定一覧より先に出して、登録漏れを防ぐ。
                        # 「同じ級の登録あり」は、予定日と一致する結果ではないため
                        # 確認が必要な状態として扱う。
                        # =====================================================
                        _today_ts_for_alert = pd.Timestamp(date.today()).normalize()
                        _alert_mask = (
                            _exam_for_pass["_exam_dt"].notna()
                            & (_exam_for_pass["_exam_dt"] <= _today_ts_for_alert)
                            & (_exam_for_pass["状態"].astype(str).str.strip().isin(["未登録", "同じ級の受験履歴あり"]))
                        )
                        _exam_alert_rows = _exam_for_pass[_alert_mask].copy()

                        if not _exam_alert_rows.empty:
                            st.warning(f"⚠ 検定結果 未登録・確認必要：{len(_exam_alert_rows)}件あります")
                            st.caption("予定日が今日以前で、まだ結果登録が完了していない可能性がある検定です。下の「この予定で入力」から登録できます。")

                            _alert_show = _exam_alert_rows.copy()
                            _alert_show["受験日"] = _alert_show["_exam_date_str"].astype(str).str.strip()
                            _alert_show["級"] = _alert_show["grade"].astype(str).str.strip().apply(lambda x: f"{x}級" if x else "級未設定")
                            _alert_show["検定"] = _alert_show["_exam_name"].astype(str).str.strip()
                            _alert_show["メモ"] = _alert_show["note"].astype(str).str.strip()
                            _alert_show = _alert_show[["受験日", "級", "検定", "状態", "メモ"]]
                            st.dataframe(_alert_show, use_container_width=True, hide_index=True)
                        else:
                            st.success("この生徒の検定結果未登録アラートはありません。")

                        _today_ts = pd.Timestamp(date.today())
                        def _priority(_r):
                            _dt = _r.get("_exam_dt", pd.NaT)
                            _status = str(_r.get("状態", "")).strip()
                            if pd.isna(_dt):
                                return 9
                            if _status in ["未登録", "同じ級の受験履歴あり"]:
                                if _dt.date() == date.today():
                                    return 0
                                if _dt < _today_ts:
                                    # 過去分の未登録は上に出す
                                    return 1
                                return 2
                            return 5

                        _exam_for_pass["_priority"] = _exam_for_pass.apply(_priority, axis=1)
                        _exam_for_pass = _exam_for_pass.sort_values(["_priority", "_exam_dt"], na_position="last").head(10).copy()

                        st.caption("予定を選ぶと、下の新規登録フォームに級・受験日・メモが入ります。点数を入力して保存してください。")

                        for _i, _r in _exam_for_pass.reset_index(drop=True).iterrows():
                            _date_str = str(_r.get("_exam_date_str", "")).strip()
                            _grade_str = str(_r.get("grade", "")).strip()
                            _exam_name = str(_r.get("_exam_name", "")).strip() or "検定"
                            _note_str = str(_r.get("note", "")).strip()
                            _status_str = str(_r.get("状態", "")).strip()

                            _c1, _c2, _c3, _c4, _c5 = st.columns([1.3, 1, 1.8, 1.3, 1.4])
                            with _c1:
                                st.write(_date_str or "日付未設定")
                            with _c2:
                                st.write(f"{_grade_str}級" if _grade_str else "級未設定")
                            with _c3:
                                st.write(_exam_name)
                                if _note_str:
                                    st.caption(_note_str)
                            with _c4:
                                if _status_str == "未登録":
                                    st.warning(_status_str)
                                elif _status_str == "同じ級の受験履歴あり":
                                    st.info(_status_str)
                                elif _status_str.startswith("登録済み"):
                                    st.success(_status_str)
                                else:
                                    st.caption(_status_str)
                            with _c5:
                                if st.button("この予定で入力", key=f"pass_from_exam_{student_for_pass}_{_i}_{_date_str}_{_grade_str}"):
                                    st.session_state["pass_new_grade"] = _grade_str
                                    try:
                                        _date_obj = pd.to_datetime(_date_str, errors="coerce")
                                        st.session_state["pass_new_date"] = _date_obj.date() if pd.notna(_date_obj) else date.today()
                                    except Exception:
                                        st.session_state["pass_new_date"] = date.today()
                                    st.session_state["pass_new_memo"] = _note_str
                                    st.session_state["pass_new_score"] = ""
                                    st.success("下の新規登録フォームに反映しました。点数を入力して保存してください。")
                                    st.rerun()

                st.divider()
                st.markdown("### 📝 検定結果の新規登録・手動登録")
                result_for_exam = st.radio(
                    "受験結果",
                    ["合格", "不合格", "後で登録"],
                    horizontal=True,
                    key="pass_new_result",
                    help=(
                        "「後で登録」は結果を保存せず、入力を保留します。"
                    ),
                )
                grade_for_pass = st.text_input("受験した級", value="", key="pass_new_grade")
                score_for_pass = st.text_input("点数（任意）", value="", key="pass_new_score")
                pass_date = st.date_input("受験日", value=date.today(), key="pass_new_date")
                pass_memo = st.text_area("メモ（任意）", value="", key="pass_new_memo")
                colA, colB = st.columns([1, 2])
                with colA:
                    if st.button("💾 検定結果を登録", key="pass_add_btn"):
                        if result_for_exam == "後で登録":
                            st.info(
                                "結果は保存していません。"
                                "判明後に合格または不合格で登録してください。"
                            )
                        elif grade_for_pass.strip() == "":
                            st.error("級を入力してください。")
                        else:
                            # 不合格→再受験→合格の履歴を残すため、
                            # 同じ級の過去記録は削除しない。
                            new_row = pd.DataFrame([{
                                "student_id": str(student_for_pass).strip(),
                                "grade": str(grade_for_pass).strip(),
                                "result": str(result_for_exam).strip(),
                                "score": str(score_for_pass).strip(),
                                "pass_date": str(pass_date),
                                "memo": str(pass_memo).strip(),
                            }])

                            results_df = pd.concat(
                                [results_df, new_row],
                                ignore_index=True,
                            )
                            save_kentei_results(results_df)

                            # 合格時だけ検定練習中フラグを自動OFFにする。
                            if result_for_exam != "合格":
                                st.success(
                                    f"{result_for_exam}として受験履歴を登録しました。"
                                )
                            else:
                                    # d251:
                                # 検定合格登録した級が、検定練習中フラグの対象級なら自動OFF。
                                # これにより、合格後も「次に見る候補」で検定課題が出続ける事故を防ぐ。
                                try:
                                    _passed_grade = str(grade_for_pass).strip()
                                    _saved_training_grade = get_kentei_training_grade(student_for_pass)
                                    if is_kentei_training_active(student_for_pass) and (
                                        str(_saved_training_grade).strip() == _passed_grade
                                        or str(_saved_training_grade).strip() == ""
                                    ):
                                        upsert_kentei_training_status(
                                            student_id=student_for_pass,
                                            is_training=False,
                                            grade="",
                                            note=f"{_passed_grade}級の合格登録により自動OFF",
                                        )
                                        st.success("合格登録しました。検定練習中フラグもOFFにしました。")
                                    else:
                                        st.success("合格登録しました")
                                except Exception:
                                    st.success("合格登録しました")

                with colB:
                    st.caption("※ 合格・不合格のどちらも履歴に残ります。間違えた場合は下から修正できます。")

                st.divider()
                st.markdown("### ✏️ 受験履歴の修正／削除")

                # 対象生徒の合格履歴だけに絞る
                df_s = results_df.copy()
                if not df_s.empty and "student_id" in df_s.columns:
                    df_s = df_s[df_s["student_id"].astype(str).str.strip() == str(student_for_pass).strip()].copy()
                else:
                    df_s = pd.DataFrame(columns=["student_id", "grade", "pass_date", "memo"])

                if df_s.empty:
                    st.info("この生徒の受験履歴はまだありません。")
                else:
                    # 表示用ラベル
                    def _mk_label(r):
                        g = str(r.get("grade", "")).strip()
                        result_value = str(
                            r.get("result", "合格")
                        ).strip() or "合格"
                        d = str(r.get("pass_date", "")).strip()
                        m = str(r.get("memo", "")).strip()
                        if m:
                            m = m.replace("\n", " ")
                            m = (m[:30] + "…") if len(m) > 30 else m
                            return f"{d}｜{g}級｜{result_value}｜{m}"
                        return f"{d}｜{g}級｜{result_value}"

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


                    current_result = str(
                        row.get("result", "合格")
                    ).strip() or "合格"
                    edit_result = st.radio(
                        "結果（修正）",
                        ["合格", "不合格"],
                        index=(
                            0
                            if current_result == "合格"
                            else 1
                        ),
                        horizontal=True,
                        key=f"pass_edit_result_{edit_key_base}",
                    )

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
                                results_df.loc[i, "result"] = str(edit_result).strip()
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
                        if st.button("🗑️ この受験記録を削除", disabled=(not confirm), key="pass_delete_btn"):
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


            # d282:
            # 左サイドバーの生徒フィルタが選ばれている時は、それを優先する。
            # その場合、画面内の「生徒を選択」は非表示になるため、動きが分かるように明記する。
            if selected_student != "（全員）":
                student_row = active_students[active_students["display_name"] == str(selected_student).strip()].head(1)
                if student_row.empty:
                    st.info("左の生徒フィルタに該当する生徒が見つかりません。")
                    sid = None
                else:
                    sid = str(student_row.iloc[0]["student_id"]).strip()
                    st.caption(f"対象生徒：{sid} | {selected_student}")
                    st.caption("左サイドバーの生徒フィルタを反映中です。画面内の「生徒を選択」は非表示になります。")
            else:
                st.caption("左サイドバーの生徒フィルタが「全員」の時だけ、下の「生徒を選択」が表示されます。")
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

        # d281:
        # 「級フィルタ」は、その級の登録データがある人を見るためのもの。
        # 「受験ステップ」は、次に受ける候補を見るためのもの。
        grade_filter = st.selectbox(
            "級フィルタ（その級の登録あり）",
            ["（全て）", "4級", "3級", "2級", "1級"],
            key="scratch_grade_filter",
            help="例：3級を選ぶと、3級の結果登録・受験登録がある生徒だけ表示します。"
        )

        step_filter = st.selectbox(
            "受験ステップ（次に受ける候補）",
            ["（全て）", "次に4級", "次に3級", "次に2級", "次に1級"],
            key="scratch_step_filter",
            help="例：次に3級＝4級の登録があり、3級・2級・1級の登録がまだない生徒です。"
        )
        st.caption("見方：級フィルタ＝その級の登録あり / 受験ステップ＝次に受ける候補。人数は左端のNo.で確認できます。")

        # d265:
        # Scratch検定一覧は、普段の確認では「在籍中」かつ「1級未合格」を中心に見る。
        # 退会済み・1級合格済みは必要な時だけ表示する。
        scratch_col1, scratch_col2 = st.columns(2)
        with scratch_col1:
            scratch_include_inactive = st.checkbox(
                "退会済みも含める",
                value=False,
                key="scratch_list_include_inactive",
                help="ONにすると退会済み生徒もScratch検定一覧に表示します。",
            )
        with scratch_col2:
            scratch_include_grade1_done = st.checkbox(
                "1級合格済みも含める",
                value=False,
                key="scratch_list_include_grade1_done",
                help="ONにすると1級まで合格済みの生徒も表示します。",
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

            # d266:
            # 点数が空でも「受験/合格登録がある」こと自体は区別して表示したい。
            # score_pivot だけだと、未受験と点数未入力がどちらも NaN に見えるため、
            # gradeごとの登録有無も別で持つ。
            attempt_pivot = (
                score_src.assign(_attempt_record=True)
                .pivot_table(
                    index="student_id",
                    columns="grade_col",
                    values="_attempt_record",
                    aggfunc="max",
                    fill_value=False,
                )
                .reset_index()
            )
            attempt_pivot = attempt_pivot.rename(
                columns={_c: f"{_c}_登録あり" for _c in attempt_pivot.columns if _c != "student_id"}
            )


            # 必要な列を必ず揃える
            for col in ["4級", "3級", "2級", "1級"]:
                if col not in score_pivot.columns:
                    score_pivot[col] = np.nan
                if f"{col}_登録あり" not in attempt_pivot.columns:
                    attempt_pivot[f"{col}_登録あり"] = False


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
            scratch_view = scratch_view.merge(attempt_pivot, on="student_id", how="left")
            scratch_view = scratch_view.merge(best_score_small, on="student_id", how="left")
            scratch_view["次の判断"] = scratch_view["best_score"].apply(judge_next_step)
            scratch_view["次の級"] = scratch_view["scratch_best"].apply(get_next_grade)

            # d281:
            # 各級の「登録あり」を、点数あり・登録ありの両方から判定する。
            # ここでは合格者/受験登録者として扱い、次の受験級候補を絞り込めるようにする。
            for _gcol in ["4級", "3級", "2級", "1級"]:
                _attempt_col = f"{_gcol}_登録あり"
                if _attempt_col not in scratch_view.columns:
                    scratch_view[_attempt_col] = False
                scratch_view[_attempt_col] = (
                    scratch_view[_attempt_col].fillna(False).astype(bool)
                    | scratch_view[_gcol].notna()
                )

            _has4 = scratch_view["4級_登録あり"].fillna(False).astype(bool)
            _has3 = scratch_view["3級_登録あり"].fillna(False).astype(bool)
            _has2 = scratch_view["2級_登録あり"].fillna(False).astype(bool)
            _has1 = scratch_view["1級_登録あり"].fillna(False).astype(bool)

            if step_filter == "次に4級":
                scratch_view = scratch_view[(~_has4) & (~_has3) & (~_has2) & (~_has1)].copy()
            elif step_filter == "次に3級":
                scratch_view = scratch_view[_has4 & (~_has3) & (~_has2) & (~_has1)].copy()
            elif step_filter == "次に2級":
                scratch_view = scratch_view[_has3 & (~_has2) & (~_has1)].copy()
            elif step_filter == "次に1級":
                scratch_view = scratch_view[_has2 & (~_has1)].copy()
            else:
                # Scratch検定が1件もない生徒は、通常表示では除外する。
                # ただし「次に4級」を選んだ時だけは、未取得の生徒も候補として表示する。
                scratch_view = scratch_view[
                    scratch_view["scratch_best"].notna()
                    | scratch_view["4級"].notna()
                    | scratch_view["3級"].notna()
                    | scratch_view["2級"].notna()
                    | scratch_view["1級"].notna()
                    | scratch_view["4級_登録あり"].fillna(False).astype(bool)
                    | scratch_view["3級_登録あり"].fillna(False).astype(bool)
                    | scratch_view["2級_登録あり"].fillna(False).astype(bool)
                    | scratch_view["1級_登録あり"].fillna(False).astype(bool)
                ].copy()

            # d265:
            # 基本表示は「在籍中」＋「1級未合格」。
            # 退会済み・1級合格済みはチェックONの時だけ表示する。
            _before_scratch_filter_count = len(scratch_view)

            if not scratch_include_inactive and "is_active" in scratch_view.columns:
                _active_norm = (
                    scratch_view["is_active"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .replace("", "true")
                )
                scratch_view = scratch_view[_active_norm.isin(["true", "1", "yes", "on"])].copy()

            if not scratch_include_grade1_done and "1級" in scratch_view.columns:
                _grade1_attempt = scratch_view.get("1級_登録あり", pd.Series([False] * len(scratch_view), index=scratch_view.index)).fillna(False).astype(bool)
                scratch_view = scratch_view[scratch_view["1級"].isna() & (~_grade1_attempt)].copy()

            _after_scratch_filter_count = len(scratch_view)
            _hidden_scratch_count = max(0, int(_before_scratch_filter_count) - int(_after_scratch_filter_count))
            if _hidden_scratch_count:
                st.caption(f"基本表示では、退会済み・1級合格済みの生徒を {_hidden_scratch_count} 件非表示にしています。必要なら上のチェックをONにしてください。")


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

                # その級の点数、または登録自体がある生徒だけ残す
                _attempt_col = f"{grade_filter}_登録あり"
                if _attempt_col in scratch_view.columns:
                    scratch_view = scratch_view[
                        scratch_view[grade_filter].notna()
                        | scratch_view[_attempt_col].fillna(False).astype(bool)
                    ].copy()
                else:
                    scratch_view = scratch_view[scratch_view[grade_filter].notna()].copy()

                # 点数でソート（高い順）。点数未入力は最後へ。
                scratch_view = scratch_view.sort_values(
                    by=grade_filter,
                    ascending=False,
                    na_position="last"
                )

            if scratch_view.empty:
                st.info("該当するScratch検定データがありません。退会済みや1級合格済みを確認したい場合は、上のチェックをONにしてください。")
            else:
                scratch_view["scratch_best"] = scratch_view["scratch_best"].fillna("—")

                # ソート用に数値コピー
                for col in ["4級", "3級", "2級", "1級"]:
                    scratch_view[col] = pd.to_numeric(scratch_view[col], errors="coerce")

                def _format_score_or_missing(_row, _col):
                    _score = _row.get(_col, np.nan)
                    _attempt = bool(_row.get(f"{_col}_登録あり", False))
                    if pd.isna(_score):
                        return "△未入力" if _attempt else "—"
                    try:
                        return str(int(_score)) if float(_score).is_integer() else str(_score)
                    except Exception:
                        return str(_score)

                for col in ["4級", "3級", "2級", "1級"]:
                    scratch_view[col] = scratch_view.apply(lambda _r, _c=col: _format_score_or_missing(_r, _c), axis=1)

                scratch_view["best_score"] = scratch_view["best_score"].apply(
                    lambda x: "—" if pd.isna(x) else str(int(x)) if float(x).is_integer() else str(x)
                )

                show_cols = ["grade", "display_name", "4級", "3級", "2級", "1級", "scratch_best", "best_score", "次の判断","次の級"]
                scratch_display_df = scratch_view.sort_values(by=["grade", "display_name"], na_position="last")[show_cols].copy()

                # d280:
                # Scratch検定一覧の左端に、表示中データだけの連番を付ける。
                # CSVには保存しない表示専用番号。絞り込み後に1から振り直されるため、
                # 一番下の番号を見るだけで「現在表示されている人数」が分かる。
                scratch_display_df.insert(0, "No.", range(1, len(scratch_display_df) + 1))

                def _style_missing_score_cells(_df):
                    return pd.DataFrame(
                        [
                            [
                                "background-color:#fff3cd; color:#7a5200; font-weight:700"
                                if str(_value).strip() == "△未入力" else ""
                                for _value in _row
                            ]
                            for _row in _df.to_numpy()
                        ],
                        index=_df.index,
                        columns=_df.columns,
                    )

                if step_filter != "（全て）":
                    st.caption(f"{step_filter}：表示人数 {len(scratch_display_df)} 人（左端No.の最終番号と同じです）")
                elif grade_filter != "（全て）":
                    st.caption(f"{grade_filter}の登録あり：表示人数 {len(scratch_display_df)} 人（左端No.の最終番号と同じです）")

                st.caption("点数欄：—＝未受験 / △未入力＝受験・合格登録あり、点数未入力")
                st.dataframe(
                    scratch_display_df.style.apply(_style_missing_score_cells, axis=None),
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
        st.caption("この一覧は、左サイドバーの「学年・生徒・今日の生徒のみ」フィルタが反映されます。特定の生徒だけ見たい場合は、左サイドバーの「生徒」で選択してください。")
        st.caption(
            f"現在の絞り込み：学年＝{selected_grade} / 生徒＝{selected_student} / 今日の生徒のみ＝{'ON' if show_today_only else 'OFF'}"
        )

        cols = ["date", "grade", "display_name", "curriculum", "item", "note"]
        cols = [c for c in cols if c in filtered_done.columns]
        done_view = filtered_done.copy()
        if show_today_only and "student_id" in done_view.columns:
            done_view = done_view[done_view["student_id"].astype(str).str.strip().isin(today_student_ids)].copy()



        show = done_view[cols].sort_values(by=["grade", "display_name", "date", "curriculum", "item"]).copy()
        show.insert(0, "No.", range(1, len(show) + 1))
        st.caption(f"表示件数：{len(show)}件")
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

    # d303:
    # st.tabs は、選択していないタブの中身も実行される。
    # 管理メニューを1つだけ選ぶ方式にし、選択中の画面だけ処理する。
    admin_section_options = [
        "🗓️ 月スケジュール",
        "🎫 検定予定登録",
        "👥 生徒管理",
        "📅 固定スケジュール（週次）",
        "📘 カリキュラム管理",
        "🧩 サブ課題管理",
        "🗓️ スケジュール例外",
        "🛠 システム設定",
        "ℹ️ 運用メモ",
    ]

    if "pending_admin_section" in st.session_state:
        _pending_admin_section = str(
            st.session_state.pop("pending_admin_section", "")
        ).strip()
        if _pending_admin_section in admin_section_options:
            st.session_state["admin_section_selector"] = (
                _pending_admin_section
            )

    admin_section = st.selectbox(
        "管理メニュー",
        admin_section_options,
        key="admin_section_selector",
        help=(
            "選択した管理画面だけを読み込みます。"
            "以前のタブ方式より、再読み込み時の処理を減らします。"
        ),
    )
    st.caption(
        "選択中の管理画面だけを実行しています。"
        "別の管理画面を開く時は、このメニューから切り替えます。"
    )

    # ---------------------------
    # 👥 生徒管理（追加・編集・退会）
    # ---------------------------
    if admin_section == "👥 生徒管理":
        # d325:
        # 生徒の追加・編集・退会は編集用データへ反映し、
        # 最後に「生徒一覧を保存」で1回だけCSVへ書き込む。
        student_edit_key = "students_batch_edit_df"
        student_dirty_key = "students_batch_edit_dirty"
        student_base_signature_key = "students_batch_edit_base_signature"

        student_required_cols = [
            "student_id",
            "display_name",
            "grade",
            "number_of_times",
            "join_date",
            "is_active",
            "weekday",
            "slot",
            "memo",
        ]

        def _students_file_signature():
            try:
                p = Path(STUDENTS_CSV)
                stat = p.stat()
                return (int(stat.st_mtime_ns), int(stat.st_size))
            except Exception:
                return None

        def _normalize_students_edit_df(df):
            out = df.copy() if df is not None else pd.DataFrame()
            for col in student_required_cols:
                if col not in out.columns:
                    if col == "number_of_times":
                        out[col] = 0
                    elif col == "is_active":
                        out[col] = True
                    else:
                        out[col] = ""

            out["student_id"] = (
                out["student_id"].fillna("").astype(str).str.strip()
            )
            out["display_name"] = (
                out["display_name"].fillna("").astype(str).str.strip()
            )
            out["grade"] = out["grade"].fillna("").astype(str).str.strip()
            out["join_date"] = (
                out["join_date"].fillna("").astype(str).str.strip()
            )
            out["weekday"] = (
                out["weekday"].fillna("").astype(str).str.strip()
            )
            out["slot"] = out["slot"].fillna("").astype(str).map(
                normalize_slot
            )
            out["memo"] = out["memo"].fillna("").astype(str)
            out["number_of_times"] = pd.to_numeric(
                out["number_of_times"],
                errors="coerce",
            ).fillna(0).astype(int)

            def _active_bool(value):
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in [
                    "true",
                    "1",
                    "yes",
                    "on",
                    "在籍",
                ]

            out["is_active"] = out["is_active"].map(_active_bool)
            return out.reset_index(drop=True)

        if student_edit_key not in st.session_state:
            loaded_students = safe_read_csv(
                STUDENTS_CSV,
                required_cols=["student_id", "display_name"],
            )
            st.session_state[student_edit_key] = (
                _normalize_students_edit_df(loaded_students)
            )
            st.session_state[student_dirty_key] = False
            st.session_state[student_base_signature_key] = (
                _students_file_signature()
            )

        students_edit = _normalize_students_edit_df(
            st.session_state[student_edit_key]
        )

        if st.session_state.get(student_dirty_key, False):
            st.warning("🟡 保存していない生徒一覧の変更があります。")
        else:
            st.success("🟢 生徒一覧は保存済みです。")

        st.caption(
            "追加・更新・退会は編集用データへ反映されます。"
            "複数人を続けて変更し、最後に一度だけ保存してください。"
        )

        # 候補作成用データ
        sched_base = safe_read_csv(
            STUDENT_SCHEDULE_CSV,
            required_cols=["student_id", "weekday", "slot"],
            stop_on_missing=False,
        )
        slots_base = safe_read_csv(
            TIMESLOTS_CSV,
            required_cols=["slot"],
            stop_on_missing=False,
        )
        grade_options = build_grade_options(students_edit)
        weekday_options = build_weekday_options(
            students_edit,
            sched_base,
        )
        slot_options = build_slot_options(
            slots_base,
            sched_base,
            students_edit,
        )
        slot_label_map = build_slot_label_map(slots_base)

        def suggest_next_student_id(existing_ids: pd.Series) -> str:
            nums = []
            for value in existing_ids.dropna().astype(str):
                value = value.strip()
                if value.startswith("S") and value[1:].isdigit():
                    nums.append(int(value[1:]))
            next_num = (max(nums) + 1) if nums else 1
            return f"S{next_num:03d}"

        add_col, edit_col = st.columns(2, gap="large")

        # =====================================================
        # 新規追加（緑）
        # =====================================================
        with add_col:
            st.markdown(
                """
                <div style="
                    background:#ecfdf5;
                    border:2px solid #22c55e;
                    border-left:10px solid #16a34a;
                    border-radius:12px;
                    padding:12px 14px;
                    margin-bottom:12px;
                ">
                    <div style="font-size:18px;font-weight:900;color:#166534;">
                        🟢 新しい生徒を追加
                    </div>
                    <div style="font-size:12px;color:#166534;margin-top:4px;">
                        追加後もCSVにはまだ保存されません。
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            next_id = suggest_next_student_id(
                students_edit["student_id"]
            )

            with st.form(
                "student_batch_add_form",
                clear_on_submit=True,
            ):
                new_id = st.text_input(
                    "生徒ID",
                    value=next_id,
                    help=(
                        "生徒IDは他の記録との紐付けに使うため、"
                        "追加後は変更できません。"
                    ),
                )
                new_name = st.text_input("表示名")

                new_grade_sel = st.selectbox(
                    "学年",
                    options=grade_options,
                    index=0,
                )
                new_grade_free = ""
                if new_grade_sel == "その他（自由入力）":
                    new_grade_free = st.text_input("学年（自由入力）")
                new_grade = (
                    new_grade_free
                    if new_grade_sel == "その他（自由入力）"
                    else new_grade_sel
                )

                new_times = st.number_input(
                    "月回数",
                    min_value=0,
                    value=0,
                    step=1,
                )
                new_join = st.date_input(
                    "入会日",
                    value=date.today(),
                )

                new_weekday_sel = st.selectbox(
                    "曜日（任意）",
                    options=weekday_options,
                    index=0,
                )
                new_weekday_free = ""
                if new_weekday_sel == "その他（自由入力）":
                    new_weekday_free = st.text_input(
                        "曜日（自由入力）"
                    )
                new_weekday = (
                    new_weekday_free
                    if new_weekday_sel == "その他（自由入力）"
                    else new_weekday_sel
                )

                new_slot_sel = st.selectbox(
                    "コマ（任意）",
                    options=slot_options,
                    index=0,
                    format_func=lambda x: (
                        "その他（自由入力）"
                        if str(x) == "その他（自由入力）"
                        else format_slot_label(x, slot_label_map)
                    ),
                )
                new_slot_free = ""
                if new_slot_sel == "その他（自由入力）":
                    new_slot_free = st.text_input(
                        "コマ（自由入力）"
                    )
                new_slot = (
                    new_slot_free
                    if new_slot_sel == "その他（自由入力）"
                    else normalize_slot(new_slot_sel)
                )

                new_memo = st.text_area(
                    "メモ（補足）",
                    height=80,
                )

                add_student_submitted = st.form_submit_button(
                    "🟢 生徒を編集一覧に追加",
                    use_container_width=True,
                )

            if add_student_submitted:
                new_id_s = str(new_id).strip()
                if not new_id_s:
                    st.error("生徒IDが空です。")
                elif new_id_s in set(
                    students_edit["student_id"].astype(str)
                ):
                    st.error(
                        f"同じ生徒IDが既にあります: {new_id_s}"
                    )
                elif not str(new_name).strip():
                    st.error("表示名が空です。")
                else:
                    new_row = {
                        col: ""
                        for col in students_edit.columns
                    }
                    new_row.update({
                        "student_id": new_id_s,
                        "display_name": str(new_name).strip(),
                        "grade": str(new_grade).strip(),
                        "number_of_times": int(new_times),
                        "join_date": str(new_join),
                        "is_active": True,
                        "weekday": str(new_weekday).strip(),
                        "slot": normalize_slot(new_slot),
                        "memo": str(new_memo).strip(),
                    })
                    edited = pd.concat(
                        [
                            students_edit,
                            pd.DataFrame([new_row]),
                        ],
                        ignore_index=True,
                    )
                    st.session_state[student_edit_key] = (
                        _normalize_students_edit_df(edited)
                    )
                    st.session_state[student_dirty_key] = True
                    st.success(
                        f"編集一覧に追加しました: "
                        f"{new_id_s} / {str(new_name).strip()}"
                    )
                    st.rerun()

        # =====================================================
        # 編集・退会（オレンジ）
        # =====================================================
        with edit_col:
            st.markdown(
                """
                <div style="
                    background:#fff7ed;
                    border:2px solid #f59e0b;
                    border-left:10px solid #ea580c;
                    border-radius:12px;
                    padding:12px 14px;
                    margin-bottom:12px;
                ">
                    <div style="font-size:18px;font-weight:900;color:#9a3412;">
                        🟠 生徒情報を編集・退会
                    </div>
                    <div style="font-size:12px;color:#9a3412;margin-top:4px;">
                        生徒IDは固定です。退会は確認チェック付きです。
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            students_view = students_edit.copy()
            if not admin_include_inactive:
                students_view = students_view[
                    students_view["is_active"].eq(True)
                ].copy()

            if students_view.empty:
                st.info("編集できる生徒がいません。")
            else:
                students_view["label"] = (
                    students_view["student_id"].astype(str)
                    + " | "
                    + students_view["display_name"].astype(str)
                    + students_view["is_active"].map(
                        lambda x: "" if bool(x) else " | 退会"
                    )
                )
                edit_ids = students_view["student_id"].tolist()
                selected_id = st.selectbox(
                    "生徒を選択",
                    edit_ids,
                    key="student_batch_edit_selected_id",
                    format_func=lambda sid: students_view.loc[
                        students_view["student_id"].eq(sid),
                        "label",
                    ].iloc[0],
                )

                selected_rows = students_edit[
                    students_edit["student_id"].eq(selected_id)
                ]
                selected_index = selected_rows.index[0]
                cur = selected_rows.iloc[0]

                st.markdown(
                    f"**生徒ID：{selected_id}**（変更不可）"
                )

                cur_grade = str(cur.get("grade", "") or "").strip()
                edit_grade_options = list(grade_options)
                if (
                    cur_grade
                    and cur_grade not in edit_grade_options
                ):
                    edit_grade_options = (
                        edit_grade_options[:-1]
                        + [cur_grade]
                        + [edit_grade_options[-1]]
                    )

                cur_slot = normalize_slot(cur.get("slot", ""))
                edit_slot_options = list(slot_options)
                if (
                    cur_slot
                    and cur_slot not in edit_slot_options
                ):
                    edit_slot_options = (
                        edit_slot_options[:-1]
                        + [cur_slot]
                        + [edit_slot_options[-1]]
                    )

                cur_join = pd.to_datetime(
                    cur.get("join_date", ""),
                    errors="coerce",
                )
                cur_join_date = (
                    cur_join.date()
                    if pd.notna(cur_join)
                    else date.today()
                )

                with st.form(
                    key=f"student_batch_edit_form_{selected_id}",
                    clear_on_submit=False,
                ):
                    edit_name = st.text_input(
                        "表示名",
                        value=str(
                            cur.get("display_name", "")
                        ),
                    )

                    default_grade_index = (
                        edit_grade_options.index(cur_grade)
                        if cur_grade in edit_grade_options
                        else 0
                    )
                    edit_grade_sel = st.selectbox(
                        "学年",
                        options=edit_grade_options,
                        index=default_grade_index,
                    )
                    edit_grade_free = ""
                    if edit_grade_sel == "その他（自由入力）":
                        edit_grade_free = st.text_input(
                            "学年（自由入力）",
                            value=cur_grade,
                        )
                    edit_grade = (
                        edit_grade_free
                        if edit_grade_sel
                        == "その他（自由入力）"
                        else edit_grade_sel
                    )

                    edit_times = st.number_input(
                        "月回数",
                        min_value=0,
                        value=int(
                            cur.get("number_of_times", 0) or 0
                        ),
                        step=1,
                    )
                    edit_join = st.date_input(
                        "入会日",
                        value=cur_join_date,
                    )

                    current_active = bool(
                        cur.get("is_active", True)
                    )
                    edit_active = st.checkbox(
                        "在籍中",
                        value=current_active,
                        help=(
                            "OFFにすると退会扱いになります。"
                            "保存時に基本席も解除します。"
                        ),
                    )

                    edit_weekday = st.text_input(
                        "曜日（任意）",
                        value=str(cur.get("weekday", "") or ""),
                    )

                    default_slot_index = (
                        edit_slot_options.index(cur_slot)
                        if cur_slot in edit_slot_options
                        else 0
                    )
                    edit_slot_sel = st.selectbox(
                        "コマ（任意）",
                        options=edit_slot_options,
                        index=default_slot_index,
                        format_func=lambda x: (
                            "その他（自由入力）"
                            if str(x) == "その他（自由入力）"
                            else format_slot_label(
                                x,
                                slot_label_map,
                            )
                        ),
                    )
                    edit_slot_free = ""
                    if edit_slot_sel == "その他（自由入力）":
                        edit_slot_free = st.text_input(
                            "コマ（自由入力）",
                            value=cur_slot,
                        )
                    edit_slot = (
                        edit_slot_free
                        if edit_slot_sel
                        == "その他（自由入力）"
                        else normalize_slot(edit_slot_sel)
                    )

                    edit_memo = st.text_area(
                        "メモ（補足）",
                        value=ui_str(cur.get("memo", "")),
                        height=80,
                    )

                    retire_confirm = True
                    if current_active and not edit_active:
                        st.warning(
                            "この生徒を退会扱いに変更します。"
                            "基本席も一括保存時に解除されます。"
                        )
                        retire_confirm = st.checkbox(
                            "退会への変更を確認しました"
                        )

                    update_student_submitted = (
                        st.form_submit_button(
                            "🟠 編集内容を一覧へ反映",
                            use_container_width=True,
                            disabled=(
                                current_active
                                and not edit_active
                                and not retire_confirm
                            ),
                        )
                    )

                if update_student_submitted:
                    if not str(edit_name).strip():
                        st.error("表示名が空です。")
                    else:
                        edited = students_edit.copy()
                        edited.loc[
                            selected_index,
                            "display_name",
                        ] = str(edit_name).strip()
                        edited.loc[
                            selected_index,
                            "grade",
                        ] = str(edit_grade).strip()
                        edited.loc[
                            selected_index,
                            "number_of_times",
                        ] = int(edit_times)
                        edited.loc[
                            selected_index,
                            "join_date",
                        ] = str(edit_join)
                        edited.loc[
                            selected_index,
                            "is_active",
                        ] = bool(edit_active)
                        edited.loc[
                            selected_index,
                            "weekday",
                        ] = str(edit_weekday).strip()
                        edited.loc[
                            selected_index,
                            "slot",
                        ] = normalize_slot(edit_slot)
                        edited.loc[
                            selected_index,
                            "memo",
                        ] = str(edit_memo).strip()

                        st.session_state[student_edit_key] = (
                            _normalize_students_edit_df(edited)
                        )
                        st.session_state[student_dirty_key] = True
                        state_label = (
                            "在籍"
                            if bool(edit_active)
                            else "退会"
                        )
                        st.success(
                            f"{selected_id} の編集内容を"
                            f"一覧へ反映しました（{state_label}）。"
                        )
                        st.rerun()

        # =====================================================
        # 編集中一覧
        # =====================================================
        st.divider()
        st.markdown("### 編集中の生徒一覧")
        preview = students_edit.copy()
        preview["状態"] = preview["is_active"].map(
            lambda x: "在籍" if bool(x) else "退会"
        )
        preview = preview.rename(columns={
            "student_id": "生徒ID",
            "display_name": "表示名",
            "grade": "学年",
            "number_of_times": "月回数",
            "join_date": "入会日",
            "weekday": "曜日",
            "slot": "コマ",
            "memo": "メモ",
        })
        preview_cols = [
            "生徒ID",
            "表示名",
            "学年",
            "月回数",
            "状態",
            "入会日",
            "曜日",
            "コマ",
            "メモ",
        ]
        st.dataframe(
            preview[
                [c for c in preview_cols if c in preview.columns]
            ],
            use_container_width=True,
            hide_index=True,
        )

        # =====================================================
        # 一括保存・破棄
        # =====================================================
        st.divider()
        st.markdown("### 編集内容を確定")
        st.caption(
            "生徒IDは変更しません。退会になった生徒の基本席は、"
            "保存時にまとめて解除します。"
        )
        save_students_col, discard_students_col = st.columns(
            [2, 1]
        )

        with save_students_col:
            save_students_batch = st.button(
                "💾 生徒一覧を保存",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.get(
                    student_dirty_key,
                    False,
                ),
                key="save_students_batch",
            )

        with discard_students_col:
            discard_students_batch = st.button(
                "↩ 編集を破棄",
                use_container_width=True,
                disabled=not st.session_state.get(
                    student_dirty_key,
                    False,
                ),
                key="discard_students_batch",
            )

        if save_students_batch:
            current_signature = _students_file_signature()
            base_signature = st.session_state.get(
                student_base_signature_key
            )

            if current_signature != base_signature:
                st.error(
                    "編集中にstudents.csvが別の処理で更新されました。"
                    "安全のため保存していません。"
                    "「編集を破棄」で最新データを読み直してから、"
                    "もう一度変更してください。"
                )
            else:
                original_students = safe_read_csv(
                    STUDENTS_CSV,
                    required_cols=[
                        "student_id",
                        "display_name",
                    ],
                    show_message=False,
                )
                original_students = _normalize_students_edit_df(
                    original_students
                )
                edited_students = _normalize_students_edit_df(
                    st.session_state[student_edit_key]
                )

                # student_idの重複・空欄を保存前に最終確認
                empty_ids = edited_students[
                    edited_students["student_id"].eq("")
                ]
                duplicate_ids = edited_students[
                    edited_students["student_id"].duplicated(
                        keep=False
                    )
                ]

                if not empty_ids.empty:
                    st.error(
                        "生徒IDが空の行があるため保存できません。"
                    )
                elif not duplicate_ids.empty:
                    st.error(
                        "生徒IDが重複しているため保存できません。"
                    )
                elif (
                    edited_students["display_name"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .eq("")
                    .any()
                ):
                    st.error(
                        "表示名が空の生徒がいるため保存できません。"
                    )
                else:
                    write_csv(edited_students, STUDENTS_CSV)

                    # 在籍→退会へ変更された生徒の基本席を解除
                    original_active_map = dict(
                        zip(
                            original_students["student_id"],
                            original_students["is_active"],
                        )
                    )
                    newly_inactive_ids = {
                        str(row["student_id"]).strip()
                        for _, row in edited_students.iterrows()
                        if (
                            bool(
                                original_active_map.get(
                                    str(
                                        row["student_id"]
                                    ).strip(),
                                    False,
                                )
                            )
                            and not bool(row["is_active"])
                        )
                    }

                    removed_default_seat_count = 0
                    if newly_inactive_ids:
                        default_df = safe_read_csv(
                            DEFAULT_SEATS_CSV,
                            DEFAULT_SEAT_COLS,
                            stop_on_missing=False,
                            show_message=False,
                        )
                        if not default_df.empty:
                            before_count = len(default_df)
                            default_df = default_df[
                                ~default_df["student_id"]
                                .astype(str)
                                .str.strip()
                                .isin(newly_inactive_ids)
                            ].copy()
                            removed_default_seat_count = (
                                before_count - len(default_df)
                            )
                            if removed_default_seat_count > 0:
                                write_csv_atomic(
                                    default_df[
                                        DEFAULT_SEAT_COLS
                                    ].fillna(""),
                                    DEFAULT_SEATS_CSV,
                                )

                    for key in [
                        student_edit_key,
                        student_dirty_key,
                        student_base_signature_key,
                    ]:
                        st.session_state.pop(key, None)

                    # 選択状態もCSV再読込後に作り直す
                    st.session_state.pop(
                        "student_batch_edit_selected_id",
                        None,
                    )

                    if removed_default_seat_count > 0:
                        st.success(
                            "生徒一覧をまとめて保存しました。"
                            f"退会者の基本席"
                            f"{removed_default_seat_count}件も"
                            "解除しました。"
                        )
                    else:
                        st.success(
                            "生徒一覧をまとめて保存しました。"
                        )
                    st.rerun()

        if discard_students_batch:
            for key in [
                student_edit_key,
                student_dirty_key,
                student_base_signature_key,
            ]:
                st.session_state.pop(key, None)
            st.session_state.pop(
                "student_batch_edit_selected_id",
                None,
            )
            st.rerun()

    # ---------------------------
    # 📅 固定スケジュール（週次）
    # ---------------------------
    if admin_section == "📅 固定スケジュール（週次）":
        st.subheader("固定スケジュール（週次）")
        st.caption("毎週の生徒に加えて、月2回の生徒も「第1・第3」「第2・第4」などの週指定で登録できます。月スケジュール生成時は指定した週だけ反映されます。")

        students_w = admin_students_for_pick.copy()
        students_w["label"] = students_w["student_id"].astype(str) + " | " + students_w["display_name"].astype(str)

        # 対象生徒
        target_label = st.selectbox("対象生徒", students_w["label"].tolist(), key="weekly_target")
        target_id = target_label.split("|")[0].strip()
        target_name = target_label.split("|", 1)[1].strip() if "|" in target_label else ""
        st.write(f"対象生徒: {target_id} | {target_name}")

        # d319: 固定スケジュールは編集用データ上でまとめて変更し、
        # 最後に1回だけCSVへ保存する。
        schedule_edit_key = "fixed_schedule_edit_df"
        schedule_dirty_key = "fixed_schedule_edit_dirty"
        schedule_base_signature_key = "fixed_schedule_edit_base_signature"

        def _fixed_schedule_file_signature():
            """編集中にCSVが外部更新されていないか確認するための署名。"""
            try:
                p = Path(STUDENT_SCHEDULE_CSV)
                stat = p.stat()
                return (int(stat.st_mtime_ns), int(stat.st_size))
            except Exception:
                return None

        def _load_fixed_schedule_for_edit():
            loaded = safe_read_csv(
                STUDENT_SCHEDULE_CSV,
                required_cols=[
                    "student_id",
                    "weekday",
                    "slot",
                    "session_type",
                ],
            )
            loaded = sanitize_df(loaded)
            if "week_pattern" not in loaded.columns:
                loaded["week_pattern"] = "毎週"
            for col in [
                "student_id",
                "weekday",
                "slot",
                "session_type",
                "week_pattern",
            ]:
                if col not in loaded.columns:
                    loaded[col] = ""
            loaded["week_pattern"] = (
                loaded["week_pattern"]
                .fillna("")
                .map(normalize_week_pattern)
            )
            return loaded.reset_index(drop=True)

        # 画面を開いた最初の1回だけCSVを読み、編集用コピーを作成する。
        if schedule_edit_key not in st.session_state:
            st.session_state[schedule_edit_key] = _load_fixed_schedule_for_edit()
            st.session_state[schedule_dirty_key] = False
            st.session_state[schedule_base_signature_key] = _fixed_schedule_file_signature()

        student_schedule = st.session_state[schedule_edit_key].copy()
        for col in [
            "student_id",
            "weekday",
            "slot",
            "session_type",
            "week_pattern",
        ]:
            if col not in student_schedule.columns:
                student_schedule[col] = ""
        student_schedule["week_pattern"] = (
            student_schedule["week_pattern"]
            .fillna("")
            .map(normalize_week_pattern)
        )

        if st.session_state.get(schedule_dirty_key, False):
            st.warning("🟡 保存していない固定スケジュールの変更があります。")
        else:
            st.success("🟢 固定スケジュールは保存済みです。")

        cur_rows = student_schedule[
            student_schedule["student_id"].astype(str).str.strip()
            == str(target_id).strip()
        ].copy()

        # 一覧
        if cur_rows.empty:
            st.info("固定スケジュールは未登録です。下の「追加」から登録できます。")
        else:
            show = cur_rows[
                ["weekday", "slot", "session_type", "week_pattern"]
            ].copy()
            show["slot"] = show["slot"].apply(
                lambda x: (
                    str(int(float(x)))
                    if str(x).replace(".", "", 1).isdigit()
                    else str(x)
                )
            )
            st.dataframe(show, use_container_width=True, hide_index=True)

            st.caption(
                "削除は編集用データに反映されます。"
                "最後に「固定スケジュールを保存」を押すまでCSVには書き込みません。"
            )
            for row_index, r in cur_rows.iterrows():
                c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 2, 1])
                with c1:
                    st.write(ui_str(r.get("weekday", "")) or "-")
                with c2:
                    st.write(ui_str(r.get("slot", "")) or "-")
                with c3:
                    st.write(ui_str(r.get("session_type", "")) or "-")
                with c4:
                    st.write(
                        normalize_week_pattern(r.get("week_pattern", ""))
                    )
                with c5:
                    if st.button(
                        "この行を削除",
                        key=f"weekly_del_{target_id}_{row_index}",
                    ):
                        edited = student_schedule.drop(
                            index=row_index,
                            errors="ignore",
                        ).reset_index(drop=True)
                        st.session_state[schedule_edit_key] = edited
                        st.session_state[schedule_dirty_key] = True
                        st.rerun()

        st.markdown("#### 追加")
        colA, colB, colC, colD, colE = st.columns([1, 1, 2, 2, 1])
        with colA:
            wday = st.selectbox(
                "曜日",
                WEEKDAY_PRESETS,
                index=0,
                key=f"weekly_add_wday_{target_id}",
            )
        with colB:
            fs_slot_label_map = build_slot_label_map(timeslots)
            fs_slot_options = [
                str(k) for k in sorted(fs_slot_label_map.keys())
            ] + ["その他（自由入力）"]
            slot_label_map = build_slot_label_map(timeslots)

            fs_slot_sel = st.selectbox(
                "コマ",
                options=fs_slot_options,
                index=0,
                key=f"fs_slot_sel_{target_id}",
                format_func=lambda x: (
                    "その他（自由入力）"
                    if str(x) == "その他（自由入力）"
                    else format_slot_label(x, slot_label_map)
                ),
            )

            fs_slot_free = ""
            if fs_slot_sel == "その他（自由入力）":
                fs_slot_free = st.text_input(
                    "コマ（自由入力）",
                    value="",
                    key=f"fs_slot_free_{target_id}",
                )

            slot_in = (
                fs_slot_free
                if fs_slot_sel == "その他（自由入力）"
                else normalize_slot(fs_slot_sel)
            )
        with colC:
            stype = st.selectbox(
                "種別",
                ["授業", "自習", "検定", "その他"],
                index=0,
                key=f"weekly_add_type_{target_id}",
            )
        with colD:
            week_pattern_in = st.selectbox(
                "反映する週",
                WEEK_PATTERN_OPTIONS,
                index=0,
                key=f"weekly_add_week_pattern_{target_id}",
                help="月2回なら「第1・第3」または「第2・第4」を選びます。",
            )
        with colE:
            add_btn = st.button(
                "追加",
                key=f"weekly_add_btn_{target_id}",
            )

        if add_btn:
            w = str(wday).strip()
            s = str(slot_in).strip()
            t = str(stype).strip()
            wp = normalize_week_pattern(week_pattern_in)

            if w == "" or w == "その他（自由入力）":
                st.error("曜日を選択してください。")
            elif s == "":
                st.error("コマを入力してください。")
            else:
                dup = (
                    student_schedule["student_id"]
                    .astype(str)
                    .str.strip()
                    .eq(str(target_id).strip())
                    & student_schedule["weekday"]
                    .astype(str)
                    .str.strip()
                    .eq(w)
                    & student_schedule["slot"]
                    .astype(str)
                    .str.strip()
                    .eq(s)
                    & student_schedule["week_pattern"]
                    .map(normalize_week_pattern)
                    .eq(wp)
                )
                if dup.any():
                    st.warning(
                        "同じ曜日・コマ・週指定が既に登録されています。"
                    )
                else:
                    new_row = pd.DataFrame(
                        [
                            {
                                "student_id": str(target_id).strip(),
                                "weekday": w,
                                "slot": s,
                                "session_type": (
                                    t if t != "その他" else ""
                                ),
                                "week_pattern": wp,
                            }
                        ]
                    )
                    edited = pd.concat(
                        [student_schedule, new_row],
                        ignore_index=True,
                    )
                    st.session_state[schedule_edit_key] = edited
                    st.session_state[schedule_dirty_key] = True
                    st.rerun()

        st.divider()
        st.markdown("#### 編集内容を確定")
        st.caption(
            "複数の生徒を続けて追加・削除した後、最後に一度だけ保存します。"
        )
        save_col, discard_col = st.columns([2, 1])

        with save_col:
            save_fixed_schedule = st.button(
                "💾 固定スケジュールを保存",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.get(
                    schedule_dirty_key,
                    False,
                ),
                key="save_fixed_schedule_batch",
            )

        with discard_col:
            discard_fixed_schedule = st.button(
                "↩ 編集を破棄",
                use_container_width=True,
                disabled=not st.session_state.get(
                    schedule_dirty_key,
                    False,
                ),
                key="discard_fixed_schedule_batch",
            )

        if save_fixed_schedule:
            current_signature = _fixed_schedule_file_signature()
            base_signature = st.session_state.get(
                schedule_base_signature_key
            )

            # 編集開始後に別処理でCSVが更新されていた場合は、
            # 意図せず上書きしない。
            if current_signature != base_signature:
                st.error(
                    "編集中に固定スケジュールのCSVが更新されました。"
                    "安全のため保存していません。"
                    "「編集を破棄」で最新データを読み直してから、"
                    "もう一度変更してください。"
                )
            else:
                edited = st.session_state[schedule_edit_key].copy()
                edited = edited.reindex(
                    columns=[
                        "student_id",
                        "weekday",
                        "slot",
                        "session_type",
                        "week_pattern",
                    ]
                )
                edited["week_pattern"] = (
                    edited["week_pattern"]
                    .fillna("")
                    .map(normalize_week_pattern)
                )
                write_csv(edited, STUDENT_SCHEDULE_CSV)

                # 保存後は次回の再表示でCSVから読み直す。
                for key in [
                    schedule_edit_key,
                    schedule_dirty_key,
                    schedule_base_signature_key,
                ]:
                    st.session_state.pop(key, None)

                st.success("固定スケジュールをまとめて保存しました。")
                st.rerun()

        if discard_fixed_schedule:
            for key in [
                schedule_edit_key,
                schedule_dirty_key,
                schedule_base_signature_key,
            ]:
                st.session_state.pop(key, None)
            st.rerun()

    # ---------------------------
    # 🎫 検定予定登録（kentei_schedule.csv）
    # ---------------------------
    if admin_section == "🎫 検定予定登録":
        st.subheader("検定予定・一覧")

        exam_edit_key = "kentei_exam_batch_edit_df"
        exam_dirty_key = "kentei_exam_batch_dirty"
        exam_base_signature_key = "kentei_exam_batch_base_signature"
        exam_cols = [
            "student_id",
            "exam_type",
            "grade",
            "exam_date",
            "note",
            "date",
            "kentei",
        ]

        def _exam_file_signature():
            try:
                p = Path(KENTEI_EXAM_SCHEDULE_CSV)
                stat = p.stat()
                return (int(stat.st_mtime_ns), int(stat.st_size))
            except Exception:
                return None

        def _normalize_exam_edit_df(df):
            out = df.copy() if df is not None else pd.DataFrame()
            for col in exam_cols:
                if col not in out.columns:
                    out[col] = ""
            for col in exam_cols:
                out[col] = out[col].fillna("").astype(str).str.strip()
            out["exam_type"] = out["exam_type"].where(
                out["exam_type"].ne(""),
                out["kentei"],
            )
            out["kentei"] = out["kentei"].where(
                out["kentei"].ne(""),
                out["exam_type"],
            )
            out["exam_date"] = out["exam_date"].where(
                out["exam_date"].ne(""),
                out["date"],
            )
            return out[exam_cols].reset_index(drop=True)

        if exam_edit_key not in st.session_state:
            loaded = safe_read_csv(
                KENTEI_EXAM_SCHEDULE_CSV,
                required_cols=["student_id", "grade"],
                stop_on_missing=False,
            )
            st.session_state[exam_edit_key] = _normalize_exam_edit_df(
                loaded
            )
            st.session_state[exam_dirty_key] = False
            st.session_state[exam_base_signature_key] = (
                _exam_file_signature()
            )

        ks = _normalize_exam_edit_df(
            st.session_state[exam_edit_key]
        )

        if st.session_state.get(exam_dirty_key, False):
            st.warning("🟡 保存していない検定予定の変更があります。")
        else:
            st.success("🟢 検定予定一覧は保存済みです。")

        students_k = admin_students_for_pick.copy()
        students_k["label"] = (
            students_k["student_id"].astype(str)
            + " | "
            + students_k["display_name"].astype(str)
        )
        student_labels = students_k["label"].tolist()
        name_map_k = dict(
            zip(
                students_k["student_id"].astype(str).str.strip(),
                students_k["display_name"].astype(str).str.strip(),
            )
        )

        add_col, edit_col = st.columns(2, gap="large")

        with add_col:
            st.markdown("### 🟢 新しい検定予定を追加")
            with st.form("kentei_exam_batch_add_form", clear_on_submit=True):
                k_date = st.date_input("受験予定日", value=date.today())
                k_student = st.selectbox("生徒", student_labels)
                k_name = st.text_input(
                    "検定名",
                    value="プログラミング検定",
                )
                k_grade = st.text_input("級（例：4 / 3 / 2）")
                k_note = st.text_input("メモ（任意）")
                add_exam = st.form_submit_button(
                    "🟢 編集一覧へ追加",
                    use_container_width=True,
                )

            if add_exam:
                sid = k_student.split("|")[0].strip()
                if not sid:
                    st.error("生徒を選択してください。")
                elif not str(k_grade).strip():
                    st.error("級を入力してください。")
                else:
                    new_row = {
                        "student_id": sid,
                        "exam_type": str(k_name).strip(),
                        "grade": str(k_grade).strip(),
                        "exam_date": str(k_date),
                        "note": str(k_note).strip(),
                        "date": str(k_date),
                        "kentei": str(k_name).strip(),
                    }
                    edited = pd.concat(
                        [ks, pd.DataFrame([new_row])],
                        ignore_index=True,
                    )
                    st.session_state[exam_edit_key] = (
                        _normalize_exam_edit_df(edited)
                    )
                    st.session_state[exam_dirty_key] = True
                    st.rerun()

        with edit_col:
            st.markdown("### 🟠 検定予定を編集・削除")
            if ks.empty:
                st.info("検定予定はありません。")
            else:
                options = ks.index.tolist()
                selected_idx = st.selectbox(
                    "予定を選択",
                    options,
                    key="kentei_exam_batch_selected",
                    format_func=lambda idx: (
                        f"{ks.loc[idx, 'exam_date']} | "
                        f"{name_map_k.get(ks.loc[idx, 'student_id'], ks.loc[idx, 'student_id'])} | "
                        f"{ks.loc[idx, 'grade']}級"
                    ),
                )
                row = ks.loc[selected_idx]
                current_label = (
                    f"{row.get('student_id','')} | "
                    f"{name_map_k.get(str(row.get('student_id','')), '')}"
                )
                if current_label not in student_labels:
                    current_label = student_labels[0]

                try:
                    current_date = pd.to_datetime(
                        row.get("exam_date", ""),
                        errors="coerce",
                    )
                    current_date = (
                        current_date.date()
                        if pd.notna(current_date)
                        else date.today()
                    )
                except Exception:
                    current_date = date.today()

                with st.form(
                    f"kentei_exam_batch_edit_form_{selected_idx}"
                ):
                    e_date = st.date_input(
                        "受験予定日",
                        value=current_date,
                    )
                    e_student = st.selectbox(
                        "生徒",
                        student_labels,
                        index=student_labels.index(current_label),
                    )
                    e_name = st.text_input(
                        "検定名",
                        value=str(row.get("exam_type", "")),
                    )
                    e_grade = st.text_input(
                        "級",
                        value=str(row.get("grade", "")),
                    )
                    e_note = st.text_input(
                        "メモ",
                        value=str(row.get("note", "")),
                    )
                    update_exam = st.form_submit_button(
                        "🟠 編集内容を一覧へ反映",
                        use_container_width=True,
                    )

                if update_exam:
                    if not str(e_grade).strip():
                        st.error("級を入力してください。")
                    else:
                        edited = ks.copy()
                        sid = e_student.split("|")[0].strip()
                        values = {
                            "student_id": sid,
                            "exam_type": str(e_name).strip(),
                            "grade": str(e_grade).strip(),
                            "exam_date": str(e_date),
                            "note": str(e_note).strip(),
                            "date": str(e_date),
                            "kentei": str(e_name).strip(),
                        }
                        for col, value in values.items():
                            edited.loc[selected_idx, col] = value
                        st.session_state[exam_edit_key] = (
                            _normalize_exam_edit_df(edited)
                        )
                        st.session_state[exam_dirty_key] = True
                        st.rerun()

                confirm_delete = st.checkbox(
                    "削除を有効にする（確認）",
                    key=f"kentei_exam_delete_confirm_{selected_idx}",
                )
                if st.button(
                    "🗑 選択中の予定を編集一覧から削除",
                    disabled=not confirm_delete,
                    key=f"kentei_exam_delete_{selected_idx}",
                ):
                    edited = ks.drop(
                        index=selected_idx,
                        errors="ignore",
                    ).reset_index(drop=True)
                    st.session_state[exam_edit_key] = (
                        _normalize_exam_edit_df(edited)
                    )
                    st.session_state[exam_dirty_key] = True
                    st.rerun()

        st.divider()
        st.markdown("### 編集中の検定予定一覧")
        if ks.empty:
            st.info("検定予定はありません。")
        else:
            view = ks.copy()
            view["生徒"] = view["student_id"].map(
                name_map_k
            ).fillna(view["student_id"])
            view = view.rename(columns={
                "exam_date": "受験予定日",
                "exam_type": "検定名",
                "grade": "級",
                "note": "メモ",
            })
            st.dataframe(
                view[["受験予定日", "生徒", "検定名", "級", "メモ"]],
                use_container_width=True,
                hide_index=True,
            )

        save_col, discard_col = st.columns([2, 1])
        with save_col:
            save_exam_batch = st.button(
                "💾 検定予定一覧を保存",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.get(
                    exam_dirty_key,
                    False,
                ),
            )
        with discard_col:
            discard_exam_batch = st.button(
                "↩ 編集を破棄",
                use_container_width=True,
                disabled=not st.session_state.get(
                    exam_dirty_key,
                    False,
                ),
            )

        if save_exam_batch:
            if (
                _exam_file_signature()
                != st.session_state.get(
                    exam_base_signature_key
                )
            ):
                st.error(
                    "編集中に検定予定CSVが別の処理で更新されました。"
                    "編集を破棄して最新データを読み直してください。"
                )
            else:
                edited = _normalize_exam_edit_df(
                    st.session_state[exam_edit_key]
                )
                if (
                    edited["student_id"].eq("").any()
                    or edited["grade"].eq("").any()
                    or edited["exam_date"].eq("").any()
                ):
                    st.error(
                        "生徒・級・受験予定日が空の行があるため保存できません。"
                    )
                else:
                    write_csv(
                        edited,
                        KENTEI_EXAM_SCHEDULE_CSV,
                    )
                    for key in [
                        exam_edit_key,
                        exam_dirty_key,
                        exam_base_signature_key,
                    ]:
                        st.session_state.pop(key, None)
                    st.session_state.pop(
                        "kentei_exam_batch_selected",
                        None,
                    )
                    st.success(
                        "検定予定一覧をまとめて保存しました。"
                    )
                    st.rerun()

        if discard_exam_batch:
            for key in [
                exam_edit_key,
                exam_dirty_key,
                exam_base_signature_key,
            ]:
                st.session_state.pop(key, None)
            st.session_state.pop(
                "kentei_exam_batch_selected",
                None,
            )
            st.rerun()

    # ---------------------------
    # 🧩 サブ課題管理（d287 試作版）
    # ---------------------------
    if admin_section == "🧩 サブ課題管理":
        st.subheader("🧩 サブ課題管理")
        st.caption(
            "HTML Masterなど、通常課題と並行して進める補助教材を登録します。"
            "生徒1人につき進行中のサブ課題は1つです。閲覧画面から完了登録できます。"
        )

        sub_master_df = load_sub_curricula()
        sub_items_df = load_sub_curriculum_items()
        student_sub_df = load_student_sub_progress()

        # d293:
        # サブ課題との紐づけに使うメインコース一覧。
        sub_main_courses_df = curr_courses.copy()
        for _c in [
            "course_id", "genre_id", "genre_name",
            "course_name", "course_order", "is_active"
        ]:
            if _c not in sub_main_courses_df.columns:
                sub_main_courses_df[_c] = ""
            sub_main_courses_df[_c] = (
                sub_main_courses_df[_c]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        if not sub_main_courses_df.empty:
            sub_main_courses_df["_order_num"] = pd.to_numeric(
                sub_main_courses_df["course_order"],
                errors="coerce",
            ).fillna(9999)
            sub_main_courses_df = sub_main_courses_df.sort_values(
                ["_order_num", "genre_name", "course_name"],
                na_position="last",
            ).copy()

        sub_main_course_ids = (
            sub_main_courses_df["course_id"]
            .astype(str)
            .str.strip()
            .tolist()
            if not sub_main_courses_df.empty
            else []
        )
        sub_main_course_ids = [
            x for x in sub_main_course_ids if x
        ]
        sub_main_course_label_map = {
            str(r.get("course_id", "")).strip(): get_main_course_label(
                str(r.get("course_id", "")).strip()
            )
            for _, r in sub_main_courses_df.iterrows()
            if str(r.get("course_id", "")).strip()
        }

        # ---------------------------------
        # 1. サブ課題名を登録
        # ---------------------------------
        st.markdown("### 1．サブ課題を登録")
        c_sub1, c_sub2 = st.columns([3, 2])
        with c_sub1:
            new_sub_name = st.text_input(
                "サブ課題名",
                placeholder="例：HTML Master",
                key="sub_master_new_name",
            )
        with c_sub2:
            new_sub_note = st.text_input(
                "メモ（任意）",
                placeholder="例：HTMLの授業前に1項目",
                key="sub_master_new_note",
            )

        new_sub_link_main = st.checkbox(
            "メイン課題と紐づける",
            value=True,
            key="sub_master_new_link_main",
            help=(
                "例：HTML MasterをHTMLコースへ紐づけます。"
                "生徒設定時に、メイン課題の未着手・進行中・完了を確認できます。"
            ),
        )

        if new_sub_link_main:
            if sub_main_course_ids:
                new_sub_main_course_id = st.selectbox(
                    "紐づけるメイン課題",
                    sub_main_course_ids,
                    format_func=lambda x: sub_main_course_label_map.get(x, x),
                    key="sub_master_new_main_course",
                )
            else:
                new_sub_main_course_id = ""
                st.warning(
                    "紐づけできるメイン課題がありません。"
                    "先にカリキュラム管理でコースを登録してください。"
                )
        else:
            new_sub_main_course_id = ""
            st.caption("このサブ課題は、メイン課題と紐づけずに使用します。")

        if st.button("サブ課題を追加", key="sub_master_add_btn"):
            name = str(new_sub_name).strip()
            if not name:
                st.error("サブ課題名を入力してください。")
            elif new_sub_link_main and not new_sub_main_course_id:
                st.error("紐づけるメイン課題を選択してください。")
            elif (
                not sub_master_df.empty
                and sub_master_df["sub_name"].astype(str).str.strip().str.lower().eq(name.lower()).any()
            ):
                st.warning("同じ名前のサブ課題がすでにあります。")
            else:
                sub_id = _next_prefixed_id(
                    sub_master_df["sub_id"] if "sub_id" in sub_master_df.columns else [],
                    "SUB",
                )
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_row = {
                    "sub_id": sub_id,
                    "sub_name": name,
                    "main_course_id": (
                        str(new_sub_main_course_id).strip()
                        if new_sub_link_main
                        else ""
                    ),
                    "is_active": "true",
                    "note": str(new_sub_note).strip(),
                    "created_at": now_str,
                    "updated_at": now_str,
                }
                sub_master_df = pd.concat(
                    [sub_master_df, pd.DataFrame([new_row])],
                    ignore_index=True,
                )
                save_sub_curricula(sub_master_df)
                st.success(f"追加しました：{name}")
                st.rerun()

        if sub_master_df.empty:
            st.info("最初にサブ課題名を登録してください。")
        else:
            sub_master_df = sub_master_df.copy()
            sub_master_df["sub_id"] = sub_master_df["sub_id"].astype(str).str.strip()
            sub_master_df["sub_name"] = sub_master_df["sub_name"].astype(str).str.strip()
            sub_master_df["label"] = (
                sub_master_df["sub_name"] + "（" + sub_master_df["sub_id"] + "）"
            )
            sub_label_to_id = dict(
                zip(sub_master_df["label"], sub_master_df["sub_id"])
            )
            sub_id_to_name = dict(
                zip(sub_master_df["sub_id"], sub_master_df["sub_name"])
            )
            sub_id_to_main_course = dict(
                zip(
                    sub_master_df["sub_id"],
                    sub_master_df["main_course_id"]
                    .fillna("")
                    .astype(str)
                    .str.strip(),
                )
            )

            st.markdown("#### 🔗 登録済みサブ課題のメイン課題設定")
            link_edit_sub_id = st.selectbox(
                "設定するサブ課題",
                sub_master_df["sub_id"].tolist(),
                format_func=lambda x: sub_id_to_name.get(x, x),
                key="sub_master_link_edit_select",
            )
            existing_main_course_id = str(
                sub_id_to_main_course.get(link_edit_sub_id, "")
            ).strip()

            link_edit_enabled = st.checkbox(
                "このサブ課題をメイン課題と紐づける",
                value=bool(existing_main_course_id),
                key=f"sub_master_link_enabled_{link_edit_sub_id}",
            )

            if link_edit_enabled:
                if sub_main_course_ids:
                    edit_course_options = list(sub_main_course_ids)
                    if (
                        existing_main_course_id
                        and existing_main_course_id not in edit_course_options
                    ):
                        edit_course_options.append(existing_main_course_id)

                    edit_course_index = (
                        edit_course_options.index(existing_main_course_id)
                        if existing_main_course_id in edit_course_options
                        else 0
                    )
                    link_edit_course_id = st.selectbox(
                        "紐づけるメイン課題",
                        edit_course_options,
                        index=edit_course_index,
                        format_func=lambda x: sub_main_course_label_map.get(
                            x, get_main_course_label(x)
                        ),
                        key=f"sub_master_link_course_{link_edit_sub_id}",
                    )
                else:
                    link_edit_course_id = ""
                    st.warning("紐づけできるメイン課題がありません。")
            else:
                link_edit_course_id = ""
                st.caption("メイン課題との紐づけを行いません。")

            if st.button(
                "メイン課題の設定を保存",
                key=f"sub_master_link_save_{link_edit_sub_id}",
            ):
                if link_edit_enabled and not link_edit_course_id:
                    st.error("紐づけるメイン課題を選択してください。")
                else:
                    link_update_mask = (
                        sub_master_df["sub_id"]
                        .astype(str)
                        .str.strip()
                        .eq(link_edit_sub_id)
                    )
                    sub_master_df.loc[
                        link_update_mask, "main_course_id"
                    ] = (
                        str(link_edit_course_id).strip()
                        if link_edit_enabled
                        else ""
                    )
                    sub_master_df.loc[
                        link_update_mask, "updated_at"
                    ] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    save_sub_curricula(
                        sub_master_df.drop(
                            columns=["label"],
                            errors="ignore",
                        )
                    )
                    st.success("メイン課題との紐づけを保存しました。")
                    st.rerun()

            link_table = sub_master_df.copy()
            link_table["メイン課題"] = (
                link_table["main_course_id"]
                .fillna("")
                .astype(str)
                .str.strip()
                .map(
                    lambda x: (
                        get_main_course_label(x)
                        if x
                        else "紐づけなし"
                    )
                )
            )
            st.dataframe(
                link_table[
                    ["sub_name", "メイン課題", "note"]
                ].rename(
                    columns={
                        "sub_name": "サブ課題",
                        "note": "メモ",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.divider()

            # ---------------------------------
            # 2. サブ課題の項目を登録・修正
            # ---------------------------------
            st.markdown("### 2．項目を登録・修正")
            selected_sub_label = st.selectbox(
                "項目を管理するサブ課題",
                sub_master_df["label"].tolist(),
                key="sub_item_master_select",
            )
            selected_sub_id = sub_label_to_id.get(selected_sub_label, "")
            selected_sub_name = sub_id_to_name.get(selected_sub_id, selected_sub_id)

            st.caption(
                "1行につき1項目で、まとめて登録できます。入力した順に並びます。"
            )
            bulk_item_text = st.text_area(
                "追加する項目",
                placeholder="例：\n1-1 HTMLの基本\n1-2 見出し\n1-3 段落",
                height=140,
                key="sub_item_bulk_text",
            )

            if st.button("項目を追加", key="sub_item_add_btn"):
                item_names = [
                    line.strip()
                    for line in str(bulk_item_text).splitlines()
                    if line.strip()
                ]
                if not item_names:
                    st.error("追加する項目を入力してください。")
                else:
                    existing_for_sub = sub_items_df[
                        sub_items_df["sub_id"].astype(str).str.strip() == selected_sub_id
                    ].copy()
                    existing_names = set(
                        existing_for_sub["item_name"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .tolist()
                    )
                    order_nums = pd.to_numeric(
                        existing_for_sub.get("order", pd.Series(dtype=str)),
                        errors="coerce",
                    ).dropna()
                    next_order = int(order_nums.max()) + 1 if not order_nums.empty else 1
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    rows = []

                    for item_name in item_names:
                        if item_name.lower() in existing_names:
                            continue
                        item_id = _next_prefixed_id(
                            pd.concat(
                                [
                                    sub_items_df.get("item_id", pd.Series(dtype=str)),
                                    pd.Series([r["item_id"] for r in rows], dtype=str),
                                ],
                                ignore_index=True,
                            ),
                            "ITEM",
                        )
                        rows.append({
                            "sub_id": selected_sub_id,
                            "item_id": item_id,
                            "item_name": item_name,
                            "order": str(next_order),
                            "is_active": "true",
                            "created_at": now_str,
                            "updated_at": now_str,
                        })
                        existing_names.add(item_name.lower())
                        next_order += 1

                    if rows:
                        sub_items_df = pd.concat(
                            [sub_items_df, pd.DataFrame(rows)],
                            ignore_index=True,
                        )
                        save_sub_curriculum_items(sub_items_df)
                        st.success(f"{selected_sub_name}に{len(rows)}項目追加しました。")
                        st.rerun()
                    else:
                        st.warning("新しく追加できる項目がありませんでした。")

            current_items = sub_items_df[
                sub_items_df["sub_id"].astype(str).str.strip() == selected_sub_id
            ].copy()

            if current_items.empty:
                st.caption("このサブ課題には、まだ項目がありません。")
            else:
                current_items["_order_num"] = pd.to_numeric(
                    current_items["order"], errors="coerce"
                ).fillna(9999)
                current_items = current_items.sort_values(
                    ["_order_num", "item_name"], na_position="last"
                ).copy()

                current_items["状態"] = (
                    current_items["is_active"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .replace("", "true")
                    .map(lambda x: "使用中" if x in ["true", "1", "yes", "on"] else "停止中")
                )

                show_items = current_items[
                    ["order", "item_name", "状態"]
                ].rename(
                    columns={
                        "order": "順番",
                        "item_name": "項目",
                    }
                )
                st.dataframe(
                    show_items,
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown("#### ✏️ 登録済み項目の修正・削除")
                st.caption(
                    "項目名は、生徒の現在位置や過去の完了履歴を保ったまま変更できます。"
                )
                st.info(
                    "【移動先の使い方】4番の項目を3番へ移動すると、"
                    "元の3番が4番へ移ります。8番を3番へ移動すると、"
                    "元の3〜7番が1つずつ後ろへずれます。"
                    "保存後は、このサブ課題内の順番を1、2、3…と自動で振り直します。"
                )

                current_items["item_id"] = (
                    current_items["item_id"].fillna("").astype(str).str.strip()
                )
                current_items["item_name"] = (
                    current_items["item_name"].fillna("").astype(str).str.strip()
                )
                current_items["order"] = (
                    current_items["order"].fillna("").astype(str).str.strip()
                )

                item_ids_for_edit = current_items["item_id"].tolist()
                item_edit_label_map = {
                    str(r.get("item_id", "")).strip(): (
                        f'{str(r.get("order", "")).strip()}｜'
                        f'{str(r.get("item_name", "")).strip()}'
                        f'（{str(r.get("状態", "")).strip()}）'
                    )
                    for _, r in current_items.iterrows()
                }

                selected_item_id = st.selectbox(
                    "修正する項目",
                    item_ids_for_edit,
                    format_func=lambda x: item_edit_label_map.get(x, x),
                    key=f"sub_item_edit_select_{selected_sub_id}",
                )

                selected_item_hit = current_items[
                    current_items["item_id"].astype(str).str.strip() == selected_item_id
                ].copy()

                if not selected_item_hit.empty:
                    selected_item_row = selected_item_hit.iloc[0]
                    selected_item_name = str(
                        selected_item_row.get("item_name", "")
                    ).strip()
                    # d292:
                    # 保存済みのorder値が重複していても、現在画面に並んでいる順を
                    # 1、2、3…の位置として扱う。
                    ordered_item_ids = (
                        current_items["item_id"]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        .tolist()
                    )
                    selected_item_position = (
                        ordered_item_ids.index(selected_item_id) + 1
                        if selected_item_id in ordered_item_ids
                        else 1
                    )
                    item_count_for_move = max(1, len(ordered_item_ids))

                    selected_item_active = (
                        str(selected_item_row.get("is_active", ""))
                        .strip()
                        .lower()
                        in ["true", "1", "yes", "on", ""]
                    )

                    edit_col1, edit_col2 = st.columns([4, 1])
                    with edit_col1:
                        edited_item_name = st.text_input(
                            "項目名",
                            value=selected_item_name,
                            key=f"sub_item_edit_name_{selected_item_id}",
                        )
                    with edit_col2:
                        edited_item_position = st.number_input(
                            "移動先",
                            min_value=1,
                            max_value=item_count_for_move,
                            step=1,
                            value=selected_item_position,
                            key=f"sub_item_edit_position_{selected_item_id}",
                            help=(
                                f"1〜{item_count_for_move}の位置を指定します。"
                                "指定した位置へ項目を移し、間にある項目を自動でずらします。"
                            ),
                        )

                    if int(edited_item_position) != selected_item_position:
                        st.caption(
                            f"現在の{selected_item_position}番から"
                            f"{int(edited_item_position)}番へ移動します。"
                        )

                    edited_item_active = st.checkbox(
                        "使用中",
                        value=selected_item_active,
                        key=f"sub_item_edit_active_{selected_item_id}",
                        help="停止中にすると、新しい生徒の項目選択や「完了して次へ」の進行対象から外れます。",
                    )

                    # この項目を現在位置として使っている生徒と、完了履歴を確認する。
                    latest_student_sub_df = load_student_sub_progress()
                    latest_sub_log_df = load_sub_progress_log()

                    current_ref_rows = pd.DataFrame()
                    if not latest_student_sub_df.empty:
                        current_ref_rows = latest_student_sub_df[
                            latest_student_sub_df["current_item_id"]
                            .astype(str)
                            .str.strip()
                            .eq(selected_item_id)
                        ].copy()

                    active_current_ref_rows = pd.DataFrame()
                    if not current_ref_rows.empty:
                        active_current_ref_rows = current_ref_rows[
                            current_ref_rows["is_active"]
                            .fillna("")
                            .astype(str)
                            .str.strip()
                            .str.lower()
                            .isin(["true", "1", "yes", "on"])
                        ].copy()

                    log_ref_rows = pd.DataFrame()
                    if not latest_sub_log_df.empty:
                        log_ref_rows = latest_sub_log_df[
                            latest_sub_log_df["item_id"]
                            .astype(str)
                            .str.strip()
                            .eq(selected_item_id)
                        ].copy()

                    current_ref_count = len(current_ref_rows)
                    active_current_ref_count = len(active_current_ref_rows)
                    log_ref_count = len(log_ref_rows)

                    if current_ref_count or log_ref_count:
                        st.caption(
                            f"参照状況：現在位置 {current_ref_count}人"
                            f"（進行中 {active_current_ref_count}人）／"
                            f"完了履歴 {log_ref_count}件"
                        )
                    else:
                        st.caption("参照状況：現在位置・完了履歴ともにありません。")

                    if st.button(
                        "変更を保存",
                        key=f"sub_item_edit_save_{selected_item_id}",
                    ):
                        new_name = str(edited_item_name).strip()
                        target_position = int(edited_item_position)
                        turning_off = selected_item_active and not edited_item_active

                        duplicate_name = bool(
                            (
                                sub_items_df["sub_id"]
                                .astype(str)
                                .str.strip()
                                .eq(selected_sub_id)
                                & sub_items_df["item_name"]
                                .astype(str)
                                .str.strip()
                                .str.lower()
                                .eq(new_name.lower())
                                & ~sub_items_df["item_id"]
                                .astype(str)
                                .str.strip()
                                .eq(selected_item_id)
                            ).any()
                        )

                        if not new_name:
                            st.error("項目名を入力してください。")
                        elif duplicate_name:
                            st.error("同じサブ課題内に、同じ項目名がすでにあります。")
                        elif turning_off and active_current_ref_count > 0:
                            st.error(
                                f"この項目を進行中の生徒が{active_current_ref_count}人いるため、"
                                "停止できません。先に生徒の「次にやる項目」を変更してください。"
                            )
                        else:
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            update_mask = (
                                sub_items_df["item_id"]
                                .astype(str)
                                .str.strip()
                                .eq(selected_item_id)
                            )

                            # 項目名・使用状態は内部IDを変えずに更新する。
                            sub_items_df.loc[update_mask, "item_name"] = new_name
                            sub_items_df.loc[update_mask, "is_active"] = (
                                "true" if edited_item_active else "false"
                            )
                            sub_items_df.loc[update_mask, "updated_at"] = now_str

                            # d292:
                            # 現在の表示順から選択項目を一度外し、
                            # 指定された移動先へ差し込む。
                            reordered_ids = list(ordered_item_ids)
                            if selected_item_id in reordered_ids:
                                reordered_ids.remove(selected_item_id)

                            safe_target_index = max(
                                0,
                                min(target_position - 1, len(reordered_ids)),
                            )
                            reordered_ids.insert(
                                safe_target_index,
                                selected_item_id,
                            )

                            # 同じサブ課題内を1、2、3…と連番で振り直す。
                            for new_position, item_id_for_order in enumerate(
                                reordered_ids,
                                start=1,
                            ):
                                order_mask = (
                                    sub_items_df["item_id"]
                                    .astype(str)
                                    .str.strip()
                                    .eq(item_id_for_order)
                                )
                                sub_items_df.loc[
                                    order_mask, "order"
                                ] = str(new_position)

                                # 順番が変わった項目にも更新時刻を記録する。
                                if new_position != (
                                    ordered_item_ids.index(item_id_for_order) + 1
                                ):
                                    sub_items_df.loc[
                                        order_mask, "updated_at"
                                    ] = now_str

                            save_sub_curriculum_items(sub_items_df)

                            if target_position == selected_item_position:
                                st.success(
                                    "サブ項目を変更し、順番を1から連番に整えました。"
                                )
                            else:
                                st.success(
                                    f"サブ項目を{selected_item_position}番から"
                                    f"{target_position}番へ移動しました。"
                                )
                            st.rerun()

                    st.markdown("##### 完全削除")
                    if current_ref_count > 0 or log_ref_count > 0:
                        st.warning(
                            "この項目は生徒の現在位置または完了履歴から参照されているため、"
                            "完全削除できません。項目名の修正、または使用停止を利用してください。"
                        )
                    else:
                        delete_confirm_key = (
                            f"sub_item_delete_confirm_{selected_item_id}"
                        )
                        delete_confirming = bool(
                            st.session_state.get(delete_confirm_key, False)
                        )

                        if not delete_confirming:
                            if st.button(
                                "🗑️ この項目を完全削除",
                                key=f"sub_item_delete_open_{selected_item_id}",
                            ):
                                st.session_state[delete_confirm_key] = True
                                st.rerun()
                        else:
                            st.warning(
                                f"「{selected_item_name}」を完全削除します。"
                                "この操作は取り消せません。"
                            )
                            delete_col1, delete_col2 = st.columns(2)

                            with delete_col1:
                                if st.button(
                                    "完全削除する",
                                    type="primary",
                                    key=f"sub_item_delete_do_{selected_item_id}",
                                ):
                                    delete_mask = (
                                        sub_items_df["item_id"]
                                        .astype(str)
                                        .str.strip()
                                        .eq(selected_item_id)
                                    )
                                    sub_items_df = sub_items_df[
                                        ~delete_mask
                                    ].copy()

                                    # d292:
                                    # 削除後に同じサブ課題の順番を詰め直す。
                                    remaining_same_sub = sub_items_df[
                                        sub_items_df["sub_id"]
                                        .astype(str)
                                        .str.strip()
                                        .eq(selected_sub_id)
                                    ].copy()
                                    remaining_same_sub["_order_num"] = pd.to_numeric(
                                        remaining_same_sub["order"],
                                        errors="coerce",
                                    ).fillna(9999)
                                    remaining_same_sub = remaining_same_sub.sort_values(
                                        ["_order_num", "item_name"],
                                        na_position="last",
                                    )

                                    delete_now_str = datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    )
                                    for new_position, remaining_item_id in enumerate(
                                        remaining_same_sub["item_id"]
                                        .astype(str)
                                        .str.strip()
                                        .tolist(),
                                        start=1,
                                    ):
                                        remaining_mask = (
                                            sub_items_df["item_id"]
                                            .astype(str)
                                            .str.strip()
                                            .eq(remaining_item_id)
                                        )
                                        sub_items_df.loc[
                                            remaining_mask, "order"
                                        ] = str(new_position)
                                        sub_items_df.loc[
                                            remaining_mask, "updated_at"
                                        ] = delete_now_str

                                    save_sub_curriculum_items(sub_items_df)

                                    st.session_state.pop(delete_confirm_key, None)
                                    st.session_state.pop(
                                        f"sub_item_edit_select_{selected_sub_id}",
                                        None,
                                    )
                                    st.success("サブ項目を完全削除しました。")
                                    st.rerun()

                            with delete_col2:
                                if st.button(
                                    "やめる",
                                    key=f"sub_item_delete_cancel_{selected_item_id}",
                                ):
                                    st.session_state[delete_confirm_key] = False
                                    st.rerun()

            st.divider()

            # ---------------------------------
            # 3. 生徒へ設定
            # ---------------------------------
            st.markdown("### 3．生徒に設定")
            st.caption(
                "「サブ課題進行中」がONの生徒だけ、「次に見る候補」にサブ課題が表示されます。"
            )

            sub_students = admin_students_for_pick.copy()
            if sub_students.empty:
                st.info("設定できる生徒がいません。")
            else:
                for c in ["student_id", "display_name"]:
                    if c not in sub_students.columns:
                        sub_students[c] = ""
                    sub_students[c] = sub_students[c].fillna("").astype(str).str.strip()
                sub_students["label"] = (
                    sub_students["student_id"] + " | " + sub_students["display_name"]
                )

                selected_student_label = st.selectbox(
                    "生徒を選択",
                    sub_students["label"].tolist(),
                    key="student_sub_student_select",
                )
                selected_student_id = selected_student_label.split("|", 1)[0].strip()

                existing_progress = student_sub_df[
                    student_sub_df["student_id"].astype(str).str.strip()
                    == selected_student_id
                ].copy()

                existing_sub_id = ""
                existing_item_id = ""
                existing_active = False
                existing_note = ""
                if not existing_progress.empty:
                    erow = existing_progress.iloc[-1]
                    existing_sub_id = str(erow.get("sub_id", "")).strip()
                    existing_item_id = str(erow.get("current_item_id", "")).strip()
                    existing_active = (
                        str(erow.get("is_active", "")).strip().lower()
                        in ["true", "1", "yes", "on"]
                    )
                    existing_note = str(erow.get("note", "")).strip()

                sub_id_options = sub_master_df["sub_id"].tolist()
                default_sub_index = (
                    sub_id_options.index(existing_sub_id)
                    if existing_sub_id in sub_id_options
                    else 0
                )

                chosen_sub_id = st.selectbox(
                    "サブ課題",
                    sub_id_options,
                    index=default_sub_index,
                    format_func=lambda x: sub_id_to_name.get(x, x),
                    key=f"student_sub_master_{selected_student_id}",
                )

                chosen_main_course_id = str(
                    sub_id_to_main_course.get(chosen_sub_id, "")
                ).strip()
                chosen_main_state = get_student_main_course_status(
                    selected_student_id,
                    chosen_main_course_id,
                )

                if not chosen_main_course_id:
                    st.caption("メイン課題：紐づけなし")
                elif not chosen_main_state.get("course_exists"):
                    st.warning(
                        "⚠ 紐づけ先のメイン課題が見つかりません："
                        f"{chosen_main_state.get('course_name', chosen_main_course_id)}"
                    )
                elif chosen_main_state.get("status") == "完了":
                    st.success(
                        "メイン課題："
                        f"{chosen_main_state.get('course_name', '')} / "
                        f"{chosen_main_state.get('status_detail', '完了')}"
                    )
                elif chosen_main_state.get("status") == "進行中":
                    if chosen_main_state.get("all_tasks_finished"):
                        st.warning(
                            "メイン課題："
                            f"{chosen_main_state.get('course_name', '')} / "
                            f"{chosen_main_state.get('status_detail', '進行中')}"
                        )
                    else:
                        st.info(
                            "メイン課題："
                            f"{chosen_main_state.get('course_name', '')} / "
                            f"{chosen_main_state.get('status_detail', '進行中')}"
                        )
                else:
                    st.warning(
                        "⚠ この生徒は、紐づいているメイン課題が未着手です："
                        f"{chosen_main_state.get('course_name', '')} / "
                        f"{chosen_main_state.get('status_detail', '未着手')}"
                    )

                chosen_items_all = sub_items_df[
                    sub_items_df["sub_id"].astype(str).str.strip() == chosen_sub_id
                ].copy()

                if not chosen_items_all.empty:
                    chosen_items_all["_active_bool"] = (
                        chosen_items_all["is_active"]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .replace("", "true")
                        .isin(["true", "1", "yes", "on"])
                    )

                    # 新規選択は使用中項目だけ。
                    # 既存設定が停止中項目を指している場合だけ、その項目も表示する。
                    chosen_items = chosen_items_all[
                        chosen_items_all["_active_bool"]
                    ].copy()
                    if (
                        existing_sub_id == chosen_sub_id
                        and existing_item_id
                        and existing_item_id
                        not in chosen_items["item_id"].astype(str).str.strip().tolist()
                    ):
                        existing_inactive_hit = chosen_items_all[
                            chosen_items_all["item_id"]
                            .astype(str)
                            .str.strip()
                            .eq(existing_item_id)
                        ].copy()
                        if not existing_inactive_hit.empty:
                            chosen_items = pd.concat(
                                [chosen_items, existing_inactive_hit],
                                ignore_index=True,
                            )

                    chosen_items["_order_num"] = pd.to_numeric(
                        chosen_items["order"], errors="coerce"
                    ).fillna(9999)
                    chosen_items = chosen_items.sort_values(
                        ["_order_num", "item_name"], na_position="last"
                    )
                    chosen_item_ids = (
                        chosen_items["item_id"].astype(str).str.strip().tolist()
                    )
                    item_name_map = dict(
                        zip(
                            chosen_items["item_id"].astype(str).str.strip(),
                            chosen_items["item_name"].astype(str).str.strip(),
                        )
                    )
                    inactive_item_ids = set(
                        chosen_items_all.loc[
                            ~chosen_items_all["_active_bool"], "item_id"
                        ].astype(str).str.strip()
                    )
                else:
                    chosen_item_ids = [""]
                    item_name_map = {"": "項目未登録"}
                    inactive_item_ids = set()

                default_item_index = (
                    chosen_item_ids.index(existing_item_id)
                    if existing_sub_id == chosen_sub_id
                    and existing_item_id in chosen_item_ids
                    else 0
                )

                chosen_item_id = st.selectbox(
                    "次にやる項目",
                    chosen_item_ids,
                    index=default_item_index,
                    format_func=lambda x: (
                        (
                            item_name_map.get(x, x or "項目未登録")
                            + "（停止中）"
                        )
                        if x in inactive_item_ids
                        else item_name_map.get(x, x or "項目未登録")
                    ),
                    key=f"student_sub_item_{selected_student_id}_{chosen_sub_id}",
                )
                chosen_active = st.checkbox(
                    "サブ課題進行中",
                    value=existing_active,
                    key=f"student_sub_active_{selected_student_id}",
                )
                chosen_note = st.text_input(
                    "生徒別メモ（任意）",
                    value=existing_note,
                    key=f"student_sub_note_{selected_student_id}",
                )

                main_course_needs_confirmation = bool(
                    chosen_main_course_id
                    and (
                        not chosen_main_state.get("course_exists")
                        or chosen_main_state.get("status") == "未着手"
                    )
                )
                allow_unstarted_main = False
                if chosen_active and main_course_needs_confirmation:
                    allow_unstarted_main = st.checkbox(
                        "メイン課題の状態を確認したうえで、このまま設定する",
                        value=False,
                        key=(
                            f"student_sub_main_override_"
                            f"{selected_student_id}_{chosen_sub_id}"
                        ),
                    )

                if st.button(
                    "生徒のサブ課題設定を保存",
                    key=f"student_sub_save_{selected_student_id}",
                ):
                    if chosen_active and not chosen_sub_id:
                        st.error("サブ課題を選択してください。")
                    elif chosen_active and not chosen_item_id:
                        st.error("進行中にする前に、項目を1つ以上登録してください。")
                    elif chosen_active and chosen_item_id in inactive_item_ids:
                        st.error(
                            "停止中の項目は進行中として設定できません。"
                            "使用中の項目を選ぶか、項目管理で再開してください。"
                        )
                    elif (
                        chosen_active
                        and main_course_needs_confirmation
                        and not allow_unstarted_main
                    ):
                        st.error(
                            "紐づいているメイン課題が未着手、"
                            "または紐づけ先が見つかりません。"
                            "状態を確認してから確認欄をONにしてください。"
                        )
                    else:
                        upsert_student_sub_progress(
                            selected_student_id,
                            chosen_sub_id,
                            chosen_item_id,
                            chosen_active,
                            chosen_note,
                        )
                        state_label = "進行中" if chosen_active else "停止中"
                        st.success(
                            f"保存しました：{sub_id_to_name.get(chosen_sub_id, chosen_sub_id)} / {state_label}"
                        )
                        st.rerun()

            # 現在の設定一覧
            st.divider()
            st.markdown("### 現在の設定")
            current_progress = load_student_sub_progress()
            if current_progress.empty:
                st.caption("生徒への設定はまだありません。")
            else:
                student_name_map = dict(
                    zip(
                        students["student_id"].astype(str).str.strip(),
                        students["display_name"].astype(str).str.strip(),
                    )
                )
                item_name_all_map = dict(
                    zip(
                        sub_items_df["item_id"].astype(str).str.strip(),
                        sub_items_df["item_name"].astype(str).str.strip(),
                    )
                )
                current_progress = current_progress.copy()
                current_progress["生徒"] = current_progress["student_id"].astype(str).str.strip().map(
                    student_name_map
                ).fillna(current_progress["student_id"])
                current_progress["サブ課題"] = current_progress["sub_id"].astype(str).str.strip().map(
                    sub_id_to_name
                ).fillna(current_progress["sub_id"])
                current_progress["次にやる項目"] = current_progress["current_item_id"].astype(str).str.strip().map(
                    item_name_all_map
                ).fillna(current_progress["current_item_id"])
                current_progress["サブ状況"] = current_progress["is_active"].astype(str).str.strip().str.lower().map(
                    lambda x: "進行中" if x in ["true", "1", "yes", "on"] else "停止中"
                )

                main_course_names = []
                main_course_statuses = []
                main_course_checks = []

                for _, progress_row in current_progress.iterrows():
                    row_sid = str(
                        progress_row.get("student_id", "")
                    ).strip()
                    row_sub_id = str(
                        progress_row.get("sub_id", "")
                    ).strip()
                    row_sub_active = (
                        str(progress_row.get("is_active", ""))
                        .strip()
                        .lower()
                        in ["true", "1", "yes", "on"]
                    )
                    row_main_course_id = str(
                        sub_id_to_main_course.get(row_sub_id, "")
                    ).strip()
                    row_main_state = get_student_main_course_status(
                        row_sid,
                        row_main_course_id,
                    )

                    if not row_main_course_id:
                        main_course_names.append("紐づけなし")
                        main_course_statuses.append("－")
                        main_course_checks.append("－")
                    else:
                        main_course_names.append(
                            str(
                                row_main_state.get(
                                    "course_name",
                                    row_main_course_id,
                                )
                            )
                        )
                        main_course_statuses.append(
                            str(
                                row_main_state.get(
                                    "status_detail",
                                    row_main_state.get("status", ""),
                                )
                            )
                        )

                        if not row_main_state.get("course_exists"):
                            main_course_checks.append("⚠ 紐づけ先不明")
                        elif (
                            row_sub_active
                            and row_main_state.get("status") == "未着手"
                        ):
                            main_course_checks.append("⚠ 要確認")
                        elif (
                            row_main_state.get("all_tasks_finished")
                            and row_main_state.get("status") != "完了"
                        ):
                            main_course_checks.append("⚠ メイン完了登録待ち")
                        else:
                            main_course_checks.append("OK")

                current_progress["メイン課題"] = main_course_names
                current_progress["メイン状況"] = main_course_statuses
                current_progress["確認"] = main_course_checks

                st.dataframe(
                    current_progress[
                        [
                            "生徒", "サブ課題", "メイン課題",
                            "メイン状況", "サブ状況",
                            "次にやる項目", "確認", "note"
                        ]
                    ].rename(columns={"note": "メモ"}),
                    use_container_width=True,
                    hide_index=True,
                )


        # ---------------------------
        # 📘 カリキュラム管理（追加・編集・削除）
        #   - curriculum_courses.csv
        #   - curriculum_tasks.csv
        # ---------------------------
    if admin_section == "📘 カリキュラム管理":
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

        # =====================================================
        # d271:
        # ↩ コース完了を取り消す
        # -----------------------------------------------------
        # 誤って「コース完了」を付けた時に戻すための安全操作。
        # 課題ごとの完了・スキップ（curriculum_progress.csv）は消さず、
        # progress_log.csv の note=course_done 行だけ削除する。
        # =====================================================
        if override_done_lock:
            with st.expander("↩ コース完了を取り消す（安全操作）", expanded=False):
                st.caption("誤って付けたコース完了だけを取り消します。課題ごとの完了・スキップ記録は消しません。")

                course_done_log = log.copy()
                if course_done_log.empty:
                    st.info("コース完了ログはありません。")
                else:
                    for _c in ["date", "student_id", "curriculum", "item", "status", "note"]:
                        if _c not in course_done_log.columns:
                            course_done_log[_c] = ""
                        course_done_log[_c] = course_done_log[_c].fillna("").astype(str).str.strip()

                    course_done_log = course_done_log[
                        (course_done_log["status"].astype(str).str.strip().str.lower() == "done")
                        & (course_done_log["note"].astype(str).str.strip() == "course_done")
                    ].copy()

                    if course_done_log.empty:
                        st.info("取り消せるコース完了ログはありません。")
                    else:
                        _student_name_map_for_course_done = {}
                        try:
                            _students_for_course_done = students.copy()
                            for _c in ["student_id", "display_name"]:
                                if _c not in _students_for_course_done.columns:
                                    _students_for_course_done[_c] = ""
                                _students_for_course_done[_c] = _students_for_course_done[_c].fillna("").astype(str).str.strip()
                            _student_name_map_for_course_done = dict(
                                zip(
                                    _students_for_course_done["student_id"].astype(str).str.strip(),
                                    _students_for_course_done["display_name"].astype(str).str.strip(),
                                )
                            )
                        except Exception:
                            _student_name_map_for_course_done = {}

                        course_done_log = course_done_log.reset_index().rename(columns={"index": "_log_index"})
                        course_done_log["_label"] = course_done_log.apply(
                            lambda _r: (
                                f"{str(_r.get('date','')).strip()}｜"
                                f"{_student_name_map_for_course_done.get(str(_r.get('student_id','')).strip(), str(_r.get('student_id','')).strip())}｜"
                                f"{str(_r.get('curriculum','')).strip()} / {str(_r.get('item','')).strip()}"
                            ),
                            axis=1,
                        )

                        selected_course_done_label = st.selectbox(
                            "取り消すコース完了",
                            course_done_log["_label"].tolist(),
                            key="cancel_course_done_target",
                        )

                        selected_course_done_row = course_done_log[
                            course_done_log["_label"].astype(str) == str(selected_course_done_label)
                        ].iloc[0]

                        st.info(
                            "取り消す対象："
                            f"{selected_course_done_row.get('date','')} / "
                            f"{_student_name_map_for_course_done.get(str(selected_course_done_row.get('student_id','')).strip(), str(selected_course_done_row.get('student_id','')).strip())} / "
                            f"{selected_course_done_row.get('curriculum','')} / {selected_course_done_row.get('item','')}"
                        )

                        confirm_cancel_course_done = st.checkbox(
                            "本当にこのコース完了だけを取り消す",
                            value=False,
                            key="confirm_cancel_course_done",
                        )

                        if st.button(
                            "↩ コース完了を取り消す",
                            key="cancel_course_done_btn",
                            disabled=not confirm_cancel_course_done,
                        ):
                            target_index = selected_course_done_row.get("_log_index", None)
                            log2 = log.copy()

                            if target_index is not None and target_index in log2.index:
                                log2 = log2.drop(index=target_index).reset_index(drop=True)
                            else:
                                # 念のため、indexが合わない場合は内容一致で削除
                                for _c in ["date", "student_id", "curriculum", "item", "status", "note"]:
                                    if _c not in log2.columns:
                                        log2[_c] = ""
                                    log2[_c] = log2[_c].fillna("").astype(str).str.strip()

                                _mask = (
                                    (log2["date"].astype(str).str.strip() == str(selected_course_done_row.get("date", "")).strip())
                                    & (log2["student_id"].astype(str).str.strip() == str(selected_course_done_row.get("student_id", "")).strip())
                                    & (log2["curriculum"].astype(str).str.strip() == str(selected_course_done_row.get("curriculum", "")).strip())
                                    & (log2["item"].astype(str).str.strip() == str(selected_course_done_row.get("item", "")).strip())
                                    & (log2["status"].astype(str).str.strip().str.lower() == "done")
                                    & (log2["note"].astype(str).str.strip() == "course_done")
                                )
                                log2 = log2.loc[~_mask].reset_index(drop=True)

                            backup_file(PROGRESS_LOG_CSV)
                            write_csv_atomic(log2, PROGRESS_LOG_CSV)
                            st.success("コース完了を取り消しました。課題ごとの進捗記録は残っています。")
                            st.rerun()
        else:
            st.caption("コース完了の取り消しは、上の『完了済み課題を編集する』をONにすると表示されます。")

        # ---------- Courses ----------
        st.markdown("### 1) コース（curriculum_courses.csv）")

        # d326:
        # コースの追加・編集・削除は編集用データへ反映し、
        # 最後に一度だけ curriculum_courses.csv へ保存する。
        course_edit_key = "curriculum_courses_batch_edit_df"
        course_dirty_key = "curriculum_courses_batch_dirty"
        course_base_signature_key = "curriculum_courses_batch_base_signature"
        course_pending_task_delete_key = "curriculum_courses_pending_task_delete"

        course_cols = [
            "course_id",
            "genre_id",
            "genre_name",
            "course_name",
            "course_order",
            "is_active",
        ]

        def _course_file_signature():
            try:
                p = Path(CURRICULUM_COURSES_CSV)
                stat = p.stat()
                return (int(stat.st_mtime_ns), int(stat.st_size))
            except Exception:
                return None

        def _normalize_courses_edit_df(df):
            out = df.copy() if df is not None else pd.DataFrame()
            for col in course_cols:
                if col not in out.columns:
                    out[col] = ""

            out["course_id"] = (
                out["course_id"].fillna("").astype(str).str.strip()
            )
            out["genre_id"] = (
                out["genre_id"].fillna("").astype(str).str.strip()
            )
            out["genre_name"] = (
                out["genre_name"].fillna("").astype(str).str.strip()
            )
            out["course_name"] = (
                out["course_name"].fillna("").astype(str).str.strip()
            )
            out["course_order"] = pd.to_numeric(
                out["course_order"],
                errors="coerce",
            ).fillna(0).astype(int)
            out["is_active"] = out["is_active"].map(
                lambda v: (
                    v
                    if isinstance(v, bool)
                    else str(v).strip().lower()
                    in ("1", "true", "t", "yes", "y", "on")
                )
            )
            return out[course_cols].reset_index(drop=True)

        if course_edit_key not in st.session_state:
            loaded_courses = safe_read_csv(
                CURRICULUM_COURSES_CSV,
                course_cols,
                stop_on_missing=False,
            )
            st.session_state[course_edit_key] = (
                _normalize_courses_edit_df(loaded_courses)
            )
            st.session_state[course_dirty_key] = False
            st.session_state[course_base_signature_key] = (
                _course_file_signature()
            )
            st.session_state[course_pending_task_delete_key] = []

        courses = _normalize_courses_edit_df(
            st.session_state[course_edit_key]
        )

        if st.session_state.get(course_dirty_key, False):
            st.warning("🟡 保存していないコース管理の変更があります。")
        else:
            st.success("🟢 コース管理は保存済みです。")

        st.caption(
            "複数のコースを追加・修正・削除してから、"
            "最後に一度だけ保存します。"
        )

        # 表示用
        courses_view = courses.copy()
        if not courses_view.empty:
            courses_view["course_order_num"] = pd.to_numeric(
                courses_view["course_order"],
                errors="coerce",
            ).fillna(9999).astype(int)
            courses_view = (
                courses_view
                .sort_values(
                    ["course_order_num", "course_id"],
                    na_position="last",
                )
                .drop(columns=["course_order_num"])
            )
        st.dataframe(
            courses_view,
            use_container_width=True,
            hide_index=True,
        )

        colC1, colC2 = st.columns(2, gap="large")

        # =====================================================
        # 新規追加
        # =====================================================
        with colC1:
            st.markdown(
                """
                <div style="
                    background:#ecfdf5;
                    border:2px solid #22c55e;
                    border-left:10px solid #16a34a;
                    border-radius:12px;
                    padding:12px 14px;
                    margin-bottom:12px;
                ">
                    <div style="font-size:18px;font-weight:900;color:#166534;">
                        🟢 新しいコースを追加
                    </div>
                    <div style="font-size:12px;color:#166534;margin-top:4px;">
                        追加後もCSVにはまだ保存されません。
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form(
                "course_batch_add_form",
                clear_on_submit=True,
            ):
                add_course_id = st.text_input(
                    "course_id（例: PY-GAME-001）"
                )
                add_genre_id = st.text_input(
                    "genre_id（例: PY / SCR など）"
                )
                add_genre_name = st.text_input(
                    "genre_name（例: Python / Scratch）"
                )
                add_course_name = st.text_input("course_name")
                add_course_order = st.number_input(
                    "course_order（表示順）",
                    min_value=0,
                    value=0,
                    step=1,
                )
                add_is_active = st.checkbox(
                    "is_active（ON=表示）",
                    value=True,
                )

                add_course_submitted = st.form_submit_button(
                    "🟢 コースを編集一覧に追加",
                    use_container_width=True,
                )

            if add_course_submitted:
                cid = str(add_course_id).strip()
                if not cid:
                    st.error("course_id が空です。")
                elif cid in set(
                    courses["course_id"].astype(str).str.strip()
                ):
                    st.error(
                        "同じ course_id が既に存在します。"
                    )
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
                    edited = pd.concat(
                        [
                            courses,
                            pd.DataFrame([new_row]),
                        ],
                        ignore_index=True,
                    )
                    st.session_state[course_edit_key] = (
                        _normalize_courses_edit_df(edited)
                    )
                    st.session_state[course_dirty_key] = True
                    st.success(
                        f"編集一覧に追加しました: {cid}"
                    )
                    st.rerun()

        # =====================================================
        # 編集・削除
        # =====================================================
        with colC2:
            st.markdown(
                """
                <div style="
                    background:#fff7ed;
                    border:2px solid #f59e0b;
                    border-left:10px solid #ea580c;
                    border-radius:12px;
                    padding:12px 14px;
                    margin-bottom:12px;
                ">
                    <div style="font-size:18px;font-weight:900;color:#9a3412;">
                        🟠 コースを編集・削除
                    </div>
                    <div style="font-size:12px;color:#9a3412;margin-top:4px;">
                        course_idは固定です。削除は確認付きです。
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if courses.empty:
                st.info("コースがありません。先に追加してください。")
            else:
                courses_sel = courses.copy()
                courses_sel["label"] = (
                    courses_sel["course_id"].astype(str)
                    + " | "
                    + courses_sel["course_name"].astype(str)
                )
                sel = st.selectbox(
                    "編集するコース",
                    courses_sel["label"].tolist(),
                    key="c_edit_sel_batch",
                )
                sel_id = sel.split("|")[0].strip()
                selected_rows = courses[
                    courses["course_id"].astype(str).str.strip()
                    == sel_id
                ]
                selected_index = selected_rows.index[0]
                cur = selected_rows.iloc[0]

                st.markdown(
                    f"**course_id：{sel_id}**（変更不可）"
                )

                with st.form(
                    key=f"course_batch_edit_form_{sel_id}",
                    clear_on_submit=False,
                ):
                    e_genre_id = st.text_input(
                        "genre_id",
                        value=str(cur.get("genre_id", "") or ""),
                    )
                    e_genre_name = st.text_input(
                        "genre_name",
                        value=str(cur.get("genre_name", "") or ""),
                    )
                    e_course_name = st.text_input(
                        "course_name",
                        value=str(cur.get("course_name", "") or ""),
                    )
                    try:
                        default_order = int(
                            float(cur.get("course_order", 0) or 0)
                        )
                    except Exception:
                        default_order = 0

                    e_course_order = st.number_input(
                        "course_order（表示順）",
                        min_value=0,
                        value=default_order,
                        step=1,
                    )
                    e_is_active = st.checkbox(
                        "is_active（ON=表示）",
                        value=normalize_bool_str(
                            cur.get("is_active", True)
                        ),
                    )

                    update_course_submitted = (
                        st.form_submit_button(
                            "🟠 編集内容を一覧へ反映",
                            use_container_width=True,
                        )
                    )

                if update_course_submitted:
                    if not str(e_course_name).strip():
                        st.error("course_name が空です。")
                    else:
                        edited = courses.copy()
                        edited.loc[
                            selected_index,
                            "genre_id",
                        ] = str(e_genre_id).strip()
                        edited.loc[
                            selected_index,
                            "genre_name",
                        ] = str(e_genre_name).strip()
                        edited.loc[
                            selected_index,
                            "course_name",
                        ] = str(e_course_name).strip()
                        edited.loc[
                            selected_index,
                            "course_order",
                        ] = int(e_course_order)
                        edited.loc[
                            selected_index,
                            "is_active",
                        ] = bool(e_is_active)

                        st.session_state[course_edit_key] = (
                            _normalize_courses_edit_df(edited)
                        )
                        st.session_state[course_dirty_key] = True
                        st.success(
                            f"{sel_id} の編集内容を一覧へ反映しました。"
                        )
                        st.rerun()

                st.markdown("#### 🗑 削除")
                delete_also_tasks = st.checkbox(
                    "コース削除時に、このコースの課題も削除する",
                    value=True,
                    key=f"c_del_also_tasks_{sel_id}",
                )
                confirm_del = st.checkbox(
                    "削除を有効にする（確認）",
                    value=False,
                    key=f"c_del_confirm_{sel_id}",
                )

                if st.button(
                    "🗑️ このコースを編集一覧から削除",
                    key=f"c_del_btn_batch_{sel_id}",
                    disabled=not confirm_del,
                ):
                    edited = courses[
                        courses["course_id"]
                        .astype(str)
                        .str.strip()
                        != sel_id
                    ].copy()

                    st.session_state[course_edit_key] = (
                        _normalize_courses_edit_df(edited)
                    )
                    st.session_state[course_dirty_key] = True

                    if delete_also_tasks:
                        pending = list(
                            st.session_state.get(
                                course_pending_task_delete_key,
                                [],
                            )
                        )
                        if sel_id not in pending:
                            pending.append(sel_id)
                        st.session_state[
                            course_pending_task_delete_key
                        ] = pending

                    st.success(
                        f"編集一覧から削除しました: {sel_id}"
                    )
                    st.rerun()

        # =====================================================
        # 一括保存・破棄
        # =====================================================
        st.divider()
        st.markdown("### コース管理の変更を確定")
        pending_task_delete = list(
            st.session_state.get(
                course_pending_task_delete_key,
                [],
            )
        )
        if pending_task_delete:
            st.warning(
                "保存時に課題も削除する予定のコース："
                + "、".join(pending_task_delete)
            )

        save_course_col, discard_course_col = st.columns(
            [2, 1]
        )

        with save_course_col:
            save_courses_batch = st.button(
                "💾 コース管理を保存",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.get(
                    course_dirty_key,
                    False,
                ),
                key="save_courses_batch",
            )

        with discard_course_col:
            discard_courses_batch = st.button(
                "↩ 編集を破棄",
                use_container_width=True,
                disabled=not st.session_state.get(
                    course_dirty_key,
                    False,
                ),
                key="discard_courses_batch",
            )

        if save_courses_batch:
            current_signature = _course_file_signature()
            base_signature = st.session_state.get(
                course_base_signature_key
            )

            if current_signature != base_signature:
                st.error(
                    "編集中にcurriculum_courses.csvが"
                    "別の処理で更新されました。"
                    "安全のため保存していません。"
                    "「編集を破棄」で最新データを読み直してから、"
                    "もう一度変更してください。"
                )
            else:
                edited_courses = _normalize_courses_edit_df(
                    st.session_state[course_edit_key]
                )

                duplicate_ids = edited_courses[
                    edited_courses["course_id"].duplicated(
                        keep=False
                    )
                ]
                if (
                    edited_courses["course_id"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .eq("")
                    .any()
                ):
                    st.error(
                        "course_id が空のコースがあるため保存できません。"
                    )
                elif not duplicate_ids.empty:
                    st.error(
                        "course_id が重複しているため保存できません。"
                    )
                elif (
                    edited_courses["course_name"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .eq("")
                    .any()
                ):
                    st.error(
                        "course_name が空のコースがあるため保存できません。"
                    )
                else:
                    backup_file(CURRICULUM_COURSES_CSV)
                    write_csv(
                        edited_courses,
                        CURRICULUM_COURSES_CSV,
                    )

                    deleted_task_count = 0
                    pending = list(
                        st.session_state.get(
                            course_pending_task_delete_key,
                            [],
                        )
                    )
                    if pending:
                        tasks_now = safe_read_csv(
                            CURRICULUM_TASKS_CSV,
                            [
                                "course_id",
                                "task_id",
                                "task_name",
                                "order",
                                "is_active",
                                "student_id",
                            ],
                            stop_on_missing=False,
                        )
                        if not tasks_now.empty:
                            before_count = len(tasks_now)
                            tasks2 = tasks_now[
                                ~tasks_now["course_id"]
                                .astype(str)
                                .str.strip()
                                .isin(pending)
                            ].copy()
                            deleted_task_count = (
                                before_count - len(tasks2)
                            )
                            if deleted_task_count > 0:
                                backup_file(
                                    CURRICULUM_TASKS_CSV
                                )
                                write_csv(
                                    tasks2,
                                    CURRICULUM_TASKS_CSV,
                                )

                    for key in [
                        course_edit_key,
                        course_dirty_key,
                        course_base_signature_key,
                        course_pending_task_delete_key,
                    ]:
                        st.session_state.pop(key, None)

                    st.session_state.pop(
                        "c_edit_sel_batch",
                        None,
                    )

                    if deleted_task_count > 0:
                        st.success(
                            "コース管理をまとめて保存しました。"
                            f"関連課題{deleted_task_count}件も"
                            "削除しました。"
                        )
                    else:
                        st.success(
                            "コース管理をまとめて保存しました。"
                        )
                    st.rerun()

        if discard_courses_batch:
            for key in [
                course_edit_key,
                course_dirty_key,
                course_base_signature_key,
                course_pending_task_delete_key,
            ]:
                st.session_state.pop(key, None)
            st.session_state.pop(
                "c_edit_sel_batch",
                None,
            )
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

        # d260:
        # task_name が空だと、編集プルダウンや課題一覧で「消えた」ように見える。
        # 保存時は必須チェックし、既存の空欄データは task_id を使って表示できるようにする。
        for _c in ["course_id", "task_id", "task_name", "order", "is_active", "student_id"]:
            if _c not in tasks.columns:
                tasks[_c] = ""
            tasks[_c] = tasks[_c].fillna("").astype(str).str.strip()

        def _task_name_display_value(row):
            _tid = str(row.get("task_id", "")).strip()
            _name = str(row.get("task_name", "")).strip()
            if _name:
                return _name
            return "（課題名未設定）"

        def _short_task_name_for_select(name_value, limit=34):
            _name = str(name_value).strip()
            if len(_name) <= limit:
                return _name
            return _name[:limit] + "…"

        def _task_admin_label(row):
            # d268:
            # iPadでは右側が切れやすいため、task_id を必ず先頭に出す。
            # 課題名は長い場合だけ短くし、編集時にID確認が不要になるようにする。
            _tid = str(row.get("task_id", "")).strip()
            _order = str(row.get("order", "")).strip()
            _name = _short_task_name_for_select(_task_name_display_value(row))
            if _tid:
                return f"{_tid} | order {_order} | {_name}"
            return f"（task_id未設定） | order {_order} | {_name}"

        _blank_task_name_count = int((tasks["task_name"].astype(str).str.strip() == "").sum()) if not tasks.empty else 0
        if _blank_task_name_count:
            st.warning(f"task_name が空の課題が {_blank_task_name_count} 件あります。CSVを整理するか、この画面から課題名を入れてください。")

        # course choices
        course_ids = []
        course_label_by_id = {}

        if not courses.empty:
            _course_label_df = courses.copy()
            for _c in ["course_id", "genre_name", "course_name", "course_order"]:
                if _c not in _course_label_df.columns:
                    _course_label_df[_c] = ""
                _course_label_df[_c] = _course_label_df[_c].fillna("").astype(str).str.strip()

            _course_label_df["_order_num"] = pd.to_numeric(
                _course_label_df["course_order"], errors="coerce"
            ).fillna(9999).astype(int)

            _course_label_df = _course_label_df.sort_values(
                ["_order_num", "genre_name", "course_name", "course_id"],
                na_position="last",
            )

            course_ids = _course_label_df["course_id"].astype(str).str.strip().dropna().unique().tolist()

            for _, _r in _course_label_df.iterrows():
                _cid = str(_r.get("course_id", "")).strip()
                if not _cid:
                    continue
                _genre = str(_r.get("genre_name", "")).strip()
                _cname = str(_r.get("course_name", "")).strip()
                _name_parts = "｜".join([x for x in [_genre, _cname] if x])
                course_label_by_id[_cid] = f"{_cid}（{_name_parts}）" if _name_parts else _cid

        def format_course_admin_label(course_id_value):
            _cid = str(course_id_value).strip()
            if _cid == "（全て）":
                return "（全て）"
            if _cid.startswith("（"):
                return _cid
            return course_label_by_id.get(_cid, _cid)

        task_course = st.session_state.get("t_course_filter", "（全て）")


        tasks_view = tasks.copy()
        if task_course != "（全て）":
            tasks_view = tasks_view[
                tasks_view["course_id"].astype(str).str.strip() == task_course
            ].copy()

        if "order" in tasks_view.columns:
            tasks_view["order_num"] = pd.to_numeric(tasks_view["order"], errors="coerce").fillna(9999).astype(int)
            tasks_view = tasks_view.sort_values(["course_id", "order_num", "task_id"], na_position="last").drop(columns=["order_num"])


        tasks_view_display = tasks_view.copy()
        if not tasks_view_display.empty:
            tasks_view_display["task_name_display"] = tasks_view_display.apply(_task_name_display_value, axis=1)
            _display_cols = [c for c in ["course_id", "task_id", "task_name_display", "task_name", "order", "is_active", "student_id"] if c in tasks_view_display.columns]
            st.dataframe(tasks_view_display[_display_cols], use_container_width=True, hide_index=True)
        else:
            st.dataframe(tasks_view, use_container_width=True, hide_index=True)


        st.selectbox(
            "編集 / 削除用：コースで絞り込み（追加には反映しません）",
            ["（全て）"] + course_ids,
            key="t_course_filter",
            format_func=format_course_admin_label,
            help="下の『編集 / 削除』で表示する課題を絞り込みます。課題追加の登録先は、左側の『追加先コース』で選びます。",
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

        # d263:
        # 挿入時は、course_id だけで sc_h-T059 のように作るのではなく、
        # 挿入基準にした課題IDの形式へ寄せる。
        # 例：scratch_56 の後に入れるなら、既存の scratch_ 系最大番号+1 → scratch_59。
        def suggest_insert_task_id(course_id: str, after_task_id: str) -> str:
            c = str(course_id).strip()
            base_tid = str(after_task_id).strip()

            if not c:
                return ""

            # d264:
            # task_id は全体で重複禁止なので、同じコース内だけでなく
            # curriculum_tasks.csv 全体の task_id を見て、重複しない番号を提案する。
            # 例：同じコースでは scratch_58 まででも、別行に scratch_59 が残っていれば scratch_60 を提案する。
            all_existing_ids = (
                tasks.get("task_id", pd.Series(dtype=str))
                .fillna("")
                .astype(str)
                .str.strip()
                .tolist()
            )
            all_existing_set = {x for x in all_existing_ids if x}

            # 末尾数字の手前までを prefix として見る。
            # scratch_56 -> scratch_ / sc_h-T022 -> sc_h-T
            m_base = re.match(r"^(.*?)(\d+)$", base_tid)
            if m_base:
                prefix = m_base.group(1)
                width = len(m_base.group(2))
                nmax = 0

                for tid in all_existing_ids:
                    m = re.match(rf"^{re.escape(prefix)}(\d+)$", str(tid).strip())
                    if m:
                        nmax = max(nmax, int(m.group(1)))

                if nmax > 0:
                    candidate_num = nmax + 1
                    candidate = f"{prefix}{candidate_num:0{width}d}"
                    while candidate in all_existing_set:
                        candidate_num += 1
                        candidate = f"{prefix}{candidate_num:0{width}d}"
                    return candidate

            # 基準課題の形式が読めない場合は従来案に戻す。
            # ただし従来案も重複する場合は番号を上げる。
            candidate = suggest_next_task_id(c)
            if not candidate:
                return ""

            m_fallback = re.match(r"^(.*?)(\d+)$", candidate)
            if not m_fallback:
                return candidate

            prefix = m_fallback.group(1)
            width = len(m_fallback.group(2))
            candidate_num = int(m_fallback.group(2))
            while candidate in all_existing_set:
                candidate_num += 1
                candidate = f"{prefix}{candidate_num:0{width}d}"
            return candidate

        with colT1:
            st.markdown("#### ➕ 課題追加")
            t_course_id = st.selectbox(
                "追加先コース（course_id｜コース名）",
                course_ids if course_ids else ["（先にコースを追加）"],
                key="t_add_course_id",
                format_func=format_course_admin_label,
                help="新規追加・挿入する課題の登録先です。上の『編集 / 削除用』絞り込みとは別です。",
            )
            if course_ids and str(t_course_id).strip():
                st.caption(f"追加先：{format_course_admin_label(t_course_id)}")
            t_task_id = st.text_input("task_id（空なら自動提案）", value="", key="t_add_task_id")

            t_task_name = st.text_input("task_name", key="t_add_task_name")

            # d261:
            # 課題を最後に追加するだけでなく、指定した課題の直後へ挿入できるようにする。
            # 挿入時は、同じコース内で挿入位置以降の order を自動で +1 する。
            t_add_mode = st.radio(
                "追加方法",
                ["最初に追加", "最後に追加", "選択した課題の次に挿入"],
                horizontal=False,
                key="t_add_mode",
            )

            insert_after_tid = ""
            insert_after_order = None

            if t_add_mode == "最初に追加":
                # 同じコース内の既存課題を後ろへ1つずつずらし、
                # 新しい課題を order 1 として先頭へ追加する。
                t_order = 1
                st.caption(
                    "保存時：新しい課題は order 1 に入り、"
                    "既存の課題は自動で +1 されます。"
                )

            elif t_add_mode == "選択した課題の次に挿入":
                insert_df = tasks[
                    tasks["course_id"].astype(str).str.strip() == str(t_course_id).strip()
                ].copy()

                if insert_df.empty:
                    st.info("このコースにはまだ課題がないため、挿入ではなく最後に追加してください。")
                else:
                    for _c in ["task_id", "task_name", "order"]:
                        if _c not in insert_df.columns:
                            insert_df[_c] = ""
                        insert_df[_c] = insert_df[_c].fillna("").astype(str).str.strip()

                    insert_df["_order_num"] = pd.to_numeric(insert_df["order"], errors="coerce").fillna(9999).astype(int)
                    insert_df = insert_df.sort_values(["_order_num", "task_id"], na_position="last").copy()

                    def _insert_after_label(_row):
                        _tid = str(_row.get("task_id", "")).strip()
                        _name = str(_row.get("task_name", "")).strip() or "（課題名未設定）"
                        _name = _short_task_name_for_select(_name)
                        _order = str(_row.get("order", "")).strip()
                        return f"{_tid}｜order {_order}｜{_name}"

                    insert_labels = insert_df.apply(_insert_after_label, axis=1).tolist()
                    insert_label = st.selectbox(
                        "この課題の後に挿入（task_id先頭）",
                        insert_labels,
                        key="t_add_insert_after",
                        help="選択した課題の直後に新しい課題を挿入し、後ろのorderを自動で+1します。",
                    )

                    insert_parts = str(insert_label).split("｜")
                    insert_after_tid = str(insert_parts[0]).strip() if len(insert_parts) >= 1 else ""
                    _hit = insert_df[insert_df["task_id"].astype(str).str.strip() == insert_after_tid].copy()
                    if not _hit.empty:
                        insert_after_order = int(_hit.iloc[0]["_order_num"])
                        st.caption(f"保存時：新しい課題は order {insert_after_order + 1} に入り、後ろの課題は自動で +1 されます。")

                t_order = 0
            else:
                # d297:
                # 「最後に追加」を選んだ時は、order入力値に頼らず、
                # 同じコース内の最大order+1を自動採番する。
                # 以前は初期値0のまま保存され、先頭に並ぶことがあった。
                _same_course_for_last = tasks[
                    tasks["course_id"].astype(str).str.strip() == str(t_course_id).strip()
                ].copy()

                if _same_course_for_last.empty:
                    t_order = 1
                else:
                    _last_order_num = pd.to_numeric(
                        _same_course_for_last.get("order", pd.Series(dtype=str)),
                        errors="coerce",
                    ).dropna()
                    if _last_order_num.empty:
                        t_order = 1
                    else:
                        t_order = int(_last_order_num.max()) + 1

                st.caption(f"保存時：新しい課題は order {t_order} で最後に追加されます。")

            if course_ids and t_course_id and not t_task_id.strip():
                if t_add_mode == "選択した課題の次に挿入" and insert_after_tid:
                    st.caption(f"提案 task_id: {suggest_insert_task_id(t_course_id, insert_after_tid)}")
                else:
                    st.caption(f"提案 task_id: {suggest_next_task_id(t_course_id)}")

            t_is_active = st.checkbox("is_active（ON=表示）", value=True, key="t_add_is_active")
            t_student_id = st.text_input("student_id（空=共通 / 入れる=個別課題）", value="", key="t_add_student_id")

            if st.button("課題を追加して保存", key="t_add_save"):
                cid = str(t_course_id).strip()
                if not cid or cid.startswith("（"):
                    st.error("course_id を選んでください。")
                else:
                    if str(t_task_id).strip():
                        tid = str(t_task_id).strip()
                    elif t_add_mode == "選択した課題の次に挿入" and insert_after_tid:
                        tid = suggest_insert_task_id(cid, insert_after_tid)
                    else:
                        tid = suggest_next_task_id(cid)
                    if not tid:
                        st.error("task_id が作れませんでした。")
                    elif tid in set(tasks["task_id"].astype(str).str.strip()):
                        st.error("同じ task_id が既に存在します。")
                    elif not str(t_task_name).strip():
                        st.error("課題名（task_name）を入力してください。空欄では保存できません。")
                    elif t_add_mode == "選択した課題の次に挿入" and (not insert_after_tid or insert_after_order is None):
                        st.error("挿入先の課題を選択してください。")
                    else:
                        tasks2 = tasks.copy()
                        for _c in ["course_id", "task_id", "task_name", "order", "is_active", "student_id"]:
                            if _c not in tasks2.columns:
                                tasks2[_c] = ""
                            tasks2[_c] = tasks2[_c].fillna("").astype(str).str.strip()

                        if t_add_mode == "最初に追加":
                            new_order = 1

                            # 同じコース内の既存課題をすべて1つ後ろへずらす。
                            _same_course = (
                                tasks2["course_id"]
                                .astype(str)
                                .str.strip()
                                == cid
                            )
                            _order_num = pd.to_numeric(
                                tasks2["order"],
                                errors="coerce",
                            )
                            _valid_order = _same_course & _order_num.notna()
                            tasks2.loc[
                                _valid_order,
                                "order",
                            ] = (
                                _order_num.loc[_valid_order]
                                .astype(int)
                                .add(1)
                                .astype(str)
                            )

                        elif t_add_mode == "選択した課題の次に挿入":
                            new_order = int(insert_after_order) + 1

                            # 同じコース内で、挿入位置以降のorderを+1する。
                            _same_course = tasks2["course_id"].astype(str).str.strip() == cid
                            _order_num = pd.to_numeric(tasks2["order"], errors="coerce")
                            _shift_mask = _same_course & (_order_num >= new_order)

                            tasks2.loc[_shift_mask, "order"] = (
                                _order_num.loc[_shift_mask].fillna(new_order).astype(int) + 1
                            ).astype(str)
                        else:
                            # d297:
                            # 「最後に追加」は、画面上で算出した最大order+1を使う。
                            new_order = int(t_order)

                        new_row = {
                            "course_id": cid,
                            "task_id": tid,
                            "task_name": str(t_task_name).strip(),
                            "order": int(new_order),
                            "is_active": bool(t_is_active),
                            "student_id": str(t_student_id).strip(),
                        }
                        tasks2 = pd.concat([tasks2, pd.DataFrame([new_row])], ignore_index=True)

                        # 保存前に、表示順が見やすくなるよう同じCSV内を整列しておく。
                        tasks2["_order_num"] = pd.to_numeric(tasks2["order"], errors="coerce").fillna(9999).astype(int)
                        tasks2 = tasks2.sort_values(["course_id", "_order_num", "task_id"], na_position="last").drop(columns=["_order_num"])
                        tasks2 = tasks2[["course_id", "task_id", "task_name", "order", "is_active", "student_id"]].fillna("")

                        backup_file(CURRICULUM_TASKS_CSV)
                        write_csv(tasks2, CURRICULUM_TASKS_CSV)
                        if t_add_mode == "選択した課題の次に挿入":
                            st.success(f"挿入しました: {tid}（{insert_after_tid} の次）")
                        else:
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
                    pick_df2["label"] = pick_df2.apply(_task_admin_label, axis=1)
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
                        st.session_state["t_edit_enable_course_change"] = False

                        st.rerun()

                    cur_course = str(cur_t.get("course_id","")).strip()

                    # d268:
                    # 所属コースは通常「確認用」にする。
                    # うっかり別コースへ変更する事故を防ぐため、変更したい時だけチェックをONにする。
                    st.caption(f"所属コース（確認用）：{format_course_admin_label(cur_course)}")
                    enable_course_change = st.checkbox(
                        "所属コースを変更する（通常OFF）",
                        value=bool(st.session_state.get("t_edit_enable_course_change", False)),
                        key="t_edit_enable_course_change",
                        help="コースを間違えて登録した課題を移動したい時だけONにします。",
                    )

                    if enable_course_change:
                        edit_course_options = course_ids if course_ids else [cur_course]
                        if "t_edit_course_id" in st.session_state and st.session_state["t_edit_course_id"] in edit_course_options:
                            course_index = edit_course_options.index(st.session_state["t_edit_course_id"])
                        else:
                            course_index = edit_course_options.index(cur_course) if cur_course in edit_course_options else 0

                        e_course_id = st.selectbox(
                            "変更先コース（course_id｜コース名）",
                            edit_course_options,
                            index=course_index,
                            key="t_edit_course_id",
                            format_func=format_course_admin_label,
                            help="課題の所属コースを本当に変更する場合だけ選んでください。",
                        )
                        if str(e_course_id).strip():
                            st.caption(f"変更先：{format_course_admin_label(e_course_id)}")
                    else:
                        e_course_id = cur_course

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
                            if not str(e_task_name).strip():
                                st.error("課題名（task_name）を入力してください。空欄では保存できません。")
                            else:
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
    # 🗓️ 月スケジュール（monthly_schedule.csv）
    # ---------------------------
    if admin_section == "🗓️ 月スケジュール":
        st.subheader("🗓️ 月スケジュール")
        st.caption("保存済みの月スケジュールをカレンダー中心に確認・変更し、必要な時は固定スケジュールから生成できます。")

        today_for_month = dt.date.today()
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            target_year = st.number_input(
                "年",
                min_value=2020,
                max_value=2100,
                value=int(today_for_month.year),
                step=1,
                key="monthly_schedule_year",
            )
        with col_m2:
            target_month = st.number_input(
                "月",
                min_value=1,
                max_value=12,
                value=int(today_for_month.month),
                step=1,
                key="monthly_schedule_month",
            )

        target_year = int(target_year)
        target_month = int(target_month)
        month_start = dt.date(target_year, target_month, 1)
        if target_month == 12:
            month_end = dt.date(target_year + 1, 1, 1) - dt.timedelta(days=1)
        else:
            month_end = dt.date(target_year, target_month + 1, 1) - dt.timedelta(days=1)

        # d321: 月スケジュールも「編集して最後に一括保存」方式にする。
        monthly_edit_key = "monthly_schedule_edit_df"
        monthly_dirty_key = "monthly_schedule_edit_dirty"
        monthly_base_signature_key = "monthly_schedule_edit_base_signature"
        monthly_pending_override_cleanup_key = "monthly_schedule_pending_override_cleanup"

        def _monthly_schedule_file_signature():
            try:
                p = Path(MONTHLY_SCHEDULE_CSV)
                stat = p.stat()
                return (int(stat.st_mtime_ns), int(stat.st_size))
            except Exception:
                return None

        def _normalize_monthly_edit_df(df):
            out = df.copy() if df is not None else pd.DataFrame()
            for col in MONTHLY_SCHEDULE_COLS:
                if col not in out.columns:
                    out[col] = ""
            return out[MONTHLY_SCHEDULE_COLS].fillna("").reset_index(drop=True)

        if monthly_edit_key not in st.session_state:
            st.session_state[monthly_edit_key] = _normalize_monthly_edit_df(
                monthly_schedule
            )
            st.session_state[monthly_dirty_key] = False
            st.session_state[monthly_base_signature_key] = (
                _monthly_schedule_file_signature()
            )
            st.session_state[monthly_pending_override_cleanup_key] = []

        # この画面内の表示・追加・修正・削除は、すべて編集用データを使う。
        monthly_schedule = _normalize_monthly_edit_df(
            st.session_state[monthly_edit_key]
        )

        if st.session_state.get(monthly_dirty_key, False):
            st.warning("🟡 保存していない月スケジュールの変更があります。")
        else:
            st.success("🟢 月スケジュールは保存済みです。")

        monthly_view_mode = st.radio(
            "表示する機能",
            ["📅 編集", "📊 回数確認", "⚙ 生成"],
            horizontal=True,
            key=f"monthly_view_mode_{target_year}_{target_month}",
            help="必要な機能だけを描画して、月スケジュール画面を軽くします。",
        )

        if monthly_view_mode == "📅 編集":
            st.info("カレンダーから予定を選び、追加・修正・削除を行います。")
        elif monthly_view_mode == "📊 回数確認":
            st.info("生徒ごとの月回数だけを確認します。")
        else:
            st.info("固定スケジュールから月予定を生成・確認します。")

        # 在籍中の生徒だけ対象にする
        active_student_ids_for_month = set()
        student_name_map_month = {}
        student_target_count_map = {}

        if not students.empty and "student_id" in students.columns:
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

            active_student_ids_for_month = set(
                students_for_month["student_id"].astype(str).str.strip()
            )

            if "display_name" in students_for_month.columns:
                student_name_map_month = dict(
                    zip(
                        students_for_month["student_id"].astype(str).str.strip(),
                        students_for_month["display_name"].astype(str).str.strip(),
                    )
                )

            if "number_of_times" in students_for_month.columns:
                student_target_count_map = dict(
                    zip(
                        students_for_month["student_id"].astype(str).str.strip(),
                        students_for_month["number_of_times"].astype(str).str.strip(),
                    )
                )

        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        generated_rows = []

        if monthly_view_mode == "⚙ 生成" and not student_schedule.empty:
            sched_for_month = student_schedule.copy()

            for c in [
                "student_id",
                "weekday",
                "slot",
                "session_type",
                "week_pattern",
            ]:
                if c not in sched_for_month.columns:
                    sched_for_month[c] = ""
                sched_for_month[c] = (
                    sched_for_month[c]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
            sched_for_month["week_pattern"] = (
                sched_for_month["week_pattern"]
                .map(normalize_week_pattern)
            )

            current_day = month_start
            while current_day <= month_end:
                wd = weekday_names[current_day.weekday()]
                day_sched = sched_for_month[
                    sched_for_month["weekday"].astype(str).str.strip() == wd
                ].copy()

                for _, r in day_sched.iterrows():
                    sid = str(r.get("student_id", "")).strip()
                    slot = normalize_slot(r.get("slot", ""))
                    session_type = str(r.get("session_type", "")).strip() or "授業"
                    week_pattern = normalize_week_pattern(
                        r.get("week_pattern", "")
                    )

                    if not sid or not slot:
                        continue
                    if not matches_week_pattern(
                        current_day,
                        week_pattern,
                    ):
                        continue
                    if active_student_ids_for_month and sid not in active_student_ids_for_month:
                        continue

                    generated_rows.append({
                        "date": current_day.isoformat(),
                        "student_id": sid,
                        "slot": slot,
                        "session_type": session_type,
                        "reason": "通常",
                        "note": "",
                        "source": f"固定スケジュールから生成（{week_pattern}）",
                    })

                current_day += dt.timedelta(days=1)

        generated_df = pd.DataFrame(generated_rows, columns=MONTHLY_SCHEDULE_COLS)

        # 月スケジュール編集・カレンダー共通の候補
        monthly_student_options = sorted(list(active_student_ids_for_month))
        monthly_student_label_map = student_name_map_month.copy()

        monthly_slot_options = ["1", "2", "3", "4", "5", "6", "7"]
        monthly_slot_label_map = build_slot_label_map(timeslots)

        # d279:
        # 「回数区分」は実際には回数チェックに使うデータなので、
        # 画面上では「回数区分（集計に使います）」として扱う。
        # 選択肢の時点で「回数に含める / 回数外」が分かるようにし、
        # 登録する人のさじ加減でカウント扱いがブレないようにする。
        monthly_count_included_reasons = {"通常", "今月振替", "追加授業", "確認必要"}
        monthly_count_excluded_reasons = {
            "前月振替", "自習", "補習・確認", "特典追加", "その他回数外",
            "回数外", "月回数外"
        }

        monthly_reason_base_options = [
            "通常",
            "今月振替",
            "追加授業",
            "前月振替",
            "自習",
            "補習・確認",
            "特典追加",
            "その他回数外",
            "確認必要",
        ]
        monthly_reason_legacy_options = ["休み調整", "特別追加", "回数外", "月回数外"]

        monthly_reason_existing_values = []
        try:
            if monthly_schedule is not None and not monthly_schedule.empty and "reason" in monthly_schedule.columns:
                monthly_reason_existing_values = [
                    str(x).strip()
                    for x in monthly_schedule["reason"].fillna("").astype(str).tolist()
                    if str(x).strip()
                ]
        except Exception:
            monthly_reason_existing_values = []

        monthly_reason_options = monthly_reason_base_options[:]
        for _r in monthly_reason_existing_values:
            # 既存データに旧区分・未知の値がある場合でも、編集画面で選べるように残す
            if _r and _r not in monthly_reason_options:
                monthly_reason_options.append(_r)

        def format_monthly_reason_label(reason):
            r = str(reason).strip() or "通常"
            if r == "通常":
                return "↑ 通常授業（回数に含める）"
            if r == "今月振替":
                return "↑ 今月振替（回数に含める）"
            if r == "追加授業":
                return "↑ 追加授業（回数に含める）"
            if r == "確認必要":
                return "↑ 確認必要（仮でカウント・要確認）"
            if r == "前月振替":
                return "− 前月振替（回数外）"
            if r == "自習":
                return "− 自習（回数外）"
            if r == "補習・確認":
                return "− 補習・確認（回数外）"
            if r == "特典追加":
                return "− 特典追加（回数外）"
            if r == "その他回数外":
                return "− その他回数外（回数外）"
            if r in {"回数外", "月回数外"}:
                return f"− {r}（旧区分・できれば自習/補習・確認/特典追加/その他回数外へ整理）"
            if r == "特別追加":
                return "↑ 特別追加（旧区分・できれば追加授業へ整理）"
            if r in monthly_count_excluded_reasons:
                return f"− {r}（回数外）"
            if r in monthly_reason_legacy_options:
                return f"↑ {r}（旧区分・できれば新しい回数区分へ整理）"
            return f"↑ {r}（回数に含める）"

        def monthly_reason_summary_label(reason):
            r = str(reason).strip() or "通常"
            if r in monthly_count_excluded_reasons:
                return f"−{r}"
            if r == "確認必要":
                return f"↑{r}"
            if r in monthly_reason_legacy_options:
                return f"↑{r}(旧)"
            return f"↑{r}"

        def _monthly_row_label(idx, row):
            sid = str(row.get("student_id", "")).strip()
            name = monthly_student_label_map.get(sid, sid)
            slot = normalize_slot(row.get("slot", ""))
            session_type = str(row.get("session_type", "")).strip() or "授業"
            reason = str(row.get("reason", "")).strip() or "通常"
            reason_part = f"｜{reason}" if reason and reason != "通常" else ""
            date_label = str(row.get("date", "")).strip()
            # iPadの幅が狭いと後ろが切れるため、生徒名を先頭にする
            return f"{name}｜{slot}コマ｜{session_type}{reason_part}｜{date_label}"

        # d330: 月カレンダーの予定をタップした時に開く試用ポップアップ
        if hasattr(st, "dialog"):
            @st.dialog("予定を編集・取消・削除")
            def _open_monthly_edit_dialog():
                selected_idx = st.session_state.get(
                    f"monthly_sidebar_update_target_{target_year}_{target_month}",
                    None,
                )

                if (
                    selected_idx is None
                    or monthly_schedule.empty
                    or selected_idx not in monthly_schedule.index
                ):
                    st.warning("編集できる月予定が選択されていません。")
                    return

                selected_row = monthly_schedule.loc[selected_idx]
                selected_date_s = str(
                    selected_row.get("date", "")
                ).strip()
                selected_slot = normalize_slot(
                    selected_row.get("slot", "")
                )
                selected_sid = str(
                    selected_row.get("student_id", "")
                ).strip()
                selected_name = monthly_student_label_map.get(
                    selected_sid,
                    selected_sid,
                )
                selected_type = str(
                    selected_row.get("session_type", "")
                ).strip() or "授業"
                selected_reason = str(
                    selected_row.get("reason", "")
                ).strip() or "通常"
                selected_note = str(
                    selected_row.get("note", "")
                ).strip()

                try:
                    selected_date_value = pd.to_datetime(
                        selected_date_s
                    ).date()
                except Exception:
                    selected_date_value = month_start

                st.markdown(
                    f"### 🟠 {selected_name}"
                )
                st.caption(
                    f"{selected_date_s}｜"
                    f"{format_slot_label(selected_slot, monthly_slot_label_map)}｜"
                    f"{selected_type}"
                )

                dialog_form_key = (
                    f"monthly_dialog_edit_"
                    f"{target_year}_{target_month}_{selected_idx}"
                )

                with st.form(dialog_form_key):
                    dialog_date = st.date_input(
                        "日付",
                        value=selected_date_value,
                        min_value=month_start,
                        max_value=month_end,
                    )

                    dialog_slot_options = list(monthly_slot_options)
                    if selected_slot not in dialog_slot_options:
                        dialog_slot_options.append(selected_slot)
                    dialog_slot = st.selectbox(
                        "コマ",
                        dialog_slot_options,
                        index=dialog_slot_options.index(selected_slot),
                        format_func=lambda x: format_slot_label(
                            x,
                            monthly_slot_label_map,
                        ),
                    )

                    dialog_type = st.radio(
                        "種別",
                        ["授業", "自習"],
                        index=0 if selected_type == "授業" else 1,
                        horizontal=True,
                    )

                    dialog_reason_options = list(monthly_reason_options)
                    if selected_reason not in dialog_reason_options:
                        dialog_reason_options.append(selected_reason)
                    dialog_reason = st.selectbox(
                        "回数区分",
                        dialog_reason_options,
                        index=dialog_reason_options.index(
                            selected_reason
                        ),
                        format_func=format_monthly_reason_label,
                    )

                    dialog_note = st.text_input(
                        "メモ",
                        value=selected_note,
                    )

                    dialog_update = st.form_submit_button(
                        "🟠 この予定を更新",
                        type="primary",
                        use_container_width=True,
                    )

                if dialog_update:
                    effective_reason = str(dialog_reason).strip()
                    if (
                        str(dialog_type).strip() == "自習"
                        and effective_reason in ["", "通常"]
                    ):
                        effective_reason = "自習"
                    elif (
                        str(dialog_type).strip() == "授業"
                        and effective_reason == "自習"
                    ):
                        effective_reason = "通常"

                    updated_df = monthly_schedule.copy()
                    updated_df.loc[
                        selected_idx,
                        "date",
                    ] = dialog_date.isoformat()
                    updated_df.loc[
                        selected_idx,
                        "slot",
                    ] = normalize_slot(dialog_slot)
                    updated_df.loc[
                        selected_idx,
                        "session_type",
                    ] = str(dialog_type).strip()
                    updated_df.loc[
                        selected_idx,
                        "reason",
                    ] = effective_reason or "通常"
                    updated_df.loc[
                        selected_idx,
                        "note",
                    ] = str(dialog_note).strip()
                    updated_df.loc[
                        selected_idx,
                        "source",
                    ] = "月カレンダーポップアップから修正"

                    st.session_state[monthly_edit_key] = (
                        _normalize_monthly_edit_df(updated_df)
                    )
                    st.session_state[monthly_dirty_key] = True
                    st.rerun()

                st.divider()
                dialog_cancel_col, dialog_delete_col = st.columns(2)

                with dialog_cancel_col:
                    if st.button(
                        "↩ 取消線のみ",
                        key=f"monthly_dialog_cancel_{selected_idx}",
                        use_container_width=True,
                    ):
                        ov2 = upsert_schedule_override_row(
                            schedule_overrides,
                            student_id=selected_sid,
                            d=selected_date_value,
                            slot=selected_slot,
                            action="キャンセル",
                            note="月予定ポップアップ：取消線のみ",
                        )
                        write_csv_atomic(
                            ov2,
                            SCHEDULE_OVERRIDES_CSV,
                        )
                        seat2 = remove_seat_assignment_for_plan(
                            seat_assignments,
                            d=selected_date_value,
                            student_id=selected_sid,
                            slot=selected_slot,
                        )
                        write_csv_atomic(
                            seat2,
                            SEAT_ASSIGNMENTS_CSV,
                        )
                        st.rerun()

                with dialog_delete_col:
                    confirm_dialog_delete = st.checkbox(
                        "削除確認",
                        key=f"monthly_dialog_delete_confirm_{selected_idx}",
                    )
                    if st.button(
                        "🗑 完全削除",
                        key=f"monthly_dialog_delete_{selected_idx}",
                        disabled=not confirm_dialog_delete,
                        use_container_width=True,
                    ):
                        updated_df = monthly_schedule.drop(
                            index=selected_idx,
                            errors="ignore",
                        ).reset_index(drop=True)
                        st.session_state[monthly_edit_key] = (
                            _normalize_monthly_edit_df(updated_df)
                        )
                        st.session_state[monthly_dirty_key] = True

                        pending_cleanup = list(
                            st.session_state.get(
                                monthly_pending_override_cleanup_key,
                                [],
                            )
                        )
                        pending_cleanup.append({
                            "student_id": selected_sid,
                            "date": str(selected_date_value),
                            "slot": selected_slot,
                        })
                        st.session_state[
                            monthly_pending_override_cleanup_key
                        ] = pending_cleanup

                        st.session_state.pop(
                            f"monthly_sidebar_update_target_"
                            f"{target_year}_{target_month}",
                            None,
                        )
                        st.session_state.pop(
                            f"monthly_sidebar_delete_target_"
                            f"{target_year}_{target_month}",
                            None,
                        )
                        st.rerun()
        else:
            def _open_monthly_edit_dialog():
                st.warning(
                    "このStreamlitではポップアップ機能を利用できません。"
                    "従来の左側編集欄を使ってください。"
                )

        if monthly_view_mode == "📅 編集":
            # =====================================================
            # d241: 月スケジュールを左右2カラム化
            # 左：操作パネル / 右：カレンダー・回数チェック
            # =====================================================
            monthly_cal_col = st.container()

            if hasattr(st, "dialog"):
                @st.dialog("新しい予定を追加")
                def _open_monthly_add_dialog():
                    _monthly_add_default_date = (
                        date.today()
                        if (
                            target_year == date.today().year
                            and target_month == date.today().month
                        )
                        else month_start
                    )

                    st.markdown("### 🟢 新しい予定を追加")
                    st.caption(
                        "入力内容は編集用データへ反映されます。"
                        "最後に画面下の保存バーから確定してください。"
                    )

                    with st.form(
                        key=(
                            f"monthly_add_dialog_"
                            f"{target_year}_{target_month}"
                        )
                    ):
                        add_date = st.date_input(
                            "追加する日付",
                            value=_monthly_add_default_date,
                            min_value=month_start,
                            max_value=month_end,
                        )

                        add_slot = st.selectbox(
                            "追加するコマ",
                            monthly_slot_options,
                            format_func=lambda x: format_slot_label(
                                x,
                                monthly_slot_label_map,
                            ),
                        )

                        if monthly_student_options:
                            add_sid = st.selectbox(
                                "追加する生徒",
                                monthly_student_options,
                                format_func=lambda sid: (
                                    monthly_student_label_map.get(
                                        sid,
                                        sid,
                                    )
                                ),
                            )
                        else:
                            add_sid = ""
                            st.info(
                                "追加できる在籍中の生徒がいません。"
                            )

                        add_type = st.radio(
                            "追加する種別",
                            ["授業", "自習"],
                            horizontal=True,
                        )

                        add_reason = st.selectbox(
                            "回数区分",
                            monthly_reason_options,
                            index=(
                                monthly_reason_options.index("通常")
                                if "通常" in monthly_reason_options
                                else 0
                            ),
                            format_func=format_monthly_reason_label,
                        )

                        add_note = st.text_input(
                            "追加メモ",
                            value="",
                            placeholder=(
                                "例：保護者都合、検定前確認、"
                                "入会特典分 など"
                            ),
                        )

                        add_submit = st.form_submit_button(
                            "🟢 新規予定として追加",
                            type="primary",
                            use_container_width=True,
                            disabled=not bool(
                                monthly_student_options
                            ),
                        )

                    if add_submit:
                        if not add_sid:
                            st.error("生徒を選択してください。")
                        else:
                            effective_reason = str(
                                add_reason
                            ).strip()
                            add_type_norm = str(add_type).strip()

                            if (
                                add_type_norm == "自習"
                                and effective_reason in ["", "通常"]
                            ):
                                effective_reason = "自習"
                            elif (
                                add_type_norm == "授業"
                                and effective_reason == "自習"
                            ):
                                effective_reason = "通常"

                            new_row = {
                                "date": add_date.isoformat(),
                                "student_id": str(add_sid).strip(),
                                "slot": normalize_slot(add_slot),
                                "session_type": add_type_norm,
                                "reason": (
                                    effective_reason or "通常"
                                ),
                                "note": str(add_note).strip(),
                                "source": (
                                    "月カレンダー追加ポップアップ"
                                ),
                            }

                            save_df = pd.concat(
                                [
                                    monthly_schedule[
                                        MONTHLY_SCHEDULE_COLS
                                    ].fillna(""),
                                    pd.DataFrame(
                                        [new_row],
                                        columns=MONTHLY_SCHEDULE_COLS,
                                    ),
                                ],
                                ignore_index=True,
                            )

                            st.session_state[monthly_edit_key] = (
                                _normalize_monthly_edit_df(save_df)
                            )
                            st.session_state[
                                monthly_dirty_key
                            ] = True
                            st.rerun()
            else:
                def _open_monthly_add_dialog():
                    st.warning(
                        "このStreamlitではポップアップ機能を"
                        "利用できません。"
                    )

            with monthly_cal_col:
                # =====================================================
                # 🗓️ 月スケジュール カレンダー表示（試験版）
                # =====================================================
                cal_title_col, cal_add_col, cal_today_col = st.columns(
                    [4, 1.4, 1.1]
                )
                with cal_title_col:
                    st.markdown("### 🗓️ 月スケジュール カレンダー")
                with cal_add_col:
                    if st.button(
                        "➕ 新しい予定",
                        type="primary",
                        use_container_width=True,
                        key=(
                            f"monthly_open_add_dialog_"
                            f"{target_year}_{target_month}"
                        ),
                    ):
                        _open_monthly_add_dialog()
                with cal_today_col:
                    today_anchor_name = f"monthly_today_{target_year}_{target_month}"
                    if month_start <= date.today() <= month_end:
                        st.markdown(
                            f'<a href="#{today_anchor_name}" style="display:block;text-align:center;'
                            f'padding:0.45rem 0.4rem;border:1px solid #f59e0b;border-radius:8px;'
                            f'background:#fff7ed;color:#92400e;font-weight:800;text-decoration:none;">今日へ移動</a>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption("今月に今日なし")

                st.caption("予定の確認・取消・解除・削除は、基本的にこのカレンダーから行います。")
                st.info("操作の意味：取消＝キャンセル記録を残します（取消線がつき、解除で戻せます） / 削除＝登録ミス・月回数調整用に予定を完全削除します（解除では戻せません） / 解除＝取消線を戻して予定を復活させます。")
                st.caption("回数区分は、通常・今月振替・前月振替・回数外・確認必要を基本にします。細かい事情はメモで補足します。")

                # =====================================================
                # 月カレンダー表示用データ
                # -----------------------------------------------------
                # d203方針：
                #   カレンダーだけが schedule_overrides.csv を別解釈してしまうと、
                #   「カレンダーではキャンセルしたのに今日の予定に残る」などのズレが起きる。
                #   そのため、今日の予定・未完了・座席と同じ build_daily_plan_for_date() で
                #   カレンダー用の予定も作る。
                #
                # 注意：月スケジュール画面では、保存済み monthly_schedule.csv を確認したいので、
                #   固定週次 student_schedule.csv へのフォールバックは使わない。
                #   ただし schedule_overrides.csv の追加・時間変更・キャンセルは重ねる。
                # =====================================================
                _empty_weekly_for_calendar = pd.DataFrame(columns=list(student_schedule.columns) if student_schedule is not None else ["student_id", "weekday", "slot", "session_type"])

                # monthly_schedule の元indexを、カレンダー上の編集ボタンへ戻すために保持する
                _monthly_index_map = {}
                if not monthly_schedule.empty:
                    _ms_idx = monthly_schedule.copy()
                    for _c in MONTHLY_SCHEDULE_COLS:
                        if _c not in _ms_idx.columns:
                            _ms_idx[_c] = ""
                    _ms_idx = _ms_idx[MONTHLY_SCHEDULE_COLS].fillna("")
                    _ms_idx["date"] = pd.to_datetime(_ms_idx["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(_ms_idx["date"].astype(str))
                    _ms_idx["slot"] = _ms_idx["slot"].astype(str).map(normalize_slot)
                    for _idx, _r in _ms_idx.iterrows():
                        _key = (
                            str(_r.get("date", "")).strip(),
                            str(_r.get("student_id", "")).strip(),
                            normalize_slot(_r.get("slot", "")),
                        )
                        if _key not in _monthly_index_map:
                            _monthly_index_map[_key] = _idx

                _calendar_rows = []
                for _day_ts in pd.date_range(month_start, month_end, freq="D"):
                    _day = _day_ts.date()
                    _plan = build_daily_plan_for_date(
                        _day,
                        students,
                        _empty_weekly_for_calendar,
                        monthly_schedule,
                        schedule_overrides,
                        timeslots,
                        include_inactive=False,
                    )
                    if _plan is None or _plan.empty:
                        continue

                    _plan = _plan.copy()
                    _plan["date_dt"] = pd.to_datetime(_day.isoformat(), errors="coerce")
                    for _c in ["reason", "source", "note", "override_status", "override_note"]:
                        if _c not in _plan.columns:
                            _plan[_c] = ""
                        _plan[_c] = _plan[_c].fillna("").astype(str).str.strip()

                    # build_daily_plan_for_date() 側で、既存予定のある生徒への「追加」は
                    # 時間変更扱いに正規化される。カレンダーも同じ解釈にする。
                    _reason_s = _plan["reason"].fillna("").astype(str).str.strip()
                    _source_s = _plan["source"].fillna("").astype(str).str.strip()
                    _override_like = _source_s.str.contains("schedule_overrides|当日例外", regex=True, na=False)
                    _plan.loc[_override_like & _reason_s.str.contains("追加|当日追加", regex=True, na=False), "override_status"] = "追加"
                    _plan.loc[_override_like & _reason_s.str.contains("変更|時間変更", regex=True, na=False), "override_status"] = "変更"
                    _plan.loc[_plan["override_status"] != "", "override_note"] = _plan.loc[_plan["override_status"] != "", "note"]

                    # 月スケジュール本体の行へ戻れる場合だけ、元indexを付ける
                    def _lookup_monthly_index(_r):
                        _key = (
                            str(_r.get("date", "")).strip(),
                            str(_r.get("student_id", "")).strip(),
                            normalize_slot(_r.get("slot", "")),
                        )
                        return _monthly_index_map.get(_key, "")

                    _plan["__monthly_index"] = _plan.apply(_lookup_monthly_index, axis=1)
                    _calendar_rows.append(_plan)

                if _calendar_rows:
                    calendar_month = pd.concat(_calendar_rows, ignore_index=True)
                else:
                    calendar_month = pd.DataFrame(columns=MONTHLY_SCHEDULE_COLS + ["date_dt", "override_status", "override_note", "__monthly_index"])

                # キャンセル済み予定は、今日の予定からは消える。
                # ただし月カレンダーでは「消えた理由」を見たいので、グレー行として1件だけ表示する。
                override_month = schedule_overrides.copy()
                if not override_month.empty:
                    for c in ["student_id", "date", "slot", "action", "session_type", "note"]:
                        if c not in override_month.columns:
                            override_month[c] = ""
                        override_month[c] = override_month[c].fillna("").astype(str).str.strip()

                    override_month["date_dt"] = pd.to_datetime(override_month["date"], errors="coerce")
                    override_month = override_month[
                        (override_month["date_dt"].dt.year == target_year)
                        & (override_month["date_dt"].dt.month == target_month)
                    ].copy()
                    override_month["slot"] = override_month["slot"].astype(str).map(normalize_slot)
                    override_month["action_norm"] = override_month["action"].map(normalize_action_value)

                    cancel_month = override_month[override_month["action_norm"] == "キャンセル"].copy()
                    if not cancel_month.empty:
                        cancel_rows = []
                        for _, _canc in cancel_month.iterrows():
                            _cdate = str(_canc.get("date", "")).strip()
                            _csid = str(_canc.get("student_id", "")).strip()
                            _cslot = normalize_slot(_canc.get("slot", ""))
                            if not _cdate or not _csid or not _cslot:
                                continue

                            # 既にグレー行がある場合は重複させない
                            _already_cancel = False
                            if not calendar_month.empty:
                                _already_cancel = bool((
                                    (calendar_month.get("date", pd.Series([], dtype=str)).astype(str).str.strip() == _cdate)
                                    & (calendar_month.get("student_id", pd.Series([], dtype=str)).astype(str).str.strip() == _csid)
                                    & (calendar_month.get("slot", pd.Series([], dtype=str)).astype(str).map(normalize_slot) == _cslot)
                                    & (calendar_month.get("override_status", pd.Series([], dtype=str)).astype(str).str.strip() == "キャンセル")
                                ).any())
                            if _already_cancel:
                                continue

                            _base = build_daily_plan_for_date(
                                _cdate,
                                students,
                                _empty_weekly_for_calendar,
                                monthly_schedule,
                                pd.DataFrame(columns=["student_id", "date", "slot", "action", "start", "end", "session_type", "note"]),
                                timeslots,
                                include_inactive=False,
                            )
                            _base_match = pd.DataFrame()
                            if _base is not None and not _base.empty:
                                _base_match = _base[
                                    (_base["student_id"].astype(str).str.strip() == _csid)
                                    & (_base["slot"].astype(str).map(normalize_slot) == _cslot)
                                ].copy()

                            if not _base_match.empty:
                                _row = _base_match.iloc[0].to_dict()
                            else:
                                # d231:
                                # 月スケジュール本体が削除済みの予定に、過去のキャンセル例外だけが
                                # 残っている場合は、カレンダーに取消線として表示しない。
                                # 「削除」は登録ミスや月2回調整のための完全削除、
                                # 「取消」は予定の履歴を残すキャンセル、という役割を分ける。
                                continue
                            _row["date"] = _cdate
                            _row["date_dt"] = pd.to_datetime(_cdate, errors="coerce")
                            _row["student_id"] = _csid
                            _row["slot"] = _cslot
                            _row["override_status"] = "キャンセル"
                            _row["override_note"] = str(_canc.get("note", "")).strip()
                            _row["__monthly_index"] = _monthly_index_map.get((_cdate, _csid, _cslot), "")
                            cancel_rows.append(_row)

                        if cancel_rows:
                            calendar_month = pd.concat([calendar_month, pd.DataFrame(cancel_rows)], ignore_index=True)

                if not calendar_month.empty:
                    for _c in ["date", "student_id", "slot", "session_type", "reason", "note", "source", "override_status", "override_note", "__monthly_index"]:
                        if _c not in calendar_month.columns:
                            calendar_month[_c] = ""
                        calendar_month[_c] = calendar_month[_c].fillna("").astype(str).str.strip()
                    calendar_month["slot"] = calendar_month["slot"].map(normalize_slot)
                    calendar_month["date_dt"] = pd.to_datetime(calendar_month["date"], errors="coerce")

                # =====================================================
                # d227:
                # 古い「保存済み月スケジュールの回数チェック」は、
                # 下の「予定回数チェック（出欠実績は含みません）」と役割が重複していたため非表示化。
                # 今後は、下の1つだけを見ればよい。
                # =====================================================

                # d206: 出席済みの予定は、月カレンダー上で誤操作しにくいように軽くロックする。
                # 完全ロックではなく、各所の「修正モード」で解除できる。
                monthly_attended_keys = build_attended_student_date_keys(load_attendance_log())

                # =====================================================
                # d276: 予定回数チェック（出欠実績は含みません）を、カレンダーより上へ移動。
                # 📊 月スケジュール 回数チェック（保存済み予定ベース）
                # =====================================================
                with st.expander("📊 予定回数チェック（出欠実績は含みません）", expanded=False):
                    st.caption("保存済みの月スケジュールに当日例外（追加・取消・変更）を重ねて、予定上の授業回数だけを月回数と比較します。出欠登録の実績回数はここには含みません。自習・前月振替・回数外は月回数に含めません。今月振替・2コマ連続の通常授業は月回数に含めます。")
                    st.info("このチェックは予定表ベースです。実際に出席・欠席した回数は attendance_log.csv ではなく、ここでは集計していません。過去月の実績確認は今後別枠で追加予定です。")

                    # d203: 回数チェックもカレンダーと同じ有効予定を使う。
                    # これにより、古い「追加」例外が通常予定と二重カウントされる事故を防ぐ。
                    check_month = calendar_month.copy()
                    if not check_month.empty:
                        if "override_status" not in check_month.columns:
                            check_month["override_status"] = ""
                        check_month = check_month[
                            check_month["override_status"].fillna("").astype(str).str.strip() != "キャンセル"
                        ].copy()

                    if check_month.empty:
                        st.info("この年月の保存済み月スケジュールがないため、回数チェックはまだできません。")
                    else:
                        # 授業だけを数える。ただし、意図的に「今月の契約回数とは別」と分かる区分は外す。
                        # d227:
                        # 2コマ連続の通常授業は「特別追加」とメモされていても月回数に含める。
                        # 回数外にしたい場合は、今後はメモや区分に「回数外」または「月回数外」と入れて区別する。
                        count_excluded_reasons = {"前月振替", "自習", "補習・確認", "特典追加", "その他回数外", "回数外", "月回数外"}
                        _reason_for_count = check_month["reason"].fillna("通常").astype(str).str.strip()
                        _note_for_count = check_month["note"].fillna("").astype(str).str.strip() if "note" in check_month.columns else pd.Series([""] * len(check_month), index=check_month.index)
                        _is_count_excluded = (
                            _reason_for_count.isin(count_excluded_reasons)
                            | _note_for_count.str.contains("回数外|月回数外", regex=True, na=False)
                        )
                        lesson_month = check_month[
                            (check_month["session_type"].astype(str).str.strip() == "授業")
                            & (~_is_count_excluded)
                        ].copy()

                        lesson_count_map = (
                            lesson_month["student_id"].astype(str).str.strip().value_counts().to_dict()
                            if not lesson_month.empty and "student_id" in lesson_month.columns
                            else {}
                        )

                        count_rows = []

                        for sid in sorted(active_student_ids_for_month, key=lambda x: student_name_map_month.get(x, x)):
                            name = student_name_map_month.get(sid, sid)
                            current_count = int(lesson_count_map.get(sid, 0))
                            target_raw = str(student_target_count_map.get(sid, "")).strip()

                            try:
                                target_num = int(float(target_raw)) if target_raw else 0
                            except Exception:
                                target_num = 0

                            if target_num <= 0:
                                status = "月回数未設定"
                                diff = ""
                                sort_key = 3
                            elif current_count < target_num:
                                status = "少ない"
                                diff = f"あと{target_num - current_count}回"
                                sort_key = 0
                            elif current_count == target_num:
                                status = "OK"
                                diff = ""
                                sort_key = 2
                            else:
                                status = "多い"
                                diff = f"+{current_count - target_num}回"
                                sort_key = 1

                            sid_rows = check_month[
                                check_month["student_id"].astype(str).str.strip() == str(sid).strip()
                            ].copy()
                            reason_values = []
                            if not sid_rows.empty and "reason" in sid_rows.columns:
                                reason_values = [
                                    x for x in sid_rows["reason"].fillna("").astype(str).str.strip().tolist()
                                    if x and x != "通常"
                                ]
                            reason_summary = "、".join(sorted(set(monthly_reason_summary_label(x) for x in reason_values)))

                            count_rows.append({
                                "生徒": name,
                                "予定回数": current_count,
                                "月回数": target_raw if target_raw else "未設定",
                                "判定": status,
                                "差分": diff,
                                "例外区分": reason_summary,
                                "_sort": sort_key,
                            })

                        if count_rows:
                            count_df = pd.DataFrame(count_rows).sort_values(["_sort", "生徒"]).drop(columns=["_sort"])

                            def _style_month_count(row):
                                status = str(row.get("判定", "")).strip()
                                if status == "少ない":
                                    return ["background-color:#fff3cd"] * len(row)
                                if status == "多い":
                                    return ["background-color:#ffe5cc"] * len(row)
                                if status == "OK":
                                    return ["background-color:#e9f8ee"] * len(row)
                                return ["background-color:#f3f3f3"] * len(row)

                            shortage_count = int((count_df["判定"] == "少ない").sum())
                            over_count = int((count_df["判定"] == "多い").sum())
                            unset_count = int((count_df["判定"] == "月回数未設定").sum())
                            need_check_statuses = ["少ない", "多い", "月回数未設定"]

                            if shortage_count or over_count or unset_count:
                                st.warning(
                                    f"確認が必要：少ない {shortage_count}人 / 多い {over_count}人 / 月回数未設定 {unset_count}人"
                                )
                            else:
                                st.success("月回数と授業予定回数は大きくズレていません。")

                            only_need_check2 = st.checkbox(
                                "確認が必要な生徒だけ表示",
                                value=True,
                                key=f"monthly_count_only_ng_{target_year}_{target_month}",
                                help="予定回数ベースで、少ない・多い・月回数未設定だけを表示します。OFFにするとOKの生徒も表示します。",
                            )

                            st.caption("※ ↑の区分は予定回数に含めます。−の区分は予定回数に含めません。今月振替・追加授業はカウント、前月振替・自習・補習/確認・特典追加は除外します。")

                            display_count_df = count_df.copy()
                            if only_need_check2:
                                display_count_df = display_count_df[
                                    display_count_df["判定"].isin(need_check_statuses)
                                ].copy()

                            if display_count_df.empty:
                                st.success("確認が必要な生徒はいません。")
                            else:
                                st.dataframe(
                                    display_count_df.style.apply(_style_month_count, axis=1),
                                    use_container_width=True,
                                    hide_index=True,
                                )

                            if shortage_count or over_count:
                                st.caption("※ 前月振替や休み予定がある場合は、メモで補足すると後で分かりやすいです。")

                            # =====================================================
                            # d257:
                            # 前月・今月・来月の簡易確認
                            # -----------------------------------------------------
                            # いきなり月跨ぎ精算機能にはせず、前後月の不足/超過と
                            # 振替・回数外などの回数区分を並べて確認しやすくする。
                            # 例：前月が少ない、今月が多い → 前月振替/今月振替の整合性確認に使う。
                            # =====================================================
                            with st.expander("↔ 前月・今月・来月の簡易確認", expanded=False):
                                st.caption("月跨ぎ振替の確認用です。自動精算ではなく、前月・今月・来月の予定回数と差分を並べて確認します。出欠実績ではなく予定表ベースです。")

                                def _month_add(_year, _month, _offset):
                                    _base = pd.Timestamp(year=int(_year), month=int(_month), day=1)
                                    _m = _base + pd.DateOffset(months=int(_offset))
                                    return int(_m.year), int(_m.month)

                                def _month_label(_year, _month):
                                    return f"{int(_year)}年{int(_month)}月"

                                def _status_and_diff(_count, _target_raw):
                                    _target_raw = str(_target_raw).strip()
                                    try:
                                        _target_num = int(float(_target_raw)) if _target_raw else 0
                                    except Exception:
                                        _target_num = 0

                                    if _target_num <= 0:
                                        return "月回数未設定", ""
                                    if int(_count) < _target_num:
                                        return "少ない", f"−{_target_num - int(_count)}"
                                    if int(_count) == _target_num:
                                        return "OK", ""
                                    return "多い", f"+{int(_count) - _target_num}"

                                def _effective_month_plan_for_count(_year, _month):
                                    _start = pd.Timestamp(year=int(_year), month=int(_month), day=1)
                                    _end = _start + pd.offsets.MonthEnd(0)
                                    _rows = []

                                    for _day_ts in pd.date_range(_start.date(), _end.date(), freq="D"):
                                        _day = _day_ts.date()
                                        _plan = build_daily_plan_for_date(
                                            _day,
                                            students,
                                            _empty_weekly_for_calendar,
                                            monthly_schedule,
                                            schedule_overrides,
                                            timeslots,
                                            include_inactive=False,
                                        )
                                        if _plan is None or _plan.empty:
                                            continue

                                        _plan = _plan.copy()
                                        for _c in ["date", "student_id", "slot", "session_type", "reason", "note", "override_status"]:
                                            if _c not in _plan.columns:
                                                _plan[_c] = ""
                                            _plan[_c] = _plan[_c].fillna("").astype(str).str.strip()
                                        _plan["date"] = _day.isoformat()
                                        _rows.append(_plan)

                                    if not _rows:
                                        return pd.DataFrame(columns=["date", "student_id", "slot", "session_type", "reason", "note", "override_status"])

                                    _df = pd.concat(_rows, ignore_index=True)
                                    for _c in ["date", "student_id", "slot", "session_type", "reason", "note", "override_status"]:
                                        if _c not in _df.columns:
                                            _df[_c] = ""
                                        _df[_c] = _df[_c].fillna("").astype(str).str.strip()

                                    _df = _df[
                                        _df["override_status"].fillna("").astype(str).str.strip() != "キャンセル"
                                    ].copy()
                                    return _df

                                def _summarize_count_month(_year, _month):
                                    _df = _effective_month_plan_for_count(_year, _month)
                                    _result = {}

                                    if _df.empty:
                                        return _result

                                    _reason = _df["reason"].fillna("通常").astype(str).str.strip()
                                    _note = _df["note"].fillna("").astype(str).str.strip() if "note" in _df.columns else pd.Series([""] * len(_df), index=_df.index)
                                    _exclude = (
                                        _reason.isin(count_excluded_reasons)
                                        | _note.str.contains("回数外|月回数外", regex=True, na=False)
                                    )

                                    _lesson = _df[
                                        (_df["session_type"].astype(str).str.strip() == "授業")
                                        & (~_exclude)
                                    ].copy()

                                    _count_map = (
                                        _lesson["student_id"].astype(str).str.strip().value_counts().to_dict()
                                        if not _lesson.empty and "student_id" in _lesson.columns
                                        else {}
                                    )

                                    for _sid in sorted(active_student_ids_for_month, key=lambda x: student_name_map_month.get(x, x)):
                                        _sid = str(_sid).strip()
                                        _count = int(_count_map.get(_sid, 0))
                                        _sid_rows = _df[_df["student_id"].astype(str).str.strip() == _sid].copy()

                                        _reason_values = []
                                        if not _sid_rows.empty and "reason" in _sid_rows.columns:
                                            _reason_values = [
                                                x for x in _sid_rows["reason"].fillna("").astype(str).str.strip().tolist()
                                                if x and x != "通常"
                                            ]
                                        _reason_summary = "、".join(sorted(set(monthly_reason_summary_label(x) for x in _reason_values)))

                                        _target_raw = str(student_target_count_map.get(_sid, "")).strip()
                                        _status, _diff = _status_and_diff(_count, _target_raw)
                                        _result[_sid] = {
                                            "count": _count,
                                            "target": _target_raw if _target_raw else "未設定",
                                            "status": _status,
                                            "diff": _diff,
                                            "reason": _reason_summary,
                                        }

                                    return _result

                                _prev_y, _prev_m = _month_add(target_year, target_month, -1)
                                _next_y, _next_m = _month_add(target_year, target_month, 1)

                                _month_specs = [
                                    ("前月", _prev_y, _prev_m),
                                    ("今月", target_year, target_month),
                                    ("来月", _next_y, _next_m),
                                ]

                                _summaries = {
                                    _label: _summarize_count_month(_y, _m)
                                    for _label, _y, _m in _month_specs
                                }

                                _summary_pieces = []
                                for _label, _y, _m in _month_specs:
                                    _s = _summaries.get(_label, {})
                                    _short = sum(1 for _v in _s.values() if _v.get("status") == "少ない")
                                    _over = sum(1 for _v in _s.values() if _v.get("status") == "多い")
                                    _unset = sum(1 for _v in _s.values() if _v.get("status") == "月回数未設定")
                                    _summary_pieces.append(f"{_label}（{_month_label(_y, _m)}）：少ない{_short} / 多い{_over} / 未設定{_unset}")
                                st.info("　｜　".join(_summary_pieces))

                                def _fmt_month_cell(_v):
                                    if not _v:
                                        return "予定0 / 未確認"
                                    _count = _v.get("count", 0)
                                    _target = _v.get("target", "未設定")
                                    _status = _v.get("status", "")
                                    _diff = _v.get("diff", "")
                                    if _status == "OK":
                                        return f"{_count}/{_target} OK"
                                    if _diff:
                                        return f"{_count}/{_target} {_status}({_diff})"
                                    return f"{_count}/{_target} {_status}"

                                compare_rows = []
                                for _sid in sorted(active_student_ids_for_month, key=lambda x: student_name_map_month.get(x, x)):
                                    _name = student_name_map_month.get(_sid, _sid)
                                    _prev = _summaries.get("前月", {}).get(_sid, {})
                                    _curr = _summaries.get("今月", {}).get(_sid, {})
                                    _next = _summaries.get("来月", {}).get(_sid, {})

                                    _reasons_joined = " / ".join([
                                        x for x in [
                                            f"前月:{_prev.get('reason','')}" if _prev.get("reason", "") else "",
                                            f"今月:{_curr.get('reason','')}" if _curr.get("reason", "") else "",
                                            f"来月:{_next.get('reason','')}" if _next.get("reason", "") else "",
                                        ] if x
                                    ])

                                    # d277:
                                    # 「回数ズレ」と「回数区分あり」を分けて扱う。
                                    # OKだけど今月内振替などの回数区分がある生徒は、普段は隠せるようにする。
                                    _has_count_issue = (
                                        _prev.get("status") in ["少ない", "多い", "月回数未設定"]
                                        or _curr.get("status") in ["少ない", "多い", "月回数未設定"]
                                        or _next.get("status") in ["少ない", "多い", "月回数未設定"]
                                    )
                                    _has_reason = bool(_reasons_joined)

                                    compare_rows.append({
                                        "生徒": _name,
                                        f"前月({_prev_m}月)": _fmt_month_cell(_prev),
                                        f"今月({target_month}月)": _fmt_month_cell(_curr),
                                        f"来月({_next_m}月)": _fmt_month_cell(_next),
                                        "回数区分メモ": _reasons_joined,
                                        "_has_count_issue": _has_count_issue,
                                        "_has_reason": _has_reason,
                                    })

                                if compare_rows:
                                    compare_df = pd.DataFrame(compare_rows)

                                    # d277:
                                    # 以前は「回数ズレあり」と「回数区分あり」を1つのチェックにまとめていたため、
                                    # OKだけど回数区分がある生徒まで普段から表示されて見づらかった。
                                    # 普段は回数ズレだけ、必要な時だけ回数区分ありも表示できるように分離する。
                                    col_cross_filter1, col_cross_filter2 = st.columns(2)
                                    with col_cross_filter1:
                                        only_count_issue_cross = st.checkbox(
                                            "回数ズレがある生徒だけ表示",
                                            value=True,
                                            key=f"monthly_cross_count_only_issue_{target_year}_{target_month}",
                                            help="予定回数ベースで、前月・今月・来月のどこかに少ない／多い／月回数未設定がある生徒だけ表示します。OFFにすると全員を表示します。",
                                        )
                                    with col_cross_filter2:
                                        include_reason_cross = st.checkbox(
                                            "回数区分がある生徒も表示",
                                            value=False,
                                            key=f"monthly_cross_count_include_reason_{target_year}_{target_month}",
                                            help="ONにすると、回数はOKでも前月振替・今月振替・回数外などの回数区分がある生徒も表示します。",
                                        )

                                    if only_count_issue_cross:
                                        if include_reason_cross:
                                            compare_df = compare_df[
                                                compare_df["_has_count_issue"] | compare_df["_has_reason"]
                                            ].copy()
                                        else:
                                            compare_df = compare_df[
                                                compare_df["_has_count_issue"]
                                            ].copy()
                                    else:
                                        if not include_reason_cross:
                                            st.caption("全員表示中です。回数区分ありの生徒も含めて表示します。")
                                        else:
                                            st.caption("全員表示中です。回数区分も確認できます。")

                                    compare_df = compare_df.drop(
                                        columns=["_has_count_issue", "_has_reason", "_need"],
                                        errors="ignore",
                                    )

                                    if compare_df.empty:
                                        if include_reason_cross:
                                            st.success("回数ズレ・回数区分ありの生徒はいません。")
                                        else:
                                            st.success("回数ズレがある生徒はいません。")
                                    else:
                                        st.dataframe(compare_df, use_container_width=True, hide_index=True)
                                        if include_reason_cross:
                                            st.caption("※ 回数ズレの生徒に加えて、回数区分があるOKの生徒も表示しています。")
                                        else:
                                            st.caption("※ 前月−1・今月+1のような回数ズレがある生徒を中心に表示しています。回数区分だけ確認したい時は右のチェックをONにしてください。")
                                else:
                                    st.info("前月・今月・来月の比較対象がありません。")
                        else:
                            st.info("在籍中の生徒が見つかりません。")



                # d204: 月カレンダー内で、選択した生徒の予定を強調表示する。
                # 予定ボタンを押しても、上のselectboxから選んでも、同じ強調状態を見る。
                _monthly_highlight_state_key = f"monthly_calendar_highlight_student_state_{target_year}_{target_month}"
                _monthly_highlight_select_key = f"monthly_calendar_highlight_student_select_{target_year}_{target_month}"
                _monthly_highlight_prev_key = f"monthly_calendar_highlight_student_prev_{target_year}_{target_month}"
                _monthly_highlight_sync_key = f"monthly_calendar_highlight_student_sync_{target_year}_{target_month}"

                _highlight_options = [""] + monthly_student_options
                _current_highlight_sid = str(st.session_state.get(_monthly_highlight_state_key, "") or "").strip()
                if _current_highlight_sid not in _highlight_options:
                    _current_highlight_sid = ""
                    st.session_state[_monthly_highlight_state_key] = ""

                # カレンダー上の「選択」ボタンから来た場合、selectboxの表示も同じ生徒に合わせる。
                if st.session_state.get(_monthly_highlight_sync_key, False):
                    st.session_state[_monthly_highlight_select_key] = _current_highlight_sid
                    st.session_state[_monthly_highlight_prev_key] = _current_highlight_sid
                    st.session_state[_monthly_highlight_sync_key] = False

                if _monthly_highlight_select_key not in st.session_state:
                    st.session_state[_monthly_highlight_select_key] = _current_highlight_sid
                    st.session_state[_monthly_highlight_prev_key] = _current_highlight_sid

                selected_highlight_sid = st.selectbox(
                    "🔎 カレンダー内で強調する生徒",
                    _highlight_options,
                    format_func=lambda sid: "強調なし" if str(sid).strip() == "" else monthly_student_label_map.get(str(sid).strip(), str(sid).strip()),
                    key=_monthly_highlight_select_key,
                    help="生徒を選ぶと、その生徒の予定だけカレンダー内で強調表示します。予定の「選択」ボタンからも強調できます。",
                )
                selected_highlight_sid = str(selected_highlight_sid or "").strip()

                if selected_highlight_sid != str(st.session_state.get(_monthly_highlight_prev_key, "") or "").strip():
                    st.session_state[_monthly_highlight_state_key] = selected_highlight_sid
                    st.session_state[_monthly_highlight_prev_key] = selected_highlight_sid

                selected_highlight_sid = str(st.session_state.get(_monthly_highlight_state_key, selected_highlight_sid) or "").strip()
                selected_highlight_name = monthly_student_label_map.get(selected_highlight_sid, selected_highlight_sid) if selected_highlight_sid else ""

                if selected_highlight_sid:
                    _highlight_rows = calendar_month.copy() if calendar_month is not None else pd.DataFrame()
                    if not _highlight_rows.empty:
                        if "override_status" not in _highlight_rows.columns:
                            _highlight_rows["override_status"] = ""
                        _highlight_rows = _highlight_rows[
                            (_highlight_rows["student_id"].astype(str).str.strip() == selected_highlight_sid)
                            & (_highlight_rows["override_status"].fillna("").astype(str).str.strip() != "キャンセル")
                        ].copy()

                    if _highlight_rows.empty:
                        st.info(f"{selected_highlight_name}さんの有効な予定は、この月のカレンダーにはありません。")
                    else:
                        _highlight_types = _highlight_rows["session_type"].fillna("").astype(str).str.strip()
                        _highlight_lesson_count = int((_highlight_types == "授業").sum())
                        _highlight_self_count = int((_highlight_types == "自習").sum())
                        _highlight_slots = "、".join(
                            [
                                f"{pd.to_datetime(r.get('date'), errors='coerce').day}日 {normalize_slot(r.get('slot', ''))}コマ"
                                for _, r in _highlight_rows.sort_values(["date_dt", "slot"]).iterrows()
                                if not pd.isna(pd.to_datetime(r.get('date'), errors='coerce'))
                            ]
                        )
                        st.markdown(
                            f"**強調中：{selected_highlight_name}**　授業 {_highlight_lesson_count}回 / 自習 {_highlight_self_count}回"
                        )
                        if _highlight_slots:
                            st.caption(f"入っている日：{_highlight_slots}")

                    if st.button("強調を解除", key=f"monthly_calendar_clear_highlight_{target_year}_{target_month}"):
                        st.session_state[_monthly_highlight_state_key] = ""
                        st.session_state[_monthly_highlight_select_key] = ""
                        st.session_state[_monthly_highlight_prev_key] = ""
                        st.rerun()

                def _monthly_calendar_day_html(day_date: dt.date, rows_df: pd.DataFrame) -> str:
                    is_target_month = (day_date.month == target_month)
                    day_bg = "#ffffff" if is_target_month else "#f3f3f3"
                    day_color = "#222" if is_target_month else "#aaa"

                    parts = [
                        f'<div style="min-height:120px;background:{day_bg};border:1px solid #ddd;border-radius:8px;padding:6px;overflow:hidden;">',
                        f'<div style="font-weight:700;color:{day_color};margin-bottom:4px;">{day_date.day}</div>'
                    ]

                    if is_target_month and rows_df is not None and not rows_df.empty:
                        _rows = rows_df.copy()
                        _rows["_slot_num"] = pd.to_numeric(_rows["slot"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
                        _rows = _rows.sort_values(["_slot_num", "student_id"], na_position="last")

                        for _, rr in _rows.iterrows():
                            sid = str(rr.get("student_id", "")).strip()
                            name = student_name_map_month.get(sid, sid)
                            slot = normalize_slot(rr.get("slot", ""))
                            typ = str(rr.get("session_type", "")).strip() or "授業"
                            reason = str(rr.get("reason", "")).strip() or "通常"
                            reason_part = f"｜{reason}" if reason and reason != "通常" else ""
                            badge_bg = "#e8f4ff" if typ == "授業" else "#f4f4f4"
                            parts.append(
                                f'<div style="font-size:12px;background:{badge_bg};border-radius:6px;padding:3px 5px;margin:3px 0;white-space:normal;">'
                                f'{slot}コマ｜{name}｜{typ}{reason_part}'
                                f'</div>'
                            )

                    parts.append('</div>')
                    return "".join(parts)

                cal_obj = cal.Calendar(firstweekday=0)
                weeks = cal_obj.monthdatescalendar(target_year, target_month)
                rows_by_date = {}
                if not calendar_month.empty:
                    for _d, _g in calendar_month.groupby(calendar_month["date_dt"].dt.date):
                        rows_by_date[_d] = _g.copy()

                weekday_header = ["月", "火", "水", "木", "金", "土", "日"]
                header_cols = st.columns(7)
                for i, wd in enumerate(weekday_header):
                    with header_cols[i]:
                        st.markdown(
                            f"""
                            <div style="text-align:center;font-weight:700;background:#f7f7f7;border-radius:6px;padding:6px;">
                                {wd}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                # d258:
                # iPad用コンパクト表示のON/OFFをCSVに保存する。
                # session_stateだけだと再読み込みや別タブ移動で外れるため、
                # 一度ONにしたら次回以降もONで開けるようにする。
                _ui_pref_path = DATA_DIR / "ui_preferences.csv"

                def _load_ui_pref_bool(_key: str, default: bool = False) -> bool:
                    try:
                        if _ui_pref_path.exists():
                            _df = pd.read_csv(_ui_pref_path, dtype=str).fillna("")
                        else:
                            return bool(default)

                        if _df.empty:
                            return bool(default)

                        for _c in ["key", "value"]:
                            if _c not in _df.columns:
                                _df[_c] = ""

                        _df["key"] = _df["key"].fillna("").astype(str).str.strip()
                        _df["value"] = _df["value"].fillna("").astype(str).str.strip().str.lower()

                        _hit = _df[_df["key"] == str(_key).strip()]
                        if _hit.empty:
                            return bool(default)

                        return str(_hit.iloc[-1].get("value", "")).strip().lower() in ["true", "1", "yes", "on"]
                    except Exception:
                        return bool(default)

                def _save_ui_pref_bool(_key: str, value: bool) -> None:
                    try:
                        if _ui_pref_path.exists():
                            _df = pd.read_csv(_ui_pref_path, dtype=str).fillna("")
                        else:
                            _df = pd.DataFrame(columns=["key", "value", "updated_at"])

                        for _c in ["key", "value", "updated_at"]:
                            if _c not in _df.columns:
                                _df[_c] = ""

                        _df["key"] = _df["key"].fillna("").astype(str).str.strip()

                        _row = {
                            "key": str(_key).strip(),
                            "value": "true" if bool(value) else "false",
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }

                        _mask = _df["key"] == str(_key).strip()
                        if _mask.any():
                            for _k, _v in _row.items():
                                _df.loc[_mask, _k] = _v
                        else:
                            _df = pd.concat([_df, pd.DataFrame([_row])], ignore_index=True)

                        write_csv_atomic(_df[["key", "value", "updated_at"]].fillna(""), _ui_pref_path)
                    except Exception:
                        pass

                # d309:
                # iPad用コンパクト表示は、現在の統一レイアウトと差がなくなったため廃止。
                # 端末に関係なく、同じカレンダー表示を使用する。
                st.caption(
                    "予定ボタンを押すと操作パネルに反映されます。"
                    "変更・取消線・削除は操作パネルで行います。"
                )

                # d242:
                # 土日など予定が多い月はカレンダーが長くなるため、週ごとに折りたたむ。
                # 全部開く / 全部閉じる / 今日の週だけ開く で表示量を調整できるようにする。
                week_state_prefix = f"monthly_week_open_{target_year}_{target_month}"

                week_ctrl_col1, week_ctrl_col2, week_ctrl_col3 = st.columns(3)
                with week_ctrl_col1:
                    if st.button("全部開く", key=f"{week_state_prefix}_open_all"):
                        for _wi in range(1, len(weeks) + 1):
                            st.session_state[f"{week_state_prefix}_{_wi}"] = True
                        st.rerun()
                with week_ctrl_col2:
                    if st.button("全部閉じる", key=f"{week_state_prefix}_close_all"):
                        for _wi in range(1, len(weeks) + 1):
                            st.session_state[f"{week_state_prefix}_{_wi}"] = False
                        st.rerun()
                with week_ctrl_col3:
                    if st.button("今日の週だけ開く", key=f"{week_state_prefix}_today_only"):
                        for _wi, _week in enumerate(weeks, start=1):
                            st.session_state[f"{week_state_prefix}_{_wi}"] = (date.today() in _week)
                        st.rerun()

                for week_no, week in enumerate(weeks, start=1):
                    week_key = f"{week_state_prefix}_{week_no}"
                    week_has_today = date.today() in week
                    if week_key not in st.session_state:
                        # 初期表示は、今日を含む週だけ開く。今月に今日がない場合は第1週だけ開く。
                        st.session_state[week_key] = week_has_today or (week_no == 1 and not any(date.today() in _w for _w in weeks))

                    week_target_days = [d for d in week if d.month == target_month]
                    week_start_label = week_target_days[0].strftime("%m/%d") if week_target_days else week[0].strftime("%m/%d")
                    week_end_label = week_target_days[-1].strftime("%m/%d") if week_target_days else week[-1].strftime("%m/%d")

                    week_lesson_count = 0
                    week_self_count = 0
                    week_selected_count = 0
                    # d274:
                    # 強調中の生徒について、週タブを開かなくても「授業か自習か」が分かるようにする。
                    # 例：★山田さん 授業1 / 自習1
                    week_selected_lesson_count = 0
                    week_selected_self_count = 0

                    for _wd in week_target_days:
                        _dr = rows_by_date.get(_wd, pd.DataFrame())
                        if _dr is None or _dr.empty:
                            continue
                        _tmp = _dr.copy()
                        if "override_status" in _tmp.columns:
                            _tmp = _tmp[_tmp["override_status"].fillna("").astype(str).str.strip() != "キャンセル"].copy()
                        _types = _tmp["session_type"].fillna("").astype(str).str.strip()
                        week_lesson_count += int((_types == "授業").sum())
                        week_self_count += int((_types == "自習").sum())

                        if selected_highlight_sid:
                            _selected_week_rows = _tmp[
                                _tmp["student_id"].astype(str).str.strip() == selected_highlight_sid
                            ].copy()
                            week_selected_count += int(len(_selected_week_rows))
                            if not _selected_week_rows.empty:
                                _selected_types = _selected_week_rows["session_type"].fillna("").astype(str).str.strip()
                                week_selected_lesson_count += int((_selected_types == "授業").sum())
                                week_selected_self_count += int((_selected_types == "自習").sum())

                    week_label = f"第{week_no}週（{week_start_label}〜{week_end_label}）｜授業{week_lesson_count} / 自習{week_self_count}"
                    if week_has_today:
                        week_label = "📍 " + week_label + "｜今日"
                    if selected_highlight_sid and week_selected_count > 0:
                        _selected_type_parts = []
                        if week_selected_lesson_count > 0:
                            _selected_type_parts.append(f"授業{week_selected_lesson_count}")
                        if week_selected_self_count > 0:
                            _selected_type_parts.append(f"自習{week_selected_self_count}")
                        _selected_type_label = " / ".join(_selected_type_parts) if _selected_type_parts else f"{week_selected_count}件"
                        week_label += f"｜★{selected_highlight_name} {_selected_type_label}"

                    week_is_open = st.toggle(
                        week_label,
                        value=bool(st.session_state.get(week_key, False)),
                        key=week_key,
                    )
                    if week_is_open:
                        day_cols = st.columns(7)
                        for i, day_date in enumerate(week):
                            with day_cols[i]:
                                is_target_month = (day_date.month == target_month)
                                is_today_in_calendar = (day_date == date.today())
                                day_bg = "#fffbe6" if (is_target_month and is_today_in_calendar) else ("#ffffff" if is_target_month else "#f3f3f3")
                                day_color = "#111" if (is_target_month and is_today_in_calendar) else ("#222" if is_target_month else "#aaa")
                                day_border = "2px solid #f59e0b" if (is_target_month and is_today_in_calendar) else "1px solid #ddd"
                                # d305:
                                # 今日カードだけ下へずれる原因になる単独アンカーを廃止し、
                                # カード本体へ id を付ける。
                                today_anchor_attr = (
                                    f'id="monthly_today_{target_year}_{target_month}"'
                                    if (is_target_month and is_today_in_calendar)
                                    else ""
                                )
                                today_badge_html = (
                                    '<span style="'
                                    'display:inline-flex;align-items:center;height:18px;'
                                    'font-size:9px;background:#f59e0b;color:white;'
                                    'border-radius:999px;padding:0 6px;margin-left:4px;'
                                    'font-weight:800;line-height:1;'
                                    '">今日</span>'
                                    if (is_target_month and is_today_in_calendar) else ""
                                )

                                day_rows = rows_by_date.get(day_date, pd.DataFrame()) if is_target_month else pd.DataFrame()

                                lesson_count = 0
                                self_count = 0
                                if day_rows is not None and not day_rows.empty:
                                    _count_rows = day_rows.copy()
                                    if "override_status" in _count_rows.columns:
                                        _count_rows = _count_rows[
                                            _count_rows["override_status"].fillna("").astype(str).str.strip() != "キャンセル"
                                        ].copy()
                                    _count_types = _count_rows["session_type"].fillna("").astype(str).str.strip()
                                    lesson_count = int((_count_types == "授業").sum())
                                    self_count = int((_count_types == "自習").sum())

                                selected_day_count = 0
                                if (
                                    is_target_month
                                    and selected_highlight_sid
                                    and day_rows is not None
                                    and not day_rows.empty
                                ):
                                    _selected_day_rows = day_rows.copy()
                                    if "override_status" in _selected_day_rows.columns:
                                        _selected_day_rows = _selected_day_rows[
                                            _selected_day_rows["override_status"].fillna("").astype(str).str.strip() != "キャンセル"
                                        ].copy()
                                    selected_day_count = int((_selected_day_rows["student_id"].astype(str).str.strip() == selected_highlight_sid).sum())

                                # d304:
                                # 日付カード内の文字数で高さや見た目が崩れないように、
                                # 人数表示を短い固定表記にし、カード高を統一する。
                                count_html = ""
                                if is_target_month:
                                    count_html = (
                                        '<div style="'
                                        'display:flex;align-items:center;justify-content:flex-start;'
                                        'gap:5px;margin-top:6px;white-space:nowrap;'
                                        'font-size:clamp(9px,1.15vw,12px);line-height:1.1;'
                                        'overflow:hidden;text-overflow:clip;'
                                        '">'
                                        f'<span style="color:#2563a6;font-weight:700;">授 {lesson_count}</span>'
                                        '<span style="color:#777;">｜</span>'
                                        f'<span style="color:#2f7d32;font-weight:700;">自 {self_count}</span>'
                                        '</div>'
                                    )

                                selected_html = ""
                                if is_target_month and selected_day_count > 0:
                                    selected_html = (
                                        '<div style="'
                                        'margin-top:4px;font-size:clamp(8px,1vw,10px);'
                                        'color:#111;font-weight:700;white-space:nowrap;'
                                        'overflow:hidden;text-overflow:ellipsis;'
                                        '">'
                                        f'★ {selected_highlight_name} {selected_day_count}件'
                                        '</div>'
                                    )

                                st.markdown(
                                    f"""
                                    <div {today_anchor_attr} style="
                                        height:78px;
                                        box-sizing:border-box;
                                        background:{day_bg};
                                        border:{day_border};
                                        border-radius:8px;
                                        padding:7px 7px 6px 7px;
                                        overflow:hidden;
                                    ">
                                        <div style="
                                            height:22px;
                                            display:flex;
                                            align-items:flex-start;
                                            justify-content:flex-start;
                                            white-space:nowrap;
                                            font-weight:800;
                                            color:{day_color};
                                            line-height:1;
                                        ">
                                            <span>{day_date.day}</span>{today_badge_html}
                                        </div>
                                        {count_html}
                                        {selected_html}
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                                if is_target_month:
                                    if day_rows is not None and not day_rows.empty:
                                        _rows = day_rows.copy()
                                        _rows["_slot_num"] = pd.to_numeric(
                                            _rows["slot"].astype(str).str.extract(r"(\d+)")[0],
                                            errors="coerce",
                                        )
                                        _rows = _rows.sort_values(["_slot_num", "student_id"], na_position="last")

                                        for row_idx, rr in _rows.iterrows():
                                            sid = str(rr.get("student_id", "")).strip()
                                            name = student_name_map_month.get(sid, sid)
                                            slot = normalize_slot(rr.get("slot", ""))
                                            typ = str(rr.get("session_type", "")).strip() or "授業"
                                            reason = str(rr.get("reason", "")).strip() or "通常"
                                            override_status = str(rr.get("override_status", "")).strip()
                                            attendance_locked = (
                                                override_status != "キャンセル"
                                                and is_attendance_locked_plan(monthly_attended_keys, sid, day_date)
                                            )

                                            label_parts = []
                                            # d203: 「当日追加｜追加」のような二重ラベルを避ける。
                                            # 例外ステータスがある場合はそれを優先し、通常の理由は補助扱いにする。
                                            if override_status == "キャンセル":
                                                label_parts.append("キャンセル")
                                            elif override_status == "追加":
                                                label_parts.append("当日追加")
                                            elif override_status == "変更":
                                                label_parts.append("変更")
                                            elif reason and reason != "通常":
                                                label_parts.append(reason)
                                            if attendance_locked:
                                                label_parts.append("✅出席済")
                                            reason_part = f"｜{'｜'.join(label_parts)}" if label_parts else ""

                                            text_style = ""
                                            opacity = "1"
                                            is_highlighted_student = bool(selected_highlight_sid and sid == selected_highlight_sid)
                                            highlight_style = ""
                                            item_font_size = "12px"
                                            item_weight = "600"

                                            if override_status == "キャンセル":
                                                item_bg = "#eeeeee"
                                                item_border = "#999999"
                                                item_icon = "⚪"
                                                text_style = "text-decoration:line-through;"
                                                opacity = "0.75"
                                            elif override_status == "追加":
                                                item_bg = "#fff0e5"
                                                item_border = "#f0a000"
                                                item_icon = "🟠"
                                            elif override_status == "変更":
                                                item_bg = "#f3e8ff"
                                                item_border = "#9b5de5"
                                                item_icon = "🟣"
                                            elif typ == "自習":
                                                item_bg = "#e9f8ee"
                                                item_border = "#39a86b"
                                                item_icon = "🟢"
                                            else:
                                                item_bg = "#e8f4ff"
                                                item_border = "#3b82c4"
                                                item_icon = "🔵"

                                            # d204: 選択中の生徒は、授業/自習の色分けを残したまま強調する。
                                            if is_highlighted_student and override_status != "キャンセル":
                                                item_font_size = "13px"
                                                item_weight = "800"
                                                if typ == "自習":
                                                    item_bg = "#dcfce7"
                                                    item_border = "#16a34a"
                                                    item_icon = "🟩"
                                                    highlight_style = "border:2px solid #16a34a;border-left:7px solid #16a34a;box-shadow:0 0 0 2px #bbf7d0;"
                                                else:
                                                    item_bg = "#dbeafe"
                                                    item_border = "#2563eb"
                                                    item_icon = "🟦"
                                                    highlight_style = "border:2px solid #2563eb;border-left:7px solid #2563eb;box-shadow:0 0 0 2px #bfdbfe;"

                                            if not highlight_style:
                                                highlight_style = f"border-left:4px solid {item_border};"

                                            # d230:
                                            # コマごとに色付きバッジを出して、文字を読まなくても
                                            # 何コマ目か見分けやすくする。
                                            _slot_color_map = {
                                                "1": ("①", "#fff7cc", "#b77900"),
                                                "2": ("②", "#e0f2fe", "#0369a1"),
                                                "3": ("③", "#dcfce7", "#15803d"),
                                                "4": ("④", "#fce7f3", "#be185d"),
                                                "5": ("⑤", "#ede9fe", "#6d28d9"),
                                                "6": ("⑥", "#ffedd5", "#c2410c"),
                                                "7": ("⑦", "#e5e7eb", "#374151"),
                                            }
                                            _slot_badge_text, _slot_badge_bg, _slot_badge_fg = _slot_color_map.get(
                                                str(slot).strip(),
                                                (str(slot).strip() or "?", "#f3f4f6", "#374151")
                                            )
                                            slot_badge_html = (
                                                f'<span style="display:inline-block;min-width:22px;text-align:center;'
                                                f'border-radius:999px;padding:1px 5px;margin-right:4px;'
                                                f'background:{_slot_badge_bg};color:{_slot_badge_fg};'
                                                f'font-weight:900;border:1px solid {_slot_badge_fg};">'
                                                f'{_slot_badge_text}</span>'
                                            )

                                            # d307:
                                            # コマ固定レーンは使わず、予定は上から順に詰めて表示する。
                                            # 生徒名だけ最大3行分の高さを確保し、できるだけフルネームが見えるようにする。
                                            item_html = (
                                                f'<div title="{slot}コマ｜{name}｜{typ}{reason_part}" '
                                                f'style="background:{item_bg};{highlight_style}'
                                                f'border-radius:6px;padding:4px 6px;margin:4px 0 2px 0;'
                                                f'height:72px;box-sizing:border-box;'
                                                f'opacity:{opacity};{text_style}">'
                                                f'<div style="display:flex;align-items:flex-start;min-width:0;">'
                                                f'<span style="flex:0 0 auto;margin-right:2px;">{item_icon}</span>'
                                                f'{slot_badge_html}'
                                                f'<span style="'
                                                f'display:-webkit-box;'
                                                f'-webkit-line-clamp:3;'
                                                f'-webkit-box-orient:vertical;'
                                                f'overflow:hidden;'
                                                f'word-break:break-word;'
                                                f'line-height:1.25;'
                                                f'max-height:3.8em;'
                                                f'font-size:{item_font_size};'
                                                f'font-weight:{item_weight};'
                                                f'color:#111;'
                                                f'">{name}</span>'
                                                f'</div>'
                                                f'<div style="'
                                                f'margin-top:4px;'
                                                f'padding-left:2px;'
                                                f'white-space:nowrap;'
                                                f'overflow:hidden;'
                                                f'text-overflow:ellipsis;'
                                                f'font-size:10px;'
                                                f'line-height:1.2;'
                                                f'color:#555;'
                                                f'">{slot}コマ｜{typ}{reason_part}</div>'
                                                f'</div>'
                                            )
                                            st.markdown(item_html, unsafe_allow_html=True)

                                            # d305:
                                            # 名前の長さでボタンが2行にならないよう、ラベルを固定する。
                                            btn_label = "選択"

                                            # d324:
                                            # ボタン押下時にStreamlitは自動再実行するため、
                                            # 選択処理内で追加の st.rerun() は呼ばない。
                                            # 二重描画を防ぎ、選択時の待ち時間を減らす。
                                            def _pick_current_monthly_calendar_item():
                                                st.session_state[f"monthly_sidebar_edit_date_{target_year}_{target_month}"] = day_date
                                                st.session_state[f"monthly_sidebar_edit_slot_{target_year}_{target_month}"] = slot
                                                st.session_state[_monthly_highlight_state_key] = sid
                                                st.session_state[_monthly_highlight_sync_key] = True
                                                _monthly_idx_raw = str(rr.get("__monthly_index", "")).strip()
                                                if _monthly_idx_raw != "":
                                                    try:
                                                        _monthly_idx_value = int(float(_monthly_idx_raw))
                                                    except Exception:
                                                        _monthly_idx_value = _monthly_idx_raw
                                                    st.session_state[f"monthly_sidebar_update_target_{target_year}_{target_month}"] = _monthly_idx_value
                                                    st.session_state[f"monthly_sidebar_delete_target_{target_year}_{target_month}"] = _monthly_idx_value
                                                else:
                                                    st.session_state.pop(f"monthly_sidebar_update_target_{target_year}_{target_month}", None)
                                                    st.session_state.pop(f"monthly_sidebar_delete_target_{target_year}_{target_month}", None)

                                            def _uncancel_current_monthly_calendar_item():
                                                _att_before = load_attendance_log().copy()
                                                ov2, att2, _cleared_absence = (
                                                    restore_cancelled_plan_and_clear_absence(
                                                        schedule_overrides,
                                                        _att_before,
                                                        student_id=sid,
                                                        d=day_date,
                                                        slot=slot,
                                                    )
                                                )
                                                write_csv_atomic(
                                                    ov2,
                                                    SCHEDULE_OVERRIDES_CSV,
                                                )
                                                if _cleared_absence:
                                                    save_attendance_log(att2)

                                                _msg = (
                                                    "キャンセルを解除しました。"
                                                    "元の予定を復活させます。"
                                                )
                                                if _cleared_absence:
                                                    _msg += (
                                                        " 欠席・取消の出欠記録も"
                                                        "未登録へ戻しました。"
                                                    )
                                                st.success(_msg)
                                                st.caption(
                                                    "※ キャンセル時に座席を空席にしていた場合、"
                                                    "座席は必要に応じて再登録してください。"
                                                )
                                                st.rerun()

                                            def _cancel_current_monthly_calendar_item():
                                                ov2 = upsert_schedule_override_row(
                                                    schedule_overrides,
                                                    student_id=sid,
                                                    d=day_date,
                                                    slot=slot,
                                                    action="キャンセル",
                                                    note="月カレンダーからキャンセル（出席済み修正）" if attendance_locked else "月カレンダーからキャンセル",
                                                )
                                                write_csv_atomic(ov2, SCHEDULE_OVERRIDES_CSV)
                                                seat2 = remove_seat_assignment_for_plan(
                                                    seat_assignments,
                                                    d=day_date,
                                                    student_id=sid,
                                                    slot=slot,
                                                )
                                                write_csv_atomic(seat2, SEAT_ASSIGNMENTS_CSV)
                                                st.success("キャンセルしました。今日の予定にも反映します。")
                                                if attendance_locked:
                                                    st.caption("※ 出席ログ自体を直す必要がある場合は、出席記録の取消も確認してください。")
                                                st.rerun()

                                            # d273:
                                            # カレンダー内は「予定を選択するだけ」にする。
                                            # 取消線・解除・削除などの修正操作は、右/左の操作パネルへ集約して誤操作を減らす。
                                            st.markdown(
                                                """
                                                <style>
                                                div[data-testid="stButton"] > button {
                                                    min-height: 38px;
                                                    height: 38px;
                                                    padding-top: 0;
                                                    padding-bottom: 0;
                                                    white-space: nowrap;
                                                }
                                                div[data-testid="stButton"] > button p {
                                                    white-space: nowrap;
                                                    overflow: hidden;
                                                    text-overflow: ellipsis;
                                                }
                                                </style>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                            if st.button(
                                                btn_label,
                                                key=f"monthly_calendar_pick_{target_year}_{target_month}_{row_idx}",
                                                use_container_width=True,
                                                help=f"{name}の予定を選択",
                                            ):
                                                _pick_current_monthly_calendar_item()
                                                _open_monthly_edit_dialog()


        # =====================================================
        # d276:
        # 便利だから畳んでいる機能と、不要かもしれない整理候補を分ける。
        # 🧹整理候補は、しばらく使わなければ後で削除するための仮置き場。
        # =====================================================
        if monthly_view_mode == "⚙ 生成":
            with st.expander("生成プレビュー・固定スケジュール反映", expanded=False):
                st.caption("固定スケジュールの曜日・コマ・週指定から、その月の予定を生成します。")
                st.markdown("### 生成プレビュー")
                if generated_df.empty:
                    st.warning("生成できる月予定がありません。固定スケジュール（週次）を確認してください。")
                else:
                    preview_df = generated_df.copy()
                    preview_df["生徒"] = preview_df["student_id"].map(student_name_map_month).fillna(preview_df["student_id"])
                    preview_df = preview_df.rename(columns={
                        "date": "日付",
                        "slot": "コマ",
                        "session_type": "種別",
                        "reason": "回数区分",
                        "note": "メモ",
                        "source": "作成元",
                    })
                    show_cols = ["日付", "コマ", "生徒", "種別", "回数区分", "メモ", "作成元"]
                    st.dataframe(
                        preview_df[show_cols],
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.markdown("### 回数チェック（授業のみ）")
                    lesson_df = generated_df[
                        generated_df["session_type"].astype(str).str.strip() == "授業"
                    ].copy()
                    count_map = lesson_df["student_id"].astype(str).str.strip().value_counts().to_dict()

                    count_rows = []
                    for sid, current_count in count_map.items():
                        target_raw = str(student_target_count_map.get(sid, "")).strip()
                        try:
                            target_num = int(float(target_raw)) if target_raw else 0
                        except Exception:
                            target_num = 0

                        if target_num <= 0:
                            check_label = "月回数未設定"
                        elif current_count < target_num:
                            check_label = f"不足 あと{target_num - current_count}回"
                        elif current_count == target_num:
                            check_label = "OK"
                        else:
                            check_label = f"超過 +{current_count - target_num}回"

                        count_rows.append({
                            "生徒": student_name_map_month.get(sid, sid),
                            "予定回数": current_count,
                            "月回数": target_raw,
                            "判定": check_label,
                        })

                    if count_rows:
                        count_df = pd.DataFrame(count_rows).sort_values(["判定", "生徒"])
                        st.dataframe(count_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("授業予定がありません。")

                    st.warning("反映すると、同じ年月の monthly_schedule.csv 既存データを置き換えます。")
                    if st.button("📅 固定スケジュールをカレンダーに反映", key=f"save_monthly_schedule_{target_year}_{target_month}"):
                        monthly_existing = monthly_schedule.copy()
                        for c in MONTHLY_SCHEDULE_COLS:
                            if c not in monthly_existing.columns:
                                monthly_existing[c] = ""
                        monthly_existing = monthly_existing[MONTHLY_SCHEDULE_COLS].fillna("")
                        monthly_existing["date_dt"] = pd.to_datetime(monthly_existing["date"], errors="coerce")

                        keep_df = monthly_existing[
                            ~(
                                (monthly_existing["date_dt"].dt.year == target_year)
                                & (monthly_existing["date_dt"].dt.month == target_month)
                            )
                        ].drop(columns=["date_dt"], errors="ignore").copy()

                        save_df = pd.concat([keep_df, generated_df], ignore_index=True)
                        save_df = save_df[MONTHLY_SCHEDULE_COLS].fillna("")
                        st.session_state[monthly_edit_key] = (
                            _normalize_monthly_edit_df(save_df)
                        )
                        st.session_state[monthly_dirty_key] = True
                        st.success(
                            f"{target_year}年{target_month}月の固定スケジュールを"
                            "編集用カレンダーに反映しました。最後に一括保存してください。"
                        )
                        st.rerun()

        if monthly_view_mode == "📊 回数確認":
            st.markdown("### 📊 月回数チェック")
            check_month = monthly_schedule.copy()
            check_month["date_dt"] = pd.to_datetime(check_month["date"], errors="coerce")
            check_month = check_month[
                (check_month["date_dt"].dt.year == target_year)
                & (check_month["date_dt"].dt.month == target_month)
            ].copy()

            if check_month.empty:
                st.info("この年月の月スケジュールはありません。")
            else:
                check_month["student_id"] = check_month["student_id"].fillna("").astype(str).str.strip()
                check_month["session_type"] = check_month["session_type"].fillna("").astype(str).str.strip()
                check_month["reason"] = (
                    check_month["reason"].fillna("").astype(str).str.strip().replace("", "通常")
                )

                counted = check_month[
                    check_month["session_type"].eq("授業")
                    & ~check_month["reason"].isin(monthly_count_excluded_reasons)
                ].copy()
                count_map = counted["student_id"].value_counts().to_dict()

                rows = []
                target_ids = sorted(
                    active_student_ids_for_month | set(check_month["student_id"].tolist())
                )
                for sid in target_ids:
                    current_count = int(count_map.get(sid, 0))
                    target_raw = str(student_target_count_map.get(sid, "")).strip()
                    try:
                        target_count = int(float(target_raw)) if target_raw else 0
                    except Exception:
                        target_count = 0

                    if target_count <= 0:
                        result = "月回数未設定"
                    elif current_count < target_count:
                        result = f"不足 あと{target_count-current_count}回"
                    elif current_count == target_count:
                        result = "OK"
                    else:
                        result = f"超過 +{current_count-target_count}回"

                    rows.append({
                        "生徒": student_name_map_month.get(sid, sid),
                        "現在の授業回数": current_count,
                        "設定回数": target_raw,
                        "判定": result,
                    })

                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                if target_ids:
                    detail_sid = st.selectbox(
                        "詳しく見る生徒",
                        target_ids,
                        key=f"monthly_count_detail_{target_year}_{target_month}",
                        format_func=lambda sid: student_name_map_month.get(sid, sid),
                    )
                    detail = check_month[check_month["student_id"].eq(detail_sid)].copy()
                    detail = detail.sort_values(["date_dt", "slot"], na_position="last")
                    detail = detail.rename(columns={
                        "date": "日付",
                        "slot": "コマ",
                        "session_type": "種別",
                        "reason": "回数区分",
                        "note": "メモ",
                    })
                    st.dataframe(
                        detail[["日付", "コマ", "種別", "回数区分", "メモ"]],
                        use_container_width=True,
                        hide_index=True,
                    )

        if monthly_view_mode == "📅 編集":
            st.caption("左の操作サイドバーは廃止し、追加・編集をポップアップへ集約しています。")

        if monthly_view_mode in ("📅 編集", "⚙ 生成"):
            monthly_has_unsaved = bool(
                st.session_state.get(monthly_dirty_key, False)
            )
            save_monthly_batch = False
            discard_monthly_batch = False

            if monthly_has_unsaved:
                st.markdown(
                    """
                    <style>
                    .st-key-monthly_fixed_save_bar {
                        position: fixed;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        z-index: 99999;
                        background: rgba(255,255,255,0.98);
                        border-top: 3px solid #f59e0b;
                        box-shadow: 0 -4px 18px rgba(0,0,0,0.18);
                        padding: 8px 14px 10px 14px;
                    }
                    .st-key-monthly_fixed_save_bar p {
                        margin-bottom: 0;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )

                with st.container(
                    key="monthly_fixed_save_bar"
                ):
                    fixed_status_col, fixed_save_col, fixed_discard_col = (
                        st.columns([2.2, 1.4, 1.0])
                    )
                    with fixed_status_col:
                        st.markdown(
                            "**🟡 月スケジュールに未保存の変更があります**"
                        )
                    with fixed_save_col:
                        save_monthly_batch = st.button(
                            "💾 今すぐ保存",
                            type="primary",
                            use_container_width=True,
                            key="save_monthly_schedule_batch",
                        )
                    with fixed_discard_col:
                        discard_monthly_batch = st.button(
                            "↩ 破棄",
                            use_container_width=True,
                            key="discard_monthly_schedule_batch",
                        )

                # 固定バーで最下部が隠れないための余白
                st.markdown(
                    "<div style='height:110px;'></div>",
                    unsafe_allow_html=True,
                )

            if save_monthly_batch:
                current_signature = _monthly_schedule_file_signature()
                base_signature = st.session_state.get(
                    monthly_base_signature_key
                )

                if current_signature != base_signature:
                    st.error(
                        "編集中にmonthly_schedule.csvが別の処理で更新されました。"
                        "安全のため保存していません。"
                        "「編集を破棄」で最新データを読み直してから、"
                        "もう一度変更してください。"
                    )
                else:
                    edited_monthly = _normalize_monthly_edit_df(
                        st.session_state[monthly_edit_key]
                    )
                    write_csv_atomic(
                        edited_monthly,
                        MONTHLY_SCHEDULE_CSV,
                    )

                    # 月予定の完全削除に関連する例外行も、この時点でまとめて整理する。
                    pending_cleanup = list(
                        st.session_state.get(
                            monthly_pending_override_cleanup_key,
                            [],
                        )
                    )
                    if pending_cleanup:
                        overrides_to_save = safe_read_csv(
                            SCHEDULE_OVERRIDES_CSV,
                            show_message=False,
                        )
                        for item in pending_cleanup:
                            overrides_to_save = remove_schedule_override_rows(
                                overrides_to_save,
                                student_id=item.get("student_id", ""),
                                d=item.get("date", ""),
                                slot=item.get("slot", ""),
                                action=None,
                            )
                        write_csv_atomic(
                            overrides_to_save,
                            SCHEDULE_OVERRIDES_CSV,
                        )

                    for key in [
                        monthly_edit_key,
                        monthly_dirty_key,
                        monthly_base_signature_key,
                        monthly_pending_override_cleanup_key,
                    ]:
                        st.session_state.pop(key, None)

                    st.success("月スケジュールをまとめて保存しました。")
                    st.rerun()

            if discard_monthly_batch:
                for key in [
                    monthly_edit_key,
                    monthly_dirty_key,
                    monthly_base_signature_key,
                    monthly_pending_override_cleanup_key,
                ]:
                    st.session_state.pop(key, None)
                st.rerun()

    # ---------------------------
    # 🗓️ スケジュール例外（schedule_overrides.csv）
    # ---------------------------

    # ---------------------------
    # 🛠 システム設定（CSV手書きをゼロに近づける）
    #   - student_schedule.csv（通常の時間割）
    #   - timeslots.csv（コマ時間）
    # ---------------------------
    if admin_section == "🛠 システム設定":
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

        # d303:
        # システム設定内も、選択していない画面を実行しない。
        system_section = st.radio(
            "設定項目",
            ["🗓️ 基本スケジュール", "⏱ コマ時間"],
            horizontal=True,
            key="system_section_selector",
        )

        # ===== student_schedule.csv =====
        if system_section == "🗓️ 基本スケジュール":
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
        if system_section == "⏱ コマ時間":
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

    
    if admin_section == "🗓️ スケジュール例外":
            st.subheader("スケジュール例外（一覧確認用）")
            st.caption("※ 予定の取消・解除・削除は、基本的に 月スケジュールカレンダー で行います。ここは schedule_overrides.csv の確認用です。")
    
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
                
                
    if admin_section == "ℹ️ 運用メモ":
        st.subheader("ℹ️ 運用メモ")
        st.info(
            "現在、運用メモとして個別に登録する項目はありません。"
            "日々の操作は、各管理メニューから行ってください。"
        )


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


    _seat_page_active_ids = set()
    if not students.empty and "student_id" in students.columns:
        _seat_page_active_students = students.copy()
        if "is_active" in _seat_page_active_students.columns:
            _seat_page_active_students = _seat_page_active_students[
                _seat_page_active_students["is_active"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
                .replace("", "true")
                .isin(["true", "1", "yes"])
            ].copy()
        _seat_page_active_ids = set(
            _seat_page_active_students["student_id"]
            .astype(str)
            .str.strip()
            .tolist()
        )

    today_seats = seat_assignments[
        (seat_assignments["date"].astype(str).str.strip() == today)
        & (seat_assignments["slot"].astype(str).str.strip() == str(seat_slot_sel).strip())
        & (
            seat_assignments["student_id"]
            .astype(str)
            .str.strip()
            .isin(_seat_page_active_ids)
        )
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

    # d208: 上の「今日の座席配置」でも、表示中コマの予定生徒を確認できるようにする。
    # 補助登録の候補だけでなく、今日の予定 / 月スケジュール / 例外追加を同じ共通ロジックで表示する。
    seat_plan_today_for_display = build_daily_plan_for_date(
        dt.date.today(),
        students,
        student_schedule,
        monthly_schedule,
        schedule_overrides,
        timeslots,
        include_inactive=False,
    )

    display_slot_norm = normalize_slot(seat_slot_sel)
    display_rows = []

    if not seat_plan_today_for_display.empty:
        _display_plan = seat_plan_today_for_display.copy()
        for _c in ["student_id", "slot", "session_type"]:
            if _c not in _display_plan.columns:
                _display_plan[_c] = ""
            _display_plan[_c] = _display_plan[_c].fillna("").astype(str).str.strip()
        _display_plan["slot"] = _display_plan["slot"].map(normalize_slot)
        _display_plan = _display_plan[_display_plan["slot"] == display_slot_norm].copy()

        for _, _r in _display_plan.iterrows():
            _sid = str(_r.get("student_id", "")).strip()
            if not _sid:
                continue
            _seat_no = ""
            for _s_no, _s_sid in seat_map.items():
                if str(_s_sid).strip() == _sid:
                    _seat_no = _s_no
                    break

            display_rows.append({
                "席": f"席{_seat_no}" if _seat_no else "⚠ 未配置",
                "生徒": student_name_map.get(_sid, _sid),
                "種別": str(_r.get("session_type", "")).strip(),
                "状態": "予定あり",
                "_seat_num": pd.to_numeric(_seat_no, errors="coerce"),
            })

    # d209: 共通ロジックに入らなかった月スケジュール/例外追加も、
    # 表示中コマでは「予定ソース確認」として見えるようにする。
    # これで「カレンダーにはいるのに座席リストに出ない」原因を画面上で追いやすくする。
    top_cancel_keys = set()
    if not schedule_overrides.empty:
        _ov_cancel = schedule_overrides.copy()
        for _c in ["date", "student_id", "slot", "action"]:
            if _c not in _ov_cancel.columns:
                _ov_cancel[_c] = ""
            _ov_cancel[_c] = _ov_cancel[_c].fillna("").astype(str).str.strip()
        _ov_cancel["slot"] = _ov_cancel["slot"].map(normalize_slot)
        _ov_cancel["action_norm"] = _ov_cancel["action"].map(normalize_action_value)
        top_cancel_keys = set(
            zip(
                _ov_cancel.loc[
                    (_ov_cancel["date"] == today) & (_ov_cancel["action_norm"] == "キャンセル"),
                    "student_id",
                ].astype(str).str.strip(),
                _ov_cancel.loc[
                    (_ov_cancel["date"] == today) & (_ov_cancel["action_norm"] == "キャンセル"),
                    "slot",
                ].astype(str).str.strip(),
            )
        )

    top_existing_keys = set()
    for _r in display_rows:
        _name = str(_r.get("生徒", "")).strip()
        for _sid0, _name0 in student_name_map.items():
            if str(_name0).strip() == _name:
                top_existing_keys.add((str(_sid0).strip(), display_slot_norm))

    def _append_top_candidate(_sid, _slot, _stype, _status):
        _sid = str(_sid).strip()
        _slot = normalize_slot(_slot)
        if not _sid or _slot != display_slot_norm:
            return
        _key = (_sid, _slot)
        if _key in top_existing_keys:
            return
        _seat_no = ""
        for _s_no, _s_sid in seat_map.items():
            if str(_s_sid).strip() == _sid:
                _seat_no = _s_no
                break
        if _key in top_cancel_keys:
            _status = "キャンセル済み（予定から除外）"
        display_rows.append({
            "席": f"席{_seat_no}" if _seat_no else "⚠ 未配置",
            "生徒": student_name_map.get(_sid, _sid),
            "種別": str(_stype).strip(),
            "状態": _status,
            "_seat_num": pd.to_numeric(_seat_no, errors="coerce"),
        })
        top_existing_keys.add(_key)

    if not monthly_schedule.empty:
        _ms_top = monthly_schedule.copy()
        for _c in ["date", "student_id", "slot", "session_type"]:
            if _c not in _ms_top.columns:
                _ms_top[_c] = ""
            _ms_top[_c] = _ms_top[_c].fillna("").astype(str).str.strip()
        _ms_top["slot"] = _ms_top["slot"].map(normalize_slot)
        _ms_top = _ms_top[(_ms_top["date"] == today) & (_ms_top["slot"] == display_slot_norm)].copy()
        for _, _r in _ms_top.iterrows():
            _append_top_candidate(_r.get("student_id", ""), _r.get("slot", ""), _r.get("session_type", ""), "月スケジュール確認")

    if not schedule_overrides.empty:
        _ov_top = schedule_overrides.copy()
        for _c in ["date", "student_id", "slot", "action", "session_type"]:
            if _c not in _ov_top.columns:
                _ov_top[_c] = ""
            _ov_top[_c] = _ov_top[_c].fillna("").astype(str).str.strip()
        _ov_top["slot"] = _ov_top["slot"].map(normalize_slot)
        _ov_top["action_norm"] = _ov_top["action"].map(normalize_action_value)
        _ov_top = _ov_top[
            (_ov_top["date"] == today)
            & (_ov_top["slot"] == display_slot_norm)
            & (_ov_top["action_norm"].isin(["追加", "時間変更", "キャンセル"]))
        ].copy()
        for _, _r in _ov_top.iterrows():
            _status = "例外追加/変更確認"
            if str(_r.get("action_norm", "")).strip() == "キャンセル":
                _status = "キャンセル済み（予定から除外）"
            _append_top_candidate(_r.get("student_id", ""), _r.get("slot", ""), _r.get("session_type", ""), _status)

    # 座席だけ登録されていて、今日の予定側にいない生徒も表示する。
    # 予定連携の漏れや、古い座席登録の残りを見つけやすくするため。
    planned_names = {str(r.get("生徒", "")).strip() for r in display_rows}
    for _seat_no, _sid in seat_map.items():
        _name = student_name_map.get(str(_sid).strip(), str(_sid).strip())
        if _name and _name not in planned_names:
            display_rows.append({
                "席": f"席{_seat_no}",
                "生徒": _name,
                "種別": "",
                "状態": "座席登録のみ",
                "_seat_num": pd.to_numeric(_seat_no, errors="coerce"),
            })

    st.markdown("#### 表示中コマの予定と座席")
    if display_rows:
        _display_df = pd.DataFrame(display_rows)
        _display_df = _display_df.sort_values(by=["_seat_num", "生徒"], na_position="last")
        _show_cols = ["席", "生徒", "種別", "状態"]

        def _highlight_top_seat_status(row):
            _seat = str(row.get("席", "")).strip()
            _status = str(row.get("状態", "")).strip()
            if _seat == "⚠ 未配置":
                return ["background-color: #ffe5e5; color: #8a1f1f; font-weight: 700"] * len(row)
            if _status == "座席登録のみ":
                return ["background-color: #fff7d6; color: #7a5200; font-weight: 700"] * len(row)
            if "確認" in _status:
                return ["background-color: #fff7d6; color: #7a5200; font-weight: 700"] * len(row)
            if "キャンセル済み" in _status:
                return ["background-color: #eeeeee; color: #666666; text-decoration: line-through"] * len(row)
            return [""] * len(row)

        st.dataframe(
            _display_df[_show_cols].style.apply(_highlight_top_seat_status, axis=1),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("このコマの予定はありません。")
    
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



        # 座席登録の候補生徒を、今日の予定だけでなく
        # 月スケジュール / 例外追加・時間変更 / 既存座席登録 まで含めて広めに集める。
        # 振替・当日追加の生徒が候補に出ない事故を防ぐ。
        seat_plan_today = build_daily_plan_for_date(
            dt.date.today(),
            students,
            student_schedule,
            monthly_schedule,
            schedule_overrides,
            timeslots,
            include_inactive=False,
        )

        today_student_ids = set()
        today_slot_student_ids = set()
        seat_register_slot_norm = normalize_slot(seat_register_slot)

        # 1) 共通ロジックで作った「今日の予定」
        if not seat_plan_today.empty and "student_id" in seat_plan_today.columns:
            _plan_today = seat_plan_today.copy()
            _plan_today["student_id"] = _plan_today["student_id"].astype(str).str.strip()
            if "slot" in _plan_today.columns:
                _plan_today["slot"] = _plan_today["slot"].astype(str).str.strip().map(normalize_slot)
            today_student_ids |= set(_plan_today["student_id"].tolist())
            if "slot" in _plan_today.columns:
                today_slot_student_ids |= set(
                    _plan_today.loc[
                        _plan_today["slot"] == seat_register_slot_norm,
                        "student_id",
                    ].tolist()
                )

        # 2) 保存済みの月スケジュール（その日の確定予定）
        if not monthly_schedule.empty:
            _ms = monthly_schedule.copy()
            for _c in ["date", "student_id", "slot"]:
                if _c not in _ms.columns:
                    _ms[_c] = ""
                _ms[_c] = _ms[_c].fillna("").astype(str).str.strip()
            _ms["slot"] = _ms["slot"].map(normalize_slot)
            _ms_day = _ms[_ms["date"] == today].copy()
            if not _ms_day.empty:
                today_student_ids |= set(_ms_day["student_id"].tolist())
                today_slot_student_ids |= set(
                    _ms_day.loc[_ms_day["slot"] == seat_register_slot_norm, "student_id"].tolist()
                )

        # 3) その日の例外（追加 / 時間変更 / 振替）
        if not schedule_overrides.empty:
            _ov = schedule_overrides.copy()
            for _c in ["date", "student_id", "slot", "action"]:
                if _c not in _ov.columns:
                    _ov[_c] = ""
                _ov[_c] = _ov[_c].fillna("").astype(str).str.strip()
            _ov["slot"] = _ov["slot"].map(normalize_slot)
            _ov["action_norm"] = _ov["action"].map(normalize_action_value)
            _ov_day = _ov[
                (_ov["date"] == today)
                & (_ov["action_norm"].isin(["追加", "時間変更"]))
            ].copy()
            if not _ov_day.empty:
                today_student_ids |= set(_ov_day["student_id"].tolist())
                today_slot_student_ids |= set(
                    _ov_day.loc[_ov_day["slot"] == seat_register_slot_norm, "student_id"].tolist()
                )

        # 4) すでに登録するコマに座席登録済みの生徒も候補に残す
        if not registration_today_seats.empty and "student_id" in registration_today_seats.columns:
            _seat_ids = set(
                registration_today_seats["student_id"].astype(str).str.strip().tolist()
            )
            today_student_ids |= _seat_ids
            today_slot_student_ids |= _seat_ids

        today_student_ids = {sid for sid in today_student_ids if sid}
        today_slot_student_ids = {sid for sid in today_slot_student_ids if sid}

        include_all_active_for_seat = st.checkbox(
            "候補に全在籍生徒も含める",
            value=False,
            key=f"seat_include_all_active_{today}_{seat_register_slot}",
            help="振替・追加の生徒が見つからない時に、全在籍生徒からも選べるようにします。",
        )

        active_students_for_seat = students.copy()

        if include_all_active_for_seat:
            pass
        elif today_slot_student_ids:
            active_students_for_seat = active_students_for_seat[
                active_students_for_seat["student_id"].astype(str).str.strip().isin(today_slot_student_ids)
            ].copy()
        elif today_student_ids:
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
            seen_students = set()
            for r in new_seat_rows:
                sid = str(r.get("student_id", "")).strip()
                if not sid:
                    continue
                if sid in seen_students:
                    duplicate_errors.append(f"{seat_register_slot}コマで同じ生徒が複数席に入っています")
                seen_students.add(sid)


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


            st.session_state["seat_display_slot"] = str(target_slot)
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


    # 今日の予定（座席確認用）
    # monthly_schedule.csv がある日は月スケジュールを優先する。
    # 追加・キャンセルの例外も build_daily_plan_for_date 側で反映済み。
    if "seat_plan_today" not in locals():
        seat_plan_today = build_daily_plan_for_date(
            dt.date.today(),
            students,
            student_schedule,
            monthly_schedule,
            schedule_overrides,
            timeslots,
            include_inactive=False,
        )

    if not seat_plan_today.empty:
        for _, r in seat_plan_today.iterrows():
            sid = str(r.get("student_id", "")).strip()
            slot = normalize_slot(r.get("slot", ""))
            if not sid or not slot:
                continue

            if active_student_ids_for_seat and sid not in active_student_ids_for_seat:
                continue

            start = str(r.get("start", "") or "").strip()
            end = str(r.get("end", "") or "").strip()
            if not start and not end:
                start, end = slot_time_map.get(slot, ("", ""))

            seat_today_rows.append({
                "student_id": sid,
                "コマ": slot,
                "start": start,
                "end": end,
                "生徒": student_name_map.get(sid, sid),
                "種別": str(r.get("session_type", "")).strip(),
                "状態": "予定あり",
            })


    # d209: build_daily_plan_for_date に最終的に入らなかった予定ソースも、
    # 座席確認リストでは確認用として表示する。
    # ここに出る場合は、キャンセル・在籍状態・日付/コマ表記のズレなどを確認する。
    seat_cancel_keys_for_today = set()
    if not schedule_overrides.empty:
        _ov_src = schedule_overrides.copy()
        for _c in ["date", "student_id", "slot", "action", "session_type"]:
            if _c not in _ov_src.columns:
                _ov_src[_c] = ""
            _ov_src[_c] = _ov_src[_c].fillna("").astype(str).str.strip()
        _ov_src["slot"] = _ov_src["slot"].map(normalize_slot)
        _ov_src["action_norm"] = _ov_src["action"].map(normalize_action_value)
        seat_cancel_keys_for_today = set(
            zip(
                _ov_src.loc[
                    (_ov_src["date"] == today_str) & (_ov_src["action_norm"] == "キャンセル"),
                    "student_id",
                ].astype(str).str.strip(),
                _ov_src.loc[
                    (_ov_src["date"] == today_str) & (_ov_src["action_norm"] == "キャンセル"),
                    "slot",
                ].astype(str).str.strip(),
            )
        )
    else:
        _ov_src = pd.DataFrame()

    existing_seat_today_keys = set(
        (str(r.get("student_id", "")).strip(), normalize_slot(r.get("コマ", "")))
        for r in seat_today_rows
    )

    def _append_seat_today_candidate(_sid, _slot, _stype, _status):
        _sid = str(_sid).strip()
        _slot = normalize_slot(_slot)
        if not _sid or not _slot:
            return
        # d300:
        # 月スケジュール・例外追加の補足表示経路でも、退会済みは座席確認へ戻さない。
        if _sid not in active_student_ids_for_seat:
            return
        _key = (_sid, _slot)
        if _key in existing_seat_today_keys:
            return
        _start, _end = slot_time_map.get(_slot, ("", ""))
        if _key in seat_cancel_keys_for_today:
            _status = "キャンセル済み（予定から除外）"
        seat_today_rows.append({
            "student_id": _sid,
            "コマ": _slot,
            "start": _start,
            "end": _end,
            "生徒": student_name_map.get(_sid, _sid),
            "種別": str(_stype).strip(),
            "状態": _status,
        })
        existing_seat_today_keys.add(_key)

    if not monthly_schedule.empty:
        _ms_src = monthly_schedule.copy()
        for _c in ["date", "student_id", "slot", "session_type"]:
            if _c not in _ms_src.columns:
                _ms_src[_c] = ""
            _ms_src[_c] = _ms_src[_c].fillna("").astype(str).str.strip()
        _ms_src["slot"] = _ms_src["slot"].map(normalize_slot)
        _ms_src = _ms_src[_ms_src["date"] == today_str].copy()
        for _, _r in _ms_src.iterrows():
            _append_seat_today_candidate(
                _r.get("student_id", ""),
                _r.get("slot", ""),
                _r.get("session_type", ""),
                "月スケジュール確認",
            )

    if not _ov_src.empty:
        _ov_add_src = _ov_src[
            (_ov_src["date"] == today_str)
            & (_ov_src["action_norm"].isin(["追加", "時間変更", "キャンセル"]))
        ].copy()
        for _, _r in _ov_add_src.iterrows():
            _status = "例外追加/変更確認"
            if str(_r.get("action_norm", "")).strip() == "キャンセル":
                _status = "キャンセル済み（予定から除外）"
            _append_seat_today_candidate(
                _r.get("student_id", ""),
                _r.get("slot", ""),
                _r.get("session_type", ""),
                _status,
            )


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
        status_value = str(r.get("状態", "")).strip()

        if "キャンセル済み" in status_value:
            r["席"] = "キャンセル済み"
        else:
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
        sid_for_seat_check = str(row.get("student_id", "")).strip()


        # d254:
        # キャンセル済みの生徒が過去に座席保存されていても、
        # 今日実際に座る対象ではないため、座席重複チェックから除外する。
        if (sid_for_seat_check, slot) in seat_cancel_keys_for_today:
            continue


        if not slot or not seat:
            continue


        key = (slot, seat)


        if key in seat_check:
            duplicate_slots.add(slot)
        else:
            seat_check[key] = True



    for r in seat_today_rows:
        # キャンセル済みの確認行は、未配置アラートには含めない。
        # 表示上の確認には残しても、座席を配置すべき予定ではないため。
        status_value = str(r.get("状態", "")).strip()
        if "キャンセル済み" in status_value:
            continue

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
        # キャンセル済みの確認行は、未配置件数に含めない
        status_value = str(r.get("状態", "")).strip()
        if "キャンセル済み" in status_value:
            continue

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


        show_cols = ["コマ", "start", "end", "席", "生徒", "種別", "状態"]
        show_cols = [c for c in show_cols if c in seat_today_df.columns]


        seat_today_display = seat_today_df[show_cols].copy()


        def highlight_missing_seat(row):
            seat_value = str(row.get("席", "")).strip()
            status_value = str(row.get("状態", "")).strip()
            if "キャンセル済み" in status_value:
                return ["background-color: #eeeeee; color: #666666; text-decoration: line-through"] * len(row)
            if seat_value == "⚠ 未配置":
                return ["background-color: #ffe5e5; color: #8a1f1f; font-weight: 700"] * len(row)
            if "確認" in status_value:
                return ["background-color: #fff7d6; color: #7a5200; font-weight: 700"] * len(row)
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


                # d254:
                # 今日キャンセル済みの生徒の保存済み座席は、自動配置では「空いた席」として扱う。
                # これを除外しないと、キャンセルした人まで席重複・使用中判定に入ってしまう。
                if (_sid, _slot) in seat_cancel_keys_for_today:
                    continue


                if _slot and _seat:
                    existing_keys.add((_slot, _seat))


                if _slot and _sid:
                    existing_student_slot_keys.add((_sid, _slot))


        candidates = {}


        for r in seat_today_rows:
            sid = str(r.get("student_id", "")).strip()
            slot = normalize_slot(r.get("コマ", ""))
            status_value = str(r.get("状態", "")).strip()


            if not sid or not slot:
                continue


            # d254:
            # 座席確認リストにはキャンセル済み行を残すが、
            # 自動配置・基本席の重複判定には含めない。
            if "キャンセル済み" in status_value or (sid, slot) in seat_cancel_keys_for_today:
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


    # 今日の配置表のプルダウン候補を作る
    # d210: ここが古い週次スケジュール寄りだったため、
    # 振替・当日追加・月スケジュールの生徒が出ないことがあった。
    # 今日の予定と同じ build_daily_plan_for_date() を主軸にして、
    # 念のため月スケジュール・例外・既存座席登録も候補に含める。
    today_student_ids_for_grid = set()

    grid_today_date_obj = dt.date.today()
    today_wd_for_grid = ["月", "火", "水", "木", "金", "土", "日"][grid_today_date_obj.weekday()]

    # 1) 最終的な今日の予定（キャンセル反映後）
    grid_plan_today = build_daily_plan_for_date(
        grid_today_date_obj,
        students,
        student_schedule,
        monthly_schedule,
        schedule_overrides,
        timeslots,
        include_inactive=False,
    )

    if not grid_plan_today.empty and "student_id" in grid_plan_today.columns:
        today_student_ids_for_grid |= set(
            grid_plan_today["student_id"].astype(str).str.strip().tolist()
        )

    # 2) monthly_schedule.csv の今日の予定（保険）
    if not monthly_schedule.empty:
        grid_ms = monthly_schedule.copy()

        for c in ["date", "student_id", "slot"]:
            if c not in grid_ms.columns:
                grid_ms[c] = ""
            grid_ms[c] = grid_ms[c].fillna("").astype(str).str.strip()

        grid_ms["slot"] = grid_ms["slot"].map(normalize_slot)
        grid_ms_day = grid_ms[grid_ms["date"] == today].copy()

        # キャンセル済みの student_id × slot は除外する
        cancel_keys_for_grid = set()
        if not schedule_overrides.empty:
            grid_cancel_src = schedule_overrides.copy()
            for c in ["student_id", "date", "slot", "action"]:
                if c not in grid_cancel_src.columns:
                    grid_cancel_src[c] = ""
                grid_cancel_src[c] = grid_cancel_src[c].fillna("").astype(str).str.strip()
            grid_cancel_src["slot"] = grid_cancel_src["slot"].map(normalize_slot)
            grid_cancel_src["action_norm"] = grid_cancel_src["action"].map(normalize_action_value)
            grid_cancel_day = grid_cancel_src[
                (grid_cancel_src["date"] == today)
                & (grid_cancel_src["action_norm"] == "キャンセル")
            ].copy()
            cancel_keys_for_grid = set(
                zip(
                    grid_cancel_day["student_id"].astype(str).str.strip(),
                    grid_cancel_day["slot"].astype(str).str.strip().map(normalize_slot),
                )
            )

        if not grid_ms_day.empty:
            if cancel_keys_for_grid:
                grid_ms_day["student_id_key"] = grid_ms_day["student_id"].astype(str).str.strip()
                grid_ms_day["slot_key"] = grid_ms_day["slot"].astype(str).str.strip().map(normalize_slot)
                grid_ms_day = grid_ms_day[
                    ~grid_ms_day.apply(
                        lambda r: (r.get("student_id_key", ""), r.get("slot_key", "")) in cancel_keys_for_grid,
                        axis=1,
                    )
                ].copy()

            today_student_ids_for_grid |= set(
                grid_ms_day["student_id"].astype(str).str.strip().tolist()
            )

    # 3) schedule_overrides.csv の今日の追加 / 時間変更 / 振替（保険）
    if not schedule_overrides.empty:
        grid_ov = schedule_overrides.copy()

        for c in ["student_id", "date", "slot", "action"]:
            if c not in grid_ov.columns:
                grid_ov[c] = ""
            grid_ov[c] = grid_ov[c].fillna("").astype(str).str.strip()

        grid_ov["slot"] = grid_ov["slot"].map(normalize_slot)
        grid_ov["action_norm"] = grid_ov["action"].map(normalize_action_value)

        grid_extra = grid_ov[
            (grid_ov["date"] == today)
            & (grid_ov["action_norm"].isin(["追加", "時間変更"]))
        ].copy()

        # 同じ student_id × slot にキャンセルがある場合だけ除外する
        grid_cancel = grid_ov[
            (grid_ov["date"] == today)
            & (grid_ov["action_norm"] == "キャンセル")
        ].copy()
        grid_cancel_keys = set(
            zip(
                grid_cancel["student_id"].astype(str).str.strip(),
                grid_cancel["slot"].astype(str).str.strip().map(normalize_slot),
            )
        )

        if not grid_extra.empty and grid_cancel_keys:
            grid_extra["student_id_key"] = grid_extra["student_id"].astype(str).str.strip()
            grid_extra["slot_key"] = grid_extra["slot"].astype(str).str.strip().map(normalize_slot)
            grid_extra = grid_extra[
                ~grid_extra.apply(
                    lambda r: (r.get("student_id_key", ""), r.get("slot_key", "")) in grid_cancel_keys,
                    axis=1,
                )
            ].copy()

        today_student_ids_for_grid |= set(
            grid_extra["student_id"].astype(str).str.strip().tolist()
        )

    # 4) 既に今日の配置表に保存済みの生徒も候補に残す
    #    これを入れないと、候補から外れた生徒が保存時に空席へ戻りやすい。
    if not seat_assignments.empty:
        grid_saved_seats = seat_assignments.copy()

        for c in ["date", "student_id"]:
            if c not in grid_saved_seats.columns:
                grid_saved_seats[c] = ""
            grid_saved_seats[c] = grid_saved_seats[c].fillna("").astype(str).str.strip()

        grid_saved_seats = grid_saved_seats[
            grid_saved_seats["date"].astype(str).str.strip() == today
        ].copy()

        today_student_ids_for_grid |= set(
            grid_saved_seats["student_id"].astype(str).str.strip().tolist()
        )

    today_student_ids_for_grid = {sid for sid in today_student_ids_for_grid if sid}

    # d255:
    # 手動座席登録の候補を、通常は「そのコマに来る予定の子」だけに絞る。
    # ただし例外対応用に、全コマ候補へ切り替えられるようにする。
    grid_slot_student_ids_map = {}
    try:
        if grid_plan_today is not None and not grid_plan_today.empty and {"student_id", "slot"}.issubset(grid_plan_today.columns):
            _gps = grid_plan_today.copy()
            _gps["student_id"] = _gps["student_id"].fillna("").astype(str).str.strip()
            _gps["slot"] = _gps["slot"].fillna("").astype(str).str.strip().map(normalize_slot)
            for _slot, _g in _gps.groupby("slot"):
                _slot = normalize_slot(_slot)
                grid_slot_student_ids_map[_slot] = [
                    _sid for _sid in _g["student_id"].astype(str).str.strip().tolist() if _sid
                ]
    except Exception:
        grid_slot_student_ids_map = {}

    include_all_slots_for_grid = st.checkbox(
        "全コマの生徒も候補に表示する",
        value=False,
        key=f"seat_grid_include_all_slots_{today}",
        help="通常は各コマの予定生徒だけを表示します。別コマの子を手動で入れたい時だけONにします。",
    )

    include_all_active_for_grid = st.checkbox(
        "配置表の候補に全在籍生徒も含める",
        value=False,
        key=f"seat_grid_include_all_active_{today}",
        help="今日の予定・振替・追加の候補に出ない生徒がいる場合だけONにします。",
    )

    grid_students = students.copy()

    if include_all_active_for_grid:
        pass
    elif today_student_ids_for_grid:
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

    # d255:
    # コマ別候補を作るための元リスト。
    # ここには「今日来る予定の全候補」または「全在籍生徒も含めた候補」が入る。
    grid_all_candidate_ids = list(grid_student_ids)

    def build_seat_options_for_slot(slot_value, current_sid_value="", saved_sid_value=""):
        """
        通常はそのコマの予定生徒だけを候補に出す。
        ただし、空席・使用予定・保存済み/選択中の生徒は必ず候補に残す。
        """
        slot_value = normalize_slot(slot_value)
        current_sid_value = str(current_sid_value or "").strip()
        saved_sid_value = str(saved_sid_value or "").strip()

        if include_all_slots_for_grid or include_all_active_for_grid:
            base_ids = list(grid_all_candidate_ids)
        else:
            slot_ids = grid_slot_student_ids_map.get(slot_value, [])
            base_ids = ["", "__RESERVED__"]
            for _sid in slot_ids:
                _sid = str(_sid).strip()
                if _sid and _sid in grid_student_labels and _sid not in base_ids:
                    base_ids.append(_sid)

        for _sid in [saved_sid_value, current_sid_value]:
            _sid = str(_sid).strip()
            if _sid and _sid in grid_student_labels and _sid not in base_ids:
                base_ids.append(_sid)

        ordered = []
        for _sid in ["", "__RESERVED__"]:
            if _sid in base_ids and _sid not in ordered:
                ordered.append(_sid)
        for _sid in base_ids:
            if _sid not in ordered:
                ordered.append(_sid)

        return ordered
            
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


            saved_sid = str(existing_grid.get((slot, seat_no), "")).strip()
            slot_candidate_ids = build_seat_options_for_slot(
                slot_value=slot,
                current_sid_value=current_sid,
                saved_sid_value=saved_sid,
            )
            default_index = slot_candidate_ids.index(current_sid) if current_sid in slot_candidate_ids else 0


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
                    slot_candidate_ids,
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
