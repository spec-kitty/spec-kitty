# Mission Specification: Doctor mission-state legacy repair & report fidelity

**Mission Branch**: `fix/doctor-mission-state-repair-fidelity`
**Created**: 2026-09-20
**Status**: Draft
**Input**: Milestone 11 (MVP launch) Slice A — GitHub issues #4778, #4780, #4779, plus the `--audit`/`--fix` validation-authority reconciliation. Grounded by a code+architecture research squad; scope confirmed as full seam.

## Overview

`spec-kitty doctor mission-state` is the diagnostic operators and orchestrating agents run to heal mission bookkeeping before they act on it. Two defects make it untrustworthy on real repositories:

1. **It refuses to repair legacy missions.** When an older mission's metadata carries a legacy `change_mode` value (e.g. `regular`) that predates the current single-value vocabulary, the repair aborts that whole mission. On the reporting repository, 21 of 124 missions are unrepairable by the tool's own recommended remediation.
2. **It hides what failed.** The `--fix` and `--teamspace-dry-run` modes print bare failure counts with no mission names or reasons; the only per-item detail is written into a manifest under a git-ignored path, and the dry-run writes no manifest at all. The operator is told something failed N times with no in-terminal way to learn what.

Compounding both, the read-only `--audit` mode *silently accepts* the same legacy value that `--fix` *fatally rejects* — two validation authorities disagreeing about whether one field is valid.

This mission makes the repair **tolerate and normalize** legacy values instead of aborting, makes every mode **honestly report** per-mission outcomes on a git-visible surface, and **reconciles** the audit/fix disagreement.

## Domain Language *(canonical terms)*

- **`change_mode`**: an *optional* mission-metadata field. Its only canonical value is `bulk_edit`. An **ordinary (non-bulk-edit) mission is represented by the field's absence**, never by a sentinel string. Every read boundary already treats any value other than `bulk_edit` identically to absence.
- **Legacy value**: a `change_mode` value this codebase never writes (e.g. `regular`), present only in missions created by an older or external tool line.
- **Normalize**: bring on-disk metadata to canonical form. Here: remove a non-`bulk_edit` `change_mode` so the mission reads as ordinary. This is lossless — it changes no runtime behavior, only the stored representation.
- **Evidence surface**: where an operator reads what a command did or would do. This mission makes the **terminal and `--json` output** the authoritative evidence surface; the existing manifest becomes an internal audit sidecar, not the sole record.
- **Repair report / dry-run report**: the per-mission outcome set (mission slug, status, actions taken, reasons for failure) a run produces.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repair legacy missions instead of aborting (Priority: P1)

An operator with older missions runs `spec-kitty doctor mission-state --fix`. Missions whose metadata carries a legacy `change_mode` are repaired — the legacy value is normalized away — and the command completes successfully instead of erroring on each one.

