---
title: Understanding the Retrospective Learning Loop
description: Conceptual explanation of the four-category model, bounded contexts, event-model layering, and the synthesize anti-corruption layer.
doc_status: active
updated: '2026-06-03'
---
# Understanding the Retrospective Learning Loop

This document explains why the retrospective learning loop exists and how it works at a conceptual
level. For the operator how-to, see
[How to Use Retrospective Learning](../guides/how-to/governance/use-retrospective-learning.md). For the schema
reference, see [Retrospective Schema Reference](../api/retrospective-schema.md).

---

## Why retrospectives exist

Governance without feedback is static. If your `charter.md` never changes, your project's policy
doctrine never improves. Directives that are unhelpful stay unhelpful. Glossary terms that are
missing stay missing.

The retrospective learning loop is the mechanism by which completed missions feed back into
governance. When a mission finishes, the runtime captures structured findings: what helped, what
did not help, what governance or context gaps appeared, and what concrete changes are proposed to
the doctrine, DRG edges, or glossary. Over many missions, the retrospective summary reveals
patterns — directives that are consistently flagged as unhelpful, terms that are consistently
missing, DRG edges that would improve context relevance.

Without retrospectives, governance stagnates. With them, governance is a living system that
improves with every completed mission.

---

## The four-category model

The retrospective system maps onto four conceptually distinct categories:

| Category | What it is | Primary artifact |
|---|---|---|
| **Policy** | When / whether / how-to-fail the loop runs | `.kittify/config.yaml#retrospective` or charter frontmatter |
| **Record** | Structured findings and proposals for one mission | `.kittify/missions/<mission_id>/retrospective.yaml` |
| **Summary** | Read-only aggregation across all records | stdout / JSON via `retrospect summary` |
| **Application** | Human-approved mutation of doctrine / DRG / glossary | `agent retrospect synthesize` with explicit `--apply` |

Each category has one and only one authoritative operation. Conflating them — for example, treating
`summary` as the authoring step — is the most common documentation error. The canonical post-merge
sequence is: **mission review → author or verify retrospective (`retrospect create`) → surface
findings (`summary` aggregates; `synthesize` reviews proposals)**.

---

## Bounded-context map

This mission spans four bounded contexts. The crossings are explicit and mediated:

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│ Retrospective Authoring      │         │ Mission Lifecycle /          │
│                              │         │ Event Log                    │
│ - RetrospectivePolicy        │         │                              │
│ - RetrospectiveRecord        │         │ - runtime_bridge.py          │
│ - generator (pure Python)    ├────────►│ - retrospective_terminus.py  │
│ - writer (merge/overwrite)   │ emits   │ - status.events.jsonl        │
│ - events (additive)          │ events  │ - reducer (no-op for         │
│                              │         │   retrospective events)      │
└────────┬─────────────────────┘         └──────────────────────────────┘
         │
         │ proposals[] (data only)
         ▼
