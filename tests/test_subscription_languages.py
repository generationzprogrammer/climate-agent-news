import unittest
import io
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock
from climate_agent.providers import fetch_subscribers
from climate_agent.delivery import build_weekly_message

class SubscriptionLanguagesTests(unittest.TestCase):
    def test_weekly_command_groups_recipients_and_honors_preference(self):
        from climate_agent.cli import main
        report = {"meta": {"end_date": "2026-10-27", "total": 1}, "highlights": [
            {"title_zh": "气候金融", "summary_zh": "政府支持适应项目。",
             "title_en": "Climate finance", "summary_en": "Governments support adaptation projects.",
             "canonical_url": "https://example.org/news"}]}
        environment = {"CLIMATE_WEEKLY_SUBSCRIBERS": "legacy@example.com,NEW@example.net",
                       "CLIMATE_SUBSCRIBE_ENDPOINT": "https://test.invalid/subscribe",
                       "CLIMATE_SUBSCRIBER_ADMIN_TOKEN": "TEST-NOT-A-SECRET"}
        with patch.dict("os.environ", environment, clear=True), \
             patch("climate_agent.cli.Database"), \
             patch("climate_agent.cli.bootstrap", return_value=(0, 0)), \
             patch("climate_agent.cli.load_archive", return_value={}), \
             patch("climate_agent.cli.weekly_report_payload", return_value=report), \
             patch("climate_agent.cli.fetch_subscribers", return_value=[{"email": "new@example.net", "language": "en"}]), \
             patch("climate_agent.cli.publish_email_batch", return_value={"sent": 1, "failed": 0, "failure_types": {}}) as send, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["deliver-weekly", "--channel", "email"]), 0)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(send.call_args_list[0].args[1], ["legacy@example.com"])
        self.assertEqual(send.call_args_list[1].args[1], ["new@example.net"])
        self.assertNotRegex(send.call_args_list[1].args[0], r"[\u3400-\u9fff]")
        self.assertIn("cop31/?lang=en", send.call_args_list[1].args[0])
        self.assertNotIn("@example", output.getvalue())

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
