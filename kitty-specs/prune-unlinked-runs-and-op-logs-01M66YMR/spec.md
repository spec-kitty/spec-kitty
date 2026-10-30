# Mission Specification: Prune unlinked runs and Op-scoped glossary logs

**Mission Branch**: `issue-6739-prune-unlinked-runs-and-op-logs`
**Created**: 2026-10-30
**Status**: Draft
**Issue**: spec-kitty/spec-kitty#6739 (follow-up to #6610, #5212)
**Input**: User description: "doctor event-logs: unlinked runs and Op-scoped glossary logs are never pruned"

## Intent Summary

An operator runs `spec-kitty doctor event-logs` on a project that has been in use
for months. Two families of local item have accumulated and the command has never
offered to remove any of them: run directories whose run-index entry was replaced
or removed, and the Op-scoped glossary logs that make up most of
`.kittify/events/glossary/`. Both are reported `Mission not found` and kept, so the
one command whose job is bounding `.kittify/` cannot bound them.

**Primary actor**: a project owner (operator) cleaning up local state.
**Trigger**: `spec-kitty doctor event-logs` (preview), then `--apply`.
**Success outcome**: both families are judged by the state of the thing they belong
to — or, when they belong to nothing this checkout can find, by age alone — while
every genuinely protected item (an open Mission, an open Op, a recorded Mission
this checkout does not know, a locked item, a committed record) stays exactly as it
is today.
**Key constraint**: the protection the operator ruled for in 2026-10-23 — an
unknown *Mission* is never pruned — is unchanged.
**Assumption (discovery skipped on operator instruction)**: this is a governed
follow-up to a released command with a reproduction, a settled design and one
GitHub issue; the mission brief instructs the run to be autonomous, so the
discovery interview is recorded as this Intent Summary rather than asked.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reclaim run directories that link to no Mission (Priority: P1)

An operator's project has run journals under `.kittify/runtime/runs/` whose
`feature-runs.json` entry was replaced or removed years ago. The run's own record
still names the Mission it belongs to — as a slug, which is the only identity the
production writer records there. Those runs are reported `Mission not found` and
kept forever today. After this mission, such a run follows its Mission: past
retention and merged (or itself finished) means it is a candidate. A run that
names **no** Mission at all — a leftover directory from a lost race — is judged on
age alone, so it no longer accumulates forever either.

**Why this priority**: it is the largest single contributor of unprunable state and
the residual the current engine documents against this issue number.

**Independent Test**: build a project with one merged Mission and one run whose
index entry is absent and whose snapshot names only `inputs.mission_slug`; the
preview lists that run as a candidate, and `--apply` deletes it and reports its
index entry removal. A second run naming nothing is also a candidate once past both
limits.

**Acceptance Scenarios**:

1. **Given** a merged Mission and an old run whose only Mission record is the slug
   in its own snapshot, **When** the operator previews, **Then** the run is a
   candidate whose `mission` is that Mission.
2. **Given** an old run that names no Mission anywhere, **When** the operator
   previews, **Then** the run is a candidate with the reason `past retention; no
   Mission recorded`.
3. **Given** an old run whose recorded Mission is open, **When** the operator
   previews, **Then** the run is kept as `Mission is open`.
4. **Given** an old run whose recorded Mission identity resolves to no Mission in
   this checkout, **When** the operator previews, **Then** the run is kept as
   `Mission not found`.

---

### User Story 2 - Reclaim glossary logs that belong to a closed Op (Priority: P1)

Most files in a real `.kittify/events/glossary/` are named
`profile-invocation-<id>.events.jsonl`. They belong to an Op, not a Mission, so no
Mission-based rule can ever reach them. After this mission, an Op's log is judged
by its Op: protected while the Op is open, eligible once the Op is completed, and
judged on age when no Op record exists at all. The logs that name no owner by
design (`_cli`, `_renderer`) stay out of the report exactly as today.

**Why this priority**: equal to User Story 1 — together they are the whole issue,
and this family is the one that dominates a real project's log directory.

**Independent Test**: a project with one completed Op and one open Op, each with an
old glossary log: the completed Op's log is a candidate, the open Op's log is kept
as `Op is open`; a log whose Op has no record is a candidate as `no Op recorded`.

**Acceptance Scenarios**:

1. **Given** an Op whose record carries a completion (or a closure on the closure
   spine) and an old log for it, **When** the operator previews, **Then** the log
   is a candidate with the reason `past retention; Op completed`.
2. **Given** an Op whose record carries only `started`, **When** the operator
   previews, **Then** the log is kept as `Op is open`.
