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
APP_MANIFEST_NAME=.installed-files.sha256
LAUNCHER_MANIFEST_NAME=.installed-launchers.sha256
LAUNCHER_KINDS=(cli open capture service desktop settings-desktop)

# The widget is the Omarchy plugin checkout itself (omarchy plugin add), so this
# script installs only the companion backend. --backend-only is accepted for
# older instructions and means the same thing.
case "$#:${1:-}" in
  0: | 1:--backend-only) ;;
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

if [[ -e $APP_TARGET ]] && ! ask_omar_owns_app_directory "$APP_TARGET" &&
    ! ask_omar_is_bytecode_residue "$APP_TARGET"; then
  fail "refusing to replace an application directory Ask Omar did not install: $APP_TARGET"
fi

require_owned_file "$BIN_HOME/ask-omar" cli
require_owned_file "$BIN_HOME/ask-omar-open" open
require_owned_file "$BIN_HOME/ask-omar-capture" capture
require_owned_file "$SERVICE_TARGET" service
require_owned_file "$DESKTOP_TARGET" desktop
require_owned_file "$SETTINGS_DESKTOP_TARGET" settings-desktop

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

# The ask-omar launcher is its source with the Python path filled in. Older
# releases differ only in the flags on that one line.
render_cli_launcher() {
  local line
  while IFS= read -r line || [[ -n $line ]]; do
    if [[ $line == 'exec __ASK_OMAR_PYTHON__ '* ]]; then
      printf 'exec %q %s\n' "$PYTHON_BIN" "${line#'exec __ASK_OMAR_PYTHON__ '}"
    else
      printf '%s\n' "$line"
    fi
  done
}

# Where each managed file comes from, and where it is installed.
launcher_source() {
  case $1 in
    cli) echo scripts/ask-omar ;;
    open) echo scripts/ask-omar-open ;;
    capture) echo scripts/capture.sh ;;
    service) echo systemd/ask-omar.service ;;
    desktop) echo desktop/ask-omar.desktop ;;
    settings-desktop) echo desktop/ask-omar-settings.desktop ;;
  esac
}
launcher_target() {
  case $1 in
    cli) echo "$BIN_HOME/ask-omar" ;;
    open) echo "$BIN_HOME/ask-omar-open" ;;
    capture) echo "$BIN_HOME/ask-omar-capture" ;;
    service) echo "$SERVICE_TARGET" ;;
    desktop) echo "$DESKTOP_TARGET" ;;
    settings-desktop) echo "$SETTINGS_DESKTOP_TARGET" ;;
  esac
}
# What this setup will write for a managed file.
render_launcher() {
  if [[ $1 == cli ]]; then
    render_cli_launcher < "$ROOT/scripts/ask-omar"
  else
    cat -- "$ROOT/$(launcher_source "$1")"
  fi
}

# Installs from before the launcher manifest: the file must be byte-identical
# to what one of the older releases installed. Tags are absent from shallow
# checkouts, so a missing tag or file is skipped.
matches_older_launcher() {
  local kind=$1 target=$2 source tag
  source=$(launcher_source "$kind")
  for tag in v0.1.0 v0.1.1 v0.1.2 v0.1.3 v0.1.4 v0.1.5; do
    git -C "$ROOT" rev-parse -q --verify "refs/tags/$tag" >/dev/null || continue
    git -C "$ROOT" cat-file -e "$tag:$source" 2>/dev/null || continue
    if [[ $kind == cli ]]; then
      # Python may have been upgraded since, so ignore which interpreter the
      # old launcher points at and compare everything else.
      cmp -s <(sed -E 's#^exec (\\.|[^ \\])+ #exec __ASK_OMAR_PYTHON__ #' -- "$target") \
        <(git -C "$ROOT" show "$tag:$source") && return 0
    else
      cmp -s -- "$target" <(git -C "$ROOT" show "$tag:$source") && return 0
    fi
  done
  return 1
}

# An existing managed file is only replaced if it is already what this setup
# writes, matches the hash recorded when it was installed, or (before the
# record existed) matches a file an older release installed. The earlier
# ownership checks have already refused symlinks and foreign files; an exact
# pre-marker legacy file is accepted only when there is no record.
PREVIOUS_LAUNCHERS="$APP_TARGET/$LAUNCHER_MANIFEST_NAME"
if [[ -e $PREVIOUS_LAUNCHERS || -L $PREVIOUS_LAUNCHERS ]] &&
    ! ask_omar_valid_launcher_manifest "$PREVIOUS_LAUNCHERS"; then
  fail "refusing to replace an invalid launcher manifest: $PREVIOUS_LAUNCHERS"
