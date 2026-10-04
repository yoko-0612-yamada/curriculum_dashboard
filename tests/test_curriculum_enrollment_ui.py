"""Enrollment only gates new ordinary progress; saved corrections stay usable."""
import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class CurriculumEnrollmentUiTests(unittest.TestCase):
    def fixture(self,join,leave,active='true'):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        f.write('students.csv',[dict(student_id='DEMO001',display_name='架空',is_active=active,join_date=join,leave_date=leave)])
        return f

    def launch(self,f):
        at=AppTest.from_file(str(f.app),default_timeout=40)
        active=pd.read_csv(f.data/'students.csv',dtype=str).iloc[0]['is_active']
        label='架空（退会）' if active=='false' else '架空'
        for k,v in dict(auth_ok=True,include_inactive=True,sidebar_student=label,sidebar_view_mode='カリキュラム課題',override_done_lock=True).items():at.session_state[k]=v
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        return at

    def test_new_entry_boundaries_legacy_zero_and_invalid(self):
        today=dt.date.today();past=today-dt.timedelta(days=1);future=today+dt.timedelta(days=1)
        for j,l,a,expected,error in [(str(future),'','true',False,False),(str(today),'','true',True,False),('',str(today),'true',True,False),('',str(past),'true',False,False),('2020-01-01','','true',True,False),('','','true',True,False),('','','false',False,False),('bad','','true',False,True),(str(future),str(past),'true',False,True)]:
            with self.subTest(join=j,leave=l,active=a):
                f=self.fixture(j,l,a)
                try:
                    path=f.data/'curriculum_progress.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
                    at=self.launch(f)
                    self.assertEqual('curr_state_DEMO001_DEMO_C01_DEMO_T01' in {w.key for w in at.selectbox},expected)
                    if error:self.assertTrue(any('通常進捗の新規入力候補' in e.value for e in at.error))
                    self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
                finally:f.doCleanups()

    def test_retired_history_and_past_date_correction_remain(self):
        past=dt.date.today()-dt.timedelta(days=2)
        f=self.fixture('2020-01-01',str(past),'false')
        f.write('curriculum_progress.csv',[dict(student_id='DEMO001',course_id='DEMO_C01',task_id='DEMO_T01',is_done='true',done_date=str(past),recorded_at='2026-01-01 12:00:00',note='保持')])
        at=self.launch(f)
        self.assertEqual(at.selectbox(key='curr_state_DEMO001_DEMO_C01_DEMO_T01').value,'完了')
        self.assertNotIn('curr_state_DEMO001_DEMO_C01_DEMO_T02',{w.key for w in at.selectbox})
        corrected=past-dt.timedelta(days=1)
        at.date_input(key='correct_done_date_DEMO001_DEMO_C01_DEMO_T01').set_value(corrected).run()
        at.button(key='save_correct_done_date_DEMO001_DEMO_C01_DEMO_T01').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        saved=pd.read_csv(f.data/'curriculum_progress.csv',dtype=str).fillna('')
        self.assertEqual(saved.done_date.tolist(),[str(corrected)])
        self.assertEqual(saved.recorded_at.tolist(),['2026-01-01 12:00:00'])
        self.assertEqual(saved.note.tolist(),['保持'])
