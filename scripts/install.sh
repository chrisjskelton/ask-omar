#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
BIN_HOME=${HOME}/.local/bin
PLUGIN_TARGET="$CONFIG_HOME/omarchy/plugins/ask-omar.assistant"
APP_TARGET="$DATA_HOME/ask-omar"
SERVICE_TARGET="$CONFIG_HOME/systemd/user/ask-omar.service"
CONFIG_TARGET="$CONFIG_HOME/ask-omar/config.toml"
DESKTOP_TARGET="$DATA_HOME/applications/ask-omar.desktop"
SETTINGS_DESKTOP_TARGET="$DATA_HOME/applications/ask-omar-settings.desktop"

mode=${1:-full}
case "$mode" in
  full) [[ $# -eq 0 ]] || { echo "Usage: $0 [--backend-only]" >&2; exit 2; } ;;
  --backend-only) [[ $# -eq 1 ]] || { echo "Usage: $0 [--backend-only]" >&2; exit 2; } ;;
  *) echo "Usage: $0 [--backend-only]" >&2; exit 2 ;;
esac

require_command() {
  command -v "$1" >/dev/null || { echo "Missing required command: $1" >&2; exit 1; }
}

# Check the source and runtime before changing any installed files. Pi is
# optional: Scratchpad and capture work even when Pi is absent.
for source in \
  "$ROOT/manifest.json" "$ROOT/plugin/AskOmar.qml" \
  "$ROOT/service/ask_omar/__main__.py" \
  "$ROOT/service/ask_omar/extensions/ask-omar-guard.ts" \
  "$ROOT/systemd/ask-omar.service" "$ROOT/scripts/capture.sh" \
  "$ROOT/config/config.example.toml" \
  "$ROOT/desktop/ask-omar.desktop" "$ROOT/desktop/ask-omar-settings.desktop"; do
  [[ -f "$source" ]] || { echo "Missing source file: $source" >&2; exit 1; }
done

for program in python node systemctl omarchy-shell omarchy-capture-region \
  omarchy-notification-send wl-copy grim jq pgrep xdg-open; do
  require_command "$program"
done
if [[ $mode == full ]]; then
  for program in omarchy omarchy-restart-shell; do require_command "$program"; done
fi

python - <<'PY' || { echo "Ask Omar requires Python 3.11 or newer." >&2; exit 1; }
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY

# Test the capability Pi's TypeScript extension needs, instead of guessing a
# Node version from its version string. Direct .ts execution works in modern Node.
ts_probe=$(mktemp --suffix=.ts)
trap 'rm -f "$ts_probe"' EXIT
printf '%s\n' 'const value: string = "ready"; if (value !== "ready") process.exit(1);' > "$ts_probe"
if ! node "$ts_probe" >/dev/null 2>&1; then
  echo "Node must support direct TypeScript execution (Node 22.18+)." >&2
  exit 1
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

install -d "$APP_TARGET/service" "$APP_TARGET/extensions" "$BIN_HOME" \
  "$(dirname "$SERVICE_TARGET")" "$(dirname "$DESKTOP_TARGET")"
install -d -m 700 "$(dirname "$CONFIG_TARGET")"

# A marketplace checkout may itself be the installed target. Never copy a
# directory into itself; its manifest and QML already have the right layout.
if [[ $mode == full ]]; then
  source_plugin=$(cd -P -- "$ROOT" && pwd)
  target_plugin=""
  if [[ -d $PLUGIN_TARGET ]]; then target_plugin=$(cd -P -- "$PLUGIN_TARGET" && pwd); fi
  if [[ $source_plugin != "$target_plugin" ]]; then
    install -d "$PLUGIN_TARGET/plugin"
    install -m 644 "$ROOT/manifest.json" "$PLUGIN_TARGET/manifest.json"
    install -m 644 "$ROOT/plugin/AskOmar.qml" "$PLUGIN_TARGET/plugin/AskOmar.qml"
    rm -f "$PLUGIN_TARGET/AskOmar.qml" "$PLUGIN_TARGET/plugin/manifest.json"
  fi
fi

rm -rf "$APP_TARGET/service/ask_omar"
cp -a "$ROOT/service/ask_omar" "$APP_TARGET/service/"
install -m 644 "$ROOT/service/ask_omar/extensions/ask-omar-guard.ts" \
  "$APP_TARGET/extensions/ask-omar-guard.ts"
install -m 644 "$ROOT/systemd/ask-omar.service" "$SERVICE_TARGET"
install -m 755 "$ROOT/scripts/capture.sh" "$BIN_HOME/ask-omar-capture"
install -m 644 "$ROOT/desktop/ask-omar.desktop" "$DESKTOP_TARGET"
install -m 644 "$ROOT/desktop/ask-omar-settings.desktop" "$SETTINGS_DESKTOP_TARGET"

if [[ ! -f "$CONFIG_TARGET" ]]; then
  install -m 600 "$ROOT/config/config.example.toml" "$CONFIG_TARGET"
else
  chmod 600 "$CONFIG_TARGET"
fi

cat >"$BIN_HOME/ask-omar" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:/usr/local/bin:/usr/bin${PATH:+:$PATH}"
export PYTHONPATH="$DATA_HOME/ask-omar/service${PYTHONPATH:+:$PYTHONPATH}"
exec python -m ask_omar "$@"
WRAPPER
chmod +x "$BIN_HOME/ask-omar"

cat >"$BIN_HOME/ask-omar-open" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
systemctl --user start ask-omar.service
exec omarchy-shell ask-omar "${1:-open}"
WRAPPER
chmod +x "$BIN_HOME/ask-omar-open"

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
