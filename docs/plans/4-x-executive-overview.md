---
title: '4.x Executive Overview'
description: 'Summary of the 4.x cycle for decision owners: where 4.0.0 stands, what the release candidates delivered, what still gates GA, and the calls to make.'
doc_status: active
type: explanation
updated: '2026-10-12'
audience: docs/context/audience/external/product-manager-evaluator.md
related:
- docs/plans/4-0-0-milestone-roadmap.md
- docs/changelog/4.0.0.md
- docs/changelog/index.md
- docs/context/team-kitty.md
- docs/plans/index.md
---

# 4.x Executive Overview

*A point-in-time summary for decision owners (CEO, CPO, CTO, PO), read against the live
tracker on 2026-10-06. It replaces the
[3.2.x Executive Overview](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/3-2-x-executive-overview.md).
The operator detail is in the [4.0.0 Milestone Roadmap](4-0-0-milestone-roadmap.md). What
actually shipped is in the [changelog](../changelog/index.md). Counts below are a snapshot:
check the [4.0.0 release scope milestone](https://github.com/spec-kitty/spec-kitty/milestone/11)
for today's numbers.*

## Bottom line

4.0.0 is close. Five release candidates have shipped. **GA now ships "done when done" — it is
no longer pinned to a date** (direction update, 12 October); release candidates keep going out
to early adopters off `main` in the meantime. The GA gate has also **grown beyond local
integrity**: alongside the data-safety work, it now covers **charter modular extraction** and
the **mission-status API backend** (the open-core producer surface). The local-integrity leg
stands at **210 items closed, with 14 open**. Most of the cycle went into one thing customers
will feel directly: **the CLI no longer loses or overwrites their work without saying so**.
Every data-safety P0 that was open on 1 October has closed. One P0 is left on that leg, a red
performance suite in the nightly. The open questions are when to ship rc6, and whether two new
collaboration P0s belong in 4.0.0.

## Where 4.0.0 stands

| Item | State |
| --- | --- |
| Last 3.x release | 3.2.7, 2026-09-10 |
| Release candidates shipped | rc1 (09-13), rc2 (09-14), rc3 (09-17), rc4 (09-21), rc5 (10-02) |
| Next candidate | rc6, open on `main` with the `consolidate` fixes made after rc5 |
| GA timing | done-when-done — not date-gated; RCs keep shipping to early adopters off `main` |
| GA gate | three legs: local integrity ([milestone 11](https://github.com/spec-kitty/spec-kitty/milestone/11): 210 closed, 14 open) · charter modular extraction (#645) · the mission-status API backend (#5528) |
| Nightly | 56 of 57 jobs green on 2026-10-06; not fully green since 2026-09-15 |
| After GA | [CLI 4.x stable](https://github.com/spec-kitty/spec-kitty/milestone/12) (milestone 12) and [4.x Work](https://github.com/spec-kitty/spec-kitty/milestone/8) (milestone 8) |

The GA gate is now three legs (local integrity, charter extraction, the mission-status API
backend), not milestone 11 alone. An issue on 4.x Work or CLI 4.x stable is planned work, not a
release blocker, unless it is one of those three legs.

## What the release candidates delivered

**Customers stop losing work.** This is the bulk of the cycle. Of the 201 closed GA issues,
119 were P0. The recurring pattern was a command that exited successfully while it deleted,
overwrote or silently dropped something the user wrote. Examples now fixed:

- `init`, `upgrade`, `migrate` and `agent config remove` no longer delete user-authored
  templates, skills, commands or settings.
- Consolidating a mission (formerly `merge`) no longer discards uncommitted edits, no longer
  lands code from a canceled work package, and now restores the branches it moved when it
  fails.
- Concurrent review and acceptance verdicts no longer overwrite each other.
- After rc5, `consolidate` stopped landing commits made after a work package was approved,
  and a failed run no longer resets past a teammate's commit. These fixes reach users with
  rc6. One visible effect: a mission approved before rc5 must have its work packages reviewed
  again, or attested, before it lands.

**Windows works again.** rc3 was unusable on Windows. rc4 repaired it on one shared
foundation for locking, safe deletion and OS detection.

**Hosted interaction is opt-in (rc5).** A fresh install sends nothing to a hosted endpoint.
Sending starts only when both the repository and the individual developer turn it on, and no
environment variable can turn it on. The old "sync" transport, with its daemon and offline
queue, was retired in August. Team Kitty now receives status moments through a per-team relay
(Zeitgeist). See [Team Kitty and Zeitgeist](../context/team-kitty.md).

**Clearer naming.** The command that combines a mission's lanes is now
`spec-kitty consolidate` (rc5). Its old name, `merge`, suggested it published to origin, which
it never does. The old name prints a migration message and does nothing. This is the one breaking change scripts must act on.

**Faster everyday use.** A warm `doctor` went from about 13 s to about 1.4 s in local
measurement.

## What still gates GA

The GA gate now has **three legs**. Leg 1 is local integrity (milestone 11, 14 open, read
2026-10-06); legs 2 and 3 are structural pieces promoted onto the gate on 12 October.

**Leg 1 — local integrity (milestone 11), by kind:**

| Kind | Issues | What it means |
| --- | --- | --- |
| Nightly | #5419 (P0) | The performance suite is the one red job. A release candidate needs a green nightly; rc5 shipped under a logged waiver. |
| Correctness residuals | #5638, #5704, #5726 (P2) | Smaller bugs in the landing and create paths. |
| Agent integration | #702 (P1) | Codex skill files drift from their manifest. |
| Hygiene and docs | #2560, #2561, #2562, #3732, #4836, #5428, #5538, #5629, #5715 (P2/P3) | Structural clean-up and docs; non-gating items can move after GA. |

**Leg 2 — charter modular extraction.** #645 moves the ~129 `specify_cli → charter` imports
onto the stable charter API so the charter can be released as its own external contract
package in its own repository.

**Leg 3 — the mission-status API backend.** The open-core producer surface (#5528) — the
stable entry point to ledger and event data the free CLI exposes — ships its backend, with the
contract canonical beside the Python reducer.

Two P0s and two P1s are open **without a milestone**:

- #5780 and #5758 (P0): in a team where several people work from their own clones, a
  teammate's pushed rejection of a work package is ignored, so rejected work can still land.
- #5722 and #5603 (P1): the automation entry point that lands work has none of the
  protections the `consolidate` command has.

Our policy is that `main` stays honestly red on known P0s instead of hiding them. The nightly
reds are that policy working, not an outage.

## What moved — out of 4.0.0, and (newly) onto the gate

From the original [4.0.0 declaration](../changelog/4.0.0.md), still off the GA gate:

- **The structural "one execution context" work** (#1619) was about 70% done (31 of 44
  sub-issues) on 2026-10-01 and sits on CLI 4.x stable. It continues after GA.
- **The hosted *backend*** (zeitgeist auth, the hosted backend, the SaaS surface) stays frozen
  while the commercial vision is reviewed. Nothing hosted-backend gates GA.
- **Hosted "sync"** as the declaration describes it no longer exists. Its goals (never report
  success while state is stranded, consent before egress) are now carried by the relay model
  and the opt-in above.

Newly promoted **onto** the GA gate (12 October): **charter modular extraction** and the
**mission-status API backend** — two pieces of the open-core structural finish that the
2026-10-06 synthesis had placed after GA. And re-scoped, not frozen: **Team Kitty is now
"Multiplayer Mode," the consumer side** of the open-core producer API — consumer-side
UI/multiplayer on that API, and the produce/drain adapter seam, are no longer blocked, while
the hosted backend stays frozen. The roadmap was re-anchored to this direction on 12 October
(#5428).

## Calls that need product ownership

1. **When to ship rc6.** Users on rc5 have the known `consolidate` defects until it ships. The
   release rule needs a green nightly; the last run had one red job (#5419). Wait for it, or
   waive the rule again as was done for rc5. (RCs keep shipping to early adopters regardless of
   the GA date, which no longer exists.)
2. **Whether #5780 and #5758 are in 4.0.0.** Both mean a teammate's rejection can be ignored.
   Neither has an owner or a milestone.
3. **Scope at each release candidate, not a date.** GA is done-when-done, so the cut-off is a
   judgment call per RC: a non-gating item moves to CLI 4.x stable with a rationale rather than
   holding the release. Intake is high: 159 issues were opened in the four days after rc5
   against 90 closed.
4. **Charter extraction and the mission-status API backend are now GA-gating.** They are two of
   the three gate legs, promoted on 12 October from "after GA." Resourcing them is now a
   release decision, not a 4.x-line one.
5. **How GA relates to the Team Kitty backend: still decided.** GA does not wait on the hosted
   backend (frozen). Team Kitty is re-framed as "Multiplayer Mode," the consumer side of the
   open-core producer API; its consumer work and the adapter seam are unblocked.

**In one sentence:** *4.0.0 turned a CLI that could quietly lose customer work into one that
refuses instead of guessing — and GA now also waits on the charter becoming its own package
and the open-core mission-status API backend, shipping when those are done rather than on a
fixed date.*
