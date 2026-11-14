#!/usr/bin/env bash
# Make an uploaded frontend release live: add the ICP filing number to the page footers (this deployment only — the
# repository stays clean), point its data/ at the synced data, then switch /srv/grenn/current in one rename.
# Usage: activate-release.sh /srv/grenn/releases/<name>        (called by deploy/publish.sh)
set -euo pipefail
REL=${1:?release directory}
ROOT=/srv/grenn
[[ -f "$REL/cop31/index.html" ]] || { echo "not a release: $REL" >&2; exit 1; }

python3 - "$REL" <<'PY'
import pathlib, sys
rel = pathlib.Path(sys.argv[1])
icp = ('<a class="site-icp" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer" '
       'style="color:inherit;opacity:.75;font-size:12px;text-decoration:none">京ICP备2026018443号-1</a>')
subtitle = '<span data-i18n="footerSubtitle">全球气候与能源信息智能分析支持系统</span>'
for page in ("cop31/index.html", "index.html", "innovation/index.html"):
    path = rel / page
    if not path.exists() or "site-icp" in path.read_text(encoding="utf-8"):
        continue
    html = path.read_text(encoding="utf-8")
    if subtitle in html:                      # under the brand line in the footer's first column
        html = html.replace(subtitle, subtitle + icp, 1)
    elif "</footer>" in html:                 # pages with a plain footer
        html = html.replace("</footer>", icp + "</footer>", 1)
    else:
        sys.exit(f"no footer in {page}")
    path.write_text(html, encoding="utf-8")
    print("ICP number added to", page)
PY

rm -rf "$REL/data"
ln -sfn "$ROOT/data/current" "$REL/data"
chmod -R a+rX "$REL"
ln -sfn "$REL" "$ROOT/current.new"
mv -T "$ROOT/current.new" "$ROOT/current"
echo "live: $REL"
# keep the newest 5 releases
ls -1dt "$ROOT"/releases/*/ | tail -n +6 | xargs -r rm -rf
