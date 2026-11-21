---
work_package_id: WP03
title: Mutation-proven mode-equality ratchet gate and changelog
dependencies:
- WP02
requirement_refs:
- FR-010
- NFR-004
- SC-003
- C-006
planning_base_branch: issue-4927-host-aware-mode-predicate
merge_target_branch: issue-4927-host-aware-mode-predicate
branch_strategy: Planning artifacts for this mission were generated on issue-4927-host-aware-mode-predicate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4927-host-aware-mode-predicate unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-host-aware-mode-predicate-01M7X6B1
base_commit: a0927aaf3ae29401eb989f1b46a8c87e6c802c2c
created_at: '2026-11-21T05:56:10.152165+00:00'
subtasks:
- T011
- T012
- T013
phase: Phase 3 - Close the class by construction
history:
- at: '2026-11-20T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_mode_equality_authority.py
- tests/architectural/_mode_equality_scan.py
- docs/changelog/unreleased/4927.fixed.md
execution_mode: code_change
owned_files:
- tests/architectural/test_mode_equality_authority.py
- tests/architectural/_mode_equality_scan.py
- docs/changelog/unreleased/4927.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Mutation-proven mode-equality ratchet gate and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP03 --note "..."`.

## Objectives & Success Criteria

- `tests/architectural/test_mode_equality_authority.py` fails, naming file:line, whenever a module under `src/specify_cli/{skills,tool_surface,runtime}` decides mode equality outside the predicate in `tool_surface/operations.py` (FR-010).
- The exemption table lists only adjudicated observed-vs-observed guards and planned-vs-planned conflict checks, each with a rationale; a stale exemption fails (US5 scenario 2).
- Non-vacuity: a scanned-node floor; self-mutation (synthetic module) flagged by each pattern; live mutation (a copy of `asset_preparation.py` with a raw compare) flagged (SC-003).
- Runs < 5 s (NFR-004).
- Changelog fragment `docs/changelog/unreleased/4927.fixed.md` records the fix and the project-skill semantic change (C-006).

## Context & Constraints

- Charter Standing Order #5 / `architectural-gate-non-vacuity` tactic / ADR `2026-09-30-1`: prefer empty allowlists; these exemptions are permanent classifications (not debt) so no `_baselines.yaml` entry. Say so in the module docstring.
- Look at an existing AST gate for house style: `tests/architectural/_no_follow_symlinks_apply_scan.py` + `test_no_follow_symlinks_apply_ban.py` (scan helper split from test; exemption file pattern under `tests/architectural/_exemptions/`). Mirror its structure; keep the exemption table in Python (a tuple of dataclasses with `file`, `qualname`, `pattern`, `rationale`) or in an `_exemptions/*.txt` file — choose the house style that fits rationale-per-entry best.
- Changelog: `docs/changelog/unreleased/README.md` defines the fragment format; run `uv run --frozen --no-sync python -m scripts.docs.check_changelog_style`.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-4927-host-aware-mode-predicate`
- **Merge target branch**: `issue-4927-host-aware-mode-predicate`

Implement with: `spec-kitty agent action implement WP03 --agent claude --mission host-aware-mode-predicate-01M7X6B1`

## Subtasks & Detailed Guidance

### Subtask T011 – Red: self-mutation and stale-exemption tests

- In `test_mode_equality_authority.py`, write the tests first against the scan API you are about to build (`scan_source(source: str, filename: str) -> list[Finding]`, `scan_tree(roots) -> list[Finding]`):
  - `test_flags_raw_mode_compare` (P1): synthetic source `def f(before, after):\n    return before.mode != after.mode` → one finding.
  - `test_flags_stat_imode_compare` (P1): `stat.S_IMODE(p.lstat().st_mode) != after.mode` → finding.
  - `test_flags_planned_stamp_equality` (P2): `if observed != effect.after: ...` → finding; `previous.after == effect.after` (both planned) → no finding.
  - `test_flags_stamp_substitution` (P3): `replace(original, state=replace(original.state, mode=effect.after.mode))` → finding.
  - `test_stale_exemption_fails`: an exemption naming a non-existent qualname → reported stale.
  - `test_live_tree_is_clean`: `scan_tree` over the real roots minus exemptions → empty.
- Red because the scan module does not exist. Commit alone.

### Subtask T012 – The gate

- `tests/architectural/_mode_equality_scan.py`: `ast` walk of every `*.py` under the three roots. Track enclosing `qualname` (class.func). Patterns:
  - **P1**: `ast.Compare` with `Eq`/`NotEq` where any operand subtree contains `ast.Attribute(attr="mode")` or a call whose func ends in `S_IMODE`.
  - **P2**: `ast.Compare` with `Eq`/`NotEq` where exactly one side is a planned stamp: `ast.Attribute(attr="after")`, or a `replace(...)` call with keyword `state=<…>.after`.
  - **P3**: `ast.Call` to `replace` with keyword `mode=` whose value is `<…>.after.mode`.
  - Allowed: any node inside `src/specify_cli/tool_surface/operations.py` functions `modes_equivalent`, `mode_equivalent`, `state_equivalent`, `effect_action`.
- Exemption table: one row per adjudicated site from research R-4 that still matches a pattern after WP02 (expected: `projection.same_observation`, finalize fstat triple, staged-member conflict, `operations` identical-effect merge, `asset_preparation` conflicting outputs, `installer` / `agent_profiles` before-guards only if they match P2 — they compare `.before`, so likely not). Each row's rationale names it guard vs conflict. Run the scan and adjudicate every hit — never exempt a planner; if a planner hits, it is a WP02 miss → fix it (small out-of-map edit with a one-line rationale in history) or bounce WP02.
- Floor: assert the scan visited ≥ N `Compare` nodes (set N to ~80% of the observed count) and ≥ 1 file per root, so an empty glob cannot pass.

### Subtask T013 – Live mutation + changelog

- `test_live_mutation_is_caught`: read `src/specify_cli/runtime/asset_preparation.py`, inject `def _mutant(before, after):\n    return "chmod" if before.mode != after.mode else None\n` (or textual replace of `effect_action(` usage with a raw compare), scan the mutated source with the same filename → ≥ 1 finding.
- `docs/changelog/unreleased/4927.fixed.md`: user-facing, plain language: on Windows, a converged project and home no longer re-plan permission repairs on every start and in `upgrade --dry-run` (#4927); read-only drift on Windows is now repaired for project skills, where file modes were previously ignored entirely; maintainers: one host-aware predicate + an architectural gate (#4810). Follow the README's section/fragment rules.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/architectural/test_mode_equality_authority.py -q --durations=5
.venv/bin/python -m pytest tests/architectural/test_layer_rules.py tests/architectural/test_no_follow_symlinks_apply_ban.py -q
uv run --frozen --no-sync python -m scripts.docs.check_changelog_style
.venv/bin/ruff check tests/architectural/test_mode_equality_authority.py tests/architectural/_mode_equality_scan.py && .venv/bin/ruff format --check --force-exclude tests/architectural/test_mode_equality_authority.py tests/architectural/_mode_equality_scan.py
.venv/bin/mypy --explicit-package-bases tests/architectural/_mode_equality_scan.py
```

## Risks & Mitigations

- Over-match → exemption rows with rationale; under-match → self- and live-mutation controls.
- Don't widen `test_os_detection_ban` here (follow-up issue, plan Charter Check).

## Review Guidance

- Each exemption is a genuine guard/conflict (read the line), never a planner.
- Mutation tests actually fail when the scan is weakened (reviewer: temporarily drop P1 and observe red).
- Gate < 5 s.

## Progress & Status

Use `spec-kitty agent tasks add-history WP03 --note "..."` and `spec-kitty agent tasks move-task WP03 --to <status>`.
