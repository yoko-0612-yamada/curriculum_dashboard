"""表示用検定2CSVのrun内共有。保存時のローダーは既存テストで保護。"""
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, Mock
import pandas as pd
from streamlit.testing.v1 import AppTest


class KenteiViewSharingTests(unittest.TestCase):
    def test_shared_hint_matches_existing_results_and_training(self):
        from .test_today_hint_reads import TodayHintReadsTests
        f=TodayHintReadsTests();f.setUp();self.addCleanup(f.doCleanups)
        for rows in [[],[dict(student_id='S',grade='4',result='不合格')],[dict(student_id='S',grade='4',result='合格')]]:
            results=pd.DataFrame(rows,columns=['student_id','grade','result'])
            for active in ['true','false']:
                training=pd.DataFrame([dict(student_id='S',is_training=active,grade='3')])
                f.ns['load_kentei_results']=Mock(return_value=results)
                f.ns['load_kentei_training_status']=Mock(return_value=training)
                expected=f.call('_today_task_hint','S')
                f.ns['load_kentei_results'].reset_mock();f.ns['load_kentei_training_status'].reset_mock()
                before=results.copy(deep=True)
                self.assertEqual(f.call('_today_task_hint','S',results_df=results,training_df=training),expected)
                f.ns['load_kentei_results'].assert_not_called();f.ns['load_kentei_training_status'].assert_not_called()
                pd.testing.assert_frame_equal(results,before)

    def test_each_run_reads_once_and_refreshes(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        ids=['A','B','C'];day=str(date.today())
        f.write('students.csv',[dict(student_id=s,display_name=s,is_active='true',join_date='2026-01-01') for s in ids])
        f.write('monthly_schedule.csv',[dict(student_id=s,date=day,slot='1',session_type='授業',reason='通常') for s in ids])
        f.write('timeslots.csv',[dict(slot='1',start_time='15:00',end_time='16:00')])
        at=AppTest.from_file(str(f.app),default_timeout=40);at.session_state['auth_ok']=True;at.run()
        names=['kentei_results.csv','kentei_training_status.csv'];original=pd.read_csv
        for grade in ['3','2']:
            f.write(names[1],[dict(student_id='A',is_training='true',grade=grade)])
            counts=dict.fromkeys(names,0)
            def read(*args,**kwargs):
                name=Path(str(args[0])).name
                if name in counts:counts[name]+=1
                return original(*args,**kwargs)
            with patch.object(pd,'read_csv',read):at.run()
            self.assertFalse(at.exception)
            self.assertEqual(counts,dict.fromkeys(names,1))
            self.assertIn(f'検定：{grade}級',at.session_state['today_task_hint_map']['A'])
