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
  read -r actual _ < <(sha256sum -- "$path")
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
