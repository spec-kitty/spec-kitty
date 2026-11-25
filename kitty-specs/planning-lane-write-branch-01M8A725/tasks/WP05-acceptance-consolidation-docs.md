---
work_package_id: WP05
title: Acceptance suite, consolidation, docs and release note
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-009
- FR-012
- C-005
- SC-001
- SC-005
- SC-006
planning_base_branch: fix/7860-planning-evidence-window
merge_target_branch: fix/7860-planning-evidence-window
branch_strategy: Planning artifacts for this mission were generated on fix/7860-planning-evidence-window. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7860-planning-evidence-window unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
phase: Phase 4 - Acceptance and polish
history:
- at: '2026-11-25T21:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/
create_intent:
- tests/integration/test_7860_consolidate_planning_lane.py
- tests/consolidation/test_planning_write_ref_single_authority_7860.py
- docs/migrations/planning-lane-write-branch.md
- docs/changelog/unreleased/7860.fixed.md
- docs/changelog/unreleased/7860.upgrade-notes.md
execution_mode: code_change
owned_files:
- tests/integration/test_7860_planning_evidence_window.py
- tests/integration/test_7860_consolidate_planning_lane.py
- tests/consolidation/test_planning_write_ref_single_authority_7860.py
- src/specify_cli/consolidation/reconciliation_authorship.py
- src/specify_cli/consolidation/approved_attestation.py
- docs/context/orchestration.md
- docs/context/topology.md
- docs/migrations/planning-lane-write-branch.md
- docs/changelog/unreleased/7860.fixed.md
- docs/changelog/unreleased/7860.upgrade-notes.md
- CLAUDE.md
- AGENTS.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Acceptance suite, consolidation, docs and release note

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

Then: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item and record it with `add-history`.

---

## Objectives & Success Criteria

Prove the whole Mission end to end on real git through the real CLI, pin the single authority, and tell readers.

Done when:
- `tests/integration/test_7860_planning_evidence_window.py` is reworked into the acceptance suite (T021) and is green.
- `tests/integration/test_7860_consolidate_planning_lane.py`: `consolidate` of a default `lanes_with_coord` Mission whose planning work sits only on the Mission branch:
  - exits 0, the reconciliation gate passes, and the file is on the target;
  - holds in both shapes: owned file inside `kitty-specs/<slug>/`, and the pre-#7816 shape with an owned file outside it (SC-006).
  - If red, `reconciliation_authorship.py` / `approved_attestation.py` attribute the planning lane against the Mission branch through `planning_write_ref` (FR-012).
- A test pins that every planning surface follows the one authority (FR-005), and a ratchet pins that the review range of the reproduction contains the owned commit (C-001).
- Docs, the glossary, CLAUDE.md and AGENTS.md (one identical clause each), a migrations note and the changelog fragments are written (FR-009, FR-014).

Requirements: FR-005, FR-009, FR-012, FR-014, C-001, C-005, SC-001..SC-006.

## Context & Constraints

