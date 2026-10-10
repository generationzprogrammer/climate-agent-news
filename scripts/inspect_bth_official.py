"""Read public policy provisions and statistic releases for curator verification."""
import concurrent.futures
import html
import json
import re
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
config = json.loads((root / "config/bth_targets.json").read_text(encoding="utf-8"))

def inspect(source):
    try:
        request = urllib.request.Request(source["url"], headers={"User-Agent": "GruenResearch/1.0 (public-policy evidence check)"})
        with urllib.request.urlopen(request, timeout=18) as response:
            raw = response.read(2_000_000).decode("utf-8", "replace")
        raw = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", raw, flags=re.I | re.S)
        text = re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]*>", " ", raw)))
        sentences = re.split("[。；]", text)
        return {"source_id": source["id"], "provisions": [s[-900:] for s in sentences if re.search("2025|2030", s) and re.search(r"\d.*[%％万亿]", s)]}
    except Exception as error:
        return {"source_id": source["id"], "error": type(error).__name__}

if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(inspect, config["sources"]):
            print(json.dumps(result, ensure_ascii=False))