┌──────────────────────────────┐         ┌──────────────────────────────┐
│ agent retrospect synthesize  │         │ Doctrine / DRG / Glossary    │
│ (anti-corruption layer)      ├────────►│                              │
│                              │ apply   │ - human-approved mutations   │
│ - preview proposals          │ (gated) │ - structural changes always  │
│ - apply with human approval  │         │   require explicit consent   │
└──────────────────────────────┘         └──────────────────────────────┘
```

- **Retrospective Authoring → Event Log**: explicit, additive event payloads
  (`RetrospectiveCaptured`, `RetrospectiveCaptureFailed`). The reducer treats them as no-ops for
  lane state; they are purely informational events in `status.events.jsonl`.
- **Retrospective Authoring → Doctrine/DRG/Glossary**: never direct. Proposals are data; their
  application goes through the `synthesize` anti-corruption layer with human approval. The runtime
  does NOT auto-apply structural governance changes.
- **CLI Surface → Retrospective Authoring**: through documented JSON contracts in
  `kitty-specs/retrospective-default-policy-01KS049J/contracts/`.

---

## The generator: pure-Python module

The default retrospective generator is a pure-Python module (not an agent profile invocation).
This design choice was deliberate:

- **Sub-second latency**: the default-on path runs at every mission boundary; agent dispatch
  (5–30 s) would be incompatible with that.
- **Determinism**: the FR-021 "byte-identical reductions" guarantee requires the same inputs to
  always produce the same output. A pure function satisfies this; an agent-authored record
  does not.
- **Testability**: unit tests scaffold mission artifacts on disk and call the generator directly,
  with no agent harness mocks.

The `retrospective-facilitator.agent.yaml` profile exists as a **human-mediated tool** for richer
post-mortems via explicit operator invocation. It is not the runtime default.

---

## Event-model layering (Renata's WP04 note)

There are two event namespaces in the codebase:

- **`retrospective.events`** (older): the autonomous-terminus lifecycle wrapper, retained for
  back-compat with pre-3.2.0 flows. It wraps the facilitator dispatch lifecycle (start / complete
  / fail) in a style consistent with the older HiC/autonomous gate model.
- **`retrospective.lifecycle_events`** (new, FR-024-compliant): the canonical contract surface
  used by post-mission flows in 3.2.0+. These events (`RetrospectiveCaptured`,
  `RetrospectiveCaptureFailed`) are emitted into `status.events.jsonl` and are the authoritative
  record of retrospective authoring state.

The two namespaces are cleanly layered: `lifecycle_events` is the public surface that
orchestrators and dashboards consume; `events` is the internal lifecycle wrapper the facilitator
runtime uses. They do not conflict, but contributors should import from `lifecycle_events` for any
new code that reacts to retrospective completion.

---

## Policy resolution and precedence

Policy is resolved at call time from a three-tier stack:

1. **Charter frontmatter** (`charter.md`): wins by default for governed projects.
2. **`.kittify/config.yaml`** (`retrospective:` key): active when charter does not define the
   field, or when charter explicitly sets `retrospective.precedence: config`.
3. **Runtime defaults**: `enabled: true`, `timing: after_completion`, `failure_policy: warn`.

The resolver returns `(policy, source_map)` where `source_map` records the origin of every
leaf field — operators can always trace which file and key drove a given gate behavior.

---

## Proposal lifecycle

A completed retrospective produces **proposals** — structured suggestions for governance changes:

- `add_glossary_term` / `update_glossary_term` — add or update a glossary term
- `flag_not_helpful` — mark a DRG artifact as not helpful
- `add_edge` — add a relationship to the DRG
- `synthesize_*` — more complex doctrine synthesis proposals

Their lifecycle:

1. **Generated**: the pure-Python generator produces proposals and writes them to
   `.kittify/missions/<mission_id>/retrospective.yaml`.
2. **Staged**: proposals are visible in `agent retrospect synthesize` (dry-run by default). No changes
   have been made to governance state yet.
3. **Applied or rejected**: `agent retrospect synthesize --apply <id>` validates, conflict-checks,
   and applies. Rejected or conflicting proposals are not applied.
4. **Provenance recorded**: every applied change carries provenance back to the originating
   mission, proposal ID, and evidence event IDs.

`flag_not_helpful` is auto-included in the effective apply batch; it still requires
`--apply` and never mutates state during preview.

---

## The synthesizer's role (anti-corruption layer)

The `agent retrospect synthesize` command is the **only** path from retrospective output to
governance change. Its role is to validate, conflict-check, and apply proposals that already
exist in the retrospective record — not to generate content.

The synthesizer is **fail-closed on conflicts**: if two proposals contradict each other (for
example, both add the same glossary term with different definitions), it applies nothing from the
conflicting set.

You cannot bypass the synthesizer by editing governance files directly — those files are derived
artifacts and would be overwritten on the next `charter synthesize` run. The correct path:

1. Review proposals (`agent retrospect synthesize`, dry-run by default)
2. Resolve any conflicts (manually, in `charter.md` if needed)
3. Apply (`agent retrospect synthesize --apply <id>` or `--apply` for full batch)
4. Re-run `charter synthesize` if `charter.md` was edited

---

## Cross-mission summary

`spec-kitty retrospect summary` aggregates retrospective records across all missions in the
project. This read-only view reveals governance patterns not visible from any single mission —
for example, a directive flagged as not helpful in 5 of 10 missions is a strong signal to revise
or remove it.

The summary tolerates a mix of complete, skipped, missing, and malformed records without aborting.
Malformed records are excluded from counts with a structured reason. Use `--include-malformed`
to see details.

---

## See Also

- [How to Use Retrospective Learning](../guides/how-to/governance/use-retrospective-learning.md) — operator how-to
- [Retrospective Schema Reference](../api/retrospective-schema.md) — YAML and event schemas
- [ADR: Retrospective Default-On Policy Architecture](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-05-19-1-retrospective-default-policy-architecture.md) — architectural decisions
