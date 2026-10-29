---
work_package_id: WP01
title: Shared evidence predicate and the consolidate axis
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
planning_base_branch: issue-6715-lane-evidence-independence
merge_target_branch: issue-6715-lane-evidence-independence
branch_strategy: Planning artifacts for this mission were generated on issue-6715-lane-evidence-independence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6715-lane-evidence-independence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-evidence-independence-01M5YHXF
base_commit: 9aaa40ec0180846aac5bd368e36977e86335f35f
created_at: '2026-10-27T12:11:44.518360+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-10-27T12:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/consolidation/wp_evidence.py
create_intent:
- src/specify_cli/consolidation/wp_evidence.py
- tests/consolidation/test_wp_evidence.py
- tests/consolidation/test_lane_evidence_axis.py
- tests/integration/test_6715_consolidate_lane_evidence.py
- tests/orchestrator_api/test_consolidate_mission_lane_evidence_6715.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/wp_evidence.py
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/orchestrator_api/consolidation.py
- tests/consolidation/test_wp_evidence.py
- tests/consolidation/test_lane_evidence_axis.py
- tests/integration/test_6715_consolidate_lane_evidence.py
- tests/orchestrator_api/test_consolidate_mission_lane_evidence_6715.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared evidence predicate and the consolidate axis

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- ONE topology-neutral predicate module, `src/specify_cli/consolidation/wp_evidence.py`, owns:
  the four neutral codes, the `SINGLE_BRANCH_*` alias table, owned-file matching, the evidence
  window per WP, the bookkeeping exclusions, the per-WP verdict, and the read side of the
  no-implementation attestation.
- `consolidate` refuses at claim time (before any mutation, so nothing is rolled back) any
  approved WP on a lanes/coord code lane or planning lane that has no owned-file change in its
  window, or whose review is not independent. The "Reconciliation verified" banner is never
  printed in that case.
- single_branch keeps its existing behaviour and `SINGLE_BRANCH_*` codes, now through the same
  module (no copy left behind in `reconciliation.py`).
- `orchestrator-api consolidate-mission` (every topology, before the first lane merge) and
  `accept-mission` refuse with codes in `data`.
- Positive controls (real owned commit + independent review) consolidate clean on lanes, coord
  and single_branch.

## Context & Constraints

- Read first: `kitty-specs/lane-evidence-independence-01M5YHXF/{spec.md,plan.md,research.md,data-model.md,contracts/refusal-codes.md}`, `.kittify/charter/charter.md`.
- Template to generalise: `reconciliation._single_branch_evidence_refusal` (~L2178),
  `_sb_owned_patterns`, `_sb_matches_owned`, `_sb_owned_files_by_wp`, `_sb_approved_wp_ids`,
  `single_branch_evidence_refusal`, `single_branch_refusal_codes`.
- Independence: reuse `preflight._independent_reviewer_confirmed` unchanged (ruling; C-002).
- `approved_bound.py` is NOT changed (C-001).
- Bookkeeping exclusions mirror `lanes/for_review_gate._STATUS_ONLY_PREFIX_TEMPLATES` +
  `.kittify/`: `kitty-specs/<slug>/status.`, `kitty-specs/<slug>/issue-matrix.`,
  `kitty-specs/<slug>/meta.json`, `.kittify/`. Import them (or move them into `wp_evidence` and
  import from `for_review_gate`) so there is one list, not two.
- Layering: `specify_cli.consolidation` may import `specify_cli.lanes` and `specify_cli.status`;
  it must not import `specify_cli.cli`.
- Attestation read side: `ATTESTATION_KEY` (`canceled_attestation.ATTESTATION_KEY`) with value
  `NO_IMPLEMENTATION = "no_implementation"`; `attested_no_implementation(events, wp_id) -> bool`
  is True iff some event for the WP has `policy_metadata[ATTESTATION_KEY] == NO_IMPLEMENTATION`
  and a non-migration actor. WP02 writes it.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: issue-6715-lane-evidence-independence
- **Merge target branch**: issue-6715-lane-evidence-independence

Execution worktrees are allocated per computed lane from `lanes.json`; run
`spec-kitty agent action implement WP01 --agent claude --mission lane-evidence-independence-01M5YHXF`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first fixtures

