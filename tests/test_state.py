import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ask_omar.state import StateStore


class StateStoreTests(unittest.TestCase):
    def test_history_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json", history_limit=2)
            store.add_history("one", "1", "help")
            store.add_history("two", "2", "help")
            store.add_history("three", "3", "help")
            self.assertEqual([item["query"] for item in store.history()], ["three", "two"])

    def test_history_entry_text_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json")
            store.add_history("q" * 3000, "a" * 60000, "k" * 100)
            entry = store.history()[0]
            self.assertEqual(len(entry["query"]), store.max_history_query_chars)
            self.assertEqual(len(entry["response"]), store.max_history_response_chars)
            self.assertEqual(len(entry["kind"]), 50)

    def test_oversized_state_file_is_not_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            with patch.object(StateStore, "max_state_bytes", 10):
                path.write_text('{"version":1,"history":[{"query":"should not load"}]}')
                self.assertEqual(StateStore(path).history(), [])

    def test_byte_limit_keeps_recent_history_and_preserves_notes_and_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            with patch.object(StateStore, "max_state_bytes", 16000):
                store = StateStore(path, history_limit=100)
                notes = ["🙂" * 1000]
                store.save_scratchpad_notes(notes)
                store.set_draft("An unsent draft")
                for index in range(6):
                    store.add_history(str(index), "🙂" * 1000, "assistant")
                self.assertLessEqual(path.stat().st_size, store.max_state_bytes)
                loaded = StateStore(path, history_limit=100)
                self.assertEqual(loaded.scratchpad_notes(), notes)
                self.assertEqual(loaded.draft(), "An unsent draft")
                self.assertEqual(loaded.history(), store.history())
                self.assertEqual(loaded.history()[0]["query"], "5")
                self.assertLess(len(loaded.history()), 6)

    def test_unfit_state_does_not_replace_last_saved_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            store.save_scratchpad_notes(["Keep this note"])
            before = path.read_bytes()
            with patch.object(StateStore, "max_state_bytes", 100):
                with self.assertRaises(ValueError):
                    store.save()
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(StateStore(path).scratchpad_notes(), ["Keep this note"])

    def test_state_directory_and_file_are_private(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "ask-omar"
            state_dir.mkdir(mode=0o755)
            path = state_dir / "state.json"
            StateStore(path).set_draft("private")
            self.assertEqual(state_dir.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_draft_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            StateStore(path).set_draft("unfinished thought")
            self.assertEqual(StateStore(path).draft(), "unfinished thought")

    def test_expired_draft_is_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            store.data["draft"] = {"text": "old", "at": 1}
            store.save()
            self.assertEqual(StateStore(path).draft(), "")

    def test_scratchpad_survives_reload_and_rejects_oversize_without_changing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            store.set_scratchpad("x" * store.max_scratchpad_chars)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                store.set_scratchpad("x" * (store.max_scratchpad_chars + 1))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(StateStore(path).scratchpad(), "x" * store.max_scratchpad_chars)

    def test_oversized_draft_and_notes_leave_saved_state_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            store.set_draft("d" * store.max_draft_chars)
            store.save_scratchpad_notes(["n" * store.max_scratchpad_chars])
            before = path.read_bytes()
            for operation in (
                lambda: store.set_draft("d" * (store.max_draft_chars + 1)),
                lambda: store.save_scratchpad_notes([""] * (store.max_scratchpad_notes + 1)),
                lambda: store.save_scratchpad_notes(["n" * (store.max_scratchpad_chars + 1)]),
                lambda: store.save_scratchpad_notes([42]),
            ):
                with self.assertRaises(ValueError):
                    operation()
                self.assertEqual(path.read_bytes(), before)

    def test_zero_history_limit_discards_loaded_and_new_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            StateStore(path).add_history("old", "answer", "assistant")
            store = StateStore(path, history_limit=0)
            self.assertEqual(store.history(), [])
            store.add_history("new", "answer", "assistant")
            store.set_draft("still saved")
            self.assertEqual(StateStore(path).history(), [])

    def test_malformed_state_collections_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('{"version":1,"events":"bad","history":{"bad":true},"draft":{"text":"bad","at":"bad"}}')
            store = StateStore(path)
            self.assertEqual(store.history(), [])
            self.assertEqual(store.draft(), "")
            store.set_draft("example")
            self.assertEqual(StateStore(path).draft(), "example")

    def assert_set_aside(self, path: Path, contents: bytes) -> StateStore:
        path.write_bytes(contents)
        store = StateStore(path)
        kept = list(path.parent.glob("state.json.unreadable-*"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_bytes(), contents)
        self.assertEqual(kept[0].stat().st_mode & 0o777, 0o600)
        self.assertIn(kept[0].name, store.warning)
        self.assertEqual(store.scratchpad_notes(), [""])
        # New saves write a fresh file and never touch the kept copy.
        store.save_scratchpad_notes(["new note"])
        self.assertEqual(kept[0].read_bytes(), contents)
        self.assertEqual(StateStore(path).scratchpad_notes(), ["new note"])
        return store

    def test_unreadable_json_is_kept_instead_of_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_set_aside(Path(directory) / "state.json", b'{"version": 1, "scratchpad_notes": ["half')

    def test_repeated_recovery_never_replaces_an_earlier_kept_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            with patch("ask_omar.state.time.strftime", return_value="20260101-000000"):
                for contents in (b"first broken", b"second broken", b"third broken"):
                    path.write_bytes(contents)
                    StateStore(path)
            kept = sorted(p.read_bytes() for p in Path(directory).glob("state.json.unreadable-*"))
            self.assertEqual(kept, [b"first broken", b"second broken", b"third broken"])
            self.assertFalse(path.exists())

    def test_invalid_utf8_is_kept_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_set_aside(Path(directory) / "state.json", b'{"version": 1, "draft": "\xff\xfe"}')

    def test_unknown_state_version_is_kept_instead_of_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_set_aside(Path(directory) / "state.json", b'{"version": 2, "scratchpad_notes": ["future"]}')

    def test_oversized_state_is_kept_instead_of_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            with patch.object(StateStore, "max_state_bytes", 400):
                self.assert_set_aside(path, b'{"version": 1, "scratchpad_notes": ["' + b"x" * 500 + b'"]}')

    def test_state_that_cannot_be_read_or_moved_blocks_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('{"version": 1, "scratchpad_notes": ["keep"]}')
            with patch.object(Path, "read_text", side_effect=PermissionError(13, "Permission denied")):
                store = StateStore(path)
            self.assertIn("could not read", store.warning)
            with self.assertRaises(ValueError):
                store.save_scratchpad_notes(["would overwrite"])
            store.add_history("question", "answer", "assistant")
            self.assertEqual(json.loads(path.read_text())["scratchpad_notes"], ["keep"])

    def test_readable_state_has_no_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            StateStore(path).save_scratchpad_notes(["fine"])
            self.assertEqual(StateStore(path).warning, "")
            self.assertEqual(list(Path(directory).glob("*.unreadable-*")), [])

    def test_scratchpad_can_be_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json")
            store.set_scratchpad("- Call Alex\n- /home/example/notes.md")
            store.clear_scratchpad()
            self.assertEqual(store.scratchpad(), "")

    def test_concurrent_draft_and_history_updates_do_not_raise(self):
        import threading

        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json")
            errors: list[BaseException] = []

            def writer(index: int) -> None:
                try:
                    for step in range(20):
                        store.set_draft(f"draft-{index}-{step}")
                        store.add_history(f"q-{index}-{step}", f"a-{index}-{step}", "help")
                except BaseException as error:  # noqa: BLE001 - collect any worker failure
                    errors.append(error)

            threads = [threading.Thread(target=writer, args=(index,)) for index in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertTrue(store.history())
            self.assertTrue(store.draft())


if __name__ == "__main__":
    unittest.main()
