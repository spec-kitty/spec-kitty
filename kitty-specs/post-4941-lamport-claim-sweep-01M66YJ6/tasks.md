# Tasks: post-#4941 "Lamport-ordered status path" claim sweep

**Mission**: post-4941-lamport-claim-sweep-01M66YJ6
**Branch**: `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md)

Correct the surviving affirmative claims that the CLI status path is Lamport-ordered
(#6604), record the accepted current ordering in ADR `2026-10-01-2` by amendment, close
gap G-3, and add a guard test that fails if the retired wording returns. Red-first: the
guard test lands first and must be shown failing against the unmodified pages before the
wording is corrected.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Write `tests/architectural/test_status_path_ordering_claims.py`: covered corpus, retired phrases, affirmative regex with negation allowance, ADR-shape assertions | WP01 | — |
| T002 | Non-vacuity: detector classifies a synthetic stale line (1 hit) and a synthetic negated line (0 hits); an empty/missing covered path fails | WP01 | — |
| T003 | Prove it red against the current tree and record the failure output in the WP history | WP01 | — |
| T004 | C4 context page: prose and mermaid node label name the wall-clock status reducer | WP02 | — |
| T005 | C4 container page: prose, alt-text and mermaid node label agree on the wall-clock fold | WP02 | — |
| T006 | API/dashboard domain plan §4 gap 2: one reducer, not two; keep the residual and the #6609 direction | WP02 | — |
| T007 | `AGENTS.md` Status Model Patterns: credit the shipped lift and the corrected docstrings, keep the narrow non-approval residual, cite the amended ADRs | WP02 | — |
| T008 | `consolidation/preflight.py::_latest_actor_for_transition` docstring cites the amended ADR, not the Lamport-primary rule | WP02 | — |
| T009 | Gap table G-3 becomes Closed (#6604) with the corrected files, the guard and the residual | WP02 | — |
| T010 | ADR `2026-10-01-2`: `## Amendment 2026-10-30 (Accepted)` recording wall clock `(at, event_id)`, the lift, and #6609; `updated:` frontmatter | WP03 | — |
| T011 | Verify the ADR's original D-5/D-3/D-7 decision text is byte-identical (history preserved) | WP03 | — |
| T012 | `[Unreleased]` changelog entry, bold impact-first lead with `(#6604)`, before/after, under 1,200 characters | WP03 | — |
| T013 | Re-run the guard test, the docs gates (`docs_index`, `freshen_adr_inventory`, `check_docs_freshness --ci`) and the touched-area tests; all green | WP03 | — |

---

## WP01 — Guard test (red-first)

**Prompt**: [tasks/WP01-claim-guard-test.md](tasks/WP01-claim-guard-test.md)

**Summary**
- **Goal**: a bounded, non-vacuous test that fails when the affirmative "Lamport reducer /
  Lamport reduction / Lamport wrapper" claim about the CLI status path returns to a covered
  file, and that also pins the ADR amendment shape.
- **Priority**: P0 — it is the red-first proof for WP02 and WP03.
- **Independent test**: `pytest tests/architectural/test_status_path_ordering_claims.py`
  fails on the unmodified tree (before WP02/WP03) and names the offending files.
- **Subtasks**: T001, T002, T003
- **Depends on**: none
- **Risks**: banning the word `Lamport` outright (legitimate mentions exist in
  retrospective lifecycle code and `kernel/clock.py`); passing vacuously on a missing path.

---

## WP02 — Living pages, agent guidelines and the corrected comment

**Prompt**: [tasks/WP02-living-pages-and-guidelines.md](tasks/WP02-living-pages-and-guidelines.md)

**Summary**
- **Goal**: make the pages that describe today's read path state the wall-clock fold, and
  make `AGENTS.md` teach it, so the guard from WP01 goes green for everything except the
  ADR assertion.
- **Priority**: P0 — the pages are the primary harm.
- **Independent test**: re-run the WP01 guard; only its ADR assertion may still fail.
- **Subtasks**: T004, T005, T006, T007, T008, T009
- **Depends on**: WP01
- **Risks**: prose and diagram drifting apart within one page; turning a "two read surfaces
  can disagree" caveat into a claim that is no longer true; over-editing surrounding prose.

---

## WP03 — ADR amendment, changelog and gate re-run

**Prompt**: [tasks/WP03-adr-amendment-and-changelog.md](tasks/WP03-adr-amendment-and-changelog.md)

**Summary**
- **Goal**: record the accepted current ordering in the ADR that owns the read API without
  rewriting its decision, add the release-note entry, and prove every gate green.
- **Priority**: P1 — completes the mission's contract: the record matches the code.
- **Independent test**: the WP01 guard's ADR assertions pass and the docs gates report zero
  errors.
- **Subtasks**: T010, T011, T012, T013
- **Depends on**: WP01
- **Risks**: writing the amendment as a new decision; leaving `updated:` behind; a changelog
  entry over the length limit or missing the `(#6604)` reference.
