# Code grounding: build-blocking frontmatter migration (#6929)

Read-only grounding run before specify. Base: `origin/main` at `7e2ca9fd`. Upstream
toolkit: `spec-kitty/doc-kitty` `main` at `fe835cd` (contains `b77e40d`). Governing
record: ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`, D-7 and D-8.
Measurement script: a throwaway walk with `scripts.docs._inventory.parse_frontmatter`
(the parser every reader uses), run over `docs/**/*.md`.

## 1. Measured counts against the issue

| Class | Issue / spike | Measured now | Why it differs |
| --- | --- | --- | --- |
| 1. `audience` as a path string | 341 | **344 pages**: 343 scalar strings, 1 list of path strings | New pages since the spike. Values: 341 persona paths, plus 3 free-text values on published pages (`end-users` on `api/init-lifecycle.md` and `api/upgrade-lifecycle.md`, `internal / pre-launch operators` on `operations/internal-hosted-readiness.md`) and 1 in `archive/` (`agentic-framework-core-team`). |
| 2. Excluded trees missing `title`/`description` | 31 | **31** (reports 24, convergence 4, archive 3) of 242 files | Same. **See §4: no longer needs an edit.** |
| 3. `related` as repository paths | 411 pages; 32 refs outside `docs/` | **413 pages, 1,267 refs**. 32 refs are not doc-kitty pages: 25 point outside `docs/` (`kitty-specs/`, `tests/`, `.github/`, `pyproject.toml`, `.kittify/`, `src/`), 6 point at non-Markdown files inside `docs/` (`page-inventory.yaml`, `docfx.json`, `llms.txt`), 1 is dangling | The issue's 32 = 25 + 6 + 1. Two refs are pre-existing dangling edges (`related_validator` reports them today): `archive/.../3-2-publication-checklist.md` → a moved plan, and `plans/engineering-notes/agent-knowledge-canonical-homes.md` → a deleted `src/` file. |
| 4. ADRs without `doc_status` / `kind` | 226 | **228 dated ADRs**: 189 Accepted, 21 Proposed, 18 Superseded. 227 lack `doc_status` (the doc-kitty ADR itself carries it). None has `kind`. | Two ADRs merged since. No promoted `adr-*.md` file exists. |
| 5. Published page `related` → draft/excluded page | 181 | **36 refs from 23 published pages** (21 into excluded trees, 15 into drafts), measured *after* class 4 | The spike's 181 counted every ADR as a draft (no `doc_status` means draft in doc-kitty). Once ADRs carry `doc_status`, 145 of those resolve. |

Also found: `docs/changelog/unreleased/*.md` (10 fragments + `README.md`, added by #6988 after the
spike) have no frontmatter. They are not pages (`scripts/docs/_page_scope.py`), and doc-kitty would
reject them, so the one-off build excludes `changelog/unreleased` as well.

`doc_status` values outside doc-kitty's canonical five (`point_in_time` ×2, `proposal` ×1 on
published pages; `closeout` ×5 in excluded trees) build, because the build schema accepts any
non-empty string. Normalising them is D-7's `doc_status` row, owned by #6931, not this issue.

## 2. Every reader of each field

| Field | Reader | What it reads | Effect of the migration |
| --- | --- | --- | --- |
| `audience` | `scripts/docs/audience_resolver.py` | scalar or list of strings; `.md` values must resolve under `docs/context/audience/`, others are free text | **Port**: read `[{profile, guidance_text}]`; a profile resolves to `docs/context/audience/<profile>.md` (or `<profile>/index.md`). |
| `audience` | `scripts/docs/touched_set_gates.py` (`_audience_values`, `check_audience_presence`, `_audience_orientation`) | same string shape; page-relative `.md` resolution; `internal`/`external` segment | **Port** (same PR). Not listed in the issue; found by grep. |
| `audience` | `scripts/docs/docs_index.py`, `src/specify_cli/docs/index_model.py` | **does not read it** (reads `title`, `description`, `type` and headings only) | None. `spec-kitty docs query` output is unchanged by this migration. |
| `related` | `scripts/docs/related_validator.py` | list of repo-relative paths, resolved as files | **Port**: read slugs (string or `{ref, note}`) and resolve them as doc-kitty does (`<slug>.md`, `<slug>/README.md`, `<slug>/index.md`). |
| `related` | `scripts/docs/frontmatter_backfill.py` (`derive_related`) | **writes** repo paths; a migration-era tool kept "for the migration, then drop" (ADR D-6) | Its writer emits the old shape. Not re-run by this mission; noted for #6931/D-6 retirement. |
| `related` | `scripts/docs/bulk_ref_rewrite.py` | rewrites `related` path values during a rename | Rewrites repo paths; after the migration a `related` slug is not a path. Noted for the README rename step (#6939), which owns this tool's reuse. |
| `doc_status` | `scripts/docs/frontmatter_backfill.py`, `tests/docs/test_doc_status_durable.py` | vocabulary checks | Adding `active`/`superseded` to ADRs stays inside the vocabulary. |
| ADR `status`, `date` | `scripts/docs/freshen_adr_inventory.py`, `tests/docs/test_adr_content_invariance.py`, `scripts/docs/adr_converter.py` | MADR `status` on every ADR | Unchanged: `status`/`date`/`superseded_by` stay as they are. |
| `kind` | nothing in `scripts/` or `src/` | — | New key; the structural lint (`packs/built-in/assets/docs_structural_lint.py`) checks required keys only, no allowlist. |
| `external_references` | nothing in core | — | New key. doc-kitty takes `{url, title, note?}` inline or `{type, id}` catalog; the catalog form needs a bibliography entry, so inline is the right shape for repository files. |
| `description` | `scripts/docs/description_length_check.py`, `check_docs_freshness.py` | length band, freshness | Unaffected (no description is written: see §4). |

Generated surfaces (`scripts/ci/generated_docs_surfaces.py`): the docs retrieval index, the page
inventory and the ADR era index tables (`docs/adr/<era>/index.md|README.md`) are regenerated on
`main` after merge; `check_generated_docs_untouched.py` refuses a PR that edits them. The migration
must skip the era index files, and must not regenerate the index or inventory. Neither generator
reads a migrated field, so neither drifts.

CI wiring: `audience_resolver`, `related_validator` and `touched_set_gates` are **not wired in any
workflow** today (only their tests run). A corpus that regresses to the old shape would therefore
pass CI unnoticed; the mission needs a corpus-level invariant test to hold the new shape.

## 3. Test seams

- `tests/docs/test_audience_resolves.py`, `tests/docs/test_touched_set_gates.py`,
  `tests/docs/test_related_validator.py`, `tests/docs/test_rulers_blocking.py` pin the old string
  shapes in fixtures: they are rewritten red-first with the ports.
- `tests/docs/test_adr_content_invariance.py` pins MADR `status` on every ADR (kept).
- `tests/docs/test_docs_index_freshness.py` and `tests/specify_cli/docs/` pin `docs query` and the
  index; unaffected because the index does not read migrated fields.
- No test hashes immutable bodies today (the byte-invariance proof was retired 2026-06-29). The
  Done-when's body-hash test is new.
- Baseline (`pytest tests/docs/ tests/specify_cli/docs/ -n 4 --dist loadfile` on `7e2ca9fd`):
  recorded in the mission's tooling-friction tracer.

## 4. Upstream doc-kitty since the spike (`fe835cd`)

- **Native folder exclusion (doc-kitty #247, ADR-0070)** — `defineDocKittyIntegrations({ exclude })`.
  The loader adds one negated glob per folder, so excluded files are never read or schema-checked,
  and the `dockitty-*` gates skip them. **Verified by build** (throwaway site in `/tmp`, doc-kitty
  git dependency at `fe835cd`): a tree of only `archive/`, `reports/`, `convergence/` plus a valid
  root page builds with `exclude: ['archive','reports','convergence']` (2 pages, exit 0), and fails
  without it on `convergence/doctrine-drg` (schema). **Class 2 therefore needs no frontmatter
  edit**; the spike's loader shim and the 31-page minimum are both retired for this issue. A
  `related` ref into an excluded folder gets a dedicated build-fatal message, so class 5 still holds.
- **Date-named ADR ids and the frontmatter `status` fallback (#255, #273)** — ADR index work; does
  not change what this migration writes (`status` stays, D-7).
- **Nested persona slugs** — `resolveProfile` maps `profile` to `context/audience/<profile>`, so
  `internal/maintainer` resolves; a profile with no persona page is a soft miss, not a failure.
- **Slug rule** — a page's slug is its path under `docs/` without the extension, with a trailing
  index basename (`README` or `index` here) removed; case is preserved. `related` resolution is an
  exact lookup on that slug.
- **Control build of the unmodified tree** (with the #6928 dual-index folders simulated, as the
  spike did): fails first on `api/batch-api-contract` — `audience: Expected type "array"`.

## 5. Collisions and sequencing

- **#6927/#6928 (parallel session):** not touched — the `docs/adr/*/README.md` stubs and
  `docs/architecture/README.md` are skipped by the migration. The one-off build simulates #6928 in
  a `/tmp` copy only.
- **#6995** (regen bot PR): touches only generated surfaces, which this mission does not edit.
- **#6902** edits the body and `updated:` of `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`;
  **#6882** edits `docs/context/charter.md` / `governance.md` (frontmatter `updated:` beside
  `related:`). Overlap is line-level in frontmatter only. The migration is a committed, idempotent
  script, so whichever PR lands second resolves by re-running it.
- No other open PR touches `docs/**` frontmatter.

## 6. Churn (since 2026-08-03)

| File | Commits | Fix-titled |
| --- | --- | --- |
| `scripts/docs/audience_resolver.py` | 3 | 1 |
| `scripts/docs/related_validator.py` | 4 | 1 |
| `scripts/docs/touched_set_gates.py` | 3 | 1 |
| `scripts/docs/docs_index.py` | 1 | 0 |
| `scripts/docs/freshen_adr_inventory.py` | 5 | 1 |
| `scripts/docs/description_length_check.py` | 2 | 1 |
| `scripts/docs/check_docs_freshness.py` | 4 | 0 |
| `src/specify_cli/docs/index_model.py` | 2 | 0 |

Low churn; the readers are small, stable and well tested, so porting them is low risk.

## 7. Consequences for the spec

1. Five slices stay, but slice 3 (excluded trees) is "no edit; exclude natively", proven by build.
2. `touched_set_gates.py` joins the audience port.
3. `docs_index.py` / `index_model.py` need no port; the issue's mention of `docs_index.py` is moot.
4. A corpus-shape invariant test is needed because the readers are not CI-wired.
5. The migration must skip generated surfaces and the #6927/#6928 files, and be re-runnable.
