---
work_package_id: WP01
title: Declaration resolution, claim threading and verifier exemptions
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-003
- SC-004
planning_base_branch: issue-6771-consolidate-dependency-ref-attribution
merge_target_branch: issue-6771-consolidate-dependency-ref-attribution
branch_strategy: Planning artifacts for this mission were generated on issue-6771-consolidate-dependency-ref-attribution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6771-consolidate-dependency-ref-attribution unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-dependency-ref-attribution-01M67J2A
base_commit: 8e4ec233ac3854358e8143159f0c7616c8ed8b6c
created_at: '2026-10-30T23:27:30.432563+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Claim attribution
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/reconciliation.py
create_intent:
- tests/consolidation/test_dependency_ref_claim.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation.py
- tests/consolidation/test_dependency_ref_claim.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6771'
---

# Work Package Prompt: WP01 – Declaration resolution, claim threading and verifier exemptions

## Goal

A lane that merged an external dependency branch's newer head is not "removed work". Give the
claim builder a verified, explicit declaration (`external_dependency_refs`) whose commits are
treated exactly like commits that predate the closed-world window, and make every
mis-declaration REFUSE before any ref moves.

## Red first (T001)

`tests/consolidation/test_dependency_ref_claim.py`, written before the fix and failing on
`main`:

1. **Exemption** — a real git repo with a base, one approved lane commit, and a two-parent
   merge of an external branch into the lane; a production-shaped claim
   (`enforce_closed_world=True`, `excluded_window_base=<base>`, `authored_shas={lane commit}`)
   with `external_dependency_shas` holding the merge's second-parent commits verifies PASS on
   the merged tip; the same claim without the exempt set FAILs `unattributable_content`.
2. **Spine guard** — declaring a ref whose commits include a commit on an approved lane's
   first-parent spine REFUSEs, and the refusal names the commit and the spine.
3. **Unresolvable ref** — REFUSE naming the ref; **never merged in** (not reachable from the
   mission branch) — REFUSE.
4. **No declaration** — `build_approved_wp_set` with no refs performs no declaration probe and
   yields the same claim fields as today (empty exempt sets).
5. **Squash** — the exempt `(path, blob)`/deletion sets silence the blob axis for the same
   content and nothing else.

Drive `build_approved_wp_set` + `MergeOutcomeVerifier` directly (see
`tests/consolidation/test_canceled_dependency_attribution.py` for the claim-level pattern) and
build the repository with plain `git` (`tests/terminus/conftest.py::_git`).

## Implementation (T002–T005)

- `resolve_external_dependency_refs(repo_root, *, refs, window_base, mission_branch, lanes_manifest, coord_base_ref)`
  returns a frozen `ExternalDependencyAttribution(refs, shas, blobs, deletions, refusal)`.
  No refs → empty result, **no git probe** (NFR-001).
  Per ref: resolve (`git_probes.resolve_commit`); require the mission branch to reach it;
  exempt set = `commits_in_range(window_base, ref)`; spine guard = the union of every lane's
  first-parent spine (`first_parent_commits_in_range(coord_base_ref, lane_branch)`, tolerant of
  an unresolvable lane exactly as `_lane_first_parent_spine` is) and the mission branch's
  first-parent spine; any exempt commit on that union → REFUSE naming the commit, the ref and
  the spine. Blobs/deletions come from the SAME `_final_authored_walk` over the exempt commits
  (C-002 — never a second walk). A `GitProbeError` anywhere → REFUSE (NFR-002), never PASS.
- `ApprovedWpCommitSet`: `external_dependency_refs`, `external_dependency_shas`,
  `external_dependency_blobs`, `external_dependency_deletions` (all empty by default, so a
  hand-built claim is unchanged — NFR-003).
- `build_approved_wp_set(..., external_dependency_refs: Sequence[str] = ())`: resolve after the
  window base is known and before the collectors; a refusal goes through `_refusal_claim` so it
  refuses at claim time (`claim_integrity_refusal`), before mutation.
- Verifier: factor the per-commit window filter into `_unattributable_in(refs, claim)` used by
  `_unattributable_content` (one ref) and by the forecast (WP02); skip a commit whose SHA is in
  `external_dependency_shas`, with a comment tying it to "history that predates the window".
  Squash axis: skip `(path, blob)` in `external_dependency_blobs` and `path` in
  `external_dependency_deletions`.
- `VerifyResult` gains an optional `attribution_hint`; `verify()` sets it when it produced
  un-attributable divergences and the claim declared no refs, and `recovery_guidance()` appends
  it. `Divergence.describe()` wording is pinned by the terminus suites — do not touch it.

## Definition of done

- New tests pass; `tests/consolidation/`, `tests/terminus/test_repro_4945.py`,
  `tests/terminus/test_repro_5013*.py` (whichever exist), `tests/consolidation/test_reconciliation*.py`
  stay green; `ruff check` and `ruff format --check` clean on the touched files.
