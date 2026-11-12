# Implementation Plan: Review context carries the WP diff and cited requirement text

**Branch**: `kitty/mission-review-context-wp-diff-01M774QF` (lands on `feat/7578-review-context`) | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/review-context-wp-diff-01M774QF/spec.md`

Planning questions were answered by the operator rulings Q1 to Q6, extended later by Q7 (narrowed owned refusal) and Q8 (stamps kept, consolidation guarded), recorded as Decision Moments in `decisions/`, and by the grounding in `research/`. The Engineering Alignment below is built from them.

## Summary

A reviewer gets each work package's own **review range** on every topology: from the window open (the shared FR-021 window-opener rule) to the newest submission for review (the `for_review` lane-head stamp). The prompt shows the range's provenance, the implementation commits, a per-file change summary scoped to the work package's owned files with out-of-map paths flagged, and the exact `git log` / `git diff` commands over that range. It never inlines the diff. The prompt also carries the declared text of every cited requirement.

Commit-to-target `single_branch` Missions start recording the window points, which today read as `not_applicable`, so the range is recorded on every topology. The pure window-opener rule moves, behaviour-preserving, from `consolidation/` into `status/`, so `src/runtime` can use it. Both review entry points render from one function.

## Engineering Alignment (from rulings Q1 to Q8)

| Topic | Decision |
|---|---|
| Diff delivery | Commands, commit list and stat. No patch text, no diff file (Q1, C-001). |
| Range tip | The newest `for_review` `lane_head`. A note gives the commit count when the live tip has moved past it (Q2). |
| Commit-to-target | A writer stamp (the write checkout's target head) on every transition. The consolidation-verdict change is accepted and must be characterized and recorded (Q3, C-008). |
| Pathspec | Owned files on every topology, plus an out-of-map warning line (Q4). |
| Window rule home | `status/wp_window_selector.py` (a sibling of the `status/wp_window.py` codec), re-exported from `consolidation/wp_attribution.py` (Q5, C-005). |
| Folds | None (Q6). |

**Invariant.** For a work package with implementation commits, the range is never empty and never open above. Each end is either recorded or derived with a named reason. When neither is possible the prompt prints an `unavailable` notice and the review still proceeds (FR-013, NFR-004).

## Technical Context

**Language/Version**: Python 3.11+ (`mypy --strict`, `ruff`, complexity ≤ 15)
**Primary Dependencies**: typer and rich (CLI); `spec_kitty_events` (status reducer, unchanged); git through `kernel.git` (`listing.numstat_entries`, `listing.commit_paths`, `runner.run_git`)
**Storage**: Git refs and commits; `status.events.jsonl` (append-only, read through `status/read_surface.resolve_status_read`); the WP frontmatter `requirement_refs` and `owned_files`; Mission `spec.md` through the placement seam
**Testing**: pytest with real-git fixtures (`git_repo` marker). ATDD acceptance tests drive the production review entry points (`spec-kitty agent action review` via `workflow.review` and `prompt_builder.build_prompt`) on `single_branch` (commit-to-target and minted), `lanes` and `lanes_with_coord` fixtures. Unit tests cover the range resolver, requirement-text resolver and renderer. Characterization tests pin consolidation verdicts before the writer stamp lands.
**Target Platform**: Linux, macOS, Windows 10+ (CLI)
**Project Type**: single (existing CLI package)
**Performance Goals**: a constant number of git invocations per range, at most 10 recorded and 12 derived (NFR-002); a review-context block of at most 4,096 bytes for any range size (NFR-001)
**Constraints**: no new gate, refusal code or exit code (C-002); no `packs/built-in` edit (C-003); the pre-review and for_review gates untouched (C-004); one window rule (C-005); the status read door (C-006); the runtime outbound ledger not widened and no path listings outside `kernel.git` (C-007)
**Scale/Scope**: about 6 source modules touched and 3 new; Missions with up to about 30 WPs

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | PASS. One window rule (moved, not copied), one range function, one renderer for both builders, and one requirement-declaration parser (#3481: built on `_declaration_occurrences`, no third parser). |
| Architectural alignment / layering | PASS. The range function lives in `specify_cli/review/` and the requirement text in `specify_cli/requirement_mapping/`; both are already on `_RUNTIME_ALLOWED_SPECIFY_CLI`, so the ledger count stays 22. No `consolidation` import from `src/runtime`. |
| ATDD-first (C-011) | PASS. IC-06's acceptance tests are committed red first. |
| Standing Order #2 (tidy-first) | PASS. IC-01 is a behaviour-preserving move that precedes the behaviour change. |
| Standing Order #3 (tracers) | PASS. The three tracer files are seeded with this plan. |
| Standing Order #5 (gate discipline) | PASS. No new gate. The new module opts into `DOOR_ONLY_MODULES`, a grow-only positive list, not an allowlist. |
| Standing Order #1 (adversarial squad) | Post-plan and post-tasks squads are run (advisory). |
| ADR governance | Amendment to ADR `2026-11-08-2` for the commit-to-target stamp (C-008), in this Mission. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS. Targeted test directories plus named architectural gate files only. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/review-context-wp-diff-01M774QF/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/review-context-block.md     # the prompt block agents read (format contract)
├── research/code-grounding.md, research/foldable-issues.md
├── decisions/                            # Q1–Q8 Decision Moments and DM-01M77PZ5833WWQB5J457GXNWYW
├── tracer-tooling-friction.md, tracer-approach.md, tracer-design-decisions.md
└── tasks.md, tasks/                      # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/status/wp_window_selector.py    # NEW: FR-021 selector moved from wp_attribution (IC-01)
src/specify_cli/ownership/                      # + owned_patterns, matches_owned moved from wp_evidence (IC-01)
src/specify_cli/consolidation/wp_attribution.py, wp_evidence.py  # re-export the moved names (IC-01)
src/mission_runtime/claim_commit.py             # generalised event-commit lookup (IC-03)
src/specify_cli/cli/commands/agent/workflow_cores.py      # retire build_owned_files_review_pathspecs (IC-05)
src/specify_cli/status/lane_head.py             # commit-to-target single_branch reading (IC-02)
src/specify_cli/review/wp_range.py              # NEW: resolve_wp_review_range → WpReviewRange (IC-03)
src/specify_cli/requirement_mapping/text.py     # NEW: resolve_requirement_texts (IC-04)
src/specify_cli/review/context_block.py         # NEW: render_review_context(...) -> list[str] (IC-05)
src/runtime/next/prompt_builder.py              # _review_command_lines → render_review_context (IC-05)
src/specify_cli/cli/commands/agent/workflow_executor.py  # _review_context_line / review contexts → same (IC-05)
src/specify_cli/review/prompt_metadata.py       # base_ref agrees with the range (IC-05)
docs/adr/4.x/2026-11-08-2-…md                   # Amendment (IC-02)
docs/changelog/unreleased/<id>.<section>.md     # fragment
tests/…                                         # see IC-06
```

