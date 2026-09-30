import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
REVIEWED_COMMIT = "4c5e83375dcc2be4e0fdb7e040f03f4d30e277cc"
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

    def make_checkout(self, destination):
        shutil.copytree(ROOT, destination, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        subprocess.run(["git", "init", "-q"], cwd=destination, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=destination,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=destination, check=True
        )
        subprocess.run(["git", "add", "."], cwd=destination, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "fixture"], cwd=destination, check=True
        )

    def make_legacy_copy(self, release="v0.1.3"):
        (self.plugin / "plugin").mkdir(parents=True, exist_ok=True)
        for relative in ("manifest.json", "plugin/AskOmar.qml"):
            (self.plugin / relative).write_bytes(
                subprocess.check_output(["git", "show", f"{release}:{relative}"], cwd=ROOT)
            )

    def home_snapshot(self):
        snapshot = {}
        for path in sorted(self.home.rglob("*")):
            relative = str(path.relative_to(self.home))
            if path.is_symlink():
                snapshot[relative] = ("symlink", os.readlink(path))
            elif path.is_file():
                snapshot[relative] = ("file", path.read_bytes())
            else:
                snapshot[relative] = ("directory",)
        return snapshot

    def reset_home(self):
        shutil.rmtree(self.home)
        self.home.mkdir()
        self.log.unlink(missing_ok=True)

    def test_setup_update_and_uninstall_preserve_user_data(self):
        self.make_checkout(self.plugin)
        self.run_script("install.sh", root=self.plugin)
        self.assertTrue((self.data / "ask-omar/service/ask_omar/__main__.py").is_file())
        self.assertTrue((self.home / ".local/bin/ask-omar").is_file())
        self.assertNotIn("omarchy plugin enable", self.calls())

        config_file = self.config / "ask-omar/config.toml"
        guard_file = self.config / "ask-omar/guard.json"
        config_file.write_text("custom config\n")
        # Obsolete guard files from older candidates are harmless user data.
        guard_file.write_text("custom guard\n")
        state_file = self.state / "ask-omar/notes.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("keep notes\n")
        app_file = self.data / "ask-omar/user-file.txt"
        nested_app_file = self.data / "ask-omar/service/ask_omar/user-file.txt"
        app_file.write_text("keep app file\n")
        nested_app_file.write_text("keep nested app file\n")
        self.run_script("install.sh", root=self.plugin)
        self.assertEqual(config_file.read_text(), "custom config\n")
        self.assertEqual(guard_file.read_text(), "custom guard\n")
        self.assertEqual(state_file.read_text(), "keep notes\n")
        self.assertEqual(app_file.read_text(), "keep app file\n")
        self.assertEqual(nested_app_file.read_text(), "keep nested app file\n")
        self.assertEqual(stat.S_IMODE(config_file.stat().st_mode), 0o600)
        self.run_script("uninstall.sh", root=self.plugin)
        self.assertEqual(config_file.read_text(), "custom config\n")
        self.assertEqual(guard_file.read_text(), "custom guard\n")
        self.assertEqual(state_file.read_text(), "keep notes\n")
        self.assertEqual(app_file.read_text(), "keep app file\n")
        self.assertEqual(nested_app_file.read_text(), "keep nested app file\n")
        self.assertTrue((self.plugin / "plugin/AskOmar.qml").is_file())
        self.assertIn("omarchy plugin disable ask-omar.assistant", self.calls())

    def test_clean_install_is_fully_removed(self):
        self.run_script("install.sh")

        self.run_script("uninstall.sh")

        self.assertFalse(self.plugin.exists())
        self.assertFalse((self.data / "ask-omar").exists())

    def test_marketplace_backend_setup_does_not_copy_plugin_into_itself(self):
        self.make_checkout(self.plugin)
        original = (self.plugin / "plugin/AskOmar.qml").read_bytes()
        self.run_script("install.sh", "--backend-only", root=self.plugin)
        self.assertEqual((self.plugin / "plugin/AskOmar.qml").read_bytes(), original)
        self.assertTrue((self.data / "ask-omar/service/ask_omar/__main__.py").is_file())
        self.assertNotIn("omarchy plugin enable", self.calls())
        self.run_script("uninstall.sh", "--backend-only", root=self.plugin)
        self.assertTrue(self.plugin.exists())
        self.assertFalse((self.data / "ask-omar").exists())
        self.assertNotIn("omarchy plugin disable", self.calls())

    def test_setup_never_copies_enables_or_restarts_the_widget(self):
        self.make_checkout(self.plugin)
        result = self.run_script("install.sh", root=self.plugin)
        self.assertTrue((self.plugin / "manifest.json").is_file())
        self.assertNotIn("omarchy plugin enable", self.calls())
        self.assertNotIn("omarchy-restart-shell", self.calls())
        self.assertIn("omarchy plugin enable ask-omar.assistant", result.stdout)

    def test_setup_without_a_widget_explains_how_to_add_it(self):
        result = self.run_script("install.sh")
        self.assertFalse(self.plugin.exists())
        self.assertIn("omarchy plugin add https://github.com/chrisjskelton/ask-omar.git", result.stdout)

    def test_full_uninstall_leaves_marketplace_source_checkout(self):
        self.make_checkout(self.plugin)
        self.run_script("install.sh", root=self.plugin)

        result = self.run_script("uninstall.sh", root=self.plugin)

        self.assertTrue((self.plugin / "manifest.json").is_file())
        self.assertTrue((self.plugin / "plugin/AskOmar.qml").is_file())
        self.assertIn("Leaving the widget checkout in place", result.stderr)
        self.assertIn("omarchy plugin remove ask-omar.assistant", result.stderr)

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

    def test_destination_symlinks_are_refused_before_any_target_changes(self):
        cases = (
            ("app", self.data / "ask-omar", "directory", "--backend-only"),
            ("service directory", self.data / "ask-omar/service", "directory", "--backend-only"),
            ("package", self.data / "ask-omar/service/ask_omar", "directory", "--backend-only"),
            ("extensions", self.data / "ask-omar/extensions", "directory", "--backend-only"),
            ("guard", self.data / "ask-omar/extensions/ask-omar-guard.ts", "file", "--backend-only"),
            ("unit", self.config / "systemd/user/ask-omar.service", "file", "--backend-only"),
            ("cli", self.home / ".local/bin/ask-omar", "file", "--backend-only"),
            ("open launcher", self.home / ".local/bin/ask-omar-open", "file", "--backend-only"),
            ("capture launcher", self.home / ".local/bin/ask-omar-capture", "file", "--backend-only"),
            ("desktop", self.data / "applications/ask-omar.desktop", "file", "--backend-only"),
            ("settings desktop", self.data / "applications/ask-omar-settings.desktop", "file", "--backend-only"),
            ("settings desktop without flag", self.data / "applications/ask-omar-settings.desktop", "file", None),
        )
        sentinels = Path(self.sandbox.name) / "sentinels"
        for name, destination, target_kind, mode in cases:
            with self.subTest(destination=name):
                self.reset_home()
                sentinel = sentinels / name.replace(" ", "-")
                if target_kind == "directory":
                    sentinel.mkdir(parents=True, exist_ok=True)
                    marker = sentinel / "keep"
                    marker.write_text("unchanged\n")
                else:
                    sentinel.parent.mkdir(parents=True, exist_ok=True)
                    sentinel.write_text("unchanged\n")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(sentinel, target_is_directory=target_kind == "directory")
                before = self.home_snapshot()

                args = (mode,) if mode else ()
                result = self.run_script("install.sh", *args, success=False)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("symlink", result.stderr)
                if target_kind == "directory":
                    self.assertEqual(marker.read_text(), "unchanged\n")
                else:
                    self.assertEqual(sentinel.read_text(), "unchanged\n")
                self.assertEqual(self.home_snapshot(), before)

    def test_symlinked_application_target_remains_empty(self):
        target = Path(self.sandbox.name) / "empty-target"
        target.mkdir()
        self.data.mkdir(parents=True)
        (self.data / "ask-omar").symlink_to(target, target_is_directory=True)

        self.run_script("install.sh", "--backend-only", success=False)

        self.assertEqual(list(target.iterdir()), [])

    def test_foreign_application_directory_is_refused_without_changes(self):
        app = self.data / "ask-omar"
        app.mkdir(parents=True)
        sentinel = app / "keep"
        sentinel.write_bytes(b"unrelated user data\n")
        before = self.home_snapshot()

        result = self.run_script("install.sh", "--backend-only", success=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("application directory Ask Omar did not install", result.stderr)
        self.assertEqual(self.home_snapshot(), before)
        self.assertEqual(sentinel.read_bytes(), b"unrelated user data\n")
        self.assertEqual(self.calls(), "")

    def test_installed_launcher_writes_no_bytecode(self):
        self.run_script("install.sh", "--backend-only")

        result = subprocess.run(
            [str(self.home / ".local/bin/ask-omar"), "--version"],
            env=self.env,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("Ask Omar", result.stdout)
        self.assertEqual(list((self.data / "ask-omar").rglob("__pycache__")), [])

    def test_bytecode_left_by_an_older_uninstall_does_not_block_setup(self):
        # Before 0.1.4 the running service wrote bytecode next to its modules,
        # and uninstall removed only recorded files, leaving these caches.
        self.run_script("install.sh", "--backend-only")
        app = self.data / "ask-omar"
        subprocess.run(
            ["python", "-m", "compileall", "-q", str(app / "service")],
            check=True,
        )
        self.run_script("uninstall.sh", "--backend-only")
        leftovers = [
            path.relative_to(app).as_posix() for path in app.rglob("*") if path.is_file()
        ]
        self.assertTrue(leftovers)
        self.assertTrue(all(path.endswith(".pyc") for path in leftovers))

        self.run_script("install.sh", "--backend-only")

        self.assertTrue((app / ".installed-by-ask-omar").is_file())
        self.assertTrue((app / "service/ask_omar/__main__.py").is_file())

    def test_bytecode_residue_with_anything_else_is_refused(self):
        cache = self.data / "ask-omar/service/ask_omar/__pycache__"
        cache.mkdir(parents=True)
        (cache / "cli.cpython-313.pyc").write_bytes(b"cache")
        extras = {
            "user file": lambda app: (app / "keep").write_text("user data\n"),
            "non-bytecode in cache": lambda app: (
                app / "service/ask_omar/__pycache__/notes.txt"
            ).write_text("user data\n"),
            "bytecode outside the package": lambda app: (app / "stray.pyc").write_bytes(b"x"),
            "symlinked cache file": lambda app: (
                app / "service/ask_omar/__pycache__/link.pyc"
            ).symlink_to(self.home / "elsewhere"),
            "unreadable directory": lambda app: (app / "service/ask_omar/locked").mkdir(mode=0),
        }
        for name, add_extra in extras.items():
            with self.subTest(name):
                app = self.data / "ask-omar"
                add_extra(app)
                before = self.home_snapshot()

                result = self.run_script("install.sh", "--backend-only", success=False)

                self.assertIn("application directory Ask Omar did not install", result.stderr)
                self.assertEqual(self.home_snapshot(), before)
                for path in (app / "keep", app / "stray.pyc", cache / "notes.txt", cache / "link.pyc"):
                    path.unlink(missing_ok=True)
                locked = app / "service/ask_omar/locked"
                if locked.exists():
                    locked.chmod(0o700)
                    locked.rmdir()

    def test_exact_legacy_application_directories_upgrade_to_marked_install(self):
        for release in ("v0.1.0", REVIEWED_COMMIT):
            with self.subTest(release=release):
                self.reset_home()
                app = self.data / "ask-omar"
                package = app / "service/ask_omar"
                extensions = app / "extensions"
                package.mkdir(parents=True)
                extensions.mkdir()
                package.joinpath("__init__.py").write_bytes(
                    subprocess.check_output(
                        ["git", "show", f"{release}:service/ask_omar/__init__.py"],
                        cwd=ROOT,
                    )
                )
                extensions.joinpath("ask-omar-guard.ts").write_bytes(
                    subprocess.check_output(
                        [
                            "git",
                            "show",
                            f"{release}:service/ask_omar/extensions/ask-omar-guard.ts",
                        ],
                        cwd=ROOT,
                    )
                )

                self.run_script("install.sh", "--backend-only")

                marker = app / ".installed-by-ask-omar"
                self.assertEqual(marker.read_text(), "# Installed by Ask Omar\n")
                self.assertTrue((app / "service/ask_omar/__main__.py").is_file())

    def test_legacy_copied_widget_is_left_by_setup_and_removed_by_uninstall(self):
        for release in ("v0.1.0", REVIEWED_COMMIT, "v0.1.2", "v0.1.3"):
            with self.subTest(release=release):
                self.reset_home()
                self.make_legacy_copy(release)
                before = (self.plugin / "plugin/AskOmar.qml").read_bytes()

                result = self.run_script("install.sh")

                self.assertEqual((self.plugin / "plugin/AskOmar.qml").read_bytes(), before)
                self.assertIn("older Ask Omar widget copy", result.stderr)

                self.run_script("uninstall.sh")

                self.assertFalse(self.plugin.exists())
                self.assertIn("omarchy plugin disable ask-omar.assistant", self.calls())

    def test_marketplace_symlink_to_checkout_is_allowed(self):
        self.plugin.parent.mkdir(parents=True)
        self.plugin.symlink_to(ROOT, target_is_directory=True)

        self.run_script("install.sh")

        self.assertTrue(self.plugin.is_symlink())
        self.assertTrue((self.data / "ask-omar/service/ask_omar/__main__.py").is_file())

    def test_uninstall_preserves_unrecognized_symlink_targets(self):
        app_target = Path(self.sandbox.name) / "foreign-app"
        plugin_target = Path(self.sandbox.name) / "foreign-plugin"
        app_target.mkdir()
        plugin_target.mkdir()
        (app_target / "keep").write_text("app\n")
        (plugin_target / "keep").write_text("plugin\n")
        self.data.mkdir(parents=True)
        (self.data / "ask-omar").symlink_to(app_target, target_is_directory=True)
        self.plugin.parent.mkdir(parents=True)
        self.plugin.symlink_to(plugin_target, target_is_directory=True)

        self.run_script("uninstall.sh")

        self.assertEqual((app_target / "keep").read_text(), "app\n")
        self.assertEqual((plugin_target / "keep").read_text(), "plugin\n")
        self.assertTrue((self.data / "ask-omar").is_symlink())
        self.assertTrue(self.plugin.is_symlink())

    def test_uninstall_preserves_foreign_application_directory(self):
        app = self.data / "ask-omar"
        app.mkdir(parents=True)
        sentinel = app / "keep"
        sentinel.write_text("unrelated user data\n")

        self.run_script("uninstall.sh", "--backend-only")

        self.assertEqual(sentinel.read_text(), "unrelated user data\n")
        self.assertIn("could not identify", self.run_script("uninstall.sh", "--backend-only").stderr)

    def test_uninstall_preserves_modified_managed_application_file(self):
        self.run_script("install.sh", "--backend-only")
        managed = self.data / "ask-omar/service/ask_omar/__init__.py"
        managed.write_text("user-modified\n")

        result = self.run_script("uninstall.sh", "--backend-only")

        self.assertEqual(managed.read_text(), "user-modified\n")
        self.assertIn("Leaving modified application file", result.stderr)

    def test_uninstall_never_follows_application_directory_symlinks(self):
        self.run_script("install.sh", "--backend-only")
        app = self.data / "ask-omar"
        external_service = Path(self.sandbox.name) / "external-service"
        external_package = external_service / "ask_omar"
        external_package.mkdir(parents=True)
        external_init = external_package / "__init__.py"
        external_init.write_bytes((app / "service/ask_omar/__init__.py").read_bytes())
        shutil.rmtree(app / "service")
        (app / "service").symlink_to(external_service, target_is_directory=True)

        result = self.run_script("uninstall.sh", "--backend-only")

        self.assertTrue((app / "service").is_symlink())
        self.assertTrue(external_init.is_file())
        self.assertIn("path containing a symlink", result.stderr)

    def test_uninstall_rejects_manifest_path_traversal(self):
        self.run_script("install.sh", "--backend-only")
        app = self.data / "ask-omar"
        outside = self.data / "outside.txt"
        outside.write_text("keep\n")
        manifest = app / ".installed-files.sha256"
        manifest.write_text(manifest.read_text() + f"{'0' * 64}\t../outside.txt\n")

        result = self.run_script("uninstall.sh", "--backend-only")

        self.assertEqual(outside.read_text(), "keep\n")
        self.assertTrue((app / ".installed-by-ask-omar").is_file())
        self.assertIn("without a valid managed-file manifest", result.stderr)

    def test_modified_and_unknown_plugin_files_survive_uninstall(self):
        self.make_legacy_copy()
        qml = self.plugin / "plugin/AskOmar.qml"
        unknown = self.plugin / "plugin/keep.txt"
        qml.write_text("user-modified\n")
        unknown.write_text("keep\n")

        result = self.run_script("uninstall.sh")

        self.assertEqual(qml.read_text(), "user-modified\n")
        self.assertEqual(unknown.read_text(), "keep\n")
        self.assertIn("Leaving modified plugin file", result.stderr)

    def test_uninstall_never_follows_plugin_directory_symlinks(self):
        self.make_legacy_copy()
        external_plugin = Path(self.sandbox.name) / "external-plugin"
        external_plugin.mkdir()
        external_qml = external_plugin / "AskOmar.qml"
        external_qml.write_bytes((self.plugin / "plugin/AskOmar.qml").read_bytes())
        shutil.rmtree(self.plugin / "plugin")
        (self.plugin / "plugin").symlink_to(external_plugin, target_is_directory=True)

        result = self.run_script("uninstall.sh")

        self.assertTrue((self.plugin / "plugin").is_symlink())
        self.assertTrue(external_qml.is_file())
        self.assertIn("path containing a symlink", result.stderr)

    def test_uninstall_from_another_checkout_leaves_the_widget_checkout(self):
        self.make_checkout(self.plugin)
        before = (self.plugin / "plugin/AskOmar.qml").read_bytes()

        result = self.run_script("uninstall.sh")

        self.assertEqual((self.plugin / "plugin/AskOmar.qml").read_bytes(), before)
        self.assertTrue((self.plugin / "manifest.json").is_file())
        self.assertIn("Leaving the widget checkout in place", result.stderr)

    def test_foreign_launchers_block_install_and_survive_uninstall(self):
        for name in ("ask-omar", "ask-omar-open", "ask-omar-capture"):
            with self.subTest(name=name):
                self.reset_home()
                launcher = self.home / ".local/bin" / name
                launcher.parent.mkdir(parents=True)
                launcher.write_text("#!/bin/sh\necho not-ours\n")
                result = self.run_script("install.sh", "--backend-only", success=False)
                self.assertIn("did not install", result.stderr)
                self.assertEqual(launcher.read_text(), "#!/bin/sh\necho not-ours\n")

                self.run_script("uninstall.sh", "--backend-only")
                self.assertEqual(launcher.read_text(), "#!/bin/sh\necho not-ours\n")

    def test_exact_legacy_launchers_upgrade_to_marked_sources(self):
        for release in ("v0.1.0", REVIEWED_COMMIT):
            with self.subTest(release=release):
                self.reset_home()
                bin_home = self.home / ".local/bin"
                bin_home.mkdir(parents=True)
                (bin_home / "ask-omar").write_text(
                    "#!/usr/bin/env bash\n"
                    "set -euo pipefail\n"
                    "DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}\n"
                    'export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:/usr/local/bin:/usr/bin${PATH:+:$PATH}"\n'
                    'export PYTHONPATH="$DATA_HOME/ask-omar/service${PYTHONPATH:+:$PYTHONPATH}"\n'
                    'exec python -m ask_omar "$@"\n'
                )
                (bin_home / "ask-omar-open").write_text(
                    "#!/usr/bin/env bash\n"
                    "set -euo pipefail\n"
                    "systemctl --user start ask-omar.service\n"
                    'exec omarchy-shell ask-omar "${1:-open}"\n'
                )
                legacy_capture = subprocess.check_output(
                    ["git", "show", f"{release}:scripts/capture.sh"], cwd=ROOT
                )
                (bin_home / "ask-omar-capture").write_bytes(legacy_capture)

                self.run_script("install.sh", "--backend-only")

                for name in ("ask-omar", "ask-omar-open", "ask-omar-capture"):
                    self.assertIn("# Installed by Ask Omar", (bin_home / name).read_text())
                cli = (bin_home / "ask-omar").read_text()
                self.assertNotIn("exec python ", cli)
                python = Path(shutil.which("python", path=self.env["PATH"])).resolve()
                self.assertIn(str(python), cli)

    def test_config_symlink_is_preserved_without_chmod(self):
        target = Path(self.sandbox.name) / "external-config.toml"
        target.write_text("external config\n")
        target.chmod(0o644)
        config = self.config / "ask-omar/config.toml"
        config.parent.mkdir(parents=True)
        config.symlink_to(target)

        self.run_script("install.sh", "--backend-only")

        self.assertTrue(config.is_symlink())
        self.assertEqual(target.read_text(), "external config\n")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_symlinked_bin_parent_is_supported(self):
        external_bin = Path(self.sandbox.name) / "external-bin"
        external_bin.mkdir()
        local = self.home / ".local"
        local.mkdir()
        (local / "bin").symlink_to(external_bin, target_is_directory=True)

        self.run_script("install.sh", "--backend-only")

        self.assertTrue((external_bin / "ask-omar").is_file())
        self.assertTrue((external_bin / "ask-omar-open").is_file())

    def test_untracked_package_files_and_caches_are_not_installed(self):
        checkout = Path(self.sandbox.name) / "checkout"
        self.make_checkout(checkout)
        package = checkout / "service/ask_omar"
        (package / "untracked-secret.txt").write_text("do not install\n")
        cache = package / "__pycache__"
        cache.mkdir()
        (cache / "cached.pyc").write_bytes(b"cache")

        self.run_script("install.sh", "--backend-only", root=checkout)

        installed = self.data / "ask-omar/service/ask_omar"
        self.assertFalse((installed / "untracked-secret.txt").exists())
        self.assertFalse((installed / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
