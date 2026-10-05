"""Build case assets offline, or explicitly request a model draft for review."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from climate_agent.innovation_cases import InnovationCaseAgent, write_innovation_cases
from climate_agent.providers import OpenAICompatibleModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-evidence", type=Path, help="Explicit opt-in model call using supplied public evidence")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.draft_evidence:
        output = args.output or ROOT / "analysis/innovation_case_draft.json"
        # Drafts may never overwrite the reviewed casebook or public assets.
        resolved = output.resolve()
        if ROOT / "analysis" not in resolved.parents:
            parser.error("Draft output must stay inside analysis/")
        evidence = json.loads(args.draft_evidence.read_text(encoding="utf-8"))
        taxonomy = json.loads((ROOT / "config/open_innovation_cases.json").read_text(encoding="utf-8"))["taxonomy"]
        result = InnovationCaseAgent(OpenAICompatibleModel.from_env()).draft(evidence, taxonomy)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "draft", "publication": result["publication"]}))
    else:
        archives = [json.loads(path.read_text(encoding="utf-8")) for path in
                    (ROOT / "static/data/news_archive.json", ROOT / "static/data/energy_archive.json") if path.exists()]
        result = write_innovation_cases(ROOT, args.output or ROOT / "static/data/innovation_cases.json", archives)
        print(json.dumps(result["statistics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
