---
work_package_id: WP22
title: Decision records and seam documentation
dependencies:
- WP21
requirement_refs:
- FR-017
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
subtasks:
- T115
- T116
- T117
- T118
phase: Phase 8 - Documentation
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
agent: claude
authoritative_surface: docs/
create_intent:
- docs/adr/4.x/2026-10-01-2-decision-ledger-primary-partition.md
execution_mode: planning_artifact
model: claude-sonnet-5
owned_files:
- docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md
- docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md
- docs/architecture/artifact-placement-seam.md
- docs/adr/4.x/2026-10-01-2-decision-ledger-primary-partition.md
- docs/adr/4.x/index.md
- docs/api/cli-commands.md
- docs/api/agent-subcommands.md
- docs/api/finalize-tasks-internals.md
role: curator
tags: []
task_type: implement
tracker_refs: []
assignee: ''
shell_pid: ''
---

# Work Package Prompt: WP22 – Decision records and seam documentation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Make the architecture records state the **shipped** behaviour (FR-017, DIRECTIVE_037 Living Documentation Sync, DIRECTIVE_003 Decision Documentation). This is a docs-only, planning-artifact WP. The code-comment half of FR-017 already landed in WP04 (`resolution.py` docstrings, the `CoordState.EMPTY` contract text) and WP12 (`artifacts.py` #3928 comments). This WP owns the three `docs/` files.

Done means:

- **ADR `2026-06-19-1`** carries a new, dated amendment section. It states:
  - the single-home rule;
  - `PlacementSeam.write_dir` as the one write-location accessor, owning materialize, seed and refuse;
  - that writes never substitute the repository root checkout;
  - that the read-side `EMPTY` fallback is kept (C-002);
  - that a post-fix `EMPTY` is loud in both coordination topologies and is restored from the coordination branch tip on write;
  - the remote-only refusal (#4970 parity).
- The **decision-ledger reversal of the #3928 intent** is recorded as an ADR amendment: the ledger is PRIMARY, its events stay COORD, the index has a merge driver, pre-fix coordination-only ledgers get a doctor repair, and teardown refuses to destroy them.
- **ADR `2026-09-24-2`** notes the write-side accessor beside its read fail-closed rule.
- **`docs/architecture/artifact-placement-seam.md`**:
  - has a `write_dir` subsection;
  - has every stale line citation re-derived against the final code;
  - records the `DECISION_LEDGER` partition move (via its Partition-Move Audit Checklist);
  - says its piece about coordination residue.
- Freshness metadata is updated, the terminology guard and the docs structure tests are green, and the PR can cite the amended sections as FR-017's checkable anchor.

## Context & Constraints

- **Spec**:
  - FR-017 (what must be amended; "review-only; the PR cites the amended ADR sections as the checkable anchor");
  - C-001 (one sanctioned seam extension), C-002 (keep the read fallback), C-003 (no automatic log merge), C-004 (fix forward);
  - FR-009 / FR-009b / FR-009c (the ledger story);
  - Edge Cases ("Read-side behaviour for an empty coordination surface", "Transient staging").
- **Plan**: IC-17 (Affected surfaces lists exactly these files and the citation fixes). "17 last": it depends on WP21, so it documents the merged, end-to-end-proven behaviour.
- **Research**: D1 (accessor shape and rejected alternatives), D2 (lock order and atomicity), D3 (prefix rule and fork refusal), D4 (post-fix discriminator, ruling Q3), D5 (seed commit, ruling Q5), D11 (target fast-forward retired), D12 (ledger readers that flip), D13 (index merge driver), D14/D15 (fork detector, teardown refusal), D20 (remote-only refusal, ruling Q1), D21 (consolidation and `materialize` writers, ruling Q4).
- **Contracts**: `contracts/write-location-accessor.md` (the state table and errors: summarize, don't paste), `contracts/seed.md`, `contracts/doctor-decisions-fork-report.md`.
- **Data model**: §2 (per-state handling) and §6 (the lifecycle diagram; you may reuse a simplified Mermaid diagram).
- **Doctrine for this WP**:
  - DIRECTIVE_042 Common Docs (in-file frontmatter lifecycle metadata, delete-stale);
  - the charter "Writing, Communication & Diagramming Doctrine" section;
  - the terminology canon: Mission, never feature, and always name the sense of "primary" (PRIMARY partition / repository root checkout / target branch / primary branch). The ADRs currently say "primary checkout"; new text says "repository root checkout".
  - Overloaded `routing` is a footgun (CLAUDE.md): name the sense ("placement routing", "branch-target routing") in any new sentence.
- **Docs tests that pin these files** (read them before editing):
  - `tests/docs/test_artifact_placement_seam_page.py` asserts the page's structure and citations, not its prose. It requires six `##` sections, among them `What "routing" means here`, `The layer table`, `Both composition roots`, `The compliance taxonomy`, `Honest bounds` and `Citations`. The `Both composition roots` body must keep `resolve_artifact_surface`, `resolve_placement_only` and `placement_seam(`. There must be no `## Decision Outcome` heading. Frontmatter is required. Put `write_dir` as a `###` subsection or a bullet inside `Both composition roots`. Never rename or remove those `##` headings.
  - `tests/docs/test_adr_content_invariance.py` (for example `test_every_adr_has_bare_madr_status_frontmatter`) keeps ADR frontmatter well-formed.
  - The freshness tests: `tests/docs/test_docs_freshness_invariant.py`, `tests/docs/test_check_docs_freshness.py`.
  - `tests/docs/test_architecture_docs_consistency.py`.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Scope guard**: this WP owns ONLY the three `docs/` files above.
  - If a new standalone ADR file seems necessary, stop and ask the orchestrator: it would have to be added to `owned_files` and to the ADR index first.
  - Do not edit `src/`, `tests/`, or `kitty-specs/` (the activity-log entry in this prompt excepted).
- **Brownfield scout (binding read)**: before coding, read `## WP22` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- This is a `planning_artifact` WP: every owned path is under `docs/`. `finalize-tasks` places it on the planning lane per `lanes.json`. Start with `spec-kitty agent action implement WP22 --agent claude`, and consume the resolved workspace path; never reconstruct it.
- It shares no owned file with another WP. It depends on WP21 and therefore transitively on every functional WP, so the code you cite is final. Re-derive citations in the workspace the command resolves, not from the plan's line numbers.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T115 – ADR 2026-06-19-1: the single-home amendment

- **Purpose**: This ADR is the governing record for the empty coordination surface. Its 2026-06-21 amendment established the **loud primary fallback**, which is a read-and-write policy. This Mission splits that policy: reads keep it, writes stop substituting the repository root checkout. The ADR must say so, or future readers will "fix" the write side back.
- **Steps**:
  1. Read the whole ADR (≈202 lines). Its structure:
     - frontmatter with `status: Superseded` and the amended date string;
     - `## Amendment (2026-06-21 — mission mission-surface-resolver-safety-net-01KVN754)` at ≈L17, followed by `### Amended decision` / `### Why the reversal` / `### Scope of the amendment (binding)` / `### Consequence for the typed-error surface` / `### Stale reference correction`;
     - then `## Context` (≈L86), `## Decision` (≈L118), `## Distinctions preserved` (≈L150), `## Consequences` (≈L163), `## Alternatives considered` (≈L191).
  2. Insert a NEW top amendment, newest first, above the 2026-06-21 one: `## Amendment (2026-10-01 — mission coord-artifact-single-home-01M3V4BE)`. Write it with these subsections:
     - `### Amended decision: writes never substitute the repository root checkout`. For a coordination-routed Mission (topology `coord` or `lanes_with_coord`, owned checkouts included), every COORD-partition write obtains its location from `PlacementSeam.write_dir(kind)` (`src/mission_runtime/resolution.py`; delegate `specify_cli.coordination.coord_seed.establish_coord_write_location`).
     - `### Per-state write behaviour`: a compact table from data-model §2 / the contract. NONE → PRIMARY; MATERIALIZED → coordination dir (no side effects unless a refused seed commit is pending, I-SEED-10); UNMATERIALIZED with a local branch → materialize first; remote-only → refuse `COORDINATION_WORKTREE_UNMATERIALIZED` with a recovery hint (#4970 parity, ruling Q1); EMPTY pre-fix → seed once under the status lock (prefix rule, one seed commit on the coordination branch, root copy restored; fork → `COORD_SEED_FORK_REFUSED`); EMPTY post-fix → loud warning, restore from the coordination branch tip, then write (ruling Q3); DELETED → `CoordinationBranchDeleted`.
     - `### Read side (unchanged, C-002)`: reads keep the loud declared PRIMARY fallback. The only read-side change is that the EMPTY warning now fires for post-fix Missions in **both** coordination topologies (D4 discriminator: the `Spec-Kitty-Coordination-Seed: <mission_id>` commit trailer written by the seed and create commits). Retiring the read fallback is a follow-up.
     - `### Create`: create materializes and seeds eagerly and commits the creation records on the coordination branch. The target branch never receives a COORD record. Expected coordination-vs-target divergence is a shared predicate (`is_expected_coordination_divergence`, `missions/_create.py`) used by create and `doctor coordination`.
     - `### Enforcement`: the extended write-side rederivation gate (`tests/architectural/test_no_write_side_rederivation.py`, COORD-writer grammar, empty shrink-only allowlist with a cap of 0) and the end-to-end invariant (`tests/integration/test_coord_single_home_workflow.py`).
  3. Update the frontmatter `date` string to append `· **Amended**: 2026-10-01`. Keep `status:` as MADR-valid; do not invent a status value. Update `description` only if it would otherwise be false. It says "the resolver falls back to the repository-root checkout", which stays true for reads, so append "for reads; writes establish the coordination surface (2026-10-01)".
  4. Re-derive every symbol and line you cite with `grep -n` in the workspace.
- **Files**: `docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md`.
- **Validation**:
  - `tests/docs/test_adr_content_invariance.py` is green;
  - every cited symbol exists (`grep -rn "def write_dir" src/mission_runtime/resolution.py`, `grep -rn "establish_coord_write_location" src/specify_cli/coordination/coord_seed.py`).
- **Edge cases**:
  - Do not rewrite the 2026-06-21 amendment's text. Amendments are additive history.
  - If the original 2026-06-19 decision text contradicts the new amendment, add a one-line pointer to the new amendment rather than editing it.

### Subtask T116 – Ledger reversal of the #3928 intent, and ADR 2026-09-24-2 write-side note

- **Purpose**: Under #3928, the decision ledger (`decisions/DM-*.md`, `decisions/index.json`) was COORD-partition, "single-writer coordination bookkeeping". This Mission reverses that: the ledger is PRIMARY and its events stay COORD (operator ruling `decision-ledger-partition`). No ADR currently records #3928's intent (`grep -rn 3928 docs/adr` is empty on this base); it lived in code comments that WP12 rewrote. A decision that big needs a durable record. ADR 2026-09-24-2 also lists `DECISION_LEDGER` among coord-partition kinds in its Context (≈L12-14), which is now stale.
- **Steps**:
  1. In ADR 2026-06-19-1's new amendment (T115), add `### Decision ledger: PRIMARY partition (reverses the #3928 COORD intent)`. Cover:
     - what moved and why: the ledger was already written and read on the PRIMARY partition since #4966, so its classification now matches;
     - what stayed COORD: decision events in `status.events.jsonl` and `decisions.events.jsonl`;
     - consequences:
       - the commit router puts the ledger on the target branch;
       - `accept` commits uncommitted ledger files, and the consolidation dirty gate refuses them instead of resetting them as residue;
       - the index travels with lane branches, so it gets the `spec-kitty-decision-index` merge driver (keyed union by `decision_id`, fold precedence from `decisions/index_fold.py`);
       - the `test_merge_reconciliation_class_guard.py` single-writer ruling was amended;
     - the fix-forward path for pre-fix Missions: `doctor decisions` reports `DECISION_LEDGER_ONLY_ON_COORDINATION`, `--repair` copies the ledger to the PRIMARY partition additively and makes no commit, and teardown and consolidation refuse with `COORDINATION_LEDGER_UNREPAIRED` until it is repaired (FR-009c);
     - the fork posture: `doctor decisions` and `decision verify` detect forks (`DECISION_LOG_FORKED`) from refs and worktrees, and `--repair` never drops an entry and never re-sequences (C-003).
  2. ADR 2026-09-24-2:
     - In `## Consequences` (≈L93-120, near the bullets about scope at ≈L80-85 and the "future contributor extending the UNMATERIALIZED raise" bullet at ≈L117-120), add a bullet: the read-side raise is unchanged, and the **write** side is governed by `PlacementSeam.write_dir`, which materializes a locally-present branch before writing and refuses a remote-only one, never substituting PRIMARY. Link ADR 2026-06-19-1's 2026-10-01 amendment.
     - In the Context list of coord-partition kinds (≈L12-14), add "(`DECISION_LEDGER` was reclassified to the PRIMARY partition on 2026-10-01; see ADR 2026-06-19-1)". Do not silently delete it; the ADR is historical.
  3. Re-check frontmatter validity in both ADRs.
- **Files**: both ADR files.
- **Validation**:
  - ADR tests are green;
  - `grep -n "DECISION_LEDGER" src/mission_runtime/artifacts.py` confirms it sits in `_PRIMARY_ARTIFACT_KINDS` in the final code;
  - the code constants you cite exist (`grep -rn "COORDINATION_LEDGER_UNREPAIRED\|DECISION_LEDGER_ONLY_ON_COORDINATION\|DECISION_LOG_FORKED\|spec-kitty-decision-index" src`).
- **Edge cases**:
  - Cite issue numbers as tracker references (#3928, #4966, #5023, #5519), as the ADRs already do.
  - Do not create a new ADR file (see the scope guard).

### Subtask T117 – `docs/architecture/artifact-placement-seam.md`: `write_dir`, stale citations, partition move

- **Purpose**: The seam page is the explanatory map of placement. It must show the third projection (`write_dir`) and stop citing lines that drifted long ago.
- **Steps**:
  1. **`write_dir` section.** In `## Both composition roots` (≈L82-97), after the read-root and write-root bullets (≈L86-89), add a short `### The write location (`write_dir`)` subsection or a third bullet. Cover:
     - `write_target` answers "which ref" and is ref-only and side-effect-free;
     - `read_dir` answers "where to read" and keeps the EMPTY fallback;
     - `write_dir` answers "where to write" and agrees with `write_target` by construction. For COORD kinds of a coordination-routed Mission it owns materialize, seed and refuse; for PRIMARY kinds and for `lanes`/`single_branch` it returns the declared PRIMARY dir.
     - Link the contract (`kitty-specs/coord-artifact-single-home-01M3V4BE/contracts/write-location-accessor.md`) and the ADR amendment.

     Keep `resolve_artifact_surface`, `resolve_placement_only` and `placement_seam(` in that section (the test asserts them).
  2. **Stale citations.** Re-derive EVERY `path:line` citation on the page with `grep -n` in the workspace. Known drifts at this Mission's base `ecb5dd914a`:

     | Citation on the page | Actual at the base |
     |---|---|
     | `PlacementSeam` `resolution.py:1373` (L53) | `class PlacementSeam` at L2261 |
     | `resolve_placement_only` `:1241` (L88) | `def` at L1827 |
     | `write_target` `:1408` / `:1415` (L89, L171) | L2304 |
     | `read_dir` `:1467` (L172) | L2318 |
     | `placement_seam(...)` `:1850` (L92) | ≈L2835 |
     | `resolve_artifact_surface` `:1718` (L86) | re-derive |
     | `coord_read_dir_for` `:1839` | re-derive |
     | `artifacts.py:136`, `:172`, `:269` (L54) | re-derive after WP12's move |

     These shifted again with WP04's `write_dir` addition, so derive from the final code, not this table. Where a citation is in a measured "Honest bounds" count table (≈L171-172), update only the line references; re-measuring the counts is out of scope unless they are trivially re-countable. If you leave a count, keep its "measured at" context honest.
  3. **Partition move.** Apply the page's own `## Partition-Move Audit Checklist` (≈L200-256) to `DECISION_LEDGER`:
     - add a short worked note ("2026-10-01: `DECISION_LEDGER` moved COORD → PRIMARY") listing how each checklist item was satisfied: the reader flips (WP12's focused tests), the guards updated, the merge driver added, the teardown refusal;
     - where the L1 row (≈L54) names the frozensets, make sure nothing implies the ledger is COORD.
  4. **Coordination-residue note.** Wherever the page discusses coordination residue (`grep -n residue`), state that `decisions/` maps to a PRIMARY kind now, so it is never reset as residue.
  5. Bump frontmatter `updated:` from `'2026-09-30'` to the commit date.
- **Files**: `docs/architecture/artifact-placement-seam.md`.
- **Validation**:
  - `tests/docs/test_artifact_placement_seam_page.py` is green;
  - every `resolution.py:NNNN` citation on the page resolves to the named symbol. A quick script is fine: grep each cited line number and assert the symbol name appears there, but do not commit the script.
- **Edge cases**:
  - Never add a `## Decision Outcome` heading (it trips `test_page_does_not_restate_normative_rules_as_its_own_heading`); link the ADRs instead.
  - Keep the six required `##` headings verbatim.

### Subtask T118 – Docs hygiene: freshness, terminology guard, FR-017 anchor list

- **Purpose**: The docs gates the CI runs, plus a checkable anchor for the review-only FR-017.
- **Steps**:
  1. Freshness: update the `updated:` / `date` metadata on all three files consistently with Common Docs conventions (DIRECTIVE_042), and confirm `tests/docs/test_docs_freshness_invariant.py` and `tests/docs/test_check_docs_freshness.py` stay green.
  2. Terminology:
     - run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` (≈0.1 s; it gates `status commit`, never `ceremony`/`status-writing`);
     - manually grep your additions for `feature` (must be "Mission") and bare `primary` (must name the sense). The guard does not check the Mission-vs-feature half, so review enforces it.
  3. Run the docs structure tests that cover these files, each by name:
     ```bash
     uv run --frozen pytest tests/docs/test_artifact_placement_seam_page.py tests/docs/test_adr_content_invariance.py \
       tests/docs/test_architecture_docs_consistency.py tests/docs/test_docs_freshness_invariant.py tests/docs/test_check_docs_freshness.py -q
     ```
  4. Write the FR-017 anchor list into the activity log for the PR body:
     - ADR 2026-06-19-1 § "Amendment (2026-10-01 …)" with its subsections;
     - ADR 2026-09-24-2 § Consequences bullet and the Context note;
     - the seam page `write_dir` subsection, the citation fixes and the partition-move note;
     - plus a pointer to the code-comment half (WP04: `resolution.py` docstrings, `_read_path_resolver.py` `CoordState.EMPTY`; WP12: `artifacts.py` comments).
- **Files**: the three docs files.
- **Validation**: all commands above green; counts recorded.
- **Edge cases**: if a freshness tool expects a specific `updated` format, match the existing quoting (`'2026-09-30'` style).

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **C5 (analyze)**: write a short, dedicated **4.x ADR**, `docs/adr/4.x/2026-10-01-2-decision-ledger-primary-partition.md`, for the decision-ledger partition reversal (the #3928 intent reversed: the ledger is PRIMARY, events stay COORD, the index merge driver, the doctor repair, the teardown refusal).
  - Register it with `python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/<adr>.md`, which updates `docs/adr/4.x/index.md` (now owned).
  - If 2026-10-01-2 is taken when you write it, use the next free N and ask the orchestrator to update owned_files.
  - ADR 2026-06-19-1's amendment links to this ADR instead of hosting the reversal.
- **ADR 2026-06-19-1** has `status: Superseded`. Its amendment must state that it binds despite that status, or point to the superseding record; keep the status MADR-valid.
- `docs/architecture/artifact-placement-seam.md` has `updated: '2026-09-30'` (L5); bump it.
- **C3 reference docs (consolidated here to avoid shared-page lane conflicts)**: this WP now owns `docs/api/cli-commands.md`, `docs/api/agent-subcommands.md` and `docs/api/finalize-tasks-internals.md`. Apply the reference deltas the code WPs recorded in their activity logs:
  - spec-commit `success=false` and the non-zero exit (WP13);
  - accept committing the decision ledger (WP16);
  - consolidate materializing an UNMATERIALIZED coordination surface, and `materialize` creating and seeding coordination worktrees (WP18);
  - finalize's automatic planning-pin refresh and the `planning_commit_refresh` JSON field (WP15);
  - the decision-index merge-driver migration (WP11);
  - coordination-routed create materializing the coordination worktree (WP06).
- CHANGELOG `[Unreleased]` entries are a **closeout item** (tasks.md), not this WP's.
- Red evidence: exempt (documentation WP; FR-017 is review-only, anchored on the cited ADR sections).
- **Round 4 (C3)**: add WP17's deltas to the reference pages.
  - `docs/api/cli-commands.md` ≈L1864: the `doctor decisions` fork report and `--repair` exiting 1 on a fork without dropping entries.
  - `docs/api/agent-subcommands.md` ≈L596: `decision verify` exiting 1 with `DECISION_LOG_FORKED`.
  - The teardown/discard refusal `COORDINATION_LEDGER_UNREPAIRED`.
- **I13**: spec FR-017's anchor list now names this WP's new ADR; ADR 2026-06-19-1's amendment links to it.

## Targeted test surface

```bash
uv run --frozen pytest tests/docs/test_artifact_placement_seam_page.py tests/docs/test_adr_content_invariance.py \
  tests/docs/test_architecture_docs_consistency.py tests/docs/test_docs_freshness_invariant.py tests/docs/test_check_docs_freshness.py -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

`make test-fast` is optional for a docs-only change; run it if any docs test imports product modules.

**Never run the bare `tests/architectural/`, any e2e/integration directory, performance/stress suites or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).** Record commands and counts in the activity log for the PR's *Tests run* section. Classify any red with the CLAUDE.md baseline-red gotcha before acting.

## Quality gates

- No code changes, so C901, mypy and coverage do not apply. Markdown must keep valid frontmatter and Mermaid, if used.
- Every cited `path:line` is verified against the final code; citing symbol names is preferred over bare line numbers where the page's convention allows.
- Terminology canon: Mission; the sense of "primary" named; the sense of "routing" named.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5023

## Definition of Done

- T115-T118 complete. The three docs state the single-home rule, `write_dir`, the write-side refusal to substitute the repository root checkout, the retained read fallback, and the ledger reclassification.
- All stale citations re-derived; docs tests and the terminology guard green.
- The FR-017 anchor list is recorded for the PR.
- No file outside the three owned docs touched.

## Risks & Mitigations

- **Citation drift again**: cite symbols alongside line numbers so the next drift is detectable.
- **Breaking the seam-page structure test**: keep the required headings and the composition-roots tokens, and add only a `###` subsection.
- **Overwriting ADR history**: amendments are additive; never edit the earlier amendment's decision text.

## Review Guidance

- The reviewer (opus, distinct from the implementer) checks FR-017 by its anchors: each spec-named element (single-home rule, accessor, write-side refusal, retained read fallback, ledger reclassification) is present and matches the merged code.
- This is a review-only requirement, so the red→green check is the docs tests passing on the final commit, plus a spot-check of 5 cited `path:line` pairs against the code.
- Confirm there is no new ADR file, no `## Decision Outcome` heading on the seam page, and terminology conformance.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

- 2026-10-02T19:10:48Z – curator-carla – Implemented T115-T118 in commit 7c5b337cc0. Tests (named files, repo root, .venv): 262 passed. Wider tests/docs run: 1726 passed, 2 skipped, 1 failed (tests/docs/test_docs_query_cli.py::test_human_table_renders_with_no_rich_markup_leak, pre-existing: fails identically with the changes stashed). FR-017 anchor list (checkable evidence, review-only):
  - docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md: heading "## Amendment (2026-10-01 — mission `coord-artifact-single-home-01M3V4BE`)" above the 2026-06-21 amendment; subsections "Status of this amendment", "Amended decision: writes never substitute the repository root checkout", "Per-state write behaviour" (table), "Read side (unchanged, C-002)", "Create", "Other writers", "Enforcement" (honest bound), "Decision ledger".
  - docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md: Consequences bullet "The write side is governed separately (amended 2026-10-01)"; Context note on DECISION_LEDGER reclassification.
  - docs/adr/4.x/2026-10-01-2-decision-ledger-primary-partition.md (new, registered in docs/adr/4.x/index.md and docs/development/page-inventory.yaml).
  - docs/architecture/artifact-placement-seam.md: "### The write location (write_dir)"; "### Worked example: `DECISION_LEDGER` moved COORD to PRIMARY (2026-10-01)" with the "Coordination residue note"; Honest bounds "The write-side rederivation gate has a blind spot, and its cap is zero" and the re-measured 14 + 9 = 23 bypass table; "Current state (2026-10-02)" under #3055; all path:line citations re-derived on lane-q 1404842433; updated: '2026-10-02'.
  - docs/api/cli-commands.md "## Coordination-routed Missions: where writes land" (spec-commit, accept, consolidate vs --dry-run asymmetry, materialize, create, doctor decisions fork report, fresh clone, merge driver); docs/api/agent-subcommands.md "## Coordination-routed Missions: where agent writes land"; docs/api/finalize-tasks-internals.md "## 4. Automatic planning-pin refresh and `planning_commit_refresh`". Both generated pages edited outside BEGIN/END GENERATED markers.
  - Deviations: ADR descriptions shortened to the 180-char gate (the "append" instruction could not fit); page-inventory.yaml changed by freshen_adr_inventory (outside owned_files).
