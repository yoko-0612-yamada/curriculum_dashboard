"""Feature-wide pause periods; production data is never used."""
from datetime import date
import ast
from unittest.mock import Mock
import pandas as pd
from .support import APP, RegressionCase, Stopped


class FeaturePauseTests(RegressionCase):
    def periods(self, rows):
        pd.DataFrame(rows,columns=self.ns['FEATURE_PAUSE_COLS']).to_csv(self.ns['FEATURE_PAUSE_PERIODS_CSV'],index=False)

    def snapshot(self):
        return {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.data.iterdir() if p.is_file()}

    def test_boundaries_open_closed_and_same_day(self):
        for end,expected in [('',[False,True,True,True]),('2026-10-20',[False,True,True,False]),('2026-10-16',[False,False,False,False])]:
            self.periods([['subtask','2026-10-16',end]])
            self.assertEqual([self.call('is_feature_paused','subtask',f'2026-10-{d}') for d in [15,16,19,20]],expected)
            self.assertFalse(self.call('is_feature_paused','typing','2026-10-16'))

    def test_missing_empty_multiple_and_restart(self):
        path=self.ns['FEATURE_PAUSE_PERIODS_CSV']
        self.assertFalse(self.call('is_feature_paused','subtask','2026-10-16'))
        self.assertFalse(path.exists())
        self.periods([])
        self.assertFalse(self.call('is_feature_paused','subtask','2026-10-16'))
        self.periods([['typing','2026-10-01','2026-10-03'],['typing','2026-10-16','2026-10-20']])
        self.assertEqual([self.call('is_feature_paused','typing',f'2026-10-{d:02}') for d in [1,2,3,15,16,19,20]], [True,True,False,False,True,True,False])
        self.periods([])
        self.assertFalse(self.call('is_feature_paused','typing','2026-10-16'))

    def test_setting_stop_resume_preserves_other_periods(self):
        self.call('set_feature_paused','subtask',True,'2026-10-16')
        self.call('set_feature_paused','typing',True,'2026-10-16')
        self.assertFalse(self.call('set_feature_paused','subtask',True,'2026-10-17'))
        self.call('set_feature_paused','subtask',False,'2026-10-20')
        self.call('set_feature_paused','subtask',True,'2026-10-21')
        df=self.call('load_feature_pause_periods')
        self.assertEqual(df.values.tolist(),[['subtask','2026-10-16','2026-10-20'],['typing','2026-10-16',''],['subtask','2026-10-21','']])
        self.call('set_feature_paused','subtask',False,'2026-10-21')
        self.assertFalse(self.call('is_feature_paused','subtask','2026-10-21'))

    def test_invalid_setting_never_written_or_treated_as_running(self):
        path=self.ns['FEATURE_PAUSE_PERIODS_CSV']
        for data in [b'',b'\xff\xfe',b'feature,pause_start,resume_date\n"broken',b'wrong\n',
                     b'feature,pause_start,resume_date\nsubtask,invalid,\n',
                     b'feature,pause_start,resume_date\nsubtask,2026-10-20,2026-10-16\n',
                     b'feature,pause_start,resume_date\ntyping,2026-10-16,\ntyping,2026-10-17,\n']:
            path.write_bytes(data);before=self.snapshot()
            for op in [lambda:self.call('is_feature_paused','subtask','2026-10-16'),lambda:self.call('set_feature_paused','typing',True,'2026-10-16'),lambda:self.call('set_feature_paused','typing',False,'2026-10-16')]:
                with self.assertRaises(Stopped):op()
                self.assertEqual(self.snapshot(),before)

    def sub_fixture(self):
        pd.DataFrame([dict(student_id='S',sub_id='SUB',current_item_id='I',is_active='true')]).to_csv(self.ns['STUDENT_SUB_PROGRESS_CSV'],index=False)
        return pd.DataFrame([dict(student_id='S',date=f'2026-10-{d}',kind='lesson') for d in [15,16,19,20]])

    def test_sub_sync_paused_past_and_resume_keeps_saved_records(self):
        att=self.sub_fixture()
        self.call('sync_sub_daily_pending_for_date',att,'2026-10-15')
        self.periods([['subtask','2026-10-16','2026-10-20']])
        before=self.snapshot()
        for d in ['2026-10-16','2026-10-19']:
            self.assertEqual(self.call('sync_sub_daily_pending_for_date',att,d),0)
            self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.call('sync_sub_daily_pending_for_date',att,'2026-10-20'),1)
        rows=self.call('load_sub_daily_check')
        self.assertEqual(rows.date.tolist(),['2026-10-15','2026-10-20'])
        self.assertEqual(rows.status.tolist(),['pending','pending'])

    def test_sub_operations_and_invalid_sync_stop_without_writes(self):
        att=self.sub_fixture();self.periods([['subtask','2026-10-16','']]);before=self.snapshot()
        for op in [lambda:self.call('complete_and_confirm_sub_daily','S','2026-10-16'),lambda:self.call('mark_sub_daily_skip','S','2026-10-16'),lambda:self.call('upsert_sub_daily_check','S','2026-10-16','done'),lambda:self.call('complete_and_advance_student_sub_task','S',operation_date='2026-10-16')]:
            with self.assertRaises(Stopped):op()
            self.assertEqual(self.snapshot(),before)
        self.ns['FEATURE_PAUSE_PERIODS_CSV'].write_bytes(b'broken')
        before=self.snapshot()
        with self.assertRaises(Stopped):self.call('sync_sub_daily_pending_for_date',att,'2026-10-20')
        self.assertEqual(self.snapshot(),before)

    def test_record_date_filters_keep_history_and_pre_pause_pending(self):
        rows=pd.DataFrame([dict(date=f'2026-10-{d}',student_id='S',status='pending') for d in [15,16,19,20]])
        before=rows.copy(deep=True)
        self.periods([['subtask','2026-10-16','2026-10-20'],['typing','2026-10-16','2026-10-20']])
        for feature in ['subtask','typing']:
            self.assertEqual(self.call('feature_running_rows',rows,feature,'date').date.tolist(),['2026-10-15','2026-10-20'])
        pd.testing.assert_frame_equal(rows,before)

    def test_typing_save_rechecks_stale_input_and_preserves_history(self):
        df=self.call('load_typing_log')
        df=self.call('upsert_typing_log',df,'S',date(2026,10,16),'done')
        self.call('save_typing_log',df)
        held=self.call('upsert_typing_log',df,'T',date(2026,10,16),'skip')
        self.periods([['typing','2026-10-16','2026-10-20']]);before=self.snapshot()
        for op in [lambda:self.call('save_typing_log',held),lambda:self.call('upsert_typing_log',df,'T',date(2026,10,16),'done'),lambda:self.call('delete_typing_log',df,'S',date(2026,10,16))]:
            with self.assertRaises(Stopped):op()
            self.assertEqual(self.snapshot(),before)
        new=self.call('upsert_typing_log',df,'T',date(2026,10,20),'skip')
        self.call('save_typing_log',new)
        result=self.call('load_typing_log')
        self.assertEqual(result.student_id.tolist(),['S','T'])
        self.assertEqual(result.status.tolist(),['done','skip'])

    def test_typing_summary_uses_requested_date(self):
        tree=ast.parse(APP.read_text());node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_typing_pending_count_for_date')
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(APP),'exec'),self.ns)
        self.ns.update(_summary_today=date(2026,10,20),_summary_target_ids={'S'},_summary_typing_df=pd.DataFrame(),_att=pd.DataFrame([dict(date=f'2026-10-{d}',student_id='S',kind_norm='lesson') for d in [19,20]]))
        self.periods([['typing','2026-10-16','2026-10-20']])
        self.assertEqual(self.call('_typing_pending_count_for_date',date(2026,10,19)),0)
        self.assertEqual(self.call('_typing_pending_count_for_date',date(2026,10,20)),1)


