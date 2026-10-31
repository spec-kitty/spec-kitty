# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · D-1: attribution stays 'approved lane first-parent authorship' or 'explicitly declared, verified external ref' - no merge simulation (C-001); #4945 and #6771 are structurally identical, so only a declaration separates them. D-2: the spine guard keeps the closed world closed - a declaration covering any commit on a lane/mission/mission-branch first-parent spine REFUSEs with the sets emptied. D-3: reachability is 'mission branch OR a lane branch', found by the forecast test: a lane brings its dependency in before the fold. D-4: the forecast reuses Divergence.describe() and the one attribution hint, so both surfaces print the same clause.