## Complexity Tracking

No Charter violations.

## Implementation Concern Map

### IC-01: Shared homes for the window-opener rule and owned-file matching (tidy-first)

- **Purpose**: let `src/runtime` and `specify_cli/review` use the FR-021 window-opener rule and the owned-file matcher without importing `consolidation`, keeping one definition of each.
- **Relevant requirements**: FR-003, FR-006, FR-007, C-005, C-007
- **Affected surfaces**:
  - (a) Move the self-contained selector block, `consolidation/wp_attribution.py:715-933`, to a NEW sibling `status/wp_window_selector.py`. `status/wp_window.py` stays the git-free codec, which keeps its "no specify_cli imports" docstring true.
    - The block: `window_opener_events`, `window_open_of`, `OpenerSelection`, `WindowOpen`, `WindowGap`, `WindowGapReason`, and the private helpers `_cycle_start_index`, `_candidates`, `_skip_leading_branch_missing`, `_bind`, `_topological_first`, `_window_value`, `_branch_missing_detail`, `_REWORK_FROM_LANES`, `_ENTERED_IMPLEMENTATION_LANES`, `_PLANNED`.
    - Also `is_migration_event`, which `approved_bound.py:42` and `canceled_attestation.py:46` use.
    - `wp_attribution` re-exports the public names. `GapEntry` stays in consolidation.
  - (b) Move `owned_patterns` and `matches_owned` from `consolidation/wp_evidence.py:133-150` into `specify_cli/ownership/`, re-exported from `wp_evidence`. move-task and the evidence axis keep their call sites.
