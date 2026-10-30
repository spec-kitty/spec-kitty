---
work_package_id: WP01
title: Rewrite the doctor identity migration page from live output, red-first
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6760-doctor-identity-docs-sync
merge_target_branch: issue-6760-doctor-identity-docs-sync
branch_strategy: Planning artifacts for this mission were generated on issue-6760-doctor-identity-docs-sync. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6760-doctor-identity-docs-sync unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-identity-docs-sync-01M66956
base_commit: 577e13d81d7bf0ab4b79e2303aa54ea38c349674
created_at: '2026-10-30T11:36:38.475100+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Documentation sync
history:
- at: '2026-10-30T11:35:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: docs/migrations/
create_intent:
- tests/docs/test_mission_id_migration_page.py
execution_mode: code_change
model: ''
owned_files:
- tests/docs/test_mission_id_migration_page.py
- docs/migrations/mission-id-canonical-identity.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Rewrite the doctor identity migration page from live output, red-first

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`docs/migrations/mission-id-canonical-identity.md` (issue spec-kitty/spec-kitty#6760)
still documents a `doctor identity` contract the CLI no longer prints: states
`ok`/`legacy`/`conflict`, a JSON sample with `status`/`total`/`ok`/`conflicts`
and `dir`/`mission_slug` rows, `conflicts > 0` guidance, and a backfill
transcript the live command does not print. Success is:

- The page's state list names exactly the five live states with the live
  definitions (FR-001).
- The Step 2 and Step 4 JSON samples match the live
  `spec-kitty doctor identity --json` contract key-for-key (FR-002).
- No stale contract references remain in the surrounding prose; the Step 3
  transcript matches live `migrate backfill-identity` output (FR-003).
- A structural test pins the page to the imported live contract and fails on
  the pre-fix page (FR-004, red-first proof recorded).
- The four docs gates named in the procedure pass (NFR-001).

## Context & Constraints

- Spec: `kitty-specs/doctor-identity-docs-sync-01M66956/spec.md`; plan:
  `kitty-specs/doctor-identity-docs-sync-01M66956/plan.md`; grounding evidence
  (live contract, fixture output, scope decisions):
  `kitty-specs/doctor-identity-docs-sync-01M66956/research.md`.
- The live contract's owning sources: `src/specify_cli/status/identity_audit.py`
  (`IDENTITY_STATES`, `IdentityState.to_dict`) and
  `src/specify_cli/cli/commands/_identity_audit.py` (`_build_identity_json`).
  Read them; never edit them (C-001: no `src/` changes).
- The page's state list must mirror the `spec-kitty doctor identity --help`
  wording, which is the same contract `docs/api/cli-commands.md` carries
  (NFR-002).
- Every documented state, key and sample value must be reproduced from a live
  run on this checkout (C-002) — use the fixture shape recorded in research.md;
  re-run the CLI rather than copying from memory.
- Keep the page's migration-runbook structure (frontmatter, section order,
  cross-references); the `residue` bullets from #5875 are correct and stay.

## Branch Strategy

- **Strategy**: single work package on the mission lane; planning artifacts
  already on `issue-6760-doctor-identity-docs-sync`
- **Planning base branch**: `issue-6760-doctor-identity-docs-sync`
- **Merge target branch**: `main` (via the mission PR; never push `main`)

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first structural test

- **Purpose**: Pin the page to the live JSON contract so the #6760 drift class
  fails CI instead of recurring (FR-004).
- **Steps**: Create `tests/docs/test_mission_id_migration_page.py` (precedent:
  `tests/docs/test_artifact_placement_seam_page.py` — structure and citations,
  never prose):
  1. Parse the page; extract the fenced JSON samples of the audit steps.
  2. Assert the page's documented state list equals the imported
     `specify_cli.status.IDENTITY_STATES` (import it — never restate it).
  3. Assert each extracted sample's top-level keys match a report built by the
     imported contract: `summary` counts keyed by the five imported states;
     `missions[]` row keys equal `IdentityState(...).to_dict()` keys; the
     `duplicate_prefixes`/`ambiguous_selectors`/`fail_on_triggered` trio
     present; `residue_remedies` treated as conditional (present only in a
     sample that also contains a `residue` row).
  4. Run `uv run pytest tests/docs/test_mission_id_migration_page.py` and
     record the red failure (it must fail against the current page).
- **Files**: `tests/docs/test_mission_id_migration_page.py` (new).
- **Parallel?**: No — everything else depends on it.
- **Notes**: Mark it `pytest.mark.unit` (or the local equivalent used by
  `tests/docs/`) so it runs in the fast lane. Assert structure, not prose.

