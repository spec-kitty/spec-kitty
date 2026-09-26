# Tracer: Approach

Seeded at planning; appended during implementation.

- 2026-09-26 (grounding→specify): confirmed the #4979 residual is LIVE on current main
  (`da6d0af97e`), not superseded by the intervening coord work (#4959/#4970/#5001). The
  `#2614` fix added a `refs/remotes/` scan to `_coord_branch_exists` but it inspects only
  ALREADY-FETCHED remote-tracking refs — a single-branch/`--depth 1`/CI/pruned checkout has
  none, so the residual (no `git ls-remote` probe) stands.
- Key structural insight: `_coord_branch_exists` is the SINGLE canonical probe both the coord
  read path (`CoordinationBranchDeleted`) and `doctor coordination --fix`
  (`_coordination_doctor.py:501`) consume. Fixing the probe closes the class at the source —
  the doctor stops emitting NEVER_CREATED and stops flattening. (Single canonical authority,
  charter Governing Principle #1 + C-001.)
- Three-tier defense chosen: (1) remote-existence in the probe [WP01, root, closes class];
  (2) belt-and-suspenders remote re-verify at the doctor flatten site [WP02]; (3) defense-
  in-depth guard so implement's auto-commit never silently carries a topology demotion [WP03].
  WP02/WP03 reuse WP01's new remote helper (dependency chain WP01 → {WP02, WP03}).
- Fail-closed throughout (NFR-002): every new git probe treats any error / unreachable remote
  as "branch present", never "deleted". `git ls-remote` runs ONLY after the local-head and
  `refs/remotes/` fast paths miss (NFR-001 — full clones pay nothing).
- 2026-09-26 (WP02 implement): tackled tier (2) of the three-tier defense above —
  `_fix_never_created_branches` (the destructive `--fix` flatten) now re-verifies each
  finding's `coordination_branch` against WP01's `remote_branch_lookup` immediately before
  `flatten_coordination_metadata`, independent of whatever the CHECK site (WP01) already
  decided. Red-first via a real bare-origin git fixture (T007), then the guard (T008): HIT/ERROR
  skip (fail-closed) + an actionable "not flattened, run `git fetch`" message; CLEAN_MISS/
  NO_REMOTE proceed exactly as before. See design-decisions.md D-18..D-20 for the signature and
  message-shape rationale.
