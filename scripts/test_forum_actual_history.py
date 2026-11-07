"""Tests for verified historic on/off accounting in Forum topic 63."""
import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

spec = importlib.util.spec_from_file_location(
    "actual_history", Path(__file__).resolve().parent / "build_forum_actual_history.py"
)
hist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hist)
K = ZoneInfo("Europe/Kyiv")
UTC = dt.timezone.utc

def at(day, hour, minute=0):
    return dt.datetime.combine(day, dt.time(hour, minute), K).astimezone(UTC)

class ActualHistoryTests(unittest.TestCase):
    def test_explicit_transition_text(self):
        self.assertEqual(hist.classify_change("🔌 Світло вимкнулось!\nЧас: 12:45"), "off")
        self.assertEqual(hist.classify_change("💡 Світло увімкнулось!\nЧас: 12:48"), "on")
        self.assertIsNone(hist.classify_change("⚡ Оновлений графік відключень\nСвітло увімкнулось!"))
        self.assertIsNone(hist.classify_change("Коли світло увімкнулось?"))
        self.assertIsNone(hist.classify_change("Завтра світло вимкнулось би"))

    def test_known_intervals_and_unknown_start(self):
        day = dt.date(2026, 11, 1)
        events = [
            (at(day, 9), "on", 1),
            (at(day, 11), "off", 2),
            (at(day, 15), "on", 3),
            (at(day + dt.timedelta(days=1), 0), "off", 4),
        ]
        result = hist.daily_totals([day], events, at(day + dt.timedelta(days=1), 2))[day.isoformat()]
        self.assertEqual(result["on_hours"], 11.0)
        self.assertEqual(result["off_hours"], 4.0)
        self.assertEqual(result["unknown_hours"], 9.0)
        self.assertEqual(result["day_hours"], 24.0)

    def test_unconfirmed_gap_is_not_assumed(self):
        day = dt.date(2026, 11, 2)
        events = [
            (at(day, 0), "on", 1),
            (at(day + dt.timedelta(days=1), 0), "off", 2),
        ]
        d = hist.daily_totals([day], events, at(day + dt.timedelta(days=1), 1))[day.isoformat()]
        self.assertEqual(d["on_hours"], 12.0)
        self.assertEqual(d["off_hours"], 0.0)
        self.assertEqual(d["unknown_hours"], 12.0)

    def test_missing_events_remain_unknown(self):
        day = dt.date(2026, 11, 2)
        d = hist.daily_totals([day], [], at(day + dt.timedelta(days=1), 1))[day.isoformat()]
        self.assertEqual(d["on_hours"], 0.0)
        self.assertEqual(d["off_hours"], 0.0)
        self.assertEqual(d["unknown_hours"], 24.0)

    def test_dst_fall_day_has_25_hours(self):
        day = dt.date(2026, 10, 25)
        d = hist.daily_totals([day], [], at(day + dt.timedelta(days=1), 1))[day.isoformat()]
        self.assertEqual(d["day_hours"], 25.0)
        self.assertEqual(d["unknown_hours"], 25.0)

if __name__ == "__main__":
    unittest.main()
