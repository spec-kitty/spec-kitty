---
title: "Test-Quality Doctrine — Artefact Series Proposal"
description: "Curator proposal for the test-slicing/mocking-boundary doctrine series: a Tests-as-Scaffold paradigm, DIRECTIVE_041 disambiguation, exemplar assets, and the DRG edge map."
doc_status: draft
updated: '2026-07-26T00:00:00Z'
related:
- docs/plans/doctrine/test_quality/mocking-boundary-and-test-slicing-research.md
- docs/plans/doctrine/index.md
kind: Planning
---
# Test-Quality Doctrine — Artefact Series Proposal

**Author:** doctrine-daphne (curator scout) + operator refinements
**Date:** 2026-07-26
**Companion to:** [Research findings](mocking-boundary-and-test-slicing-research.md)
**Feeds:** [#2935](https://github.com/Priivacy-ai/spec-kitty/issues/2935)

This is a **design proposal for a curator**, not the artefacts themselves. It supersedes
§8 of the research findings (which recommended a single new artifact from a false-uniqueness
premise — see the reconciliation note below). No files are created by this document.

---

## Binding constraints (added 2026-07-26, after the proposal was first written)

Two ADRs landed on this branch *because* of questions this proposal raised. They are
**binding on the curator** and they change or retire parts of what follows:

1. **[ADR 2026-07-26-1](../../../adr/3.x/2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md)
   — DRG edges are the canonical artefact-relationship authority.** Inline `references:`
   blocks in artefact YAML are pre-DRG residue: frozen, closed to growth, slated for
   migration. Consequences here:
   - Every relationship in this series is an **edge**. No new artefact carries an inline
     `references:` block, and no existing block gains entries.
   - The `<kind>_reference.type` schema enums must **not** be widened. `asset` being
     unnameable inline is correct behaviour. This retires the "asset support is not
     end-to-end" reading of the #2918 finding (see the revised capability section below).
   - `DIRECTIVE_041` is itself one of the legacy carriers (5 structured entries). Those five
     migrate to edges as part of FR-013 — and because editing `041` is its own reviewed change,
     do that migration **with** the intent split rather than as an anonymous line in the bulk
     pass. The new link to the paradigm is an edge from the start.
2. **[ADR 2026-07-26-2](../../../adr/3.x/2026-07-26-2-doctrine-artefact-pack-layout-convention.md)
   — artefacts live at `<type>/<pack>/[<category>/]<name>`.** The pack layer (`built-in`) is
   mandatory and any category grouping nests *inside* it. Consequences here:
   - Asset blobs go to `assets/built-in/<file>` or `assets/built-in/<category>/<file>` —
     **never** `assets/<category>/built-in/`, which is the #2918 mistake.
   - A layout gate now enforces this, so a misplaced artefact fails a test instead of
     silently never loading.

### Prior art found and removed (record, not a fold)

A dormant `paradigm:test-first` ("Test-First Doctrine") and `directive:TEST_FIRST`
("Test-First Development") were discovered outside the pack layer — never loaded, never
activated, invisible to node discovery. The operator's call was to *reconcile* them into
this series rather than drop them blind. On inspection there was **nothing to fold**:
between them they carried an id, a title, and a one-line summary, with no procedures, steps,
integrity rules, or validation criteria. They were deleted as part of the layout cleanup
(`f7ee9fb02`). Recorded here so the reconciliation is honest rather than dressed up as a
merge — but the *names* are a useful warning: do not let this series produce a third
tests-doctrine authority. `DIRECTIVE_041` + the new paradigm are the authority.

---

## Guiding correction — augment-heavy, not create-heavy

An overlap audit against the pack's existing testing doctrine found that most of the
research doc's load is **already carried** by wired, activatable authority:

- `styleguide:test-desiderata-and-boundaries` — the 12 desiderata + boundary-by-responsibility.
- `tactic:test-boundaries-by-responsibility` — the operative "mock only at the border" rule.
- `tactic:function-over-form-testing` — the interaction→outcome assertion shift.
- `tactic:connascence-analysis` — the connascence lens the research calls its backbone.
- `directive:DIRECTIVE_041` "Tests as Scaffold, Not Friction" (`enforcement: required`) — already binds "assert the observable contract, not the internal call graph."

So the series is **augment-heavy, create-light**. This also resolves the external review's
finding #1 (PR #2936): the research doc's "currently unwritten" framing (§6) and its
"create a new binding artifact" recommendation (§8) overclaimed uniqueness; the correct move
is to reconcile and extend the existing wired authority, creating only the genuine deltas.

The genuine deltas: (1) the **positive** allow-list of legitimate mock seams as a citable
rule; (2) the specific failure mode — mocking internal SUT logic to pin a call-contract,
which manufactures a production-unreachable state; (3) a remediation **procedure**
("unfake a test"); (4) the **mindset** currently mis-homed inside a directive.

---

## The operator's topology refinements (applied)

1. **"Tests as Scaffold, Not Friction" is a paradigm (mindset), not a directive.** Create a
   new paradigm; disambiguate `DIRECTIVE_041` so the binding rule stays a directive and the
   mindset/why moves to the paradigm, relinked via `refines`.
2. **Test Desiderata is a complementary checklist that is part of the paradigm** — relinked,
   not re-kinded (it stays a styleguide; its enumerated list becomes an asset).
3. **Checklists → assets.** The `asset` kind is a loose-contract blob (markdown/python via a
   `*.asset.yaml` sidecar), resolved-only, referenced via `requires` edges (working precedent:
   `directive:DIRECTIVE_042 --requires--> asset:common-docs-structural-lint`). Move duplicated
   checklists (the desiderata list; the Quad-A definition) into shared assets.
4. **Exemplar assets for exhaustive examples.** Short good/bad snippets stay inline; the full
   UserRegistration slicing case and the #2934 before/after become exemplar assets, referenced
   from the good artefacts (never emitted from anti-pattern nodes — those are `rejects` targets
   only).

---

## Proposed series

### Create

- **`paradigm:tests-as-scaffold-not-friction`** [activatable] — the mindset: tests protect
  change; the false-confidence (mocked-out behaviour) / false-friction (implementation-coupled
  assertions) duality; Beck's desiderata as the value system; connascence framing; the
  policy-choice honesty clause. Carries the migrated `DIRECTIVE_041.intent`.
- **`directive:DIRECTIVE_047` — Mock Only at the Responsibility Border** [activatable,
  `required`] — the positive allow-list (other-domain / filesystem / DB / rare system-logic) +
  the manufactured-state failure mode. `requires` DIRECTIVE_041; does not restate it.
- **`procedure:unfake-an-over-mocked-test`** [activatable] — the six-step remediation.
- **`anti_pattern:mock-internal-sut-logic`** [resolved-only], **`anti_pattern:assert-on-mock-interactions`** [resolved-only]
  — nodes in `anti_pattern.graph.yaml`, `rejects` targets only.
- **Assets** [resolved-only]: `asset:test-desiderata-checklist`, `asset:quad-a-test-structure`,
  `asset:exemplar-slicing-user-registration`, `asset:exemplar-2934-unfake-merge-test` (markdown
  blobs under `assets/built-in/` + `*.asset.yaml` sidecars).

### Augment (edit, no new node)

- `DIRECTIVE_041` — move `intent` (mindset) into the paradigm; shrink to a pointer; add
  `--refines--> paradigm`.
- `styleguide:test-desiderata-and-boundaries` — add the "Isolated ≠ isolate-via-mocks" and
  Gold-Plating traps + the connascence-of-a-mock line; extract the desiderata list to the asset.
- `styleguide:testing-principles` / `python-conventions` / `java-conventions` — extract the
  shared Quad-A **definition** to the asset; keep language-specific code examples inline.
- `tactic:test-boundaries-by-responsibility` — add the rare system-logic exception + a
  `failure_modes` entry; `rejects` the internal-mock anti-pattern; `suggests` the slicing exemplar.
- `tactic:function-over-form-testing` — add the #2934 one-liner; `rejects` the interaction-assert smell.

---

## DIRECTIVE_041 disambiguation (stays vs moves)

- **Stays in the directive** (binding surface): `enforcement`, `scope`, all `procedures`,
  `integrity_rules`, `validation_criteria`, `references`.
- **Moves to the paradigm** (mindset): the long `intent` block ("Tests must protect change,
  not obstruct it… tests that pass for the wrong reason are friction…"). Replace 041's `intent`
  with a one-line pointer to the paradigm.
- **Relink relation: `refines`** (directive sharpens the mindset into an enforceable rule).
  Not `specializes_from` (that is agent_profile→agent_profile lineage only). Not `requires`
  (a hard cascade-prerequisite; the rule can operate as a checklist independently) — unless the
  curator wants the paradigm auto-pulled whenever an action scopes 041, in which case `requires`
  is the documented fallback trade-off. **This is the first `refines` edge in the built-in
  graph** — confirm it round-trips through the org→DRG bridge on regeneration.

---

## DRG edge map (source --relation--> target)

Paradigm hub:
- `paradigm:tests-as-scaffold-not-friction --requires--> styleguide:test-desiderata-and-boundaries`
- `paradigm:… --suggests--> styleguide:testing-principles`, `tactic:connascence-analysis`,
  `asset:quad-a-test-structure`, `asset:exemplar-slicing-user-registration`
- `paradigm:… --rejects--> anti_pattern:mock-internal-sut-logic`, `anti_pattern:assert-on-mock-interactions`

Directives:
- `directive:DIRECTIVE_041 --refines--> paradigm:tests-as-scaffold-not-friction`
- `directive:DIRECTIVE_047 --refines--> paradigm:tests-as-scaffold-not-friction`
- `directive:DIRECTIVE_047 --requires--> directive:DIRECTIVE_041`
- `directive:DIRECTIVE_047 --suggests--> tactic:test-boundaries-by-responsibility`,
  `tactic:function-over-form-testing`, `styleguide:test-desiderata-and-boundaries`,
  `asset:exemplar-2934-unfake-merge-test`
- `directive:DIRECTIVE_047 --rejects--> anti_pattern:mock-internal-sut-logic`, `anti_pattern:assert-on-mock-interactions`

Procedure:
- `procedure:unfake-an-over-mocked-test --requires--> tactic:test-boundaries-by-responsibility`
- `procedure:… --suggests--> directive:DIRECTIVE_047`, `tactic:function-over-form-testing`, `asset:exemplar-2934-unfake-merge-test`
- `procedure:… --rejects--> anti_pattern:mock-internal-sut-logic`

Tactics / checklist-asset edges:
- `tactic:test-boundaries-by-responsibility --rejects--> anti_pattern:mock-internal-sut-logic`; `--suggests--> asset:exemplar-slicing-user-registration`
- `tactic:function-over-form-testing --rejects--> anti_pattern:assert-on-mock-interactions`
- `styleguide:test-desiderata-and-boundaries --requires--> asset:test-desiderata-checklist`
- `styleguide:testing-principles --requires--> asset:test-desiderata-checklist`, `asset:quad-a-test-structure`
- `styleguide:python-conventions --requires--> asset:quad-a-test-structure`
- `styleguide:java-conventions --requires--> asset:quad-a-test-structure`

Every resolved-only node (asset / anti_pattern) has ≥1 inbound edge from an activatable node — no orphans.

---

## Capability-awareness (intent dominates) — REVISED 2026-07-26

The sibling doctrine PR #2918 was read as showing that **asset support is not end-to-end**, on
two counts. Investigation resolved both, and **neither is an asset-support defect**:

1. *"`type: asset` inside a tactic is schema-rejected."* — **Not a defect.** The
   `<kind>_reference.type` enum belongs to the inline `references:` surface, which ADR
   2026-07-26-1 pins as frozen pre-DRG residue. A kind being unnameable there is the
   deprecated surface correctly refusing to grow. Widening it was drafted and **abandoned**:
   it would have entrenched a second relationship authority. (Worth knowing: all four schema
   copies of that enum had already drifted apart — they omit `asset` *and* `glossary_pack`,
   and the `tactic` copy additionally omits `agent_profile` and `mission_step_contract`. The
   fix is to close the surface, not to reconcile four copies of it.)
2. *"The extractor misses `assets/<subdir>/built-in/**`."* — **Not an extractor defect.** The
   directory was misplaced: #2918 inverted pack and category. Per ADR 2026-07-26-2 the
   correct path is `assets/built-in/audiences/`, which the existing scan already finds via
   `rglob`. A widening of the extractor scan was drafted and **abandoned** in favour of
   fixing the layout and gating it.

This matters as a method note, not just bookkeeping: *intent dominates over capability* means
fix the tooling to serve the intended model — it does **not** mean assume every blocked path
is a tooling gap. Two of the three "prerequisite fixes" this proposal originally called for
dissolved once the intended model was actually pinned. The proposal's design was already
right by construction (edges + `assets/built-in/` paths); what was wrong was the diagnosis of
*why* the alternatives failed.

Residual verification the curator must still run:

1. Confirm the extractor picks up the four new `assets/built-in/*.md` blobs (the layout gate
   now catches misplacement, but node *discovery* is a separate assertion).
2. Re-evaluate the claimed CLI-vs-canonical-validator **parity gap** — `spec-kitty doctrine
   validate` vs the strict canonical tests. Part of the originally-reported gap is likely the
   frozen inline surface behaving correctly; characterize what genuinely diverges before
   "fixing" it, and add a parity test for whatever remains.
3. If a genuine asset-support gap does surface, closing it is **in-scope prerequisite work**,
   not a reason to downgrade the artefacts.

---

## Load-time / validation risks

1. Asset **path containment** — relative, under `assets/`, no `..`/symlink escape (all use `built-in/<file>`).
2. Asset **mime/extension consistency** — `text/markdown ↔ .md`; never declare markdown on a `.py`.
3. **Resolved-only** discipline — assets/anti-patterns are never charter-activated; enter context only via inbound edges.
4. **URN/kind prefix** must equal kind; confirm `DIRECTIVE_047` is free (max present is 046).
5. `enhances`/`overrides` are **not** usable on assets/anti-patterns — dedup is via `requires`→asset edges.
6. Anti-pattern nodes **emit no edges** — route exemplar references through the good artefacts.
7. `refines` **first use — CONFIRMED, and it is a real risk.** Measured relation histogram
   across all 14 shipped fragments: `suggests` 332, `requires` 259, `scope` 157, `rejects` 8,
   `instantiates` 8, `specializes_from` 4, `reconciles_tension` 3, `in_tension_with` 2,
   `applies` 1, **`refines` 0**. So the `041 --refines--> paradigm` edge is genuinely the
   first in any built-in fragment. `refines` has been first-class since #2079 — which fixed a
   silent `refines`→`applies` downgrade in the org→DRG bridge — but *nothing built-in has ever
   exercised that fix*. Verify the round-trip explicitly on regeneration; do not assume.
8. The 041 split must not author an accidental `in_tension_with` — the relation is `refines` (aligned, not competing).
9. Add each anti-pattern/asset **node** in the same change as its referencing edges; regenerate the compiled graph; validate to zero errors.
10. **Golden-count baselines move.** `tests/doctrine/drg/migration/test_extractor_projection.py`
    pins node/edge/orphan cardinality (currently 305/757/32) with a composition ledger in the
    constant's docstring. Every node and edge this series adds must extend that ledger with its
    own entry — the counts are a contract, not an incidental.
11. **Regeneration is via the CLI**, not by hand: `spec-kitty doctrine regenerate-graph`. The
    fragments are `generated_by: drg-migration-v1`; hand-editing them desynchronizes the
    freshness test (`test_shipped_graph_yaml_is_fresh`).

---

## Build order for the curator

0. **Prerequisite (not optional):** freeze the four `<kind>_reference.type` enums with a
   pointer-comment to ADR 2026-07-26-1, and fix the ~10 source sites whose operator-facing
   migration hint names `src/doctrine/graph.yaml` — a file #2680 sharded out of existence.
   Authoring new doctrine while the system's own migration instruction is unfollowable just
   propagates the confusion this series is meant to reduce.
1. Asset blobs + sidecars at `assets/built-in/[<category>/]<file>`; asset nodes in `asset.graph.yaml`.
2. Paradigm; migrate `041.intent` → paradigm; shrink 041's intent to a pointer. **Editing the
   live `enforcement: required` `DIRECTIVE_041` is its own reviewed change — audit inbound
   edges first.** Do not touch its existing inline `references:` block (ADR 2026-07-26-1).
3. `DIRECTIVE_047` + `procedure:unfake-an-over-mocked-test`; two anti-pattern nodes.
4. Excise the desiderata list + language-neutral Quad-A definition from the styleguides (keep language-specific examples inline).
5. Author all edges; regenerate the fragments with `spec-kitty doctrine regenerate-graph`;
   extend the golden-count ledger; run the reference/cross-edge audit + pack validation to zero
   errors; confirm the *Clear Test Boundaries* URL.
6. Update the `doctrine-daphne` profile with the canonical doctrine/charter structure (layout
   convention + edges-not-inline-refs), so the next curator invocation starts from the pinned
   model rather than rediscovering it. A curator profile that does not carry these rules is how
   the #2918 layout mistake happened in the first place.
