# Mission Specification: One synthesis-ownership reader, one unreadable-record error

**Mission Branch**: `issue-6767-synthesis-ownership-single-reader`
**Created**: 2026-10-31
**Status**: Draft
**Input**: spec-kitty/spec-kitty#6767 — "Converge the synthesis-ownership readers and their 'unreadable record' errors".

## Intent Summary (confirmed)

- **Primary actor**: the agent or operator whose governance is computed from the synthesis
  ownership record — `charter context`, `charter dispatch`, the action-governance bundle, and
  the `charter synthesize` JSON envelope.
- **Trigger**: any read that has to answer "what did synthesis create?".
- **Outcome**: exactly one reader answers that question, applying one fallback policy and
  raising exactly one documented, coded "unreadable record" error. The lenient display path
  stops parsing the provenance sidecar and wraps the strict reader instead.
- **Rule**: a record that cannot be read never answers "nothing was synthesized" (fail closed),
  and an unreadable record is always named with the file at fault and a remedy.
- **Boundary**: the three existing answers' *meaning* is preserved: the manifest is the commit
  record, a `project-direct-write` sidecar is a registration rather than synthesis ownership,
  and the created-artifacts record is the documented stand-in when the manifest cannot be read.
  No new file format, no new module, no gate weakened.

### Grounding (current `main`)

