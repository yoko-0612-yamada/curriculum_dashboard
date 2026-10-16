"""Typing writes fail closed on unreadable files; all data is temporary."""
from datetime import date
from unittest.mock import patch
import pandas as pd
from .support import RegressionCase, Stopped


class TypingReadProtectionTests(RegressionCase):
    def test_unreadable_blocks_load_done_skip_and_undo(self):
        path = self.ns['TYPING_LOG_CSV']
        held = pd.DataFrame([dict(date='2026-10-15',student_id='S',status='done',note='保持')])
        for content in [b'', b'\xff\xfe', b'date,student_id\n"broken']:
            path.write_bytes(content)
            before = (path.read_bytes(),path.stat().st_mtime_ns)
            for operation in [
                lambda: self.call('load_typing_log'),
                *[lambda status=status: self.call('save_typing_log',self.call('upsert_typing_log',held,'S',date(2026,10,15),status)) for status in ['done','skip']],
                lambda: self.call('save_typing_log',self.call('delete_typing_log',held,'S',date(2026,10,15))),
            ]:
                with self.subTest(content=content,operation=operation):
                    with self.assertRaises(Stopped):operation()
                    self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
                    self.assertEqual(list(self.data.iterdir()),[path])
                    self.assertIn('タイピング履歴ファイルを読み込めないため、保存できません',self.messages[-1])

    def test_permission_failure_does_not_write(self):
        path=self.ns['TYPING_LOG_CSV'];path.write_text('date,student_id,status,completed_at,note\n')
        before=(path.read_bytes(),path.stat().st_mtime_ns)
        with patch.object(pd,'read_csv',side_effect=PermissionError('denied')):
            with self.assertRaises(Stopped):self.call('save_typing_log',pd.DataFrame())
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)

    def test_missing_empty_existing_support_done_skip_and_undo(self):
        path=self.ns['TYPING_LOG_CSV'];cols=self.ns['TYPING_LOG_COLS']
        for mode in ['missing','empty','existing']:
            with self.subTest(mode=mode):
                path.unlink(missing_ok=True)
                if mode!='missing':
                    pd.DataFrame([dict(date='2026-10-14',student_id='OLD',status='done',note='保持')] if mode=='existing' else [],columns=cols).to_csv(path,index=False)
                df=self.call('load_typing_log')
                self.assertTrue(path.exists())
                for status in ['done','skip']:
                    df=self.call('upsert_typing_log',df,'NEW',date(2026,10,15),status)
                    self.call('save_typing_log',df)
                    df=self.call('load_typing_log')
                    self.assertEqual(self.call('get_typing_today',df,'NEW',date(2026,10,15))['status'],status)
                self.call('save_typing_log',self.call('delete_typing_log',df,'NEW',date(2026,10,15)))
                result=self.call('load_typing_log')
                self.assertEqual(len(result),int(mode=='existing'))
                if mode=='existing':self.assertEqual(result.iloc[0]['note'],'保持')
