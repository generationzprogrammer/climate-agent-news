"""Optional offline translation using an already cached open model; resumable."""
import importlib.metadata
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tmp/innovation-import/HORIZON"
MODEL = "Helsinki-NLP/opus-mt-en-zh"


def excerpt(value):
    # Preserve complete sentences, never label this an achieved outcome.
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", value.replace("\n", " "))
    chosen = []
    for sentence in sentences:
        if len(" ".join(chosen + [sentence])) > 1050:
            break
        chosen.append(sentence)
        if len(chosen) >= 3:
            break
    return " ".join(chosen) or sentences[0][:1050]


def main():
    import numpy
    original_version = importlib.metadata.version
    # Local environment has missing NumPy distribution version metadata. Do not
    # edit installed packages; use the imported library's actual version here.
    importlib.metadata.version = lambda name: numpy.__version__ if name == "numpy" else original_version(name)
    import torch
    from transformers import AutoConfig, AutoModelForSeq2SeqLM, AutoTokenizer
    from transformers.utils.hub import cached_file
    from opencc import OpenCC
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    config = AutoConfig.from_pretrained(MODEL, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_config(config)
    weights = torch.load(cached_file(MODEL, "pytorch_model.bin", local_files_only=True), map_location="cpu", weights_only=True)
    loaded = model.load_state_dict(weights, strict=False)
    if set(loaded.missing_keys) - {"lm_head.weight"} or loaded.unexpected_keys:
        raise ValueError("Cached model tensor schema mismatch")
    model.tie_weights()
    model.eval()
    simplifier = OpenCC("t2s")
    rows = json.loads((DATA / "energy_candidates.json").read_text(encoding="utf-8"))
    rows = [r for r in rows if r["startDate"][:4] <= "2025"]
    cache_path = DATA / "translation_drafts.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    pending = [(r["id"], field, r["title"] if field == "title" else excerpt(r["objective"]))
               for r in rows for field in ("title", "objective") if not cache.get(r["id"], {}).get(field)]
    started = time.monotonic()
    for offset in range(0, len(pending), 12):
        if time.monotonic() - started > 3300:
            print("Time budget reached; resume from translation cache", flush=True)
            break
        batch = pending[offset:offset+12]
        encoded = tokenizer([">>cmn_Hans<< " + text for _, _, text in batch], return_tensors="pt", padding=True,
                            truncation=True, max_length=380)
        with torch.inference_mode():
            result = model.generate(**encoded, max_new_tokens=380, num_beams=2)
        for (pid, field, original), translated in zip(batch, tokenizer.batch_decode(result, skip_special_tokens=True)):
            translated = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", simplifier.convert(translated))
            cache.setdefault(pid, {})[field] = {"en": original, "zh": translated}
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"done": min(offset+12, len(pending)), "total": len(pending), "seconds": round(time.monotonic()-started)}), flush=True)


if __name__ == "__main__":
    main()
