import json
import pandas as pd
from .support import RegressionCase


class ScheduleTests(RegressionCase):
    def test_import_sequences_weekly_and_monthly(self):
        students=pd.DataFrame([dict(student_id=s,display_name=s,is_active='true') for s in ['S1','S2']]);bot=pd.DataFrame([dict(student_id=s,bot_student_id=s) for s in ['S1','S2']])
        empty=pd.DataFrame();total=0
        D='2026-09-30';E='2026-10-01'
        def req(typ='lesson_add',sid='S1',d=D,slot='1',src=D,ss='1'):
         return dict(request_type=typ,bot_student_id=sid,requested_date=d,requested_slot=slot,source_date=src,source_slot=ss,status='confirmed')
        def base(typ='授業',sid='S1',d=D,slot='1'):
         return dict(student_id=sid,date=d,slot=slot,session_type=typ)
        def run(name,rows,initial,expected_status,expected):
         nonlocal total
         for i,r in enumerate(rows):r=dict(r);r['reservation_id']=f'R{i}';r['line_request_id']=f'L{i}';rows[i]=r
         for mode in ['monthly','weekly']:
          month=pd.DataFrame(initial) if mode=='monthly' else empty
          weekly=pd.DataFrame([{**r,'weekday':['月','火','水','木','金','土','日'][pd.Timestamp(r['date']).weekday()],'week_pattern':'毎週'} for r in initial]) if mode=='weekly' else empty
          ov=empty.copy();log=empty.copy();raw=pd.DataFrame(rows);original=[x.copy(deep=True) for x in [ov,log,raw,month,weekly]]
          preview=self.ns['validate_seat_transfer_import_rows'](raw,students_df=students,student_schedule_df=weekly,monthly_schedule_df=month,schedule_overrides_df=ov,timeslots_df=empty,bot_map_df=bot,applied_log_df=log)
          assert preview['反映'].tolist()==expected_status,(name,mode,preview[['反映','理由/注意']])
          result,hist,count=self.ns['apply_confirmed_seat_transfers'](preview,schedule_overrides_df=ov,import_source_df=raw,applied_log_df=log)
          assert count==len(hist)==expected_status.count('OK')
          actual=set()
          for d in [D,E]:
           plan=self.ns['build_daily_plan_for_date'](d,students,weekly,month,result,empty,include_inactive=True)
           active=self.ns['_active_plan_rows'](plan)
           actual.update((r.student_id,d,r.slot,r.session_type) for _,r in active.iterrows())
          # weekly fixture on D doesn't introduce E (different weekday).
          assert actual==set(expected),(name,mode,actual,expected)
          for before,after in zip(original,[ov,log,raw,month,weekly]):pd.testing.assert_frame_equal(before,after)
          total+=1
        
        a=lambda sid='S1',d=D,slot='1',typ='授業':(sid,d,slot,typ)
        run('duplicate lesson',[req(),req()],[],['OK','不可'],[a()])
        run('duplicate selfstudy',[req('selfstudy_add'),req('selfstudy_add')],[],['OK','不可'],[a(typ='自習')])
        run('different slots',[req(),req(slot='2')],[],['OK','OK'],[a(),a(slot='2')])
        run('different dates',[req(),req(d=E)],[],['OK','OK'],[a(),a(d=E)])
        run('different students',[req(),req(sid='S2')],[],['OK','OK'],[a(),a(sid='S2')])
        run('two transfers',[req('lesson_transfer',d=E),req('selfstudy_transfer',d=E,slot='2',ss='2')],[base(),base('自習',slot='2')],['OK','OK'],[a(d=E),a(d=E,slot='2',typ='自習')])
        run('cancel readd',[req('lesson_cancel'),req()],[base()],['OK','OK'],[a()])
        run('selfstudy cancel readd',[req('selfstudy_cancel'),req('selfstudy_add')],[base('自習')],['OK','OK'],[a(typ='自習')])
        run('conversion chain',[req('lesson_to_selfstudy'),req('selfstudy_to_lesson')],[base(),base(slot='2')],['OK','OK'],[a(),a(slot='2')])
        run('add then convert',[req(),req('lesson_to_selfstudy')],[],['OK','OK'],[a(typ='自習')])
        run('add cancel readd duplicate',[req(),req('lesson_cancel'),req(),req()],[],['OK','OK','OK','不可'],[a()])
        run('rejected row does not reserve',[{**req(),'status':'pending'},req()],[],['不可','OK'],[a()])
        run('existing destination',[req()],[base()],['不可'],[a()])
        run('normalized date slot',[req(),req(d='2026/09/30',slot='1.0')],[],['OK','不可'],[a()])
        run('one way lesson to selfstudy',[req('lesson_to_selfstudy')],[base(),base(slot='2')],['OK','OK'][:1],[a(typ='自習'),a(slot='2')])
        run('one way selfstudy to lesson',[req('selfstudy_to_lesson')],[base('自習'),base(slot='2')],['OK'],[a(),a(slot='2')])
        run('add preserves other slot',[req('selfstudy_add',slot='2')],[base()],['OK'],[a(),a(slot='2',typ='自習')])

    def test_week_patterns_and_month_authority(self):
        students = pd.DataFrame([dict(student_id='S', display_name='S', is_active='true')])
        empty = pd.DataFrame()
        def daily(day, weekly, monthly=empty):
            return self.call('build_daily_plan_for_date', day, students, weekly, monthly, empty, empty)
        for pattern, weeks in [('毎週', [1,2,3,4,5]), ('第1・第3', [1,3]), ('第2・第4', [2,4])]:
            weekly = pd.DataFrame([dict(student_id='S', weekday='水', slot='1', session_type='授業', week_pattern=pattern)])
            for week, day in enumerate(['2026-07-01','2026-07-08','2026-07-15','2026-07-22','2026-07-29'], 1):
                with self.subTest(pattern=pattern, week=week):
                    self.assertEqual(len(daily(day, weekly)), int(week in weeks))
        weekly['week_pattern'] = '毎週'
        monthly = pd.DataFrame([dict(student_id='S', date='2026-07-01', slot='2', session_type='自習')])
        self.assertEqual(daily('2026-07-01', weekly, monthly)['slot'].tolist(), ['2'])
        self.ns['MONTHLY_SCHEDULE_CONFIRMATION_JSON'].write_text(json.dumps(dict(version=1, confirmed_months=['2026-07'], confirmed_dates=[])))
        self.assertTrue(daily('2026-07-01', weekly).empty)

    def test_cancel_export_counts_readd_and_history(self):
        empty = pd.DataFrame()
        day = '2026-09-30'
        slots = pd.DataFrame([dict(weekday='水',slot='1',start='16:00',end='17:00')])
        for size, readd, expected in [(3,False,2),(1,False,0),(1,True,1)]:
            with self.subTest(size=size, readd=readd):
                students = pd.DataFrame([dict(student_id=f'S{i}',display_name=f'S{i}',is_active='true') for i in range(size)])
                bot = students[['student_id']].assign(bot_student_id=students.student_id)
                monthly = students[['student_id']].assign(date=day,slot='1',session_type='授業')
                raw = pd.DataFrame([dict(request_type=typ,bot_student_id='S0',requested_date=day,requested_slot='1',source_date=day,source_slot='1',status='confirmed',reservation_id=f'R{i}',line_request_id=f'L{i}') for i,typ in enumerate(['lesson_cancel'] + (['lesson_add'] if readd else []))])
                preview = self.call('validate_seat_transfer_import_rows',raw,students_df=students,student_schedule_df=empty,monthly_schedule_df=monthly,schedule_overrides_df=empty,timeslots_df=slots,bot_map_df=bot,applied_log_df=empty)
                self.assertEqual(preview['反映'].tolist(), ['OK']*len(raw))
                overrides, _, _ = self.call('apply_confirmed_seat_transfers',preview,schedule_overrides_df=empty,import_source_df=raw,applied_log_df=empty)
                args = (day,day,students,empty,monthly,overrides,slots)
                exported = self.call('build_bot_schedule_export',*args,bot)
                self.assertEqual(len(exported),expected)
                seats = self.call('build_seat_reservation_sync_export',*args)
                self.assertEqual(int((seats.base_count-seats.absence_count).sum()),expected)
                plan = self.call('build_daily_plan_for_date',day,students,empty,monthly,overrides,slots)
                self.assertEqual(len(self.call('_active_plan_rows',plan)),expected)
                if not readd:
                    self.assertGreater(len(plan),expected)  # retained for calendar strike-through
