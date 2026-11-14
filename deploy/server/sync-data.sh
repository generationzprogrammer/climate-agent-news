#!/usr/bin/env bash
# Mirror the published data/ of the GitHub Pages site (built twice a day by the original repo's workflow, with the
# Gemini-compiled summaries) into /srv/grenn/data. github.com is unreachable from this server, github.io is reachable
# but slow, so: check dashboard.json first, download everything (gzip on the wire) only when it changed, validate,
# then switch data/current to the new snapshot in one rename. A failed or partial download never reaches the site.
# Usage: sync-data.sh [--force]        (cron: /etc/cron.d/grenn-sync)
set -euo pipefail
SRC=${GRENN_DATA_SRC:-https://generationzprogrammer.github.io/climate-agent-news/data}
ROOT=/srv/grenn/data
KEEP=3
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
  weekly_report.json weekly_report.md weekly_report.pdf)

mkdir -p "$ROOT/snapshots"
exec 9>/run/lock/grenn-sync.lock
flock -n 9 || { echo "another sync is running"; exit 0; }

fetch() { curl -fsS --compressed --retry 3 --retry-delay 15 --connect-timeout 20 -m 1800 -o "$2" "$SRC/$1"; }
stamp_of() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["meta"]["generated_at"])' "$1"; }

tmp=$(mktemp -d "$ROOT/.incoming.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
fetch dashboard.json "$tmp/dashboard.json"
stamp=$(stamp_of "$tmp/dashboard.json")
if [[ "${1:-}" != "--force" && -e "$ROOT/current/dashboard.json" && "$(stamp_of "$ROOT/current/dashboard.json")" == "$stamp" ]]; then
  echo "up to date ($stamp)"; exit 0
fi
echo "new data $stamp — downloading"

for f in "${REQUIRED[@]}"; do
  [[ $f == dashboard.json ]] || fetch "$f" "$tmp/$f"
done
for f in "${OPTIONAL[@]}"; do
  if ! fetch "$f" "$tmp/$f" 2>/dev/null; then
    rm -f "$tmp/$f"
    if [[ -e "$ROOT/current/$f" ]]; then cp -p "$ROOT/current/$f" "$tmp/$f"; echo "kept previous $f"; else echo "skipped $f"; fi
  fi
done
# the research release named in the catalogue (main-site research tools)
release=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["release"]["id"])' "$tmp/research_catalog.json" 2>/dev/null || true)
if [[ -n "$release" ]]; then
  mkdir -p "$tmp/research_releases/$release"
  for f in manifest.json corpus.jsonl.gz; do
    fetch "research_releases/$release/$f" "$tmp/research_releases/$release/$f" || rm -f "$tmp/research_releases/$release/$f"
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

name=$(echo "$stamp" | tr -c 'A-Za-z0-9\n' '-' | cut -c1-40)
chmod -R a+rX "$tmp"
mv "$tmp" "$ROOT/snapshots/$name"
trap - EXIT
ln -sfn "snapshots/$name" "$ROOT/current.new"
mv -T "$ROOT/current.new" "$ROOT/current"
echo "live: $name"
# keep the newest $KEEP snapshots
ls -1dt "$ROOT"/snapshots/*/ | tail -n +$((KEEP + 1)) | xargs -r rm -rf
