# Approach: residue-safe-migration-sweep-01M5SS0F

- **[2026-10-25][specify] Red-first P0 first.** The `p0_repro(issue=6669)` landed in its own `pr:p0-repro` PR (#6672) before any fix, as the operator ruled for #6627.
- **[2026-10-25][specify] Scope grew after the adversarial review.** A narrow fix (the rule plus superseding 2.0.6) still left 3.1.1 and 0.9.0 writing into residue. The operator extended the supersession to 0.9.0, 0.9.1 and 3.1.1.
- **[2026-10-25][plan] Successor shape per predecessor.** Class-based migrations (0.9.x) are subclassed with per-folder overrides; module-function migrations (2.0.6, 3.1.1) are re-walked over the frozen helpers.

## Implement-review outcome (2026-10-25)
- WP01 approved cycle 2 (spy measured git at process level; corrupt-index degrade; doctor reason from shared notice by ruling).
- WP06 approved cycle 2 (load_meta census row; isolated tracked-meta negative).
- WP02 approved cycle 2 (probe-branch tests). WP04, WP05, WP03 approved cycle 1.
- Follow-ups folded into WP07: single probe helper, backfill-wp-status residue reporting, cutover docstring, walker test gaps, LIVE_COORDINATION_SKIPS, partition_checkout_specs home, gate hop restriction, 0.9.1 dry-run string test.

- **[2026-10-25][WP07]** One `spec-kitty upgrade` run against a project holding all six residue folders plus two controls proves the residue rule end to end and the once-per-folder notice collapse. Red-first evidence: the same guard, run against `origin/main` 1ec38c99 in a scratch worktree, failed by writing `meta.json` and status files into the residue. Review follow-ups were folded into WP07: one public `probe_tracked_mission_paths`, `residue_directories` in `backfill-wp-status`, and the gate restricted to guarded seams.
