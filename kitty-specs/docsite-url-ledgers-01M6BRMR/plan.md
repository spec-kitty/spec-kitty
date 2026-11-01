# Implementation Plan: Docsite URL baseline, moves ledger and single index files

**Branch**: `issue-6927-url-baseline-moves-ledger` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/docsite-url-ledgers-01M6BRMR/spec.md`
**Grounding**: [research/code-grounding.md](research/code-grounding.md)

## Summary

Add two standing ledgers under `site/`. `url-baseline.txt` lists every published route. `moves.yaml` is an append-only list of `from`/`to` route moves. A new module, `scripts/docs/moves_ledger.py`, is the single owner of reading and validating them. `redirect_stub_generator.py regenerate-map` and `check-map` derive `scripts/docs/redirect_map.yaml` from the moves ledger with chain collapse, which removes the closed-Mission occurrence-map binding (#2358). The ledger is seeded with the 163 current redirects and the 124 file moves #3914 found without a redirect. `rename_reconcile.py`, `bulk_ref_rewrite.py` and `relative_link_fixer.py` default to the ledger. Then the four dual-index folders keep only `index.md`, and their `README.html` routes are appended to the ledger. DocFX keeps deploying from the derived map throughout.

## Engineering Alignment

This is a dispatched, non-interactive session. The planning questions were answered from the brief, the ADR and the grounding, with no live interview:

| Question | Answer |
|---|---|
| Where does the single authority for ledger I/O live? | `scripts/docs/moves_ledger.py`, stdlib + PyYAML (both already used by `redirect_stub_generator.py`, which the deploy job runs with system `python3`). |
| What does `coverage` measure in the deploy job? | It switches from the 180-URL JSON manifest to `site/url-baseline.txt`, so the deploy proves the full baseline (NFR-001). A PR-time test mirrors it over the source tree, so a page deleted without a ledger entry fails before merge, not at deploy. |
| What happens to the old JSON manifest? | It stays as a committed historical input: the containment test (FR-002) reads it, and its amendments are copied into the ledger header. Retiring it is #6933's job (ADR D-6 "port"). |
| What happens to the closed Missions' occurrence maps? | Untouched (C-003, and `test_archive_root_byte_identical.py` pins the convergence map). No script reads them by default. |
| Grow-on-publish? | Reported in the deploy job, not gated (spec FR-012, assumptions). |

## Technical Context

**Language/Version**: Python 3.11+ (repository floor); the deploy job's system `python3` on `ubuntu-latest`
**Primary Dependencies**: PyYAML (already used by `redirect_stub_generator.py`), stdlib; ruamel.yaml stays in `rename_reconcile.py`
**Storage**: Two committed text files under `site/` (`url-baseline.txt`, `moves.yaml`) and the derived `scripts/docs/redirect_map.yaml`
**Testing**: pytest under `tests/docs/` (fast, file-based, `tmp_path` fixtures); a local DocFX build plus the `generate`/`coverage` subcommands for NFR-001
**Target Platform**: The GitHub Actions `docs-pages.yml` deploy job (DocFX, push to `main`) and developer machines
**Project Type**: single (repository scripts + data)
**Performance Goals**: The ledger tests run in under 5 s in total (NFR-004); derivation is linear in ledger size (about 300 entries)
**Constraints**: DocFX stays live (C-001); no `site/` build, doc-kitty config, `redirects.json` or frontmatter migration (C-002); immutable history (C-003); generated docs surfaces untouched (C-004)
**Scale/Scope**: about 300 moves, about 965 baseline routes, 4 folders, about 10 inbound references

## Charter Check

| Charter rule | How this plan meets it |
|---|---|
| Single canonical authority | One module owns both ledgers. `redirect_map.yaml` becomes a pure derivation, and the occurrence-map derivation and its Mission constants are deleted, not kept beside the new path. |
| ATDD-first (C-011) | Each WP commits its failing acceptance test before the change (see the IC map). |
| Architectural gate discipline | The one-index-per-folder test and the "no Mission-scoped default" test start empty, with no allowlist, and carry a positive control. |
| Canonical sources | Mission artifacts from the canonical templates; changelog via a fragment in `docs/changelog/unreleased/`; generated docs surfaces left to the post-merge bot. |
| Terminology canon | Prose uses Mission. `test_no_legacy_terminology.py` runs before push. |
| Immutable history | ADR bodies, plans, reports, the changelog and closed occurrence maps are not edited. |
| Test policy | `make test-fast` + `tests/docs/` + named architectural gate files; never `test-full`. |
| Quality | Complexity ≤ 15, ruff + format (`--force-exclude`) + mypy on changed Python. |

No violation needs justification.

## Project Structure

### Documentation (this mission)

```
kitty-specs/docsite-url-ledgers-01M6BRMR/
├── spec.md
├── plan.md               # this file
├── research.md           # decisions (Phase 0)
├── research/code-grounding.md
├── data-model.md         # ledger entities and invariants
├── contracts/
│   ├── moves-ledger.md   # site/moves.yaml format
│   └── url-baseline.md   # site/url-baseline.txt format
├── quickstart.md         # how a maintainer records a move
├── occurrence_map.yaml   # DIRECTIVE_035 classification of this Mission's README repoint
├── traces/               # tracer files
└── tasks/
```

### Source Code (repository root)

```
site/
├── url-baseline.txt                 # NEW: baseline ledger
└── moves.yaml                       # NEW: moves ledger
scripts/docs/
├── moves_ledger.py                  # NEW: single authority for both ledgers
├── redirect_stub_generator.py       # regenerate-map/check-map from the ledger; coverage on the new baseline; baseline-drift report
├── redirect_map.yaml                # regenerated (derived)
├── rename_reconcile.py              # default: ledger
├── bulk_ref_rewrite.py              # default: ledger
└── relative_link_fixer.py           # follows bulk_ref_rewrite's default
.github/workflows/docs-pages.yml     # trigger paths + baseline-drift report step
docs/adr/{1,2,3}.x/README.md         # deleted
docs/architecture/README.md          # folded into index.md, deleted
tests/docs/test_moves_ledger.py      # NEW
tests/docs/test_redirect_spine.py, test_redirect_stub_generator.py, test_adr_readme_prose.py, …  # re-pinned
```

**Structure Decision**: single project. `site/` holds only the two data files until #6930 adds the npm project around them.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Ledger authority and seeded ledgers (S-3 core)

- **Purpose**: Create `moves_ledger.py`, seed `site/moves.yaml` (163 carried + 124 reconciled + chain follow-ups) and `site/url-baseline.txt` (site walk ∪ derived keys), and derive `redirect_map.yaml` from the ledger.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-012, NFR-001, NFR-002, NFR-004
- **Affected surfaces**: `site/`, `scripts/docs/moves_ledger.py`, `scripts/docs/redirect_stub_generator.py`, `scripts/docs/redirect_map.yaml`, `.github/workflows/docs-pages.yml`, `tests/docs/test_moves_ledger.py`, `tests/docs/test_redirect_stub_generator.py`, `tests/docs/test_redirect_spine.py`
- **Sequencing/depends-on**: none
- **Risks**: the deploy-time `coverage` switching to the larger baseline. The PR-time mirror test and a local DocFX run (NFR-001) retire that risk. Keys must never be live pages; the derivation validates this against the published set.
- **ATDD first commit**: `tests/docs/test_moves_ledger.py` (containment of the old manifest and map keys, derivation equals the committed map, refusals, #3914 forward reconcile clean), red before the ledgers exist.

### IC-02 — No Mission-scoped occurrence map in docs tooling (#2358)

- **Purpose**: Point `rename_reconcile.py`, `bulk_ref_rewrite.py` and `relative_link_fixer.py` at the ledger by default; remove the `MISSION_SLUG`/`DEFAULT_OCCURRENCE_MAP` constants.
- **Relevant requirements**: FR-007
- **Affected surfaces**: those three scripts and their tests
- **Sequencing/depends-on**: IC-01
- **Risks**: `relative_link_fixer` and `bulk_ref_rewrite` consume source-path pairs. The ledger's routes convert to `docs/` source paths one to one for pages. Explicit `--occurrence-map` fixtures in their tests keep working.
- **ATDD first commit**: a test asserting that no `scripts/docs/*.py` default names a path under `kitty-specs/`, with a positive control on a synthetic module.

### IC-03 — One index file per folder (S-4)

- **Purpose**: Delete the three ADR-era stubs, fold `architecture/README.md` into `architecture/index.md`, append the four `README.html` moves, regenerate the map, and repoint live references.
- **Relevant requirements**: FR-008, FR-009, FR-010, FR-011
- **Affected surfaces**: `docs/adr/{1,2,3}.x/README.md`, `docs/architecture/{README,index}.md`, `docs/architecture/vision/README.md`, `docs/architecture/diagrams/README.md` (`related`), `src/charter/offering/templates/diagrams/README.md`, `tests/docs/test_adr_readme_prose.py`, `tests/charter_offering/test_wp_authoring_contract_roundtrip.py`, `CLAUDE.md`, `AGENTS.md`, `site/moves.yaml`, `site/url-baseline.txt` (the four routes are already in it from the walk), `scripts/docs/redirect_map.yaml`, a changelog fragment
- **Sequencing/depends-on**: IC-01
- **Risks**: the frontmatter edits to `related` overlap #6929 (ruling 11: each PR resolves its own conflicts). `CLAUDE.md` and `AGENTS.md` are agent guidance; the edit is a one-word path fix. Generated docs surfaces are left to the bot (C-004).
- **ATDD first commit**: a test asserting no `docs/` folder holds both `index.md` and `README.md` (red on today's four), plus ledger assertions for the four `README.html` routes.