3. **Given** an old Op-scoped log whose Op has no record in this checkout,
   **When** the operator previews, **Then** the log is a candidate as
   `past retention; no Op recorded`.
4. **Given** `_cli` and `_renderer` logs of any age, **When** the operator
   previews, **Then** neither appears in the report.

---

### User Story 3 - Trust the report and the limits while cleaning up (Priority: P2)

The operator must be able to act on the preview without fear: the list of
candidates is exactly what `--apply` deletes, `keep_runs` still protects the newest
N of *each* kind (a flood of Op logs must not push a Mission's log out of the newest
N), a locked item is never deleted, and every new verdict says why in both the
human and the `--json` report.

**Why this priority**: safety and legibility of an irreversible command; it does not
change what is deleted, only how the operator can see and trust it.

**Independent Test**: run the preview and then the apply on the same fixture and
compare the two reports item for item; hold a lock on a candidate and confirm it is
reported kept.

**Acceptance Scenarios**:

1. **Given** a preview that lists N candidates, **When** the operator runs
   `--apply` with no other process active, **Then** exactly those N items are
   reported deleted and nothing else changes.
2. **Given** a candidate whose lock another process holds, **When** the operator
   applies, **Then** the item is kept and reported `lock held`.
3. **Given** `keep_runs: 20`, many old Op logs and one old Mission log, **When**
   the operator previews, **Then** the Mission log's rank is computed against
   Mission logs only.

---

### Edge Cases

- A run's snapshot is unreadable or is not a JSON object: it names an unknown
  Mission, so it stays kept (fail safe, unchanged).
- A run's recorded slug is claimed by two Mission directories: ambiguous, so it
  stays kept as `Mission not found` (no first-match-wins).
- A run records a `mission_id` this checkout does not know: kept, even though a
  slug in `inputs` would have resolved (an id is the only identity; only a record
  with no id falls back to a slug).
- An Op record exists but is empty or corrupt: it carries no completion, so the Op
  reads as open and its log is kept (fail safe).
- An Op log's file disappears mid-scan, or a run directory does: the item is
  skipped, as today.
- The Op records directory or the closure spine is absent: every Op log reads as
  having no Op recorded and is judged on age.
- `keep_runs: 0` and `max_age_days: 0`: nothing younger than "now" is removed; the
  limits still require both thresholds to be exceeded.