- **Sequencing/depends-on**: none (first).
- **Risks**:
  - Behaviour-preserving. `tests/consolidation/test_window_opener.py` imports `OpenerSelection`, so keep it importable from the old path.
  - Check `test_no_dead_symbols` and `test_layer_rules`.

### IC-02: Commit-to-target `single_branch` records window points (writer stamp)

- **Purpose**: make the window recorded on every topology.
- **Relevant requirements**: FR-002, C-008, C-009, SC-004
- **Affected surfaces**:
  - `status/lane_head.py::_read_lane_head`: when the stored topology is `single_branch` and the write branch equals the target (commit-to-target, read from `meta.json` through `single_branch_landing`), return the head of the write branch, which is the target. It reuses `_write_branch_head`'s best-effort semantics.
  - Planning lanes of lane topologies stay `not_applicable` (C-009).
  - The ADR `2026-11-08-2` amendment. It also corrects the Q3 ruling's mechanism note: `check_write_branch_windows` is never reached for commit-to-target, because `_bound_write_branch` returns None.
- **Sequencing/depends-on**: the characterization tests (IC-06a) land first.
- **Risks (the operator-accepted verdict change, measured, not assumed)**: the stamps newly reach
  - (1) `reconciliation_canceled._mixed_lanes` and the canceled attribution with `lacks_lane_head_stamps`, on a mixed planning lane;
  - (2) `reconciliation_closed_world._recorded_lane_heads`, the `--dependency-ref` refusal;
  - (3) `approved_attestation._has_review_approval_stamp:103`.

  Verified unchanged: `_bound_write_branch` returns None, and `cutover_eligibility` treats the keys as provenance. **Correction (post-tasks squad):** `tests/integration/test_single_branch_approval_windows.py::test_commit_to_target_unbounded_residual` asserts that a commit-to-target Mission is already refused with `LANE_MOVED_AFTER_APPROVAL`, so some bound reaches these Missions today. WP02's T006 traces and pins that path before the stamp lands. Pin today's verdicts for (1)–(3), plus the approved-only consolidation and accept, then record the after-state in the ADR amendment and in `tracer-design-decisions.md`. Escalate if a previously passing Mission now refuses.

### IC-03: The review-range resolver (the single owner of a WP's review range and pathspecs)

