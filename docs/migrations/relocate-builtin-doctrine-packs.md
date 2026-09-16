---
title: 'Migration: Relocate Built-In Doctrine to packs/built-in'
description: 'Migration for the built-in doctrine relocation: content moved from src/doctrine into a top-level packs/built-in/ pack root, resolved through a shared pack-root seam.'
doc_status: active
updated: '2026-07-30'
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migration: Relocate Built-In Doctrine to `packs/built-in`

**Mission**: `relocate-builtin-doctrine-packs-01KYT87F`
**Audience**: downstream org/project doctrine-pack authors, and anyone whose code or docs referenced the built-in doctrine artefacts by their old `src/doctrine/` paths.

## What changed

The **content** (data files) of the built-in doctrine pack moved out of the
`src/doctrine/` Python package into a new **top-level `packs/built-in/` pack
root**. Only the shipped artefact data moved — no doctrine `.py` code, schemas,
templates, skills, or the `missions/` tree moved (those still live under
`src/doctrine/`).

The move is **breaking** for anything that named the old paths, and it
**flattens** the layout: the pre-move per-kind home `src/doctrine/<kind>/built-in/`
loses its inner `built-in/` segment and becomes `packs/built-in/<kind>/`.

| Kind of reference | Before (pre-move) | After (this mission) |
|---|---|---|
| Per-kind built-in content | `src/doctrine/<kind>/built-in/<file>` | `packs/built-in/<kind>/<file>` |
| Sharded DRG fragments | `src/doctrine/<kind>.graph.yaml` | `packs/built-in/<kind>.graph.yaml` |
| Built-in agent profiles | `src/doctrine/agent_profiles/built-in/*.agent.yaml` | `packs/built-in/agent_profiles/*.agent.yaml` |
| Built-in glossary packs | `src/doctrine/glossary_packs/built-in/*.glossary-pack.yaml` | `packs/built-in/glossary_packs/*.glossary-pack.yaml` |
| Doctrine `.py` code, `schemas/`, `templates/`, `skills/`, `missions/` | `src/doctrine/…` | **unchanged** — still `src/doctrine/…` |

### The new resolution seam

All three tiers (built-in → org → project) now resolve the built-in root
through a single shared seam, `resolve_pack_root("built-in")`
(`src/doctrine/pack_paths.py`). It fails **closed** (`PackRootNotFound`) rather
than guessing, and discovers the root in three ordered ways:

1. an explicit environment override;
2. **editable checkout** — the nearest ancestor directory that contains
   `packs/built-in/`;
3. **installed wheel** — `packs/` ships as a site-packages *sibling* of the
   `doctrine` package, i.e. `files("doctrine").parent / "packs" / "built-in"`.

The DRG seam (`built_in_graph_source()` / `load_built_in_graph()` in
`src/doctrine/drg/loader.py`) now yields the `packs/built-in/` directory
(`source.name == "built-in"`), and the shipped graph loads by merging the
per-kind `*.graph.yaml` fragments it finds there.

### No runtime shim

There is **no compatibility shim** for the old `src/doctrine/<kind>/built-in`
locations. A reader that still names an old path gets a missing file, not a
silent redirect — the fail-closed resolver is deliberate. Update the reference
(see the table above) rather than relying on a fallback.

### Packaging

Both the wheel and the sdist ship the relocated tree:

- **wheel**: `[tool.hatch.build.targets.wheel] force-include = { "packs" = "packs" }`
  lands `packs/built-in/<kind>/…` as a site-packages sibling of `doctrine`.
- **sdist**: `packs/**` is added to `[tool.hatch.build.targets.sdist]` (the
  `src/**` globs never match a top-level `packs/` tree).

