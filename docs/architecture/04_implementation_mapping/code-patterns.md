---
title: Core Code Patterns Applied in the Codebase
description: The core code patterns applied across the Spec Kitty codebase, mapping recurring implementation idioms to the architecture components they realize (2.x-era record).
doc_status: active
updated: '2026-09-08'
related:
- docs/architecture/04_implementation_mapping/README.md
- docs/architecture/status-model.md
---
# Core Code Patterns Applied in the Codebase

| Field | Value |
|---|---|
| Status | Draft |
| Date | 2026-05-14 |
| Scope | Catalog of recurring code patterns used across Spec Kitty modules |
| Parent | [Implementation Mapping](README.md) |

## Purpose

This is the in-code conventions catalog. It is the answer to: "When I open a
new module in Spec Kitty, what shapes should I expect to see, and which one
should I reach for when adding code?"

Each entry names the pattern, links to the doctrine tactic that codifies it,
points at one or two canonical implementations already in the tree, and
states when to use it (and when not).

This document is descriptive, not aspirational. Every entry below names a
pattern that currently appears in two or more places in the codebase. Future
contributions to this catalog should keep the same bar — list a pattern only
once it has at least two real consumers.

---

## 1. Rule-Based Pipeline (Chain of Responsibility)

**Doctrine:** [`chain-of-responsibility-rule-pipeline`](../../../packs/built-in/tactics/code-patterns/chain-of-responsibility-rule-pipeline.tactic.yaml)

A pipeline of small, pure functions, each one (1) checking applicability,
(2) optionally executing its narrow piece of work, and (3) returning a result
object that the runner threads to the next function in the chain.

Three flavors are in use, distinguished by what each rule produces:

| Flavor | Rule contract | Composition |
|---|---|---|
| **Validator** | `(input, ctx) -> list[Finding]` | Accumulate findings; order usually free; no short-circuit |
| **Transformer** | `(state, ctx) -> StepResult(state', actions, error?)` | Thread state forward; order matters; short-circuit on `error` |
| **Scorer** | `(candidate, ctx) -> float` | Weighted sum; global adjustments applied outside the rule set |

**Canonical implementations in tree:**

- Validator: `src/specify_cli/audit/detectors.py` (`detect_legacy_keys`,
  `detect_forbidden_keys`, `detect_corrupt_jsonl`); composed by
  `src/specify_cli/audit/classifiers/*` (one classifier per artifact type).
- Validator (class-based): `src/specify_cli/charter_runtime/lint/checks/*` —
  `OrphanChecker`, `StalenessChecker`, `ContradictionChecker`,
  `ReferenceIntegrityChecker`, each with `run(drg, scope) -> list[LintFinding]`.
- Transformer: `src/specify_cli/migration/canonicalization.py::CanonicalRule`
  (Protocol + `apply_rules` runner). Consumed by
  `src/specify_cli/migration/mission_state.py::_canonicalize_status_row` and
  `src/specify_cli/migration/rebuild_state.py`.
- Scorer: `src/charter/offering/agent_profiles/repository.py::_score_profile` —
  DDR-011 weighted-signal profile matching.

**Reach for it when:** you have 3+ independent decisions over a shared input
shape and a uniform per-decision contract. Cognitive complexity stays low,
adding/removing a rule is a localized change, and each rule is independently
testable as a value transformer.

**Do not force it onto:** CLI multiplexers (extract per-mode runners
instead), renderers/formatters (often deliberately linear for traceability —
see `_auth_doctor.render_report`), orchestrators with side effects.

---

## 2. Append-Only Event Log + Reducer

**Reference documentation:** [Status Model](../status-model.md);
canonical specs in
`kitty-specs/034-feature-status-status-state-model-remediation/data-model.md`.

Per-mission state is persisted as an append-only JSONL event log
(`status.events.jsonl`). A deterministic reducer (`materialize()`) replays
the events to produce a current-state snapshot (`status.json`). The event log
is the sole authority; the snapshot is derived.

Properties:

- **Immutable history.** Events are never edited or deleted; corrections are
  represented as new events with a `from_lane` reflecting the prior state.
- **Deterministic projection.** Same event sequence always produces the same
  snapshot. The reducer is a pure function.
- **Single entry point for mutation.** `emit_status_transition()` validates
  the (from, to) transition, persists the event, regenerates the snapshot,
  and pushes views. No code path bypasses it.

**Canonical implementation:** `src/specify_cli/status/` —
`store.py` (JSONL I/O), `reducer.py` (event → snapshot),
`transitions.py` (legality matrix), `emit.py` (orchestration).
Per-merge state at `src/specify_cli/consolidation/state.py` uses the same event-log
shape for resumable merge operations.

