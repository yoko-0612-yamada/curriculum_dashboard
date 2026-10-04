import pandas as pd
import unittest
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class CalendarHistoryTests(RegressionCase):
    def test_history_and_effective_rows_are_separate(self):
        students = pd.DataFrame([dict(student_id='S',display_name='退会済み架空',is_active='false',join_date='2026-10-02',leave_date='2026-10-03')])
        history = pd.DataFrame([dict(student_id='S',date=f'2026-10-0{i}',slot='1',session_type='授業',override_status='') for i in range(1,5)])
        before = history.copy(deep=True)
        result = self.call('calendar_effective_rows',history,students)
        self.assertEqual(result.date.tolist(),['2026-10-02','2026-10-03'])
        pd.testing.assert_frame_equal(history,before)
        history.loc[1,'override_status']='キャンセル'
        self.assertEqual(self.call('calendar_effective_rows',history,students).date.tolist(),['2026-10-03'])
        self.call('validate_schedule_destination',students,'S','2026-10-03')
        with self.assertRaises(ValueError):
            self.call('validate_schedule_destination',students,'S','2026-10-04')

    def test_zero_and_invalid_keep_original_history(self):
        students = pd.DataFrame([dict(student_id='S',is_active='false',join_date='',leave_date='')])
        history = pd.DataFrame([dict(student_id='S',date='2026-10-04',slot='1',session_type='授業')])
        before=history.copy(deep=True)
        self.assertTrue(self.call('calendar_effective_rows',history,students).empty)
        students['join_date']='invalid'
        with self.assertRaises(ValueError):
            self.call('calendar_effective_rows',history,students)
        pd.testing.assert_frame_equal(history,before)


class CalendarHistoryUiTests(unittest.TestCase):
    def test_saved_outside_and_cancelled_cards_remain_visible(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        f.write('students.csv',[dict(student_id='DEMO001',display_name='退会済み架空',is_active='false',join_date='2026-10-02',leave_date='2026-10-03')])
        f.write('monthly_schedule.csv',[dict(student_id='DEMO001',date=f'2026-10-0{i}',slot='1',session_type='授業',reason='通常') for i in [2,3,4]])
        f.write('schedule_overrides.csv',[dict(student_id='DEMO001',date='2026-10-02',slot='1',action='キャンセル',session_type='授業',note='振替元履歴'),dict(student_id='DEMO001',date='2026-10-03',slot='2',action='追加',session_type='自習',note='振替先')])
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=2026,monthly_schedule_month=10).items():at.session_state[k]=v
        at.session_state['monthly_view_mode_2026_10']='📅 編集'
        at.session_state['monthly_week_open_2026_10_1']=True
        at.run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        html='\n'.join(m.value for m in at.markdown)
        cards=[m.value for m in at.markdown if '<div title=' in m.value and '退会済み架空' in m.value]
        self.assertEqual(len(cards),4)
        self.assertTrue(any('line-through' in c for c in cards))
        self.assertIn('**1コマ**',html);self.assertIn('**2コマ**',html)
        # The first week's effective totals exclude both cancellation and Oct 4 history.
        self.assertTrue(any('授業1 / 自習1' in w.label for w in at.toggle))
        picks = [b for b in at.button if b.label=='選択']
        self.assertEqual(len(picks),4)
        picks[-1].click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertTrue(at.get('dialog'))
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)
