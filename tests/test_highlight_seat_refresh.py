"""Highlight reset and saved default-seat warning refresh (temporary files only)."""
import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class SeatPlanTests(RegressionCase):
    def test_conflicts_reserved_cancellation_and_existing_student(self):
        defaults = pd.DataFrame([dict(student_id=s,default_seat_no=n) for s,n in [('A','1'),('B','1'),('C','2'),('D','3')]])
        rows = [dict(student_id=s,コマ='1',状態='') for s in 'ABCD']
        saved = pd.DataFrame([dict(date='2026-11-14',slot='1',seat_no='2',student_id='__RESERVED__')])
        args = (defaults,saved,rows,set(),{},'2026-11-14')
        before = [x.copy(deep=True) for x in [defaults,saved]]
        plan,messages=self.call('build_default_seat_auto_plan',*args)
        self.assertEqual([r['student_id'] for r in plan],['D'])
        self.assertEqual(len(messages),2)
        self.assertIn('重複',messages[0]);self.assertIn('使用中',messages[1])
        pd.testing.assert_frame_equal(defaults,before[0]);pd.testing.assert_frame_equal(saved,before[1])
        plan,messages=self.call('build_default_seat_auto_plan',defaults,saved,rows,{('B','1'),('__RESERVED__','1')},{},'2026-11-14')
        self.assertFalse(messages);self.assertEqual([r['student_id'] for r in plan],['A','C','D'])
        saved.loc[0,'student_id']='C'
        plan,messages=self.call('build_default_seat_auto_plan',defaults,saved,rows,set(),{},'2026-11-14')
        self.assertNotIn('C',[r['student_id'] for r in plan])


class HighlightSeatUiTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        self.f=ProgressUiTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.today=dt.date.today()
        self.f.write('students.csv',[dict(student_id=s,display_name=s,is_active='true') for s in 'ABCD'])
        self.f.write('monthly_schedule.csv',[dict(date=str(self.today),student_id=s,slot='1',session_type='授業') for s in 'ABCD'])

    def launch(self,mode):
        a=AppTest.from_file(str(self.f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=self.today.year,monthly_schedule_month=self.today.month).items():a.session_state[k]=v
        a.session_state[f'monthly_view_mode_{self.today.year}_{self.today.month}']=mode
        a.run();self.assertFalse(a.exception)
        return a

    def test_highlight_clear_reselect_and_month_isolation(self):
        a=self.launch('📅 編集');ym=f'{self.today.year}_{self.today.month}'
        key=f'monthly_calendar_highlight_student_select_{ym}'
        other=self.today.replace(day=1)+dt.timedelta(days=32);om=f'{other.year}_{other.month}'
        a.session_state[f'monthly_calendar_highlight_student_state_{om}']='B'
        a.selectbox(key=key).set_value('A').run()
        self.assertEqual(a.session_state[f'monthly_calendar_highlight_student_state_{ym}'],'A')
        a.button(key=f'monthly_calendar_clear_highlight_{ym}').click().run()
        self.assertFalse(a.exception)
        self.assertEqual(a.selectbox(key=key).value,'')
        self.assertEqual(a.session_state[f'monthly_calendar_highlight_student_prev_{ym}'],'')
        self.assertEqual(a.session_state[f'monthly_calendar_highlight_student_state_{om}'],'B')
        a.selectbox(key=key).set_value('B').run();self.assertFalse(a.exception)
        a.button(key=f'monthly_calendar_clear_highlight_{ym}').click().run()
        # Change the same backing month state used by the sidebar, then return.
        a.session_state['monthly_schedule_year']=other.year;a.session_state['monthly_schedule_month']=other.month
        a.session_state[f'monthly_view_mode_{om}']='📅 編集';a.run()
        self.assertFalse(a.exception)
        a.session_state['monthly_schedule_year']=self.today.year;a.session_state['monthly_schedule_month']=self.today.month;a.run()
        self.assertFalse(a.exception);self.assertEqual(a.selectbox(key=key).value,'')

    def test_saved_defaults_refresh_without_applying_or_saving_seats(self):
        self.f.write('default_seats.csv',[dict(student_id=s,default_seat_no=n,note='') for s,n in [('A','1'),('B','1'),('C','3'),('D','3')]])
        a=self.launch('🪑 今日の座席')
        path=self.f.data/'seat_assignments.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
        messages=lambda:a.session_state['seat_auto_conflict_messages']
        self.assertEqual(len(messages()),2)
        def save(s,n):
            a.selectbox(key='default_seat_student').set_value(s).run()
            a.selectbox(key='default_seat_no').set_value(n).run()
            a.button(key='save_default_seat').click().run();self.assertFalse(a.exception)
        save('B','2');self.assertEqual(len(messages()),1);self.assertIn('席3',messages()[0])
        save('D','4');self.assertFalse(messages());a.run();self.assertFalse(messages())
        self.assertEqual(a.selectbox(key=f'seat_grid_{self.today}_1_1').value,'')
        save('D','3');self.assertEqual(len(messages()),1)
        save('D','4');self.assertFalse(messages())
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        a.button(key=f'auto_assign_default_seats_{self.today}').click().run()
        self.assertFalse(a.exception)
        for s,n in [('A',1),('B',2),('C',3),('D',4)]:self.assertEqual(a.selectbox(key=f'seat_grid_{self.today}_1_{n}').value,s)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
