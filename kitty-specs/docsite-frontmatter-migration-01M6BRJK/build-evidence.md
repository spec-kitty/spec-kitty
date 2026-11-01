# Build evidence: the migrated `docs/` tree builds on doc-kitty (#6929)

One-off build, as in the spike (`kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md`),
run in `/tmp` on 2026-11-01. Nothing from the site project is committed; #6930 owns `site/`.

## Result

| Build | Tree | Exit | Pages |
| --- | --- | --- | --- |
| Migrated | this branch's `docs/` (`git archive HEAD docs`) | **0** | **640 page(s) built** (spike: 637 on its patched copy) |
| Control | `origin/main`'s `docs/` | 1 | fails on the first page: `api/batch-api-contract`, ``audience: Expected type "array", received "string"`` |

Both builds simulate #6928 in the `/tmp` copy only, as the spike did: `adr/{1,2,3}.x/README.md` and
`architecture/README.md` are deleted there, because the four dual-index folders collide when both
`README` and `index` are section indexes. #6928 (parallel session) resolves them in the repository.

## Toolchain

- Node v22.23.4, pnpm 10.28.0, Astro 7.4.4, Starlight 0.42.8, `@astrojs/markdown-remark` 7.3.5.
- doc-kitty: `@spec-kitty/doc-toolkit` 0.5.0 at commit `fe835cd3a2d657e7c7ff31c504b8e44233007685` (doc-kitty `main`, contains `b77e40d`), as a pnpm git dependency. `pnpm-lock.yaml` records `resolution: {commit: fe835cd…, path: /src, repo: git@github.com:spec-kitty/doc-kitty.git, type: git}`.

## Site files

`package.json`:

```json
{
  "name": "spk-docsite-oneoff",
  "private": true,
  "type": "module",
  "dependencies": {
    "@spec-kitty/doc-toolkit": "github:spec-kitty/doc-kitty#fe835cd3a2d657e7c7ff31c504b8e44233007685&path:/src",
    "astro": "^7.4.0",
    "@astrojs/starlight": "~0.42.6",
    "@astrojs/markdown-remark": "^7.3.3",
    "@astrojs/sitemap": "^3.7.4"
  }
}
```

`astro.config.mjs`:

```js
import { defineConfig } from 'astro/config';
import { defineDocKittyIntegrations } from '@spec-kitty/doc-toolkit/config';
const EXCLUDE = (process.env.SPK_EXCLUDE ?? 'archive,reports,convergence,changelog/unreleased').split(',').filter(Boolean);
export default defineConfig({
  site: 'https://docs.spec-kitty.ai',
  base: '/',
  integrations: defineDocKittyIntegrations({
    title: 'Spec Kitty',
    docsDir: process.env.SPK_DOCS ?? '../docs',
    base: '/',
    indexBasename: ['README', 'index'],
    exclude: EXCLUDE,
  }),
});
```

`src/content.config.ts`:

```ts
import { defineCollection } from 'astro:content';
import { docKittyDocsSchema, docKittyDocsLoader } from '@spec-kitty/doc-toolkit/schema';
export const collections = { docs: defineCollection({ loader: docKittyDocsLoader({ base: process.env.SPK_DOCS ?? '../docs' }), schema: docKittyDocsSchema() }) };
```

The exclude list equals `scripts/docs/_dockitty_contract.py::EXCLUDED_FOLDERS`; #6930 should take it from there.

## Commands

```bash
mkdir -p /tmp/dk-site/site && cd /tmp/dk-site/site   # files above
pnpm install
git -C <repo> archive HEAD docs | tar -x -C /tmp/dk-site
rm /tmp/dk-site/docs/adr/{1,2,3}.x/README.md /tmp/dk-site/docs/architecture/README.md   # #6928 simulation
DK_PUBLISH_DRAFTS=off pnpm exec astro build                                            # exit 0, 640 pages
# control: same, with `git archive origin/main docs` into /tmp/dk-base and SPK_DOCS=../../dk-base/docs  -> exit 1
```

## What changed against the spike

- **No exclusion shim.** doc-kitty's native `exclude` (doc-kitty #247, ADR-0070) never reads the
  excluded folders, so they need no `title`/`description` backfill. Verified separately: a tree of
  only `archive/`, `reports/` and `convergence/` plus a valid root page builds with `exclude`
  (exit 0) and fails without it (schema error on `convergence/doctrine-drg`).
- **`changelog/unreleased` is excluded too.** Per-PR changelog fragments (#6988, after the spike)
  have no frontmatter and are not pages.
- **Root slug.** Twelve pages name the docs root in `related`; doc-kitty keys it as `''`
  (`slugFromEntryId`), and the build resolves it.

## doc-kitty gates (information only; #6931 and #6937 own them)

Run with `--astro-config astro.config.mjs`, so both read `indexBasename` and `exclude` from the
site config. The docs path given to a gate must be the config's `docsDir`. With a different
path, `exclude` silently does not apply: reviewers saw 886 failures, archive pages included, until
the two matched. #6930/#6937 should wire the gates with the same path.

- `dockitty-validate-frontmatter ../docs`: exit 1. 632 files fail, and every failure is `kind`
  required (443) or `updated` required (189). Both are contract completion (#6931). None
  involves `audience`, `related`, `external_references` or ADR `doc_status`.
- `dockitty-check-links ../docs --strict`: exit 1. 117 problems in 43 files, all body links:
  links out of `docs/` into `kitty-specs/`/`tests/`, and links that leave and re-enter the docs
  root. These are #6930/#6937's gate scope. None is a `related` reference.

## Gaps

- PlantUML code blocks render as text, with a highlighter warning. The diagrams step (#6936) owns this.
- No new upstream doc-kitty gap found. The four classes of #6929 are resolved without a shim.
