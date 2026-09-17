#!/usr/bin/env bash
set -euo pipefail

CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

systemctl --user disable --now ask-omar.service 2>/dev/null || true
omarchy plugin disable ask-omar.assistant 2>/dev/null || true
rm -f "$CONFIG_HOME/systemd/user/ask-omar.service" "$HOME/.local/bin/ask-omar" "$HOME/.local/bin/ask-omar-capture"
rm -f "$DATA_HOME/applications/ask-omar.desktop" "$DATA_HOME/applications/ask-omar-settings.desktop" "$HOME/.local/bin/ask-omar-open"
rm -rf "$CONFIG_HOME/omarchy/plugins/ask-omar.assistant" "$DATA_HOME/ask-omar"
systemctl --user daemon-reload
omarchy-shell shell rescanPlugins 2>/dev/null || true

echo "Ask Omar removed. Pi and its provider sign-ins were not changed."
echo "Ask Omar's configuration, drafts, history, Scratchpad notes, and attachments were preserved."
echo "Remove them manually with: rm -rf '$CONFIG_HOME/ask-omar' '${XDG_STATE_HOME:-$HOME/.local/state}/ask-omar'"
