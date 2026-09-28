#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
# shellcheck source=install-ownership.sh
source "$ROOT/scripts/install-ownership.sh"

CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
BIN_HOME=${HOME}/.local/bin
SERVICE_TARGET="$CONFIG_HOME/systemd/user/ask-omar.service"
PLUGIN_TARGET="$CONFIG_HOME/omarchy/plugins/ask-omar.assistant"

case ${1:-full} in
  full) [[ $# -eq 0 ]] || { echo "Usage: $0 [--backend-only]" >&2; exit 2; } ;;
  --backend-only) [[ $# -eq 1 ]] || { echo "Usage: $0 [--backend-only]" >&2; exit 2; } ;;
  *) echo "Usage: $0 [--backend-only]" >&2; exit 2 ;;
esac
mode=${1:-full}

remove_owned_file() {
  local path=$1 kind=$2
  [[ -e $path || -L $path ]] || return 0
  if ask_omar_owns_file "$path" "$kind" "$ROOT"; then
    rm -f -- "$path"
  else
    echo "Leaving file Ask Omar did not install: $path" >&2
  fi
}

if ask_omar_owns_file "$SERVICE_TARGET" service "$ROOT"; then
  systemctl --user disable --now ask-omar.service 2>/dev/null || true
fi

plugin_owned=0
if [[ $mode == full && -L $PLUGIN_TARGET ]] &&
    [[ $(readlink -f -- "$PLUGIN_TARGET") == $(readlink -f -- "$ROOT") ]]; then
  plugin_owned=1
elif [[ $mode == full && -d $PLUGIN_TARGET && ! -L $PLUGIN_TARGET ]] &&
    cmp -s "$PLUGIN_TARGET/manifest.json" "$ROOT/manifest.json"; then
  plugin_owned=1
fi

if (( plugin_owned )); then
  omarchy plugin disable ask-omar.assistant 2>/dev/null || true
fi

remove_owned_file "$SERVICE_TARGET" service
remove_owned_file "$BIN_HOME/ask-omar" cli
remove_owned_file "$BIN_HOME/ask-omar-open" open
remove_owned_file "$BIN_HOME/ask-omar-capture" capture
remove_owned_file "$DATA_HOME/applications/ask-omar.desktop" desktop
remove_owned_file "$DATA_HOME/applications/ask-omar-settings.desktop" settings-desktop

if [[ -d $DATA_HOME/ask-omar && ! -L $DATA_HOME/ask-omar ]]; then
  rm -rf -- "$DATA_HOME/ask-omar"
elif [[ -e $DATA_HOME/ask-omar || -L $DATA_HOME/ask-omar ]]; then
  echo "Leaving non-directory application path: $DATA_HOME/ask-omar" >&2
fi

if [[ $mode == full && ( -e $PLUGIN_TARGET || -L $PLUGIN_TARGET ) ]]; then
  if (( plugin_owned )); then
    if [[ -L $PLUGIN_TARGET ]]; then
      rm -f -- "$PLUGIN_TARGET"
    else
      rm -rf -- "$PLUGIN_TARGET"
    fi
  else
    echo "Leaving plugin directory Ask Omar could not identify: $PLUGIN_TARGET" >&2
  fi
fi

systemctl --user daemon-reload
if [[ $mode == full ]]; then
  omarchy-shell shell rescanPlugins 2>/dev/null || true
fi

echo "Ask Omar removed. Pi and its provider sign-ins were not changed."
echo "Ask Omar's configuration, drafts, history, Scratchpad notes, and attachments were preserved."
printf 'Remove them manually with: rm -rf -- %q %q\n' \
  "$CONFIG_HOME/ask-omar" "${XDG_STATE_HOME:-$HOME/.local/state}/ask-omar"
