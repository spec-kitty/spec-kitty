# Implementation Plan: Review context carries the WP diff and cited requirement text

**Branch**: `kitty/mission-review-context-wp-diff-01M774QF` (lands on `feat/7578-review-context`) | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/review-context-wp-diff-01M774QF/spec.md`

Planning questions were answered by the six operator rulings, recorded as Decision Moments in `decisions/`, and by the grounding in `research/`. The Engineering Alignment below is built from them.

## Summary

A reviewer gets each work package's own **review range** on every topology: from the window open (the shared FR-021 window-opener rule) to the newest submission for review (the `for_review` lane-head stamp). The prompt shows the range's provenance, the implementation commits, a per-file change summary scoped to the work package's owned files with out-of-map paths flagged, and the exact `git log` / `git diff` commands over that range. It never inlines the diff. The prompt also carries the declared text of every cited requirement.

Commit-to-target `single_branch` Missions start recording the window points, which today read as `not_applicable`, so the range is recorded on every topology. The pure window-opener rule moves, behaviour-preserving, from `consolidation/` into `status/`, so `src/runtime` can use it. Both review entry points render from one function.

## Engineering Alignment (from rulings Q1 to Q6)

| Topic | Decision |
|---|---|
| Diff delivery | Commands, commit list and stat. No patch text, no diff file (Q1, C-001). |
| Range tip | The newest `for_review` `lane_head`. A note gives the commit count when the live tip has moved past it (Q2). |
| Commit-to-target | A writer stamp (the write checkout's target head) on every transition. The consolidation-verdict change is accepted and must be characterized and recorded (Q3, C-008). |
| Pathspec | Owned files on every topology, plus an out-of-map warning line (Q4). |
| Window rule home | `status/wp_window.py`, re-exported from `consolidation/wp_attribution.py` (Q5, C-005). |
| Folds | None (Q6). |

**Invariant.** For a work package with implementation commits, the range is never empty and never open above. Each end is either recorded or derived with a named reason. When neither is possible the prompt prints an `unavailable` notice and the review still proceeds (FR-013, NFR-004).

## Technical Context

**Language/Version**: Python 3.11+ (`mypy --strict`, `ruff`, complexity ≤ 15)
**Primary Dependencies**: typer and rich (CLI); `spec_kitty_events` (status reducer, unchanged); git through `kernel.git` (`listing.numstat_entries`, `listing.commit_paths`, `runner.run_git`)
**Storage**: Git refs and commits; `status.events.jsonl` (append-only, read through `status/read_surface.resolve_status_read`); the WP frontmatter `requirement_refs` and `owned_files`; Mission `spec.md` through the placement seam
**Testing**: pytest with real-git fixtures (`git_repo` marker). ATDD acceptance tests drive the production review entry points (`spec-kitty agent action review` via `workflow.review` and `prompt_builder.build_prompt`) on `single_branch` (commit-to-target and minted), `lanes` and `lanes_with_coord` fixtures. Unit tests cover the range resolver, requirement-text resolver and renderer. Characterization tests pin consolidation verdicts before the writer stamp lands.
**Target Platform**: Linux, macOS, Windows 10+ (CLI)
**Project Type**: single (existing CLI package)
**Performance Goals**: at most 1.0 s added to review-prompt generation (p95, ≤ 200 commits and ≤ 500 files in range; NFR-002); a review-context block of at most 4 KB at 40 files and 20 commits (NFR-001)
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
├── decisions/                            # Q1–Q6 Decision Moments
├── tracer-tooling-friction.md, tracer-approach.md, tracer-design-decisions.md
└── tasks.md, tasks/                      # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/status/wp_window.py             # + window_opener_events, window_open_of, WindowOpen/WindowGap/WindowGapReason (moved, IC-01)
src/specify_cli/consolidation/wp_attribution.py # re-exports the moved names (IC-01)
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

### IC-01: A shared home for the window-opener rule (tidy-first)

- **Purpose**: let `src/runtime` and `specify_cli/review` use the FR-021 window-opener rule without importing `consolidation`, keeping one definition.
- **Relevant requirements**: FR-003, C-005, C-007
- **Affected surfaces**:
  - Move the pure `window_opener_events`, `window_open_of`, `_cycle_start_index`, `WindowOpen`, `WindowGap` and `WindowGapReason` from `consolidation/wp_attribution.py` to `status/wp_window.py`.
  - `wp_attribution` re-exports them, so every consolidation import site is unchanged.
  - Export from `specify_cli.status` only if a caller needs it (`test_no_dead_symbols`).
- **Sequencing/depends-on**: none (first).
- **Risks**:
  - `wp_window.py` must stay git-free (predicates are injected).
  - Check `test_no_dead_symbols`, `test_layer_rules` and the consolidation suite.
  - Behaviour-preserving: no test changes except new import paths, if any.

### IC-02: Commit-to-target `single_branch` records window points (writer stamp)

- **Purpose**: make the window recorded on every topology.
- **Relevant requirements**: FR-002, C-008, C-009, SC-004
- **Affected surfaces**:
  - `status/lane_head.py::_read_lane_head`: when the stored topology is `single_branch` and the write branch equals the target (commit-to-target, both read from `meta.json` via `single_branch_landing`), read the target branch head as the WP's reading. It is labelled like the minted case and keeps C-1 best-effort semantics.
  - Planning lanes of lane topologies stay `not_applicable` (C-009).
  - The ADR `2026-11-08-2` amendment.
- **Sequencing/depends-on**: none for the code. The characterization tests (IC-06a) must land **before** this concern changes behaviour.
- **Risks (the operator-accepted verdict change)**:
  - Consolidation readers keep commit-to-target unbounded: `_write_branch_scope` returns None (`reconciliation_bound.py:340`), and `approved_bound` excludes it (348-429).
  - **But** `_mixed_lanes` (`reconciliation_canceled.py:55`) does not skip planning lanes. A commit-to-target Mission with an approved and a canceled WP on its planning lane runs canceled-content attribution, which reads per-transition `lane_head`. Today those stamps are missing, so it reads as unattributable. After the change it attributes.
  - Pin the current verdict for (a) approved-only, (b) approved + canceled and (c) the move-task / `agent status emit` warnings, then record the after-state in the ADR amendment and in `tracer-design-decisions.md`.
  - If the after-state emits a refusal code the before-state did not, escalate. The operator accepted a verdict change, but a new code on a previously passing Mission is reported, not assumed.

### IC-03: The review-range resolver

- **Purpose**: one function that yields a WP's review range on every topology, with provenance.
- **Relevant requirements**: FR-001, FR-004, FR-005, FR-006, FR-007, FR-009, FR-013, NFR-002, NFR-004, NFR-005
- **Affected surfaces**: NEW `specify_cli/review/wp_range.py`.
  - **Signature.** `resolve_wp_review_range(repo_root, mission_slug, wp_id, *, owned_files, owned=None) -> WpReviewRange`.
  - **Events.** Read through `resolve_status_read` + `read_status_events`, and opt into `DOOR_ONLY_MODULES`.
  - **Base resolution order.**
    1. Recorded: `window_open_of(...)` over the events, with predicates bound to the tip through `kernel.git`.
    2. Derived: the `refs/spec-kitty/wp-base/<slug>/<WP>` claim-base ref.
    3. Derived: the commit that introduced the window-opener event (the `claim_commit_for_wp` technique, generalised to an event id).
    4. Unavailable, with a reason.
  - **Tip resolution order.**
    1. Recorded: the newest non-migration `for_review` event's `policy_metadata.lane_head`.
    2. Derived: the commit that introduced that event.
    3. Unavailable.
  - **Moved-past count.** `rev-list --count tip..<write/lane branch>`.
  - **Commits.** `git log --format=%H%x00%s base..tip` (no listing flag), minus bookkeeping-only commits. A commit counts as bookkeeping when every path in `kernel.git.listing.commit_paths` is under `for_review_gate.status_only_excluded_prefixes` or `.kittify/`.
  - **Stat.** `numstat_entries(base, tip, pathspecs=owned)`, plus `changed_paths(base, tip)` minus owned for the out-of-map list.
- **Sequencing/depends-on**: IC-01 (window rule home). It reads IC-02's stamps when present, but does not depend on IC-02 landing first.
- **Risks**:
  - `open_sha` may not resolve after a rebase (`not_on_lane`): fall back.
  - Coord topologies: the status log lives on the coordination branch, so derived event-commit lookup searches that branch, via the door's resolved surface.
  - Cap list lengths (NFR-001).
  - Keep each function ≤ 15 complexity.

### IC-04: Requirement-text resolver

- **Purpose**: turn the cited IDs into their declared text.
- **Relevant requirements**: FR-010, FR-011, NFR-003
- **Affected surfaces**: NEW `requirement_mapping/text.py`.
  - **Signature.** `resolve_requirement_texts(spec_text, refs, *, mission_type) -> tuple[CitedRequirement, ...]`.
  - Built on `_declaration_occurrences`. A table row becomes `ID — Title: statement` from the cells. A heading, list item or bold lead becomes that block's first paragraph.
  - Grammar comes from `grammar.parse`/`tokenize_refs`. A cross-Mission `slug#ID` is labelled. An undeclared ID is marked. A duplicate declaration is reported as ambiguous.
  - The WP's `requirement_refs` come from `WPMetadata` (frontmatter, the canonical source).
  - `spec.md` is read through the placement seam.
