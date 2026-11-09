# Research: Docsite publication rules, llms.txt and render parity

Grounding: [research/code-grounding.md](research/code-grounding.md). Operator decisions: four Decision Moments (2026-11-09) in `decisions/`.

## R-1: Unpublishing single pages
- **Decision:** move retired hosted/sync pages (and `sync-workspaces`) under `docs/archive/<section>/` with `site/moves.yaml` rows to the section hub (D-5 rule 4); working-note folders become `doc_status: draft`.
- **Rationale:** doc-kitty `exclude` takes folders only (`src/lib/config.ts:336-338`); the operator chose archive moves for retired pages; plans bodies are immutable so drafts are frontmatter-only.
- **Alternatives:** draft frontmatter on retired pages (rejected by operator); a per-file exclude upstream (filed as a gap, not awaited).

## R-2: Proof of publication
- **Decision:** a stdlib built-site check over `site/dist` with one mutant fixture per surface, run in the shared build after `pnpm run build`.
- **Rationale:** #7484 — evidence over the built artifact, not configuration restatements; pytest cannot build the site, so the real check runs in CI and the fixtures prove the check itself.
- **Alternatives:** doc-kitty's internal `assert-build-artifacts` (not exported); YAML-shape tests (rejected, #7484).

## R-3: `llms.txt` stance and the machine index
- **Decision:** thin wrapper page over `llmsTxtRoute` that inserts the stance after the header; stance text lives in the contract module and is projected to JSON; mount `agentIndexRoute` at `/api/index.json`.
- **Rationale:** no preamble option at v0.7.0 (doc-kitty #265); the route always prints the machine-index line (`llms-txt.ts:108`); operator chose mounting the index.

## R-4: Render parity
- **Decision:** `githubAlerts: true`; SEO tags proven per page by the check; parity checklist maps each `seo_verify.py` rule to its doc-kitty equivalent or an upstream issue.
- **Rationale:** Starlight + doc-kitty already emit description, canonical, og:*; alerts need one flag; #295 forbids `starlight.head`.

## Supply chain
No new package or action. doc-kitty remains pinned at `5acb83c` (v0.7.0).