- **Purpose**: one function that yields a WP's review range on every topology, with provenance, and that owns the WP's owned-file pathspecs and its owned/out-of-map split.
- **Relevant requirements**: FR-001, FR-004 to FR-009, FR-013, NFR-001, NFR-002, NFR-004, NFR-005
- **Affected surfaces**: NEW `specify_cli/review/wp_range.py`, and `mission_runtime/claim_commit.py`, which is generalised.
  - **Signature.** `resolve_wp_review_range(repo_root, mission_slug, wp_id, *, owned_files, owned=None) -> WpReviewRange`.
  - **Events.** Read through `resolve_status_read` and `read_status_events`. The module opts into `DOOR_ONLY_MODULES`.
  - **Tip.** The newest non-migration `for_review` event **after the window opener**:
    1. its `policy_metadata.lane_head`;
    2. else, on `single_branch` only, the commit that introduced that event;
    3. else unavailable.
  - **Base.**
    1. Recorded: `window_open_of(...)`, with `on_lane` and `is_ancestor` bound to the tip through `kernel.git`.
    2. Else the opener event's own `lane_head` stamp, if it is an ancestor of the tip (lane Missions created before #7403, stamped since rc5).
    3. Else, on `single_branch` only: the `wp-base` claim-base ref, then the commit that introduced the opener event.
    4. Else unavailable.

    Every derived anchor must be an ancestor of the tip, or it is skipped. Event commits are never used on lane topologies: they sit on the status branch, not the code branch.
  - **Generalised event lookup.** Generalise `claim_commit_for_wp` in place to `commit_introducing_status_event(status_dir_or_ref, wp_id, event_id, *, rev)`. It supports a path surface and a ref surface, and keeps its ambiguity handling and race guard. `claim_commit_for_wp` becomes a thin wrapper or is folded; no second `-S` authority.
  - **Pathspecs.** `owned_pathspecs` are glob pathspecs from the owned files. Every `kernel.git` call passes `glob=True`, since the default is literal pathspecs. The two existing builders, `prompt_builder._review_pathspecs:325` and `workflow_cores.build_owned_files_review_pathspecs:540`, are retired in IC-05 in favour of this field.
  - **Commit list.** One call: `git log --format=%H%x00%s base..tip -- <owned globs>`, which is the printed command's own result. A second single call, unscoped with `:(exclude)` of the bookkeeping prefixes (`for_review_gate.status_only_excluded_prefixes`, which already covers `.kittify/`), counts the commits that touch only out-of-map paths. Merge handling is documented and tested.
  - **Stat and out-of-map.**
    - Stat: one `numstat_entries(base, tip, pathspecs=owned, glob=True)`.
    - Out-of-map: one `changed_paths(base, tip)`, classified with `ownership.matches_owned`, the same matcher the evidence axis uses, so review and `IMPLEMENTATION_MISSING` agree.
  - **Moved-past.** Non-bookkeeping commits only (excluded with the same pathspec), so the WP's own status commits never trigger the note.
  - **Budget.** A constant number of git calls (NFR-002), and byte-budget truncation of the block (NFR-001).
- **Sequencing/depends-on**: IC-01. It reads IC-02's stamps when present.
- **Risks**:
  - Foreign commits on a shared commit-to-target range that touch owned paths: a named residual.
  - Keep each function's complexity ≤ 15.

### IC-04: Requirement-text resolver

- **Purpose**: turn the cited IDs into their declared text.
- **Relevant requirements**: FR-010, FR-011, NFR-003
- **Affected surfaces**: NEW `requirement_mapping/text.py::resolve_requirement_texts(spec_text, refs, *, mission_type)`.
  - Built on `_declaration_occurrences`. The probe on this Mission's spec found all 34 IDs with usable line numbers.
  - A table row becomes `ID — Title: statement`, with escaped `\|` handled. A heading, list item or bold lead becomes its block's first paragraph, with the SC trailer (`— [build] · …`) stripped.
  - AMBIGUOUS uses only `duplicate_declared_ids` semantics, so a bullet that merely restates an ID is not ambiguous.
  - A cross-Mission `slug#ID` is labelled, and an undeclared ID is marked.
  - The WP's `requirement_refs` come from the frontmatter. `spec.md` is read through the placement seam.
- **Sequencing/depends-on**: none (it can run in parallel).
- **Risks**: #3481. Use only the canonical declaration parser.

### IC-05: One renderer for every review render site

