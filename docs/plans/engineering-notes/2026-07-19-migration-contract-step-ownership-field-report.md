---
title: 'Field report: a migration-contract step with no owning WP (caught at closeout, not planning)'
description: 'Field report: a #2684 staged migration passed every planning gate with a contract step no WP owned, caught only at closeout. Proposes a step-ownership lint.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- kitty-specs/wp-runtime-state-eviction-01KXWN13/contracts/migration.md
- kitty-specs/wp-runtime-state-eviction-01KXWN13/tasks.md
- docs/plans/engineering-notes/2026-07-18-doctrine-driven-p0-remediation-field-report.md
- .kittify/charter/charter.md
---

# Field report: a migration-contract step with no owning WP

**Date:** 2026-07-19 · **Agent run:** implement-review orchestration (Claude Code, Opus,
per-WP subagents) · **Human-in-command:** maintainer (operator) · **Mission:**
`wp-runtime-state-eviction-01KXWN13` (#2684 — evict runtime-mutable WP state into the
append-only event log) · **Outcome so far:** 9/10 WPs approved; the 10th (closeout) surfaced
a mission-scoping gap that the operator resolved by re-scoping (ship dual-write, defer the
corpus cutover).

This note is for maintainers weighing *what the planning gates do and do not catch*. It
records one gap — a step in the mission's own declared migration contract that no work
package owned — and proposes a cheap structural check that would have caught it at the
post-tasks point-cut instead of at closeout.

## The contract, and the gap

The mission declared a strict, ordered migration contract in
`contracts/migration.md`:

```
backfill → verify(FAIL-CLOSED) → reader cutover → writer cutover → delete fallbacks → hash guard
```

The work-package decomposition (10 WPs) covered the two ends well:

- The **event infrastructure**, reducer fold, emit API, and per-field readers/writers were
  each owned (WP01–WP09), and each landed its reader/writer **behind a phase-1 flag**
  (`_phase1_dual_write_enabled`, default **OFF** → legacy frontmatter stays authoritative).
  This is the correct shape for a *safe additive increment*: dual-write, nothing flips yet.
- The **terminal steps** — "delete fallbacks" and "verify no shim survives" — were owned by
  the closeout WP10 (T037 / T036).

But the **middle** of the contract had no owner:

- **No WP wired the runtime-state `backfill → verify → cutover` CLI.** The backfill *library*
  existed (WP03), but nothing invoked it: `migrate_cmd.py` only had identity/topology
  backfills, and `migration/runner.py` is the `.kittify`-layout migration, not the event
  backfill.
- **No WP flipped the flag unconditional.** WP10's T036 was written assuming each field
  vertical "tears down its own dual-write" as part of its atomic switch — but the verticals
  landed dual-write *behind the flag* and none removed the OFF branch. The assumption was
  plausible-but-wrong, and never cross-checked against the verticals' actual scopes.

Result: WP10 was told to *delete the fallbacks* (the last contract step) while the steps that
must precede it (a wired, verified backfill; an unconditional cutover) were produced by no
one. The precondition chain was broken in the middle.

## Why every gate passed anyway

The gap survived **finalize-tasks**, **three adversarial squads** (post-spec, post-plan,
post-tasks), and **/analyze**. None of them is wrong; none of them checks the thing that was
missing:

- **finalize-tasks** validates `owned_files` non-overlap and **requirement coverage** — every
  `FR-###` maps to ≥1 WP. FR-005 ("reader cutover") *was* referenced by WP05 and WP10, so
  coverage was satisfied. Coverage counts **references to a requirement**, not **completion of
  that requirement's own multi-step contract**.
- **/analyze** checks FR→task coverage, duplication, ambiguity, and charter alignment. Its
  coverage table (`FR-005 reader cutover → WP05, WP10`) was green. It has no notion of "this
  requirement is delivered by an ordered contract; does every *step* have an owner?"
- **The dependency graph** encoded WP10 depends on WP04–WP09, but nothing asserted WP10's
  *contract preconditions* (a merged+verified backfill) were **produced by an ancestor**. A
  dep edge says "runs after," not "precondition satisfied by."

So a requirement can read as "covered" while the terminal step of its contract silently has
no owner — or is placed in a WP whose precondition no WP produces. The blind spot is
orthogonal to the mission's own theme (single canonical authority); it's about **migration
sequencing ownership**.

## Caught at closeout (the loop working, expensively)

The WP10 implementer, instructed to delete the fallbacks, investigated the base first, found
the precondition chain broken, and **STOPPED** — refusing to force an unsafe cross-lane
cascade across ~12 files in already-approved WPs, and refusing to fake green (both
STOP-authorized in its prompt). It filed a structured blocker. The operator then made the
scoping call: **ship the dual-write end-state now, defer the corpus cutover** (wire backfill,
flip the flag, delete fallbacks) to a follow-up mission — which is what the staged contract
*already implied*: deleting a migration's fallbacks belongs after the corpus migration, in the
same bucket as the already-deferred IC-08 reduction.

That is the right outcome — but it was reached at the most expensive point (a full closeout
WP dispatched, investigated, and re-scoped), when the same conclusion was available at
post-tasks from the artifacts alone.

## Recommendation: a post-tasks contract-step-ownership lint

When a mission declares a **sequenced contract** — an ordered step list in `contracts/*.md`,
a lifecycle/state-machine, or a migration order — add a structural check (finalize-tasks
validate pass, or a post-tasks squad lens) that asserts:

1. **Every declared step maps to an owning WP.** Flag an **orphan contract step** — a step in
   the ordered contract that no WP's scope/subtasks claim. ("`backfill → verify → cutover` is
   named in migration.md but owned by no WP.")
2. **Every step's declared precondition is produced by a dependency-graph ancestor.** Flag a
   **precondition inversion** — a WP performs step *N* but no ancestor produces step *N-1*'s
   output. ("WP10 deletes fallbacks; its precondition *backfill merged + verify passed* has no
   producing ancestor.")

Both are cheap and purely structural (parse the ordered steps; intersect with WP scopes;
walk the dep graph). Both would have fired at post-tasks — where re-scoping is a one-paragraph
edit — instead of at closeout. This complements, not replaces, FR-coverage: FR-coverage asks
"is the requirement referenced?"; this asks "is the requirement's *contract* wholly owned and
correctly ordered?"

A lighter, doctrine-only version: make "does every step of every declared contract have an
owner, and is its precondition produced upstream?" an explicit lens in the **post-tasks
anti-laziness squad** checklist. The squad already reads `contracts/` and `tasks.md`; it just
wasn't pointed at step-ownership.

## Takeaway

**FR-coverage ≠ contract-step-coverage.** A staged-migration mission can pass every existing
planning gate while a middle step of its own contract has no owner, because the gates count
requirement *references* and validate *file ownership*, not *ordered-contract completeness*.
The dual-write increment the verticals shipped was correct and safe; what was missing was an
owner for the cutover that turns it on, and a check that would have named that absence during
planning. The blocker was caught — by an implementer that stopped instead of forcing green,
and an operator who owned the scope call — but one structural lint would move this whole class
of finding from "discovered at closeout" to "flagged at post-tasks."
