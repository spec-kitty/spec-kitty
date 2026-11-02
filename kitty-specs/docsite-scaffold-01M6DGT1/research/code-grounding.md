# Code grounding: docsite scaffold (#6930)

Read-only grounding run on `origin/main` at `49030397` (2026-11-02), before specifying.

## Router wiring

- **Two authorities, one parser.** `.github/workflows/ci-router.yml` has a dorny `changes` filter block (group -> globs) and job `if:` gates (group -> job). `scripts/ci/gate_selection.py::load_router` parses both straight from the YAML (`_dorny_filters`, `_job_gates`); there is no second hand-written map. A filter group is "registered in `gate_selection.py`" by appearing in the filter block, and is gated by a job's `needs.changes.outputs.<group>` reference.
- **`_GROUP_REF` pitfall.** `_GROUP_REF = re.compile(r"needs\.changes\.outputs\.([A-Za-z0-9_]+)")` reads ANY `needs.changes.outputs.<name>` in a job's `if:` as a routing group. A new output on `changes` that is not a filter group would be mis-parsed as one. So the new group name must be both a filter-block key and a `changes.outputs` entry, and the job's `if:` must reference nothing else under `needs.changes.outputs`.
- **Non-src vs src-backed.** `Router.src_backed_groups` is every group with a `src/` glob. Src-backed groups join the FR-004 `unmatched` union in the `changes` job and the heavy battery's `if:`. A docs/site group must carry no `src/` glob and stay out of that union (`tests/ci/test_mission_state_audit_routing.py` shows the pinned shape for a non-src group gating one job).
- **Outputs fold.** Every group's `changes.outputs.<group>` row folds in full mode and `unmatched` (`(inputs.mode == 'full' || steps.unmatched.outputs.unmatched == 'true') && 'true' || steps.filter.outputs.<group>`).
- **#6996 rule** (CI routes every architectural gate whose scan scope a PR touches): `arch_scan_scope` is a transcription of `gate_selection.battery_scope_router_globs()` from `.github/ci-module-registry.yml` `special_tiers.architectural.scan_scopes`. It already lists `docs/**`. `site/**` is in no scan scope, so a `site/**`-only change selects no battery leg; nothing in this mission needs an architectural gate to read `site/`. The new Python helper under `scripts/docs/` is already in `scripts/**` (scan scope), and `tests/**` covers its test.
- **Scrub registry.** `tests/release/ci_retirement_scrub.json` `non_src_router_groups` documents non-src groups (`docs`, `corpus`, `e2e`, `mission_state`) with `roots` equal to the router globs; per-group tests pin the equality. The new group gets a row.
- **Router tests.** Tests reading the router: `tests/ci/*` (notably `test_fork_guard.py`, `test_docs_lint_job.py`, `test_mission_state_audit_routing.py`, `test_ci_module_wiring.py`, `test_workflows_sync_packs.py`, `test_pause_ci_label.py`, `test_merge_queue_wiring.py`, `test_skip_if_green_wiring.py`) and the architectural router gates (`test_gate_selection_authority.py`, `test_ci_quality_path_filters.py`, `test_ci_router_transcription_guards.py`, `test_ci_integrity_oracle_nonvacuous.py`, `test_no_duplicate_suite_execution.py`, `test_battery_scan_scope_routing.py`, `test_local_gate_parity.py`, and the others listed by `grep -rl 'ci-router.yml\|gate_selection' tests/architectural`).
- **Fork guard.** `tests/ci/test_fork_guard.py` requires the canonical guard as the first `&&` conjunct on every job that can start on its own (root job with no `needs`, or `always()`). A job with `needs: [changes]` skips with the guarded `changes` job (which also carries the `pr:pause-ci` guard), as `mission-state-audit` does.
- **Release ownership.** `tests/release/test_release_ci_ownership.py` pins `docs-pages.yml` (probe-then-configure, main-only deploy). This mission does not touch `docs-pages.yml` (DocFX keeps deploying). Note: `docs-pages.yml` already triggers on `site/moves.yaml` and `site/url-baseline.txt` (DocFX reads them); other `site/**` files do not trigger it.
- **`router-gate`.** Its `needs:` is the required set; the new job stays out of it until #6937.

## Toolchain

- Root `package.json` is a maintenance manifest (`all-contributors-cli`) with an npm `package-lock.json`. `site/` stays separate with its own `package.json` and `pnpm-lock.yaml`.
- Local: Node v22.23.4, pnpm 10.28.0 (the toolchain the #6929 one-off build used). doc-kitty `src/package.json` at `45e455b` (= doc-kitty `main` HEAD on 2026-11-02): `@spec-kitty/doc-toolkit` 0.6.0, `engines.node >=22.22.0`, peers `astro >=7.2.10 <8`, `@astrojs/starlight >=0.42.0 <0.43.0`, `@astrojs/markdown-remark >=7.3.0 <8`. doc-kitty's own repository uses pnpm 11 (`allowBuilds`); with pnpm 10 the build-script allow-list is `pnpm.onlyBuiltDependencies` (`esbuild`, `sharp`).
- **Codespell scope.** `scripts/docs/check_spelling.py` scans only `docs/` (typos), `README.md`, and `docs/guides` + `docs/context` (US spelling). `site/` is outside every root, so `site/node_modules` and `site/dist` need no codespell skip.
- **Ruff scope.** Repository-wide; `site/` holds no Python. `node_modules/` and `dist/` are already gitignored globally (`.gitignore`); Astro's `site/.astro/` cache needs an entry.

## Packaging

`pyproject.toml` `[tool.hatch.build.targets.sdist]` excludes `site/**` since #6926/#7007, and `tests/cross_cutting/packaging/test_packaging_safety.py::_SDIST_FORBIDDEN_TREES` includes `"site/"` (built-archive assertion plus `test_sdist_config_anchors_the_root_documents_and_excludes_site`). The wheel ships only declared packages. No packaging change is needed; the suite is re-run as a guard.

## Build reproduction

- Spike: `kitty-ops/research/01M6947JAAGSMJTM6ST9D429BG/spike-evidence.md`. #6929: `kitty-specs/docsite-frontmatter-migration-01M6BRJK/build-evidence.md` — `pnpm install`, `DK_PUBLISH_DRAFTS=off pnpm exec astro build`, exit 0, **640 pages**, with `exclude: ['archive','reports','convergence','changelog/unreleased']` and `indexBasename: ['README','index']`, `docsDir: '../docs'`, `docKittyDocsLoader({ base: '../docs' })`.
- **Shim decision.** doc-kitty's native `exclude` (doc-kitty #247/#252, ADR-0070 there) replaces the spike's section-exclusion shim in `src/content.config.ts`; #6929 verified the excluded folders need no frontmatter backfill with it. `exclude` and `indexBasename` must not be passed to the loader (it reads them from the integration; a custom `pattern` throws). **No shim.**
- **Single authority.** `scripts/docs/_dockitty_contract.py` owns `EXCLUDED_FOLDERS` and `INDEX_BASENAMES` and says the site scaffold takes them from there. `astro.config.mjs` cannot import Python, so the site reads a generated, committed `site/dockitty-contract.json`, and a test asserts it equals the module (parity, plus a drift negative control).
- **Gates.** `dockitty-validate-frontmatter` and `dockitty-check-links` are still red on the tree (#6929 evidence: `kind`/`updated` required; 117 body links) — completion is #6931/#6937. This job therefore runs the build only; the `--astro-config` invariant (ADR D-1) is enforced as a structural check over the workflow and Makefile so the gates #6937 adds cannot omit it.
- **Redirects.** doc-kitty #253 (`legacyHtmlRedirects`, ADR-0071) makes Astro `.html` redirect keys fatal on static output. The scaffold sets no `redirects` and leaves `legacyHtmlRedirects` unwired (#6933).
- **Diagrams.** PlantUML in doc-kitty's build mode fails the build with no server; auto-detection switches to build mode wherever a Chromium exists. The scaffold sets `diagrams: false` (deterministic, no PlantUML egress); #6936 turns diagrams on with the pinned service.
- **404.** doc-kitty has no 404 convention; Starlight's built-in 404 is used unless the site provides `src/pages/404.astro` — the scaffold adds one carrying the `/kitty-specs/` notice.

## Known baseline red

#7022 (18 `make test-fast` failures on `287a226cfe`) is **closed**, fixed by PR #7058 (2026-11-02). Classified per the CLAUDE.md gotcha at run time; any red is re-checked on `origin/main` before being attributed.

## Churn (90 days)

`git log --since='90 days ago' --oneline -- <path> | wc -l`: `.github/workflows/ci-router.yml` 2, `scripts/ci/gate_selection.py` 2 (counted on this branch's history; both are hot through squash-merged PRs, so the edit is kept to an additive group, output row and job).
