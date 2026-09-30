#!/usr/bin/env bash
# Installed by Ask Omar

ask_omar_has_marker() {
  local path=$1
  [[ -f $path && ! -L $path ]] && grep -Fxq '# Installed by Ask Omar' "$path"
}

ask_omar_matches_legacy_cli() {
  local path=$1
  [[ -f $path && ! -L $path ]] || return 1
  cmp -s "$path" <(printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}' \
    'export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:/usr/local/bin:/usr/bin${PATH:+:$PATH}"' \
    'export PYTHONPATH="$DATA_HOME/ask-omar/service${PYTHONPATH:+:$PYTHONPATH}"' \
    'exec python -m ask_omar "$@"')
}

ask_omar_matches_source_without_marker() {
  local path=$1 source=$2
  [[ -f $path && ! -L $path ]] || return 1
  cmp -s "$path" <(sed '/^# Installed by Ask Omar$/d' "$source")
}

ask_omar_matches_sha256() {
  local path=$1 expected=$2 actual
  [[ -f $path && ! -L $path ]] || return 1
  command -v sha256sum >/dev/null || return 1
  read -r actual _ < <(sha256sum < "$path")
  [[ $actual == "$expected" ]]
}

ask_omar_owns_app_directory() {
  local path=$1 init guard
  [[ -d $path && ! -L $path ]] || return 1
  ask_omar_has_marker "$path/.installed-by-ask-omar" && return 0

  init="$path/service/ask_omar/__init__.py"
  guard="$path/extensions/ask-omar-guard.ts"
  if ask_omar_matches_sha256 "$init" "99f685c4490a478c5f010859d3bd635dfb1c73b59fc207fad499aeb7dbc19735"; then
    ask_omar_matches_sha256 "$guard" "f7f0696e3809b7ff3f3494f79bbd7d6f1192100af3d98603a0e87bdb7699f0e0"
  elif ask_omar_matches_sha256 "$init" "a57da2d68176ae3cc78f3166e43f9a06f831f4fbbd3fe76064f1af535902462d"; then
    ask_omar_matches_sha256 "$guard" "0ee811d84d020ee40d970ba288b8618ae8f7b75bd339ec02ddbeb4af4a558fc9"
  else
    return 1
  fi
}

# Before 0.1.4 the service wrote Python bytecode next to its installed modules,
# and uninstall (which removes only recorded files) left those caches behind.
# A directory holding nothing but them is safe to install into: setup only adds
# known files and never deletes anything there.
ask_omar_is_bytecode_residue() {
  local path=$1 kind relative
  [[ -d $path && ! -L $path && -r $path && -x $path ]] || return 1
  while IFS=$'\t' read -r -d '' kind relative; do
    case $kind in
      d) [[ $relative == service || $relative == service/ask_omar ||
            $relative == service/ask_omar/* ]] || return 1 ;;
      f) [[ ( $relative == service/ask_omar/*.pyc && ${relative%/*} == */__pycache__ ) ||
            $relative == .installed-launchers.sha256 ]] || return 1 ;;
      *) return 1 ;;
    esac
  done < <(find "$path" -mindepth 1 \
    \( -type d ! \( -readable -executable \) -printf 'unreadable\t%P\0' -prune \) -o \
    -printf '%y\t%P\0')
}

