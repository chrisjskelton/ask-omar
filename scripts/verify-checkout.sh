#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
expected=${ASK_OMAR_COMMIT:-}

if [[ ! $expected =~ ^[0-9a-f]{40}$ ]]; then
  echo "ASK_OMAR_COMMIT must be the full 40-character commit from the release notes." >&2
  exit 1
fi

actual=$(git -C "$ROOT" rev-parse --verify 'HEAD^{commit}' 2>/dev/null) || {
  echo "Ask Omar must be installed from a Git checkout." >&2
  exit 1
}
if [[ $actual != "$expected" ]]; then
  echo "Ask Omar checkout is at $actual, not the required commit $expected." >&2
  exit 1
fi

if [[ -n $(git -C "$ROOT" status --porcelain --untracked-files=all) ]]; then
  echo "Ask Omar checkout has modified or untracked files; refusing to install." >&2
  exit 1
fi

echo "Verified Ask Omar checkout at $expected."
