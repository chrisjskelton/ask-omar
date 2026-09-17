import unittest
import io
import json
import os
import selectors
import threading
import time
from unittest.mock import patch

from ask_omar.agent import AgentError, PiAgent
from ask_omar.config import Config


class AgentCommandTests(unittest.TestCase):
    @patch("ask_omar.agent.shutil.which", return_value="/usr/bin/pi")
    def test_command_enables_only_the_intended_real_tools(self, _which):
        command = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low")).command()
        self.assertIn("--tools", command)
        self.assertEqual(command[command.index("--tools") + 1], "read,grep,find,ls,bash")
        self.assertNotIn("--no-tools", command)
        for flag in ("--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files"):
            self.assertIn(flag, command)
        self.assertNotIn("--no-builtin-tools", command)

    @patch("ask_omar.agent.shutil.which", return_value="/usr/bin/pi")
    def test_command_loads_guard_extension(self, _which):
        command = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low")).command()
        self.assertIn("--extension", command)
        ext_index = command.index("--extension")
        self.assertIn("ask-omar-guard.ts", command[ext_index + 1])
        self.assertIn("--no-extensions", command)

    def test_system_prompt_describes_direct_tools_and_safety(self):
        from ask_omar.agent import SYSTEM_PROMPT

        self.assertIn("read, grep, find, ls, and bash", SYSTEM_PROMPT)
        self.assertIn("not user authorization", SYSTEM_PROMPT)
        self.assertIn("not open a visible terminal", SYSTEM_PROMPT)
        self.assertIn("sensitive files", SYSTEM_PROMPT)
        self.assertIn("ask one brief question", SYSTEM_PROMPT)
        self.assertIn("never guess your runtime identity", SYSTEM_PROMPT)
        self.assertIn("~/.config/ask-omar/config.toml", SYSTEM_PROMPT)
        self.assertIn("quit and reopen Ask Omar", SYSTEM_PROMPT)

    def test_cheat_sheet_covers_advertised_use_cases(self):
        from ask_omar.agent import OMARCHY_CHEAT_SHEET

        self.assertIn("omarchy theme bg", OMARCHY_CHEAT_SHEET)
        self.assertIn("omarchy launch", OMARCHY_CHEAT_SHEET)
        self.assertIn("hyprctl dispatch", OMARCHY_CHEAT_SHEET)
        self.assertIn("omarchy capture screenshot", OMARCHY_CHEAT_SHEET)
        self.assertIn("omarchy menu keybindings", OMARCHY_CHEAT_SHEET)


