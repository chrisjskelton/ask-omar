import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class VerifyCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.checkout = Path(self.temporary.name)
        scripts = self.checkout / "scripts"
        scripts.mkdir()
        (scripts / "verify-checkout.sh").write_bytes(
            (ROOT / "scripts/verify-checkout.sh").read_bytes()
        )
        subprocess.run(["git", "init", "-q"], cwd=self.checkout, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=self.checkout,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self.checkout, check=True
        )
        subprocess.run(["git", "add", "."], cwd=self.checkout, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "fixture"], cwd=self.checkout, check=True
        )
        self.commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.checkout, text=True
        ).strip()

    def verify(self, commit=None):
        env = dict(os.environ)
        if commit is not None:
            env["ASK_OMAR_COMMIT"] = commit
        else:
            env.pop("ASK_OMAR_COMMIT", None)
        return subprocess.run(
            ["bash", "scripts/verify-checkout.sh"],
            cwd=self.checkout,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_only_exact_clean_commit_passes(self):
        for candidate in (None, self.commit[:12], "0" * 40):
            with self.subTest(candidate=candidate):
                self.assertNotEqual(self.verify(candidate).returncode, 0)
        self.assertEqual(self.verify(self.commit).returncode, 0)

    def test_tracked_and_untracked_changes_fail(self):
        script = self.checkout / "scripts/verify-checkout.sh"
        original = script.read_text()
        script.write_text(original + "\n")
        self.assertNotEqual(self.verify(self.commit).returncode, 0)
        script.write_text(original)
        subprocess.run(["git", "checkout", "--", str(script)], cwd=self.checkout, check=True)

        (self.checkout / "untracked.txt").write_text("not reviewed\n")
        self.assertNotEqual(self.verify(self.commit).returncode, 0)


if __name__ == "__main__":
    unittest.main()
