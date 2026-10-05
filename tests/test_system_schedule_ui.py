"""System schedule edits use only temporary CSVs; retain raw type and row identity."""
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class SystemScheduleUiTests(unittest.TestCase):
    def fixture(self, rows):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests(); f.setUp(); self.addCleanup(f.doCleanups)
        pd.DataFrame(rows).to_csv(f.data/'student_schedule.csv', index=False)
        at = AppTest.from_file(str(f.app), default_timeout=40)
        for k, v in dict(auth_ok=True, page_state='管理（入力）',
                         admin_section_selector='🛠 システム設定',
                         system_section_selector='🗓️ 固定予定（全件保守・メモ編集）').items():
            at.session_state[k] = v
        at.run(); self.assertFalse(at.exception)
        return f, at

    def row(self, typ='自習', week='第1・第3', note='original'):
        return dict(student_id='DEMO001', weekday='月', slot=3,
                    session_type=typ, week_pattern=week, note=note)

    def read(self, f):
        return pd.read_csv(f.data/'student_schedule.csv', keep_default_na=False)

    def test_note_only_preserves_japanese_english_and_unknown_types(self):
        types = ['自習', '授業', 'lesson', 'self', 'kentei', ' legacy ', '']
        rows = [dict(self.row(t), slot=i+1) for i, t in enumerate(types)]
        f, at = self.fixture(rows)
        for i, typ in enumerate(types):
            at.selectbox(key='ss_edit_sel').select(i).run()
            self.assertIsNone(at.selectbox(key='ss_edit_sess').value)
            at.text_input(key='ss_edit_note').set_value('changed'+str(i))
            at.button(key='ss_edit_save').click().run()
            self.assertFalse(at.exception)
            saved = self.read(f)
            self.assertEqual(saved.session_type.tolist(), types)
            self.assertEqual(saved.loc[i, 'note'], 'changed'+str(i))
            self.assertEqual(saved.week_pattern.tolist(), ['第1・第3']*len(types))
        self.assertTrue(list(f.data.glob('student_schedule.csv.bak_*')))

    def test_week_rows_select_update_delete_and_reset(self):
        f, at = self.fixture([self.row(note='first'), self.row(week='第2・第4', note='second')])
        opts = at.selectbox(key='ss_edit_sel').options
        self.assertIn('第1・第3', opts[0]); self.assertIn('第2・第4', opts[1])
        at.selectbox(key='ss_edit_sel').select(1).run()
        self.assertEqual(at.text_input(key='ss_edit_note').value, 'second')
        at.text_input(key='ss_edit_note').set_value('updated')
        at.button(key='ss_edit_save').click().run()
        self.assertFalse(at.exception)
        saved=self.read(f)
        self.assertEqual(saved.note.tolist(), ['first','updated'])
        self.assertEqual(saved.week_pattern.tolist(), ['第1・第3','第2・第4'])
        at.selectbox(key='ss_edit_sel').select(0).run()
        self.assertEqual(at.text_input(key='ss_edit_note').value, 'first')
        at.selectbox(key='ss_edit_sess').select('授業').run()
        at.selectbox(key='ss_edit_sel').select(1).run()
        self.assertIsNone(at.selectbox(key='ss_edit_sess').value)
        at.button(key='ss_edit_del').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.read(f).note.tolist(), ['first'])
        self.assertEqual(self.read(f).week_pattern.tolist(), ['第1・第3'])

    def test_new_weekly_row_and_duplicate_and_explicit_type_change(self):
        f, at = self.fixture([self.row()])
        at.selectbox(key='ss_add_slot_sel').select('その他（自由入力）').run()
        at.text_input(key='ss_add_slot_free').set_value('3')
        at.selectbox(key='ss_add_sess').select('自習')
        at.button(key='ss_add_btn').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(self.read(f)),2)
        self.assertEqual(self.read(f).session_type.tolist(), ['自習','自習'])
        before=(f.data/'student_schedule.csv').read_bytes()
        at.button(key='ss_add_btn').click().run()
        self.assertTrue(any('週指定' in e.value for e in at.error))
        self.assertEqual((f.data/'student_schedule.csv').read_bytes(),before)
        at.selectbox(key='ss_edit_sel').select(1).run()
        at.selectbox(key='ss_edit_sess').select('授業')
        at.button(key='ss_edit_save').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.read(f).session_type.tolist(), ['自習','授業'])
