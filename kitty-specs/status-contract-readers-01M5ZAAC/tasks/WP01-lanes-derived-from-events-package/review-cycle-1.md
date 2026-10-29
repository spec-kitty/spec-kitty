---
affected_files: []
cycle_number: 1
mission_slug: status-contract-readers-01M5ZAAC
reproduction_command:
reviewed_at: '2026-10-27T19:29:49Z'
reviewer_agent: claude-reviewer
wp_id: WP01
---

# WP01 review: changes requested (one blocking item)

The derivation is correct. `CANONICAL_LANES` is byte-identical. Red-to-green was verified: on the base tree, 5 tests fail (4 AttributeError, and the AST guard flags `status_lanes.py:8`). The consumer tests (204) and the three gate files (80) pass, and ruff, format and C901 are clean. Only the item below blocks approval.

## Blocking

1. **mypy error in the new test file** (NFR-003; CLAUDE.md Code Style: "New code MUST pass ruff and mypy with zero issues").
   - Location: `tests/status/test_status_lanes_derivation.py:70`.
   - mypy reports: `"AST" has no attribute "lineno"  [attr-defined]`.
   - Reproduce with `mypy tests/status/test_status_lanes_derivation.py`; it also fails under `--strict`.
   - Cause: `ast.walk` yields `ast.AST`, and that type has no `lineno` attribute.
   - Fix: narrow the type without a suppression. One way is to make `_is_hand_typed_lane_list` a `TypeGuard[ast.Tuple | ast.List | ast.Set]`. Another is to filter with `isinstance(node, (ast.Tuple, ast.List, ast.Set))` in the comprehension before reading `node.lineno`.
   - Do not add `# type: ignore`.

## Should fix (same change, low cost)

2. **Stale rationale comment** (DIRECTIVE_037; T004 allows this one-line out-of-map edit if you give the rationale in the history note).
   - Location: `src/specify_cli/status/event_log_merge.py:21-26`.
   - The comment calls `CANONICAL_LANES` "the declared ordered lane authority in `status_lanes`" and contrasts it with "the `Lane` enum's member declaration order".
   - After WP01 the order comes from the declaration order of `spec_kitty_events.status.Lane`. The package's enum order is therefore now load-bearing. A reorder there is caught by the literal ratchet in `test_canonical_lanes_are_package_lanes_minus_non_authorable_in_order` and by `test_event_log_merge_forward_rank_excludes_genesis_and_keeps_order`.
   - Reword the comment to say this, so a later reader does not believe the order is hand-declared and safe from upstream changes.

## Verified (no action)
- Commit order: the test commit 25d5b9d3 comes before the implementation commit 27a3e92d.
- No alias name was added, and `genesis` is excluded.
- The AST guard is non-vacuous: it fails on the base file, and its detector has its own unit test.
- Only the two owned files change in `src`/`tests`.
