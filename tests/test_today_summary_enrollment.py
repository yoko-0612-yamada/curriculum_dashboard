"""Today's summary and unfinished rows share normal attendance enrollment scope."""
import unittest


class TodaySummaryEnrollmentTests(unittest.TestCase):
    def launch(self,mode):
        from .test_today_enrollment_ui import TodayEnrollmentUiTests
        fixture=TodayEnrollmentUiTests()
        self.addCleanup(fixture.doCleanups)
        return fixture.launch_fixture(mode)

    def test_boundaries_match_display_and_attendance(self):
        at,visible=self.launch('normal')
        self.assertEqual(len(visible),4)
        self.assertTrue(any('今日の未完了タスク：4件' in w.value for w in at.warning))
        summary=next(m.value for m in at.markdown if '最終確認｜今日の入力状況' in m.value)
        self.assertIn('出欠 4 / 進捗 0',summary)
        # There is no separate today's unfinished registration route.
        self.assertFalse(any(str(b.key).startswith('today_lesson_') for b in at.button))

    def test_zero_remains_zero(self):
        at,visible=self.launch('zero')
        self.assertEqual(visible,[])
        self.assertFalse(any('今日の未完了タスク：' in w.value for w in at.warning))
        self.assertTrue(any('今日の未完了タスクはありません' in x.value for x in at.success))
        summary=next(m.value for m in at.markdown if '最終確認｜今日の入力状況' in m.value)
        self.assertNotIn('出欠 6',summary)

    def test_invalid_is_error_not_success(self):
        at,_=self.launch('invalid')
        self.assertTrue(any('今日の未完了・入力状況を作成できません' in x.value for x in at.error))
        self.assertFalse(any('今日の未完了タスクはありません' in x.value for x in at.success))
        summary=next(m.value for m in at.markdown if '最終確認｜今日の入力状況' in m.value)
        self.assertIn('集計できません',summary)
