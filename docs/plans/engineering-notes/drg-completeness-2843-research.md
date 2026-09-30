---
title: 'DRG completeness (#2843/#2847) — pre-spec research squad findings'
description: 'Four-lens pre-spec research findings on the #2833 post-landing residue: relation-description parity, the activation-gate latent bug, and the anti-pattern corpus split.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/index.md
- docs/plans/engineering-notes/doctrine-drg-missing-links-analysis.md
- docs/adr/3.x/2026-07-21-1-in-tension-with-drg-edge.md
- docs/architecture/doctrine-relationships.md
---
# DRG completeness (#2843 / #2847) — pre-spec research squad findings

> **Historical (delivered).** The parked mission this research fed, `drg-relation-parity-activation-gate-01KY48PD`, has since completed (see its `retrospective.yaml` under `kitty-specs/`). Kept as a record; the active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

**Date:** 2026-07-21
**Origin:** post-landing residue of PR #2833 (in_tension_with DRG edges). A bounded 4-lens,
profile-loaded pre-spec research squad (doctrine-daphne, architect-alphonso, paula-patterns,
planner-priti) investigated GitHub issue #2843 before spec. This note is the durable record so
the parked mission can resume without re-running the squad.

## Operator decision — SPLIT

The original #2843 bundle was split into two missions:

- **#2843** (re-scoped) — items 2+3, the small "close what #2833 opened" work. Mission branch
  `doctrine/drg-completeness-2843`.
- **#2847** — item 1 (anti-pattern corpus promotion), carved out as its own mission because it is
  ~22× the size of the other two combined, needs a human curation pass, and has **zero
  build-dependency** on them.

Both are native sub-issues of epic #2466.

## Corrected ground truth (measured, not estimated)

- **136 inline `anti_patterns:` entries / 131 unique**, across **34 authoring files** (18
  styleguides carrying rich 4-field blocks `name`/`description`/`bad_example`/`good_example`; 16
  procedures carrying thin 2-field blocks `name`/`description`). Tactics carry no inline block.
- **Dedup ≈ 0.** The "collapse duplicate copies" premise is false — the inline corpus is a
  disjoint, mostly-unique population. The only exact recurrence is one **byte-identical duplicate
  file** (`styleguides/writing/kitty-glossary-writing.styleguide.yaml` mirrored at
  `built-in/writing/`) — a campsite delete.
- The inline population is **disjoint from #2833's 6 nodes** (those are paradigm-derived and
  appear zero times inline).
- **12** `Relation` members lack descriptions (the issue's "9" was stale; `models.py` docstring
  says twelve).

## Item A (#2843) — relation-description + glossary parity · size S

- Backfill `RELATION_DESCRIPTIONS` (`src/doctrine/drg/models.py`) for: `requires, suggests,
  refines, replaces, enhances, overrides, specializes_from, delegates_to, scope, instantiates,
  applies, vocabulary`.
- **Dual-doc:** the content-equality parity test `tests/doctrine/test_relation_doc_parity.py`
  guards `docs/architecture/doctrine-relationships.md` (widen `_SCOPED_RELATIONS` 3→15); also
  extend `docs/context/charter.md` (decision pending: bring it under the parity check too).
- **Not transcription:** `applies` vs `scope` are semantically contested/mis-wired (`applies`
  has 1 edge, `scope` 157) — an adjudication; `vocabulary`/`refines`/`delegates_to` are "never
  emitted" today and must be described as intended-but-dormant.

## Item B (#2843) — activation-gate consolidation = LATENT CORRECTNESS BUG · size M

Two lenses (alphonso + paula) independently found this is **not a cosmetic refactor**:
`charter/drg.py::_node_is_activated` Step 3 compares canonical node ids (`DIRECTIVE_001`)
against config **stems** (`001-architectural-integrity-standard`), so a populated
`activated_directives` list **silently drops every directive node**. It only appears healthy
because per-ID activation lists are ~always `None` (default-allow). Three sites independently work
around it: `compiler._resolve_config_activated_ids`, `_check_graph_kind_parity`, and #2833's
`_node_is_tension_scan_active`.

Required (for the spec):

1. **Verify first (highest-leverage):** confirm empirically that no production `.kittify/config.yaml`
   populates per-kind `activated_*` lists — decides "latent-bugfix" framing and blast radius.
2. **Red-first characterization test** proving `filter_graph_by_activation` drops a stem≠canonical
   directive node under a populated list (against the real corpus, not hermetic `id==stem` fixtures).
3. **One canonical-URN-aware gate** via a single stem→canonical resolver (home
   `charter.kind_vocabulary`, where `resolve_artifact_urn` lives). Siting (resolve-in-filter vs
   resolve-at-`PackContext` vs resolve-at-gate-boundary) is a `/plan` design decision.
4. **Collapse workarounds honestly:** delete the tension-scan reimplementation
   (`_node_is_tension_scan_active`/`_build_tension_active_urns`/`_resolve_activated_urns_for_kind`)
   so it becomes a plain gate consumer; re-point `_check_graph_kind_parity` (a per-ID **behavior
   upgrade** owned with tests). The compiler `references.yaml` **projection legitimately stays**
   (it builds a catalog id list, not a graph filter) — do not promise deleting it.
5. **5-consumer regression net** (populated-`activated_directives` before/after tests):
   `specify_cli/mission_step_contracts/executor.py`, `charter/reference_resolver.py`,
   `charter/compiler.py` closure, `charter/consistency_check.py::_check_drg_cross_kind_refs`,
   `charter/context.py`.

## Item 1 (#2847) — anti-pattern corpus promotion · size L (own mission)

- **Retain, don't migrate:** `DRGNode` holds only `urn/kind/label/provenance/tags` — no room for
  description/examples. Keep the rich inline blocks (examples co-located); the node is a thin
  queryable handle; the "why" lives on the `rejects` edge `reason`.
- **Extractor-mint, not hand-overlay:** teach `src/doctrine/drg/migration/extractor.py` to mint an
  `anti_pattern` node + `rejects` edge (source = host artefact URN) from each inline block. It has
  no `anti_patterns` path today; hand-authoring 131 nodes in the overlay registry does not scale.
- **Add a `severity`/tag field** (`anti-pattern` | `smell`) to the inline schemas so the ~131
  classification calls are authored, not guessed.
- **Human curation pass (the real weight):** ~6 near-duplicate concept clusters under different
  names (`Over-Mocking`, `Shared Mutable State` ×3, `Gate-hardwiring`, `Meta-tracker` …) that
  exact-name extraction would silently double-mint → a reviewed `name → canonical-urn` map.
- **Integrity:** ~118–131 `rejects` edges; INV-004 validators already enforce the shape (add a
  dup-URN guard); golden-count churn in `tests/doctrine/drg/migration/test_extractor_projection.py`.

## Sequencing

Item A is independent (enum+docs). Item B lands before #2847 (the ~118 anti_pattern nodes ride the
corrected gate; no hard dependency since `anti_pattern:` URNs are slug==id, so they don't hit the
stem≠canonical bug). Full per-lens detail lives in the #2843 / #2847 issue bodies and session
memory (`project_drg_completeness_2843_mission`).
