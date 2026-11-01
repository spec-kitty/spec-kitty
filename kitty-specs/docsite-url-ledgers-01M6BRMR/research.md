# Research: Docsite URL baseline, moves ledger and single index files

The measured facts live in [research/code-grounding.md](research/code-grounding.md). This file records the decisions taken from them.

## D1. Route form

- **Decision**: a route is the legacy published path with a leading slash, `/a/b.html`. `url-baseline.txt` and `moves.yaml` both use it. DocFX's `redirect_map.yaml` keeps its existing slash-less keys.
- **Rationale**: doc-kitty's baseline format is one site-relative URL per line with a leading slash (spike evidence). Every legacy URL is a `.html` route, which DocFX can use as is and a doc-kitty generator maps to `/a/b/` (ADR D-5 rule 1). For pages, a route converts one to one to its `docs/` source path, which the rename gate and link rewriters need.
- **Alternatives considered**: `docs/` source paths (cannot express a route whose page is gone, or hub redirects); directory URLs (DocFX cannot use them, and they lose the `README.html` vs `index.html` distinction). Decision Moment `01M6BRRA8VAED9C86WVXDKSKBK`.

## D2. Ledger semantics

- **Decision**: entries are append-only. A later move of a destination is a new entry from the old destination, and the derivation collapses chains. A `from` appears at most once. Cycles are refused. A collapsed target must be a published page or section hub. A `from` must not be a published page.
- **Rationale**: ADR D-5 rules 1 and 2. The old `_relocate` was single-move and first-match, which forced the convergence Mission to hand-collapse a "cumulative spine". Collapsing chains in the derivation removes that.
- **Alternatives considered**: allowing a duplicate `from` with last-wins semantics (hides history edits); prefix (directory) moves (ambiguous once collapsed, and every past directory move is already expanded in the map).

## D3. What the derived map contains

- **Decision**: `redirect_map.yaml` = the collapsed ledger, every `from` a key, with no baseline filter.
- **Rationale**: the baseline filter in the old derivation is the root cause of #3914: a move whose old URL missed the 180-URL manifest silently got no redirect.

## D4. Seeding

- **Decision**:
  - `moves.yaml` has three sections, each with provenance comments:
    1. the 163 current map entries (the structural-move and convergence Missions);
    2. the 124 occurrence-map file moves #3914 lists, as recorded in that map, resolved to routes;
    3. follow-on entries that carry the destinations which have since moved or been archived to their current page, or to the section hub when the page is unpublished (ADR D-5 rule 4).
  - `url-baseline.txt` = the 672 pages of a local DocFX walk (excluding `/kitty-specs/**` and `/toc.html`) ∪ every derived key.
- **Rationale**: ADR D-5 seeding rule. The walk was run on a real DocFX 2.81.0 build of this base (grounding §2); the derive-from-source set matches it except for `toc.html`.

## D5. Deploy-job coverage and PR-time mirror

- **Decision**: `coverage` reads `site/url-baseline.txt` by default. A `tests/docs/` test asserts every baseline route is a page the docs tree publishes (derive-from-source) or a map key with a published target.
- **Rationale**: NFR-001 over the full baseline. The mirror moves the failure from deploy time to PR time.

## D6. Grow-on-publish

- **Decision**: a `baseline-drift` subcommand prints a GitHub `::warning::` per published page missing from the baseline. The deploy job runs it; it never fails.
- **Rationale**: spec FR-012 and its assumption; the gate belongs with doc-kitty's build gate.

## D7. Folding `architecture/README.md`

- **Decision**: `index.md` takes the README's landing sections (purpose line, boundary rule, living and frozen pages, decay rule, era README-history pointers) above its existing page list. Its self-references to `README.md` are removed. Every live inbound reference moves to `index.md`.
- **Rationale**: ADR D-7 "folded into `architecture/index.md`"; no content is lost (FR-009).

## Supply chain

No dependency is added, upgraded or removed (`pyproject.toml` and `uv.lock` untouched), so `DIRECTIVE_051` has nothing to assess.
