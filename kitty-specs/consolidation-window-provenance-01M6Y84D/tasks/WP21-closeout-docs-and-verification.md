---
work_package_id: WP21
title: 'Closeout: docs sync, ADR residuals and verification sweep'
dependencies:
- WP20
requirement_refs:
- FR-001
- FR-006
- NFR-004
- NFR-005
- NFR-009
- C-009
- C-011
- C-012
- C-013
- C-014
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidation-window-provenance-01M6Y84D
base_commit: b8e57c68ca22a63560ba69b99481f421dafa8e2b
created_at: '2026-11-09T20:30:16.559263+00:00'
subtasks:
- T109
- T110
- T111
- T112
- T113
phase: Phase 4 - Behaviour changes, red-first
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/changelog/unreleased/7403-history-read-error-refuses.fixed.md
- docs/changelog/unreleased/7403-resume-frozen-anchors.fixed.md
execution_mode: code_change
model: ''
owned_files:
- CLAUDE.md
- docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md
- docs/changelog/unreleased/7403-history-read-error-refuses.fixed.md
- docs/changelog/unreleased/7403-resume-frozen-anchors.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP21 – Closeout: docs sync, ADR residuals and verification sweep

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP21 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Every behaviour change of the Mission has landed (WP16-WP20). This work package makes the written record match what shipped and proves the Mission-wide gates, **without changing any code**:

