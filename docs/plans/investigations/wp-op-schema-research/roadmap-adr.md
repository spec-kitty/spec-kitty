---
title: 'WP & Op Schema Research — Roadmap / Vision / ADR (researcher-robbie)'
description: 'Verbatim research report: roadmap/vision alignment and ADR binding for the WP & Op schema-model idea.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/plans/investigations/wp-op-schema-research/README.md
- docs/plans/investigations/wp-op-schema-model.md
---
# Roadmap / Vision / ADR Grounding — WP & Op Schema Model

> **Historical (verbatim research report, 2026-07-16).** Archived input to the [WP & Op schema model](../wp-op-schema-model.md) idea note; milestone references are to the closed 3.2.x cycle and the retired 3.3.x line. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

**Lens:** roadmap-vision alignment + ADR binding. **Mode:** read-only, non-rubber-stamping.
**Idea note:** `docs/plans/investigations/wp-op-schema-model.md`

## Executive summary

The idea is *directionally aligned* with the 3.2.x milestone (it is a consolidation-onto-one-authority move, which is exactly what G2/degod favours), and the model-first precedent it invokes is real. **But its two headline justifications are largely already claimed by in-flight, ADR-anchored work** — the WP half by **#2093 / #2400** (metadata authority split) plus the already-shipped `lane` retirement, and the Op half by **ADR 2026-06-11-1 + epic #1804**. As written, the note risks minting a *third* narrative over ground two ratified seams already own. There is a genuine, un-owned residual (a validated **WP prompt-body content model** and an **Op intent/scope payload**), but it is much narrower than the note's framing and it is **sequenced behind**, not alongside, the enablers it names.

## 1. Roadmap fit

