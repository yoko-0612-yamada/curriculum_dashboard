"""Empty active course input and stale selection recovery, using temporary data."""
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class EmptyActiveCourseTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        self.f = ProgressUiTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.courses = pd.read_csv(self.f.data / 'curriculum_courses.csv')
        self.key = 'progress_course_DEMO001'
        self.label = 'テスト教材｜テストコース  [DEMO_C01]'
        self.at = AppTest.from_file(str(self.f.app), default_timeout=40)
        self.at.session_state['auth_ok'] = True
        self.at.session_state['sidebar_student'] = 'テスト生徒01（架空）'
        self.at.session_state['daily_input_mode'] = '進捗登録'

    def run_view(self):
        self.at.run()
        self.assertFalse(self.at.exception, [e.message for e in self.at.exception])

    def test_disable_reactivate_and_other_view_preserve_history(self):
        self.f.write('curriculum_progress.csv', [dict(student_id='DEMO001', course_id='DEMO_C01', task_id='DEMO_T01', is_done='true', done_date='2026-01-01')])
        paths = [self.f.data / n for n in ['curriculum_progress.csv', 'progress_log.csv', 'kentei_progress.csv']]
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
        self.run_view()
        self.assertEqual(self.at.selectbox(key=self.key).value, self.label)
        self.courses.assign(is_active='false').to_csv(self.f.data / 'curriculum_courses.csv', index=False)
        self.run_view()
        self.assertTrue(any('現在、入力対象の有効コースはありません' in i.value for i in self.at.info))
        self.assertFalse(any(w.key == self.key for w in self.at.selectbox))
        self.assertFalse(any(str(w.key).startswith('curr_state_') for w in self.at.selectbox))
        self.assertFalse(any(b.label == '💾 保存（カリキュラム課題）' for b in self.at.button))
        self.at.radio(key='view_mode_trial').set_value('検定課題').run()
        self.assertFalse(self.at.exception)
        self.assertTrue(any(str(w.key).startswith('kentei_state_') for w in self.at.selectbox))
        self.courses.to_csv(self.f.data / 'curriculum_courses.csv', index=False)
        self.at.radio(key='view_mode_trial').set_value('カリキュラム課題').run()
        self.assertFalse(self.at.exception)
        self.assertEqual(self.at.selectbox(key=self.key).value, self.label)
        self.assertTrue(any(w.key == 'curr_state_DEMO001_DEMO_C01_DEMO_T02' for w in self.at.selectbox))
        self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths])
        self.at.selectbox(key='curr_state_DEMO001_DEMO_C01_DEMO_T02').set_value('完了').run()
        next(b for b in self.at.button if b.label == '💾 保存（カリキュラム課題）').click().run()
        self.assertFalse(self.at.exception)
        saved = pd.read_csv(paths[0])
        self.assertTrue(saved.loc[saved.task_id.eq('DEMO_T02'), 'is_done'].astype(str).str.lower().eq('true').all())

    def test_invalid_selection_recovers_with_unchanged_recommendation(self):
        self.run_view()
        for value in [None, '', '候補外の旧コース']:
            with self.subTest(value=value):
                # Seed stale server state before widget serialization by AppTest.
                self.at = AppTest.from_file(str(self.f.app), default_timeout=40)
                self.at.session_state['auth_ok'] = True
                self.at.session_state['sidebar_student'] = 'テスト生徒01（架空）'
                self.at.session_state['daily_input_mode'] = '進捗登録'
                self.at.session_state[self.key] = value
                self.at.session_state['progress_course_recommended_DEMO001'] = self.label
                self.run_view()
                self.assertEqual(self.at.selectbox(key=self.key).value, self.label)
        # No recommended course: fall back to the first active candidate.
        self.f.write('progress_log.csv', [dict(student_id='DEMO001', course_id='DEMO_C01', curriculum='DEMO_G01', item='テストコース', status='done', note='course_done')])
        self.at.session_state[self.key] = None
        self.run_view()
        self.assertEqual(self.at.selectbox(key=self.key).value, self.label)
        self.assertTrue(any('すべてのコースが完了' in i.value for i in self.at.info))

    def test_empty_master_and_no_applicable_tasks(self):
        self.f.write('curriculum_courses.csv', [])
        self.run_view()
        self.assertFalse(any(w.key == self.key for w in self.at.selectbox))
        self.courses.to_csv(self.f.data / 'curriculum_courses.csv', index=False)
        for changes in [dict(student_id='OTHER'), dict(is_active='false')]:
            with self.subTest(changes=changes):
                self.f.write('curriculum_tasks.csv', [dict(t, **changes) for t in self.f.tasks])
                self.run_view()
                self.assertTrue(any('このコースに表示対象の課題はありません' in i.value for i in self.at.info))