- **Purpose**: pin the P0 at the consolidate and orchestrator-api surfaces before the fix.
- **Steps**:
  1. `tests/integration/test_6715_consolidate_lane_evidence.py`, modelled on
     `tests/integration/test_5939_single_branch_autowalk_guards.py` (real CLI via
     `python -m specify_cli`, isolated HOME). Mission with WP01 (`src/m1/**`) and WP02
     (`tools/check.sh`, `create_intent`), parametrised over `coord` and `lanes`.
  2. Hollow case: WP01 implemented by `alice` (commit in the lane worktree), reviewed by `bob`
     (`agent action review` + unforced approve). WP02 claimed by `claude` via
     `agent action implement`, no owned commit, then `move-task --to approved --agent bob --force`
     (forced so WP03's future move gate cannot mask this test). acceptance-verdict, `accept --lenient`,
     then `consolidate`. Assert rc != 0, `IMPLEMENTATION_MISSING` in output, "Reconciliation
     verified" absent, WP02 not `done`, `tools/check.sh` absent on the target.
  3. Self-approval case: WP02 committed by `claude` and approved `--force` by `claude` ⇒
     `REVIEW_NOT_INDEPENDENT`.
  4. Positive control: WP02 implemented (commit `tools/check.sh` in its lane) and reviewed by
     `bob` ⇒ consolidate rc 0, both `done`, file on target.
  5. A planning-lane case (a WP with `execution_mode: planning_artifact` owning a
     `kitty-specs/<slug>/research/...` file, approved with no change) ⇒ `IMPLEMENTATION_MISSING`.
  6. `tests/orchestrator_api/test_consolidate_mission_lane_evidence_6715.py`: same hollow state
     ⇒ `consolidate-mission` envelope `PREFLIGHT_FAILED`, `data.preflight_error_codes` contains
     `IMPLEMENTATION_MISSING`, no lane merged. Reuse helpers from
     `tests/orchestrator_api/test_consolidate_mission_post_approval.py` if they fit.
  7. Commit the tests alone first (`test(WP01): red-first ...`); record the red run in the
     history note.
- **Notes**: fixtures that need a real CLI must use the checkout's `src/` (they do via
  `sys.executable -m specify_cli` under `uv run`).

### Subtask T002 – `consolidation/wp_evidence.py`

- **Purpose**: the single authority (C-003).
- **Shape** (adapt names to the surrounding style; keep `__all__`):
  ```python
  IMPLEMENTATION_MISSING = "IMPLEMENTATION_MISSING"
  REVIEW_NOT_INDEPENDENT = "REVIEW_NOT_INDEPENDENT"
  IMPLEMENTATION_UNREADABLE = "IMPLEMENTATION_UNREADABLE"
  EVIDENCE_WINDOW_UNCOMPUTABLE = "EVIDENCE_WINDOW_UNCOMPUTABLE"
  SINGLE_BRANCH_ALIASES = {"SINGLE_BRANCH_IMPLEMENTATION_MISSING": IMPLEMENTATION_MISSING, ...}
  def canonical_code(code: str) -> str
  def refusal_codes(text: str) -> list[str]          # neutral + alias codes leading a line
  def owned_patterns(owned_files) / matches_owned(path, patterns)
  def is_evidence_path(path, mission_slug) -> bool   # not bookkeeping
  def evidence_window(repo_root, manifest, lane) -> tuple[str, str] | None
  def wp_has_owned_change(repo_root, window, patterns, mission_slug) -> bool  # raises GitProbeError
  def attested_no_implementation(events, wp_id) -> bool
  def evidence_refusal_lines(...) -> list[str]       # per-WP verdict lines, ordered as data-model.md
  ```
- Windows: code lane ⇒ `(planning_commit_sha, _lane_branch_for(manifest, lane_id))`; planning
  lane ⇒ `(planning_commit_sha, manifest.target_branch)`; single_branch ⇒ the existing
  `single_branch_evidence_window`. `None` when `planning_commit_sha` is missing.
- Diff with `consolidation.git_probes.changed_paths_in_range` (tree diff, `--no-renames`); any
  `GitProbeError` ⇒ `IMPLEMENTATION_UNREADABLE` (NFR-002).