**The milestone shape (`docs/plans/3-2-x-milestone-roadmap.md`).** 3.2.x is explicitly a *stabilization + structural-debt* cycle whose stated posture is **"No new shadow paths"** and **"adopt the existing execution-context machinery rather than building new construction."** The dependency spine is enablers (#1868 seam-binding, #2173 ports) → delivery (#1797 degod/unshim) → root (#1619 runtime/state) → first functional pickup (#1746). Everything experience-shaped is deferred to 3.3.x.

Against that spine the idea lands as follows:

- **Degod / `specify_cli` cleanup (#1797):** *Aligned in spirit, subordinate in sequence.* "One code-owned model instead of scattered frontmatter/body parsing" is precisely the "one authority, ports over scattered parsing" consolidation #1797 rewards. But the roadmap is emphatic that shim/god deletions are **only safe once the seam they hold is bound (#1868) and the pure core is port-testable (#2173)**. A WP/Op schema revamp is a *consumer* of those seams, not an enabler of them — it should ride behind #1797, not race it.

- **Mission-type → doctrine (#2468, under #2466/#2467):** The note's "why now" leans hardest here ("WP prompt templates are moving into doctrine, change the representation at the same time"). **This is the weakest timing claim.** #2467 (split built-in → packs) is the *keystone* that blocks #2468, and #2468 itself is still open. The templates that *shape* WP files moving into doctrine is not the same event as the *WP record representation* changing — conflating them couples a narrow record-format change to the single most load-bearing, not-yet-landed keystone of the entire G1 arc. That is schedule risk, not a free ride.

- **Runtime/state overhaul (#1619) — the P0 root:** *Direct overlap, and the design is still molten.* #1619's own domain-model work is actively re-cutting what a WP/Mission/MissionRun *is* (`docs/plans/engineering-notes/runtime_and_state_overhaul/15-dialectic-on-the-domain-model.md`). That dialectic is *unsettled* — three of four recent refinements were refuted at the consolidation gate; even the "is Context a subdomain" question was reversed. Formalising a WP logical model now, while #1619 is still deciding the aggregate boundaries the model must sit inside, risks authoring a model against a domain map that is mid-revision. This is the strongest "not yet" signal in the roadmap.

- **Infra-logic separation (#2173):** *Compatible, even synergistic.* A pure Pydantic WP/Op model with parsing behind a port is the shape #2173 wants. No collision; if anything the idea should be *expressed as* a #2173-style port rather than a standalone artifact.

- **Doctrine extensibility / packs (#2466):** *Compatible but downstream.* The model-first schema pattern the idea extends is the same machinery packs will lean on. Fine — but again keystone-gated.

**Verdict on fit:** the *direction* is on-roadmap; the *timing and framing* over-reach. The note positions itself as riding three in-flight waves simultaneously (#1797, #2468, #1619) when in fact it is a **downstream consumer of all three**, two of which (#2468, #1619) have not landed their load-bearing pieces.

## 2. ADR binding

| ADR | Binds because | Constraint it imposes |
|---|---|---|
| **2026-06-11-1 — Op as first-class execution artifact** | The Op half of the idea *is* this ADR's subject. | **Hardest constraint.** The Op record shape and its enrichment are explicitly assigned to **epic #1804** ("reconcile the shipped `invocation/` shapes with the ratified concept… tracked under #1804, **not this ADR**"). The ADR also fixes the Op's spine: `route → context → record → act → close`, an append-only `OpStartedEvent`/`OpCompletedEvent` trail, **C-005 no-parallel-primitive**. An "Op intent/scope payload" is legitimate *only as a field extension on the existing Op record under #1804* — inventing a separate "small-WP-for-an-Op" artifact would re-open the exact C-005 divergence this ADR exists to close. |
| **2026-06-06-1 — Plan concerns → WP traceability** | Governs WP frontmatter schema + the `wps.yaml` manifest. | `WPMetadata` frontmatter is already a Pydantic model with **`extra="forbid"`**; `wps.yaml` (`WpsManifest`/`WorkPackageEntry`, both `pydantic.BaseModel` — confirmed in `src/specify_cli/core/wps_manifest.py`) is *already* the machine-readable structured SSOT. Constraint: the "code-owned model" the note asks for **partly exists**; any revamp must extend these, and must respect that some fields are deliberately *forbidden* in frontmatter and live only in the manifest. |
| **2026-06-07-1 — WP-lane FSM genesis + finalize clobber** | Establishes where mutable lane state lives. | Lane state is owned by the **append-only status event log**, not the WP file; `finalize-tasks` is forbidden from copying `status.events.jsonl` over the coord copy. Constraint: the note's headline "hash churn from status flips" **must not** be solved by a new WP store — the mutable half already left the file. |
| **Status append-only event model** (2.x `2026-02-09-*`; CLAUDE.md: *"Frontmatter `lane` is retired (migration-only)"*) | The note's pain-point #1 (bookkeeping churn). | The bookkeeping/semantic split the note calls its key unblock is **already the shipped architecture** for lane, and **#2093 generalizes it** to `agent`/`shell_pid`/`history`/reviews. Constraint: pain-point #1 is largely *already solved*; the WP file needs to *shed* residual mutable fields (that's #2093), not *adopt a new authoritative store*. |
| **2026-04-25-1 — Shared-package boundary** | Any new model lives in `src/`. | Models must sit in the CLI tree behind OHS facades; no new cross-package coupling, no editable `[tool.uv.sources]`, consumer-contract tests if any shared surface is touched. Low friction but binding. |
| **2026-05-16-1 — Doctrine-layer merge semantics** | Binds only if WP/Op *templates* become doctrine artifacts (the #2468 path the note invokes). | Field-level merge with collision warnings, `extra='forbid'` on models, model-first `generate_schemas.py --check` drift gate. Constraint: if WP shape becomes a doctrine kind, it inherits this merge contract and the schema-generation discipline — a real cost the note lists as a benefit. |
| **2026-06-03-1 — Execution-state domain model** | Places WP status/kanban ownership. | WP status/kanban is owned exclusively by **Mission Management**, reached only via the `status/` OHS facade. A WP model revamp cannot re-derive or co-locate status; it consumes the facade. |

**Net:** four ADRs *actively constrain* the design (Op-as-artifact, plan-concerns traceability, WP-lane FSM, status event model), and two of them (#1804-anchored Op ADR, and the #2093-generalized event model) mean **the two problems the note leads with already have owners**.

## 3. Vision congruence

Spec Kitty's vision — *specifications ahead of implementation; traceability from intent to artefact* — is well served by *structured, sliceable* records, so the **general instinct is congruent**.

The note's central governance claim deserves scrutiny, though: *"today's Op stores 'something was done' (facts), not the 'why & what', blurring `ad-hoc` vs `op`."*

- **The premise is factually soft.** The Op record already carries `request_text` (the operator's ask = the "why" in the operator's own words), `action`, `profile_id`, `mode_of_work`, and `outcome`. ADR 2026-06-11-1's own tier table says the `ad-hoc`↔`op` distinction is **governance + durability**, *not* the richness of an intent field — an ad-hoc shell command is *untraced*; an Op is *traced with loaded doctrine context*. So the claim that "an Op leaves no more trace of intent than an ad-hoc action" is **overstated**: the Op already carries `request_text` + a governance-context binding an ad-hoc edit has by definition none of. The line is not as blurred as the note asserts.

- **The residual is real but modest.** What the Op genuinely lacks is a *structured, machine-sliceable scope* — the change surface, the self-set boundary, the reasoning — beyond free-text `request_text`. Capturing that **advances** the traceability vision. But framing it as "restoring the distinction from ad-hoc" over-sells it; the distinction is intact. The honest framing is *enrichment of an already-governed artifact*, which is exactly **#1804's** charter.

- **Over-engineering risk:** modelling an Op as "a small WP" imports WP-shaped overhead (scope/acceptance/requirements sections) onto a tier whose whole reason to exist (per the ADR) is *being lighter than a Mission*. A heavyweight intent schema would erode the very Op/Mission boundary the ADR draws. The vision is served by a **lightweight, optional** intent+scope field, not a WP-clone.

## 4. Prior art / duplication

This has been circled repeatedly; it is **not virgin ground**:

- **#2093 (WP-metadata authority split, under #2400)** — the closest prior art, and it is *already adjudicated*: architect-alphonso's DECISION rules it **REWORK-staged**. Its ruling: *static design-intent stays frontmatter-canonical; dynamic runtime state (`agent`/`shell_pid`/`history`/reviews) retires to event-log/invocation authority, generalizing the `lane` retirement.* That is **the note's semantic-vs-bookkeeping split, already decided** — and decided the *opposite* way on authority: frontmatter *stays canonical* for intent, rather than YAML/model becoming authoritative with markdown derived. The note must reconcile with this, not re-litigate it.
- **#1804 (Ops execution layer)** — owns the durable, queue-backed Op record and its shape reconciliation (ADR 2026-06-11-1). The Op-intent extension belongs here.
- **ADR 2026-06-06-1 + `wps.yaml`** — already established a structured, code-owned machine-readable WP manifest distinct from prose, with `extra="forbid"` models. The "no code-owned model exists" premise is only half true.
- **`model-first-schema-generation.md`** — the invoked precedent; genuinely proven (10 doctrine schemas, `--check` gate).
- **Runtime/state overhaul notes** (`.../15-dialectic-on-the-domain-model.md`, `13-dialectic-mission-vs-missionrun.md`, `14-model-diagrams.md`) — actively re-deriving the WP/Mission/MissionRun aggregate model the schema would have to conform to.

No prior note proposes *exactly* "make WP-body YAML authoritative, markdown derived." That specific slice is new. Everything the note leads *with* (bookkeeping churn, Op why/what) has an owner.

## Verdict

**Narrower framing — proceed only as a downstream slice, after reconciliation. Not a "now" greenfield mission.**

The roadmap/vision/ADR landscape **does not block** the underlying instinct (code-owned models + model-first schemas are the house style and on-direction for G2/degod), but it **substantially deflates the note as written**: its two headline justifications are already owned, one of them decided the opposite way on authority.

Before any spec/plan, it **must reconcile with**, in priority order:

1. **#2093 / #2400 (WP-metadata authority split)** — *blocking prior art.* The semantic/bookkeeping split is already adjudicated (frontmatter stays intent-canonical; dynamic state → event log). Re-doing it as "YAML authoritative, markdown derived" is a competing decision that needs #2400's owner and architect-alphonso, not a fresh mission. Pain-point #1 (hash churn) is *mostly already solved* by the shipped `lane` retirement + #2093.
2. **ADR 2026-06-11-1 + #1804 (Op-as-artifact)** — the Op intent/scope idea is **#1804 field-extension scope**, C-005-bound. It cannot become a separate "small-WP-for-Op" primitive. Route it as an enrichment RFC on #1804, not a standalone schema mission.
3. **#1619 runtime/state overhaul** — the WP/Mission aggregate model is *mid-revision* (note 15's consolidation gate). Formalising a WP logical model now front-runs an unsettled domain map. Wait for #1619's aggregate boundaries to settle, or the model will be re-cut.
4. **#1868 / #2173 / #1797 sequencing** — this is a *consumer* of the seam-binding and ports work, and of #2468's keystone (#2467). It belongs **behind** those, expressed as a #2173-style port over WP/Op parsing, not as a peer of the degod wave.

**The genuine, un-owned residual worth carrying forward** is narrow: (a) a **validated content model for the WP prompt *body*** (scope/acceptance/requirements as structured fields rather than free prose) with markdown as a derived view — the one slice with no existing owner; and (b) a **lightweight, optional Op intent/scope payload** folded into #1804. Both are legitimate. Neither justifies a standalone "WP & Op schema revamp" mission in 3.2.x, and both should be filed as **reconciliation items under existing epics (#2400, #1804) and sequenced behind #1619/#2468**, not opened as new construction against the milestone's explicit "no new shadow paths / adopt don't build" posture.

Recommended disposition for the idea note: **"documented, narrowed, and re-parented"** — not "spec now."