- **Sequencing/depends-on**: none (it can run in parallel with IC-01 to IC-03).
- **Risks**:
  - #3481: two "declares" definitions disagree, so use only `_declaration_occurrences`.
  - Truncate at 600 characters.

### IC-05: One renderer for both review entry points

- **Purpose**: both paths show the same block.
- **Relevant requirements**: FR-008, FR-012, NFR-001, NFR-005
- **Affected surfaces**:
  - NEW `review/context_block.py::render_review_context(range, cited) -> list[str]`, per `contracts/review-context-block.md`.
  - `prompt_builder._review_command_lines` calls it. The old `_lane_review_base` and the claim-commit arm go away for the range lines. `OWNED_REVIEW_BASE_UNAVAILABLE` stays unchanged (C-002); the anti-pattern checklist stays.
  - `workflow_executor._review_context_line`, `review_context_for_repo_root_workspace` and `review_context_for_worktree_branch` take the base and tip from the range. Their dict keys stay for `ReviewPromptMetadata`, with `base_ref` = range base.
  - `workflow.py` changes stay inside the review helpers.
- **Sequencing/depends-on**: IC-03, IC-04.
- **Risks**:
  - Hot files (25 and 48 commits in 90 days): keep the edits minimal.
  - `workflow.py` and `workflow_executor.py` are on the format ratchet, so check with `--force-exclude`.
  - `test_execution_context_parity.py` must stay green.
  - Existing tests that pin the old `<base>..HEAD` text: re-pin them where stale (DIRECTIVE_041), never delete a valid one.

### IC-06: Acceptance and characterization tests (ATDD-first)

- **Purpose**: the executable contract.
- **Relevant requirements**: C-010, SC-001 to SC-004, User Stories 1 to 5
- **Affected surfaces**:
  - (a) Characterization of the consolidation and accept verdicts for commit-to-target `single_branch`, before IC-02.
  - (b) Red-first acceptance tests that drive both production review entry points on four fixtures: `single_branch` commit-to-target, `single_branch` minted, `lanes`, and `lanes_with_coord`. They assert that the range holds only the WP's commits, that commands are non-empty, that out-of-map paths are flagged, that requirement text is present, and that both paths are identical.
  - (c) Gap fixtures: pre-window, `lane_branch_missing` opener, unresolvable.
  - Location: `tests/review/` and `tests/next/`, plus `tests/integration/review/`. Do **not** edit `tests/integration/test_single_branch_write_checkout_e2e.py`, which overlaps PR #7562.
- **Sequencing/depends-on**: (a) before IC-02; (b) committed red before IC-03 to IC-05 land.
- **Risks**:
  - Fixture cost: build each Mission once per module with real git.
  - Use `monkeypatch.delenv` for the harness's `SPEC_KITTY_*` variables.

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
