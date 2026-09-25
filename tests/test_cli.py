import io
import socket
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from ask_omar.cli import main, print_setup, request


class RequestRetryTests(unittest.TestCase):
    def test_connect_failure_can_start_service_and_retry_before_send(self):
        first = Mock()
        first.__enter__ = Mock(return_value=first)
        first.__exit__ = Mock(return_value=False)
        first.connect.side_effect = ConnectionRefusedError("not running")

        second = Mock()
        second.__enter__ = Mock(return_value=second)
        second.__exit__ = Mock(return_value=False)
        second.recv.return_value = b'{"ok":true}\n'

        with (
            patch("ask_omar.cli.socket.socket", side_effect=[first, second]) as make_socket,
            patch("ask_omar.cli.subprocess.run") as start,
            patch("ask_omar.cli.time.sleep"),
        ):
            result = request({"type": "health"})

        self.assertTrue(result["ok"])
        self.assertEqual(make_socket.call_count, 2)
        start.assert_called_once()
        second.sendall.assert_called_once()

    def test_receive_timeout_after_send_does_not_replay_request(self):
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.recv.side_effect = socket.timeout("late response")

        with (
            patch("ask_omar.cli.socket.socket", return_value=client) as make_socket,
            patch("ask_omar.cli.subprocess.run") as start,
        ):
            result = request({"type": "query", "query": "do something"})

        self.assertFalse(result["ok"])
        self.assertIn("not retried", result["error"])
        self.assertEqual(make_socket.call_count, 1)
        client.sendall.assert_called_once()
        start.assert_not_called()

    def test_query_waits_without_fixed_read_deadline_for_delayed_approvals(self):
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.recv.return_value = b'{"ok":true}\n'
        with patch("ask_omar.cli.socket.socket", return_value=client):
            result = request({"type": "query", "query": "run two approved commands"})
        self.assertTrue(result["ok"])
        self.assertEqual(client.settimeout.call_args_list[0].args, (5,))
        self.assertEqual(client.settimeout.call_args_list[1].args, (None,))


class SetupReportTests(unittest.TestCase):
    @staticmethod
    def report(payload: dict) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = print_setup(payload)
        return code, buffer.getvalue()

    @staticmethod
    def health(status: str, provider: str = "openai-codex", **agent: str) -> dict:
        return {
            "ok": True,
            "provider": provider,
            "model": "gpt-5.6-sol",
            "thinking": "low",
            "agent": {"status": status, **agent},
        }

    def test_ready_reports_success_and_settings(self):
        code, output = self.report(self.health("ready"))

        self.assertEqual(code, 0)
        self.assertIn("setup is done", output)
        self.assertIn("omarchy-shell ask-omar open", output)
        self.assertIn("openai-codex", output)
        self.assertIn("config.toml", output)

    def test_missing_pi_gives_install_steps_and_fails(self):
        code, output = self.report(self.health("missing"))

        self.assertEqual(code, 1)
        self.assertIn("https://pi.dev", output)
        self.assertIn("Scratchpad and capture", output)

    def test_configure_asks_for_model_choice(self):
        code, output = self.report(self.health("configure", provider=""))

        self.assertEqual(code, 1)
        self.assertIn("no provider/model", output)
        self.assertIn("Settings", output)

    def test_signin_names_the_configured_provider_not_a_hardcoded_one(self):
        code, output = self.report(self.health("signin", provider="anthropic"))

        self.assertEqual(code, 1)
        self.assertIn("anthropic", output)
        self.assertNotIn("openai-codex", output)
        self.assertNotIn("https://pi.dev", output)

    def test_signin_gives_the_real_pi_sign_in_steps(self):
        _, output = self.report(self.health("signin"))

        self.assertIn("run pi", output)
        self.assertIn("/login", output)
        self.assertIn("Never paste passwords", output)

    def test_ready_does_not_claim_the_provider_is_reachable(self):
        _, output = self.report(self.health("ready"))

        self.assertIn("credentials are available locally", output)
        self.assertIn("does not guarantee the provider is online", output)

    def test_malformed_agent_payload_exits_without_raising(self):
        payload = self.health("ready")
        payload["agent"] = "not a mapping"

        code, output = self.report(payload)

        self.assertEqual(code, 1)
        self.assertIn("ask-omar health", output)

    def test_unreachable_service_points_at_the_unit(self):
        code, output = self.report({"ok": False, "error": "Ask Omar service is unavailable: nope"})

        self.assertEqual(code, 1)
        self.assertIn("unavailable", output)
        self.assertIn("systemctl --user status ask-omar.service", output)

    def test_setup_command_is_wired_to_the_health_request(self):
        with (
            patch("ask_omar.cli.request", return_value=self.health("ready")) as send,
            redirect_stdout(io.StringIO()),
        ):
            code = main(["setup"])

        self.assertEqual(code, 0)
        send.assert_called_once_with({"type": "health"})

    def test_set_access_command_is_wired_to_system_access_request(self):
        with (
            patch("ask_omar.cli.request", return_value={"ok": True}) as send,
            redirect_stdout(io.StringIO()),
        ):
            code = main(["set-access", "full"])

        self.assertEqual(code, 0)
        send.assert_called_once_with({"type": "set_system_access", "mode": "full"})

    def test_query_draft_and_notes_prefer_stdin_over_argv(self):
        with (
            patch("ask_omar.cli.request", return_value={"ok": True}) as send,
            patch("ask_omar.cli.sys.stdin", io.StringIO("secret ask")),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["query", "--stdin"]), 0)
        send.assert_called_once_with({"type": "query", "query": "secret ask"})

        with (
            patch("ask_omar.cli.request", return_value={"ok": True}) as send,
            patch("ask_omar.cli.sys.stdin", io.StringIO("draft body")),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["draft", "--stdin"]), 0)
        send.assert_called_once_with({"type": "draft_set", "draft": "draft body"})

        with (
            patch("ask_omar.cli.request", return_value={"ok": True}) as send,
            patch("ask_omar.cli.sys.stdin", io.StringIO('["note"]')),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["scratchpad-notes-save", "--stdin"]), 0)
        send.assert_called_once_with({"type": "scratchpad_notes_save", "notes": ["note"]})

    def test_unknown_agent_status_falls_back_to_health(self):
        code, output = self.report(self.health("error", message="Ask Omar couldn't check Pi authentication."))

        self.assertEqual(code, 1)
        self.assertIn("couldn't check Pi", output)
        self.assertIn("ask-omar health", output)


if __name__ == "__main__":
    unittest.main()
