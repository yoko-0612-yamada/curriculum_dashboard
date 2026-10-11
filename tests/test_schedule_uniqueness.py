"""One active student/date/slot; history and other consumers are unchanged."""
import ast
import datetime as dt
import pandas as pd
import unittest
from streamlit.testing.v1 import AppTest
from .support import RegressionCase, Stopped, APP

D='2026-10-10'
class ScheduleUniquenessTests(RegressionCase):
    def setUp(self):
        super().setUp()
        self.students=pd.DataFrame([dict(student_id=s,display_name=s,is_active='true') for s in ['S','T']])
        self.empty=pd.DataFrame()
        self.month=pd.DataFrame([dict(student_id='S',date=D,slot='1',session_type='自習')])
    def guard(self,month=None,ov=None,sid='S',slot=1,edit=False,day=D):
        return self.call('require_unique_schedule_slot',day,sid,slot,self.students,self.empty,
                         self.month if month is None else month,self.empty if ov is None else ov,self.empty,editing_same_slot=edit)
    def test_cross_type_additions_blocked(self):
        for typ in ['自習','授業','検定']:
            with self.subTest(typ=typ),self.assertRaises(Stopped):self.guard(self.month.assign(session_type=typ))
        self.assertTrue(all('既存予定を編集' in m for m in self.messages))
    def test_self_edit_and_other_slots_students_days(self):
        self.guard(edit=True)
        self.guard(slot='2'); self.guard(sid='T'); self.guard(day='2026-10-11')
        changed=self.month.assign(session_type='授業')
        self.guard(changed,edit=True)
    def test_cancelled_history_does_not_conflict(self):
        ov=pd.DataFrame([dict(student_id='S',date=D,slot=1,action='キャンセル',session_type='自習',note='座席予約連携 R / 元予定取消')])
        before=ov.copy(deep=True)
        self.guard(ov=ov)
        pd.testing.assert_frame_equal(ov,before)
    def test_existing_duplicates_detected_not_repaired(self):
        month=pd.concat([self.month,self.month.assign(session_type='授業')],ignore_index=True)
        before=month.copy(deep=True)
        dup=self.call('schedule_duplicate_rows',D,self.students,self.empty,month,self.empty,self.empty)
        self.assertEqual(len(dup),2)
        with self.assertRaises(Stopped):self.guard(month,edit=True)
        pd.testing.assert_frame_equal(month,before)
        # Normal consumers keep their existing presentation/count behavior.
        normal=self.call('build_daily_plan_for_date',D,self.students,self.empty,month,self.empty,self.empty)
        self.assertEqual(len(normal),1)
    def preview(self,types,month):
        raw=pd.DataFrame([dict(reservation_id=f'R{i}',line_request_id=f'L{i}',bot_student_id='B',request_type=t,status='confirmed',requested_date=D,requested_slot='1',source_date='2026-10-09',source_slot='2') for i,t in enumerate(types)])
        preview=self.call('validate_seat_transfer_import_rows',raw,students_df=self.students,student_schedule_df=self.empty,monthly_schedule_df=month,schedule_overrides_df=self.empty,timeslots_df=self.empty,bot_map_df=pd.DataFrame([dict(student_id='S',bot_student_id='B')]),applied_log_df=self.empty)
        ov,log,count=self.call('apply_confirmed_seat_transfers',preview,schedule_overrides_df=self.empty,import_source_df=raw,applied_log_df=self.empty)
        return preview,ov,log,count
    def test_external_collision_and_transfer_source_unchanged(self):
        month=pd.concat([self.month,pd.DataFrame([dict(student_id='S',date='2026-10-09',slot='2',session_type='授業')])],ignore_index=True)
        before=month.copy(deep=True)
        for req in ['lesson_add','selfstudy_add','lesson_transfer']:
            p,ov,log,count=self.preview([req],month)
            self.assertEqual(p['反映'].tolist(),['不可']);self.assertEqual(count,0)
            self.assertTrue(ov.empty);self.assertTrue(log.empty)
        pd.testing.assert_frame_equal(month,before)
    def test_batch_different_types_same_key(self):
        for types in [['lesson_add','selfstudy_add'],['selfstudy_add','lesson_add']]:
            p,ov,log,count=self.preview(types,self.empty)
            self.assertEqual(p['反映'].tolist(),['OK','不可']);self.assertEqual(count,1)
    def test_cancel_then_readd_batch_remains_active(self):
        raw=pd.DataFrame([
            dict(reservation_id='C',bot_student_id='B',request_type='selfstudy_cancel',status='confirmed',source_date=D,source_slot='1'),
            dict(reservation_id='A',bot_student_id='B',request_type='lesson_add',status='confirmed',requested_date=D,requested_slot='1'),
        ])
        preview=self.call('validate_seat_transfer_import_rows',raw,students_df=self.students,student_schedule_df=self.empty,monthly_schedule_df=self.month,schedule_overrides_df=self.empty,timeslots_df=self.empty,bot_map_df=pd.DataFrame([dict(student_id='S',bot_student_id='B')]),applied_log_df=self.empty)
        self.assertEqual(preview['反映'].tolist(),['OK','OK'])
        ov,log,count=self.call('apply_confirmed_seat_transfers',preview,schedule_overrides_df=self.empty,import_source_df=raw,applied_log_df=self.empty)
        active=self.call('schedule_slot_conflicts',D,'S',1,self.students,self.empty,self.month,ov,self.empty)
        self.assertEqual(active.session_type.tolist(),['授業']);self.assertEqual(len(log),2)

    def test_linked_history_is_not_independent_duplicate(self):
        ov=pd.DataFrame([dict(student_id='S',date=D,slot='1',action='追加',session_type=t,note=f'座席予約連携 R{i}') for i,t in enumerate(['自習','授業'])])
        before=ov.copy(deep=True)
        dup=self.call('schedule_duplicate_rows',D,self.students,self.empty,self.empty,ov,self.empty)
        self.assertTrue(dup.empty)
        pd.testing.assert_frame_equal(ov,before)

    def test_all_ui_guards_and_generation_block_present(self):
        tree=ast.parse(APP.read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='require_unique_schedule_slot']
        self.assertEqual(len(calls),5) # add, monthly edit, override edit, inbox, date-specific exceptions

