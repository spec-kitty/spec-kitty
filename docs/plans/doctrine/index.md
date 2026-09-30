---
title: Doctrine
description: Doctrine layering, charter boundary, and artifact-selection planning — architecture reviews, gap analyses, and mission scope notes.
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/index.md
---
# Doctrine

Design and review artifacts for the doctrine layering system: charter/runtime
boundary audits, layered resolution design, org-doctrine-layer reviews, and
related mission scope notes.

> **Reconciliation note.** Most working-notes below have been **retired
> (`doc_status: deprecated`)** — their designs shipped or were superseded; each
> retired page carries an evidence banner and is preserved as a historical
> record. The **AUTHORITY** creed docs, the **Layered Doctrine Resolution** design
> blueprint (retained pending an operator durable-vs-retire ruling), the
> **Test Quality** series (input for the unmerged Mission C), and the
> **Charter as Sole Door** deferred-issues record remain **live**.

- [Doctrine Usage Test (WP11 dogfood)](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/391-doctrine-usage-test.md) — **retired (deprecated)**
- [Charter as Central Path Resolver — Gap Analysis](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/charter-path-resolution-gaps.md) — **retired (deprecated)**
- [Pre-flight investigation — user-authored doctrine artifact selection](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/doctrine-artifact-selection-preflight.md) — **retired (deprecated)**
- [Doctrine Inclusion Assessment](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/doctrine-inclusion-assessment.md) — **retired (deprecated)**
- [Doctrine Migration: Architecture Alignment Review](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/doctrine-migration-architecture-review.md) — **retired (deprecated)**
- [Layered Doctrine Resolution — Design Blueprint](layered-doctrine-resolution-design.md) — *durable in its frontmatter; the durable-vs-retire operator ruling is still pending*
- [Repo-Coupling Audit of Built-In Doctrine](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/built-in-doctrine-repo-coupling-audit.md) — **retired (deprecated)**
- [Charter Activation vs DRG Reachability](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/charter-activation-reachability-assessment.md) — **retired (deprecated)**
- [Delivery-reachability wiring table (FR-015)](delivery-reachability-wiring-table.md) — deprecated, but kept here because `tests/doctrine/drg/test_reachability.py` reads it as a ledger
- [Cross-Layer missions/ Reader Inventory (WP03)](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/missions-reader-inventory-01KZ6G6H.md) — **retired (deprecated)**
- [Charter-Resolution Program](../charter-resolution/README.md) — sibling folder; parked 2026-08-19, resumed for 4.x (#5431)

*Tiering: **AUTHORITY** docs are the only citable design/sequence statements; **RECORD** docs are superseded inputs and verdicts kept for provenance; **EVIDENCE** docs are raw squad reports and measurements.*

- [The Manifesto Tier — doctrine's missing primary-driver layer](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/manifesto-tier-primary-drivers.md) — RECORD; **retired (deprecated)**; *superseded in part; read the verdict first*
- [Manifesto tier — verdict, corrections, and handover](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/manifesto-tier-verdict-and-handover.md) — RECORD; **retired (deprecated)**
- **[FoundationalValues and Creed — canonical design](foundational-values-and-creed.md)** — **AUTHORITY**: the only doc citable as "the design"
- **[FoundationalValues/creed program — delivery sequence](manifesto-program-delivery-sequence.md)** — **AUTHORITY** for sequencing
- [Creed and FoundationalValues — design as proposed](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/creed-and-values-design-as-proposed.md) — RECORD; **retired (deprecated)**; operator input + measured corpus grounding
- [Creed and FoundationalValues — hardened design](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/creed-and-values-design-hardened.md) — RECORD; **retired (deprecated)**; four-lens hardening round
- [Squad reports + measurements](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/squad-reports/index.md) — EVIDENCE; **retired (deprecated)**; raw lens reports, measurements, and the [final verification round](squad-reports/review-round-2026-07-26.md)
- [Mission B (proposed scope) — Charter-mediated doctrine selection](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/mission-b-proposed-scope.md) — **retired (deprecated)**
- [Org Doctrine Layer — Post-Implementation Architecture Review](org-doctrine-layer-architecture-review.md) — **retired (deprecated)**
- [Runtime → Charter → Doctrine — boundary audit and recommendations](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/runtime-charter-doctrine-boundary.md) — **retired (deprecated)**
- [WP-Prompt Governance Contract — ATDD Findings](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/wp-prompt-governance-atdd-findings.md) — **retired (deprecated)**
- [Test Quality — test slicing & mocking-boundary discipline](test_quality/index.md) — *live (input for the unmerged Mission C)*
- [Next doctrine slice (preliminary research) — wheel cutover, mission-type relocation, public API surface](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/next-slice-wheel-mission-types-public-api-research.md) — RECORD; **retired (deprecated)**; pre-spec research, gap-flags a missing tracker issue for the public-API thread
- [#3179 doctrine public API surface — scoping brief](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/3179-public-api-surface-scoping.md) — EVIDENCE; **retired (deprecated)**; reach-through inventory, facade gap map, lazy-import ratchet design, SonarCloud read, and the OpenAPI-does-not-apply decision
- [Charter as Sole Door: Deferred Issues Record](charter-sole-door-deferred-issues.md) — *live (relocated by PR #3324)*

## Programme realization (2026-07-26 operator ruling)

The FoundationalValues/creed programme captured by the two AUTHORITY docs above was specced as a
single mission — `kitty-specs/doctrine-canonical-structure-remediation-01KYEYSD/` — then **split by
operator ruling into five sequenced missions**. `01KYEYSD` is the **programme record**: it is
specced, then split, and does **not** itself implement (its `tasks/` carries no work packages).

| Mission | Slug | Delivers |
| --- | --- | --- |
| A | `doctrine-silence-guards-01KYFV7Q` | Guards + campsite band: I19 zero-producer lint, occurrence-map field-path granularity, the four-site silent-kind-drop closure (I2), I3b/I3c `extra="forbid"` + writers + round-trip, I3a schema-generation CI wiring, layout/enum ratchets, followable guidance, org→DRG bridge fix, `applies` hygiene |
| B1 | `drg-relation-impacts-vocabulary-01KYFV87` | `Relation.IMPACTS` + `is_symmetric`, retires `in_tension_with`, re-points `consistency_check.py`. Delivers ADR [`2026-07-26-3`](../../adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md) |
| B2 | `drg-edge-migration-extractor-retirement-01KYFV8C` | All 774 edges become authored; extractor edge production retired |
| C | `test-quality-doctrine-series-01KYFV8H` | The original #2935 deliverable: paradigm, DIRECTIVE_047, procedure, anti-patterns, assets, DIRECTIVE_041 intent split, CLI/CI validator parity |
| D | `foundational-values-creed-band-01KYFV8N` | Reachable creed band: I5, I9, I6, I13, I8, I1a, I16, I4-WP01–03, I10 |

**Mandatory order: A → B1 → B2 → C; D gates on A only.** The order is load-bearing (the
programme's sequencing constraints), not preference.

**Status (checked 2026-09-30): stalled after Mission A.** Mission A landed (consolidated as
mission 186). Missions B1, B2, C and D were created on 2026-07-26 but never got past
specify: their only status event is `SpecifyStarted` and they have no mission number.
Re-confirm the programme before resuming it. Full increment→mission mapping, the two measurements that amended the ranked list,
and the D-2/D-3 rulings are recorded in
[`manifesto-program-delivery-sequence.md` § 10](manifesto-program-delivery-sequence.md#10-realization-amendment-2026-07-26).

## See also

- [Plans home](../index.md)
