"""Direct atomic-write tests use only disposable files."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
from unittest.mock import Mock, patch
import pandas as pd
from .support import RegressionCase


class AtomicWriteTests(RegressionCase):
    def setUp(self):
        super().setUp()
        self.path = self.data / 'target.csv'
        self.path.write_bytes(b'value\nOLD\n')
        self.before = (self.path.read_bytes(), self.path.stat().st_mtime_ns)
        self.clear = Mock()
        self.ns['clear_csv_cache'] = self.clear
        self.df = pd.DataFrame({'value': ['日本語,"引用"\n次行', '', None], 'number': [1.5, 0, None]})

    def assert_original(self):
        self.assertEqual(self.before, (self.path.read_bytes(), self.path.stat().st_mtime_ns))
        self.clear.assert_not_called()

    def test_success_matches_previous_bytes_and_closes_before_replace(self):
        factory = tempfile.NamedTemporaryFile
        replace = Path.replace
        files = []
        def create(*args, **kwargs):
            f = factory(*args, **kwargs)
            files.append(f)
            return f
        def closed_replace(src, dst):
            self.assertTrue(files[-1].closed)
            self.assertEqual(src.parent, self.path.parent)
            self.assertNotEqual(src, self.path.with_suffix('.csv.tmp'))
            return replace(src, dst)
        for df in [self.df, self.df.iloc[:0]]:
            expected = self.data / 'expected.csv'
            df.to_csv(expected, index=False, encoding='utf-8')
            with patch.object(tempfile, 'NamedTemporaryFile', side_effect=create), patch.object(Path, 'replace', closed_replace):
                self.call('write_csv_atomic', df, str(self.path))
            self.assertEqual(expected.read_bytes(), self.path.read_bytes())
            self.assertEqual(list(self.data.glob('*.tmp')), [])
        self.assertEqual(self.clear.call_count, 2)

    def test_overlapping_writers_have_separate_complete_files(self):
        barrier = threading.Barrier(2)
        replace = Path.replace
        paths, published = [], []
        lock = threading.Lock()
        frames = [pd.DataFrame({'value': [label] * 1000}) for label in ['A', 'B']]
        expected = [df.to_csv(index=False).encode('utf-8') for df in frames]
        def overlap(src, dst):
            with lock:
                paths.append(src)
                self.assertIn(src.read_bytes(), expected)
            barrier.wait(timeout=10)
            with lock:
                result = replace(src, dst)
                published.append(Path(dst).read_bytes())
                return result
        with patch.object(Path, 'replace', overlap), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.call, 'write_csv_atomic', df, self.path) for df in frames]
            for future in futures:
                future.result(timeout=15)
        self.assertEqual(len(set(paths)), 2)
        self.assertEqual(set(published), set(expected))
        self.assertIn(self.path.read_bytes(), expected)
        self.assertEqual(list(self.data.glob('*.tmp')), [])
        self.assertEqual(self.clear.call_count, 2)

    def test_write_failure_cleans_only_own_temp(self):
        other = self.data / 'target.csv.other.tmp'
        other.write_bytes(b'other writer')
        error = OSError('write failed')
        def fail(_df, f, **kwargs):
            f.write('partial')
            raise error
        with patch.object(pd.DataFrame, 'to_csv', fail):
            with self.assertRaises(OSError) as caught:
                self.call('write_csv_atomic', self.df, self.path)
        self.assertIs(caught.exception, error)
        self.assert_original()
        self.assertEqual(list(self.data.glob('*.tmp')), [other])
        self.assertEqual(other.read_bytes(), b'other writer')

    def test_replace_failure_cleans_temp(self):
        error = PermissionError('replace denied')
        with patch.object(Path, 'replace', side_effect=error):
            with self.assertRaises(PermissionError) as caught:
                self.call('write_csv_atomic', self.df, self.path)
        self.assertIs(caught.exception, error)
        self.assert_original()
        self.assertEqual(list(self.data.glob('*.tmp')), [])

    def test_cleanup_failure_preserves_original_exception(self):
        error = OSError('original save error')
        with patch.object(Path, 'replace', side_effect=error), patch.object(Path, 'unlink', side_effect=PermissionError('cleanup denied')):
            with self.assertRaises(OSError) as caught:
                self.call('write_csv_atomic', self.df, self.path)
        self.assertIs(caught.exception, error)
        self.assert_original()
        self.assertEqual(len(list(self.data.glob('*.tmp'))), 1)

    def test_creation_failure_does_not_touch_other_files(self):
        with patch.object(tempfile, 'NamedTemporaryFile', side_effect=PermissionError('create denied')):
            with self.assertRaises(PermissionError):
                self.call('write_csv_atomic', self.df, self.path)
        self.assert_original()
        self.assertEqual(list(self.data.glob('*.tmp')), [])

    def test_close_failure_cleans_temp(self):
        factory = tempfile.NamedTemporaryFile
        error = OSError('close failed')
        class CloseFailure:
            def __init__(self, f):
                self.f, self.name = f, f.name
            def __enter__(self):
                return self
            def write(self, value):
                return self.f.write(value)
            def __exit__(self, *args):
                self.f.close()
                raise error
        with patch.object(tempfile, 'NamedTemporaryFile', side_effect=lambda **kw: CloseFailure(factory(**kw))):
            with self.assertRaises(OSError) as caught:
                self.call('write_csv_atomic', self.df, self.path)
        self.assertIs(caught.exception, error)
        self.assert_original()
        self.assertEqual(list(self.data.glob('*.tmp')), [])

    def test_monthly_confirmation_and_rollback(self):
        cols = self.ns['MONTHLY_SCHEDULE_COLS']
        old = pd.DataFrame([dict(student_id='S1', date='2026-10-01', slot='1', session_type='授業')]).reindex(columns=cols, fill_value='')
        self.call('save_monthly_schedule_with_confirmation', old, ['2026-10'])
        csv = self.ns['MONTHLY_SCHEDULE_CSV']
        state = self.ns['MONTHLY_SCHEDULE_CONFIRMATION_JSON']
        self.assertIn('2026-10', self.call('load_monthly_schedule_confirmation')['confirmed_months'])
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in [csv, state]}
        new = old.copy()
        new['slot'] = '2'
        replace = Path.replace
        def fail_state(src, dst):
            if Path(dst) == state:
                raise PermissionError('state replace failed')
            return replace(src, dst)
        with patch.object(Path, 'replace', fail_state):
            with self.assertRaises(PermissionError):
                self.call('save_monthly_schedule_with_confirmation', new, ['2026-10'])
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
        self.assertEqual(list(self.data.glob('*.tmp')), [])
