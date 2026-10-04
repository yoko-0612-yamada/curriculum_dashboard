import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class SeatEnrollmentTests(RegressionCase):
    def test_boundaries_legacy_and_zero(self):
        for j,l,a,expected in [('2026-10-02','','true',0),('2026-10-01','','false',1),('', '2026-10-01','false',1),('', '2026-09-30','true',0),('2020-01-01','','true',1),('','','true',1),('','','false',0)]:
            with self.subTest(join=j,leave=l,active=a):
                students=pd.DataFrame([dict(student_id='S',join_date=j,leave_date=l,is_active=a)])
                self.assertEqual(len(self.call('seat_enrolled_students',students,'2026-10-01')),expected)

    def test_bad_dates_error(self):
        for j,l in [('bad',''),('2026-11-01','2026-10-01')]:
            with self.assertRaises(ValueError):
                self.call('seat_enrolled_students',pd.DataFrame([dict(student_id='S',join_date=j,leave_date=l)]),'2026-10-01')

    def test_counts_use_each_day_and_exclude_outside_cancellations(self):
        students=pd.DataFrame([dict(student_id='S',display_name='S',join_date='2026-10-02',leave_date='2026-10-03',is_active='false')])
        monthly=pd.DataFrame([dict(date=f'2026-10-0{i}',student_id='S',slot='1',session_type='授業') for i in range(1,5)])
        result=self.call('build_seat_reservation_sync_export','2026-10-01','2026-10-04',students,pd.DataFrame(),monthly,pd.DataFrame(),pd.DataFrame([dict(slot='1')]))
        self.assertEqual((result.base_count-result.absence_count).tolist(),[0,1,1,0])
        ov=pd.DataFrame([dict(date='2026-10-04',student_id='S',slot='1',action='キャンセル')])
        result=self.call('build_seat_reservation_sync_export','2026-10-04','2026-10-04',students,pd.DataFrame(),monthly,ov,pd.DataFrame([dict(slot='1')]))
        self.assertEqual(result.base_count.tolist(),[0]);self.assertEqual(result.absence_count.tolist(),[0])

    def test_preserve_excluded_rows_notes_and_other_dates(self):
        original=pd.DataFrame([dict(date=d,slot='1',seat_no='1',student_id='OUT',note='履歴') for d in ['2026-09-01','2026-10-01']])
        proposed=original.iloc[:1].copy()
        result=self.call('preserve_ineligible_seat_history',original,proposed,'2026-10-01',set())
        pd.testing.assert_frame_equal(result,original)
        collision=pd.concat([proposed,pd.DataFrame([dict(date='2026-10-01',slot='1',seat_no='1',student_id='IN',note='')])])
        with self.assertRaises(ValueError):
            self.call('preserve_ineligible_seat_history',original,collision,'2026-10-01',{'IN'})


class SeatEnrollmentUiTests(unittest.TestCase):
    def test_candidates_save_history_reserved_and_auto(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        today=dt.date.today();past=today-dt.timedelta(days=1)
        f.write('students.csv',[
            dict(student_id='IN',display_name='在籍',is_active='true',join_date=str(today),leave_date=str(today)),
            dict(student_id='OUT',display_name='対象外',is_active='true',leave_date=str(past))])
        f.write('monthly_schedule.csv',[dict(date=str(today),student_id=s,slot='1',session_type='授業') for s in ['IN','OUT']])
        f.write('default_seats.csv',[dict(student_id=s,default_seat_no=n,note='保持') for s,n in [('IN','3'),('OUT','1')]])
        f.write('seat_assignments.csv',[dict(date=str(d),slot='1',seat_no='1',student_id='OUT',note='履歴') for d in [past,today]])
        path=f.data/'default_seats.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=today.year,monthly_schedule_month=today.month).items():at.session_state[k]=v
        at.session_state[f'monthly_view_mode_{today.year}_{today.month}']='🪑 今日の座席'
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        key=lambda seat:f'seat_grid_{today}_1_{seat}'
        self.assertNotIn(key(1),{w.key for w in at.selectbox})
        self.assertNotIn('対象外',at.selectbox(key=key(2)).options)
        at.button(key=f'auto_assign_default_seats_{today}').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertEqual(at.selectbox(key=key(3)).value,'IN')
        at.selectbox(key=key(2)).set_value('__RESERVED__').run()
        at.selectbox(key=key(4)).set_value('__RESERVED__').run()
        at.button(key=f'save_seat_grid_{today}').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        saved=pd.read_csv(f.data/'seat_assignments.csv',dtype=str).fillna('')
        self.assertEqual(saved.loc[saved.student_id=='OUT','note'].tolist(),['履歴','履歴'])
        self.assertEqual((saved.student_id=='__RESERVED__').sum(),2)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)

    def test_zero_and_invalid_ui_do_not_restore_candidates(self):
        from .test_progress_ui import ProgressUiTests
        today=dt.date.today()
        for join,leave,error in [('',str(today-dt.timedelta(days=1)),False),('invalid','',True)]:
            with self.subTest(error=error):
                f=ProgressUiTests();f.setUp()
                try:
                    f.write('students.csv',[dict(student_id='OUT',display_name='対象外',is_active='true',join_date=join,leave_date=leave)])
                    f.write('monthly_schedule.csv',[dict(date=str(today),student_id='OUT',slot='1',session_type='授業')])
                    paths=[f.data/'students.csv',f.data/'seat_assignments.csv',f.data/'default_seats.csv']
                    before=[(p.read_bytes(),p.stat().st_mtime_ns) for p in paths]
                    at=AppTest.from_file(str(f.app),default_timeout=40)
                    at.session_state['auth_ok']=True;at.session_state['page_state']='管理（入力）'
                    at.session_state['monthly_schedule_year']=today.year;at.session_state['monthly_schedule_month']=today.month
                    at.session_state[f'monthly_view_mode_{today.year}_{today.month}']='🪑 今日の座席'
                    at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
                    if error:
                        self.assertTrue(any('座席の在籍判定エラー' in e.value for e in at.error))
                        self.assertFalse([b for b in at.button if str(b.key).startswith('save_seat')])
                    else:
                        at.checkbox(key=f'seat_grid_include_all_active_{today}').check().run()
                        for w in at.selectbox:
                            if str(w.key).startswith(f'seat_grid_{today}_'):
                                self.assertEqual(w.options,['空席','使用予定'])
                    self.assertEqual([(p.read_bytes(),p.stat().st_mtime_ns) for p in paths],before)
                finally:
                    f.doCleanups()
