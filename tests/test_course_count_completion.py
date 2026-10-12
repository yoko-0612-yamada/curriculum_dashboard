"""Course-count view uses the shared ID-based completion/legacy policy."""
import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class CourseCountCompletionTests(unittest.TestCase):
    def fixture(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        return f

    def launch(self, f):
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True
        at.session_state['sidebar_view_mode'] = 'コース別（件数）'
        at.run()
        self.assertFalse(at.exception)
        return at

    def snapshot(self, f):
        return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in f.data.iterdir() if p.is_file()}

    def test_explicit_id_survives_rename_and_retirement_without_cross_course_marks(self):
        f = self.fixture()
        f.write('students.csv', [dict(student_id='DEMO001', display_name='退会済み', is_active='false',
                                    join_date='2020-01-01', leave_date=str(dt.date.today()-dt.timedelta(days=1)))])
        courses = [
            dict(course_id='C1', genre_id='G1', genre_name='教材1', course_name='旧名', course_order='2', is_active='true'),
            dict(course_id='C2', genre_id='G1', genre_name='教材1', course_name='別コース', course_order='1', is_active='true'),
            dict(course_id='C3', genre_id='G2', genre_name='教材2', course_name='変更後', course_order='1', is_active='true'),
        ]
        f.write('curriculum_courses.csv', courses)
        pd.DataFrame([dict(student_id='DEMO001', date='2021-01-01', curriculum='G1', item='旧名',
                           course_id='C1', status='done', note='course_done')]).to_csv(f.data/'progress_log.csv', index=False)
        before = self.snapshot(f)
        at = self.launch(f)
        self.assertIn('- 旧名 ⭕️', [m.value.strip() for m in at.markdown])
        self.assertEqual(before, self.snapshot(f))
        courses[0].update(course_name='変更後', course_order='99')
        f.write('curriculum_courses.csv', courses)
        before = self.snapshot(f)
        at.run()
        self.assertFalse(at.exception)
        g1 = next(e for e in at.expander if '(G1)' in e.label)
        g2 = next(e for e in at.expander if '(G2)' in e.label)
        self.assertIn('- 変更後 ⭕️', [m.value.strip() for m in g1.markdown])
        self.assertIn('- 別コース', [m.value.strip() for m in g1.markdown])
        self.assertIn('- 変更後', [m.value.strip() for m in g2.markdown])
        self.assertIn('⭕️', g1.label)
        self.assertNotIn('⭕️', g2.label)
        self.assertEqual(before, self.snapshot(f))

    def test_legacy_unique_only_no_single_genre_guess_or_task_skip_completion(self):
        f = self.fixture()
        specs = [('C1','G1','一意'), ('C2','G2','曖昧'), ('C3','G2','曖昧'),
                 ('C4','G3','新しい名称'), ('C5','G4','課題だけ'), ('C6','G5','スキップだけ')]
        f.write('curriculum_courses.csv', [dict(course_id=c, genre_id=g, genre_name=g, course_name=n,
                                              course_order='1', is_active='true') for c,g,n in specs])
        rows = [dict(student_id='DEMO001', date='2021-01-01', curriculum=g, item=n,
                     course_id='', status='done', note='course_done')
                for g,n in [('G1','一意'), ('G2','曖昧'), ('G3','昔の名称')]]
        rows += [dict(student_id='DEMO001', date='2021-01-01', curriculum='G4', item='課題だけ',
                      course_id='C5', status='done', note=''),
                 dict(student_id='DEMO001', date='2021-01-01', curriculum='G5', item='スキップだけ',
                      course_id='C6', status='skip', note='course_skip')]
        pd.DataFrame(rows).to_csv(f.data/'progress_log.csv', index=False)
        before = self.snapshot(f)
        at = self.launch(f)
        marks = [m.value.strip() for m in at.markdown if m.value.strip().startswith('- ')]
        self.assertEqual([m for m in marks if '⭕️' in m], ['- 一意 ⭕️'])
        self.assertTrue(any('一意に対応付けできません' in w.value for w in at.warning))
        for e in at.expander:
            if any(f'({g})' in e.label for g in ['G2','G3','G4','G5']):
                self.assertNotIn('⭕️', e.label)
        self.assertEqual(before, self.snapshot(f))
