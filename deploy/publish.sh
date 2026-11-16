#!/usr/bin/env bash
# Publish to the zerocarbonx.cn server over SSH.
# The website data is not uploaded: the server makes it itself (pipeline/, Zhipu GLM-4-Flash, 06:30 / 18:30; since 2026-11-07),
# or, with grenn-pipeline.timer off, mirrors the original project's output (server/sync-data.sh, every 2 hours).
# The news database (newsdb/) lives on the server too: it merges the upstream data, crawls, and writes /downloads/.
# Usage (Git Bash, from anywhere; this folder is deploy/ in the climate-agent-news repo):
#   deploy/publish.sh            upload server scripts + a new frontend release, switch to it
#   deploy/publish.sh --app      also upload the backend code (climate-agent-news src/ + config/) the news database crawls with
#   deploy/publish.sh --setup    also (re)install nginx, cron, certbot hook, the newsdb user / venv / systemd timers (implies --app)
# Needs the `grenn` host in ~/.ssh/config (key ~/.ssh/aliyun_grenn). Rollback: on the server,
#   /srv/grenn/bin/activate-release.sh /srv/grenn/releases/<previous>
set -euo pipefail
# GRENN_SSH_OPTS: extra ssh options, e.g. "-b <this PC's LAN address>" so the upload skips a global proxy
ssh() { command ssh ${GRENN_SSH_OPTS-} "$@"; }
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
tar -czf - -C "$HERE" --exclude=__pycache__ server newsdb subscriptions pipeline research | ssh "$HOST" 'set -e; mkdir -p /srv/grenn/bin /srv/grenn/conf
  tar -xzf - -C /srv/grenn/conf --strip-components=1
  install -m 755 /srv/grenn/conf/sync-data.sh /srv/grenn/conf/activate-release.sh /srv/grenn/conf/grenn_newsdb.py /srv/grenn/conf/grenn_brief.py /srv/grenn/conf/grenn_visits.py /srv/grenn/conf/grenn_regions.py /srv/grenn/bin/
  install -m 755 /srv/grenn/conf/grenn-pipeline.sh /srv/grenn/conf/grenn_glm.py /srv/grenn/bin/
  # 每日气候通讯 fonts (FangSong_GB2312.ttf, timesbd.ttf) are commercial: uploaded by hand to /srv/grenn/app/fonts/
  # (not served by nginx, not in this repository) — see deploy/README.md
  install -d /srv/grenn/app/fonts
  install -m 755 /srv/grenn/conf/grenn-newsdb /usr/local/bin/grenn-newsdb
  # weekly-briefing subscriptions (deploy/subscriptions); the service picks up a new script on restart
  install -m 755 /srv/grenn/conf/grenn_subscriptions.py /srv/grenn/bin/
  install -m 755 /srv/grenn/conf/grenn-subscriptions /usr/local/bin/grenn-subscriptions
  systemctl try-restart grenn-subscriptions.service 2>/dev/null || true  # not installed before the first --setup
  # research index API (deploy/research, 2026-11-13): the script and the 14 x 83 dictionary it reads beside itself
  install -m 755 /srv/grenn/conf/grenn_research.py /srv/grenn/bin/
  install -m 644 /srv/grenn/conf/grenn_research_taxonomy.json /srv/grenn/bin/
  install -m 755 /srv/grenn/conf/grenn-research /usr/local/bin/grenn-research
  systemctl try-restart grenn-research.service 2>/dev/null || true
  # the governance labelling rules grenn_newsdb.py imports (copied from the 2026-11-05 history handover)
  rm -rf /srv/grenn/bin/.grenn_governance.new && cp -r /srv/grenn/conf/grenn_governance /srv/grenn/bin/.grenn_governance.new
  python3 -m compileall -q /srv/grenn/bin/.grenn_governance.new && rm -rf /srv/grenn/bin/grenn_governance && mv /srv/grenn/bin/.grenn_governance.new /srv/grenn/bin/grenn_governance'

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
# brotli for nginx (grenn-site.conf) and the command line (sync-data.sh / grenn_newsdb.py precompress with it)
dpkg -s libnginx-mod-http-brotli-static >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y -q brotli libnginx-mod-http-brotli-filter libnginx-mod-http-brotli-static
install -m 644 /srv/grenn/conf/grenn-site.conf /etc/nginx/snippets/grenn-site.conf
if [[ -e /etc/letsencrypt/live/zerocarbonx.cn/fullchain.pem ]]; then conf=nginx-zerocarbonx.conf; else conf=nginx-bootstrap.conf; fi
install -m 644 "/srv/grenn/conf/$conf" /etc/nginx/sites-available/zerocarbonx
ln -sfn /etc/nginx/sites-available/zerocarbonx /etc/nginx/sites-enabled/zerocarbonx
rm -f /etc/nginx/sites-enabled/default
printf '%s\n' 'SHELL=/bin/bash' '17 */2 * * * root /srv/grenn/bin/sync-data.sh 2>&1 | systemd-cat -t grenn-sync' > /etc/cron.d/grenn-sync
printf '%s\n' '#!/bin/sh' 'systemctl reload nginx' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
# group datasets (/datasets/): one shared login, made once; the password stays readable by root only
if [[ ! -s /etc/nginx/grenn-datasets.htpasswd ]]; then
  pass=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-16)
  printf 'grenn:%s\n' "$(openssl passwd -apr1 "$pass")" > /etc/nginx/grenn-datasets.htpasswd
  chown root:www-data /etc/nginx/grenn-datasets.htpasswd && chmod 640 /etc/nginx/grenn-datasets.htpasswd
  printf 'https://zerocarbonx.cn/datasets/\nuser: grenn\npassword: %s\n' "$pass" > /root/grenn-datasets-credentials.txt
  chmod 600 /root/grenn-datasets-credentials.txt
