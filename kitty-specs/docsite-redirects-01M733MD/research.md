# Research: Docsite legacy redirects

The full code grounding is in [research/code-grounding.md](research/code-grounding.md).

## Decisions

- **R-1 Mechanism.**
  - Decision: doc-kitty's `legacyHtmlRedirects` with a committed flat JSON map, `site/legacy-redirects.json`.
  - Rationale: Astro `.html` redirect keys are fatal on static output (#253), and all 970 baseline routes end in `.html`.
  - Rejected: Astro `redirects`, and doc-kitty's `dockitty-generate-legacy-redirects`, which maps `README.html` to `README/` and knows nothing about drafts.
- **R-2 Gate override retired.**
  - doc-kitty v0.7.0 maps `/a/index.html` to the file `/a/` serves.
  - Measured: 970/970 covered with no `--redirects` override.
- **R-3 Rule 4 in the generator.** While DocFX still publishes drafts, a `moves.yaml` row `draft.html -> hub` fails DocFX's `validate()`, which rejects a source that is a published page. Rule 4 therefore reads `unpublished_routes()` in the generator.
- **R-4 Stub exemption.**
  - Measured: a build with the map gives 4091 built-site findings, all of them stubs.
  - One predicate in the contract, mirroring doc-kitty's `REDIRECT_STUB_RE`, exempts them from `page` and `render`.
  - The `link` surface keeps refusing a stub whose target is unpublished.
- **R-5 Resources.**
  - `docs/assets/spec-kitty-backlog.html` and `docs/assets/spec-kitty-evolution-v1-to-v3.html` are DocFX resources that doc-kitty does not publish.
  - Operator ruling 2026-11-10: redirect both to the hub.
  - Encoded as a rule, not a list: a baseline route backed by a non-`.md` file under `docs/` goes to its nearest live ancestor.
- **R-6 Self-test as a job step.** Node is not on the pytest module shards. The real-gate mutants run as `site_redirects selftest site/dist` in the job. Its verdict matching is unit-tested with an injected gate command.
