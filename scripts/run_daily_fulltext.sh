#!/usr/bin/env bash
# Run from cron or manually; NEVER invoke with bash -x (environment is private).
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
if [ -f /etc/green-daily-fulltext.env ]; then
  set -a
  . /etc/green-daily-fulltext.env
  set +a
fi
PYTHON="${GREEN_PYTHON:-.venv/bin/python}"
mkdir -p data/private_daily_fulltext
exec 9>data/private_daily_fulltext/run.lock
flock -n 9 || exit 0
export PYTHONPATH=src
"$PYTHON" scripts/prepare_daily_fulltext.py
"$PYTHON" scripts/daily_fulltext_v2.py --input data/private_daily_fulltext/input.json --require-target
