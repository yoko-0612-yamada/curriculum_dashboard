"""Top shortcuts use the existing routes; all app writes stay in temporary data."""
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class TopNavigationTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests(); f.setUp(); self.addCleanup(f.doCleanups)
        self.f = f
        self.at = AppTest.from_file(str(f.app), default_timeout=40)
        self.at.session_state['auth_ok'] = True
        self.at.session_state['sidebar_student'] = 'テスト生徒01（架空）'
        self.at.run()
        self.check()

    def check(self):
        self.assertFalse(self.at.exception, [e.message for e in self.at.exception])
        self.assertEqual(len([b for b in self.at.button if str(b.key).startswith('app_nav_')]), 5)

    def nav(self, label):
        self.at.button(key='app_nav_'+label).click().run()
        self.check()
        self.assertEqual(self.at.button(key='app_nav_'+label).proto.type, 'primary')

    def test_viewer_routes_sidebar_and_progress_draft(self):
        self.nav('進捗')
        self.assertEqual(self.at.radio(key='page_widget').value, '閲覧')
        self.assertEqual(self.at.radio(key='daily_input_mode').value, '進捗登録')
        key = 'curr_state_DEMO001_DEMO_C01_DEMO_T01'
        self.at.selectbox(key=key).set_value('完了').run()
        self.nav('出席'); self.nav('進捗')
        self.assertEqual(self.at.selectbox(key=key).value, '完了')
        self.assertEqual(self.at.selectbox(key='sidebar_student').value, 'テスト生徒01（架空）')
        self.nav('確認')
        self.assertEqual(self.at.radio(key='view_mode_group').value, 'たまに見る：確認・一覧')
        self.assertFalse(any(r.key == 'daily_input_mode' for r in self.at.radio))
        self.at.radio(key='view_mode_group').set_value('毎日使う：進捗登録').run()
        self.check()
        self.assertEqual(self.at.button(key='app_nav_進捗').proto.type, 'primary')
        self.at.radio(key='daily_input_mode').set_value('出席登録').run()
        self.assertEqual(self.at.button(key='app_nav_出席').proto.type, 'primary')

    def test_month_seats_staged_data_and_return_selection(self):
        self.nav('カレンダー')
        self.assertEqual(self.at.radio(key='page_widget').value, '管理（入力）')
        self.assertEqual(self.at.selectbox(key='admin_section_selector').value, '🗓️ 月スケジュール')
        self.at.number_input(key='monthly_schedule_year').set_value(2026)
        self.at.number_input(key='monthly_schedule_month').set_value(12).run()
        staged = self.at.session_state['monthly_schedule_edit_df'].copy(deep=True)
        self.at.session_state['monthly_schedule_edit_dirty'] = True
        self.nav('座席')
        self.assertEqual(self.at.radio(key='monthly_view_mode_2026_12').value, '🪑 今日の座席')
        self.nav('カレンダー')
        self.assertEqual(self.at.radio(key='monthly_view_mode_2026_12').value, '📅 編集')
        pd.testing.assert_frame_equal(self.at.session_state['monthly_schedule_edit_df'], staged)
        self.assertTrue(self.at.session_state['monthly_schedule_edit_dirty'])
        self.nav('進捗')
        self.assertEqual(self.at.selectbox(key='sidebar_student').value, 'テスト生徒01（架空）')
        self.nav('カレンダー')
        self.assertEqual(self.at.number_input(key='monthly_schedule_month').value, 12)
        pd.testing.assert_frame_equal(self.at.session_state['monthly_schedule_edit_df'], staged)
        self.at.radio(key='monthly_view_mode_2026_12').set_value('🪑 今日の座席').run()
        self.assertEqual(self.at.button(key='app_nav_座席').proto.type, 'primary')

    def test_existing_pending_page_overrides_old_widget_and_admin_menu(self):
        self.at.session_state['pending_page'] = '管理（入力）'
        self.at.run(); self.check()
        self.assertEqual(self.at.radio(key='page_widget').value, '管理（入力）')
        self.at.selectbox(key='admin_section_selector').select('👥 生徒管理').run()
        self.check()
        self.assertTrue(all(b.proto.type == 'secondary' for b in self.at.button if str(b.key).startswith('app_nav_')))
        self.nav('出席')
        self.assertEqual(self.at.session_state['page_state'], '閲覧')
        self.assertEqual(self.at.radio(key='daily_input_mode').value, '出席登録')