All three paths named in the issue still exist on `main` and still disagree; the issue's stated
blocker (Mission `resynthesis-after-activation`, #6510, PR #6778) is merged, so the convergence
is now unblocked.

| Path | Source of truth | Fallback | Failure |
| --- | --- | --- | --- |
| `charter.activation.synthesizer.reach_only._synthesized_slugs` | manifest entries (`<kind>:<slug>`) | `.kittify/charter/synthesized-artifacts.yaml` (+ legacy tactics record) | `SynthesisMembershipUnreadableError`, code `SYNTHESIS_MEMBERSHIP_UNREADABLE` |
| `charter.activation.synthesizer.manifest.synthesized_urns` | manifest entries + provenance sidecars (`artifact_urn`, direct-write excluded) | none | module-private `_SynthesisOwnershipUnreadableError` (a `ManifestIntegrityError`), uncoded |
| `specify_cli.cli.commands.charter._synthesis._extract_artifact_id_from_provenance` | its own lenient YAML parse of the sidecar | n/a (returns `None`) | never raises |

The disagreement is exactly two-fold: **fallback** (only the reach-only reader has one) and
**error identity** (two classes, one coded, one not). The sidecar shape additionally has two
parsers. This mission collapses all of that onto one reader and one error.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One reader answers "what did synthesis create?" (Priority: P1)

A maintainer reads `reach_only_ids`, `synthesis_owned_directive_ids` and the JSON envelope of
`charter synthesize`, and finds one function behind all three, documented in one place, with the
same ownership rule.

**Why this priority**: the three answers are today independently maintained; a rule fixed in one
is missed in the others (this issue is the recorded instance).

**Independent Test**: a fixture with a manifest, sidecars (one synthesized, one
`project-direct-write`) and a created-artifacts record yields the same ownership from all three
consumer entry points; `grep` finds no second manifest/sidecar reader.

**Acceptance Scenarios**:

1. **Given** a manifest listing a synthesized directive, a `project-direct-write` directive and a
   synthesized tactic, with sidecars, **When** the ownership reader is called per kind, **Then**
   it returns the synthesized URNs only, and both `reach_only_ids` and
   `synthesis_owned_directive_ids` return their ids from that same call path.
2. **Given** a synthesized artifact later re-registered as `project-direct-write`, **When** the
   reader runs, **Then** the URN stays owned (one synthesis-written entry is enough).
3. **Given** a manifest-less project, **When** the reader runs, **Then** it answers "nothing was
   synthesized" without reading the created-artifacts record.

---

### User Story 2 - One documented "unreadable record" error (Priority: P1)

An operator whose `.kittify/charter/` records are damaged sees one error, with one code, naming
the file at fault and the remedy — whichever reader reached it.

**Why this priority**: two error types for one condition means two catch sites, two wordings and
one uncoded private class the CLI cannot render uniformly.

**Independent Test**: corrupt the manifest and the sidecar in turn, from each consumer entry
point, and assert the same class and code; assert `charter context` exits 1 printing the code and
the offending path.

**Acceptance Scenarios**:

1. **Given** a corrupt manifest and no usable created-artifacts record, **When** either consumer
   runs, **Then** it raises `SynthesisMembershipUnreadableError` with code
   `SYNTHESIS_MEMBERSHIP_UNREADABLE`, and the body names the manifest, the record and the remedy.
2. **Given** a corrupt manifest and a usable record, **When** a reach-only kind is asked for,
   **Then** the record's ids are used, with the existing warning, and nothing is raised.
3. **Given** a corrupt manifest and a directive slate, **When** directive ownership is asked for,
   **Then** the one coded error is raised (the record does not track directives), not a guess.
4. **Given** a corrupt or missing sidecar for a directive entry, **When** ownership is asked for,
   **Then** the one coded error names that sidecar.
5. **Given** a dangling manifest symlink, **When** the reader runs, **Then** it is treated as
   unreadable (not absent), exactly as today.

---

### User Story 3 - The display path wraps the strict reader (Priority: P2)

The `charter synthesize --json` envelope is built from the one sidecar reader, not a second YAML
parse, and still never raises: an unreadable ownership record costs the envelope its
`artifact_id` values, not its shape.

**Why this priority**: a second parser of the same file is the defect; a strict-JSON contract
that crashes on a damaged record is the risk of fixing it carelessly.

**Independent Test**: run the envelope builder over a manifest with (a) good sidecars, (b) a
missing sidecar, (c) a corrupt sidecar, and assert the envelope shape is unchanged and the
`artifact_id` degrades to `null`.

**Acceptance Scenarios**:

1. **Given** sidecars that parse, **When** the envelope is built, **Then** each directive's
   `artifact_id` is the URN id segment, exactly as today.
2. **Given** a sidecar that does not parse or is missing, **When** the envelope is built, **Then**
   the entry's `artifact_id` is `null` and the envelope is otherwise intact.
3. **Given** the display module, **When** it is inspected, **Then** it contains no YAML parse of
   the sidecar shape.

### Edge Cases

- Manifest absent but present as a dangling symlink → unreadable (record consulted), not empty.
- Manifest unreadable, record present but listing no id of the requested kind → the one error.
- Manifest unreadable and kind not tracked by the record (directives) → the one error.
- Manifest readable, one directive entry's sidecar missing → the one error naming that sidecar
  (the URN is unknowable from the entry alone).
- Manifest readable, one tactic entry's sidecar missing, record usable → record ids, warning.
- Sidecar whose `artifact_urn` kind does not match the entry's kind, or has an empty id → the one
  error.
- Sidecar path outside `.kittify/charter/provenance/`, or resolving outside the repo → the one
  error.
- Overlay absent, or present with no synthesized-shape edge → empty set, and the ownership record
  is not read at all (unchanged lazy read).
- An org-required id stays excluded from reach-only delivery (unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One ownership reader | As a maintainer, I want one function that answers "which artifacts of this kind did synthesis create?" from the manifest and its sidecars, so that one rule serves every consumer. | High | Open | [build] | no — no such function exists on the base; the two current readers answer with different sources |
| FR-002 | One fallback policy | As an operator, I want an unreadable manifest *or* an unreadable sidecar to fall back to the created-artifacts record, and only an unusable record to raise, so that one damaged file does not refuse delivery when the record can answer. | High | Open | [build] | no — the base has fallback only in the reach-only reader and none in the directive reader |
| FR-003 | One coded error | As a CLI consumer, I want a single `SynthesisMembershipUnreadableError` (`SYNTHESIS_MEMBERSHIP_UNREADABLE`) for every unreadable-record condition, carrying the offending file, so that one catch renders one diagnostic. | High | Open | [build] | no — the base raises a private uncoded `ManifestIntegrityError` subclass on one path |
| FR-004 | reach_only adopts the reader | As a maintainer, I want `reach_only_ids` to derive its slugs from the one reader instead of its own manifest-only read, so that delivery gating and directive ownership cannot diverge. | High | Open | [build] | no — the base reads slugs itself, without sidecars |
| FR-005 | Directive ownership adopts the reader | As a maintainer, I want `synthesis_owned_directive_ids` to use the one reader and delete its private URN reader, so that the ownership rule has one home. | High | Open | [build] | no — the private reader is the only source today |
| FR-006 | One sidecar parser | As a maintainer, I want one strict sidecar reader (validated model, contained path, URN kind/id checked) and no second YAML parse of `artifact_urn`, so that the sidecar shape has one parser. | High | Open | [build] | no — the base has a lenient second parser in the CLI envelope |
| FR-007 | Display path wraps the strict reader | As an operator, I want the `charter synthesize --json` envelope to keep its shape and never raise, taking `artifact_id` from the one sidecar reader and degrading to `null` on its coded error. | High | Open | [ratchet] | yes — same envelope on a healthy fixture, paired with FR-006's corrupt-sidecar fixture |
| FR-008 | Remedy text preserved | As an operator, I want the collision remedy to keep naming the offending file and the remedy it gives today, now driven by the one coded error. | Medium | Open | [ratchet] | yes — the existing remedy assertions stay green |
| FR-009 | Reader documented as the authority | As a reader of the code, I want the one reader and its one error code documented where they live, and the retired readers gone (no re-export of a second answer). | Medium | Open | [build] | no — the base documents two readers and a private error |
| FR-010 | Behaviour preserved for reach-only delivery | As an agent, I want delivery gating to keep dropping a reach-only artifact of an inactive directive and keep delivering the rest, so that the convergence changes no governance outcome beyond the documented hand-authored case. | High | Open | [ratchet] | yes — paired with FR-004 on the pre-existing delivery fixtures |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Diff coverage | Changed and new lines reach at least 90% diff coverage. | Reliability | High | Open |
| NFR-002 | Quality gates | `ruff check`, `ruff format --check` and `mypy` report 0 issues on touched files; no new `noqa`/`type: ignore`; every touched function stays at complexity 15 or below. | Maintainability | High | Open |
| NFR-003 | No extra I/O when unneeded | A call that cannot have a synthesized artifact reads no ownership record (the overlay check stays first); a healthy read does not parse the sidecar twice. | Performance | Medium | Open |
| NFR-004 | Determinism | The reader's result is a `frozenset`, so ordering never leaks into delivery or the envelope. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new record format | `.kittify/charter/synthesized-artifacts.yaml` and the provenance sidecar keep their current shapes; this mission reads them differently, it does not migrate them. | Technical | High | Open |
| C-002 | No new module | The reader lives with the record it owns (the synthesizer `manifest` module); no new package boundary and no re-export that preserves a second answer. | Technical | Medium | Open |
| C-003 | No weakened refusal | The fail-closed refusal introduced by #6454 keeps exiting 1 with `SYNTHESIS_MEMBERSHIP_UNREADABLE`; no condition that refuses today may start returning an empty set. | Technical | High | Open |
| C-004 | Public surface stable | `charter.activation.api` keeps exporting the ownership entry points and `ManifestIntegrityError`; no caller loses a name it imports. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Exactly one function in `src/` reads the synthesis manifest to answer ownership, and exactly one reads the provenance sidecar shape; a repository search for the retired names returns no production hit. — [build] · no-op passable: no
- **SC-002**: Every unreadable-record condition reachable from either consumer raises the same class with code `SYNTHESIS_MEMBERSHIP_UNREADABLE`; zero production sites raise the retired private class. — [build] · no-op passable: no
- **SC-003**: `charter context` on a damaged-but-recorded project still exits 1 with the code and the offending path, and on a healthy project its output is byte-identical to the base. — [ratchet] · no-op passable: yes
- **SC-004**: The `charter synthesize --json` envelope keeps its documented four-field shape on healthy and damaged fixtures alike. — [ratchet] · no-op passable: yes
