"""Typing operation scope must not narrow global counts or saved histories."""
from datetime import date, timedelta
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class TypingScopeTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        self.f = ProgressUiTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.today = str(date.today()); self.past = str(date.today() - timedelta(days=1))
        self.f.write('students.csv', [dict(student_id=s, display_name=s, is_active='true') for s in ['A','B','C']])
        self.f.write('monthly_schedule.csv', [dict(student_id=s,date=self.today,slot='1',session_type='授業') for s in ['A','B']])
        self.f.write('attendance_log.csv', [dict(student_id=s,date=d,kind='lesson') for s in ['A','B'] for d in [self.today,self.past]])
        self.at = AppTest.from_file(str(self.f.app), default_timeout=40)
        self.at.session_state['auth_ok'] = True
        self.at.session_state['daily_input_mode'] = '進捗登録'

    def run_view(self):
        self.at.run(); self.assertFalse(self.at.exception)

    def buttons(self):
        return {str(b.key) for b in self.at.button if str(b.key).startswith('typing_')}

    def summary(self):
        return next(m.value for m in self.at.markdown if '最終確認｜今日の入力状況' in m.value)

    def select(self, sid):
        self.at.selectbox(key='sidebar_student').set_value(sid).run(); self.assertFalse(self.at.exception)

    def test_scope_counts_and_attendance_mode(self):
        self.run_view(); baseline = self.summary()
        self.assertFalse(self.buttons())
        for sid in ['A','B']:
            self.select(sid)
            self.assertEqual(self.buttons(), {f'typing_done_{self.today}_{sid}',f'typing_skip_{self.today}_{sid}',f'typing_past_done_{self.past}_{sid}',f'typing_past_skip_{self.past}_{sid}'})
            self.assertEqual(self.summary(), baseline)
        self.select('C'); self.assertFalse(self.buttons())
        self.assertTrue(any('今日のタイピングチェック対象ではありません' in c.value for c in self.at.caption))
        self.at.radio(key='daily_input_mode').set_value('出席登録').run()
        self.assertEqual(len(self.buttons()),8)
        self.assertEqual(self.summary(),baseline)

    def test_saved_states_undo_past_and_history(self):
        self.run_view(); self.select('A')
        self.at.button(key=f'typing_done_{self.today}_A').click().run()
        self.assertFalse(self.at.exception)
        self.assertNotIn(f'typing_done_{self.today}_A',self.buttons())
        self.assertTrue(any('選択生徒のタイピング：✅ 完了' in c.value for c in self.at.caption))
        self.at.checkbox(key=f'typing_show_completed_{self.today}').check().run()
        self.assertIn(f'typing_undo_{self.today}_A',self.buttons())
        self.select('B')
        self.assertNotIn(f'typing_undo_{self.today}_A',self.buttons())
        self.at.button(key=f'typing_skip_{self.today}_B').click().run()
        self.assertTrue(any('選択生徒のタイピング：⚪ 免除' in c.value for c in self.at.caption))
        self.at.checkbox(key=f'typing_show_completed_{self.today}').check().run()
        self.assertEqual({k for k in self.buttons() if k.startswith('typing_undo')},{f'typing_undo_{self.today}_B'})
        self.at.button(key=f'typing_undo_{self.today}_B').click().run()
        self.assertIn(f'typing_done_{self.today}_B',self.buttons())
        self.at.button(key=f'typing_past_done_{self.past}_B').click().run()
        self.assertFalse(self.at.exception)
        saved=pd.read_csv(self.f.data/'typing_log.csv')
        self.assertEqual(set(zip(saved.student_id,saved.date)),{('A',self.today),('B',self.past)})
        # A history-only ID remains in the global saved-history table.
        self.f.write('typing_log.csv',[dict(student_id='ORPHAN',date=self.past,status='skip')])
        self.run_view()
        self.assertTrue(any('student_id' in w.value.columns and 'ORPHAN' in w.value.student_id.astype(str).tolist() for w in self.at.dataframe))

    def test_pause_and_read_failure_keep_data(self):
        self.f.write('typing_log.csv',[dict(student_id='A',date=self.past,status='done')])
        path=self.f.data/'typing_log.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
        pd.DataFrame([dict(feature='typing',pause_start=self.past,resume_date='')]).to_csv(self.f.data/'feature_pause_periods.csv',index=False)
        self.run_view();self.select('A')
        self.assertFalse(self.buttons())
        self.assertEqual(before,(path.read_bytes(),path.stat().st_mtime_ns))
        self.assertTrue(any('タイピングは一時停止中' in i.value for i in self.at.info))
        (self.f.data/'feature_pause_periods.csv').unlink()
        path.write_text('date,student_id\n"broken')
        before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.at.run()
        self.assertFalse(self.buttons())
        self.assertTrue(any('タイピング履歴ファイルを読み込めない' in e.value for e in self.at.error))
        self.assertEqual(before,(path.read_bytes(),path.stat().st_mtime_ns))
