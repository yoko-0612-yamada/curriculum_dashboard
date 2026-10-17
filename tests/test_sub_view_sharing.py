"""Run-local sub-task display sharing; writers keep fresh reads."""
from datetime import date
from pathlib import Path
from unittest.mock import patch
import unittest
import pandas as pd
from .support import RegressionCase


class SubDisplayDataTests(RegressionCase):
    def test_daily_shared_matches_fresh_and_last_row_without_mutation(self):
        rows = pd.DataFrame([
            dict(student_id=' S ', date='2026-10-17', status=status)
            for status in ['pending', 'done', 'skip']
        ])
        self.call('save_sub_daily_check', rows)
        shared = self.call('load_sub_daily_check')
        before = shared.copy(deep=True)
        for sid in ['S', 'MISSING']:
            expected = self.call('get_sub_daily_check_row', sid, '2026-10-17')
            with patch.dict(self.ns, load_sub_daily_check=lambda: self.fail('shared display reread')):
                self.assertEqual(self.call('get_sub_daily_check_row', sid, '2026-10-17', checks_df=shared), expected)
        self.assertEqual(self.call('get_sub_daily_check_row', 'S', '2026-10-17', checks_df=shared)['status'], 'skip')
        pd.testing.assert_frame_equal(shared, before)

    def test_operations_read_fresh_after_display_snapshot(self):
        self.call('save_sub_curricula', pd.DataFrame([dict(sub_id='SUB', sub_name='課題', is_active='true')]))
        self.call('save_sub_curriculum_items', pd.DataFrame([
            dict(sub_id='SUB', item_id=f'I{i}', item_name=f'項目{i}', order=i, is_active='true') for i in [1, 2]
        ]))
        self.call('upsert_student_sub_progress', 'S', 'SUB', 'I1', True)
        day = str(date.today())
        pd.DataFrame([dict(student_id='S', date=day, kind='lesson')]).to_csv(self.ns['ATTENDANCE_LOG_CSV'], index=False)
        held = self.call('load_student_sub_progress')
        self.assertTrue(self.call('mark_sub_daily_skip', 'S', day)[0])
        self.assertEqual(self.call('get_sub_daily_check_row', 'S', day)['status'], 'skip')
        self.assertTrue(self.call('complete_and_confirm_sub_daily', 'S', day)[0])
        self.assertEqual(self.call('get_sub_daily_check_row', 'S', day)['status'], 'done')
        self.assertEqual(self.call('load_student_sub_progress').iloc[0].current_item_id, 'I2')
        self.assertEqual(held.iloc[0].current_item_id, 'I1')
        self.assertTrue(self.call('undo_latest_student_sub_completion', 'S')[0])
        self.call('reconcile_sub_daily_after_undo', 'S', day)
        self.assertEqual(self.call('load_student_sub_progress').iloc[0].current_item_id, 'I1')
        self.assertEqual(self.call('get_sub_daily_check_row', 'S', day)['status'], 'pending')


class SubDisplayUiTests(unittest.TestCase):
    def test_card_reads_constant_refresh_and_pause(self):
        from .test_progress_ui import ProgressUiTests
        from streamlit.testing.v1 import AppTest
        f = ProgressUiTests(); f.setUp(); self.addCleanup(f.doCleanups)
        ids = ['A', 'B', 'C']; day = str(date.today())
        f.write('students.csv', [dict(student_id=s, display_name=s, is_active='true') for s in ids])
        f.write('monthly_schedule.csv', [dict(student_id=s, date=day, slot='1', session_type='授業', reason='通常') for s in ids])
        f.write('timeslots.csv', [dict(slot='1', start_time='15:00', end_time='16:00')])
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True; at.run()
        original = pd.read_csv
        names = ['student_sub_progress.csv', 'sub_daily_check.csv']
        for status in ['pending', 'skip']:
            f.write(names[1], [dict(student_id='A', date=day, status=status)])
            counts = dict.fromkeys(names, 0)
            def read(p, *args, **kwargs):
                name = Path(str(p)).name
                if name in counts: counts[name] += 1
                return original(p, *args, **kwargs)
            with patch.object(pd, 'read_csv', read): at.run()
            self.assertFalse(at.exception)
            # Daily: summary before sync + cards after sync. No reuse across sync.
            self.assertEqual(counts, dict(zip(names, [1, 2])))
            self.assertEqual(sum(str(b.key).startswith('sub_daily_done_') for b in at.button), 1 if status == 'pending' else 0)
        pd.DataFrame([dict(feature='subtask', pause_start=day, resume_date='')]).to_csv(f.data/'feature_pause_periods.csv', index=False)
        counts = dict.fromkeys(names, 0)
        with patch.object(pd, 'read_csv', read): at.run()
        self.assertFalse(at.exception)
        self.assertEqual(counts, dict(zip(names, [0, 1])))
