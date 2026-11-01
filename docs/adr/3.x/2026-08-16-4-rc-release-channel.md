---
title: 'Default-off pre-release (rc) consumer channel, gated by SPEC_KITTY_PRERELEASE'
description: 'A default-off SPEC_KITTY_PRERELEASE preference makes update checks pre-release-aware with a pinned rc install command, without ever nagging stable users.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-08-16'
---
# Default-off pre-release (rc) consumer channel, gated by `SPEC_KITTY_PRERELEASE`

**Filename:** `2026-08-16-4-rc-release-channel.md`

**Status:** Accepted

**Date:** 2026-08-16

**Deciders:** Stijn Dejongh (operator); design squad (architect-alphonso design + paula-patterns adversarial review)

**Technical Story:** Epic #3493 child #3496 (T3/US3, WP3 — consumer slice); mission
`operator-config-ergonomics-01M04YK8`; related #3047 (rc producer half)

---

## Context and Problem Statement

Early adopters and internal team members want to catfood release-candidate (`rcN`) builds of
`spec-kitty-cli` ahead of a stable release, and to be nudged toward the latest rc the same way
stable users are nudged toward the latest stable release. Before this decision there was no
opt-in mechanism: the update-check path (`spec-kitty upgrade --agent-check` and the throttled
startup nag) only ever compared against the newest *stable* PyPI release, so an rc was
invisible even to someone who explicitly wanted it, and there was no risk of accidentally
surfacing an rc to someone who did not ask.

The problem statement is therefore narrow and asymmetric: add a way to *opt in* to rc
awareness without ever changing behavior for the (overwhelming majority) stable-channel
population — including on the very first invocation after upgrade, with no config file
present yet.

This ADR covers the **consumer** half only: how the CLI decides whether to show an rc and how
it proposes installing one. The **producer** half — CI's rc build/publish cadence, tagging
scheme, and PyPI publication mechanics — is explicitly out of scope and stays in #3047; this
decision only commits to a discovery *interface* with that work (PEP 440 pre-release versions
on the same PyPI index the CLI already probes).

## Decision Drivers

* Stable users must never be advised to install an rc — zero false positives, by construction,
  not by convention.
* The preference must be settable without a shell export, consistent with the
  `.kitty.env` mechanism this mission already introduces (see the companion
  [env-expansion-seam ADR](2026-08-16-5-operator-config-env-expansion-seam.md)) —
  operators should not need a second, different config file for this knob.
* No new CLI dependency: pre-release comparison reuses `packaging.version`, already present.
* No `--pre`-style transitive blast radius — a pinned exact rc install, not a floating
  "always latest pre-release" mode.
* `SPEC_KITTY_` naming convention; no bare `KITTY_*`.

## Considered Options

* **A.** No consumer opt-in; rc's stay installable only via an explicit
  `pip install spec-kitty-cli==<rc>` a user already knows to type.
* **B.** A `--pre` / `pip`-style always-latest-prerelease flag with no persisted preference.
* **C. (chosen)** A default-off, persisted `SPEC_KITTY_PRERELEASE` preference (readable from
  `.kitty.env`) that makes "latest version" surfaces pre-release-aware and offers a pinned
  `spec-kitty-cli==<rc>` install command.
* **D.** Fold rc awareness into the existing `SPEC_KITTY_ENABLE_SAAS_SYNC`-style hosted-mode
  gate rather than a standalone variable.

## Decision Outcome

**Chosen option: "C"**, because it is the only option that gives an explicit, durable,
per-operator opt-in without inventing a new floating-update mode or overloading an unrelated
gate.

Concretely, as shipped:

- **`SPEC_KITTY_PRERELEASE`** (`src/specify_cli/core/channel.py`, `prerelease_enabled()`) is a
  single-authority, default-OFF boolean read via the existing `core/env.is_truthy` grammar.
  Since the `.kitty.env` pre-import loader (see the companion ADR) seeds the process
  environment before any command body runs, this module reads only `os.environ` — it never
  re-reads the file itself, matching the single-read style used elsewhere.
