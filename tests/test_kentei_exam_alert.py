"""受験回ごとの上部アラートと個別画面の照合（ファイル書込みなし）。"""
import ast
import textwrap
import unittest
from datetime import date, timedelta
import pandas as pd
from .support import APP


class KenteiExamAlertTests(unittest.TestCase):
    def setUp(self):
        source = APP.read_text()
        tree = ast.parse(source)
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name in {'kentei_result_status_for_exam', '_kentei_result_status'}]
        self.ns = {'pd': pd, 'date': date}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP), 'exec'), self.ns)
        start = source.index('    kentei_alert_rows = []', source.index('# ⚠ 検定結果未登録アラート'))
        end = source.index('    # 表示\n', start)
        self.block = compile(textwrap.dedent(source[start:end]), str(APP), 'exec')
        self.today = str(date.today())
        self.old = str(date.today() - timedelta(days=30))

    def check(self, results, schedules=None):
        results_df = pd.DataFrame(results, columns=['student_id','grade','result','pass_date'])
        schedules = schedules or [('A','3',self.today)]
        schedule_df = pd.DataFrame([dict(student_id=s, grade=g, exam_date=d, exam_type='プログラミング', kentei='') for s,g,d in schedules])
        before = results_df.copy(deep=True)
        n = self.ns
        n.update(students=pd.DataFrame(columns=['student_id','display_name']),
                 safe_read_csv=lambda *a, **kw: schedule_df.copy(),
                 KENTEI_EXAM_SCHEDULE_CSV='', load_kentei_results=lambda: results_df.copy(),
                 _view_kentei_results=results_df.copy())
        exec(self.block, n)
        alerts = {(r['student_id'],r['grade'],r['受験日']) for r in n['kentei_alert_rows']}
        for sid, grade, day in schedules:
            n.update(_results_chk=results_df, student_for_pass=sid)
            status = n['_kentei_result_status']({'grade':grade,'_exam_date_str':day})
            parsed = pd.to_datetime(day, errors='coerce')
            expected = pd.notna(parsed) and parsed.date() <= date.today() and status in ['未登録','同じ級の受験履歴あり']
            self.assertEqual((sid,grade,day) in alerts, expected)
        pd.testing.assert_frame_equal(results_df,before)
        return alerts

    def test_first_attempt_missing(self):
        self.assertTrue(self.check([]))

    def test_first_attempt_recorded(self):
        self.assertFalse(self.check([('A','3','合格',self.today)]))

    def test_retake_old_failure_only(self):
        self.assertTrue(self.check([('A','3','不合格',self.old)]))

    def test_retake_recorded_pass_or_fail(self):
        for result in ['合格','不合格']:
            self.assertFalse(self.check([('A','3','不合格',self.old),('A','3',result,self.today)]))

    def test_other_grade_history(self):
        self.assertTrue(self.check([('A','4','合格',self.old)]))

    def test_students_independent(self):
        self.assertEqual(self.check([('A','3','合格',self.today)], [('A','3',self.today),('B','3',self.today)]), {('B','3',self.today)})

    def test_attempt_dates_independent(self):
        self.assertEqual(self.check([('A','3','不合格',self.old)], [('A','3',self.old),('A','3',self.today)]), {('A','3',self.today)})

    def test_future_excluded(self):
        self.assertFalse(self.check([], [('A','3',str(date.today()+timedelta(days=1)))]))

    def test_blank_invalid_result_dates(self):
        for day in ['', None, 'not-a-date', '2026-02-30']:
            with self.subTest(day=day):
                self.assertTrue(self.check([('A','3','不合格',day)]))

    def test_date_normalization_and_invalid_schedule(self):
        self.assertFalse(self.check([('A','3','合格',self.today.replace('-','/'))]))
        self.assertFalse(self.check([], [('A','3','bad-date')]))
