"""Offline tests for live Telegram listener and staleness policy."""
import datetime as dt
import importlib.util
import os
import pathlib
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("live_monitor", ROOT / "realtime" / "monitor.py")
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)
UTC = dt.timezone.utc

class LiveMonitorTests(unittest.TestCase):
    def test_topic_filter(self):
        nested = types.SimpleNamespace(id=100, reply_to=types.SimpleNamespace(reply_to_top_id=63, reply_to_msg_id=12))
        root = types.SimpleNamespace(id=101, reply_to=types.SimpleNamespace(reply_to_top_id=None, reply_to_msg_id=63))
        other = types.SimpleNamespace(id=102, reply_to=types.SimpleNamespace(reply_to_top_id=42, reply_to_msg_id=12))
        self.assertTrue(monitor.topic_header_matches(nested))
        self.assertTrue(monitor.topic_header_matches(root))
        self.assertFalse(monitor.topic_header_matches(other))

    def test_newest_off_event_wins(self):
        now = dt.datetime(2026,11,8,7,51,tzinfo=UTC)
        messages = [
            types.SimpleNamespace(id=4824,date=now-dt.timedelta(hours=5),raw_text="Світло увімкнулось!"),
            types.SimpleNamespace(id=4883,date=now-dt.timedelta(minutes=7),raw_text="🔌 Світло вимкнулось!"),
            types.SimpleNamespace(id=4884,date=now-dt.timedelta(minutes=2),raw_text="Оновлений графік відключень"),
        ]
        winner = monitor.choose_latest(messages, now)
        self.assertEqual(winner[1:], (4883, "off"))

    def test_staleness_and_freshness(self):
        now=dt.datetime(2026,11,8,7,51,tzinfo=UTC)
        with tempfile.TemporaryDirectory() as folder:
            previous = monitor.STATE_PATH
            try:
                monitor.STATE_PATH=pathlib.Path(folder)/"status.json"
                store=monitor.Store()
                store.apply((now-dt.timedelta(minutes=7),4883,"off"), now)
                self.assertEqual(store.payload(now)["state"],"off")
                self.assertEqual(store.payload(now+dt.timedelta(seconds=121))["state"],"unknown")
                store.last_sync=now+dt.timedelta(hours=24)
                self.assertEqual(store.payload(now+dt.timedelta(hours=24))["state"],"unknown")
            finally:
                monitor.STATE_PATH=previous

if __name__ == "__main__":
    unittest.main()
