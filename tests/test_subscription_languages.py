import unittest
from unittest.mock import patch, MagicMock
from climate_agent.providers import fetch_subscribers
from climate_agent.delivery import build_weekly_message

class SubscriptionLanguagesTests(unittest.TestCase):
    def test_legacy_defaults_and_new_preferences(self):
        response=MagicMock()
        response.read.return_value=b'{"subscribers":["legacy@example.com","new@example.net"],"preferences":[{"email":"new@example.net","language":"en"}]}'
        response.__enter__.return_value=response
        with patch("climate_agent.providers.urllib.request.urlopen",return_value=response):
            records=fetch_subscribers("https://test.invalid/subscribers","TEST",include_preferences=True)
        self.assertEqual(records,[{"email":"legacy@example.com","language":"zh"},{"email":"new@example.net","language":"en"}])

    def test_weekly_email_language_and_website(self):
        report={"meta":{"title":"周报","total":1,"start_date":"2026-10-20","end_date":"2026-10-27"},"observations":["中文观察"],"highlights":[{"title_zh":"中文标题","summary_zh":"中文摘要","title_en":"Climate finance agreement","summary_en":"Governments agreed to fund climate adaptation projects.","canonical_url":"https://example.org/news"}]}
        en=build_weekly_message(report,"https://generationzprogrammer.github.io/climate-agent-news/",language="en")
        self.assertNotRegex(en,r"[\u3400-\u9fff]")
        self.assertIn("Governments agreed",en)
        self.assertIn("cop31/?lang=en",en)
        self.assertIn("unsubscribe",en.lower())
        zh=build_weekly_message(report,"https://generationzprogrammer.github.io/climate-agent-news/")
        self.assertIn("中文摘要",zh)
        self.assertIn("/cop31/",zh)
