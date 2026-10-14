"""Hint-local sharing; temporary CSVs only, no Streamlit startup."""
import ast
from datetime import date
from unittest.mock import Mock

import pandas as pd

from .support import APP, RegressionCase, Stopped


class TodayHintReadsTests(RegressionCase):
    def setUp(self):
        super().setUp()
        tree = ast.parse(APP.read_text())
        names = {'_passed_kentei_grades_for_student',
                 '_recommended_kentei_grade_for_candidate', '_today_task_hint'}
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP), 'exec'), self.ns)
        self.ns['kentei_exam'] = pd.DataFrame()
        self.ns['load_kentei_training_status'] = lambda: pd.DataFrame()
        self.ns['_next_kentei_task_hint'] = lambda sid, grade: f'検定：{grade}級 / 課題'
        self.ns['_next_curriculum_task_hint'] = lambda sid: '通常：コース / 課題'

    def legacy_hint(self, sid):
        # Before sharing: recommendation reads once, pending-exam check reads again.
        n = self.ns
        grade = n['_recommended_kentei_grade_for_candidate'](sid)
        training = n['load_kentei_training_status']()
        active = n['is_kentei_training_active'](sid, training_df=training)
        training_grade = n['get_kentei_training_grade'](sid, training_df=training)
        if active and training_grade:
            grade = training_grade
        pending = False
        if grade:
            passed = n['_passed_kentei_grades_for_student'](sid)
            exam = n['kentei_exam'].copy()
            if not exam.empty:
                for c in ['student_id', 'grade']:
                    if c not in exam.columns:
                        exam[c] = ''
                    exam[c] = exam[c].fillna('').astype(str).str.strip()
                pending = bool(((exam.student_id == sid.strip()) & (exam.grade == grade)
                                & (~exam.grade.isin(passed))).any())
        return n['_next_kentei_task_hint'](sid, grade) if active or pending else n['_next_curriculum_task_hint'](sid)

    def test_results_and_read_counts_match_legacy(self):
        for grades, exam_grade, training_grade in [
            ([], '', ''), ([], '4', ''), (['4'], '4', ''),
            (['4'], '3', ''), (['4','3','2','1'], '', ''),
            (['4','3','2','1'], '1', '2'), ([], '', '3'),
        ]:
            with self.subTest(grades=grades, exam=exam_grade, training=training_grade):
                results = pd.DataFrame([{'student_id':' S ', 'grade':f' {g} '} for g in grades]
                                       + [{'student_id':'OTHER', 'grade':'3'}])
                loader = Mock(side_effect=lambda: results.copy())
                self.ns['load_kentei_results'] = loader
                self.ns['kentei_exam'] = pd.DataFrame([{'student_id':' S ', 'grade':exam_grade,
                    'exam_date':str(date.today())}]) if exam_grade else pd.DataFrame()
                self.ns['load_kentei_training_status'] = lambda: pd.DataFrame([
                    {'student_id':'S', 'grade':training_grade, 'is_training':'true'}
                ]) if training_grade else pd.DataFrame()
                old = self.legacy_hint('S')
                old_reads = loader.call_count
                loader.reset_mock()
                self.assertEqual(self.call('_today_task_hint', 'S'), old)
                self.assertEqual(loader.call_count, 1)
                self.assertEqual(old_reads, 1 if len(grades)==4 and not training_grade else 2)
                # A new invocation must fetch again, not retain a prior result.
                self.call('_today_task_hint', 'S')
                self.assertEqual(loader.call_count, 2)

    def test_empty_and_missing_results_keep_behavior(self):
        loader = self.ns['load_kentei_results']
        path = self.ns['KENTEI_RESULTS_CSV']
        for missing in [True, False]:
            with self.subTest(missing=missing):
                if not missing:
                    path.write_text('student_id,grade,passed_date\n')
                wrapped = Mock(wraps=loader)
                self.ns['load_kentei_results'] = wrapped
                old = self.legacy_hint('S')
                wrapped.reset_mock()
                self.assertEqual(self.call('_today_task_hint', 'S'), old)
                self.assertEqual(wrapped.call_count, 1)

    def test_unreadable_results_stop_and_preserve_file(self):
        path = self.ns['KENTEI_RESULTS_CSV']
        for content in [b'', b'\xff\xfe\xfa', b'student_id,grade\n"broken']:
            with self.subTest(content=content):
                path.write_bytes(content)
                before = (path.read_bytes(), path.stat().st_mtime_ns)
                self.messages.clear()
                with self.assertRaises(Stopped):
                    self.legacy_hint('S')
                old_errors = self.messages.copy()
                self.messages.clear()
                with self.assertRaises(Stopped):
                    self.call('_today_task_hint', 'S')
                self.assertEqual(self.messages, old_errors)
                self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
