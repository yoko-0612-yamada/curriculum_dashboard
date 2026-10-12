"""Existing private task ownership survives editing outside new-task candidates."""
import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class KenteiTaskOwnerTests(unittest.TestCase):
    def test_preserve_existing_owner_and_require_explicit_target_change(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        today = dt.date.today()
        f.write('students.csv', [
            dict(student_id='IN', display_name='期間内', is_active='false',
                 join_date=str(today-dt.timedelta(days=30)), leave_date=str(today+dt.timedelta(days=30))),
            dict(student_id='LEFT', display_name='退会済み', is_active='false',
                 join_date=str(today-dt.timedelta(days=60)), leave_date=str(today-dt.timedelta(days=1))),
            dict(student_id='FUTURE', display_name='入会前', is_active='false',
                 join_date=str(today+dt.timedelta(days=30))),
            dict(student_id='OTHER', display_name='別生徒', is_active='true'),
        ])
        owners = ['IN', 'LEFT', 'FUTURE', 'MISSING']
        f.write('kentei_tasks.csv', [
            dict(grade='4', task_id=f'PRIVATE{i}', task_name=f'個別{i}', order=10*i+1, student_id=sid)
            for i, sid in enumerate(owners)
        ])
        path = f.data/'kentei_tasks.csv'
        untouched = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                     for p in f.data.glob('*.csv') if p != path}
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True
        at.session_state['page_state'] = '管理（入力）'
        # A live session may still contain the old, unsafe selection.
        at.session_state['kt_admin_edit_student_0'] = '共通'
        at.run()
        at.selectbox(key='admin_section_selector').select('🎯 検定課題管理').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.selectbox(key='kt_admin_add_student').options, ['共通', '別生徒｜OTHER'])
        for i, sid in enumerate(owners):
            with self.subTest(owner=sid):
                at.selectbox(key='kt_admin_edit_target').set_value(i).run()
                target = at.selectbox(key=f'kt_admin_edit_target_student_{i}_{sid}')
                self.assertIn(sid, target.value)
                at.text_input(key=f'kt_admin_edit_name_{i}').set_value(f'変更済み{i}').run()
                at.button(key=f'kt_admin_edit_save_{i}').click().run()
                self.assertFalse(at.exception)
                saved = pd.read_csv(path, dtype=str).fillna('')
                self.assertEqual(saved.student_id.tolist(), owners)
                self.assertEqual(saved.iloc[i].task_name, f'変更済み{i}')
                at.number_input(key=f'kt_admin_edit_order_{i}').set_value(10*i+2).run()
                at.button(key=f'kt_admin_edit_save_{i}').click().run()
                saved = pd.read_csv(path, dtype=str).fillna('')
                self.assertEqual(saved.student_id.tolist(), owners)
                self.assertEqual(saved.iloc[i]['order'], str(10*i+2))
        at.selectbox(key='kt_admin_edit_target').set_value(0).run()
        at.selectbox(key='kt_admin_edit_target_student_0_IN').select('別生徒｜OTHER').run()
        at.button(key='kt_admin_edit_save_0').click().run()
        self.assertEqual(pd.read_csv(path).fillna('').iloc[0].student_id, 'OTHER')
        at.selectbox(key='kt_admin_edit_target_student_0_OTHER').select('共通').run()
        at.button(key='kt_admin_edit_save_0').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(pd.read_csv(path).fillna('').student_id.tolist(), ['', *owners[1:]])
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in untouched}, untouched)
