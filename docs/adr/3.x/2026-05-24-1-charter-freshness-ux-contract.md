---
title: 'ADR: Charter Freshness UX Contract'
description: 'Establishes one freshness vocabulary across the charter command family, anchored by a tri-state graph identity carried on every decay report the lint engine emits.'
status: Accepted
date: '2026-05-24'
doc_status: active
kind: ADR
updated: '2026-05-24T00:00:00Z'
---

- [`2026-05-16-1-doctrine-layer-merge-semantics.md`](2026-05-16-1-doctrine-layer-merge-semantics.md) (predecessor — locks the layer-merge semantics this contract reports on)
- [`2026-05-24-2-pack-augmentation-vocabulary.md`](2026-05-24-2-pack-augmentation-vocabulary.md) (sibling — `overrides` / `enhances` vocabulary used in the freshness banners)
- [`2026-05-24-3-shipped-to-built-in-cutover.md`](2026-05-24-3-shipped-to-built-in-cutover.md) (sibling — the `built-in` label this contract surfaces)
**Related issues**: [#1099](https://github.com/Priivacy-ai/spec-kitty/issues/1099), [#1100](https://github.com/Priivacy-ai/spec-kitty/issues/1100), [#1101](https://github.com/Priivacy-ai/spec-kitty/issues/1101), [#1104](https://github.com/Priivacy-ai/spec-kitty/issues/1104)

## Context

A developer adopting Spec Kitty today encounters fragmented freshness signals across the
charter command family. Concretely:

- `spec-kitty charter status` reports `SYNCED / No decay detected` even when the project
  Doctrine Reference Graph (DRG) is missing, because the existing status path only
  inspects file existence, not the relationship between charter source, synced bundle, and
  synthesized DRG.
- `spec-kitty charter lint` returns an empty `DecayReport` (`Scanned 0 nodes`,
  `No decay detected`) when `.kittify/doctrine/graph.yaml` is absent. This is the
  fresh-checkout default and is indistinguishable from a healthy zero-finding scan
  ([#1099](https://github.com/Priivacy-ai/spec-kitty/issues/1099)).
- `spec-kitty charter synthesize` does not publish a deterministic post-condition. There is
  no marker that distinguishes "synthesize ran and produced nothing because the project
  has no overrides" from "synthesize never ran" ([#1104](https://github.com/Priivacy-ai/spec-kitty/issues/1104)).
- There is no session-start preflight that ties these signals together, so governed
  commands silently degrade against stale or absent doctrine
  ([#1100](https://github.com/Priivacy-ai/spec-kitty/issues/1100)).

The shared root cause is **vocabulary**: every command reports its own slice of the
freshness story in its own shape, so the operator cannot compose the signals into a single
remediation decision. The four issues above are symptoms of a missing contract, not four
independent bugs.

## Decision

We establish a single freshness UX contract that spans the charter command family. The
contract has four parts. Wave 1 of this mission (WP01) lands part (1); waves 2–4 land
parts (2)–(4) under the same vocabulary.

1. **Tri-state graph identity on `DecayReport` (WP01, this ADR's anchor).** The lint engine
   introduces a `GraphState(StrEnum)` enum with three values: `merged`,
   `built_in_only`, `missing`. Every `DecayReport` carries `graph_state`. The
   `LintEngine.run()` orchestrator resolves the graph via a deterministic three-step
   fallback — project DRG → built-in DRG → none — and labels the report accordingly.
   The CLI human banner branches on `graph_state` per the contract table in
   `contracts/charter-lint-json.md`. The `--json` payload exposes `graph_state` at the
   top level. This satisfies FR-001 .. FR-004.

2. **Freshness sub-payload on `charter status --json` (WP02).** The status JSON gains a
   `freshness` object with separate sub-states for `charter_source`, `synced_bundle`,
   and `synthesized_drg`. Each sub-state carries `state`, `last_change`, and
   `remediation`. The state vocabulary matches the preflight surface (see (3)) so
   the two commands compose. This satisfies FR-005.

3. **`charter preflight` surface (WP03).** A new command and a matching session-start hook
   compute a `CharterPreflightResult` with explicit `passed` / `checks` /
   `auto_refresh_applied` / `blocked_reason` fields. It emits deterministic JSON and never
   silently no-ops. When the preflight detects a fresh-checkout state, it either runs the
   safe refresh sequence (`charter sync` → `charter synthesize` → `bundle validate`) or
   blocks with one exact recovery command, governed by a documented configuration flag.
   The preflight refuses to auto-refresh when uncommitted generated artifacts exist in the
   worktree. This satisfies FR-006 .. FR-008.

4. **Documented synthesize post-condition (WP04).** `charter synthesize` guarantees that
   either `.kittify/doctrine/graph.yaml` exists and is valid, or a `built_in_only: true`
   marker is recorded in `synthesis-manifest.yaml` and downstream commands honour it. The
   synthesizer is responsible for the atomicity that prevents the
   "manifest says built_in_only but graph.yaml exists" conflict state from arising; if it
   is detected at read time, the freshness surface treats the manifest as authoritative
   and reports `state="invalid"` with a remediation hint. This satisfies FR-009.

The four parts share one piece of vocabulary: the `state` value space
(`fresh` | `stale` | `missing` | `invalid` | `skipped`) and the `graph_state` value space
(`merged` | `built_in_only` | `missing`). Every public JSON surface and every human banner
uses those exact strings; there are no synonyms.

## Alternatives considered

### A — Eager auto-refresh on every CLI invocation

Every governed command silently runs `charter sync` → `synthesize` → `bundle validate`
before doing anything else. This was rejected for two reasons:

- **NFR-001 budget**. The mission's freshness preflight budget is < 300 ms warm /
  < 1.0 s cold. A full synthesize on every invocation costs seconds on a non-trivial
  charter — well outside the budget and intolerable for interactive use.
- **Surprise factor**. Silent regeneration on every command would overwrite uncommitted
  generated artifacts without operator consent. The preflight (FR-008) treats that case
  as a hard block; promoting it to the default would invert the safety property.

### B — Status-only patch (fix `charter status` and ignore the rest)

Tighten `charter status` to detect a missing project DRG and rely on operators to read it
before running other commands. This was rejected because three of the four symptoms
(#1099 empty lint, #1100 silent degradation in `next` / `implement` / `dashboard`, #1104
opaque synthesize post-condition) live downstream of status. A status-only patch leaves
those symptoms intact and re-introduces the original "fragmented signals" failure mode.

### C — Inline `graph_state` in existing fields (`drg_node_count: -1` or magic string)

Smuggle the tri-state through existing fields rather than adding `graph_state`. Rejected
on contract-hygiene grounds: every external consumer (`charter status --json` callers,
the dashboard, governed agents) would have to learn the sentinel convention and decode it
the same way. An explicit enum is cheaper to document, cheaper to test, and impossible to
confuse with a legitimate node count.

## Consequences

### Positive

- Operators read one vocabulary across `status`, `lint`, `synthesize`, and `preflight`.
  The remediation hint is identical regardless of which command surfaced the gap.
- The dashboard, governed context, and agent-facing surfaces (`next`, `implement`) can
  rely on a single freshness model rather than re-inventing the check at each call site.
- Programmatic consumers get a stable JSON shape: `graph_state` is a top-level enum, not
  a derived field; the freshness sub-payload is structurally identical on
  `charter status --json` and `charter preflight --json`.

### Negative / cost

- The lint engine signature changes: `load_merged_drg(repo_root)` now returns
  `tuple[Any | None, GraphState]` rather than `Any | None`. Internal callers and tests
  that patch `load_merged_drg` must update their stubs. The existing test fixtures in
  `tests/specify_cli/charter_lint/test_engine.py` are updated as part of WP01.
- `DecayReport` gains a required field. `to_dict()` and `to_json()` emit the new field
  unconditionally; the dataclass default is `GraphState.MISSING` so older callers that
  construct `DecayReport(...)` without the field continue to work but report the missing
  state explicitly.
- The CLI banner gains two new branches (`built_in_only`, `missing`). Integration tests
  that asserted on the old "No decay detected / Scanned 0 nodes" string for fresh-checkout
  repos must update. WP01 includes the matching test rewrites.

### Migration impact

External consumers that grep `charter lint --json` for a particular finding shape are
unaffected: `findings`, `scanned_at`, `drg_node_count`, `drg_edge_count` remain. New
consumers that want the tri-state read `graph_state`. No CHANGELOG breaking entry is
required for WP01 because the field is additive; the `shipped → built-in` rename in WP10
will carry its own CHANGELOG note.

## Scope of this ADR

This ADR fixes the contract for the freshness UX across all four waves of the mission. It
does **not** lock the schema for `freshness.*` sub-states beyond the value vocabulary —
that schema is finalised in WP02 and lives in the data model and JSON contract files. It
does **not** mandate when `charter preflight` runs (every command vs session-start only);
that decision is recorded in WP03 against the matching research question (open question
3 in `spec.md`).

This ADR is the foundation contract for WP01 .. WP04. Subsequent WPs in this mission build
on it; they do not amend it.