fi

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

# weekly-briefing subscriptions: private list folder, root-only SMTP settings (filled in by hand), service + Monday timer
install -d -o grenn -g grenn -m 700 /srv/grenn/subscriptions
[[ -e /srv/grenn/subscriptions/smtp.env ]] || install -m 600 -o root -g root /srv/grenn/conf/smtp.env.example /srv/grenn/subscriptions/smtp.env
install -m 644 /srv/grenn/conf/grenn-limits.conf /etc/nginx/conf.d/grenn-limits.conf
install -m 644 /srv/grenn/conf/grenn-subscriptions.service /srv/grenn/conf/grenn-subscriptions-weekly.service   /srv/grenn/conf/grenn-subscriptions-weekly.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now grenn-subscriptions.service grenn-subscriptions-weekly.timer

# research index API (research/, 2026-11-13): the index is derived from the news database (rebuilt after each update,
# grenn-newsdb-update.service ExecStartPost); reviewed positions are filed by hand (grenn-research claims)
install -d -o grenn -g grenn -m 755 /srv/grenn/newsdb/research
install -m 644 /srv/grenn/conf/grenn-research.service /etc/systemd/system/
systemctl daemon-reload
[[ -s /srv/grenn/newsdb/research/index.sqlite ]] || /usr/local/bin/grenn-research sync
systemctl enable --now grenn-research.service

# site data pipeline (pipeline/, 2026-11-07): the repo copy and the model settings are put in place by hand (README);
# the timer is switched on once both exist, and while it is on the cron sync no longer mirrors the original repo
install -d -o grenn -g grenn -m 755 /srv/grenn/pipeline
install -d -o grenn -g grenn -m 750 /srv/grenn/pipeline/state
install -d -o root -g grenn -m 750 /srv/grenn/secrets
install -m 644 /srv/grenn/conf/grenn-pipeline.service /srv/grenn/conf/grenn-pipeline.timer /etc/systemd/system/
systemctl daemon-reload
if [[ -f /srv/grenn/pipeline/repo/pyproject.toml && -f /srv/grenn/secrets/model.env ]]; then systemctl enable --now grenn-pipeline.timer; fi

nginx -t && systemctl reload nginx
echo "nginx: $conf"
EOF
fi

echo "== release $name"
tar -czf - -C "$REPO/static" --exclude=./data . | ssh "$HOST" "mkdir -p /srv/grenn/releases/$name && tar -xzf - -C /srv/grenn/releases/$name && /srv/grenn/bin/activate-release.sh /srv/grenn/releases/$name"
