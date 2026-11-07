"""Regression checks for static dashboard markup and schedule visibility."""
import pathlib
import unittest

HTML = (pathlib.Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8")

class DashboardChecks(unittest.TestCase):
    def test_unpublished_tomorrow_is_hidden(self):
        self.assertIn('if(slots(rows[tomorrow]?.["GPV"+q.value]))days.push([tomorrow,"Завтра"]);', HTML)
        self.assertNotIn('days=[[dstr(now),"Сьогодні"],[dstr(now.getTime()+86400000),"Завтра"]]', HTML)

    def test_labels(self):
        self.assertIn('<div class="label">Факт</div>', HTML)
        self.assertIn('<h2>Фактичний стан світла · Петропавлівська Борщагівка</h2>', HTML)
        self.assertNotIn('Факт · ЖК «Форум Празький»', HTML)

    def test_svitlobot_map(self):
        self.assertIn('src="https://svitlobot.in.ua/map?lat=50.434465&amp;lng=30.337877&amp;zoom=14"', HTML)
        self.assertIn('Мапа та дані — <a href="https://svitlobot.in.ua/"', HTML)
        self.assertNotIn('open_popup_channel_link=svitlobot_daniya', HTML)

    def test_map_has_no_duplicate_power_status(self):
        for fragment in (
            'id="forumActual"',
            'id="forumState"',
            'id="forumDuration"',
            'id="forumFreshness"',
            'Мапа СвітлоБота · Петропавлівська Борщагівка',
            'el("forumState")',
            'el("forumDuration")',
            'el("forumFreshness")',
        ):
            self.assertNotIn(fragment, HTML)

    def test_top_fact_still_works(self):
        self.assertIn('id="forumTopState"', HTML)
        self.assertIn('id="forumTopDuration"', HTML)
        self.assertIn('el("forumTopState").textContent=is52?state', HTML)
        self.assertIn('data/forum-prazkyi-status.json', HTML)

    def test_archive_52_historical_telegram_stats(self):
        self.assertIn('className="ranking-fact"', HTML)
        self.assertIn('if(r.group==="5.2"){const fact=', HTML)
        self.assertIn('Факт за період (Telegram): світло було', HTML)
        self.assertIn('не було ', HTML)
        self.assertIn('невідомо ', HTML)
        self.assertIn('data/forum-prazkyi-actual-history.json?t=', HTML)
        self.assertIn('setInterval(loadForumHistory,30*60*1000)', HTML)
        self.assertIn('archiveDates=dates;', HTML)
        self.assertIn('Світла не було ', HTML)
        self.assertNotIn('Факт зараз (Telegram):', HTML)
        self.assertIn('data/forum-prazkyi-status.json', HTML)

    def test_existing_components(self):
        for section in ('id="dailySchedules"', 'id="archiveTitle"', 'data/forum-prazkyi-status.json'):
            self.assertIn(section, HTML)

if __name__ == "__main__":
    unittest.main()