- Plan IC-05. Research R-03 (#4, #6, #13, #16, #17). Quickstart. Contracts C1/C2.
- The red test exists at `tests/integration/test_7860_planning_evidence_window.py` (commit f1ecef5d on `fix/7860-planning-evidence-window`). Its fixture creates a default Mission with 3 code WPs and 1 planning WP that owns `kitty-specs/{slug}/research/notes.md`; it settles `lanes_with_coord`.
  - Its "control" case `test_planning_work_where_implement_puts_it_moves_into_review` contradicts ruling A' and must become the in-flight refusal.
  - Its `_commit_bookkeeping` helper (`git add -A kitty-specs`) can sweep an owned file into a "status residue" commit, which would fake the evidence. Narrow it to tool-written files.
- The pre-#7816 shape cannot be produced by a fresh `finalize-tasks`: a planning WP that owns paths outside `kitty-specs/` is normalised to `code_change` (`ownership/kind_normalisation.py`). Build it by hand-editing `lanes.json` after finalize (move the WP into `lane-planning`, and set its `execution_mode` back), or through the frozen-membership path. Explain the construction in the test docstring.
- CLAUDE.md and AGENTS.md must stay identical in the edited clause. The charter says edit both.

## Branch Strategy

- **Planning base branch**: `fix/7860-planning-evidence-window` · **Merge target branch**: `fix/7860-planning-evidence-window`
- Use the workspace `spec-kitty agent action implement WP05 --agent claude --mission planning-lane-write-branch-01M8A725` prints.

## Subtasks & Detailed Guidance

### Subtask T021 – Rework the #7860 red test into the acceptance suite

- **Cases** (all on the same fixture; SC references in each docstring):
  1. `test_planning_work_on_the_topic_branch_moves_into_review` (SC-001):
     - **parse the workspace from `implement`'s output** (use `--json` if `agent action implement` supports it, else the printed `Workspace:` line);
     - assert it is the coordination worktree and that the output names the Mission branch;
     - commit there, then run an unforced move into review: it passes.
  2. `test_a_hollow_planning_work_package_is_still_refused` (SC-002):
     - assert `IMPLEMENTATION_MISSING`, the window ending `..<mission branch> (lane-planning)`, and the Mission branch in the remedy;
     - assert the "target branch only" addendum is **absent**.
  3. New `test_pre_existing_owned_file_is_not_evidence`: the owned file was committed on the Mission branch during planning, before the claim, and nothing changed after the claim → refused (FR-010).
  4. Replace the control with `test_target_only_planning_work_is_refused` (SC-004):
     - commit the owned file in the root checkout on `main`, then add an unrelated commit on `main` touching another path;
     - assert `IMPLEMENTATION_MISSING`, the owned commit's SHA present, the unrelated SHA absent, and both remedies.
  5. New `test_explicit_topology_keeps_the_repository_root_checkout` (SC-003, FR-006): `--topology lanes_with_coord` → the workspace is the root checkout on the target; work there passes.
  6. Update the module docstring: ruling A' is in force, not "pending".
- Narrow `_commit_bookkeeping` to tool-written files (status events, status.json, meta.json, lanes.json, analysis-report, decisions/).
- Keep `pytest.mark.timeout` explicit (see `test_6715_consolidate_lane_evidence.py`).

### Subtask T022 – Consolidate end-to-end in both shapes

- **File**: `tests/integration/test_7860_consolidate_planning_lane.py`, modelled on `tests/integration/test_6715_consolidate_lane_evidence.py`:
  - drive every WP to approved with an independent reviewer (code WPs with real owned commits in their lane worktrees; the planning WP in the coordination worktree);
  - `accept`, then `consolidate`.
- **Assert**: exit 0, the "Reconciliation verified" banner, every WP `done`, the planning file on the target (`git cat-file -e main:<path>`).
- **Shape A**: the owned file is in `kitty-specs/<slug>/research/`.
- **Shape B (pre-#7816)**: the owned file is `curation/apply_curation.py`, in `lane-planning` (hand-built, see Context).
- If shape B FAILs the reconciliation gate (an unattributable blob):
  - fix the planning-lane branch in `reconciliation_authorship.py:~766` (`_lane_branch_for(lanes_manifest, lane.lane_id)` → the planning write ref before landing) and in `approved_attestation.py:~203`, using `planning_write_ref`;
  - add unit coverage under `tests/consolidation/` (add the file to your history note).
- If it passes without a fix, record that in `add-history` with the reason (bookkeeping definition, or how the squash attribution saw it).

### Subtask T023 – One-authority pin and review-range ratchet

- **File**: `tests/consolidation/test_planning_write_ref_single_authority_7860.py`.
  - **(a)** Monkeypatch `mission_runtime.resolution.planning_write_ref` (and `planning_lane_target`) to return a sentinel branch or checkout. Assert that the workspace resolution (WP02), the claim-base recording (WP03) and the planning evidence window (WP04) all report the sentinel. A surface that ignores the authority fails.
  - **(b)** An AST check that no module other than `resolution.py` calls `default_mission_primary_ref` on these paths except the known placement and review-range readers (allowlist exactly those two, each with an issue reference: #5604 for wp_range). A static allowlist here is a priced debt (Standing Order #5); give it an exit (#5604) in the test docstring.
- Review-range ratchet: on the T021 fixture after the owned commit, run `resolve_wp_review_range(...)` (read only). Assert it is available, not withheld as bookkeeping-only, and that its commit list contains the owned commit.

### Subtask T024 – Docs, glossary, CLAUDE.md/AGENTS.md, migrations note, changelog

- `docs/context/orchestration.md:~178` ("`lane-planning` … resolves to the write checkout, normally the repository root checkout"): add the exception. Before a default Mission lands, it resolves to the checkout that holds the Mission branch (the coordination worktree once settled).
- `docs/context/topology.md:~77` ("always resolves to the write checkout"): restrict "always" to `single_branch`, and describe the default-Mission planning lane. At `:~155` (planning WPs stamped `direct_repo` "because they resolve to the repo-root lane"): state the `execution_mode` WP02 chose for the new kind.
- CLAUDE.md and AGENTS.md: one identical sentence each, in "Create-time topology" (or near "Owned-file evidence"): "Before a default Mission lands, its planning lane writes to the Mission branch: `implement` names the coordination worktree, and the planning evidence window runs from the WP's claim commit to the Mission branch (#7860, ADR 2026-11-06-3 and ADR 2026-10-04-5, Amendments 2026-11-25, Proposed)."
- `docs/migrations/planning-lane-write-branch.md`:
  - who is affected: default Missions in flight whose planning work was committed on the target;
  - the symptom: `IMPLEMENTATION_MISSING` with the target-only addendum;
  - the remedies: cherry-pick onto the Mission branch in the coordination worktree, or `--attest-no-implementation`;
  - no migration runs. Follow the style of the neighbouring migration notes.
- Changelog fragments (`docs/changelog/unreleased/README.md`):
  - `7860.fixed.md`: one entry, "Before/After" style;
  - `7860.upgrade-notes.md`: the in-flight guidance.
  - Run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
- If a docs index or inventory check covers `docs/context/` or `docs/migrations/`, run it (`ls scripts/docs`).

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/integration/test_7860_planning_evidence_window.py tests/integration/test_7860_consolidate_planning_lane.py -q -p no:cacheprovider
PWHEADLESS=1 .venv/bin/python -m pytest tests/consolidation tests/review tests/lanes tests/status -q -p no:cacheprovider
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
make test-fast
```

Plus ruff, format and mypy on changed Python; the docs checks above.

## Risks & Mitigations

- Integration tests are slow (about 2 minutes each). Use `-n` with `--dist loadfile` only via the make targets; locally run them serially.
- The hand-built pre-#7816 shape could drift from reality: assert the `lanes.json` shape you built before driving the CLI.
- The CLAUDE.md and AGENTS.md copies must be identical: diff the clause.

## Standing rules

Signed commits; no model names; zero ruff/format/mypy findings, no suppressions, complexity ≤ 15; no `test-full`; attribute every red.

## Review Guidance

- Case 1 reads `implement`'s workspace; it does not find the worktree by itself.
- The in-flight test has the unrelated-commit negative control.
- The consolidate E2E covers both shapes. Any reconciliation fix is minimal and tested.
- The pin test fails if any surface bypasses the authority (try it by reverting one call locally).
- The docs are consistent with the ADR amendments, and the fragments pass the style and spelling checks.

## Progress & Status

- `spec-kitty agent tasks add-history WP05 --note "..."` · `mark-status T021 … --status done` · `move-task WP05 --to for_review`