### Subtask T002 – Rewrite the Step 2 state list

- **Purpose**: FR-001.
- **Steps**: In the Step 2 bullet list, replace `ok`/`legacy`/`conflict` with
  the five live states and their live definitions, mirroring the help text:
  `assigned` (mission_id present AND mission_number non-null),
  `pending` (mission_id present AND mission_number null),
  `legacy` (mission_id missing AND mission_number present),
  `orphan` (both missing or meta.json unreadable),
  `residue` (not a Mission; keep the #5875 residue bullets and remedies).
  Note that duplicate numeric prefixes and ambiguous selectors are reported
  separately (`duplicate_prefixes`, `ambiguous_selectors`) — they are not a
  state.
- **Files**: `docs/migrations/mission-id-canonical-identity.md`.
- **Parallel?**: No.

### Subtask T003 – Rewrite the Step 2 and Step 4 JSON samples

- **Purpose**: FR-002.
- **Steps**: Replace both samples with ones matching the live contract
  (re-run the CLI on a fixture to confirm values):
  - Step 2: a project with one legacy mission — `summary` with all five
    counts, `missions[]` rows with `path`, `slug`, `mission_id`,
    `mission_number`, `state`, `error`, `residue_reason`, empty
    `duplicate_prefixes` and `ambiguous_selectors`, `fail_on_triggered:
    false`; when the sample shows a residue row, include `residue_remedies`
    and say it appears only then.
  - Step 4: the same project after backfill — `legacy` back to 0, the
    backfilled row now `assigned` with its minted `mission_id` and
    merge-assigned `mission_number`, and no `residue_remedies` key.
- **Files**: `docs/migrations/mission-id-canonical-identity.md`.
- **Parallel?**: No.

### Subtask T004 – Correct the conflicts prose and the backfill transcript

- **Purpose**: FR-003.
- **Steps**: Remove the `conflicts > 0` paragraph and the "backfill refuses to
  run while conflicts are present" claim (no such gate exists in
  `specify_cli/migration/backfill_identity.py`); where disambiguation guidance
  is still useful, point at `duplicate_prefixes`/`ambiguous_selectors` and the
  `MISSION_AMBIGUOUS_SELECTOR` error already documented in Step 6. Replace the
  Step 3 expected-output transcript with the live
  `spec-kitty migrate backfill-identity` summary table (run it with
  `--dry-run` to confirm the exact lines).
- **Files**: `docs/migrations/mission-id-canonical-identity.md`.
- **Parallel?**: No.

### Subtask T005 – Green proof and docs gates

- **Purpose**: FR-004 green half + NFR-001.
- **Steps**: Run `uv run pytest tests/docs/test_mission_id_migration_page.py`
  (must pass), then the four docs gates:
  `uv run python -m scripts.docs.docs_index --write`,
  `uv run python -m scripts.docs.freshen_adr_inventory`,
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect
  errors=0), and `uv run pytest
  tests/architectural/test_no_legacy_terminology.py`. Reconcile any fallout
  (frontmatter `updated` date, index entries) caused by the page edit.
- **Files**: whatever the gates regenerate (expected: none beyond the page).
- **Parallel?**: No.

### Subtask T006 – Changelog entry

- **Purpose**: User-facing change (#6760).
- **Steps**: Add an `[Unreleased]` entry to `docs/changelog/CHANGELOG.md`:
  bold impact-first lead with `(#6760)`, then before/after, under 1,200
  characters.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: No.

## Test Strategy (include only when tests are required)

- The structural test IS the deliverable of T001; run it with
  `uv run pytest tests/docs/test_mission_id_migration_page.py`.
- No other suites locally (NO_FULL_HEAVY_SUITES_IN_MISSION); the four docs
  gates named in T005 are the doc-change gates.

## Risks & Mitigations

- Over-rewriting → ground every edit in the recorded live runs; touch only the
  four defective areas.
- Second source of truth in the test → import the contract from
  `specify_cli`; assert structure, never prose wording.
- Gate fallout (stale `updated` frontmatter, index drift) → run the gates and
  reconcile; never disable or skip a gate.

## Review Guidance

- The red-first proof (failing run before the fix) must be recorded in the WP
  history before approval.
- Reviewer checks: state list equals the imported `IDENTITY_STATES`; both
  samples parse and match the imported contract key-for-key; no `status`,
  `conflicts`, `ok`/`conflict` state tokens remain anywhere in the page; the
  backfill transcript matches live output; the four gates green.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
