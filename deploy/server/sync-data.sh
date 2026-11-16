#!/usr/bin/env bash
# Mirror the site data the original repo's workflow publishes twice a day (with the Gemini-compiled summaries) into
# /srv/grenn/data: check dashboard.json first, take everything only when it changed, validate, then switch
# data/current to the new snapshot in one rename. A failed or partial download never reaches the site.
# Where the data comes from:
#   --from <folder|zip>   a snapshot at hand (the workflow's daily-publish-snapshot artifact, unzipped or not)
#   /srv/grenn/conf/github-token present (root only; a read-only token for the repo's Actions artifacts): the newest
#                         daily-publish-snapshot artifact through the GitHub API — since 2026-11-05 the repo is private
#                         and its GitHub Pages site is gone, the workflow still uploads that artifact every run
#   otherwise             the GitHub Pages copy (GRENN_DATA_SRC), as before
# While grenn-pipeline.timer is enabled (2026-11-07) the server makes the data itself (deploy/pipeline, Zhipu GLM-4-Flash)
# and calls this with --from; the cron run then leaves the original repo alone, so the two never overwrite each other.
# Usage: sync-data.sh [--force] [--from <folder|zip>]        (cron: /etc/cron.d/grenn-sync)
set -euo pipefail
SRC=${GRENN_DATA_SRC:-https://generationzprogrammer.github.io/climate-agent-news/data}
REPO=${GRENN_DATA_REPO:-generationzprogrammer/climate-agent-news}
TOKEN_FILE=/srv/grenn/conf/github-token
ROOT=/srv/grenn/data
KEEP=3
FORCE=0 FROM=""
while (( $# )); do
  case "$1" in
    --force) FORCE=1 ;;
    --from) FROM=${2:?--from needs a folder or zip}; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
if [[ -z $FROM ]] && systemctl is-enabled --quiet grenn-pipeline.timer 2>/dev/null; then
  echo "site data comes from grenn-pipeline (GLM-4-Flash on this server); not mirroring the original repo"; exit 0
fi
# Files the COP31 page cannot work without; the rest fall back to the previous snapshot when a download fails.
REQUIRED=(dashboard.json news_archive.json corpus_analytics.json climate_spotlights.json topic_desks.json team.json
  subscription.json taxonomy.json site_metrics.json daily_brief.pdf daily_brief_en.pdf)
OPTIONAL=(bth_assistant_config.json bth_assistant_knowledge.json bth_energy_database.json bth_policy_archive.json
  bth_target_tracker.json climate_text_corpus.jsonl climate_text_corpus.manifest.json daily_brief.md energy_archive.json
  energy_companies.json energy_corpus_analytics.json energy_dashboard.json energy_reports.json
  global_climate_analysis_data_2026-08-04.json global_climate_analysis_report_latest.html innovation_cases.json
  innovation_update.json national_carbon_market_entities.json quarter_continent_keywords_2026-08-04.csv
  quarter_global_keywords_2026-08-04.csv research_catalog.json research_index.json research_records.csv
  research_texts.jsonl stance_assertions.csv stance_assertions.jsonl stance_codebook.json stance_pilot.json
  weekly_report.json weekly_report.md weekly_report.pdf weekly_report_en.pdf)

mkdir -p "$ROOT/snapshots"
exec 9>/run/lock/grenn-sync.lock
flock -n 9 || { echo "another sync is running"; exit 0; }

stamp_of() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["meta"]["generated_at"])' "$1"; }

tmp=$(mktemp -d "$ROOT/.incoming.XXXXXX")
work=$(mktemp -d "$ROOT/.snapshot.XXXXXX")
trap 'rm -rf "$tmp" "$work"' EXIT
artifact=""
if [[ -z $FROM && -r $TOKEN_FILE ]]; then
  token=$(tr -d '[:space:]' < "$TOKEN_FILE")
  api() { curl -fsS --retry 3 --retry-delay 10 --connect-timeout 20 -m 120 -H "Authorization: Bearer $token" -H "Accept: application/vnd.github+json" "$@"; }
  artifact=$(api "https://api.github.com/repos/$REPO/actions/artifacts?name=daily-publish-snapshot&per_page=10" | python3 -c '
import json, sys
found = sorted((a for a in json.load(sys.stdin)["artifacts"] if not a["expired"]), key=lambda a: a["created_at"], reverse=True)
print(" ".join(str(found[0][k]) for k in ("id", "created_at")) if found else "")')
  [[ -n $artifact ]] || { echo "no daily-publish-snapshot artifact in $REPO"; exit 1; }
  if (( ! FORCE )) && [[ -e $ROOT/.artifact && "$(cat "$ROOT/.artifact")" == "$artifact" ]]; then
    echo "up to date (artifact ${artifact#* })"; exit 0
  fi
  # the API answers with a short-lived link to the zip in GitHub's storage, fetched without the token
  url=$(api -o /dev/null -w '%{redirect_url}' "https://api.github.com/repos/$REPO/actions/artifacts/${artifact%% *}/zip")
  curl -fsS --retry 3 --retry-delay 10 --connect-timeout 20 -m 900 -o "$work/snapshot.zip" "$url"
  FROM=$work/snapshot.zip
fi
snap=""
if [[ -n $FROM ]]; then
  if [[ -d $FROM ]]; then snap=$FROM; else python3 -m zipfile -e "$FROM" "$work/data"; snap=$work/data; fi
fi
# get FILE DEST: from the snapshot, else from the GitHub Pages copy
get() {
  if [[ -n $snap ]]; then [[ -f $snap/$1 ]] && cp -p "$snap/$1" "$2"
  else curl -fsS --compressed --retry 3 --retry-delay 15 --connect-timeout 20 -m 1800 -o "$2" "$SRC/$1"; fi
}

get dashboard.json "$tmp/dashboard.json"
stamp=$(stamp_of "$tmp/dashboard.json")
if (( ! FORCE )) && [[ -e "$ROOT/current/dashboard.json" && "$(stamp_of "$ROOT/current/dashboard.json")" == "$stamp" ]]; then
  [[ -n $artifact ]] && echo "$artifact" > "$ROOT/.artifact"
  echo "up to date ($stamp)"; exit 0
fi
echo "new data $stamp — downloading"

for f in "${REQUIRED[@]}"; do
  [[ $f == dashboard.json ]] || get "$f" "$tmp/$f" || { echo "missing required $f"; exit 1; }
done
for f in "${OPTIONAL[@]}"; do
  if ! get "$f" "$tmp/$f" 2>/dev/null; then
    rm -f "$tmp/$f"
    if [[ -e "$ROOT/current/$f" ]]; then cp -p "$ROOT/current/$f" "$tmp/$f"; echo "kept previous $f"; else echo "skipped $f"; fi
  fi
done
# the research release named in the catalogue (main-site research tools)
release=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["release"]["id"])' "$tmp/research_catalog.json" 2>/dev/null || true)
if [[ -n "$release" ]]; then
  mkdir -p "$tmp/research_releases/$release"
  for f in manifest.json corpus.jsonl.gz; do
    get "research_releases/$release/$f" "$tmp/research_releases/$release/$f" || rm -f "$tmp/research_releases/$release/$f"
  done
