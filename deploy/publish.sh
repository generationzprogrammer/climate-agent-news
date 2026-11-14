#!/usr/bin/env bash
# Publish to the zerocarbonx.cn server over SSH.
# The website data is not uploaded: the server mirrors it from the GitHub Pages site (server/sync-data.sh, every 2 hours).
# The news database (newsdb/) lives on the server too: it merges the upstream data, crawls, and writes /downloads/.
# Usage (Git Bash, from anywhere; this folder is deploy/ in the climate-agent-news repo):
#   deploy/publish.sh            upload server scripts + a new frontend release, switch to it
#   deploy/publish.sh --app      also upload the backend code (climate-agent-news src/ + config/) the news database crawls with
#   deploy/publish.sh --setup    also (re)install nginx, cron, certbot hook, the newsdb user / venv / systemd timers (implies --app)
# Needs the `grenn` host in ~/.ssh/config (key ~/.ssh/aliyun_grenn). Rollback: on the server,
#   /srv/grenn/bin/activate-release.sh /srv/grenn/releases/<previous>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO="$HERE/.."
HOST=${GRENN_HOST:-grenn}
SETUP=0; APP=0
for arg in "$@"; do
  case "$arg" in
    --setup) SETUP=1; APP=1 ;;
    --app) APP=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

rev=$(git -C "$REPO" rev-parse --short HEAD)
if [[ -n "$(git -C "$REPO" status --porcelain -- static ':!static/data')" ]]; then
  echo "note: static/ has uncommitted changes — they are published as they are on disk"
fi
name=$(date +%Y%m%d-%H%M%S)-$rev

echo "== server scripts"
tar -czf - -C "$HERE" --exclude=__pycache__ server newsdb | ssh "$HOST" 'set -e; mkdir -p /srv/grenn/bin /srv/grenn/conf
  tar -xzf - -C /srv/grenn/conf --strip-components=1
  install -m 755 /srv/grenn/conf/sync-data.sh /srv/grenn/conf/activate-release.sh /srv/grenn/conf/grenn_newsdb.py /srv/grenn/bin/
  install -m 755 /srv/grenn/conf/grenn-newsdb /usr/local/bin/grenn-newsdb'

if (( APP )); then
  echo "== backend code $rev (for the newsdb crawler)"
  tar -czf - -C "$REPO" --exclude=__pycache__ pyproject.toml src/climate_agent config | ssh "$HOST" "set -e
    mkdir -p /srv/grenn/app/releases/$name && tar -xzf - -C /srv/grenn/app/releases/$name
    python3 -m compileall -q /srv/grenn/app/releases/$name/src  # the services see /srv read-only
    ln -sfn releases/$name /srv/grenn/app/.current.tmp && mv -T /srv/grenn/app/.current.tmp /srv/grenn/app/current
    cd /srv/grenn/app/releases && ls -1 | sort | head -n -3 | xargs -r rm -rf"
fi

if (( SETUP )); then
  echo "== nginx, cron, certbot hook, newsdb"
  ssh "$HOST" 'bash -s' <<'EOF'
set -euo pipefail
mkdir -p /var/www/letsencrypt /srv/grenn/releases /srv/grenn/data /etc/letsencrypt/renewal-hooks/deploy
install -m 644 /srv/grenn/conf/grenn-site.conf /etc/nginx/snippets/grenn-site.conf
if [[ -e /etc/letsencrypt/live/zerocarbonx.cn/fullchain.pem ]]; then conf=nginx-zerocarbonx.conf; else conf=nginx-bootstrap.conf; fi
install -m 644 "/srv/grenn/conf/$conf" /etc/nginx/sites-available/zerocarbonx
ln -sfn /etc/nginx/sites-available/zerocarbonx /etc/nginx/sites-enabled/zerocarbonx
rm -f /etc/nginx/sites-enabled/default
printf '%s\n' 'SHELL=/bin/bash' '17 */2 * * * root /srv/grenn/bin/sync-data.sh 2>&1 | systemd-cat -t grenn-sync' > /etc/cron.d/grenn-sync
printf '%s\n' '#!/bin/sh' 'systemctl reload nginx' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# news database: service user, folders (public/ is what nginx serves), Python venv with the backend's dependencies
id grenn >/dev/null 2>&1 || useradd --system --home-dir /srv/grenn/newsdb --shell /usr/sbin/nologin grenn
install -d -o grenn -g grenn -m 755 /srv/grenn/newsdb
install -d -o grenn -g grenn -m 750 /srv/grenn/newsdb/backups
python3 -c 'import ensurepip' 2>/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-venv
[[ -x /srv/grenn/app/venv/bin/python ]] || python3 -m venv /srv/grenn/app/venv
deps=$(python3 -c 'import tomllib,sys; print(" ".join(tomllib.load(open("/srv/grenn/app/current/pyproject.toml","rb"))["project"]["dependencies"]))')
/srv/grenn/app/venv/bin/pip install -q --disable-pip-version-check $deps
install -m 644 /srv/grenn/conf/grenn-newsdb-update.service /srv/grenn/conf/grenn-newsdb-update.timer \
  /srv/grenn/conf/grenn-newsdb-backup.service /srv/grenn/conf/grenn-newsdb-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now grenn-newsdb-update.timer grenn-newsdb-backup.timer

nginx -t && systemctl reload nginx
echo "nginx: $conf"
EOF
fi

echo "== release $name"
tar -czf - -C "$REPO/static" --exclude=./data . | ssh "$HOST" "mkdir -p /srv/grenn/releases/$name && tar -xzf - -C /srv/grenn/releases/$name && /srv/grenn/bin/activate-release.sh /srv/grenn/releases/$name"
