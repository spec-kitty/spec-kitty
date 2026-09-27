---
affected_files: []
cycle_number: 2
mission_slug: issue-matrix-partition-integrity-01M3H10A
reproduction_command:
reviewed_at: '2026-09-27T12:00:45Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review feedback (cycle 2) — reviewer-renata

Progress confirmed: all four cycle-1 swaps now trip (partition-swap / discovery-dir-read); counterfactual on the planning base still reports every original bug; ALLOWED_TAINTS pins + stale-pin detection work; 30/30 pass; ruff, ruff format, mypy clean. The adversarial pass below found swaps that still pass `scan_python` with zero violations (each applied to the current lane-e source).

## Blocking

**Issue 1: swapping the helper's own tuple destructuring is not caught (the most likely form of the #4943/#5171 regression).**
- `merge_gates.py` (both gates): `primary_discovery_dir, coord_matrix_source = resolve_issue_matrix_partition(` -> `coord_matrix_source, primary_discovery_dir = resolve_issue_matrix_partition(`: NOT CAUGHT.
- `review/__init__.py`: `_primary_discovery_dir, matrix_source = ...` -> `matrix_source, _primary_discovery_dir = ...`: NOT CAUGHT.
Cause: `_collect_assignments` only records single-`Name` targets, so a `Tuple` target (the helper call site) is invisible to taint and to the rules.
Fix: add a positional rule for every `<a>, <b> = resolve_issue_matrix_partition(...)`: element 0 must be a `DISCOVERY_DIR_NAMES` name and element 1 must not be one (and must not be `feature_dir`). Add a self-mutation test that swaps the order at each of the three call sites.

**Issue 2: an attribute-held discovery dir is not taint-tracked.** In `review_mission`, `_evaluate_issue_matrix(..., matrix_dir=resolved.feature_dir, ...)` is NOT CAUGHT, because `_mentions` only matches `ast.Name` ids. `review_mission` literally has `resolved.feature_dir` in scope, so this is a realistic swap. Fix: have `_mentions` also treat an `ast.Attribute` whose `.attr` is in `DISCOVERY_DIR_NAMES` as tainted, and add a mutation test.

**Issue 3: a hand-rebuilt mission dir fed to a sink is not caught (this is FR-008's own wording, "reconstructs a topology-dependent issue-matrix path by hand").** `_load_issue_matrix_rows(repo_root / "kitty-specs" / mission_slug)` is NOT CAUGHT. The raw-path rule only fires when the join ends in the matrix filename, and the literal rule needs `kitty-specs/...issue-matrix` in one string. Fix: flag any sink argument containing a `"kitty-specs"` string constant (or a join with one), and add a mutation test.

## Non-blocking (fold if cheap)
- Tuple-target taint (`matrix_dir, _x = _primary_discovery_dir, None`), `for matrix_dir in (...)` targets, and indexing into the split (`resolve_issue_matrix_partition(...)[0]` fed to a sink) also slip. Issue 1's tuple handling largely covers the first. The others are contrived, so a documented limitation is acceptable.
- Doctrine carve-out still exempts non-prohibitions that contain a prohibition word: "Don't forget to `cat kitty-specs/s/issue-matrix.json`." and "Never skip `cat ...`" both pass. Suggest requiring the prohibition to govern the command directly (e.g. clause matches `^\s*(do not|don't|never)\s*(run|use|call)?\s*$`) and pin these two sentences as negatives.
- False-red risk: `_HAND_BUILT_PATH_RE` runs over every string constant, including docstrings and user-facing hints. A docstring "Never read kitty-specs/<slug>/issue-matrix.json directly" or a hint "Create kitty-specs/<slug>/issue-matrix.md" goes red. Consider skipping docstrings (or only scanning constants that reach a call/sink).
- Flow-insensitivity yields misleading messages: once `matrix_dir` is tainted, `matrix_dir = None` and `matrix_dir = matrix_source` are also reported as partition-swaps. Consider reporting only assignments whose own value mentions a tainted name.
