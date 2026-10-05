import datetime as dt
import pandas as pd
import unittest
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class ExamCandidateTests(RegressionCase):
    def test_filter_sort_preserve_indices_and_invalid(self):
        df=pd.DataFrame({'exam_date':['2026-10-07','2026-10-01','2026-10-05','bad','','2026-10-04']},index=[40,90,30,70,10,60])
        before=df.copy(deep=True)
        self.assertEqual(self.call('exam_schedule_edit_options',df,dt.date(2026,10,5)),([30,40,70,10],{70,10}))
        self.assertEqual(self.call('exam_schedule_edit_options',df,dt.date(2026,10,5),True),([30,40,60,90,70,10],{70,10}))
        pd.testing.assert_frame_equal(df,before)


class ExamCandidateUiTests(unittest.TestCase):
    def fixture(self,dates):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        f.write('kentei_exam_schedule.csv',[dict(student_id='DEMO001',exam_type='検定',grade=str(i+1),exam_date=str(day),note=f'row{i}',date=str(day),kentei='検定') for i,day in enumerate(dates)])
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',admin_section_selector='🎫 検定予定登録').items():at.session_state[k]=v
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        return f,at

    def test_past_edit_filter_reset_delete_and_full_save(self):
        today=dt.date.today()
        f,at=self.fixture([today-dt.timedelta(days=1),today+dt.timedelta(days=1),today])
        path=f.data/'kentei_exam_schedule.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
        picker=at.selectbox(key='kentei_exam_batch_selected')
        self.assertEqual(picker.value,2)
        self.assertEqual(len(picker.options),2)
        at.checkbox(key='kentei_exam_show_past').check().run()
        at.selectbox(key='kentei_exam_batch_selected').select(0).run()
        next(w for w in at.text_input if w.label=='級').set_value('9')
        next(b for b in at.button if b.label=='🟠 編集内容を一覧へ反映').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        edited=at.session_state['kentei_exam_batch_edit_df']
        self.assertEqual(edited.grade.tolist(),['9','2','3'])
        at.checkbox(key='kentei_exam_delete_confirm_0').check().run()
        at.checkbox(key='kentei_exam_show_past').uncheck().run()
        self.assertEqual(at.selectbox(key='kentei_exam_batch_selected').value,2)
        self.assertFalse(at.checkbox(key='kentei_exam_delete_confirm_2').value)
        self.assertEqual(len(at.session_state['kentei_exam_batch_edit_df']),3)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        at.button(key='exam_schedule_save_fixed').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        saved=pd.read_csv(path,dtype=str)
        self.assertEqual(saved.grade.tolist(),['9','2','3'])
        at.checkbox(key='kentei_exam_show_past').check().run()
        at.selectbox(key='kentei_exam_batch_selected').select(0).run()
        self.assertFalse(at.checkbox(key='kentei_exam_delete_confirm_0').value)
        at.checkbox(key='kentei_exam_delete_confirm_0').check().run()
        at.button(key='kentei_exam_delete_0').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertEqual(at.session_state['kentei_exam_batch_edit_df'].note.tolist(),['row1','row2'])
        self.assertFalse(any(c.value for c in at.checkbox if c.key and c.key.startswith('kentei_exam_delete_confirm_')))
        at.button(key='exam_schedule_save_fixed').click().run()
        self.assertEqual(pd.read_csv(path).note.tolist(),['row1','row2'])

    def test_past_only_and_bad_date_remain_accessible(self):
        f,at=self.fixture([dt.date.today()-dt.timedelta(days=1)])
        self.assertFalse(any(w.key=='kentei_exam_batch_selected' for w in at.selectbox))
        self.assertEqual(len(at.session_state['kentei_exam_batch_edit_df']),1)
        at.checkbox(key='kentei_exam_show_past').check().run()
        self.assertEqual(at.selectbox(key='kentei_exam_batch_selected').value,0)
        # Inject an existing malformed date into only the isolated edit buffer.
        edited=at.session_state['kentei_exam_batch_edit_df'].copy()
        edited.loc[0,'exam_date']='bad'
        at.session_state['kentei_exam_batch_edit_df']=edited
        at.checkbox(key='kentei_exam_show_past').uncheck().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertIn('要確認',at.selectbox(key='kentei_exam_batch_selected').options[0])
