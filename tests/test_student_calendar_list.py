"""Student-centric calendar entries reuse existing dialogs and staged data."""
import datetime as dt
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class StudentCalendarListTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        self.f = ProgressUiTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.write('students.csv', [dict(student_id=s, display_name=s, is_active='true', join_date='2026-01-01', leave_date='2026-12-31' if s == 'A' else '') for s in ('A','B')])
        self.f.write('timeslots.csv',[dict(slot=str(i), start_time=t, end_time='19:00') for i,t in [(1,'17:10'),(2,'18:20')]])
        self.f.write('monthly_schedule.csv',[
            dict(date='2026-12-20', student_id='A',slot='2',session_type='自習',reason='自習'),
            dict(date='2026-12-06', student_id='A',slot='1',session_type='授業',reason='通常'),
            dict(date='2026-12-06', student_id='A',slot='2',session_type='授業',reason='通常'),
            dict(date='2026-12-10', student_id='B',slot='1',session_type='授業',reason='通常'),
            dict(date='2027-01-10', student_id='A',slot='1',session_type='授業',reason='通常'),
        ])

    def launch(self):
        self.at=AppTest.from_file(str(self.f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=2026,monthly_schedule_month=12).items():
            self.at.session_state[k]=v
        self.at.session_state['monthly_view_mode_2026_12']='📅 編集'
        self.at.run(); self.ok()
        self.select('A')

    def ok(self):
        self.assertFalse(self.at.exception,[e.message for e in self.at.exception])

    def select(self,sid):
        self.at.selectbox(key='monthly_calendar_highlight_student_select_2026_12').set_value(sid).run();self.ok()

    def rows(self):
        return [b for b in self.at.button if str(b.key).startswith('monthly_student_plan_pick_')]

    def test_filter_order_original_index_and_month_preserves_staged_data(self):
        self.launch()
        self.assertEqual(len(self.rows()),3)
        before=self.at.session_state['monthly_schedule_edit_df'].copy(deep=True)
        self.at.session_state['monthly_schedule_edit_dirty']=True
        self.rows()[0].click().run();self.ok()
        self.assertEqual(self.at.session_state['monthly_sidebar_update_target_2026_12'],1)
        self.assertTrue(any('予定を編集' in str(x.proto) for x in self.at.get('dialog')))
        self.at.run();self.rows()[1].click().run();self.ok()
        self.assertEqual(self.at.session_state['monthly_sidebar_update_target_2026_12'],2)
        self.at.run();self.select('B');self.assertEqual(len(self.rows()),1)
        pd.testing.assert_frame_equal(before,self.at.session_state['monthly_schedule_edit_df'])
        self.select('A')
        self.at.number_input(key='monthly_schedule_month').set_value(11).run();self.ok()
        self.assertEqual(self.at.selectbox(key='monthly_calendar_highlight_student_select_2026_11').value,'A')
        self.assertFalse(self.rows())
        self.at.number_input(key='monthly_schedule_month').set_value(12).run();self.ok()
        self.assertEqual(len(self.rows()),3)
        pd.testing.assert_frame_equal(before,self.at.session_state['monthly_schedule_edit_df'])
        self.assertTrue(self.at.session_state['monthly_schedule_edit_dirty'])
        # Calendar entry still routes to the same original row.
        next(b for b in self.at.button if str(b.key).startswith('monthly_calendar_pick_')).click().run();self.ok()
        self.assertIn(self.at.session_state['monthly_calendar_selected_source_2026_12'],['monthly','override'])

    def test_cancel_history_and_external_override_reuse_restrictions(self):
        self.f.write('schedule_overrides.csv',[
            dict(date='2026-12-06',student_id='A',slot='1',action='キャンセル',note='月カレンダー手動振替 元予定'),
            dict(date='2026-12-13',student_id='A',slot='1',action='追加',session_type='授業',note='座席予約連携 受付経路:LINE'),
        ])
        self.launch();self.assertEqual(len(self.rows()),4)
        self.assertTrue(any('キャンセル' in m.value for m in self.at.markdown))
        # 6th slot1 (cancel), 6th slot2, 13th override, 20th slot2.
        self.rows()[2].click().run();self.ok()
        self.assertEqual(self.at.session_state['monthly_calendar_selected_source_2026_12'],'override')
        self.assertTrue(any('外部受付から反映' in m.value for m in self.at.info))
        self.assertEqual(self.at.session_state['monthly_calendar_highlight_student_state_2026_12'],'A')

    def test_add_selected_student_and_out_of_period_never_falls_back(self):
        # Test-only persistent dialog for AppTest full-script reruns.
        source=self.f.app.read_text().replace(
            '                        if st.button("＋ 新規追加", key=f"monthly_student_plan_add_{target_year}_{target_month}"):',
            '                        if st.button("＋ 新規追加", key=f"monthly_student_plan_add_{target_year}_{target_month}") or st.session_state.get("test_keep_add", False):')
        self.f.app.write_text(source)
        self.launch()
        path=self.f.data/'monthly_schedule.csv';original=(path.read_bytes(),path.stat().st_mtime_ns)
        self.at.button(key='monthly_student_plan_add_2026_12').click().run();self.ok()
        self.assertEqual(self.at.selectbox(key='monthly_add_student_2026_12').value,'A')
        self.at.session_state['test_keep_add']=True
        next(b for b in self.at.button if '新規予定を一覧へ追加' in b.label).click().run();self.ok()
        self.assertEqual(len(self.at.session_state['monthly_schedule_edit_df']),6)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),original)
        self.assertEqual(self.at.session_state['monthly_calendar_highlight_student_state_2026_12'],'A')
        self.at.number_input(key='monthly_schedule_year').set_value(2027).run();self.ok()
        self.assertTrue(any('選択生徒は追加日当日の在籍対象ではありません' in m.value for m in self.at.info))
        self.assertFalse(any(b for b in self.at.button if '新規予定を一覧へ追加' in b.label))
        self.assertNotIn('monthly_add_student_2027_12',self.at.session_state)

    def test_edit_and_cancel_use_existing_save_boundaries(self):
        source=self.f.app.read_text().replace(
            '                                _open_monthly_edit_dialog()\n                        if st.button("＋ 新規追加",',
            '                                _open_monthly_edit_dialog()\n                        if st.session_state.get("test_keep_edit", False):\n                            _open_monthly_edit_dialog()\n                        if st.button("＋ 新規追加",',1)
        self.f.app.write_text(source)
        self.launch()
        path=self.f.data/'monthly_schedule.csv';original=path.read_bytes()
        self.rows()[0].click().run();self.ok()
        self.at.session_state['test_keep_edit']=True
        next(w for w in self.at.radio if w.label=='変更後の種別').set_value('自習').run();self.ok()
        next(b for b in self.at.button if '変更を反映（通常は未保存' in b.label).click().run();self.ok()
        self.assertEqual(self.at.session_state['monthly_schedule_edit_df'].loc[1,'session_type'],'自習')
        self.assertEqual(path.read_bytes(),original)
        next(b for b in self.at.button if b.label=='↩ 予定をキャンセル').click().run();self.ok()
        overrides=pd.read_csv(self.f.data/'schedule_overrides.csv')
        self.assertTrue(overrides.action.eq('キャンセル').any())
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(self.at.session_state['monthly_calendar_highlight_student_state_2026_12'],'A')
