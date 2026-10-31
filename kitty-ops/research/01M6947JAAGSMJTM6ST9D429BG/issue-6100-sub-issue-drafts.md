# Sub-issues of epic #6100 (docsite: DocFX → doc-kitty)

Written by Op `01M6947JAAGSMJTM6ST9D429BG` for the operator to file. They follow [ADR 2026-10-31-1](../../../docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md); "D-n" refers to its decisions, and "result N" to the spike-evidence results table.

**Filed 2026-10-31** as sub-issues of #6100; each heading carries its issue number. #2358, #3914, #2361 and #2362 were re-parented under #6100.

**Provenance.** This run received the operator's rulings but not the research squad's 17-step plan itself. The sequence below is rebuilt from the rulings, the ADR and the spike, with the adjustments the brief named:
- README rename PRs;
- directory URLs plus the full redirect layer;
- dashboards dropped;
- #2358, #3914, #2361 and #2362 under #6100;
- #648 not a child.

Compare it with the squad's 17 steps before filing.

**What the spike changed** (results 13 to 16, from a build of the real `docs/` tree):
- **The README rename moves after DocFX retirement**, not just after cutover. DocFX publishes a section only from `index.md`, and reverting the cutover must still give a whole DocFX site.
- **Today's frontmatter blocks the build itself**, not only the validator. That is a new step, #6929, before the scaffold's job can go green.
- **The redirect generator works on the real baseline** (831/831 covered).

Sizes: S ≤ ½ day, M ≈ 1–3 days, L > 3 days.

## Order at a glance

```text
ADR (#6925)
 ├─ #6926 sdist README include (pre-existing)
 ├─ #6927 ledgers (#2358) + #3914 ──► #6928 dual-index folders
 ├─ #6929 build-blocking frontmatter migration
 │
 └─► #6930 site scaffold + docs-site job (parallel run)   ◄── #6926, #6927, #6928, #6929
       ├─ #6931 frontmatter contract completion
       ├─ #6932 publication rules
       ├─ #6933 redirect layer
       ├─ #6934 llms.txt
       ├─ #6935 render parity (SEO, alerts)
       ├─ #6936 diagrams (self-hosted PlantUML, build mode)
       ▼
     #6937 gate required (router) → #6938 canary + cutover (+ #2361)
       ├─ #2362 nightly crawl
       ├─ #6940 glossary         ◄── #3024
       ├─ #6941 mission pages    ◄── doc-kitty (g)
       ├─ #6942 ADR index        ◄── doc-kitty (a)
       └─ #6943 DocFX retirement (one release after cutover)
            └─ #6939 README rename (60)   ◄── #6926
```

---

## Existing issues to re-parent under #6100 (operator decision 7)

| Issue | Role in #6100 | Done-when to add |
| --- | --- | --- |
| #2358 | Becomes #6927 (standing moves ledger + living baseline). | The ledger home is `site/moves.yaml` and `site/url-baseline.txt` (ADR D-5). |
| #3914 | Folded into #6927: the 124 historical missing redirects are reconciled while the ledger is seeded. | `rename_reconcile.py --strict` reports 0 `occurrence_subset_redirect` violations, or each remaining one carries a recorded baseline amendment. |
| #2361 | Post-deploy smoketest; lands with cutover (#6938). | Probes the new site after each deploy: one `.html` redirect key, one chain, one live `dir/index.html`, one orphan `dir/index.html` key, one `dir/README.html`, one unpublished page's URL (expects its hub). |
| #2362 | Nightly crawl of the new site after cutover. | Crawls the doc-kitty build (`dockitty-assert-no-broken-links`) and the live site; files a deduplicated alert issue. |

Not children: #3891 (separate epic; its description needs refreshing, since the Zeitgeist claim is stale after #6164); #648 (standalone); #2302 (written after cutover, in `spec-kitty-open-packs`).

---

## #6926 · Anchor the sdist `README.md` include to the repository root (pre-existing defect)

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-12; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** S · **Depends on:** — · **Blocks:** #6930, #6939

