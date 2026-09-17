import unittest
from pathlib import Path


INSTALLER = (Path(__file__).parents[1] / "scripts" / "install.sh").read_text(encoding="utf-8")
UNINSTALLER = (Path(__file__).parents[1] / "scripts" / "uninstall.sh").read_text(encoding="utf-8")


class InstallContractTests(unittest.TestCase):
    def test_service_wrapper_can_find_user_installed_pi(self):
        self.assertIn(
            'export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:',
            INSTALLER,
        )

    def test_local_config_is_installed_privately(self):
        self.assertIn('install -d -m 700 "$(dirname "$CONFIG_TARGET")"', INSTALLER)
        self.assertIn('install -m 600 "$ROOT/config/config.example.toml"', INSTALLER)
        self.assertIn('chmod 600 "$CONFIG_TARGET"', INSTALLER)

    def test_installs_a_discoverable_launcher(self):
        self.assertIn('DESKTOP_TARGET="$DATA_HOME/applications/ask-omar.desktop"', INSTALLER)
        self.assertIn('install -m 644 "$ROOT/desktop/ask-omar.desktop" "$DESKTOP_TARGET"', INSTALLER)

        launcher = Path(__file__).parents[1] / "desktop" / "ask-omar.desktop"
        self.assertTrue(launcher.exists())
        content = launcher.read_text(encoding="utf-8")
        self.assertIn("Name=Ask Omar", content)
        self.assertIn("Exec=ask-omar-open open", content)

    def test_capture_helper_is_installed_and_removed(self):
        self.assertIn('install -m 755 "$ROOT/scripts/capture.sh" "$BIN_HOME/ask-omar-capture"', INSTALLER)
        self.assertIn('"$HOME/.local/bin/ask-omar-capture"', UNINSTALLER)
        helper = Path(__file__).parents[1] / "scripts" / "capture.sh"
        self.assertTrue(helper.exists())
        self.assertIn("omarchy capture screenshot", helper.read_text(encoding="utf-8"))

    def test_pi_is_detected_but_not_installed_or_changed(self):
        self.assertIn("command -v pi", INSTALLER)
        self.assertIn("Pi was not found", INSTALLER)
        self.assertIn("did not install it", INSTALLER)
        self.assertIn("was not changed", INSTALLER)

    def test_install_restarts_shell_to_load_the_installed_plugin_version(self):
        self.assertIn(
            "for command in python omarchy omarchy-shell omarchy-restart-shell systemctl",
            INSTALLER,
        )
        enable_index = INSTALLER.index(
            "omarchy plugin enable ask-omar.assistant --after omarchy.agents"
        )
        restart_index = INSTALLER.index("omarchy-restart-shell", enable_index)
        self.assertLess(enable_index, restart_index)

    def test_uninstall_preserves_pi_signin_and_names_retained_data(self):
        self.assertIn("Pi and its provider sign-ins were not changed", UNINSTALLER)
        self.assertIn("drafts, history, Scratchpad notes, and attachments", UNINSTALLER)


if __name__ == "__main__":
    unittest.main()
