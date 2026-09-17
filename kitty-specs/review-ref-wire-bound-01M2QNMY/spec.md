# Mission Specification: Bound review_ref at the WPStatusChanged wire projection

**Mission Branch**: `issue-3954-review-ref-wire-bound`
**Created**: 2026-09-17
**Status**: Draft
**Input**: GitHub issue [#3954](https://github.com/spec-kitty/spec-kitty/issues/3954) — "Truncate review_ref instead of dropping WPStatusChanged at the 240-byte bound" (MVP-interim scope, per the issue's top clarification + the operator 2026-09-17 reconcile + Robert's release-control claim).

## Intent Summary *(confirmed)*

- **Primary actor**: an operator/agent running `spec-kitty agent tasks move-task` (approval, completion, rejection/rework) or emitting a status transition directly, on a repo admitted to a Team Kitty relay.
- **Trigger**: the transition carries a legacy-prose `review_ref` (a real review note copied from `--note`) longer than 240 UTF-8 bytes.
- **Desired outcome**: the `WPStatusChanged` Zeitgeist *moment* still broadcasts (bounded), instead of the whole moment being silently dropped; the canonical local status event log keeps the FULL note.
- **Load-bearing rule/invariant**: bound/normalize **only legacy prose** `review_ref` at the wire-projection boundary; **never truncate pointer-shaped values**; **exactly one publish offer per emitted event**.
- **Canonical terms / boundary**: *moment* = one volatile Zeitgeist broadcast ("Zeitgeist carries NOW, Git carries DONE"); the wire-projection boundary is `status/zeitgeist_bridge.py` (`_broadcast_status_transition` → `_broadcast_moment`), upstream of the pinned events codec `spec_kitty_events.zeitgeist_attrs` (a CLIENT dependency, not edited here). This is an **MVP interim**; the structural fix is post-MVP in #4327/#4336.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — An approval with a real review note still broadcasts (Priority: P1)

An operator approves a work package with `move-task --to approved`, attaching a substantive multi-line review note (routinely >240 bytes). Today the moment is dropped whole and the team relay never learns the WP was approved. After this mission, the moment broadcasts with a bounded one-line `review_ref`, while the full note stays in the local status event log.

**Why this priority**: This is the launch-critical defect (F-46). E2E-MVP §1.2–1.3 require `move-task` transitions to broadcast within 60 s; a drop at the 240-byte bound silences a required moment on the MVP walkthrough.

**Independent Test**: Drive `move-task --to approved` with a >240-byte multi-line note through the real CLI entry point; assert exactly one publish offer, wire `review_ref` ≤240 UTF-8 bytes and single-line with a trailing `…`, and the persisted `status.events.jsonl` entry retains the full note verbatim.

**Acceptance Scenarios**:

1. **Given** a valid FSM fixture at `in_review` and a >240-byte multi-line prose review note, **When** `move-task --to approved --note <long prose>` runs, **Then** the `WPStatusChanged` moment is offered exactly once, its wire `review_ref` is one line, ≤240 UTF-8 bytes, ends with a visible `…`, no "not broadcast" overflow warning is logged, and an INFO-level log records that `review_ref` was bounded.
2. **Given** the same transition, **When** the moment is offered, **Then** the canonical local `status.events.jsonl` event still contains the full, untruncated note.
3. **Given** a transition whose `review_ref` is already a short pointer (e.g. `review:WP04`), **When** it is broadcast, **Then** the value rides the wire verbatim (no collapse, no `…`).

### User Story 2 — Rejection/rework and completion broadcast the same way (Priority: P2)

The same bound applies to every otherwise-valid transition carrying prose `review_ref`, not approvals alone: rejection-to-rework (`--to doing`, the review_ref-required edge) and completion (`--to done`, possibly multi-hop).

**Why this priority**: The interim's breadth clarification (2026-09-14) mandates coverage for approval/completion, rejection/rework, and direct emission; a fix that only covers approval leaves F-46's twins live.

**Independent Test**: Drive rejection and completion transitions with >240-byte prose notes through the CLI; assert bounded broadcast and exactly one offer per emitted event (multi-hop commands emit one offer per event, never a double-offer).

**Acceptance Scenarios**:

1. **Given** a valid FSM fixture eligible for rejection with a >240-byte note, **When** `move-task --to doing --note <long prose>` runs, **Then** the moment broadcasts with a bounded one-line `review_ref` and exactly one offer.
2. **Given** a multi-hop completion command that emits more than one status event, **When** it runs, **Then** each emitted event produces exactly one publish offer (no added or dropped offers).

### User Story 3 — Direct status emission and pointer safety (Priority: P3)

A path that emits a status transition directly (`emit_status_transition`) with a prose `review_ref`, and the guarantee that pointer-shaped values are never mangled and that the bound is scoped to `review_ref` only.

**Why this priority**: Closes the breadth matrix (direct emission) and pins the two load-bearing safety invariants (pointer-not-truncated; scope is review_ref-only, other over-bound attrs still fail closed).

**Independent Test**: Call `emit_status_transition` with a prose ref and assert bounded broadcast; assert an over-bound *pointer* rides verbatim (codec fails closed loudly if the codec itself rejects it); assert an over-bound *non-review_ref* attr is still left to the codec (fails closed).

**Acceptance Scenarios**:

1. **Given** a direct `emit_status_transition` with a >240-byte prose ref and a clock-derived `at=`, **When** it emits, **Then** the moment broadcasts bounded.
2. **Given** an over-bound pointer-shaped `review_ref` (e.g. a filesystem path with spaces), **When** projected, **Then** it is passed through unchanged; if the codec still rejects it, the drop is loud (logged), never a silently corrupted broadcast.
3. **Given** an over-bound value on an attr other than `review_ref`, **When** projected, **Then** the interim does not touch it — codec fail-closed behavior is unchanged.

### Edge Cases

- Multi-byte UTF-8 codepoint sitting exactly on the 240-byte boundary → the cut never splits a codepoint; the trailing `…` (3 bytes) fits inside the budget (237-byte prefix + `…`).
- A prose note containing raw newlines/tabs → whitespace is collapsed to single spaces **before** the byte bound and **before** the codec's non-printable-character guard (order matters, else the newline drops the moment independently).
- A value that is prose but under 240 bytes after one-line collapse → collapsed, not ellipsised (no `…` unless truncated).
- `review_ref` absent/`None` → unchanged (no moment impact).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Bound prose review_ref before the codec | As the wire-projection seam, I bound a legacy-prose `review_ref` to ≤240 UTF-8 bytes before `to_zeitgeist_attrs` runs, so an overflow no longer drops the whole `WPStatusChanged` moment. | High | Open |
| FR-002 | Collapse to one line before bounding | As the seam, I collapse `review_ref` whitespace to single spaces (`" ".join(value.split())`) before the byte bound and before the printability guard, so newlines never independently drop the moment. | High | Open |
| FR-003 | Trailing ellipsis on truncation | As the seam, when I truncate I append a visible `…` within the 240-byte budget (237-byte prefix + `…`), codepoint-safe. | High | Open |
| FR-004 | Never truncate pointer-shaped values | As the seam, I pass pointer-shaped `review_ref` values through verbatim (scheme-URI, or a whitespace-free `<verb>:<id>` token, or a path with a separator and no line break), letting the codec fail closed loudly if it still rejects them. | High | Open |
| FR-005 | Preserve full local event text | As the mission, I bound only the wire projection; the canonical `status.events.jsonl` retains the full note (structurally: journal append precedes fan-out; the bridge has no journal write path). | High | Open |
| FR-006 | Exactly one publish offer per emitted event | As the seam, my transform converts a dropped (0-offer) moment into a valid (1-offer) broadcast and adds no offer; multi-hop commands still emit one offer per event. | High | Open |
| FR-007 | Breadth across transition families | As the mission, the bound applies to every otherwise-valid transition carrying prose `review_ref`: approval, completion, rejection/rework, and direct emission. | High | Open |
| FR-008 | Interim marking + INFO log + PR panel note | As the seam, I mark the change interim (`refs #3954`, `# SUNSET: remove when #4327 lands`) and log a truncation at INFO; the delivering PR body states that the human review panel does not render `review_ref`, so bounding it carries no operator-visible regression (this is the load-bearing rationale for why prose truncation is acceptable). | Medium | Open |
| FR-009 | Campsite: correct #4318 docstring | As campsite in the same file, I fix the stale `_first_non_printable_attr` docstring (names the 8.2.0 pin and a missing printability check that 9.1.6 now has). | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Byte-accurate bound | The bound is measured in UTF-8 **bytes** (`len(v.encode("utf-8")) <= 240`), byte-identical to the codec's own `_truncate_utf8` (237-byte prefix + `…`), verified by test. | Reliability | High | Open |
| NFR-002 | Deterministic re-emit | The transform is a pure value transform; re-emitting the same event yields byte-identical wire attrs (no nondeterminism). | Reliability | Medium | Open |
| NFR-003 | No added Git/network cost | Observable: a bounded broadcast makes exactly one publish offer and opens no additional Git/credential deadline versus a normal broadcast (one offer, one credential resolution). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Events pin unchanged | `spec-kitty-events` stays pinned `>=9,<10` (9.1.6); no events release or lock bump. | Technical | High | Open |
| C-002 | No edit to the events package | The codec (`spec_kitty_events.zeitgeist_attrs`) is an upstream CLIENT dependency; the bound lives CLI-side in `zeitgeist_bridge.py` only. | Technical | High | Open |
| C-003 | Single seam, no whack-a-field | One minimal helper in the bridge; do NOT duplicate the bound into `tasks_move_task.py`, `emit.py`, or the codec (parallel-authority risk vs #4336's source-side `summary` attr). | Technical | High | Open |
| C-004 | Out of scope = #4327/#4336 | No new event vocabulary / dedicated `summary` attr, no durable publisher (#4266, NOT_PLANNED), no `review_ref`→pointer-only, no change to move-task `--note` handling, no per-attr bounding beyond `review_ref`. | Business | High | Open |
| C-005 | KISS classifier | Minimal, pointer-biased structural classifier; no multi-regex/em-dash sentence detector (why Robert closed #4319). | Technical | Medium | Open |

### Key Entities

- **`review_ref` (wire attr)**: a `WPStatusChanged` payload field. Two shapes — a *pointer* (`<verb>:<id>` / URI / path) that must ride verbatim, and *legacy prose* (a copied `--note`) that must be bounded. Not in `UNBROADCAST_FIELDS[WPStatusChanged]`, so it reaches the wire.
- **`WPStatusChanged` moment**: the volatile broadcast for a status transition; dropped whole today when any attr overflows 240 bytes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `move-task --to approved` with a >240-byte review note broadcasts its `WPStatusChanged` moment (≥1 offer, exactly 1 per emitted event) — reproduced RED before the fix, GREEN after.
- **SC-002**: For every bounded broadcast, the persisted `status.events.jsonl` review note is byte-for-byte the full original (0 bytes lost locally).
- **SC-003**: A pointer-shaped `review_ref` is transmitted with 0 characters altered — including an over-240-byte, space-containing filesystem path (the load-bearing pointer case).
- **SC-004**: The regression matrix covers all four transition families (approval, completion, rejection/rework, direct emission) **and** the four safety cases — over-bound pointer rides verbatim (T5), codepoint boundary never split (T6), exactly-one-offer single-hop (T7), and an over-bound non-`review_ref` attr is untouched / still fails closed (T8) — with issue-pinned `@pytest.mark.regression` tests, each RED-first through the pre-existing entry point.

## Issue Matrix

| Issue | Title | Role | Claim | Verdict |
|-------|-------|------|-------|---------|
| [#3954](https://github.com/spec-kitty/spec-kitty/issues/3954) | Bound review_ref instead of dropping WPStatusChanged at the 240-byte bound (MVP interim) | Primary — this mission closes it | stijn-dejongh (assigned, `taken-by-human`) | _pending_ |
| [#4318](https://github.com/spec-kitty/spec-kitty/issues/4318) | Stale `_first_non_printable_attr` docstring (same file) | Campsite fold (FR-009) | folded | _pending_ |
| [#4327](https://github.com/spec-kitty/spec-kitty/issues/4327) / [#4336](https://github.com/spec-kitty/spec-kitty/issues/4336) | Dedicated inline `summary` attr; review_ref pointer-only | Explicitly OUT of scope (post-MVP) | separate | n/a |
| [#4266](https://github.com/spec-kitty/spec-kitty/issues/4266) | Durable publisher | Dead dependency (CLOSED/NOT_PLANNED) | n/a | n/a |

## Provenance

Grounded by a bounded, profile-loaded pre-spec squad (researcher-robbie, architect-alphonso, reviewer-renata) on canonical `spec-kitty/spec-kitty` @ `192ec02763` (v4.0.0rc3); all three lenses independently reproduced F-46 as CONFIRMED-ON-MAIN. Debrief: `work/mission-briefs/review-ref-wire-bound-3954-SYNTHESIZED.md`.
