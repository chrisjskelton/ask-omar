from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    description: str
    command: tuple[str, ...] | None
    dismiss: bool = True
    available_if: str | None = None

    def available(self) -> bool:
        return self.available_if is None or shutil.which(self.available_if) is not None


ACTIONS: tuple[Action, ...] = (
    Action(
        "capture.region",
        "Screenshot",
        "Drag around the area to capture; press Escape to cancel.",
        ("omarchy", "capture", "screenshot"),
    ),
    Action(
        "help.windows",
        "Arrange windows",
        "Use Super + Shift + arrow keys to swap tiled windows. Use Super + left-drag to move a floating window, Super + right-drag to resize it, and Super + T to toggle tiling.",
        None,
        False,
    ),
    Action(
        "app.herdr",
        "Herdr",
        "Opening Herdr.",
        ("omarchy", "launch", "terminal", "herdr"),
        True,
        "herdr",
    ),
    Action(
        "app.browser",
        "Browser",
        "Opening your default browser.",
        ("omarchy", "launch", "browser"),
    ),
    Action(
        "terminal.pi.continue",
        "Continue Pi",
        "Opening Pi in a terminal and continuing your last session.",
        ("omarchy-launch-terminal", "--app-id=dev.ask-omar.pi", "--title=Pi", "pi", "-c"),
        True,
        "pi",
    ),
    Action(
        "terminal.pi.new",
        "Open Pi",
        "Opening Pi in a terminal.",
        ("omarchy-launch-terminal", "--app-id=dev.ask-omar.pi", "--title=Pi", "pi"),
        True,
        "pi",
    ),
    Action(
        "app.1password",
        "1Password",
        "Opening 1Password Quick Access.",
        ("omarchy", "launch", "1password"),
        True,
        "1password",
    ),
    Action(
        "help.keybindings",
        "Keybindings",
        "Opening Omarchy's searchable keybindings.",
        ("omarchy", "menu", "keybindings"),
    ),
)


HTTP_URL_PATTERN = re.compile(r"(?<![a-z0-9])https?://[^\s<>\"']+", re.IGNORECASE)


def validate_http_url(candidate: str) -> str | None:
    candidate = candidate.strip()
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {'"', "'"}:
        candidate = candidate[1:-1]
    if any(character.isspace() or ord(character) < 32 for character in candidate):
        return None
    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not hostname:
        return None
    return candidate


def extract_http_urls(text: str) -> tuple[str, ...]:
    urls: list[str] = []
    for match in HTTP_URL_PATTERN.finditer(text):
        candidate = match.group(0).rstrip(".,!?;:)]}")
        validated = validate_http_url(candidate)
        if validated:
            urls.append(validated)
    return tuple(urls)


def open_url_request(text: str) -> str | None:
    """Return a URL only when it is the entire explicit request operand."""
    match = re.match(r"^\s*(?:open|visit|browse(?:\s+to)?|go\s+to)\s+(.+?)\s*$", text, re.IGNORECASE)
    if not match:
        return None
    operand = match.group(1).strip()
    urls = extract_http_urls(operand)
    if len(urls) != 1:
        return None
    candidate = urls[0]

    if len(operand) >= 2 and (operand[0], operand[-1]) in {("\"", "\""), ("'", "'"), ("(", ")")}:
        operand = operand[1:-1].strip()
    operand = operand.rstrip(".,!?;:")
    return candidate if operand == candidate else None


def web_search_request(text: str) -> str | None:
    """Extract the terms from a request that explicitly asks for a web search.

    Only Google or web wording opens the browser. A bare "search ..." is left
    for Omar, because it often means a local search ("search my Downloads").
    """
    match = re.match(
        r"^\s*(?:please\s+)?(?:"
        r"search\s+(?:on\s+)?google(?:\s+for)?"
        r"|google(?:\s+for)?"
        r"|search\s+(?:the\s+)?(?:web|internet|online)(?:\s+for)?"
        r"|web\s+search(?:\s+for)?"
        r")\b(.*)$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    query = match.group(1).lstrip(" \t,:-").strip()
    return query[:500] or None


def action_by_id(action_id: str) -> Action | None:
    return next((action for action in ACTIONS if action.id == action_id and action.available()), None)


def launch(action: Action) -> None:
    if not action.command:
        return
    subprocess.Popen(
        list(action.command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )


def launch_url(url: str) -> None:
    subprocess.Popen(
        ["omarchy", "launch", "browser", url],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )
