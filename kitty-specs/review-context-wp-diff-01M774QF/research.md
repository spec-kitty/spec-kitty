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
