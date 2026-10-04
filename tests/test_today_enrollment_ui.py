"""Today display is filtered; new attendance candidates share the same enrollment scope."""
import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class TodayEnrollmentUiTests(unittest.TestCase):
    def launch_fixture(self, mode):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        today=dt.date.today();yesterday=today-dt.timedelta(days=1);tomorrow=today+dt.timedelta(days=1)
        periods=[(str(tomorrow),''),(str(today),''),('',str(today)),('',str(yesterday)),('2020-01-01',''),('','')]
        if mode=='zero':periods=[('',str(yesterday))]*6
        if mode=='invalid':periods[0]=('bad-date','')
        students=[dict(student_id=f'S{i}',display_name=f'架空{i}',is_active='true',join_date=j,leave_date=l) for i,(j,l) in enumerate(periods)]
        if mode=='mixed_flags':
            for i in [1,2,4,5]:students[i]['is_active']='false'
        f.write('students.csv',students)
        f.write('monthly_schedule.csv',[dict(date=str(today),student_id=f'S{i}',slot='1',session_type='授業',reason='通常') for i in range(6)])
        f.write('attendance_log.csv',[dict(date=str(yesterday),student_id='S3',kind='lesson',memo='過去保持')])
        f.write('default_seats.csv',[dict(student_id='S3',default_seat_no='3',note='設定保持')])
        files=['students.csv','attendance_log.csv','default_seats.csv','curriculum_progress.csv','kentei_progress.csv']
        snapshot={name:((f.data/name).read_bytes(),(f.data/name).stat().st_mtime_ns) for name in files}
        at=AppTest.from_file(str(f.app),default_timeout=40)
        at.session_state['auth_ok']=True
        at.run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        visible=[m.value for m in at.markdown if '限 /' in str(m.value) and '席：' in str(m.value)]
        self.assertEqual({name:((f.data/name).read_bytes(),(f.data/name).stat().st_mtime_ns) for name in files},snapshot)
        keys={w.key for w in at.selectbox}
        expected = {1,2,4} if mode=='mixed_flags' else ({1,2,4,5} if mode=='normal' else set())
        for i in range(6):
            self.assertEqual(f'att_kind_{today}_S{i}' in keys, i in expected)
        # Shared attendance hints are calculated even for hidden display rows.
        self.assertEqual(set(at.session_state['today_task_hint_map']),{f'S{i}' for i in range(6)})
        return at,visible

    def test_today_boundaries_leave_blank_legacy_attendance_and_history(self):
        at,visible=self.launch_fixture('normal')
        self.assertEqual(len(visible),4)
        for i in [1,2,4,5]:self.assertTrue(any(f'架空{i}' in s for s in visible))
        for i in [0,3]:self.assertFalse(any(f'架空{i}' in s for s in visible))

    def test_zero_display_and_attendance_candidates(self):
        at,visible=self.launch_fixture('zero')
        self.assertEqual(visible,[])
        self.assertTrue(any('今日の予定：0人' in str(c.value) for c in at.caption))

    def test_invalid_date_errors_block_new_attendance(self):
        at,visible=self.launch_fixture('invalid')
        self.assertEqual(visible,[])
        self.assertTrue(any('今日の表示を作成できません' in str(e.value) for e in at.error))

    def test_period_overrides_flag_consistently_across_today_views(self):
        at,visible=self.launch_fixture('mixed_flags')
        self.assertEqual(len(visible),3)
        for i in [1,2,4]:self.assertTrue(any(f'架空{i}' in s for s in visible))
        for i in [0,3,5]:self.assertFalse(any(f'架空{i}' in s for s in visible))
        self.assertTrue(any('今日の未完了タスク：3件' in w.value for w in at.warning))
        summary=next(m.value for m in at.markdown if '最終確認｜今日の入力状況' in m.value)
        self.assertIn('出欠 3 / 進捗 0',summary)
