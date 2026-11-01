---
title: 'ADR: `shipped` → `built-in` Vocabulary Cutover for Doctrine Layer Label'
description: 'Renames the doctrine layer label from shipped to built-in across identifiers, messages, and CLI JSON output in one breaking cutover with no deprecation window.'
status: Accepted
date: '2026-05-24'
doc_status: active
kind: ADR
updated: '2026-05-24T00:00:00Z'
---

- [ADR 2026-05-16-1 — Doctrine Layer Merge Semantics](2026-05-16-1-doctrine-layer-merge-semantics.md)
- [ADR 2026-05-24-2 — Pack Augmentation Vocabulary](2026-05-24-2-pack-augmentation-vocabulary.md)
**Cross-references**:
- [`2026-05-24-1-charter-freshness-ux-contract.md`](2026-05-24-1-charter-freshness-ux-contract.md) (sibling — consumes the renamed `built-in` label in its freshness banners and preflight output)

## Context

The doctrine layer system has three layers stacked from least- to most-specific:
`built-in → org → project`. The runtime resolves an artifact by reading the
lowest-precedence layer first and overlaying higher-precedence layers on top
of it (per the field-level merge ratified in `2026-05-16-1`).

On disk, the lowest layer has always been called `built-in/` — there are
`built-in/` directories under every artifact kind (`tactics/built-in/`,
`paradigms/built-in/`, `agent_profiles/built-in/`, etc.). But in code,
the same layer is referred to inconsistently:

- Python identifiers in `src/doctrine/base.py` say `_shipped_dir`,
  `_load_shipped_items`, and parameter names like `shipped`.
- Docstrings say `"shipped → org → project"`.
- Log lines say `Skipping invalid shipped {kind}`.
- CLI JSON surfaces (`spec-kitty agent profile list --json`,
  `spec-kitty charter status --json`) emit `"shipped"` as the layer label.
- Test fixtures and assertions across `tests/` bake the literal `"shipped"`.
- Docs and CHANGELOG entries refer to the layer as `shipped` in some
  places and `built-in` in others.

The on-disk vocabulary is canonical (it is what operators see when they
`ls` the doctrine tree), but the in-code vocabulary lags. This asymmetry
hurts readability, makes greps misleading, and confuses pack authors who
read a `built-in/` directory and then see `"shipped"` echoed in `--json`
output.

`2026-05-24-2` added two declarative pack-augmentation fields
(`overrides`, `enhances`) whose target *is* the built-in layer. The new
fields are authored in pack YAML against `built-in` IDs while the runtime
internally still calls that layer `shipped`. Resolving the vocabulary
asymmetry now — at the same time pack augmentation lands — keeps the
mental model coherent for pack authors.

## Decision

Perform a **straight cutover** of the layer label from `shipped` to
`built-in` across all `src/` source surfaces:

1. Python identifiers (functions, methods, parameters, local variables).
2. Docstrings and inline comments.
3. Log / advisory / warning message strings.
4. CLI JSON output values (`spec-kitty agent profile list --json` source label,
   `_warn_project_override` log payload).

The on-disk layout (`built-in/` directories) already uses the target term and
is unchanged.

The cutover is performed without a deprecation window. The CHANGELOG entry
(authored in WP09 of this mission) flags this as a **breaking change** for any
external tooling that pattern-matches the string `"shipped"` in CLI JSON
output. An architectural regression test (FR-016, authored in WP08) asserts
zero occurrences of the literal `"shipped"` as a layer label in `src/` and
`tests/`, preventing regression.

## Alternatives Considered

### A. Dual-emit deprecation period (rejected)

The runtime could emit *both* `"shipped"` and `"built-in"` for one or more
minor versions, signalling deprecation of `"shipped"` and removing it in a
later version. This was rejected because:

- The doctrine pack vocabulary is internal-facing: it is consumed by
  `spec-kitty` operators reading CLI output, not by long-lived external
  pipelines with deployment lag.
- Dual-emit doubles the surface that tests must cover and creates a
  permanent gravitational pull back toward `"shipped"` (engineers reading
  dual-emit code will copy the wrong half).
- The asymmetry is a documented bug (`built-in/` on disk vs `shipped` in
  code), not a feature. Deprecating one half encodes the bug into the
  contract.
- Per R-3 in `research.md`: the surface area is small enough that a
  straight cutover plus CHANGELOG warning is cheaper than a deprecation
  cycle.

### B. Postpone until a major release (rejected)

The cutover could ride alongside a future 4.0 boundary change. Rejected
because:

- The vocabulary mismatch confuses pack authors *today*, especially in
  combination with `2026-05-24-2`'s new `overrides` / `enhances` fields.
- Postponement only enlarges the surface that has to be edited later.

## Consequences

### Positive

- The in-code vocabulary matches the on-disk layout. `grep -r built-in
  src/` returns coherent results.
- Log lines, advisory text, and JSON output use the same word a pack
  author sees when they `ls built-in/`.
- The pack augmentation vocabulary from `2026-05-24-2` lands against
  consistent terminology (pack YAML authors `enhances: <id>` targets the
  `built-in` layer; the runtime now says so in every surface).

### Negative

- Breaking change for any external tooling that pattern-matches
  `"shipped"` in `spec-kitty agent profile list --json` or
  `spec-kitty charter status --json` output. Documented in CHANGELOG
  under the next release.
- A large mechanical edit touches many files. Mitigated by:
  - Authoritative `occurrence_map.yaml` classifying every rename target.
  - Bulk-edit gate enforcing per-commit trace to a classification row.
  - FR-016 architectural regression test (WP08) preventing reintroduction.
- Cross-cutting test failures land in WP07 and are intentionally left
  for WP08 to fix in bulk (per the per-WP scoping in the mission tasks).
  This is not a regression; it is the planned wave boundary.

### Neutral

- The word `"shipped"` remains acceptable in unrelated English contexts
  (e.g. `"the v3.2 release shipped on 2026-05-12"`). Only its use as a
  doctrine layer label is in scope. The `occurrence_map.yaml` codifies
  this distinction.
- Historical text (ADR `2026-05-16-1`, CHANGELOG entries before this
  mission merges, frozen kitty-spec snapshots) is preserved as-is. The
  `historical_preservation` section of `occurrence_map.yaml` lists the
  paths that MUST NOT be edited.

## Cross-references

- [ADR 2026-05-16-1 — Doctrine Layer Merge Semantics](2026-05-16-1-doctrine-layer-merge-semantics.md)
  ratified the field-level merge. This ADR aligns the vocabulary of that
  merge contract with the on-disk layout.
- [ADR 2026-05-24-2 — Pack Augmentation Vocabulary](2026-05-24-2-pack-augmentation-vocabulary.md)
  introduced `overrides` / `enhances` declarative fields whose target is
  the built-in layer. This ADR ensures that target is named consistently
  across code, logs, and CLI output.
- `kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/occurrence_map.yaml`
  is the authoritative per-file classification for the rename.
- `kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/research.md` R-3
  records the decision rationale for straight cutover over dual-emit.
- WP08 authors `tests/architectural/test_no_shipped_layer_label.py`
  (FR-016) to operationalise this ADR on every CI run.
- WP09 authors the CHANGELOG breaking-change entry.