The sdist's bare `README.md` include in `pyproject.toml` is gitignore-style, so it matches every nested `README.md`. A `uv build --sdist` at 2026-10-31 ships 31 `docs/**/README.md` and 676 `kitty-specs/**/README.md` files, plus others under `scripts/` and `tests/`. The README rename (#6939) would add 56 more, net, and `site/README.md` would ship as well.

**Done when:**
- The include is anchored (`/README.md`) or the stray trees are excluded, and `site/**` is excluded.
- `tests/cross_cutting/packaging/test_packaging_safety.py` asserts, on the built archive, that no `docs/`, `kitty-specs/` or `site/` file ships.
- The test fails on the current `pyproject.toml` (red first).

---

## #6927 · Standing URL baseline and moves ledgers (absorbs #2358, folds #3914)

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-5; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M · **Depends on:** #6925 (ADR) · **Blocks:** #6928, #6930, #6933

**Do:**
- Seed `site/url-baseline.txt` from a site walk of the last DocFX build (`capture_baseline_urls.py --site-dir docs/_site`, run in CI) unioned with every key of `scripts/docs/redirect_map.yaml`. The derive-from-source count is 831.
- Create `site/moves.yaml` (append-only `old route -> new route`) from the current redirect map and occurrence-map moves. Record the amendment provenance of `redirect_baseline_urls.json` in the new ledger's header.
- Repoint `redirect_stub_generator.py regenerate-map` at `site/moves.yaml`, so DocFX's `redirect_map.yaml` is derived from the standing ledger during the parallel run.
- Reconcile #3914's 124 missing redirects.

**Done when:**
- Both ledgers are committed, with a provenance header.
- A test asserts that every URL of the old manifest and every redirect-map key is in the new baseline.
- #3914's strict reconcile is clean or amended.
- No script reads a mission-scoped occurrence map.

---

## #6928 · Resolve the 4 folders holding both `index.md` and `README.md`

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-1, D-7; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** S · **Depends on:** #6927 · **Blocks:** #6930

doc-kitty refuses a build with both index files in one folder (`[dk-routes] 4 route collision(s)`, result 13).

**Do:**
- Delete the three ADR-era `README.md` redirect stubs (`adr/1.x`, `adr/2.x`, `adr/3.x`).
- Fold `architecture/README.md` (a 131-line landing page) into `architecture/index.md`.
- Add `site/moves.yaml` entries for `adr/<era>/README.html` and `architecture/README.html`, then regenerate `redirect_map.yaml`, which is what DocFX reads, so those URLs keep resolving on the live DocFX site.

**Done when:** each of the 4 folders has exactly one index file, the DocFX redirect-coverage step stays green, and `docs_index.py --write` and the page inventory are regenerated.

---

## #6929 · Build-blocking frontmatter migration

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-7, D-8; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** L · **Depends on:** #6925 (ADR) · **Blocks:** #6930

The real `docs/` tree does not build on doc-kitty until four frontmatter classes are fixed (result 14). Each must land with the `scripts/docs` readers of that field ported in the same PR, so DocFX and `spec-kitty docs query` keep working.

**Do:**
1. `audience`: path string to `[{ profile: internal/maintainer, guidance_text: … }]` (341 pages). Port `audience_resolver.py`, `docs_index.py` and every other reader. Check nested persona slugs (doc-kitty draft (d)).
2. Excluded trees (archive, reports, convergence): add the build-schema minimum, `title` and `description`, to the 31 pages missing either (frontmatter only).
3. `related`: repository paths to doc-kitty slugs (411 pages). Move the 32 references outside `docs/` to `external_references`. Port `related_validator.py`.
4. ADRs: add `doc_status` (`Accepted` and `Proposed` → `active`, `Superseded` → `superseded`; 226 files), and `kind: ADR`.
5. A published page's `related` may not name a draft or excluded page; that is build-fatal (181 references in the spike). Move each into the body as an ordinary link, or drop it.

