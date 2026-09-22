---
work_package_id: WP01
title: Charter recompile preserves recorded mission type (#4908)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
planning_base_branch: fix/silent-destructive-write-hardening
merge_target_branch: fix/silent-destructive-write-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/silent-destructive-write-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/silent-destructive-write-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-silent-destructive-write-hardening-01M355VK
base_commit: 286b75cccb0cbfeb6cc7e65550337527c27bba81
created_at: '2026-09-22T18:42:07.825825+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/charter/generate.py
- src/specify_cli/cli/commands/charter/activate.py
- src/specify_cli/cli/commands/charter/pack.py
- tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile via `/ad-hoc-profile-load`
(profile: `python-pedro`, role: `implementer`). Adopt its identity, boundaries, and discipline
for the whole work package.

## Objective

Fix #4908: the post-activation charter catalog recompile hardcodes the mission type to
`software-dev`, discarding the project's recorded mission type. On a `research` project, a single
`charter activate` flips `catalog.mission` research→software-dev, flips `template_set`
research-default→software-dev-default, drops `catalog.references` from 268→165, exits 0, writes no
backup. The same defect is in `charter deactivate` (same recompile) and `charter pack apply --compile`.

## Structural root cause (SSOT violation)

The recorded mission type has an SSOT: `.kittify/charter/interview/answers.yaml` `mission:` and,
once compiled, `charter.yaml` `catalog.mission`. The recompile path deliberately sets
`from_interview=False` (a #2940 guard so a malformed answers file cannot abort a recompile), then
passes `resolved_mission_type=None`, so `_load_interview_for_generate` reads NEITHER SSOT and
collapses to the `"software-dev"` literal at `generate.py:249`. It is a derived-view writer
(rebuilding `catalog.references`) that recomputes an input it should read from the source of truth.

## Guidance per subtask

### T001 — Red-first regression test
Add `tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py` with a
`@pytest.mark.regression` test pinned to #4908. Reproduce through the real entry point: generate a
charter for `--mission-type research`, run `charter activate directive 025-boy-scout-rule`, and
assert `catalog.mission == "research"`, `catalog.template_set == "research-default"`, and
`len(catalog.references)` does not shrink. This test MUST be RED before the fix (witness the flip).
Follow the QA repro in the issue for the exact CLI shape.

### T002 — Read recorded mission type from the SSOT (generate.py:249)
Replace the `resolved_mission = resolved_mission_type or "software-dev"` fallback with a read of the
recorded mission. Preferred: a small helper that resolves the recorded mission from
`charter.yaml` `catalog.mission` (guaranteed present at the activate recompile guard) and/or
`answers.yaml` `mission:` — used as the fallback in place of the literal, so BOTH the activate and
pack callers are fixed at one seam. **Do NOT flip `from_interview=True`** — that reintroduces the
#2940 abort-on-malformed-answers regression. Keep `"software-dev"` only as the last-resort default
when neither SSOT is present (a brand-new project with no charter — not the recompile path).

### T003 — Thread through the activate.py recompile call site (:558-566)
Ensure `recompile_catalog` / `recompile_or_notify` pass the recorded mission type (or that the
generate helper reads it) so `compile_charter(mission=...)` receives the project's actual mission.

### T004 — pack apply --compile (pack.py:208-217)
Apply the same SSOT read to the `pack apply --compile` recompile call site (identical
`from_interview=False, resolved_mission_type=None` shape). Confirm with a test assertion or by
sharing the T002 helper.

### T005 — Focused unit tests + #2940 guard
Unit-test the SSOT-read helper: (a) `charter.yaml` present with `catalog.mission: research` →
returns `research`; (b) `answers.yaml` present, no compiled charter → returns its `mission`;
(c) malformed `answers.yaml` → recompile does NOT abort (guard preserved), falls back to the
recorded compiled mission. Cover deactivate path if it shares the recompile.

## Definition of Done

- T001 regression RED before, GREEN after.
- `catalog.mission` / `template_set` preserved and `catalog.references` non-shrinking across
  `activate`, `deactivate`, and `pack apply --compile`.
- #2940 malformed-answers guard intact (no `from_interview=True` flip).
- Blast radius green: `tests/specify_cli/cli/commands/charter/` (+ `tests/charter/`, `tests/doctrine/`
  if touched). `ruff check`, `ruff format --check`, `mypy` clean. Touched functions ≤15 complexity.

## Reviewer guidance

Verify the fix reads the SSOT rather than threading a hardcoded default; confirm the deactivate and
pack paths are covered (not just activate); confirm the #2940 guard is preserved; confirm the
regression test fails on merge-base.
