---
title: 'ADR: upgrade never runs the mission-state repair'
description: 'spec-kitty upgrade, including --yes, only reports TeamSpace mission-state blockers (and only when hosted drain is on); doctor mission-state --fix is the sole repair consent path.'
status: Accepted
date: '2026-10-07'
updated: '2026-10-07'
---

**Status:** Accepted

**Date:** 2026-10-07

**Deciders:** Stijn Dejongh (repository owner).

**Technical Story:** #5811 (an up-to-date `spec-kitty upgrade --yes` rewrote historical Mission state); this record reverses the #4775 decision that `--yes` consents to the repair. Related: #3653.

**Reader:** a maintainer changing the upgrade finalizer, the TeamSpace mission-state gate, or the mission-state repair.

---

## Context and Problem Statement

`spec-kitty upgrade` ends with a finalizer step that used to offer the mission-state repair (`doctor mission-state --fix`, `repair_repo`), a mutating rewrite of `kitty-specs/`. Mission `upgrade-command-hardening` (#3653) made that repair a separately-consented, default-deny gate. #4775 then reconciled "`--yes` is fully non-interactive" with that gate by passing the `--yes` value as the gate's own opt-in, so `upgrade --yes` ran the repair.

#5811 showed the cost: a project that was already up to date had its historical Mission state rewritten by a routine `upgrade --yes`, with no operator decision about the repair, in a repository whose hosted (Team Kitty) features are off and unsupported ([ADR 2026-10-06-1](2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md)). The repair exists to prepare history for a TeamSpace import, which only matters when hosted drain is on.

## Decision

1. **`upgrade` is report-only.** The finalizer step calls `report_teamspace_mission_state_blockers`, which never calls `repair_repo`, never prompts, and never raises `typer.Exit`. The upgrade exit code is unchanged by a reported blocker.
2. **Drain-gated.** With hosted drain off (the default) readiness is not evaluated and nothing is printed. With drain on, the gate prints the blocker count, the finding codes and `spec-kitty doctor mission-state --fix`. The posture is read through the `hosted_posture.drain_posture` module attribute.
3. **One consent path.** `spec-kitty doctor mission-state --fix` is the only caller of `repair_repo`. It names every errored Mission and exits non-zero when any errored, and never prints a "cleared" claim in that case. `tests/architectural/test_mission_state_repair_sole_caller.py` pins the sole caller with an empty allowlist.
4. **The consent plumbing is deleted.** `_should_run_repair`, the `repair_opt_in` and `assume_yes` repair parameters, and the `declined` / `ran` outcome states have no remaining meaning and are removed.

## Considered Options

1. **Report-only, drain-gated (chosen).** Keeps the operator informed where the repair matters and writes nothing.
2. **Keep the `--yes`-carries-consent wiring and add a no-op guard.** Rejected: the repair still runs from a command whose name and flags do not announce it.
3. **Restore the default-deny prompt of #3653.** Rejected: an interactive prompt inside `upgrade` for an unsupported hosted feature is noise, and the explicit command already exists.
4. **Remove the report as well.** Rejected: with drain on, the blocker count is the signal that tells the operator to run the doctor.

## Consequences

- `--yes` stays fully non-interactive (FR-017 of #4775 still holds); it no longer carries a repair consent.
- Already-damaged history is not restored by this change.
- Upgrade output with drain off no longer mentions mission-state at all.
- `enforce_teamspace_mission_state_ready`, the blocking gate for hosted operations, is unchanged.
- Reversible only by an explicit, new decision; the sole-caller gate fails on any other `repair_repo` caller until its allowlist is amended in the same change.
