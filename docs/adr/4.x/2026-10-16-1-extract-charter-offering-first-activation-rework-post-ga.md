---
title: 'ADR: extract the charter offering layer first as the GA gate leg; the activation rework rides the post-GA stable line'
description: 'Charter extraction splits by seam: offering extracts first as the 4.0.0 GA gate leg; the activation drain/rework moves off-gate to CLI 4.x stable. Amends 2026-10-12-2.'
status: Accepted
date: '2026-10-16'
updated: '2026-10-19'
---

**Status:** Accepted (2026-10-16).

**Date:** 2026-10-16

**Deciders:** Stijn Dejongh (operator).

**Technical Story:** epic #6099 (extract the charter offering layer to its own
independently-released repository — GA-gating, milestone "4.0.0 release scope"); #6188
(move the `specify_cli → charter` imports onto the offering seam — **completed** 2026-10-13,
PR #6200); #6218 (align the seam's return types with `spec-kitty-charter` ADR-0004).
Amends ADR [2026-10-12-2](2026-10-12-2-charter-extraction-to-its-own-repository.md) (the
charter becomes an external contract package in its own repository) and its Amendment
2026-10-13. Companion: ADR
[2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md) (the
open-core producer surface). Durable plan:
[Doctrine & Charter](../../plans/domains/doctrine-charter-domain-plan.md) §3.6.

**Reader:** a maintainer sequencing the charter extraction, or planning the 4.0.0 GA gate.

---

## Context and Problem Statement

ADR 2026-10-12-2 ratified that the charter becomes an external contract package in its own
repository, with two sibling entry-point seams (`charter.offering.api`, `charter.activation.api`;
Amendment 2026-10-13). That amendment held **236 `(file, module)` reaches** from
`specify_cli`, `runtime`, `glossary` and `mission_runtime` into `charter.activation` internals
as a shrink-only baseline (`tests/architectural/charter_activation_boundary_baseline.yaml`,
owner #6099) and stated they would be "drained onto `charter.activation.api` **before the
4.0.0 GA gate**."

Two facts have changed the right sequencing since then:

1. **The import-move precondition is done.** #6188 ("move the `specify_cli → charter` imports
   onto the `charter.offering.api` public surface") **closed completed** on 2026-10-13
   (PR #6200 split the offering and activation entry-point seams). #645 ("Stable Application
   API Surface"), long cited as the open GA-gating precondition, **closed `not_planned`** the
   same day with all 13 children shipped. Any plan whose first task is "move the ~129 imports"
   or that cites #645 as an open precondition is planning finished work.
2. **The offering layer has zero code dependency on activation.** Verified in-tree:
   `src/charter/offering/**` contains **no** runtime import of `charter.activation` (the 67
   textual matches are all docstrings / Sphinx cross-references — `org_pack_loader.py` even
   documents that "`charter.offering` sits below the charter facades and `charter.activation`").
   The reverse edge is heavy: **~360** `charter.offering` references from `charter.activation`.
   Offering is the foundational bottom layer; activation sits above it and consumes it.

The consequence: **offering can be lifted out cleanly now**, consuming nothing that would have
to follow it, while **activation can stay in core** and keep consuming the (now external)
offering package. Draining the 236 activation reaches — the long pole of the whole extraction —
is **not** a precondition for extracting offering, so forcing it onto the GA gate couples the
cheap, ready leg to the expensive, not-ready one.

## Decision Drivers

- **Dependency direction (verified).** offering → activation code edges = 0; activation →
  offering ≈ 360. The clean cut is offering-first.
- **Smallest viable GA scope.** The GA gate should carry the leg that is ready and foundational,
  not the leg (activation drain) whose 236-reach baseline is still being worked down.
- **Single canonical authority / architectural alignment** (charter governing principles): the
  extracted unit is consumed through one public surface, like `spec-kitty-events` /
  `spec-kitty-tracker`.
- **Honest records** (Standing Order #9 throughline — don't carry stale "truth"): the
  precondition record (#645 open, "~129 imports to move") is stale and must be corrected.

## Decision Outcome

**Charter modular extraction splits by seam. Offering extracts first as the GA gate leg;
the activation rework rides the post-GA CLI 4.x stable line.**

- **D-1 (Accepted): extract `charter.offering` first, as the charter modular-extraction GA
  leg.** It is the foundational layer with zero code dependency on activation, so it is
  independently liftable. This is the charter leg of the 4.0.0 GA gate (ADR 2026-10-12-2 D-2,
  roadmap rule 5), now scoped to **offering**.
- **D-2 (Accepted): the `charter.activation` drain/rework moves OFF the GA gate to the post-GA
  "CLI 4.x stable" milestone.** Activation **stays in core as-is for GA**. The 236-reach
  shrink-only baseline remains a priced, shrink-only ratchet (ADR 2026-09-30-1), but draining
  it onto `charter.activation.api`, and any activation extraction, is **post-GA**. **This
  supersedes ADR 2026-10-12-2 Amendment 2026-10-13's clause that the activation reaches are
  "drained onto `charter.activation.api` before the 4.0.0 GA gate."**
- **D-3 (Accepted): the offering extraction is tracked as four phases under epic #6099 on
  milestone "4.0.0 release scope."** They follow the `spec-kitty-events` / `spec-kitty-tracker`
  precedent (version-locked first, decouple cadence once the boundary is proven) and the
  #645/#460 pattern (typed contract + acceptance test before transport). ADR-0004 DTO
  alignment (#6218) coordinates with the first phase.

  | Phase | Issue | Scope | Size | Red-first |
  |---|---|---|---|---|
  | P1 | #6285 | enumerate + freeze the offering public contract surface (reconcile `charter.offering.api` + the `charter.*` facades; annotate ADR-0004 DTO-forward) | M | — |
  | P2 | #6286 | red-first offering contract-conformance acceptance suite against the frozen surface (the "a seam-pinned consumer survives the split" net) | M | **yes** |
  | P3 | #6287 | enforce `charter` as an external contract package at the boundary/layer gates (importing up the chain fails dependency resolution) | L | — |
  | P4 | #6288 | ~~extract `src/charter/offering/` to `spec-kitty-charter`, consume version-locked first~~ **(replaced by Amendment 2026-10-19):** the offering stays in core behind `charter.offering.api` and is replaced in place by the spec-kitty-charter service (spec-kitty-charter ADR-0008). The 4.0.0 leg is a frozen seam and a green conformance corpus, not an extraction. | L | — |

  #6218 (align `api.py` C-003 with `spec-kitty-charter` ADR-0004) is a **P1 prerequisite**, not a
  phase — it is docs/ADR only. The single first ticket is **#6285 (P1)**.

- **D-4 (Accepted): the event ledger's value-bearing read surface is confirmed GA-gating; no
  additional read-path tickets join the gate.** The claim "the event API is only valuable if the
  read path is enabled" is **true only abstractly** (a write-only ledger nobody reads delivers no
  value) but is **disproved as a reason to widen the gate**: the append-only `status.events.jsonl`
  ledger already has live readers today — `orchestrator-api mission-state`/`list-ready`,
  `agent tasks status --json`, `events tail`, and the Java `services/mission-status-api/` reading
  the ledger off disk — and ADR 2026-10-13-2 routes event value through the ledger being *read*,
  not through the deliberately inert `status/adapters.py` fan-out. The value-bearing read surface —
  epic #5528 and its detail resource #957 — is **already GA-gating** on milestone "4.0.0 release
  scope" (ADR 2026-10-01-2 D-12), so the intent that read-path value sit on the GA gate is
  **already satisfied with no change**. The reader-consolidation refactors #5532 (re-point readers
  onto one seam/reducer) and #5533 (rehome ex-dashboard routes) stay **off-gate** (CLI 4.x stable)
  by their deliberate placement; pulling them onto the gate would duplicate #5528 and contradict
  ADR 2026-10-01-2 D-5. **Open sub-decision (operator):** whether to pull **#5532 alone** onto the
  gate on the separate reducer-duality argument (two reducers persist at GA while #5532 stays
  off-gate, #4941) — recorded here, not decided.

- **D-5 (Accepted): correct the stale precondition record.** #645 is closed `not_planned`;
  #6188 (the import move onto the offering seam) is complete. Neither is an open precondition.
  #6099 is the live extraction epic; the roadmap, charter and domain plans that still cite
  "#645 / ~129 imports to move" as open GA-gating work are corrected to match.

### Consequences

#### Positive

- The GA gate carries the ready, foundational leg (offering) and is not blocked on the 236-reach
  activation drain.
- Open-core consumers can depend on the extracted `charter.offering` unit at its own version.
- The precondition record stops asserting finished work as pending.

#### Negative

- The charter is extracted in two steps (offering now, activation later), so cross-repo
  coordination exists for longer than a single-shot extraction would.
- Activation keeps a shrink-only baseline of 236 reaches live past GA (priced debt, owner #6099
  / its post-GA successor).

#### Neutral

- Activation staying in core for GA does not change any gate or layer rule in this ADR; it
  changes *when* the activation drain must land.

### Confirmation

- An architectural test pins `charter.offering` as an external contract package once the
  extraction lands; a consumer pinned to the offering seam survives the split (the phase-2
  acceptance suite is that net).
- The four #6099 children are filed on milestone "4.0.0 release scope".
- The roadmap and ADR 2026-10-12-2 no longer cite #645 / "~129 imports" as open GA-gating work.

## More Information

- ADR [2026-10-12-2](2026-10-12-2-charter-extraction-to-its-own-repository.md) and its
  Amendment 2026-10-13 (the two sibling seams and the shrink-only activation baseline).
- [Doctrine & Charter domain plan](../../plans/domains/doctrine-charter-domain-plan.md) §3.6.
- [4.0.0 milestone roadmap](../../plans/4-0-0-milestone-roadmap.md) — the GA gate legs.
- `spec-kitty-charter` ADR-0004 (the public API returns generated OpenAPI DTOs), tracked in
  core by #6218.

## Amendment 2026-10-19: P4 is replaced; the offering is replaced in place, not extracted

**Deciders:** Stijn Dejongh (operator), 2026-10-19. Requested by
[`spec-kitty-charter` ADR-0010](https://github.com/spec-kitty/spec-kitty-charter/blob/main/docs/adr/0010-cutover-scope-and-seam-boundary.md)
("Requests to core"), building on `spec-kitty-charter`
[ADR-0008](https://github.com/spec-kitty/spec-kitty-charter/blob/main/docs/adr/0008-rewrite-and-replace-against-bdd-and-openapi-contracts.md)
(rewrite and replace). Recorded in
[spec-kitty-charter#88](https://github.com/spec-kitty/spec-kitty-charter/pull/88).

D-3, phase P4 (#6288, "extract `src/charter/offering/` to `spec-kitty-charter`") is replaced
with:

> The offering stays in core behind `charter.offering.api` and is replaced in place by the
> spec-kitty-charter service (spec-kitty-charter ADR-0008). The 4.0.0 leg is a frozen seam and
> a green conformance corpus, not an extraction.

What this changes in the record above:

- **D-1 is read through this amendment.** "Extract `charter.offering` first" no longer means a
  repository move. Nothing Python moves to `spec-kitty-charter`; the Python charter stays in
  core until its reads are retired by the cutover that ADR
  [2026-10-03-1](2026-10-03-1-charter-read-write-service-strangler.md) (Amendment 2026-10-19)
  governs. The GA leg is the frozen seam (P1, #6285) and the green conformance corpus (P2,
  #6286).
- **D-2 stands.** `charter.activation` stays in core until its post-GA rework.
- **ADR [2026-10-12-2](2026-10-12-2-charter-extraction-to-its-own-repository.md) is
  superseded** by `spec-kitty-charter` ADR-0008 and ADR-0010 (operator ruling, 2026-10-19).
- **P3 (#6287) is premised on the extraction** (`charter` as an external contract package at
  the boundary gates). It is not re-scoped by this amendment; the operator decides its fate
  separately.
- The *Confirmation* bullet "an architectural test pins `charter.offering` as an external
  contract package once the extraction lands" no longer applies: no extraction lands. The
  phase-2 conformance corpus remains the net.
