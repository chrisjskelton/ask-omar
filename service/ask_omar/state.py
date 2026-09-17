from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class StateStore:
    max_state_bytes = 10 * 1024 * 1024
    max_history_query_chars = 2000
    max_history_response_chars = 50000

    def __init__(self, path: Path, history_limit: int = 10):
        self.path = path
        self.history_limit = history_limit
        self.data: dict[str, Any] = {"version": 1, "events": [], "history": []}
        self.load()

    def load(self) -> None:
        try:
            if self.path.stat().st_size > self.max_state_bytes:
                return
            raw = json.loads(self.path.read_text())
            if isinstance(raw, dict) and raw.get("version") == 1:
                self.data.update(raw)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        fd, temporary = tempfile.mkstemp(prefix="state.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def record_action(self, action_id: str) -> None:
        now = time.time()
        events = self.data.setdefault("events", [])
        events.append({"action": action_id, "at": now})
        cutoff = now - 90 * 86400
        self.data["events"] = [event for event in events if event.get("at", 0) >= cutoff][-1000:]
        self.save()

    def add_history(self, query: str, response: str, kind: str) -> None:
        history = self.data.setdefault("history", [])
        history.insert(0, {
            "query": query[: self.max_history_query_chars],
            "response": response[: self.max_history_response_chars],
            "kind": kind[:50],
            "at": time.time(),
        })
        self.data["history"] = history[: self.history_limit]
        self.save()

    def history(self) -> list[dict[str, Any]]:
        return list(self.data.get("history", []))[: self.history_limit]

    def clear_history(self) -> None:
        self.data["history"] = []
        self.save()

    def set_draft(self, text: str) -> None:
        value = text[:2000]
        self.data["draft"] = {"text": value, "at": time.time()} if value else None
        self.save()

    def draft(self, max_age_seconds: int = 86400) -> str:
        draft = self.data.get("draft")
        if not isinstance(draft, dict):
            return ""
        if time.time() - float(draft.get("at", 0)) > max_age_seconds:
            self.data["draft"] = None
            self.save()
            return ""
        return str(draft.get("text", ""))

    def set_scratchpad(self, text: str) -> None:
        self.data["scratchpad"] = {"text": text[:20000], "at": time.time()}
        self.save()

    def scratchpad(self) -> str:
        scratchpad = self.data.get("scratchpad")
        if not isinstance(scratchpad, dict):
            return ""
        return str(scratchpad.get("text", ""))

    def clear_scratchpad(self) -> None:
        self.data["scratchpad"] = {"text": "", "at": time.time()}
        self.save()

    def scratchpad_notes(self) -> list[str]:
        notes = self.data.get("scratchpad_notes")
        if isinstance(notes, list) and all(isinstance(note, str) for note in notes) and notes:
            return notes
        return [self.scratchpad()]

    def save_scratchpad_notes(self, notes: list[str]) -> list[str]:
        bounded = [str(note)[:20000] for note in notes[:20]] or [""]
        self.data["scratchpad_notes"] = bounded
        self.data["scratchpad"] = {"text": bounded[0], "at": time.time()}
        self.save()
        return bounded

    def score(self, action_id: str, base: float = 0.0) -> float:
        now = time.time()
        score = base
        for event in self.data.get("events", []):
            if event.get("action") != action_id:
                continue
            age_days = max(0.0, (now - float(event.get("at", now))) / 86400)
            score += 4.0 * math.exp(-age_days / 14.0)
        return score
