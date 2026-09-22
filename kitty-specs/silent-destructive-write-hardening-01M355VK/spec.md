# Mission Specification: Silent Destructive-Write Hardening

**Mission Branch**: `fix/silent-destructive-write-hardening`
**Created**: 2026-09-22
**Status**: Draft
**Input**: Three independently-reproduced QA P0 defects — #4908, #4897, #4894

## Overview

Three separate `spec-kitty` operations silently destroy healthy, committed data and
report success. A charter activation recompiles the governance catalog with the wrong
mission type and drops 103 references; a documented state-repair command quarantines
authoritative decision records and then empties the ledger; a git merge driver deletes
repeated lines from authored trace markdown on any ordinary merge. In every case the
command exits `0` (or reports `errors=0`), emits no warning, and writes no backup, so the
loss is invisible until a human happens to notice — if the artifact was committed at all.

The three defects touch **disjoint seams** (charter compile, status/decisions repair, git
merge driver) and share **one structural family**: *a documented operation performs a
destructive write on healthy input without first proving it read the canonical source or
that the discarded content is redundant.* This mission fixes each seam on its own terms —
read the SSOT; consult one authoritative registry; union at the right granularity — under a
single acceptance bar: **no silent data loss**.

Grounding is complete (two profile-loaded opus lenses); all three defects were confirmed
live on `main` @ `d57619a900` and are not superseded by the recently-landed
`asset_preservation`, `acceptance-matrix-merge-fail-closed`, or `verdict-matrix-rmw-preservation`
missions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Charter activation preserves the recorded mission type (Priority: P1)

An operator running a **research** (non-`software-dev`) project runs a routine
`spec-kitty charter activate directive <id>`. The post-activation catalog recompile must
keep the project's recorded mission type and only *grow* the reference set with the newly
activated artifact.

**Why this priority**: The compiled `charter.yaml` is the canonical governance catalog read
by `charter context`, the runtime prompt builder, and the dispatch router. A silent flip to
`software-dev` mis-governs every downstream action on the project and loses 103 references.

**Independent Test**: On a project generated with `--mission-type research`, run
`charter activate <kind> <id>` and assert `catalog.mission` stays `research`,
`catalog.template_set` stays `research-default`, and `catalog.references` does not shrink.

**Acceptance Scenarios**:

1. **Given** a project whose `charter.yaml` records `catalog.mission: research`, **When**
   `charter activate directive 025-boy-scout-rule` runs, **Then** `catalog.mission` remains
   `research`, `catalog.template_set` remains `research-default`, and `catalog.references`
   is a superset of the previous set plus the activated artifact (never shrinks).
2. **Given** the same project, **When** `charter deactivate` or `charter pack apply --compile`
   runs, **Then** the recorded mission type is likewise preserved (the fix covers every
   recompile call site, not only `activate`).
3. **Given** a project whose `answers.yaml` is malformed, **When** a recompile runs, **Then**
   the command does not abort (the #2940 malformed-file guard is preserved — the fix does not
   flip `from_interview=True`).

---

### User Story 2 - State repair preserves authoritative decision records (Priority: P1)

An operator runs `spec-kitty doctor mission-state --fix` (or `spec-kitty upgrade`, which
routes into the same repair) on a healthy mission that has recorded Decision Moments. The
repair must not remove rows that another subsystem reads as authoritative, and must not
report `errors=0` if it quarantines canonical rows.

**Why this priority**: `DecisionPoint*` rows in `status.events.jsonl` are the authoritative
store for the decisions subsystem; `decisions/index.json` is a derived fold. Quarantining
those rows destroys the decision record — question, options, chosen answer, rationale,
resolver, and the idempotency key — and the advertised follow-up `doctor decisions --repair`
then rebuilds the index from an emptied log to zero entries.

**Independent Test**: On a healthy mission with one resolved Decision Moment, run
`doctor mission-state --fix` and assert `status.events.jsonl` is byte-identical apart from
documented normalization, `doctor decisions` stays `clean: true`, and
`agent decision list` count is unchanged.

**Acceptance Scenarios**:

