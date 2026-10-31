# Spike evidence: doc-kitty build, `../docs` layout and `.html` redirects

Evidence for [ADR 2026-10-31-1](../../../docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md) (epic #6100, step 1). The spike was throwaway: it ran in `/tmp`, and nothing from it lands in the repository except this record.

- **Op:** `01M6947JAAGSMJTM6ST9D429BG` (dispatch, profile `architect-alphonso`)
- **Date:** 2026-10-31
- **doc-kitty commit:** `494f2d878e2e4766d9859a4f073efb793ad86900` (`@spec-kitty/doc-toolkit` 0.5.0 plus unreleased commits)
- **Toolchain:** Node v22.23.4. The doc-kitty workspace ran pnpm 11.22.0 through its `packageManager` field; the host also has pnpm 10.28.0. Astro 7.4.4, Starlight 0.42.8.
- **Environment limits:** `docs.spec-kitty.ai` and `api.github.com` were not reachable from the session's network proxy (HTTP 403). The live site was not probed, and no deploy to GitHub Pages was made. Results about GitHub Pages come from an emulator of its documented serving rules and are **UNVERIFIED** against the real service. ADR D-13's canary closes that.

## Results

| # | Question | Result | Status |
| --- | --- | --- | --- |
| 1 | Does a `site/` project with `docsDir: '../docs'` and a matching loader `base` build? | Yes. 8 pages built, each `README.md` as its section index (`indexBasename: 'README'`). | VERIFIED (local build) |
| 2 | What does Astro emit for a redirect key ending in `.html`? | A directory stub, `dist/a/b.html/index.html`: Astro's `Redirecting to:` page with a meta refresh, `noindex` and a canonical link to the target. | VERIFIED (local build) |
| 3 | Does `check-redirect-coverage.mjs` cover `.html` keys and chains? | Yes. `/guides/old-start.html`, `/guides/getting-started.html`, `/adr/4.x/2026-10-29-1-example.html` and the chain `/explanation/moved.html` → `/guides/old-start.html` → `/guides/getting-started/` all covered. | VERIFIED (local gate run) |
| 4 | Does it cover legacy `dir/index.html` URLs? | **No.** `/guides/index.html` and `/index.html` are reported "no page and no redirect", although `dist/guides/index.html` and `dist/index.html` are the real pages. The gate maps `/x.html` only to `dist/x.html/index.html`. | VERIFIED gap (upstream b) |
| 5 | Interim for #4? | A gate-only `--redirects` override (`/guides/index.html` → `/guides/`, `/index.html` → `/`) gives 8/8 covered. A mutant override pointing at `/nowhere/` fails with "redirect target is dead", so the override is not vacuous. | VERIFIED |
| 6 | Do the stubs serve at the domain root on GitHub Pages? | Under the emulator, every baseline URL reaches a 200. A `.html` key costs one 301 (directory → trailing slash) before the meta refresh. `dir/index.html` and directory URLs are served directly. | UNVERIFIED on real Pages (emulated) |
| 7 | Flat meta-refresh stub fallback (`dist/a/b.html` as a file)? | The emulator serves every URL with one hop fewer, but the coverage gate reports all six `.html` URLs uncovered, because it cannot see flat files. | Evaluated, not chosen |
| 8 | Can doc-kitty be consumed as a pinned git dependency without a token? | Yes. `github:spec-kitty/doc-kitty#<sha>&path:/src` installed from the public repository; `pnpm-lock.yaml` records `resolution: {commit, path: /src, repo, type: git}`; the site built; the `dockitty-*` binaries ran from `node_modules/.bin`. | VERIFIED |
| 9 | Can unpublished sections be excluded before doc-kitty supports it? | Yes, with a limit: wrapping the loader to drop route prefixes works, but the entries are validated against the schema first, so an excluded page must still be schema-valid (result 14). With the wrapper, an archived `doc_status: deprecated` page appeared in no output (pages, hub links, sitemap, `llms.txt`, OKF export, content graph). The control build without it built 9 pages and the page appeared in two hubs, the OKF export and the content graph. | VERIFIED |
| 10 | GitHub `> [!NOTE]` alerts? | Rendered as literal text inside a `<blockquote>` (`<p>[!NOTE] A GitHub alert.</p>`). | VERIFIED gap (upstream c) |
| 11 | ADR index for date-named ADRs? | `generate-adr-index.mjs` wrote ID `2026` for `4.x/2026-10-29-1-example.md` (it takes the leading digits as the number). | VERIFIED gap (upstream a) |
| 12 | `llms.txt` preamble? | `llmsTxtRoute` writes `# title`, `> description`, then sections. There is no slot for free text such as the version stance. | VERIFIED gap (upstream h) |
| 13 | Do the 4 dual-index folders break a `['README', 'index']` build? | Yes. doc-kitty refuses the build: `[dk-routes] 4 route collision(s)` (`adr/1.x`, `adr/2.x`, `adr/3.x`, `architecture`). With those 4 `README.md` files removed (#6928 simulated), the build moves on. | VERIFIED (real corpus) |
| 14 | Does the real `docs/` tree build on doc-kitty? | Not as it stands. Four blockers, in order: (1) `audience` is a string, and the schema needs a list (341 pages); (2) 31 excluded pages lack `title` or `description` and fail the schema, because the exclusion shim runs after validation; (3) `related` holds repository paths, and doc-kitty resolves slugs (411 pages; 32 references point outside `docs/`); (4) `related` naming a draft or excluded page is build-fatal (181 references, including every ADR until ADRs get `doc_status`). With all four patched in the throwaway copy, the build passes: **637 pages** with `docsDir: '../docs'`, `indexBasename: ['README', 'index']` and the exclusion shim. | VERIFIED (real corpus, patched copy) |
| 15 | Does the D-5 generator cover the real baseline? | Yes. 831 baseline URLs (668 current `.html` pages plus 163 legacy map keys): 789 declared redirects (753 to the URL's own page, 36 to a section hub for unpublished pages), 42 native `dir/index.html` URLs, every legacy chain collapsed. `dockitty-check-redirect-coverage`, run **without `--docs`** and with the gate-only override: **831/831 covered**. The emulator resolved all 831. Build time with 789 redirects: 3m14s. | VERIFIED gate; Pages emulated |
| 16 | A redirect key ending in `/index.html` whose section is gone? | Emitted as `dist/tutorials/index.html/index.html`; covered by the gate; resolved by the emulator. | VERIFIED |

## Corpus measurements (core, at this record's base)

- **URLs:** `scripts/docs/capture_baseline_urls.py` (derive-from-source, written to `/tmp`, the committed manifest untouched) gives 669 URLs, 668 of them `.html`. The one other is `assets/index.md`, a resource file DocFX copies verbatim; it cannot carry a redirect stub and stays outside the baseline, as the committed manifest's 2026-07-04 amendment already records. Adding the 163 keys of `redirect_map.yaml` (none of them current pages, every target live) gives 831, which matches the operator's "about 830".
- **Index files:** 60 folders hold an `index.md`. The 4 that also hold a `README.md` are `adr/1.x`, `adr/2.x`, `adr/3.x` and `architecture`; 56 are rename-only.
- **Frontmatter:** 911 of 913 Markdown files have frontmatter; none has `kind`; 209 have a Divio `type`; 342 have a path-string `audience`. All 226 ADRs lack `doc_status`.
- **Alerts:** 7 files use GitHub alert syntax.
- **sdist:** `uv build --sdist` ships, through the bare `README.md` include, 31 `docs/**/README.md` and 676 `kitty-specs/**/README.md` files today.

## Reproduction

```bash
# 1. Throwaway copy of doc-kitty at the pinned commit, installed from its own lockfile
git -C ../doc-kitty archive 494f2d878e2e4766d9859a4f073efb793ad86900 | tar -x -C /tmp/dk-spike
cd /tmp/dk-spike && pnpm install --frozen-lockfile

# 2. Consumer layout outside the workspace: /tmp/dk-git/{docs,site}
#    site/package.json depends on
#    "@spec-kitty/doc-toolkit": "github:spec-kitty/doc-kitty#494f2d878e2e4766d9859a4f073efb793ad86900&path:/src"
#    with astro ^7.4.0, @astrojs/starlight ^0.42.6, @astrojs/markdown-remark ^7.3.3, @astrojs/sitemap ^3.7.4
#    astro.config.mjs: site 'https://docs.spec-kitty.ai', base '/', redirects from redirects.json,
#    defineDocKittyIntegrations({ title, docsDir: '../docs', base: '/', indexBasename: 'README' })
#    src/content.config.ts: docKittyDocsLoader({ base: '../docs' })
cd /tmp/dk-git/site && pnpm install && DK_PUBLISH_DRAFTS=off pnpm exec astro build

# 3. Gates
DK_PUBLISH_DRAFTS=off pnpm exec dockitty-check-redirect-coverage baseline.txt dist \
  --docs ../docs --astro-config astro.config.mjs --declared-redirects redirects.json
DK_PUBLISH_DRAFTS=off pnpm exec dockitty-check-redirect-coverage baseline.txt dist --redirects gate-overrides.json
pnpm exec dockitty-validate-frontmatter ../docs

# 4. GitHub Pages emulation (script below)
node ghpages-emulate.mjs dist baseline.txt
```

**Fixtures.** `redirects.json`:

```json
{
  "/guides/old-start.html": "/guides/getting-started/",
  "/guides/getting-started.html": "/guides/getting-started/",
  "/adr/4.x/2026-10-29-1-example.html": "/adr/4.x/2026-10-29-1-example/",
  "/explanation/moved.html": "/guides/old-start.html"
}
```

`baseline.txt`: the four keys above, plus `/guides/index.html`, `/index.html`, `/guides/` and `/`.

**Section-exclusion wrapper** (`src/content.config.ts`):

```ts
import { defineCollection } from 'astro:content';
import { docKittyDocsSchema, docKittyDocsLoader } from '@spec-kitty/doc-toolkit/schema';
const UNPUBLISHED = ['archive/', 'reports/', 'convergence/'];
function excludeSections(inner) {
  return { ...inner, name: 'spk-excluding', async load(ctx) {
    await inner.load(ctx);
    for (const [id] of ctx.store.entries()) if (UNPUBLISHED.some((p) => id === p.slice(0, -1) || id.startsWith(p))) ctx.store.delete(id);
  } };
}
export const collections = { docs: defineCollection({ loader: excludeSections(docKittyDocsLoader({ base: '../docs' })), schema: docKittyDocsSchema() }) };
```

**GitHub Pages emulator** (`ghpages-emulate.mjs`). It encodes GitHub Pages' documented static-serving rules; it is not the service.

```js
// exact file -> 200; directory without trailing slash -> 301 to "<path>/";
// directory with slash -> its index.html; else 404.
// Follows 301s and Astro meta-refresh stubs to a terminus, printing each hop.
import { existsSync, statSync, readFileSync } from 'node:fs';
import path from 'node:path';
const [dist, baselineFile] = process.argv.slice(2);
function serve(url) {
  const p = path.join(dist, decodeURIComponent(url));
  if (url.endsWith('/')) { const f = path.join(p, 'index.html'); return existsSync(f) ? { status: 200, file: f } : { status: 404 }; }
  if (existsSync(p) && statSync(p).isDirectory()) return { status: 301, location: url + '/' };
  if (existsSync(p)) return { status: 200, file: p };
  if (existsSync(p + '.html')) return { status: 200, file: p + '.html' };
  return { status: 404 };
}
const REFRESH = /<meta http-equiv="refresh" content="\d+;\s*url=([^"]*)"/i;
let bad = 0;
for (const raw of readFileSync(baselineFile, 'utf8').split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#'))) {
  let url = raw; const hops = [];
  for (let i = 0; i < 10; i++) {
    const r = serve(url);
    if (r.status === 301) { hops.push(`301 ${r.location}`); url = r.location; continue; }
    if (r.status === 404) { hops.push('404'); break; }
    const m = readFileSync(r.file, 'utf8').match(REFRESH);
    if (m) { hops.push(`refresh ${m[1]}`); url = m[1]; continue; }
    hops.push('200'); break;
  }
  const ok = hops.at(-1) === '200'; if (!ok) bad++;
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${raw} -> ${hops.join(' -> ')}`);
}
process.exit(bad ? 1 : 0);
```

**Emulator output (directory stubs, as Astro emits them):**

```text
OK   /guides/old-start.html -> 301 /guides/old-start.html/ -> refresh /guides/getting-started/ -> 200
OK   /guides/getting-started.html -> 301 /guides/getting-started.html/ -> refresh /guides/getting-started/ -> 200
OK   /adr/4.x/2026-10-29-1-example.html -> 301 /adr/4.x/2026-10-29-1-example.html/ -> refresh /adr/4.x/2026-10-29-1-example/ -> 200
OK   /explanation/moved.html -> 301 /explanation/moved.html/ -> refresh /guides/old-start.html -> 301 /guides/old-start.html/ -> refresh /guides/getting-started/ -> 200
OK   /guides/index.html -> 200
OK   /index.html -> 200
OK   /guides/ -> 200
OK   / -> 200
```

**Emulator output (flat-stub fallback):**

```text
OK   /guides/old-start.html -> refresh /guides/getting-started/ -> 200
OK   /explanation/moved.html -> refresh /guides/old-start.html -> refresh /guides/getting-started/ -> 200
```

The other two `.html` keys lose their 301 hop in the same way. The four `index.html` and directory URLs are unchanged.

## Full-corpus run (results 13 to 16)

This run used a copy of core's `docs/` at this record's base in `/tmp/dk-full/docs`, with `site/` from the git-dependency layout above and `indexBasename: ['README', 'index']`. The frontmatter patches (audience to a list, schema minimum, `related` to slugs, ADR `doc_status`, pruning `related` references to unpublished pages) were applied by throwaway scripts to that copy only. They show which D-7 migrations the build needs, not how #6931 should write them.

**Redirect generator** (`genredirects.py`), a working seed for #6933. Inputs: the derive-from-source URL set, `scripts/docs/redirect_map.yaml`, a first build's `dist/`. Outputs: `redirects.json`, `url-baseline.txt` and the gate-only override.

```python
import json,sys,pathlib,yaml
derived,mapf,dist,out_red,out_base,out_ovr=sys.argv[1:7]
dist=pathlib.Path(dist)
cur=[u.replace('https://docs.spec-kitty.ai/','') for u in json.load(open(derived))['urls'] if u.endswith('.html')]
m=yaml.safe_load(open(mapf))
base=sorted(set(cur)|set(m))
def page(route):  # route like 'a/b/' or ''
    f=dist/route/'index.html'
    return f.exists() and 'Redirecting to:' not in f.read_text(errors='ignore')[:400]
def html_to_route(u):
    if u.endswith('index.html'): return u[:-len('index.html')]
    if u.endswith('README.html'): return u[:-len('README.html')]
    return u[:-len('.html')]+'/'
def hub(route):
    parts=route.strip('/').split('/')
    while parts:
        parts=parts[:-1]; r='/'.join(parts)+('/' if parts else '')
        if page(r): return r
    return ''
red={}; ovr={}; stats={'native_index':0,'to_page':0,'to_hub':0,'map_chain':0}
for u in base:
    src=u; seen=set()
    while src in m and src not in seen: seen.add(src); src=m[src]; 
    if src!=u: stats['map_chain']+=1
    r=html_to_route(src)
    if u.endswith('index.html') and page(html_to_route(u)):
        ovr['/'+u]='/'+html_to_route(u); stats['native_index']+=1; continue
    if page(r): red['/'+u]='/'+r; stats['to_page']+=1
    else: red['/'+u]='/'+hub(r); stats['to_hub']+=1
json.dump(red,open(out_red,'w'),indent=1); json.dump(ovr,open(out_ovr,'w'),indent=1)
open(out_base,'w').write('# derived for the spike\n'+'\n'.join('/'+u for u in base)+'\n')
print('baseline',len(base),stats,'declared',len(red))
```

Commands:

```bash
python3 -I genredirects.py derived_urls.json ../../spec-kitty/scripts/docs/redirect_map.yaml dist redirects.json url-baseline.txt gate-overrides.json
rm -rf dist .astro node_modules/.astro && DK_PUBLISH_DRAFTS=off pnpm exec astro build
DK_PUBLISH_DRAFTS=off pnpm exec dockitty-check-redirect-coverage url-baseline.txt dist --redirects gate-overrides.json   # 831/831
node ghpages-emulate.mjs dist url-baseline.txt                                                                           # 831 OK
```
