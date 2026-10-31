---
affected_files: []
cycle_number: 1
mission_slug: stale-coord-lane-base-01M67HRA
reproduction_command:
reviewed_at: '2026-10-31T00:42:02Z'
reviewer_agent: pi
wp_id: WP01
---

# WP01 review feedback (cycle 1) — reviewer-renata

## Issue 1 (blocking): the warning pollutes `--json` stdout

`allocate_lane_worktree` writes the new warning with a bare `print(...)`, which goes to
`sys.stdout`. The top-level `spec-kitty implement` command is wrapped by
`_json_safe_output` (`src/specify_cli/cli/commands/implement.py`), and in `--json` mode that
wrapper captures **only the rich console** (`_json_wrapper_begin_capture` sets
`console.file = capture_buffer`); a bare `print` is not captured. The machine-readable payload
is written to stdout by the same process, so on a coord mission whose target has advanced — the
common case this WP targets — `spec-kitty implement <WP> --json` would emit a `WARNING:` line
ahead of the JSON and break `json.loads(stdout)` for every consumer.

Pre-existing `print` warnings in this module (`_merge_dependency_lane_tips`) are not a licence:
they fire only on dependency-bearing lanes, whereas this one fires on every stale coord
allocation, so this change is what turns a latent risk into a routine one. The repo already
routes diagnostics to stderr (`specify_cli/plan_validation.py:105`,
`specify_cli/runtime/resolver.py:226`, `policy/commit_guard_hook.py`).

**Fix**: emit the warning to `sys.stderr`, and pin it — the same-fixture stale case must assert
the warning is on stderr **and that stdout stayed empty**, so the machine-readable channel is
provably untouched. Keep the message text and the `WARNING:` prefix.

## Verified OK (no change requested)

- The probe reuses the already-captured `target_tip` (`capture_branch_tip`) instead of adding a
  second target-tip authority, and adds no subprocess on the legacy, reuse, crash-recovery or
  planning routes (NFR-001).
- Three-state answer: an unresolvable target (`None`), a non-zero non-1 exit, or an `OSError`
  all render as "unknown" and print nothing (NFR-002); `test_unresolvable_target_branch_is_silent`
  pins it and also asserts the allocation still succeeds.
- `decision.parent_ref` (not the raw `coordination_branch`) is what the probe reads, so
  `--base <current tip>` is correctly silent — pinned by `test_explicit_current_base_is_silent`.
- `_stale_base_warning` and `_lane_base_contains_target_tip` are private, typed, and singletons
  for this decision; no second parent-ref authority was introduced.
- Parentage is unchanged on the stale cut: `test_stale_report_keeps_the_coordination_parent`
  (`merge-base --is-ancestor <coord> <lane>` exits 0) and
  `test_stale_lane_lacks_the_target_commit` pin C-001 / FR-003 both ways.
- Red-first evidence is real: `test_stale_coord_base_is_reported` failed on the silence
  (`expected a stale-base warning, got: ''`) and the five controls around it were green before
  the production change, so the assertion is non-vacuous.
- Suites: `tests/specify_cli/lanes` + `tests/lanes` → 1228 passed, 2 skipped; ruff and
  `ruff format --check --force-exclude` clean on both touched files.
- Comment accuracy: the FRESH_COORD-arm comment cites C-001/C-002/C-005 and the module's own
  `_merge_dependency_lane_tips` precedent for the operator-facing warning; both still hold after
  the stderr fix (update the wording to say "stderr" if it names the channel).
