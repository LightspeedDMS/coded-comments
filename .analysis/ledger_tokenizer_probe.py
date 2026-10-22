"""Upsert tokenizer metadata and probe-string counts into numbers.json (keeps other entries)."""

import json
from pathlib import Path

import tiktoken

LEDGER = Path(__file__).resolve().parent / "numbers.json"
ENCODINGS = ("o200k_base", "cl100k_base")
PROBES = {
    "intel_glyph": "§ △0.6 ◎const ■research ◇0.7 ↻3",
    "intel_ascii": "# i:0.6 scope:const type:research conf:0.7 iter:3",
    "plain_comment": "# Loop over items and add each one to the result list",
}
API_REASON = (
    "no ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN in environment; only a Claude Code "
    "subscription login exists, which is not used for the token-counting API"
)
CAVEAT = (
    "Counts are tiktoken proxy counts (OpenAI vocabularies), not Claude tokenizer "
    "counts; absolute Claude numbers may differ, so decisions rely on relative cost "
    "and on agreement across both encodings."
)


def main() -> None:
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    ledger.setdefault("entries", {})
    ledger["tokenizers"] = {
        "tiktoken_version": tiktoken.__version__,
        "encodings": list(ENCODINGS),
        "anthropic_api": {"available": False, "reason": API_REASON},
        "caveat": CAVEAT,
    }
    ledger["probe_strings"] = PROBES
    for enc_name in ENCODINGS:
        enc = tiktoken.get_encoding(enc_name)
        for key, text in PROBES.items():
            ledger["entries"]["tok.probe.%s.%s" % (key, enc_name)] = {
                "value": len(enc.encode(text)),
                "source": "probe_strings." + key,
                "method": "len(tiktoken.get_encoding(name).encode(text))",
                "tokenizer": "tiktoken %s %s" % (tiktoken.__version__, enc_name),
            }
    LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