**Reach for it when:** you need an audit trail, resumable operations after a
crash, or a single source of truth across multiple readers. The cost is that
every mutation becomes an event, which feels heavy on small problems — match
the pattern to genuine state-machine work, not every dict update.

---

## 3. Two-Source Doctrine Repository (Shipped + Project Override)

**Doctrine:** Implemented in `src/charter/offering/base.py::BaseDoctrineRepository`.

Doctrine artifacts (tactics, directives, paradigms, toolguides, agent
profiles) load from **two sources**: the shipped package data
(`rglob("*.tactic.yaml")` under the shipped tree) and a project override
directory (non-recursive `glob` by default). Field-level merge semantics let
a project replace specific fields without redeclaring the whole artifact.

Properties:

- Shipped is authoritative and never modified by user code.
- Project overrides are additive and field-scoped.
- Schema validation runs against both sources via `validation.py` modules.
- Inline references to other artifacts are rejected (`reject_inline_refs`) —
  artifacts reference each other by id, never by embedding.

**Canonical implementations:** `src/charter/offering/tactics/repository.py`,
`src/charter/offering/directives/repository.py`,
`src/charter/offering/agent_profiles/repository.py`.

**Reach for it when:** introducing a new artifact type that benefits from
both a shipped default and project-level override. Use the existing
`BaseDoctrineRepository[T]` generic; do not write a parallel loader.

---

## 4. preflight validation with Structured Result Object

**Doctrine:** Reflected in
[`refactoring-extract-first-order-concept`](../../../packs/built-in/tactics/refactoring/refactoring-extract-first-order-concept.tactic.yaml)
applied to the "validate-then-act" boundary.

Before any non-trivial mutating operation (merge, migration, upgrade), a
`run_preflight(...) -> PreflightResult` checks all preconditions and returns
a structured result containing per-target status entries plus an aggregated
`passed` flag. The mutating function never starts work without consulting
preflight first, and never repeats preflight's checks itself.

Properties:

- The preflight result is a value object (dataclass) — no behavior, only
  data. Callers branch on `passed` and surface `errors` / `warnings` to the
  user.
- Per-target detail (per-WP status, per-file findings) lives on the result
  so the user can see *which* item failed without re-running.
- Preflight is idempotent and side-effect-free.

**Canonical implementations:** `src/specify_cli/consolidation/preflight.py`
(`PreflightResult`, `WPStatus`); the same shape extends to
`src/specify_cli/post_merge/` and the bulk-edit gate.

**Reach for it when:** an operation has expensive setup or destructive
effects and needs to fail fast with actionable detail. Do not inline the
checks into the mutator — split for testability and reusability.

---

## 5. Pure-Function Finding (Code / Severity / Path / Detail Tuple)

A `Finding`-shaped dataclass appears across audit, charter-lint, and bulk-edit
modules. The shape is uniform:

```
@dataclass(frozen=True)
class XxxFinding:
    code: str           # machine-readable category (LEGACY_KEY, MISSING_EVIDENCE, ...)
    severity: Severity  # info | warning | error
    artifact_path: str  # forward-slash relative path
    detail: str         # short human-readable explanation
```

Properties:

- Frozen / immutable — findings flow through pipelines as values.
- The `code` is documented in an `ERROR_CODES.md` adjacent to the module
  that produces it. Codes are part of the public contract; renames are
  breaking.
- Findings compose into `list[Finding]` via `.extend()` or
  `itertools.chain.from_iterable`.

**Canonical implementations:**

- `src/specify_cli/audit/models.py::MissionFinding`
- `src/specify_cli/charter_runtime/lint/findings.py::LintFinding`
- `src/specify_cli/cli/commands/review/ERROR_CODES.md` and adjacent finding
  emitters in `review/`.

**Reach for it when:** a new module needs to emit machine-readable
observations about an input. Reuse the existing `MissionFinding` or
`LintFinding` shape; do not introduce a third type unless it carries
genuinely new fields (e.g. structured fix suggestions).

---

## How to Extend This Catalog

To add a pattern to this catalog:

1. The pattern must already appear in **two or more** modules in the
   codebase. New patterns introduced by a single feature do not belong here
   yet.
2. There must be a corresponding doctrine artifact (tactic, directive, or
   toolguide) that codifies the pattern. The catalog entry links to it.
3. Cite canonical implementations by file path. Keep the citation small (two
   or three exemplars), not exhaustive.
4. State when **not** to use the pattern. Catalog entries without a
   counter-indication tend to drive over-application.

This catalog is reviewed as part of mission-review for any mission that
introduces or extracts a pattern. If a refactor turns three ad-hoc
implementations into one shared one, the consolidated location updates the
relevant entry here.
