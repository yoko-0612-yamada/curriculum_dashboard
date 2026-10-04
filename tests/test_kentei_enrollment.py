import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class KenteiEnrollmentTests(RegressionCase):
    def test_dates_legacy_zero_and_errors(self):
        for join,leave,active,count in [('2026-10-02','','true',0),('2026-10-01','','false',1),('', '2026-10-01','false',1),('', '2026-09-30','true',0),('2020-01-01','','true',1),('','','true',1),('','','false',0),('bad','','true',0),('2026-11-01','2026-10-01','true',0)]:
            with self.subTest(join=join,leave=leave):
                rows=pd.DataFrame([dict(student_id='S',join_date=join,leave_date=leave,is_active=active)])
                before=rows.copy(deep=True)
                self.assertEqual(len(self.call('kentei_entry_students',rows,'2026-10-01')),count)
                pd.testing.assert_frame_equal(rows,before)
        self.assertEqual(len(self.messages),2)


class KenteiEnrollmentUiTests(unittest.TestCase):
    def fixture(self,join,leave,active='true'):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        f.write('students.csv',[dict(student_id='DEMO001',display_name='架空',is_active=active,join_date=join,leave_date=leave)])
        return f

    def launch(self,f,admin=False):
        at=AppTest.from_file(str(f.app),default_timeout=40)
        at.session_state['auth_ok']=True
        if admin:
            at.session_state['page_state']='管理（入力）'
            at.session_state['admin_section_selector']='🎫 検定予定登録'
        else:
            at.session_state['include_inactive']=True
            active=pd.read_csv(f.data/'students.csv',dtype=str).iloc[0].is_active
            at.session_state['sidebar_student']='架空（退会）' if active=='false' else '架空'
            at.session_state['sidebar_view_mode']='検定課題'
            at.session_state['override_done_lock']=True
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        return at

    def test_retired_progress_results_training_history_and_result_date(self):
        past=dt.date.today()-dt.timedelta(days=1)
        f=self.fixture('2020-01-01',str(past),'false')
        f.write('kentei_progress.csv',[dict(student_id='DEMO001',grade='4',task_id='DEMO_K01',is_done='true',done_date=str(past))])
        f.write('kentei_results.csv',[dict(student_id='DEMO001',grade='3',result='不合格',pass_date=str(past),score='30',memo='履歴保持')])
        paths=[f.data/name for name in ['kentei_progress.csv','kentei_results.csv','kentei_training_status.csv']]
        before=[(p.read_bytes(),p.stat().st_mtime_ns) for p in paths]
        at=self.launch(f)
        self.assertEqual(at.selectbox(key='kentei_state_DEMO001_4_DEMO_K01').value,'完了')
        self.assertTrue(at.checkbox(key='kentei_training_flag_DEMO001').disabled)
        self.assertTrue(at.button(key='pass_add_btn').disabled)
        at.date_input(key='pass_new_date').set_value(past).run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertFalse(at.button(key='pass_add_btn').disabled)
        self.assertEqual([(p.read_bytes(),p.stat().st_mtime_ns) for p in paths],before)

    def test_exam_date_candidates_and_saved_future_schedule(self):
        today=dt.date.today();future=today+dt.timedelta(days=1)
        f=self.fixture('2020-01-01',str(today))
        f.write('kentei_exam_schedule.csv',[dict(student_id='DEMO001',grade='4',exam_date=str(future),date=str(future),exam_type='検定',kentei='検定',note='保持')])
        path=f.data/'kentei_exam_schedule.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
        at=self.launch(f,admin=True)
        self.assertEqual(at.selectbox(key='kentei_exam_new_student').options,['DEMO001 | 架空'])
        at.date_input(key='kentei_exam_new_date').set_value(future).run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertEqual(at.selectbox(key='kentei_exam_new_student').options,[])
        self.assertEqual(len(at.selectbox(key='kentei_exam_batch_selected').options),1)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)

    def test_new_progress_blocked_before_join_and_after_leave(self):
        today=dt.date.today()
        for join,leave in [(str(today+dt.timedelta(days=1)),''),('',str(today-dt.timedelta(days=1)))]:
            f=self.fixture(join,leave)
            try:
                at=self.launch(f)
                self.assertNotIn('kentei_state_DEMO001_4_DEMO_K01',{w.key for w in at.selectbox})
                self.assertTrue(next(b for b in at.button if b.label=='💾 保存（検定課題）').disabled)
            finally:f.doCleanups()
