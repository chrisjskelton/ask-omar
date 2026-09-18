from __future__ import annotations

import json
import os
import shutil
import socketserver
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .actions import (
    action_by_id,
    discover_apps,
    launch,
    launch_url,
    open_url_request,
    web_search_request,
)
from .agent import AgentCancelled, AgentError, OMARCHY_CHEAT_SHEET, PiAgent
from .config import (
    THINKING_LEVELS,
    Config,
    default_config_path,
    parse_pi_list_models,
    read_pi_default_identity,
    runtime_socket,
    state_home,
    update_agent_settings,
)
from .state import StateStore


MAX_SCRATCHPAD_ATTACHMENT_BYTES = 25 * 1024 * 1024
SCRATCHPAD_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def scratchpad_image_kind(path: Path) -> str | None:
    """Return png/jpeg/webp when the file content matches, else None."""
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return None
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    return None


class AskOmar:
    def __init__(self, config: Config | None = None, config_path: Path | None = None):
        self.config_path = config_path or default_config_path()
        self.config = config or Config.load(self.config_path)
        self.state = StateStore(state_home() / "state.json", self.config.history_limit)
        self.agent = PiAgent(self.config) if self.config.backend == "pi" else None
        self.foreground_lock = threading.Lock()
        self.active_cancel_event: threading.Event | None = None
        self.active_lock = threading.Lock()

    @staticmethod
    def response(**values: Any) -> dict[str, Any]:
        return {"ok": True, **values}

    def perform(self, action_id: str, query: str | None = None) -> dict[str, Any]:
        action = action_by_id(action_id)
        if not action:
            return {"ok": False, "error": f"Action is unavailable: {action_id}"}
        try:
            launch(action)
        except OSError as error:
            return {"ok": False, "error": f"Could not run {action.label}: {error}"}
        self.state.record_action(action.id)
        self.state.add_history(query or action.label, action.description, "action")
        return self.response(
            kind="action",
            action=action.id,
            message=action.description,
            dismiss=action.dismiss,
        )

    def query(self, raw_query: str) -> dict[str, Any]:
        with self.foreground_lock:
            cancel_event = threading.Event()
            with self.active_lock:
                self.active_cancel_event = cancel_event
            try:
                return self._query(raw_query, cancel_event)
            finally:
                with self.active_lock:
                    if self.active_cancel_event is cancel_event:
                        self.active_cancel_event = None

    def _query(
        self,
        raw_query: str,
        cancel_event: threading.Event,
    ) -> dict[str, Any]:
        query = raw_query.strip()[:2000]
        if not query:
            return {"ok": False, "error": "Ask Omar needs a question or request."}
        if cancel_event.is_set():
            return self.stopped_response()

        url = open_url_request(query)
        if url:
            try:
                launch_url(url)
            except OSError as error:
                return {"ok": False, "error": f"Could not open the link: {error}"}
            message = "Opening the link in your browser."
            self.state.record_action("url.open")
            self.state.add_history(query, message, "action")
            return self.response(kind="action", action="url.open", message=message, dismiss=True)

        search_terms = web_search_request(query)
        if search_terms:
            search_url = "https://www.google.com/search?" + urlencode({"q": search_terms})
            try:
                launch_url(search_url)
            except OSError as error:
                return {"ok": False, "error": f"Could not run the Google search: {error}"}
            message = f"Searching Google for: {search_terms}"
            self.state.record_action("web.search")
            self.state.add_history(query, message, "action")
            return self.response(kind="action", action="web.search", message=message, dismiss=True)

        if not self.agent:
            return {"ok": False, "error": f"Unsupported agent backend: {self.config.backend}"}

        blocked = self.query_blocked_by_agent_readiness()
        if blocked is not None:
            return blocked

        prompt = self.agent_prompt(query)
        try:
            answer = self.agent.query(prompt, cancel_event=cancel_event)
        except AgentCancelled:
            stopped = self.stopped_response()
            self.state.add_history(query, stopped["message"], "stopped")
            return stopped
        except AgentError as error:
            if cancel_event.is_set():
                stopped = self.stopped_response()
                self.state.add_history(query, stopped["message"], "stopped")
                return stopped
            return {
                "ok": False,
                "error": self.friendly_error(str(error)),
                "error_code": error.code,
            }
        if cancel_event is not None and cancel_event.is_set():
            stopped = self.stopped_response()
            self.state.add_history(query, stopped["message"], "stopped")
            return stopped
        answer = answer.strip()
        if not answer:
            return {"ok": False, "error": "Omar could not produce an answer. Try rephrasing your request."}
        self.state.add_history(query, answer, "assistant")
        recap = self.tool_recap()
        return self.response(kind="assistant", message=answer, dismiss=False, recap=recap)

    def stopped_response(self) -> dict[str, Any]:
        return self.response(
            kind="stopped",
            message="Stopped. Anything Omar already ran has not been undone.",
            dismiss=False,
            stopped=True,
        )

    def query_blocked_by_agent_readiness(self) -> dict[str, Any] | None:
        """Fail fast when Pi is missing, unsigned-in, or unset instead of waiting on a hung prompt."""
        readiness = self.health()
        agent = readiness.get("agent") if isinstance(readiness.get("agent"), dict) else {}
        status = str(agent.get("status", ""))
        provider = str(readiness.get("provider") or self.config.provider or "your provider")
        if status == "missing":
            return {
                "ok": False,
                "error": self.friendly_error(
                    "Pi is not installed. Install it from https://pi.dev, then run: ask-omar setup"
                ),
                "error_code": str(agent.get("code") or "pi_missing"),
            }
        if status == "configure":
            return {
                "ok": False,
                "error": (
                    "Omar needs a provider and model. Open Ask Omar Settings, pick one from Pi's "
                    "list, or run 'ask-omar setup' after Pi is signed in."
                ),
                "error_code": str(agent.get("code") or "agent_unset"),
            }
        if status == "signin":
            return {
                "ok": False,
                "error": (
                    f"Omar needs {provider} connected in Pi. "
                    "In a terminal, run pi, enter /login, sign in, then try again. "
                    "Don't paste passwords, tokens, or codes into Ask Omar."
                ),
                "error_code": str(agent.get("code") or "pi_not_ready"),
            }
        return None

    @staticmethod
    def parse_pi_models(output: str) -> list[dict[str, str]]:
        models: list[dict[str, str]] = []
        lines = [line.rstrip() for line in output.splitlines() if line.strip()]
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            models.append(
                {
                    "provider": parts[0],
                    "model": parts[1],
                    "thinking": parts[4] if len(parts) > 4 else "",
                    "images": parts[5] if len(parts) > 5 else "",
                }
            )
        return models

    def seed_agent_defaults(self) -> bool:
        """Fill empty provider/model from Pi settings, else the first listed model."""
        if self.config.agent_identity_ready:
            return False
        if not shutil.which("pi"):
            return False

        provider, model = read_pi_default_identity()
        if not provider or not model:
            try:
                completed = subprocess.run(
                    ["pi", "--list-models"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                return False
            pairs = parse_pi_list_models(completed.stdout or completed.stderr or "")
            if not pairs:
                return False
            provider, model = pairs[0]

        path = self.config_path
        try:
            update_agent_settings(
                path,
                provider=provider,
                model=model,
                thinking=self.config.thinking or "low",
            )
        except ValueError:
            return False
        self.config = Config.load(path)
        if self.agent:
            self.agent.stop()
        self.agent = PiAgent(self.config) if self.config.backend == "pi" else None
        return True

    def list_models(self) -> dict[str, Any]:
        self.seed_agent_defaults()
        if not shutil.which("pi"):
            return self.response(
                kind="models",
                models=[],
                thinking_levels=list(THINKING_LEVELS),
                provider=self.config.provider,
                model=self.config.model,
                thinking=self.config.thinking,
                message="Pi is not installed, so Ask Omar cannot list models yet.",
            )
        try:
            completed = subprocess.run(
                ["pi", "--list-models"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return {
                "ok": False,
                "error": f"Ask Omar couldn't list Pi models: {error}",
                "error_code": "models_unavailable",
            }
        output = completed.stdout or completed.stderr or ""
        models = self.parse_pi_models(output)
        return self.response(
            kind="models",
            models=models,
            thinking_levels=list(THINKING_LEVELS),
            provider=self.config.provider,
            model=self.config.model,
            thinking=self.config.thinking,
            message="" if models else "Pi returned no models. Sign in with pi /login, then try again.",
        )

    def set_agent(
        self,
        provider: str | None = None,
        model: str | None = None,
        thinking: str | None = None,
    ) -> dict[str, Any]:
        next_provider = (provider or self.config.provider).strip()
        next_model = (model or self.config.model).strip()
        next_thinking = (thinking or self.config.thinking).strip()
        if not next_provider or not next_model or not next_thinking:
            return {"ok": False, "error": "Provider, model, and reasoning are required."}
        path = self.config_path
        try:
            update_agent_settings(
                path,
                provider=next_provider,
                model=next_model,
                thinking=next_thinking,
            )
        except ValueError as error:
            return {"ok": False, "error": str(error), "error_code": "invalid_agent_settings"}
        with self.foreground_lock:
            if self.agent:
                self.agent.stop()
            self.config = Config.load(path)
            self.agent = PiAgent(self.config) if self.config.backend == "pi" else None
        readiness = self.health()
        return self.response(
            kind="agent_settings",
            provider=self.config.provider,
            model=self.config.model,
            thinking=self.config.thinking,
            agent=readiness.get("agent"),
            message="AI settings saved. New requests use the updated model and reasoning.",
        )

    @staticmethod
    def friendly_error(message: str) -> str:
        """Wrap developer-toned agent errors with plain-language guidance."""
        lower = message.casefold()
        if "timed out" in lower:
            return "Omar is taking too long to respond. Try again, or rephrase your request."
        if "pi is not installed" in lower:
            return "Omar needs Pi. Install it from https://pi.dev, then run 'ask-omar setup' in a terminal."
        if "could not be reached" in lower:
            return "Omar could not reach Pi. Try restarting the Ask Omar service."
        if "stopped before answering" in lower:
            return "Pi stopped unexpectedly. Try asking again."
        if "did not receive an answer" in lower or "empty answer" in lower:
            return "Omar could not produce an answer. Try rephrasing your request."
        if "invalid data" in lower:
            return "Omar received unreadable data from Pi. Try asking again."
        if "rejected the request" in lower:
            return "Pi rejected the request. Check your provider settings in the Ask Omar config."
        return message

    def tool_recap(self) -> str:
        """Build a one-line summary of which tools Omar used."""
        if not self.agent or not self.agent.last_tools_used:
            return "No commands run."
        tools = self.agent.last_tools_used
        if len(tools) == 1:
            return f"Ran: {tools[0]}"
        return f"Ran: {' · '.join(tools)}"

    def agent_prompt(self, query: str) -> str:
        idle = self.config.conversation_idle_minutes
        idle_description = (
            f"after {idle} minutes without an AI response"
            if idle > 0
            else "only when New is chosen, the service restarts, or the agent fails"
        )
        product_context = (
            "Ask Omar conversation behavior: follow-up questions share one in-memory Pi conversation. "
            f"A fresh conversation starts {idle_description}. The New control resets it immediately. "
            f"The local Past answers view retains the newest {self.config.history_limit} requests and responses "
            "across conversations and service restarts; opening a saved answer is view-only and does not "
            "restore that old Pi context. "
            f"The authoritative runtime settings are provider={self.config.provider}, "
            f"model={self.config.model}, reasoning={self.config.thinking}."
        )
        return (
            f"User request: {query}\n\n"
            f"Ask Omar product context:\n{product_context}\n\n"
            "The user can use separate convenience buttons for frequent actions. "
            "Those buttons are not a limit on your capabilities.\n\n"
            f"{OMARCHY_CHEAT_SHEET}"
        )

    def health(self) -> dict[str, Any]:
        self.seed_agent_defaults()
        if self.config.backend != "pi":
            agent_ready: dict[str, Any] = {
                "status": "error",
                "code": "unsupported_backend",
                "message": f"Ask Omar does not support the {self.config.backend} backend.",
            }
        elif not shutil.which("pi"):
            agent_ready = {
                "status": "missing",
                "code": "pi_missing",
                "message": "Ask Omar couldn't find Pi, the separate app that runs its AI requests.",
            }
        elif not self.config.agent_identity_ready:
            agent_ready = {
                "status": "configure",
                "code": "agent_unset",
                "message": (
                    "Choose a provider and model in Ask Omar Settings. "
                    "Omar can also pick Pi's defaults once Pi is signed in."
                ),
            }
        else:
            try:
                check = subprocess.run(
                    [
                        "pi", "auth", "check",
                        "--provider", self.config.provider,
                        "--json", "--no-refresh",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                raw = json.loads(check.stdout)
                pi_status = str(raw.get("status", ""))
                if pi_status == "ready":
                    agent_ready = {
                        "status": "ready",
                        "code": "credentials_ready",
                        "message": "Pi found and provider credentials are available locally.",
                        "auth_type": str(raw.get("authType", "")),
                    }
                elif pi_status in ("not_ready", "invalid"):
                    agent_ready = {
                        "status": "signin",
                        "code": f"pi_{pi_status}",
                        "message": f"Open Pi and connect {self.config.provider} before sending AI requests.",
                    }
                else:
                    agent_ready = {
                        "status": "error",
                        "code": "pi_check_failed",
                        "message": "Ask Omar couldn't verify Pi authentication.",
                    }
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, AttributeError):
                agent_ready = {
                    "status": "error",
                    "code": "pi_check_failed",
                    "message": "Ask Omar couldn't check Pi authentication.",
                }
        return self.response(
            kind="health",
            backend=self.config.backend,
            provider=self.config.provider,
            model=self.config.model,
            thinking=self.config.thinking,
            agent=agent_ready,
            conversation={
                "storage": "memory",
                "idle_timeout_minutes": self.config.conversation_idle_minutes,
                "history_limit": self.config.history_limit,
            },
            apps=len(discover_apps()),
        )

    def activity(self) -> dict[str, Any]:
        if not self.agent:
            return self.response(kind="activity", active=False, message="No agent is configured.")
        current = self.agent.activity()
        confirmation = self.agent.confirmation()
        return self.response(
            kind="activity",
            active=bool(current.get("active")),
            message=str(current.get("message", "Working…")),
            confirmation=confirmation,
        )

    def attach_scratchpad_screenshot(self, source: str) -> dict[str, Any]:
        try:
            candidate = Path(source).expanduser()
        except (OSError, RuntimeError):
            return {"ok": False, "error": "Ask Omar could not find that screenshot."}
        # Refuse symlink hops before resolve so a same-UID confused deputy cannot
        # copy an arbitrary secret path that happens to end in .png.
        try:
            if candidate.is_symlink() or any(part.is_symlink() for part in candidate.parents):
                return {"ok": False, "error": "Ask Omar will not follow a screenshot symlink."}
            image = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            return {"ok": False, "error": "Ask Omar could not find that screenshot."}
        if not image.is_file():
            return {"ok": False, "error": "Ask Omar could not attach that screenshot."}
        if image.suffix.casefold() not in SCRATCHPAD_IMAGE_SUFFIXES:
            return {"ok": False, "error": "Ask Omar can only preview PNG, JPEG, or WebP screenshots."}
        if scratchpad_image_kind(image) is None:
            return {"ok": False, "error": "Ask Omar can only preview PNG, JPEG, or WebP screenshots."}
        try:
            if image.stat().st_size > MAX_SCRATCHPAD_ATTACHMENT_BYTES:
                return {"ok": False, "error": "That screenshot is too large to attach."}
        except OSError:
            return {"ok": False, "error": "Ask Omar could not read that screenshot."}
        attachments = state_home() / "scratchpad" / "attachments"
        attachments.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(attachments, 0o700)
        suffix = image.suffix.casefold()
        destination = attachments / f"screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}{suffix}"
        try:
            shutil.copy2(image, destination)
            os.chmod(destination, 0o600)
        except OSError as error:
            return {"ok": False, "error": f"Ask Omar could not save the screenshot: {error}"}
        return self.response(
            kind="scratchpad_attachment",
            markdown=f"![Screenshot](<{destination.as_uri()}>)",
        )

    def stop(self) -> dict[str, Any]:
        with self.active_lock:
            cancel_event = self.active_cancel_event
        if cancel_event is None:
            return self.stopped_response()
        cancel_event.set()
        if self.agent:
            self.agent.deny_pending_confirmation()
            self.agent.abort()
        return self.response(kind="stopping", message="Stopping…", status="stopping")

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        request_type = request.get("type")
        if request_type == "stop":
            return self.stop()
        if request_type == "activity":
            return self.activity()
        if request_type == "confirm":
            if self.agent:
                accepted = self.agent.respond_confirmation(
                    str(request.get("id", "")),
                    str(request.get("response", "")),
                )
                if accepted:
                    return self.response(kind="confirmed")
                return {
                    "ok": False,
                    "error": "That approval request is no longer pending.",
                    "error_code": "stale_confirmation",
                }
            return {"ok": False, "error": "No agent is configured."}
        if request_type == "query":
            return self.query(str(request.get("query", "")))
        if request_type == "action":
            with self.foreground_lock:
                return self.perform(str(request.get("id", "")))
        if request_type == "history":
            return self.response(kind="history", history=self.state.history())
        if request_type == "clear_history":
            self.state.clear_history()
            return self.response(kind="history", history=[])
        if request_type == "draft_get":
            return self.response(kind="draft", draft=self.state.draft())
        if request_type == "draft_set":
            self.state.set_draft(str(request.get("draft", "")))
            return self.response(kind="draft", draft=self.state.draft())
        if request_type == "scratchpad_get":
            return self.response(kind="scratchpad", text=self.state.scratchpad())
        if request_type == "scratchpad_set":
            self.state.set_scratchpad(str(request.get("text", "")))
            return self.response(kind="scratchpad", text=self.state.scratchpad())
        if request_type == "scratchpad_clear":
            self.state.clear_scratchpad()
            return self.response(kind="scratchpad", text="")
        if request_type == "scratchpad_attach":
            return self.attach_scratchpad_screenshot(str(request.get("path", "")))
        if request_type == "scratchpad_notes":
            return self.response(kind="scratchpad_notes", notes=self.state.scratchpad_notes())
        if request_type == "scratchpad_notes_save":
            notes = request.get("notes", [])
            if not isinstance(notes, list):
                return {"ok": False, "error": "Scratchpad notes must be a list."}
            return self.response(kind="scratchpad_notes", notes=self.state.save_scratchpad_notes(notes))
        if request_type == "new_conversation":
            with self.foreground_lock:
                if self.agent:
                    self.agent.stop()
            return self.response(kind="conversation", message="Started a new conversation.")
        if request_type == "health":
            return self.health()
        if request_type == "models":
            return self.list_models()
        if request_type == "set_agent":
            return self.set_agent(
                provider=str(request.get("provider", "") or "") or None,
                model=str(request.get("model", "") or "") or None,
                thinking=str(request.get("thinking", "") or "") or None,
            )
        return {"ok": False, "error": f"Unknown request type: {request_type}"}

    def close(self) -> None:
        with self.active_lock:
            if self.active_cancel_event:
                self.active_cancel_event.set()
        if self.agent:
            self.agent.stop()


class RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(1_000_000)
        if not raw:
            return
        try:
            request = json.loads(raw.decode("utf-8"))
            response = self.server.omar.handle(request)  # type: ignore[attr-defined]
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            response = {"ok": False, "error": f"Invalid request: {error}"}
        except Exception as error:  # Keep the desktop surface responsive on unexpected failures.
            response = {"ok": False, "error": f"Ask Omar failed: {error}"}
        self.wfile.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))


class OmarServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, socket_path: Path, omar: AskOmar):
        self.omar = omar
        previous_umask = os.umask(0o177)
        try:
            super().__init__(str(socket_path), RequestHandler)
        finally:
            os.umask(previous_umask)


def serve() -> None:
    path = runtime_socket()
    # XDG_RUNTIME_DIR is already private; only force 0700 on Ask Omar's /tmp fallback.
    if path.parent.name.startswith("ask-omar-"):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    omar = AskOmar()
    server = OmarServer(path, omar)
    os.chmod(path, 0o600)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        omar.close()
        try:
            path.unlink()
        except FileNotFoundError:
            pass
