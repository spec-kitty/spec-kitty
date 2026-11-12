# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · **[2026-11-11][research] Research-first, read-only squad before specify.** Code grounding, tracer evidence mining and foldable-issue discovery ran in parallel, then a fresh-context second opinion; the fold set and design approach go to the operator before specify (#7547).

2026-11-12 · claude-orchestrator · **[2026-11-12][plan] Post-plan squad reshaped the seams.** The hook now builds the invocation, probe and evidence tree and passes only a plain run_env down; the baseline gets the same environment recipe; the invocation is re-derived per step instead of persisted (stale probes); foreign is reachable only through a lane-owned venv, which is the #1907 case. 19 findings, 18 accepted, 1 rejected (workspace members outside src/); dispositions in research.md.
