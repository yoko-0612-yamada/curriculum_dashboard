"""Viewer candidates and count use today's enrollment; history stays accessible."""
import datetime as dt
import unittest
from streamlit.testing.v1 import AppTest


class SidebarEnrollmentTests(unittest.TestCase):
    def test_candidates_status_count_and_history_access(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        today = dt.date.today()
        cases = [
            ('期間内OFF', 'false', -30, None),
            ('退会予定', 'true', -30, 30),
            ('最終日', 'true', -30, 0),
            ('退会済み', 'true', -30, -1),
            ('入会前', 'true', 1, None),
            ('旧在籍', 'true', None, None),
            ('旧退会', 'false', None, None),
            ('不正日付', 'true', 'invalid', None),
            ('期間逆転', 'true', 10, -10),
        ]
        def day(value):
            return '' if value is None else value if isinstance(value, str) else str(today+dt.timedelta(days=value))
        f.write('students.csv', [dict(student_id=f'S{i}', display_name=name,
            is_active=active, join_date=day(start), leave_date=day(end))
            for i, (name, active, start, end) in enumerate(cases)])
        f.write('curriculum_progress.csv', [dict(student_id='S3', course_id='DEMO_C01', task_id='DEMO_T01',
            is_done='true', done_date=str(today-dt.timedelta(days=2)), note='保持')])
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True
        at.run()
        self.assertFalse(at.exception)
        labels = at.selectbox(key='sidebar_student').options
        self.assertEqual(set(labels), {'（全員）', '期間内OFF', f'退会予定（退会予定：{today+dt.timedelta(days=30):%m/%d}まで）', '最終日', '旧在籍'})
        self.assertEqual(next(m.value for m in at.metric if m.label == '今日の在籍生徒数'), '4')
        at.checkbox(key='include_inactive').check().run()
        labels = at.selectbox(key='sidebar_student').options
        for label in ['退会済み（退会）', '入会前（入会前）', '旧退会（退会）', '不正日付（要確認）', '期間逆転（要確認）']:
            self.assertIn(label, labels)
        self.assertEqual(next(m.value for m in at.metric if m.label == '今日の在籍生徒数'), '4')
        for name in ['退会済み', '入会前', '不正日付', '期間逆転']:
            at.selectbox(key='sidebar_student').set_value(name).run()
            self.assertEqual(at.selectbox(key='sidebar_student').value, name)
            self.assertFalse(at.exception)
        at.checkbox(key='include_inactive').uncheck().run()
        self.assertEqual(at.selectbox(key='sidebar_student').value, '（全員）')
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)

    def test_zero_enrollment_has_no_all_students_fallback(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.write('students.csv', [dict(student_id='OLD', display_name='旧退会', is_active='false')])
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True
        at.run()
        self.assertEqual(at.selectbox(key='sidebar_student').options, ['（全員）'])
        self.assertEqual(next(m.value for m in at.metric if m.label == '今日の在籍生徒数'), '0')
