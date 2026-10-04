"""Today's new candidates change; saved records and past corrections do not."""
import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class PastAttendanceTests(RegressionCase):
    def test_past_record_can_be_corrected_without_touching_other_dates(self):
        past=dt.date(2026,9,1)
        rows=pd.DataFrame([dict(date=str(past),student_id='S1',kind='lesson',memo='旧記録'),
                           dict(date='2026-09-02',student_id='S1',kind='lesson',memo='別日')])
        original=rows.copy(deep=True)
        result=self.call('upsert_attendance',rows,'S1',past,'self',memo='訂正')
        self.call('save_attendance_log',result)
        saved=pd.read_csv(self.ns['ATTENDANCE_LOG_CSV'],dtype=str).fillna('')
        self.assertEqual(saved.loc[saved.date==str(past),'kind'].tolist(),['self'])
        self.assertEqual(saved.loc[saved.date=='2026-09-02','memo'].tolist(),['別日'])
        pd.testing.assert_frame_equal(rows,original)


class SavedTodayAttendanceUiTests(unittest.TestCase):
    def test_saved_today_remains_available_for_correction_after_leave(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        today=dt.date.today();past=today-dt.timedelta(days=1)
        f.write('students.csv',[dict(student_id='DEMO001',display_name='退会予定テスト',is_active='true',join_date='2020-01-01',leave_date=str(past))])
        f.write('monthly_schedule.csv',[dict(date=str(today),student_id='DEMO001',slot='1',session_type='授業',reason='通常')])
        f.write('attendance_log.csv',[dict(date=str(d),student_id='DEMO001',kind='lesson',memo='保持') for d in [past,today]])
        path=f.data/'attendance_log.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
        at=AppTest.from_file(str(f.app),default_timeout=40)
        at.session_state['auth_ok']=True
        at.run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        key=f'att_kind_{today}_DEMO001'
        self.assertNotIn(key,{w.key for w in at.selectbox})
        at.checkbox(key=f'att_show_done_{today}').check().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertIn(key,{w.key for w in at.selectbox})
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
