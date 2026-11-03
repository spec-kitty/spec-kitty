# Implementation Plan: Lifecycle vocabulary parity pin

**Branch**: `issue-6876-lifecycle-vocabulary-parity` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/lifecycle-vocabulary-parity-01M6GSPC/spec.md`; grounded findings in [research.md](./research.md)

## Summary

Add one fast test module, `tests/status/test_lifecycle_events_package_parity.py`, that holds
`specify_cli.status.lifecycle_events`' twelve lifecycle constants and both membership sets to
the values `spec_kitty_events` publishes, and asserts that the CLI's set is a deliberate strict
subset of the package's wider vocabulary. The assertions compare **values**, never how a
constant is declared, so the pin passes unchanged when #6447 replaces the literals with an
import — and it never re-creates the static source parsing the deleted frozen tools used, which
is exactly what forced this issue open.

No production code changes. `src/specify_cli/status/lifecycle_events.py` is untouched (C-001).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `spec-kitty-events>=11.3.0,<12` (`specify_cli.status.lifecycle_events`, `spec_kitty_events` top-level exports); pytest
**Storage**: none
**Testing**: pytest, `tests/status/` (module marked `fast`), no fixture, no git repo, no network
**Target Platform**: Linux/macOS developer CLI + CI
**Project Type**: single (Python CLI/library)
**Performance Goals**: the new module runs in under 2 s (NFR-001); it is a module-import-time comparison, no I/O beyond importing two modules
**Constraints**: declaration-agnostic (FR-005); no new gate and no relaxed gate (C-002); no edit to the vocabulary module (C-001); core repo only (C-003)
**Scale/Scope**: one test module (~120 lines) plus a changelog fragment

## Charter Check

*GATE: charter context loaded for `specify`/`plan`.*

- **Single canonical authority** (charter, Governing Principles): the package is the owning
  authority for the twelve values; the CLI's copy is an implementation detail. The pin asserts
  the copy against the authority it *claims* to mirror. Compliant — the test introduces no new
  source of truth, it compares two existing ones.
- **DIRECTIVE_041 (test only where it guards real behaviour or a standing invariant)**: the
  standing invariant is "the CLI emits exactly the twelve canonical lifecycle strings". Until
  `a212ccdf55`, the deleted contract tools were its only guard; there is none now. Compliant.
- **DIRECTIVE_034 (red-first)**: no defect is being fixed here, so there is no defect repro to
  write first. Instead the guard's teeth are proved by a recorded mutation audit (mutate a
  literal, observe the named red, revert) — SC-001. Stated plainly in the PR body.
- **NO_FULL_HEAVY_SUITES_IN_MISSION**: only the targeted `tests/status` slice plus the gate
  checks the PR itself touches.
- **DIRECTIVE_024/025 (locality vs boy-scout)**: the change is additive and sits next to the
  module it guards; it does not opportunistically edit `lifecycle_events.py` (that would collide
  with the parked #6447 branch, C-001).

No blocking charter gates.

## Project Structure

### Documentation (this mission)

```
kitty-specs/lifecycle-vocabulary-parity-01M6GSPC/
├── spec.md              # authored
├── research.md          # discovery findings D-1 .. D-5 (grounding: the freeze exited)
├── plan.md              # this file
└── tasks.md             # Phase 2 (/spec-kitty.tasks — not created here)
```

### Source Code (repository root)

```
tests/
└── status/
    ├── test_lifecycle_events.py                    # existing; unchanged
    └── test_lifecycle_events_package_parity.py     # NEW — the pin (WP01)
