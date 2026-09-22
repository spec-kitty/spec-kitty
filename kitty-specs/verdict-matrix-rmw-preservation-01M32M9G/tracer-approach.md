# Tracer — Approach (verdict-matrix RMW preservation: #4858 + #4868)

Append as the approach evolves. Seeded at planning.

## Unifying invariant
A verdict-recording write must be based on the true authoritative current matrix and change
ONLY the row it owns — never overwrite from a stale (concurrency), partial, or wrong-source
(migration) snapshot. Applies to both the acceptance matrix and the issue matrix.

## Root #4858 — acceptance-matrix concurrency lost-update (P0)
- **Red-first:** deterministic serialized `read1 → full-run2 → finish1` harness (no real threads)
  driving two `--negative-invariant` verdicts for distinct ids; assert both rows + evidence
  survive and overall_verdict stays `fail`; flat + coord variants; PLUS a lock-acquisition spy
  (key == matrix_dir.name, path under git common dir) + call-order (check before lock) so the
  lock itself is gated. Criterion-mode concurrency case at its own seam.
- **Fix (Option A):** in `acceptance_verdict.py`, run the slow check OUTSIDE the lock, then INSIDE
  `feature_status_lock(repo_root, matrix_dir.name)` re-read the matrix from disk, splice ONLY the
  owned entry, write+commit. Route `write_acceptance_matrix` through `kernel.atomic.atomic_write`
  (benefits all callers).

## Root #4868 — issue-matrix wrong-source serial migration (P1)
- **Red-first:** deterministic serial repro — seed a coord authoritative `issue-matrix.md` with
  issue #A (fixed + evidence), record issue #B via the real CLI, assert BOTH #A and #B survive in
  the committed JSON and via the canonical reader; flat control passes on base.
- **Fix (per triage, pending grounding confirmation):** make the first-JSON migration read the
  coord-aware authoritative `read_dir` (the matrix actually read for this mission), preserving its
  existing rows before upserting the requested issue — do not treat "no legacy file on primary" as
  "no prior matrix anywhere."

## Shared / reused primitives
- `status/locking.py::feature_status_lock` (git-common-dir keyed; cross-worktree). #4858 only.
- `kernel/atomic.py::atomic_write` (atomic write door).
- Coord fixtures: `_build_coord_mission_for_matrix` (acceptance) + the issue-matrix coord fixture
  (from #4868 grounding).
- Consider: does #4868's issue-matrix writer also warrant the atomic door / same preservation
  helper? Evaluate in plan for a shared, non-over-engineered preservation seam.

## Sequencing
Two independent red-first repros → two fixes. #4858 (P0) leads. Keep the two fix loci cleanly
separable in the commit history so review can verify each red→green independently.