class CalendarUniquenessUiTests(unittest.TestCase):
    def fixture(self,duplicate=False,edit=False):
        from .test_progress_ui import ProgressUiTests
        f=ProgressUiTests();f.setUp();self.addCleanup(f.doCleanups)
        rows=[dict(student_id='DEMO001',date='2026-10-01',slot='1',session_type='自習',reason='自習',note='',source='月予定')]
        if duplicate:rows.append(dict(rows[0],session_type='授業'))
        f.write('monthly_schedule.csv',rows)
        source=f.app.read_text()
        if not edit:
            source=source.replace('            if open_monthly_add_from_fixed:', '            if True:\n                open_monthly_add_from_fixed = "授業"',1)
            f.app.write_text(source)
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=2026,monthly_schedule_month=10).items():at.session_state[k]=v
        at.session_state['monthly_view_mode_2026_10']='📅 編集'
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        return f,at
    def test_calendar_add_stops_and_duplicates_warn_without_writing(self):
        f,at=self.fixture(duplicate=True)
        path=f.data/'monthly_schedule.csv';before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.assertTrue(any('重複予定あり' in w.value for w in at.warning))
        next(w for w in at.date_input if w.label=='追加する日付').set_value(dt.date(2026,10,1))
        next(b for b in at.button if b.label=='🟢 新規予定を一覧へ追加（未保存）').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertTrue(any('重複' in e.value for e in at.error))
        self.assertEqual(len(at.session_state['monthly_schedule_edit_df']),2)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)

    def test_calendar_existing_type_edit_and_move_conflict(self):
        f,at=self.fixture(edit=True)
        source=f.app.read_text()
        source=source.replace('            if open_monthly_add_from_fixed:',
            '            if True:\n                _open_monthly_edit_dialog()\n            if open_monthly_add_from_fixed:',1)
        f.app.write_text(source)
        # Force the selected monthly row in the temporary AppTest copy only.
        at=AppTest.from_file(str(f.app),default_timeout=40)
        for k,v in dict(auth_ok=True,page_state='管理（入力）',monthly_schedule_year=2026,monthly_schedule_month=10).items():at.session_state[k]=v
        at.session_state['monthly_view_mode_2026_10']='📅 編集'
        at.session_state['monthly_sidebar_update_target_2026_10']=0
        at.session_state['monthly_calendar_selected_source_2026_10']='monthly'
        at.run();self.assertFalse(at.exception,[e.message for e in at.exception])
        next(w for w in at.radio if w.label=='変更後の種別').set_value('授業').run()
        next(b for b in at.button if b.label=='🟠 変更を反映（通常は未保存・振替は保存）').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertEqual(at.session_state['monthly_schedule_edit_df'].iloc[0]['session_type'],'授業')
        edited=at.session_state['monthly_schedule_edit_df'].copy()
        edited=pd.concat([edited,edited.assign(slot='2',session_type='自習')],ignore_index=True)
        at.session_state['monthly_schedule_edit_df']=edited
        at.run()
        next(w for w in at.selectbox if w.label=='コマ').select('2')
        next(b for b in at.button if b.label=='🟠 変更を反映（通常は未保存・振替は保存）').click().run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertTrue(any('重複' in e.value for e in at.error))
        self.assertEqual(at.session_state['monthly_schedule_edit_df'].slot.tolist(),['1','2'])
