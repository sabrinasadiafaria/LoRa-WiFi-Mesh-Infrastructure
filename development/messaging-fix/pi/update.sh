#!/usr/bin/env bash
#
# update.sh - pull the latest from upstream and (if installed) restart
# the running service. Run this on the Pi whenever you push to main
# and want the dashboard to reflect the change.
#
# Usage:
#   bash update.sh                 # git pull + restart if systemd unit exists
#   bash update.sh --no-restart    # git pull only (manual restart later)
#   bash update.sh --check         # show what would be updated, don't change anything
#
set -euo pipefail

cd "$(dirname "$0")"

DO_RESTART=1
DRY_RUN=0

for arg in "$@"; do
    case "$arg" in
        --no-restart) DO_RESTART=0 ;;
        --check)      DRY_RUN=1 ;;
        -h|--help)
            sed -n '2,12p' "$0"
            exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

echo ">>> git fetch + status"
git fetch --quiet origin

UPSTREAM="${1:-}"
if [ -z "$UPSTREAM" ]; then
    UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
fi

if [ -z "$UPSTREAM" ]; then
    # No upstream set (fresh clone?) - guess main
    UPSTREAM="origin/main"
fi

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "$UPSTREAM")"

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "    already up to date ($LOCAL)"
else
    echo "    local  : $LOCAL"
    echo "    remote : $REMOTE"
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "    --check: would run 'git pull --ff-only'"
        git --no-pager log --oneline "$LOCAL..$REMOTE" || true
        exit 0
    fi
    echo ">>> git pull --ff-only"
    git pull --ff-only
fi

if [ "$DRY_RUN" -eq 1 ]; then
    exit 0
fi

# Re-install requirements if requirements.txt is newer than venv marker.
if [ -f requirements.txt ] && [ -d venv ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
    if [ requirements.txt -nt venv/pyvenv.cfg ]; then
        echo ">>> requirements.txt changed - pip install"
        pip install -r requirements.txt
    fi
fi

if [ "$DO_RESTART" -eq 0 ]; then
    echo ">>> --no-restart: skipping service restart"
    exit 0
fi

if ! command -v systemctl >/dev/null 2>&1; then
    echo ">>> no systemctl on this host; nothing to restart"
    echo "    run manually:  python3 main.py"
    exit 0
fi

if ! systemctl list-unit-files sar-pi.service >/dev/null 2>&1; then
    echo ">>> sar-pi.service is not installed; nothing to restart"
    echo "    start manually:  python3 main.py --fake-radio"
    exit 0
fi

if ! systemctl is-active --quiet sar-pi; then
    echo ">>> sar-pi.service is installed but not active"
    echo "    start it with:  sudo systemctl start sar-pi"
    exit 0
fi

echo ">>> sudo systemctl restart sar-pi"
sudo systemctl restart sar-pi
sleep 1
echo "    status: $(systemctl is-active sar-pi)   journal: journalctl -u sar-pi -n 30"