1. **Given** a healthy mission with 2 `DecisionPoint*` rows and 0 audited errors, **When**
   `doctor mission-state --fix` runs, **Then** both `DecisionPoint*` rows survive,
   `doctor decisions` reports `clean: true`, and `agent decision list` count is unchanged.
2. **Given** the durable reader (`status/store.py:is_non_lane_event`) and the mission-state
   repair (`_is_preserved_non_lane_row`), **When** either decides whether a non-lane
   `event_type` row is authoritative, **Then** both consult **one shared registry** of
   authoritative non-lane event types (no second hand-maintained list).
3. **Given** a repair that would quarantine a canonical row, **When** it runs, **Then** it
   does not report `errors=0` / success for that mission.

---

### User Story 3 - Trace merge preserves repeated authored content (Priority: P1)

Two branches each append a section (containing fenced code blocks and repeated prose) to the
same `kitty-specs/**/traces/*.md`. An ordinary `git merge` invokes the `spec-kitty-traces`
merge driver. The merged file must contain both sections with all fences and repeated lines
intact — or produce a git conflict for the operator to resolve.

**Why this priority**: The driver is bound to every `traces/*.md` on *every* `git merge` /
`rebase` / `cherry-pick`, not only spec-kitty's own squash. Its line-level global dedup
deletes every repeat of any non-empty line (markdown fences, headings, prose), structurally
destroying authored documents while recording a clean merge. 4 of the 124 traces files in
this repo already contain repeated lines, so the self-dedup arm is live on real content.

**Independent Test**: Merge two branches that each append a fenced section to the same
`traces/*.md`; assert every fence and repeated prose line present in either input is present
in the output (or the merge exits non-zero with a conflict).

**Acceptance Scenarios**:

