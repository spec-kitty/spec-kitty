# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · Red-first recovery of a misattributed report: the issue blamed the refinalize short-circuit, but the red assert was the earlier backfill_mission call. Minimal repro (an empty .git directory above TMPDIR flips the fixture red; a clean TMPDIR makes it green) separated 'production bug' from 'host pollution' and showed the pollution is only the trigger: the refusal was fabricated by a name check after git had already answered 'not a git repository'.
