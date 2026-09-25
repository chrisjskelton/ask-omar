import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ask_omar.config import Config, read_pi_default_identity, runtime_socket, update_agent_settings


class ConfigTests(unittest.TestCase):
    def test_conversation_timeout_and_history_limit_are_configurable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text(
                "[conversation]\nidle_timeout_minutes = 45\n\n[history]\nlimit = 250\n",
                encoding="utf-8",
            )
            config = Config.load(path)
            self.assertEqual(config.conversation_idle_minutes, 45)
            self.assertEqual(config.history_limit, 250)

    def test_system_access_defaults_to_ask_and_validates_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            self.assertEqual(Config.load(path).system_access, "ask")
            path.write_text('[agent]\nsystem_access = "full"\n', encoding="utf-8")
            self.assertEqual(Config.load(path).system_access, "full")
            path.write_text('[agent]\nsystem_access = "unsafe"\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "system_access must be one of"):
                Config.load(path)

    def test_zero_disables_idle_expiry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text("[conversation]\nidle_timeout_minutes = 0\n", encoding="utf-8")
            self.assertEqual(Config.load(path).conversation_idle_minutes, 0)

    def test_zero_disables_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text("[history]\nlimit = 0\n", encoding="utf-8")
            self.assertEqual(Config.load(path).history_limit, 0)

    def test_malformed_sections_and_values_raise_useful_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            for source, message in (
                ('agent = "bad"\n', r"\[agent\] must be a table"),
                ('[agent]\nprovider = ["bad"]\n', "provider must be text"),
                ('[history]\nlimit = "bad"\n', "limit must be an integer"),
            ):
                path.write_text(source, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    Config.load(path)

    def test_failed_atomic_update_leaves_previous_config_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text('[agent]\nmodel = "old"\n', encoding="utf-8")
            before = path.read_bytes()
            with patch("ask_omar.config.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    update_agent_settings(path, model="new")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.glob("config.*")), [path])

    def test_update_keeps_existing_parent_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "shared"
            parent.mkdir(mode=0o755)
            parent.chmod(0o755)
            path = parent / "config.toml"
            update_agent_settings(path, model="example")
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(Config.load(path).model, "example")

    def test_update_in_unowned_writable_parent(self):
        parent = Path(tempfile.gettempdir())
        if parent.stat().st_uid == os.getuid():
            self.skipTest("No non-owned writable temporary parent is available")
        with tempfile.NamedTemporaryFile(dir=parent, prefix="ask-omar-config-", delete=False) as handle:
            path = Path(handle.name)
        try:
            before = stat.S_IMODE(parent.stat().st_mode)
            update_agent_settings(path, model="example")
            self.assertEqual(Config.load(path).model, "example")
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), before)
        finally:
            path.unlink(missing_ok=True)

    def test_new_config_directory_is_private(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "ask-omar"
            update_agent_settings(parent / "config.toml", model="example")
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o700)

    def test_update_agent_settings_preserves_other_sections(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text(
                "# keep me\n\n[agent]\n"
                'backend = "pi"\n'
                'provider = "openai-codex"\n'
                'model = "gpt-5.6-sol"\n'
                'thinking = "low"\n'
                "timeout_seconds = 90\n\n"
                "[history]\nlimit = 40\n",
                encoding="utf-8",
            )
            update_agent_settings(path, model="gpt-5.6-terra", thinking="high")
            text = path.read_text(encoding="utf-8")
            self.assertIn("# keep me", text)
            self.assertIn('model = "gpt-5.6-terra"', text)
            self.assertIn('thinking = "high"', text)
            self.assertIn('provider = "openai-codex"', text)
            self.assertIn("[history]\nlimit = 40", text)
            config = Config.load(path)
            self.assertEqual(config.model, "gpt-5.6-terra")
            self.assertEqual(config.thinking, "high")
            self.assertEqual(config.history_limit, 40)

    def test_update_system_access_preserves_other_agent_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text('[agent]\nprovider = "example"\nmodel = "model"\n', encoding="utf-8")
            update_agent_settings(path, system_access="off")
            config = Config.load(path)
            self.assertEqual(config.system_access, "off")
            self.assertEqual(config.provider, "example")
            with self.assertRaisesRegex(ValueError, "System access must be one of"):
                update_agent_settings(path, system_access="unsafe")

    def test_update_agent_settings_rejects_unknown_thinking(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text('[agent]\nthinking = "low"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                update_agent_settings(path, thinking="ultra")

    def test_example_config_does_not_pin_a_provider_model(self):
        example = Path(__file__).parents[1] / "config" / "config.example.toml"
        text = example.read_text(encoding="utf-8")
        self.assertIn('provider = ""', text)
        self.assertIn('model = ""', text)
        self.assertIn('system_access = "ask"', text)
        self.assertNotIn("gpt-5.6-sol", text)

    def test_read_pi_default_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(
                '{"defaultProvider":"openai-codex","defaultModel":"gpt-5.6-sol"}',
                encoding="utf-8",
            )
            self.assertEqual(
                read_pi_default_identity(path),
                ("openai-codex", "gpt-5.6-sol"),
            )


class RuntimeSocketTests(unittest.TestCase):
    def test_xdg_runtime_socket_uses_existing_private_runtime(self):
        with patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/example"}):
            self.assertEqual(runtime_socket(), Path("/run/user/example/ask-omar.sock"))

    def test_fallback_parent_is_private_before_socket_bind(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": ""}), patch(
                "ask_omar.config.tempfile.gettempdir", return_value=temporary
            ):
                path = runtime_socket()
                self.assertEqual(path.name, "ask-omar.sock")
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
                self.assertEqual(path.parent.stat().st_uid, os.getuid())

    def test_fallback_rejects_precreated_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "other"
            target.mkdir()
            (root / f"ask-omar-{os.getuid()}").symlink_to(target, target_is_directory=True)
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": ""}), patch(
                "ask_omar.config.tempfile.gettempdir", return_value=temporary
            ):
                with self.assertRaises(RuntimeError):
                    runtime_socket()


if __name__ == "__main__":
    unittest.main()
