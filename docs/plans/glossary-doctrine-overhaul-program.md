---
title: 'Glossary Doctrine Overhaul — Program Plan'
description: 'Program plan: promote the glossary to a first-order doctrine artefact (GLOSSARY_PACK kind), retire the runtime glossary, wire terminology enforcement, and build the ASSET gate.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/index.md
- docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md
- docs/architecture/doctrine-kinds.md
---

# Glossary Doctrine Overhaul — Program Plan

> **Status (checked 2026-09-30).** Mission A landed: #1418 (the `GLOSSARY_PACK` kind) closed
> on 2026-07-22 via PR #2852, and `ArtifactKind.GLOSSARY_PACK` exists in
> `src/charter/offering/artifact_kinds.py`. Mission D has not shipped: #2599 (executable
> ASSET-kind gate) is open in Product backlog. Mission C has not happened: `src/glossary/` is
> still present. Mission B (#2822, #2830, #2823) was not re-checked.
>
> *Original status (2026-07-21): pre-spec planning.* This is the operator-facing cross-mission
> sequencing intent, produced from a 4-lens pre-spec research squad (branch
> `research/glossary-doctrine-artefact`). It precedes the per-mission specs
> (`/spec-kitty.specify`) and follows the distil-then-retire lifecycle of `docs/plans/`.

## Vision

Promote the glossary from a runtime observation pipeline to a **first-order doctrine
delivery artefact**: a new `ArtifactKind.GLOSSARY_PACK` that ships canonical terminology
(definitions, aliases, banned synonyms) as an activatable, distributable doctrine pack —
and deliver terminology **adherence checks as shipped executable code** (the ASSET-kind
gate), not as hardcoded in-repo Python tests.

Beyond the glossary, the executable-ASSET primitive is a **strategic enabler**. Once
doctrine can ship runnable code modules, other repository-specific logic can move onto the
same rail, e.g.:

- Glossary/terminology (contextive) parsing relocated into a shipped code-module asset.
- Repository-local step guards relocated out of core Python into a local doctrine bundle
  (step-contract + guard + directive + toolguide + asset), so repo-specific enforcement
  lives in doctrine rather than in the shared runtime.

This is why the ASSET-kind work is **in scope** for this program rather than deferred: it
unlocks a class of cleanup/simplification, with glossary enforcement as its first consumer.

## Ground truth (from research)

- **#1418 is a draft architecture doc, not a spec; the pack half is fully greenfield.** The
  *term* half exists (`NodeKind.GLOSSARY`, `Relation.VOCABULARY`, runtime `glossary:<hash>`
  DRG bridge). `GLOSSARY_PACK` is not an `ArtifactKind`; `src/doctrine/glossaries/` does not
  exist.
- **The runtime glossary's dynamic pipeline is provably dead** (~2,220 LOC never invoked;
  the runner is never registered). It retains exactly **two** pieces of live authority: the
  104 curated canonical definitions in `spec_kitty_core.yaml`, and an unlisted 8th consumer,
  `tests/architectural/test_glossary_canonical_terms.py`, which imports
  `glossary.scope.load_seed_file` and is the live CI casing gate.
- **#2822 is partly stale:** `GlossarySeedTerm.synonyms_to_avoid` already exists (3 terms
  populate it) but is dropped at runtime and consumed by nothing. The work is *add `aliases` +
  wire enforcement to the inert metadata*, not invent from scratch.
- **#2830 sizing:** 200 mechanical casing fixes, ~70 files, 24 terms. The ticket's "almost
  all `docs/api`" is wrong — the real concentration is `docs/context/orchestration.md`
  (62/200 = 31%). Batch that file first, then by term (5 terms cover 68%).
- **#2823:** one-line fix at `CLAUDE.md:489` (`template` → `procedure`) + a
  non-charter-activatable note for `template`/`asset`.

## Keystone reconciliation: #1418 ↔ #2727

As written, #1418 proposes an ACL (`pack_seed_loader.py`) that seeds the pack **into** the
runtime `src/glossary/`. #2727 **deletes** that package. Research resolves the apparent
conflict: the runtime is dead, so **do not seed into it**. Instead —

1. Migrate the 104 curated terms into the built-in `spec-kitty-core` glossary pack.
2. Repoint `test_glossary_canonical_terms.py` at the pack loader (the one hard dependency).
3. Then retire the runtime package.

The #1418 seed-into-runtime ACL is dropped/inverted. This is the single most
important design decision the specs must carry.

## Program shape — four sequenced missions

The **3-mission decomposition philosophy is preserved** (each mission is independently
reviewable, keystone stabilises before dependents); the ASSET-kind work is added as a fourth
mission per the operator decision to build it in-program.

