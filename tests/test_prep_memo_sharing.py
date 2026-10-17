"""準備メモは表示run内だけで共有。実CSVは一時領域のみ。"""
import unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest


class PrepMemoSharingTests(unittest.TestCase):
    def setUp(self):
        from .test_progress_ui import ProgressUiTests
        self.f=ProgressUiTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.write('monthly_schedule.csv',[dict(student_id='DEMO001',date=str(date.today()),slot='1',session_type='授業',reason='通常')])
        self.f.write('timeslots.csv',[dict(slot='1',start_time='15:00',end_time='16:00')])
        self.at=AppTest.from_file(str(self.f.app),default_timeout=40)
        self.at.session_state['auth_ok']=True

    def test_single_read_refresh_after_save_update_delete(self):
        self.f.write('prep_memo.csv',[dict(student_id='DEMO001',memo='元のメモ')])
        self.at.run()  # 初期化rerun後の通常runを計測
        reads=[];original=pd.read_csv
        def read(*a,**kw):
            if Path(str(a[0])).name=='prep_memo.csv':reads.append(a[0])
            return original(*a,**kw)
        with patch.object(pd,'read_csv',read):self.at.run()
        self.assertEqual(len(reads),1)
        self.assertTrue(any('元のメモ' in x.value for x in self.at.caption))
        self.assertTrue(any('元のメモ' in x.value for x in self.at.info))
        for value in ['新しいメモ','更新したメモ']:
            self.at.text_input(key='prep_text_input').set_value(value)
            self.at.button(key='prep_add_btn').click().run()
            self.assertFalse(self.at.exception)
            self.assertTrue(any(value in x.value for x in self.at.info))
            self.assertEqual(pd.read_csv(self.f.data/'prep_memo.csv').memo.tolist(),[value])
        self.at.button(key='prep_del_DEMO001').click().run()
        self.assertTrue(pd.read_csv(self.f.data/'prep_memo.csv').empty)
        self.assertFalse(any('次の準備：' in x.value for x in self.at.info))

    def test_missing_empty_and_read_failure(self):
        path=self.f.data/'prep_memo.csv'
        path.unlink()
        self.at.run()
        self.assertFalse(self.at.exception)
        self.assertTrue(pd.read_csv(path).empty)
        self.at.run()
        self.assertFalse(self.at.exception)
        path.write_bytes(b'\xff\xfe\x81')
        before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.at.run()
        self.assertTrue(self.at.exception)  # 従来の読込例外を空データへ変えない
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
