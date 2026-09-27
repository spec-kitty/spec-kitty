---
work_package_id: WP03
title: 'Mission-review issue-matrix gate partition split + Gate-4 doctrine (IC-02) — #5171'
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-008
planning_base_branch: claude/spec-kitty-ci-failures-r0xui3
merge_target_branch: claude/spec-kitty-ci-failures-r0xui3
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-ci-failures-r0xui3. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-ci-failures-r0xui3 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-matrix-partition-integrity-01M3H10A
base_commit: 991a46898e5b50c080ad2865490cadb284941e78
created_at: '2026-09-27T10:42:18.566835+00:00'
subtasks:
- T009
- T010
- T011
history:
- Created by /spec-kitty.tasks 2026-09-27
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/review/__init__.py
create_intent:
- tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py
- tests/doctrine/test_mission_review_skill_gate4.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/review/__init__.py
- src/charter/offering/skills/spec-kitty-mission-review/SKILL.md
- tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py
- tests/doctrine/test_mission_review_skill_gate4.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load implementer-ivan
```

Apply the resolved initialization, boundaries, directives, and tactics. State which you applied, then continue.

## Objective

Close #5171. Make the mission-review issue-matrix gate read gating **references from PRIMARY** and
**verdicts from COORD/ref** (via the WP02 shared helper), fully separating the two reads that today share
one `feature_dir`. Replace the documented Gate-4 raw `cat` with a resolver-backed read, proven by a
positive control on the rendered doctrine.

Depends on WP02. Read `../plan.md` (IC-02), `../spec.md` (US1, FR-001/002/008), `../contracts/issue-matrix-read.md`.

## Context (confirmed live code)

- `_evaluate_issue_matrix` (`src/specify_cli/cli/commands/review/__init__.py:273`); caller block
  `:424-434` does `issue_matrix_dir = coord_read_dir_for(...) or feature_dir` and feeds ONE dir into BOTH
  `gating_issue_numbers(feature_dir)` (:309) and the matrix read (:315,331) — the conflation that causes
  the FR-001 false FAIL. Separate them: discovery from PRIMARY, matrix from the WP02 helper's coord source.
- Doctrine: `src/charter/offering/skills/spec-kitty-mission-review/SKILL.md:593` — Gate 4 (`### Gate 4:
  Issue matrix (FR-037)` at :590) instructs `cat kitty-specs/<slug>/issue-matrix.json` (raw, unconditional
  PRIMARY). This is the actual #5171 defect for a manual reviewer.
- This repo has NO materialized `.claude/`/`.agents/skills/` copies — edit the SOURCE SKILL.md; the copy
  regeneration is a consumer-side `spec-kitty upgrade` mechanism. Test against SKILL.md directly (pattern:
  `tests/doctrine/test_mission_review_skill_gate3_floor.py`).

## Subtasks

### T009 — Failing-first test (RED before T010/T011)
`tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py`: coord fixture with divergent
matrices (`#11 in-mission` in primary residue, `#11 fixed` on coord surface) → gate PASSes reading coord
(FR-001). Same-fixture control: coord `in-mission` → gate FAILs (probe still sees a real problem). Flat
fixture → reads primary unchanged. Include a post-consolidation arm (worktree gone) via WP01/WP02.
Also `tests/doctrine/test_mission_review_skill_gate4.py`: assert the rendered Gate-4 doctrine references a
resolver-backed read command/API and does NOT contain a raw `cat kitty-specs/.../issue-matrix` (FR-002
positive control, not merely absence). RED on base.

### T010 — Separate discovery from matrix read
In `_evaluate_issue_matrix`, use the WP02 shared helper: `gating_issue_numbers` against the PRIMARY
discovery dir; matrix load/validate against the coord matrix source. Do not feed one dir to both. Preserve
flat-topology behavior.

### T011 — Fix the Gate-4 doctrine (positive read)
Replace the raw `cat` at SKILL.md:593 with a resolver-backed read (point Gate 4 at `spec-kitty review`'s
partition-aware result, or a dedicated `spec-kitty agent issue-matrix show`-style read). It must be a
POSITIVE instruction to read via the resolver — not a deletion that leaves the reviewer reading nothing.

## Definition of Done
- T009 RED on base, GREEN on final; divergent-matrix + in-mission control + flat-unchanged + post-consolidation arms all green.
- Doctrine test proves the rendered Gate-4 references the resolver-backed read (FR-002).
- Re-judge any existing review test that pinned the wrong-partition read — correct it, do not green-wash.
- `ruff`/`ruff format`/mypy clean; terminology guard: `pytest tests/architectural/test_no_legacy_terminology.py -q` (doctrine prose touched).
- Targeted: `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/review tests/doctrine -q`.

## Reviewer guidance
Grep the diff: discovery must read the PRIMARY dir, matrix the coord source — not one dir for both. Confirm
the doctrine change is a positive resolver read (FR-002), not a deletion. Confirm no raw issue-matrix path
remains in the gate.
