"""Small UI integration tests: only synthetic data in a temporary app copy."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import APP


class ProgressUiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dashboard-ui-regression-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root/'data'
        self.data.mkdir()
        (self.root/'curriculum_dashboard').mkdir()
        self.app = self.root/'curriculum_dashboard/dashboard.py'
        shutil.copyfile(APP,self.app)
        self.headers = json.loads((Path(__file__).parent/'fixtures/csv_headers.json').read_text())
        for name, cols in self.headers.items():
            pd.DataFrame(columns=cols).to_csv(self.data/name,index=False)
        self.write('students.csv',[dict(student_id='DEMO001',display_name='テスト生徒01（架空）',is_active='true',grade='小3',number_of_times='4',join_date='2026-01-01')])
        self.write('curriculum_courses.csv',[dict(course_id='DEMO_C01',genre_id='DEMO_G01',genre_name='テスト教材',course_name='テストコース',course_order=1,is_active='true')])
        self.tasks = [dict(course_id='DEMO_C01',task_id=f'DEMO_T0{i}',task_name=f'課題{i}',order=i,is_active='true',student_id='') for i in [1,2]]
        self.write('curriculum_tasks.csv',self.tasks)
        self.write('kentei_tasks.csv',[dict(grade='4',task_id='DEMO_K01',task_name='検定課題',order=1,student_id='')])
        cwd = Path.cwd()
        self.addCleanup(os.chdir,cwd)  # restore before TemporaryDirectory cleanup
        os.chdir(self.root)

    def write(self,name,rows):
        pd.DataFrame(rows).reindex(columns=self.headers[name],fill_value='').to_csv(self.data/name,index=False)

    def launch(self,kind):
        view = 'カリキュラム課題' if kind=='curriculum' else '検定課題'
        at = AppTest.from_file(str(self.app),default_timeout=40)
        at.session_state['auth_ok']=True
        at.session_state['sidebar_student']='テスト生徒01（架空）'
        at.session_state['sidebar_view_mode']=view
        at.session_state['override_done_lock']=True
        at.run()
        self.assertFalse(at.exception,[x.message for x in at.exception])
        return at,view

    def save(self,at,view,key,value):
        at.selectbox(key=key).set_value(value).run()
        next(b for b in at.button if b.label==f'💾 保存（{view}）').click().run()
        self.assertFalse(at.exception,[x.message for x in at.exception])

    def test_empty_then_existing_progress_both_kinds(self):
        for kind,key in [('curriculum','curr_state_DEMO001_DEMO_C01_DEMO_T01'),('kentei','kentei_state_DEMO001_4_DEMO_K01')]:
            with self.subTest(kind=kind):
                at,view=self.launch(kind)
                self.assertEqual(at.selectbox(key=key).value,'未実施')
                self.save(at,view,key,'完了')
                saved=pd.read_csv(self.data/f'{kind}_progress.csv')
                self.assertTrue(saved.is_done.astype(str).str.lower().eq('true').any())
                at,view=self.launch(kind)
                self.assertEqual(at.selectbox(key=key).value,'完了')
                self.save(at,view,key,'未実施')
                saved=pd.read_csv(self.data/f'{kind}_progress.csv')
                self.assertFalse(saved.is_done.astype(str).str.lower().eq('true').any())

    def test_invalid_or_missing_is_not_empty(self):
        for kind in ['curriculum','kentei']:
            path=self.data/f'{kind}_progress.csv'
            for value in [None,b'',b'wrong\n',b'student_id,task_id\n"unterminated']:
                with self.subTest(kind=kind,value=value):
                    if path.exists(): path.unlink()
                    if value is not None: path.write_bytes(value)
                    before=(path.read_bytes(),path.stat().st_mtime_ns) if path.exists() else None
                    at,view=self.launch(kind)
                    self.assertFalse([b for b in at.button if b.label==f'💾 保存（{view}）'])
                    self.assertTrue(at.error or at.warning)
                    after=(path.read_bytes(),path.stat().st_mtime_ns) if path.exists() else None
                    self.assertEqual(before,after)

    def test_inactive_history_survives_save_and_reactivation(self):
        self.write('curriculum_progress.csv',[dict(student_id='DEMO001',course_id='DEMO_C01',task_id='DEMO_T01',is_done='true',is_skip='false',done_date='2026-01-01',note='保持')])
        before=pd.read_csv(self.data/'curriculum_progress.csv').fillna('')
        self.tasks[0]['is_active']='false'
        self.write('curriculum_tasks.csv',self.tasks)
        at,view=self.launch('curriculum')
        key='curr_state_DEMO001_DEMO_C01_DEMO_T01'
        self.assertNotIn(key,[w.key for w in at.selectbox])
        self.save(at,view,'curr_state_DEMO001_DEMO_C01_DEMO_T02','完了')
        after=pd.read_csv(self.data/'curriculum_progress.csv').fillna('')
        pd.testing.assert_frame_equal(before,after[after.task_id=='DEMO_T01'].reset_index(drop=True),check_dtype=False)
        self.tasks[0]['is_active']='true'
        self.write('curriculum_tasks.csv',self.tasks)
        at,_=self.launch('curriculum')
        self.assertEqual(at.selectbox(key=key).value,'完了')
