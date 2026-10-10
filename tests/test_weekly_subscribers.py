import unittest
from climate_agent.providers import resolve_subscriber_endpoint, fetch_subscribers
from unittest.mock import patch, MagicMock


class WeeklySubscribersTests(unittest.TestCase):
    def test_public_form_controls_which_service_is_read(self):
        self.assertEqual(resolve_subscriber_endpoint("https://live.example/subscribe","https://old.example/subscribers"),"https://live.example/subscribers")
        self.assertEqual(resolve_subscriber_endpoint("","https://legacy.example/subscribers"),"https://legacy.example/subscribers")

    def test_no_embedded_secret_or_query_in_endpoint(self):
        for value in ["http://example.com/subscribe","https://token@example.com/subscribe","https://example.com/subscribe?email=private@example.com","https://example.com/admin"]:
            with self.assertRaises(ValueError): resolve_subscriber_endpoint(value)

    def test_all_active_emails_are_deduplicated_not_owner_only(self):
        response=MagicMock(); response.read.return_value=b'{"subscribers":["one@example.com","new@example.net","NEW@example.net"]}'
        response.__enter__.return_value=response
        with patch("climate_agent.providers.urllib.request.urlopen",return_value=response) as fetch:
            self.assertEqual(fetch_subscribers("https://test.example/subscribers","TEST-NOT-SECRET"),["one@example.com","new@example.net"])
            request=fetch.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"),"Bearer TEST-NOT-SECRET")

    def test_invalid_schema_fails_instead_of_fixed_address_fallback(self):
        response=MagicMock(); response.read.return_value=b'{"ok":true}'
        response.__enter__.return_value=response
        with patch("climate_agent.providers.urllib.request.urlopen",return_value=response):
            with self.assertRaises(ValueError): fetch_subscribers("https://test.example/subscribers","TEST")
