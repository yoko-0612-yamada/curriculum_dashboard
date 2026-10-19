"""Share only the unchanged active-course table for one display run."""
import ast
from datetime import date
from unittest.mock import Mock
import unittest
import pandas as pd
from .support import APP, RegressionCase


class CourseTableSharingTests(RegressionCase):
    def setUp(self):
        super().setUp()
        names = {'_active_course_table', '_next_curriculum_task_hint'}
        nodes = [n for n in ast.walk(ast.parse(APP.read_text())) if isinstance(n, ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP), 'exec'), self.ns)
        self.ns['log'] = pd.DataFrame()

    def test_table_priority_ties_inactive_and_input_unchanged(self):
        rows = [dict(course_id=cid, course_name=name, genre_name='教材', course_order=order, is_active=active)
                for cid,name,order,active in [('Z','同名',1,'true'),('Y','同名',1,''),('PY','Python',1,'yes'),('sc_h','高学年',9,'1'),('sc_l','低学年',9,'true'),('OFF','Scratch',0,'false')]]
        source = pd.DataFrame(rows); self.ns['curr_courses'] = source
        before = source.copy(deep=True)
        table = self.call('_active_course_table')
        self.assertEqual(table.course_id.tolist(), ['sc_l','sc_h','PY','Z','Y'])
        pd.testing.assert_frame_equal(source, before)

    def test_shared_and_unshared_hints_match(self):
        courses = pd.DataFrame([dict(course_id=c, course_name=name, genre_name='教材', course_order=order, is_active=active)
            for c,name,order,active in [('sc_l','Scratch',1,'true'),('B','次コース',2,'true'),('OFF','無効',0,'false')]])
        tasks = pd.DataFrame([dict(course_id=c, task_id=t, task_name=t, order=o, is_active=a, student_id=s)
            for c,t,o,a,s in [('sc_l','OFF_TASK',0,'false',''),('sc_l','PERSONAL',1,'true','S'),('sc_l','COMMON',2,'true',''),('B','NEXT',1,'true','')]])
        for course_count in [1,3]:
            self.ns['curr_courses'] = courses.iloc[:course_count].copy()
            self.ns['curr_tasks'] = tasks
            for done in [False, True]:
                self.ns['curr_prog'] = pd.DataFrame([dict(student_id='S', course_id='sc_l', task_id='PERSONAL', is_done=str(done).lower(), is_skip='false')])
                for course_done in [False,True]:
                    self.ns['log'] = pd.DataFrame([dict(student_id='S',course_id='sc_l',status='done',note='course_done')]) if course_done else pd.DataFrame()
                    expected = {sid:self.call('_next_curriculum_task_hint',sid) for sid in ['S','OTHER']}
                    if not done and not course_done:
                        self.assertIn('PERSONAL', expected['S'])
                        self.assertIn('COMMON', expected['OTHER'])
                    shared = self.call('_active_course_table'); before = shared.copy(deep=True)
                    original = self.ns['_active_course_table']
                    self.ns['_active_course_table'] = Mock(side_effect=AssertionError('unexpected rebuild'))
                    try:
                        for sid in expected:
                            self.assertEqual(self.call('_next_curriculum_task_hint',sid,active_courses=shared),expected[sid])
                            self.assertNotIn('OFF_TASK', expected[sid])
                        self.ns['_active_course_table'].assert_not_called()
                    finally:self.ns['_active_course_table'] = original
                    pd.testing.assert_frame_equal(shared,before)


class CourseTableSharingUiTests(unittest.TestCase):
    def test_once_per_run_and_refresh_after_course_change(self):
        from .test_progress_ui import ProgressUiTests
        from streamlit.testing.v1 import AppTest
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        # Counter lives only in the temporary app, reset on each run.
        src=f.app.read_text().replace('        def _active_course_table():', '        st.session_state["audit_course_calls"] = 0\n        def _active_course_table():\n            st.session_state["audit_course_calls"] += 1',1)
        src=src.replace('            _today_active_courses = _active_course_table()', '            _today_active_courses = _active_course_table()\n            st.session_state["audit_active_ids"] = _today_active_courses["course_id"].tolist()',1)
        f.app.write_text(src)
        ids=['A','B','C'];day=str(date.today())
        f.write('students.csv',[dict(student_id=s,display_name=s,is_active='true') for s in ids])
        f.write('monthly_schedule.csv',[dict(student_id=s,date=day,slot='1',session_type='授業',reason='通常') for s in ids])
        f.write('timeslots.csv',[dict(slot='1',start_time='15:00',end_time='16:00')])
        at=AppTest.from_file(str(f.app),default_timeout=40);at.session_state['auth_ok']=True
        for name,active in [('元コース','true'),('変更コース','true'),('変更コース','false')]:
            f.write('curriculum_courses.csv',[dict(course_id='DEMO_C01',genre_id='G',genre_name='教材',course_name=name,course_order=1,is_active=active)])
            at.run();self.assertFalse(at.exception)
            self.assertEqual(at.session_state['audit_course_calls'],1)
            hints=at.session_state['today_task_hint_map']
            for sid in ids:
                if active=='true':self.assertIn(name,hints[sid])
            # Existing persisted hint-map handling is outside this sharing change.
            self.assertEqual(at.session_state['audit_active_ids'], ['DEMO_C01'] if active=='true' else [])
