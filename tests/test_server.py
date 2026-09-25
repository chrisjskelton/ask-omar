import json
import socket
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ask_omar.agent import AgentCancelled
from ask_omar.config import Config
from ask_omar.server import MAX_REQUEST_BYTES, AskOmar, OmarServer
from ask_omar.state import StateStore


class LocalAnswerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.omar = AskOmar(Config(provider="openai-codex", model="gpt-5.6-sol", thinking="low"))
        self.omar.state = StateStore(Path(self.temp.name) / "state.json")
        # Existing query tests assume the agent path is reachable; keep readiness open
        # unless a test deliberately exercises the fail-fast gate.
        self.readiness_patch = patch.object(
            AskOmar, "query_blocked_by_agent_readiness", return_value=None
        )
        self.readiness_patch.start()

    def tearDown(self):
        self.readiness_patch.stop()
        self.omar.close()
        self.temp.cleanup()

    @patch.object(AskOmar, "agent_prompt", return_value="structured prompt")
    def test_natural_language_questions_always_reach_tool_enabled_pi(self, _prompt):
        questions = [
            "What is a screenshot?",
            "What is Herdr?",
            "What key closes a window?",
            "Explain what a workspace is",
        ]
        for question in questions:
            agent = Mock()
            agent.query.return_value = "Model answer"
            agent.last_tools_used = []
            self.omar.agent = agent
            result = self.omar.query(question)
            self.assertEqual(result["message"], "Model answer")
            agent.query.assert_called_once()
            self.assertEqual(agent.query.call_args.args[0], "structured prompt")
            self.assertIn("cancel_event", agent.query.call_args.kwargs)

    @patch.object(AskOmar, "agent_prompt", return_value="structured prompt")
    @patch("ask_omar.server.launch")
    def test_ambiguous_requests_reach_pi_without_local_execution(self, launch, _prompt):
        agent = Mock()
        agent.query.return_value = "Please tell me what you would like to do."
        agent.last_tools_used = []
        self.omar.agent = agent
        result = self.omar.query("screenshot")
        self.assertEqual(result["kind"], "assistant")
        launch.assert_not_called()

    @patch("ask_omar.server.launch_url")
    def test_open_url_fast_path_does_not_use_desktop_app_matching(self, launch_url):
        url = "https://github.com/Xn4m3d/omarchy-ask"
        result = self.omar.query(f"open {url}")
        launch_url.assert_called_once_with(url)
        self.assertEqual(result["action"], "url.open")

    @patch.object(AskOmar, "agent_prompt", return_value="structured prompt")
    @patch("ask_omar.server.launch_url")
    def test_compound_url_request_reaches_pi_without_local_launch(self, launch_url, _prompt):
        agent = Mock()
        agent.query.return_value = "I need to know whether to open the link or explain it."
        agent.last_tools_used = []
        self.omar.agent = agent
        result = self.omar.query("open https://example.com and explain it")
        self.assertEqual(result["kind"], "assistant")
        launch_url.assert_not_called()

    @patch("ask_omar.server.launch_url")
    def test_explicit_google_search_opens_encoded_results(self, launch_url):
        result = self.omar.query("Search on Google, what's the time?")
        self.assertEqual(result["action"], "web.search")
        self.assertEqual(result["message"], "Searching Google for: what's the time?")
        launch_url.assert_called_once_with(
            "https://www.google.com/search?q=what%27s+the+time%3F"
        )

    @patch("ask_omar.server.launch")
    def test_direct_fixed_actions_still_run(self, launch):
        result = self.omar.handle({"type": "action", "id": "app.browser"})
        self.assertEqual(result["action"], "app.browser")
        launch.assert_called_once()

    def test_agent_plain_text_answer_remains_in_panel(self):
        agent = Mock()
        agent.query.return_value = "Which window do you mean?"
        agent.last_tools_used = []
        self.omar.agent = agent
        result = self.omar.query("ambiguous request")
        self.assertTrue(result["ok"])
        self.assertFalse(result["dismiss"])
        self.assertEqual(result["message"], "Which window do you mean?")
        self.assertEqual(result["recap"], "No commands run.")

    def test_agent_response_includes_tool_recap(self):
        agent = Mock()
        agent.query.return_value = "I moved Firefox to the left."
        agent.last_tools_used = ["run_command"]
        self.omar.agent = agent
        result = self.omar.query("put firefox on the left")
        self.assertEqual(result["recap"], "Ran: run_command")

    def test_agent_prompt_explains_session_history_and_runtime_settings(self):
        self.omar.config = Config(
            provider="test-provider",
            model="test-model",
            thinking="medium",
            conversation_idle_minutes=30,
            history_limit=100,
        )
        prompt = self.omar.agent_prompt("How long do you remember our chat?")
        self.assertIn("after 30 minutes", prompt)
        self.assertIn("newest 100 requests", prompt)
        self.assertIn("view-only", prompt)
        self.assertIn("does not restore that old Pi context", prompt)
        self.assertIn("not a limit on your capabilities", prompt)
        self.assertIn("provider=test-provider, model=test-model, reasoning=medium", prompt)
        self.assertNotIn("Active window", prompt)
        self.assertNotIn("Live system context", prompt)

    def test_agent_prompt_includes_omarchy_cheat_sheet(self):
        prompt = self.omar.agent_prompt("How do I change my wallpaper?")
        self.assertIn("omarchy theme bg", prompt)
        self.assertIn("omarchy launch", prompt)
        self.assertIn("hyprctl dispatch", prompt)
        self.assertIn("omarchy capture screenshot", prompt)

    def test_friendly_error_maps_known_messages(self):
        self.assertIn("too long", AskOmar.friendly_error("Omar's AI response timed out."))
        detailed = AskOmar.friendly_error(
            "Omar's AI response timed out after running shell command “hyprctl clients -j”."
        )
        self.assertIn("after running shell command “hyprctl clients -j”", detailed)
        self.assertIn("ask-omar setup", AskOmar.friendly_error("Pi is not installed. Run setup."))
        self.assertIn("reach Pi", AskOmar.friendly_error("Pi could not be reached."))
        self.assertIn("rephrasing", AskOmar.friendly_error("Omar did not receive an answer from Pi."))

    def test_friendly_error_passes_through_unknown_messages(self):
        self.assertEqual(AskOmar.friendly_error("Something unusual."), "Something unusual.")

    def test_tool_recap_when_no_tools_used(self):
        agent = Mock()
        agent.last_tools_used = []
        self.omar.agent = agent
        self.assertEqual(self.omar.tool_recap(), "No commands run.")

    def test_tool_recap_with_tools(self):
        agent = Mock()
        agent.last_tools_used = ["run_command", "read"]
        self.omar.agent = agent
        self.assertEqual(self.omar.tool_recap(), "Ran: run_command · read")

    def test_history_endpoint_returns_retained_records(self):
        self.omar.state.add_history("Question", "Answer", "assistant")
        result = self.omar.handle({"type": "history"})
        self.assertEqual(result["history"][0]["query"], "Question")
        self.assertEqual(result["history"][0]["response"], "Answer")

    def test_clear_history_endpoint_removes_local_records(self):
        self.omar.state.add_history("Question", "Answer", "assistant")
        result = self.omar.handle({"type": "clear_history"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["history"], [])
        self.assertEqual(self.omar.state.history(), [])

    def test_scratchpad_endpoints_persist_and_clear_text(self):
        saved = self.omar.handle({
            "type": "scratchpad_set",
            "text": "- Follow up\n- /home/example/notes.md",
        })
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["text"], "- Follow up\n- /home/example/notes.md")
        self.assertEqual(self.omar.handle({"type": "scratchpad_get"})["text"], saved["text"])
        self.assertEqual(self.omar.handle({"type": "scratchpad_clear"})["text"], "")

    def test_over_limit_requests_return_codes_and_preserve_state(self):
        self.omar.handle({"type": "draft_set", "draft": "saved draft"})
        self.omar.handle({"type": "scratchpad_set", "text": "saved text"})
        self.omar.handle({"type": "scratchpad_notes_save", "notes": ["saved note"]})
        before = self.omar.state.path.read_bytes()
        requests = [
            ({"type": "query", "query": "q" * 2001}, "query_too_long"),
            ({"type": "draft_set", "draft": "d" * 2001}, "draft_too_long"),
            ({"type": "scratchpad_set", "text": "s" * 20001}, "scratchpad_too_long"),
            ({"type": "scratchpad_notes_save", "notes": [""] * 21}, "scratchpad_notes_too_many"),
            ({"type": "scratchpad_notes_save", "notes": ["n" * 20001]}, "scratchpad_note_too_long"),
            ({"type": "scratchpad_notes_save", "notes": [42]}, "invalid_scratchpad_notes"),
        ]
        for request, code in requests:
            result = self.omar.handle(request)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], code)
            self.assertEqual(self.omar.state.path.read_bytes(), before)

    def test_query_at_limit_reaches_agent_without_truncation(self):
        query = "q" * self.omar.state.max_query_chars
        agent = Mock()
        agent.query.return_value = "Answer"
        agent.last_tools_used = []
        self.omar.agent = agent
        with patch.object(self.omar, "agent_prompt", side_effect=lambda text: text):
            result = self.omar.query(query)
        self.assertTrue(result["ok"])
        agent.query.assert_called_once()
        self.assertEqual(agent.query.call_args.args[0], query)

    def test_scratchpad_screenshot_attachment_is_private_markdown(self):
        source = Path(self.temp.name) / "source image.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"image data")
        state_home = Path(self.temp.name) / "state"
        with patch("ask_omar.server.state_home", return_value=state_home):
            result = self.omar.handle({"type": "scratchpad_attach", "path": str(source)})
        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "scratchpad_attachment")
        self.assertTrue(result["markdown"].startswith("![Screenshot](<file://"))
        attachments = state_home / "scratchpad" / "attachments"
        files = list(attachments.iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), b"\x89PNG\r\n\x1a\n" + b"image data")
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)

    def test_scratchpad_attachment_rejects_non_images_and_oversized_files(self):
        source = Path(self.temp.name) / "notes.txt"
        source.write_bytes(b"not an image")
        result = self.omar.handle({"type": "scratchpad_attach", "path": str(source)})
        self.assertFalse(result["ok"])
        self.assertIn("PNG, JPEG, or WebP", result["error"])

        fake = Path(self.temp.name) / "secret.png"
        fake.write_bytes(b"not really a png")
        result = self.omar.handle({"type": "scratchpad_attach", "path": str(fake)})
        self.assertFalse(result["ok"])
        self.assertIn("PNG, JPEG, or WebP", result["error"])

        link = Path(self.temp.name) / "alias.png"
        target = Path(self.temp.name) / "real.png"
        target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"ok")
        link.symlink_to(target)
        result = self.omar.handle({"type": "scratchpad_attach", "path": str(link)})
        self.assertFalse(result["ok"])
        self.assertIn("symlink", result["error"])

        source = Path(self.temp.name) / "large.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"xx")
        with patch("ask_omar.server.MAX_SCRATCHPAD_ATTACHMENT_BYTES", 1):
            result = self.omar.handle({"type": "scratchpad_attach", "path": str(source)})
        self.assertFalse(result["ok"])
        self.assertIn("too large", result["error"])

    def test_activity_endpoint_exposes_safe_agent_status(self):
        agent = Mock()
        agent.activity.return_value = {"active": True, "message": "Using bash…"}
        agent.confirmation.return_value = None
        self.omar.agent = agent
        result = self.omar.handle({"type": "activity"})
        self.assertEqual(result, {
            "ok": True,
            "kind": "activity",
            "active": True,
            "message": "Using bash…",
            "confirmation": None,
        })

    def test_activity_endpoint_includes_pending_confirmation(self):
        agent = Mock()
        agent.activity.return_value = {"active": True, "message": "Waiting for permission…"}
        agent.confirmation.return_value = {
            "id": "abc",
            "method": "select",
            "title": "Omar wants to delete a folder\nCommand: rm -r /tmp/x",
            "options": ["Allow once", "Allow for 15 minutes", "Deny"],
        }
        self.omar.agent = agent
        result = self.omar.handle({"type": "activity"})
        self.assertEqual(result["confirmation"]["id"], "abc")
        self.assertEqual(result["confirmation"]["method"], "select")
        self.assertIn("rm -r", result["confirmation"]["title"])

    def test_confirm_endpoint_delivers_response(self):
        agent = Mock()
        agent.respond_confirmation.return_value = True
        self.omar.agent = agent
        result = self.omar.handle({"type": "confirm", "id": "abc", "response": "Allow once"})
        agent.respond_confirmation.assert_called_once_with("abc", "Allow once")
        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "confirmed")

    def test_confirm_endpoint_rejects_a_stale_confirmation(self):
        agent = Mock()
        agent.respond_confirmation.return_value = False
        self.omar.agent = agent
        result = self.omar.handle({"type": "confirm", "id": "old", "response": "Allow once"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "stale_confirmation")

    def test_stop_denies_pending_confirmation(self):
        agent = Mock()
        self.omar.agent = agent
        cancel_event = threading.Event()
        with self.omar.active_lock:
            self.omar.active_cancel_event = cancel_event
        result = self.omar.handle({"type": "stop"})
        agent.deny_pending_confirmation.assert_called_once_with()
        agent.abort.assert_called_once_with()
        self.assertEqual(result["kind"], "stopping")

    def test_new_conversation_resets_agent(self):
        agent = Mock()
        self.omar.agent = agent
        result = self.omar.handle({"type": "new_conversation"})
        agent.revoke_temporary_grant.assert_called_once_with()
        agent.stop.assert_called_once_with()
        self.assertTrue(result["ok"])

    def test_stop_invokes_abort(self):
        agent = Mock()
        self.omar.agent = agent
        cancel_event = threading.Event()
        with self.omar.active_lock:
            self.omar.active_cancel_event = cancel_event
        result = self.omar.handle({"type": "stop"})
        self.assertEqual(result["kind"], "stopping")
        self.assertTrue(cancel_event.is_set())
        agent.abort.assert_called_once_with()

    def test_stop_is_responsive_while_pi_query_is_blocked(self):
        started = threading.Event()
        release = threading.Event()

        class BlockingAgent:
            def query(self, _prompt, cancel_event=None):
                started.set()
                while cancel_event is not None and not cancel_event.is_set():
                    time.sleep(0.01)
                release.set()
                raise AgentCancelled("Omar stopped the task.")

            def abort(self):
                return True

            def stop(self):
                return None

            def deny_pending_confirmation(self):
                return False

        self.omar.agent = BlockingAgent()
        result_holder = {}
        query_thread = threading.Thread(
            target=lambda: result_holder.setdefault(
                "result", self.omar.handle({"type": "query", "query": "do something"})
            )
        )
        query_thread.start()
        self.assertTrue(started.wait(2))
        stop_result = self.omar.handle({"type": "stop"})
        self.assertEqual(stop_result["kind"], "stopping")
        self.assertTrue(release.wait(2))
        query_thread.join(timeout=2)
        self.assertFalse(query_thread.is_alive())
        self.assertEqual(result_holder["result"]["kind"], "stopped")
        stopped = self.omar.state.history()
        self.assertEqual(stopped[0]["query"], "do something")
        self.assertEqual(stopped[0]["kind"], "stopped")

    @patch("ask_omar.server.shutil.which", return_value=None)
    def test_health_reports_pi_missing_without_running_it(self, _which):
        with patch("ask_omar.server.subprocess.run") as run:
            result = self.omar.health()
        self.assertEqual(result["agent"]["status"], "missing")
        self.assertEqual(result["agent"]["code"], "pi_missing")
        run.assert_not_called()

    @patch("ask_omar.server.shutil.which", return_value="/usr/bin/pi")
    def test_health_checks_provider_credentials_without_claiming_model_availability(self, _which):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"status":"ready","provider":"openai-codex","authType":"oauth"}',
            stderr="",
        )
        with patch("ask_omar.server.subprocess.run", return_value=completed) as run:
            result = self.omar.health()
        command = run.call_args.args[0]
        self.assertEqual(result["agent"]["status"], "ready")
        self.assertIn("credentials", result["agent"]["message"])
        self.assertNotIn("--model", command)
        self.assertEqual(command[:3], ["pi", "auth", "check"])

    @patch("ask_omar.server.shutil.which", return_value="/usr/bin/pi")
    def test_health_maps_pi_not_ready_and_invalid_to_signin(self, _which):
        for pi_status in ("not_ready", "invalid"):
            completed = subprocess.CompletedProcess(
                args=[], returncode=1, stdout=f'{{"status":"{pi_status}"}}', stderr=""
            )
            with patch("ask_omar.server.subprocess.run", return_value=completed):
                result = self.omar.health()
            self.assertEqual(result["agent"]["status"], "signin")

    def test_stopped_request_cannot_record_a_late_success(self):
        class LateSuccessAgent:
            def query(self, _prompt, cancel_event=None):
                assert cancel_event is not None
                cancel_event.set()
                return "This must not be shown as success."

            def stop(self):
                return None

        self.omar.agent = LateSuccessAgent()
        with patch("ask_omar.server.launch") as launch:
            result = self.omar.query("run something")
        self.assertEqual(result["kind"], "stopped")
        self.assertEqual(result["message"], "Stopped. Anything Omar already ran has not been undone.")
        stopped = self.omar.state.history()
        self.assertEqual(stopped[0]["query"], "run something")
        self.assertEqual(stopped[0]["kind"], "stopped")
        launch.assert_not_called()

    def test_query_fails_fast_when_pi_needs_sign_in(self):
        agent = Mock()
        self.omar.agent = agent
        self.readiness_patch.stop()
        with patch.object(
            AskOmar,
            "health",
            return_value={
                "ok": True,
                "provider": "openai-codex",
                "agent": {"status": "signin", "code": "pi_not_ready", "message": "sign in"},
            },
        ):
            result = self.omar.query("hello there")
        self.readiness_patch.start()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "pi_not_ready")
        self.assertIn("/login", result["error"])
        agent.query.assert_not_called()

    def test_query_fails_fast_when_pi_is_missing(self):
        agent = Mock()
        self.omar.agent = agent
        self.readiness_patch.stop()
        with patch.object(
            AskOmar,
            "health",
            return_value={
                "ok": True,
                "provider": "openai-codex",
                "agent": {"status": "missing", "code": "pi_missing", "message": "missing"},
            },
        ):
            result = self.omar.query("hello there")
        self.readiness_patch.start()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "pi_missing")
        self.assertIn("pi.dev", result["error"])
        agent.query.assert_not_called()

    def test_parse_pi_models_reads_provider_and_model_columns(self):
        output = (
            "provider      model                context  max-out  thinking  images\n"
            "openai-codex  gpt-5.6-sol          272K     128K     yes       yes\n"
            "openai-codex  gpt-5.6-terra        272K     128K     yes       yes\n"
        )
        models = AskOmar.parse_pi_models(output)
        self.assertEqual(
            models,
            [
                {
                    "provider": "openai-codex",
                    "model": "gpt-5.6-sol",
                    "thinking": "yes",
                    "images": "yes",
                },
                {
                    "provider": "openai-codex",
                    "model": "gpt-5.6-terra",
                    "thinking": "yes",
                    "images": "yes",
                },
            ],
        )

    def test_set_agent_writes_config_and_reloads_runtime(self):
        config_path = Path(self.temp.name) / "config.toml"
        config_path.write_text(
            '[agent]\nprovider = "openai-codex"\nmodel = "gpt-5.6-sol"\nthinking = "low"\n',
            encoding="utf-8",
        )
        self.omar.config_path = config_path
        old_agent = Mock()
        old_agent.temporary_grant_until = 123456
        self.omar.agent = old_agent
        with patch("ask_omar.server.PiAgent") as agent_cls:
            agent_cls.return_value = Mock()
            result = self.omar.set_agent(model="gpt-5.6-terra", thinking="high")
        old_agent.stop.assert_called_once()
        self.assertEqual(agent_cls.call_args.args[1], 123456)
        self.assertTrue(result["ok"])
        self.assertEqual(result["model"], "gpt-5.6-terra")
        self.assertEqual(result["thinking"], "high")
        self.assertEqual(Config.load(config_path).model, "gpt-5.6-terra")

    def test_set_system_access_writes_config_and_reloads_runtime(self):
        config_path = Path(self.temp.name) / "config.toml"
        config_path.write_text(
            '[agent]\nprovider = "openai-codex"\nmodel = "gpt-5.6-sol"\nsystem_access = "ask"\n',
            encoding="utf-8",
        )
        self.omar.config_path = config_path
        old_agent = Mock()
        self.omar.agent = old_agent
        with patch("ask_omar.server.PiAgent") as agent_cls:
            agent_cls.return_value = Mock()
            result = self.omar.set_system_access("full")
        old_agent.revoke_temporary_grant.assert_called_once_with()
        old_agent.stop.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual(result["system_access"], "full")
        self.assertEqual(Config.load(config_path).system_access, "full")
        agent_cls.assert_called_once()
        self.assertEqual(agent_cls.call_args.args[0].system_access, "full")

    def test_set_system_access_rejects_unknown_mode_without_reloading(self):
        old_agent = Mock()
        self.omar.agent = old_agent
        result = self.omar.set_system_access("always")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "invalid_system_access")
        old_agent.stop.assert_not_called()

    def test_seed_agent_defaults_uses_pi_settings_when_unset(self):
        config_path = Path(self.temp.name) / "empty.toml"
        config_path.write_text('[agent]\nprovider = ""\nmodel = ""\nthinking = "low"\n', encoding="utf-8")
        settings = Path(self.temp.name) / "settings.json"
        settings.write_text(
            '{"defaultProvider":"openai-codex","defaultModel":"gpt-5.6-terra"}',
            encoding="utf-8",
        )
        self.omar = AskOmar(Config.load(config_path), config_path=config_path)
        with patch("ask_omar.server.shutil.which", return_value="/usr/bin/pi"), patch(
            "ask_omar.server.read_pi_default_identity", return_value=("openai-codex", "gpt-5.6-terra")
        ), patch("ask_omar.server.PiAgent") as agent_cls:
            agent_cls.return_value = Mock()
            seeded = self.omar.seed_agent_defaults()
        self.assertTrue(seeded)
        self.assertEqual(self.omar.config.model, "gpt-5.6-terra")
        self.assertEqual(Config.load(config_path).provider, "openai-codex")

    def test_health_reports_configure_when_identity_still_unset(self):
        config_path = Path(self.temp.name) / "blank.toml"
        config_path.write_text('[agent]\nprovider = ""\nmodel = ""\nthinking = "low"\n', encoding="utf-8")
        self.omar = AskOmar(Config.load(config_path), config_path=config_path)
        with patch.object(AskOmar, "seed_agent_defaults", return_value=False), patch(
            "ask_omar.server.shutil.which", return_value="/usr/bin/pi"
        ):
            result = self.omar.health()
        self.assertEqual(result["agent"]["status"], "configure")
        self.assertEqual(result["agent"]["code"], "agent_unset")

    def test_socket_is_private_at_bind_time(self):
        path = Path(self.temp.name) / "omar.sock"
        server = OmarServer(path, Mock())
        try:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        finally:
            server.server_close()
            path.unlink(missing_ok=True)

    def test_socket_accepts_full_surrogate_escaped_unicode_scratchpad(self):
        notes = ["😀" * self.omar.state.max_scratchpad_chars] * (
            self.omar.state.max_scratchpad_notes
        )
        payload = (
            json.dumps(
                {"type": "scratchpad_notes_save", "notes": notes}, ensure_ascii=True
            )
            + "\n"
        ).encode("utf-8")
        self.assertGreater(len(payload), 4_000_000)
        self.assertLessEqual(len(payload), MAX_REQUEST_BYTES)

        response = self.socket_request(payload)

        self.assertTrue(response["ok"])
        self.assertEqual(response["notes"], notes)

    def test_socket_rejects_oversized_request_with_clear_error(self):
        response = self.socket_request(b"x" * (MAX_REQUEST_BYTES + 1) + b"\n")

        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "request_too_large")
        self.assertIn("maximum 5 MiB", response["error"])

    def socket_request(self, payload: bytes) -> dict:
        path = Path(self.temp.name) / "request.sock"
        server = OmarServer(path, self.omar)
        server_thread = threading.Thread(target=server.handle_request)
        server_thread.start()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(path))
                client.sendall(payload)
                client.shutdown(socket.SHUT_WR)
                response = client.makefile("rb").readline()
            return json.loads(response.decode("utf-8"))
        finally:
            server_thread.join(timeout=2)
            server.server_close()
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
