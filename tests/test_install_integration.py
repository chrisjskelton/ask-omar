import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
COMMANDS = (
    "systemctl",
    "omarchy",
    "omarchy-shell",
    "omarchy-restart-shell",
    "omarchy-capture-region",
    "omarchy-notification-send",
    "wl-copy",
    "grim",
    "jq",
    "pgrep",
    "xdg-open",
)


class InstallIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.home = Path(self.sandbox.name) / "home"
        self.home.mkdir()
        self.config = self.home / ".config"
        self.data = self.home / ".local/share"
        self.state = self.home / ".local/state"
        self.bin = Path(self.sandbox.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.sandbox.name) / "commands.log"
        for command in COMMANDS:
            path = self.bin / command
            path.write_text(
                '#!/bin/sh\n'
                'printf "%s %s\\n" "$(basename "$0")" "$*" >> "$TEST_COMMAND_LOG"\n'
                'exit 0\n',
                encoding="utf-8",
            )
            path.chmod(0o755)
        self.env = dict(os.environ)
        self.env.update(
            HOME=str(self.home),
            XDG_CONFIG_HOME=str(self.config),
            XDG_DATA_HOME=str(self.data),
            XDG_STATE_HOME=str(self.state),
            TEST_COMMAND_LOG=str(self.log),
            PATH=f"{self.bin}:{os.environ['PATH']}",
        )
        self.plugin = self.config / "omarchy/plugins/ask-omar.assistant"

    def run_script(self, script, *args, root=ROOT, success=True):
        result = subprocess.run(
            ["bash", str(root / "scripts" / script), *args],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )
        if success and result.returncode:
            self.fail(f"{script} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
        return result

    def calls(self):
        return self.log.read_text(encoding="utf-8") if self.log.exists() else ""

    def test_full_install_update_and_uninstall_preserve_user_data(self):
        self.run_script("install.sh")
        manifest = json.loads((self.plugin / "manifest.json").read_text())
        self.assertEqual(manifest["entryPoints"]["barWidget"], "plugin/AskOmar.qml")
        self.assertTrue((self.plugin / "plugin/AskOmar.qml").is_file())
        self.assertFalse((self.plugin / "AskOmar.qml").exists())
        self.assertTrue((self.data / "ask-omar/service/ask_omar/__main__.py").is_file())
        self.assertTrue((self.home / ".local/bin/ask-omar").is_file())
        self.assertIn(f"omarchy plugin validate {ROOT}", self.calls())
        self.assertIn("omarchy plugin enable ask-omar.assistant --after omarchy.agents", self.calls())

        config_file = self.config / "ask-omar/config.toml"
        guard_file = self.config / "ask-omar/guard.json"
        config_file.write_text("custom config\n")
        guard_file.write_text("custom guard\n")
        state_file = self.state / "ask-omar/notes.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("keep notes\n")
        (self.plugin / "plugin/AskOmar.qml").write_text("old version\n")
        self.run_script("install.sh")
        self.assertEqual(config_file.read_text(), "custom config\n")
        self.assertEqual(guard_file.read_text(), "custom guard\n")
        self.assertEqual(state_file.read_text(), "keep notes\n")
        self.assertEqual(
            (self.plugin / "plugin/AskOmar.qml").read_bytes(),
            (ROOT / "plugin/AskOmar.qml").read_bytes(),
        )
        self.assertEqual(stat.S_IMODE(config_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(guard_file.stat().st_mode), 0o600)
        self.run_script("uninstall.sh")
        self.assertFalse(self.plugin.exists())
        self.assertFalse((self.data / "ask-omar").exists())
        self.assertEqual(config_file.read_text(), "custom config\n")
        self.assertEqual(guard_file.read_text(), "custom guard\n")
        self.assertEqual(state_file.read_text(), "keep notes\n")
        self.assertIn("omarchy plugin disable ask-omar.assistant", self.calls())

    def test_marketplace_backend_setup_does_not_copy_plugin_into_itself(self):
        shutil.copytree(ROOT, self.plugin, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        original = (self.plugin / "plugin/AskOmar.qml").read_bytes()
        self.run_script("install.sh", "--backend-only", root=self.plugin)
        self.assertEqual((self.plugin / "plugin/AskOmar.qml").read_bytes(), original)
        self.assertTrue((self.data / "ask-omar/service/ask_omar/__main__.py").is_file())
        self.assertNotIn("omarchy plugin enable", self.calls())
        self.run_script("uninstall.sh", "--backend-only", root=self.plugin)
        self.assertTrue(self.plugin.exists())
        self.assertFalse((self.data / "ask-omar").exists())
        self.assertNotIn("omarchy plugin disable", self.calls())

    def test_full_install_from_already_installed_marketplace_source(self):
        shutil.copytree(ROOT, self.plugin, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.run_script("install.sh", root=self.plugin)
        self.assertTrue((self.plugin / "manifest.json").is_file())
        self.assertTrue((self.plugin / "plugin/AskOmar.qml").is_file())
        self.assertIn("omarchy plugin enable ask-omar.assistant", self.calls())

    def test_failed_runtime_preflight_leaves_targets_untouched(self):
        node = self.bin / "node"
        node.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        node.chmod(0o755)
        result = self.run_script("install.sh", success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("direct TypeScript execution", result.stderr)
        self.assertFalse(self.plugin.exists())
        self.assertFalse((self.data / "ask-omar").exists())
        self.assertFalse((self.config / "ask-omar").exists())
        self.assertEqual(self.calls(), "")

    def test_pi_detection_only_reads_local_help_offline(self):
        pi = self.bin / "pi"
        pi.write_text(
            '#!/bin/sh\n'
            'printf "pi %s offline=%s\\n" "$*" "$PI_OFFLINE" >> "$TEST_COMMAND_LOG"\n'
            'printf "%s\\n" "--mode --no-session --tools --no-extensions --extension '
            '--no-skills --no-prompt-templates --no-themes --no-context-files '
            '--provider --model --thinking --system-prompt --name --list-models"\n',
            encoding="utf-8",
        )
        pi.chmod(0o755)
        result = self.run_script("install.sh", "--backend-only")
        self.assertIn("Pi supports Ask Omar's required flags", result.stdout)
        self.assertIn("pi --help offline=1", self.calls())


if __name__ == "__main__":
    unittest.main()
