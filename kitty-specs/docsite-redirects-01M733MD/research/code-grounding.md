# Grounding for #6933: the docsite redirect layer

Worktree `/home/user/spec-kitty-6933`, branch `issue-6933-docsite-redirects` at `87fd7af8`. doc-kitty is pinned at `5acb83c` (doc-toolkit 0.7.0).

This was read-only research. One experiment ran for real: the full site was built with a generated `legacyHtmlRedirects` map, using a temporary config whose `outDir` and `publicDir` pointed into the scratchpad. The config was deleted afterwards, and `git status` is clean. Every number marked **(measured)** comes from that build or from `scratchpad/g6933/classify.py`. The scratch outputs are in `scratchpad/g6933/`: `map.json`, `site/legacy-redirects.json`, `build.log`, `cov1.log`, `cov2.log`, `sbc.log` and `bl.log`.

## Key findings

1. **Gap (b) is closed in v0.7.0, so no interim override is needed.** The gate maps `/a/index.html` to the file `<dist>/a/index.html`, the same file as `/a/` (`check-redirect-coverage.mjs:167-176`).
   - All 41 live `dir/index.html` URLs were covered with no key and no `--redirects` override **(measured)**.
   - D-5's "Gate gap and interim" paragraph and the D-14 "gate override" shim can be retired.
2. **Astro `redirects` carries nothing today.** All 970 baseline URLs end in `.html` **(measured)**, so the whole layer is `legacyHtmlRedirects`.
   - An old section URL such as `/1x/` is covered for free. The flat stub at `dist/1x/index.html`, written for the key `/1x/index.html`, is also the file the host serves for `/1x/`.
3. **Both gate runs report 970/970** **(measured)**: `--docs ../docs --astro-config astro.config.mjs --declared-redirects <map>`, and `--astro-config astro.config.mjs` alone. The map has 927 keys (929 if the two `/assets/*.html` URLs are sent to their hub instead), and the build wrote 927 stubs.
4. **All three mutants behave as the issue's Done-when needs** **(measured)**:
   - **Dead target:** both runs exit 1.
   - **Missing key:** both runs exit 1.
   - **Draft-excused URL:** the run with `--docs` exits **0** ("1 unpublished") and the run without `--docs` exits **1**. This proves the second run is needed.
5. **The blocker: `site_built_check` fails on stubs.** It reports **4091** findings: 4083 on the `render` surface and 8 on the `page` surface. Each stub lacks `og:*` and a meta description and has a canonical that is not its own URL. The `page` surface flags the 8 stubs sitting at unpublished directory routes, such as `plans/research/index.html`. The check needs a redirect-stub exemption.
6. **No #7489 link-debt entry resolves.** The built-links run gave 98 problems, all 98 priced, 0 stale **(measured)**.
   - The broken links are unrewritten `.md` and source-file hrefs, such as `../architecture/team-kitty-saas.md`. Each resolves to a path that never existed as a URL, so no redirect can serve it.
   - `assert-no-broken-links` checks only that a file exists (`assert-no-broken-links.mjs:20-36`). It never follows a stub to its target.
