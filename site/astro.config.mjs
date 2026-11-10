// docs.spec-kitty.ai, built with doc-kitty (ADR docs/adr/4.x/2026-10-31-1, D-1).
//
// `site/` is a sub-project; the pages stay in `../docs`. The folders the site leaves out and
// the section index basenames come from scripts/docs/_dockitty_contract.py, the single
// authority, through the generated dockitty-contract.json (`python -m scripts.docs.site_contract`).
// Every dockitty-* gate must be run with `--astro-config astro.config.mjs` so it reads them.
//
// llms.txt and the agent index are pages (src/pages/llms.txt.ts, src/pages/api/index.json.ts; #6934).
// GitHub alerts (`> [!NOTE]`) render as asides (#6935). No `starlight.head` here: it replaces the
// toolkit's head entries (spec-kitty/doc-kitty#295).
//
// Not wired here yet: redirects (#6933; Astro `.html` redirect keys are fatal on static output)
// and diagrams (#6936, needs the pinned PlantUML service).
import { readFileSync } from 'node:fs';
import { defineConfig } from 'astro/config';
import { defineDocKittyIntegrations } from '@spec-kitty/doc-toolkit/config';

const contract = JSON.parse(readFileSync(new URL('./dockitty-contract.json', import.meta.url), 'utf8'));

export default defineConfig({
  site: 'https://docs.spec-kitty.ai',
  base: '/',
  integrations: defineDocKittyIntegrations({
    title: 'Spec Kitty',
    description: 'Spec Kitty documentation: governed, spec-driven delivery from agreed intent to a verified result.',
    docsDir: '../docs',
    base: '/',
    indexBasename: contract.indexBasename,
    exclude: contract.exclude,
    diagrams: false,
    githubAlerts: true,
    starlight: { disable404Route: true },
  }),
});
