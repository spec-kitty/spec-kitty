# Decision: runner-relative evidence for the cascade cost (#6777)

**Status**: accepted · 2026-10-30 · mission `cascade-stem-resolution-pass-01M67JG7`

## Context

The mission's first draft set an absolute "<60 s on this host" threshold. The shared
build host runs ~20 concurrent agent missions: load average moved from ~21 (46 min into
the work) to 44–91 during the same afternoon, and a scripted run of the *unmodified*
writer moved from 80.3 s to 95.2 s across that window with no code change.

An absolute wall-clock threshold would therefore decide on host load, not on the fix — the
exact failure mode `docs/development/testing/testing-flakiness.md` argues against
("widening an absolute budget to absorb a slow runner is not accepted"), and the same
reason `docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md` replaced the
repo's absolute performance gates with runner-relative ratios.

## Decision

NFR-001 and SC-002 are expressed the only way this host can support:

1. **Interleaved A/B wall clock** — the pre-fix and post-fix arms run in the same process,
   on alternating fresh fixtures, in the same load window. The fix must be ≤0.8× of the
   pre-fix arm. Measured: 0.62× (load ≈21) and 0.70× (load 44–91).
2. **A load-independent count** — artifact-file parses performed by the cascade's URN
   resolution: 5028 before, 240 after (≤5%), exactly reproducible on any host. This is also
   what the regression guard pins (NFR-003: no timing assertion).

## Consequences

* The absolute CI margin is reported, not asserted: the case measured 70.9–80.3 s pre-fix
  and ~50–66 s post-fix here, so a runner ~2× slower lands near 110–135 s against the
  240 s backstop instead of at/over it.
* A future regression that re-adds a per-target catalog walk fails the parse-count guard,
  not a wall clock, so it cannot hide behind a quiet host.
