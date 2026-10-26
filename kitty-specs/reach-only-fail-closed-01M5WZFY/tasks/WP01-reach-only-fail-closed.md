---
work_package_id: WP01
title: Reach-only membership falls back, then fails closed
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
- C-001
- C-002
- C-003
- SC-001
- SC-002
planning_base_branch: issue-6454-reach-only-fail-closed
merge_target_branch: issue-6454-reach-only-fail-closed
branch_strategy: Planning artifacts for this mission were generated on issue-6454-reach-only-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6454-reach-only-fail-closed unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix
history:
- at: '2026-10-26T20:52:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/reach_only.py
- tests/charter/synthesizer/test_reach_only_delivery.py
- tests/charter/synthesizer/test_styleguide_reach_only.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Reach-only membership falls back, then fails closed

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- With the synthesis manifest present but unreadable and the created-artifacts record readable,
  `reach_only_ids(repo_root, kind)` resolves membership from the record (FR-001).
- With neither readable (record malformed or absent), `reach_only_ids` returns every overlay
  node of the kind that a synthesis-shaped edge (`is_synthesized_source_edge`) targets, minus
  org-required ids (FR-002, FR-006).
- Both degraded paths log one WARNING naming the unreadable file(s) and the membership used (FR-003).
- Tactics and styleguides behave identically (FR-004).
- Absent manifest: unchanged, empty set, no warning (FR-005).
- No extra reads when the overlay has no synthesis-shaped edge of the kind (NFR-001).

## Context & Constraints

- Findings: `kitty-specs/reach-only-fail-closed-research-01M5WZCH/research.md`.
- Spec / plan / data model: `kitty-specs/reach-only-fail-closed-01M5WZFY/{spec,plan,data-model}.md`.
- Charter: `.kittify/charter/charter.md` (ATDD-first C-011, `__all__` convention, complexity ≤ 15).
- C-001: the decision lives only in `reach_only_ids`; do not touch `action_governance_bundle.py`
  or `compiler.py`.
- C-002: `_manifest_slugs` (used by `_first_time_slugs` and `append_synthesized_activations`)
  keeps its lenient "unreadable → empty" contract.
- C-003: warnings via a module `logging.getLogger(__name__)` at WARNING.

## Branch Strategy

- **Strategy**: single_branch (owned checkout)
- **Planning base branch**: issue-6454-reach-only-fail-closed
- **Merge target branch**: issue-6454-reach-only-fail-closed

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement command: `spec-kitty agent action implement WP01 --agent claude --mission reach-only-fail-closed-01M5WZFY`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first tactic tests

- **Purpose**: pin the fail-open through the pre-existing entry points.
- **Steps** (in `tests/charter/synthesizer/test_reach_only_delivery.py`, reuse `_write_overlay`,
  `_delivered_tactics`, `_merged_graph`, `_pack_context`):
  1. Helper that corrupts `MANIFEST_PATH` (e.g. `"artifacts: [\n  {broken\n"`) and one that
     writes the record `CREATED_ARTIFACTS_PATH` with `created_tactics: [...]`.
  2. Unreadable manifest + readable record listing the reach-only tactic: `reach_only_ids` ==
     `{_REACH_ONLY}`; the bundle with the directive off does not deliver it; `_CONTROL` and the
     hand-authored tactic are delivered; with the directive on it is delivered. Assert a WARNING
     (`caplog`, logger `charter.activation.synthesizer.reach_only`) naming the manifest.
  3. Legacy record (`synthesized-tactics.yaml`) alone also serves as the fallback for tactics.
  4. Both unreadable (malformed record) and manifest unreadable + record absent: `reach_only_ids`
     == every synthesis-edge target; the bundle with the directive off does not deliver
     `_REACH_ONLY`; a hand-authored-edge target stays a root; WARNING names both files.
  5. Org-required id stays a root when failing closed.
  6. Absent manifest (delete it): empty set and no WARNING.
- **Files**: the tactic test module.

### Subtask T002 – Red-first styleguide tests

- **Steps** (in `tests/charter/synthesizer/test_styleguide_reach_only.py`, reuse
  `_install_with_sourced` / `_install_overlay`): corrupt the manifest; with a readable record
  (`created_styleguides`) and with neither readable, `_direct_root_urns` excludes the sourced
  styleguide while keeping an edgeless control root.

### Subtask T003 – Commit the failing tests

- Run them, confirm red on the base (ratchet cases green), commit as a separate commit.

### Subtask T004 – Implement the membership resolution

- **Steps** in `src/charter/activation/synthesizer/reach_only.py`:
  1. Add `_LOGGER = logging.getLogger(__name__)` and a private `_UnreadableManifestError`.
  2. Strict reader: absent manifest → empty; load error → `_UnreadableManifestError`.
     `_manifest_slugs` wraps it and keeps returning empty on error (C-002).
  3. Record membership: `None` when no record file that could hold the kind exists, or when
     `_read_record` raises `_UnreadableRecordError`; otherwise `recorded[kind]`.
  4. `reach_only_ids`: compute synthesis-edge targets of the kind first; return empty when none
     (NFR-001); then resolve membership; on fallback warn; on `None` warn and keep every target.
  5. Keep each function ≤ 15 complexity; `__all__` unchanged.

### Subtask T005 – Changelog and gates

- `docs/changelog/CHANGELOG.md` `[Unreleased]` entry in the existing style.
- `uv run --frozen ruff check <files>`, `uv run --frozen ruff format --check --force-exclude <files>`,
  `uv run --frozen mypy <src file>`; targeted tests; `tests/charter/`, `tests/charter_offering/`.

## Test Strategy

- `uv run --frozen pytest tests/charter/synthesizer/test_reach_only_delivery.py tests/charter/synthesizer/test_styleguide_reach_only.py -q`
- mypy on the touched source file (typed sources).

## Risks & Mitigations

- The record lists ids synthesis created in the past (a superset): membership still needs the
  synthesis-shaped edge, so a hand-authored artifact is never affected.
- Repeated warnings across calls: acceptable for a corrupt-file state.

## Review Guidance

- Verify red on the base, green on the final commit.
- Verify no consumer changed (C-001) and the append path is unchanged (C-002).
- Confirm the mypy check ran.

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`
