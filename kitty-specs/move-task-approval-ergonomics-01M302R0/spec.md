# Mission Specification: move-task / approval-gate ergonomics

**Mission Branch**: `fix/move-task-approval-ergonomics`
**Created**: 2026-09-20
**Status**: Draft
**Input**: GitHub issue #3469 (split from umbrella #3454) — "move-task / approval ergonomics: flag aliases, inert tasks.md checkboxes, reviewer-identity handoff, batch issue-matrix gaps"

## Context & Grounding

Issue #3469 reports a cluster of ergonomic defects in the operator-facing work-package
lifecycle-transition surface (`spec-kitty agent tasks move-task`) and the issue-matrix
approval gate that guards the WP `approved` transition. A profile-loaded grounding squad
reproduced every sub-defect against `main` (HEAD `a9d3f4b747`, CLI 4.0.0rc4) before this
spec was written, so the mission fixes only what is still real and explicitly excludes what
has already landed.

**Confirmed still-real (in scope):** flag-alias gap on `move-task`; over-broad issue-matrix
reference scanning that scaffolds *gating* rows for PR references and context-only citations;
absence of any truthful verdict for a context-only citation; undocumented evidence-token rule
in `issue-verdict --help`; no early warning that approvals gate on verdicts; by-design inert
`tasks.md` checkboxes (a docs/guidance gap, not a behavior bug); a stale `--assignee` help
string.

