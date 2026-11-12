# Research: One placement surface after topology settlement

Detailed grounding with citations: [research/code-grounding.md](research/code-grounding.md).
Fold classification: [research/foldable-issues.md](research/foldable-issues.md).

## Decision: the placement seam's `write_dir(kind).surface_root` is the one checkout authority

- **Rationale**: topology is already read correctly after settlement (`resolve_topology` →
  `default_mission_topic_dir`). The defect is which checkout holds the resolved ref. Four of the five
  holder probes already go through the seam's read side; the router's `_primary_commit_root` is the
  outlier, and the seam's own PRIMARY `write_dir` arm reports the repository root checkout as
  `surface_root` while its `path` sits in the coordination worktree.
- **Alternatives considered**: (A) route `use_coord` by topology + kind — rejected: does not fix the
  reported failure (coordination staging copies from the root path) and regresses PUBLISHED/E2 and
  landed Missions whose coordination worktree is torn down. Reading topology from `lanes.json` or a
  cache — rejected: a second authority, trips `test_topology_inference_retired`.

## Decision: re-anchor, never copy

- **Rationale**: a Mission-relative path given against the repository root checkout is re-expressed
  as `write_dir(kind).path / <mission-relative tail>` through the router's existing
  `_translate_to_owning_surface` only when the root copy is absent. A root-only copy refuses with the
  holder named, so a stale leftover can never overwrite the holder's file.
- **Alternatives considered**: resolving CLI arguments against the current directory — rejected:
  `find_repo_root()` folds every worktree back to the root by design; copying the root file into the
  holder — rejected (data-loss risk).

## Decision: protected preflights judge `write_target(WORK_PACKAGE_TASK).ref`

- **Rationale**: the sanctioned commit-ref authority (the rederivation ratchet forbids refs from a
  current-checkout expression); drains allow-list entry #2453. Operator ruling
  `01M78GS4H8AAJW5Y4ATZ3TES6B` accepts the flat-Mission message change.
- **Alternatives considered**: the HEAD of the claim commit checkout — strictly behaviour-preserving
  but another current-checkout read.

## Decision: status lock engages on the holder checkout

- **Rationale**: settlement makes the coordination and Mission branch names equal, so the
  ref-inequality `use_coord` is False and the #5353 lock is skipped (#7607). Taking the lock whenever
  a non-owned group commits in a checkout other than the repository root checkout restores it without
  changing routing. The lock is re-entrant.

## Adversarial evidence

No dependency decision is made (no supply-chain surface). The design was challenged by an independent
second-opinion agent that re-ran every claim as a live probe; its findings and dispositions are in
`research/code-grounding.md` §6–§7 (design A refuted, H2 confirmed, the `move-task --note` gate and the
silent baseline drop added, the status-lock regression added as #7607).
