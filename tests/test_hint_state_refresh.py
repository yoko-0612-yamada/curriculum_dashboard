"""Display snapshots must replace old hints, including empty results."""
from datetime import date, timedelta
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class HintStateRefreshTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        self.f = ProgressUiTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.day = str(date.today())
        self.students = [dict(student_id=s, display_name=s, is_active='true') for s in ['A', 'B']]
        self.f.write('students.csv', self.students)
        self.plans = [dict(student_id=s, date=self.day, slot='1', session_type='授業', reason='通常') for s in ['A', 'B']]
        self.f.write('monthly_schedule.csv', self.plans)
        self.f.write('timeslots.csv', [dict(slot=str(i), start_time='15:00', end_time='16:00') for i in [1,2]])
        self.courses = [dict(course_id=c, course_name=c, genre_id='G', course_order=i, is_active='true') for i,c in enumerate(['C1','C2'])]
        self.f.write('curriculum_courses.csv', self.courses)
        self.f.write('curriculum_tasks.csv', [dict(course_id=c, task_id=c+'T', task_name=c+'課題', order=1, is_active='true') for c in ['C1','C2']])
        self.at = AppTest.from_file(str(self.f.app), default_timeout=40)
        self.at.session_state['auth_ok'] = True

    def run_view(self):
        self.at.run()
        self.assertFalse(self.at.exception)
        return dict(self.at.session_state['today_task_hint_map'])

    def test_courses_empty_partial_reactivation_and_zero_plans(self):
        self.assertIn('C1課題', self.run_view()['A'])
        self.courses[0]['is_active'] = 'false'
        self.f.write('curriculum_courses.csv', self.courses)
        self.assertIn('C2課題', self.run_view()['A'])
        candidates = [x.value.removeprefix('今日やる候補：') for x in self.at.caption if x.value.startswith('今日やる候補：')]
        cards = [x.value.split('今日やる予定：',1)[1] for x in self.at.success if '今日やる予定：' in x.value]
        self.assertEqual(candidates, cards)
        self.courses[1]['is_active'] = 'false'
        self.f.write('curriculum_courses.csv', self.courses)
        self.assertEqual(self.run_view(), {})
        self.assertFalse(any('今日やる予定：' in x.value for x in self.at.success))
        self.courses[0]['is_active'] = 'true'
        self.f.write('curriculum_courses.csv', self.courses)
        self.assertIn('C1課題', self.run_view()['A'])
        self.f.write('monthly_schedule.csv', [])
        self.assertEqual(self.run_view(), {})
        self.assertEqual(dict(self.at.session_state['today_sub_hint_map']), {})

    def test_target_removed_and_exam_end_and_multiple_slots(self):
        self.run_view()
        self.students[1].update(join_date=str(date.today()+timedelta(days=1)))
        self.f.write('students.csv', self.students)
        self.assertEqual(set(self.run_view()), {'A'})
        # Both orders preserve lesson over self-study for a student with two slots.
        for types in [('授業','自習'), ('自習','授業')]:
            self.f.write('monthly_schedule.csv', [dict(student_id='A',date=self.day,slot=str(i),session_type=t,reason='通常') for i,t in enumerate(types,1)])
            self.assertIn('C1課題', self.run_view()['A'])
        self.f.write('kentei_exam_schedule.csv', [dict(student_id='A',grade='4',exam_date=self.day)])
        self.assertTrue(self.run_view()['A'].startswith('🎫 検定'))
        self.f.write('kentei_exam_schedule.csv', [])
        self.f.write('monthly_schedule.csv', [self.plans[0]])
        self.f.write('curriculum_courses.csv', [dict(c,is_active='false') for c in self.courses])
        self.assertEqual(self.run_view(), {})

    def test_sub_pause_resume_and_assignment_removed(self):
        self.f.write('sub_curricula.csv', [dict(sub_id='S',sub_name='サブ教材',is_active='true')])
        self.f.write('sub_curriculum_items.csv', [dict(sub_id='S',item_id='I',item_name='項目',order=1,is_active='true')])
        self.f.write('student_sub_progress.csv', [dict(student_id='A',sub_id='S',current_item_id='I',is_active='true')])
        self.run_view()
        before = dict(self.at.session_state['today_sub_hint_map'])
        self.assertIn('項目', before['A'])
        pause = self.f.data/'feature_pause_periods.csv'
        pd.DataFrame([dict(feature='subtask',pause_start=self.day,resume_date='')]).to_csv(pause,index=False)
        self.run_view()
        self.assertEqual(dict(self.at.session_state['today_sub_hint_map']), {})
        pd.DataFrame([dict(feature='subtask',pause_start=self.day,resume_date=self.day)]).to_csv(pause,index=False)
        self.run_view()
        self.assertEqual(dict(self.at.session_state['today_sub_hint_map']), before)
        self.f.write('student_sub_progress.csv', [])
        self.run_view()
        self.assertEqual(dict(self.at.session_state['today_sub_hint_map']), {})