7. **The `.html` key guard (#253) is fatal on static output.**
   - Any Astro `redirects` key ending in `.html` throws (`lib/legacy-html-redirects.mjs:219-241`, called at `lib/integrations/legacy-html-redirects.ts:55-65`).
   - A legacy source that collides with an existing file throws at `astro:build:done`. Seen live: copying the two `/assets/*.html` files into `public/` while they were also map keys broke the build.

## 1. Current state

### `site/moves.yaml`

- **Format:** header comment, then `kind: docs-moves-ledger`, `version: 1`, `moves:` as a list of flow maps `{from, to, ref, note?}` (`site/moves.yaml:37-39`). Routes are in legacy DocFX form (`/x.html`, `/dir/index.html`).
- **Entries:** 312, every `from` unique, 25 with a `note`.
  - (a) l.40+ is 163 entries carried from `redirect_map.yaml`.
  - (b) and (c) are #3914 follow-ups.
  - l.343-347 are the #6928 dual-index rows (`/adr/1.x/README.html -> /adr/1.x/index.html`, …).
  - l.348-359 are the 10 archived retired pages, each pointing to its section hub as `/x/index.html` (#6932).
- **Chains:** 16 entries point at another entry's `from`. The longest chain has one extra hop **(measured)**.
- **Rule 4 cannot live in the moves ledger yet.** DocFX still publishes draft pages, so a moves row `draft.html -> hub` would trip `validate()`, which rejects a source that is a published page (`moves_ledger.py:155-172`, used by `check-map`). Rule 4 therefore belongs in the generator, reading `unpublished_routes()`, until DocFX retires in #6943.

### `site/url-baseline.txt`

- 970 routes. The issue still says 831.
- Every route ends in `.html`: 62 are `…/index.html` and 23 are `…/README.html` **(measured)**.
- Header l.6-11 records the seeding: 672 DocFX pages plus 298 map keys.

### Reusable Python (single authority; reuse, don't duplicate)

| API | Where | Use for #6933 |
|---|---|---|
| `load_moves`, `collapse` (cycle refusal, chain collapse) | `scripts/docs/moves_ledger.py:107,131-146` | Rule 2. Collapse first, then map the final legacy route to its directory route. |
| `load_baseline` | `moves_ledger.py:175-188` | Baseline reader. |
| `route_to_source` / `source_to_route` | `moves_ledger.py:191-202` | `.html` ↔ `docs/*.md`. It does **not** fold `README`/`index`, so the generator needs a `legacy_route -> directory route` helper. Best placed beside `slug_of`. |
| `slug_of`, `route_of`, `page_for_slug`, `unpublished_routes()`, `EXCLUDED_FOLDERS`, `DRAFT_FOLDERS`, `INDEX_BASENAMES` | `scripts/docs/_dockitty_contract.py:163-246, 80-104` | The live set is the `route_of` of every `docs/**/*.md` minus `unpublished_routes()`. Rule 4's hub is the nearest live ancestor route. |
| `validate`, `derive_redirect_map`, `check-map`, `regenerate-map` | `moves_ledger.py:149-172`, `redirect_stub_generator.py:299-334` | DocFX side. These stay untouched until #6943, together with `redirect_map.yaml` and the `docs-pages.yml` l.191-204 steps. |
| `site_contract.py` render, write and `--check` pattern | `scripts/docs/site_contract.py:33-80` | The template for the "generated equals committed" step: bare `python3`, `PYTHONPATH=.:src`. `moves_ledger` needs PyYAML, which the runner's system `python3` already has; `docs-pages.yml` relies on it. |

### `site/astro.config.mjs`

- l.12-13: "Not wired here yet: redirects (#6933 …) and diagrams (#6936)".
- It reads `dockitty-contract.json` (l.17) and passes `exclude` and `indexBasename`. It sets no `redirects` and no `legacyHtmlRedirects`.

### `.github/workflows/docs-site-build.yml`

- The build is at l.68-70, `site_built_check` at l.71-75, and the built-links gate at l.76-80.
- There is no redirect step. The coverage gate never runs anywhere today.

### `Makefile:45-52`

- The `docs-site` target mirrors the workflow, also with no redirect step. Its comment at l.44 states the `--astro-config` rule.

## 2. What doc-kitty v0.7.0 offers

Paths are under `site/node_modules/@spec-kitty/doc-toolkit/`.

### `legacyHtmlRedirects` option

- **Declared at** `lib/config.ts:366-379`. Its shape is `Record<string,string>`: base-less `'/old.html': '/new/'`; a target may also be an absolute URL.
- **Wiring:** `lib/config.ts:935-939` wires `legacyHtmlRedirectsIntegration(legacyHtmlRedirects, docsDir, indexBasename)`.
- **Validation** (`lib/legacy-html-redirects.mjs:47-66`). Each source must:
  - start with `/`;
  - end in `.html`;
  - carry no `?` or `#`, no empty, `.` or `..` segment, and no backslash.

  **A `$comment` key would fail validation, so the JSON map must be a flat object with no header key.**
- **Chains and loops** (l.78-91): chains inside the map are flattened, and a loop throws.
- **The stub** (l.115-127) is a flat `<dist>/a/b.html` page. It has the title "Redirecting to:", a `0;url=` refresh, `noindex`, a canonical link to the target, and the text "Redirecting from `<code>`…". It is written in `astro:build:done`, so it never appears in the sitemap, `llms.txt` or the agent API.
- **The writer** (l.152-184):
  - A key `/x/index.html` whose `/x/` is a live page **and** whose target is `/x/` is reported as `servedByPage`. That form is optional and harmless.
  - **Any other existing file or folder at a source path is fatal.** That covers a page, a `public/` asset and an Astro directory stub.
- **Drafts** (`lib/integrations/legacy-html-redirects.ts:83-100`): with `DK_PUBLISH_DRAFTS` off, an entry whose target is a draft is **withheld with a warning, not failed**. The old URL then 404s. Only the gate run without `--docs` catches this (mutant 3).
- **Dev server** (l.69-81): `astro dev` answers a legacy URL with a 302.

### Astro `redirects`

- doc-kitty does not pass Astro's `redirects` through; it is Astro's own top-level `defineConfig({ redirects })`.
- `refuseAstroHtmlRedirects` (l.219-241) throws on any `.html` key when `output` is `static` and `build.redirects` is not off. That is #253 / ADR-0071 in force.
- `lib/draft-publication.mjs:470-505` (`redirectsToDrafts`) withholds directory redirects that lead to drafts.

### `dockitty-check-redirect-coverage` (`scripts/check-redirect-coverage.mjs`)

**Usage** (l.5-8): `<baseline> <dist> [--redirects <map>] [--docs <dir> [--index-basename a,b] [--astro-config <p>] [--declared-redirects <map>]…]`, plus `--site-root`, `--mode` and `--env-dir` (`takeSiteFlags`).

**Resolution:**
- A `.html` URL is looked up as a FILE (l.172-177). An Astro directory-form stub never covers it, and the verdict names it (l.185-189, 266-273).
- A chain is followed for at most 10 hops (`MAX_CHAIN_DEPTH`, l.97). A loop is uncovered (l.252-280).

**`--redirects`** is an override map consulted before `dist` (l.226-229). With gap (b) closed it is not needed.

**`--docs` with `--declared-redirects`** (repeatable, l.392-396) excuses a URL as "unpublished" only when all of these hold (l.290-318, 355-367):
- drafts are off;
- the URL has no page **and** no stub;
- the URL itself, or the end of its *declared* chain, is a `doc_status` draft route.

A `.html` URL is only excused through the declared map, because `/x.html/` is never a draft route. "The declared map never makes a URL count as covered" (l.60-61).

**Dead-stub walk:** every stub in `dist`, baselined or not, must reach a live page (l.368-371). It finds both flat `.html` stubs and `index.html` stubs (l.325-342).

**Exit codes:** 0 is OK (l.539-546). 1 is uncovered or dead stubs (l.549-577). 2 is a usage error, a missing file or directory, a config-evaluation refusal, or an `--astro-config` mismatch (l.420-511).

**Observed `--astro-config` mismatch:** with `--docs ../docs`, the gate requires the config that *builds* `../docs`. Passing any other config exits 2 (l.478-492). Use `--astro-config astro.config.mjs` in both runs.

**Draft resolution** reads `site/.env.production` (`DK_PUBLISH_DRAFTS=off`) and prints its source line first.

### `dockitty-generate-legacy-redirects` (`scripts/generate-legacy-redirects.mjs`)

- It exists, as a bin. It applies the mechanical rule plus a `--overrides` JSON (`mechanicalHtmlMap`, `lib/legacy-html-redirects.mjs:255-273`).
- **It maps `/x/README.html` to `/x/README/`, which is wrong for us.** It also knows nothing about unpublished pages.
- So core's Python generator should emit the full map. Upstream's guide (`docs/migrations/legacy-html-urls.md`, at commit `5acb83c`) treats this CLI as optional.

### Does a live `dir/index.html` still need a key?

No. It is covered directly (finding 1), so 41 keys are omitted. Including them would also be accepted (`servedByPage`).

### Where the map lives

- Use a committed flat JSON object, e.g. `site/legacy-redirects.json`.
- Read it in `astro.config.mjs` with `JSON.parse(readFileSync(new URL('./legacy-redirects.json', import.meta.url)))`, as the contract file is read. Pass the same file to `--declared-redirects`.
- **Name it `legacy-redirects.json`, not D-5's `redirects.json`.** It is not Astro's `redirects` map, and that map stays empty. Neither file can carry a `$comment`, so provenance goes in the `astro.config.mjs` comment and the generator docstring.

## 3. D-5 rules → implementation (quotes from `docs/adr/4.x/2026-10-31-1-…md:129-165`)

| D-5 text | Status at v0.7.0 | Implementation step |
|---|---|---|
| "**Redirect declarations.** `site/redirects.json` (Astro's `redirects` map) is generated…" | **Amend.** Astro `.html` keys are fatal. | Generate `site/legacy-redirects.json` and feed `legacyHtmlRedirects`. Astro `redirects` keeps only directory-to-directory moves, of which there are none today. |
| Rule 1: "`X.html` → `X/` … or the page that `moves.yaml` says replaced it. A legacy `dir/README.html` … redirects to `dir/`." | Holds. | `legacy_route_to_dir_route()`: strip `.html`; a last segment of `README` or `index` (case-folded, per `INDEX_BASENAMES`) maps to `dir/`. |
| Rule 2: "Redirect chains are collapsed: every key points at a final, live route." | Holds. | `moves_ledger.collapse()`, then map the final route. Keep a generator check that every target is in the live set. |
| Rule 3: "A legacy `dir/index.html` URL gets **no** declaration **when `dir/` is a live section** … 11 such keys…" | Holds. The keyed count is now 21, not 11. | Omit keys where the URL's own route is live and unmoved. |
| Rule 4: "A baseline URL whose page is unpublished … redirects to the nearest published page, normally its section hub." | Holds. It must be in the generator, not in `moves.yaml`, while DocFX lives. | After rule 1 or 2: if the target is in `unpublished_routes()`, walk up to the nearest live ancestor route. |
| "Gate gap and interim … `--redirects` override …" | **Retire.** Gap (b) is closed upstream. | No override. Amend D-5 and D-14. |
| "Full-corpus spike … 831/831" | Stale. Now 970. | |
| "Fallback (evaluated, not chosen): flat stubs" | **Inverted.** Flat stubs are now the upstream mechanism, and the gate sees them (ADR-0071). | The amendment records this inversion. The D-13 canary still decides the Pages leg, though a flat file removes the 301 hop the spike worried about. |
| "No silent excuse … runs a second time without `--docs`" | Holds and is proven (mutant 3). | Two workflow steps. |

### Baseline classes (970) **(measured)**

| Class | Count | Key → target |
|---|---|---|
| Live, its own page (`X.html` → `X/`) | 562 | yes |
| Live `dir/README.html` → `dir/` | 9 | yes |
| Live `dir/index.html` (incl. `/index.html`) | 41 | **no key** |
| Moved (in `moves.yaml`), final target live | 305 | yes. 21 of these are `index.html` keys of dead sections (`/1x/`, `/archive/…`, `/plans/zeitgeist…`). |
| Moved, final target unpublished → hub | 7 | yes. Example: `/plans/testing/test-change-coupling-caacs.html` → `/plans/`. |
| Unpublished in place → hub | 44 | yes. 38 are in draft folders; 6 are `doc_status` drafts or no-status pages such as `/plans/doctrine/**` and `/development/analysis-report-transactions.html`. All except the last go to `/plans/`; it goes to `/development/`. |
| Dead: no page, not moved | **2** | `/assets/spec-kitty-backlog.html` and `/assets/spec-kitty-evolution-v1-to-v3.html`, standalone HTML that DocFX copied as `resource` (`docs/docfx.json:28-31`). doc-kitty does not publish non-`.md` files from `docs/`. |

- The **excluded-folder** archived pages (the 10 from #6932) are already covered by `moves.yaml` rows pointing to their hubs.
- `/archive/1x/*` rows point to `/changelog/1x/*`.
- `unpublished_routes()` holds 317 routes, and the live set holds 631.

**Operator decision for the two assets:**
- **(a) Recommended:** redirect them to `/assets/`, by a rule-4-style rule for unpublished resources. `docs/assets/index.md:19` already links the backlog file by its GitHub blob URL.
- **(b)** Copy them into `site/public/assets/`, with no key. This was measured to work: both gate runs are green. It duplicates the files, though, and the render surface flags them ("no canonical link", "no meta description").

## 4. Gates and tests touched

- **`tests/ci/test_docs_site_job.py`**
  - l.47-48, 226-243: every line in `ci-router.yml`, `docs-site-build.yml` and `Makefile` that names `dockitty-*` must carry `--astro-config astro.config.mjs` on the **same line**. Both coverage runs therefore stay single-line, with the flag in each.
  - Add assertions that both runs exist, that one has `--docs` and `--declared-redirects` and the other has neither, and that the generator `--check` step runs before the build.
  - l.84-97 is the path parametrize: add the generator and `moves_ledger.py` there.
- **Router group:** `ci-router.yml:456-464` already uses the glob `scripts/docs/site_built_check*.py`. It lacks `scripts/docs/moves_ledger.py` and the new generator module, and must gain both.
  - `tests/release/ci_retirement_scrub.json` (`non_src_router_groups`, checked by `test_scrub_documentation_copy_equals_the_router_group`, l.136-141) must change in lockstep.
  - `site/**` already covers the map file.
- **`scripts/docs/site_built_check.py` and `site_built_check_render.py` (blocker, finding 5).**
  - Add one predicate "is a redirect stub". It is the same expression as doc-kitty's `REDIRECT_STUB_RE` and belongs in `_dockitty_contract.py` as the single authority.
  - `_pages` (`site_built_check.py:110-114`) skips a stub. A stub is a redirect, not a publication. It should still check that the stub's target is not unpublished.
  - `render.surface` (`site_built_check_render.py:103-112`) skips stubs.
  - The #6936 diagram surface needs the same predicate.
  - Tests: `tests/docs/test_site_built_check.py` and `test_site_built_check_render.py`. A stub fixture passes. A non-stub page carrying a refresh tag, or a stub pointing at an unpublished route, still fails.
- **`tests/docs/test_moves_ledger.py`** (l.126-143) uses DocFX's view and is unaffected. **`test_redirect_spine.py`** and **`test_redirect_stub_generator.py`** are unaffected: DocFX tools stay until #6943.
- **`tests/docs/test_site_scaffold.py`:** l.79-84 `test_astro_config_reads_the_contract_and_restates_no_folder` is the place to pin that `astro.config.mjs` reads the generated map and declares no `.html` Astro key.
- **`check_generated_docs_untouched.py`** guards `docs-retrieval-index.yaml`, `page-inventory.yaml` and the ADR era `index|README.md` (`scripts/ci/generated_docs_surfaces.py`). An amendment section in the ADR file does not trip it. Do not touch the era index or the inventory.
- **Packaging:** `pyproject.toml:293-294` excludes `site/**` from the sdist, and `tests/cross_cutting/packaging/test_packaging_safety.py:441-478` forbids `site/` and `scripts/`. No change is needed.
- **#7489 link debt:** no entry resolves (finding 6). `assert-no-broken-links` does not follow stubs, only checks that files exist. The issue's "Redirect" resolution route does not apply to the current 98 built-links entries, which are `.md` and source-file hrefs. Say so on #7489.
- **Lasting-value tests (#7484):**
  - *Python, over fixture inputs:* a tmp `docs/`, a moves ledger and a baseline. Mutants each make the generator refuse or change:
    - a moves target that is a draft page must go to the hub;
    - a chain;
    - a cycle;
    - a baseline URL with no page and no move must be refused as dead;
    - `README.html`;
    - a live `index.html` that must get no key;
    - a key whose `/x/index.html` is a live page but whose target differs, which must be refused because it would be fatal at build.
  - *Real gate:* a CI step, or a `selftest` subcommand run in the job after the build, that hard-links `dist` (`cp -al`, cheap: 186 MB, measured) and applies the three mutants. It asserts the run without `--docs` exits 1 for all three, and the run with `--docs` exits 1 for the dead target and the missing key and **0** for the draft-excused URL. This is the exact matrix measured above. Node is not on the pytest module shards, so a pytest wrapper of the gate would skip there, which makes it vacuous.

## 5. Risks

- **Size:**
  - The map is 927-929 keys, about 90 KB of JSON **(measured)**.
  - The stubs are about 450 B each, about 0.4 MB in total; `du` shows 3.7 MB with blocks.
  - `astro.config.mjs` does not grow, because it reads the file.
- **Build time:** a warm build took 20 s with the stubs, and the stub write is negligible **(measured)**. Each gate run takes seconds. The hard-link self-test adds about 2 runs per mutant.
- **#6936 (diagrams), developed in parallel:**
  - It edits the same `astro.config.mjs` comment (l.12-13) and options block, and the same workflow, where it adds `services:`, env and a Chromium install.
  - Expect a textual conflict only.
  - Coordinate on the shared stub predicate, so its diagram surface skips stubs.
  - Land order does not matter. Whoever lands second rebases the comment.
- **#6938 (cutover):**
  - It calls the shared workflow with `pages-artifact: true`, so it inherits the redirect gate.
  - The D-13 canary must probe a flat `.html` stub, a chain, a live `dir/index.html` with no key, a `dir/README.html`, and a dead-section `dir/` such as `/1x/` (served by the `index.html` stub).
  - A flat file removes the spike's 301-to-directory hop, so the Pages risk is lower than D-5 assumed. It stays UNVERIFIED until the canary.
- **Collision brittleness:** any future `public/` file, or a new page whose path equals a legacy source, is a build-fatal error. That is good. The generator should pre-check it, so the error is a clear generator message, not an Astro stack trace.
- **Grow-on-publish:**
  - A new page appended to the baseline needs a regenerated map. Otherwise the `--check` step fails, which is intended.
  - The issue's "831" is stale. Done-when should read "970 (the ledger's count)".
- **Drafts:** a page later flipped to draft silently becomes a hub redirect on regenerate. The `--check` step forces that regeneration into the same PR, so it is visible.

## 6. Upstream gaps

- `/x/README.html` is mis-mapped by `mechanicalHtmlMap` (`lib/legacy-html-redirects.mjs:268-269`); it does not consult `indexBasename`. This is not blocking, since core generates the map itself. **Check upstream** before filing.
- doc-kitty does not publish non-`.md` resources from `docsDir`, such as DocFX `resource` HTML. **Check upstream.** The workaround is decision (a) or (b) above.
- `dockitty-assert-no-broken-links` does not follow redirect stubs. It treats any file as resolved, so a link to a stub with a dead target passes; the coverage gate's dead-stub walk covers that. Probably by design, but **check upstream** whether #7489's "the built-links gate then follows the redirect" was assumed.
- Per-file `exclude` is `spec-kitty/doc-kitty#312`, still relevant to the 10 archived pages but not blocking here.
- Closed upstream: #249, #253 / ADR-0071 (`ce9073d`, `d66e2da`, `d73f2dd`) and gap (b). The pin includes them. `origin/main` has 3 later commits (`dc59f5c`, `8865232`, `211c4b6`, docs on root-base redirect targets), none needed.

## 7. 90-day churn (`git log --since=90.days`)

| Changes | File |
|---|---|
| 117 | `.github/workflows/ci-router.yml` (hot: keep the edit to the 2 filter lines) |
| 32 | `Makefile` |
| 11 | `tests/ci/test_docs_site_job.py` |
| 7 | the ADR |
| 5 | `_dockitty_contract.py`, `redirect_map.yaml` |
| 3 | `moves.yaml`, `site_built_check.py` |
| 2 | `astro.config.mjs`, `docs-site-build.yml` (both also touched by #6936) |
| 1 | `url-baseline.txt`, `moves_ledger.py`, `redirect_stub_generator.py`, `site_built_check_render.py` |

## 8. Suggested WP cut (2 WPs; stays `single_branch`)

**WP01: generator, committed map and site wiring.**
- Add `scripts/docs/site_redirects.py`:
  - `render`, `write` and `--check`, modelled on `site_contract.py`;
  - stdlib plus PyYAML, using `moves_ledger` and `_dockitty_contract`;
  - rules 1-4, the asset decision, and pre-checks for dead targets, dead baseline URLs and file collisions.
- Generate `site/legacy-redirects.json`.
- Wire `astro.config.mjs` (`legacyHtmlRedirects`, comment update).
- Add the stub predicate in `_dockitty_contract.py`, and the stub exemption in the `site_built_check` `page` and `render` surfaces.
- Tests: fixture mutants for the generator and the built-site check.
- Write the ADR D-5 amendment section: legacy map not Astro `.html` keys, override retired, D-14 shim list, counts 970/41/21/51, file name.

**WP02: CI gates and the real-gate self-test.** It depends on WP01.
- In `docs-site-build.yml` and `Makefile docs-site`:
  - a `site_redirects --check` step before the build;
  - coverage run 1: `--docs ../docs --declared-redirects legacy-redirects.json --astro-config astro.config.mjs`;
  - coverage run 2: `--astro-config astro.config.mjs` only;
  - the hard-linked-`dist` mutant self-test step (dead target, missing key, draft-excused).
- Add the router filter lines (`moves_ledger.py`, `site_redirects.py`) and the scrub JSON.
- `test_docs_site_job.py` assertions.
- A comment on #7489 that no entry resolves through redirects, and why.

WP01 alone can be verified with `make docs-site` plus a local gate run. A one-WP cut is also viable if the self-test is folded in.