ask_omar_valid_app_manifest() {
  local path=$1 hash relative extra
  [[ -f $path && ! -L $path ]] || return 1
  while IFS=$'\t' read -r hash relative extra || [[ -n ${hash}${relative}${extra} ]]; do
    [[ $hash =~ ^[0-9a-f]{64}$ && -n $relative && -z $extra ]] || return 1
    [[ $relative != /* && $relative != . && $relative != .. ]] || return 1
    [[ $relative != */ && $relative != *//* ]] || return 1
    [[ /$relative/ != *'/../'* && /$relative/ != *'/./'* ]] || return 1
  done < "$path"
}

# Setup records the hash of each launcher, the service unit and the two menu
# entries it installs, one "kind<TAB>hash" line each, so a later setup or
# uninstall can tell an untouched file from one the user has edited.
ask_omar_valid_launcher_manifest() {
  local path=$1 kind hash extra
  [[ -f $path && ! -L $path ]] || return 1
  while IFS=$'\t' read -r kind hash extra || [[ -n ${kind}${hash}${extra} ]]; do
    case $kind in
      cli | open | capture | service | desktop | settings-desktop) ;;
      *) return 1 ;;
    esac
    [[ $hash =~ ^[0-9a-f]{64}$ && -z $extra ]] || return 1
  done < "$path"
}

ask_omar_recorded_launcher_hash() {
  local manifest=$1 kind=$2
  awk -F '\t' -v kind="$kind" '$1 == kind { print $2; found = 1; exit } END { exit !found }' \
    "$manifest"
}

# Before 0.1.4, `make install` copied the widget into Omarchy's plugin folder.
# Since 0.1.4 the plugin folder is always a Git checkout, so this list of the
# copied releases (0.1.0-0.1.3) is complete and never needs new entries.
ask_omar_owns_plugin_file() {
  local path=$1 relative=$2 root=$3
  [[ -f $path && ! -L $path ]] || return 1
  cmp -s "$path" "$root/$relative" && return 0
  case "$relative" in
    manifest.json)
      ask_omar_matches_sha256 "$path" "5f55b563be14abe2e979f7da785554487b4875c5a7665596ae1c7e41e6f3c3b0" ||
        ask_omar_matches_sha256 "$path" "21b9613934ba088b41fb0c56fde7b84e0e009de7e96bef60e2bdd6ada3140c2f" ||
        ask_omar_matches_sha256 "$path" "8d3330d4bce61e084baf297b33dd71577815d86b1eb9cb7fd62ecf646b4a63ba" ||
        ask_omar_matches_sha256 "$path" "d237b1ab2f45f6bbed065251403f2c4ca1128ae389f185261e5c8f47832dee0a"
      ;;
    plugin/AskOmar.qml)
      ask_omar_matches_sha256 "$path" "3d6855a37cd779cc97af4e16d19e5bfa5c3eac50fd05b6b8f200afb53081d84b" ||
        ask_omar_matches_sha256 "$path" "1dfa8a34fad656345fb1ab06b6a37b16950a247acaebb3625798c45be0c20e55"
      ;;
    *) return 1 ;;
  esac
}

ask_omar_owns_file() {
  local path=$1 kind=$2 root=$3
  ask_omar_has_marker "$path" && return 0
  case "$kind" in
    cli) ask_omar_matches_legacy_cli "$path" ;;
    open) ask_omar_matches_source_without_marker "$path" "$root/scripts/ask-omar-open" ;;
    capture)
      ask_omar_matches_source_without_marker "$path" "$root/scripts/capture.sh" ||
        ask_omar_matches_sha256 "$path" "28f2856a946b6d4296187da735820e13c3f7071de89889a19edeb9dd0525a051"
      ;;
    service) ask_omar_matches_source_without_marker "$path" "$root/systemd/ask-omar.service" ;;
    desktop) ask_omar_matches_source_without_marker "$path" "$root/desktop/ask-omar.desktop" ;;
    settings-desktop) ask_omar_matches_source_without_marker "$path" "$root/desktop/ask-omar-settings.desktop" ;;
    *) return 1 ;;
  esac
}

# A pre-0.1.4 copied widget: an ordinary plugin directory, not a Git checkout.
ask_omar_is_legacy_plugin_copy() {
  local path=$1
  [[ -d $path && ! -L $path && ! -e $path/.git ]] || return 1
  [[ -f $path/manifest.json ]] && grep -q '"ask-omar.assistant"' "$path/manifest.json"
}
