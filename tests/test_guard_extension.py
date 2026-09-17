import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
GUARD = ROOT / "service" / "ask_omar" / "extensions" / "ask-omar-guard.ts"
CONFIG = json.loads((ROOT / "config" / "guard.example.json").read_text())


def evaluate(command: str) -> dict:
    script = """
import { evaluateCommand } from %s;
const decision = evaluateCommand(%s, %s);
process.stdout.write(JSON.stringify(decision));
""" % (json.dumps(GUARD.as_uri()), json.dumps(command), json.dumps(CONFIG))
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class GuardExtensionTests(unittest.TestCase):
    def test_direct_and_wrapped_catastrophic_commands_are_hard_blocked(self):
        self.assertEqual(evaluate("mkfs.ext4 /dev/sda")["kind"], "hard-block")
        self.assertEqual(evaluate('bash -c "mkfs.ext4 /dev/sda"')["kind"], "hard-block")
        self.assertEqual(evaluate("rm -rf /; echo done")["kind"], "hard-block")
        self.assertEqual(evaluate("bash -c 'rm -rf /'")["kind"], "hard-block")

    def test_safe_cleanup_cannot_mask_hard_block_in_compound_command(self):
        decision = evaluate("rm -rf ./node_modules && mkfs.ext4 /dev/sda")
        self.assertEqual(decision["kind"], "hard-block")
        self.assertEqual(decision["rule"]["reason"], "Filesystem format")

    def test_power_control_warns_and_can_continue_after_confirmation(self):
        direct = evaluate("systemctl reboot")
        compound = evaluate("rm -rf ./node_modules; sudo reboot")
        self.assertEqual(direct["kind"], "confirm")
        self.assertEqual(direct["rule"]["reason"], "System power control")
        self.assertIn("unsaved work", direct["rule"]["description"])
        self.assertEqual(compound["kind"], "confirm")

    def test_safe_exception_only_allows_the_whole_cleanup_command(self):
        self.assertEqual(evaluate("rm -rf ./node_modules")["kind"], "allow")
        self.assertEqual(evaluate("rm -rf /tmp/ask-omar-cache")["kind"], "allow")
        self.assertEqual(evaluate("rm -rf ./node_modules && sudo true")["kind"], "confirm")

    def test_version_one_default_rules_are_migrated_on_load(self):
        legacy = dict(CONFIG)
        legacy.pop("version")
        power = CONFIG["confirmRequired"][0]
        legacy["confirmRequired"] = CONFIG["confirmRequired"][1:]
        legacy["hardBlocked"] = [
            {
                "pattern": r"\brm\s+(-[a-z]*r[a-z]*f?|--recursive).*\s+/\s*$",
                "reason": "Wipe root filesystem",
                "description": "delete everything on the system",
            },
            *CONFIG["hardBlocked"][1:],
            power,
        ]
        legacy["safeExceptions"] = [
            r"rm\s+-rf?\s+\./?(node_modules|dist|build|\.next|target|\.cache|\.tmp)\b",
            r"rm\s+-rf?\s+/tmp/",
        ]

        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory) / "ask-omar"
            config_dir.mkdir()
            path = config_dir / "guard.json"
            path.write_text(json.dumps(legacy))
            script = """
import guard from %s;
let handler;
guard({ on: (_name, callback) => { handler = callback; } });
await handler({ toolName: "bash", input: { command: "true" } }, {});
""" % json.dumps(GUARD.as_uri())
            subprocess.run(
                ["node", "--input-type=module", "--eval", script],
                check=True,
                env={**os.environ, "XDG_CONFIG_HOME": directory},
            )
            migrated = json.loads(path.read_text())

        self.assertEqual(migrated["version"], 2)
        self.assertFalse(any(rule["pattern"] == power["pattern"] for rule in migrated["hardBlocked"]))
        self.assertTrue(any(rule["pattern"] == power["pattern"] for rule in migrated["confirmRequired"]))
        migrated_root = migrated["hardBlocked"][0]["pattern"]
        self.assertIn("[;&|]", migrated_root)
        self.assertNotIn(r"node_modules|dist|build|\.next|target|\.cache|\.tmp)\b", migrated["safeExceptions"][0])


if __name__ == "__main__":
    unittest.main()
