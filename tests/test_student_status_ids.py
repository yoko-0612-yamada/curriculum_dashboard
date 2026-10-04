import datetime as dt
import pandas as pd
import unittest
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class StudentStatusIdTests(RegressionCase):
    def test_labels_boundaries_and_conflicts(self):
        rows = pd.DataFrame([
            dict(student_id='F',join_date='2026-01-01',leave_date='2026-10-31',is_active='false'),
            dict(student_id='D',join_date='',leave_date='2026-10-04',is_active='true'),
            dict(student_id='P',join_date='',leave_date='2026-10-03',is_active='true'),
            dict(student_id='O',join_date='2026-01-01',leave_date='',is_active='true'),
            dict(student_id='L1',join_date='',leave_date='',is_active='true'),
            dict(student_id='L0',join_date='',leave_date='',is_active='false'),
            dict(student_id='N',join_date='2026-10-05',leave_date='',is_active='true')])
        before=rows.copy(deep=True)
        status=self.call('student_status_display',rows,'2026-10-04')
        self.assertEqual(status['状態'].tolist(),['退会予定：10/31まで','在籍','退会','在籍','在籍','退会','入会前'])
        self.assertTrue(status.loc[[0,2,6],'状態確認'].ne('').all())
        pd.testing.assert_frame_equal(rows,before)

    def test_bad_dates_visible_not_guessed(self):
        rows=pd.DataFrame([dict(student_id='S',join_date='bad'),dict(student_id='T',join_date='2026-11-01',leave_date='2026-10-01')])
        result=self.call('student_status_display',rows,'2026-10-04')
        self.assertEqual(result['状態'].tolist(),['要確認','要確認'])
        self.assertTrue(result['状態確認'].ne('').all())

    def test_ids_current_and_scheduled_preserved(self):
        today=dt.date.today();beforeday=today-dt.timedelta(days=1);future=today+dt.timedelta(days=2)
        students=pd.DataFrame([
            dict(student_id='IN',join_date=str(today),leave_date='',is_active='false'),
            dict(student_id='LEAVING',join_date='',leave_date=str(future),is_active='true'),
            dict(student_id='PAST',join_date=str(beforeday),leave_date=str(beforeday),is_active='true'),
            dict(student_id='FUTURE',join_date=str(future),leave_date='',is_active='false'),
            dict(student_id='OLD',join_date='',leave_date='',is_active='false')])
        path=self.ns['BOT_STUDENT_MAP_PRIVATE_CSV']
        pd.DataFrame([dict(student_id='OLD',bot_student_id='EXISTING')]).to_csv(path,index=False)
        ids=self.call('ensure_bot_student_map_private',students)
        self.assertEqual(set(ids.student_id),{'IN','LEAVING','OLD'})
        snapshot=(path.read_bytes(),path.stat().st_mtime_ns)
        again=self.call('ensure_bot_student_map_private',students)
        pd.testing.assert_frame_equal(ids,again)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),snapshot)
        expanded=self.call('ensure_bot_student_map_private',students,target_dates=[beforeday,future])
        self.assertEqual(set(expanded.student_id),set(students.student_id))
        self.assertEqual(expanded.set_index('student_id').loc['OLD','bot_student_id'],'EXISTING')
        self.assertEqual(expanded.bot_student_id.nunique(),5)
        for _,row in ids.iterrows():
            self.assertEqual(expanded.set_index('student_id').loc[row.student_id,'bot_student_id'],row.bot_student_id)

    def test_invalid_id_candidates_do_not_write(self):
        path=self.ns['BOT_STUDENT_MAP_PRIVATE_CSV']
        pd.DataFrame([dict(student_id='OLD',bot_student_id='EXISTING')]).to_csv(path,index=False)
        before=(path.read_bytes(),path.stat().st_mtime_ns)
        with self.assertRaises(ValueError):
            self.call('ensure_bot_student_map_private',pd.DataFrame([dict(student_id='X',join_date='invalid')]))
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)


class StudentStatusUiTests(unittest.TestCase):
    def test_admin_status_does_not_write_students_seats_or_ids(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        today=dt.date.today();tomorrow=today+dt.timedelta(days=1);yesterday=today-dt.timedelta(days=1)
        f.write('students.csv',[
            dict(student_id='DEMO001',display_name='予定架空',is_active='false',join_date=str(yesterday),leave_date=str(tomorrow)),
            dict(student_id='OUT',display_name='退会架空',is_active='true',join_date='',leave_date=str(yesterday))])
        f.write('default_seats.csv',[dict(student_id='OUT',default_seat_no='1',note='保持')])
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',admin_section_selector='👥 生徒管理').items():at.session_state[k]=v
        at.run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        preview=next(d.value for d in at.dataframe if '状態確認' in d.value.columns)
        self.assertEqual(preview['状態'].tolist(),[f'退会予定：{tomorrow:%m/%d}まで','退会'])
        self.assertTrue(preview['状態確認'].ne('').all())
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)

    def test_readonly_student_list_shows_current_status(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        today=dt.date.today();end=today+dt.timedelta(days=3)
        f.write('students.csv',[dict(student_id='DEMO001',display_name='一覧架空',is_active='false',join_date=str(today),leave_date=str(end))])
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='閲覧',sidebar_view_mode='生徒ごと一覧').items():at.session_state[k]=v
        at.run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        tables=[d.value for d in at.dataframe if '状態確認' in d.value.columns]
        self.assertTrue(tables)
        self.assertEqual(tables[0]['状態'].tolist(),[f'退会予定：{end:%m/%d}まで'])
