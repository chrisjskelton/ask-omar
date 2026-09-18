#!/usr/bin/env bash
set -euo pipefail

CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

case ${1:-full} in
  full) [[ $# -eq 0 ]] || { echo "Usage: $0 [--backend-only]" >&2; exit 2; } ;;
  --backend-only) [[ $# -eq 1 ]] || { echo "Usage: $0 [--backend-only]" >&2; exit 2; } ;;
  *) echo "Usage: $0 [--backend-only]" >&2; exit 2 ;;
esac
mode=${1:-full}

systemctl --user disable --now ask-omar.service 2>/dev/null || true
if [[ $mode == full ]]; then
  omarchy plugin disable ask-omar.assistant 2>/dev/null || true
fi
rm -f "$CONFIG_HOME/systemd/user/ask-omar.service" "$HOME/.local/bin/ask-omar" "$HOME/.local/bin/ask-omar-capture"
rm -f "$DATA_HOME/applications/ask-omar.desktop" "$DATA_HOME/applications/ask-omar-settings.desktop" "$HOME/.local/bin/ask-omar-open"
rm -rf "$DATA_HOME/ask-omar"
if [[ $mode == full ]]; then
  rm -rf "$CONFIG_HOME/omarchy/plugins/ask-omar.assistant"
fi
systemctl --user daemon-reload
if [[ $mode == full ]]; then
  omarchy-shell shell rescanPlugins 2>/dev/null || true
fi

echo "Ask Omar removed. Pi and its provider sign-ins were not changed."
echo "Ask Omar's configuration, drafts, history, Scratchpad notes, and attachments were preserved."
echo "Remove them manually with: rm -rf '$CONFIG_HOME/ask-omar' '${XDG_STATE_HOME:-$HOME/.local/state}/ask-omar'"
