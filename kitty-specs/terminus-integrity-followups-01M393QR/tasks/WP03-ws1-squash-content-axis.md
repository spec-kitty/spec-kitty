---
work_package_id: WP03
title: WS1 squash-sound content axis
dependencies: []
requirement_refs:
- FR-001
planning_base_branch: fix/terminus-integrity-followups
merge_target_branch: fix/terminus-integrity-followups
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-integrity-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-integrity-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-integrity-followups-01M393QR
base_commit: 638999414cf002ae8317d5742f36aba29483f1e7
created_at: '2026-09-24T08:00:21.866467+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Parallel fan (file-isolated)
history:
- at: '2026-09-24T07:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/reconciliation.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/merge/git_probes.py
- src/specify_cli/merge/reconciliation.py
- tests/merge/test_git_probes_seam.py
- tests/merge/test_reconciliation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – WS1 squash-sound content axis

## ⚡ Do This First: Load Agent Profile
Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before
reading further. State what you applied, then continue.

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks.

## Objectives & Success Criteria

Deliver the P0 (#5013) fix: a **squash-sound blob-attribution** content axis so the DEFAULT squash merge
fails-closed when a removed/canceled WP's content is on the target. Content identity (blob), never lane-tip
SHAs or patch-ids (both destroyed by squash). Success (FR-001):

- New git probes in `merge/git_probes.py`: `blob_id_at`, `changed_paths_in_range(--no-renames)`, and
  `first_parent_commits_in_range` **propagates** `GitProbeError` (today it returns `[]` on error — fail-open,
  post-plan F7).
- `ApprovedWpCommitSet.authored_blobs`: the **FINAL** first-parent-authored blob **per (lane, path)**
  (post-plan F5 — union-of-all admits superseded intermediate blobs and false-PASSes; final-per-(lane,path)
  is the crux that makes the 3-way defer sound).
- `_unattributable_content_squash`: iterate `git diff --name-status B..T` (`--no-renames`), for each **A/M**
  path get `blob_id_at(T,path)`; an unexpected empty blob for an A/M path ⇒ **REFUSE** (never infer deletion
  from a rev-parse failure — post-plan F1); if `(path, blob) not in authored_blobs` ⇒ FAIL naming the path.
- REORDER so the `excluded_window_base is None` REFUSE and a new **empty-`authored_blobs`-while-`approved`-nonempty**
  REFUSE both fire for squash — i.e. above the `verify_reachability=False` early-return (F1 corollary).
- Bookkeeping paths excluded via the existing `_is_bookkeeping_path`.

**Read first**: `work/epic-5001-research/followup-architect.md`, `contracts/invariants.md` (INV-1),
`data-model.md` (§1 + derived predicate), and the current `merge/reconciliation.py` (`MergeOutcomeVerifier.verify`
~line 263, the squash early-return ~301, `_collect_authored`, `build_approved_wp_set`, `_is_bookkeeping_path`)
and `merge/git_probes.py`. Verify all line anchors. Tests: `PWHEADLESS=1 .venv/bin/python -m pytest
tests/merge/test_reconciliation.py tests/merge/test_git_probes_seam.py -o addopts="" -q`.

## Subtasks

### T011 — git probes (merge/git_probes.py)
- `blob_id_at(repo, ref, path) -> str`: `git rev-parse <ref>:<path>`; raise `GitProbeError` on git error.
  Caller distinguishes "A/M path but empty" (error → REFUSE) from "D path" (skipped before calling).
- `changed_paths_in_range(repo, base, tip) -> list[str]`: `git diff --name-status --no-renames <base>..<tip>`;
  return `(status, path)` pairs (or a typed result) so the caller filters A/M vs D. `--no-renames` matches
  `_collect_authored`'s `changed_paths_of` (post-plan F6). Raise `GitProbeError` on git error.
- `first_parent_commits_in_range`: change the `return []`-on-error to **raise** `GitProbeError` (F7); update
  callers to handle (they already fail-closed on the raising `commits_in_range`).

### T012 — authored_blobs FINAL-per-(lane,path) (merge/reconciliation.py)
- In `_collect_authored` / `build_approved_wp_set`, compute for each approved lane its first-parent authored
  paths and record the **final** `(path, blob_id_at(lane_tip, path))` per (lane, path) — walk first-parent
  newest→oldest and keep the first (newest) blob seen per path, or diff `merge_base..lane_tip` and read the
  tip blob. Union across lanes into `authored_blobs: frozenset[tuple[str,str]]`. Always the `(path, blob)`
  tuple, never blob-only (F10 — catches identical-content-different-path).

### T013 — _unattributable_content_squash + reorder (merge/reconciliation.py)
- Add `_unattributable_content_squash(self, target_ref)` per the data-model derived predicate (A/M only,
  REFUSE on unexpected "", skip D, exclude bookkeeping via `_is_bookkeeping_path`, FAIL naming the path).
- In `MergeOutcomeVerifier.verify`, REORDER so: (1) the hoisted vacuous-manifest REFUSE (already above),
  (2) a NEW `if approved non-empty and not authored_blobs: REFUSE`, (3) the `excluded_window_base is None`
  REFUSE — all fire BEFORE the `if not verify_reachability: return passed()` early-return. Then, on the squash
  path (verify_reachability False) run `_unattributable_content_squash`; FAIL ⇒ returns a FAIL result that the
  executor's existing rollback path consumes. Do NOT weaken the merge/rebase path.
- Keep the change additive to the existing `enforce_closed_world` opt-in (only the production builder turns it
  on; hand-built claims keep pre-widening behavior).

### T014 — unit tests (tests/merge/test_reconciliation.py) — **RED-FIRST**
Write these failing-first (against the current squash-early-return), then green with T012/T013:
- FINAL-blob: an approved lane that authored `v1` then `v2` at a path — a canceled blob matching the discarded
  `v1` at that path ⇒ FAIL (not attributed to the superseded intermediate). Second-parent-smuggled blob ⇒ not
  in authored_blobs ⇒ FAIL.
- Unattributable A/M path ⇒ FAIL naming the path; clean squash (all target blobs authored) ⇒ PASS.
- Empty `authored_blobs` while `approved` non-empty ⇒ REFUSE (not empty-loop PASS).
- Probe error for an A/M path ⇒ REFUSE.
- **`excluded_window_base is None` ⇒ REFUSE on the squash path** (post-tasks renata — the last NFR-001 fail-closed
  branch; verify the reorder makes it fire under squash).
- **3-way merge-resolution residual (C-003):** add a dedicated test that ACTUALLY exercises a conflict-resolving
  squash (a path whose final target blob equals neither parent verbatim) and asserts the documented behavior with
  `@pytest.mark.xfail(strict=True, reason="3-way merge-resolution content: final blob ≠ either parent is not
  attributable to a single approved lane; bounded, file-disjoint-lane-mitigated; tracked follow-up")`. It must run
  a real 3-way scenario, not be a bare never-executed marker.
- Both positive and negative arms throughout.

### T015 — unit tests (tests/merge/test_git_probes_seam.py) — **RED-FIRST**
- `blob_id_at`: existing path returns the blob; missing path / bad ref raises `GitProbeError`.
- `changed_paths_in_range`: `--no-renames` behavior (a rename shows as delete+add, not R); A/M/D statuses.
- `first_parent_commits_in_range`: raises on git error (regression for F7).

## Definition of Done
- FR-001 core implemented; the WS1 default-squash repros (WP01) will go green at integration.
- Every new REFUSE/FAIL branch has a direct unit test (NFR-001); FINAL-blob + second-parent exclusion proven.
- `ruff`/`mypy`/`ruff format --check` clean; new helpers ≤ McCabe 15 (push git work into small helpers);
  repeated REFUSE/probe strings hoisted to module constants (Sonar S1192).
- Do NOT edit `executor.py` (WP05 wires the honest message + owns the squash-path call site if any) — but note
  the architect verified `_reconciliation_claim_for_gate`'s `replace(..., verify_reachability=False)` already
  preserves `enforce_closed_world`/`authored_blobs`, so the axis is reachable without an executor change.

## Risks / reviewer guidance
- Reviewer: the F5 FINAL-blob semantics are the crux — verify the superseded-v1 test FAILs. Verify the F1
  A/M-vs-D handling REFUSEs on probe error, never infers deletion. Verify the reorder puts empty-authored +
  None-base REFUSE above the squash early-return. Confirm the merge/rebase path is byte-unchanged.
