# REASONS Canvas — System status actor

> Mission: `system-status-actor-01M67HTR`
> Source: [#6722](https://github.com/spec-kitty/spec-kitty/issues/6722). [spec.md](spec.md) is authoritative; this canvas is non-governing and advisory.

## Requirements

- **Problem.** #6400 gave every agent and operator status write the structured 4-key actor; by explicit operator decision it left the system writers on bare strings. Consumers therefore still accept two shapes on one event field, and the boundary sentence in `docs/architecture/status-model.md` ("Still strings") is the debt this mission closes.
- **Decision (spec § Decision).** A system write records `{tool: <the identity it records today>, role: "system", profile: null, model: null}`. One new role value; `tool` unchanged so every projection and every gate keeps its rule; no fifth key.
- **Acceptance.** Spec FR-001 … FR-013, one test family per writer family; SC-001 … SC-005.
- **Definition of done.** All 13 system-writer emit sites (nine writer modules) structured (SC-001); every committed mission log reduces byte-identically (SC-002); a mixed-shape log reduces and verifies like an all-string one (SC-003); no system row carries a profile or model (SC-004); docs and changelog state the rule (SC-005). Proven through the real entry points (`finalize-tasks`/bootstrap, `reconcile`, `consolidate`, the three `migrate` backfills, `status reduce`), red-first.

## Entities

- **System actor** — the 4-key dict a system writer records. Built by one function in `status/actor.py`; never assembled inline.
- **Role** — the kind of agency on a hop: `implementer`, `reviewer`, `system`. Closed vocabulary, owned by `status/actor.ActorRole`, taken from the action and never from a profile.
- **Seed identity** — `migration:<id>`, the name of an in-process reconstruction. It stays in the actor's `tool`, so `is_migration_actor` and the reducer's seed arm keep the rule #6093/#6271 gave them.
- **Seed row** — an immutable `status.events.jsonl` line; the backfill verifies its payload byte-semantically, so a row's actor *shape* may differ from today's builder while its identity may not.

## Approach

- Additive: one builder plus one `ActorRole` member; every existing builder (`build_status_actor`, `actor_from_option`, `compose_status_actor`) is untouched, so the agent and operator paths cannot drift.
- Compatibility is proven by the readers, not by rewriting stored rows: the seed predicate becomes shape-blind and the backfill verification tolerates a shape-only difference for an immutable row.
- The system identity is never routed through `parse_agent_boundary_string` — a `migration:<id>` tool would be split on its colon.

## Structure

- Writers: `status/bootstrap.py`, `lanes/recovery.py`, `consolidation/{done_bookkeeping,preflight,approved_attestation,canceled_attestation}.py`, `migration/{wp_status_backfill,backfill_runtime_state,verdict_provenance_backfill}.py`.
- Authority: `status/actor.py` (builder, role vocabulary) and `status/models.py` (projection, migration prefix).
- Frozen and untouched: `services/`, `contracts/` (ADR `2026-10-29-1` D-9).

## Operations

- Research → specify → plan → tasks → red-first implement/review → accept → local consolidation → independent aggregate review → changelog/docs → draft PR → CI green → ready for review. The operator merges.