- An Op log is a symlink, or a run directory is a symlink: never collected and
  never deleted (unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Snapshot slug links a run | As an operator, I want a run whose own record names its Mission by slug to follow that Mission's lifecycle, so that a run with no index entry is no longer kept forever. | High | Open | [build] | no — paired on the same fixture with an unknown-identity run that must stay kept |
| FR-002 | No Mission recorded is judged by age | As an operator, I want an item that names no Mission at all to be judged on age alone, so that leftover run directories stop accumulating. | High | Open | [build] | no — paired on the same fixture with an open-Mission run that must stay kept |
| FR-003 | Recorded unknown Mission stays protected | As an operator, I want a run whose recorded Mission this checkout cannot find to stay kept, so that work on another branch is never destroyed. | High | Open | [ratchet] | no — pins the 2026-10-23 operator ruling |
| FR-004 | Ambiguous identity stays protected | As an operator, I want a run whose Mission identity resolves to more than one directory to stay kept, so that no arbitrary guess deletes a run. | Medium | Open | [ratchet] | no |
| FR-005 | Op log follows its Op | As an operator, I want an Op-scoped glossary log to be eligible once its Op is completed, so that the log directory stops growing without bound. | High | Open | [build] | no — paired with an open Op's log on the same fixture |
| FR-006 | Open Op's log stays protected | As an operator, I want an Op-scoped log kept while its Op is open, so that a running invocation never loses its own audit trail or resume point. | High | Open | [build] | no |
| FR-007 | No Op recorded is judged by age | As an operator, I want an Op-scoped log whose Op has no record in this checkout to be judged on age alone, so that logs abandoned by a lost Op are reclaimable. | Medium | Open | [build] | no |
| FR-008 | Every verdict states its reason | As an operator, I want each new candidate and kept item to carry a distinct reason in both the human and the JSON report, so that I can tell an unlinked item from an unknown owner before applying. | High | Open | [build] | no |
| FR-009 | Op logs rank among their own kind | As an operator, I want `keep_runs` to protect the newest N Op logs among Op logs, so that one family cannot push another out of the newest N. | Medium | Open | [ratchet] | no |
| FR-010 | Preview equals apply | As an operator, I want the preview to list exactly what `--apply` deletes, so that I can trust the report before an irreversible step. | High | Open | [ratchet] | no |
| FR-011 | Locks still protect | As an operator, I want an item whose lock another process holds to be kept at preview and at apply, so that cleanup never races a live writer. | High | Open | [ratchet] | no |
| FR-012 | Never-removed items stay out | As an operator, I want `_cli`/`_renderer` logs, committed Mission records, Op records and the Op index, the run index and tracked files to stay untouched, so that cleanup loses no history. | High | Open | [ratchet] | no |
| FR-013 | One owner says when an Op is closed | As a maintainer, I want the "is this Op open" rule to live in one place used by both the doctor surface and cleanup, so that the two can never disagree about what closes an Op. | Medium | Open | [build] | no |
| FR-014 | Docs describe the new verdicts | As an operator, I want the how-to and the command help to describe the unlinked and Op-scoped verdicts, so that I can predict what the tool will do. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Scan cost stays flat | A preview over a project with 1,000 Op records and 1,000 glossary logs completes in under 2 s on a warm filesystem and reads each Op record at most once per scan. | Performance | High | Open |
| NFR-002 | Read-only preview | A preview performs zero writes: no lock file is created, no index is rewritten, and no file under the project changes (byte-identical tree before and after). | Reliability | High | Open |
| NFR-003 | Deletion stays inside the local tier | Every deletion target is strictly inside a registry-declared local tier root; a symlink, a committed ledger or a path outside the project is never deleted. | Security | High | Open |
| NFR-004 | Deterministic verdicts | Two scans over the same tree at the same reference time produce identical candidate sets and reasons, with no dependence on directory iteration order. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Identity rule unchanged | A recorded `mission_id` remains the only runtime identity; a slug is read only from a record that carries no id. This mission widens where the slug is read from, never the rule itself. | Technical | High | Open |
| C-002 | Operator ruling preserved | An unknown *Mission* stays protected. Nothing in this mission prunes an item whose recorded Mission this checkout cannot resolve. | Business | High | Open |
| C-003 | No new configuration | The behaviour is governed by the existing `ledger.retention` keys (`keep_runs`, `max_age_days`); no new key, default or migration is introduced. | Technical | High | Open |
| C-004 | Reader side only | The cleanup engine stays on the reader side of the event-log seam: it probes and holds existing locks with the kernel primitive and never calls an event-log append door. | Technical | High | Open |
| C-005 | Report shape is additive | The JSON report gains no new top-level key and no item key; only new `kind` and `reason` values may appear. | Technical | Medium | Open |
| C-006 | Resume points survive | Deleting an Op's log is only possible after that Op's work is over and past `max_age_days`, so no live glossary checkpoint/resume point is removed. | Technical | High | Open |

### Key Entities

- **Run directory**: a journalled `next` run under `.kittify/runtime/runs/<run>/`. It
  may name its Mission through the run index, through its own snapshot's
  `mission_id`/`mission_slug`, through its snapshot's recorded input slug, or not
  at all.
- **Mission**: a `kitty-specs/<slug>/` directory with a `meta.json`, its lifecycle
  facts (merged, completed, open) read from the status log.
- **Op**: a dispatched profile invocation with a durable record `kitty-ops/<id>.jsonl`
  and a closure spine `kitty-ops/op-closures.jsonl`; open until it carries a
  completion.
- **Op-scoped glossary log**: `.kittify/events/glossary/profile-invocation-<id>.events.jsonl`,
  named for the Op it belongs to.
- **Retention verdict**: one item judged as `candidate` or `kept` with exactly one
  reason, reported identically by the preview and the apply.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fixture with an old unindexed run whose snapshot names a merged Mission, a preview reports that run as a candidate — 0 such runs are unprunable (today: all of them are). — [build] · no-op passable: no
- **SC-002**: On a fixture with an old Op-scoped log for a completed Op, a preview reports it as a candidate, and a log for an open Op is still kept — 100% of the Op-log family is decided by its Op's state. — [build] · no-op passable: no
- **SC-003**: Every item in both reports carries a reason that names its verdict, with 0 items reported `Mission not found` unless a Mission identity was actually recorded. — [build] · no-op passable: no
- **SC-004**: Applying a preview deletes exactly the previewed candidates in 100% of runs (0 items reported as candidates survive an apply, 0 undeleted items are absent from the preview). — [ratchet] · no-op passable: no
- **SC-005**: A preview over 1,000 Op records and 1,000 glossary logs completes in under 2 s and leaves the tree byte-identical. — [build] · no-op passable: no
