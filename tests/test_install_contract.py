import json
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
        self.assertIn("install: test validate", makefile)
        self.assertIn("./scripts/install.sh --backend-only", makefile)

    def test_capture_helper_and_launcher_are_packaged(self):
        helper = (ROOT / "scripts/capture.sh").read_text(encoding="utf-8")
        launcher = (ROOT / "desktop/ask-omar.desktop").read_text(encoding="utf-8")
        self.assertIn("omarchy capture screenshot", helper)
        self.assertIn("Name=Ask Omar", launcher)
        self.assertIn("Exec=ask-omar-open open", launcher)


if __name__ == "__main__":
    unittest.main()
