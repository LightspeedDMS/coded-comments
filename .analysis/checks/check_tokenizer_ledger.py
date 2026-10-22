"""Step 6 check: ledger tokenizer entries match an independent tiktoken recount."""

import json
import re
import sys
from pathlib import Path

import tiktoken

LEDGER = Path(__file__).resolve().parents[1] / "numbers.json"
ENCODINGS = ("o200k_base", "cl100k_base")


def main() -> None:
    assert LEDGER.exists(), "numbers.json missing"
    raw = LEDGER.read_text()
    ledger = json.loads(raw)
    assert not re.search(r"sk-ant-|Bearer\s", raw), "credential-like text in ledger"
    entries = ledger["entries"]
    tok = ledger["tokenizers"]
    assert tok["tiktoken_version"] == tiktoken.__version__
    assert tok["anthropic_api"]["available"] is False
    assert tok["anthropic_api"]["reason"], "API unavailability needs a reason"
    assert "proxy" in tok["caveat"].lower() and "claude" in tok["caveat"].lower()
    probe = ledger["probe_strings"]
    assert len(probe) >= 3
    for enc_name in ENCODINGS:
        enc = tiktoken.get_encoding(enc_name)
        for key, text in probe.items():
            ident = "tok.probe.%s.%s" % (key, enc_name)
            assert ident in entries, "missing ledger id " + ident
            got = len(enc.encode(text))
            want = entries[ident]["value"]
            assert got == want, "%s: ledger %s, recount %s" % (ident, want, got)
            for field in ("method", "source", "tokenizer"):
                assert entries[ident].get(field), "%s lacks %s" % (ident, field)
    print("tokenizer ledger OK: %d probes x %d encodings" % (len(probe), len(ENCODINGS)))


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print("FAIL:", exc)
        sys.exit(1)
