# Tracer: Approach

Mission: `charter-generation-drops-scoped-references-01M3M1KF` (#5257)

## Overall approach

Reuse `charter.activation._catalog_miss`'s already-built, already-tested classification
primitives — `CatalogMissCause`, `classify_scope_filtered_miss`, `classify_catalog_miss` — inside
`_render_kind_references` (`src/charter/activation/compiler.py`) rather than inventing a parallel
classification scheme (DIRECTIVE_044, single-canonical-authority). `_render_kind_references` does
not currently consult these primitives at all — it just appends an opaque `"Unresolved reference:
<kind>/<id>"` string and drops the reference. The fix wires the existing mechanism in, rather than
duplicating its logic.

Reuse `BaseDoctrineRepository.scope_filtered_ids` (`src/charter/offering/base.py`, a `frozenset`
property already populated at repository load time) to distinguish "present but filtered" from
"never existed": every raw per-kind repository `_raw_kind_repository` returns (StyleguideRepository,
ToolguideRepository, AgentProfileRepository, etc. — all subclass `BaseDoctrineRepository`) already
exposes this set for free; no new tracking mechanism is needed.

Reuse the existing placeholder-construction pattern (`_doctrine_yaml_reference`,
compiler.py ~line 1487, which already builds a `CharterReference` with
`summary="Definition unavailable in bundled doctrine."` when a YAML source is absent — the paradigm
kind's existing precedent) as the TEMPLATE (not a direct reuse — `_doctrine_yaml_reference` operates
on raw YAML dicts from `_index_yaml_assets`, while the DRG-backed kinds this mission fixes go through
typed repository models via `_doctrine_model_reference`) for a new placeholder path inside
`_render_kind_references`.

**The placeholder path is scoped to the `SCOPE_FILTERED` cause only — Contract C4 stands** (see
tracer-design-decisions.md's "WP-CORE's placeholder path is scoped to `SCOPE_FILTERED` only" entry
for the full reasoning; this reconciles plan-review finding PLAN-GOV-001 against the prior,
currently-tested `Contract C4`, issue #4785, `kitty-specs/charter-catalog-coherence-01M2XQQF/contracts/behavior-contracts.md`).
An unresolved id whose raw-repository miss is classified `SCOPE_FILTERED` (present on disk,
excluded solely by language/scope — `raw_id in repository.scope_filtered_ids`) is PRESERVED as a
placeholder reference (never dropped) with a reason-bearing diagnostic, **uniformly regardless of
cardinality within that cause** — one scope-filtered id or every scope-filtered id of a kind — which
satisfies FR-001's "preserve OR loudly report" requirement via the simpler, single-mechanism branch:
**placeholder-preservation always for this cause**, not a second, parallel fail-closed/non-zero-exit
code path. An unresolved id classified `MISSING_ARTIFACT`/`TYPO_SUSPECTED` (genuinely no bundled
definition anywhere) stays on the EXISTING Contract-C4-compatible diagnostics-only path — no
placeholder row, `references` unchanged at `[]` for that id — with a reason-bearing diagnostic
string satisfying the disjunctive "loudly report" branch instead.

## Rejected alternative: a hard fail-closed exit branch (for the `SCOPE_FILTERED` cause)

A second design considered was: on any `SCOPE_FILTERED`-caused unresolved id, exit `charter
generate` non-zero before writing any catalog (the spec's FR-001 explicitly allows this as an
alternative-satisfying mechanism). Rejected in favor of always-placeholder-for-`SCOPE_FILTERED`
because:

- **Uniform mechanism within the cause, no cardinality special-casing (C-002).** A single-scope-
  filtered-id case and an every-scope-filtered-id-of-a-kind case (Acceptance Scenario 4 / SC-005) are
  handled by the exact same code path with no branch on "how many ids are affected" — a fail-closed
  design would need a second branch deciding WHEN to exit vs. WHEN to placeholder, which is exactly
  the kind of cardinality special-casing C-002 forbids in spirit (it explicitly forbids hardcoding
  the six named ids, but the same principle — no special-cased branching around this defect class —
  argues against a cardinality-conditioned exit decision too).
- **Matches the existing paradigm-placeholder precedent.** `_doctrine_yaml_reference` already
  placeholders an absent paradigm source rather than failing the whole `generate` invocation; the
  scope-filtered DRG-backed kinds gain the same behavior, keeping the generator's overall failure
  posture consistent across all reference kinds for this cause — while genuinely-nonexistent ids
  keep the separate, already-established diagnostics-only posture Contract C4 pins.
- **Satisfies SC-005's aggregate case for free.** "Every activated toolguide id unresolvable [by
  language scope]" needs no special handling under always-placeholder-for-`SCOPE_FILTERED` — each
  one becomes a placeholder, `catalog.references` stays structurally valid and non-empty for that
  kind (never a silently-empty section), and the diagnostics/`unresolved_references` list names all
  of them. A fail-closed design would need to detect "the whole kind is empty" as a distinct trigger
  condition; always-placeholder needs no such detection.
- **Idempotency (NFR-001) is simpler to prove.** A placeholder path produces the same
  `catalog.references` content on every repeated run against an unchanged repo — a fail-closed path
  that sometimes exits non-zero and sometimes doesn't (depending on unrelated state) is a harder
  idempotency argument.

The always-placeholder-for-`SCOPE_FILTERED` mechanism was verified sound against the actual current
code (not just argued abstractly) before being adopted — see plan.md's "Auto-refresh fail-closed
swallow" section for the parallel verification discipline applied to the preflight fold-in decision,
and tracer-design-decisions.md for the Contract C4 reconciliation and placeholder-text-format
decisions this scoping implies.

## FR-004 JSON-diagnostics design decision

See plan.md's Charter Check → "Whether any contract moves" section for the full reasoning. Summary:
add a new, always-present, additive top-level key `unresolved_references: list[{kind, id, cause,
detail}]` to `charter generate --json`'s output, alongside the existing, unchanged-in-shape
`diagnostics: list[str]` field. Rejected alternative: widening `diagnostics` entries from `str` to
`str | dict` — rejected because it is a breaking shape change for any existing consumer that treats
`diagnostics` as a flat string list, with no compile-time signal to catch the break in a
dynamically-typed JSON contract. Documented as a versioned/additive contract change in
`contracts/charter-generate-json-diagnostics.md`, not a silent one.
