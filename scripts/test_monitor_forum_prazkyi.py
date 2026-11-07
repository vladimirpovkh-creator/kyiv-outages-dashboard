import importlib.util
import pathlib
import unittest

FILE = pathlib.Path(__file__).resolve().parent / "monitor_forum_prazkyi.py"
spec = importlib.util.spec_from_file_location("forum_monitor", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ClassificationTests(unittest.TestCase):
    def test_on(self):
        self.assertEqual(module.classify("Світло є"), "on")
        self.assertEqual(module.classify("Світло дали"), "on")
        self.assertEqual(module.classify("💡 Світло увімкнулось!"), "on")
    def test_off(self):
        self.assertEqual(module.classify("Світла немає"), "off")
        self.assertEqual(module.classify("Світло вимкнули"), "off")
        self.assertEqual(module.classify("🔌 Світло вимкнулось!"), "off")
    def test_uncertain(self):
        for message in ("Коли буде світло?", "Світло є?", "За графіком світло є", "Світло є, але світла немає", "⚡ ОНОВЛЕНИЙ ГРАФІК ВІДКЛЮЧЕНЬ", ""):
            with self.subTest(message=message):
                self.assertIsNone(module.classify(message))
    def test_topic(self):
        self.assertEqual(module.TOPIC_ID, 63)

if __name__ == "__main__":
    unittest.main()
