from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from typing import Any

from . import __version__
from .config import Config, runtime_socket
from .server import serve


def request(payload: dict[str, Any], start_service: bool = True) -> dict[str, Any]:
    path = runtime_socket()
    last_error: OSError | None = None
    for attempt in range(2):
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        except OSError as error:
            last_error = error
            break
        with client:
            try:
                client.settimeout(5)
                client.connect(str(path))
            except OSError as error:
                last_error = error
                if attempt == 0 and start_service:
                    subprocess.run(
                        ["systemctl", "--user", "start", "ask-omar.service"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    time.sleep(0.35)
                    continue
                break
            try:
                # Pi bounds its turn and each approval, but several approvals can
                # outlast any fixed socket read timeout. Stop uses a separate request.
                client.settimeout(None if payload.get("type") == "query" else 360)
                client.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
                chunks: list[bytes] = []
                while True:
                    chunk = client.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    if b"\n" in chunk:
                        break
                return json.loads(b"".join(chunks).split(b"\n", 1)[0].decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                return {"ok": False, "error": f"Ask Omar returned invalid data: {error}"}
            except OSError as error:
                return {
                    "ok": False,
                    "error": (
                        "Ask Omar lost the service response. The request was not retried "
                        f"because it may already be running: {error}"
                    ),
                }
    return {"ok": False, "error": f"Ask Omar service is unavailable: {last_error}"}


def print_json(value: dict[str, Any]) -> int:
    print(json.dumps(value, ensure_ascii=False))
    return 0 if value.get("ok") else 1


def print_setup(value: dict[str, Any]) -> int:
    """Report readiness as next steps rather than the raw health payload."""
    if not value.get("ok"):
        print(value.get("error", "Ask Omar could not be reached."))
        print("Check the service with: systemctl --user status ask-omar.service")
        return 1

    raw_agent = value.get("agent")
    agent = raw_agent if isinstance(raw_agent, dict) else {}
    status = agent.get("status")
    provider = value.get("provider") or "your provider"
    print(f"Ask Omar {__version__}")
    print(
        f"Provider {provider}, model {value.get('model') or 'unset'}, "
        f"reasoning {value.get('thinking') or 'unset'}."
    )
    print("Settings live in ~/.config/ask-omar/config.toml.")
    print()

    if status == "ready":
        print(f"Pi is installed and {provider} credentials are available locally.")
        print("That does not guarantee the provider is online, but setup is done.")
        print("Open Ask Omar with: omarchy-shell ask-omar open")
        return 0
    if status == "missing":
        print("Pi is not installed. Ask Omar uses it to run AI requests.")
        print("1. Install Pi from https://pi.dev")
        print("2. Run pi, enter /login, and complete sign-in")
        print("3. Run 'ask-omar setup' again")
        print()
        print("Scratchpad and capture work without Pi.")
        return 1
    if status == "configure":
        print("Pi is installed, but Ask Omar has no provider/model yet.")
        print("1. Sign in with pi /login if you have not already")
        print("2. Open Ask Omar Settings and pick a model, or run setup again")
        print("   so Omar can copy Pi's defaults")
        return 1
    if status == "signin":
        print(f"Pi is installed but has no {provider} credentials.")
        print(f"1. In a terminal, run pi, enter /login, and sign in for {provider}")
        print("2. Run 'ask-omar setup' again")
        print()
        print("Sign in inside Pi. Never paste passwords, tokens, or codes into Ask Omar.")
        return 1

    print(agent.get("message", "Ask Omar could not check Pi."))
    print("Run 'ask-omar health' for the full status.")
    return 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="ask-omar", description="Ask Omar desktop assistant")
    result.add_argument("--version", action="version", version=f"Ask Omar {__version__}")
    commands = result.add_subparsers(dest="command", required=True)
    query = commands.add_parser("query", help="Ask a question or request an action")
    query.add_argument(
        "--stdin",
        action="store_true",
        help="Read the query from stdin instead of argv (preferred for private text)",
    )
    query.add_argument("text", nargs="*")
    action = commands.add_parser("action", help="Run an approved action")
    action.add_argument("id")
    commands.add_parser("stop", help="Stop the active Pi request")
    commands.add_parser("activity", help="Show the current Pi activity")
    confirm = commands.add_parser("confirm", help="Respond to a pending command confirmation")
    confirm.add_argument("id", help="Pending confirmation ID")
    confirm.add_argument("response", help="Approval option returned by the confirmation panel")
    commands.add_parser("history", help="Show recent local history")
    commands.add_parser("clear-history", help="Clear recent local history")
    draft = commands.add_parser("draft", help="Save an unsent draft")
    draft.add_argument(
        "--stdin",
        action="store_true",
        help="Read the draft from stdin instead of argv (preferred for private text)",
    )
    draft.add_argument("text", nargs="?", default="")
    commands.add_parser("get-draft", help="Read the current unsent draft")
    scratchpad = commands.add_parser("scratchpad", help="Save scratchpad text")
    scratchpad.add_argument(
        "--stdin",
        action="store_true",
        help="Read scratchpad text from stdin instead of argv",
    )
    scratchpad.add_argument("text", nargs="?", default="")
    commands.add_parser("get-scratchpad", help="Read scratchpad text")
    commands.add_parser("clear-scratchpad", help="Clear scratchpad text")
    notes = commands.add_parser("scratchpad-notes", help="Read scratchpad notes")
    save_notes = commands.add_parser("scratchpad-notes-save", help="Save scratchpad notes")
    save_notes.add_argument(
        "--stdin",
        action="store_true",
        help="Read the JSON notes list from stdin instead of argv",
    )
    save_notes.add_argument("notes", nargs="?", default="")
    attach = commands.add_parser("scratchpad-attach", help="Attach a screenshot to scratchpad")
    attach.add_argument("path")
    commands.add_parser("new-conversation", help="Reset the in-memory agent conversation")
    commands.add_parser("health", help="Check service and agent readiness")
    commands.add_parser("setup", help="Check Pi and report the remaining setup steps")
    commands.add_parser("models", help="List Pi models available for Ask Omar")
    set_agent = commands.add_parser("set-agent", help="Change Ask Omar provider, model, or reasoning")
    set_agent.add_argument("--provider")
    set_agent.add_argument("--model")
    set_agent.add_argument("--thinking")
    set_access = commands.add_parser("set-access", help="Change model-generated command access")
    set_access.add_argument("mode", choices=("ask", "off", "full"))
    commands.add_parser("serve", help="Run the local service")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "serve":
        serve()
        return 0
    if args.command == "query":
        if args.stdin:
            text = sys.stdin.read()
        else:
            text = " ".join(args.text)
        if not str(text).strip():
            return print_json({"ok": False, "error": "Ask Omar needs a question or request."})
        return print_json(request({"type": "query", "query": text}))
    if args.command == "action":
        return print_json(request({"type": "action", "id": args.id}))
    if args.command == "stop":
        return print_json(request({"type": "stop"}))
    if args.command == "activity":
        return print_json(request({"type": "activity"}))
    if args.command == "confirm":
        return print_json(request({"type": "confirm", "id": args.id, "response": args.response}))
    if args.command == "history":
        return print_json(request({"type": "history"}))
    if args.command == "clear-history":
        return print_json(request({"type": "clear_history"}))
    if args.command == "draft":
        draft = sys.stdin.read() if args.stdin else args.text
        return print_json(request({"type": "draft_set", "draft": draft}))
    if args.command == "get-draft":
        return print_json(request({"type": "draft_get"}))
    if args.command == "scratchpad":
        text = sys.stdin.read() if args.stdin else args.text
        return print_json(request({"type": "scratchpad_set", "text": text}))
    if args.command == "get-scratchpad":
        return print_json(request({"type": "scratchpad_get"}))
    if args.command == "clear-scratchpad":
        return print_json(request({"type": "scratchpad_clear"}))
    if args.command == "scratchpad-notes":
        return print_json(request({"type": "scratchpad_notes"}))
    if args.command == "scratchpad-notes-save":
        raw = sys.stdin.read() if args.stdin else args.notes
        try:
            notes = json.loads(raw)
        except json.JSONDecodeError:
            return print_json({"ok": False, "error": "Scratchpad notes must be JSON."})
        return print_json(request({"type": "scratchpad_notes_save", "notes": notes}))
    if args.command == "scratchpad-attach":
        return print_json(request({"type": "scratchpad_attach", "path": args.path}))
    if args.command == "new-conversation":
        return print_json(request({"type": "new_conversation"}))
    if args.command == "health":
        return print_json(request({"type": "health"}))
    if args.command == "setup":
        return print_setup(request({"type": "health"}))
    if args.command == "models":
        return print_json(request({"type": "models"}))
    if args.command == "set-agent":
        if not args.provider and not args.model and not args.thinking:
            return print_json(
                {"ok": False, "error": "Pass at least one of --provider, --model, or --thinking."}
            )
        payload: dict[str, Any] = {"type": "set_agent"}
        if args.provider:
            payload["provider"] = args.provider
        if args.model:
            payload["model"] = args.model
        if args.thinking:
            payload["thinking"] = args.thinking
        return print_json(request(payload))
    if args.command == "set-access":
        return print_json(request({"type": "set_system_access", "mode": args.mode}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