- With the preference unset (the default for every existing and new project), every "latest
  version" surface — `spec-kitty upgrade --agent-check`, the throttled startup nag, the
  compat planner's cache — reports the newest **stable** release only, even when a newer rc
  exists on the configured index. Stable users see no behavior change whatsoever.
- With the preference on, the newest PEP 440 pre-release on the configured PyPI index is
  surfaced, and the proposed upgrade command is a **pinned** `spec-kitty-cli==<rc>` install —
  never a floating `--pre` flag — so the operator gets exactly the version that was surfaced,
  not "whatever is newest at install time".
- `doctor channel` (`src/specify_cli/cli/commands/_channel_doctor.py`, a self-registering
  sibling via the `doctor.py` auto-discovery seam) reports the active channel as an info line
  (`stable` or `prerelease-opt-in`) — read-only, always exits 0.
- The preference is honored from `.kitty.env` with no shell export required, consistent with
  every other operator knob this mission moved off ad hoc shell exports.

### Consequences

#### Positive
* Zero rc advisories reach a stable user under any tested condition, even when a newer rc
  exists on the index — the default-off gate is structural, not a UX nicety.
* Early adopters get one durable opt-in (`.kitty.env`, no per-shell export) instead of
  remembering a flag every time.
* The pinned-install command removes ambiguity about which rc is about to be installed.

#### Negative
* A second "latest version" code path (pre-release-aware vs. stable-only) exists in the compat
  planner and cache-key logic, adding a small amount of branching to maintain.
* Coordination risk with #3047: if the producer half never actually publishes PEP 440
  pre-releases on the probed index, this consumer slice has nothing to discover — the two
  halves must agree on the discovery interface independently of either one's ship date.

#### Neutral
* This is purely a consumer read; no new CI job, tag, or publish step is introduced by this
  ADR — see #3047 for that half.

### Confirmation

Success signals, verified at ship time: (1) with the channel off, `upgrade --agent-check`
reports only the latest stable release even when a newer rc exists on the index; (2) with the
channel on, the newest pre-release is surfaced and the upgrade command is a pinned
`spec-kitty-cli==<rc>` install; (3) the preference is honored when set only in `.kitty.env`,
with no shell export; (4) `doctor channel` reports the active channel correctly in both states.

## Pros and Cons of the Options

### A. No consumer opt-in
**Pros:** zero new surface area. **Cons:** does nothing for the stated need — an early
adopter has to already know the exact rc version string to type, with no discovery path.

### B. `--pre`-style always-latest-prerelease flag
**Pros:** familiar `pip`-style ergonomics. **Cons:** no persisted preference means re-passing
the flag on every invocation, and "always latest pre-release" risks silently jumping to a
newer, less-tested rc than the one the operator evaluated — rejected in favor of an explicit
pinned-version proposal per check.

### C. Default-off persisted `SPEC_KITTY_PRERELEASE` + pinned install (chosen)
**Pros:** durable, explicit, no shell export needed, pinned install avoids surprise version
drift. **Cons:** a second latest-version code path to maintain.

### D. Fold into `SPEC_KITTY_ENABLE_SAAS_SYNC`
**Pros:** one fewer variable. **Cons:** conflates two unrelated concerns (hosted-mode gating
vs. release-channel preference); a local-only user who never touches hosted sync would have no
way to opt into rc's, and a hosted-mode user would be opted into rc's whether they wanted them
or not. Rejected — the two axes are orthogonal and must stay independently settable.

## More Information
- Design source: `kitty-specs/operator-config-ergonomics-01M04YK8/design-record.md`
  (companion-ADR note) + `spec.md` (US3) / `plan.md` (IC-05).
- Companion: [ADR: operator config env-expansion seam](2026-08-16-5-operator-config-env-expansion-seam.md)
  — the `.kitty.env` mechanism this preference is read through.
- Producer half (CI rc-cadence + publication): #3047.
