"""Course skip excludes all hints; task skip only advances within a course."""
import ast
import unittest
import pandas as pd
from .support import APP, RegressionCase
from . import test_hint_state_refresh as fixtures

class CourseSkipHintTests(RegressionCase):
    def setUp(self):
        super().setUp()
        nodes=[n for n in ast.walk(ast.parse(APP.read_text())) if isinstance(n,ast.FunctionDef) and n.name in {'_active_course_table','_next_curriculum_task_hint'}]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(APP),'exec'),self.ns)
        self.ns['curr_courses']=pd.DataFrame([dict(course_id=c,course_name='同名',genre_name='教材',genre_id='G',course_order=i,is_active='true') for i,c in enumerate(['C1','C2'])])
        self.ns['curr_tasks']=pd.DataFrame([dict(course_id=c,task_id=t,task_name=c+t,order=i,is_active='true',student_id='') for c in ['C1','C2'] for i,t in enumerate(['T1','T2'])])
        self.ns['curr_prog']=pd.DataFrame()
        self.ns['log']=pd.DataFrame()

    def hint(self):return self.call('_next_curriculum_task_hint','S')

    def test_course_done_skip_id_and_rename(self):
        self.assertIn('C1T1',self.hint())
        for status in ['skip','done']:
            self.ns['log']=pd.DataFrame([dict(student_id='S',course_id='C1',curriculum='OLD',item='旧名称',status=status,note='course_'+status)])
            self.assertIn('C2T1',self.hint())
            self.ns['curr_courses'].loc[0,'course_name']='改名後'
            self.assertIn('C2T1',self.hint())
            self.ns['log'].loc[0,'student_id']='OTHER'
            self.assertIn('C1T1',self.hint())

    def test_task_states_and_course_skip_cancel(self):
        for flag in ['is_skip','is_done']:
            self.ns['curr_prog']=pd.DataFrame([dict(student_id='S',course_id='C1',task_id='T1',**{flag:'true'})])
            self.ns['log']=pd.DataFrame()
            self.assertIn('C1T2',self.hint())
            self.ns['log']=pd.DataFrame([dict(student_id='S',course_id='C1',status='skip',note='course_skip')])
            before=self.ns['curr_prog'].copy(deep=True)
            self.assertIn('C2T1',self.hint())
            self.ns['log']=self.ns['log'].iloc[:0].copy()
            self.assertIn('C1T2',self.hint())
            pd.testing.assert_frame_equal(self.ns['curr_prog'],before)

class CourseSkipHintUiTests(unittest.TestCase):
    def test_shared_displays_refresh_on_skip_and_cancel(self):
        f=fixtures.HintStateRefreshTests();f.setUp();self.addCleanup(f.doCleanups)
        self.assertIn('C1課題',f.run_view()['A'])
        f.f.write('progress_log.csv',[dict(student_id='A',course_id='C1',curriculum='G',item='C1',status='skip',note='course_skip',date=f.day)])
        log=f.f.data/'progress_log.csv';before=(log.read_bytes(),log.stat().st_mtime_ns)
        hints=f.run_view()
        self.assertIn('C2課題',hints['A']);self.assertIn('C1課題',hints['B'])
        candidates=[x.value.removeprefix('今日やる候補：') for x in f.at.caption if x.value.startswith('今日やる候補：')]
        cards=[x.value.split('今日やる予定：',1)[1] for x in f.at.success if '今日やる予定：' in x.value]
        self.assertEqual(candidates,cards)
        f.at.selectbox(key='sidebar_student').set_value('A').run()
        f.at.radio(key='daily_input_mode').set_value('進捗登録').run()
        self.assertFalse(f.at.exception)
        self.assertEqual(dict(f.at.session_state['today_task_hint_map']),{'A':hints['A']})
        self.assertTrue(any(x.value=='今日やる候補：'+hints['A'] for x in f.at.caption))
        self.assertEqual((log.read_bytes(),log.stat().st_mtime_ns),before)
        f.f.write('progress_log.csv',[])
        self.assertIn('C1課題',f.run_view()['A'])
        self.assertNotIn('C2課題',f.at.session_state['today_task_hint_map']['A'])
