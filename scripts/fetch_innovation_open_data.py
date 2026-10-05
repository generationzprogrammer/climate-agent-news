"""One official bulk snapshot, bounded download and on-disk cache; never CI crawl."""
import argparse
import hashlib
import json
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--programme", choices=["h2020", "HORIZON"], default="HORIZON")
    args = parser.parse_args()
    URL = f"https://cordis.europa.eu/data/cordis-{args.programme}projects-csv.zip"
    CACHE = ROOT / "tmp/innovation-import" / args.programme
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"cordis-{args.programme}projects-csv.zip"
    if not target.exists():
        request = urllib.request.Request(URL, headers={"User-Agent": "GruenOpenInnovation/1.1 (academic open-data analysis)"})
        deadline = time.monotonic() + 240
        total = 0
        with urllib.request.urlopen(request, timeout=30) as response, target.with_suffix(".part").open("wb") as out:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 90_000_000 or time.monotonic() > deadline:
                    raise TimeoutError("Bulk snapshot exceeds size/time budget")
                out.write(chunk)
        target.with_suffix(".part").replace(target)
    audit = {"url": URL, "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
             "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "bytes": target.stat().st_size,
             "rights_review": "https://cordis.europa.eu/about/legal", "retry_limit": 0,
             "cache": "Reuse downloaded snapshot; manual refresh only", "status": "downloaded"}
    with zipfile.ZipFile(target) as archive:
        audit["files"] = archive.namelist()
        for name in archive.namelist():
            # Never extract an untrusted member path. Only recognised basename CSVs.
            if Path(name).name == name and name.endswith(".csv"):
                (CACHE / name).write_bytes(archive.read(name))
    (CACHE / "download_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
