<!-- Read-only grounding, 2026-11-09. Operator answers recorded as Decision Moments in decisions/. -->
# Grounding: docsite publication rules, llms.txt and render parity (#6932, #6934, #6935)

Read-only research, 2026-11-09. Base: local branch `issue-6937-docs-site-shared-build` (PR #7486). Its working tree equals the branch, and it is 4 commits ahead of `origin/main` (`e1fde158d`). doc-kitty is pinned at v0.7.0 = `5acb83c` (`site/package.json:15`). Paths into doc-kitty are `src/...` at `5acb83c`. Out of scope: #6933 (redirects), #6936 (diagrams), #6938 (cutover and the deletion of `docs/llms.txt`).

## 0. Headline findings (read first)

1. **Folder exclusion is already in place (ADR gap f is closed).** doc-kitty's `exclude` option (ADR-0070, `src/lib/config.ts:325-340`) is fed from `EXCLUDED_FOLDERS` through `site/dockitty-contract.json`. `site/src/content.config.ts` therefore carries **no loader-filter shim**, although ADR D-8 still describes one. The ADR text is stale: amend it or record the drift.
2. **`exclude` takes FOLDERS only.** The doc says: "Each entry must name an existing folder with its exact letter case; glob patterns are not accepted" (`config.ts:336-338`). The retired hosted and sync pages are single files spread over `operations/`, `architecture/`, `migrations/`, `guides/` and `plans/`, so `exclude` cannot remove them. Two options:
   - (a) set `doc_status: draft` in frontmatter, which is what the operator ruling permits ("draft or unpublished");
   - (b) move the files under `archive/`, which makes it #6933 territory (moves.yaml).

   Option (a) is the only one that stays inside this mission. `EXCLUDED_FOLDERS` then gains no new entry. The "single authority" for the retired set becomes either the page frontmatter, or a new tuple in `_dockitty_contract.py` that a test checks against the frontmatter.
3. **`sections.yaml` already sets `plans` to `feeds: [sitemap]`** (`docs/_meta/sections.yaml:63-68`). It is already pinned by `tests/docs/test_site_scaffold.py:146-149` (`test_plans_has_restricted_feeds`), and `development` is already registered (`sections.yaml:51-54`). Both #6932 bullets on the section registry are therefore done.
4. **No llms.txt preamble option exists at v0.7.0.** `LlmsTxtRouteOptions` is `{title, description?, links?, indexBasename?}` (`src/lib/routes/llms-txt.ts:49-63`), so the D-9 wrapper shim is required. Gap (h) / doc-kitty #265 is still open (check upstream).
5. **llms.txt always prints `Full machine index: <site>/api/index.json`** (`llms-txt.ts:108`). Core mounts no `agentIndexRoute` (`site/dist/api/` has no `index.json`). `dockitty-assert-no-broken-links --site` scans absolute URLs inside `llms.txt` (`src/scripts/assert-no-broken-links.mjs:50-57`), so mounting llms.txt alone will probably make that gate red. Fixes:
   - mount `src/pages/api/index.json.ts` as well (doc-kitty's documented location, `src/lib/routes/agent-index.ts:6`), or
   - strip that line in the wrapper, which is less faithful.

   Watch the namespace: core's `docs/api/` section also builds to `dist/api/`.
6. **GitHub alerts are supported in v0.7.0** as the opt-in `githubAlerts: true` (#250 / ADR-0068, `config.ts:274-283`, wired at `:929`). Core's `astro.config.mjs` does not set it, so alerts render as literal text today. 5 published files match a strict grep:
   - `development/contributing.md`
   - `guides/tutorials/{claude-code-workflow,charter-governed-workflow,claude-code-integration}.md`
   - `guides/how-to/installation/install-spec-kitty.md`

   Plus 2 changelog pages. `dist/guides/tutorials/your-first-mission/` also shows a literal `[!`. The fix is one flag in config, not rewrites.
7. **SEO parity is already met by Starlight 0.42.8 plus doc-kitty.** In the existing `site/dist`, 650/650 HTML pages carry `rel="canonical"`. Each page also has `og:title`, `og:type`, `og:url`, `og:locale`, `og:description`, `og:site_name`, `twitter:card`, `meta description`, and from doc-kitty `HeadShare` `og:image*` and `twitter:image*`. Sources:
   - Starlight `dist/utils/head.js:14-119`;
   - doc-kitty `src/components/Head.astro:61-80` (also `robots noindex` on drafts, `:64`);
   - doc-kitty `src/components/slots/HeadShare.astro`.

   DocFX-only items to put on the checklist: JSON-LD (dropped by ruling 3), the `FALLBACK_DESCRIPTION` boilerplate detection and the non-default-title rule (`scripts/docs/seo_postprocess.py:22-31`, `seo_verify.py:281-306`).
8. **doc-kitty #295 is confirmed in code.** The toolkit's `head: [...fontHead, PRE_PAINT_SCRIPT]` (`config.ts:784-796`) is followed by `...overrides` (`config.ts:799`, where `overrides = starlight` `:590`). A consumer `starlight: { head: [...] }` therefore **replaces** the toolkit head entries, including the TOC pre-paint script. Core must not add `starlight.head` until #295 lands; any extra meta goes through a component or slot instead.
9. **Drafting pages is a link-hygiene job.** With `DK_PUBLISH_DRAFTS=off`, `dockitty-check-links --strict` reports every link from a published page to a draft (`src/scripts/check-links.mjs:56-66, 276-282`). doc-kitty also treats a `related:` entry naming a draft as build-fatal (ADR D-8). Rough inbound counts from published-ish pages (they include links inside the folders themselves) are in §4. Each must be removed or reworded. Bodies under `plans/` are immutable (`_dockitty_contract.py:103,196-200`): only frontmatter may change there, so links *from* plans bodies to new drafts cannot be edited.

## 1. Current state (files each issue touches)

### Single authority and projection
- `scripts/docs/_dockitty_contract.py` (441 lines):
  - `EXCLUDED_FOLDERS = ("archive","reports","convergence","changelog/unreleased")` at `:88`;
  - `DRAFT_STATUS` at `:97`;
  - `is_excluded` at `:147-149`;
  - `is_published` at `:169-174` (absent `doc_status` counts as draft);
  - `_IMMUTABLE_PREFIXES` (plans/, reports/, changelog/, archive/) at `:103`;
  - `DOCKITTY_PIN` mirror (validated by `tests/docs/test_dockitty_contract.py:194`).

  #6932 extends it, for example with a `RETIRED_PAGES` tuple or an `UNPUBLISHED_DRAFT_FOLDERS` set (`plans/engineering-notes`, `plans/investigations`, `plans/research`), plus a predicate.
- `scripts/docs/site_contract.py`: `_expected()` projects only `exclude` and `indexBasename` (`:34-39`); `--check` runs in the shared workflow (`docs-site-build.yml:39-44`). It also needs extending if new contract keys must reach JS (for example the llms stance text, or a retired-slug list for an artifact check).
- `site/dockitty-contract.json`: generated, with 4 excludes and 2 index basenames (`:3-12`).

### Site
- `site/astro.config.mjs:16-29`: `exclude: contract.exclude` `:25`, `diagrams: false` `:26`, `starlight: { disable404Route: true }` `:27`. There is no `githubAlerts`, and no llms or agent routes. The header comment (`:8-9`) says llms.txt (#6934) is "not wired here yet".
- `site/src/`:
  - `content.config.ts` (loader with no filter);
  - `pages/404.astro`.

  There is no `pages/llms.txt.ts` and no `pages/api/index.json.ts`.
- `site/.env.production:1`: `DK_PUBLISH_DRAFTS=off`. This is the single place, and the workflow does not repeat it.
- `site/public/robots.txt` points at `sitemap-index.xml`.
- `docs/_meta/sections.yaml`: 16 sections, with `development` (`:51`) and `plans` `feeds: [sitemap]` (`:63-68`). Note that `templates` and `assets` are registered sections (`:69-76`).
- `docs/llms.txt`: 60 lines, hand-written. It holds the "Current Version Stance" block (lines 5-12) that D-9 must carry over. It is deleted at #6938.
- Top-level `docs/retrospective-learning-loop.md` builds to `dist/retrospective-learning-loop/`, an unregistered "section". It is worth checking as part of the publication rules.

### Build workflow and Makefile
- `.github/workflows/docs-site-build.yml` (72 lines, `workflow_call` only): the contract check (`:39-44`), then pnpm/node setup, `pnpm install --frozen-lockfile` (`:54-56`), `pnpm run build` (`:57-59`) and the upload (`:60-72`). **No `dockitty-*` gate runs yet.** #6932 adds `dockitty-validate-frontmatter ../docs --astro-config astro.config.mjs` and `dockitty-check-links ../docs --strict --astro-config astro.config.mjs` (after install; working-directory `site`), plus the artifact check after the build.
- `.github/workflows/ci-router.yml`:
  - `docs-site` job `:1774-1778` (uses the shared file);
  - `docs_site` path filter `:456-462` (docs/**, site/**, `_dockitty_contract.py`, `site_contract.py`, ci-router.yml, docs-site-build.yml).

  A new artifact-check script under `scripts/docs/` must be added to this filter. `tests/ci/test_docs_site_job.py:132` pins the scrub copy against the router group.
- `Makefile:45-47` `docs-site`: `site_contract --check`, then install and build. It runs no gates. `tests/ci/test_docs_site_job.py:225-229` also requires every `dockitty-*` call in the Makefile to carry `--astro-config astro.config.mjs`.
- DocFX side (keep untouched until retirement): `.github/workflows/docs-pages.yml:147` runs `seo_postprocess.py` and `:224` runs `seo_verify.py --site-dir docs/_site --strict`. D-6 says "port". Under D-13 they are deleted only at retirement, so #6935 records parity and does not delete them now. Their tests are `tests/docs/test_docs_seo.py` and `test_seo_verify.py`.

### Built output today (`site/dist`, built 2026-11-09 18:46 from this tree; no build was run here)
- 650 HTML pages; `sitemap-index.xml` and `sitemap-0.xml`; `pagefind/` (search); `okf/` (OKF export, 711 files); `api/content-graph.json`; `api/pages/*.atom.xml` (per-page Atom); `robots.txt`; `404.html`.
- **No `llms.txt`, no `rss.xml`, no `api/index.json`.** The routes are not mounted.
- Excluded folders (`archive`, `reports`) are absent from `dist/` and `okf/`. Drafts are absent from `dist/`.
- 12 non-draft pages (7 `deprecated`, 1 `active` in engineering-notes; 4 `deprecated` in investigations) **are built today** under `dist/plans/engineering-notes/` (6 entries) and `dist/plans/investigations/` (4). `plans/research` has 2/2 drafts.
- Because `plans` has `feeds:[sitemap]`, plans pages correctly appear in the sitemap. They also appear in `okf/plans/` and search. `feeds` governs only `sitemap|rss|llms|agent` (`src/lib/sections.ts:381`). A test must not assert plans' absence from OKF or search: only drafts and excluded pages must be absent.

## 2. What doc-kitty v0.7.0 offers

| Need | doc-kitty v0.7.0 | Path |
|---|---|---|
| Folder exclusion | `exclude` option; loader, sidebar, sitemap, feeds, llms, agent API, search and gates all honour it; folders only | `src/lib/config.ts:325-340, 684-687`; `src/lib/docs-walk.mjs` |
| Drafts | `DK_PUBLISH_DRAFTS` (default on); `draftPublicationIntegration`; `sitemapDraftFilter`; `robots noindex` on a rendered draft | `config.ts:957-980`; `src/components/Head.astro:54,64` |
| validate-frontmatter | `dockitty-validate-frontmatter [<root>...] [--index-basename] [--astro-config <path>] [--exclude <folder>...]`; reads `exclude` from config; **drafts are still validated** | `src/scripts/validate-frontmatter.mjs:6-8, 665-727` |
| check-links | `dockitty-check-links [<root>...] [--strict] [--index-basename] [--astro-config] [--site-root <dir>] [--mode] [--exclude <folder>]`; strict mode reports links to drafts (env from `--site-root`'s `.env.<mode>`) and links into excluded folders | `src/scripts/check-links.mjs:6-10, 56-80, 264-299` |
| Built-output links | `dockitty-assert-no-broken-links <dist> [--base] [--site]`; also scans llms.txt, rss and api JSON absolute URLs | `src/scripts/assert-no-broken-links.mjs:3-57` |
| OKF | always-on `okfExportIntegration` writes `dist/okf/`; `dockitty-export-okf --check` | `config.ts:987-990`; `src/scripts/export-okf.mjs:5-21` |
| llms.txt | `llmsTxtRoute({title, description, links:{mcp}, indexBasename})`; filters `feedsSurface(...,'llms')` (`:85-87`); always prints the machine-index line (`:108`); **no preamble** | `src/lib/routes/llms-txt.ts`; example mount `example/src/pages/llms.txt.ts` |
| Agent index | `agentIndexRoute`, mounted at `src/pages/api/index.json.ts` | `src/lib/routes/agent-index.ts:6`; exports `src/lib/routes/index.ts:1-13` |
| Head/SEO | Starlight Head plus the doc-kitty `Head` carrier and `HeadShare` (og:image); `starlight.head` override clobbers toolkit head (#295) | `config.ts:784-799`; `src/components/Head.astro`; `src/components/slots/HeadShare.astro:1-16` |
| GitHub alerts | `githubAlerts: true` | `config.ts:274-283, 929`; `src/lib/remark/github-alerts.ts` |
| Legacy .html | `legacyHtmlRedirects` and `dockitty-generate-legacy-redirects` (#6933, not this mission) | `config.ts:365-378` |

Installed bins: `site/node_modules/.bin/dockitty-*` (11). There is no `assert-build-artifacts` bin. doc-kitty's own artifact asserter is not exported (`src/package.json` `bin`), so core needs its own artifact check (Python stdlib is consistent with `site_contract.py`).

## 3. Gates and tests touched

- `tests/ci/test_docs_site_job.py` (345 lines). It pins: the router filter group (`:93-132`); the fork guard via `changes` (`:151`); SHA pins (`:176`); no credential (`:187`); `--frozen-lockfile` and the contract check (`:201-205`); no `continue-on-error` or `|| true` (`:208-213`); **every `dockitty-*` call carries `--astro-config astro.config.mjs` in the router, the shared file and the Makefile** (`:225-238`); required by router-gate (`:258-311`); the router calls the shared definition (`:326-331`). New gate steps and an artifact-check step extend it.
- `tests/docs/test_site_scaffold.py` (149 lines): contract JSON equals the authority (`:44`); `astro.config` restates no folder (`:78`); every published top-level folder is registered (`:135-143`, uses `contract.is_excluded`); plans has restricted feeds (`:146`).
- `tests/docs/test_dockitty_contract.py` (320 lines): `is_excluded` / `is_published` tables (`:69-88`); the pin mirror (`:194`). New predicates are tested here.
- `tests/docs/test_site_bump.py`: `make docs-site` shape (`:181`). Touched if the Makefile target gains gates.
- `tests/architectural/test_dual_mode_contract.py`: router-gate needs and wiring (`:268-389`). Touched only if jobs change. Adding steps inside the shared workflow does not touch it.
- `tests/release/test_release_ci_ownership.py:419` pins `docs-pages.yml` (deploy). Do not touch it (#6938).
- `tests/ci/test_fork_guard.py`: the shared workflow is `workflow_call`, so no new automated trigger is involved. Unaffected unless a new workflow is added.
- `tests/cross_cutting/packaging/test_packaging_safety.py:478` `test_sdist_ships_no_docs_kitty_specs_or_site_member`. New files under `site/` stay excluded, and a new `scripts/docs/*.py` is not a wheel package.
- Also affected by drafting or editing frontmatter:
  - `tests/docs/test_related_validator.py`, `test_immutable_bodies.py` (body bytes of plans/ must not change), `test_doc_status_durable.py`, `test_audience_resolves.py`, `test_docs_structural_lint.py`, `test_description_length_gate.py`;
  - DocFX's `scripts/docs/_published_pages.py` (reads docfx.json, so it is unaffected by doc_status).
- **Bot-regenerated surfaces a PR must NOT edit** (`scripts/ci/check_generated_docs_untouched.py:1-25`, `scripts/ci/generated_docs_surfaces.py:21`):
  - `docs/development/docs-retrieval-index.yaml`;
  - `docs/development/page-inventory.yaml`;
  - new rows in `docs/adr/<era>/index.md` tables.

  A frontmatter flip will make these stale. That is expected: leave them for the `ci/regen-docs-index` bot.
- Terminology guard (`tests/architectural/test_no_legacy_terminology.py`) applies to user-facing prose, such as the llms stance text.

## 4. Retired-page inventory (hosted/sync), outside archive/reports/convergence/changelog

Grep: `zeitgeist|teamspace|sync daemon|offline queue|OfflineQueue|offline_queue|sync_daemon` plus filename/title scan. **Candidates for unpublishing (draft):**

| Page | doc_status now | Baseline URL? | Reason |
|---|---|---|---|
| `operations/sync-daemon-orphan-cleanup.md` | deprecated | yes (`:869`) | runbook for removed sync daemon |
| `operations/logged-out-teamspace.md` | deprecated | yes (`:862`, also `/recovery/...:957`) | "(Removed)" stub, exists only so old links resolve |
| `operations/internal-hosted-readiness.md` | deprecated | yes (`:861`, plus guides/how-to legacy `:707,:797`) | "(Removed)" stub for hosted-readiness mode |
| `architecture/team-kitty-saas.md` | deprecated | yes (`:392`) | "(Removed)" hosted sync flow |
| `architecture/zeitgeist-session-identity.md` | deprecated | yes (`:399`) | Zeitgeist publisher/lease identity, retired |
| `guides/project-sync-consent.md` | deprecated | yes (`:720`) | per-project hosted-sync consent, retired |
| `migrations/teamspace-mission-state-repair.md` | deprecated | yes (`:850`) | TeamSpace repair before connecting, a hosted surface |
| `migrations/teamspace-mission-state-920-closeout.md` | deprecated | yes (`:849`) | TeamSpace closeout evidence |
| `plans/zeitgeist-client-wp01-remaining.md` | **active** | yes (`:955`) | plan for the removed zeitgeist_client |
| `guides/how-to/collaboration/sync-workspaces.md` | deprecated | yes (`:622,:734,:815`) | *borderline*: retired workspace-sync (lanes), not hosted; banner says "Removed in 3.2.6… deletion in 3.2.7". Operator call. |

**Keep published** (they name the surfaces as context, or are ADRs, which ruling 5 keeps indexed):
- `context/team-kitty.md` (canonical glossary on why "sync" is dead);
- ADRs `3.x/2026-04-21-1`, `2026-06-30-1` (superseded), `2026-09-06-1`, `2026-09-06-2`, `2026-09-26-3`, `2026-04-11-1`, `4.x/2026-10-06-1`;
- `migrations/tracker-egress-refusal.md` (live tracker binding);
- `plans/4-0-0-milestone-roadmap.md`, `plans/agent-moment-delivery-4216.md`;
- `api/batch-api-contract.md`, `api/cli-commands.md`, `api/configuration.md`;
- `development/how-to/sync-packs.md` (pack sync, unrelated);
- architecture indexes and diagrams that mention them in passing.

These still need **prose links** to the retired pages removed. Approximate inbound link counts (published plus intra-folder): team-kitty-saas 2, zeitgeist-session-identity 1, sync-daemon-orphan-cleanup 2 (+1 `related`), teamspace-mission-state 1 (+1 `related`), sync-workspaces 3 (+2 `related`), zeitgeist-client-wp01 1.

**plans subfolders:** engineering-notes 27 files (19 draft, 7 deprecated, 1 active), investigations 11 (7 draft, 4 deprecated), research 2 (2 draft). That leaves 12 pages to flip, listed with `grep -L '^doc_status: draft' -r docs/plans/{engineering-notes,investigations,research}`. 36 of their URLs are in `site/url-baseline.txt` (the ADR says 34). Inbound approx: 13 `related` and about 15 links into engineering-notes; 3 `related` and about 5 links into investigations; about 18 links into research (many from inside plans/, whose bodies are immutable: check whether they are themselves drafts).

## 5. Interactions

- **#6933 (redirects)** consumes this mission's unpublished set. D-5 rule 4 sends a baseline URL of an unpublished page to its section hub (36 URLs today). The second coverage run (without `--docs`) excuses nothing. So #6932 must expose the unpublished set from the single authority in a form the redirect generator can read, either the predicate or a JSON projection. Adding retired pages grows the "to hub" set beyond 36: about 15 more baseline URLs from §4. #6933 is blocked by #6932 (issue body). Do not generate `redirects.json` here.
- **#6936 (diagrams)** edits the same `site/astro.config.mjs` (`diagrams: false` → true) and `docs-site-build.yml` (PlantUML service, Playwright Chromium). Merge-conflict hotspot: keep this mission's edits to the shared workflow additive and in separate steps.
- **#6938** deletes `docs/llms.txt` and switches deploy. #6934 only generates `dist/llms.txt` beside it.
- **#7484 ATDD caution:** acceptance tests must have lasting value. Prefer:
  - a check over the **built artifact**: walk `site/dist` and assert no excluded/draft/retired slug appears in the HTML pages, hub links, `sitemap-0.xml`, `llms.txt`, `okf/`, `pagefind` index and `api/content-graph.json`; and that `llms.txt` carries the stance block and no `plans/` entry;
  - mutant tests on a fixture dist (planted page, planted sitemap loc, planted llms line) that must fail;

  over YAML-shape restatement such as "sections.yaml has feeds: [sitemap]", which already exists. The artifact check must run in the shared workflow after `pnpm run build`, because pytest cannot build the site without Node.

## 6. 90-day churn (`git log --since=90.days origin/main -- <f> | wc -l`)

| File | commits |
|---|---|
| `.github/workflows/ci-router.yml` | 114 |
| `docs/plans` (tree) | 115 |
| `Makefile` | 31 |
| `.github/workflows/docs-pages.yml` | 14 |
| `scripts/docs/_dockitty_contract.py` | 4 |
| `tests/ci/test_docs_site_job.py` | 4 |
| `tests/docs/test_dockitty_contract.py` | 3 |
| `scripts/docs/site_contract.py`, `tests/docs/test_site_scaffold.py` | 2 |
| `site/astro.config.mjs`, `site/src`, `site/.env.production`, `docs/_meta/sections.yaml`, `site/dockitty-contract.json`, `scripts/docs/seo_postprocess.py` | 1 |
| `docs/llms.txt`, `scripts/docs/seo_verify.py` | 0 |

(`docs-site-build.yml` is new on the PR #7486 branch and not yet on main.) Hotspots: ci-router.yml and Makefile; prefer editing the shared `docs-site-build.yml`.

## 7. doc-kitty upstream gaps (check upstream for existing issues)

- **Per-file exclusion**: `exclude` is folders-only (`config.ts:336-338`). Retired single pages need draft status or a move. File as a follow-on to #247/#252 if needed (check upstream).
- **llms.txt preamble** (ADR gap h, doc-kitty #265): absent in v0.7.0 (`llms-txt.ts:49-63`).
- **llms.txt machine-index line is unconditional** (`llms-txt.ts:108`): it dangles when no agent index is mounted. Ask for the line to be opt-in, or to follow served-surface detection (check upstream).
- **`starlight.head` replaces toolkit head** (#295): `config.ts:784-799`.
- **No exported built-artifact assertion bin** for "unpublished page absent from all surfaces". Core writes its own; consider an upstream `dockitty-assert-unpublished` (check upstream).
- **Drafts are still validated by `validate-frontmatter`**: drafts in plans/ must keep build-schema-valid frontmatter. The gate has no "published only" mode except `exclude` (check upstream).
- **SEO parity extras** DocFX had: a boilerplate or default-description detector and a unique-title rule. Starlight falls back to the site `description` when a page has none (`head.js:19`). No doc-kitty gate fails a page that uses the fallback. The frontmatter gate requires `description`, so this is low risk. Note it on the parity checklist.

## 8. Suggested WP cut (for the planner)

- **WP01 #6932:**
  - extend the authority (draft folders and the retired set) and its JSON projection;
  - flip 12 plans pages and about 9 retired pages to draft (frontmatter only);
  - clean inbound links and `related` refs from published pages;
  - add the `dockitty-validate-frontmatter` and `check-links --strict` steps (with `--astro-config astro.config.mjs`) to `docs-site-build.yml` and the Makefile;
  - add the artifact check script (stdlib), its workflow step after the build, and fixture/mutant tests;
  - update the ADR D-8 shim text.
- **WP02 #6934:**
  - add `site/src/pages/llms.txt.ts` (a wrapper that inserts the D-9 stance block from `docs/llms.txt:5-12`);
  - decide on the agent index (mount `api/index.json.ts`, or strip the line);
  - extend the artifact check: stance present, only `feeds: llms` sections, no plans, no draft.
- **WP03 #6935:**
  - set `githubAlerts: true`;
  - write the parity checklist vs DocFX (`seo_verify.py` rules V-01..V-08) as artifact assertions: description, self-canonical, og:* on every page;
  - add no `starlight.head` (#295);
  - leave `seo_postprocess.py` and `seo_verify.py` until DocFX retirement (D-13).
