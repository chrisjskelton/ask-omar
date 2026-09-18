from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path


THINKING_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")


def _section(raw: dict, name: str) -> dict:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Ask Omar config [{name}] must be a table.")
    return value


def _integer(section: dict, key: str, default: int, minimum: int) -> int:
    value = section.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"Ask Omar config {key} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Ask Omar config {key} must be an integer.") from error
    return max(minimum, parsed)


def _string(section: dict, key: str, default: str) -> str:
    value = section.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"Ask Omar config {key} must be text.")
    return value.strip()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="config.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def xdg_path(variable: str, fallback: str) -> Path:
    return Path(os.environ.get(variable, str(Path.home() / fallback))).expanduser()


def default_config_path() -> Path:
    return Path(
        os.environ.get(
            "ASK_OMAR_CONFIG",
            xdg_path("XDG_CONFIG_HOME", ".config") / "ask-omar" / "config.toml",
        )
    )


@dataclass(frozen=True)
class Config:
    backend: str = "pi"
    provider: str = ""
    model: str = ""
    thinking: str = "low"
    timeout_seconds: int = 90
    conversation_idle_minutes: int = 30
    history_limit: int = 100

    @property
    def agent_identity_ready(self) -> bool:
        return bool(self.provider.strip() and self.model.strip())

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or default_config_path()
        if not path.exists():
            return cls()

        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        agent = _section(raw, "agent")
        conversation = _section(raw, "conversation")
        history = _section(raw, "history")
        return cls(
            backend=_string(agent, "backend", cls.backend),
            provider=_string(agent, "provider", cls.provider),
            model=_string(agent, "model", cls.model),
            thinking=_string(agent, "thinking", cls.thinking) or cls.thinking,
            timeout_seconds=_integer(agent, "timeout_seconds", cls.timeout_seconds, 10),
            conversation_idle_minutes=_integer(
                conversation, "idle_timeout_minutes", cls.conversation_idle_minutes, 0
            ),
            history_limit=_integer(history, "limit", cls.history_limit, 0),
        )


def update_agent_settings(
    path: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    thinking: str | None = None,
) -> None:
    """Update [agent] provider/model/thinking while preserving the rest of the file."""
    updates = {
        key: value
        for key, value in {
            "provider": provider,
            "model": model,
            "thinking": thinking,
        }.items()
        if value is not None
    }
    if not updates:
        return
    for key, value in updates.items():
        if not re.fullmatch(r"[A-Za-z0-9._:/-]+", value):
            raise ValueError(f"Invalid {key} value.")
    if "thinking" in updates and updates["thinking"] not in THINKING_LEVELS:
        raise ValueError(
            "Thinking must be one of: " + ", ".join(THINKING_LEVELS) + "."
        )

    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if not text.strip():
        text = (
            "# Ask Omar configuration.\n\n"
            "[agent]\n"
            'backend = "pi"\n'
            f'provider = "{updates.get("provider", "")}"\n'
            f'model = "{updates.get("model", "")}"\n'
            f'thinking = "{updates.get("thinking", Config.thinking)}"\n'
            "timeout_seconds = 90\n"
        )
        _atomic_write(path, text)
        return

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_agent = False
    seen: set[str] = set()
    agent_seen = False

    def flush_missing() -> None:
        for key, value in updates.items():
            if key not in seen:
                out.append(f'{key} = "{value}"\n')
                seen.add(key)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_agent:
                flush_missing()
            in_agent = stripped == "[agent]"
            if in_agent:
                agent_seen = True
            out.append(line)
            continue
        if in_agent:
            replaced = False
            for key, value in updates.items():
                if re.match(rf"^{re.escape(key)}\s*=", stripped):
                    out.append(f'{key} = "{value}"\n')
                    seen.add(key)
                    replaced = True
                    break
            if not replaced:
                out.append(line)
        else:
            out.append(line)
    if in_agent:
        flush_missing()
    elif not agent_seen:
        if out and not out[-1].endswith("\n"):
            out.append("\n")
        out.append("\n[agent]\n")
        flush_missing()

    updated = "".join(out)
    tomllib.loads(updated)
    _atomic_write(path, updated)


def pi_agent_home() -> Path:
    return Path.home() / ".pi" / "agent"


def read_pi_default_identity(settings_path: Path | None = None) -> tuple[str, str]:
    """Return (provider, model) from Pi's interactive defaults, or empty strings."""
    path = settings_path or (pi_agent_home() / "settings.json")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return "", ""
    if not isinstance(raw, dict):
        return "", ""
    provider = str(raw.get("defaultProvider") or "").strip()
    model = str(raw.get("defaultModel") or "").strip()
    return provider, model


def parse_pi_list_models(output: str) -> list[tuple[str, str]]:
    """Parse `pi --list-models` text into (provider, model) pairs."""
    pairs: list[tuple[str, str]] = []
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            pairs.append((parts[0], parts[1]))
    return pairs


def config_home() -> Path:
    return xdg_path("XDG_CONFIG_HOME", ".config") / "ask-omar"


def data_home() -> Path:
    return xdg_path("XDG_DATA_HOME", ".local/share") / "ask-omar"


def state_home() -> Path:
    return xdg_path("XDG_STATE_HOME", ".local/state") / "ask-omar"


def runtime_socket() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "ask-omar.sock"

    # Never bind directly in world-searchable /tmp. An attacker could connect
    # in the interval between bind() and chmod(). The fallback parent is
    # owner-verified and private before the socket is created.
    base = Path(tempfile.gettempdir()) / f"ask-omar-{os.getuid()}"
    try:
        base.mkdir(mode=0o700)
    except FileExistsError:
        details = base.lstat()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid():
            raise RuntimeError(f"Unsafe Ask Omar runtime directory: {base}")
    os.chmod(base, 0o700)
    return base / "ask-omar.sock"
