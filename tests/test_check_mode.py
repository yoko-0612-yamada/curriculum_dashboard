"""Confirmation view keeps global safety information without daily input widgets."""
from datetime import date,timedelta
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class CheckModeTests(unittest.TestCase):
    def setUp(self):
        from .test_hint_state_refresh import HintStateRefreshTests
        self.fxt=HintStateRefreshTests();self.fxt.setUp();self.addCleanup(self.fxt.doCleanups)
        self.f=self.fxt.f;self.at=self.fxt.at;self.day=self.fxt.day
        self.past=str(date.today()-timedelta(days=1))
        self.f.write('attendance_log.csv',[dict(student_id=s,date=self.day,kind='lesson') for s in ['A','B']])
        self.f.write('monthly_schedule.csv',self.fxt.plans+[dict(student_id='A',date=self.past,slot='1',session_type='授業')])
        self.f.write('kentei_exam_schedule.csv',[dict(student_id='B',grade='4',exam_date=self.past)])
        self.f.write('sub_curricula.csv',[dict(sub_id='S',sub_name='サブ',is_active='true')])
        self.f.write('sub_curriculum_items.csv',[dict(sub_id='S',item_id='I',item_name='項目',order=1,is_active='true')])
        self.f.write('student_sub_progress.csv',[dict(student_id=s,sub_id='S',current_item_id='I',is_active='true') for s in ['A','B']])
        src=self.f.app.read_text().replace('if page == "閲覧":','if page == "閲覧":\n    st.session_state["audit_hint_ids"] = []',1)
        marker='                def _today_task_hint(_sid: str, *, results_df=None, training_df=None, active_courses=None) -> str:\n'
        self.f.app.write_text(src.replace(marker,marker+'                    st.session_state["audit_hint_ids"].append(_sid)\n',1))

    def run_view(self):
        self.at.run();self.assertFalse(self.at.exception,[e.message for e in self.at.exception])

    def check(self):
        self.at.radio(key='view_mode_group').set_value('たまに見る：確認・一覧').run()
        self.assertFalse(self.at.exception,[e.message for e in self.at.exception])

    def summary(self):
        return next(m.value for m in self.at.markdown if '最終確認｜今日の入力状況' in m.value)

    def test_check_hides_input_keeps_counts_alerts_sync_and_history(self):
        self.run_view();before=self.summary();self.check()
        self.assertEqual(self.summary(),before)
        self.assertEqual(self.at.session_state['audit_hint_ids'],[])
        self.assertEqual(dict(self.at.session_state['today_task_hint_map']),{})
        self.assertEqual(dict(self.at.session_state['today_sub_hint_map']),{})
        self.assertFalse(any(w.key=='daily_input_mode' for w in self.at.radio))
        prefixes=('att_save_','att_kind_','att_memo_','typing_done_','typing_skip_','typing_past_','typing_undo_','sub_daily_done_','sub_daily_skip_','sub_progress_','curr_state_','kentei_state_','overdue_lesson_','overdue_self_','overdue_absence_','prep_add_')
        for kind in ['button','selectbox','checkbox','text_input','number_input']:
            self.assertFalse([w.key for w in getattr(self.at,kind) if str(w.key).startswith(prefixes)])
        self.assertFalse(any(b.label in ['✅ 完了して次へ','💾 保存（カリキュラム課題）','💾 保存（検定課題）'] for b in self.at.button))
        self.assertTrue(any('検定結果未登録' in w.value for w in self.at.warning))
        self.assertTrue(any('サブ課題確認未' in w.value for w in self.at.warning))
        self.assertTrue(any('未完了タスク（昨日以前）' in w.value for w in self.at.subheader))
        self.assertTrue(any('タイピングの保存済み履歴' in w.label for w in self.at.expander))
        self.assertEqual(set(pd.read_csv(self.f.data/'sub_daily_check.csv').student_id),{'A','B'})

    def test_return_daily_modes_and_progress_save(self):
        self.run_view()
        self.at.selectbox(key='sidebar_student').set_value('A').run()
        self.at.radio(key='daily_input_mode').set_value('進捗登録').run()
        self.check()
        self.at.radio(key='view_mode_group').set_value('毎日使う：進捗登録').run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.radio(key='daily_input_mode').value,'進捗登録')
        self.assertEqual(self.at.selectbox(key='sidebar_student').value,'A')
        self.at.selectbox(key='curr_state_A_C1_C1T').set_value('完了').run()
        next(b for b in self.at.button if b.label=='💾 保存（カリキュラム課題）').click().run()
        self.assertFalse(self.at.exception)
        self.assertTrue(pd.read_csv(self.f.data/'curriculum_progress.csv').student_id.eq('A').any())
        self.at.radio(key='daily_input_mode').set_value('出席登録').run()
        self.at.checkbox(key=f'att_show_done_{self.day}').check().run()
        self.assertTrue(any(str(b.key).startswith('att_save_') for b in self.at.button))

    def test_management_edit_buffer_not_cleared(self):
        self.run_view()
        self.at.session_state['students_batch_edit_df']=pd.DataFrame([dict(student_id='DRAFT',display_name='未保存')])
        expected=self.at.session_state['students_batch_edit_df'].copy()
        self.check()
        pd.testing.assert_frame_equal(self.at.session_state['students_batch_edit_df'],expected)
        self.at.radio(key='page_widget').set_value('管理（入力）').run()
        self.assertFalse(self.at.exception)
        pd.testing.assert_frame_equal(self.at.session_state['students_batch_edit_df'],expected)