**Why this priority**: This is the milestone-blocking defect (#4778). Until it is fixed, the tool's own recommended remediation cannot heal the missions it flags, so hosted-walkthrough blockers are unresolvable.

**Independent Test**: Seed a mission whose metadata has `change_mode: regular`, run `--fix`, and confirm the mission is reported repaired, the stored value is gone, and the run exits 0 with no `ValueError`.

**Acceptance Scenarios**:

1. **Given** a mission whose metadata has `change_mode: regular`, **When** the operator runs `doctor mission-state --fix`, **Then** the mission is counted as updated, its stored `change_mode` is removed, the run records that a normalization occurred, and the command exits 0.
2. **Given** a mission whose metadata has `change_mode: bulk_edit`, **When** `--fix` runs, **Then** the value is left untouched (not normalized away).
3. **Given** a mission with no `change_mode` field, **When** `--fix` runs, **Then** the field stays absent and the mission is unaffected.
4. **Given** a mission carrying any other non-canonical `change_mode` value (unknown string or malformed type), **When** `--fix` runs, **Then** it is normalized to absent the same way `regular` is (the fix generalizes, not a `regular`-only special case).
5. **Given** a mission repaired by a prior `--fix`, **When** `--fix` runs again, **Then** it reports zero changes for that mission (idempotent).
6. **Given** any code path that reads `change_mode` (including `implement`'s bulk-edit gate consumer), **When** the field holds a legacy value vs when it is absent, **Then** the observable behavior is identical (FR-012 reader alignment) — so normalizing is behavior-preserving. A test enumerates every reader and asserts legacy-value ≡ absent.

---

### User Story 2 - See which missions failed and why, in the terminal (Priority: P1)

An operator runs `--fix` (or `--teamspace-dry-run`) and, when anything is not fully successful, sees each affected mission named with its reason directly in the command output — and gets the same structured detail from `--json` — without opening any other file.

**Why this priority**: Without this (#4780), a failing run is un-triageable from the terminal; the detail lives only in a git-ignored manifest. This is also what turned #4778 into a multi-hour diagnosis.

**Independent Test**: Force a run with at least one failing and one succeeding mission; confirm the terminal output names the failing mission(s) and reason(s), and that `--json` carries the same per-mission records.

**Acceptance Scenarios**:

1. **Given** a `--fix` run where some missions error, **When** it completes, **Then** the terminal output names each non-successful mission and states its reason, in addition to the summary counts.
2. **Given** the same run with `--json`, **When** it completes, **Then** the machine-readable output contains a per-mission record (slug, status, reason/actions) for every non-successful mission.
3. **Given** a fully successful `--fix` run, **When** it completes, **Then** the output still reports what changed per mission (or an explicit "nothing to change"), never a bare count alone.
4. **Given** any failing run, **When** the operator reads only the command's own terminal/`--json` output, **Then** they can identify every failing mission and its reason without opening a git-ignored file.

---

### User Story 3 - Dry-run parity and a git-visible evidence surface (Priority: P2)

An operator runs `spec-kitty doctor mission-state --teamspace-dry-run` to preview what a repair would do. It reports the same per-mission structured detail a real `--fix` would, and that detail is available from the command output itself rather than only from a git-ignored artifact.

**Why this priority**: Closes the dry-run half of #4780 and the git-invisibility of evidence (#4779). Lower than P1 because it is preview/observability rather than the blocking repair, but it is required for the seam to be coherent.

**Independent Test**: Run `--teamspace-dry-run` on a repo with legacy/invalid missions; confirm it emits per-mission detail (terminal + `--json`) equivalent in shape to `--fix`, and that no per-error detail is reachable *only* through a git-ignored path.

**Acceptance Scenarios**:

1. **Given** missions that would fail validation, **When** the operator runs `--teamspace-dry-run`, **Then** the output names each affected mission and its reason, not just a total count.
2. **Given** the same `--teamspace-dry-run` with `--json`, **When** it completes, **Then** it emits per-mission structured records equivalent in shape to the `--fix` report.
3. **Given** any run (fix or dry-run), **When** it completes, **Then** the complete per-mission triage detail is present on the command's terminal/`--json` surface, so a git-ignored manifest location no longer hides it.

---

### User Story 4 - Audit and fix agree on legacy values (Priority: P2)

An operator sees consistent verdicts across modes: a legacy `change_mode` that `--audit` reports is treated by `--fix` as repairable, not fatal. The two modes do not disagree about whether the same field is valid.

**Why this priority**: The audit/fix disagreement is the deeper root cause behind #4778 and the exact anti-pattern epic #2720 targets (two validation authorities on one field). Fixing US1 without this leaves the divergence latent for the next legacy field.

**Independent Test**: On a mission with a legacy `change_mode`, run `--audit` and `--fix` and confirm neither classifies the field in a way the other contradicts (audit does not silently pass something fix treats as an unrecoverable error).

**Acceptance Scenarios**:

1. **Given** a mission with a legacy `change_mode`, **When** `--audit` runs, **Then** it does not present the field as valid-and-final while `--fix` treats it as an unrecoverable error — the two modes classify it consistently (repairable).
2. **Given** the reconciled behavior, **When** a genuinely invalid mission is audited and fixed, **Then** both modes agree it is invalid for the same reason.

### Edge Cases

- **`change_mode` present as a non-string / malformed type** → treated as non-canonical, normalized to absent (US1 scenario 4).
- **Mission fails for a reason unrelated to `change_mode`** → still surfaced per-mission with its own reason by the fidelity behavior (US2 is not scoped to `change_mode` failures only).
- **Repository with no missions** → run exits 0 with no errors and an explicit "nothing to do".
- **A mission that legitimately must stay `bulk_edit`** → never normalized (US1 scenario 2); the write-path guard still rejects an attempt to *write* an invalid value.
- **Count discrepancy between modes** (e.g. dry-run's validation set differs from fix's) → per-mission detail makes the difference explainable rather than an unexplained "20 vs 21".

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Normalize legacy change_mode on repair | As an operator, I want `--fix` to remove a non-`bulk_edit` `change_mode` so legacy missions repair instead of aborting. | High | Open |
| FR-002 | Record the normalization | As an auditor, I want each normalization recorded as an explicit action in the run record so the change is traceable. | High | Open |
| FR-003 | Repair exits successfully after normalizing | As an operator, I want a run whose only blocker was a legacy `change_mode` to exit 0 with the mission counted as updated. | High | Open |
| FR-004 | Preserve the strict write-path guard | As a maintainer, I want the metadata *write* path to keep rejecting invalid `change_mode` values so garbage is never persisted going forward. | High | Open |
| FR-005 | Per-mission failure detail in terminal (fix) | As an operator, I want `--fix` to name each non-successful mission and its reason in the terminal, alongside the summary counts. | High | Open |
| FR-006 | Per-mission detail in `--json` (fix) | As an agent, I want `--fix --json` to include a per-mission record (slug, status, reason/actions) for every non-successful mission. | High | Open |
| FR-007 | Per-mission failure detail in terminal (dry-run) | As an operator, I want `--teamspace-dry-run` to name each affected mission and its reason, not just a total count. | Medium | Open |
| FR-008 | Structured dry-run parity in `--json` | As an agent, I want `--teamspace-dry-run --json` to emit per-mission records equivalent in shape to the `--fix` report. | Medium | Open |
| FR-009 | Triage without a git-ignored file | As an operator, I want the complete per-mission triage detail available from the command's own terminal/`--json` output, so a git-ignored manifest is not the sole record. | Medium | Open |
| FR-010 | Reconcile audit/fix verdicts | As a maintainer, I want `--audit` and `--fix` to classify a legacy `change_mode` consistently (repairable), so the two modes do not contradict each other on the same field. | Medium | Open |
| FR-011 | Generalize beyond `regular` | As an operator, I want any non-canonical `change_mode` value (not only `regular`) handled by the same normalization path. | Medium | Open |
| FR-012 | Align implicit change_mode readers | As a maintainer, I want every reader that treats "change_mode present" as "this is a bulk-edit mission" to compare `== "bulk_edit"` (the single canonical check), so a legacy value and absence are indistinguishable at every read boundary and normalization is genuinely behavior-preserving. | High | Open |
| FR-013 | Record normalization in the report | As an auditor, I want each per-mission normalization surfaced through a report field (new `meta_actions` on the repair result) so `normalized_change_mode` reaches terminal/`--json`, not just a discarded write-gate boolean. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behavior-preserving normalization | After FR-012 reader alignment, removing a non-`bulk_edit` `change_mode` changes zero runtime behavior at any read boundary: for every code path that reads `change_mode` (including `implement.py`'s bulk-edit-gate consumer), the outcome with the field absent equals the outcome with the legacy value present. Verified by a test that enumerates every reader. NB: without FR-012 this does NOT hold — `implement.py:1340` currently distinguishes legacy-value from absent (post-plan squad [BLOCKER]). | Reliability | High | Open |
| NFR-002 | Idempotent repair | Re-running `--fix` after a successful repair produces zero further changes and zero errors for already-canonical missions. | Reliability | High | Open |
| NFR-003 | Single-invocation observability | For any failing run, 100% of failing missions and their reasons are obtainable from a single command invocation's terminal/`--json` output, with no second command and no git-ignored file read. | Observability | High | Open |
| NFR-004 | No material performance regression | Repair/dry-run wall-clock over a fixed mission set stays within 10% of the pre-change baseline (added per-mission reporting must not scan the tree again). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Vocabulary stays single-valued | The canonical `change_mode` vocabulary remains exactly `{bulk_edit}`. Do NOT introduce `regular` or any new canonical value (charter: Use Canonical Sources, Never Improvise). | Technical | High | Open |
| C-002 | Absence is the ordinary representation | An ordinary mission is represented by absence of `change_mode`; normalization targets absence, not a substitute sentinel (bulk-edit doctrine data-model). | Technical | High | Open |
| C-003 | Writer-schema-sourced validation | Validation must derive from the canonical writer schema; audit and fix must not carry divergent hand-rolled value lists (writer-parity constraint C-005/FR-011). | Technical | High | Open |
| C-004 | Scanner unification out of scope | Unifying the multiple mission-discovery scanners into one canonical discovery (epic #2720) is explicitly OUT of scope; note it as follow-up, do not implement here. | Technical | High | Open |
| C-005 | Python + tests only; ATDD-first | Changes are confined to Python source and tests; no `packs/` template-source edits (so no regenerated-fixture gate). Every new branch/helper lands with a red-first test in the same change. | Process | High | Open |
| C-006 | Manifest may stay git-ignored | The fix must not depend on committing the manifest/quarantine; the terminal/`--json` surface carries the evidence. Un-ignoring the manifest path is not required and is not the mechanism. | Technical | Medium | Open |

### Key Entities

- **Mission metadata record**: the per-mission metadata carrying the optional `change_mode` field; the object normalization operates on.
- **Repair report**: the per-mission outcome set produced by `--fix` (slug, status, actions such as `normalized_change_mode`, and reasons); source of both the summary counts and the new per-mission detail.
- **Dry-run report**: the preview outcome set produced by `--teamspace-dry-run`; must reach shape parity with the repair report.
- **Evidence surface**: the command's terminal and `--json` output — the authoritative record of what happened; the manifest becomes a secondary audit sidecar.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of missions whose only blocker is a non-canonical `change_mode` are repaired by a single `--fix` run (exit 0), where before they errored.
- **SC-002**: For any failing run, an operator identifies every failing mission and its reason from the command's own terminal or `--json` output alone — zero cases require opening a git-ignored file.
- **SC-003**: `--teamspace-dry-run` reports per-mission detail equivalent in shape to `--fix` in a single run (structured parity), for 100% of affected missions.
- **SC-004**: `--audit` and `--fix` return consistent verdicts on a legacy `change_mode` — zero fields are treated as valid-and-final by one mode and unrecoverably fatal by the other.
- **SC-005**: Re-running `--fix` after a successful repair reports zero changes and zero errors (idempotency holds).
- **SC-006**: No read boundary changes behavior when a legacy `change_mode` is removed (behavior-preservation test passes for every path that reads the field).

## Out of Scope

- Unifying the multiple mission-discovery scanners into one canonical discovery (epic #2720) — noted as strategic follow-up.
- Any change to the `bulk_edit` occurrence-classification guardrail semantics themselves.
- Committing or un-git-ignoring the repair manifest/quarantine as the fix mechanism.

## Traceability

| Requirement(s) | Source issue |
|----------------|--------------|
| FR-001, FR-002, FR-003, FR-004, FR-011, NFR-001, NFR-002 | #4778 |
| FR-005, FR-006, FR-007, FR-008, FR-009, FR-013, NFR-003 | #4780 |
| FR-009, C-006 | #4779 |
| FR-010, C-003 | audit/fix reconciliation (epic #2720 anti-pattern) — achieved by `--fix` no longer being fatal; **no `shape_registry.py` change** |
| FR-012, NFR-001 | post-plan brownfield squad [BLOCKER]: `implement.py:1340` reader alignment (DIRECTIVE_044/052) |