import unittest
from streamlit.testing.v1 import AppTest


class FeaturePauseUiTests(unittest.TestCase):
    def fixture(self):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        return f

    def test_settings_buttons_stop_resume_only_settings_file(self):
        f=self.fixture()
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in f.data.iterdir()}
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',admin_section_selector='🛠 システム設定',system_section_selector='運用設定').items():at.session_state[k]=v
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertFalse((f.data/'feature_pause_periods.csv').exists())
        for feature in ['subtask','typing']:
            at.button(key=f'feature_pause_{feature}').click().run()
            self.assertFalse(at.exception,[e.message for e in at.exception])
            self.assertEqual(at.button(key=f'feature_pause_{feature}').label,'再開する')
        # Recreated session reads persisted state, not session_state.
        again=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',admin_section_selector='🛠 システム設定',system_section_selector='運用設定').items():again.session_state[k]=v
        again.run()
        self.assertEqual(again.button(key='feature_pause_subtask').label,'再開する')
        for feature in ['subtask','typing']:
            again.button(key=f'feature_pause_{feature}').click().run()
            self.assertFalse(again.exception,[e.message for e in again.exception])
            self.assertEqual(again.button(key=f'feature_pause_{feature}').label,'一時停止する')
        periods=pd.read_csv(f.data/'feature_pause_periods.csv',dtype=str).fillna('')
        self.assertEqual(periods.pause_start.tolist(),[str(date.today())]*2)
        self.assertEqual(periods.resume_date.tolist(),[str(date.today())]*2)
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)

    def test_paused_daily_ui_suppresses_controls_and_keeps_history(self):
        f=self.fixture();today=str(date.today())
        f.write('monthly_schedule.csv',[dict(date=today,student_id='DEMO001',slot='1',session_type='授業',reason='通常')])
        f.write('attendance_log.csv',[dict(date=today,student_id='DEMO001',kind='lesson')])
        f.write('student_sub_progress.csv',[dict(student_id='DEMO001',sub_id='SUB',current_item_id='I',is_active='true')])
        f.write('sub_curricula.csv',[dict(sub_id='SUB',sub_name='保持する教材',is_active='true')])
        f.write('sub_curriculum_items.csv',[dict(sub_id='SUB',item_id='I',item_name='保持する項目',order='1',is_active='true')])
        f.write('sub_daily_check.csv',[dict(date=today,student_id='DEMO001',sub_id='SUB',item_id='I',status='pending')])
        f.write('typing_log.csv',[dict(date=today,student_id='DEMO001',status='done',note='保持')])
        pd.DataFrame([dict(feature=k,pause_start=today,resume_date='') for k in ['subtask','typing']]).to_csv(f.data/'feature_pause_periods.csv',index=False)
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in f.data.iterdir()}
        at=AppTest.from_file(str(f.app),default_timeout=40)
        at.session_state['auth_ok']=True
        at.session_state['today_sub_hint_map']={'DEMO001':'古いサブ課題ヒント'}
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertFalse([b for b in at.button if str(b.key).startswith(('sub_progress_next_','sub_daily_done_','typing_done_','typing_skip_','typing_undo_'))])
        text='\n'.join(x.value for x in at.markdown)+ '\n'.join(x.value for x in at.caption)
        self.assertNotIn('古いサブ課題ヒント',text)
        self.assertFalse(any('サブ課題確認未' in x.value or 'タイピング未完了' in x.value for x in list(at.warning)+list(at.error)))
        self.assertTrue(any(e.label=='サブ課題の保存済み履歴' for e in at.expander))
        self.assertTrue(any(e.label=='タイピングの保存済み履歴' for e in at.expander))
        self.assertEqual({p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before},before)
