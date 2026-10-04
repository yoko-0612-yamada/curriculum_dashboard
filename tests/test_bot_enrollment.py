"""Bot export applies event-date enrollment without mutating IDs or history."""
import pandas as pd
from .support import RegressionCase


class BotEnrollmentTests(RegressionCase):
    def setUp(self):
        super().setUp()
        self.students=pd.DataFrame([dict(student_id='S',display_name='架空',is_active='false',join_date='2026-10-02',leave_date='2026-10-03')])
        self.mapping=pd.DataFrame([dict(student_id='S',bot_student_id='ANON')])
        self.month=pd.DataFrame([dict(date=f'2026-10-0{i}',student_id='S',slot='1',session_type='授業') for i in range(1,5)])

    def export(self,overrides=None):
        ov=pd.DataFrame() if overrides is None else overrides
        sources=[self.students,self.mapping,self.month,ov]
        before=[df.copy(deep=True) for df in sources]
        result=self.call('build_bot_schedule_export','2026-10-01','2026-10-04',self.students,pd.DataFrame(),self.month,ov,pd.DataFrame(),self.mapping)
        for a,b in zip(sources,before):pd.testing.assert_frame_equal(a,b)
        return result

    def test_boundaries_zero_and_mapping_preserved(self):
        path=self.ns['BOT_STUDENT_MAP_PRIVATE_CSV'];self.mapping.to_csv(path,index=False)
        before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.assertEqual(self.export().date.tolist(),['2026-10-02','2026-10-03'])
        self.students['leave_date']='2026-09-30';self.students['join_date']='2026-09-01'
        self.assertTrue(self.export().empty)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)

    def test_open_end_legacy_and_invalid(self):
        self.students['leave_date']=''
        self.assertEqual(len(self.export()),3)
        self.students['join_date']=''
        self.assertTrue(self.export().empty)
        self.students['is_active']='true'
        self.assertEqual(len(self.export()),4)
        for join,leave in [('bad',''),('2026-11-01','2026-10-01')]:
            self.students['join_date']=join;self.students['leave_date']=leave
            with self.assertRaises(ValueError):self.export()

    def test_cancel_and_readd(self):
        ov=pd.DataFrame([dict(student_id='S',date='2026-10-02',slot='1',action='キャンセル',session_type='授業',note='取消')])
        self.assertEqual(self.export(ov).date.tolist(),['2026-10-03'])
        # 実際の受付反映経路で取消後の再追加を作る（手書きの例外行で代用しない）。
        raw=pd.DataFrame([dict(request_type=typ,bot_student_id='ANON',requested_date='2026-10-02',requested_slot='1',source_date='2026-10-02',source_slot='1',status='confirmed',reservation_id=f'R{i}',line_request_id=f'L{i}') for i,typ in enumerate(['lesson_cancel','lesson_add'])])
        preview=self.call('validate_seat_transfer_import_rows',raw,students_df=self.students.assign(is_active='true'),student_schedule_df=pd.DataFrame(),monthly_schedule_df=self.month,schedule_overrides_df=pd.DataFrame(),timeslots_df=pd.DataFrame(),bot_map_df=self.mapping,applied_log_df=pd.DataFrame())
        self.assertEqual(preview['反映'].tolist(),['OK','OK'])
        ov,history,count=self.call('apply_confirmed_seat_transfers',preview,schedule_overrides_df=pd.DataFrame(),import_source_df=raw,applied_log_df=pd.DataFrame())
        history_before=history.copy(deep=True)
        self.assertEqual(self.export(ov).date.tolist(),['2026-10-02','2026-10-03'])
        pd.testing.assert_frame_equal(history,history_before)

    def test_transfer_destination_and_source_history(self):
        self.month=self.month[self.month.date=='2026-10-02'].copy()
        for dest,expected in [('2026-10-03',['2026-10-03']),('2026-10-04',[])]:
            ov=pd.DataFrame([dict(student_id='S',date='2026-10-02',slot='1',action='キャンセル',session_type='授業',note='振替元'),dict(student_id='S',date=dest,slot='2',action='追加',session_type='授業',note='振替先')])
            self.assertEqual(self.export(ov).date.tolist(),expected)
            self.assertEqual(len(ov),2)
            self.assertEqual(self.month.date.tolist(),['2026-10-02'])


import unittest
from streamlit.testing.v1 import AppTest


class BotEnrollmentUiTests(unittest.TestCase):
    def test_invalid_date_stops_before_id_preparation_or_export_write(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        f.write('students.csv',[dict(student_id='DEMO001',display_name='架空',is_active='true',join_date='invalid')])
        paths=[f.data/'bot_student_map_private.csv',f.data/'bot_schedule.csv']
        before=[(p.read_bytes(),p.stat().st_mtime_ns) for p in paths]
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',admin_section_selector='🤖 Bot匿名CSV').items():at.session_state[k]=v
        at.run()
        at.button(key='generate_bot_anonymous_csv').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertTrue(any('Bot用CSV生成エラー' in e.value for e in at.error))
        self.assertEqual([(p.read_bytes(),p.stat().st_mtime_ns) for p in paths],before)
