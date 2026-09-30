---
title: '13 — Dialectic: Is "Mission" the same as "Mission Run"?'
description: Dialectical research (Phase 2) on whether Mission is the same as Mission Run, corroborating then refuting and reconciling, for the runtime and state overhaul.
doc_status: deprecated
updated: '2026-06-03'
---
# 13 — Dialectic: Is "Mission" the same as "Mission Run"?

**Phase:** 2 (conceptual modeling) · **Date:** 2026-06-03 · **Method:** dialectical research (corroborate
‖ refute, then reconcile) — see the `dialectic-research` tactic.

**Theory T (Stijn):** *"Mission" and "Mission Run" are the same concept; "Mission" is the
old/deprecated term for what is now a "Mission Run", predating distinct Mission Types — a false dichotomy.*

> **Verdict: T is REFUTED** — Mission and Mission Run are distinct by deliberate, enforced design.
> **But the theory was productive:** it surfaced three real truths, including a **correction to our own
> model** (doc `12` §5a conflated them) and a live **degeneracy smell** adjacent to #1619.

---

## The decisive test: cardinality

If Mission and Mission Run were one concept, a Mission could never have more than one Run. **It can.**
- `_start_ephemeral_query_run()` (`runtime_bridge.py:1970-2003`) creates a *separate* run for the
  **same `mission_slug`** in a temp store, explicitly to stay non-mutating — one Mission, two live runs.
- `start_mission_run()` mints a fresh `run_id = uuid4().hex` per call (`engine.py:196`); because the
  run tree is gitignored/ephemeral, a cleaned/cloned/CI checkout deterministically gets a **new run**
  for the same Mission (`get_or_start_run`, `runtime_bridge.py:2006-2060`).

**Mission : Mission Run is 1 : many.** You cannot collapse a 1:many into an identity. This alone refutes T.

## Distinct storage, identity, lifecycle (machine-declared)

| Axis | **Mission** | **Mission Run** |
|------|-------------|-----------------|
| Storage | `kitty-specs/<slug>/` (spec/plan/tasks/status) — **git, durable** | `.kittify/runtime/runs/<run_id>/` — **gitignored, ephemeral** (`state/contract.py:181-210`, `.gitignore:63`) |
| Identity | `mission_id` (ULID) / `mission_slug` | `run_id = uuid4().hex` / `mission_run_id` |
| Lifecycle | committed history | `GitClass.IGNORED`, `AuthorityClass.LOCAL_RUNTIME` |
| Run-only state | — | `template_hash`, frozen policy snapshot, `issued_step_id`, `pending_decisions`, `blocked_reason` (`schema.py:523-537`) |

Different persistence + different identifier scheme + different durability = **different aggregate.**

## The governing decision + enforcement

- ADR `2026-04-04-2` (**Accepted**) defines three distinct layers and **explicitly rejected Option 3**
  ("use Mission Run as the canonical tracked item") because it "directly collides with the existing
  runtime/session use" (`:235`). Rule: `mission_run_id` "must never alias a tracked mission slug" (`:122-123`).
- The split is **CI-enforced**: `tests/contract/test_terminology_guards.py:105-138` fails if any command
  aliases the terms. A deprecated synonym would not have a green suite forbidding it.

---

## What the theory got right (salvaged truths)

The dialectic is not "you were wrong, move on." T surfaced three findings worth keeping:

### 1. Mission Run is **degenerate in the current implementation** (a real smell)

The affirmative case landed here: `mission_run_id` is minted as `uuid.uuid4()` (`dossier/indexer.py:82`)
or faked as a `snapshot.snapshot_id` "proxy" (`dossier/api.py:473`); it appears in ~3 live lines; and
`MissionRunSnapshot`/`MissionRunRef` store `run_id` + `mission_key` (the **type**) but **no mission
slug/id at all** (`schema.py:523`, `engine.py:92`). **The runtime's Mission Run cannot name the
Mission it belongs to.** So the concept is *real by design* but *under-realized in code* — which is
exactly why it *feels* redundant. This is **adjacent to #1619**: a run layer that can't reference its
own Mission is a weak "sense of self/purpose" at the runtime boundary.

### 2. The history is real but the direction is inverted

"Mission" did predate distinct Mission Types (mission system 2025-10-29 vs `mission_types/` 2026-02-16),
and the three-noun ontology was **retrofitted** onto one undifferentiated "mission" (ADR #378/#383).
**But** "Mission" is **not** the old term *for the Mission Run* — the record shows Mission Run is the
**newer** runtime term, carved *out* of the overload; only **`Feature`** was deprecated as an alias
(for software-dev Missions). So T's "originally one concept, later split" is true; its "Mission == the
old MissionRun" direction is **backwards**.

### 3. Model correction — our own `12` §5a conflated them

This is the most useful outcome. In `12` §5a I labelled the two-layer state (mission-level + WP-level)
as **"MissionRun"**. That is wrong: that durable, layered state lives on the **Mission**
(`kitty-specs/<slug>/` — meta + status events + WP frontmatter, all git-tracked). The **Mission Run**
is the *ephemeral session/execution instance that drives a Mission through its steps*. Corrected picture:

```
  MISSION TYPE   — reusable blueprint (lifecycle actions, templates, guards)
        │ instantiated as
        ▼
  MISSION        — durable tracked item  (kitty-specs/<slug>/, git)        ← the LAYERED state
    ├── mission-level state: identity · type · phase · topology · interaction policy
    └── work-package-level state: lane · profile · role · location · model · tool · evidence
        ▲ driven through its steps by
        │ 1 : many
  MISSION RUN    — ephemeral session instance (.kittify/runtime/runs/<run_id>/, gitignored)
        frozen template · issued step · decisions · blocked reason   (run_id; should reference the Mission)
```

So `12` §5a's "MissionRun is layered" is really **"the *Mission* is layered (mission + WP state);
the *Mission Run* is the ephemeral driver, 1:many to the Mission."**

---

## Net verdict

| Sub-claim | Verdict |
|-----------|---------|
| Mission ≡ Mission Run (same concept) | **Refuted** — 1:many cardinality; distinct storage/id/lifecycle; ADR rejected the collapse; CI-enforced |
| Originally one undifferentiated "mission", later split | **Confirmed** — retrofitted three-noun ontology (#378/#383) |
| "Mission" is the deprecated term *for the Mission Run* | **Refuted** — direction inverted; Mission Run is the newer carved-out concept; only `Feature` was deprecated |
| The distinction is fully realized in code | **Refuted-ish** — it is *real by design* but **degenerate in implementation** (the smell that motivated T) |

## Implications for the overhaul

1. **Correct `12` §5a:** the layered state is the **Mission**; the **Mission Run** is the ephemeral
   1:many driver. (Done — see `12` §5a banner.)
2. **`MissionStatus` aggregate (`07`/`09` F5) belongs to the Mission**, not the Run — it is the
   durable WP-layer state machine under `kitty-specs/`.
3. **Track the degeneracy** as a real, separable finding: the Mission Run snapshot should reference
   its Mission (`mission_id`/slug), not just the mission *type*. This is small and adjacent to #1619's
   "runtime can't reliably resolve which mission/topology it's in." Candidate follow-up issue.
4. **Keep all three nouns** — Mission Type / Mission / Mission Run — in the model and vocabulary; do
   not collapse. The actor model (`12`): self/purpose live on Mission+Charter; the Run is *which
   pass through the work* an actor is currently making.
