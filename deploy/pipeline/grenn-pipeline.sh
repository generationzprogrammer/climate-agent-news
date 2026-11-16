#!/usr/bin/env bash
# The original project's daily update (.github/workflows/pages.yml, scheduled run), on this server (2026-11-07):
# crawl → collect source texts → compile Chinese/English summaries with Zhipu's free GLM-4-Flash (glm-4-flash-250414
# on open.bigmodel.cn, through grenn_glm.py, in place of Gemini) → export the site data → quality gate.
# grenn-pipeline.service then hands repo/site/data to sync-data.sh --from, which validates it, re-typesets the brief
# and switches /srv/grenn/data/current.
# Since 2026-11-05 the original repo is private: its site data cannot be mirrored without the owner's token.
# 2026-11-10 (it is public again; user: 每次先取原项目数据): every run first takes the original repo's latest main
# (its code and data/ — its own crawl of all its sources, with the Gemini summaries) when it has a new commit, so this
# server only adds what was published since and GLM compiles only articles still without a summary (grenn_glm.py).
#   /srv/grenn/pipeline/repo         a copy of the original repo (code + data/), replaced by each new upstream commit
#                                    (.upstream-commit); when the original cannot be reached it carries on with this copy
#   /srv/grenn/pipeline/state/       model request ledger (CLIMATE_MODEL_DAILY_REQUEST_LIMIT requests per day)
#   /srv/grenn/secrets/model.env     CLIMATE_MODEL_BASE_URL / _API_KEY / _NAME (root:grenn 640, written by hand)
# Differences from the workflow: only the sources this server can reach are crawled (no Google News, Guardian, BBC);
# the historical-corpus translation and the stance pilot are skipped (both accept only the free Gemini model);
# no visitor statistics (Cloudflare) and no git commit.
# Usage: grenn-pipeline.sh [--skip-crawl]      (run as grenn; timer 06:30 / 18:30 like the original)
set -euo pipefail
HOME_DIR=${GRENN_PIPELINE_HOME:-/srv/grenn/pipeline}
REPO=$HOME_DIR/repo
PY=/srv/grenn/app/venv/bin/python
GLM=${GRENN_GLM:-/srv/grenn/bin/grenn_glm.py}
CRAWL=1
for arg in "$@"; do
  case "$arg" in
    --skip-crawl) CRAWL=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
UPSTREAM=${GRENN_UPSTREAM_REPO:-generationzprogrammer/climate-agent-news}
# the original's newest commit: its tarball replaces the copy (a failed or partial download leaves the copy alone)
head=$(curl -fsS --retry 2 --connect-timeout 20 -m 60 -H "Accept: application/vnd.github.sha" "https://api.github.com/repos/$UPSTREAM/commits/main" 2>/dev/null || true)
if [[ $head =~ ^[0-9a-f]{40}$ ]] && [[ "$(cat "$REPO/.upstream-commit" 2>/dev/null)" != "$head" ]]; then
  fresh=$HOME_DIR/.repo.new
  rm -rf "$fresh" && mkdir -p "$fresh"
  if curl -fsS --retry 3 --retry-delay 10 --connect-timeout 20 -m 900 "https://codeload.github.com/$UPSTREAM/tar.gz/$head" | tar -xz -C "$fresh" --strip-components=1 \
      && [[ -f $fresh/pyproject.toml && -s $fresh/data/climate.db ]]; then
    echo "$head" > "$fresh/.upstream-commit"
    rm -rf "$HOME_DIR/.repo.old"; [[ -e $REPO ]] && mv "$REPO" "$HOME_DIR/.repo.old"; mv "$fresh" "$REPO"; rm -rf "$HOME_DIR/.repo.old"
    echo "== upstream ${head:0:7}: copy replaced"
  else
    rm -rf "$fresh"; echo "== upstream ${head:0:7}: download failed, carrying on with the copy"
  fi
else
  echo "== upstream ${head:0:7}: ${head:+no new commit}${head:-not reachable}, carrying on with the copy"
fi
[[ -f $REPO/pyproject.toml ]] || { echo "no pipeline repo in $REPO (see deploy/README.md)"; exit 1; }
cd "$REPO"
set -a; . /srv/grenn/secrets/model.env; set +a
export PYTHONPATH=src PYTHONUNBUFFERED=1
export CLIMATE_ARCHIVE_LIMIT=100000 CLIMATE_MAX_STALE_DAYS=2 CLIMATE_TRANSLATION_LIMIT=32 ENERGY_REPORT_DISCOVERY_LIMIT=12
export CLIMATE_MODEL_USAGE_PATH=$HOME_DIR/state/model_usage.json CLIMATE_MODEL_MIN_INTERVAL_SECONDS=12
export CLIMATE_MODEL_DAILY_REQUEST_LIMIT=${CLIMATE_MODEL_DAILY_REQUEST_LIMIT:-40} CLIMATE_RESEARCH_GROUNDED_LOOKUP=0
# the P0 sources the mainland network reaches (same list as the news database crawler)
SOURCES=${GRENN_CRAWL_SOURCES:-INT001,INT002,INT007,INT008,INT009,INT010,INT019,INT020,OFF001,OFF006,OFF013,OFF014,API001,API005}
mkdir -p "$HOME_DIR/state"

step() { echo "== $*"; "$PY" "$GLM" "$@"; }

step -m climate_agent.cli init
if (( CRAWL )); then
  args=(); for source in ${SOURCES//,/ }; do args+=(--source "$source"); done
  step -m climate_agent.cli sync --skip-ndc "${args[@]}"
  step scripts/update_research_corpus.py --fetch-limit 40 --documents
  step -m climate_agent.cli translate --limit 12
fi
# export is offline and deterministic, as in the workflow
unset CLIMATE_MODEL_API_KEY
rm -rf site
step -m climate_agent.cli export-web --output site --archive-limit 100000
step scripts/build_innovation_live_figures.py --site site
step -m climate_agent.cli validate-publish --site site
cp site/data/news_archive.json data/news_archive.json
echo "pipeline done: $(python3 -c 'import json; print(json.load(open("site/data/dashboard.json"))["meta"]["generated_at"])')"
