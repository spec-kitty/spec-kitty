# Upstream doc-kitty issue drafts (spec-kitty docsite migration, epic spec-kitty/spec-kitty#6100)

Drafts for `spec-kitty/doc-kitty`, written by Op `01M6947JAAGSMJTM6ST9D429BG`. This run has no write access to doc-kitty; the operator files them. Check doc-kitty's open issues for duplicates first.

**Pasting.** Each draft below is self-contained from its second-level heading down. Its title is the heading text without the letter. Every cross-repository reference is written `spec-kitty/spec-kitty#N`, so it links correctly from doc-kitty.

Each draft names the evidence from the spike (`spike-evidence.md` in this folder; doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`) and the consumer-side shim spec-kitty carries until the issue lands, if any.

Drafts (a) to (g) were requested. (h) and (i) came out of the spike.

---

## (a) ADR index: support date-named ADRs in era folders, with a frontmatter-status fallback

**Size:** M · **Consumer:** spec-kitty (226 ADRs)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.** `src/scripts/generate-adr-index.mjs` assumes numbered ADRs (`0042-title.md`). It keeps files whose name starts with `^(\d{4})-`, takes those four digits as the ADR number, and sorts by it. spec-kitty names ADRs `YYYY-MM-DD-N-title.md` in era folders (`adr/1.x/`, `2.x/`, `3.x/`, `4.x/`). On `4.x/2026-10-29-1-example.md` the generator writes ID `2026`, so every ADR of a year collides on one number. Status is read only from the body's `## Status` section; spec-kitty ADRs carry it in frontmatter (`status: Accepted`), some with a `**Status:**` line instead of a section. The `Hub.astro` cards share the same extractor.

**Evidence.** Spike result 11: the generator wrote ID `2026` for `4.x/2026-10-29-1-example.md`.

**Proposal.**
- Recognise a date-named file, `^(\d{4}-\d{2}-\d{2})-(\d+)-`, as ID `YYYY-MM-DD-N`, and sort by date, then N.
- Group the index by era folder when ADRs sit in subfolders, with one table per era or an era column.
- Read status from the body `## Status` section, then from frontmatter `status`, then from a `**Status:**` line. Say in the output which source each status came from.
- Read the date from frontmatter `date` when present, else `updated`.

**Done when.** A fixture with numbered ADRs and date-named, era-foldered ADRs produces a correct, stable index; existing numbered-ADR output is byte-identical; `--check` detects drift for both shapes.

**spec-kitty shim meanwhile.** None. spec-kitty keeps its own era indexes (`docs/adr/<era>/index.md`) and `scripts/docs/freshen_adr_inventory.py` until this lands.

---

## (b) Redirect-coverage gate: resolve an exact `*.html` file before `<path>/index.html`

**Size:** S · **Consumer:** spec-kitty (about 830 legacy `*.html` URLs at the domain root)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.**
- `check-redirect-coverage.mjs`'s `urlToDistFile` maps every URL to `<dist>/<path>/index.html`, so `/guides/index.html` is looked up at `dist/guides/index.html/index.html`.
- A legacy DocFX URL such as `/guides/index.html` is served by GitHub Pages straight from `dist/guides/index.html`, the section's real page. The gate still reports it "no page and no redirect".
- A site cannot declare an Astro redirect at that path: it would collide with the page.
- A flat meta-refresh stub (`dist/old.html` as a file, one 301 fewer on Pages than Astro's directory stub) is equally invisible to the gate.

Separately, `base: '/'` sites should not prefix targets with the base; the example's `${BASE}${to}` gives `//x`. A note in `consumer-setup.md` is enough for that.

**Proposal.** For a URL whose last segment ends in `.html`, inspect `<dist>/<path>` (an exact file) first, then `<dist>/<path>/index.html`. Treat an exact file as a page, or as a redirect when it carries Astro's stub shape or a plain meta refresh.

**Done when.**
- A fixture serves `/section/index.html` from the section's own page and `/old.html` from a flat stub; both are covered.
- A flat stub to a dead target fails.
- The existing directory-stub behaviour is unchanged.

**Evidence.**
- Spike results 4 and 7 (spike evidence, Results table): `/guides/index.html` and `/index.html` were reported uncovered.
- With flat stubs, all six `.html` URLs were reported uncovered, although an emulation of GitHub Pages served every one of them.

**spec-kitty shim meanwhile.** The gate runs with a generated `--redirects` override that maps each `dir/index.html` to `dir/`. It is gate-only, never used by the site. A mutant with a dead target fails.

---

## (c) Render GitHub alert syntax (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`)

**Size:** S · **Consumer:** spec-kitty (7 files today; authors write GitHub-flavoured Markdown that also renders on github.com)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.** A GitHub alert renders as a plain blockquote with the marker as literal text: `<blockquote><p>[!NOTE] A GitHub alert.</p></blockquote>`. Starlight asides (`:::note`) and Markua render fine, but they do not render on github.com, where these docs are also read.

**Evidence.** Spike result 10.

**Proposal.** A remark plugin, on by default or behind a flag, that turns the five GitHub alert types into the same aside component Starlight and Markua use, with the same tokens and accessible label. The output must be identical whichever syntax the author used.

**Done when.** Each of the five types renders as an aside in the example; a blockquote that merely starts with `[!` text that is not an alert type stays a blockquote; an axe check passes.

**spec-kitty shim meanwhile.** None. The 7 files render the marker as text until this lands, or the migration rewrites them to `:::note`.

---

## (d) Nested persona slugs in `audience.profile`

**Size:** S · **Consumer:** spec-kitty (personas under `context/audience/internal/` and `context/audience/external/`)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.** spec-kitty groups personas into `internal/` and `external/` subfolders, so the natural profile is `internal/maintainer`. `resolveProfile` resolves `context/audience/${profile}` by string concatenation, and `humanizeProfile` splits on `/`, so it may already work; it is untested, and no doc covers it. The frontmatter validator's persona checks and the persona hub listing are not known to handle a nested path.

**Evidence.** Code reading only (`src/lib/metadata.ts`, `resolveProfile`); the spike did not exercise personas.

**Proposal.** State in the contract that a profile slug may contain `/`. Add a fixture with nested personas covering resolution, the label, the persona hub, the validator's `kind: Persona` checks and broken-profile detection.

**Done when.** That fixture passes, and a nested profile that does not exist fails the validator with its full path in the message.

**spec-kitty shim meanwhile.** None needed if it already works. The migration step checks it on the scaffold build.

---

## (e) Multi-file Contextive glossary (`imports:`) and a configurable glossary path

**Size:** M · **Consumer:** spec-kitty (glossary split by bounded context; its source is being settled in spec-kitty/spec-kitty#3024)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.**
- The glossary loader reads exactly one `<cwd>/.contextive/definitions.yaml`. For a site in a sub-project (`site/`), that is `site/.contextive/`, not the repository's `.contextive/`.
- Contextive's `imports:` key, which splits a glossary across files, is silently ignored, as are other unknown top-level keys.

**Evidence.** Code reading (`src/lib/glossary/load.ts`, `load.internal.ts`); the spike did not enable a glossary.

**Proposal.**
- A `glossary: { path }` option on `defineDocKittyIntegrations`, resolved against the Astro root.
- Follow Contextive `imports:` (relative paths and URLs Contextive allows, local files only at build time), with cycle detection.
- Warn on unknown top-level keys instead of ignoring them.
- Let the site choose where generated term pages go. Today they are written into `<docsDir>/glossary/`, which for a `docsDir` outside the site project means inside the consumer's source tree.

**Done when.** A fixture glossary split across three files with `imports:` renders the same terms as the merged single file; a cycle fails the build with the chain named; `glossary.path` pointing outside the site project works.

**spec-kitty shim meanwhile.** Not needed for the migration. Per the operator's decision ([comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324)), spec-kitty generates one `definitions.yaml` into `site/.contextive/` from the source spec-kitty/spec-kitty#3024 settles.

---

## (f) Exclude sections or path prefixes from the build

**Size:** S/M · **Consumer:** spec-kitty (`archive/`, `reports/`, `convergence/` and retired-surface pages live in `docs/` and must never publish)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.**
- The docs loader's `pattern` must be the default, and nothing else excludes content: only drafts (`DK_PUBLISH_DRAFTS=off`), `_meta` and dot folders are left out.
- `feeds` filters only sitemap, RSS, `llms.txt` and the agent API.
- A repository that keeps historical material next to its live docs therefore publishes all of it. Pages with `doc_status: deprecated` are built, linked from hubs and exported.

**Proposal.** An `exclude` option, a list of route prefixes or globs relative to `docsDir`, on `defineDocKittyIntegrations`, or an `unpublished: true` flag on a `sections.yaml` entry. Excluded content must be absent from every output: pages, hubs, the sidebar, the sitemap, RSS, `llms.txt`, the agent API, the OKF export (doc-kitty's agent-facing Markdown export), the content graph and search. The link checker must report a published page that links into excluded content.

Exclusion must apply **before** schema validation: a consumer-side loader filter cannot do this, because the glob loader validates every entry first, so an excluded page with incomplete frontmatter still fails the build (spike result 14: 31 such pages).

**Done when.** A fixture with an excluded section shows none of its pages in any of those outputs, and a link into it from a published page is reported. An excluded page with frontmatter that would fail the schema does not fail the build.

**Evidence.** Spike result 9 (spike evidence, Results table). Without a filter, an archived page was built and appeared in two hubs, the OKF export and the content graph.

**spec-kitty shim meanwhile.** `site/src/content.config.ts` wraps `docKittyDocsLoader` and deletes the excluded route prefixes from the store after load. The spike showed this removes the page from every output listed above. The shim is removed when this lands.

---

## (g) Mission pages and glossary pages as a hub-style grid of cards, styled with the site-chrome ("chromed") design system

**Size:** M · **Consumer:** spec-kitty (operator request, [spec-kitty/spec-kitty#6100 decisions](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324), item 3)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.**
- spec-kitty's DocFX site had generated mission dashboards: a card per mission, with status, linking to per-mission pages, plus a glossary page with term cards. Those are dropped in the migration.
- doc-kitty's `kind: Hub` renders the child pages one level down as a described-link list, not a grid.
- It has no card treatment for a glossary.

**Proposal.**
- A card-grid presentation for hubs, opted into by a hub's frontmatter (for example `hub_layout: cards`) or by the section registry. Each card shows the child page's title, description and a small set of declared fields (for example `doc_status`, `updated` and a status badge).
- The same card component for glossary terms on the glossary page, grouped by context.
- Styled with the site-chrome design system (`specKittyTheme`, the `--dk-*` tokens), light and dark, so mission and glossary pages read as one system with the rest of the site.

**Done when.**
- The example has a card-grid hub and a card glossary page in both colour schemes.
- Cards are keyboard-navigable and pass axe.
- A list hub's existing output is unchanged.

**spec-kitty shim meanwhile.** None. Mission pages return to the spec-kitty site when this lands (a sub-issue of spec-kitty/spec-kitty#6100).

---

## (h) A preamble option for the generated `llms.txt`

**Size:** S · **Consumer:** spec-kitty (operator decision, [comment](https://github.com/spec-kitty/spec-kitty/issues/6100#issuecomment-6544333324) item 3: the generated `llms.txt` keeps spec-kitty's version-stance text)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.** `llmsTxtRoute({ title, description })` writes `# title` and `> description`, then the sections. A site cannot add the free-text block the llmstxt.org format allows between the summary and the sections. spec-kitty states its version stance there: which docs are current, the runtime model, the governance source, the mission loop command, and where historical 1.x and 2.x pages live.

**Proposal.** A `preamble` option (a Markdown string, or a path to a Markdown file resolved against the site root), written after the `>` summary and before the first section.

**Done when.** The example's `llms.txt` carries a preamble block in the right position, and output without the option is byte-identical to today's.

**spec-kitty shim meanwhile.** `site/src/pages/llms.txt.ts` wraps the route's response and inserts the block after the summary line.

---

## (i) Test a `docsDir` outside the Astro project (`docsDir: '../docs'`)

**Size:** S · **Consumer:** spec-kitty (`site/` sub-project; `docs/` stays at the repository root)

**Context.** spec-kitty is moving docs.spec-kitty.ai from DocFX to doc-kitty (spec-kitty/spec-kitty#6100; decision record: [ADR 2026-10-31-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md)). Evidence comes from a throwaway build against doc-kitty commit `494f2d878e2e4766d9859a4f073efb793ad86900`: [spike evidence](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md).

**Problem.** `consumer-setup.md` describes docs inside the site project, or two folders below it. Nothing tests a docs root that is a sibling of the site project. The generated sidebar prefixes autogenerate directories with `docsDir` to match Starlight's `filePath`, and a `../` prefix there is untested.

**Evidence.** Spike results 1 and 14 (spike evidence, Results table). An 8-page `../docs` site built with correct section indexes, and the real spec-kitty tree, nested several levels deep, built 637 pages with `docsDir: '../docs'`. Edit links and the gates' config discovery were not checked; without `--astro-config` the gates look for the site config in the docs root's parent and fall back to the default index name.

**Proposal.** A consumption fixture with `site/` and a sibling `docs/` covering the sidebar (nested sections), edit links, the gates' `--astro-config` discovery, `llms.txt` and the OKF export. Add a short "docs outside the site project" section to `consumer-setup.md`.

**Done when.** That fixture builds and passes every gate in doc-kitty's CI.

**spec-kitty shim meanwhile.** None. spec-kitty's own `docs-site` job builds this layout on every pull request.