| Mission | Scope | Tickets | Depends on |
| --- | --- | --- | --- |
| **A — Glossary pack kind (keystone)** | New `ArtifactKind.GLOSSARY_PACK` end-to-end (enum, `NodeKind.GLOSSARY_PACK`, `src/doctrine/glossaries/` repo, `DoctrineService.glossaries`, the 3 mirrored kind-lists + `activated_glossary_packs`, `charter/drg.py` maps, extractor + `*.graph.yaml`, doctor); built-in `spec-kitty-core` pack; migrate 104 terms; pack schema carries `aliases`/`banned_synonyms`/`synonyms_to_avoid`. | #1418 | — |
| **D — Executable ASSET-kind gate** | Asset repository, URN→path resolver (stop discarding `path`/`mime`), code-asset entrypoint contract, runner, asset activation; **phased trust model** (below). Greenfield; depends on epic #2535 steps 1–4 landing. | #2599 (epic #2535) | A |
| **B — Enforcement + cleanup** | Ship glossary adherence as a built-in executable ASSET gate (alias/banned-synonym + casing) consuming the pack; fold the two deprecated status-commit synonyms from the legacy denylist; sweep the 200 casing fixes + delete the ratchet; fix CLAUDE.md. | #2822, #2830, #2823 | A, D |
| **C — Retire runtime glossary** | Delete the dead pipeline, cut inert hot-paths, deprecate (not silent-delete) the `spec-kitty glossary` CLI + dashboard handler, delete `src/glossary/`, retire the seed dir. | #2727 | A, B |

**Sequencing note.** Recommended order is **A → D → B → C** so enforcement (B) ships directly
in its target form (a built-in executable asset) rather than as throwaway Python that D would
later re-home. Fallback if D proves too large to land before B: B ships interim data-driven
Python architectural enforcement, and a later increment re-homes it onto the asset rail. This
is an open sequencing decision for the specs, not a settled one.

## Phased trust model for the executable ASSET gate (#2599)

The operator direction is to build the ASSET gate now and **defer the security concerns that
do not yet apply** — without shipping an actual RCE surface. The resolution is a phased trust
model keyed on provenance:

- **Phase 1 (this program) — built-in provenance only.** A built-in asset is Spec Kitty's own
  shipped code; executing it is the same trust level as the rest of the CLI, so the
  RCE-surface concern (which is about third-party / org-pack code) does not yet apply. Phase 1
  keeps the cheap, load-bearing guards from day one: `review.allow_executable_gate_assets`
  opt-in **default-OFF**, per-invocation **timeout**, **fail-OPEN**, and
  **structured-verdict-or-warn**. Provenance is hard-restricted to `built-in`.
- **Deferred (follow-up) — org-pack / third-party provenance.** The expensive hardening — full
  sandboxed runner, interpreter allowlist / no-shell — is deferred to the increment that first
  enables **non-built-in** asset execution, because that is the only point at which it becomes
  load-bearing.

We are **not** deferring the provenance gate or the default-off flag (cheap and load-bearing);
we are deferring the sandbox/interpreter-hardening depth that only matters once untrusted
provenance can execute.

## Correctness / feasibility traps for the specs

- **URN spelling.** The pack URN must be `glossary_pack:` (underscore) — the DRG URN regex and
  the `prefix == kind.value` assertion (`src/doctrine/drg/models.py:19,117-121`) reject
  #1418's hyphenated `glossary-pack:`. Hyphen is the operator token only.
- **Silent-invisibility guard.** Packs reach charter resolution only if the extractor emits
  them *and* a `*.graph.yaml` fragment ships. Mission A needs an explicit "resolves as a loaded
  node" test (the fakeable-failure guard pattern), or built-in packs load but are invisible.
- **Kind classification.** `GLOSSARY_PACK` joins the 8-kind charter-activatable universe, NOT
  the `{template, asset}` exclusion set. Copy the `directive` kind's wiring; do not copy
  `asset`.
- **Three mirrored kind-lists** (`pack_context._BUILTIN_ARTIFACT_KINDS`,
  `activations._ALLOWED_KINDS`, `org_pack_loader._ORG_DRG_CANONICAL_KINDS`) are drift-guarded
  to move in lockstep — all three must be updated together.

## Boundaries (do not touch)

- **NOT #2653** (prose-only: `docs/context/`, `glossary/README.md`) — bounded-context #1/#3.
- Doctrine-side tests (`test_glossary_link_integrity`, `test_glossary_node_kind`,
  `scripts.docs.glossary_linker`) — leave alone.
- Epic **#1629** framing: this program is bounded-context #2 (runtime/project glossary state);
  context #1 is the #1418 destination, context #3 is presentation surfaces.

## Research artefacts

Full lens briefs (pre-spec, scratchpad, distil into per-mission `research.md`):

- `00-consolidated-pre-spec-brief.md` — this synthesis.
- `01-doctrine-glossary-kind.md` — #1418 design + "add an ArtifactKind" checklist.
- `02-runtime-glossary-retirement.md` — 7-surface migrate/drop matrix + 22-module inventory.
- `03-enforcement-as-asset.md` — current gates + executable-ASSET requirements + trust model.
- `04-terminology-cleanup-inventory.md` — casing baseline breakdown + canonical-term corpus.
