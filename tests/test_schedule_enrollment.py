"""Stage 2 opt-in daily plans and actual monthly generation loop."""
import ast
import json
import pandas as pd
from .support import APP, RegressionCase, Stopped


class ScheduleEnrollmentTests(RegressionCase):
    def setUp(self):
        super().setUp()
        self.students=pd.DataFrame([dict(student_id='S1',display_name='S1',join_date='2026-10-10',leave_date='2026-10-20',is_active='true')])
        self.weekly=pd.DataFrame([dict(student_id='S1',weekday=w,slot='1',session_type='授業',week_pattern='毎週') for w in ['月','火','水','木','金','土','日']])
        self.empty=pd.DataFrame()

    def daily(self,day,monthly=None,overrides=None):
        return self.call('build_enrolled_daily_plan_for_date',day,self.students,self.weekly,
                         self.empty if monthly is None else monthly,
                         self.empty if overrides is None else overrides,self.empty)

    def month(self):
        tree=ast.parse(APP.read_text())
        loop=next(n for n in ast.walk(tree) if isinstance(n,ast.While) and ast.unparse(n.test)=='current_day <= month_end')
        self.ns.update(current_day=self.ns['date'](2026,10,1),month_end=self.ns['date'](2026,10,31),
                       weekday_names=['月','火','水','木','金','土','日'],generated_rows=[],
                       students_enrollment_source=self.students.copy(),sched_for_month=self.weekly.copy(),
                       active_student_ids_for_month=set())
        exec(compile(ast.Module(body=[loop],type_ignores=[]),str(APP),'exec'),self.ns)
        return pd.DataFrame(self.ns['generated_rows'])

    def test_daily_boundaries(self):
        for day,count in [('2026-10-09',0),('2026-10-10',1),('2026-10-20',1),('2026-10-21',0)]:
            with self.subTest(day=day):self.assertEqual(len(self.daily(day)),count)

    def test_midmonth_generation_and_no_source_mutation(self):
        before=[x.copy(deep=True) for x in [self.students,self.weekly]]
        result=self.month()
        self.assertEqual(result.date.tolist(),[f'2026-10-{d:02}' for d in range(10,21)])
        for a,b in zip(before,[self.students,self.weekly]):pd.testing.assert_frame_equal(a,b)

    def test_unbounded_leave_and_legacy(self):
        self.students['leave_date']=''
        self.assertEqual(len(self.daily('2027-01-01')),1)
        self.assertEqual(len(self.month()),22)
        self.students['join_date']=''
        self.assertEqual(len(self.month()),31)
        self.students['is_active']='false'
        self.assertTrue(self.daily('2026-10-15').empty)
        self.assertTrue(self.month().empty)

    def test_invalid_dates_raise_or_stop_without_mutating(self):
        for field,value in [('join_date','bad'),('leave_date','2026-02-30'),('join_date','2027-01-01')]:
            with self.subTest(field=field,value=value):
                saved=self.students.copy()
                self.students.loc[0,field]=value
                with self.assertRaises(ValueError):self.daily('2026-10-15')
                with self.assertRaises(Stopped):self.month()
                self.assertTrue(self.messages)
                self.students=saved

    def test_patterns_and_confirmed_empty(self):
        self.students['join_date']='';self.students['leave_date']=''
        self.weekly=self.weekly[self.weekly.weekday=='木'].copy()
        for pattern,days in [('毎週',[1,8,15,22,29]),('第1・第3',[1,15]),('第2・第4',[8,22])]:
            self.weekly['week_pattern']=pattern
            self.assertEqual(self.month().date.tolist(),[f'2026-10-{d:02}' for d in days])
            for d in [1,8,15,22,29]:self.assertEqual(len(self.daily(f'2026-10-{d:02}')),int(d in days))
        self.ns['MONTHLY_SCHEDULE_CONFIRMATION_JSON'].write_text(json.dumps(dict(version=1,confirmed_months=['2026-10'],confirmed_dates=[])))
        self.assertTrue(self.daily('2026-10-08').empty)

    def test_saved_month_priority_and_past_with_inactive_flag(self):
        monthly=pd.DataFrame([dict(student_id='S1',date='2026-10-15',slot='2',session_type='自習')])
        before=monthly.copy()
        self.students['is_active']='false'
        self.assertEqual(self.daily('2026-10-15',monthly=monthly).slot.tolist(),['2'])
        self.assertTrue(self.daily('2026-10-21',monthly=monthly).empty)
        pd.testing.assert_frame_equal(monthly,before)

    def test_transfer_cancel_add_reuses_existing_operations(self):
        bot=pd.DataFrame([dict(student_id='S1',bot_student_id='S1')])
        monthly=pd.DataFrame([dict(student_id='S1',date='2026-10-15',slot='1',session_type='授業')])
        raw=pd.DataFrame([dict(request_type='lesson_transfer',bot_student_id='S1',source_date='2026-10-15',source_slot='1',requested_date='2026-10-16',requested_slot='2',status='confirmed',reservation_id='R1',line_request_id='L1')])
        preview=self.call('validate_seat_transfer_import_rows',raw,students_df=self.students,student_schedule_df=self.empty,monthly_schedule_df=monthly,schedule_overrides_df=self.empty,timeslots_df=self.empty,bot_map_df=bot,applied_log_df=self.empty)
        self.assertEqual(preview['反映'].tolist(),['OK'])
        overrides,_,_=self.call('apply_confirmed_seat_transfers',preview,schedule_overrides_df=self.empty,import_source_df=raw,applied_log_df=self.empty)
        self.weekly=self.empty
        source=self.daily('2026-10-15',monthly,overrides)
        self.assertTrue(self.call('_active_plan_rows',source).empty)
        self.assertEqual(len(source),1)  # cancellation history survives
        self.assertEqual(self.call('_active_plan_rows',self.daily('2026-10-16',monthly,overrides)).slot.tolist(),['2'])
        self.students['leave_date']='2026-10-15'
        self.assertTrue(self.call('_active_plan_rows',self.daily('2026-10-16',monthly,overrides)).empty)

    def test_existing_consumers_remain_legacy(self):
        day='2026-10-21'
        old=self.call('build_daily_plan_for_date',day,self.students,self.weekly,self.empty,self.empty,self.empty)
        self.assertEqual(len(old),1)
        self.assertTrue(self.daily(day).empty)
        bot=pd.DataFrame([dict(student_id='S1',bot_student_id='S1')])
        self.assertEqual(len(self.call('build_bot_schedule_export',day,day,self.students,self.weekly,self.empty,self.empty,self.empty,bot)),0)
        tree=ast.parse(APP.read_text())
        # Enrollment opt-in is limited to the daily entry and the seat paths added later.
        enabled=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                 and n.func.id=='build_daily_plan_for_date' and any(k.arg=='apply_enrollment_dates' for k in n.keywords)]
        owners={fn.name for fn in tree.body if isinstance(fn,ast.FunctionDef)
                for n in ast.walk(fn) if n in enabled}
        self.assertEqual(owners,{'build_enrolled_daily_plan_for_date',
                                'render_integrated_seat_view','build_seat_reservation_sync_export',
                                'build_bot_schedule_export','build_seat_current_state_sync_df'})
        self.assertEqual(len(enabled),8)

    def test_month_ui_validates_original_join_date_before_coercion(self):
        from .test_progress_ui import ProgressUiTests
        from streamlit.testing.v1 import AppTest
        fixture=ProgressUiTests()
        fixture.setUp()
        try:
            fixture.write('students.csv',[dict(student_id='DEMO001',display_name='架空生徒',is_active='true',join_date='invalid-date',leave_date='2026-10-20')])
            fixture.write('student_schedule.csv',[dict(student_id='DEMO001',weekday='木',slot='1',session_type='授業')])
            at=AppTest.from_file(str(fixture.app),default_timeout=40)
            for key,value in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=2026,monthly_schedule_month=10,monthly_view_mode_2026_10='⚙ 生成').items():
                at.session_state[key]=value
            path=fixture.data/'monthly_schedule.csv'
            before=(path.read_bytes(),path.stat().st_mtime_ns)
            at.run()
            self.assertFalse(at.exception,[e.message for e in at.exception])
            self.assertTrue(any('join_date' in e.value for e in at.error))
            self.assertFalse([b for b in at.button if b.label=='📅 固定スケジュールをカレンダーに反映'])
            self.assertEqual(before,(path.read_bytes(),path.stat().st_mtime_ns))
        finally:
            fixture.doCleanups()
