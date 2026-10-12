"""Bulk item drafts must never carry over to another sub-curriculum."""
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class SubBulkTargetTests(unittest.TestCase):
    def test_switch_clears_draft_and_saves_only_to_selected_target(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.write('sub_curricula.csv', [
            dict(sub_id=sid, sub_name=name, main_course_id='', is_active='true')
            for sid, name in [('SUB001', '課題A'), ('SUB002', '課題B')]
        ])
        f.write('sub_curriculum_items.csv', [
            dict(sub_id=sid, item_id=iid, item_name=name, order='1', is_active='true')
            for sid, iid, name in [('SUB001', 'ITEM001', 'A保存済み'),
                                   ('SUB002', 'ITEM002', 'B保存済み')]
        ])
        path = f.data / 'sub_curriculum_items.csv'
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        initial = pd.read_csv(path).fillna('')
        at = AppTest.from_file(str(f.app), default_timeout=40)
        at.session_state['auth_ok'] = True
        at.session_state['page_state'] = '管理（入力）'
        at.run()
        at.selectbox(key='admin_section_selector').select('🧩 サブ課題管理').run()
        self.assertFalse(at.exception, [e.message for e in at.exception])
        selector = at.selectbox(key='sub_item_master_select')
        a, b = selector.options
        selector.select(a).run()
        at.text_area(key='sub_item_bulk_text').set_value('A未保存1\nA未保存2').run()
        self.assertEqual(at.text_area(key='sub_item_bulk_text').value, 'A未保存1\nA未保存2')
        at.selectbox(key='sub_item_master_select').select(b).run()
        self.assertEqual(at.text_area(key='sub_item_bulk_text').value, '')
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)
        at.button(key='sub_item_add_btn').click().run()
        self.assertTrue(any('追加する項目を入力' in e.value for e in at.error))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before[path])
        at.text_area(key='sub_item_bulk_text').set_value('B新規1\nB新規2').run()
        at.button(key='sub_item_add_btn').click().run()
        self.assertFalse(at.exception, [e.message for e in at.exception])
        saved = pd.read_csv(path).fillna('')
        added = saved[~saved.item_id.isin(initial.item_id)]
        self.assertEqual(added.sub_id.tolist(), ['SUB002', 'SUB002'])
        self.assertEqual(added.item_name.tolist(), ['B新規1', 'B新規2'])
        pd.testing.assert_frame_equal(saved[saved.item_id.isin(initial.item_id)].reset_index(drop=True), initial, check_dtype=False)
        at.text_area(key='sub_item_bulk_text').set_value('B未保存').run()
        at.selectbox(key='sub_item_master_select').select(a).run()
        self.assertEqual(at.text_area(key='sub_item_bulk_text').value, '')
        at.selectbox(key='sub_item_master_select').select(b).run()
        self.assertEqual(at.text_area(key='sub_item_bulk_text').value, '')
        pd.testing.assert_frame_equal(pd.read_csv(path).fillna(''), saved)
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before if p != path},
                         {p: value for p, value in before.items() if p != path})