**Done when:**
- A one-off doc-kitty build of `docs/` (the spike's commands) passes with `indexBasename: ['README', 'index']` and the exclusion shim.
- A test hashes the body of every ADR, plan, report and changelog file before and after and finds no difference.
- `tests/docs/` passes, and DocFX still builds.

---

## #6930 · Site scaffold, pinned doc-kitty and the pull-request build job (parallel run starts)

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-1, D-2, D-8, D-11; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M · **Depends on:** #6926, #6927, #6928, #6929 · **Blocks:** #6931 to #6938

**Do:**
- Add `site/` (D-1):
  - `package.json` pinning `@spec-kitty/doc-toolkit` as `github:spec-kitty/doc-kitty#<sha>&path:/src` (D-2), and `pnpm-lock.yaml`;
  - `astro.config.mjs` with `site: https://docs.spec-kitty.ai`, `base: '/'`, `docsDir: '../docs'`, `indexBasename: ['README', 'index']`;
  - `.env.production` with `DK_PUBLISH_DRAFTS=off` (D-8);
  - `src/content.config.ts` with the section-exclusion shim (D-8);
  - `public/` (`CNAME`, `robots.txt`), and the `404` page with the `/kitty-specs/` notice.
- Add `docs/_meta/sections.yaml`.
- Add `make docs-site` (install and build) and `make docs-site-bump REF=<tag>` (D-2 steps 1 and 2, including the peer ranges).
- Add a `docs-site` job to `ci-router.yml`, behind a `docs/**` + `site/**` path filter registered in `gate_selection.py`. It builds and uploads `site/dist` as an artifact, and every `dockitty-*` call passes `--astro-config astro.config.mjs` (D-1). It is not yet in `router-gate`'s `needs:` (#6937). DocFX still deploys.

**Done when:**
- The job builds the full published corpus (about 637 pages in the spike) on a pull request.
- The fork guard (`tests/ci/test_fork_guard.py`) and the router tests cover the job.
- `site/**` is excluded from the sdist (#6926).
- `pnpm install --frozen-lockfile` passes in CI with no token.

---

## #6931 · Frontmatter contract completion (immutable bodies)

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-7; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M/L (two or three PRs) · **Depends on:** #6930 · **Blocks:** #6937

**Do:** the rest of the D-7 mapping:
- `kind` from `type`, or `Hub` for indexes;
- `doc_status` normalisation (`closeout` and `point_in_time` → `durable`, `proposal` → `draft`);
- `updated` as an instant (ADRs from `date`).

Delete `description_length_check.py` and the other checks once `dockitty-validate-frontmatter` covers them (D-6).

**Done when:**
- `dockitty-validate-frontmatter --astro-config site/astro.config.mjs`, over the published sections, reports zero errors.
- The body-hash test from #6929 still passes.
- `spec-kitty docs query` still answers, with its index regenerated.

---

## #6932 · Publication rules: sections, drafts and exclusions

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-8; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** S/M · **Depends on:** #6930 · **Blocks:** #6933, #6937

**Do:**
- Register `development` as its own section and `plans` with restricted `feeds` (no `llms`, `agent` or `rss`).
- Mark `plans/engineering-notes/`, `plans/investigations/` and `plans/research/` as `doc_status: draft`. 34 of their URLs are in the baseline.
- List `archive/`, `reports/`, `convergence/` and an inventoried set of retired hosted and sync pages in the exclusion shim. The inventory is part of this issue, starting from the pages that name zeitgeist, teamspace, the sync daemon or the offline queue.
- Scope the `dockitty-validate-frontmatter` and `dockitty-check-links` runs to the published sections.

**Done when:** no excluded or draft page appears in the build output, hubs, sitemap, `llms.txt`, OKF export or search; a test asserts this on the artifact.

---

## #6933 · Redirect layer: directory URLs and every legacy `*.html` URL

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-5; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M · **Depends on:** #6927, #6930, #6932 · **Blocks:** #6937, #6938

**Do:** a generator (seeded from the spike's `genredirects.py`) that writes `site/redirects.json` from `url-baseline.txt` and `moves.yaml`, with the D-5 rules:
1. `X.html` → `X/`; `dir/README.html` → `dir/`; moved pages → their final route, with chains collapsed.
2. No key for a `dir/index.html` whose section is live (42 today); the 11 orphan `dir/index.html` keys are declared.
3. A baseline URL whose page is unpublished redirects to its section hub (36 today).
4. The gate-only `--redirects` override covers live `dir/index.html` until doc-kitty (b) lands.

Add to the `docs-site` job: `redirects.json` equals its generated form; the coverage gate runs **twice**, with `--docs --declared-redirects` and without `--docs`, so nothing is excused.

**Done when:**
- The job reports 831/831 (or the ledger's current count) covered in both runs.
- Mutant tests prove the gate fails on a dead target, a missing key and a draft-excused URL.

---

## #6934 · Generated `llms.txt` with the version stance

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-9; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** S · **Depends on:** #6930, #6932

**Do:** mount `llmsTxtRoute` in `site/src/pages/llms.txt.ts`, with the thin wrapper that inserts the version-stance block (D-9) until doc-kitty (h) lands.

**Done when:** the built `llms.txt` carries the stance block and only `feeds: llms` sections; `docs/llms.txt` is scheduled for deletion at cutover (#6938).

---

## #6935 · Render parity: SEO metadata and GitHub alerts

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-6, D-11; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** S/M · **Depends on:** #6930

**Do:**
- Confirm Starlight emits description, self-canonical and Open Graph tags on every page, replacing what `seo_postprocess.py` and `seo_verify.py` provided.
- Either rewrite the 7 GitHub-alert files to `:::note` asides, or record that they wait on doc-kitty (c).
- File any missing check upstream.

**Done when:** a parity checklist against the DocFX output is green, or each gap is filed upstream with an owner.

---

## #6936 · Diagrams: PlantUML and Mermaid through doc-kitty's build-time render

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-11 (Diagrams); operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** S/M · **Depends on:** #6930

**Do (ADR D-11, "Diagrams"):**
- Set `diagrams: true` and `DK_DIAGRAM_BUILD_RENDER=build`, and install a pinned Playwright Chromium in the job. Without these, the mode follows whether Chromium happens to be present, and PlantUML stays as code in client mode.
- Add a job-level `services:` container for `plantuml/plantuml-server`, pinned by digest, mapped to `localhost:8091`, with a readiness wait. Set `DK_PLANTUML_SERVER_URL=http://localhost:8091/svg/`. This is doc-kitty's own CI pattern.
- Run doc-kitty's `plantuml-guard` check through `assert-build-artifacts.mjs` or a thin wrapper, since it has no `dockitty-*` binary.
- Handle remote `!include` in diagram sources, the one remaining egress path: restrict it in the server's configuration, or refuse it with a source check.

**Done when:** every current diagram (18 Mermaid, 5 PlantUML sources) renders as a static SVG in `site/dist`, the `plantuml-guard` check is green, and the image is digest-pinned. `plantuml_render.py`, `plantuml_invoke.py`, `plantuml_pins.json` and their tests are deleted in #6943.

---

## #6937 · Make the `docs-site` gate required

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-11, D-12; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** S · **Depends on:** #6931, #6932, #6933 (and #6934, #6935, #6936 for content)

**Done when:**
- The `docs-site` job is green on `main` and is in `router-gate`'s `needs:` in `ci-router.yml`, with no `continue-on-error`. It cannot join `ci-aggregate.yml`'s `aggregate-gate`, which runs on `workflow_run`.
- The router tests (for example `tests/ci/test_docs_lint_job.py`) pin the wiring.
- The deploy workflow and the job share one build definition (D-11).
- `tests/release/test_release_ci_ownership.py` still pins the Pages probe and the `main`-only deploy (D-12).

---

## #6938 · Canary deploy and cutover (with #2361)

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-13; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M · **Depends on:** #6937, #6933

**Do:**
- **Canary.** This is a short production window on `docs.spec-kitty.ai`, because the deploy job may only publish from `main` in the core repository. Announce it, and freeze docs merges to `main` while it runs: a push would queue a DocFX deploy in the `pages` concurrency group. A dispatched run deploys the doc-kitty artifact, probes over HTTP each URL class #2361 lists, then redeploys DocFX. This closes the UNVERIFIED GitHub Pages leg of D-5.
- **Cutover.** Switch the deploy artifact to `site/dist`, delete `docs/llms.txt`, and land #2361's post-deploy smoketest in the same workflow.

**Done when:** the canary probes pass on the real Pages service, the cutover deploy is green, and the smoketest passes after it.

**Rollback:** revert the cutover PR. This works until #6943, because the README rename (#6939) waits for retirement.

---

## #6939 · Rename the 60 `index.md` section indexes to `README.md`

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-1, D-7; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M (one PR per top-level section is fine; the operator's decision 11 lets open PRs resolve their own conflicts) · **Depends on:** #6943, #6926

The rename waits for DocFX retirement. Before then, reverting the cutover would redeploy a DocFX site whose renamed sections return 404.

**Do:**
- `git mv` each of the 60 `index.md` files (the 56 rename-only folders plus the 4 resolved in #6928) to `README.md`.
- Rewrite links through `site/moves.yaml`. In the 43 immutable files that link to an `index.md`, this is the one body change D-7 allows, and the body-hash test normalises link targets before comparing.
- Regenerate the docs-query index and page inventory, and update `freshen_adr_inventory.py` and every `scripts/docs` reader that names `index.md`.
- Narrow `indexBasename` to `'README'`.

**Done when:**
- No `index.md` remains under `docs/` (a test asserts it).
- `dockitty-check-links --strict` is clean.
- Every baseline URL is still covered. `dir/index.html` stays live because the build output is unchanged.

---

## #6940 · Glossary on doc-kitty (after #3024)

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-10; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M · **Depends on:** #3024, #6938

**Do:**
- Generate `site/.contextive/definitions.yaml` (not committed) from the source #3024 settles (D-10), and turn on doc-kitty's glossary and auto-link.
- The integration writes generated term pages into `docs/glossary/`: gitignore that folder and exclude it from `docs_index.py` and the page inventory until doc-kitty (e) adds an output path.
- Retire `glossary_linker.py` and `glossary_page/`.

**Done when:** the glossary page and term links render, and the generation is deterministic and checked in CI.

---

## #6941 · Mission and glossary pages as card-grid hubs (after doc-kitty (g))

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-14 (gap g); operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M · **Depends on:** doc-kitty (g), #6940 for the glossary half

**Do:** bring mission pages back as hub card grids generated from `kitty-specs/`, replacing the dropped dashboards. Decide whether the old `/kitty-specs/**` URLs redirect to them.

**Done when:** mission pages render as card grids in the site-chrome design system, and the `404` notice for `/kitty-specs/` is replaced by redirects where a page exists.

---

## #6942 · ADR index from doc-kitty (after doc-kitty (a))

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-14 (gap a); operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** S · **Depends on:** doc-kitty (a)

**Do:** switch the ADR index pages to doc-kitty's generated index, and retire the era index tables and the index-writing half of `freshen_adr_inventory.py` (operator decision 6).

**Done when:** every ADR appears once with the right date, status and era, and `--check` runs in the `docs-site` job.

---

## #6943 · Retire DocFX (one release after cutover)

Part of spec-kitty/spec-kitty#6100. Implements [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) D-6, D-13; operator decisions: [#6100 comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324).

**Size:** M · **Depends on:** #6938, plus one Spec Kitty release shipped with the doc-kitty site live · **Blocks:** #6939

**Do:**
- Remove `docs/docfx.json`, every `toc.yml`, `docs/templates/spec-kitty/` (including `main.js`) and the .NET steps.
- Remove the scripts marked "drop" in ADR D-6 and their tests, including `plantuml_render.py`, `plantuml_invoke.py` and `plantuml_pins.json` (#6936).
- Update or delete the 26 Python files that read `docfx.json` or `toc.yml`: most under `tests/docs/`, plus `tests/_support/docfx_reports_guard.py` and the terminology scope helper.
- Remove `redirect_map.yaml` and `redirect_baseline_urls.json`, which are superseded by the #6927 ledgers.

**Done when:** no DocFX reference remains (`grep -ri docfx` is clean outside ADRs and the changelog), CI is green, and no `scripts/docs` test imports a deleted module.
