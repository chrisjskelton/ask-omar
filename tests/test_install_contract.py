import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class InstallContractTests(unittest.TestCase):
    def test_marketplace_manifest_has_root_relative_widget(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "ask-omar.assistant")
        self.assertEqual(manifest["entryPoints"]["barWidget"], "plugin/AskOmar.qml")
        self.assertTrue((ROOT / manifest["entryPoints"]["barWidget"]).is_file())
        self.assertFalse((ROOT / "plugin/manifest.json").exists())

    def test_make_targets_support_checkout_and_marketplace_setup(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("omarchy plugin validate .", makefile)
        self.assertIn("install: verify", makefile)
        self.assertIn("setup: verify", makefile)
        install_recipe = makefile[makefile.index("install: verify"):makefile.index("setup: verify")]
        setup_recipe = makefile[makefile.index("setup: verify"):makefile.index("uninstall:")]
        self.assertIn("$(MAKE) test", install_recipe)
        self.assertIn("$(MAKE) test", setup_recipe)
        self.assertIn("./scripts/install.sh --backend-only", makefile)

    def test_capture_helper_and_launcher_are_packaged(self):
        helper = (ROOT / "scripts/capture.sh").read_text(encoding="utf-8")
        launcher = (ROOT / "desktop/ask-omar.desktop").read_text(encoding="utf-8")
        self.assertIn("omarchy capture screenshot", helper)
        self.assertIn("Name=Ask Omar", launcher)
        self.assertIn("Exec=ask-omar-open open", launcher)

    def test_installer_uses_checked_in_marked_sources_and_safe_file_installs(self):
        installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        self.assertNotIn("cat >", installer)
        self.assertNotIn("chmod +x", installer)
        self.assertNotIn("cp -a", installer)
        for line in installer.splitlines():
            if re.match(r"\s*install\s", line) and "install -d" not in line:
                self.assertIn(" -T ", line, line)

        marked_sources = (
            "scripts/app-install-marker",
            "scripts/ask-omar",
            "scripts/ask-omar-open",
            "scripts/capture.sh",
            "systemd/ask-omar.service",
            "desktop/ask-omar.desktop",
            "desktop/ask-omar-settings.desktop",
        )
        for relative in marked_sources:
            with self.subTest(relative=relative):
                self.assertIn(
                    "# Installed by Ask Omar",
                    (ROOT / relative).read_text(encoding="utf-8"),
                )

    def test_readme_pins_a_full_detached_commit_for_each_install_route(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotRegex(readme, r"git clone[^\n]*--branch")
        checkout = 'git -c advice.detachedHead=false checkout --detach "$ASK_OMAR_COMMIT"'
        self.assertGreaterEqual(readme.count(checkout), 4)
        self.assertIn('make install ASK_OMAR_COMMIT="$ASK_OMAR_COMMIT"', readme)
        self.assertIn('make setup ASK_OMAR_COMMIT="$ASK_OMAR_COMMIT"', readme)


if __name__ == "__main__":
    unittest.main()
