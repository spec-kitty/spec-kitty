---
work_package_id: WP04
title: Verifier axes bounded at the base
dependencies:
- WP01
- WP03
requirement_refs:
- FR-004
- FR-005
- NFR-001
- NFR-004
- C-002
planning_base_branch: fix/7560-dependency-ref-spine-base
merge_target_branch: fix/7560-dependency-ref-spine-base
branch_strategy: Planning artifacts for this mission were generated on fix/7560-dependency-ref-spine-base. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7560-dependency-ref-spine-base unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-base-window-bound-01M78XB4
base_commit: 0c69f54a909b1b777f98a46624fdbc44917ce785
created_at: '2026-11-13T00:25:24.648280+00:00'
subtasks:
- T016
- T017
- T018
- T019
phase: Phase 3 - Behaviour change
history:
- at: '2026-11-12T22:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/reconciliation_verifier.py
create_intent:
- tests/consolidation/test_mission_base_verifier.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/reconciliation_verifier.py
- tests/consolidation/test_mission_base_verifier.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Verifier axes bounded at the base

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`, and address every item. Record progress with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Objectives & Success Criteria

This WP covers the verifier half of FR-004, plus FR-005 and NFR-001. On every window axis, history reachable from the Mission base that the target lacks (`claim.pre_mission_*`, built by WP03) has the standing of content already on the target, exactly like a verified declared dependency (`claim.external_dependency_*`):

- **Closed world** (`_unattributable_patch_id`): a sha in `claim.pre_mission_shas` is not a divergence. This covers the landed-target scan and the forecast scan (`_unattributable_in`), because both run the same per-commit filter.
- **Squash** (`_unattributable_content_squash`): `(path, blob) in claim.pre_mission_blobs` is attributable, and a `D` path in `claim.pre_mission_deletions` is attributable.
- **Vacuous squash** (`_window_has_non_bookkeeping_change`): a `D` path in `pre_mission_deletions` is not content. An A/M path whose target blob is in `pre_mission_blobs` is not content either; that reads the blob, so keep the cost bounded to the A/M paths.
- **Patch-id window** (`_reachable_excluded`): the window's patch-ids exclude those of `pre_mission_shas`. Compute `patch_ids_in_range(window_base, target)` minus `{patch_id_of(s) for s in pre_mission_shas}`, but only when `pre_mission_shas` is non-empty (NFR-001 / NFR-002: zero extra probes otherwise).
- WP01's strict xfails now pass. Remove their `xfail` marks: this is the one allowed out-of-map edit, to `tests/consolidation/test_dependency_ref_mission_base_7560.py`, and the rationale is the flip WP01 planned. The ratchets stay green.

The approved-bound and canceled-content axes are **not** changed (dispatch non-goal; plan.md Charter Check).

## Context & Constraints

- Read `reconciliation_verifier.py`: lines about 540–640 (`_reachable_excluded`, `_unattributable_content`, `_unattributable_in`, `_unattributable_patch_id`) and 680–830 (the squash axes).
- Mirror the existing `external_dependency_*` checks; they are the model. Update the docstrings that describe the external dependency exemption so they also name the pre-Mission history (#7560).
- Complexity ≤ 15. `_unattributable_content_squash` is close to the limit, so extract a helper such as `_attributed_outside_mission(path, blob, claim)` that holds the external-dependency check, the pre-Mission check and the three-way-resolution check.
- C-001: no refusal code or text changes. C-002: no rollback change.

## Branch Strategy

- **Planning base branch**: `fix/7560-dependency-ref-spine-base`
- **Merge target branch**: `fix/7560-dependency-ref-spine-base`
- Run `spec-kitty agent action implement WP04 --agent claude --mission mission-base-window-bound-01M78XB4`.

## Subtasks & Detailed Guidance

### Subtask T016 – Closed-world filter

In `_unattributable_patch_id`, next to `if sha in claim.external_dependency_shas: return None` (about line 626), add the same for `claim.pre_mission_shas`, with a comment.

### Subtask T017 – Squash axes

- `_unattributable_content_squash`: deletions are attributable when the path is in `authored_deletions`, `external_dependency_deletions` or `pre_mission_deletions`; blobs likewise, through the extracted helper.
- `_window_has_non_bookkeeping_change`: skip `D` paths in `pre_mission_deletions`. For A/M paths, when `claim.pre_mission_blobs` is non-empty, read the blob and skip it when `(path, blob)` is in that set. When `pre_mission_blobs` is empty, keep today's no-blob-read path.
- Edge: a path the Mission changed after the base has a target blob that is not the pre-Mission final blob, so it is judged as today. Pin that in a test.

### Subtask T018 – Patch-id window

As described in the objectives. Write it as a helper so `_reachable_excluded` stays readable.

### Subtask T019 – Flip xfails; unit tests

- Remove the `xfail` marks in WP01's module. Every test must pass.
- `tests/consolidation/test_mission_base_verifier.py`, with hand-built claims (`_claim(...)` style from `test_dependency_ref_claim.py`) on small tmp repos:
  1. Closed world: a pre-Mission sha in the window → not flagged. The same sha with empty `pre_mission_shas` → flagged (same-fixture control).
  2. Squash blob: target blob equal to the pre-Mission final blob → attributable. A post-base modification of that path → still unattributable.
  3. Squash deletion: a path deleted in the pre-Mission range → attributable. A post-base deletion of a pre-existing path with no WP authoring it → still unattributable.
  4. Vacuous squash with only pre-Mission content → PASS; with an extra post-base content path → REFUSE, as today.
  5. Patch-id window: a canceled WP's patch-id equal to a pre-Mission commit's patch-id is not reported as reachable through that pre-Mission commit, but is still reported when it is reachable through a post-base commit.
  6. NFR-001: with empty `pre_mission_*`, every verdict equals today's. Parametrise over the existing claim helper.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/consolidation/test_mission_base_verifier.py tests/consolidation/test_dependency_ref_mission_base_7560.py -q -rxX
.venv/bin/python -m pytest tests/consolidation -q -n auto --dist loadfile
make test-fast
uv run --frozen ruff check <files>; uv run --frozen ruff format --check --force-exclude <files>; uv run --frozen mypy src/specify_cli/consolidation/reconciliation_verifier.py
```

## Risks & Mitigations

- **Over-exemption**: an exemption is keyed on the exact pre-Mission sha, or on the exact `(path, blob)` final state, never on a path alone. A post-base change always produces a different blob or commit. Tests 2, 3 and 5 pin this.
- **Complexity creep** in the squash loop: extract helpers.

## Review Guidance

- Each exemption is a mirror of the `external_dependency_*` one, with a same-fixture control.
- WP01's ratchets are still green; the xfails are removed rather than skipped.
- No change to the approved-bound or canceled-content axes.
