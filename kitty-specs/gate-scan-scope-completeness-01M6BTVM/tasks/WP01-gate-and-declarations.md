---
work_package_id: WP01
title: The completeness gate and the declarations it proves missing
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-7000-gate-scan-scope-completeness
merge_target_branch: issue-7000-gate-scan-scope-completeness
branch_strategy: Planning artifacts for this mission were generated on issue-7000-gate-scan-scope-completeness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7000-gate-scan-scope-completeness unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
history: []
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/_gate_read_scope.py
- tests/architectural/test_gate_scan_scope_completeness.py
execution_mode: code_change
owned_files:
- tests/architectural/_gate_read_scope.py
- tests/architectural/test_gate_scan_scope_completeness.py
- .github/ci-module-registry.yml
- .github/workflows/ci-router.yml
- .github/ci-shard-timings.json
role: implementer
tags: []
tracker_refs:
- '#7000'
---

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` (`spec-kitty agent profile show python-pedro`) before reading anything else.

## Objective
Add the static completeness gate for #7000 and fix the declarations it proves missing, so the gate
lands green on the live tree. **FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002,
NFR-003.**

## Context (grounded on 287a226cfe)
- `.github/ci-module-registry.yml` `special_tiers.architectural.scan_scopes` declares 98 gate rows;
  `scripts/ci/gate_selection.py` derives the `arch_scan_scope` router group and the per-gate scoped
  selection from them.
- `tests/architectural/test_battery_scan_scope_routing.py` proves routing for *declared* globs and
  pins the router transcription. Nothing checks that a declaration is *complete*.
- 137 files under `tests/architectural/` read the repository through
  `Path(__file__).resolve().parents[2]`. A prototype scan finds 34 undeclared reads over 19 gates;
  32 are real tracked reads, 2 are not repository reads (a synthetic `.nonexistent-home` probe and
  an untracked `.pytest_cache/...` dir).
- Code scope (what already runs the whole battery) is stated by the router, not by a separate list:
  `Router.job_gates[HEAVY_BATTERY_JOB] - {BATTERY_SCOPE_GROUP}` gives `architectural` +
  `ci_config` + the module groups.

## Guidance
**T001 — the scanner** (`tests/architectural/_gate_read_scope.py`, AST + pathlib only):
- repo-root names: `X = Path(__file__).resolve().parents[2]`, `X = _THIS.parents[2]` (`_THIS =
  Path(__file__)`), and any name assigned a chain rooted at one (`_SRC = _REPO_ROOT / "src"`).
- reads: maximal `BinOp(Div)` chains rooted at those names; constant components stay literal, a
  non-constant right operand becomes `*`; also `X.glob(...)`, `X.rglob(...)`, `X.iterdir()`,
  `X.walk()`.
- ownership: gate set = `tests/architectural/test_*.py`; a read inside a `tests.architectural`
  helper module belongs to every gate that imports it transitively (`import_closure`).
- coverage: prefix covered when it matches a declared glob of the owning gate or the code scope
  (`fnmatch` against the prefix and `<prefix>/__probe__`); a dynamic read requires its literal
  parent `<prefix>/**`; a bare-root read requires `**`.
- `EXEMPT_READS: Mapping[str, Mapping[str, str]]` (gate → exact prefix → reason), and
  `validate_exemptions()` returning problems for an empty reason, a `**` prefix, an unknown gate,
  or an entry that is no longer needed (stale).
- `uncovered_reads(gates=..., registry_path=..., router=..., root=...) -> tuple[Finding, ...]`,
  pure over its inputs so the WP02 controls can mutate them. Never swallow a parse error.

**T002 — the gate** (`tests/architectural/test_gate_scan_scope_completeness.py`, markers
`architectural` + `fast`): the live property; a non-vacuity floor (≥ 90 gates, ≥ 300 reads); each
exemption non-empty, narrow and still needed; an unparseable gate file raises with its path.

**T003 — declarations**: run the gate red first and record the failure list; then fix each row
minimally (a new row where the gate has none), re-derive the `arch_scan_scope` block with
`gate_selection.battery_scope_router_globs()` (do not hand-edit the list), add a
`battery_file_durations.architectural` entry for the new gate file, and update the registry comment
block. `tests/architectural/test_battery_scan_scope_routing.py`,
`tests/architectural/test_workflow_coherence.py` and `tests/ci/test_battery_roster_budgets.py`
must stay green.

## Definition of Done
- The gate reds on a planted undeclared read and greens on the live tree.
- No gate is skipped, xfailed or weakened; `scripts/ci/gate_selection.py` is unchanged.
- `PWHEADLESS=1 uv run --frozen pytest -q -p no:randomly tests/architectural/test_gate_scan_scope_completeness.py tests/architectural/test_battery_scan_scope_routing.py tests/architectural/test_workflow_coherence.py tests/ci/test_battery_roster_budgets.py` green;
  `uv run --frozen ruff check .` and `ruff format --check .` clean.