docs/changelog/unreleased/
└── <pr>.internal.md                                # NEW — non-user-facing fragment (WP01)
```

**Structure Decision**: the guard belongs where the module's own tests live (`tests/status/`),
so a drift is reported by the suite an editor of that module already runs. It is deliberately
not an `tests/architectural/` gate: it asserts runtime values, not source shape — the mistake
that made the old tools block the import.

## Implementation Concern Map

> Concerns are not work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — The parity assertion set

- **Purpose**: one parameterized comparison per constant (twelve) plus the two membership
  sets, each failure naming the constant and both values; a missing package attribute must
  surface as a named failure, not an unhandled `AttributeError` (FR-004).
- **Relevant requirements**: FR-001, FR-002, FR-004, FR-005, NFR-001.
- **Affected surfaces**: `tests/status/test_lifecycle_events_package_parity.py`.
- **Sequencing/depends-on**: none.
- **Risks**: asserting via the CLI's own constants (tautology) — the comparison must read the
  package attribute by name; asserting the literal *declaration* would rebuild the old freeze.

### IC-02 — The narrower-by-design assertion

- **Purpose**: assert `LIFECYCLE_EVENT_TYPES` is a strict subset of the package's wide
  vocabulary, with the reason in the docstring, so a future "just derive it from the package"
  edit is caught rather than silently widening repair-preservation.
- **Relevant requirements**: FR-003, FR-002.
- **Affected surfaces**: same module.
- **Sequencing/depends-on**: IC-01.
- **Measured correction (11.3.0)**: the package publishes **two** relevant sets, and neither
  alone is the CLI's vocabulary — `CANONICAL_LIFECYCLE_EVENT_TYPES` (13) lacks
  `MissionCreated`, `MissionReopened`, `FollowUpRecorded`; `MISSION_EVENT_TYPES` (9) lacks the
  nine project/spec/plan/tasks/WP types. The plan therefore asserts against their **union**
  (22 members): CLI ⊂ union, strictly, with ten members the CLI deliberately does not emit —
  which is exactly the "wider by ten" comparison the issue records. A naive assertion against
  `CANONICAL_LIFECYCLE_EVENT_TYPES` alone would be red on the unmodified tree.
- **Risks**: the union grows as the package adds types — the assertion is subset/strictness, not
  an exact difference set, so a package addition stays green; a package *removal* below the
  CLI's twelve is a red that asks for a decision.

### IC-03 — Fragment and evidence

- **Purpose**: the changelog fragment (`internal` section — no user-facing behaviour change)
  and the recorded mutation audit that proves SC-001/SC-003.
- **Relevant requirements**: SC-001, SC-002, SC-003.
- **Affected surfaces**: `docs/changelog/unreleased/<pr>.internal.md`; PR body `## Tests run`.
- **Sequencing/depends-on**: IC-01, IC-02.

## Testing Strategy

1. **Green on the unmodified tree**: `uv run pytest tests/status/test_lifecycle_events_package_parity.py -q`.
2. **Teeth (SC-001)**: copy the module aside, change `TASKS_STARTED` to `"TaskStarted"` in
   `src/specify_cli/status/lifecycle_events.py`, re-run, confirm the parity case for
   `TASKS_STARTED` fails and names the value pair; restore byte-for-byte
   (`git checkout -- <path>`), confirm green.
3. **Membership teeth (SC-002 of US2)**: drop a member from `LIFECYCLE_EVENT_TYPES`, confirm
   the membership case fails; restore.
4. **Declaration-agnostic (SC-003 / FR-005)**: apply the #6447 import locally (kept out of the
   branch), re-run the module, confirm green; restore.
5. **Suite slice**: `uv run pytest tests/status -q -k lifecycle` plus the module; ruff check and
   format on the new file.

## Risks

- **Over-pinning**: an assertion on how the constants are declared would re-freeze the copy and
  block #6447. Mitigation: values only; SC-003 proves it.
- **Duplicating #6447**: editing `lifecycle_events.py` here. Mitigation: C-001, no edit.
- **A brittle strict-subset assertion**: if the package's wide set ever narrows below the CLI's,
  the test fails and asks for a decision — intended, and stated in the docstring so the failure
  is read as a prompt, not a mystery.

## Definition of Done

- The new module passes on the unmodified tree and fails, naming the constant, under each of the
  three recorded mutations (literal drift, membership change, and — as a pass, not a failure —
  the import form).
- `src/specify_cli/status/lifecycle_events.py` is byte-identical to `origin/main` in the PR diff.
- Changelog fragment present and valid; PR body validated by `validate-pr-body.py`.
