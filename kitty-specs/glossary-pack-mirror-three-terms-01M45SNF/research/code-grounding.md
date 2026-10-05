# Code grounding: mirror three glossary terms into the built-in pack (#5761)

Read-only grounding run, 2026-10-05, on `origin/main` @ `14d653bb9`. No file
outside this mission directory was edited to produce it.

## 1. The two glossary files and how they relate

| File | Role | Shape |
|---|---|---|
| `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` | Shipped to every consumer (wheel includes `packs/built-in/`). Loaded by `GlossaryPackRepository` as DRG node `glossary_pack:spec-kitty-core`. | Top-level `id`, `provenance`, `description`, `terms:`. Each term: `confidence`, `definition`, `status`, `surface` (keys sorted alphabetically, ruamel dump style, plain multi-line scalars wrapped at ~78 columns). Optional: `see_also`, `introduced_in_mission`, `synonyms_to_avoid`, `aliases`, `banned_synonyms`. Schema `GlossaryTerm` (`src/charter/offering/glossary_packs/models.py`, `extra=forbid`, surfaces unique). 112 terms. |
| `.kittify/glossaries/spec_kitty_core.yaml` | This repository's own seed (not shipped). Read by the runtime glossary scope loader and by `scripts/docs/generate_kitty_specs_docs.py` (docs glossary page, built at docs-build time, output gitignored). | `terms:` list, 2-space `- surface:` lead, 4-space keys in the order `surface`, `definition`, `confidence`, `status`, optional keys. Schema `GlossarySeedTerm` (`src/glossary/seed_schema.py`, `extra=forbid`; `surface` lowercase and trimmed; `status` in active/draft/deprecated; no `aliases`). 103 terms. |

**Which is generated from which.** The pack was migrated once from the seed
(its header names a migration script that no longer exists in the repo). Since
then neither is generated: both are hand-edited, and the standing invariant is
`tests/architectural/test_glossary_pack_parity.py`: pack surfaces == seed
surfaces ∪ `_MISSION_ADDED_SURFACES`, and every key present on a seed term
round-trips identically into the pack. Precedent `b70a344fc8` edited the pack,
and `8fc1a85560` then mirrored the same definition into the seed to keep that
test green.

**Ordering convention.** The migrated core is alphabetical by surface; later
additions are appended at the end of the list in both files (for example
`issue-matrix schema drift`, `transition gate`, `requirement id`). No test
checks order. New terms are appended at the end of both files.

## 2. Gates that read either file

