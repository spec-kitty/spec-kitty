---
title: 'ADR: allowlist ratchets are priced debt'
description: 'Accepted: an allowlist ratchet costs CI money on every run and keeps a known defect alive, so it is owned, time-boxed and drained; a defect-class gate closes with no allowlist.'
status: Accepted
date: '2026-09-30'
---

# ADR: allowlist ratchets are priced debt

**Status:** Accepted

**Date:** 2026-09-30

**Deciders:** Stijn Dejongh (owner), ruling of 2026-09-30.

**Technical Story:** Mission `git-paths-are-data-01M3SSXR`
([#5392](https://github.com/spec-kitty/spec-kitty/issues/5392),
[#5400](https://github.com/spec-kitty/spec-kitty/issues/5400)).

---

## Context and Problem Statement

`DIRECTIVE_043` tells us to close a recurring defect class with a structural gate. In
practice the gate usually ships with a shrink-only allowlist: the current offenders are
frozen in a list or a count in `tests/architectural/_baselines.yaml`, and the gate only
stops the list from growing. Charter standing order 5 named that allowlist as part of the
fix.

That shape has two costs we were not counting:

- **It costs money on every CI run.** Every allowlisted entry is scanned again on every
  pull request, every push and every nightly run. The cost does not stop when the mission
  that added the ratchet closes.
- **It keeps a known defect alive.** An allowlisted site is a site we already know is
  wrong. Allowlists outlive their missions: nobody owns the burn-down, and the entries stay.

The 2026-09-14 census ruling
([`2026-09-14-1-census-floor-ratchet-adjudication.md`](../3.x/2026-09-14-1-census-floor-ratchet-adjudication.md))
already showed the maintenance side of this: an estimated 40 of the last 70
baseline-maintenance commits went to four census ratchets whose measured catch record was
at or near zero. That ADR judged four
specific gates. This one sets the rule for all of them.

The owner's ruling, 2026-09-30:

> "Regarding those ratchets: we should start considering them very expensive debt. As
> they cost us money on every single CI run. Make note of this, and ensure it is stored in
> our ADRs / charter as part of the git issue remediation mission."

## Decision Drivers

- The recurring CI cost of a ratchet, paid on every run for as long as it exists.
- A ratchet keeps known defects in the codebase; a gate should end the class, not freeze it.
- `DIRECTIVE_043` still applies: a gate must be non-vacuous, with a concrete floor and a
  self-mutation test.
- Single canonical authority: one baseline file, one rule for when an entry may exist.

## Considered Options

1. Keep shrink-only ratchets as the standard way to close a defect class.
2. Ban allowlists entirely.
3. Treat every allowlist as priced debt: owned, time-boxed, and drained, with an
   empty-allowlist invariant as the default closing state.

## Decision Outcome

**Chosen option:** 3, because it removes the recurring cost without blocking the rare case
where a class cannot be drained in one mission.

- A shrink-only allowlist ratchet is **debt with a price**. Every entry is re-scanned on
  every CI run and keeps a known defect alive.
- The **default closing state** of a defect-class gate is an **empty-allowlist
  invariant**: the gate forbids the pattern everywhere except the canonical owner.
- A **new gate** is added only when it can start empty, or in the same mission that
  drains it to empty.
- A **transient allowlist** needs a tracker issue, a named owner and an exit date, and is
  recorded in `tests/architectural/_baselines.yaml`. A gate with no allowlist needs no
  baseline entry.
- Existing ratchets are drained as campsite work when a mission touches their surface.
  A ratchet with no owner or exit date is a finding, not a baseline to re-pin.

This relates to, and does not supersede, the 2026-09-14 census ruling. Its per-gate
verdicts stand.

**First application.** Mission `git-paths-are-data-01M3SSXR` closes the git path-listing
class with `tests/architectural/test_git_path_listing_owner.py`, which ships with an empty
allowlist. The hand-built git runners that do not list paths could not be drained in the
same mission, so they became follow-up issue
[#5475](https://github.com/spec-kitty/spec-kitty/issues/5475), whose gate is added only
once it can start empty. They were not added as allowlist entries.

### Consequences

#### Positive

- CI stops paying, run after run, for defects we have already decided to remove.
- Each defect-class gate has a clear finish line: an empty allowlist.
- Every remaining allowlist has someone who answers for it and a date to meet.

#### Negative

- Closing a class takes more work up front: the offenders are migrated in the same
  mission instead of frozen.
- A class too large for one mission waits for its gate until the drain is planned, so it
  has only review cover in the meantime.

#### Neutral

- `DIRECTIVE_043` and the `architectural-gate-non-vacuity` tactic are unchanged in
  substance. The built-in `frozen-baseline-shrink-only-ratchet` tactic gains a generic
  cost caveat; the CI-cost rationale lives in the internal pack
  (`spec-kitty-ratchet-cost` tactic), not in consumer doctrine.

### Confirmation

- Charter standing order 5 and Burn-down Policy (a) state the rule.
- The next gate that lands does so with an empty allowlist, or with a drain mission.
- The count of non-zero entries in `tests/architectural/_baselines.yaml` goes down over
  the 4.x line, and none is added without an issue, an owner and an exit date.

## Pros and Cons of the Options

### 1. Keep shrink-only ratchets

**Pros:** cheapest way to land a gate; no migration needed.

**Cons:** the cost recurs on every run with no end; entries outlive their missions; the
defect class stays open.

### 2. Ban allowlists entirely

**Pros:** no ratchet cost ever.

**Cons:** a class too large for one mission could never get a gate until fully drained,
and a necessary short-lived exception would have to be forced through anyway.

### 3. Priced debt, empty by default (chosen)

**Pros:** removes the recurring cost in the normal case; keeps an escape hatch that is
visible, owned and dated.

**Cons:** more up-front work per gate; needs review to hold the owner and exit date.

## More Information

- Owner ruling: Stijn Dejongh, 2026-09-30 (quoted above).
- Related ADR: [`2026-09-14-1-census-floor-ratchet-adjudication.md`](../3.x/2026-09-14-1-census-floor-ratchet-adjudication.md).
- Mission: `kitty-specs/git-paths-are-data-01M3SSXR/` (FR-009 to FR-012), issues
  [#5392](https://github.com/spec-kitty/spec-kitty/issues/5392) and
  [#5400](https://github.com/spec-kitty/spec-kitty/issues/5400).
- Follow-up: [#5475](https://github.com/spec-kitty/spec-kitty/issues/5475), route the
  remaining hand-built git runners and `worktree list` parsing through `kernel.git`.
- Doctrine: `.kittify/charter/charter.md` (standing order 5, Burn-down Policy),
  `packs/built-in/tactics/frozen-baseline-shrink-only-ratchet.tactic.yaml`,
  `packs/internal/tactics/spec-kitty-ratchet-cost.tactic.yaml`.
