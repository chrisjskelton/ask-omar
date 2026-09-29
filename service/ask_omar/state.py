from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


class StateStore:
    max_state_bytes = 10 * 1024 * 1024
    max_query_chars = 2000
    max_draft_chars = 2000
    max_scratchpad_chars = 20000
    max_scratchpad_notes = 20
    max_history_query_chars = 2000
    max_history_response_chars = 50000

    def __init__(self, path: Path, history_limit: int = 10):
        self.path = path
        self.history_limit = history_limit
        self.data: dict[str, Any] = {"version": 1, "history": []}
        self.warning = ""
        self._save_block = ""
        self._lock = threading.RLock()
        self.load()

    def _set_aside(self, problem: str) -> None:
        """Keep an unusable state file instead of overwriting it with empty data."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        try:
            # Link under a new name, then drop the original. os.link never
            # replaces an existing file, so an earlier kept copy is never lost.
            for attempt in range(1000):
                suffix = f"-{attempt}" if attempt else ""
                kept = self.path.with_name(f"{self.path.name}.unreadable-{stamp}{suffix}")
                try:
                    os.link(self.path, kept)
                    break
                except FileExistsError:
                    continue
            else:
                raise FileExistsError(f"too many kept copies named {kept.name}")
            os.unlink(self.path)
            os.chmod(kept, 0o600)
        except OSError as error:
            self._block_saves(
                f"Ask Omar's saved notes file {problem} and could not be moved aside "
                f"({error.strerror or error}). Nothing was overwritten."
            )
            return
        self.warning = (
            f"Ask Omar's saved notes file {problem}. It was kept as {kept.name} "
            "and Ask Omar started with empty notes and history."
        )

    def _block_saves(self, message: str) -> None:
        self.warning = message
        self._save_block = message

    def load(self) -> None:
        with self._lock:
            raw: Any = None
            try:
                if self.path.stat().st_size > self.max_state_bytes:
                    self._set_aside("is larger than Ask Omar's storage limit")
                    return
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                pass
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._set_aside("could not be read")
                return
            except OSError as error:
                self._block_saves(f"Ask Omar could not read its saved notes ({error.strerror or error}).")
                return
            if raw is not None and not (isinstance(raw, dict) and raw.get("version") == 1):
                self._set_aside("is in a format this version does not recognise")
                return
            if isinstance(raw, dict):
                history = raw.get("history")
                if isinstance(history, list):
                    self.data["history"] = [
                        item for item in history
                        if isinstance(item, dict)
                        and all(isinstance(item.get(field), str) for field in ("query", "response", "kind"))
                    ]
                for key in ("draft", "scratchpad"):
                    value = raw.get(key)
                    if value is None or (
                        isinstance(value, dict)
                        and isinstance(value.get("text"), str)
                        and isinstance(value.get("at"), (int, float))
                    ):
                        self.data[key] = value
                notes = raw.get("scratchpad_notes")
                if isinstance(notes, list) and all(isinstance(note, str) for note in notes):
                    self.data["scratchpad_notes"] = notes[: self.max_scratchpad_notes]
            if self.history_limit <= 0:
                had_history = bool(self.data["history"])
                self.data["history"] = []
                if had_history:
                    self._save_unlocked()
            else:
                self.data["history"] = self.data["history"][: self.history_limit]

    def save(self) -> None:
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self) -> None:
        if self._save_block:
            raise ValueError(self._save_block)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        # Use the same byte ceiling on save and load. Large multibyte answers
        # must not make the next restart discard notes and drafts as oversized.
        payload = dict(self.data)

        def encode() -> bytes:
            return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

        encoded = encode()
        if len(encoded) > self.max_state_bytes:
            history = payload.get("history", [])
            low, high = 0, len(history)
            payload["history"] = []
            encoded = encode()
            if len(encoded) > self.max_state_bytes:
                raise ValueError("Saved state exceeds its storage limit; existing saved data was not changed.")
            # Keep the largest prefix of newest answers that fits. Notes and
            # drafts are never removed to make room for answer history.
            while low < high:
                middle = (low + high + 1) // 2
                payload["history"] = history[:middle]
                candidate = encode()
                if len(candidate) <= self.max_state_bytes:
                    low, encoded = middle, candidate
                else:
                    high = middle - 1
            payload["history"] = history[:low]
        fd, temporary = tempfile.mkstemp(prefix="state.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
            self.data["history"] = payload.get("history", [])
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def add_history(self, query: str, response: str, kind: str) -> None:
        with self._lock:
            # Answer history is optional. When saving is blocked, keep the
            # answer flowing instead of failing the request.
            if self.history_limit <= 0 or self._save_block:
                return
            history = self.data.setdefault("history", [])
            history.insert(0, {
                "query": query[: self.max_history_query_chars],
                "response": response[: self.max_history_response_chars],
                "kind": kind[:50],
                "at": time.time(),
            })
            self.data["history"] = history[: self.history_limit]
            self._save_unlocked()

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            if self.history_limit <= 0:
                return []
            return list(self.data.get("history", []))[: self.history_limit]

    def clear_history(self) -> None:
        with self._lock:
            self.data["history"] = []
            self._save_unlocked()

    def set_draft(self, text: str) -> None:
        with self._lock:
            if len(text) > self.max_draft_chars:
                raise ValueError(f"Draft exceeds {self.max_draft_chars} characters.")
            value = text
            self.data["draft"] = {"text": value, "at": time.time()} if value else None
            self._save_unlocked()

    def draft(self, max_age_seconds: int = 86400) -> str:
        with self._lock:
            draft = self.data.get("draft")
            if not isinstance(draft, dict):
                return ""
            if time.time() - float(draft.get("at", 0)) > max_age_seconds:
                self.data["draft"] = None
                self._save_unlocked()
                return ""
            return str(draft.get("text", ""))

    def set_scratchpad(self, text: str) -> None:
        with self._lock:
            if len(text) > self.max_scratchpad_chars:
                raise ValueError(f"Scratchpad exceeds {self.max_scratchpad_chars} characters.")
            self.data["scratchpad"] = {"text": text, "at": time.time()}
            self._save_unlocked()

    def scratchpad(self) -> str:
        with self._lock:
            scratchpad = self.data.get("scratchpad")
            if not isinstance(scratchpad, dict):
                return ""
            return str(scratchpad.get("text", ""))

    def clear_scratchpad(self) -> None:
        with self._lock:
            self.data["scratchpad"] = {"text": "", "at": time.time()}
            self._save_unlocked()

    def scratchpad_notes(self) -> list[str]:
        with self._lock:
            notes = self.data.get("scratchpad_notes")
            if isinstance(notes, list) and all(isinstance(note, str) for note in notes) and notes:
                return list(notes)
            scratchpad = self.data.get("scratchpad")
            if isinstance(scratchpad, dict):
                return [str(scratchpad.get("text", ""))]
            return [""]

    def save_scratchpad_notes(self, notes: list[str]) -> list[str]:
        with self._lock:
            if len(notes) > self.max_scratchpad_notes:
                raise ValueError(f"Scratchpad allows at most {self.max_scratchpad_notes} notes.")
            if not all(isinstance(note, str) for note in notes):
                raise ValueError("Scratchpad notes must contain text only.")
            if any(len(note) > self.max_scratchpad_chars for note in notes):
                raise ValueError(f"Scratchpad note exceeds {self.max_scratchpad_chars} characters.")
            bounded = notes or [""]
            self.data["scratchpad_notes"] = bounded
            self.data["scratchpad"] = {"text": bounded[0], "at": time.time()}
            self._save_unlocked()
            return list(bounded)
