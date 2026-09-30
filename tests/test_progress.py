import pandas as pd
from .support import RegressionCase

class ProgressTests(RegressionCase):
    def test_course_ids_rename_legacy_and_task_move(self):
        courses=pd.DataFrame([dict(course_id='C1',genre_id='G',genre_name='ジャンル',course_name='旧名称'),dict(course_id='C2',genre_id='G',genre_name='ジャンル',course_name='別コース')])
        legacy=pd.DataFrame([dict(date='2026-01-01',student_id='S',curriculum='G',item='旧名称',status='done',note='course_done')]);original=legacy.copy()
        resolve=self.ns['resolve_course_history_ids'];mask=self.ns['course_history_mask'];status=self.ns['get_student_main_course_status']
        self.ns['curr_tasks']=pd.DataFrame([dict(course_id='C1',task_id='T',is_active='true',student_id='')]);self.ns['curr_prog']=pd.DataFrame([dict(course_id='C1',task_id='T',student_id='S',is_done='true',is_skip='false')]);self.ns['curr_courses']=courses
        linked=resolve(legacy,courses);assert linked.course_id.tolist()==['C1'];pd.testing.assert_frame_equal(legacy,original);self.ns['log']=linked
        assert status('S','C1')['status']=='完了'
        renamed=courses.copy();renamed.loc[0,'course_name']='新名称';self.ns['curr_courses']=renamed;assert status('S','C1')['status']=='完了'
        renamed.loc[0,'genre_name']='新ジャンル';assert status('S','C1')['status']=='完了'
        assert status('S','C2')['status']!='完了';assert status('other','C1')['status']!='完了'
        self.ns['log']=pd.DataFrame();before=status('S','C1');self.ns['curr_courses']=courses;assert status('S','C1')=={**before,'course_name':self.ns['get_main_course_label']('C1')}
        self.ns['log']=linked
        amb=courses.copy();amb.loc[1,'course_name']='旧名称';assert resolve(legacy,amb).course_id.iloc[0]=='';assert self.messages
        self.messages.clear();assert resolve(legacy,renamed).course_id.iloc[0]=='';assert self.messages
        explicit=linked.copy();explicit.loc[0,'course_id']='C2';assert resolve(explicit,courses).course_id.iloc[0]=='C2'
        skip=linked.copy();skip['status']='skip';skip['note']='course_skip';assert mask(skip,'S','C1','skip').any();assert not mask(skip,'S','C1','done').any()
        # Moving a task does not move historical progress to the new course.
        self.ns['curr_tasks'].loc[0,'course_id']='C2';assert status('S','C2')['completed_count']==0;assert self.ns['curr_prog'].course_id.iloc[0]=='C1';assert status('S','C1')['status']=='完了'

    def test_active_task_toggle_preserves_history(self):
        tasks = pd.DataFrame([dict(task_id='T1',course_id='C1',is_active='true'),dict(task_id='T2',course_id='C2',is_active='false')])
        history = pd.DataFrame([dict(task_id='T2',is_done='true')])
        before = history.copy(deep=True)
        self.assertEqual(tasks[self.call('active_curriculum_task_mask',tasks)].task_id.tolist(), ['T1'])
        tasks.loc[1,'is_active'] = 'true'
        self.assertEqual(tasks[self.call('active_curriculum_task_mask',tasks)].task_id.tolist(), ['T1','T2'])
        pd.testing.assert_frame_equal(history,before)
