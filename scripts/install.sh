#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
# shellcheck source=install-ownership.sh
source "$ROOT/scripts/install-ownership.sh"

CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
BIN_HOME=${HOME}/.local/bin
PLUGIN_TARGET="$CONFIG_HOME/omarchy/plugins/ask-omar.assistant"
APP_TARGET="$DATA_HOME/ask-omar"
SERVICE_TARGET="$CONFIG_HOME/systemd/user/ask-omar.service"
CONFIG_TARGET="$CONFIG_HOME/ask-omar/config.toml"
DESKTOP_TARGET="$DATA_HOME/applications/ask-omar.desktop"
SETTINGS_DESKTOP_TARGET="$DATA_HOME/applications/ask-omar-settings.desktop"
GUARD_SOURCE="$ROOT/service/ask_omar/extensions/ask-omar-guard.ts"
GUARD_TARGET="$APP_TARGET/extensions/ask-omar-guard.ts"

mode=${1:-full}
case "$mode" in
  full) [[ $# -eq 0 ]] || { echo "Usage: $0 [--backend-only]" >&2; exit 2; } ;;
  --backend-only) [[ $# -eq 1 ]] || { echo "Usage: $0 [--backend-only]" >&2; exit 2; } ;;
  *) echo "Usage: $0 [--backend-only]" >&2; exit 2 ;;
esac

fail() {
  echo "Ask Omar: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null || fail "missing required command: $1"
}

# Check the source and runtime before changing any installed files. Pi is
# optional: Scratchpad and capture work even when Pi is absent.
for source in \
  "$ROOT/manifest.json" "$ROOT/plugin/AskOmar.qml" \
  "$ROOT/service/ask_omar/__main__.py" "$GUARD_SOURCE" \
  "$ROOT/systemd/ask-omar.service" "$ROOT/scripts/ask-omar" \
  "$ROOT/scripts/ask-omar-open" "$ROOT/scripts/capture.sh" \
  "$ROOT/scripts/install-ownership.sh" "$ROOT/scripts/app-install-marker" \
  "$ROOT/config/config.example.toml" \
  "$ROOT/desktop/ask-omar.desktop" "$ROOT/desktop/ask-omar-settings.desktop"; do
  [[ -f $source ]] || fail "missing source file: $source"
done

for program in git python node readlink sha256sum systemctl tar omarchy-shell \
  omarchy-capture-region omarchy-notification-send wl-copy grim jq pgrep xdg-open; do
  require_command "$program"
done
if [[ $mode == full ]]; then
  for program in omarchy omarchy-restart-shell; do require_command "$program"; done
fi

refuse_symlink() {
  local path=$1
  [[ ! -L $path ]] || fail "refusing to replace symlink: $path"
}

require_owned_file() {
  local path=$1 kind=$2
  [[ ! -e $path && ! -L $path ]] && return 0
  refuse_symlink "$path"
  [[ -f $path ]] || fail "refusing to replace non-file destination: $path"
  ask_omar_owns_file "$path" "$kind" "$ROOT" ||
    fail "refusing to replace a file Ask Omar did not install: $path"
}

# Complete destination preflight before invoking tools that may create state.
for path in \
  "$APP_TARGET" "$APP_TARGET/service" "$APP_TARGET/service/ask_omar" \
  "$APP_TARGET/extensions" "$GUARD_TARGET" "$SERVICE_TARGET" \
  "$BIN_HOME/ask-omar" "$BIN_HOME/ask-omar-open" "$BIN_HOME/ask-omar-capture" \
  "$DESKTOP_TARGET" "$SETTINGS_DESKTOP_TARGET"; do
  refuse_symlink "$path"
done

if [[ -e $APP_TARGET ]] && ! ask_omar_owns_app_directory "$APP_TARGET"; then
  fail "refusing to replace an application directory Ask Omar did not install: $APP_TARGET"
fi

require_owned_file "$BIN_HOME/ask-omar" cli
require_owned_file "$BIN_HOME/ask-omar-open" open
require_owned_file "$BIN_HOME/ask-omar-capture" capture
require_owned_file "$SERVICE_TARGET" service
require_owned_file "$DESKTOP_TARGET" desktop
require_owned_file "$SETTINGS_DESKTOP_TARGET" settings-desktop

ROOT_REAL=$(readlink -f -- "$ROOT")
PLUGIN_IS_SOURCE=0
if [[ $mode == full ]]; then
  if [[ -e $PLUGIN_TARGET || -L $PLUGIN_TARGET ]]; then
    if [[ -d $PLUGIN_TARGET && $(readlink -f -- "$PLUGIN_TARGET") == "$ROOT_REAL" ]]; then
      PLUGIN_IS_SOURCE=1
    elif [[ -L $PLUGIN_TARGET ]]; then
      fail "refusing to replace plugin symlink: $PLUGIN_TARGET"
    elif [[ ! -d $PLUGIN_TARGET ]]; then
      fail "plugin destination is not a directory: $PLUGIN_TARGET"
    fi
  fi

  if [[ $PLUGIN_IS_SOURCE -eq 0 ]]; then
    for path in \
      "$PLUGIN_TARGET/plugin" "$PLUGIN_TARGET/manifest.json" \
      "$PLUGIN_TARGET/plugin/AskOmar.qml" "$PLUGIN_TARGET/AskOmar.qml" \
      "$PLUGIN_TARGET/plugin/manifest.json"; do
      refuse_symlink "$path"
    done
  fi
fi

if [[ -L $CONFIG_TARGET ]]; then
  echo "Leaving symlinked config unchanged: $CONFIG_TARGET" >&2
elif [[ -e $CONFIG_TARGET && ! -f $CONFIG_TARGET ]]; then
  fail "config destination is not a regular file: $CONFIG_TARGET"
fi

python - <<'PY' || fail "Python 3.11 or newer is required."
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY

PYTHON_BIN=$(readlink -f -- "$(command -v python)")
[[ -x $PYTHON_BIN ]] || fail "could not resolve the Python interpreter."

# Test the capability Pi's TypeScript extension needs, instead of guessing a
# Node version from its version string. Direct .ts execution works in modern Node.
ts_probe=$(mktemp --suffix=.ts)
trap 'rm -f "$ts_probe"' EXIT
printf '%s\n' 'const value: string = "ready"; if (value !== "ready") process.exit(1);' > "$ts_probe"
if ! node "$ts_probe" >/dev/null 2>&1; then
  fail "Node must support direct TypeScript execution (Node 22.18+)."
fi
rm -f "$ts_probe"
trap - EXIT

if [[ $mode == full ]]; then
  omarchy plugin validate "$ROOT"
fi

# Inspect Pi's local help only. This avoids invoking a provider, logging in,
# or relying on a version number to infer option support.
pi_status=$(python - <<'PY'
import os
import re
import shutil
import subprocess

if not shutil.which("pi"):
    print("Pi was not found. Ask Omar did not install it; install it from https://pi.dev to enable AI requests.")
    print("Scratchpad and capture work without Pi.")
else:
    env = dict(os.environ, PI_OFFLINE="1")
    try:
        result = subprocess.run(
            ["pi", "--help"], capture_output=True, text=True, timeout=5, env=env, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Pi was found, but its supported options could not be checked locally.")
    else:
        required = {
            "--mode", "--no-session", "--tools", "--no-extensions", "--extension",
            "--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files",
            "--provider", "--model", "--thinking", "--system-prompt", "--name",
            "--list-models",
        }
        available = set(re.findall(r"(?<!\w)--[a-z][a-z-]*", result.stdout))
        missing = sorted(required - available)
        if result.returncode or missing:
            print("Pi was found but may not support Ask Omar's required flags: " + ", ".join(missing or ["help failed"]))
        else:
            print("Pi supports Ask Omar's required flags; provider sign-in was not checked.")
PY
)

ensure_directory() {
  local path=$1
  if [[ -L $path ]]; then
    [[ -d $path ]] || fail "directory symlink does not resolve to a directory: $path"
  else
    install -d "$path"
  fi
}

# All destination checks have passed. Stage only files tracked in the verified
# commit, then swap the application directory without copying caches or extras.
ensure_directory "$DATA_HOME"
ensure_directory "$BIN_HOME"
ensure_directory "$(dirname "$SERVICE_TARGET")"
ensure_directory "$(dirname "$DESKTOP_TARGET")"

STAGE_ROOT=$(mktemp -d "$DATA_HOME/.ask-omar-stage.XXXXXX")
LAUNCHER_STAGE=$(mktemp -d "${TMPDIR:-/tmp}/ask-omar-launchers.XXXXXX")
cleanup() {
  rm -rf -- "$STAGE_ROOT" "$LAUNCHER_STAGE"
}
trap cleanup EXIT

mkdir -p "$STAGE_ROOT/ask-omar/extensions"
git -C "$ROOT" archive --format=tar HEAD service/ask_omar | tar -x -C "$STAGE_ROOT/ask-omar"
install -T -m 644 "$GUARD_SOURCE" "$STAGE_ROOT/ask-omar/extensions/ask-omar-guard.ts"
install -T -m 644 "$ROOT/scripts/app-install-marker" "$STAGE_ROOT/ask-omar/.installed-by-ask-omar"

if [[ -e $APP_TARGET ]]; then
  APP_BACKUP=$(mktemp -d "$DATA_HOME/.ask-omar-backup.XXXXXX")
  rmdir "$APP_BACKUP"
  mv -T -- "$APP_TARGET" "$APP_BACKUP"
  if ! mv -T -- "$STAGE_ROOT/ask-omar" "$APP_TARGET"; then
    mv -T -- "$APP_BACKUP" "$APP_TARGET"
    fail "could not install the application files."
  fi
  rm -rf -- "$APP_BACKUP"
else
  mv -T -- "$STAGE_ROOT/ask-omar" "$APP_TARGET"
fi

# A marketplace checkout may itself be the installed target. Keep it intact;
# otherwise install just the runtime plugin files.
if [[ $mode == full && $PLUGIN_IS_SOURCE -eq 0 ]]; then
  install -d "$PLUGIN_TARGET/plugin"
  install -T -m 644 "$ROOT/manifest.json" "$PLUGIN_TARGET/manifest.json"
  install -T -m 644 "$ROOT/plugin/AskOmar.qml" "$PLUGIN_TARGET/plugin/AskOmar.qml"
  rm -f "$PLUGIN_TARGET/AskOmar.qml" "$PLUGIN_TARGET/plugin/manifest.json"
fi

if [[ ! -e $CONFIG_TARGET && ! -L $CONFIG_TARGET ]]; then
  if [[ -L $(dirname "$CONFIG_TARGET") ]]; then
    echo "Using symlinked config directory: $(dirname "$CONFIG_TARGET")" >&2
  else
    install -d -m 700 "$(dirname "$CONFIG_TARGET")"
  fi
  install -T -m 600 "$ROOT/config/config.example.toml" "$CONFIG_TARGET"
elif [[ ! -L $CONFIG_TARGET ]]; then
  chmod 600 "$CONFIG_TARGET"
fi

while IFS= read -r line || [[ -n $line ]]; do
  if [[ $line == 'exec __ASK_OMAR_PYTHON__ -m ask_omar "$@"' ]]; then
    printf 'exec %q -m ask_omar "$@"\n' "$PYTHON_BIN"
  else
    printf '%s\n' "$line"
  fi
done < "$ROOT/scripts/ask-omar" > "$LAUNCHER_STAGE/ask-omar"

install -T -m 755 "$LAUNCHER_STAGE/ask-omar" "$BIN_HOME/ask-omar"
install -T -m 755 "$ROOT/scripts/ask-omar-open" "$BIN_HOME/ask-omar-open"
install -T -m 755 "$ROOT/scripts/capture.sh" "$BIN_HOME/ask-omar-capture"
install -T -m 644 "$ROOT/systemd/ask-omar.service" "$SERVICE_TARGET"
install -T -m 644 "$ROOT/desktop/ask-omar.desktop" "$DESKTOP_TARGET"
install -T -m 644 "$ROOT/desktop/ask-omar-settings.desktop" "$SETTINGS_DESKTOP_TARGET"

systemctl --user daemon-reload
systemctl --user enable ask-omar.service >/dev/null
systemctl --user restart ask-omar.service
if [[ $mode == full ]]; then
  omarchy plugin validate "$PLUGIN_TARGET"
  omarchy plugin enable ask-omar.assistant --after omarchy.agents
  # An existing QML instance may still be running the previous version.
  omarchy-restart-shell
fi

echo "Ask Omar backend installed."
if [[ $mode == full ]]; then echo "Ask Omar plugin installed and enabled."; fi
printf '%s\n' "$pi_status"
echo "Check it with: ask-omar setup"
echo "Open it from the Omarchy app menu, or run: omarchy-shell ask-omar open"
