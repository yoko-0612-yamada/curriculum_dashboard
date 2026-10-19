"""Progress-mode detail hints only; global warnings and sync remain global."""
from datetime import date, timedelta
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class HintScopeTests(unittest.TestCase):
    def setUp(self):
        from .test_hint_state_refresh import HintStateRefreshTests
        self.fixture=HintStateRefreshTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.day=self.fixture.day
        self.at=self.fixture.at
        # Only the temporary app is instrumented, no production state/caching.
        src=self.f.app.read_text().replace('if page == "閲覧":','if page == "閲覧":\n    st.session_state["audit_hint_ids"] = []',1)
        marker='                def _today_task_hint(_sid: str, *, results_df=None, training_df=None, active_courses=None) -> str:\n'
        src=src.replace(marker,marker+'                    st.session_state["audit_hint_ids"].append(_sid)\n',1)
        self.f.app.write_text(src)

    def run_view(self):
        self.at.run();self.assertFalse(self.at.exception)
        return dict(self.at.session_state['today_task_hint_map'])

    def test_scope_selection_empty_and_switches(self):
        self.assertEqual(set(self.run_view()),{'A','B'})
        self.assertEqual(self.at.session_state['audit_hint_ids'],['A','B'])
        self.at.radio(key='daily_input_mode').set_value('進捗登録').run()
        self.assertEqual(dict(self.at.session_state['today_task_hint_map']),{})
        self.assertEqual(self.at.session_state['audit_hint_ids'],[])
        for sid in ['A','B']:
            self.at.selectbox(key='sidebar_student').set_value(sid).run()
            self.assertEqual(set(self.at.session_state['today_task_hint_map']),{sid})
            self.assertEqual(self.at.session_state['audit_hint_ids'],[sid])
        self.at.radio(key='daily_input_mode').set_value('出席登録').run()
        self.assertEqual(set(self.at.session_state['today_task_hint_map']),{'A','B'})
        self.at.selectbox(key='sidebar_student').set_value('（全員）').run()
        self.at.radio(key='daily_input_mode').set_value('進捗登録').run()
        self.assertEqual(dict(self.at.session_state['today_task_hint_map']),{})
        self.assertEqual(dict(self.at.session_state['today_sub_hint_map']),{})

    def test_kentei_sub_detail_and_global_checks(self):
        self.f.write('kentei_training_status.csv',[dict(student_id=s,grade='4',is_training='true') for s in ['A','B']])
        self.f.write('kentei_exam_schedule.csv',[dict(student_id='B',grade='4',exam_date=str(date.today()-timedelta(days=1)))])
        self.f.write('attendance_log.csv',[dict(student_id=s,date=self.day,kind='lesson') for s in ['A','B']])
        self.f.write('sub_curricula.csv',[dict(sub_id='SUB',sub_name='サブ',is_active='true')])
        self.f.write('sub_curriculum_items.csv',[dict(sub_id='SUB',item_id='I1',item_name='項目',order=1,is_active='true')])
        self.f.write('student_sub_progress.csv',[dict(student_id=s,sub_id='SUB',current_item_id='I1',is_active='true') for s in ['A','B']])
        self.run_view()
        all_hints=dict(self.at.session_state['today_task_hint_map'])
        self.assertTrue(all(x.startswith('検定：') for x in all_hints.values()))
        self.assertEqual(set(self.at.session_state['today_sub_hint_map']),{'A','B'})
        self.at.selectbox(key='sidebar_student').set_value('A').run()
        self.at.radio(key='daily_input_mode').set_value('進捗登録').run()
        self.assertEqual(dict(self.at.session_state['today_task_hint_map']),{'A':all_hints['A']})
        self.assertEqual(set(self.at.session_state['today_sub_hint_map']),{'A'})
        self.assertTrue(any('検定結果未登録：1件' in w.value for w in self.at.warning))
        daily=pd.read_csv(self.f.data/'sub_daily_check.csv')
        self.assertEqual(set(daily.student_id),{'A','B'})
        self.assertTrue(daily.status.eq('pending').all())
        self.assertTrue(any('サブ課題' in w.value and '2件' in w.value for w in self.at.warning))
        self.assertEqual({b.key for b in self.at.button if str(b.key).startswith('typing_done_')},{f'typing_done_{self.day}_A'})
        self.assertEqual(self.at.session_state['audit_hint_ids'],['A'])
        # No selection must not clear the shared pending records or suppress warnings.
        self.at.selectbox(key='sidebar_student').set_value('（全員）').run()
        self.assertEqual(dict(self.at.session_state['today_sub_hint_map']),{})
        self.assertEqual(set(pd.read_csv(self.f.data/'sub_daily_check.csv').student_id),{'A','B'})

    def test_multiple_slots_keep_priority_and_attendance_jump(self):
        for kinds in [('自習','授業'),('授業','自習')]:
            self.f.write('monthly_schedule.csv',[dict(student_id='A',date=self.day,slot=str(i),session_type=k,reason='通常') for i,k in enumerate(kinds,1)])
            self.at.session_state['daily_input_mode']='出席登録'
            expected=self.run_view()['A']
            self.at.selectbox(key='sidebar_student').set_value('A').run()
            self.at.radio(key='daily_input_mode').set_value('進捗登録').run()
            self.assertEqual(self.at.session_state['today_task_hint_map']['A'],expected)
            self.assertTrue(expected.startswith('通常：'))
        self.f.write('kentei_exam_schedule.csv',[dict(student_id='A',grade='4',exam_date=self.day)])
        self.assertTrue(self.run_view()['A'].startswith('🎫 検定'))
        self.f.write('kentei_exam_schedule.csv',[])
        self.f.write('monthly_schedule.csv',self.fixture.plans)
        self.at.radio(key='daily_input_mode').set_value('出席登録').run()
        self.at.checkbox(key=f'att_open_after_save_{self.day}').check().run()
        self.at.button(key=f'att_save_{self.day}_B').click().run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.radio(key='daily_input_mode').value,'進捗登録')
        self.assertEqual(self.at.selectbox(key='sidebar_student').value,'B')
        self.assertEqual(set(self.at.session_state['today_task_hint_map']),{'B'})
