#!/usr/bin/env bash
# Install personal Rust binaries system-wide via each repo's justfile.
#
#   just install --system  →  /usr/local/bin  (sudo; build=release+upx)
#
# Usage (from anywhere):
#   ./install-system-bins.sh
#   PASSFILE=/path/to/pass ./install-system-bins.sh
#   ROOT=/srv/project/personal ./install-system-bins.sh
#
# Expects a password file (default: sibling `pass` next to this script) containing
# the sudo password for the current user, single line. Fed to `sudo -S` only —
# never printed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(dirname "$SCRIPT_DIR")}"
PASSFILE="${PASSFILE:-$SCRIPT_DIR/pass}"

# Installable binary crates on the shared justfile baseline (JUST.md).
# Excluded: nvprime / compose-utils (L2 systemd — use setup/teardown in-repo).
REPOS=(
  zentools
  frontmatter-mcp
  stash-mcp
  pika
  vicuna
  media-forge
  llama.rs
  wsmr
  tei-proxy
  dotlinker
)

die() {
  echo "error: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

sudo_unlock() {
  # Refresh sudo timestamp using the pass file (no echo of the secret).
  # Trailing newline required by sudo -S.
  local pw
  pw="$(tr -d '\r' <"$PASSFILE")"
  # ensure exactly one trailing newline
  printf '%s\n' "${pw%$'\n'}" | sudo -S -v 2>/dev/null \
    || die "sudo rejected password from $PASSFILE (wrong/stale password?)"
}

main() {
  need_cmd just
  need_cmd sudo
  need_cmd cargo
  need_cmd upx

  [[ -f "$PASSFILE" ]] || die "pass file not found: $PASSFILE"
  [[ -s "$PASSFILE" ]] || die "pass file is empty: $PASSFILE"
  [[ -d "$ROOT" ]] || die "project root not found: $ROOT"

  echo "root:     $ROOT"
  echo "passfile: $PASSFILE"
  echo "repos:    ${REPOS[*]}"
  echo

  sudo_unlock

  local fail=0
  local r
  for r in "${REPOS[@]}"; do
    local dir="$ROOT/$r"
    echo "########################################"
    echo "# just install --system  →  $r"
    echo "########################################"
    if [[ ! -d "$dir" ]]; then
      echo "FAIL $r (missing dir: $dir)"
      fail=1
      echo
      continue
    fi
    if [[ ! -f "$dir/justfile" ]]; then
      echo "FAIL $r (no justfile)"
      fail=1
      echo
      continue
    fi

    # Long release builds can outlive the sudo stamp — refresh each repo.
    sudo_unlock

    if (
      cd "$dir"
      just install --system
    ); then
      echo "OK $r"
    else
      echo "FAIL $r"
      fail=1
    fi
    echo
  done

  echo "=== /usr/local/bin ==="
  local bins=(
    zentools zen-epp zen-smu zen-mem
    frontmatter frontmatter-mcp
    stash-mcp pika vicuna media-forge llama wsmr tei-proxy dot-rs
  )
  local b
  for b in "${bins[@]}"; do
    if [[ -e "/usr/local/bin/$b" ]]; then
      ls -la "/usr/local/bin/$b"
    else
      echo "MISSING $b"
    fi
  done
  echo

  if [[ "$fail" -ne 0 ]]; then
    die "one or more installs failed"
  fi
  echo "All installs succeeded."
}

main "$@"
