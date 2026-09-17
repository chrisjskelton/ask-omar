import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ask_omar.actions import (
    action_by_id,
    close_request,
    discover_apps,
    extract_http_urls,
    find_app,
    normalize,
    open_url_request,
    resolve_action,
    validate_http_url,
    web_search_request,
)


class ActionResolutionTests(unittest.TestCase):
    def test_normalize_human_text(self):
        self.assertEqual(normalize("  Take a Screen-shot! "), "take a screen shot")

    @patch("ask_omar.actions.shutil.which", return_value="/usr/bin/tool")
    def test_only_explicit_screenshot_request_executes_locally(self, _which):
        self.assertEqual(resolve_action("take a screenshot").id, "capture.region")
        self.assertIsNone(resolve_action("screenshot"))

    @patch("ask_omar.actions.shutil.which", return_value="/usr/bin/tool")
    def test_screenshot_question_does_not_execute(self, _which):
        self.assertIsNone(resolve_action("what is the screenshot shortcut?"))

    @patch("ask_omar.actions.shutil.which", return_value="/usr/bin/tool")
    def test_explicit_browser_language(self, _which):
        self.assertEqual(resolve_action("open the internet").id, "app.browser")
        self.assertIsNone(resolve_action("internet"))

    @patch("ask_omar.actions.shutil.which", return_value="/usr/bin/tool")
    def test_open_herdr(self, _which):
        self.assertEqual(resolve_action("open Herdr").id, "app.herdr")

    @patch("ask_omar.actions.shutil.which", return_value="/usr/bin/tool")
    def test_close_operation_never_opens_target(self, _which):
        self.assertIsNone(resolve_action("close browser"))
        self.assertIsNone(resolve_action("close Herdr"))

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

    def test_close_request_extracts_target(self):
        self.assertEqual(close_request("please close the browser"), "browser")

    @patch("ask_omar.actions.discover_apps", return_value=[
        {"id": "X.desktop", "name": "X"},
        {"id": "org.chromium.Chromium.desktop", "name": "Chromium"},
    ])
    def test_app_name_matching_uses_words_not_characters(self, _apps):
        self.assertIsNone(find_app("https://github.com/Xn4m3d/omarchy-ask"))
        self.assertEqual(find_app("X"), {"id": "X.desktop", "name": "X"})

    @patch("ask_omar.actions.shutil.which", return_value="/usr/bin/pi")
    def test_pi_actions_use_fixed_argv(self, _which):
        continued = action_by_id("terminal.pi.continue")
        fresh = action_by_id("terminal.pi.new")
        self.assertEqual(
            continued.command,
            ("omarchy-launch-terminal", "--app-id=dev.ask-omar.pi", "--title=Pi", "pi", "-c"),
        )
        self.assertEqual(fresh.command[-1], "pi")

    @patch("ask_omar.actions.shutil.which", return_value="/usr/bin/pi")
    def test_exact_pi_fast_paths_only(self, _which):
        self.assertEqual(resolve_action("open pi in a terminal").id, "terminal.pi.new")
        self.assertEqual(
            resolve_action("open pi in a terminal and continue the last session").id,
            "terminal.pi.continue",
        )
        self.assertIsNone(resolve_action("could you get me back into pi?"))

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

    def test_desktop_discovery_filters_hidden_and_unavailable_tryexec(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home-apps"
            system = root / "system-apps"
            home.mkdir()
            system.mkdir()

            def desktop(directory, name, body):
                (directory / name).write_text("[Desktop Entry]\nType=Application\n" + body, encoding="utf-8")

            desktop(home, "valid.desktop", "Name=Valid App\nExec=valid\nTryExec=python\n")
            desktop(home, "hidden.desktop", "Name=Hidden App\nExec=hidden\nHidden=true\n")
            desktop(home, "missing.desktop", "Name=Missing App\nExec=missing\nTryExec=definitely-missing\n")
            desktop(home, "duplicate.desktop", "Name=User Copy\nExec=user-copy\n")
            desktop(system, "duplicate.desktop", "Name=System Copy\nExec=system-copy\n")

            environment = {"XDG_DATA_HOME": str(root / "home"), "XDG_DATA_DIRS": str(root / "system")}
            (root / "home" / "applications").mkdir(parents=True)
            (root / "system" / "applications").mkdir(parents=True)
            for source in home.iterdir():
                (root / "home" / "applications" / source.name).write_text(source.read_text())
            for source in system.iterdir():
                (root / "system" / "applications" / source.name).write_text(source.read_text())

            real_which = __import__("shutil").which
            with patch.dict(os.environ, environment), patch(
                "ask_omar.actions.shutil.which",
                side_effect=lambda command: None if command == "definitely-missing" else real_which(command),
            ):
                apps = discover_apps()

            names = {app["name"] for app in apps}
            self.assertIn("Valid App", names)
            self.assertIn("User Copy", names)
            self.assertNotIn("System Copy", names)
            self.assertNotIn("Hidden App", names)
            self.assertNotIn("Missing App", names)

    @patch("ask_omar.actions.discover_apps", return_value=[
        {"id": "one.desktop", "name": "Same Name"},
        {"id": "two.desktop", "name": "Same Name"},
    ])
    def test_duplicate_app_name_is_ambiguous(self, _apps):
        self.assertIsNone(find_app("Same Name"))

    def test_unknown_action(self):
        self.assertIsNone(action_by_id("not.real"))


if __name__ == "__main__":
    unittest.main()
