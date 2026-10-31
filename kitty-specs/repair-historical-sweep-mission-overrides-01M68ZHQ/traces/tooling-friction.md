# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · s7-agent · spec-kitty plan failed once with 'Global asset input changed: /home/exedev/.kittify/cache/agent-commands-freshness.lock; re-run the command' — the shared global asset cache is rewritten by the other agents on this host. Retried once and it succeeded; no workaround applied beyond the retry the error itself suggests.

2026-10-31 · s7-agent · spec-kitty agent acceptance-verdict --criterion SC-00N exits 0 and prints the valid-FR list instead of recording anything: the acceptance matrix is scaffolded from the FR table only, so success-criterion verdicts are silently dropped. The SCs are therefore evidenced in the PR body and the tests rather than in acceptance-matrix.json.
