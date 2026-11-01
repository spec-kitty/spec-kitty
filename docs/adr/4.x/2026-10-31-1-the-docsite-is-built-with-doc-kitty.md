---
title: 'ADR: the docsite is built with doc-kitty, consumed as a pinned git dependency, at directory URLs with every legacy URL redirected'
description: 'doc-kitty replaces DocFX for docs.spec-kitty.ai: a site/ sub-project reads ../docs, pins doc-kitty by commit, deploys at the domain root and redirects every legacy URL.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-10-31'
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
