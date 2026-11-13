---
work_package_id: WP03
title: Guard and claim bounded at the base
dependencies:
- WP02
requirement_refs:
- FR-003
- FR-006
- FR-007
- C-001
- C-003
- C-005
planning_base_branch: fix/7560-dependency-ref-spine-base
merge_target_branch: fix/7560-dependency-ref-spine-base
branch_strategy: Planning artifacts for this mission were generated on fix/7560-dependency-ref-spine-base. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7560-dependency-ref-spine-base unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-base-window-bound-01M78XB4
base_commit: 7e56e1d36f118cdeed3e20a282bd9e8b0e89f25c
created_at: '2026-11-12T23:35:40.571719+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 3 - Behaviour change
history:
- at: '2026-11-12T22:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/reconciliation_closed_world.py
create_intent:
- tests/consolidation/test_mission_base_claim.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/reconciliation_closed_world.py
- src/specify_cli/consolidation/reconciliation_claim.py
- src/specify_cli/consolidation/reconciliation_claim_types.py
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/forecast.py
- tests/consolidation/test_mission_base_claim.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Guard and claim bounded at the base

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`, and address every item. Record progress with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

FR-003, FR-006, FR-007 and the claim half of FR-004:

- `build_approved_wp_set` resolves the Mission base once (WP02's `resolve_mission_base`), computes the pre-Mission history `window_base..mission_base` (WP02's `pre_mission_history`) and its final per-path state (`_final_authored_walk`, the **same** walk #6771 uses; never a second one), and puts all of it on the claim.
- The #6771 guard drops pre-Mission commits from the **Mission-spine** walk (`_mission_spines`) and the **recorded-tip** walk (`_recorded_work_hit`). The declared ref's own window stays `window_base..ref`: do **not** add `^base` there, or report 2's window empties (challenger finding, research.md).
- Every route (forecast, fresh run, gate rebuild, resume, orchestrator-api) builds its claim through `build_approved_wp_set`, so all of them use the same base (FR-006) with no new `ConsolidationState` field.
- The run and the forecast print one note line when pre-Mission history is non-empty, or when the base is unavailable (FR-007).
- No refusal code, exit code or severity changes (C-001). No new refusal text: a probe failure while resolving the base **degrades to today's bound** (empty pre-Mission history, provenance `unavailable`). That is fail-closed, because it exempts nothing new.

WP01's acceptance tests are expected to **stay xfailed** after this WP: the overlay base commit is still un-attributable on the closed-world axis until WP04. If one of them XPASSes in your lane, do not edit WP01's file. Record it with `add-history`, so WP04 flips it.

## Context & Constraints

- Read: `reconciliation_closed_world.py` (whole module), `reconciliation_claim.py::build_approved_wp_set` and `_refusal_claim`, `reconciliation_claim_types.py::ApprovedWpCommitSet` (the `external_dependency_*` fields at about line 262), `reconciliation.py` (the facade; re-export new public names, C-005), `phase_claim.py` (`_print_degraded_dependency_anchors`, about line 530), and `forecast.py` around line 420 (the claim build and the `json_output` handling).
- PR #7596 (open) also edits `reconciliation_closed_world.py`. Keep your diff local to the functions named here, to make the later rebase easy.
- A2's surfaces are off limits (#7598): consolidate recovery, teardown, resume and refusal text. A note line is not refusal text; do not touch any refusal message.
- Complexity ≤ 15; ruff/format/mypy clean.

## Branch Strategy

- **Planning base branch**: `fix/7560-dependency-ref-spine-base`
- **Merge target branch**: `fix/7560-dependency-ref-spine-base`
- Run `spec-kitty agent action implement WP03 --agent claude --mission mission-base-window-bound-01M78XB4`.

## Subtasks & Detailed Guidance

### Subtask T011 – Claim fields

In `ApprovedWpCommitSet`, next to `external_dependency_*`, add:

```python
mission_base: MissionBase | None = None
pre_mission_shas: frozenset[str] = frozenset()
pre_mission_blobs: frozenset[tuple[str, str]] = frozenset()
pre_mission_deletions: frozenset[str] = frozenset()
```

Give each a docstring comment: history the target lacks that predates the Mission (`window_base..mission_base`), which has the standing of content already on the target (#7560, ADR 2026-09-29-1 amendment). Defaults keep every hand-built claim unchanged.

### Subtask T012 – Resolve in the claim builder

In `build_approved_wp_set`, before `resolve_external_dependency_refs`:

```python
mission_base = resolve_mission_base(repo_root, feature_dir, mission_branch=lanes_manifest.mission_branch, mission_slug=lanes_manifest.mission_slug)
pre_mission = _pre_mission_attribution(repo_root, excluded_window_base, mission_base)   # new small helper
```

- Put `_pre_mission_attribution` in `reconciliation_closed_world.py`, as a frozen dataclass `PreMissionHistory(base, shas, blobs, deletions)`. It calls `pre_mission_history(...)`, then `_final_authored_walk(repo_root, list(shas))` when non-empty.
- On a `GitProbeError` it returns empty sets, with `base` replaced by `MissionBase(None, UNAVAILABLE, reason=f"probe failed: {exc}")`.
- `feature_dir` may be a forecast read-door copy without `meta.json`. That is fine: the resolver then derives. Do not reconstruct paths.
- Pass `pre_mission.shas` into `resolve_external_dependency_refs(..., pre_mission=pre_mission.shas)`, a new keyword parameter with default `frozenset()`.
- Set the four new claim fields on the success-path `ApprovedWpCommitSet(...)`. Also set `mission_base` on `_refusal_claim` (add an optional keyword), so the note can print on a refusal too.
- Keep `build_approved_wp_set`'s complexity under 15. If it is near the limit, extract.

### Subtask T013 – Guard walks

- `_mission_spines(..., pre_mission: frozenset[str] = frozenset())`: skip any sha in `pre_mission` for **both** the lane spines and the Mission-branch spine. Lane spines are bounded by `coord_base_ref` and descend from the base, so this is defensive there. Keep the label text unchanged.
- `_recorded_work_hit(..., pre_mission=...)`: `in_window = set(window) - pre_mission`.
- `_verify_declared_ref`: unchanged, except that it passes the pruned structures. `window` stays `commits_in_range(window_base, tip)`.
- Update the docstrings of `_mission_spines` and `resolve_external_dependency_refs`. Mission work is what the Mission authored *after its base*; history the target lacks below the base is pre-Mission (#7560). Name the ADR amendment.

### Subtask T014 – Provenance note

One helper, `mission_base_note(claim) -> str | None`, in `reconciliation_closed_world.py`:

- `pre_mission_shas` non-empty → `"Mission base {sha[:10]} ({provenance}{': ' + reason if reason else ''}): {n} commit(s) of history the target lacks predate this Mission and are not judged as Mission work (#7560)."`
- `provenance == UNAVAILABLE` → `"Mission base unavailable ({reason}); reconciliation windows are bounded by the target's pre-run tip only."`
- Otherwise `None`.

Print it in `phase_claim.py` right after the claim is built (next to `_print_degraded_dependency_anchors`, same console style), and in `forecast.py` after `build_claim` **only when not `json_output`**, so the JSON stays valid. Do not add JSON fields.

### Subtask T015 – Facade + unit tests

- Re-export `PreMissionHistory` and `mission_base_note` from `reconciliation.py`, following the existing `as` re-export style, and add them to the right `__all__`. If tests patch through `tests/consolidation/reconciliation_family.py`, check whether a new module family entry is needed.
- `tests/consolidation/test_mission_base_claim.py`, built on the `merged_dependency_repo` style from `test_dependency_ref_claim.py` (a self-contained tmp repo):
  1. Fork shape (the window base lacks the Mission base; the base's parent is the pin), with `resolve_external_dependency_refs(... pre_mission=<range>)`. The pin declared → no refusal. Without `pre_mission` → `DEPENDENCY_REF_COVERS_MISSION_WORK`, which is the red control.
  2. A post-base commit on the Mission branch declared through a side branch → still refuses with `pre_mission` supplied.
  3. A recorded-tip walk: a lane-tip ref whose first-parent history includes pre-Mission commits plus a post-base commit → refuses on the post-base commit only.
  4. `_pre_mission_attribution` with a probe failure (monkeypatch `pre_mission_history` to raise `GitProbeError`) → empty sets, `UNAVAILABLE`.
  5. `mission_base_note` for the three cases.
  6. `build_approved_wp_set` on a fixture where the target reaches the base: the claim's `pre_mission_shas` is empty and every other field equals the claim built before this WP. Compare against a build with `resolve_mission_base` monkeypatched to `UNAVAILABLE` (NFR-001).

## Test Strategy

```bash
.venv/bin/python -m pytest tests/consolidation/test_mission_base_claim.py tests/consolidation/test_dependency_ref_claim.py tests/consolidation/test_dependency_ref_attribution_6771.py tests/consolidation/test_dependency_ref_forecast.py tests/consolidation/test_claim_inputs_parity.py -q
.venv/bin/python -m pytest tests/consolidation -q -n auto --dist loadfile     # owning subsystem
.venv/bin/python -m pytest tests/architectural/test_single_rollback_authority.py -q 2>/dev/null || .venv/bin/python -m pytest tests/consolidation/test_single_rollback_authority.py -q
uv run --frozen ruff check <files>; uv run --frozen ruff format --check --force-exclude <files>; uv run --frozen mypy <src files>
```

## Risks & Mitigations

- **Bypass risk**: a too-wide `pre_mission` set would exempt Mission work. It is exactly `window_base..base`, and the base is validated as an ancestor of the Mission branch (WP02), so every commit in it is an ancestor of the base. Mission work is never an ancestor of the base. Pin this with test 2.
- **Cost**: `_final_authored_walk` over a large pre-Mission range only runs on forks; that is acceptable.

## Review Guidance

- The declared window is unchanged (`target..ref`).
- No refusal text or code changed; a probe failure degrades to today's bound.
- The facade re-exports, and the existing consolidation suite is green.
