#!/usr/bin/env bash
#
# sync.sh — sync this repo's config to/from the hobbiton server.
#
#   ./sync.sh diff      Dry run: what `deploy` would change on the server.
#   ./sync.sh deploy    Lint YAML → rsync local→server → (for HA changes) validate → reload.
#   ./sync.sh pull      rsync server→local to capture UI-made changes (mainly Home Assistant).
#   ./sync.sh check     Validate the Home Assistant config currently on the server (read-only).
#
# Transport is rsync over `ssh hobbiton`, scoped to the files git would track
# (tracked + untracked-but-not-ignored), so secrets (.envrc), Pi-hole runtime
# data, HA's .storage/DB/logs, etc. are never touched. Git is NOT part of
# syncing — commit & push to GitHub yourself whenever you want a backup point.
#
# Needs a Home Assistant long-lived token in $HA_TOKEN, loaded from .envrc via
# direnv (run `direnv allow` once). Add -y / --yes to skip the confirm prompt.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
HA_URL="${HA_URL:-http://192.168.0.81:8123}"
SSH_HOST="${SSH_HOST:-hobbiton}"
REMOTE_DIR="${REMOTE_DIR:-hobbiton}"   # path to the repo on the server, relative to its home

RSYNC_OPTS=(-rc --no-owner --no-group --no-perms)  # -c: compare by content checksum, ignore mtime skew
ASSUME_YES=0

# Everything git considers part of the repo (tracked + untracked, minus .gitignore'd).
# Paths are relative to REPO_ROOT — exactly what rsync --files-from wants.
manifest() { git -C "$REPO_ROOT" ls-files --cached --others --exclude-standard; }

die() { echo "✗ $*" >&2; exit 1; }

require_token() {
  [ -n "${HA_TOKEN:-}" ] || die "HA_TOKEN not set — is direnv active here? Run: direnv allow $REPO_ROOT"
}

confirm() {
  [ "$ASSUME_YES" = 1 ] && return 0
  printf '%s [y/N] ' "$1"; read -r reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

# Quick local syntax check. HA's custom tags (!include, !secret, …) are treated
# as no-ops, so this checks well-formedness only, not semantics.
lint() {
  echo "› linting YAML locally…"
  manifest | grep '\.yaml$' | while IFS= read -r f; do
    python3 - "$REPO_ROOT/$f" <<'PY' || die "YAML syntax error in $f"
import sys, yaml
class L(yaml.SafeLoader): pass
L.add_multi_constructor('!', lambda loader, suffix, node: None)
with open(sys.argv[1]) as fh:
    yaml.load(fh, Loader=L)
PY
  done
  echo "  ok"
}

api() { # api METHOD PATH
  curl -fsS -X "$1" "$HA_URL$2" \
    -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d '{}'
}

check() {
  require_token
  echo "› validating Home Assistant config on server ($HA_URL)…"
  local resp result
  resp="$(api POST /api/config/core/check_config)" \
    || die "could not reach HA at $HA_URL (token valid? server up?)"
  result="$(printf '%s' "$resp" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("result",""))')"
  if [ "$result" = "valid" ]; then echo "  ✓ config valid"; return 0; fi
  echo "  ✗ config INVALID:" >&2
  printf '%s' "$resp" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("errors") or d.get("warnings") or d)' >&2
  return 1
}

reload() {
  echo "› reloading Home Assistant (reload_all)…"
  api POST /api/services/homeassistant/reload_all >/dev/null
  echo "  ✓ reloaded"
}

rsync_files() { # rsync_files SRC DEST [extra opts...]
  local src="$1" dest="$2"; shift 2
  rsync "${RSYNC_OPTS[@]}" "$@" --files-from=<(manifest) "$src" "$dest"
}

# Dry-run list of files whose *content* would actually transfer SRC→DEST
# (drops attribute-only and directory lines from rsync's itemize output).
changeset() { rsync_files "$1" "$2" -ni | grep -Ev '^(\.|$)' || true; }

deploy() {
  lint
  echo "› changes to push to $SSH_HOST:"
  local changes
  changes="$(changeset "$REPO_ROOT/" "$SSH_HOST:$REMOTE_DIR/")"
  if [ -z "$changes" ]; then echo "  (nothing to deploy — server already matches)"; return 0; fi
  echo "$changes" | sed 's/^/  /'
  confirm "Push these to the server?" || die "aborted"
  rsync_files "$REPO_ROOT/" "$SSH_HOST:$REMOTE_DIR/" -v

  # Home Assistant config: validate before reloading; a broken config never goes live.
  if grep -q 'homeassistant/config/' <<<"$changes"; then
    require_token
    check || die "server config invalid — NOT reloading; the previous config keeps running"
    reload
  fi

  # Activation steps rsync can't do — flag the ones that apply.
  if grep -Eq 'homeassistant/config/configuration.yaml|homeassistant/docker-compose.yml' <<<"$changes"; then
    echo "⚠ HA core/compose changed — reload_all may miss new integrations/platforms. If so:"
    echo "    ssh $SSH_HOST 'cd $REMOTE_DIR/homeassistant && docker-compose up -d'"
  fi
  grep -q 'pihole/' <<<"$changes" && \
    echo "⚠ Pi-hole changed — apply with: ssh $SSH_HOST 'cd $REMOTE_DIR/pihole && docker-compose up -d'"
  grep -q 'autossh/' <<<"$changes" && \
    echo "⚠ autossh unit changed — install to /etc/systemd/system/ on the server, then: sudo systemctl daemon-reload && sudo systemctl restart autotunnel"
  return 0
}

pull() {
  echo "› changes the server would bring into your working tree:"
  local changes
  changes="$(changeset "$SSH_HOST:$REMOTE_DIR/" "$REPO_ROOT/")"
  if [ -z "$changes" ]; then echo "  (nothing to pull — local already matches server)"; return 0; fi
  echo "$changes" | sed 's/^/  /'
  confirm "Pull these into your working tree?" || die "aborted"
  rsync_files "$SSH_HOST:$REMOTE_DIR/" "$REPO_ROOT/" -v
  echo "› done. Review with: git -C $REPO_ROOT diff   (then commit/push to GitHub when ready)"
}

main() {
  local cmd="${1:-}"; shift || true
  for arg in "$@"; do case "$arg" in -y|--yes) ASSUME_YES=1 ;; esac; done
  case "$cmd" in
    diff)   c="$(changeset "$REPO_ROOT/" "$SSH_HOST:$REMOTE_DIR/")"; echo "${c:-(in sync — server matches local)}" ;;
    deploy) deploy ;;
    pull)   pull ;;
    check)  check ;;
    *) sed -n '3,15p' "$0"; exit 1 ;;
  esac
}

main "$@"
