"""Per-sync progress reuse: real read counts, fresh next call, and failure safety."""
from unittest.mock import patch
import pandas as pd
from .support import RegressionCase, Stopped


class SubSyncReadTests(RegressionCase):
    def attendance(self, n):
        return pd.DataFrame([dict(student_id=f'S{i}', date='2026-10-14', kind='lesson') for i in range(n)],
                            columns=['student_id', 'date', 'kind'])

    def seed(self):
        for i in range(3):
            self.call('upsert_student_sub_progress', f'S{i}', 'SUB', f'I{i}', True)

    def test_reads_once_per_call_and_zero_without_targets(self):
        self.seed()
        path = self.ns['STUDENT_SUB_PROGRESS_CSV']
        original = (path.read_bytes(), path.stat().st_mtime_ns)
        reads = []
        read_csv = pd.read_csv
        def read(p, *args, **kwargs):
            if self.ns['Path'](p) == path:
                reads.append(p)
            return read_csv(p, *args, **kwargs)
        with patch.object(pd, 'read_csv', side_effect=read):
            for n, expected in [(3, 1), (3, 1), (1, 1), (0, 0)]:
                before = len(reads)
                self.call('sync_sub_daily_pending_for_date', self.attendance(n), '2026-10-14')
                self.assertEqual(len(reads) - before, expected)
            # Nonempty attendance with no matching date / no real student also avoids a read.
            before = len(reads)
            self.call('sync_sub_daily_pending_for_date', self.attendance(3), '2026-10-15')
            blank = self.attendance(1); blank['student_id'] = ''
            self.call('sync_sub_daily_pending_for_date', blank, '2026-10-14')
            self.assertEqual(len(reads), before)
        rows = self.call('load_sub_daily_check')
        self.assertEqual(rows.student_id.tolist(), ['S0', 'S1', 'S2'])
        self.assertEqual(rows.item_id.tolist(), ['I0', 'I1', 'I2'])
        self.assertEqual(rows.status.tolist(), ['pending'] * 3)
        self.assertEqual(rows.date.tolist(), ['2026-10-14'] * 3)
        self.assertTrue(rows.checked_at.eq('').all())
        self.assertEqual(original, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_next_sync_reads_fresh_progress_and_preserves_saved_checks(self):
        self.seed()
        self.call('sync_sub_daily_pending_for_date', self.attendance(3), '2026-10-14')
        old = self.call('load_sub_daily_check').copy()
        self.call('upsert_student_sub_progress', 'S0', 'SUB', 'NEXT', True)
        self.call('upsert_student_sub_progress', 'S1', 'SUB', 'I1', False)
        tomorrow = self.attendance(3); tomorrow['date'] = '2026-10-15'
        self.call('sync_sub_daily_pending_for_date', tomorrow, '2026-10-15')
        rows = self.call('load_sub_daily_check')
        pd.testing.assert_frame_equal(rows[rows.date.eq('2026-10-14')].reset_index(drop=True), old)
        newer = rows[rows.date.eq('2026-10-15')]
        self.assertEqual(newer.student_id.tolist(), ['S0', 'S2'])
        self.assertEqual(newer.item_id.tolist(), ['NEXT', 'I2'])

    def test_unreadable_progress_stops_before_any_write(self):
        self.seed()
        self.call('sync_sub_daily_pending_for_date', self.attendance(3), '2026-10-14')
        path = self.ns['STUDENT_SUB_PROGRESS_CSV']
        for content in [b'', b'\xff', b'student_id\n"broken']:
            path.write_bytes(content)
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.data.iterdir()}
            with self.assertRaises(Stopped):
                self.call('sync_sub_daily_pending_for_date', self.attendance(3), '2026-10-14')
            self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
            self.assertTrue(self.messages)
