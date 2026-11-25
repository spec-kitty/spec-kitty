---
title: 'ADR: `not-applicable` issue-matrix verdict — non-gating, terminal, classifier-narrowed approval gate'
description: 'Adds a non-gating, terminal not-applicable verdict and narrows the approval blocker to gate only implementation_target references, superseding the never-shipped WP09 Gate-4 intent.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-09-20'
updated: '2026-11-22T00:00:00Z'
---

## Context and Problem Statement

Mission `move-task-approval-ergonomics-01M302R0` (#3469) WP02, built on WP01's reference
classifier (`specify_cli.tasks.issue_reference_discovery`). WP01 landed a pure,
deterministic classifier (`classify_occurrences` / `GatingClass`) that labels every
discovered `#NNNN` reference as `implementation_target` (gating), `context_only`, or
`pr_or_commit_ref` (both non-gating), plus the single shared predicate `is_gating()` /
`gating_issue_numbers()` every consumer must derive "referenced-but-missing" from
(FR-012). WP02 is the first consumer to wire that classifier into a live enforcement
site: the `move-task`/approval blocker in
`src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`.

Two problems motivated this change:

1. **No truthful non-gating verdict.** `IssueMatrixVerdict` (`src/specify_cli/cli/
   commands/review/_issue_matrix.py`) offered four values: `fixed`,
   `verified-already-fixed`, `deferred-with-followup`, `in-mission`. None of them let an
   operator honestly record "this reference is cited for context, or is a PR/commit
   reference — the mission owes it no work." An operator resolving a context-only row
   was forced to pick a verdict that asserted work that never happened (`fixed`) or an
   unintended follow-up promise (`deferred-with-followup`).
2. **The approval blocker gated on every discovered reference, not just gating ones.**
   `_issue_matrix_approval_blocker` (and its internal `_issue_matrix_evaluation` helper)
   computed `referenced_issues = {f"#{ref.number}" for ref in refs}` — every reference
   `discover_issue_references` found, with no consultation of WP01's classification at
   all. A mission that referenced only `context_only`/`pr_or_commit_ref` issues (e.g. a
   `baseline-red until #200 lands` note, or a `PR #300` citation) was still forced to
   scaffold an `issue-matrix.json` and fill a row for every one of them before `approved`
   — the classifier existed but nothing consumed it yet.

### A previously-documented, never-implemented alternative

`src/specify_cli/policy/merge_gates.py::_evaluate_issue_matrix_completeness_gate` already
carried this comment before this ADR:

> "Fail-closed only when references exist: zero discovered references is a PASS (nothing
> to enforce). WP09 owns the formal `not_applicable` Gate-4 verdict for the post-merge
> review surface; this merge gate's zero-reference branch is intentionally the simpler
> "nothing to check" case, not a re-definition of `not_applicable`."

No "WP09" mission ever implemented a `not_applicable` Gate-4 verdict anywhere in this
repository — grepping the tree turns up only this one comment, describing an intent that
was never realized. Left standing, that comment invited a second, independently-invented
`not_applicable` definition on the merge-gate surface whenever someone eventually acted
on it, which would have diverged from whatever vocabulary landed first on the
`issue-verdict`/approval-blocker surface (exactly the two-definitions-diverge failure
mode FR-010 calls out). **This ADR is that first landing, and it explicitly supersedes
the WP09 comment's intent**: there is now exactly one `not_applicable`-shaped verdict —
`IssueMatrixVerdict.NOT_APPLICABLE` — and any future work on `merge_gates.py`'s
`_evaluate_issue_matrix_completeness_gate` (mission `move-task-approval-ergonomics-
01M302R0` WP03, cross-site adoption) must consume this same value and the same
classifier predicate (`is_gating`), not invent a second Gate-4-specific enum or string
literal. The comment in `merge_gates.py` is left in place (WP02 does not own that file)
but is superseded in intent as of this ADR; WP03 updates or removes it when it adopts the
classifier.

## Decision

### D1 — Add `IssueMatrixVerdict.NOT_APPLICABLE = "not-applicable"` (additive)

Appended as a fifth member of the `StrEnum`, after `IN_MISSION`. No existing member is
renamed, reordered, or removed. Every consumer that parses a verdict does so via
`IssueMatrixVerdict(value)` (a plain `try`/`except ValueError`) rather than an exhaustive
`match`, so the four legacy values continue to parse and validate byte-for-byte
unchanged — an existing `issue-matrix.json`/`issue-matrix.md` needs no migration
(NFR-001, SC-006).

### D2 — `not-applicable` is non-gating at `approved` and terminal at `done`/merge

Unlike `in-mission` (non-terminal: accepted at `approved`, rejected at `done` via the
`_issue_matrix_approval_blocker`'s `unresolved_in_mission` special-case list),
`not-applicable` requires **no special-case code at either transition**. Once a row
exists with verdict `not-applicable`:

- It is a *valid* `IssueMatrixVerdict` member, so `validate_issue_matrix`/
  `diagnose_structured_issue_matrix` accept the row (assuming a non-empty
  `evidence_ref` — the one universal row rule) at both `approved` and `done`.
- It is never added to `unresolved_in_mission` (that list only ever collects rows whose
  verdict `is IssueMatrixVerdict.IN_MISSION`).
- It therefore never re-blocks at merge — it is terminal by the *absence* of a rejection
  rule, not by an added exemption. This is deliberate: there is no future state in which
  this mission "resolves" a reference it never owed work on, so there is nothing for a
  `done`-time check to wait for.

### D3 — The approval blocker gates only WP01-classified `implementation_target` references

`_issue_matrix_approval_blocker` and `_issue_matrix_evaluation`
(`tasks_parsing_validation.py`) now import `is_gating` from
`specify_cli.tasks.issue_reference_discovery` and filter every discovered reference
through it before computing `referenced_issues` / `missing_issues` /
`unresolved_in_mission`, and before deciding whether an issue-matrix artifact is
required at all:

```python
gating_refs = [ref for ref in refs if is_gating(ref)]
if not gating_refs:
    return None
```

A mission whose only references are `context_only`/`pr_or_commit_ref` now requires **no
issue-matrix artifact at all** — not even a scaffolded one — because classification
decides row-*requirement* (FR-013), and non-gating classifications never require a row.
This is a narrowing of what blocks approval, not a widening: every reference that
gated before this change (an unmarked bare `#NNNN`, the FR-011 fail-safe default) still
gates identically. Only references the classifier positively demotes (an explicit `PR
#N`/`pull` token or a `Follow-up:`/`baseline-red`/`see #`/`parent`/`epic` context marker)
stop requiring a row.

### D4 — Lever SSOT: classification governs requirement, verdict governs resolution (FR-013)

Two independent levers, pinned to distinct roles, with explicit behavior where they
appear to disagree:

- **Classification decides whether a row is REQUIRED.** Only `implementation_target`
  references ever force a row to exist.
- **Verdict decides whether an existing row is RESOLVED.** An operator may record *any*
  verdict — including `not-applicable` — on *any* row, regardless of what the classifier
  said about the underlying reference. Recording `not-applicable` on a reference the
  classifier calls `implementation_target` is an explicit operator override (allowed);
  the classifier never auto-assigns `not-applicable` itself — it only ever produces
  `GatingClass` labels, never `IssueMatrixVerdict` values. Conversely, an
  `implementation_target` classification requires a row to exist even if none was ever
  scaffolded — a missing row is `missing_issues`, not silently exempted, regardless of
  what verdict an operator might eventually want to put there.

### D5 — CLI surface: `--verdict` and `--evidence-ref` document both new/existing rules

`spec-kitty agent issue-verdict --help` now lists `not-applicable` alongside the four
legacy values with its non-gating/terminal meaning (NFR-004, contract C5.2), and
`--evidence-ref --help` documents the pre-existing `deferred-with-followup` evidence-
token rule (a `#NNN` or `Follow-up:` substring, previously enforced but undocumented —
FR-006) so both gating rules on the verdict surface are discoverable pre-flight rather
than discovered only after a validation failure.

## Consequences

**Positive:**

- An operator can now record the truth on a context-only/PR-reference row instead of
  a verdict that overstates work done or promises a follow-up that will never come.
- A mission that only ever cites non-gating references needs no issue-matrix artifact —
  removing a category of unnecessary friction the classifier existed to solve but that,
  before this WP, nothing consumed.
- `merge_gates.py` and `status/doctor` (WP03) now have exactly one `not_applicable`-
  shaped vocabulary member and one classifier predicate to adopt, rather than reinventing
  the WP09-intended Gate-4 verdict independently.

**Trade-offs / follow-ups:**

- WP03 (cross-site adoption) still owns wiring `merge_gates.py`'s
  `_evaluate_issue_matrix_completeness_gate` and `status/doctor`'s equivalent check onto
  the same `is_gating`/`gating_issue_numbers` predicate this ADR's approval-blocker
  change already consumes (NFR-006 cross-site consistency: a reference non-gating at
  `approved` must be non-gating at merge and report clean in doctor). Until WP03 lands,
  the merge-time gate and doctor's divergence check still gate on every discovered
  reference — a narrower gap than before WP01/WP02 (the approval blocker is now correct),
  but not yet fully closed end-to-end.
- The `merge_gates.py` comment naming "WP09" is left in place (out of this WP's owned
  files) pending WP03's pass over that module; this ADR is the authoritative record that
  its `not_applicable` intent is superseded by `IssueMatrixVerdict.NOT_APPLICABLE`.

## Amendment 2026-11-22 — scope decides; color values and commit citations are not owed

Mission `issue-matrix-over-matching-01M81KK0` (#7808, #5297, #5516; operator rulings
"One Mission, all three" and "Scope decides") narrows what D3 gates. The FR-011
fail-safe default, under which an unmarked bare `#NNNN` gates, now holds **inside the
gating scope only**:

- **Gating scope (an allowlist).** References in `spec.md` and in `tasks/*.md` keep
  the FR-011 default. A reference found in any other scanned artefact is *cited*: it
  classifies as `context_only` (non-gating) and stays in the audit trail. Today that
  covers `plan.md`, `research.md`, `analysis-report.md` and `contracts/*.md`, and any
  artefact added to the scan later defaults to cited. A planted-break label
  ("Break #N"), a research-table id and background prose therefore need no row.
  Discovery marks each `Occurrence` with `in_gating_scope`, and `classify_occurrence`
  remains the one classifier that reads it.
- **Closing keywords gate everywhere.** A non-negated closing keyword
  (`close`/`fix`/`resolve` family, optional colon, optionally emphasised) that leads
  into a citation makes that occurrence an `implementation_target` in any scanned
  artefact. The citation may be wrapped in backticks, emphasis or a markdown link, or be an issue URL. The
  keyword binds to the one citation it leads into, as GitHub's does, so in
  `Closes #A and #B` only `#A` is closed. It takes
  precedence over every demoting rule, including the commit rule below. The same
  helper feeds the Mission source-issue derivation (#7011), so the two cannot drift.
- **Commit citations.** A backticked 7-40 character hex SHA that contains at least one
  letter `a-f` and one digit, and sits within 16 characters of the citation on either
  side, classes the occurrence as `pr_or_commit_ref`, as in ``(`<sha>`, #N)``. An
  all-digit backticked token, or an all-letter word such as `defaced`, stays gating.
- **Number filter.** No issue-number pattern accepts a leading zero, so `#000` and
  `#000000` are no longer issue 0. The rule is not limited to colors: zero-padded
  prose such as `#083` (a Mission number) is no longer a reference either. Digits are
  ASCII only. An all-digit hex color in CSS
  declaration form is not a reference. Declaration form means a listed lower-case
  color-bearing property name (`color`, `background`, `border-color`, `fill`, and so
  on) or a `--custom-property`, as a whole token. The property must start a
  declaration: at line start, after `{`, `;`, a backtick or a quote, or after
  whitespace inside a `{` block opened earlier on the line. Then come a colon, the
  value, and a declaration terminator (`;`, `}`, `!important`, or a closing backtick
  or quote that also opened the declaration, so a prose apostrophe in `color: #N's fix`
  is not one). The value must have a hex-color length (3, 4, 6 or 8 digits). Prose
  such as `Backfill: #N`, `Border-color: #N tracks this`, `Fix text color: #N;` or
  `fill: #12345;` stays a reference. This is narrower than plan D1 of the Mission,
  whose regex was case-insensitive and unanchored; review cycle 1 found that version
  dropped real references. A CSS
  word elsewhere on the line does not filter anything, because a 4-digit `#RGBA`
  color is indistinguishable from a 4-digit issue. The closing-keyword and
  source-description patterns now read numbers only through `_GH_ISSUE_PATTERN` and
  `_matched_issue_number`, leaving one number-recognition authority.

**Promotion layer.** The Mission source-issue promotion (#7011) still runs after
`classify_occurrence`. A Mission's own issue therefore gates wherever it is cited,
including when it is cited only out of scope. This is a documented guarantee layered
on top of the classifier, not a second classifier.

**Accepted narrowings.** The closing-keyword and source-description labels now read
the number through the canonical detector. Forms that detector deliberately rejects
are therefore no longer source issues:
- a hyphen or other non-terminator glued to the number (`Closes #N-fix`, `Issue #N-color`);
- no boundary before the `#` (`Fixes:#N`, `Closes#N`);
- a keyword and number split across lines.

A negation such as "does not fix" is now judged within the line only. Of these forms,
only the keyword split across lines still gates in `spec.md` and `tasks/`, under the
scope default. The glued and boundary-less forms (`#N-fix`, `Fixes:#N`, `Closes#N`)
are not detected anywhere, so they neither gate nor appear in the audit trail. The
detector on main never found them either, so this is not a regression; it is recorded
so no fail-safe is claimed for them.

**Known residual over-match (within the rulings).** The closing-keyword label also
gates noun uses ("the fix #N regressed"), past-tense history ("PR #M fixed #N",
"closed #N") and negations outside the existing list ("must not close #N", "do not
fix #N"). The commit-citation window also demotes a backticked hex-only identifier
next to a citation. Outside `spec.md` and `tasks/` the closing-keyword cases all
gated before this amendment as well. Extending the negation list and narrowing the
keyword to imperative use are follow-ups.

**Scaffold.** `scaffold_issue_matrix` still detects on `spec.md` alone. It agrees with
discovery there. References that gate only through `tasks/` or a closing keyword
elsewhere are reported as missing rows by the gates rather than pre-scaffolded, as
before.

`GatingClass` is unchanged. "Cited" is the existing `context_only` value, so persisted
rows and scaffold verdicts keep their vocabulary. D2, D4 and D5 are unaffected. The
default inside the gating scope still fails safe: no reference in `spec.md` or `tasks/`
that gated before stops gating, unless it is a color, a leading-zero number or a
commit citation. Tests: `tests/tasks/test_issue_matrix_over_matching.py`.

## Alternatives Considered

- **Reuse `in-mission` for context-only rows.** Rejected: `in-mission` asserts "a later
  WP in this mission will resolve this," which is false for a reference the mission
  never owed work on, and `in-mission` is explicitly non-terminal (rejected at `done`) —
  the opposite of the terminal semantics a context-only reference needs.
- **Skip the enum member; treat "row exists at all" as sufficient regardless of
  verdict.** Rejected: this would silently launder an unresolved `fixed`/`deferred-
  with-followup` row that never got its real verdict recorded, and gives up the
  truthfulness goal (User Story 2) entirely — the row would say nothing honest about
  *why* no further work is owed.
- **Gate on `context_only` too, only exempting `pr_or_commit_ref`.** Rejected: contradicts
  WP01's own classification contract (C1.2/C1.3), which defines both as non-gating
  outcomes for the same reason (cited but not an implementation target); treating them
  differently at the enforcement site would silently re-diverge from the single-source
  classifier WP01 built specifically to prevent that (FR-012).

## References

- Mission `kitty-specs/move-task-approval-ergonomics-01M302R0/`: `spec.md` (FR-003,
  FR-004, FR-006, FR-010, FR-011, FR-012, FR-013, FR-014, NFR-001, NFR-005, NFR-006),
  `data-model.md` (`IssueMatrixVerdict` value table), `contracts/classification-and-
  verdict-contract.md` (C3, C4).
- WP01 classifier: `src/specify_cli/tasks/issue_reference_discovery.py`
  (`GatingClass`, `classify_occurrences`, `is_gating`, `gating_issue_numbers`).
- This WP's changes: `src/specify_cli/cli/commands/review/_issue_matrix.py`
  (`IssueMatrixVerdict.NOT_APPLICABLE`), `src/specify_cli/cli/commands/agent/
  issue_verdict.py` (`--verdict`/`--evidence-ref` help), `src/specify_cli/cli/commands/
  agent/tasks_parsing_validation.py` (`_issue_matrix_evaluation`,
  `_issue_matrix_approval_blocker`).
- Superseded intent: `src/specify_cli/policy/merge_gates.py::
  _evaluate_issue_matrix_completeness_gate` (the "WP09 ... `not_applicable` Gate-4"
  comment).
- Regression test: `tests/specify_cli/cli/commands/test_issue_matrix_not_applicable.py`.
- #4330 (unrelated, non-regressed): the JSON-first error prefix and batched
  missing-row diagnostic surfacing in `_issue_matrix_approval_blocker` predate this ADR
  and are unchanged by it.
