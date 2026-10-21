"""Today's post-attendance skip correction uses only temporary data."""
from datetime import date, timedelta
import unittest
import pandas as pd
from . import test_separate_input_screens as fixtures

class TodayProgressSkipTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SeparateInputScreensTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.at.session_state['daily_input_mode'] = '進捗登録'
        self.key = f'today_no_progress_{self.f.day}_{self.f.sid}'
        self.cancel = f'today_no_progress_cancel_{self.f.day}_{self.f.sid}'

    def launch(self, attended=True):
        if attended:
            self.f.f.write('attendance_log.csv', [dict(date=self.f.day,student_id=self.f.sid,kind='lesson')])
        self.f.run_view()

    def progress_count(self, n):
        self.assertTrue(any(f'進捗 {n} /' in x.value for x in self.f.at.markdown))

    def test_register_cancel_and_keep_other_records(self):
        other = [dict(date=str(date.today()-timedelta(days=1)),student_id=self.f.sid,note='past'),
                 dict(date=self.f.day,student_id='OTHER',note='other')]
        self.f.f.write('progress_skip_ok.csv',other)
        self.launch()
        protected={p:p.read_bytes() for p in [self.f.f.data/n for n in ['attendance_log.csv','curriculum_progress.csv','kentei_progress.csv']]}
        self.progress_count(1)
        self.assertFalse(self.f.at.button(key=self.key).disabled)
        self.f.at.button(key=self.key).click().run()
        self.assertFalse(self.f.at.exception)
        self.assertTrue(any('進捗なしで完了済み' in x.value for x in self.f.at.success))
        self.progress_count(0)
        self.assertNotIn(self.key,self.f.keys())
        self.assertEqual(len(pd.read_csv(self.f.f.data/'progress_skip_ok.csv')),3)
        self.f.at.button(key=self.cancel).click().run()
        self.assertFalse(self.f.at.exception)
        self.progress_count(1)
        self.assertIn(self.key,self.f.keys())
        self.assertEqual(pd.read_csv(self.f.f.data/'progress_skip_ok.csv').to_dict('records'),other)
        for p,b in protected.items(): self.assertEqual(p.read_bytes(),b)

    def test_registered_progress_and_no_attendance(self):
        self.launch(False)
        self.assertNotIn(self.key,self.f.keys())
        self.assertTrue(any('今日は出席登録されていません' in x.value for x in self.f.at.info))
        for kind in ['curriculum','kentei']:
            with self.subTest(kind=kind):
                for name in ['curriculum','kentei']: self.f.f.write(name+'_progress.csv',[])
                self.f.f.write(kind+'_progress.csv',[dict(student_id=self.f.sid,course_id='DEMO_C01',grade='4',task_id='DEMO_T01' if kind=='curriculum' else 'DEMO_K01',is_done='true',done_date=self.f.day)])
                self.launch()
                self.assertNotIn(self.key,self.f.keys())
                self.assertTrue(any('今日の進捗は登録済みです' in x.value for x in self.f.at.success))
                self.progress_count(0)
                self.assertTrue(pd.read_csv(self.f.f.data/'progress_skip_ok.csv').empty)

    def test_coexisting_skip_cancellation_keeps_progress(self):
        self.f.f.write('progress_skip_ok.csv',[dict(student_id=self.f.sid,date=self.f.day,note='existing')])
        self.f.f.write('curriculum_progress.csv',[dict(student_id=self.f.sid,course_id='DEMO_C01',task_id='DEMO_T01',is_done='true',done_date=self.f.day)])
        self.launch()
        before=(self.f.f.data/'curriculum_progress.csv').read_bytes()
        self.assertNotIn(self.key,self.f.keys())
        self.f.at.button(key=self.cancel).click().run()
        self.assertFalse(self.f.at.exception)
        self.progress_count(0)
        self.assertEqual(before,(self.f.f.data/'curriculum_progress.csv').read_bytes())
