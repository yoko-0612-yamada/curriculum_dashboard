"""Current state shares event-date eligibility with Bot and seat counts."""
import pandas as pd
from .support import RegressionCase


class CurrentStateEnrollmentTests(RegressionCase):
    def setUp(self):
        super().setUp()
        self.students = pd.DataFrame([dict(student_id='S', display_name='架空', is_active='false', join_date='2026-10-02', leave_date='2026-10-03')])
        self.month = pd.DataFrame([dict(date=f'2026-10-0{i}', student_id='S', slot='1', session_type='授業') for i in range(1, 5)])
        self.log = pd.DataFrame([dict(reservation_id=f'R{i}', student_id='S', request_type='lesson_add', requested_date=f'2026-10-0{i}', requested_slot='1', requested_session_type='授業') for i in range(1, 5)])
        self.ov = pd.DataFrame()

    def export_state(self):
        frames = [self.students, self.month, self.log, self.ov]
        before = [f.copy(deep=True) for f in frames]
        result, preview = self.call('build_seat_current_state_sync_df', students_df=self.students, student_schedule_df=pd.DataFrame(), monthly_schedule_df=self.month, schedule_overrides_df=self.ov, timeslots_df=pd.DataFrame(), import_log_df=self.log)
        for actual, expected in zip(frames, before):
            pd.testing.assert_frame_equal(actual, expected)
        self.assertEqual(result.reservation_id.tolist(), self.log.reservation_id.tolist())
        self.assertTrue(result.current_updated_at.ne('').all())
        return result

    def test_boundaries_match_bot_and_counts(self):
        state = self.export_state()
        self.assertEqual(state.current_status.tolist(), ['cancelled', 'active', 'active', 'cancelled'])
        mapping = pd.DataFrame([dict(student_id='S', bot_student_id='ANON')])
        bot = self.call('build_bot_schedule_export', '2026-10-01', '2026-10-04', self.students, pd.DataFrame(), self.month, self.ov, pd.DataFrame(), mapping)
        counts = self.call('build_seat_reservation_sync_export', '2026-10-01', '2026-10-04', self.students, pd.DataFrame(), self.month, self.ov, pd.DataFrame([dict(slot='1')]))
        dates = state.loc[state.current_status.eq('active'), 'current_date'].tolist()
        self.assertEqual(dates, bot.date.tolist())
        self.assertEqual(dates, counts.loc[(counts.base_count-counts.absence_count).gt(0), 'date'].tolist())
        self.assertTrue(state.loc[state.current_status.eq('cancelled'), ['current_date','current_slot','current_session_type']].eq('').all().all())

    def test_open_end_legacy_zero_and_errors(self):
        self.students['leave_date'] = ''
        self.assertEqual(self.export_state().current_status.tolist(), ['cancelled','active','active','active'])
        self.students['join_date'] = ''
        self.assertTrue(self.export_state().current_status.eq('cancelled').all())
        self.students['is_active'] = 'true'
        self.assertTrue(self.export_state().current_status.eq('active').all())
        for join, leave in [('bad',''), ('2026-11-01','2026-10-01')]:
            self.students['join_date'] = join
            self.students['leave_date'] = leave
            with self.assertRaises(ValueError):
                self.export_state()

    def test_cancel_readd_and_cancel_receipt_preserved(self):
        self.ov = pd.DataFrame([dict(student_id='S', date='2026-10-02', slot='1', action='キャンセル', session_type='授業')])
        self.assertEqual(self.export_state().iloc[1].current_status, 'cancelled')
        raw = pd.DataFrame([dict(request_type=t, bot_student_id='ANON', requested_date='2026-10-02', requested_slot='1', source_date='2026-10-02', source_slot='1', status='confirmed', reservation_id=f'NEW{i}', line_request_id=f'L{i}') for i,t in enumerate(['lesson_cancel','lesson_add'])])
        preview = self.call('validate_seat_transfer_import_rows', raw, students_df=self.students, student_schedule_df=pd.DataFrame(), monthly_schedule_df=self.month, schedule_overrides_df=pd.DataFrame(), timeslots_df=pd.DataFrame(), bot_map_df=pd.DataFrame([dict(student_id='S',bot_student_id='ANON')]), applied_log_df=pd.DataFrame())
        self.assertEqual(preview['反映'].tolist(), ['OK','OK'])
        self.ov, _, count = self.call('apply_confirmed_seat_transfers', preview, schedule_overrides_df=pd.DataFrame(), import_source_df=raw, applied_log_df=pd.DataFrame())
        self.assertEqual(count, 2)
        self.assertEqual(self.export_state().iloc[1].current_status, 'active')
        self.log.loc[1,'request_type'] = 'lesson_cancel'
        self.assertEqual(self.export_state().iloc[1].current_status, 'cancelled')

    def test_transfer_uses_destination_and_preserves_receipt(self):
        self.log = self.log.iloc[[1]].copy()
        for dest, expected in [('2026-10-03','changed'),('2026-10-04','cancelled')]:
            self.ov = pd.DataFrame([
                dict(student_id='S',date='2026-10-02',slot='1',action='キャンセル',session_type='授業',note='R2 振替元'),
                dict(student_id='S',date=dest,slot='2',action='追加',session_type='自習',note='R2 振替先')])
            result = self.export_state().iloc[0]
            self.assertEqual(result.current_status, expected)
            if expected == 'changed':
                self.assertEqual((result.current_date,result.current_slot,result.current_session_type), (dest,'2','自習'))
            self.assertEqual(self.log.iloc[0].requested_date,'2026-10-02')


import unittest
from streamlit.testing.v1 import AppTest


class CurrentStateEnrollmentUiTests(unittest.TestCase):
    def test_invalid_raw_date_blocks_download_without_writes(self):
        from .test_progress_ui import ProgressUiTests
        f = ProgressUiTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.write('students.csv', [dict(student_id='DEMO001', display_name='架空', is_active='true', join_date='invalid')])
        f.write('seat_transfer_import_log.csv', [dict(reservation_id='R', student_id='DEMO001', request_type='lesson_add', requested_date='2026-10-02', requested_slot='1', requested_session_type='授業')])
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in f.data.glob('*.csv')}
        at = AppTest.from_file(str(f.app), default_timeout=40)
        for k,v in dict(auth_ok=True, page_state='管理（入力）', admin_section_selector='🔄 座席予約現在状態CSV').items():
            at.session_state[k] = v
        at.run()
        self.assertFalse(at.exception, [e.message for e in at.exception])
        self.assertTrue(any('現在状態CSV生成エラー' in e.value for e in at.error))
        self.assertFalse(at.get('download_button'))
        self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)