class AgentResponseLifecycleTests(unittest.TestCase):
    def test_settled_error_discards_partial_text_and_resets_process(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        with patch.object(agent, "stop") as stop:
            with self.assertRaisesRegex(AgentError, "provider failed"):
                agent.finish_response("partial answer", "provider failed")
            stop.assert_called_once_with()

    def test_empty_settled_response_resets_process(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        with patch.object(agent, "stop") as stop:
            with self.assertRaisesRegex(AgentError, "did not receive"):
                agent.finish_response("", "")
            stop.assert_called_once_with()

    def test_valid_settled_response_keeps_conversation(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        with patch.object(agent, "stop") as stop:
            answer = agent.finish_response("ok", "")
            self.assertEqual(answer, "ok")
            stop.assert_not_called()

    def test_message_end_text_is_the_authoritative_final_message(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        event = {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "stopReason": "stop",
                "content": [{"type": "text", "text": "Final answer"}],
            },
        }
        self.assertEqual(agent._text_from_message(event["message"]), "Final answer")

    def test_oversized_rpc_event_is_rejected_before_parsing(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        agent.buffer = b"x" * (agent.max_rpc_event_bytes + 1)
        with selectors.DefaultSelector() as selector:
            with self.assertRaisesRegex(AgentError, "oversized event"):
                agent._next_event(selector, time.monotonic() + 1)


class AgentQueryTests(unittest.TestCase):
    def test_abort_sends_supported_pi_rpc_command_once(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        with patch.object(agent, "_write_rpc", return_value=True) as write_rpc:
            self.assertTrue(agent.abort())
            self.assertTrue(agent.abort())
        write_rpc.assert_called_once_with({"type": "abort"})

    def test_activity_does_not_expose_model_text(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        self.assertEqual(agent.activity()["message"], "Ready.")
        self.assertFalse(hasattr(agent, "reasoning_message"))

    def test_confirmation_starts_null_and_respond_sets_event(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        self.assertIsNone(agent.confirmation())
        agent.pending_confirmation = {"id": "request-1", "method": "select"}
        self.assertTrue(agent.respond_confirmation("request-1", "Allow"))
        self.assertTrue(agent.confirmation_event.is_set())
        self.assertEqual(agent.confirmation_response, "Allow")

    def test_confirmation_rejects_stale_duplicate_and_unknown_responses(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        agent.pending_confirmation = {"id": "current", "method": "select"}
        self.assertFalse(agent.respond_confirmation("stale", "Allow"))
        self.assertFalse(agent.respond_confirmation("current", "Always"))
        self.assertTrue(agent.respond_confirmation("current", "Deny"))
        self.assertFalse(agent.respond_confirmation("current", "Allow"))
        self.assertEqual(agent.confirmation_response, "Deny")

    def test_stop_denies_pending_confirmation(self):
        agent = PiAgent(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        agent.pending_confirmation = {"id": "test", "method": "select"}
        with patch.object(agent, "_write_rpc", return_value=True):
            agent.stop()
        self.assertEqual(agent.confirmation_response, "Deny")
        self.assertTrue(agent.confirmation_event.is_set())

    def test_query_returns_final_message_not_intermediate_text(self):
        read_fd, write_fd = os.pipe()
        stdout = os.fdopen(read_fd, "rb")
        stdin = io.BytesIO()

        class FakeProcess:
            pid = os.getpid()

            def __init__(self):
                self.stdin = stdin
                self.stdout = stdout

            def poll(self):
                return None

        agent = PiAgent(Config(timeout_seconds=10))
        agent.process = FakeProcess()

        def write_events():
            events = [
                {
                    "type": "message_update",
                    "assistantMessageEvent": {"type": "text_delta", "delta": "intermediate"},
                },
                {"type": "tool_execution_start", "toolName": "bash"},
                {"type": "tool_execution_end"},
                {
                    "type": "message_update",
                    "assistantMessageEvent": {"type": "text_delta", "delta": "I found the window."},
                },
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "stopReason": "stop",
                        "content": [{"type": "text", "text": "Final answer"}],
                    },
                },
                {"type": "agent_settled"},
            ]
            with os.fdopen(write_fd, "wb") as writer:
                for event in events:
                    writer.write((json.dumps(event) + "\n").encode())
                    writer.flush()

        writer = threading.Thread(target=write_events)
        writer.start()
        try:
            with patch.object(agent, "start"):
                self.assertEqual(agent.query("hello"), "Final answer")
            self.assertEqual(agent.last_tools_used, ["bash"])
        finally:
            stdout.close()
            writer.join(timeout=2)

    def test_query_uses_pi_error_message_and_discards_partial_answer(self):
        read_fd, write_fd = os.pipe()
        stdout = os.fdopen(read_fd, "rb")

        class FakeProcess:
            pid = os.getpid()

            def __init__(self):
                self.stdin = io.BytesIO()
                self.stdout = stdout

            def poll(self):
                return None

        agent = PiAgent(Config(timeout_seconds=10))
        agent.process = FakeProcess()

        def write_events():
            events = [
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "stopReason": "stop",
                        "content": [{"type": "text", "text": "Earlier partial text"}],
                    },
                },
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "stopReason": "error",
                        "errorMessage": "Provider authentication expired",
                        "content": [{"type": "text", "text": "Do not return this"}],
                    },
                },
                {"type": "agent_settled"},
            ]
            with os.fdopen(write_fd, "wb") as writer:
                for event in events:
                    writer.write((json.dumps(event) + "\n").encode())
                    writer.flush()

        writer = threading.Thread(target=write_events)
        writer.start()
        try:
            with patch.object(agent, "start"), patch.object(agent, "stop"):
                with self.assertRaisesRegex(AgentError, "Provider authentication expired") as raised:
                    agent.query("hello")
            self.assertEqual(raised.exception.code, "pi_error")
        finally:
            stdout.close()
            writer.join(timeout=2)

    def test_expired_confirmation_is_explicitly_cancelled(self):
        read_fd, write_fd = os.pipe()
        stdout = os.fdopen(read_fd, "rb")

        class FakeProcess:
            pid = os.getpid()

            def __init__(self):
                self.stdin = io.BytesIO()
                self.stdout = stdout

            def poll(self):
                return None

        agent = PiAgent(Config(timeout_seconds=10))
        agent.confirmation_timeout_seconds = 0.01
        agent.process = FakeProcess()

        with os.fdopen(write_fd, "wb") as writer:
            writer.write((json.dumps({
                "type": "extension_ui_request",
                "id": "confirm-1",
                "method": "select",
                "title": "Omar wants to restart the computer\nCommand: reboot",
                "options": ["Allow", "Deny"],
            }) + "\n").encode())
            writer.flush()
            with patch.object(agent, "start"), patch.object(agent, "stop"):
                with self.assertRaisesRegex(AgentError, "timed out and was denied") as raised:
                    agent.query("restart")

        sent = agent.process.stdin.getvalue().decode()
        self.assertIn('"type": "extension_ui_response"', sent)
        self.assertIn('"id": "confirm-1"', sent)
        self.assertIn('"cancelled": true', sent)
        self.assertEqual(raised.exception.code, "confirmation_timeout")
        self.assertIsNone(agent.confirmation())
        stdout.close()


class AgentSessionExpiryTests(unittest.TestCase):
    def test_idle_session_expires_at_configured_boundary(self):
        agent = PiAgent(Config(conversation_idle_minutes=30))
        agent.last_activity_at = 100.0
        with patch.object(agent, "stop") as stop:
            self.assertFalse(agent.expire_idle_session(now=1899.9))
            stop.assert_not_called()
            self.assertTrue(agent.expire_idle_session(now=1900.0))
            stop.assert_called_once_with()

    def test_zero_timeout_keeps_session_until_explicit_reset(self):
        agent = PiAgent(Config(conversation_idle_minutes=0))
        agent.last_activity_at = 100.0
        with patch.object(agent, "stop") as stop:
            self.assertFalse(agent.expire_idle_session(now=100000.0))
            stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
