# REASONS Canvas — Mixed-lane authorship soundness

Source artifacts: [spec.md](spec.md) (authoritative requirements). Plan-phase sections (Approach, Structure, Operations, Norms, Safeguards) are added by `/spec-kitty.plan`.

## Requirements

The reconciliation gate must attribute content per work package inside a shared execution lane, so no canceled WP's content reaches the target while consolidation exits 0.

- Problem: a lane counts as approved if any WP in it is approved, and its whole history is trusted, so a canceled sibling's committed content passes under both squash and merge (spec "Why this mission exists").
- Acceptance: unsuperseded canceled content → FAIL + target restored (FR-003); superseded → PASS (FR-004); missing/contradictory attribution for an implemented canceled WP in a mixed lane → REFUSE (FR-005); non-mixed lanes unchanged (FR-006); squash-capable fixture (FR-007/FR-008); per-path residual pinned (FR-009).
- Definition of done: SC-001…SC-006 met through the real `spec-kitty consolidate` entry point, red-first (C-006).

## Entities

Five domain concepts carry the change; their canonical definitions live in the spec's Domain Language table.

- **Work package lifecycle history** — decides surviving vs canceled.
- **WP commit attribution** — bounds each WP work session on its lane so the canceled WP's commits can be identified.
- **Mixed lane** — the only lane shape the new verdicts apply to.
- **Superseded (path-level)** — final lane content equal to base, or last written by a surviving WP.
- **Reconciliation claim / verdicts** — PASS, FAIL (restore target), REFUSE (target unchanged).
