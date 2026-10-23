"""New-calendar candidates follow the chosen date; production data is never used."""
import ast
from datetime import date
import unittest
from streamlit.testing.v1 import AppTest
from . import test_progress_ui as fixtures
from .support import APP

class CalendarAddCandidatesTests(unittest.TestCase):
    def launch(self, rows, entry='授業'):
        f=fixtures.ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        f.write('students.csv',rows)
        # Keep the dialog open across full AppTest reruns (real UI uses dialog reruns).
        source=f.app.read_text().replace('            if open_monthly_add_from_fixed:',
            f'            if True:\n                open_monthly_add_from_fixed = {entry!r}',1)
        f.app.write_text(source)
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=2026,monthly_schedule_month=10,monthly_add_date_2026_10=date(2026,10,10)).items():at.session_state[k]=v
        at.session_state['monthly_view_mode_2026_10']='📅 編集'
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        return f,at

    def row(self,sid,join='',leave='',active='true'):
        return dict(student_id=sid,display_name=sid,join_date=join,leave_date=leave,is_active=active)

    def options(self,at):
        return at.selectbox(key='monthly_add_student_2026_10').options

    def test_boundaries_legacy_and_false_active(self):
        f,at=self.launch([self.row('PERIOD','2026-10-10','2026-10-20','false'),
                         self.row('FUTURE','2026-10-20'),self.row('LEGACY'),
                         self.row('RETIRED','','','false')])
        self.assertEqual(self.options(at),['PERIOD','LEGACY'])
        for day,expected in [(9,['LEGACY']),(20,['PERIOD','FUTURE','LEGACY']),(21,['FUTURE','LEGACY'])]:
            at.date_input(key='monthly_add_date_2026_10').set_value(date(2026,10,day)).run()
            self.assertFalse(at.exception)
            self.assertEqual(self.options(at),expected)

    def test_date_change_clears_selection_and_zero_never_falls_back(self):
        f,at=self.launch([self.row('OLD','2026-10-01','2026-10-10'),self.row('NEW','2026-10-11','2026-10-20')],'自習')
        self.assertEqual(at.selectbox(key='monthly_add_student_2026_10').value,'OLD')
        at.date_input(key='monthly_add_date_2026_10').set_value(date(2026,10,11)).run()
        self.assertEqual(at.selectbox(key='monthly_add_student_2026_10').value,'NEW')
        self.assertEqual(at.session_state['monthly_add_student_2026_10'],'NEW')
        at.date_input(key='monthly_add_date_2026_10').set_value(date(2026,10,21)).run()
        self.assertFalse(at.exception)
        self.assertFalse([x for x in at.selectbox if x.key=='monthly_add_student_2026_10'])
        self.assertNotIn('monthly_add_student_2026_10',at.session_state)
        self.assertTrue(any('この日に追加できる在籍生徒はいません' in x.value for x in at.info))
        self.assertTrue(next(b for b in at.button if '新規予定を一覧へ追加' in b.label).disabled)
        self.assertTrue((f.data/'monthly_schedule.csv').read_text().count('\n')==1)

    def test_invalid_dates_stop_dialog_without_writing(self):
        for join,leave in [('invalid',''),('2026-10-01','invalid'),('2026-10-20','2026-10-10')]:
            with self.subTest(join=join,leave=leave):
                f,at=self.launch([self.row('BAD',join,leave)])
                self.assertTrue(any('在籍日付を確認してください' in x.value for x in at.error))
                self.assertFalse([b for b in at.button if '新規予定を一覧へ追加' in b.label])
                self.assertEqual((f.data/'monthly_schedule.csv').read_text().count('\n'),1)

    def test_shared_entries_and_final_guard_remain(self):
        tree=ast.parse(APP.read_text())
        dialog=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_open_monthly_add_dialog' and len(n.body)>1)
        calls=[n.func.id for n in ast.walk(dialog) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        self.assertIn('student_enrollment_mask',calls)
        self.assertIn('require_schedule_destination',calls)
        source=ast.get_source_segment(APP.read_text(),dialog)
        self.assertLess(source.index('add_date ='),source.index('with st.form'))
        self.assertIn('monthly_open_add_dialog_fixed_{add_type}',APP.read_text())
        self.assertIn('"➕ 新しい予定"',APP.read_text())
        self.assertIn('(fixed_lesson_col, "授業")',APP.read_text())
        self.assertIn('(fixed_selfstudy_col, "自習")',APP.read_text())
