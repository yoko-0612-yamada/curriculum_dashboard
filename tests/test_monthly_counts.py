"""Monthly counts share date eligibility, preserve history, and never prorate."""
import datetime as dt
import json
import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
from .support import RegressionCase


class MonthlyCountTests(RegressionCase):
    def context(self, students, plans=None, attendance=None, confirmation=None, month=10, overrides=None):
        plans = pd.DataFrame(plans or [])
        return self.call('monthly_count_data', 2026, month, pd.DataFrame(students), plans,
                         plans, pd.DataFrame(overrides or []), pd.DataFrame(attendance or []), confirmation or {})

    def test_boundaries_flags_contracts_and_history_ids(self):
        students = [
            dict(student_id='JOIN', is_active='true', join_date='2026-10-15', number_of_times='4'),
            dict(student_id='LEAVE', is_active='true', leave_date='2026-10-20', number_of_times='4'),
            dict(student_id='OFF', is_active='false', join_date='2026-01-01', leave_date='2026-10-31', number_of_times='4'),
            dict(student_id='ENDED', is_active='true', leave_date='2026-09-30', number_of_times='4'),
            dict(student_id='OLD', is_active='false', number_of_times='4'),
        ]
        plans = [dict(student_id=sid, date=f'2026-10-{day}', slot='1', session_type='授業')
                 for sid in ['JOIN', 'LEAVE', 'OFF', 'ENDED', 'OLD'] for day in ['10','15','20','21']]
        c = self.context(students, plans, [dict(student_id='MISSING', date='2026-10-01', kind='lesson')]*2)
        self.assertEqual(c['planned'], {'JOIN':3, 'LEAVE':3, 'OFF':4})
        self.assertEqual(c['actual']['MISSING'], 2)
        self.assertEqual(c['names']['MISSING'], 'MISSING | （マスタ未登録）')
        self.assertEqual(c['ids'], {'JOIN','LEAVE','OFF','ENDED','OLD','MISSING'})
        self.assertEqual(c['targets']['OFF'], '4')
        self.assertEqual(c['targets']['JOIN'], '4')  # no proration
        historical = self.context(students, [dict(student_id='OLD', date='2026-09-01', session_type='授業')],
            [dict(student_id='OLD', date='2026-09-01', kind='lesson')], month=9)
        self.assertIn('OLD', historical['ids'])
        self.assertEqual(historical['actual']['OLD'], 1)

    def test_exclusions_cancellation_multiple_slots_and_no_mutation(self):
        students = [dict(student_id='S', is_active='true', number_of_times='4')]
        rows = [dict(student_id='S', date='2026-10-01', slot=str(i), session_type='授業', reason=reason)
                for i,reason in enumerate(['通常','今月振替','追加授業','確認必要','前月振替','自習','補習・確認','特典追加','その他回数外','回数外','月回数外'])]
        rows += [dict(student_id='S', date='2026-10-02', session_type='授業', note='月回数外'),
                 dict(student_id='S', date='2026-10-03', session_type='自習'),
                 dict(student_id='S', date='2026-10-03', session_type='検定'),
                 dict(student_id='S', date='2026-10-04', session_type='授業', override_status='キャンセル')]
        original = json.dumps(rows)
        c = self.context(students, rows)
        self.assertEqual(c['planned'], {'S':4})
        self.assertEqual(json.dumps(rows), original)

    def test_zero_actual_only_confirmation_and_invalid_dates(self):
        students = [dict(student_id='S', is_active='false', leave_date='2026-09-30', number_of_times='4')]
        att = [dict(student_id='S', date='2026-10-01', kind='lesson')]*2
        c = self.context(students, attendance=att)
        self.assertEqual(c['planned'], {})
        self.assertEqual(c['actual'], {'S':2})
        self.assertEqual(c['state'], '月予定未生成')
        c = self.context(students, attendance=att, confirmation={'confirmed_months':['2026-10']})
        self.assertEqual(c['state'], '確定済み')
        dates = [str(d.date()) for d in pd.date_range('2026-10-01','2026-10-31')]
        self.assertEqual(self.context(students, confirmation={'confirmed_dates':dates})['state'], '確定済み')
        self.assertEqual(self.context(students, confirmation={'confirmed_dates':dates[:1]})['state'], '一部日付のみ確定')
        for change in [dict(join_date='invalid'),dict(join_date='2026-11-01',leave_date='2026-10-01')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.context([dict(student_id='S', **change)])


class MonthlyCountUiTests(unittest.TestCase):
    def fixture(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests(); f.setUp(); self.addCleanup(f.doCleanups)
        return f

    def launch(self, f, mode='📅 編集'):
        at=AppTest.from_file(str(f.app), default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=2026,monthly_schedule_month=10,
                        monthly_count_only_ng_2026_10=False,monthly_cross_count_only_issue_2026_10=False).items():
            at.session_state[k]=v
        at.session_state['monthly_view_mode_2026_10']=mode
        at.run(); self.assertFalse(at.exception,[e.message for e in at.exception])
        return at

    def test_main_cross_and_generation_share_counts_and_targets(self):
        f=self.fixture()
        f.write('students.csv',[dict(student_id=sid,display_name=sid,is_active=flag,join_date=start,leave_date=end,number_of_times='4')
            for sid,flag,start,end in [('JOIN','true','2026-10-15',''),('LEAVE','true','','2026-10-20'),
                                     ('OFF','false','2026-01-01','2026-10-31'),('ENDED','true','','2026-09-30'),('ZERO','true','','')]])
        f.write('monthly_schedule.csv',[dict(student_id=sid,date=f'2026-10-{day}',slot='1',session_type='授業',reason='通常')
            for sid in ['JOIN','LEAVE','OFF','ENDED'] for day in ['10','15','20','21']])
        f.write('student_schedule.csv',[dict(student_id='OFF',weekday='水',slot='1',session_type='授業',week_pattern='毎週')])
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        at=self.launch(f)
        table=next(d.value for d in at.dataframe if '予定授業回数' in d.value.columns).set_index('生徒')
        cross=next(d.value for d in at.dataframe if '今月(10月)' in d.value.columns).set_index('生徒')
        for sid,count in [('JOIN',3),('LEAVE',3),('OFF',4),('ENDED',0),('ZERO',0)]:
            self.assertEqual(table.loc[sid,'予定授業回数'],count)
            self.assertTrue(cross.loc[sid,'今月(10月)'].startswith(f'{count}/4 '))
        self.assertEqual(table.loc['JOIN','月回数'],'4')
        at=self.launch(f,'⚙ 生成')
        preview=next(d.value for d in at.dataframe if '予定回数' in d.value.columns).set_index('生徒')
        self.assertEqual(preview.loc['OFF','月回数'],'4')
        self.assertEqual(preview.loc['OFF','予定回数'],4)
        self.assertEqual(preview.loc['ZERO','予定回数'],0)
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)

    def test_actual_only_missing_master_confirmed_zero_and_adjacent_history(self):
        f=self.fixture()
        f.write('students.csv',[dict(student_id='OLD',display_name='退会済み',is_active='false',leave_date='2026-09-30',number_of_times='4')])
        f.write('attendance_log.csv',[dict(student_id='OLD',date='2026-10-01',kind='lesson')]*2+
                [dict(student_id='MISSING',date='2026-10-02',kind='lesson')])
        f.write('monthly_schedule.csv',[dict(student_id='OLD',date='2026-09-15',slot='1',session_type='授業',reason='通常')])
        confirmation=f.data/'monthly_schedule_confirmation.json'
        confirmation.write_text(json.dumps({'version':1,'confirmed_months':['2026-10'],'confirmed_dates':[]}))
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in f.data.iterdir() if p.is_file()}
        at=self.launch(f)
        table=next(d.value for d in at.dataframe if '授業実績回数' in d.value.columns).set_index('生徒')
        self.assertEqual(table.loc['退会済み','授業実績回数'],2)
        self.assertEqual(table.loc['退会済み','予定授業回数'],0)
        self.assertEqual(table.loc['MISSING | （マスタ未登録）','授業実績回数'],1)
        cross=next(d.value for d in at.dataframe if '今月(10月)' in d.value.columns).set_index('生徒')
        self.assertTrue(cross.loc['退会済み','前月(9月)'].startswith('1/4 '))
        self.assertIn('確定済み',cross.loc['退会済み','今月(10月)'])
        self.assertTrue(any('月予定の状態：確定済み' in c.value for c in at.caption))
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)
        # With no current-month population at all, adjacent history remains reachable.
        f.write('attendance_log.csv',[])
        at=self.launch(f)
        cross=next(d.value for d in at.dataframe if '今月(10月)' in d.value.columns).set_index('生徒')
        self.assertTrue(cross.loc['退会済み','前月(9月)'].startswith('1/4 '))
