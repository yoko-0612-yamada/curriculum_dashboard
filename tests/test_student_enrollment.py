"""Stage 1: student-only dates, empty selections, default-seat side effects."""
import ast
import pandas as pd
from .support import APP, RegressionCase, Stopped


class StudentEnrollmentTests(RegressionCase):
    def enrolled(self, day, **changes):
        row = dict(student_id='S1',join_date='2026-04-01',leave_date='2026-10-31',is_active='true')
        row.update(changes)
        return self.call('student_is_enrolled_on',row,day)

    def test_join_day_inclusive(self):
        self.assertTrue(self.enrolled('2026-04-01'))

    def test_before_join(self):
        self.assertFalse(self.enrolled('2026-03-31'))

    def test_leave_day_inclusive(self):
        self.assertTrue(self.enrolled('2026-10-31'))

    def test_after_leave(self):
        self.assertFalse(self.enrolled('2026-11-01'))

    def test_open_ended_and_missing_start(self):
        self.assertTrue(self.enrolled('2027-01-01',leave_date=''))
        self.assertTrue(self.enrolled('2026-01-01',join_date=''))
        self.assertFalse(self.enrolled('2026-11-01',join_date=''))

    def test_legacy_active(self):
        self.assertTrue(self.enrolled('2026-10-01',join_date='',leave_date='',is_active='true'))

    def test_legacy_inactive(self):
        self.assertFalse(self.enrolled('2026-10-01',join_date='',leave_date='',is_active='false'))

    def test_invalid_reversed_or_ambiguous_dates(self):
        for changes in [dict(join_date='2027-01-01'),dict(join_date='2026-02-30'),
                        dict(leave_date='10/11/2026'),dict(join_date='not a date')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.enrolled('2026-10-01',**changes)
        for day in ['',None,'bad']:
            with self.subTest(day=day), self.assertRaises(ValueError):self.enrolled(day)

    def test_explicit_period_preserves_past_despite_current_flag(self):
        self.assertTrue(self.enrolled('2026-05-01',is_active='false'))
        self.assertFalse(self.enrolled('2026-11-01',is_active='true'))

    def test_no_students_is_not_everyone_or_load_failure(self):
        students=pd.DataFrame([dict(student_id='S1',join_date='2026-04-01',leave_date='2026-10-31')])
        original=students.copy(deep=True)
        mask=self.call('student_enrollment_mask',students,'2026-11-01')
        ids=set(students.loc[mask,'student_id'])
        self.assertTrue(self.call('filter_student_ids',students,ids).empty)
        self.assertTrue(self.call('student_enrollment_mask',students.iloc[:0],'2026-11-01').empty)
        for missing in [None,pd.DataFrame()]:
            with self.assertRaises(ValueError):self.call('student_enrollment_mask',missing,'2026-11-01')
        with self.assertRaises(ValueError):self.call('filter_student_ids',students,None)
        pd.testing.assert_frame_equal(students,original)

    def test_daily_plan_zero_current_students_and_missing_master(self):
        students=pd.DataFrame([dict(student_id='S1',display_name='S1',is_active='false')])
        monthly=pd.DataFrame([dict(student_id='S1',date='2026-10-01',slot='1',session_type='授業')])
        overrides=pd.DataFrame([dict(student_id='S1',date='2026-10-01',slot='2',session_type='自習',action='追加')])
        empty=pd.DataFrame()
        self.assertTrue(self.call('build_daily_plan_for_date','2026-10-01',students,empty,monthly,overrides,empty).empty)
        with self.assertRaises(ValueError):
            self.call('build_daily_plan_for_date','2026-10-01',None,empty,monthly,overrides,empty)
        # Stage 1 must not apply future dates to existing daily business logic.
        students['is_active']='true';students['leave_date']='2026-09-30'
        self.assertEqual(len(self.call('build_daily_plan_for_date','2026-10-01',students,empty,monthly,overrides,empty)),2)

    def test_default_seat_filter_and_explicit_delete_preserve_hidden_rows(self):
        path=self.ns['DEFAULT_SEATS_CSV']
        full=pd.DataFrame([dict(student_id=s,default_seat_no=str(i),note='保持') for i,s in enumerate(['S1','S2','S3'],1)])
        full.to_csv(path,index=False)
        before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.ns['students']=pd.DataFrame([dict(student_id=s,is_active=v) for s,v in [('S1','true'),('S2','false'),('S3','true')]])
        self.ns['default_seats']=full.copy()
        tree=ast.parse(APP.read_text())
        start=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='default_seats_all' for t in n.targets))
        # Execute the actual startup filter; a reintroduced CSV write here fails the snapshot.
        end=next(i for i in range(start+1,len(tree.body)) if isinstance(tree.body[i],ast.If) and ast.unparse(tree.body[i].test)=='seat_assignments.empty')
        exec(compile(ast.Module(body=tree.body[start:end],type_ignores=[]),str(APP),'exec'),self.ns)
        self.assertEqual(self.ns['default_seats'].student_id.tolist(),['S1','S3'])
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        pd.testing.assert_frame_equal(self.ns['default_seats_all'],full)
        # Exercise actual explicit delete button body with fake Streamlit feedback.
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Call)
                  and any(k.arg=='key' and isinstance(k.value,ast.Constant) and k.value.value=='delete_default_seat' for k in n.test.keywords))
        self.ns['target_sid']='S1'
        self.ns['st'].success=lambda *a:None
        self.ns['st'].rerun=lambda:None
        exec(compile(ast.Module(body=node.body,type_ignores=[]),str(APP),'exec'),self.ns)
        saved=pd.read_csv(path,dtype=str)
        pd.testing.assert_frame_equal(saved,full.iloc[1:].reset_index(drop=True))

    def test_current_course_list_zero_does_not_restore_everyone(self):
        tree=ast.parse(APP.read_text())
        # Locate current list selection by its assignment using the legacy mask.
        assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign)
                        and any(isinstance(t,ast.Name) and t.id=='active_students' for t in n.targets)
                        and 'student_legacy_active_mask' in ast.unparse(n.value))
        self.ns['students']=pd.DataFrame([dict(student_id='S1',is_active='false')])
        exec(compile(ast.Module(body=[assignment],type_ignores=[]),str(APP),'exec'),self.ns)
        self.assertTrue(self.ns['active_students'].empty)
        # Guard audited ID checks against restoring truthiness fallbacks.
        for n in ast.walk(tree):
            if isinstance(n,ast.If):
                self.assertNotIn(ast.unparse(n.test),[
                    'active_ids',
                    'active_student_ids_for_month and sid not in active_student_ids_for_month',
                    'active_student_ids_for_seat and sid not in active_student_ids_for_seat',
                ])

    def test_student_load_failure_stops_but_header_only_does_not(self):
        tree = ast.parse(APP.read_text())
        guard = next(n for n in tree.body if isinstance(n, ast.If)
                     and 'issubset(students.columns)' in ast.unparse(n.test))
        for frame, should_stop in [(pd.DataFrame(), True),
                                  (pd.DataFrame(columns=['student_id','display_name']), False)]:
            with self.subTest(should_stop=should_stop):
                self.ns['students'] = frame
                code = compile(ast.Module(body=[guard], type_ignores=[]), str(APP), 'exec')
                if should_stop:
                    with self.assertRaises(Stopped): exec(code, self.ns)
                    self.assertTrue(self.messages)
                else:
                    exec(code, self.ns)

    def test_month_generation_zero_ids_stays_empty(self):
        tree = ast.parse(APP.read_text())
        loop = next(n for n in ast.walk(tree) if isinstance(n, ast.While)
                    and ast.unparse(n.test) == 'current_day <= month_end')
        day = self.ns['date'](2026, 10, 1)
        for ids, expected in [(set(), 0), ({'S1'}, 1)]:
            with self.subTest(ids=ids):
                self.ns.update(current_day=day, month_end=day,
                               weekday_names=['月','火','水','木','金','土','日'],
                               active_student_ids_for_month=ids, generated_rows=[],
                               students_enrollment_source=pd.DataFrame([dict(student_id='S1',is_active='S1' in ids)]),
                               sched_for_month=pd.DataFrame([dict(student_id='S1', weekday='木',
                                                                  slot='1', session_type='授業', week_pattern='毎週')]))
                exec(compile(ast.Module(body=[loop],type_ignores=[]),str(APP),'exec'),self.ns)
                self.assertEqual(len(self.ns['generated_rows']),expected)

    def test_explicit_default_seat_update_keeps_invisible_settings(self):
        full = pd.DataFrame([dict(student_id='S1',default_seat_no='1',note='変更対象'),
                             dict(student_id='S2',default_seat_no='2',note='非表示でも保持')])
        self.ns.update(default_seats_all=full, default_seats=full.iloc[:1].copy(),
                       target_sid='S1', default_seat_no='3', note='更新')
        self.ns['st'].success=lambda *a:None
        self.ns['st'].rerun=lambda:None
        tree=ast.parse(APP.read_text())
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Call)
                  and any(k.arg=='key' and isinstance(k.value,ast.Constant) and k.value.value=='save_default_seat' for k in n.test.keywords))
        exec(compile(ast.Module(body=node.body,type_ignores=[]),str(APP),'exec'),self.ns)
        saved=pd.read_csv(self.ns['DEFAULT_SEATS_CSV'],dtype=str)
        self.assertEqual(saved.set_index('student_id').loc['S1','default_seat_no'],'3')
        pd.testing.assert_frame_equal(saved[saved.student_id=='S2'].reset_index(drop=True),full.iloc[1:].reset_index(drop=True))
