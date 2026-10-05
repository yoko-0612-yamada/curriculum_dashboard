import pandas as pd
import unittest
from streamlit.testing.v1 import AppTest


class SidebarNavigationTests(unittest.TestCase):
    def test_switch_keeps_staged_data_and_single_sidebar_control(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        at=AppTest.from_file(str(f.app),default_timeout=40)
        at.session_state['auth_ok']=True
        at.run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertEqual(at.sidebar.radio[0].key,'page_widget')
        self.assertEqual(len([w for w in at.radio if w.key=='page_widget']),1)
        self.assertTrue(any(w.label=='👤 生徒' for w in at.sidebar.selectbox))
        at.sidebar.radio(key='page_widget').set_value('管理（入力）').run()
        self.assertEqual(at.session_state['page_state'],'管理（入力）')
        at.selectbox(key='admin_section_selector').select('👥 生徒管理').run()
        self.assertTrue(any(w.key=='admin_include_inactive' for w in at.sidebar.checkbox))
        [w for w in at.text_input if w.label=='表示名'][-1].set_value('編集済み架空')
        next(b for b in at.button if b.label=='🟠 編集内容を一覧へ反映').click().run()
        staged=at.session_state['students_batch_edit_df'].copy(deep=True)
        self.assertEqual(staged.display_name.tolist(),['編集済み架空'])
        self.assertTrue(at.session_state['students_batch_edit_dirty'])
        [w for w in at.text_input if w.label=='表示名'][-1].set_value('未反映の入力')
        at.sidebar.radio(key='page_widget').set_value('閲覧').run()
        pd.testing.assert_frame_equal(at.session_state['students_batch_edit_df'],staged)
        at.sidebar.radio(key='page_widget').set_value('管理（入力）').run()
        at.selectbox(key='admin_section_selector').select('👥 生徒管理').run()
        pd.testing.assert_frame_equal(at.session_state['students_batch_edit_df'],staged)
        self.assertTrue(at.session_state['students_batch_edit_dirty'])
        self.assertEqual([w for w in at.text_input if w.label=='表示名'][-1].value,'編集済み架空')
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertEqual(len([w for w in at.radio if w.key=='page_widget']),1)
        self.assertFalse(any('display: none !important' in m.value and 'stSidebar' in m.value for m in at.markdown))
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)

    def test_pending_page_uses_existing_transition(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        at=AppTest.from_file(str(f.app),default_timeout=40)
        at.session_state['auth_ok']=True
        at.session_state['pending_page']='管理（入力）'
        at.run()
        self.assertEqual(at.sidebar.radio(key='page_widget').value,'管理（入力）')
        self.assertFalse(at.exception,[e.message for e in at.exception])
