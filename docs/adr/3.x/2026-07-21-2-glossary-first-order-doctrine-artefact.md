---
title: 'ADR: promote the glossary to a first-order doctrine artefact (GLOSSARY_PACK kind), retire the runtime glossary, and deliver terminology enforcement as an executable ASSET gate'
description: 'The glossary is promoted to a charter-activatable `GLOSSARY_PACK` artefact kind, the runtime glossary retires, and terminology enforcement ships as an executable ASSET gate.'
status: Accepted
date: '2026-07-21'
doc_status: active
kind: ADR
updated: '2026-07-21T00:00:00Z'
---

**Status:** Accepted

**Date:** 2026-07-21

**Deciders:** Operator (Stijn Dejongh); assessment by a 4-lens pre-spec research squad
(2026-07-21, branch `research/glossary-doctrine-artefact`).

**Technical Story:** epics [#1629](https://github.com/Priivacy-ai/spec-kitty/issues/1629)
(glossary coherence slice) / [#2535](https://github.com/Priivacy-ai/spec-kitty/issues/2535)
(doctrine-controlled transition gates); tickets
[#1418](https://github.com/Priivacy-ai/spec-kitty/issues/1418) (glossary as first-order
artifact — keystone), [#2727](https://github.com/Priivacy-ai/spec-kitty/issues/2727) (retire
runtime `src/glossary/`), [#2822](https://github.com/Priivacy-ai/spec-kitty/issues/2822)
(alias/banned-synonym governance), [#2830](https://github.com/Priivacy-ai/spec-kitty/issues/2830)
(retire the casing ratchet), [#2823](https://github.com/Priivacy-ai/spec-kitty/issues/2823)
(stale CLAUDE.md kind table), [#2599](https://github.com/Priivacy-ai/spec-kitty/issues/2599)
(executable ASSET-kind gate handlers). Program plan:
[`docs/plans/glossary-doctrine-overhaul-program.md`](../../plans/glossary-doctrine-overhaul-program.md).
Aligns with [ADR 2026-05-16-1](2026-05-16-1-doctrine-layer-merge-semantics.md).

---

## Context and Problem Statement

Spec Kitty carries **two** glossary subsystems that are drifting apart. The **runtime
glossary** (`src/glossary/`, ~6,379 LOC / 22 modules) is a dynamic observation/extraction/
resolution pipeline seeded from `.kittify/glossaries/<scope>.yaml`. In parallel, #1418 designs
a **static, distributable doctrine glossary** (a first-order artefact) and explicitly names the
runtime package as the thing it supersedes. Maintaining both is a standing tax; meanwhile the
runtime pipeline's enforcement role has already lapsed.

A 4-lens pre-spec research squad established the ground truth:

- **#1418 is a draft architecture doc, not a spec; the pack half is fully greenfield.** The
  *term* half exists (`NodeKind.GLOSSARY`, `Relation.VOCABULARY`, the runtime `glossary:<hash>`
  DRG bridge). `ArtifactKind.GLOSSARY_PACK` does not exist; `src/doctrine/glossaries/` does not
  exist.
- **The runtime glossary's dynamic pipeline is provably dead** (~2,220 LOC never invoked; the
  runner is never registered). All seven consumer surfaces named in #2727 are inert or cosmetic.
  The package retains exactly **two** pieces of live authority: the 104 curated canonical
  definitions in `spec_kitty_core.yaml`, and an *unlisted 8th consumer*,
  `tests/architectural/test_glossary_canonical_terms.py`, which imports
  `glossary.scope.load_seed_file` and is the live CI casing gate.
- **#1418's design contradicts #2727 as written.** #1418 proposes an ACL
  (`pack_seed_loader.py`) that seeds the pack *into* `src/glossary/` — the very package #2727
  deletes.
- **Terminology enforcement is two disjoint hardcoded gates today:**
  `test_no_legacy_terminology.py` (a 2-term git-grep denylist) and the casing gate above.
  `GlossarySeedTerm.synonyms_to_avoid` already exists in the schema (3 terms populate it) but is
  dropped at runtime and consumed by nothing — the metadata rail is present but unwired.
- **The executable ASSET-kind gate (#2599) is a security-sensitive greenfield subsystem** — it
  executes pack-supplied code (RCE-equivalent surface) and its trust model is binding.

## Decision Drivers

- **Single canonical authority** (charter governing principle) — one owning source for
  terminology; collapse the two subsystems onto the doctrine artefact.
- **Glossary & terminology adherence** (charter governing principle) — enforcement must be
  data-driven from the canonical source, not hardcoded in disjoint tests.
- **Executable doctrine as a strategic enabler** — an executable ASSET rail lets
  repository-specific logic (glossary/contextive parsing; repo-local step guards) move out of
  the shared runtime and into shipped doctrine bundles. Glossary enforcement is its first
  consumer, not its only one.
- **Readable, reviewable PRs** (DIRECTIVE_046) — keystone-first decomposition over one
  unreviewable mega-diff.
- **Do not ship an RCE surface** while still deferring hardening that does not yet apply.

## Considered Options

- **Option 1 (chosen)** — Build `GLOSSARY_PACK` as a first-order charter-activatable kind;
  migrate the 104 terms onto it; deliver enforcement as an executable ASSET gate; retire the
  runtime package. Sequenced four-mission program **A → D → B → C**.
- **Option 2** — Follow #1418 literally: keep `src/glossary/` and seed the pack into it via the
  proposed ACL. *Rejected* — the runtime is dead, this perpetuates the dual subsystem, and it
  directly contradicts #2727.
- **Option 3** — Defer the ASSET gate; ship enforcement only as a data-driven Python
  architectural test. *Rejected by the operator* — the ASSET kind is a strategic enabler beyond
  glossary and is wanted in-program.
- **Option 4** — One mega-mission covering all six tickets. *Rejected* — unreviewable diff; the
  keystone cannot stabilise before its dependents build on it.

## Decision Outcome

Chosen: **Option 1.** Four decisions bind the program:

1. **`GLOSSARY_PACK` becomes a first-order, charter-activatable `ArtifactKind`** — it joins the
   8-kind charter-activatable universe, **not** the `{template, asset}` exclusion set. Copy the
   `directive` kind's wiring. The pack URN is `glossary_pack:` (underscore) — the DRG URN regex
   and the `prefix == kind.value` assertion (`src/doctrine/drg/models.py:19,117-121`) reject the
   hyphenated form; hyphen is the operator token only. A "resolves as a loaded node" test guards
   the silent-invisibility trap (packs load but stay invisible unless the extractor emits them
   and a `*.graph.yaml` fragment ships).

2. **Reconcile #1418 ↔ #2727 by not seeding into the dying runtime.** #1418's proposed
   seed-into-runtime ACL is dropped/inverted. Instead: migrate the 104 curated terms into the
   built-in `spec-kitty-core` pack; repoint the casing gate at the pack loader (the single hard
   dependency); then retire `src/glossary/`.

3. **Terminology enforcement is delivered as a built-in executable ASSET gate** consuming the
   pack's `aliases` / `banned_synonyms` / `synonyms_to_avoid`, folding in the 2-term legacy
   denylist. The 200 baselined casing violations are swept and the ratchet deleted (#2830); the
   stale CLAUDE.md kind table is corrected (#2823).

4. **The executable ASSET trust model is phased on provenance.** A *built-in* asset is Spec
   Kitty's own shipped code, so executing it is the same trust level as the rest of the CLI; the
   RCE-surface concern applies only to *non-built-in* provenance. Phase 1 (this program) ships
   with the cheap, load-bearing guards — `review.allow_executable_gate_assets` opt-in
   **default-OFF**, per-invocation **timeout**, **fail-OPEN**, **structured-verdict-or-warn** —
   and hard-restricts provenance to `built-in`. The expensive hardening (full sandboxed runner,
   interpreter allowlist / no-shell) is deferred to the increment that first enables org-pack /
   third-party asset execution, because that is the only point at which it becomes load-bearing.
   The provenance gate and the default-off flag are **not** deferred.

### Program sequence

**A** (build `GLOSSARY_PACK` kind + migrate 104 terms, #1418, keystone) → **D** (executable
ASSET-kind gate, #2599, depends on A + #2535 steps 1–4) → **B** (enforcement shipped as a
built-in ASSET gate + casing/CLAUDE.md cleanup, #2822/#2830/#2823, depends on A + D) → **C**
(retire runtime `src/glossary/`, #2727, depends on A + B). Recommended order is A → D → B → C so
enforcement ships directly in its target form; a fallback lets B ship interim Python enforcement
if D slips, re-homed onto the asset rail later.

## Consequences

- **Positive** — one canonical terminology authority; ~6,379 LOC of dead machinery removed; a
  reusable executable-doctrine rail; enforcement data-driven from the pack rather than hardcoded.
- **Negative / risk** — the ASSET gate is security-sensitive greenfield and depends on #2535
  steps 1–4 landing; three mirrored kind-lists (`pack_context._BUILTIN_ARTIFACT_KINDS`,
  `activations._ALLOWED_KINDS`, `org_pack_loader._ORG_DRG_CANONICAL_KINDS`) are drift-guarded to
  move in lockstep; the `spec-kitty glossary` CLI + dashboard handler are user-facing contracts
  requiring a deprecation path, not a silent delete.
- **Boundaries** — NOT #2653 (prose-only), and the doctrine-side tests
  (`test_glossary_link_integrity`, `test_glossary_node_kind`, `scripts.docs.glossary_linker`)
  are left untouched.

## Related ADRs

- [2026-07-22-1-gate-binding-content-vs-relationship.md](2026-07-22-1-gate-binding-content-vs-relationship.md)
  — the reuse/attach counterpart of this promote decision: same content-vs-relationship
  rule, opposite outcome. That ADR reuses the existing `mission_step_contract` kind for
  gate bindings (a relationship/configuration on an existing artefact) rather than
  promoting a new `gate` kind, because a gate binding — unlike this glossary pack — has no
  files, repository, or provenance of its own.
