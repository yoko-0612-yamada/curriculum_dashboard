import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import RegressionCase, Stopped


class DestinationTests(RegressionCase):
    def setUp(self):
        super().setUp()
        self.students=pd.DataFrame([dict(student_id='S',display_name='架空',is_active='true',join_date='2026-10-02',leave_date='2026-10-03')])
        self.bot=pd.DataFrame([dict(student_id='S',bot_student_id='B')])

    def test_boundaries_and_legacy(self):
        for day,ok in [('2026-10-01',False),('2026-10-02',True),('2026-10-03',True),('2026-10-04',False)]:
            if ok:self.call('validate_schedule_destination',self.students,'S',day)
            else:
                with self.assertRaises(ValueError):self.call('validate_schedule_destination',self.students,'S',day)
        self.students['leave_date']=''
        self.call('validate_schedule_destination',self.students,'S','2027-01-01')
        self.students['join_date']='';self.students['is_active']='false'
        with self.assertRaises(ValueError):self.call('validate_schedule_destination',self.students,'S','2026-10-02')
        self.students['is_active']='true'
        self.call('validate_schedule_destination',self.students,'S','2026-10-02')

    def test_invalid_zero_and_ui_stop(self):
        for rows in [self.students.iloc[:0],self.students.assign(join_date='bad'),self.students.assign(join_date='2026-11-01')]:
            with self.assertRaises(Stopped):self.call('require_schedule_destination',rows,'S','2026-10-02')
        self.assertEqual(len(self.messages),3)

    def preview(self,types,dest='2026-10-04',source='2026-10-01'):
        raw=pd.DataFrame([dict(request_type=t,bot_student_id='B',requested_date=dest,requested_slot='2',source_date=source,source_slot='1',status='confirmed',reservation_id=f'R{i}',line_request_id=f'L{i}') for i,t in enumerate(types)])
        monthly=pd.DataFrame([dict(student_id='S',date=source,slot='1',session_type='自習' if types[0].startswith('selfstudy') else '授業')])
        before=monthly.copy(deep=True)
        preview=self.call('validate_seat_transfer_import_rows',raw,students_df=self.students,student_schedule_df=pd.DataFrame(),monthly_schedule_df=monthly,schedule_overrides_df=pd.DataFrame(),timeslots_df=pd.DataFrame(),bot_map_df=self.bot,applied_log_df=pd.DataFrame())
        ov,log,count=self.call('apply_confirmed_seat_transfers',preview,schedule_overrides_df=pd.DataFrame(),import_source_df=raw,applied_log_df=pd.DataFrame())
        pd.testing.assert_frame_equal(monthly,before)
        return preview,ov,log,count

    def test_all_destination_operations_rejected_without_history(self):
        for typ in ['lesson_add','selfstudy_add','lesson_transfer','selfstudy_transfer','lesson_to_selfstudy','selfstudy_to_lesson']:
            with self.subTest(typ=typ):
                p,ov,log,count=self.preview([typ])
                self.assertEqual(p['反映'].tolist(),['不可'])
                self.assertIn('まで在籍',p.iloc[0]['理由/注意'])
                self.assertTrue(ov.empty);self.assertTrue(log.empty);self.assertEqual(count,0)

    def test_cancel_outside_period_and_transfer_into_period(self):
        for typ in ['lesson_cancel','selfstudy_cancel']:
            p,ov,log,count=self.preview([typ]);self.assertEqual(p['反映'].tolist(),['OK']);self.assertEqual(count,1)
        self.students['is_active']='false'
        p,ov,log,count=self.preview(['lesson_transfer'],dest='2026-10-02')
        self.assertEqual(p['反映'].tolist(),['OK'])
        self.assertEqual(set(ov.action),{'キャンセル','追加'})
        self.assertEqual(count,1)

    def test_rejected_row_does_not_reserve_and_duplicate_still_blocked(self):
        p,ov,log,count=self.preview(['lesson_add','lesson_add'],dest='2026-10-02')
        self.assertEqual(p['反映'].tolist(),['OK','不可']);self.assertEqual(count,1)


class DestinationUiTests(unittest.TestCase):
    def test_calendar_rejects_before_editing_schedule(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        f.write('students.csv',[dict(student_id='DEMO001',display_name='架空',is_active='true',join_date='2020-01-01',leave_date='2026-10-31')])
        paths=[f.data/name for name in ['monthly_schedule.csv','schedule_overrides.csv']]
        before=[(p.read_bytes(),p.stat().st_mtime_ns) for p in paths]
        # AppTest performs a full rerun on dialog form submission. Keep only
        # this temporary copy's dialog open to exercise its unchanged submit body.
        source=f.app.read_text()
        source=source.replace('            if open_monthly_add_from_fixed:',
                              '            if True:\n                open_monthly_add_from_fixed = "授業"',1)
        f.app.write_text(source)
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=2026,monthly_schedule_month=11).items():at.session_state[k]=v
        at.session_state['monthly_view_mode_2026_11']='📅 編集'
        at.run()
        chosen=[(w.label,str(w.value)) for w in at.date_input]
        next(b for b in at.button if b.label=='🟢 新規予定として追加').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertTrue(any('2026-10-31 まで在籍' in e.value for e in at.error), (chosen,[e.value for e in at.error],[e.value for e in at.success]))
        self.assertEqual([(p.read_bytes(),p.stat().st_mtime_ns) for p in paths],before)
