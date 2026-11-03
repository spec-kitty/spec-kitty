---
work_package_id: WP01
title: Unresolved-ownership verdict and attestation refusal
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-004
- SC-001
- SC-002
- SC-004
planning_base_branch: fix/7149-ownership-unresolved
merge_target_branch: fix/7149-ownership-unresolved
branch_strategy: Planning artifacts for this mission were generated on fix/7149-ownership-unresolved. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7149-ownership-unresolved unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-files-unresolved-fail-closed-01M6HAHF
base_commit: 4283c87e140c2ed753caafdf2db0999e066e7a27
created_at: '2026-11-03T18:57:59.493199+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Fail-closed verdict (P0)
history:
- at: '2026-11-03T18:31:15Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_evidence_ownership_unresolved.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/consolidation/wp_evidence.py
- src/specify_cli/consolidation/no_implementation_attestation.py
- src/specify_cli/orchestrator_api/envelope.py
- tests/consolidation/test_evidence_code_literals.py
- tests/consolidation/test_no_implementation_attestation.py
- tests/consolidation/test_evidence_ownership_unresolved.py
- tests/integration/test_owned_acceptance_authority_6023.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Unresolved-ownership verdict and attestation refusal

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
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

Issue #7149's still-open half: today an approved work package whose ownership declaration (`owned_files` in its task file) **cannot be read** is judged `IMPLEMENTATION_MISSING`, and `--attest-no-implementation` can lift it. That points operators at the wrong recovery: committing more work, or attesting falsely. After this WP:

- An approved work package that is **absent from the resolved ownership map** (the `tasks/` directory is missing, or the work package's task file is absent from it or unreadable) is refused with `OWNERSHIP_UNRESOLVED`. A single_branch Mission reports `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED`. The line names the location read (FR-001, FR-002).
- That check runs **before** the owned-change test, so `IMPLEMENTATION_MISSING` again means only "ownership resolved, no owned change" (FR-003).
- `--attest-no-implementation` refuses an unresolved work package and records nothing (FR-004).
- An **authored** `owned_files` list, **including an empty one**, is a resolved declaration and keeps exactly today's verdicts (FR-008). `finalize-tasks` legitimately allows `owned_files: []` for non-`code_change` work packages (`mission_finalize_bootstrap.py:219-228`).
- No new git subprocess (NFR-001); `ruff` and `mypy` clean, no new suppressions (NFR-003).

Done when every subtask below holds and the tests in the Test Strategy pass red-first.

## Context & Constraints

- Spec: `kitty-specs/owned-files-unresolved-fail-closed-01M6HAHF/spec.md` (FR-001..FR-005, FR-008). Plan: IC-01 and IC-02. Data model: verdict precedence. Contract: `contracts/evidence-codes.md` (line shape and recovery wording).
- **C-001 one predicate**: the verdict is decided only in `src/specify_cli/consolidation/wp_evidence.py`. Do not touch `accept.py`, `consolidate` or `orchestrator-api` call sites; they consume `mission_evidence_report` / `evaluate_evidence` and pick the verdict up automatically.
- **C-002**: the owned-checkout read is already correct on this branch (#7099, `088c2f1661`): `_wp_task_dir(..., owned=owned)` → `placement_seam(repo_root, slug, owned=owned).read_dir(WORK_PACKAGE_TASK)`. Reuse it; do not re-implement it.
- **C-004**: do not change evidence-window computation.
- Open PR #7146 also edits `wp_evidence.py`. Keep your diff inside `_Scan`, `_owned_patterns_by_wp`, `_judge`, the code constants, `_SINGLE_BRANCH_ALIASES`, `_ALL_CODES`/`_NEUTRAL_CODES` and `_RECOVERY`.
- Charter: ATDD and red-first (Standing Order 4, DIRECTIVE_041). Run `spec-kitty charter context --action implement --json` before you start.

### ⚠️ Test economy (read before writing any test)

Every test you add is vetted at closeout under DIRECTIVE_041 and the KEEP / RETIRE / SPLIT-BY-KIND rubric (`packs/built-in/procedures/development-assist-test-cleanup.procedure.yaml`). Add a test only when it guards real behaviour through the existing entry point (`mission_evidence_report` / `evaluate_evidence`, or the `spec-kitty accept` CLI through the owned-checkout integration fixture), with realistic data, and fails on a real regression. Do not duplicate an existing assertion, add a second planted control where one already proves non-vacuity, or pin code shape. Prefer strengthening an existing test over adding a function; at most one focused test per behaviour unless a second covers a genuinely different failure mode. A red-first demonstration not worth keeping goes in your report (command + failing output), not in the commit. **In your hand-off, include a table of every test you added or changed: test, regression it catches, existing coverage it relates to.**

## Branch Strategy

- **Planning/base branch**: `fix/7149-ownership-unresolved`
- **Final consolidation target**: `fix/7149-ownership-unresolved` (the PR branch; it reaches `main` through a pull request, never directly)
- Execution worktrees are allocated per computed lane from `lanes.json`. Run the command below; never pick a base branch by hand:

```bash
spec-kitty agent action implement WP01 --agent claude --mission owned-files-unresolved-fail-closed-01M6HAHF
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first tests for the unresolved verdict

**Purpose**: prove the defect on the current code before changing it.

**Steps**:
1. Read the existing fixtures that build a Mission and call `mission_evidence_report` / `evaluate_evidence`: `tests/consolidation/test_wp_evidence.py`, `test_lane_evidence_axis.py`, `test_single_branch_evidence_axis.py`. Reuse their fixture helpers; do not copy them.
2. In the new module `tests/consolidation/test_evidence_ownership_unresolved.py` (declare `pytestmark` consistent with its directory, check `tests/consolidation/` siblings), write focused tests through `mission_evidence_report`:
   - **lanes topology, task file absent**: an approved work package whose `tasks/WPxx-*.md` is removed; the window holds an owned-looking change. Assert the refusal contains `OWNERSHIP_UNRESOLVED: WPxx`, names the `tasks/` path, and contains no `IMPLEMENTATION_MISSING` line for that work package. **Positive control on the same fixture**: with the task file present the evidence passes (or yields no refusal for it).
   - **`tasks/` directory missing**: every approved work package reports `OWNERSHIP_UNRESOLVED` naming the missing directory. Cover it in the same parametrized test as the absent-file case if the assertions are identical.
   - **unreadable task file** (e.g. invalid YAML frontmatter): `OWNERSHIP_UNRESOLVED` naming the file or directory.
   - **single_branch**: the same absent-file case reports `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED`. One case is enough.
3. **CLI production path (owned checkout)**: in `tests/integration/test_owned_acceptance_authority_6023.py`, add one scenario row to the existing `_Scenario` table, e.g. `missing_owned_task_file`, that deletes the owned checkout's `tasks/WP01-test.md` (mirror `_drop_owned_ownership`; **commit the deletion**, since it happens after `finalize-tasks`) and expects `OWNERSHIP_UNRESOLVED`. Set `stale_primary=True` on that row, so the test also proves there is no fallback to the repository root's copy. If the existing summary assertions (`lanes.approved`, the `blocked_checks` evidence entry) break because summary collection reads the task file, assert only `error_code` / `error_codes` for that row and say so in your report. **Leave `missing_owned_ownership` (authored `owned_files: []`) expecting `IMPLEMENTATION_MISSING`**: it is the FR-008 ratchet. Do not change its expectation.
4. Run them on the unchanged code and record the failing output in your report (they must be red for the right reason).

**Files**: `tests/consolidation/test_evidence_ownership_unresolved.py` (new), `tests/integration/test_owned_acceptance_authority_6023.py`.

### Subtask T002 – Register the new codes

**Steps**:
1. In `wp_evidence.py` add `OWNERSHIP_UNRESOLVED = "OWNERSHIP_UNRESOLVED"` beside the other neutral codes and append it to `_NEUTRAL_CODES` (order matters for recovery-line order; put it after `EVIDENCE_WINDOW_UNCOMPUTABLE` or where the data-model precedence reads naturally, and keep `_lanes_refusal_text`'s recovery ordering sensible).
2. Add `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED = "SINGLE_BRANCH_OWNERSHIP_UNRESOLVED"` and map it in `_SINGLE_BRANCH_ALIASES` to `OWNERSHIP_UNRESOLVED`. `_ALL_CODES` derives from both.
3. Update `tests/consolidation/test_evidence_code_literals.py`: its `_NEUTRAL_CODES` tuple assertion and alias map must include the new pair. This is the one place the literals are pinned; strengthen it, do not add a new test.

### Subtask T003 – Carry the read location; check unresolved first

**Steps**:
1. `_owned_patterns_by_wp` already records a work package only when its task file was read (a parse failure `continue`s; a missing `tasks/` yields nothing). Keep that contract: **key absent = unresolved, key present (even an empty tuple) = authored**. Do not change how present keys are built.
2. The refusal must name where it read. Add the resolved `tasks/` location to the scan, e.g. a `tasks_dir: Path` field on `_Scan` (dataclass; give it a sensible place in the field order) set where `_Scan(...)` is built in `evaluate_evidence` (around `:757`) from the same `_wp_task_dir(...)` call `_owned_patterns_by_wp` uses. Resolve it **once** (NFR-001: no extra I/O beyond the existing read; computing the path again is fine if it does not touch git).
3. In `_judge` (used by both `_scan_lane` and the single_branch scan), before the `has_owned_change` test: if `wp_id not in scan.owned`, add the unresolved line and return. Respect the topology: the lanes path emits `OWNERSHIP_UNRESOLVED`, the single_branch path `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED`. `_judge` already receives `missing_line` and `not_independent_code` per topology; pass the unresolved code the same way (a parameter), rather than branching on topology inside `_judge`.
4. Line shape (contract): `OWNERSHIP_UNRESOLVED: WPxx owned_files could not be read from <tasks dir>: its task file is missing or unreadable, or the directory does not exist, so implementation evidence cannot be judged.` Keep wording plain; make sure the `code: detail` split (`line.partition(": ")`) still yields the code for `scan.mark`.
5. **Omitted key**: `WPMetadata.owned_files` defaults to `[]` (`wp_metadata.py:246`), so a task file that omits the key reads as an authored empty list (present key). Treat that as **resolved**, matching today's verdict and the FR-008 ratchet; do not use `model_fields_set`. Say so in a comment.
6. **Docstrings that become wrong**: update the module docstring's numbered verdict list (add the unresolved verdict **after** the `REVIEW_NOT_INDEPENDENT` item, to keep the conflict with PR #7146 small; it edits the lines around the `IMPLEMENTATION_UNREADABLE` item), `_owned_patterns_by_wp`'s docstring (it says an absent *or empty* set is "cannot be proven"; now absent = unresolved, present-empty = resolved), and `_judge`'s docstring ("Verdicts 3 and 4").
7. Check the other `scan.owned` readers (`:544` overlap check, `:689` widened paths) still behave for an absent key (they use `.get(wp_id, ())`), and that an unresolved work package is not additionally reported as missing.

### Subtask T004 – Recovery line

Add `_RECOVERY[OWNERSHIP_UNRESOLVED]` **after** the `REVIEW_NOT_INDEPENDENT` entry (smaller conflict with PR #7146): restore or commit the work package's task file with its `owned_files`, or re-run from the checkout that owns the Mission (`--owned-checkout <path>`), and end with "No attestation lifts this." (the `REVIEW_NOT_INDEPENDENT` wording). **Do not put the literal `--attest-no-implementation` in this recovery text**: `orchestrator_api/consolidation.py::_no_implementation_attestation_note` (~:553-561) appends an "attestation is done with `spec-kitty accept`/`consolidate`" hint whenever a refusal contains that literal, which would point the operator at the wrong recovery. The single_branch refusal text (`_single_branch_refusal_text`) has one fixed recovery line. Check whether an unresolved single_branch refusal needs its own line, and add it only if the existing one would mislead ("implement the work package" is misleading here).

### Subtask T005 – Attestation refuses the unresolved verdict

**Steps**:
1. Red first, in `tests/consolidation/test_no_implementation_attestation.py`: **no existing test exercises `_refuse_unliftable`** (the accept tests mock the planner). Add **one parametrized test** through `plan_no_implementation_attestations`: row 1 is the unresolved work package (build it with `build_post_approval_lanes_mission` and the task file removed), expecting an `AttestationError` naming it, with the status event log byte-identical afterwards; row 2 is the control, a resolved `IMPLEMENTATION_MISSING` work package, which is still accepted.
2. In `no_implementation_attestation.py`, add **only the neutral** `OWNERSHIP_UNRESOLVED` to `_UNLIFTABLE_VERDICTS`: `report.verdicts` is canonicalised through `scan.mark` → `_canonical_code`, so the single_branch alias never appears there. Then check `_refuse_unliftable`'s message: it says the evidence "cannot be read". Make sure it reads correctly for an unresolved declaration (it names the verdict per work package, so it probably does), and adjust minimally if not.

### Subtask T006 – Orchestrator-api envelope registry comment

`src/specify_cli/orchestrator_api/envelope.py` (~:170) lists the evidence codes in a comment beside the `PREFLIGHT_FAILED` contract. Add `OWNERSHIP_UNRESOLVED` (and its single_branch alias), and **bump `CONTRACT_VERSION` 1.22.0 → 1.23.0** with a one-paragraph changelog comment in the same style as the 1.21.0 / 1.22.0 entries (decision `plan.contract.version-bump`, following the 1.21.0 precedent). Tests that pin the literal version (`grep -rn '1.22.0' tests/orchestrator_api`) are updated as a recorded out-of-map edit. The docs (`docs/api/orchestrator-api.md` version line and changelog, the operator skill contract reference) and the ADR amendment are done at closeout, not in this WP.

## Test Strategy

- New module: `tests/consolidation/test_evidence_ownership_unresolved.py` (T001). Strengthened: `test_evidence_code_literals.py` (T002), `test_no_implementation_attestation.py` (T005), `test_owned_acceptance_authority_6023.py` (+1 scenario row, T001).
- Run: `uv run --frozen pytest -q -p no:randomly tests/consolidation tests/integration/test_owned_acceptance_authority_6023.py tests/integration/test_p0_repro_6023_owned_acceptance_verdict.py tests/specify_cli/cli/commands/test_accept_evidence_preflight.py tests/orchestrator_api -k "evidence or attest or accept or consolidat"`, then the full `tests/consolidation` directory. Plus `ruff check`, `ruff format --check --force-exclude` and `mypy` on the changed source files.
- Non-vacuity: revert T003 alone and confirm the T001 tests go red; revert T005 alone and confirm its test goes red. Report both.

## Risks & Mitigations

- **Over-firing** on authored empty lists: the `missing_owned_ownership` ratchet guards it.
- **Recovery-line ordering**: `_lanes_refusal_text` emits recovery lines in `_NEUTRAL_CODES` order; check the combined refusal reads sensibly when unresolved and missing appear together for different work packages.
- **Collision with PR #7146**: minimal, localised edits.

## Review Guidance

- Verify unresolved is decided by key absence only, and an authored empty list still yields `IMPLEMENTATION_MISSING`.
- Verify no call site outside `wp_evidence` / `no_implementation_attestation` / the envelope comment changed.
- Verify the red-first evidence in the hand-off, and the half-by-half reverts.
- Check the test table against the test-economy rules above.

## Progress & Status

Record progress with `spec-kitty agent tasks mark-status T00x --status done --mission owned-files-unresolved-fail-closed-01M6HAHF` and notes with `spec-kitty agent tasks add-history WP01 --note "..."`.