**Execution mode is `code_change` although you change no code** (tasks decision, 2026-11-08): the verification sweep (T113) must run against the integrated code, so this work package runs in an execution lane that builds on the code lane, not in the planning lane (a planning-lane checkout does not hold the code lanes' work before consolidation, and a planning-artifact work package at both ends of the Mission made the lane graph cyclic).

1. `CLAUDE.md` consolidation sections: the residual list, the `--dry-run` sentence (research R-09, settled by test), and one new "work-package windows" paragraph (T109).
2. ADR `2026-10-04-5-approval-stamp-bounds-the-approved-claim`: an amendment pointer to the Mission ADR and a synced residual list (T110).
3. The Mission ADR `2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition` matches the shipped design (sanctioned out-of-map edit, T111).
4. A draft follow-up comment for spec-kitty/spec-kitty-events#229, ready for the operator to post (T112). **You do not post it.**
5. Two changelog fragments for the operator-visible Phase 4 refusals that no earlier work package wrote (orchestrator decision 2026-11-08): `docs/changelog/unreleased/7403-history-read-error-refuses.fixed.md` (WP16, #5048(b)) and `docs/changelog/unreleased/7403-resume-frozen-anchors.fixed.md` (WP18, resume frozen anchors) (T109). Write each from the WP16 / WP18 design-decisions tracer entry that states the fix's operator-visible Before/After (the fix's reviewer already checked that sentence). WP07, WP17 (conditional), WP19 and WP20 own their own fragments; do not edit them.
6. A recorded Mission-wide verification sweep (sizes, complexity, coverage, suppressions, gates) and the tracer-file assessment (procedure `mission-tracer-files`, "Assess" step) (T113).
7. The issue matrix written with `spec-kitty agent issue-verdict` (every row a non-`unknown` verdict with evidence) and the acceptance matrix filled with `spec-kitty agent mission acceptance-verdict` (real criterion and evidence per `FR-001`..`FR-023`) (T113 blocks 13-14; post-tasks squad R-05/R-10).

If the sweep finds a defect in code, **do not fix it here**: record it in the WP history with the failing command and output, and tell the orchestrator, who returns the owning work package.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-001, FR-006, NFR-003, NFR-004, NFR-005, NFR-009, C-009, C-011 (cite ADRs by full slug), C-012 (Mission, never "feature"; name the sense of "merge"), C-013, C-014; Out of Scope.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-01 "Named residuals the ADR records", IC-09 (#229), Charter Check row "Mission hygiene (issue matrix)".
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-09, R-12, R-13 (count residuals from test files, never from prose), R-15, R-16, R-17.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/quickstart.md` — sections 3-5 (the verification commands this sweep runs).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/*.md` — the R-09 answer (WP02 entry), the (b) tier-1/tier-2 interpretation (WP19), the (g) reachability note (WP05/WP18), every design-decision entry.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/contracts/status-event-wp-window.md` — the shipped key contract (for T112).
- `packs/built-in/procedures/mission-tracer-files.procedure.yaml` — the "Assess" step.
- Current text to change:
  - `CLAUDE.md:566` — the paragraph "**Approved claim is bounded by the approval stamp (#5668).**" (one long line). It contains "Residuals, each open: a commit between two approvals on one lane; ..." and "`--dry-run` reports the claim-time refusals (it builds the full claim since #6771) but not the approved-bound refusals".
  - `CLAUDE.md:578` — cites `reconciliation.py:26-34`, `:1464-1471` and `reconciliation.py::build_approved_wp_set`; after the Phase 3 split those names live in new modules behind the facade.
  - `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md:168-183` (Residuals), `:177` and `:226` ("`consolidate --dry-run` ... does not report"), `:316` (single_branch amendment mentions `--dry-run`), frontmatter `updated:` (line 8).
- **Do not**: regenerate the docs index or ADR inventory (bot-owned; a docs lint fails hand edits); edit `docs/changelog/CHANGELOG.md`; bump `pyproject.toml`; post on GitHub; edit any file under `src/` or `tests/`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP21 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T109 – Sync `CLAUDE.md`

- **Step 0 — collect the facts first** (record each answer in the WP history before editing):
  1. R-09: read the WP02 entry in `traces/design-decisions.md` and run `uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py -k "post_approval"` plus `tests/consolidation/test_lane_approval_windows.py::test_stray_commit_between_two_approvals_forecast_refuses`. Answer: does `consolidate --dry-run` report `LANE_MOVED_AFTER_APPROVAL` for a post-approval commit? Yes or no, with the cell key.
  2. Residuals: count strict `xfail`s from the test files, never from prose (R-13): `grep -n "xfail" tests/consolidation/test_approved_bound_residuals.py tests/consolidation/test_reconciliation_intended_verdicts.py tests/consolidation/test_canceled_content_residuals.py tests/consolidation/test_canceled_line_attribution_6309.py tests/integration/test_single_branch_approval_windows.py`.
  3. Module homes: `grep -n "^def build_approved_wp_set\|^def _approved_bound_verdict\|^class ApprovedWpCommitSet" src/specify_cli/consolidation/*.py`.
- **Edits in the paragraph at `CLAUDE.md:566`** (keep it one paragraph; change only these clauses):
  1. Replace the residual "a commit between two approvals on one lane" with: "a commit between two approvals on a lane where no approved work package has a recorded window (a Mission started before #7403; on a lane with at least one recorded window it is refused, ADR `2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition`); two work packages claimed in parallel on one lane, or one claimed early and parked without returning to `planned`, whose window also covers the other's commits (strict `xfail` `test_parallel_claims_window_is_not_over_wide`)".
  2. Rewrite the `--dry-run` clause from the Step 0 answer. If the forecast reports the bound refusal: "`--dry-run` reports the claim-time refusals, the approved-bound refusals included (it builds the full claim since #6771)". If it does not, keep the clause and name the cell that proves it.
- **New paragraph** right after `CLAUDE.md:566`, headed `**Work-package windows (#7403).**`, 8-14 sentences, covering exactly:
  - where the window is recorded: `policy_metadata.wp_window` on every non-migration move of a lane-mapped work package into `claimed` / `in_progress` (`{"schema_version": 1, "open_sha": ...}` or a typed gap `lane_branch_missing` / `capture_failed` with `cause`); written by `status/transition_pipeline.py` from the one lane-head reading (`status/lane_head.py` `LaneHeadReading`), never refusing a move; classified `BRANCH_RELATIVE`;
  - the window opener (FR-021) in one sentence, with the review-rejection interpretation;
  - the lane check: windows `(open SHA, newest approval stamp]`; exemption anchors = closed-world anchors + other lanes' approval stamps, never the lane's own; tier 1 (`check_lane`) unchanged first; a commit outside every window refuses `LANE_MOVED_AFTER_APPROVAL` naming the commit and the work package approved before it; the dependency-chain exception;
  - the fallback: a window gap (`not recorded`, `capture failed`, `lane branch missing`, `not on lane`) is judged by the approval-stamp bound from the claim base and never refused for the gap alone; an all-gap lane runs today's check unchanged; the gap report (heading text, `window_gaps` in `--dry-run --json`; not in the `orchestrator-api` envelope);
  - `single_branch` reads the recorded window when present;
  - the other Phase 4 fixes, one clause each: a history-read error in the authored walk refuses instead of counting as a deletion (#5048(b)); on `--resume` the closed world, the approved bound, the fully-canceled-lane check and the approved-reviewed attestation read one frozen claim-time anchor set (degraded anchors: a pre-upgrade record, a record with no capture); the forecast, fresh run and resume build their claim inputs in one constructor (`consolidation/claim_inputs.py`, sources `LIVE` / `LIVE_THEN_SAVED` / `SAVED`);
  - `reconciliation.py` is a re-exporting facade over `reconciliation_*.py` modules; patch moved names through `tests/consolidation/reconciliation_family.py`.
- **Changelog fragments** (section `fixed`, one entry each, README style `- **<what>** (#issue). **Before:** ... **After:** ...`; no version bump, never edit `docs/changelog/CHANGELOG.md`). Write each from what shipped (read the WP16 / WP18 red-first tests and their refusal text first), not from this prompt:
  - `docs/changelog/unreleased/7403-history-read-error-refuses.fixed.md`: a git history read error during the authored-content walk of `spec-kitty consolidate` now refuses the claim, naming the path and the error, before any branch moves, instead of counting the path as deleted (#5048).
  - `docs/changelog/unreleased/7403-resume-frozen-anchors.fixed.md`: `spec-kitty consolidate --resume` judges the closed world, the approved bound, the fully-canceled-lane check and the approved-reviewed attestation against the anchors frozen when the claim was first taken, instead of re-reading live tips (#7403).
  Then run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
- **Stale references**: retarget the file references on `CLAUDE.md:578` to the module that now defines each symbol (Step 0.3). Do not reword that paragraph otherwise.
- **Style**: plain sentences, "Mission" never "feature", "consolidate" (lane consolidation into the local target branch), never bare "merge"; ADRs by full slug.

### Subtask T110 – `2026-10-04-5` amendment pointer and residual sync [P]

- **File**: `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md`.
- **Steps**:
  1. Append a section at the end: `## Amendment 2026-11-08: lane approvals are judged by recorded work-package windows (#7403)`, 4-8 sentences: what changed for lanes (the Option 6 per-work-package windows now apply to every code lane with a recorded window), the exemption-anchor ruling, the fallback and gap report, `single_branch` reading the recorded window, and a link to the Mission ADR by full slug and relative path (`./2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md`). The Mission ADR holds the detail; do not repeat it.
  2. In `### Residuals` (`:168-183`): change the first bullet to say the residual is closed on lanes with at least one recorded window and stays open on lanes where every approved work package has a window gap, and add the parallel-claims residual (WW-6). Correct the `--dry-run` bullet (`:177`) and the matching sentence at `:226` and the mention at `:316` from the T109 Step 0 answer. Leave every other residual as written.
  3. Update frontmatter `updated:` to the date you edit it (ISO, `T00:00:00Z`).
  4. Do not change `status:` or `doc_status:`; do not touch the generated ADR index.

### Subtask T111 – Sync the Mission ADR with what shipped (sanctioned out-of-map edit) [P]

- **File**: `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md` (owned by WP01; this edit is sanctioned and is the only out-of-map file edit besides the tracer files and the T112 draft).
- **Steps**: compare the ADR text with the code and the tracer entries, and correct only what differs:
  - the tier-1 / tier-2 structure of the lane check and its consequence for refusal text (WP19 entry);
  - the shipped names: `GapEntry`, `window_gap_report.py`, `bind_lane_predicates`, `classify_windows`, `check_lane_windows`, `check_write_branch_windows`, `ClaimInputs` / `ClaimInputSource`;
  - the R-09 answer (the ADR was told not to state it until the corpus pinned it; state it now);
  - the NFR-002 flip list as it landed, including (g) if WP18 recorded it as unreachable, with the reason;
  - a `Confirmation` (or `Evidence`) list naming the test files: `tests/status/test_wp_window_capture.py`, `tests/consolidation/test_window_opener.py`, `test_claim_inputs_parity.py`, `test_lane_approval_windows.py`, `test_lane_window_query_count.py`, `test_window_gap_report_entry_points.py`, `test_resume_frozen_anchors.py`, `test_reconciliation_characterization.py`, `test_reconciliation_intended_verdicts.py`, `test_reconciliation_seeded_mutations.py`.
- Keep `status: Proposed` (acceptance is the operator's call); update `updated:`.

### Subtask T112 – Draft the spec-kitty/spec-kitty-events#229 follow-up comment [P]

- **Steps**:
  1. Read the issue (read-only): `unset GITHUB_TOKEN && gh issue view 229 -R spec-kitty/spec-kitty-events --comments`.
  2. Compare its stated key shape with `contracts/status-event-wp-window.md` and with what `status/transition_pipeline.py` writes. Known delta: the gap reason `lane_branch_missing` (no `cause`) was added after filing (plan IC-09); check also `detail` `maxLength`, `schema_version`, and the writer rules W-1..W-7.
  3. Write a comment of at most 20 lines: what changed since filing, the final JSON Schema excerpt (or a link to the contract file at the PR head), the reader rules R-1..R-7 in one line each, and the request (write, preserve and type the key with the same shape).
  4. Save the draft as `kitty-specs/consolidation-window-provenance-01M6Y84D/research/events-229-follow-up.md` when your checkout carries `kitty-specs/`, and always paste it into `spec-kitty agent tasks add-history WP21 --note "..."`. **Do not post it**: posting is an outward-facing write that needs the operator's authorization.
  5. If nothing differs, the draft says so in one line and the operator decides whether to post.

### Subtask T113 – Mission-wide verification sweep and tracer assessment

Run every block, record each command with its pass/fail counts (or numbers) in the WP history. A red result is reported, not fixed (see Objectives).

1. **Phase gates and Mission tests**:
   ```bash
   uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py tests/consolidation/test_refusal_precedence_matrix.py tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py tests/consolidation/test_reconciliation_seeded_mutations.py
   uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py
   uv run --frozen pytest -q tests/status/test_wp_window_capture.py tests/consolidation/test_window_opener.py tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_lane_window_query_count.py tests/consolidation/test_window_gap_report.py tests/consolidation/test_window_gap_report_entry_points.py tests/consolidation/test_resume_frozen_anchors.py
   uv run --frozen pytest -q tests/consolidation/test_authored_walk_read_error.py tests/consolidation/test_forecast_fresh_run_parity.py tests/consolidation/test_reconciliation_split_shape.py tests/consolidation/test_reconciliation_module_imports.py
   uv run --frozen pytest -q tests/integration/test_single_branch_approval_windows.py
   ```
   Expected `-rxX`: only `test_parallel_claims_window_is_not_over_wide` (and a (g) pin only if WP18 recorded it unreachable) report `XFAIL`; zero `XPASS`.
2. **Owning subsystem directories** (C-013): `uv run --frozen pytest -q tests/consolidation/ tests/terminus/ tests/status/`.
3. **Architectural gate files** (named, never the bare directory):
   ```bash
   uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py tests/architectural/test_dossier_sha_provenance.py tests/architectural/test_status_module_boundary.py tests/architectural/test_cold_import_status_boundary.py tests/ci/test_reducer_lock_census.py tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_no_legacy_terminology.py
   ```
4. **NFR-003 sizes**: `wc -l src/specify_cli/consolidation/reconciliation*.py` (every module ≤ 1,200 lines; largest ≤ 1,228, 30% of 4,096) and `grep -cE '^(def|class) ' src/specify_cli/consolidation/reconciliation.py` (expected `0`).
5. **NFR-004 complexity**: `uv run --frozen ruff check --select C901 src/specify_cli/consolidation src/specify_cli/status` (zero findings).
6. **C-014 lint, format, types**: `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, `uv run --frozen mypy src/specify_cli/consolidation src/specify_cli/status`.
7. **NFR-005 suppressions and allowlists** (moved lines re-add existing suppressions, so compare added against removed):
   ```bash
   git diff main...HEAD -U0 -- src tests | grep -cE '^\+[^+].*(# noqa|# type: ignore)'
   git diff main...HEAD -U0 -- src tests | grep -cE '^-[^-].*(# noqa|# type: ignore)'
   git diff --stat main...HEAD -- tests/architectural/dead_symbol_allowlist.yaml tests/architectural/_exemptions
   ```
   Added must not exceed removed; the allowlist entry count is unchanged (count `- ` entries before and after with `git show main:<file> | grep -c ...`).
8. **NFR-009 changed-line coverage**:
   ```bash
   uv run --frozen pytest -q --cov=src/specify_cli/consolidation --cov=src/specify_cli/status --cov-report=xml:coverage-mission.xml tests/consolidation/ tests/terminus/ tests/status/
   uv run --frozen diff-cover coverage-mission.xml --compare-branch=main --fail-under=90
   ```
   Delete `coverage-mission.xml` afterwards; never commit it.
9. **Docs gates** (for T109-T111):
   ```bash
   uv run --frozen pytest -q tests/docs/test_adr_content_invariance.py tests/docs/test_adr_readme_prose.py tests/docs/test_architecture_docs_consistency.py tests/architectural/test_glossary_authority_parity.py
   uv run --frozen pytest -q tests/runtime/test_requirement_grammar_parity.py tests/specify_cli/test_requirement_reason_parity.py
   uv run --frozen python -m scripts.docs.check_spelling --pass typo
   uv run --frozen python -m scripts.docs.check_spelling --pass us
   uv run --frozen python -m scripts.docs.check_changelog_style
   ```
10. **Red-first evidence audit** (NFR-002, NFR-010): `git log --oneline main..HEAD -- tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_resume_frozen_anchors.py tests/consolidation/test_claim_inputs_parity.py tests/consolidation/test_window_gap_report_entry_points.py tests/consolidation/test_reconciliation_intended_verdicts.py`; for each of WP16-WP20, confirm the WP history names a red commit that precedes its fix commit. List missing evidence.
11. **Golden diff audit**: take `<phase-3 tip>` from WP15's design-decisions tracer entry `Phase 3 tip = <sha>` (post-tasks squad R-11; cite it in the history note), then `git diff <phase-3 tip>..HEAD -- tests/consolidation/characterization/verdict_corpus.json` and `uv run --frozen python -c "from tests.consolidation.characterization_support import changed_cells; print(changed_cells('<phase-3 tip>'))"`; list every changed cell key and map it to NFR-002 (a)-(h). Any unmapped cell is a finding.
12. **Tracer assessment** (procedure "Assess" step): read all three files under `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/`. Then:
    - append one entry with `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category approach --actor "closeout WP21" --entry "Tracer assessment. <the 3-5 most significant insights in 1-3 sentences>"` (never hand-edit the file);
    - draft one tracker issue (title + 3-6 line body) per unresolved tooling-friction entry and put the drafts in the WP history. **Do not file them**: filing is an outward-facing write the operator authorizes;
    - list the insights the Mission retrospective should carry.
13. **Issue matrix** (post-tasks squad R-05; this WP owns the write, through the canonical command only, never by editing `issue-matrix.json`). One call per row; every row ends with a non-`unknown` verdict and an `--evidence-ref` (test id plus commit SHA, or the spec section):
    ```bash
    M=consolidation-window-provenance-01M6Y84D
    spec-kitty agent issue-verdict --mission $M --issue "#7403" --verdict fixed --wp WP19 --actor "closeout WP21" --title "<issue title>" --evidence-ref "WP19 red <sha> / fix <sha>: tests/consolidation/test_lane_approval_windows.py::test_stray_commit_between_two_approvals_refuses; WP07-WP20 window provenance"
    spec-kitty agent issue-verdict --mission $M --issue "#5721" --verdict deferred-with-followup --wp WP19 --actor "closeout WP21" --title "<issue title>" --evidence-ref "Partial: the commit-between-two-approvals bullet is fixed by WP19 (<sha>, test_stray_commit_between_two_approvals_refuses); the parallel-claims residual WW-6 (test_parallel_claims_window_is_not_over_wide, strict xfail) and the other bullets stay open. Follow-up: #5721"
    spec-kitty agent issue-verdict --mission $M --issue "#5048" --verdict fixed --wp WP16 --actor "closeout WP21" --title "<issue title>" --evidence-ref "Part (b): WP16 red <sha> / fix <sha>: tests/consolidation/test_authored_walk_read_error.py::test_history_read_error_refuses_the_claim_and_moves_nothing"
    spec-kitty agent issue-verdict --mission $M --issue "#5703" --verdict not-applicable --actor "closeout WP21" --title "<issue title>" --evidence-ref "Out of scope: spec.md Out of Scope (lane-id rebuilds that orphan recorded windows)"
    spec-kitty agent issue-verdict --mission $M --issue "#7359" --verdict not-applicable --actor "closeout WP21" --title "<issue title>" --evidence-ref "Out of scope: spec.md Out of Scope (interrupted-run recovery and teardown honesty)"
    spec-kitty agent issue-verdict --mission $M --issue "#7362" --verdict not-applicable --actor "closeout WP21" --title "<issue title>" --evidence-ref "Out of scope: spec.md Out of Scope (forecast evaluating every verify-side check)"
    ```
    The CLI has no `partial` verdict: #5721 is `deferred-with-followup` with "Partial:" leading the evidence and the WW-6 residual named. Read each issue title with `gh issue view <n> --json title` (read-only). If a verdict above contradicts what shipped (for example WP16's fix was reverted), stop and ask the orchestrator.
14. **Acceptance matrix** (post-tasks squad R-10; this WP owns it, canonical command only, never edit `acceptance-matrix.json`): for **every** criterion row (`FR-001` .. `FR-023`), replace the scaffold placeholder with a real criterion and record its evidence:
    ```bash
    spec-kitty agent mission acceptance-verdict --mission $M --criterion FR-007 --result pass --verification-method automated_test --description "<one-sentence testable criterion from spec.md FR-007>" --evidence "tests/consolidation/test_lane_approval_windows.py::test_stray_commit_between_two_approvals_refuses @ <sha>" --notes "<NFR-002 cell / SC it also proves>" --actor "closeout WP21"
    ```
    Use the test names collected in block 11 and in every WP's history. A criterion without passing evidence is `--result pending` with `--notes` saying what is missing, never `pass`; a criterion the Mission defers is `--result deferred --reason "..." --follow-up "#NNN"`. After the last call, `python3 -c "import json;d=json.load(open('kitty-specs/$M/acceptance-matrix.json'));print([c['criterion_id'] for c in d['criteria'] if 'TODO' in (c.get('notes') or '') or c['evidence'] is None])"` (run from a checkout carrying the coordination surface, or read it through `git show <coord branch>:...`) prints `[]` or only deliberately pending rows, listed in the history.

## Test Strategy

No new tests. The sweep re-runs the Mission's tests and gates and records the evidence. Docs edits are gated by the docs and terminology tests in block 9 and block 3.

## Definition of Done

- [ ] `CLAUDE.md` and the `2026-10-04-5` ADR edited per T109/T110, and the two changelog fragments created per T109; only those owned files plus the sanctioned out-of-map edits (Mission ADR, tracer files, the T112 draft) changed: `git diff --stat` shows nothing under `src/` or `tests/`.
- [ ] Every ADR citation uses the full slug (`grep -nE "ADR \`20[0-9-]+\`" CLAUDE.md docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` shows full slugs only).
- [ ] T112 draft recorded and **not** posted.
- [ ] T113 blocks 1-13 recorded with commands and counts; every red result reported to the orchestrator with its command and output.
- [ ] No docs index or ADR inventory regenerated; `pyproject.toml` untouched.
- [ ] Issue matrix (T113 block 13): `#7403` fixed, `#5721` deferred-with-followup with "Partial:" evidence naming WW-6, `#5048` fixed (part (b)), `#5703` / `#7359` / `#7362` not-applicable (spec Out of Scope); every row has an `evidence_ref`; zero `unknown` verdicts; all written with `spec-kitty agent issue-verdict`.
- [ ] Acceptance matrix (T113 block 14): every `FR-001`..`FR-023` row has a real description and evidence (or is deliberately `pending`/`deferred`, listed in the history); no `TODO` placeholder left; all written with `spec-kitty agent mission acceptance-verdict`.
- [ ] Block 11 cites WP15's `Phase 3 tip = <sha>` tracer entry.
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback): the T113 assessment entry via `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category approach --actor "closeout WP21" --entry "Tracer assessment. <the 3-5 most significant insights>"`; `--category design-decisions --actor "implement WP21"` for any wording choice in T109-T111; `--category tooling-friction` for friction. The command works from any checkout and commits to the coordination surface itself.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Stating the R-09 behaviour from memory**: Step 0 makes it a test result.
- **Residual drift between prose and pins**: count from test files (R-13).
- **Hand-edited generated docs**: the "Do not" list; the docs lint fails such edits anyway.
- **Sweep turns into fixing**: report, do not fix; the owning work package is returned.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid** (docs judgment against shipped behaviour; the sweep itself is mechanical).
- Check each changed residual and the `--dry-run` sentence against the cited test, not against the ADR.
- Check the new `CLAUDE.md` paragraph against the Mission ADR and the code names (spot-check three names with `grep`).
- Check the sweep record is complete (13 blocks) and that nothing was posted to GitHub.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP21 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP21 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
