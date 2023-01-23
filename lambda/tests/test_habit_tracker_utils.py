import unittest
import datetime
from context import habit_tracker_utils


class TestHabitTrackerUtils(unittest.TestCase):

    # Had issues with test package resolving content of /lambda/documents...
    # def test_get_present_tense(self):
    # def test_get_phrase(self):

    def test_get_active_streak(self):

        # Mock current date, for less variability in test performance
        current_date = datetime.date(2020, 1, 1)
        current_date_iso = current_date.isoformat()

        # Get streaks for test (7, 66 days, all with either current date or not)
        streak_7_days_current_day_iso = reversed([
            (current_date - datetime.timedelta(days=i)).isoformat() for i in range(7)])
        streak_7_days_not_current_day_iso = reversed([
            (current_date - datetime.timedelta(days=i)).isoformat() for i in range(1, 8)])
        streak_66_days_current_day_iso = reversed([
            (current_date - datetime.timedelta(days=i)).isoformat() for i in range(0, 66)])

        self.assertEqual(
            0, habit_tracker_utils.get_active_streak([], current_date_iso))
        self.assertEqual(1, habit_tracker_utils.get_active_streak(
            [current_date_iso], current_date_iso))
        self.assertEqual(1, habit_tracker_utils.get_active_streak(
            [(current_date - datetime.timedelta(days=1)).isoformat()], current_date_iso))

        self.assertEqual(7, habit_tracker_utils.get_active_streak(
            streak_7_days_current_day_iso, current_date_iso))
        self.assertEqual(7, habit_tracker_utils.get_active_streak(
            streak_7_days_not_current_day_iso, current_date_iso))

        self.assertEqual(66, habit_tracker_utils.get_active_streak(
            streak_66_days_current_day_iso, current_date_iso))


if __name__ == '__main__':
    unittest.main()