fi
for kind in "${LAUNCHER_KINDS[@]}"; do
  target=$(launcher_target "$kind")
  [[ -e $target ]] || continue
  cmp -s -- "$target" <(render_launcher "$kind") && continue
  if [[ -f $PREVIOUS_LAUNCHERS ]]; then
    hash=$(ask_omar_recorded_launcher_hash "$PREVIOUS_LAUNCHERS" "$kind") &&
      ask_omar_matches_sha256 "$target" "$hash" && continue
  else
    ask_omar_has_marker "$target" || continue
    matches_older_launcher "$kind" "$target" && continue
  fi
  fail "refusing to replace a file Ask Omar did not install, or that has been changed: $target (move it aside and run setup again; if you installed before 0.1.4, run git fetch --tags here first)"
done

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
            [
                "pi", "--help", "--no-extensions", "--no-skills",
                "--no-prompt-templates", "--no-themes", "--no-context-files",
            ],
            capture_output=True, text=True, timeout=5, env=env, check=False,
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
# commit without copying caches or extras.
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

(
  cd "$STAGE_ROOT/ask-omar"
  while IFS= read -r -d '' file; do
    relative=${file#./}
    read -r digest _ < <(sha256sum < "$file")
    printf '%s\t%s\n' "$digest" "$relative"
  done < <(find . -type f ! -name "$APP_MANIFEST_NAME" -print0 | sort -z)
) > "$STAGE_ROOT/ask-omar/$APP_MANIFEST_NAME"

if [[ -e $APP_TARGET/$APP_MANIFEST_NAME ]] &&
    ! ask_omar_valid_app_manifest "$APP_TARGET/$APP_MANIFEST_NAME"; then
  fail "refusing to replace an invalid application manifest: $APP_TARGET/$APP_MANIFEST_NAME"
fi

# Preflight every managed runtime path before writing any of them. Existing
# Ask Omar files are updated in place; unknown nested files are left alone.
while IFS= read -r -d '' directory; do
  relative=${directory#"$STAGE_ROOT/ask-omar"/}
  [[ $directory == "$STAGE_ROOT/ask-omar" ]] && continue
  target="$APP_TARGET/$relative"
  refuse_symlink "$target"
  [[ ! -e $target || -d $target ]] || fail "application directory path is not a directory: $target"
done < <(find "$STAGE_ROOT/ask-omar" -type d -print0)
# An existing file is only replaced if Ask Omar put it there unchanged: it is
# already this release's file, it matches the hash recorded when it was
# installed, or (for installs from before the manifest) it matches that file
# in an older release.
PREVIOUS_MANIFEST="$APP_TARGET/$APP_MANIFEST_NAME"
recorded_hash() {
  [[ -f $PREVIOUS_MANIFEST ]] || return 1
  awk -F '\t' -v path="$1" '$2 == path { print $1; found = 1; exit } END { exit !found }' \
    "$PREVIOUS_MANIFEST"
}
matches_older_release() {
  local relative=$1 target=$2 source tag
  # These two are checked against the exact 0.1.0/0.1.1 hashes used to
  # recognise an older install. Every other file needs the release tags.
  case $relative in
    service/ask_omar/__init__.py)
      ask_omar_matches_sha256 "$target" 99f685c4490a478c5f010859d3bd635dfb1c73b59fc207fad499aeb7dbc19735 ||
        ask_omar_matches_sha256 "$target" a57da2d68176ae3cc78f3166e43f9a06f831f4fbbd3fe76064f1af535902462d
      ;;
    extensions/ask-omar-guard.ts)
      ask_omar_matches_sha256 "$target" f7f0696e3809b7ff3f3494f79bbd7d6f1192100af3d98603a0e87bdb7699f0e0 ||
        ask_omar_matches_sha256 "$target" 0ee811d84d020ee40d970ba288b8618ae8f7b75bd339ec02ddbeb4af4a558fc9
      ;;
    *) false ;;
  esac && return 0
  source=$relative
  [[ $relative == extensions/* ]] && source="service/ask_omar/$relative"
  for tag in v0.1.0 v0.1.1 v0.1.2; do
    git -C "$ROOT" rev-parse -q --verify "refs/tags/$tag" >/dev/null || continue
    cmp -s -- "$target" <(git -C "$ROOT" show "$tag:$source" 2>/dev/null) && return 0
  done
  return 1
}
while IFS= read -r -d '' file; do
  relative=${file#"$STAGE_ROOT/ask-omar"/}
  target="$APP_TARGET/$relative"
  refuse_symlink "$target"
  [[ ! -e $target || -f $target ]] || fail "application file path is not a regular file: $target"
  [[ -e $target && $relative != "$APP_MANIFEST_NAME" ]] || continue
  cmp -s -- "$file" "$target" && continue
  if [[ -f $PREVIOUS_MANIFEST ]]; then
    hash=$(recorded_hash "$relative") && ask_omar_matches_sha256 "$target" "$hash" && continue
  elif matches_older_release "$relative" "$target"; then
    continue
  fi
  fail "refusing to replace a file Ask Omar did not install, or that has been changed: $target (move it aside and run setup again; if you installed before 0.1.4, run git fetch --tags here first)"
done < <(find "$STAGE_ROOT/ask-omar" -type f -print0)

ensure_directory "$APP_TARGET"
while IFS= read -r -d '' directory; do
  relative=${directory#"$STAGE_ROOT/ask-omar"/}
  [[ $directory == "$STAGE_ROOT/ask-omar" ]] && continue
  ensure_directory "$APP_TARGET/$relative"
done < <(find "$STAGE_ROOT/ask-omar" -type d -print0)
while IFS= read -r -d '' file; do
  relative=${file#"$STAGE_ROOT/ask-omar"/}
  [[ $relative == "$APP_MANIFEST_NAME" ]] && continue
  install -T -m 644 "$file" "$APP_TARGET/$relative"
done < <(find "$STAGE_ROOT/ask-omar" -type f -print0)
install -T -m 644 \
  "$STAGE_ROOT/ask-omar/$APP_MANIFEST_NAME" "$APP_TARGET/$APP_MANIFEST_NAME"

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

render_launcher cli > "$LAUNCHER_STAGE/ask-omar"

install -T -m 755 "$LAUNCHER_STAGE/ask-omar" "$BIN_HOME/ask-omar"
install -T -m 755 "$ROOT/scripts/ask-omar-open" "$BIN_HOME/ask-omar-open"
install -T -m 755 "$ROOT/scripts/capture.sh" "$BIN_HOME/ask-omar-capture"
install -T -m 644 "$ROOT/systemd/ask-omar.service" "$SERVICE_TARGET"
install -T -m 644 "$ROOT/desktop/ask-omar.desktop" "$DESKTOP_TARGET"
install -T -m 644 "$ROOT/desktop/ask-omar-settings.desktop" "$SETTINGS_DESKTOP_TARGET"

# Record what was just installed so a later setup or uninstall can leave
# anything the user changes since.
for kind in "${LAUNCHER_KINDS[@]}"; do
  read -r digest _ < <(sha256sum < "$(launcher_target "$kind")")
  printf '%s\t%s\n' "$kind" "$digest"
done > "$LAUNCHER_STAGE/$LAUNCHER_MANIFEST_NAME"
install -T -m 644 "$LAUNCHER_STAGE/$LAUNCHER_MANIFEST_NAME" "$PREVIOUS_LAUNCHERS"

systemctl --user daemon-reload
systemctl --user enable ask-omar.service >/dev/null
systemctl --user restart ask-omar.service

echo "Ask Omar backend installed."
printf '%s\n' "$pi_status"
if ask_omar_is_legacy_plugin_copy "$PLUGIN_TARGET"; then
  echo "An older Ask Omar widget copy is still installed at $PLUGIN_TARGET." >&2
  echo "Run make uninstall, then install the widget with omarchy plugin add (see README)." >&2
elif [[ ! -d $PLUGIN_TARGET ]]; then
  echo "Install the widget with: omarchy plugin add https://github.com/chrisjskelton/ask-omar.git"
else
  echo "If the widget is not enabled yet, run: omarchy plugin enable ask-omar.assistant"
  echo "If you updated Ask Omar, run omarchy-restart-shell so the bar loads the new widget."
fi
echo "Check the AI connection with: ask-omar setup"
