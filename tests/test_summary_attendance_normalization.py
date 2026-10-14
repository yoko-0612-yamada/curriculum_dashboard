"""Summary-local normalization, preserving the existing last-row semantics."""
import ast
from datetime import date
from unittest.mock import Mock, patch
import pandas as pd
from .support import APP, RegressionCase


class SummaryAttendanceNormalizationTests(RegressionCase):
    def setUp(self):
        super().setUp()
        tree = ast.parse(APP.read_text())
        names = {'_prepare_summary_attendance_kind', '_summary_attendance_kind'}
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=funcs, type_ignores=[]), str(APP), 'exec'), self.ns)
        def assigns(node, name):
            return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id==name for t in node.targets)
        body = next(n.body for n in ast.walk(tree) if isinstance(n, ast.If)
                    and any(assigns(x, '_summary_rows') for x in n.body))
        start = next(i for i,n in enumerate(body) if assigns(n, '_summary_rows'))
        end = next(i for i,n in enumerate(body) if assigns(n, '_summary_status_df'))
        self.block = compile(ast.Module(body=body[start:end], type_ignores=[]), str(APP), 'exec')
        self.ns.update(_summary_today=date(2026,10,14), _summary_curr_done=pd.DataFrame(),
                       _summary_kentei_done=pd.DataFrame(), _summary_skip_df=pd.DataFrame())
        for name in ['is_attendance_done_today','is_progress_done_today','is_progress_skip_ok_today']:
            self.ns[name] = lambda *args: False

    def run_summary(self, frame, ids):
        self.ns['_summary_att_df'] = frame
        self.ns['_summary_plan'] = pd.DataFrame({'student_id':ids})
        prepare = self.ns['_prepare_summary_attendance_kind']
        wrapped = Mock(wraps=prepare)
        self.ns['_prepare_summary_attendance_kind'] = wrapped
        original_copy = pd.DataFrame.copy
        copies = []
        def counted(df, *args, **kwargs):
            if df is frame:
                copies.append(1)
            return original_copy(df,*args,**kwargs)
        try:
            with patch.object(pd.DataFrame,'copy',counted):
                exec(self.block,self.ns)
        finally:
            self.ns['_prepare_summary_attendance_kind'] = prepare
        return wrapped.call_count,len(copies)

    def test_once_for_multiple_rows_and_same_last_record(self):
        frame=pd.DataFrame([
            ['2026-10-14',' S ',' LESSON ',1],
            ['2026-10-14','S',' ABSENCE ',1],
            ['2026-10-13','S','lesson',1],
            ['2026-10-14','T','selfstudy',2],
            ['2026-10-14','T','lesson',1],
        ],columns=['date','student_id','kind','slot'],index=[9,2,7,5,1])
        before=frame.copy(deep=True)
        self.assertEqual(self.run_summary(frame,['S','T','U','S']),(1,1))
        for sid,expected in [('S','absence'),('T','lesson'),('U','')]:
            self.assertEqual(self.call('_summary_attendance_kind',sid),expected)
            self.assertEqual(self.call('_summary_attendance_kind',sid),self.legacy_kind(frame,sid))
        pd.testing.assert_frame_equal(frame,before)
        self.assertEqual(self.run_summary(frame,['T']),(1,1))
        self.assertEqual(self.run_summary(frame,[]),(0,0))
        self.assertEqual(self.run_summary(frame,[' ']),(0,0))

    def test_empty_missing_kind_and_next_summary_refresh(self):
        empty=pd.DataFrame(columns=['date','student_id','kind'])
        self.assertEqual(self.run_summary(empty,['S','T']),(1,0))
        self.assertEqual(self.call('_summary_attendance_kind','S'),'')
        frame=pd.DataFrame([{'date':'2026-10-14','student_id':'S'}])
        self.run_summary(frame,['S'])
        self.assertEqual(self.call('_summary_attendance_kind','S'),self.legacy_kind(frame,'S'))
        frame['kind']='lesson'
        self.run_summary(frame,['S'])
        self.assertEqual(self.call('_summary_attendance_kind','S'),'lesson')
        frame.loc[0,'kind']='selfstudy'
        self.run_summary(frame,['S'])
        self.assertEqual(self.call('_summary_attendance_kind','S'),'selfstudy')

    def test_loader_failure_empty_and_missing_keep_behavior(self):
        path=self.ns['ATTENDANCE_LOG_CSV']
        for data in [b'',b'\xff\xfa',b'date,student_id,kind\n"broken']:
            path.write_bytes(data)
            before=(path.read_bytes(),path.stat().st_mtime_ns)
            with self.assertRaises((pd.errors.EmptyDataError,pd.errors.ParserError,UnicodeError)):
                self.call('load_attendance_log')
            self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        path.write_text('date,student_id,kind,memo\n')
        self.run_summary(self.call('load_attendance_log'),['S'])
        self.assertEqual(self.call('_summary_attendance_kind','S'),'')
        path.unlink()
        self.run_summary(self.call('load_attendance_log'),['S'])
        self.assertTrue(path.exists())
        self.assertEqual(self.call('_summary_attendance_kind','S'),'')

    def legacy_kind(self, frame, student_id):
        if frame is None or frame.empty:
            return ''
        sid=str(student_id).strip()
        ds=str(self.ns['_summary_today'])
        tmp=frame.copy()
        tmp['student_id']=tmp['student_id'].astype(str).fillna('').str.strip()
        tmp['date']=tmp['date'].astype(str).fillna('').str.strip()
        if 'kind' not in tmp.columns:
            return ''
        tmp['kind']=tmp['kind'].astype(str).fillna('').str.strip().str.lower()
        hit=tmp[(tmp.student_id==sid)&(tmp.date==ds)]
        return '' if hit.empty else str(hit.iloc[-1]['kind']).strip().lower()
