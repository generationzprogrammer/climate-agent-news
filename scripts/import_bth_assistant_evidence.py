"""Import selected public observations; exclude private templates and assumed CIB scores."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
observations = json.loads((args.source / "data" / "观测数据.json").read_text(encoding="utf-8"))
observations = [row for row in observations if row.get("selected") is True]
source_ids = {row["source_id"] for row in observations}
sources = json.loads((args.source / "data" / "sources.json").read_text(encoding="utf-8"))
sources = [row for row in sources if row["id"] in source_ids]
if any(not row["url"].startswith("https://") for row in sources):
    raise ValueError("non-public evidence source")
payload = {"snapshot_date": "2026-10-01", "observations": observations, "sources": sources}
(root / "config" / "bth_energy_evidence.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"observations": len(observations), "sources": len(sources)}))