- **Purpose**: every review surface shows the same range.
- **Relevant requirements**: FR-008, FR-012, NFR-001, NFR-005
- **Affected surfaces**:
  - NEW `review/context_block.py::render_review_context(range, cited) -> list[str]`, per `contracts/review-context-block.md`.
  - **Three render sites** move onto it:
    1. `prompt_builder._review_command_lines`. The `_lane_review_base`, claim-commit arm and `_review_pathspecs` go.
    2. `workflow_executor._review_context_line`, `review_context_for_repo_root_workspace` and `review_context_for_worktree_branch`, which take base and tip from the range. Their dict keys stay, and `ReviewPromptMetadata.base_ref` is the range base.
    3. **`workflow_executor._review_print_finalize_summary:2498-2507`**, whose stdout line prints the same range.
  - `workflow_cores.build_owned_files_review_pathspecs` is retired.
  - `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and message; per ruling Q7 its condition narrows to: the scoped review range is unavailable, or the work package declares no `owned_files`.
- **Sequencing/depends-on**: IC-03, IC-04.
- **Risks**:
  - Hot files. Check the format ratchet with `--force-exclude`.
  - Keep `test_execution_context_parity.py` green.
  - Re-pin stale old-range text tests (DIRECTIVE_041).

### IC-06: Acceptance and characterization tests (ATDD-first)

- **Purpose**: the executable contract.
- **Relevant requirements**: C-010, SC-001 to SC-004, User Stories 1 to 5
- **Affected surfaces**:
  - **(a) Characterization, before IC-02.** For commit-to-target `single_branch`, pin the consolidation and accept verdicts of approved-only, of mixed approved+canceled on the planning lane, of `--dependency-ref`, and of `--attest-approved-reviewed`. Reuse `tests/integration/single_branch_window_support.py`.
  - **(b) Red-first acceptance**, driving all three render sites on four fixtures:
    - `single_branch` commit-to-target and minted, through `single_branch_window_support.build_template(commit_to_target=...)` and `claim`/`implement`/`submit`;
    - `lanes` and `lanes_with_coord`, through `tests/consolidation/characterization_support.build_two_wp_lane`, adapted with a `topology` meta key.

    Assert:
    - the range holds only this WP's commits (a lane-mate is excluded), and the commands are non-empty;
    - out-of-map paths are flagged;
    - requirement text is present;
    - every render site is identical;
    - a plain submission shows no moved-past note.
  - **(c) Gap fixtures**: pre-window lanes (opener `lane_head` only), a `lane_branch_missing` opener, unresolvable.
  - **(d) Git-call-count test** (NFR-002), following `tests/consolidation/test_lane_window_query_count.py`.
  - Do **not** edit `tests/integration/test_single_branch_write_checkout_e2e.py` (PR #7562 overlap).
- **Sequencing/depends-on**: (a) before IC-02; (b) committed red before IC-03 to IC-05 land.
- **Risks**:
  - Fixture cost: build templates once and copy them per cell.
  - Use `monkeypatch.delenv` for the harness `SPEC_KITTY_*` variables.

### IC-07: Documentation and close-out

- **Purpose**: record the decision and the change.
- **Relevant requirements**: C-003, C-008
- **Affected surfaces**:
  - The ADR amendment (with IC-02).
  - A changelog fragment in `docs/changelog/unreleased/`.
  - The CLAUDE.md "Work-package windows" paragraph: one sentence on commit-to-target stamping and on the review range.
  - An `spec-kitty-open-packs` follow-up issue for the stale review-template wording.
- **Sequencing/depends-on**: after IC-02 to IC-05.
- **Risks**: none.

## Test surface (declared, per charter Testing Requirements)

- **Baseline**: `make test-fast`.
- **Owning directories**: `tests/review/`, `tests/next/`, `tests/runtime/`, `tests/status/`, `tests/requirement_mapping/` (or the mirror `grep -rl requirement_mapping tests/`), `tests/consolidation/` (IC-01 and IC-02 touch consolidation inputs), `tests/agent/`, `tests/integration/review/`, and `tests/specify_cli/cli/commands/agent/test_workflow_cores.py` (out-of-matrix, run explicitly).
- **Architectural gate files**: `test_layer_rules.py`, `test_status_read_single_door.py`, `test_git_path_listing_owner.py`, `test_no_dead_symbols.py`, `test_execution_context_parity.py`, `test_dossier_sha_provenance.py`, `test_cold_import_status_boundary.py`, `test_no_legacy_terminology.py`.