fi

# validate before anything goes live
python3 - "$tmp" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for path in root.rglob("*"):
    if not path.is_file():
        continue
    if path.suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix == ".jsonl":
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert lines, f"{path.name} is empty"
        json.loads(lines[0]); json.loads(lines[-1])
    elif path.suffix == ".pdf":
        assert path.read_bytes()[:5] == b"%PDF-", f"{path.name} is not a PDF"
dashboard = json.loads((root / "dashboard.json").read_text(encoding="utf-8"))
assert dashboard.get("intelligence"), "dashboard has no intelligence records"
assert json.loads((root / "news_archive.json").read_text(encoding="utf-8")).get("records"), "archive has no records"
print("validated", sum(1 for p in root.rglob("*") if p.is_file()), "files")
PY

# One China (2026-11-15, user: 把中国台湾和中华人民共和国合并到一起…统一为中华人民共和国): the original project's code files
# Taiwan as a country of its own; every classification in the snapshot (country codes and names, company countries,
# places, the CSV downloads' code columns) is filed under China here (grenn_regions.py; article texts stay as published).
# A failure stops the update, so a snapshot that still lists Taiwan separately never goes live.
if [[ -f /srv/grenn/bin/grenn_regions.py ]]; then
  python3 /srv/grenn/bin/grenn_regions.py apply "$tmp"
fi

# 累计访问量 (2026-11-14): the original project's series counts the old github.io address only and stopped on 2026-11-05;
# this site's own browser page loads (from the nginx log, daily totals kept in $ROOT/visits.json) are added to it here.
# If that fails the original series goes out unchanged.
if [[ -f /srv/grenn/bin/grenn_visits.py ]]; then
  python3 /srv/grenn/bin/grenn_visits.py apply "$tmp/site_metrics.json" || echo "visits: not added, the original series stays"
fi

# 每日气候通讯 (2026-11-05): the Chinese brief PDF is re-typeset here in the team's template (grenn_brief.py); the
# original project's file stays as daily_brief_source.pdf, and is kept as the brief if typesetting fails
if [[ -x /srv/grenn/app/venv/bin/python && -f /srv/grenn/bin/grenn_brief.py ]]; then
  cp -p "$tmp/daily_brief.pdf" "$tmp/daily_brief_source.pdf"
  if /srv/grenn/app/venv/bin/python /srv/grenn/bin/grenn_brief.py "$tmp/dashboard.json" "$tmp/daily_brief.new.pdf"; then
    mv "$tmp/daily_brief.new.pdf" "$tmp/daily_brief.pdf"
  else
    rm -f "$tmp/daily_brief.new.pdf"; echo "brief: typesetting failed, kept the original"
  fi
fi

# precompressed copies beside the text files for nginx's brotli_static / gzip_static (2026-11-07): brotli is about a
# third smaller than the on-the-fly gzip for the big JSON (news_archive.json 3.4 → 2.2 MB), with no work per request
if command -v brotli >/dev/null; then
  for f in "$tmp"/*.json "$tmp"/*.jsonl "$tmp"/*.md "$tmp"/*.csv "$tmp"/*.html; do
    [[ -f $f && $(stat -c %s "$f") -gt 1024 ]] || continue
    { brotli -q 9 -f -o "$f.br" "$f" && gzip -9 -c "$f" > "$f.gz"; } || rm -f "$f.br" "$f.gz"
  done
fi

name=$(echo "$stamp" | tr -c 'A-Za-z0-9\n' '-' | cut -c1-40)
# the same data again (--force): a folder of its own — mv into an existing snapshot would put this one inside it and
# leave the site on the old files (found 2026-11-14)
[[ -e "$ROOT/snapshots/$name" ]] && name="$name-r$(date +%Y%m%d%H%M%S)"
chmod -R a+rX "$tmp"
mv "$tmp" "$ROOT/snapshots/$name"
trap - EXIT
rm -rf "$work"
ln -sfn "snapshots/$name" "$ROOT/current.new"
mv -T "$ROOT/current.new" "$ROOT/current"
[[ -n $artifact ]] && echo "$artifact" > "$ROOT/.artifact"
echo "live: $name"
# keep the newest $KEEP snapshots
ls -1dt "$ROOT"/snapshots/*/ | tail -n +$((KEEP + 1)) | xargs -r rm -rf
