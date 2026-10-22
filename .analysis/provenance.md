# Claude coauthor provenance

Discovery: immediate child directories of ~/Dev containing .git; nested test/third-party repos excluded.
Locator: git log --all --regexp-ignore-case --extended-regexp --grep='Co-Authored-By:[[:space:]]*Claude' --format=COMMIT:%H --name-only.
The TSV contains one row per commit/file pair, including an empty file cell for commits without paths.
Paths are historical; later corpus steps must check whether they still exist before reading.
All source repos were read-only. Counts are distinct commit hashes and distinct historical paths per repo.

| Repo | Claude-coauthored commits | Distinct files |
|---|---:|---:|
| DistributedLock | 0 | 0 |
| GitNexus | 196 | 557 |
| agent-server-router | 32 | 571 |
| anthropic-companion | 1 | 2 |
| claude-delegation-agents | 3 | 3 |
| claude-pace-maker | 341 | 594 |
| claude-pace-maker-competitive | 341 | 594 |
| claude-pace-maker-story6-agent-tracking | 341 | 594 |
| claude-server | 542 | 3450 |
| claude-server-workspace-2 | 128 | 367 |
| claude-usage-reporting | 123 | 123 |
| claude-visualizer | 31 | 73 |
| code-indexer | 3848 | 9804 |
| code-indexer-master | 3712 | 9653 |
| code-indexer-security | 72 | 122 |
| cow-storage-daemon | 9 | 59 |
| csv-sql-engine-memory-capped | 1 | 4 |
| dsa-databricks | 46 | 11 |
| elasticsearch | 0 | 0 |
| product-docs | 22 | 502 |
| full-text-search | 0 | 0 |
| gmail-buddy | 0 | 0 |
| keycloak | 0 | 0 |
| langfuse-apikey-auto-provisioner | 1 | 34 |
| llm-creds-provider | 16 | 165 |
| mcp-agents-comms-hub | 0 | 0 |
| message-bus | 0 | 0 |
| metl | 0 | 0 |
| metrics-library | 0 | 0 |
| ragflow | 97 | 901 |
| ragflow-worker-autoscaler | 5 | 25 |
| remote_mcp_auth | 0 | 0 |
| resource-login | 0 | 0 |
| roxy | 85 | 306 |
| rust-hello-world | 0 | 0 |
| setup-dev-rocky | 105 | 81 |
| simple-cache | 0 | 0 |
| ssh-mcp | 66 | 400 |
| swing-mcp-automation | 51 | 287 |
| tdd-guard | 399 | 417 |
| token-validator | 0 | 0 |
| tries | 0 | 0 |
| tries-rs | 0 | 0 |

Total: 10614 commits across 43 top-level repositories.
