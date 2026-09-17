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

    def test_state_directory_and_file_are_private(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "ask-omar"
            state_dir.mkdir(mode=0o755)
            path = state_dir / "state.json"
            StateStore(path).record_action("capture.region")
            self.assertEqual(state_dir.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_recent_actions_raise_score(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json")
            before = store.score("capture.region", 5)
            store.record_action("capture.region")
            self.assertGreater(store.score("capture.region", 5), before)

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

    def test_scratchpad_survives_reload_and_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            StateStore(path).set_scratchpad("x" * 20001)
            self.assertEqual(StateStore(path).scratchpad(), "x" * 20000)

    def test_scratchpad_can_be_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "state.json")
            store.set_scratchpad("- Call Alex\n- /home/example/notes.md")
            store.clear_scratchpad()
            self.assertEqual(store.scratchpad(), "")


if __name__ == "__main__":
    unittest.main()
