"""Course history access is independent of current enrollment or master presence."""
import datetime as dt
import unittest
from streamlit.testing.v1 import AppTest


class CourseHistoryCandidateTests(unittest.TestCase):
    def test_all_master_and_history_ids_accessible_without_writing(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        today = dt.date.today()
        students = [
            dict(student_id='ACTIVE', display_name='在籍', is_active='true'),
            dict(student_id='LEFT', display_name='退会済み', is_active='true', join_date=str(today-dt.timedelta(days=60)), leave_date=str(today-dt.timedelta(days=1))),
            dict(student_id='LEGACY', display_name='旧退会', is_active='false'),
            dict(student_id='DATED', display_name='期間内OFF', is_active='false', join_date=str(today-dt.timedelta(days=30))),
        ]
        f.write('students.csv', students)
        ids = ['ACTIVE', 'LEFT', 'LEGACY', 'DATED', 'MISSING']
        f.write('progress_log.csv', [dict(student_id=sid, date=str(today-dt.timedelta(days=2)), curriculum='DEMO_G01', item='テストコース', status='done', note='保持') for sid in ids])
        f.write('curriculum_progress.csv', [dict(student_id='PROGRESS_ONLY', course_id='DEMO_C01', task_id='DEMO_T01', is_done='false', is_skip='true', done_date=str(today-dt.timedelta(days=3)), note='保持')])
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True
        at.session_state['sidebar_view_mode'] = 'コース別（件数）'
        at.run()
        self.assertFalse(at.exception)
        labels = at.selectbox(key='course_done_student').options
        self.assertEqual(len(labels), 6)
        self.assertIn('MISSING | （マスタ未登録）', labels)
        self.assertIn('PROGRESS_ONLY | （マスタ未登録）', labels)
        for sid in ids:
            label = next(label for label in labels if label.startswith(sid+' | '))
            at.selectbox(key='course_done_student').select(label).run()
            self.assertFalse(at.exception)
            self.assertTrue(any('テストコース ⭕️' in m.value for m in at.markdown))
        at.selectbox(key='course_done_student').select('PROGRESS_ONLY | （マスタ未登録）').run()
        self.assertFalse(at.exception)
        at.checkbox(key='include_inactive').check().run()
        at.selectbox(key='sidebar_student').set_value('退会済み').run()
        self.assertTrue(any('テストコース ⭕️' in m.value for m in at.markdown))
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)

    def test_empty_master_still_exposes_saved_history(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.write('students.csv', [])
        f.write('progress_log.csv', [dict(student_id='MISSING', date='2026-01-01', curriculum='DEMO_G01', item='テストコース', status='done')])
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True
        at.session_state['sidebar_view_mode'] = 'コース別（件数）'
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(at.selectbox(key='course_done_student').options, ['MISSING | （マスタ未登録）'])
        self.assertTrue(any('テストコース ⭕️' in m.value for m in at.markdown))
