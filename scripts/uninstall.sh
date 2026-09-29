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
APP_TARGET="$DATA_HOME/ask-omar"
APP_MANIFEST_NAME=.installed-files.sha256

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

path_has_symlink_component() {
  local root=$1 relative=$2 component path
  local -a components
  path=$root
  IFS=/ read -r -a components <<< "$relative"
  for component in "${components[@]}"; do
    path="$path/$component"
    [[ ! -L $path ]] || return 0
  done
  return 1
}

remove_empty_managed_parents() {
  local relative=$1 parent=${1%/*} path
  [[ $parent != "$relative" ]] || return 0
  while [[ $parent != . && -n $parent ]]; do
    path="$APP_TARGET/$parent"
    [[ ! -L $path ]] || return 0
    rmdir -- "$path" 2>/dev/null || return 0
    if [[ $parent == */* ]]; then
      parent=${parent%/*}
    else
      parent=.
    fi
  done
}

remove_owned_plugin_file() {
  local relative=$1 path="$PLUGIN_TARGET/$1"
  [[ -e $path || -L $path ]] || return 0
  if path_has_symlink_component "$PLUGIN_TARGET" "$relative"; then
    echo "Leaving plugin path containing a symlink: $path" >&2
  elif ask_omar_owns_plugin_file "$path" "$relative" "$ROOT"; then
    rm -f -- "$path"
  else
    echo "Leaving modified plugin file: $path" >&2
  fi
}

if ask_omar_owns_file "$SERVICE_TARGET" service "$ROOT"; then
  systemctl --user disable --now ask-omar.service 2>/dev/null || true
fi

plugin_is_source=0
plugin_owned=0
if [[ $mode == full && ( -d $PLUGIN_TARGET || -L $PLUGIN_TARGET ) ]] &&
    [[ $(readlink -f -- "$PLUGIN_TARGET") == $(readlink -f -- "$ROOT") ]]; then
  plugin_is_source=1
  plugin_owned=1
elif [[ $mode == full && -d $PLUGIN_TARGET && ! -L $PLUGIN_TARGET ]] &&
    ask_omar_owns_plugin_file "$PLUGIN_TARGET/manifest.json" manifest.json "$ROOT"; then
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

if ask_omar_owns_app_directory "$APP_TARGET"; then
  manifest="$APP_TARGET/$APP_MANIFEST_NAME"
  if ask_omar_valid_app_manifest "$manifest"; then
    while IFS=$'\t' read -r hash relative; do
      path="$APP_TARGET/$relative"
      if path_has_symlink_component "$APP_TARGET" "$relative"; then
        echo "Leaving application path containing a symlink: $path" >&2
      elif ask_omar_matches_sha256 "$path" "$hash"; then
        rm -f -- "$path"
        remove_empty_managed_parents "$relative"
      elif [[ -e $path || -L $path ]]; then
        echo "Leaving modified application file: $path" >&2
      fi
    done < "$manifest"
    rm -f -- "$manifest"
    rmdir -- "$APP_TARGET" 2>/dev/null || true
  else
    echo "Leaving application directory without a valid managed-file manifest: $APP_TARGET" >&2
  fi
elif [[ -e $APP_TARGET || -L $APP_TARGET ]]; then
  echo "Leaving application path Ask Omar could not identify: $APP_TARGET" >&2
fi

if [[ $mode == full && ( -e $PLUGIN_TARGET || -L $PLUGIN_TARGET ) ]]; then
  if (( plugin_is_source )); then
    echo "Leaving marketplace checkout in place: $PLUGIN_TARGET" >&2
  elif [[ -d $PLUGIN_TARGET && ! -L $PLUGIN_TARGET ]]; then
    remove_owned_plugin_file manifest.json
    remove_owned_plugin_file plugin/AskOmar.qml
    rmdir -- "$PLUGIN_TARGET/plugin" 2>/dev/null || true
    rmdir -- "$PLUGIN_TARGET" 2>/dev/null || true
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
