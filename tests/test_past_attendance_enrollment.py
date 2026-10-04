"""Past unfinished attendance uses event-date enrollment, never filters saved rows."""
import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class PastEnrollmentTests(RegressionCase):
    def split(self, students, attendance=None):
        students=pd.DataFrame(students)
        plan=pd.DataFrame([dict(student_id=s,slot='1') for s in students.student_id])
        att=pd.DataFrame(attendance or [],columns=['date','student_id','kind','memo'])
        before=att.copy(deep=True)
        result=self.call('split_past_attendance_plan',plan,att,students,dt.date(2026,9,15))
        pd.testing.assert_frame_equal(att,before)
        return result

    def test_boundaries_and_currently_inactive(self):
        periods=[('2026-09-16',''),('2026-09-15',''),('', '2026-09-15'),('', '2026-09-14'),('2020-01-01',''),('2026-09-01','2026-09-30')]
        rows=[dict(student_id=str(i),join_date=j,leave_date=l,is_active='false') for i,(j,l) in enumerate(periods)]
        saved,new,error=self.split(rows)
        self.assertEqual(set(new.student_id),{'1','2','4','5'})
        self.assertTrue(saved.empty);self.assertEqual(error,'')

    def test_legacy_and_zero(self):
        for active,expected in [('true',1),('false',0)]:
            saved,new,error=self.split([dict(student_id='S',is_active=active)])
            self.assertEqual(len(new),expected);self.assertFalse(error)

    def test_saved_history_outside_period_is_not_filtered(self):
        saved,new,error=self.split([dict(student_id='S',is_active='false',leave_date='2020-01-01')],
                                  [('2026-09-15','S','lesson','保持')])
        self.assertEqual(saved.student_id.tolist(),['S']);self.assertTrue(new.empty)
        self.assertFalse(error)

    def test_invalid_period_blocks_only_new_candidates(self):
        for join,leave in [('bad',''),('2026-10-01','2026-09-01')]:
            saved,new,error=self.split([dict(student_id='S',join_date=join,leave_date=leave)],
                                      [('2026-09-15','S','lesson','保持')])
            self.assertEqual(saved.student_id.tolist(),['S'])
            self.assertTrue(new.empty);self.assertTrue(error)


class PastEnrollmentUiTests(unittest.TestCase):
    def test_overdue_candidates_use_past_date_and_preserve_saved_log(self):
        from .test_progress_ui import ProgressUiTests
        today=dt.date.today()
        if today.day==1:
            self.skipTest('既存の未完了表示は今月のみ。月初日は過去日の表示対象なし')
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        past=today-dt.timedelta(days=1)
        f.write('students.csv',[
            dict(student_id='IN',display_name='過去日在籍',is_active='false',join_date=str(past),leave_date=str(past)),
            dict(student_id='OUT',display_name='入会前',is_active='true',join_date=str(today)),
            dict(student_id='SAVED',display_name='履歴保持',is_active='false',leave_date='2020-01-01'),
        ])
        f.write('monthly_schedule.csv',[dict(date=str(past),student_id=s,slot='1',session_type='授業',reason='通常') for s in ['IN','OUT','SAVED']])
        f.write('attendance_log.csv',[dict(date=str(past),student_id='SAVED',kind='lesson',memo='保持')])
        path=f.data/'attendance_log.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
        at=AppTest.from_file(str(f.app),default_timeout=40)
        at.session_state['auth_ok']=True;at.run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        buttons=[b for b in at.button if str(b.key).startswith('overdue_lesson_')]
        self.assertTrue(any('_IN_' in b.key and not b.disabled for b in buttons))
        self.assertFalse(any('_OUT_' in b.key for b in buttons))
        self.assertTrue(any('_SAVED_' in b.key and b.disabled for b in buttons))
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        next(b for b in buttons if '_IN_' in b.key).click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        written=pd.read_csv(path,dtype=str).fillna('')
        self.assertEqual(written.loc[written.student_id=='IN','date'].tolist(),[str(past)])
        self.assertEqual(written.loc[written.student_id=='SAVED','memo'].tolist(),['保持'])
        self.assertNotIn('OUT',set(written.student_id))
