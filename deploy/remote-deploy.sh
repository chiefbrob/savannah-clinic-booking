#!/usr/bin/env bash
# Runs on the production host, invoked over SSH by .github/workflows/deploy.yml.
# Pulls the merged commit, installs dependencies, migrates, restarts, verifies.
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/clinic-booking}"
PORT="${PORT:-8100}"
BRANCH="${BRANCH:-main}"

cd "$APP_DIR"

echo "==> fetching origin/$BRANCH"
git fetch --prune origin "$BRANCH"
git reset --hard "origin/$BRANCH"

echo "==> installing dependencies"
.venv/bin/pip install -q -r requirements.txt

echo "==> applying migrations"
.venv/bin/alembic upgrade head

echo "==> syncing nginx config"
if ! cmp -s deploy/nginx.conf /etc/nginx/sites-available/clinic-booking; then
    cp deploy/nginx.conf /etc/nginx/sites-available/clinic-booking
    nginx -t
    systemctl reload nginx
    echo "    nginx updated"
fi

echo "==> restarting service"
systemctl restart clinic-booking.service
systemctl is-active --quiet clinic-booking.service

echo "==> verifying"
for _ in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
        echo "healthy on 127.0.0.1:${PORT}"
        exit 0
    fi
    sleep 1
done

echo "service did not become healthy" >&2
systemctl status clinic-booking.service --no-pager >&2 || true
journalctl -u clinic-booking.service -n 40 --no-pager >&2 || true
exit 1
