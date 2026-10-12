"""Saved sub-task pending rows are history, not new enrollment candidates."""
import datetime as dt
import unittest
from streamlit.testing.v1 import AppTest


class SubPendingHistoryTests(unittest.TestCase):
    def test_summary_and_list_include_all_saved_pending_without_writes(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        today = dt.date.today()
        f.write('students.csv', [
            dict(student_id='ACTIVE', display_name='在籍', is_active='true'),
            dict(student_id='LEFT', display_name='退会済み', is_active='true', join_date=str(today-dt.timedelta(days=30)), leave_date=str(today-dt.timedelta(days=1))),
            dict(student_id='LEGACY', display_name='旧退会', is_active='false'),
        ])
        ids = ['ACTIVE', 'LEFT', 'LEGACY', 'MISSING']
        f.write('sub_daily_check.csv', [
            dict(date=str(today-dt.timedelta(days=offset)), student_id=sid, sub_id='SUB', item_id='ITEM', status=' pending ', note='保持')
            for offset in [0, 1] for sid in ids
        ] + [dict(date=str(today+dt.timedelta(days=1)), student_id='MISSING', status='pending'),
             dict(date=str(today), student_id='DONE', status='done'),
             dict(date=str(today), student_id='SKIP', status='skip')])
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True
        at.run()
        self.assertFalse(at.exception)
        summary = next(m.value for m in at.markdown if '最終確認｜今日の入力状況' in m.value)
        self.assertIn('サブ 4 /', summary)
        self.assertIn('前日以前の確認漏れ 4件（サブ 4 /', summary)
        self.assertIn('その他の日付）：1件', summary)
        self.assertTrue(any(e.label == '🧩 サブ課題確認未（9件）' for e in at.expander))
        buttons = [b for b in at.button if str(b.key).startswith('sub_daily_done_')]
        self.assertEqual(len(buttons), 9)
        for sid in ids:
            self.assertEqual(sum(f'_{sid}_' in b.key for b in buttons), 3 if sid=='MISSING' else 2)
        self.assertTrue(any('MISSING | （マスタ未登録）' in m.value for m in at.markdown))
        at.checkbox(key='include_inactive').check().run()
        self.assertEqual(len([b for b in at.button if str(b.key).startswith('sub_daily_done_')]), 9)
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)
