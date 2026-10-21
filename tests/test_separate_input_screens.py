"""Input modes render only their own controls; shared safeguards remain."""
from datetime import date, timedelta
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class SeparateInputScreensTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        self.f = ProgressUiTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.day = str(date.today())
        self.sid = 'DEMO001'
        self.f.write('monthly_schedule.csv', [
            dict(student_id=self.sid, date=self.day, slot='1', session_type='授業')
        ])
        self.f.write('timeslots.csv', [dict(slot='1', start_time='15:00', end_time='16:00')])
        self.at = AppTest.from_file(str(self.f.app), default_timeout=40)
        self.at.session_state['auth_ok'] = True
        self.at.session_state['sidebar_student'] = 'テスト生徒01（架空）'

    def run_view(self):
        self.at.run()
        self.assertFalse(self.at.exception, [e.message for e in self.at.exception])

    def mode(self, mode):
        self.at.radio(key='daily_input_mode').set_value(mode)
        self.run_view()

    def keys(self):
        return [str(w.key) for kind in
                ['button', 'checkbox', 'selectbox', 'radio', 'text_input', 'number_input']
                for w in getattr(self.at, kind)]

    def test_exclusive_controls_and_shared_safety(self):
        self.f.write('attendance_log.csv', [dict(student_id=self.sid, date=self.day, kind='lesson')])
        self.f.write('kentei_exam_schedule.csv', [
            dict(student_id=self.sid, grade='4', exam_date=str(date.today()-timedelta(days=1)))
        ])
        self.f.write('sub_curricula.csv', [dict(sub_id='S', sub_name='サブ', is_active='true')])
        self.f.write('sub_curriculum_items.csv', [
            dict(sub_id='S', item_id='I', item_name='項目', order=1, is_active='true')
        ])
        self.f.write('student_sub_progress.csv', [
            dict(student_id=self.sid, sub_id='S', current_item_id='I', is_active='true')
        ])
        self.at.session_state[f'att_show_done_{self.day}'] = True
        self.run_view()
        self.assertIn(f'att_save_{self.day}_{self.sid}', self.keys())
        self.assertIn(f'prep_done_{self.day}_{self.sid}', self.keys())
        self.assertNotIn('view_mode_trial', self.keys())
        self.assertFalse([k for k in self.keys() if k.startswith(
            ('curr_state_', 'kentei_state_', 'sub_progress_', 'sub_daily_done_', 'typing_done_', 'no_progress_done_'))])
        summary = next(m.value for m in self.at.markdown if '最終確認｜今日の入力状況' in m.value)
        self.assertTrue(any('検定結果未登録' in w.value for w in self.at.warning))
        self.assertTrue(pd.read_csv(self.f.data/'sub_daily_check.csv').status.eq('pending').any())
        self.mode('進捗登録')
        self.assertEqual(summary, next(m.value for m in self.at.markdown if '最終確認｜今日の入力状況' in m.value))
        self.assertFalse([k for k in self.keys() if k.startswith(
            ('att_save_', 'att_kind_', 'att_memo_', 'att_lesson_count_', 'prep_done_'))])
        self.assertTrue(any(k.startswith('curr_state_') for k in self.keys()))
        self.assertTrue(any(k.startswith('sub_progress_next_') for k in self.keys()))
        self.assertTrue(any(k.startswith('typing_done_') for k in self.keys()))
        self.assertTrue(any('検定結果未登録' in w.value for w in self.at.warning))

    def test_progress_drafts_survive_hidden_widgets_and_save(self):
        self.at.session_state['daily_input_mode'] = '進捗登録'
        self.run_view()
        normal = 'curr_state_DEMO001_DEMO_C01_DEMO_T01'
        self.at.selectbox(key=normal).set_value('完了').run()
        self.mode('出席登録')
        self.assertNotIn(normal, self.keys())
        self.mode('進捗登録')
        self.assertEqual(self.at.selectbox(key=normal).value, '完了')
        next(b for b in self.at.button if b.label == '💾 保存（カリキュラム課題）').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(pd.read_csv(self.f.data/'curriculum_progress.csv').is_done.astype(str).str.lower().eq('true').any())
        self.at.radio(key='view_mode_trial').set_value('検定課題').run()
        exam = 'kentei_state_DEMO001_4_DEMO_K01'
        self.at.selectbox(key=exam).set_value('完了').run()
        self.mode('出席登録')
        self.assertNotIn(exam, self.keys())
        self.mode('進捗登録')
        self.assertEqual(self.at.radio(key='view_mode_trial').value, '検定課題')
        self.assertEqual(self.at.selectbox(key=exam).value, '完了')
        next(b for b in self.at.button if b.label == '💾 保存（検定課題）').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(pd.read_csv(self.f.data/'kentei_progress.csv').is_done.astype(str).str.lower().eq('true').any())

    def test_attendance_save_navigates_to_progress(self):
        self.run_view()
        self.at.checkbox(key=f'att_open_after_save_{self.day}').check().run()
        self.at.button(key=f'att_save_{self.day}_{self.sid}').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.radio(key='daily_input_mode').value, '進捗登録')
        self.assertTrue(any(k.startswith('curr_state_') for k in self.keys()))
        self.assertFalse(any(k.startswith('att_save_') for k in self.keys()))
        self.assertEqual(self.at.selectbox(key='sidebar_student').value, 'テスト生徒01（架空）')

    def test_no_progress_confirmation_is_a_progress_operation(self):
        self.run_view()
        self.assertFalse([k for k in self.keys() if
                          k.startswith('no_progress_done_') or '_no_progress_' in k])
        self.at.button(key=f'att_save_{self.day}_{self.sid}').click().run()
        self.assertFalse(self.at.exception)
        self.mode('進捗登録')
        buttons = [b for b in self.at.button if '_no_progress_' in str(b.key)]
        self.assertTrue(buttons)
        buttons[0].click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(pd.read_csv(self.f.data/'progress_skip_ok.csv').student_id.eq(self.sid).any())
        self.assertFalse(any(k.startswith('att_save_') for k in self.keys()))
