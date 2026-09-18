import contextlib
import io
import json
import unittest
from pathlib import Path

from ask_omar import __version__
from ask_omar.cli import parser


class VersionTests(unittest.TestCase):
    def test_version_is_consistent_and_available_from_cli(self):
        manifest = json.loads(
            (Path(__file__).parents[1] / "manifest.json").read_text()
        )
        self.assertEqual(__version__, "0.1.0")
        self.assertEqual(manifest["version"], __version__)

        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stopped:
            parser().parse_args(["--version"])
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), f"Ask Omar {__version__}")


if __name__ == "__main__":
    unittest.main()
