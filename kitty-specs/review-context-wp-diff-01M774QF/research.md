---
type: explanation
updated: 2026-11-12
---

# Research: decisions for #7578

Full grounding and citations: [research/code-grounding.md](research/code-grounding.md). Issue triage: [research/foldable-issues.md](research/foldable-issues.md). Operator rulings are in `decisions/` (Q1–Q6).

| # | Decision | Rationale | Alternatives considered |
|---|---|---|---|
| R1 | The range runs from the window open to the newest `for_review` `lane_head` | It is the only anchor pair defined on every topology. It is bounded above, so later WPs cannot leak in, and it matches consolidation's window (FR-021). Rulings Q2 and Q3. | `<lane base>..HEAD`: empty on single_branch. `claim..HEAD`: unbounded above, and after a rework it disagrees with FR-021. The live tip: it moves. |
| R2 | Commands, commits and stat; no patch text and no diff file | The benchmark failure was an empty or unbounded command, not a missing inline diff. Inline patches cost 2–72 KB. Ruling Q1. | Inline with a cap. A diff file beside the prompt (stale on rework, extra state to clean up). |
| R3 | Stamp commit-to-target `single_branch` at the target head | One recorded window authority on every topology (ruling Q3). Consolidation keeps such Missions unbounded (`reconciliation_bound.py:340`, `approved_bound.py:348-429`). | Read-side derivation only. It was rejected by the operator. |
| R4 | Move the FR-021 rule to `status/wp_window.py` | `src/runtime` may not import `consolidation` (`test_layer_rules.py:178-203`). One definition (C-005). Ruling Q5. | A second selector on the review side. It would break the single-authority principle. |
| R5 | Scope to owned files on every topology, with an out-of-map line | Lane-mates and parallel claims otherwise leak into the summary. Ruling Q4. | Scoping on the repo root only (today's behaviour). |
| R6 | Requirement text comes from `_declaration_occurrences` | It is the canonical declaration parser (#3481). The ID grammar is already shared. | A new spec parser: a third definition. |
| R7 | The stat comes from `kernel.git.listing.numstat_entries`, and commit lists from `run_git log --format` | `test_git_path_listing_owner.py` (empty allowlist) bans listing flags outside `kernel.git`. A plain `log --format` is not a listing. | A raw `git diff --stat` subprocess: it is gated. |
| R8 | Characterize consolidation verdicts before the writer stamp | `_mixed_lanes` (`reconciliation_canceled.py:55`) includes planning lanes. A commit-to-target Mission with approved and canceled WPs now gets attribution inputs, which is the accepted verdict change. It must be measured, not assumed. | Assume no change. The code contradicts that assumption. |

## Supply chain

No dependency is added, upgraded or removed. DIRECTIVE_051 does not apply.

## Adversarial evidence

The pre-spec squad (code grounding, evidence, issue discovery, plus a fresh-context second opinion) has its verdicts folded into `research/code-grounding.md`. The post-plan squad's findings and their dispositions are appended below once it reports.

## Post-plan squad (2026-11-12): architect-alphonso + researcher-robbie, both PROCEED-WITH-FOLDS

Disposition of every finding (A = architect, R = researcher):

| # | Finding | Severity | Disposition |
|---|---|---|---|
| P1 | A third render site, `_review_print_finalize_summary` (A) | MAJOR | **Folded**: IC-05 lists three render sites, and the parity test pins all three. |
| P2 | Two pathspec builders, and the out-of-map matcher disagrees with the evidence axis (A, R) | MAJOR | **Folded**: `WpReviewRange.owned_pathspecs` is the one owner. `matches_owned` moves to `ownership/` (IC-01b). Both builders are retired (IC-05). |
| P3 | Event-commit fallback is unusable on lane topologies (A, R) | MAJOR | **Folded**: event commits only on `single_branch`. Lanes fall back to the opener's rc5 `lane_head`. Every derived anchor is ancestry-guarded (IC-03). |
| P4 | A second `-S` authority (A) | MAJOR | **Folded**: generalise `claim_commit_for_wp` in `mission_runtime` (IC-03). |
| P5 | Foreign commits on a commit-to-target range, and the commit list disagreeing with the command (A, R) | MAJOR | **Folded**: the list is the command's result (scoped). Out-of-map-only commits are counted. Foreign commits that touch owned paths are a named residual (spec edge case). |
| P6 | Moved-past fires on every single_branch review (R) | MAJOR | **Folded**: count non-bookkeeping commits only (FR-009 amended). |
| P7 | NFR-002: one subprocess per commit (A, R) | MAJOR | **Folded**: a constant number of git calls. NFR-002 is restated as a call-count bound with a call-count test. |
| P8 | Caps exceed 4 KB (R) | MAJOR | **Folded**: truncation by byte budget (NFR-001, contract). |
| P9 | `wp_window.py` purity docstring (A) | MINOR | **Folded**: a sibling `status/wp_window_selector.py`. |
| P10 | Incomplete IC-01 move list (A, R) | MINOR | **Folded**: full list, plus `is_migration_event`. |
| P11 | Missed readers `_recorded_lane_heads` and `_has_review_approval_stamp` (A, R) | MINOR | **Folded**: added to the IC-02 risk list and the IC-06a characterization. |
| P12 | The Q3 ruling text names `check_write_branch_windows`, which commit-to-target never reaches; C-008 says "expected: none" (A, R) | MINOR | **Folded**: C-008 restated. The ADR amendment corrects the mechanism. Reported to the operator. The substance of the ruling stands. |
| P13 | The gate's claim-base anchor and the review's window rule diverge after a rewind (A) | MINOR | **Folded**: spec edge case and provenance line. The gate is not changed (C-004). |
| P14 | Tip must come after the window opener (R) | MINOR | **Folded** (IC-03). |
| P15 | `glob=True` for kernel listing calls (R) | MINOR | **Folded** (IC-03). |
| P16 | IC-04: ambiguity semantics, SC trailer, escaped pipes (R) | MINOR | **Folded** (IC-04). |
| P17 | `.kittify/` already in the prefixes; one term for "write checkout head" (A) | NIT | **Folded**. |
| P18 | "First claim often records lane_branch_missing" is not supported for production verbs (R) | NIT | **Accepted** as a correction. It happens only for hand-made move-task claims, and the gap fixture still covers that shape. |
| P19 | SC-005 is a benchmark (R) | NIT | **Kept** as `[build]`, already marked "tracked, not gating". |
