# Mission Specification: Sonar new-code reliability blockers removed at source

**Mission Branch**: `kitty/mission-sonar-new-code-reliability-01M6GRHZ`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#7113 — "Sonar: new-code reliability rating is E on main (no tracking issue)", with operator guidance: *if the rating is driven by pre-existing code rather than a recent regression, say so plainly with evidence rather than mass-editing to move a metric.*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The new-code reliability BLOCKERs stop being analyzer false positives (Priority: P1)

A maintainer reading the nightly SonarCloud quality gate sees `new_reliability_rating = 5 (E)` on `main` and cannot tell whether the project regressed or the analyzer mis-read an intentional construct. The two findings that alone produce the E are analyzer false positives on code merged 2026-10-29/30: a value lookup on a functional-API `Enum` (`python:S5756`) and a name used in a function-local annotation above the `import` that binds it (`python:S3827`). The mission removes both constructs at their source, so the rating can recover without a SonarCloud web-UI waiver that would be invisible to the repository.

**Why this priority**: the E rating is produced by exactly these two BLOCKER findings (`new_bugs = 4`, of which 2 BLOCKER); no other finding can move the rating above it. Until they are resolved the gate stays red and the debt is easy to stop noticing (#7109 already made the step informational).

**Independent Test**: point the repository's own analysis at the two sites (or a reviewer reads the diff): after the change neither flagged construct exists, both call sites behave exactly as before, and the guard test in `tests/architectural/` fails on the pre-change tree and passes on the post-change tree.

**Acceptance Scenarios**:

1. **Given** `src/specify_cli/cli/commands/events.py` as of `main`, **When** the `--kind` default is resolved, **Then** it is selected by *name* from the closed registry `_LOG_KIND_MEMBERS` instead of by calling the functional-API `Enum`, and `spec-kitty events tail` still defaults to `status`.
2. **Given** `src/charter/activation/compiler.py::_default_active_charter_service`, **When** the function is read top to bottom, **Then** every name used in an annotation is bound by a statement that precedes that use, in both branches, and both branches return the same objects as before.

---

### User Story 2 - The provably-dead branch behind `S2583` is gone (Priority: P2)

`src/specify_cli/migration/backfill_identity.py:132` guards a helper call whose result is non-`None` exactly in the branch that calls it, so the guard is provably dead (`pythonbugs:S2583`, MAJOR, new code). The mission replaces the dead guard with an explicit narrowing that states the invariant, so the analyzer state matches the code's actual contract.

**Why this priority**: it is one of the four reliability findings on new code; it does not change the rating letter on its own, but leaving it means the mission did not finish the class of finding it set out to fix.

**Independent Test**: the same guard test asserts the dead conditional expression is absent and that `_tracked_mission_id` still returns `(None, <notice>)` for an unavailable tracked `meta.json` and `(<mission_id>, None)` for a usable one.

**Acceptance Scenarios**:

1. **Given** a Mission whose tracked `meta.json` cannot supply an identity, **When** `_tracked_mission_id` runs, **Then** it returns the refusal's notice exactly as before, with no provably-dead conditional in the path.
2. **Given** a Mission whose tracked `meta.json` supplies an identity, **When** `_tracked_mission_id` runs, **Then** it returns `(mission_id, None)` exactly as before.

---

### User Story 3 - The remaining findings are adjudicated honestly, not swept (Priority: P2)

The issue's work list implies 23 reliability findings are in scope; the live analysis says 4 are on new code and 19 are pre-existing (Sonar `creationDate` 2026-08-22 … 2026-10-12, all before the new-code window that starts at `4.0.0rc7`, 2026-10-15). The mission records that classification, with its query and its per-finding evidence, where a maintainer can check it — and explicitly does **not** rewrite the 19, several of which are deliberate determinism control assertions and the Java ones a documented scan-scope decision.

**Why this priority**: moving a metric by mass-editing deliberate tests would weaken the suite; the value here is a truthful disposition the next reader can act on.

**Independent Test**: the PR body and the mission's evidence record state, with the reproducing query, which findings are new code (and now resolved), which are pre-existing, and which need a maintainer decision; a reviewer can re-run the query and get the same split.

**Acceptance Scenarios**:

1. **Given** the SonarCloud project API, **When** `sinceLeakPeriod=true` is applied to `types=BUG`, **Then** it returns 4 findings before the change and the mission's documents name those 4 as the new-code set.
2. **Given** the 19 pre-existing findings, **When** the mission's diff is read, **Then** none of their sites is modified and the reason each is left alone (deliberate control assertion / documented scan-scope decision) is named.

### Edge Cases

- The functional-API `Enum` is built from `SUPPORTED_LOG_KINDS`; if that registry ever loses `status`, both the old value lookup and the new name lookup fail at import. The behaviour on that impossible path is unchanged (fail fast at import), and the guard test pins the registry's membership so the failure is legible.
- `from __future__ import annotations` is active in `compiler.py`, so the annotation never runs. Reordering the import must not change which module objects are imported in which branch order, and must not introduce an import cycle at call time (the import stays function-local).
- `_tracked_mission_id`'s helper has exactly one caller; a future second caller must not inherit a live `None` branch that the narrowing no longer expresses. The docstring states the precondition.
- The rating cannot reach A from inside this repository: `acceptance-jvm` is scanned as MAIN code on purpose (`sonar.yml`), so `java:S5960` on Cucumber step definitions continues to score. The mission reports this rather than reversing the decision.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `--kind` default resolved by name | As a maintainer, I want the `events tail` default kind selected from the closed registry by name so that the deliberate construct stops reading as a call on a non-callable. | High | Open | [ratchet] | no — the guard asserts the value-lookup call shape is absent, which is present before the change |
| FR-002 | Annotation follows its binding | As a maintainer, I want `_default_active_charter_service` to bind `ActiveCharterService` before the annotation that names it so that no reader or analyzer sees a use-before-definition. | High | Open | [ratchet] | no — the guard asserts import-before-annotation order, which fails before the change |
| FR-003 | Dead refusal guard replaced | As a maintainer, I want the provably-dead `None` guard removed in favour of an explicit narrowing so that the code states the invariant the helper actually guarantees. | Medium | Open | [ratchet] | no — the guard asserts the dead conditional expression is absent |
| FR-004 | Findings classified with evidence | As a maintainer, I want the new-code and pre-existing findings split with a reproducible query and a per-finding reason so that I can act on the real debt instead of the whole list. | High | Open | [build] | no — a no-op change ships no classification |
| FR-005 | Behaviour preserved on both paths | As an operator, I want the three affected surfaces to behave identically so that an analyzer-driven change cannot alter runtime behaviour. | High | Open | [ratchet] | no — the tests exercise both branches/outcomes of each site |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero new suppressions | The diff adds zero `NOSONAR` markers, zero `sonar.issue.ignore` rules, and changes neither `sonar-project.properties` nor the scan scope in `.github/workflows/sonar.yml`. Measured: `git diff main -- '*.py' 'sonar-project.properties' '.github/workflows/sonar.yml'` contains no suppression or scope line. | Maintainability | High | Open |
| NFR-002 | Proportionate, verifiable diff | Four source files change: the three finding sites (one edit each, inside the flagged function) and the docstring of the single helper the `S2583` fix narrows; plus one new test module and one changelog fragment. `git diff --stat main` shows no file outside those. | Maintainability | High | Open |
| NFR-003 | Tests stay in the fast tier | Every added test carries an existing fast-tier marker and the new module completes in under 5 s when run alone (`pytest <file> -q`), so the change adds no measurable cost to the shared baseline. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No SonarCloud write access | This environment has no SonarCloud token and the issue's "mark in the UI" step is a web-UI action; adjudication is therefore recorded in the repository (source comment + PR body) instead of in SonarCloud. | Technical | High | Open |
| C-002 | `acceptance-jvm` scope is a maintainer decision | `sonar.yml` documents scanning `acceptance-jvm` as MAIN code on purpose (full Java rule set incl. security), so `java:S5960` on step definitions is a consequence of that decision. The mission must not reverse it; it reports the option instead. | Technical | High | Open |
| C-003 | Pre-existing findings are not rewritten | The 19 findings outside the new-code window are out of scope; in particular the `S5863` sites are deliberate same-input determinism controls (one is commented "control: the baseline key is stable"), so deleting them to move a metric would weaken the suite. | Technical | High | Open |
| C-004 | Repository gates are not weakened | No gate, ratchet baseline, exclusion list or test marker may be relaxed to make this change pass; a gate that fails for an unrelated reason is reported, not silenced. | Technical | High | Open |

### Key Entities *(include if the mission involves data)*

- **New-code window**: the SonarCloud period `previous_version` anchored at `4.0.0rc7` (2026-10-15); determines which findings carry the rating.
- **Reliability finding**: a SonarCloud issue of `type=BUG` with a severity (`BLOCKER`/`CRITICAL`/`MAJOR`/`MINOR`) and a `rule` (`python:S5756`, `python:S3827`, `pythonbugs:S2583`, `java:S5960`, …).
- **Adjudication**: the disposition of one finding — resolved at source, deliberate-and-kept, or needs a maintainer decision — with the reason and, where relevant, the commit that introduced the line.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: None of the three removed constructs returns: reverting any one of the three fixes independently makes exactly one check fail, and restoring it makes all of them pass. — [ratchet] · no-op passable: no
- **SC-002**: The reliability findings attributable to new code drop from 4 to 1 (only the documented `java:S5960` remains), i.e. `new_reliability_rating` moves from 5 (E) to at most 3 (C) and no BLOCKER remains on new code. — [build] · no-op passable: no
- **SC-003**: Every targeted suite for the three touched modules passes unchanged, with counts recorded in the PR; the diff contains no suppression and no scan-scope change (NFR-001). — [ratchet] · no-op passable: no
- **SC-004**: A reviewer can reproduce the new-code/pre-existing split in one API call and finds the mission's documents consistent with it. — [build] · no-op passable: no
