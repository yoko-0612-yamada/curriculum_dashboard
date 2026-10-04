import datetime as dt
import pandas as pd
import unittest
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class LeaveDateInputTests(RegressionCase):
    def test_stage_change_clear_and_validation(self):
        original=pd.DataFrame([dict(student_id='S',join_date='2026-10-01',leave_date='',is_active='true',memo='保持')])
        before=original.copy(deep=True)
        staged=self.call('stage_student_leave_date',original,'S','2026-10-31')
        self.assertEqual(staged.leave_date.tolist(),['2026-10-31'])
        self.assertEqual(staged.is_active.tolist(),['true'])
        self.assertEqual(self.call('student_status_display',staged,'2026-10-31')['状態'].tolist(),['在籍'])
        self.assertEqual(self.call('student_status_display',staged,'2026-11-01')['状態'].tolist(),['退会'])
        changed=self.call('stage_student_leave_date',staged,'S','2026-11-30')
        self.assertEqual(changed.leave_date.tolist(),['2026-11-30'])
        cleared=self.call('stage_student_leave_date',changed,'S','')
        pd.testing.assert_frame_equal(cleared,original,check_dtype=False)
        for value in ['invalid','2026-02-30','2026-09-30']:
            with self.assertRaises(ValueError):self.call('stage_student_leave_date',original,'S',value)
        pd.testing.assert_frame_equal(original,before)

    def test_saved_schedule_count_is_readonly(self):
        monthly=pd.DataFrame([dict(student_id='S',date=d,slot='1') for d in ['2026-10-31','2026-11-01']])
        overrides=pd.DataFrame([dict(student_id='S',date='2026-11-01',slot='1',action='キャンセル'),dict(student_id='S',date='2026-11-01',slot='2',action='追加')])
        before=[monthly.copy(deep=True),overrides.copy(deep=True)]
        self.assertEqual(self.call('saved_schedule_count_after','S','2026-10-31',monthly,overrides),2)
        for a,b in zip([monthly,overrides],before):pd.testing.assert_frame_equal(a,b)


class LeaveDateUiTests(unittest.TestCase):
    def test_register_change_cancel_save_without_other_csv_changes(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        today=dt.date.today();end=today+dt.timedelta(days=10);later=end+dt.timedelta(days=10)
        f.write('students.csv',[dict(student_id='DEMO001',display_name='予定架空',is_active='true',join_date=str(today),leave_date='')])
        f.write('bot_student_map_private.csv',[dict(student_id='DEMO001',bot_student_id='EXISTING')])
        f.write('default_seats.csv',[dict(student_id='DEMO001',default_seat_no='1',note='保持')])
        f.write('monthly_schedule.csv',[dict(student_id='DEMO001',date=str(later+dt.timedelta(days=1)),slot='1',session_type='授業')])
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in f.data.glob('*.csv') if p.name!='students.csv'}
        student_path=f.data/'students.csv';initial=(student_path.read_bytes(),student_path.stat().st_mtime_ns)
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',admin_section_selector='👥 生徒管理').items():at.session_state[k]=v
        at.run();self.assertFalse(at.exception)
        next(w for w in at.date_input if w.label=='最終在籍日').set_value(today-dt.timedelta(days=1)).run()
        self.assertTrue(at.button(key='stage_leave_DEMO001').disabled)
        self.assertTrue(any('退会予定を登録できません' in e.value for e in at.error))
        for value in [end,later]:
            next(w for w in at.date_input if w.label=='最終在籍日').set_value(value).run()
            self.assertTrue(any('保存済み予定：1件' in c.value for c in at.caption))
            at.button(key='stage_leave_DEMO001').click().run()
            self.assertFalse(at.exception,[e.message for e in at.exception])
            if value==end:self.assertEqual((student_path.read_bytes(),student_path.stat().st_mtime_ns),initial)
            at.button(key='students_save_fixed').click().run()
            self.assertFalse(at.exception,[e.message for e in at.exception])
            saved=pd.read_csv(student_path,dtype=str).fillna('')
            self.assertEqual(saved.leave_date.tolist(),[str(value)])
            self.assertEqual(saved.is_active.str.lower().tolist(),['true'])
        at.button(key='clear_leave_DEMO001').click().run()
        at.button(key='students_save_fixed').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        saved=pd.read_csv(student_path,dtype=str).fillna('')
        self.assertEqual(saved.leave_date.tolist(),[''])
        self.assertEqual(saved.is_active.str.lower().tolist(),['true'])
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)