| Gate | Invariant | Effect of this change |
|---|---|---|
| `tests/architectural/test_glossary_pack_parity.py` | Surface-set parity; every seed key identical in the pack; a key absent on the seed is absent on the pack. | Adding each term to **both** files keeps it green with no edit. Definitions must be byte-identical strings: a seed `>` block keeps a trailing newline, so use a single-line plain seed definition. `synonyms_to_avoid` lists must match. |
| `tests/architectural/test_pack_manifest_no_author_edit.py` (+ `test_doctrine_regenerate_graph_roundtrip.py`) | Regenerating reproduces the committed `packs/built-in/pack-manifest.yaml` byte for byte. | The pack's `content_hash` and the `manifest_hash` change: run `spec-kitty doctrine regenerate-graph`, confirm with `--check`. |
| `tests/architectural/test_builtin_pack_provenance_ratchet.py` | Shrink-only baseline per built-in file; the pack is pinned at `repo_paths: 6`, `provenance: 15` (`src/specify_cli`, `src/doctrine`, `tests/architectural`, `kitty-specs/`; `#NNN`, `WPnn`, `FR-n`). | Pack definitions must cite **no** issue numbers (the `docs/context/` entries cite #5745 and #702) and **no** `src/specify_cli/...` paths (the entries cite `runner.py`, `contract.py`). Point at `docs/context/` instead, as the precedent does. |
| `tests/architectural/test_no_legacy_terminology.py` | Bans `ceremony` / `status-writing` (pack dir exempt); `spec-kitty merge` phrasing must not grow, and `packs/` is scanned. | Do not write "spec-kitty merge" in a pack definition. |
| `tests/architectural/test_no_dead_cli_paths.py`, `test_transition_guard_shrink_only.py`, `test_glossary_authority_parity.py` | Dead-path, `surface: doctrine`, and charter-term pins. | Unaffected (no such surfaces or paths). |
| `tests/architectural/test_no_inert_schema_slots.py` | `aliases` / `banned_synonyms` slots baselined as inert. | Do not author `banned_synonyms`. |
| `tests/glossary/*`, `tests/doctrine/glossary_packs/*`, `tests/charter/test_drg_activation_gate.py`, `tests/doctrine/test_project_charter_single_owner.py`, `tests/docs/test_glossary_linker.py` | Specific-term checks, DRG node resolution, unique anchor ids. | Unaffected; the new anchors (`tool-surface-drift`, `integrating-worktree`, `target-owned-bookkeeping`) collide with nothing. |
| `tests/cross_cutting/packaging/test_packaging_safety.py` | Wheel contains `packs/built-in/` and never `packs/internal/` or `.kittify/`. | Unaffected (path prefixes only). |
| Contextive generator (`scripts/generate_contextive_glossaries.py`) + `tests/cross_cutting/encoding/test_contextive_traceability.py` | Generates `src/**/.contextive*` from `docs/context/*.md` and the traceability map. | Reads neither file; `docs/context/` is not edited, so no regeneration. Confirm with `generate_contextive_glossaries.py check`. |
| Docs retrieval index (`scripts/docs/docs_index.py`, `tests/docs/test_docs_index_freshness.py`) | Walks `docs/**/*.md` only. | Unaffected unless a docs page changes; confirm with `--strict`. |
| Template renderer glossary markers (`src/specify_cli/template/renderer.py`) and rendered-template snapshots | Seed surfaces matched as whole words in templates. | None of the three phrases appears in any template or skill today, so no snapshot moves. |

## 3. Pack-tier decision (CLAUDE.md "Pack Tiers")

Question for each term: does it govern consumers, or only how the core team works?

- **tool-surface drift → built-in.** It names what every consumer sees from
  `spec-kitty upgrade` (`Not updated, your local edit was kept: <path>`, the
  `drift_unresolved` outcome and `surface_drift` reason) and what
  `spec-kitty doctor tool-surfaces` reports. Shipped product behavior
  (ADR `2026-10-04-3`).
- **integrating worktree → built-in.** It names which worktrees a consumer's
  `spec-kitty upgrade` run skips, and explains why a consumer's lane still shows
  a pre-upgrade `.kittify/metadata.yaml`. Shipped product behavior
  (ADR `2026-10-04-4`, `_is_integrating_worktree` in the upgrade runner).
- **target-owned bookkeeping → built-in.** It names why `consolidate`, review
  start, implement resume and lane sync resolve a `.kittify/metadata.yaml`
  conflict without refusing in any consumer project, and which copy survives
  (ADR `2026-10-04-4`, rule `R-TARGET-OWNED-BOOKKEEPING`). The recovery runbook
  (`docs/operations/upgrade-with-live-lanes-recovery.md`) is tagged for the
  maintainer audience, but the behavior it explains runs in every consumer's
  consolidation; the term is product vocabulary, not core-team practice.

No term is maintainer-only, so none goes to `packs/internal/`.

## 4. Field mapping for "do not use" guidance

The pack schema has no "do not use when" field. The closest field is
`synonyms_to_avoid` (metadata only; no runtime enforcement reads it, see
`src/glossary/scope.py`). Plan:

- the definition carries a condensed "not this" sentence, as existing entries do
  ("Not to be confused with ...");
- `synonyms_to_avoid` carries the names the `docs/context/` entry forbids:
  `drift` (bare) for tool-surface drift, `primary-owned bookkeeping` for
  target-owned bookkeeping (named only as the term to avoid, as the
  `docs/context/` entry itself does). integrating worktree has no forbidden
  synonym, so it has none.

## 5. Regeneration commands

- Required: `spec-kitty doctrine regenerate-graph`, then `spec-kitty doctrine regenerate-graph --check`.
- Confirm unchanged: `uv run python -m scripts.docs.docs_index --strict`; `uv run python scripts/generate_contextive_glossaries.py check`.

## 6. Findings worth noting (not in scope)

- `test_glossary_pack_parity.py` docstrings say "104 seed terms"; the seed has 103. Comment-only, not asserted.
- The pack header still says "Do not hand-edit; re-run the migration script", but the script is gone and every later addition was hand-edited.
