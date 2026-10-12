"""Unreadable training/sub-task files must never become empty update bases."""
from unittest.mock import patch
import pandas as pd
from .support import RegressionCase, Stopped


class TrainingSubReadProtectionTests(RegressionCase):
    routes = [
        ('SUB_CURRICULA_CSV', 'SUB_CURRICULA_COLS', 'sub_curricula'),
        ('SUB_CURRICULUM_ITEMS_CSV', 'SUB_CURRICULUM_ITEMS_COLS', 'sub_curriculum_items'),
        ('STUDENT_SUB_PROGRESS_CSV', 'STUDENT_SUB_PROGRESS_COLS', 'student_sub_progress'),
        ('SUB_PROGRESS_LOG_CSV', 'SUB_PROGRESS_LOG_COLS', 'sub_progress_log'),
        ('SUB_DAILY_CHECK_CSV', 'SUB_DAILY_CHECK_COLS', 'sub_daily_check'),
    ]

    def snapshot(self):
        return {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.data.iterdir() if p.is_file()}

    def assert_stops_unchanged(self, operation):
        before = self.snapshot()
        with self.assertRaises(Stopped):
            operation()
        self.assertEqual(before, self.snapshot())
        self.assertTrue(self.messages)

    def test_training_invalid_update_and_direct_save(self):
        path = self.ns['KENTEI_TRAINING_STATUS_CSV']
        for content in [b'', b'\xff\xfe', b'student_id,grade\n"broken']:
            path.write_bytes(content)
            for operation in [
                lambda: self.call('upsert_kentei_training_status', 'S1', True, '4'),
                lambda: self.call('save_kentei_training_status', pd.DataFrame()),
            ]:
                with self.subTest(content=content):
                    self.assert_stops_unchanged(operation)
        self.assertIn('検定練習状態ファイルを読み込めない', self.messages[-1])

    def test_training_missing_empty_and_existing(self):
        path = self.ns['KENTEI_TRAINING_STATUS_CSV']
        for mode in ['missing', 'empty', 'existing']:
            if path.exists():
                path.unlink()
            if mode != 'missing':
                rows = [dict(student_id='S2', is_training='true', grade='3', note='保持')] if mode == 'existing' else []
                pd.DataFrame(rows, columns=self.ns['KENTEI_TRAINING_STATUS_COLS']).to_csv(path, index=False)
            self.call('upsert_kentei_training_status', 'S1', True, '4')
            result = self.call('load_kentei_training_status')
            self.assertEqual(len(result), 2 if mode == 'existing' else 1)
            self.assertTrue(self.call('is_kentei_training_active', 'S1'))
            self.assertEqual(self.call('get_kentei_training_grade', 'S1'), '4')
            if mode == 'existing':
                self.assertEqual(result.loc[result.student_id.eq('S2'), 'note'].iloc[0], '保持')

    def test_every_sub_loader_and_save_rejects_invalid_files(self):
        for key, cols, name in self.routes:
            for content in [b'', b'\xff\xfe', b'a,b\n"broken']:
                self.ns[key].write_bytes(content)
                with self.subTest(route=name, content=content):
                    self.assert_stops_unchanged(lambda: self.call('load_' + name))
                    # Covers direct saves from a previously loaded editor as well.
                    self.assert_stops_unchanged(lambda: self.call('save_' + name, pd.DataFrame(columns=self.ns[cols])))
        self.assertIn('保存・自動同期できません', self.messages[-1])

    def test_every_sub_route_missing_empty_and_existing(self):
        for key, cols, name in self.routes:
            path = self.ns[key]
            for mode in ['missing', 'empty', 'existing']:
                if path.exists():
                    path.unlink()
                if mode != 'missing':
                    rows = [dict.fromkeys(self.ns[cols], '保持')] if mode == 'existing' else []
                    pd.DataFrame(rows, columns=self.ns[cols]).to_csv(path, index=False)
                before = self.snapshot()
                df = self.call('load_' + name)
                self.assertEqual(before, self.snapshot())  # loading never initializes on disk
                new = pd.DataFrame([dict.fromkeys(self.ns[cols], '追加')])
                expected = pd.concat([df, new], ignore_index=True)
                self.call('save_' + name, expected)
                pd.testing.assert_frame_equal(self.call('load_' + name), expected, check_dtype=False)

    def test_daily_update_failure_and_initial_creation(self):
        path = self.ns['SUB_DAILY_CHECK_CSV']
        path.write_bytes(b'\xff')
        operation = lambda: self.call('upsert_sub_daily_check', 'S1', '2026-10-12', 'done', sub_id='SUB1', item_id='I1')
        self.assert_stops_unchanged(operation)
        for mode in ['missing', 'empty']:
            path.unlink()
            if mode == 'empty':
                pd.DataFrame(columns=self.ns['SUB_DAILY_CHECK_COLS']).to_csv(path, index=False)
            operation()
            self.assertEqual(self.call('load_sub_daily_check').status.tolist(), ['done'])

    def seed_sub(self):
        self.call('save_sub_curricula', pd.DataFrame([dict(sub_id='SUB1', sub_name='教材', is_active='true')]))
        self.call('save_sub_curriculum_items', pd.DataFrame([dict(sub_id='SUB1', item_id='I1', item_name='項目', order='1', is_active='true')]))
        self.call('upsert_student_sub_progress', 'S1', 'SUB1', 'I1', True)
        self.call('save_sub_progress_log', pd.DataFrame(columns=self.ns['SUB_PROGRESS_LOG_COLS']))
        self.call('save_sub_daily_check', pd.DataFrame(columns=self.ns['SUB_DAILY_CHECK_COLS']))

    def test_automatic_sync_stops_without_any_write(self):
        attendance = pd.DataFrame([dict(student_id='S1', date='2026-10-12', kind='lesson')])
        for key in ['SUB_DAILY_CHECK_CSV', 'SUB_PROGRESS_LOG_CSV', 'STUDENT_SUB_PROGRESS_CSV']:
            self.seed_sub()
            path = self.ns[key]
            original = path.read_bytes()
            path.write_bytes(b'\xff')
            self.assert_stops_unchanged(lambda: self.call('sync_sub_daily_pending_for_date', attendance, '2026-10-12'))
            path.write_bytes(original)
        self.call('sync_sub_daily_pending_for_date', attendance, '2026-10-12')
        self.assertEqual(self.call('load_sub_daily_check').status.tolist(), ['pending'])

    def test_completion_stops_before_writes_on_read_failure(self):
        for key in ['SUB_CURRICULA_CSV', 'SUB_CURRICULUM_ITEMS_CSV', 'STUDENT_SUB_PROGRESS_CSV', 'SUB_PROGRESS_LOG_CSV']:
            self.seed_sub()
            path = self.ns[key]
            original = path.read_bytes()
            path.write_bytes(b'\xff')
            self.assert_stops_unchanged(lambda: self.call('complete_and_advance_student_sub_task', 'S1'))
            path.write_bytes(original)

    def test_io_error_stops_without_writes(self):
        self.seed_sub()
        self.call('upsert_kentei_training_status', 'S1', True)
        with patch.object(pd, 'read_csv', side_effect=PermissionError('read denied')):
            self.assert_stops_unchanged(lambda: self.call('upsert_kentei_training_status', 'S1', False))
            for _, cols, name in self.routes:
                self.assert_stops_unchanged(lambda: self.call('save_' + name, pd.DataFrame(columns=self.ns[cols])))
