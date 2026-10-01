---
title: '4.x Executive Overview'
description: 'Summary of the 4.x cycle for decision owners: where 4.0.0 stands, what the release candidates delivered, what still gates GA, and the calls to make.'
doc_status: active
type: explanation
updated: '2026-10-01'
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
tracker on 2026-10-01. It replaces the
[3.2.x Executive Overview](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/3-2-x-executive-overview.md).
The operator detail is in the [4.0.0 Milestone Roadmap](4-0-0-milestone-roadmap.md). What
actually shipped is in the [changelog](../changelog/index.md). Counts below are a snapshot:
check the [4.0.0 release scope milestone](https://github.com/spec-kitty/spec-kitty/milestone/11)
for today's numbers.*

## Bottom line

4.0.0 is close. Four release candidates have shipped, and the GA gate stands at **146 of 162
issues closed, with 16 open**. Most of the cycle went into one thing customers will feel
directly: **the CLI no longer loses or overwrites their work without saying so**. The
remaining GA work is a short, named list, mostly data-safety bugs in `consolidate` and red
nightly test runs. The main open question is when to call GA, not whether the release is
sound.

## Where 4.0.0 stands

| Item | State |
| --- | --- |
| Last 3.x release | 3.2.7, 2026-09-10 |
| Release candidates shipped | rc1 (09-13), rc2 (09-14), rc3 (09-15), rc4 (09-21) |
| Next candidate | rc5, open on `main` |
| GA gate | [milestone 11](https://github.com/spec-kitty/spec-kitty/milestone/11): 146 closed, 16 open |
| After GA | [CLI 4.x stable](https://github.com/spec-kitty/spec-kitty/milestone/12) (milestone 12) and [4.x Work](https://github.com/spec-kitty/spec-kitty/milestone/8) (milestone 8) |

Only milestone 11 gates GA. An issue on 4.x Work or CLI 4.x stable is planned work, not a
release blocker.

## What the release candidates delivered

**Customers stop losing work.** This is the bulk of the cycle. Of the 142 closed GA issues,
89 were P0. The recurring pattern was a command that exited successfully while it deleted,
overwrote or silently dropped something the user wrote. Examples now fixed:

- `init`, `upgrade`, `migrate` and `agent config remove` no longer delete user-authored
  templates, skills, commands or settings.
- Consolidating a mission (formerly `merge`) no longer discards uncommitted edits, no longer
  lands code from a canceled work package, and now restores the branches it moved when it
  fails.
- Concurrent review and acceptance verdicts no longer overwrite each other.

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

The 16 open issues on milestone 11 (read 2026-10-01), by kind:

| Kind | Issues | What it means |
| --- | --- | --- |
| Consolidation data safety | #5392, #5400, #5440 (P0), #5385 (P1) | Ways consolidation can still overwrite or delete ignored local files or trip over status files the CLI itself committed, and one rollback path that is not yet covered. |
| Workflow and status correctness | #3931, #5390, #5409, #5513, #5519 (P0) | A work package prompt that the status tool then blocks; a copied project that moves the original's progress; a charter option that is advertised but rejected; status and decision events that split between two checkouts of the same mission. |
| Nightly test runs | #5258, #5418, #5419, #5505, #5506, #5507 (P0) | Six nightly suites are red. A green nightly is a condition for cutting rc5. |
| Engineering hygiene | #5428 (P2) | Docs cleanup after the 4.x re-anchor. |

Our policy is that `main` stays honestly red on known P0s instead of hiding them. The nightly
reds are that policy working, not an outage.

## What moved out of 4.0.0

Two things the original [4.0.0 declaration](../changelog/4.0.0.md) promised are no longer on
the GA gate:

- **The structural "one execution context" work** (#1619) is about 70% done (31 of 44
  sub-issues) and now sits on CLI 4.x stable. It continues after GA.
- **Hosted collaboration as a whole** is off the critical path. On 2026-10-01 the CEO, CPO
  and CTO froze Team Kitty / SaaS work while the commercial vision is reviewed. Nothing
  hosted gates GA; all external interaction will flow through the CLI's adapter module.
- **Hosted "sync"** as the declaration describes it no longer exists. Its goals (never report
  success while state is stranded, consent before egress) are now carried by the relay model
  and the opt-in above. The roadmap and the declaration were re-anchored on 2026-10-01; the
  remaining docs cleanup is tracked in #5428.

## Calls that need product ownership

1. **When to cut rc5.** The code it waits on has landed. It also needs a green nightly, and
   six nightly suites are red.
2. **Whether milestone 11 is the final GA scope.** If it is, GA is the 16 issues above. If new
   P0s keep landing on it, set a cut-off.
3. **How GA relates to the Team Kitty launch: decided 2026-10-01.** It does not wait. Team
   Kitty / SaaS is frozen, and CLI 4.0.0 GA is milestone 11 alone.

**In one sentence:** *4.0.0 turned a CLI that could quietly lose customer work into one that
refuses instead of guessing, and what stands between the fourth release candidate and GA is a
short, named list.*
