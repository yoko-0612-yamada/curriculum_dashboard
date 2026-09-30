import ast
import pandas as pd
from .support import APP, RegressionCase, Stopped


class CsvAndSeatTests(RegressionCase):
    def test_kentei_missing_initializes(self):
        path = self.ns['KENTEI_RESULTS_CSV']
        self.assertFalse(path.exists())
        self.assertTrue(self.call('load_kentei_results').empty)
        self.assertTrue(path.exists())

    def test_kentei_valid_empty_is_available(self):
        path = self.ns['KENTEI_RESULTS_CSV']
        path.write_text('student_id,grade,result,score,pass_date,memo\n')
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.assertTrue(self.call('load_kentei_results').empty)
        self.assertFalse(self.messages)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_kentei_failures_never_overwrite(self):
        path = self.ns['KENTEI_RESULTS_CSV']
        for content in [b'', b'student_id,grade\n"broken', b'\xff\xfe\x81']:
            with self.subTest(content=content):
                path.write_bytes(content)
                before = (path.read_bytes(), path.stat().st_mtime_ns)
                with self.assertRaises(Stopped):
                    self.call('load_kentei_results')
                self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
                self.assertTrue(self.messages)

    def test_kentei_legacy_record(self):
        self.ns['KENTEI_RESULTS_CSV'].write_text('student_id,grade\nS1,4\n')
        self.assertTrue(self.call('is_kentei_passed', 'S1', '4'))
        self.assertFalse(self.call('is_kentei_passed', 'S1', '3'))

    def test_slot_normalization(self):
        for value in [3, '3', 3.0, '3.0', ' 3 ']:
            with self.subTest(value=value):
                self.assertEqual('3', self.call('normalize_slot', value))
        self.assertEqual('特別', self.call('normalize_slot', '特別'))

    def test_note_retention_and_other_fields(self):
        original = pd.DataFrame([
            dict(student_id='S1', weekday='水', slot='3', session_type='授業',
                 week_pattern='毎週', note=' メモ\n保持 '),
            dict(student_id='S2', weekday='水', slot='3', session_type='授業',
                 week_pattern='毎週', note='別画面のメモ'),
        ])
        for column, value in [('week_pattern', '第1・第3'), ('session_type', '自習')]:
            with self.subTest(column=column):
                edited = original.copy()
                edited.loc[0, column] = value
                result = self.call('prepare_student_schedule_for_save', edited)
                pd.testing.assert_frame_equal(result, edited)
                self.call('write_csv_atomic', result, self.data/'schedule.csv')
                actual = pd.read_csv(self.data/'schedule.csv', dtype=str, keep_default_na=False)
                pd.testing.assert_frame_equal(actual, edited)
        result = self.call('prepare_student_schedule_for_save', original.drop(columns='note'))
        self.assertEqual(['', ''], result.note.tolist())

    def test_all_schedule_save_routes_preserve_columns(self):
        # Structural contract, independent of line numbers: new save routes must
        # also use the common column-preserving preparation function.
        tree = ast.parse(APP.read_text())
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name)
                 and n.func.id in ['write_csv', 'write_csv_atomic']
                 and len(n.args) > 1 and isinstance(n.args[1], ast.Name)
                 and n.args[1].id == 'STUDENT_SCHEDULE_CSV']
        self.assertTrue(calls)
        for node in calls:
            self.assertIsInstance(node.args[0], ast.Call)
            self.assertEqual('prepare_student_schedule_for_save', node.args[0].func.id)

    def test_seat_move_scope_and_reserved(self):
        key = lambda d, s, n: f'seat_grid_{d}_{s}_{n}'
        self.state.update({key('D','3','1'):'S1', key('D','3','3'):'S1',
                           key('D','4','1'):'S1', key('E','3','1'):'S1',
                           key('D','3','2'):'S2'})
        self.call('move_selected_student_to_seat', 'D','3','3')
        self.assertEqual('', self.state[key('D','3','1')])
        for d, s in [('D','4'),('E','3')]:
            self.assertEqual('S1', self.state[key(d,s,'1')])
        self.assertEqual('S2', self.state[key('D','3','2')])
        self.assertEqual('S1', self.state[key('D','3','3')])
        for value in ['', '__RESERVED__']:
            self.state[key('D','3','1')] = value
            self.state[key('D','3','3')] = value
            before = self.state.copy()
            self.call('move_selected_student_to_seat', 'D','3','3')
            self.assertEqual(before, self.state)

    def test_syntax(self):
        compile(APP.read_text(encoding='utf-8'), str(APP), 'exec')
