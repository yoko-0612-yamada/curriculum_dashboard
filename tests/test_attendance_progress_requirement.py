"""Progress requires an actual lesson, independently of row order or view mode."""
from datetime import date,timedelta
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import RegressionCase
from . import test_progress_ui as fixtures

class RequirementTests(RegressionCase):
    def test_all_kinds_and_order_are_independent(self):
        for kinds,expected in [(['lesson'],True),(['selfstudy'],False),(['absence'],False),(['cancel'],False),(['lesson','selfstudy'],True),(['selfstudy','lesson'],True),(['lesson','absence'],True),(['cancel','lesson'],True),([' 自習 ',' 授業 '],True),(['present'],True)]:
            with self.subTest(kinds=kinds):
                df=pd.DataFrame([dict(student_id=' S ',date='2026-10-20',kind=k) for k in kinds])
                before=df.copy(deep=True)
                self.assertEqual(self.call('attendance_requires_progress',df,'S',date(2026,10,20)),expected)
                self.assertFalse(self.call('attendance_requires_progress',df,'OTHER',date(2026,10,20)))
                self.assertFalse(self.call('attendance_requires_progress',df,'S',date(2026,10,21)))
                pd.testing.assert_frame_equal(df,before)

    def test_empty_and_prepared_frame(self):
        self.assertFalse(self.call('attendance_requires_progress',pd.DataFrame(),'S',date.today()))
        df=pd.DataFrame([dict(student_id='S',date='2026-10-20',kind='selfstudy'),dict(student_id='S',date='2026-10-20',kind='lesson')])
        self.assertTrue(self.call('attendance_requires_progress',df,'S',date(2026,10,20),normalized=True))
        self.assertFalse(self.call('attendance_requires_progress',df.drop(columns='kind'),'S',date(2026,10,20)))

class RequirementUiTests(unittest.TestCase):
    def launch(self):
        f=fixtures.ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        today=date.today();past=today-timedelta(days=1)
        cases={'L':['lesson'],'N':['lesson'],'K':['lesson'],'SK':['lesson'],'S':['selfstudy'],
               'A':['absence'],'C':['cancel'],'M1':['lesson','selfstudy'],'M2':['selfstudy','lesson'],
               'MA':['lesson','absence'],'FALSE':['lesson']}
        f.write('students.csv',[dict(student_id=s,display_name=s,is_active='true',join_date='2020-01-01') for s in cases])
        f.write('monthly_schedule.csv',[dict(student_id=s,date=str(d),slot=str(i),session_type=t) for s in cases for d in [past,today] for i,t in [(1,'授業'),(2,'自習')]])
        f.write('attendance_log.csv',[dict(student_id=s,date=str(d),kind=k) for s,ks in cases.items() for d in [past,today] for k in ks])
        f.write('curriculum_progress.csv',[dict(student_id=s,course_id='DEMO_C01',task_id='DEMO_T01',is_done=done,done_date=str(today)) for s,done in [('N','true'),('FALSE','false')]])
        f.write('kentei_progress.csv',[dict(student_id='K',grade='4',task_id='DEMO_K01',is_done='true',done_date=str(today))])
        f.write('progress_skip_ok.csv',[dict(student_id='SK',date=str(d),note='保持') for d in [past,today]])
        protected={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in [f.data/n for n in ['attendance_log.csv','curriculum_progress.csv','kentei_progress.csv','progress_skip_ok.csv','monthly_schedule.csv']]}
        # Observe local results in the isolated app, without changing their logic.
        src=f.app.read_text().replace('    overdue_df = pd.DataFrame(overdue_rows)',
            '    st.session_state["audit_unfinished"] = (today_rows, overdue_rows)\n    overdue_df = pd.DataFrame(overdue_rows)',1)
        src=src.replace('                pending_count = len(pending_ids)',
            '                st.session_state["audit_missing"] = missing_progress_ids\n                pending_count = len(pending_ids)',1)
        src=src.replace('        # 次に見る候補',
            '        # 次に見る候補',1)
        needle='        next_candidates = today_view.copy()'
        src=src.replace(needle,'        st.session_state["audit_status"] = today_view[["student_id", "進捗完了"]].to_dict("records")\n'+needle,1)
        f.app.write_text(src)
        at=AppTest.from_file(str(f.app),default_timeout=60);at.session_state['auth_ok']=True
        return f,at,protected,past,today

    def assert_consistent(self,at,expected,past,today):
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        summary=next(m.value for m in at.markdown if '最終確認｜今日の入力状況' in m.value)
        self.assertIn(f'進捗 {len(expected)} /',summary)
        self.assertEqual(set(at.session_state['audit_missing']),expected)
        self.assertEqual({r['student_id'] for r in at.session_state['audit_status'] if not r['進捗完了']},expected)
        current,previous=at.session_state['audit_unfinished']
        self.assertEqual({r['student_id'] for r in current},expected)
        if past.month==today.month:
            self.assertEqual({r['student_id'] for r in previous if r['日付']==str(past)},expected)

    def test_all_views_and_past_rules_match(self):
        f,at,protected,past,today=self.launch();expected={'L','M1','M2','MA','FALSE'}
        self.assert_consistent(at,expected,past,today)
        at.radio(key='daily_input_mode').set_value('進捗登録')
        self.assert_consistent(at,expected,past,today)
        at.radio(key='view_mode_group').set_value('たまに見る：確認・一覧')
        self.assert_consistent(at,expected,past,today)
        for p,state in protected.items():self.assertEqual((p.read_bytes(),p.stat().st_mtime_ns),state)

    def test_self_only_no_alert_even_with_lesson_plans(self):
        f,at,_,past,today=self.launch()
        f.write('attendance_log.csv',[dict(student_id=s,date=str(d),kind='selfstudy') for s in ['L','N','K','SK','S','A','C','M1','M2','MA','FALSE'] for d in [past,today]])
        self.assert_consistent(at,set(),past,today)
        self.assertFalse(any('最優先：進捗未登録' in m.value for m in at.markdown))