A `.gitignore` audit confirms no `packs/`- or `built-in/`-shaped pattern
swallows the new tree (`git check-ignore packs/built-in/...` returns "not
ignored").

## Action required

**Downstream pack authors and integrators:**

- If you referenced a built-in artefact by its `src/doctrine/<kind>/built-in/…`
  path (in code, docs, DRG endpoints, or tooling), repoint it to
  `packs/built-in/<kind>/…` (drop the inner `built-in/`).
- If you resolved the built-in root yourself, switch to
  `resolve_pack_root("built-in")` rather than reconstructing the path.
- Org and project packs are unaffected in shape — this mission moved **only**
  the built-in tier's on-disk home. Converging built-in onto the org-pack
  loader/schema contract is **Phase 2** (see Follow-ons).

## Rollback

This is a pure relocation of committed content plus a resolver repoint; there
is no data migration and no persisted state to revert. To roll back, revert the
mission's merge commit — the built-in content returns to `src/doctrine/<kind>/built-in/`
and the resolver/loader repoint reverts with it. No downstream cleanup is
required because there is no shim or generated sidecar to unwind.

## Follow-ons

Two pieces of work are **deliberately deferred** and must not be treated as
lost:

- **Phase 1b — relocate the `missions/` tree**
  ([#3091](https://github.com/Priivacy-ai/spec-kitty/issues/3091)). The
  `missions/` readers span the kernel layer and use `__file__`-relative idioms
  that cannot route through the doctrine-layer resolver without a layering
  violation. **First task:** a cross-layer `missions/`-reader inventory (every
  `files("doctrine*")` / `__file__`-relative reader that touches `missions/`),
  classified as move-or-stay, before any file moves.
- **Phase 2 — loader/schema convergence.** Unify built-in onto the org-pack
  loader and schema contract and re-architect `merge_three_layers`. This
  mission preserved the built-in *structure* (a per-kind mirror); it did **not**
  claim built-in's on-disk shape matches the org/project pack contract.

## Notes

Observations recorded during the closeout for a later agent to action — **out
of scope to fix in this mission**:

- **`CLAUDE.md` "Deferred Items" lists a closed issue.** The
  "Charter Activation and Doctrine Integrity Model → Deferred Items" list still
  carries [#1624](https://github.com/Priivacy-ai/spec-kitty/issues/1624)
  (`_tag_source` provenance sidecar typing), which is **already closed**. Flag
  for a later CLAUDE.md correction.
- **Migration-hint repoint was cross-cutting.** The relocation left the
  operator-facing DRG-edge migration hint (`build_migration_hint`,
  `src/doctrine/shared/errors.py`) naming the now-dead `src/doctrine/<kind>.graph.yaml`.
  It was repointed to `packs/built-in/<kind>.graph.yaml` here, along with the
  tests that pin its shape (`tests/doctrine/shared/test_errors.py`,
  `tests/doctrine/test_inline_ref_rejection.py`) — because both the mission's
  own dead-path gate and a sibling test went red on the dead path. **Follow-on:**
  the shape contract at
  `kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6/contracts/validator-rejection-error.schema.json`
  is an archived artifact of another mission and was **left untouched**; its
  `pattern`/example still name the old `src/doctrine/…graph.yaml` shape. No test
  loads that JSON at runtime (it is documentation only), so nothing is red, but
  the contract now lags the emitted hint and should be refreshed by the owning
  mission.
- **Cross-tree markdown links.** Because `packs/built-in/toolguides/` (moved)
  and `src/doctrine/templates/` (stayed) cross-reference each other, several
  navigation links are now cross-tree relative paths
  (`packs/built-in/…` ↔ `src/doctrine/templates/…`). They resolve and are
  guarded by `tests/architectural/test_no_dead_doctrine_paths.py` Gate C, but
  the split home is a structural smell a future consolidation (Phase 1b/2) may
  want to remove.
- **Toolguide `guide_path:` metadata.** Several `packs/built-in/toolguides/*.toolguide.yaml`
  still carry `guide_path: src/doctrine/toolguides/built-in/<FILE>.md` in their
  YAML metadata (a data field, not markdown navigation, so outside Gate C's
  `*.md` scope). Confirm the toolguide loader/resolver repoints these to
  `packs/built-in/toolguides/` (content-move integrity, not a WP08 test-literal
  concern).

## Why this happened

See [ADR 2026-07-26-2: Doctrine Artefact Pack Layout Convention](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-07-26-2-doctrine-artefact-pack-layout-convention.md)
and the mission spec at
`kitty-specs/relocate-builtin-doctrine-packs-01KYT87F/spec.md` for the full
rationale, the built-in → org → project resolution-seam goal, and why loader
convergence is deferred to Phase 2.