- Per lane at most one diff (NFR-001): compute the changed path set once per window and match
  every WP of that lane against it.
- Keep each function ≤ 15 complexity.

### Subtask T003 – Claim-builder axis

- Replace the single_branch-only call in `build_approved_wp_set` (~L1593–1606) with one call to
  the generalised axis: single_branch keeps its window and alias codes and its refusal header;
  lanes/coord iterate every non-fully-canceled lane (code and planning) and emit neutral codes.
- Refusal text: header `Mission <slug>: work packages cannot be landed as reviewed:` then one
  line per WP (code-led) then a recovery line naming `--attest-no-implementation <WP>
  --attest-reason "<why>"` for `IMPLEMENTATION_MISSING` and "a reviewer who is not the
  implementer" for `REVIEW_NOT_INDEPENDENT`. Keep the single_branch header/recovery text as it is
  today (existing tests assert it).
- Position: after the approved-bound check (its refusals keep precedence) and before the
  collectors, exactly where the single_branch axis is now.
- `single_branch_evidence_refusal` / `single_branch_refusal_codes` stay as thin public wrappers
  (or are replaced by a general `wp_evidence_refusal` used by orchestrator-api); remove the
  `_sb_*` copies once callers moved.

### Subtask T004 – orchestrator-api

- `consolidate-mission`: run the general refusal for EVERY topology at the point where
  `_refuse_single_branch_hollow_content` runs today (before the planning-only short-circuit),
  raising `ApprovedBoundRefused(text, error_code=codes[0], error_codes=codes)` so the envelope is
  `PREFLIGHT_FAILED` with `data.preflight_error_code(s)`. Note in the text that attestation is
  done with `spec-kitty consolidate`/`accept` (this command has no flag), like
  `_orchestrator_refusal_text`.
- `accept-mission`: after the incomplete-WP check, `_fail(cmd, "MISSION_NOT_READY", text,
  {..., "evidence_error_codes": codes})`.

### Subtask T005 – Unit tests and re-pins

- `tests/consolidation/test_wp_evidence.py`: alias mapping, `refusal_codes`, bookkeeping
  exclusion, revert-is-nothing (commit then revert ⇒ missing), unreadable range ⇒ unreadable,
  missing base ⇒ uncomputable, attestation reader ignores migration actors.
- `tests/consolidation/test_lane_evidence_axis.py`: `build_approved_wp_set` refuses/admits on a
  small git fixture (reuse helpers in `tests/consolidation/` such as `approval_stamps.py`).
- Run `tests/consolidation/`, `tests/orchestrator_api/`, `tests/integration/test_5939_*`,
  `tests/specify_cli/consolidation/`. Any test that now refuses because it self-approves or
  approves a hollow WP: judge it (DIRECTIVE_041). If its intent is something else, re-pin it with
  a distinct reviewer or a real owned commit (out-of-map edit allowed with a one-line rationale
  in the commit message). Never weaken the gate to make a test pass.

## Test Strategy

- `uv run --frozen pytest tests/consolidation tests/orchestrator_api tests/specify_cli/consolidation tests/integration/test_5939_single_branch_autowalk_guards.py tests/integration/test_6715_consolidate_lane_evidence.py -q`
- `uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched> && uv run --frozen mypy <touched src>`
- Architectural gates implicated: `tests/architectural/test_layer_rules.py`,
  `tests/architectural/test_single_rollback_authority.py` if it lists claim callers (check),
  `tests/architectural/test_no_dead_symbols.py` only if it covers `specify_cli` (check).

## Risks & Mitigations

- Many existing coord/lanes consolidate fixtures may use one agent name for claim and approve.
  Budget time for re-pins; list each in the history note.
- `planning_commit_sha` absent on hand-built test manifests ⇒ `EVIDENCE_WINDOW_UNCOMPUTABLE`.
  Unit fixtures must set it.

## Review Guidance

- Red-first commit precedes the fix; it fails on the parent commit.
- Exactly one owned-file matcher and one bookkeeping list remain in `src/`.
- `approved_bound.py` unchanged; claim-time refusal happens before the first mutation.
- ruff, ruff format, mypy clean; no new `noqa` / `type: ignore`.

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`
