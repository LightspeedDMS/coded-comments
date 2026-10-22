# Python and TS/JS comment-to-code sample

Inputs: provenance.tsv; canonical code-indexer and claude-pace-maker for Python, tdd-guard and claude-server for TS/JS. Paths must exist at HEAD. Test/fixture/build paths are excluded. Up to 60 files per repo are selected by SHA256(repo:path).
A line with both code and comment counts once in each column. Blank lines count in neither. Python docstrings count as code; TS/JS scanning handles quoted strings and block comments but may misclassify regex literals or template interpolation. Skips are in ratio_skipped.tsv.

| Language | Files | Comment lines | Code lines | Ratio |
|---|---:|---:|---:|---:|
| python | 120 | 7275 | 49208 | 0.147842 |
| typescript_js | 83 | 2415 | 14015 | 0.172315 |
