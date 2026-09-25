#!/usr/bin/env bash
set -euo pipefail

notify_shell() {
  omarchy-shell -q ask-omar "$@" >/dev/null 2>&1 || true
}

notify_screenshot() {
  local path=$1
  local message=$2
  omarchy-notification-send \
    --image "$path" \
    -t 8000 \
    "Screenshot saved" \
    "$message" \
    --exec xdg-open "$path" >/dev/null 2>&1 || true
}

deliver_file() {
  local path=${1:-}
  local target=${2:-assistant}
  [[ -n $path && -f $path ]] || return 0

  if [[ $target == scratchpad ]]; then
    local response markdown
    response=$(ask-omar scratchpad-attach "$path") || return 0
    markdown=$(jq -er '.markdown // empty' <<<"$response") || return 0
    notify_shell appendScratchpad "$markdown"
    notify_screenshot "$path" "Added to Scratchpad · $path"
  else
    printf '%s' "$path" | wl-copy
    notify_screenshot "$path" "File path copied · $path"
  fi
}

delayed_screenshot() {
  local picked freeze_pid selection notification_id="" remaining
  local output_dir filename path

  picked=$(omarchy-capture-region smart --keep-freeze) || return 0
  freeze_pid=${picked%%$'\n'*}
  selection=${picked#*$'\n'}
  [[ -n $selection && $selection != "$picked" ]] || return 0
  [[ -n $freeze_pid ]] && kill "$freeze_pid" 2>/dev/null || true

  for remaining in 5 4 3 2 1; do
    if [[ ! $notification_id =~ ^[0-9]+$ ]]; then
      notification_id=$(omarchy-notification-send -p -u normal -t 1500 \
        "Capturing in $remaining…" "Keep the selected area ready") || true
    else
      omarchy-notification-send -r "$notification_id" -u normal -t 1500 \
        "Capturing in $remaining…" "Keep the selected area ready" || true
    fi
    sleep 1
  done
  omarchy-shell -q notifications dismiss "Capturing in" >/dev/null 2>&1 || true
  sleep 0.2

  [[ -f ~/.config/user-dirs.dirs ]] && source ~/.config/user-dirs.dirs
  output_dir=${OMARCHY_SCREENSHOT_DIR:-${XDG_PICTURES_DIR:-$HOME/Pictures}}
  mkdir -p "$output_dir"
  filename="screenshot-$(date +'%Y-%m-%d_%H-%M-%S').png"
  path="$output_dir/$filename"
  grim -g "$selection" "$path"
  printf '%s\n' "$path"
}

case ${1:-} in
screenshot)
  mode=${2:-smart}
  target=${3:-assistant}
  if [[ $mode == delayed ]]; then
    path=$(delayed_screenshot)
  else
    path=$(omarchy capture screenshot "$mode" save)
  fi
  deliver_file "$path" "$target"
  ;;
record-start)
  mode=${2:-region}
  target=${3:-assistant}
  if [[ $mode == fullscreen ]]; then
    omarchy capture screenrecording --fullscreen
  else
    omarchy capture screenrecording
  fi
  if pgrep -f '^gpu-screen-recorder' >/dev/null; then
    notify_shell recordingStarted "$target"
  fi
  ;;
record-stop)
  target=${2:-assistant}
  path=$(omarchy capture screenrecording --stop-recording)
  notify_shell recordingStopped
  deliver_file "$path" "$target"
  ;;
*)
  echo "Usage: ask-omar-capture {screenshot MODE TARGET|record-start MODE TARGET|record-stop TARGET}" >&2
  exit 2
  ;;
esac
