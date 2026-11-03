# Work Packages: Lifecycle vocabulary parity pin

**Inputs**: Design documents from `kitty-specs/lifecycle-vocabulary-parity-01M6GSPC/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (grounding D-1 .. D-5)
**Issue**: [#6876](https://github.com/spec-kitty/spec-kitty/issues/6876)

**Tests**: this mission *is* a test. The guard's teeth are proved by a recorded mutation audit
(mutate a literal → named red → revert), not by a defect repro, because #6876 asks for the
assertion the deleted frozen contract tools used to carry, and there is no defect left in core to
reproduce.

**Organization**: one work package. The change is one additive test module plus its changelog
fragment; splitting it would separate the assertion from the evidence that it bites.

**Prompt Files**: `/tasks/WP01-lifecycle-package-parity.md`.

## Path Conventions

- Tests: `tests/…`; changelog fragment: `docs/changelog/unreleased/<id>.internal.md`.
- `src/specify_cli/status/lifecycle_events.py` is **read-only for this mission** (C-001): the
  literal deletion belongs to #6447's parked mission.

---

## Work Package WP01: Pin the twelve lifecycle constants to `spec_kitty_events` (Priority: P1)

**Goal**: a drifted lifecycle literal, or a change to the CLI's lifecycle membership, is a named
red in core's fast status suite instead of a silent divergence from the package that publishes
those values.
**Independent Test**: `uv run pytest tests/status/test_lifecycle_events_package_parity.py -q` is
green on the unmodified tree; changing one literal to a plausible sibling value makes exactly that
constant's case fail and name both values; the same module stays green when the literals are
replaced by the #6447 import.
**Prompt**: `/tasks/WP01-lifecycle-package-parity.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Write the parity module: one parameterized case per constant comparing the CLI constant with the same-named `spec_kitty_events` attribute, naming both values on mismatch
T002 Assert the two membership sets exactly (`LIFECYCLE_EVENT_TYPES` = the twelve, `POST_MISSION_LIFECYCLE_EVENT_TYPES` = the two, post-mission ⊆ lifecycle)
T003 Assert the CLI's set is a strict subset of the package's wide vocabulary (`CANONICAL_LIFECYCLE_EVENT_TYPES | MISSION_EVENT_TYPES`, 22 members in 11.3.0) and record why it is deliberately narrower
T004 Prove the teeth: mutate one literal and confirm the named red; drop a member and confirm the membership red; restore byte-for-byte
T005 Prove declaration-agnosticism: apply the #6447 import locally, re-run green, restore (not committed)
T006 Changelog fragment `docs/changelog/unreleased/6876-lifecycle-vocabulary-parity.internal.md`; rename to `<pr>.internal.md` once the PR number is known
T007 Run the targeted suite slice plus ruff check/format; record the self-review

### Implementation Notes

- Compare **values**, never declarations. Reading the module's source with `ast` is exactly the
  design that forced #6876 open; do not reintroduce it, even in a test.
- Take the package side by name from `spec_kitty_events` (all twelve are top-level in
  `>=11.3.0,<12`), not from a hand-written expected-value table — a table would be a third copy.
- A missing package attribute must fail as a named assertion (`FR-004`), so resolve it with an
  explicit existence check and a `pytest.fail` naming the symbol, not a bare `getattr`.
- The module is `fast`, needs no fixture, no git repo and no temp dir (NFR-001); keep imports at
  module top so a broken `spec_kitty_events` install fails loudly at collection.
- Do not touch `tests/status/test_lifecycle_events.py`; it is the module's behavioural suite and
  stays green unchanged.

### Parallel Opportunities

None: one file.

### Risks

- An assertion against `CANONICAL_LIFECYCLE_EVENT_TYPES` alone is red on the unmodified tree
  (three of the twelve are `MISSION_EVENT_TYPES` members) — use the union, as measured.
- A test that asserts the *declaration* form re-freezes the copy and blocks #6447.
- Over-asserting the exact difference set (ten members today) makes a future package addition a
  failure that is not a defect; assert subset plus strictness instead.

### Dependencies

None. Independent of #6447 (it must stay green before *and* after that import).