**Already fixed on `main` — explicitly OUT of scope (must NOT be re-fixed):** the
`issue-matrix.md`-vs-`.json` error string and one-at-a-time missing-row surfacing (both landed
via #4330); the failure-time half of the evidence-token diagnostic (#4330). The reported
`--assignee`-only-binds-on-`doing` failure does **not** reproduce — only its stale docstring
remains.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Honest approval gate for context-only and PR references (Priority: P1)

An agent drives a mission whose `spec.md`/`plan.md`/`research.md`/WP prompts cite other issues
for context (parent epics, sibling missions, historical findings) and reference PRs by their
`#NNNN` hash form. Today the approval gate scaffolds a **gating** issue-matrix row for every one
of those tokens and demands a verdict from a four-value vocabulary in which **no value is true**
for "merely cited, no work owed". The agent is forced to either stall the mission or write a
false outcome (`fixed` / `verified-already-fixed` / `deferred-with-followup` / `in-mission`)
into `issue-matrix.json` — the exact artifact a later audit reads to learn what the mission
touched.

**Why this priority**: This is the core defect (#3469 bullet 4; corroborated by two maintainers).
It corrupts a governance/audit artifact and blocks approvals on well-cited specs — the better a
spec cites its context, the more it is punished.

**Independent Test**: Author a mission spec citing an implementation-target issue, a context-only
issue, and a `PR #NNNN` reference; run the approval-gate path; confirm only the implementation
target produces a gating row, and that the context-only and PR references can be recorded
truthfully without blocking approval.

**Acceptance Scenarios**:

1. **Given** a bare `#200` cited on a line carrying an explicit context marker (e.g. `parent`,
   `epic`, `see #`), **When** the issue-matrix is scaffolded, **Then** `#200` is classified
   non-gating (context-only) — because of the marker rule (FR-011), not a hardcoded number.
2. **Given** a bare, unmarked `#100` appearing in ordinary prose, **When** references are
   discovered, **Then** `#100` defaults to a **gating** row (fail-safe: only an explicit signal
   demotes a reference).
3. **Given** a WP prompt containing `PR #300` in hash form, **When** references are discovered,
   **Then** `#300` is classified as a PR/commit reference and does not become a gating row.
4. **Given** a context-only row, **When** the operator records the `not-applicable` verdict,
   **Then** the WP `approved` transition is not blocked by that row and `issue-matrix.json`
   states the truth.
5. **Given** a `#NNNN` citation on a "baseline-red, do not touch" line in a WP prompt, **When**
   the gate runs, **Then** it does not demand a work-outcome verdict for that citation.
6. **Given** a `#NNNN` cited once as context and once as an implementation target, **When**
   references are discovered, **Then** the aggregate classification is gating (FR-015 —
   implementation-target wins).
7. **Given** a reference classified non-gating at the `approved` transition, **When** the mission
   later reaches merge and `status/doctor` runs, **Then** the same reference is non-gating there
   too (FR-012 / NFR-006 — one shared decision).

### User Story 2 - A truthful non-gating verdict value (Priority: P1)

An operator resolving the issue-matrix needs a verdict that honestly says "this reference is
cited for context / is a PR reference and the mission owes it no work", without asserting work
that never happened and without an unintended follow-up promise.

**Why this priority**: Without a truthful value, User Story 1's classification still leaves
residual rows (ambiguous or deliberately-recorded references) with no honest verdict. This is the
contract change that makes the gate trustworthy; it carries the ADR.

**Independent Test**: Run `issue-verdict` with `--verdict not-applicable` on a context-only row;
confirm it is accepted, is treated as non-gating by the approval blocker, and persists into
`issue-matrix.json`.

**Acceptance Scenarios**:

1. **Given** the verdict vocabulary, **When** `issue-verdict --help` is shown, **Then**
   `not-applicable` appears alongside the four existing values with a description of its
   non-gating meaning.
2. **Given** a row with verdict `not-applicable`, **When** the WP `approved` transition runs,
   **Then** that row does not block approval.
3. **Given** an existing `issue-matrix.json` carrying only the four legacy verdicts, **When** the
   upgraded gate validates it, **Then** every legacy value still validates unchanged (additive,
   backward-compatible).

### User Story 3 - Natural flag names on move-task (Priority: P2)

An agent reaches for the natural `--actor` / `--reason` flags on `move-task` (the names its
sibling `issue-verdict` already uses) and gets a bare "No such option" with no pointer to the
real `--agent` / `--note` flags.

**Why this priority**: A frequent, self-inflicted friction for every bare-system agent; the two
sibling commands disagree on the same concepts, which the fix reconciles.

**Independent Test**: Run `move-task WP01 --to doing --actor claude --reason "…"`; confirm it
succeeds and behaves identically to `--agent`/`--note`.

**Acceptance Scenarios**:

1. **Given** `move-task`, **When** invoked with `--actor` and `--reason`, **Then** the command
   succeeds and applies the same values as `--agent`/`--note`.
2. **Given** `move-task` and `issue-verdict`, **When** their actor vocabulary is compared,
   **Then** `--actor` works on both (the reconciliation is one-directional — `issue-verdict` has
   no `--note`/`--reason` concept to gain).

### User Story 4 - Discoverability: early warning + documented rules (Priority: P2)

An operator planning a mission is never told, at specify/plan/tasks/analyze time, that every
referenced `#NNNN` will gate approval until it carries a verdict row — the surprise arrives only
at the first blocked approval. Separately, the rule that a `deferred-with-followup` evidence
string must contain a `#NNN` reference or a literal `Follow-up:` token is stated nowhere in
`issue-verdict --help` (it appears only at failure time).

**Why this priority**: Turns two late, confusing failures into early, documented expectations.
Low-risk, prose/help-text surface.

**Independent Test**: Inspect the specify/plan/tasks/analyze prompt output for a non-gating
approval-gating heads-up; inspect `issue-verdict --help` for the evidence-token rule.

**Acceptance Scenarios**:

1. **Given** the specify/plan/tasks/analyze prompts, **When** an operator reads them, **Then** a
   non-gating note states that approvals will require an issue-matrix verdict for referenced
   issues.
2. **Given** `issue-verdict --help`, **When** it is shown, **Then** the evidence-token rule for
   `deferred-with-followup` is documented pre-flight.

### User Story 5 - Docs cleanup for known-surprising behavior (Priority: P3)

An operator ticks `- [x]` subtask checkboxes in `tasks.md` and is surprised the `for_review` gate
still blocks (subtask completion is event-sourced via `mark-status`, by design per #2816). The
`--assignee` help string also still claims it only applies "when moving to doing", which no
longer matches behavior.

**Why this priority**: Pure documentation/guidance; no behavior change. Removes two standing
sources of confusion without touching the coherence model.

**Independent Test**: Confirm move-task guidance/docs point at `mark-status` for subtask
completion; confirm the `--assignee` help string describes actual behavior.

**Acceptance Scenarios**:

1. **Given** the `move-task`/subtask surface, **When** an operator looks for how to complete
   subtasks, **Then** guidance points at `spec-kitty agent tasks mark-status` and states that
   `tasks.md` checkboxes are not the completion source of truth.
2. **Given** `move-task --help`, **When** the `--assignee` flag is described, **Then** the text
   matches the actual (any-lane) behavior.

### Edge Cases

- A `#NNNN` that is genuinely both cited as context *and* an implementation target → classified
  as gating (implementation-target wins; never silently downgraded). This requires classification
  to aggregate over ALL occurrences, not the first-occurrence-only dedupe the discovery surface
  does today (FR-015).
- A `not-applicable` row at the `done`/merge boundary → passes unchanged (terminal), unlike
  `in-mission` which must resolve before `done` (FR-014).
- An unmarked bare `#NNNN` in ordinary prose → gates by default; only an explicit signal demotes
  it (FR-011). Ambiguity never fails open.
- A cross-repo issue URL (`owner/repo#NN` or a full `/issues/<n>` URL for another repo) → already
  excluded from discovery; must remain excluded.
- A PR reference given as a full `/pull/<n>` URL vs. the bare `PR #NNNN` hash form → both classify
  as PR/commit references.
- An operator explicitly recording `not-applicable` on a row that *was* an implementation target
  → allowed (operator override), but the classifier does not auto-assign it there.
- A malformed or corrupt `issue-matrix.json` → the gate continues to fail closed (unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Classify discovered references by explicit signal | As the approval gate, I want each discovered `#NNNN` classified as gating (implementation-target), context-only, or PR/commit reference **by a defined, deterministic signal** (see FR-011 for the rule), so that classification is implementable and testable rather than ad hoc. | High | Open |
| FR-002 | Non-gating scaffolding | As the issue-matrix scaffolder, I want context-only and PR/commit references recorded non-gating (not as gating rows), so that a well-cited spec is not punished at approval. | High | Open |
| FR-003 | `not-applicable` verdict value | As an operator, I want a `not-applicable` verdict in `IssueMatrixVerdict`, the `issue-verdict` CLI, and the approval-blocker logic, treated as non-gating, so that every row can state the truth. | High | Open |
| FR-004 | Backward-compatible enum | As a maintainer, I want the new verdict added additively with all four existing values unchanged, so that existing `issue-matrix.json` files validate without migration. | High | Open |
| FR-005 | move-task flag aliases | As an agent, I want `--actor` (alias of `--agent`) and `--reason` (alias of `--note`) accepted on `move-task` — matching `issue-verdict`'s existing `--actor` vocabulary — so the natural flag names work. (One-directional: `issue-verdict` has no `--note`/`--reason` concept; this adds aliases to `move-task` only.) | Medium | Open |
| FR-006 | Document evidence-token rule | As an operator, I want `issue-verdict --help` to document the `deferred-with-followup` evidence-token rule (`#NNN` or `Follow-up:`), so it is discoverable pre-flight. | Medium | Open |
| FR-007 | Early approval-gating warning | As an operator, I want a non-gating heads-up at specify/plan/tasks/analyze that approvals will require issue-matrix verdicts, so the gate is not a late surprise. | Medium | Open |
| FR-008 | Inert-checkbox guidance | As an operator, I want move-task/subtask guidance to point at `mark-status` and state that `tasks.md` checkboxes are not the completion source of truth, so the by-design behavior stops surprising people. | Low | Open |
| FR-009 | Fix stale `--assignee` help | As an operator, I want the `--assignee` help string to describe its actual any-lane behavior, so the docs match reality. | Low | Open |
| FR-010 | ADR for the contract change | As a future maintainer, I want an ADR recording the new non-gating verdict value, the classification narrowing, its non-gating semantics, the backward-compat rationale, **and citing/superseding the never-implemented WP09 `not_applicable` Gate-4 intent** (documented in `merge_gates.py`), so two definitions do not diverge and the change is not "cleaned up" later. | Medium | Open |
| FR-011 | Default-gating fail-safe | As the approval gate, I want a discovered reference to be gating **by default**, with classification only ever *demoting* it to non-gating on a positive, explicit signal (e.g. a leading `PR `/`pull` token, a `Follow-up:`/`baseline-red`/`see #`/`parent`/`epic` context marker, or a cross-repo URL), so that an unmarked bare `#NNNN` in prose still gates and ambiguity never silently escapes the completeness control. | High | Open |
| FR-012 | Single-source gating decision | As a maintainer, I want the gating classification to live in ONE shared function (extending the discovery surface / `IssueReference`) consumed identically by every site that computes "referenced-but-missing" — the approval blocker, `merge_gates`, and `status/doctor` — so a reference cannot be non-gating at one site and gating at another. | High | Open |
| FR-013 | Lever SSOT (row-required vs row-resolved) | As a maintainer, I want the two levers pinned to distinct roles — **classification decides whether a row is REQUIRED (gating); verdict decides whether an existing row is RESOLVED** — with defined behavior when they disagree (an operator may record any verdict on any row; a `not-applicable` verdict makes a row non-gating regardless of classification; an implementation-target classification requires a row even if none was scaffolded), so there is no ambiguous parallel authority. | High | Open |
| FR-014 | `not-applicable` is terminal | As an operator, I want `not-applicable` to be terminal — it passes the merge-time / `done` completeness gate unchanged (unlike `in-mission`, which is accepted at `approved` but rejected at `done`) — so a `not-applicable` row never re-blocks at merge. | High | Open |
| FR-015 | Multi-occurrence aggregate classification | As the discovery surface, I want classification computed as an aggregate over ALL occurrences of an issue number (not the first occurrence only), so that a `#NNNN` cited once as context and once as an implementation target is classified gating (implementation-target wins; never silently downgraded). | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Backward compatibility | 100% of pre-existing verdict values (`fixed`, `verified-already-fixed`, `deferred-with-followup`, `in-mission`) continue to validate; zero migration steps required for existing `issue-matrix.json`. | Compatibility | High | Open |
| NFR-002 | No regression of landed work | Existing tests for #4330 (JSON-first error strings, batched missing-row reporting) and #2816 (event-sourced subtask completion) remain green; no code path re-reads `tasks.md` checkboxes for completion. | Reliability | High | Open |
| NFR-003 | Gate performance | Reference classification adds < 200ms to the finalize-tasks/gate path for a typical mission (≤ 20 references); CLI operations stay < 2s. | Performance | Medium | Open |
| NFR-004 | Documented verdict surface | Zero undocumented gating rules on the verdict surface: both the evidence-token rule and the new `not-applicable` value appear in `--help`. | Usability | Medium | Open |
| NFR-005 | ATDD red-first evidence | Each in-scope defect lands an issue-pinned `@pytest.mark.regression` repro that is RED on the planning base and GREEN on the fix commit. | Quality | High | Open |
| NFR-006 | Cross-site gating consistency | Zero references that are non-gating at the `approved` transition but re-block at merge (`merge_gates`) or report dirty in `status/doctor`; all consumers derive gating from the single shared function (FR-012). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No #2816 regression | Do not re-read `tasks.md` checkboxes as the subtask-completion source; the fix for inert checkboxes is documentation/guidance only. | Technical | High | Open |
| C-002 | Do not re-fix #4330 | Do not modify the `issue-matrix.md`/`.json` error-string resolution or the batched missing-row reporting — both already landed. | Technical | High | Open |
| C-003 | Additive contract only | The verdict enum change is additive: no removal/rename of existing values; `issue-matrix.json` schema stays backward compatible. | Technical | High | Open |
| C-004 | Terminology canon | New flags/help/docs use canonical vocabulary; no `--feature` flag is introduced; `--mission` is the canonical mission selector. | Business | High | Open |
| C-005 | Scope boundary | Sibling #3454 children #3468/#3470/#3471/#3472 are out of scope; do not touch the sync transport. | Business | Medium | Open |
| C-006 | Reviewer ≠ implementer | Each WP is reviewed by a distinct role; the full compliance suite runs at review. | Process | Medium | Open |

### Key Entities

- **Issue Reference**: a `#NNNN` token detected in mission artifacts (spec/plan/research/analysis/
  WP-prompts/contracts). Carries a *classification*: gating implementation-target, context-only
  citation, or PR/commit reference.
- **Issue-Matrix Row**: a row in `issue-matrix.json` keyed by issue number; carries title,
  verdict, and evidence. May be gating or non-gating depending on classification/verdict.
- **Verdict**: the vocabulary value asserting the mission's relationship to a referenced issue.
  Existing: `fixed`, `verified-already-fixed`, `deferred-with-followup`, `in-mission`. New:
  `not-applicable` (non-gating, truthful for context-only/PR references).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A mission spec citing N context-only issues and M PR references produces **0**
  gating rows for those N+M references (previously N+M).
- **SC-002**: **Zero** cases where an operator must assert a false work outcome to pass the
  approval gate — every row has a truthful verdict available.
- **SC-003**: `move-task --actor X --reason Y` succeeds in **100%** of cases where `--agent`/
  `--note` would (previously a hard error).
- **SC-004**: **Zero** undocumented gating rules on the verdict surface — the evidence-token rule
  and the `not-applicable` value both appear in `--help`.
- **SC-005**: At specify/plan/tasks/analyze, the operator sees an approval-gating heads-up
  **before** reaching the gate (previously never).
- **SC-006**: **100%** of pre-existing `issue-matrix.json` files validate unchanged after the
  enum change (no migration).
- **SC-007**: **100%** of unmarked bare `#NNNN` references in prose still produce a gating row
  (fail-safe preserved — classification only demotes on an explicit signal).
- **SC-008**: **Zero** references that are non-gating at the `approved` transition but re-block at
  merge or report dirty in `status/doctor` (single-source gating decision).
