---
title: 'ADR: the docsite is built with doc-kitty, consumed as a pinned git dependency, at directory URLs with every legacy URL redirected'
description: 'doc-kitty replaces DocFX for docs.spec-kitty.ai: a site/ sub-project reads ../docs, pins doc-kitty by commit, deploys at the domain root and redirects every legacy URL.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-10-31'
updated: '2026-10-31T00:00:00Z'
---

# The docsite is built with doc-kitty, consumed as a pinned git dependency, at directory URLs with every legacy URL redirected

**Status:** Proposed (2026-10-31). The operator accepts it by merging the pull request that carries it.

> **What was ruled and what is derived.**
> - **Ruled by the operator (2026-10-31, [#6100 decisions comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324)).** Numbered as in the comment; "ruling N" below refers to this list.
>   1. **URL scheme.** Directory URLs; every current `*.html` URL (about 830) redirects to its new address; no baseline URL breaks.
>   2. **Section index file.** `README.md`. The 56 folders whose index is `index.md` are renamed, and the 4 folders holding both files are resolved.
>   3. **Features only DocFX has.** The kitty-specs mission dashboards, their JSON-LD and the template's `main.js` are dropped for now. doc-kitty's generated `llms.txt` replaces the hand-written one and keeps the version-stance text. An upstream issue asks for mission and glossary pages as a hub-style grid of cards.
>   4. **What is published.** `plans/` (restricted feeds) and `development/` (its own section). Engineering-notes, investigations and research are draft or unpublished. Archive, reports, convergence and the pages about the retired hosted and sync surfaces are unpublished.
>   5. **Proposed ADRs** take `doc_status: active`.
>   6. **ADR index.** doc-kitty gains support for date-named ADRs in era folders, with a frontmatter `status` fallback; core's era indexes stay until then.
>   7. **#3891 stays separate**; [#2358](https://github.com/spec-kitty/spec-kitty/issues/2358), [#3914](https://github.com/spec-kitty/spec-kitty/issues/3914), [#2361](https://github.com/spec-kitty/spec-kitty/issues/2361) and [#2362](https://github.com/spec-kitty/spec-kitty/issues/2362) move under #6100.
>   8. **[#648](https://github.com/spec-kitty/spec-kitty/issues/648) stays standalone.**
>   9. **[#2302](https://github.com/spec-kitty/spec-kitty/issues/2302)** is written after cutover, in spec-kitty-open-packs.
>   10. **Toolkit.** The build consumes `spec-kitty/doc-kitty` directly; this record says how: a pinned git dependency or checkout, or the package doc-kitty publishes.
>   11. **Collisions.** Moves and renames are allowed; each open docs PR resolves its own conflicts when it merges.
>   12. **Glossary.** [#3024](https://github.com/spec-kitty/spec-kitty/issues/3024) settles the source of truth first; one `definitions.yaml` is then generated from it.
> - **Operator steer relayed with the step-1 brief (2026-10-31), not in the comment:** prefer not to depend on a separately authorised package. D-2 weighs it.
> - **Derived:** every decision below marked *(derived)*, and the spike results, which are evidence, not rulings.

**Date:** 2026-10-31

**Deciders:** Stijn Dejongh (operator). Derived clauses are proposed by this record for the operator's sign-off.

**Technical Story:**
- Epic [#6100](https://github.com/spec-kitty/spec-kitty/issues/6100) (step 1: this ADR and its spike).
- Absorbs [#2358](https://github.com/spec-kitty/spec-kitty/issues/2358) (a standing moves ledger and a living URL baseline). Places [#3914](https://github.com/spec-kitty/spec-kitty/issues/3914), [#2361](https://github.com/spec-kitty/spec-kitty/issues/2361) and [#2362](https://github.com/spec-kitty/spec-kitty/issues/2362) under #6100.
- Builds on [ADR 2026-06-27-1](../3.x/2026-06-27-1-common-docs-reconciliation.md) (in-file frontmatter is the page-metadata authority) where it still applies.
- Spike evidence: [`kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md) (on `main` once this record merges; `kitty-ops/` is outside the published site).

---

## Context and Problem Statement

`docs.spec-kitty.ai` is built by DocFX (.NET) from `docs/` and then post-processed by six Python scripts, in seven steps, in `.github/workflows/docs-pages.yml`: kitty-specs dashboard generation, SEO metadata, glossary auto-linking, PlantUML rendering, meta-refresh redirect stubs and two verifiers. The pipeline runs on a push to `main` or `2.x` and on manual dispatch. No pull request builds the site, so a render defect is found after merge. The workflow's own comments record this, and they still name a `docs-build-pr.yml` that no longer exists.

[doc-kitty](https://github.com/spec-kitty/doc-kitty) is Spec Kitty's own Astro + Starlight docs toolkit. It owns the frontmatter contract, the section registry, `llms.txt`, the agent and OKF exports (OKF: doc-kitty's export of the docs as plain Markdown with metadata, for agents), and the link and redirect gates that core rebuilt piecemeal around DocFX. Epic #6100 moves the docsite onto it. This record fixes the decisions every later step of #6100 depends on: how core consumes doc-kitty, where the site lives, what URLs it serves, how no published URL breaks, and how the move is gated, run in parallel, rolled back and finished.

## Decision Drivers

- **No published URL breaks.** About 830 URLs are live today: 668 current pages (derived from `docfx.json`'s content globs against the tree at this record's base) plus 163 legacy URLs already redirected by `scripts/docs/redirect_map.yaml`.
- **One authority per concern.** doc-kitty owns rendering and its gates; core owns its content, its URL ledger and its publication choices. Core does not fork or patch the toolkit.
- **No credential that is not already in the workflow.** No PAT. The operator also steered away from depending on a separately authorised package (the step-1 brief).
- **`docs/` stays where it is.** `spec-kitty docs query` reads `docs/development/docs-retrieval-index.yaml`, and agents, scripts and links across the repository address `docs/` paths.
- **A defect is caught on the pull request**, not after deploy.

## Considered Options

For consuming doc-kitty (ruling 10 leaves the choice to this record):

1. **A pnpm git dependency pinned by commit**, `github:spec-kitty/doc-kitty#<sha>&path:/src`, recorded in `site/pnpm-lock.yaml`.
2. **A CI checkout** of `spec-kitty/doc-kitty` at a pinned SHA, linked as `file:` or `link:`.
3. **doc-kitty's published package**, `@spec-kitty/doc-toolkit` on GitHub Packages.
4. **Vendoring** the toolkit source into core.

For the site's place in the repository: a `site/` sub-project reading `../docs`, or moving the content under the site project.

## Decision Outcome

**Chosen options:** a `site/` sub-project that reads `../docs`, consuming doc-kitty as a pnpm git dependency pinned by commit, deployed at the domain root with directory URLs and a generated redirect for every legacy URL. The decisions follow.

### D-1: doc-kitty replaces DocFX; `site/` is a sub-project and `docs/` stays at the root *(replacement: ruling 10 and the epic; layout: derived)*

- The docsite is built by doc-kitty. DocFX is retired as set out in D-13.
- `site/` holds the Astro project: `package.json`, `pnpm-lock.yaml`, `astro.config.mjs`, `src/content.config.ts`, `src/pages/llms.txt.ts`, `public/` (with `CNAME` and `robots.txt`), `url-baseline.txt`, `moves.yaml` and `redirects.json`.
- `defineDocKittyIntegrations({ docsDir: '../docs', indexBasename: 'README', … })` and `docKittyDocsLoader({ base: '../docs' })`. The two must agree; doc-kitty requires it.
- **Index-file sequencing.** DocFX emits a section page only from `index.md`. Renaming a folder's `index.md` to `README.md` while DocFX still deploys would make that section's `/dir/` and `/dir/index.html` return 404 on the live site.
  - During the parallel run (D-13), the site sets `indexBasename: ['README', 'index']`, as doc-kitty's own example does.
  - The 4 folders holding both files are resolved before the scaffold build, keeping `index.md` as the index, because two index files in one folder collapse to one route.
  - After DocFX retirement (D-13 step 5), all 60 `index.md` files become `README.md` (the 56 of ruling 2, plus the 4 resolved folders, which keep `index.md` until then); `indexBasename` then narrows to `'README'`. The rename waits for retirement, not just cutover, so that reverting the cutover still redeploys a DocFX site whose sections all build.
  - Every `dockitty-*` gate is run with `--astro-config astro.config.mjs`. Without it, a gate looks for the site config in the parent of the docs root (the repository root), finds none and falls back to `README` alone, so it would misread the 60 `index.md` files during the parallel run.
- `docs/` stays at the repository root. That keeps `spec-kitty docs query`, every in-repo link and every `scripts/docs` tool that reads `docs/` working unchanged.
- `docs/_meta/sections.yaml` is the section registry (doc-kitty's shape); it is authored content, not generated.
- **Spike:** a build with `docsDir: '../docs'` from a sibling `site/` project emitted every page, with each `README.md` as its section index. The doc-kitty survey had flagged this layout as untested upstream, so the scaffold step adds a fixture for it upstream (gap list, D-14).

### D-2: doc-kitty is consumed as a pnpm git dependency pinned by commit *(derived)*

`site/package.json` declares:

```json
"@spec-kitty/doc-toolkit": "github:spec-kitty/doc-kitty#<40-character commit SHA>&path:/src"
```

pnpm records the commit, the subpath and the repository in `site/pnpm-lock.yaml`. CI installs with `pnpm install --frozen-lockfile`. **Spike:** this resolved from the public repository with no token, built the site, and put the toolkit's `dockitty-*` gate binaries on the path.

| | Git dependency by commit (chosen) | CI checkout at a SHA | GitHub Packages (`@spec-kitty/doc-toolkit`) | Vendoring |
| --- | --- | --- | --- | --- |
| Pin authority | the lockfile, one place | a SHA in the workflow, plus a `file:` path the lockfile cannot verify | the lockfile (version + integrity) | the copied tree |
| Local build | `pnpm install` | needs a second clone at the right path | needs a PAT with `read:packages` in `~/.npmrc` | works |
| CI credential | none (public repository) | none (public repository) | `packages: read`, and package access granted to this repository | none |
| Separately authorised package | no | no | **yes** (rejected: the operator's steer, and a PAT locally) | no |
| Drift from upstream | none | none | none | the copy forks |

The CI checkout duplicates the pin into a place a lockfile does not see and makes local and CI builds differ. GitHub Packages is the package the operator did not want to depend on, and it needs a token locally. Vendoring forks the toolkit, against D-14.

**Bump procedure** (one pull request per bump, titled `docs(site): bump doc-kitty to <tag> (<short sha>)`):

1. Choose a doc-kitty release tag (`v*`) and resolve it to its commit: `git ls-remote https://github.com/spec-kitty/doc-kitty refs/tags/<tag>^{}`. Pin a commit a release tag points at, unless a fix the site needs is not yet released; then say so in the pull request.
2. Replace the SHA in `site/package.json`, align `astro`, `@astrojs/starlight` and `@astrojs/markdown-remark` with the peer ranges the new `src/package.json` declares, and run `pnpm install` in `site/`.
3. Run the build and every gate of D-11 locally, and read doc-kitty's `CHANGELOG.md` between the two tags for frontmatter or config changes.
4. Open the pull request; the required build gate (D-11) must pass.

A `make docs-site-bump REF=<tag>` target that does steps 1 and 2 is part of the scaffold step.

### D-3: CI uses no PAT *(derived)*

- **Install:** doc-kitty is public, so `pnpm install` needs no credential.
- **Deploy:** GitHub Pages deploys through OIDC (`pages: write`, `id-token: write`), as today.
- **Pages probe:** the existing probe keeps using `${{ github.token }}`.
- If doc-kitty ever becomes private, this record is amended before any credential is added. A PAT is not the fallback.

### D-4: the site deploys at the domain root *(derived)*

`astro.config.mjs` sets `site: 'https://docs.spec-kitty.ai'` and `base: '/'`, and passes `base: '/'` to `defineDocKittyIntegrations`. `CNAME` moves to `site/public/CNAME`.

Redirect targets are written base-less (`/guides/x/`). doc-kitty's example prefixes targets with the base; with `base: '/'` that produces `//guides/x/`, so the site does not copy that line.

### D-5: the URL contract, the baseline ledger and the moves ledger (absorbs #2358) *(URL shape: ruling 1; ledgers and generator: derived)*

**URL shape.** Every page is served at a directory URL (`/guides/getting-started/`, Astro's default `build.format: 'directory'`).

**Baseline ledger.** `site/url-baseline.txt` is the committed list of every URL the site has ever published (doc-kitty's format: one site-relative URL per line, `#` comments). It is a living ledger:

- It is **seeded once**, before cutover, from the union of:
  - a site walk of the last DocFX build (`scripts/docs/capture_baseline_urls.py --site-dir`), which is the canonical capture and replaces the current 180-URL manifest;
  - every key of `scripts/docs/redirect_map.yaml`.

  The derive-from-source run for this record counts 668 + 163 = 831 URLs.
- It **grows on publish**: a new page's URL is appended in the pull request that publishes it.
- An entry is **removed** only with a recorded amendment (date, pull request, ruling), as `redirect_baseline_urls.json` already does.

**Moves ledger.** `site/moves.yaml` is a standing, repository-level, append-only list of `old route -> new route` moves. It replaces the mission-scoped `occurrence_map.yaml` binding that #2358 reports.

**Redirect declarations.** `site/redirects.json` (Astro's `redirects` map) is generated from the two ledgers by one script, never edited by hand:

1. Every legacy `X.html` page URL redirects to the directory URL of its current page, `X/`, or to the page that `moves.yaml` says replaced it. A legacy `dir/README.html` (DocFX published a `README.md` index under its own name; 16 such URLs today) redirects to `dir/`.
2. Redirect chains are collapsed: every key points at a final, live route.
3. A legacy `dir/index.html` URL gets **no** declaration **when `dir/` is a live section**. With the directory build format, the section's page is always `dist/dir/index.html`, whether its source is `index.md` or `README.md`, and GitHub Pages serves it at that URL. A declaration there would collide with the page. A `dir/index.html` key whose section no longer exists is declared like any other key; 11 such keys sit in today's map (`1x/`, `2x/`, `3x/`, `archive/`, `archive/1x/`, `archive/2x/`, `explanation/`, `how-to/`, `recovery/`, `reference/`, `tutorials/`). **Spike:** a key `/tutorials/index.html` emitted `dist/tutorials/index.html/index.html`, the gate covered it, and the emulation resolved it.
4. A baseline URL whose page is unpublished (ruling 4: draft, excluded or retired) redirects to the nearest published page, normally its section hub (for example `/plans/research/x.html` → `/plans/`). Ruling 1 says no baseline URL breaks, and ruling 4 says the page is not published; a redirect to the hub satisfies both. 34 such URLs come from `plans/` alone (engineering-notes 21, investigations 11, research 2). An entry leaves the baseline only by a recorded amendment that cites an operator ruling.

**Spike:**
- Astro emits a `.html` redirect key as a directory stub, `dist/a/b.html/index.html`.
- Under the documented GitHub Pages serving rules (emulated), `/a/b.html` returns a 301 to `/a/b.html/`, then the stub's meta refresh, then the page.
- doc-kitty's `check-redirect-coverage.mjs` covers these keys, including a two-hop chain, without change.
- The real Pages service was not exercised. The canary in D-13 confirms it before cutover, so the GitHub Pages leg is **UNVERIFIED** until then.

**Fallback (evaluated, not chosen):** flat stubs (`dist/a/b.html` as a file) remove the 301 hop. The emulation serves them correctly, but doc-kitty's coverage gate cannot see them, and they need a post-build step outside Astro. Use them only if the canary shows the directory 301 misbehaving; until upstream gap (b) lands they also need the gate override below.

**Gate gap and interim.** doc-kitty's gate looks only for `<path>/index.html`, so it reports a legacy `dir/index.html` URL as uncovered even though the page is there. Until upstream gap (b) lands, the gate runs with a generated `--redirects` override mapping each `dir/index.html` to `dir/`. The override is used by the gate alone, never by the site, and the gate still checks that the target is live. The spike's mutant run, with a dead target, failed as expected.

**Full-corpus spike.** The generator rules above, run on the real ~831-URL baseline against a doc-kitty build of the real `docs/` tree (after the D-7 fixes, see the spike evidence), declared 789 redirects: 753 to the URL's own page, 36 to a section hub (rule 4), with all 163 legacy map entries collapsed to their final page. 42 legacy `dir/index.html` URLs needed no declaration (rule 3). The coverage gate, run without `--docs`, reported **831/831 covered**, and the GitHub Pages emulation resolved all 831.

**No silent excuse.** Run with `--docs` and drafts off, the gate accepts a baselined URL that ends at a draft page as "unpublished". So the gate also runs a second time without `--docs`, which excuses nothing; rule 4 makes that run pass.

**Dropped dashboards.** The kitty-specs dashboard URLs (`/kitty-specs/**`, including `/kitty-specs/glossary.html`) are generated, were never part of the baseline, and are not in the ~830. They are dropped (ruling 3). The site's `404` page names the retirement for any `/kitty-specs/` path.

### D-6: `scripts/docs` keep / port / drop *(derived)*

"Keep" means the script stays as it is and keeps its tests. "Port" means its job moves to doc-kitty or to `site/`, and the Python script is deleted in the step that ports it. "Drop" means it is deleted at DocFX retirement (D-13), or sooner when nothing calls it.

| Script | Verdict | Where its job goes |
| --- | --- | --- |
| `docs_index.py`, `_inventory.py`, `inventory_lockfile.py` | keep | They feed `spec-kitty docs query` and the page inventory, from `docs/` frontmatter. Updated for `README.md` indexes. |
| `freshen_adr_inventory.py` | keep (until gap a) | Keeps the era indexes (ruling 6); retired when doc-kitty's ADR index lands. |
| `check_changelog_style.py`, `sync_changelog.py`, `check_spelling.py` | keep | Source-level checks with no DocFX dependency. |
| `build_cli_reference.py`, `check_cli_reference_freshness.py`, `check_slash_command_freshness.py`, `_typer_walker.py`, `_render.py`, `_guards.py` | keep | They generate or check source pages. |
| `check_docs_freshness.py`, `version_leakage_check.py` | keep | Re-pointed at `README.md` indexes. |
| `audience_resolver.py`, `related_validator.py`, `description_length_check.py` | port | `dockitty-validate-frontmatter` (audience, related, description length). |
| `relative_link_fixer.py` (link check) | port | `dockitty-check-links docs --strict`. The one-shot fixer mode is dropped. |
| `capture_baseline_urls.py` | keep for one run, then drop | Seeds `site/url-baseline.txt` from the last DocFX build. |
| `redirect_stub_generator.py`, `redirect_map.yaml`, `redirect_baseline_urls.json` | port | `site/redirects.json` generator + doc-kitty's `check-redirect-coverage`. The map and manifest feed the seed, then retire. |
| `seo_postprocess.py`, `seo_verify.py` | port | Starlight emits description, canonical and Open Graph; `dockitty-assert-no-broken-links` and the build artifact checks verify the output. Any check doc-kitty lacks is an upstream gap. |
| `glossary_linker.py`, `glossary_page/` | port (after #3024) | doc-kitty's Contextive glossary and auto-link (D-10). |
| `plantuml_render.py`, `plantuml_invoke.py`, `plantuml_pins.json` | port, then drop at retirement | doc-kitty's build-time diagram render (its ADR-0040) against a self-hosted PlantUML server; see D-11. They and their tests are deleted with DocFX. |
| `generate_kitty_specs_docs.py` | drop | Dashboards dropped (ruling 3). |
| `_published_pages.py` | port | `docs/_meta/sections.yaml` plus the publication rules of D-8. |
| `frontmatter_backfill.py`, `frontmatter_backfill_sections.yaml`, `adr_converter.py` | keep for the migration, then drop | Reused by the frontmatter migration of D-7. |
| `bulk_ref_rewrite.py`, `rename_reconcile.py`, `touched_set_gates.py` | keep for the README rename, then drop | Reused by the rename step; their binding to a closed Mission's `occurrence_map.yaml` is replaced by `site/moves.yaml`. |
| `docs/docfx.json`, every `toc.yml`, `docs/templates/spec-kitty/` (incl. `main.js`) | drop | At DocFX retirement. |

### D-7: the frontmatter contract mapping *(derived)*

doc-kitty's gate requires `title`, `description`, `doc_status`, `updated` and `kind`. The current corpus (913 Markdown files) maps as follows, in one mechanical migration per row group:

| Field | Today | On doc-kitty |
| --- | --- | --- |
| `kind` | absent everywhere; 209 pages carry a lowercase Divio `type` | `kind` from `type` (`how-to` → `How-To`, `explanation` → `Explanation`, `reference` → `Reference`, `tutorial` → `Tutorial`); section index pages get `kind: Hub`; ADRs get `kind: ADR`; the rest are classified in the migration step, and any page left unclassified is a migration failure. `type` stays only where it carries doc-kitty's `type` meaning. |
| `audience` | a path string such as `docs/context/audience/internal/maintainer.md` | `[{ profile: internal/maintainer, guidance_text: … }]`, which needs nested persona slugs (gap d). Personas stay under `docs/context/audience/`. |
| `doc_status` | `active`, `deprecated`, `draft`, `superseded`, `durable`, plus `closeout`, `point_in_time` and `proposal` | The five canonical values pass. `closeout` and `point_in_time` map to `durable`; `proposal` maps to `draft`. |
| `updated` | a date (`'2026-10-26'`) on 724 pages; absent on the rest | Normalised to an instant (`2026-10-26T00:00:00Z`); ADRs take theirs from `date`. |
| ADR metadata | `status` (`Accepted`, `Proposed`, `Superseded`) and `date`, with **no `doc_status`** on all 226 ADRs that predate this record | `kind: ADR`; `doc_status`: `Accepted` → `active`, `Proposed` → `active` (ruling 5), `Superseded` → `superseded`; `updated` from `date`. `status` and `date` stay, because core's era indexes read them. This record already carries `doc_status: active`. |
| `related` | repository paths (`docs/changelog/index.md`) on 413 pages, 32 of them outside `docs/` (`kitty-specs/`, `tests/`, `pyproject.toml`) | doc-kitty page slugs (`changelog`, `adr/3.x/<file>` without `.md`). References outside `docs/` move to `external_references`; references to unpublished pages follow D-8. |
| Excluded trees | archive, reports and convergence (242 files); 31 lack `title` or `description` | Only the build-schema minimum: `title`, `description`, an `audience` list where present (D-8). |
| Index files | `index.md` in 60 folders; 4 also hold a `README.md` (`adr/1.x`, `adr/2.x`, `adr/3.x`, `architecture`) | Before the scaffold, the 4 folders get one index each, `index.md`. The three ADR-era `README.md` files are redirect stubs pointing at their `index.md`; they are deleted, and their `README.html` URLs redirect to `/adr/<era>/`. `architecture/README.md` is a 131-line landing page and is folded into `architecture/index.md`. After DocFX retirement, all 60 `index.md` become `README.md` and `indexBasename` is `README` only (sequencing: D-1). |

**ADRs must gain `doc_status`.** doc-kitty treats a page with no `doc_status` as a draft, and a drafts-off build does not publish it. Without the ADR row above, every ADR would vanish from the live site.

**The immutable corpus.** ADRs, plans, reports and changelog entries keep their **body** byte for byte. A frontmatter-only change made by a recorded, mechanical migration is allowed. The migration step carries a test that hashes every immutable file's body before and after and fails on any difference.

One body change is allowed, and it needs the operator's sign-off with this record: a **mechanical link-target rewrite** driven by `site/moves.yaml`. The README rename alone touches links in 43 immutable files. The hash test normalises link targets through the moves ledger before comparing, so a rewritten link passes and any other change fails.

### D-8: what is published *(derived from ruling 4)*

- `docs/_meta/sections.yaml` registers every published section. `development` is its own section. `plans` is registered with restricted `feeds` (no `llms`, no `agent`, no `rss`).
- `plans/engineering-notes/`, `plans/investigations/` and `plans/research/` take `doc_status: draft`. The live build runs with `DK_PUBLISH_DRAFTS=off`, so they are not published. doc-kitty defaults the setting to `on`, so `site/.env.production` sets it to `off`, in one place; workflows do not repeat it.
- An unpublished page's old URL redirects to its section hub (D-5 rule 4).
- `archive/`, `reports/` and `convergence/`, together with the pages about the retired hosted and sync surfaces (listed in the publication step), are not published.
- **Exclusion mechanism.** doc-kitty has no section exclusion (gap f). Until it does, `site/src/content.config.ts` wraps `docKittyDocsLoader` with a filter that drops those route prefixes. **Spike:** with the filter, an archived `doc_status: deprecated` page was absent from pages, hub links, the sitemap, `llms.txt`, the OKF export and the content graph. Without it, the same page was built and linked from two hubs.
  - **Limit of the shim.** The filter drops entries only after doc-kitty's loader has validated them, so an excluded page must still pass the build schema (`title`, `description`, an `audience` list). In the full-corpus spike, 31 excluded pages (reports 24, convergence 4, archive 3) failed it. They get that minimum frontmatter in the D-7 migration until gap (f) lands.
- **`related` must name published pages.** doc-kitty resolves every `related` entry against the built pages, and a dangling one is build-fatal. A published page may therefore not list a draft or excluded page there. In the full-corpus spike, 181 such entries had to go; the migration moves them into the body as ordinary links, which `check-links` judges, or drops them.
- **Gates scope.** `dockitty-validate-frontmatter` and `dockitty-check-links` walk every file under `docs/`, including the 242 files in archive, reports and convergence that are never published. They run over the published sections only; the unpublished trees get only the build-schema minimum above.

### D-9: `llms.txt` is generated *(ruling 3)*

`site/src/pages/llms.txt.ts` mounts doc-kitty's `llmsTxtRoute`. The route takes a title and a description only, so the version-stance block (current docs, runtime model, governance source, mission loop command, where 1.x and 2.x history lives) is inserted by a thin wrapper around its response until doc-kitty takes a preamble option (gap h). The hand-written `docs/llms.txt` is deleted at cutover.

### D-10: the glossary waits on #3024 *(ruling 12)*

The glossary step starts after #3024 settles the source (packs or `docs/context`). That step then generates the single `.contextive/definitions.yaml` doc-kitty reads. doc-kitty reads it from the site project, so it is `site/.contextive/definitions.yaml`, generated and not committed. Multi-file Contextive (`imports:`, gap e) is not needed for that. doc-kitty's glossary integration writes generated term pages into `<docsDir>/glossary/`, which here is `docs/glossary/`, inside core's tree. Until doc-kitty takes an output path (gap e), that folder is gitignored and excluded from `docs_index.py` and the page inventory. The current glossary page is a dashboard page (`/kitty-specs/glossary.html`), outside the baseline, so cutover does not wait for the glossary step.

### D-11: a required pull-request build gate *(derived)*

A `docs-site` job runs on every pull request that touches `docs/**`, `site/**` or its own workflow. It installs with the frozen lockfile and builds with drafts off (D-8). It then runs these gates, each with `--astro-config astro.config.mjs` (D-1), over the published sections (D-8):

- `dockitty-validate-frontmatter`;
- `dockitty-check-links --strict`;
- `dockitty-check-redirect-coverage url-baseline.txt dist --docs ../docs --astro-config astro.config.mjs --declared-redirects redirects.json`, plus the interim override of D-5;
- `dockitty-assert-no-broken-links dist --base / --site https://docs.spec-kitty.ai`;
- a check that `redirects.json` equals its generated form.

**Diagrams.** doc-kitty renders PlantUML at build time to static SVG against a self-hosted server, never `plantuml.com`. Its own CI runs `plantuml/plantuml-server` as a job-level `services:` container on `localhost:8091` with a readiness wait, sets `DK_PLANTUML_SERVER_URL=http://localhost:8091/svg/`, and checks with `plantuml-guard.mjs` (used by `assert-build-artifacts.mjs`) that no `plantuml.com` URL and no non-self-hosted default reaches the build. PlantUML only renders in doc-kitty's build mode. Left alone, the mode follows whether a Playwright Chromium happens to be installed, so local and CI builds could differ. The site therefore sets `diagrams: true` and `DK_DIAGRAM_BUILD_RENDER=build`, and the job installs a pinned Playwright Chromium (core has 18 Mermaid and 5 PlantUML sources). Core's `docs-site` job and the deploy workflow adopt doc-kitty's server pattern, with one change: the image is pinned by digest, not `:jetty`, keeping core's practice of pinning third-party build inputs by digest. The current `docker --network=none` isolation does not carry over, because the server runs as a service container. A diagram's `!include` of a remote URL is therefore the remaining egress path, and the diagrams step restricts it in the server's configuration or refuses such includes at source.

The job lives in `ci-router.yml`, behind a path filter for `docs/**` and `site/**` registered in `gate_selection.py`, and is added to `router-gate`'s `needs:`. That makes it required, with no `continue-on-error`. It cannot join `ci-aggregate.yml`'s `aggregate-gate`: that workflow runs on `workflow_run`, and GitHub Actions has no cross-workflow `needs:`. The router's own tests (for example `tests/ci/test_docs_lint_job.py`) pin the wiring. The deploy workflow builds with the same steps, so main can never deploy a site no pull request built.

### D-12: invariants kept *(derived)*

- **Packaging.** `site/**` is excluded from the sdist; the wheel only ships its declared packages. `tests/cross_cutting/packaging/test_packaging_safety.py` asserts it on the built archive.
  - The sdist's bare `README.md` include is gitignore-style. Today it already ships 31 `docs/**/README.md` and 676 `kitty-specs/**/README.md` files, and the README rename would add 56 more, net. Anchoring it to `/README.md` is a pre-existing defect, tracked in [#6926](https://github.com/spec-kitty/spec-kitty/issues/6926), and must land before the rename.
- **Fork guard.** Every new workflow's automated trigger (push, schedule, `workflow_run`) carries the core-repository guard pinned by `tests/ci/test_fork_guard.py`. Pull-request and dispatch runs work on forks.
- **Pages probe.** The deploy workflow keeps the probe-then-configure job, the 404-skips and other-status-fails semantics, and the `main`-only, core-repository-only deploy pinned by `tests/release/test_release_ci_ownership.py`. The test is updated with the workflow, never loosened.

### D-13: parallel run, rollback and DocFX retirement *(derived)*

A repository has one Pages site, so "parallel" means built in parallel, not served in parallel.

1. **Parallel run.** From the scaffold step on, every pull request and every push to `main` builds the doc-kitty site and runs the D-11 gates. The deploy workflow still publishes DocFX.
2. **Canary.** The deploy job may only publish from `main` in the core repository, so the canary is a short production window on `docs.spec-kitty.ai`. It is announced, and docs merges to `main` are frozen for its duration (a push would queue a DocFX deploy in the `pages` concurrency group). Before cutover, one manually dispatched run deploys the doc-kitty build, probes a sample of baseline URLs over HTTP (one `.html` redirect key, one chain, one `dir/index.html`, one `dir/README.html`, one directory URL), and redeploys DocFX. This is where the D-5 GitHub Pages result stops being UNVERIFIED.
3. **Cutover.** One pull request switches the deploy job's artifact to `site/dist`.
4. **Rollback.** Revert the cutover pull request. The DocFX path stays intact until retirement, and the README rename waits for retirement (D-1), so the rollback works for that whole window.
5. **Retirement.** After one Spec Kitty release ships with the doc-kitty site live, a pull request removes DocFX: `docfx.json`, `toc.yml`, the template, the .NET setup and the scripts marked "drop" in D-6. It also updates or deletes the 26 Python files that read `docfx.json` or `toc.yml`, most of them under `tests/docs/`, plus `tests/_support/docfx_reports_guard.py` and the terminology scope helper. The README rename (D-1) follows in its own pull requests.

### D-14: upstream gaps go to doc-kitty *(derived)*

Core does not patch, fork or vendor doc-kitty. A gap is filed upstream; core carries at most a thin, named, consumer-side shim with a removal trigger. The shims are the loader filter (D-8), the `llms.txt` wrapper (D-9) and the gate override (D-5).

Gaps filed or to file:
- (a) ADR index for date-named, era-foldered ADRs with a frontmatter-status fallback;
- (b) the coverage gate resolves an exact `*.html` file before `<path>/index.html`;
- (c) GitHub `> [!NOTE]` alerts (7 files use them; the spike rendered them as literal text);
- (d) nested persona slugs;
- (e) multi-file Contextive, `imports:`, and an output path for generated glossary pages;
- (f) excluding sections from the build, before schema validation;
- (g) hub-style card grids for mission and glossary pages, styled with the operator's "chromed" design system, that is doc-kitty's site-chrome theme (`specKittyTheme`, the `--dk-*` tokens);
- (h) an `llms.txt` preamble option;
- (i) a fixture for a `docsDir` outside the site project.

### Consequences

#### Positive

- One toolkit owns rendering, metadata and gates; seven post-processing steps leave core.
- A pull request builds and gates the site; DocFX's deploy-time-only verification ends.
- No URL in the ledger breaks, and the ledger has a standing home (#2358).
- No .NET toolchain and no credential beyond the workflow token.

#### Negative

- Node and pnpm join core's CI toolchain for the docs job.
- The frontmatter migration touches most of the 913 Markdown files once (frontmatter only).
- Three consumer-side shims live until their upstream gaps close.
- `.html` redirects cost one extra 301 on GitHub Pages.

#### Neutral

- The kitty-specs dashboards and the dashboard glossary page go dark until the hub-card work (gap g) brings mission pages back.

### Confirmation

- The D-11 gate is green on the scaffold pull request with the full ~830-URL ledger.
- The D-13 canary probes pass on the real Pages service.
- After cutover, #2361's post-deploy smoketest and #2362's nightly crawl are green.

## Pros and Cons of the Options

### Git dependency pinned by commit (chosen)

- Good, because the lockfile is the one pin, local and CI builds match, and no credential is needed.
- Bad, because a bump is a hand-chosen SHA rather than a semver range, and the toolkit's own dependencies resolve in core's lockfile.

### CI checkout at a pinned SHA

- Good, because it needs no registry.
- Bad, because the pin lives outside the lockfile and local builds need a second clone.

### GitHub Packages

- Good, because it is versioned and integrity-hashed.
- Bad, because it is the separately authorised package the operator steered away from, and installing it locally needs a PAT.

### Vendoring

- Good, because it is self-contained.
- Bad, because it forks the toolkit and hides gaps from upstream.

## More Information

- Spike evidence, reproduction steps and the GitHub Pages emulator: [`kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).
- **Delivery.** The remaining steps are sub-issues of #6100:
  - ledgers and the dual-index folders: [#6927](https://github.com/spec-kitty/spec-kitty/issues/6927) (D-5, absorbs #2358 and #3914) and [#6928](https://github.com/spec-kitty/spec-kitty/issues/6928) (D-1);
  - frontmatter: [#6929](https://github.com/spec-kitty/spec-kitty/issues/6929), the build-blocking migration, and [#6931](https://github.com/spec-kitty/spec-kitty/issues/6931), contract completion (D-7);
  - site: [#6930](https://github.com/spec-kitty/spec-kitty/issues/6930), the scaffold and `docs-site` job (D-1, D-2, D-11); [#6932](https://github.com/spec-kitty/spec-kitty/issues/6932), publication (D-8); [#6933](https://github.com/spec-kitty/spec-kitty/issues/6933), redirects (D-5); [#6934](https://github.com/spec-kitty/spec-kitty/issues/6934), `llms.txt` (D-9);
  - rendering: [#6935](https://github.com/spec-kitty/spec-kitty/issues/6935), render parity, and [#6936](https://github.com/spec-kitty/spec-kitty/issues/6936), diagrams (D-11);
  - rollout: [#6937](https://github.com/spec-kitty/spec-kitty/issues/6937), the required gate; [#6938](https://github.com/spec-kitty/spec-kitty/issues/6938), canary and cutover, with #2361; [#6943](https://github.com/spec-kitty/spec-kitty/issues/6943), DocFX retirement; then [#6939](https://github.com/spec-kitty/spec-kitty/issues/6939), the README rename (D-13);
  - after upstream work: [#6940](https://github.com/spec-kitty/spec-kitty/issues/6940), glossary (after #3024); [#6941](https://github.com/spec-kitty/spec-kitty/issues/6941), mission pages (gap g); [#6942](https://github.com/spec-kitty/spec-kitty/issues/6942), ADR index (gap a);
  - packaging: [#6926](https://github.com/spec-kitty/spec-kitty/issues/6926) (D-12).
- The upstream doc-kitty issue drafts (a)–(i) sit in the same folder as the spike evidence.
- doc-kitty commit the spike ran against: `494f2d878e2e4766d9859a4f073efb793ad86900` (doc-toolkit 0.5.0 plus unreleased commits).

## Amendment 2026-11-09

Recorded with #6932 (publication). D-8's text above is unchanged; this section records how it is carried out and where it drifted.

- **Folder exclusion runs through doc-kitty's `exclude` option.** Gap (f) closed upstream (doc-kitty ADR-0070) before #6932 started. `site/astro.config.mjs` passes `exclude` from the generated `site/dockitty-contract.json`, which `scripts/docs/site_contract.py` projects from `EXCLUDED_FOLDERS` in `scripts/docs/_dockitty_contract.py`. No loader-filter shim exists: `site/src/content.config.ts` does not filter. The D-14 shim list therefore no longer includes the loader filter.
- **Working-note folders are drafts.** `plans/engineering-notes/`, `plans/investigations/` and `plans/research/` are named once, as `DRAFT_FOLDERS` in the contract module. Every page in them takes `doc_status: draft` (a frontmatter-only change; the bodies are history). They are not excluded folders, because `exclude` would also drop them from the frontmatter and link gates.
- **Retired single pages are archived.** `exclude` takes folders only (per-file exclusion is asked upstream in `spec-kitty/doc-kitty#312`), and the retired hosted and sync pages are single files spread over several sections. The operator decided on 2026-11-09 to move them under `docs/archive/<section>/`. The move changed one thing in their bodies: 14 relative links in 7 of the 10 moved pages were re-pointed to the same targets, the path adjusted for the new location. Nothing else in a body changed. This is accepted under C-001 as part of a move. Each old route gets an append-only `site/moves.yaml` row to its section hub (D-5 rule 4).
- **One authority for the unpublished set.** `unpublished_routes()` in the contract module derives it: pages in an excluded folder, pages in a draft folder, and pages that are not published. The built-site check `scripts/docs/site_built_check.py` reads it after the build, and so does the redirect generator (#6933). The check walks the built pages, links, sitemap, OKF export, search index, `llms.txt` and the agent index.
- **The link gates run with priced debt.** `dockitty-check-links --strict` and `dockitty-assert-no-broken-links` run in the shared build through `scripts/docs/site_link_gates.py`. It fails on any problem that `site/link-debt.json` does not list. That file lists only problems whose source is immutable history (dated ADRs, `plans/`, `reports/`, `changelog/`, `archive/`), whose bodies are never rewritten (Standing Order #5, burn-down #7489). A problem in an editable page is fixed, not listed. The relative-link test reads the same file. It is not a ratchet.
- Clarification 2026-11-10: a live hub (`kind: Hub`) is never an immutable source, and neither is a `plans/` page whose `doc_status` is `active` or `durable`, or whose `kind` or `doc_status` cannot be read; such a page fixes its broken links instead of pricing them in `site/link-debt.json`. One predicate, `is_debt_eligible_source`, judges both the link gates and the relative-link debt.
- **One frontmatter edit to a dated ADR.** `docs/adr/3.x/2026-08-16-1-pack-metadata-manifest-unification.md` dropped `related: plans/investigations/2026-08-pack-level-metadata-manifest`. That page is now a draft (working-note folder, above), and a `related` entry that names an unpublished page is a build-fatal dangling reference in doc-kitty's `Related` block. The ADR body is unchanged.

## Amendment 2026-11-10

Recorded with #6933 (redirects). D-5's and D-14's text above is unchanged. This section records how the redirect layer is carried out with doc-kitty v0.7.0 (`5acb83c`), and where it departs from them.

- **The map is doc-kitty's `legacyHtmlRedirects`, not Astro's `redirects`.**
  - Every one of the 970 baseline routes ends in `.html`. doc-kitty refuses `.html` keys in Astro's `redirects` on static output (doc-kitty #253), so Astro's `redirects` stays empty.
  - The generated map is `site/legacy-redirects.json`, not D-5's `site/redirects.json`. It is a flat JSON object with no comment key, because doc-kitty validates every key as a legacy `.html` path.
  - `site/astro.config.mjs` reads it, and doc-kitty writes one flat stub per key (`dist/a/b.html`).
- **D-5's fallback is now the mechanism.** Flat stubs, the fallback D-5 evaluated and did not choose, are what upstream writes. The coverage gate sees them (doc-kitty ADR-0071), and they remove the 301 hop D-5's spike worried about. The D-13 canary still decides the GitHub Pages leg.
- **The gate override is retired.** Gap (b) closed upstream: the gate resolves `/a/index.html` to the file that `/a/` serves. Both runs report 970/970 with no `--redirects` override, so the D-14 shim list no longer includes the gate override.
- **One generator, one authority per input.** `scripts/docs/site_redirects.py` derives the map from three inputs:
  - the URL baseline;
  - `site/moves.yaml`, with chains collapsed by `moves_ledger.collapse`;
  - the published set: `route_of` of every page minus `unpublished_routes()`.

  `--check` fails the build when the committed map is stale.
- **Rule 4 lives in the generator.** While DocFX still publishes drafts, a `moves.yaml` row away from a draft page fails DocFX's own map check. The generator therefore redirects an unpublished page's route to its nearest published ancestor. Rule 4 moves into the ledger only once #6943 retires DocFX. Until then the two sites may answer the same legacy URL differently: DocFX's own map (`redirect_stub_generator.py`) has no rule 4 and no resource rule. That difference is accepted until the #6943 cutover.
- **Rule 5: resources.** `docs/assets/spec-kitty-backlog.html` and `docs/assets/spec-kitty-evolution-v1-to-v3.html` are standalone HTML that DocFX copied as resources; doc-kitty publishes only pages.
  - Operator ruling 2026-11-10: they redirect to the `/assets/` hub.
  - The generator applies this as a rule, not a list: a baseline route backed by a non-page file under `docs/` goes to its nearest published ancestor.
  - Any other baseline route with no page and no move is refused.
- **Counts at this amendment.** 970 baseline routes and 929 keys:

  | Kind of route | Count |
  | --- | --- |
  | its own page | 571 |
  | its moved page | 305 |
  | a section hub, page unpublished | 51 |
  | a section hub, resource | 2 |
  | no key: a live, unmoved `dir/index.html` (rule 3) | 41 |

  D-5's "11 dead-section `dir/index.html` keys" are now 21, because more sections moved since.
- **The gate runs twice, as D-5 says, and proves itself.** The shared build runs `dockitty-check-redirect-coverage` once with `--docs` and the declared map, and once with neither. A self-test then runs the gate against a hard-linked copy of the built site with three mutants: a dead target, a missing key and a draft-excused URL. It requires each verdict, so a gate that stops failing is caught.
- **Redirect stubs are not publications.** The built-site check recognises doc-kitty's stub through one predicate, `redirect_stub_target` in `scripts/docs/_dockitty_contract.py`. That predicate mirrors doc-kitty's `REDIRECT_STUB_RE`.
  - The `page` and `render` surfaces skip stubs.
  - The `link` surface still reports a stub whose target is unpublished.

## Amendment 2026-11-11

Recorded with #6938 (canary, first of two pull requests; the cutover is the second). D-11's and D-13's text above is unchanged. This section records how the D-13 canary is carried out.

- **The canary is a dispatch input of the deploy workflow.** `docs-pages.yml` takes `canary` (boolean, off by default) on `workflow_dispatch`. A push to `main`, or a dispatch without it, runs the DocFX path as before: the same `pages` and `build` jobs, and a `deploy` that runs only after a successful DocFX build.
- **The canary builds through the one shared definition (D-11).**
  - `canary-build` calls `docs-site-build.yml` with `pages-artifact: true` and its own artifact name, `github-pages-canary`, a new input of the shared build that defaults to `github-pages`. The two Pages artifacts of one run never collide.
  - So the deploy workflow and the `docs-site` gate now share one build definition, which was the open part of #6937.
- **The restore is ready before production changes.** `canary-deploy` publishes the canary with `actions/deploy-pages` (`artifact_name: github-pages-canary`, environment `github-pages`) only when both the canary build and the DocFX build succeeded, from `main` of the core repository. Only this job holds `pages: write` and `id-token: write` among the canary jobs.
- **DocFX is always republished.** `canary-probe` runs after the canary is live. The DocFX `deploy` job needs it and runs on `!cancelled() || inputs.canary`, so on a canary it republishes DocFX whatever the probe found, and also after a cancel. `needs.build.result == 'success'` still blocks it after a failed DocFX build. A failed canary job leaves the run red.
- **The probe's URL classes.** `scripts/docs/site_live_probe.py` derives one URL per class from the committed ledgers (`site/url-baseline.txt`, `site/moves.yaml`, `site/legacy-redirects.json`), the first in sorted order. A class with no candidate refuses. The classes are:
  - a legacy `.html` key to its own page;
  - a moved-chain key, whose `moves.yaml` destination moved again;
  - a live `dir/index.html` with no key (D-5 rule 3) and its directory URL;
  - a `dir/README.html` key;
  - the site root and `/llms.txt`;
  - `/kitty-specs/glossary.html`, which D-5 drops and which must answer 404.
- **What the probe asserts.** Redirects are not followed, so a 3xx fails: flat stubs exist to remove that hop. A page answers 200 and is not a stub. A key answers 200 with a stub (judged by `redirect_stub_target`) whose target equals the map's, and the target answers 200 with a page. Each URL gets bounded retries for Pages propagation, under a 300 s wall-clock budget that covers the whole request.
- **The gate runs the probe too.** The shared build serves `site/dist` on loopback and runs the probe once with one attempt. A ledger change that drops a class, or a build that stops answering one, fails a pull request before any canary.
- **Operation.** The operator dispatches the canary on `main` in an announced window with docs merges frozen, because a push would queue a DocFX deploy in the `pages` concurrency group. The D-5 GitHub Pages leg stays UNVERIFIED until that run passes. The post-deploy smoketest of #2361 lands with the cutover and reuses the probe.

## Amendment 2026-11-11 (cutover)

Recorded with #6938 (cutover, the second of its two pull requests) and #2361 (post-deploy smoketest). D-9's, D-11's and D-13's text above is unchanged. This section records how D-13 step 3 is carried out and what step 4, the rollback, restores.

- **The canary passed.** The operator dispatched it on `main` in an announced window: run [43027580608](https://github.com/spec-kitty/spec-kitty/actions/runs/43027580608), report on [#6938](https://github.com/spec-kitty/spec-kitty/issues/6938#issuecomment-6796965517). All 8 URL classes of the probe passed on the real GitHub Pages service, and DocFX was then restored byte-identical. The D-5 GitHub Pages leg is VERIFIED.
- **The deploy publishes the doc-kitty build.** In `docs-pages.yml`, `build` calls the shared `docs-site-build.yml` with `pages-artifact: true`, under the default artifact name `github-pages`. `deploy` publishes that artifact with `actions/deploy-pages`, from `main` of the core repository only, after a successful build. D-11's last sentence now holds: `main` deploys only a site built by the definition the `docs-site` pull-request gate runs.
- **The Pages probe stays.** The `pages` probe-then-configure job, its 404-skips and other-status-fails semantics, the `pages` concurrency group (no cancel in progress) and the fork guard are unchanged (D-12). `actions/configure-pages` is now pinned by commit, like every other action in the workflow.
- **Token permissions.**
  - The workflow default is `contents: read`.
  - The `pages` job holds `pages: read`.
  - `build` and `smoketest` hold `contents: read`.
  - Only `deploy` holds `pages: write` and `id-token: write`.
- **Post-deploy smoketest (#2361).**
  - What it is: a `smoketest` job with `needs: deploy`, on `main` of the core repository only.
  - What it runs: `python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai`.
  - Which URLs: the probe and its URL classes are the canary's (Amendment 2026-11-11 above), derived from the committed ledgers.
  - On failure: a mismatch fails the job and turns the run red.
  - No alert issue: the operator decided that the red run is the signal, so #2361's optional auto-filed alert issue is not adopted.
- **The canary is retired into the smoketest.** The `canary` dispatch input and the `canary-build`, `canary-deploy` and `canary-probe` jobs are removed. A canary of the site already live would duplicate the smoketest. A plain dispatch on `main` deploys and smoketests like a push; on another branch it only builds.
- **DocFX stops running in the deploy workflow.** The DocFX `build` and `deploy` jobs are removed. Their sources stay until #6943 (D-13 step 5): `docs/docfx.json`, `toc.yml`, the template, the DocFX scripts and their tests. In the meantime no CI job builds DocFX.
- **`docs/llms.txt` is deleted (D-9).** The site generates `/llms.txt` with the version stance (`site/src/pages/llms.txt.ts`), and the smoketest probes it. The test that kept the hand copy's stance equal to `LLMS_STANCE` now asserts the hand copy is absent. `docs/docfx.json` no longer lists it as a resource. Two archived pages still link to it; their bodies are immutable, so `site/link-debt.json` prices both links (`relative-links` gate, burn-down #7489).
- **What a revert restores (D-13 step 4).** Reverting the cutover pull request brings back, in `docs-pages.yml`:
  - the DocFX `build` job and its `deploy`;
  - the dispatch-only canary jobs and their `canary` input;
  - the DocFX-era push path filter and the workflow-level `pages: write` and `id-token: write`;
  - `actions/configure-pages` on the floating `@v6` tag instead of its commit pin.

  It reverts the comment-only updates in `ci-router.yml`, `docs-site-build.yml` and `tests/ci/test_docs_site_job.py` that describe the cutover.

  It also brings back `docs/llms.txt` with its `docs/docfx.json` resource entry (and drops the two `site/link-debt.json` entries for it), and the tests that pinned the DocFX deploy (`tests/release/test_release_ci_ownership.py`, `tests/ci/test_nightly_tooling_cache.py`, `tests/docs/test_docs_seo.py`, `tests/docs/test_dockitty_contract.py`). The revert's own push to `main` then deploys DocFX. It does not touch the doc-kitty build gate (`docs-site`). The rollback works until #6943, as D-13 says.
- **Done when (#6938).** The first post-merge deploy is green and its smoketest passes on `docs.spec-kitty.ai`. Both can only be shown after the merge, so they are followed up on #6938.

## Amendment 2026-11-12 (DocFX retired)

Recorded with #6943. D-6's, D-13's and D-14's text above is unchanged. This section records how D-13 step 5 is carried out.

- **The release gate is waived (operator decision, 2026-11-12).** D-13 step 5 waits for one Spec Kitty release shipped with the doc-kitty site live. The last release, v4.0.0rc8, predates the cutover, so the gate is waived. The evidence that stands in for it:
  - the production canary, run [43027580608](https://github.com/spec-kitty/spec-kitty/actions/runs/43027580608), report on [#6938](https://github.com/spec-kitty/spec-kitty/issues/6938#issuecomment-6796965517);
  - the post-cutover runs of `docs-pages.yml` on `main`, green on every completed run since the merge of #7558 in all four jobs (`pages`, `build`, `deploy`, `smoketest`), for example run [43265541140](https://github.com/spec-kitty/spec-kitty/actions/runs/43265541140).
- **What was removed.**
  - The DocFX sources: `docs/docfx.json`, the eight `toc.yml` files, `docs/templates/` (with `main.js`, `main.css` and its hub page, whose route was never in the URL baseline), and the static resources `docs/docfx.json` copied (`docs/CNAME`, `docs/robots.txt`, `docs/.nojekyll`) with the DocFX build-output `docs/.gitignore`. `site/public/` carries the site's own `CNAME` and `robots.txt`, and `templates` left `docs/_meta/sections.yaml`.
  - The D-6 "drop" scripts: `plantuml_render.py`, `plantuml_invoke.py`, `plantuml_pins.json` and `generate_kitty_specs_docs.py`. Its `slugify`, which `docs_index.py` imported, moved into `docs_index.py`.
  - The D-6 "port" scripts whose port is done, removed in this step rather than in their porting steps because their only runner was the DocFX build: `redirect_stub_generator.py` with `redirect_map.yaml` and `redirect_baseline_urls.json` (ported to `site_redirects.py`, #6933; `rename_reconcile.py` now cross-checks `site/legacy-redirects.json`, and `moves_ledger.derive_redirect_map` and `validate` went too); `seo_postprocess.py` and `seo_verify.py` (Starlight emits the tags and `site_built_check_render.py` proves them); `description_length_check.py` and `_published_pages.py` (the published set is `published_pages()` in `_dockitty_contract.py`, and `dockitty-validate-frontmatter` enforces the description band). `capture_baseline_urls.py` ran its one run.
  - `glossary_linker.py` and `glossary_page/`, ahead of D-6's "port (after #3024)". They post-processed DocFX's rendered HTML and imported the dropped generator, and nothing has run them since the cutover. The port to doc-kitty's Contextive glossary and auto-link (D-10) reuses no Python, and #6940 still tracks the glossary page and the auto-link; #3024 is still open. The glossary source `.kittify/glossaries/spec_kitty_core.yaml` stays.
  - The tests of the removed modules. The tests that guarded a still-live rule read the contract now: the published-page title and description rule (`tests/docs/test_docs_seo.py`) and the guard that `docs/reports/` is never published (`tests/_support/reports_unpublished_guard.py`, used by the three terminology tests).
  - The PlantUML-jar steps of the router's `tests (docs)` job.
- **What stays.** The D-6 "keep" scripts and the migration-era tools (`frontmatter_backfill.py`, `adr_converter.py`, `dockitty_frontmatter_migration.py`, `bulk_ref_rewrite.py`, `rename_reconcile.py`, `touched_set_gates.py`) keep their D-6 verdicts. The ported frontmatter readers `audience_resolver.py`, `related_validator.py` and `relative_link_fixer.py` read no DocFX file and keep running.
- **Gates.** `tests/docs/test_legacy_docsite_retired.py` keeps the DocFX sources and modules absent and fails on an import of a removed module. `tests/architectural/test_legacy_docsite_named_nowhere.py` fails on any tracked living file that names DocFX; it excludes only immutable history (dated ADRs, `docs/changelog/`, `CHANGELOG.md`, `docs/plans/`, `docs/reports/`, `docs/archive/`, `kitty-specs/`, the append-only `kitty-ops/` and `.kittify/` records, the #4562 bulk-edit record and a dated timeline page) and two generated files.
- **Rollback posture.** D-13 step 4's rollback, "revert the cutover pull request", no longer works on its own. Going back to DocFX now needs a revert of the #6943 pull request and of #7558. Rolling forward is preferred.
- **D-13 is complete apart from the README rename (#6939, D-1),** which follows in its own pull requests with the content pass (#3891). The D-14 shim list is unchanged.

## Amendment 2026-11-12 (section indexes renamed)

Recorded with #6939. D-1's, D-5's, D-7's and D-13's text above is unchanged. This section records how D-1's index-file sequencing and D-13 step 5's README rename are carried out.

- **59 files, not 60.** Every `docs/**/index.md` is now `README.md`, moved with `git mv`. D-1 counted 60; `docs/templates/index.md` left with the DocFX template in #6943. The 4 folders #6928 resolved (`adr/1.x`, `adr/2.x`, `adr/3.x`, `architecture`) are among the 59.
- **`indexBasename` is `'README'` only.** `INDEX_BASENAMES` in `scripts/docs/_dockitty_contract.py` is `("README",)`, and the generated `site/dockitty-contract.json` follows. `tests/docs/test_section_index_basename.py` fails on any `index.md` under `docs/`, with a planted control that proves the walk reports one.
- **The moves ledger records each rename.** `site/moves.yaml` gains one entry per folder, `/x/index.html -> /x/README.html` (ref `#6939`). Eight folders had moved `README.md -> index.md` before (#3914, #6928), so their new entry points back at a route with an older move away. The ledger stays append-only and now reads a later entry into a route as superseding that route's earlier move away: the route is live again (`moves_ledger.collapse`). A route that moves to itself is still refused as a cycle, and a return to a route with no page is still refused by the redirect generator.
- **Links.** Every link to a renamed page was rewritten from the ledger's own `#6939` pairs (`moves_ledger.source_pairs`): the `index.md` segment of a link target that resolves to a renamed page became `README.md`, and nothing else in the target changed. Living pages also had exact path mentions rewritten. In immutable files (dated ADRs, `plans/`, `reports/`, `changelog/`, `archive/`) only link targets changed, the one body change D-7 allows; a check that re-applies the rewrite to each such file's previous body and compares the result with the new body found no other change. Prose and frontmatter that name an old path are history and stay. `site/link-debt.json` follows the two rewritten targets it prices.
- **Redirects.** `site/legacy-redirects.json` is byte-identical. A legacy `dir/index.html` or `dir/README.html` URL folds to `dir/` by the legacy site's own file names, whatever `INDEX_BASENAMES` holds, and D-5 rule 3 excuses a `dir/index.html` that ends at its own live directory page when it is unmoved or its collapsed move is an index rename; any other move of it that lands on `dir/`, for example through a hub fallback, is still refused. An index rename keeps its directory URL, so it needs no baseline entry and no redirect key (`moves_ledger.is_index_rename`, read by the ledger tests and by `rename_reconcile.py`). The directory build still writes each section page to `dist/<dir>/index.html`.
- **Readers.** `freshen_adr_inventory.py` writes the era table to `README.md`. It still reads a lone `index.md` but never writes one: adding or pruning a row there refuses with "era index not found". `check_generated_docs_untouched.py` matches ADR era table rows per era folder, so a table that moves between the landing files of one era adds no row. `dockitty_frontmatter_migration.py` no longer skips the 4 #6928 folders' `README.md`, which is their section index again, and `site_built_check.py` resolves a folder's metadata route through `README.md`.
- **A known gap upstream.** The built-in pack's docs lint (`packs/built-in/assets/docs_structural_lint.py`, sourced from spec-kitty-open-packs) still reads a section's landing page as `index.md`. Its `check_index_completeness` skips a section without one, so the curated-complete check on `docs/architecture/` does not run until the asset reads `README.md`. Packs are not edited here; the fix belongs upstream.
- **Generated surfaces.** The retrieval index and the page inventory are not edited in the pull request; the post-merge `ci/regen-docs-index` bot regenerates them on the new paths.
- **D-1 and D-13 are complete.**
