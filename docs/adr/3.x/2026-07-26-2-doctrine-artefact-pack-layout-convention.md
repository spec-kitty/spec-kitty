---
title: 'ADR: doctrine artefacts live at `<type>/<pack>/[<category>/]<name>` — misplacement is an error, not invisibility'
description: 'Doctrine artefacts must sit at `<type>/<pack>/[<category>/]<name>`; a file placed directly under `<type>/` is a loud error rather than silently invisible to the loader.'
status: Accepted
date: '2026-07-26'
doc_status: active
kind: ADR
updated: '2026-07-26T00:00:00Z'
---

**Status:** Accepted

**Date:** 2026-07-26

**Deciders:** Operator (Stijn Dejongh), who named both the convention and its future form:
*"I would expect it to be `assets/built-in/audiences`, as per `type/pack/<name>` repository
convention. After extract of our doctrine packs to a secondary repository (future scope),
that would become `<pack id>/type/name`."*

**Technical Story:** surfaced while triaging an asset-discovery finding on
[#2918](https://github.com/Priivacy-ai/spec-kitty/pull/2918) during the #2935
doctrine-authoring session (PR [#2936](https://github.com/Priivacy-ai/spec-kitty/pull/2936)).
Sibling ADR [2026-07-26-1](2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md)
covers the *relationship* axis of the same "doctrine layer predates its own canonical model"
problem; this one covers the *physical layout* axis.

---

## Context and Problem Statement

Doctrine artefacts resolve from a three-part path: the **type** (plural kind directory), the
**pack** (provenance layer), and the artefact **name**, with an optional **category** grouping
in between. The shipped built-in tree follows it — `tactics/built-in/testing/`,
`toolguides/built-in/system_tools/`, `styleguides/built-in/writing/` — and both resolvers
depend on it:

* the per-kind repositories scan **only** `<type>/built-in` (`_default_builtin_dir()` →
  `Path(__file__).parent / "built-in"`);
* DRG node discovery (`_discover_built_in_artifact_nodes`) scans `<plural>/built-in` and
  `rglob`s beneath it, so categories *inside* the pack layer are found automatically.

**Nothing enforces the layout.** An artefact placed outside `<type>/<pack>/` is not rejected —
it is simply never loaded, never registered as a DRG node, and therefore never resolvable and
never a legal edge target. The failure mode is **silent invisibility**, which is the worst
available outcome: the file looks authored, passes review, and does nothing.

Three classes of evidence, all found by inspection rather than by any gate:

1. **#2918 inverted pack and category.** It ships assets at `assets/audiences/built-in/*.asset.yaml`
   instead of `assets/built-in/audiences/`. Because the base directory is fixed at
   `assets/built-in`, those artefacts are invisible to node discovery. This was initially
   diagnosed as an extractor bug ("the extractor misses `assets/<subdir>/built-in/**`") and a
   widening of the scan was drafted. That diagnosis was wrong: the extractor is correct and the
   directory is misplaced.
2. **Nine pre-existing artefacts sit outside any pack layer**, all confirmed dead (nothing loads
   them, by id or by path — `tests/doctrine/paradigms/conftest.py` builds its own copy in a tmp
   dir):
   * *three byte-identical duplicates* of live built-ins — `tactics/tdd-red-green-refactor`,
     `tactics/zombies-tdd`, `styleguides/writing/kitty-glossary-writing`;
   * *two stale divergent copies* — `tactics/acceptance-test-first` and
     `tactics/glossary-curation-interview` differ from their built-in twins (the strays lack the
     inline `references:` blocks their twins carry). Two files claiming one artefact id with
     different content is an **edit-the-wrong-file trap**;
   * *four seed stubs* from the framework's first commit — `directives/test-first` (`TEST_FIRST`),
     `paradigms/test-first`, `styleguides/python-implementation`,
     `toolguides/powershell-syntax`. The first three are content-free placeholders superseded by
     real built-ins; the fourth points at a genuine 245-line guide that has been unreachable the
     whole time.
3. **The kind READMEs document a pack layer that does not exist** — `src/doctrine/toolguides/README.md`
   and `src/doctrine/paradigms/README.md` describe `<type>/shipped/*.yaml`, and
   `tests/glossary/test_seed_schema.py` names `src/doctrine/tactics/shipped/...`. On disk the pack
   layer is always `built-in`. A third name for one slot.

## Decision Drivers

* **Silent invisibility is unacceptable** — a misplaced artefact must fail loudly. This is the
  charter's architectural-gate standing order (close the defect class by construction with a
  non-vacuous gate) applied to layout.
* **Single canonical authority** — one artefact id, one file. The two divergent duplicates are a
  direct violation.
* **Forward compatibility with pack extraction** — doctrine packs will move to their own
  repository; the layout decided now should survive that move as a rotation, not a redesign.
* **Campsite cleaning** — the litter class is small enough (9 files) to clear in the same change
  that lands the gate, so the gate ships with nothing to allowlist.

## Considered Options

* **Option 1 (chosen)** — Pin `<type>/<pack>/[<category>/]<name>`, clear the 9, land a
  non-vacuous gate with an empty allowlist.
* **Option 2** — Widen the resolvers to accept `<type>/<category>/<pack>/` too (the shape #2918
  used), making both layouts legal.
* **Option 3** — Pin the convention in docs only; no gate.
* **Option 4** — Land the gate with the 9 frozen as a shrink-only baseline; clear them later.

## Decision Outcome

**Chosen option: 1.**

The layout this ADR pins:

```text
src/doctrine/<type>/<pack>/[<category>/]<name>.<kind>.yaml
                   │       │            │
                   │       │            └─ artefact file, id matches its content
                   │       └─ OPTIONAL grouping, nests INSIDE the pack
                   └─ provenance layer: `built-in` today (org/project layers overlay it)
```

1. **`<type>/<pack>/` is mandatory.** An artefact directly under `<type>/` is misplaced.
2. **Categories nest inside the pack, never above it.** `assets/built-in/audiences/` is correct;
   `assets/audiences/built-in/` is not. This is the #2918 correction.
3. **`built-in` is the only spelling of the built-in pack layer.** `shipped/` is a phantom — the
   README and test references to it are stale and get corrected.
4. **Misplacement is an error.** A gate rejects any `*.<kind>.yaml` under `src/doctrine/` that is
   not at a legal path, so the failure mode becomes a red test rather than a silently dead file.
   The gate is non-vacuous (a self-mutation case proves it fails on a planted violation) and its
   allowlist is **empty** — there is nothing to grandfather, because the 9 are cleared in the same
   change.
5. **Mission-tier kinds are outside this rule**, because they resolve from their own
   documented locations rather than from the artifact-tier shape: `template` (mission-tier,
   empty glob), `anti_pattern` (hand-authored inside graph fragments, no standalone file), and
   `mission_step_contract` — which lives at `missions/built_in_step_contracts/`, the path
   `extractor.py::_iter_step_contract_data` documents as *authoritative*; there is no
   `mission_step_contracts/` directory at all. This carve-out was discovered *by* the gate
   (17 step contracts flagged on its first run) and is pinned **positively** — the gate also
   asserts step contracts exist at that path and appear nowhere else — so "it's mission-tier"
   cannot become a hiding place for a genuine stray.
6. **Future form, after packs are extracted to their own repository:**
   `<pack id>/<type>/[<category>/]<name>`. The pack becomes the outermost segment (it is the repo
   root), so the migration is a **rotation of the first two segments**, not a re-layout — the
   type/category/name tail is unchanged. Recorded so the extraction mission inherits a decision
   instead of re-litigating one.

### Disposition of the nine

| Artefact | Action | Why |
| --- | --- | --- |
| `tactics/tdd-red-green-refactor`, `tactics/zombies-tdd`, `styleguides/writing/kitty-glossary-writing` | delete | byte-identical to the live built-in |
| `tactics/acceptance-test-first`, `tactics/glossary-curation-interview` | delete | stale strays; the built-in twin is authoritative and richer |
| `directives/test-first`, `paradigms/test-first` | delete | content-free stubs; the live tests-doctrine authority is `DIRECTIVE_041` + the #2935 series |
| `styleguides/python-implementation` | delete | superseded by built-in `python-conventions` |
| `toolguides/powershell-syntax` + `POWERSHELL_SYNTAX.md` | **promote** into `built-in/` | 245 lines of real guidance; the toolguide tests already name the `built-in/` path |

Note on the two `test-first` stubs: the #2935 decision was to *reconcile* them into the new
`paradigm:tests-as-scaffold-not-friction` rather than drop them blind. On inspection there is
nothing to fold — between them they carry an id, a title, and a one-line summary, with no
procedures, steps, or rules. The reconciliation is therefore honestly a no-op, and recorded as
such rather than dressed up as a merge.

### Consequences

#### Positive

* Misplaced artefacts fail at test time instead of disappearing.
* One artefact id → one file; the divergent-duplicate trap is removed.
* A real 245-line PowerShell guide becomes reachable for the first time.
* Pack extraction inherits a pinned target layout.

#### Negative

* The gate constrains where future artefacts may live, and contributors adding a new category
  must put it inside the pack layer — the opposite of the intuition #2918 followed. The gate's
  failure message must therefore state the correct shape, not merely reject.
* Promoting the PowerShell toolguide makes a previously-dead artefact live. That is the point,
  but it is a behavioural change riding along with a layout cleanup, and is called out in the PR.

#### Neutral

* Org/project pack layers overlay the same `<type>/<pack>/` shape and are unaffected.
* The `assets/` tree keeps its loose-contract sidecar convention; only its directory nesting is
  constrained.

### Confirmation

* The layout gate fails on a planted misplaced artefact (self-mutation case) and passes on the
  shipped tree with an **empty** allowlist.
* `find src/doctrine -name '*.<kind>.yaml'` yields only paths matching
  `<type>/<pack>/[<category>/]<name>`.
* `TerminologyGuard`-style README/test references to `shipped/` are corrected to `built-in/`.
* The promoted PowerShell toolguide loads through `ToolguideRepository` and appears as a DRG node.
* Regenerating the DRG fragments after the cleanup produces no unexpected node loss (the deleted
  strays were never nodes).

## Pros and Cons of the Options

### Option 1 — Pin the layout, clear the litter, gate it (chosen)

**Pros:** removes the silent-invisibility class outright; gate ships with an empty allowlist, so
it can never be read as "the violations are acceptable"; corrects #2918's diagnosis before the
wrong fix (widening the extractor scan) is built.
**Cons:** widens this PR by a cleanup; makes one dormant artefact live.

### Option 2 — Accept both layouts in the resolvers

**Pros:** #2918 needs no change; contributors cannot get it wrong.
**Cons:** two legal shapes for one concept — the same two-authority smell as the sibling ADR,
and it doubles the scan surface for every kind forever. It also makes the pack layer's *position*
meaningless, which breaks the clean rotation to `<pack id>/<type>/...` on extraction. Rejected.

### Option 3 — Document only, no gate

**Pros:** zero risk to the current tree.
**Cons:** documentation already exists and is already wrong (the `shipped/` phantom). Convention
without enforcement is exactly how nine dead files and #2918 happened. Rejected.

### Option 4 — Gate with the 9 frozen as a baseline

**Pros:** narrower change; standard charter fallback for a litter class too big to clear.
**Cons:** the class is nine files and five of them are provable duplicates — small enough that a
baseline would be ceremony, and a frozen list of dead files invites a future reader to assume
they matter. Rejected on size, not on principle.

## More Information

* Resolver scan paths: `src/doctrine/*/repository.py` (`_default_builtin_dir`);
  `src/doctrine/drg/migration/extractor.py::_discover_built_in_artifact_nodes`.
* Sibling axis: ADR 2026-07-26-1 (DRG edges as the relationship authority).
* Originating finding: PR #2918 review; corrected diagnosis recorded in this ADR's context.
