#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
BIN_HOME=${HOME}/.local/bin
PLUGIN_TARGET="$CONFIG_HOME/omarchy/plugins/ask-omar.assistant"
APP_TARGET="$DATA_HOME/ask-omar"
SERVICE_TARGET="$CONFIG_HOME/systemd/user/ask-omar.service"
CONFIG_TARGET="$CONFIG_HOME/ask-omar/config.toml"
DESKTOP_TARGET="$DATA_HOME/applications/ask-omar.desktop"
SETTINGS_DESKTOP_TARGET="$DATA_HOME/applications/ask-omar-settings.desktop"

for command in python omarchy omarchy-shell omarchy-restart-shell systemctl; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 1; }
done

install -d "$PLUGIN_TARGET" "$APP_TARGET/service" "$APP_TARGET/extensions" "$BIN_HOME" "$(dirname "$SERVICE_TARGET")" "$(dirname "$DESKTOP_TARGET")"
install -d -m 700 "$(dirname "$CONFIG_TARGET")"
cp -a "$ROOT/plugin/." "$PLUGIN_TARGET/"
rm -rf "$APP_TARGET/service/ask_omar"
cp -a "$ROOT/service/ask_omar" "$APP_TARGET/service/"
cp "$ROOT/service/ask_omar/extensions/ask-omar-guard.ts" "$APP_TARGET/extensions/ask-omar-guard.ts"
cp "$ROOT/systemd/ask-omar.service" "$SERVICE_TARGET"
install -m 755 "$ROOT/scripts/capture.sh" "$BIN_HOME/ask-omar-capture"
install -m 644 "$ROOT/desktop/ask-omar.desktop" "$DESKTOP_TARGET"
install -m 644 "$ROOT/desktop/ask-omar-settings.desktop" "$SETTINGS_DESKTOP_TARGET"

if [[ ! -f "$CONFIG_TARGET" ]]; then
  install -m 600 "$ROOT/config/config.example.toml" "$CONFIG_TARGET"
else
  chmod 600 "$CONFIG_TARGET"
fi

GUARD_TARGET="$CONFIG_HOME/ask-omar/guard.json"
if [[ ! -f "$GUARD_TARGET" ]]; then
  install -m 600 "$ROOT/config/guard.example.json" "$GUARD_TARGET"
else
  chmod 600 "$GUARD_TARGET"
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
omarchy plugin validate "$PLUGIN_TARGET"
omarchy plugin enable ask-omar.assistant --after omarchy.agents
# Plugin rescans can leave an existing QML instance running the previous
# version. Restarting the Shell ensures the installed UI and IPC methods match.
omarchy-restart-shell

echo "Ask Omar installed."
if command -v pi >/dev/null; then
  echo "Pi was already installed and was not changed. Ask Omar will check its provider connection when opened."
else
  echo "Pi was not found. Ask Omar did not install it; install it from https://pi.dev to enable AI requests."
  echo "Scratchpad and capture work without Pi."
fi
echo "Check it with: ask-omar setup"
echo "Open it from the Omarchy app menu, or run: omarchy-shell ask-omar open"
echo "Dismiss the panel with Escape, by clicking outside it, or with its X button."
