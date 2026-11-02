# Mission Specification: dispatch `--brief` governance payload

**Mission Branch**: `issue-6990-dispatch-brief-governance-payload`
**Created**: 2026-11-01
**Status**: Draft
**Input**: Issue #6990 — "dispatch: full governance payload re-embedded per invocation (~13-26 KB); consider embed-by-reference or a `--brief` mode"

**Guidance recorded from the operator brief**: this is a small, user-facing CLI
ergonomics change. It must not weaken any governance gate and must not change
default output. The fix has to be proven red-first through the existing
`spec-kitty dispatch` entry point.

## Problem statement

`spec-kitty dispatch` re-embeds the whole rendered governance context in every
invocation. Measured on `main` @ `287a226cfe` in this clone:

```text
spec-kitty dispatch "implement the login handler" --profile python-pedro --dry-run --json
→ 24,983 bytes total, of which governance_context_text = 23,668 bytes (308 lines)
```

A harness that dispatches dozens of times per day pays that volume as prompt
context on every call, although after the first read the marginal information is
near zero (same charter, same directives, same rules). The payload content is
correct; the delivery is not.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Re-read the governance payload by reference (Priority: P1)

An agent coordinator that already read the full governance context for a
profile/action earlier in the session dispatches again with `--brief`. The
response keeps every routing and orientation field, replaces the re-embedded
text with a digest line (hash, size, line count), and prints the exact command
that fetches the full text if it is needed again.

**Why this priority**: this is the whole issue. Without it there is no fix.

**Independent Test**: run the real `spec-kitty dispatch` command twice on the
same request — once plain, once with `--brief` — and compare envelopes and
console output.

**Acceptance Scenarios**:

1. **Given** a project with a charter, **When** `dispatch "<request>" --profile <p> --json --brief` runs, **Then** `governance_context_text` is `null`, a `governance_context_reference` block carries the payload digest, byte count, line count and fetch command, and every other envelope field (profile, action, confidence, alternatives, recommendation, hash, availability, status, close contract) is unchanged from the non-brief run.
2. **Given** the same project, **When** `dispatch "<request>" --profile <p> --brief` runs in console mode, **Then** the full governance text is not printed, and instead a digest line plus the fetch command is printed, followed by the unchanged open-Op close hint.
3. **Given** the same project and request, **When** `dispatch` runs **without** `--brief`, **Then** the output is byte-identical to the pre-change behaviour (full text in the JSON envelope and in the console panel).

---

### User Story 2 - Fetch exactly the text that was omitted (Priority: P1)

The fetch command printed by `--brief` must reproduce the payload's governance
text exactly — including the profile-cited directives, which today only
`dispatch` renders. So `spec-kitty charter context` gains `--profile <id>`.

**Why this priority**: an inexact fetch command would silently drop the
profile-cited doctrine, which is a governance-faithfulness bug, not an
ergonomics win. The reference mode is only honest if the reference resolves.

**Independent Test**: for a fixed project and action, render the text through
`charter context --action <a> --profile <id>` and through `dispatch --profile
<id>`, and compare them.

**Acceptance Scenarios**:

1. **Given** a project with a charter and a resolvable profile, **When** `spec-kitty charter context --action <a> --profile <id>` runs, **Then** the rendered text equals the text `dispatch --profile <id>` embeds for that action (same profile-cited sections), and without `--profile` the output is unchanged from today.
2. **Given** a `--brief` JSON envelope, **When** the printed fetch command is run, **Then** it fetches the full governance text for the same action and profile named in the envelope.

---

### Edge Cases

- **No charter / governance unavailable**: `--brief` prints the existing
  "Governance context unavailable" signal and no digest block; the envelope's
  `governance_context_available` stays `false`.
- **`--dry-run --brief`**: same substitution on the dry-run envelope
  (`status: "dry_run"`, no `close_contract`), no Op opened.
- **Ambiguous routing with `--dry-run`**: the ambiguous payload carries no
  governance text at all; `--brief` must leave it untouched.
- **Unknown `--profile` on `dispatch`**: unchanged `PROFILE_NOT_FOUND` exit 1.
- **`charter context --profile <unknown>`**: renders without profile sections and
  says so on stderr, rather than failing the fetch.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `dispatch --brief` replaces the embedded text with a reference | As an agent coordinator, I want a brief dispatch mode so that repeated invocations do not re-embed ~24 KB of unchanged governance text. | High | Open | [build] | no — non-brief run must still embed the full text on the same fixture |
| FR-002 | The brief reference names an exact fetch command | As an agent coordinator, I want the reference to carry a command that reproduces exactly the omitted text, so I can re-read it without guessing. | High | Open | [build] | no — the fetch command must be asserted against the profile-cited text it is supposed to reproduce |
| FR-003 | `charter context --profile` renders the profile-cited sections | As an operator, I want `charter context` to accept a profile so the fetch command can match what dispatch embeds. | High | Open | [build] | no — a no-op would leave the profile sections missing from the fetched text |
| FR-004 | Default dispatch output is unchanged | As an existing consumer, I want dispatch without `--brief` to behave exactly as before. | High | Open | [ratchet] | no — pinned by an assertion on the full text of the same fixture |
| FR-005 | Brief mode is documented where users meet it | As a user of the dispatch surface, I want the flag in the command reference, the standalone-invocation skill and the changelog, so I know when to use it and that it never replaces the first read. | Medium | Open | [build] | no — docs are asserted present in the changed surfaces |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Brief envelope volume | On the reference project the `--brief --json` envelope is at most 10% of the non-brief envelope for the same request (measured: full = 24,983 bytes), and contains no governance text characters. | Performance | High | Open |
| NFR-002 | No gate weakening | No lint, type, architecture or test gate is skipped, xfailed, or relaxed by this change; `dispatch` still assembles governance context on every call. | Maintainability | High | Open |
| NFR-003 | Blast radius | Only the dispatch command surface, the charter-context command surface, their tests, and the docs/changelog that describe them change. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Opt-in only | `--brief` is opt-in; no automatic/stateful suppression of the payload, because dispatch must never silently stop loading governance. | Technical | High | Open |
| C-002 | Reference must resolve | A brief payload may only omit text it can reproduce with a printed command; if reproduction is impossible the text stays embedded. | Technical | High | Open |
| C-003 | Existing envelope contract | The non-brief envelope shape (`contracts/cli-do-output.md`) is unchanged; brief mode adds keys and nulls the text field, it does not remove or rename an existing one. | Technical | High | Open |

### Key Entities

- **Brief governance reference**: the digest of the omitted payload — hash, byte
  count, line count, and the fetch command — that stands in for
  `governance_context_text`.
- **Governance payload digest**: the already-computed
  `governance_context_hash` plus the size and line count of the rendered text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `dispatch --brief --json` on the reference project emits an envelope of at most 2,500 bytes (10% of the 24,983-byte baseline) with `governance_context_text` null and a populated reference block — [build] · no-op passable: no (the baseline envelope is measured on the same fixture)
- **SC-002**: The structured fetch command reproduces the omitted text byte-for-byte for the same action and profile — [build] · no-op passable: no (compared against the dispatch-embedded text, not against a hand-written expectation)
- **SC-003**: A run without `--brief` is byte-identical to `main`'s output for the same request — [ratchet] · no-op passable: no (the same fixture asserts the full text is still embedded)
