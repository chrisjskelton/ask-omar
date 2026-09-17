from __future__ import annotations

import configparser
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    description: str
    command: tuple[str, ...] | None
    phrases: tuple[str, ...]
    base_score: float = 0.0
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
        ("take a screenshot", "capture the screen", "capture a region"),
        5.0,
    ),
    Action(
        "help.windows",
        "Arrange windows",
        "Use Super + Shift + arrow keys to swap tiled windows. Use Super + left-drag to move a floating window, Super + right-drag to resize it, and Super + T to toggle tiling.",
        None,
        ("show window arrangement help", "show window management help"),
        4.0,
        False,
    ),
    Action(
        "app.herdr",
        "Herdr",
        "Opening Herdr.",
        ("omarchy", "launch", "terminal", "herdr"),
        ("open herdr", "launch herdr", "start herdr"),
        3.0,
        True,
        "herdr",
    ),
    Action(
        "app.browser",
        "Browser",
        "Opening your default browser.",
        ("omarchy", "launch", "browser"),
        ("open browser", "open the browser", "launch browser", "open the internet"),
        2.0,
    ),
    Action(
        "terminal.pi.continue",
        "Continue Pi",
        "Opening Pi in a terminal and continuing your last session.",
        ("omarchy-launch-terminal", "--app-id=dev.ask-omar.pi", "--title=Pi", "pi", "-c"),
        (
            "continue pi",
            "resume pi",
            "continue my last pi session",
            "continue the last pi session",
            "resume my last pi session",
            "resume the last pi session",
            "open pi in a terminal and continue the last session",
            "open pi in terminal and continue the last session",
        ),
        1.8,
        True,
        "pi",
    ),
    Action(
        "terminal.pi.new",
        "Open Pi",
        "Opening Pi in a terminal.",
        ("omarchy-launch-terminal", "--app-id=dev.ask-omar.pi", "--title=Pi", "pi"),
        ("open pi", "launch pi", "start pi", "open pi in a terminal", "open pi in terminal"),
        1.6,
        True,
        "pi",
    ),
    Action(
        "app.1password",
        "1Password",
        "Opening 1Password Quick Access.",
        ("omarchy", "launch", "1password"),
        ("open 1password", "launch 1password", "open my password manager"),
        1.0,
        True,
        "1password",
    ),
    Action(
        "help.keybindings",
        "Keybindings",
        "Opening Omarchy's searchable keybindings.",
        ("omarchy", "menu", "keybindings"),
        ("show shortcuts", "show keyboard shortcuts", "show keybindings"),
        0.5,
    ),
)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def looks_like_question(text: str) -> bool:
    words = set(normalize(text).split())
    return bool(words & {"how", "what", "which", "where", "why", "shortcut", "key", "keys"})


NON_OPEN_VERBS = frozenset({"close", "quit", "exit", "stop", "kill"})
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
    """Extract the terms from an explicit Google/search request."""
    google = re.match(
        r"^\s*(?:please\s+)?(?:search\s+(?:on\s+)?google|google)\b(.*)$",
        text,
        re.IGNORECASE,
    )
    if google:
        remainder = re.sub(r"^\s+for\b", "", google.group(1), flags=re.IGNORECASE)
        query = remainder.lstrip(" \t,:-").strip()
        return query[:500] or None

    generic = re.match(r"^\s*(?:please\s+)?search(?:\s+for)?\b(.*)$", text, re.IGNORECASE)
    if not generic:
        return None
    query = generic.group(1).lstrip(" \t,:-").strip()
    return query[:500] or None


def close_request(text: str) -> str | None:
    match = re.match(
        r"^\s*(?:please\s+)?(?:close|quit)\s+(.+?)\s*$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    target = re.sub(r"^(?:my|the)\s+", "", match.group(1), flags=re.IGNORECASE)
    target = re.sub(r"\s+please$", "", target, flags=re.IGNORECASE)
    return target.strip() or None


def resolve_action(text: str) -> Action | None:
    value = normalize(text)
    if not value:
        return None

    # Classify the requested operation before matching a target noun. Without
    # this guard, "close browser" scores the "browser" phrase and opens one.
    value_words = set(value.split())
    if value_words & NON_OPEN_VERBS:
        return None
    if re.search(r"\b(?:do not|don t|dont|never)\s+(?:open|launch|start|run)\b", value):
        return None

    # Questions should be answered rather than accidentally performing the
    # action they mention. Dedicated help actions are still allowed.
    question = looks_like_question(value)
    for action in ACTIONS:
        if not action.available():
            continue
        if value not in {normalize(phrase) for phrase in action.phrases}:
            continue
        if question and action.command is not None and not action.id.startswith("help."):
            return None
        return action
    return None


def action_by_id(action_id: str) -> Action | None:
    return next((action for action in ACTIONS if action.id == action_id and action.available()), None)


def agent_action_catalog() -> list[dict[str, str]]:
    return [
        {"id": action.id, "label": action.label, "description": action.description}
        for action in ACTIONS
        if action.available()
    ]


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


def desktop_directories() -> Iterable[Path]:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    yield data_home / "applications"
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    for entry in data_dirs.split(":"):
        if entry:
            yield Path(entry) / "applications"


def discover_apps() -> list[dict[str, str]]:
    apps: dict[str, dict[str, str]] = {}
    for directory in desktop_directories():
        if not directory.is_dir():
            continue
        for path in directory.glob("*.desktop"):
            desktop_id = path.name
            if desktop_id in apps:
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            parser.optionxform = str
            try:
                parser.read(path, encoding="utf-8")
                entry = parser["Desktop Entry"]
            except (OSError, UnicodeError, KeyError, configparser.Error):
                continue
            if entry.get("Type", "Application") != "Application":
                continue
            if entry.get("Hidden", "false").casefold() == "true" or entry.get("NoDisplay", "false").casefold() == "true":
                continue
            name = entry.get("Name", "").strip()
            if not name:
                continue
            try_exec = entry.get("TryExec", "").strip()
            if try_exec:
                executable = Path(try_exec).expanduser()
                if "/" in try_exec:
                    if not executable.is_file() or not os.access(executable, os.X_OK):
                        continue
                elif shutil.which(try_exec) is None:
                    continue
            apps[desktop_id] = {"id": desktop_id, "name": name}
    return sorted(apps.values(), key=lambda app: app["name"].casefold())


def find_app(query: str) -> dict[str, str] | None:
    """Resolve only an exact discovered app name or desktop ID.

    Natural-language and partial-name interpretation belongs to Pi. The local
    fast path is deliberately strict so a short app name cannot hijack prose.
    """
    needle = normalize(query)
    if not needle:
        return None
    matches = [
        app
        for app in discover_apps()
        if needle in {
            normalize(app["name"]),
            normalize(re.sub(r"\.desktop$", "", app["id"], flags=re.IGNORECASE)),
        }
    ]
    return matches[0] if len(matches) == 1 else None


def app_by_id(desktop_id: str) -> dict[str, str] | None:
    return next((app for app in discover_apps() if app["id"] == desktop_id), None)


def launch_url(url: str) -> None:
    subprocess.Popen(
        ["omarchy", "launch", "browser", url],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )


# Window mutation is intentionally absent until Hyprland offers a documented,
# safely testable target contract for this compositor version.


def launch_desktop_app(app: dict[str, str]) -> None:
    subprocess.Popen(
        ["uwsm-app", "--", "gtk-launch", app["id"]],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )
