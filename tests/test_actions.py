import unittest
from unittest.mock import patch

from ask_omar.actions import (
    action_by_id,
    extract_http_urls,
    open_url_request,
    validate_http_url,
    web_search_request,
)


class ActionResolutionTests(unittest.TestCase):
    def test_explicit_https_url_is_preserved(self):
        url = "https://github.com/Xn4m3d/omarchy-ask"
        self.assertEqual(open_url_request(f"open {url}"), url)
        self.assertEqual(open_url_request(f'open "{url}"'), url)
        self.assertEqual(open_url_request(f"open ({url})"), url)
        self.assertIsNone(open_url_request("open file:///tmp/example"))

    def test_compound_url_request_is_not_a_local_fast_path(self):
        url = "https://example.com"
        self.assertIsNone(open_url_request(f"open {url} and close the browser"))
        self.assertIsNone(open_url_request(f"open {url} and explain it"))
        self.assertIsNone(open_url_request(f"open {url} or https://example.org"))

    def test_explicit_google_search_extracts_terms(self):
        self.assertEqual(web_search_request("Search on Google, what's the time?"), "what's the time?")
        self.assertEqual(web_search_request("search google for Omarchy"), "Omarchy")
        self.assertEqual(web_search_request("google Ask Omar"), "Ask Omar")
        self.assertIsNone(web_search_request("What is Google?"))
        self.assertIsNone(web_search_request("search Google"))
        self.assertIsNone(web_search_request("Googled it yesterday"))
        self.assertIsNone(web_search_request("Google's DNS address?"))

    def test_web_wording_opens_a_search_but_bare_search_goes_to_omar(self):
        self.assertEqual(web_search_request("search the web for Omarchy themes"), "Omarchy themes")
        self.assertEqual(web_search_request("search online for Hyprland gaps"), "Hyprland gaps")
        self.assertEqual(web_search_request("web search Quickshell"), "Quickshell")
        self.assertIsNone(web_search_request("search my Downloads for invoices"))
        self.assertIsNone(web_search_request("search for large files in ~/Videos"))

    @patch("ask_omar.actions.shutil.which", return_value="/usr/bin/pi")
    def test_pi_actions_use_fixed_argv(self, _which):
        continued = action_by_id("terminal.pi.continue")
        fresh = action_by_id("terminal.pi.new")
        self.assertEqual(
            continued.command,
            ("omarchy-launch-terminal", "--app-id=dev.ask-omar.pi", "--title=Pi", "pi", "-c"),
        )
        self.assertEqual(fresh.command[-1], "pi")

    def test_url_validation_rejects_unsafe_or_ambiguous_values(self):
        self.assertEqual(validate_http_url("https://example.com/path"), "https://example.com/path")
        self.assertIsNone(validate_http_url("file:///tmp/example"))
        self.assertIsNone(validate_http_url("https://example.com/has space"))
        self.assertIsNone(validate_http_url("javascript:alert(1)"))

    def test_url_extraction_preserves_exact_request_boundaries(self):
        self.assertEqual(
            extract_http_urls("Please open https://example.com/path."),
            ("https://example.com/path",),
        )
        self.assertEqual(
            extract_http_urls("Open https://example.com.evil"),
            ("https://example.com.evil",),
        )
        self.assertEqual(extract_http_urls("prefixhttps://example.com"), ())
        self.assertEqual(
            extract_http_urls("Open https://evil.example/?next=https://example.com"),
            ("https://evil.example/?next=https://example.com",),
        )

    def test_unknown_action(self):
        self.assertIsNone(action_by_id("not.real"))


if __name__ == "__main__":
    unittest.main()