1. **Given** two branches each appending a `## section` with a ```` ``` ```` fence to the
   same `traces/*.md`, **When** they are merged, **Then** the result contains both sections
   with all fences and repeated prose lines intact.
2. **Given** any merge the driver resolves, **When** it writes the result, **Then** no
   non-empty line present in either input is absent from the output.
3. **Given** a genuine conflict the driver cannot union structurally, **When** it resolves,
   **Then** it either produces a correct structural union or falls back to a non-zero git
   conflict — never a silent lossy exit-0 "clean" merge.

### Edge Cases

- **#4908**: `answers.yaml` present vs. absent; `charter.yaml` present (recompile guard only
  runs when it exists) — read `catalog.mission` from the existing compiled charter as the
  authoritative fallback.
- **#4897**: missions with zero Decision Moments (no-op); other non-lane event types
  (retrospective, annotation, `WPStatusChanged`, `review_result`) already preserved must stay
  preserved after the registry refactor (no regression to the class already fixed).
- **#4894**: identical whole sections on both sides (dedup at section granularity is correct);
  a repeated line *within one distinct section* (must be preserved); base-common content
  inherited from `%O` (must not be misread as a new-side addition).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Charter recompile reads recorded mission type (#4908) | As an operator on a non-software-dev project, I want `charter activate`/`deactivate`/`pack apply --compile` to keep my recorded mission type and template set so that my governance catalog is not silently reclassified. | High | Open |
| FR-002 | Charter recompile never shrinks the reference set (#4908) | As an operator, I want the recompiled `catalog.references` to be a superset of the prior set plus the activated artifact so that no references silently vanish. | High | Open |
| FR-003 | Preserve malformed-answers guard (#4908) | As a maintainer, I want the fix to keep `from_interview=False` so that a malformed `answers.yaml` does not abort a recompile (no #2940 regression). | High | Open |
| FR-004 | Shared authoritative-non-lane-event-type registry (#4897) | As a maintainer, I want a single registry of authoritative non-lane event types that both the durable reader and the mission-state repair consult so that no subsystem can prune rows another treats as canonical. | High | Open |
| FR-005 | mission-state --fix preserves DecisionPoint rows (#4897) | As an operator, I want `doctor mission-state --fix` on a healthy mission to leave `DecisionPoint*` rows intact so that the decision ledger survives repair and `upgrade`. | High | Open |
| FR-006 | Repair reports honest status on quarantine (#4897) | As an operator, I want a repair that quarantines canonical rows to NOT report `errors=0`/success so that silent data loss cannot masquerade as a clean run. | High | Open |
| FR-007 | Trace merge unions at section granularity (#4894) | As an author of trace files, I want the traces merge driver to union whole sections (dedup only identical whole sections/blocks) so that repeated lines within distinct sections are preserved. | High | Open |
| FR-008 | Trace merge preserves all one-sided content or conflicts (#4894) | As an author, I want the driver to keep every non-empty line present in either input, or fall back to a non-zero git conflict, so that no authored content is silently dropped. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Red-first reproduction per defect | Each defect lands an issue-pinned `@pytest.mark.regression` test that is RED through the pre-existing entry point before the fix and GREEN after (3 defects → ≥3 repro tests). | Reliability | High | Open |
| NFR-002 | No behavioral regression to sibling seams | The recently-landed acceptance/issue-matrix drivers, `asset_preservation` guard, and already-preserved event classes (retrospective/annotation/WPStatusChanged/review_result) show zero behavior change (existing suites green). | Reliability | High | Open |
| NFR-003 | New branches/helpers covered | Every new helper/branch introduced by the fixes has a focused unit test in the same PR; cyclomatic complexity of touched functions stays ≤15 (Sonar/ruff C901). | Maintainability | Medium | Open |
| NFR-004 | Lint/type clean | `ruff check`, `ruff format --check`, and `mypy` pass with zero new issues/warnings; no new blanket suppressions. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Do not route through the path-level asset_preservation guard | These are content/row/line-level writes, not filesystem-path deletions; forcing them through `guard_destructive_removal` (which proves package ownership over a `Path`) is a category error. Apply the guard's *principle* per-seam, not its mechanism. | Technical | High | Open |
| C-002 | WP02 fix depth = shared registry | Per recorded decision `01M3560PHPQM617TH5MZHWRF8J`: close the whack-a-field class with one shared registry, not another hand-maintained preserved-set entry. | Technical | High | Open |
| C-003 | Traces driver is not fail-closed like the acceptance driver | Traces are keyless append-union prose; failing closed on every repeat would abort nearly every real merge. Structural union (+ optional 3-way base-awareness) is the correct shape, distinct from the verdict-authority fail-closed rule. | Technical | High | Open |
| C-004 | single_branch topology | This mission fixes the traces merge driver; a lanes-topology run would push the mission's own `traces/*.md` through the buggy driver during lane consolidation. Stay `single_branch`. | Technical | High | Open |
| C-005 | Issue-matrix rows | #4908, #4897, #4894 are each addressed work — each gets an issue-matrix row + claim + verdict slot; each carries a WP. | Process | High | Open |

### Key Entities

- **Compiled charter catalog** (`charter.yaml` `catalog`): canonical governance catalog —
  `mission`, `template_set`, `references`. SSOT for mission type: `answers.yaml` `mission` and
  the existing `catalog.mission`.
- **status.events.jsonl**: append-only event log; **authoritative** store for `DecisionPoint*`
  rows (the decisions subsystem's `index.json` is a derived fold).
- **Authoritative non-lane event-type registry** (new): the single set of `event_type`s both
  `is_non_lane_event` and the mission-state repair treat as canonical.
- **traces/*.md**: authored mission trace documents (approach, design-decisions,
  tooling-friction), section-delimited markdown, merged by the `spec-kitty-traces` driver.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a `research` project, `charter activate` leaves `catalog.mission=research`,
  `catalog.template_set=research-default`, and `catalog.references` count ≥ the pre-activation
  count — verified by the #4908 regression test (RED before, GREEN after).
- **SC-002**: `doctor mission-state --fix` on a healthy mission with recorded Decision Moments
  changes the `DecisionPoint*` row count by 0 and keeps `doctor decisions clean:true` and
  `agent decision list` count unchanged — verified by the #4897 regression test.
- **SC-003**: Merging two branches that each append a fenced section to the same `traces/*.md`
  yields 100% of fences and repeated prose lines from both inputs (or a git conflict), with no
  non-empty input line missing — verified by the #4894 regression test.
- **SC-004**: All three issue-pinned regression tests are RED on the merge-base and GREEN on
  the branch; the full blast-radius suites (charter, status/decisions, merge) pass; `ruff`,
  `ruff format --check`, and `mypy` are clean.
