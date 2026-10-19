"""Attendance-card-only lazy rendering; common safety work stays active."""
from datetime import date, timedelta
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class InputModeTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        self.f = ProgressUiTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.day = str(date.today()); self.sid = 'DEMO001'
        self.f.write('monthly_schedule.csv', [dict(student_id=self.sid, date=self.day, slot='1', session_type='授業', reason='通常')])
        self.f.write('timeslots.csv', [dict(slot='1',start_time='15:00',end_time='16:00')])
        self.at = AppTest.from_file(str(self.f.app), default_timeout=40)
        self.at.session_state['auth_ok'] = True

    def run_view(self):
        self.at.run(); self.assertFalse(self.at.exception)

    def mode(self, value):
        self.at.radio(key='daily_input_mode').set_value(value).run()
        self.assertFalse(self.at.exception)

    def test_cards_only_hidden_common_warnings_sync_and_hints_remain(self):
        self.f.write('attendance_log.csv',[dict(student_id=self.sid,date=self.day,kind='lesson')])
        self.f.write('kentei_exam_schedule.csv',[dict(student_id=self.sid,grade='4',exam_date=str(date.today()-timedelta(days=1)))])
        self.f.write('sub_curricula.csv',[dict(sub_id='S',sub_name='サブ',is_active='true')])
        self.f.write('sub_curriculum_items.csv',[dict(sub_id='S',item_id='I',item_name='項目',order=1,is_active='true')])
        self.f.write('student_sub_progress.csv',[dict(student_id=self.sid,sub_id='S',current_item_id='I',is_active='true')])
        self.at.session_state['daily_input_mode']='進捗登録'
        self.at.session_state['sidebar_student']='テスト生徒01（架空）'
        self.run_view()
        self.assertTrue(pd.read_csv(self.f.data/'sub_daily_check.csv').status.eq('pending').any())
        self.assertFalse(any(str(b.key).startswith('att_save_') for b in self.at.button))
        self.assertFalse(any(str(w.key).startswith('att_kind_') for w in self.at.selectbox))
        self.assertTrue(any('検定結果未登録' in w.value for w in self.at.warning))
        self.assertTrue(any('未完了' in w.value for w in self.at.warning))
        summary=next(m.value for m in self.at.markdown if '最終確認｜今日の入力状況' in m.value)
        self.assertIn('タイピング',summary)
        self.assertTrue(any(str(b.key).startswith('typing_done_') for b in self.at.button))
        hints=dict(self.at.session_state['today_task_hint_map'])
        self.mode('出席登録')
        self.assertEqual(dict(self.at.session_state['today_task_hint_map']),hints)
        self.mode('進捗登録')
        self.f.write('kentei_exam_schedule.csv',[])
        # Keep the selected student without entering the unrelated empty-course input selector.
        self.at.radio(key='view_mode_trial').set_value('検定課題').run()
        courses=pd.read_csv(self.f.data/'curriculum_courses.csv');courses['is_active']='false';courses.to_csv(self.f.data/'curriculum_courses.csv',index=False)
        self.run_view();self.assertEqual(dict(self.at.session_state['today_task_hint_map']),{})
        self.mode('出席登録');self.assertEqual(dict(self.at.session_state['today_task_hint_map']),{})

    def test_attendance_save_jumps_to_progress_normal_and_exam(self):
        for training in [False,True]:
            with self.subTest(training=training):
                self.f.write('attendance_log.csv',[])
                self.f.write('kentei_training_status.csv',[dict(student_id=self.sid,grade='4',is_training='true')] if training else [])
                self.at.session_state['daily_input_mode']='出席登録'
                self.run_view()
                self.assertTrue(any(b.key==f'att_save_{self.day}_{self.sid}' for b in self.at.button))
                self.at.checkbox(key=f'att_open_after_save_{self.day}').check().run()
                self.at.button(key=f'att_save_{self.day}_{self.sid}').click().run()
                self.assertFalse(self.at.exception)
                self.assertEqual(self.at.radio(key='daily_input_mode').value,'進捗登録')
                self.assertEqual(self.at.radio(key='view_mode_trial').value,'検定課題' if training else 'カリキュラム課題')
                self.assertEqual(self.at.selectbox(key='sidebar_student').value,'テスト生徒01（架空）')
                self.assertFalse(any(str(b.key).startswith('att_save_') for b in self.at.button))
                self.assertTrue(pd.read_csv(self.f.data/'attendance_log.csv').student_id.eq(self.sid).any())

    def test_unsaved_attendance_reset_progress_retained_and_saved(self):
        self.at.session_state['sidebar_student']='テスト生徒01（架空）'
        self.run_view()
        self.assertEqual(self.at.radio(key='daily_input_mode').value,'出席登録')
        memo=f'att_memo_{self.day}_{self.sid}'
        self.at.text_input(key=memo).set_value('未保存メモ').run()
        self.at.selectbox(key=f'att_lesson_count_d410_{self.day}_{self.sid}').set_value(2).run()
        normal='curr_state_DEMO001_DEMO_C01_DEMO_T01'
        self.at.selectbox(key=normal).set_value('完了').run()
        self.mode('進捗登録')
        self.assertEqual(self.at.selectbox(key=normal).value,'完了')
        self.mode('出席登録');self.assertEqual(self.at.text_input(key=memo).value,'')
        self.assertEqual(self.at.selectbox(key=normal).value,'完了')
        self.assertEqual(self.at.selectbox(key=f'att_lesson_count_d410_{self.day}_{self.sid}').value,1)
        self.at.selectbox(key=f'att_kind_{self.day}_{self.sid}').set_value('自習').run()
        self.mode('進捗登録');self.mode('出席登録')
        self.assertEqual(self.at.selectbox(key=f'att_kind_{self.day}_{self.sid}').value,'授業')
        self.mode('進捗登録')
        next(b for b in self.at.button if b.label=='💾 保存（カリキュラム課題）').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(pd.read_csv(self.f.data/'curriculum_progress.csv').is_done.astype(str).str.lower().eq('true').any())
        self.at.radio(key='view_mode_trial').set_value('検定課題').run()
        self.at.selectbox(key='kentei_state_DEMO001_4_DEMO_K01').set_value('完了').run()
        self.mode('出席登録');self.mode('進捗登録')
        self.assertEqual(self.at.selectbox(key='kentei_state_DEMO001_4_DEMO_K01').value,'完了')
        next(b for b in self.at.button if b.label=='💾 保存（検定課題）').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(pd.read_csv(self.f.data/'kentei_progress.csv').is_done.astype(str).str.lower().eq('true').any())
        self.at.radio(key='view_mode_group').set_value('たまに見る：確認・一覧').run()
        self.assertFalse(any(w.key=='daily_input_mode' for w in self.at.radio))
