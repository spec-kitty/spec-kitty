<!-- Read-only grounding, 2026-11-10. -->
# Grounding for #6936: docsite diagrams through doc-kitty v0.7.0

Read-only research. Branch `issue-6936-docsite-diagrams` (HEAD `6beaca4c3`, on top of PR #7501).
doc-kitty pin `5acb83c099cde169e5e24d2f42d4012cb356a3ab` (v0.7.0). The installed toolkit is at
`site/node_modules/@spec-kitty/doc-toolkit/` (called `TK/` below). doc-kitty repo paths are `5acb83c:<path>`.

## TL;DR (blocking findings first)

1. **BLOCKER (likely): 5 of the 8 published PlantUML blocks are `@startyaml`, and doc-kitty v0.7.0 does not support them.**
   - `TK/lib/remark/plantuml-meta.internal.ts:186-215` (`injectSkinparam`) knows only `@startuml` and `@startjson`. Any other source gets the `skinparam` preamble *prepended*.
   - `astro-plantuml@1.0.0` `dist/render.js:25-35` (`encodePlantUmlForUrl`) then wraps any text that does not start with `@startuml` in `@startuml … @enduml`.
   - A `@startyaml` block is therefore sent as `@startuml / skinparam… / @startyaml … @endyaml / @enduml`. That is almost certainly a PlantUML error.
   - A render error fails the build: `TK/lib/rehype/diagram-figure.ts:352-360` throws "astro-plantuml failed to render a plantuml diagram".
   - Affected: `docs/architecture/doctrine-kinds.md:56,82`, `doctrine-relationships.md:46`, `mission-type-resolution.md:229,260`.
   - Not verified against a live server: the docker CLI is installed here (v29.9.2), but no daemon runs (`/var/run/docker.sock` is missing).
   - `git grep startyaml` over doc-kitty `5acb83c` (`src`, `docs`, `CHANGELOG.md`) finds nothing, so this is an **upstream gap; check upstream / file one**.
   - The ADR 2026-08-12-1 lane exists *for* `@startyaml` schema diagrams.
2. **`--service-container` on a GitHub-hosted runner is solved.**
   - Use `"${{ job.services.plantuml.id }}"`, exactly as doc-kitty's own CI does (`5acb83c:.github/workflows/ci.yml:258-264`).
   - The generated container name is never needed. `plantuml-service-config.mjs:16` says "All work with a GitHub Actions service id or a container name".
   - The gateway for `--canary-host` comes from `docker inspect -f '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}' <id>`.
   - doc-kitty #287 (asserting the service without inspecting a container) is **not needed**: our service is an inspectable Docker container. See §2.5.
3. **Playwright is not installed in `site/` today.**
   - `site/node_modules/.pnpm` holds no `playwright*`.
   - `mermaid-isomorphic@3.1.0` declares `playwright: "1"` as an *optional peer*.
   - The mission must add an exact-pinned `playwright` to `site/package.json`, plus a lockfile update. doc-kitty tests against `@playwright/test` 1.62.1 (`5acb83c:package.json:69`).
   - The consumer guide says only "the toolkit does not install Playwright" (`consumer-setup.md:1113-1116`) and never names the package to add: **upstream doc gap (check upstream)**.
4. **`DK_DIAGRAM_BUILD_RENDER` and `DK_PLANTUML_SERVER_URL` must go in the process environment (job `env:` and Makefile), not in `site/.env.production`.**
   - Both are read from `process.env` only: `TK/lib/integrations/diagrams.ts:151-155,345-349`.
   - Only `DK_PUBLISH_DRAFTS` has the env-file resolution (`TK/lib/integrations/draft-publication.ts:34-81`).
5. **The `plantuml-guard` check has no bin.**
   - `TK/scripts/plantuml-guard.mjs` is a library: it exports `checkPlantumlSources(libDir)` and `PLANTUML_COM_URL_RE`.
   - doc-kitty's `assert-build-artifacts.mjs` runs it against `REPO_ROOT/src/lib` (lines 38, 588). That script is doc-kitty's own example-site gate, not a consumer tool.
   - Core can run it through the `./scripts/*` export (`TK/package.json` exports) with a thin wrapper: `node -e` or a small `.mjs` that calls `checkPlantumlSources(<resolved TK>/lib)` and exits non-zero on `ok:false`.

---

## 1. Current state (core)

| File | Lines | State |
|---|---|---|
| `site/astro.config.mjs` | 12-13 | Comment: "Not wired here yet: redirects (#6933 …) and diagrams (#6936, needs the pinned PlantUML service)". |
| `site/astro.config.mjs` | 29 | `diagrams: false,`. This is the line to flip. |
| `site/.env.production` | 1 | `DK_PUBLISH_DRAFTS=off` only. Do **not** add the diagram variables here (TL;DR 4). |
| `site/package.json` | 15-20 | deps: toolkit `github:spec-kitty/doc-kitty#5acb83c…&path:/src`, `astro >=7.2.10 <8`, `@astrojs/starlight >=0.42.0 <0.43.0`, `@astrojs/markdown-remark >=7.3.0 <8`. **No `playwright`.** |
| `site/package.json` | 21-26 | `pnpm.onlyBuiltDependencies: [esbuild, sharp]`. The `playwright` npm package needs no install script; browsers come from `playwright install`. |
| `.github/workflows/docs-site-build.yml` | 34-38 | Job `build`: `ubuntu-24.04`, `timeout-minutes: 20`, no `services:`, no job `env:`. |
| `.github/workflows/docs-site-build.yml` | 39-93 | Steps in order: checkout (SHA-pinned) → site_contract check → pnpm/action-setup → setup-node (pnpm cache) → `pnpm install --frozen-lockfile` → frontmatter gate → source link gate → `pnpm run build` (l.68-70) → `site_built_check` (l.71-75) → built link gate → upload. |
| `.github/workflows/docs-site-build.yml` | 30-31 | `permissions: contents: read`, `workflow_call` only. |
| `.github/workflows/ci-router.yml` | 1776-1780 | Caller `docs-site:` (`needs: [changes]`, `if: docs_site == 'true'`, `uses: ./.github/workflows/docs-site-build.yml`). |
| `.github/workflows/ci-router.yml` | 456-464 | `docs_site` path filter. |
| `Makefile` | 45-52 | `docs-site` target: mirrors CI line by line, with no PlantUML service and no Chromium. |
| `Makefile` | 54-56 | `docs-site-bump` (`scripts/docs/site_bump.py`; keeps unrelated deps, `bump_manifest` l.109-125). |

**Path-filter gap (pre-existing).** `ci-router.yml:456-464` lists `scripts/docs/site_built_check.py` but **not** `site_built_check_render.py` or `site_built_check_llms.py`, both added by #7501. A change to those modules alone does not trigger the `docs-site` build. A new `site_built_check_diagrams.py` would have the same problem.
- Prefer a glob `scripts/docs/site_built_check*.py`.
- `tests/ci/test_docs_site_job.py:134-138` requires the scrub copy (`non_src_router_groups`) to match the filter exactly, so update both.

**Current built output** (`site/dist`, built 2026-11-10, client mode with diagrams off):
- 24 `data-language="mermaid"` code blocks on 11 pages.
- 8 `data-language="plantuml"` code blocks on 4 pages.

These are the counts the acceptance check must drive to zero.

**Local `make docs-site`.** The target needs four things it does not have today:
1. A running service. Use the same digest, hardened as in the consumer guide (`5acb83c:docs/guides/consumer-setup.md:1167-1170`):
   ```sh
   docker run -d --name plantuml -p 127.0.0.1:8091:8080 \
     -e PLANTUML_SECURITY_PROFILE=SANDBOX \
     plantuml/plantuml-server:jetty-v1.2026.9@sha256:065c66adc6728ba6dd353a29d4ada73f8358b68549a0f710c4bf46b43c103618
   ```
2. The canary. Locally, use `--service-container plantuml` and the `docker inspect` gateway (guide l.1187-1192).
3. Chromium: `pnpm --dir site exec playwright install chromium` (on a bare host, also `playwright install-deps chromium`).
4. The two variables exported: `DK_DIAGRAM_BUILD_RENDER=build`, `DK_PLANTUML_SERVER_URL=http://localhost:8091/svg/`.

Suggestion: add a `docs-site-plantuml` helper target, or a preflight that fails with the `docker run` line when `:8091` does not answer. Do not silently fall back to client mode.

**This container:** the docker CLI exists (29.9.2), but no daemon runs, and `~/.cache/ms-playwright` is absent. A full diagram build is not possible here; it must be proven in CI.

## 2. doc-kitty v0.7.0 diagram pipeline

### 2.1 `diagrams` option
- `5acb83c:docs/guides/consumer-setup.md:1058-1068`: `diagrams: true` draws them. Left out or `false` (the default) shows code blocks, and `false` ≠ client render.
- `TK/lib/config.ts:242` says the mode comes from `DK_DIAGRAM_BUILD_RENDER` or Chromium auto-detection.

### 2.2 `DK_DIAGRAM_BUILD_RENDER`
- `TK/lib/integrations/diagrams.ts`:
  - **114-119**: `PLAYWRIGHT_CANDIDATES = ['playwright','playwright-core','@playwright/test']`.
  - **126-141**: `chromiumResolvable()`: `createRequire` → `chromium.executablePath()` → `existsSync`.
  - **151-156**: `resolveDiagramMode(process.env)`. Values `1/on/build/yes/true` give build; `0/off/client/no/false` give client; anything else auto-detects.
- A pinned build mode does not fall back: without Chromium the build fails (guide l.1122-1124).
- Build branch (`diagrams.ts:478-563`):
  - `@beoe/rehype-mermaid` is loaded via `loadBeoe` (it statically imports `playwright` through `mermaid-isomorphic`).
  - The disk cache `withMermaidDiskCache` uses `DK_BEOE_CACHE_DIR`.
  - `astro-plantuml` `createRemarkPlugin({serverUrl: resolvePlantumlServerUrl(), format:'svg'})`.
  - Remark plugins: `[diagramMeta, plantumlMeta, plantumlRemark]`. Rehype plugins: `[cachedMermaid, sentinelThemeRewrite, diagramFigure]`.
- Client branch (`diagrams.ts:565-590`): `mermaidFenceTransform` plus an injected client render script. PlantUML stays code (guide l.1133-1134).
- Resolution of `playwright` with pnpm: `createRequire(TK/lib/integrations/diagrams.ts)` walks up to `site/node_modules` (and pnpm's hoisted `.pnpm/node_modules`), so a site-level `playwright` dependency is found. `mermaid-isomorphic`'s optional peer is satisfied by the same dependency.

### 2.3 `DK_PLANTUML_SERVER_URL`
- `diagrams.ts:324` sets `DEFAULT_PLANTUML_SERVER_URL = 'http://localhost:8091/svg/'`.
- `diagrams.ts:327-335` (`assertSelfHostedPlantuml`) throws on `plantuml.com`.
- `diagrams.ts:345-350` (`resolvePlantumlServerUrl`) reads only `process.env`.
- Render errors fail the build: `TK/lib/rehype/diagram-figure.ts:232-250` (`plantumlErrorRaw`) and `:352-360` (throw). `astro-plantuml`'s `remark-plugin.js:48-53` catches the axios error and emits `<div class="plantuml-error">`, which `diagram-figure` turns into a throw.

### 2.4 `plantuml-guard.mjs` (library, not a bin)
- `TK/scripts/plantuml-guard.mjs:1-53` exports `PLANTUML_COM_URL_RE` and `checkPlantumlSources(libDir)`.
  - It scans `.ts/.mjs/.js` under `libDir` for a plantuml.com URL.
  - It requires a self-hosted `DEFAULT_PLANTUML_SERVER_URL` definition.
  - It returns `{ok,…}` and never exits.
- Callers: only `TK/scripts/assert-build-artifacts.mjs:38` (doc-kitty-internal; uses `TOOLKIT_LIB_DIR = REPO_ROOT/src/lib`, l.588). It is not in `bin` (`TK/package.json` bin list has 11 entries; neither of these is one).
- It is importable as `@spec-kitty/doc-toolkit/scripts/plantuml-guard.mjs` (exports `"./scripts/*"`).
- Core wrapper: resolve the toolkit dir, call `checkPlantumlSources(<TK>/lib)`, exit 1 with the message.
- **Value caveat:** it checks the *toolkit's* source, not core's. Its lasting value is a pin-bump regression guard. Pair it with a built-site assertion that no built page names `plantuml.com`, which tests our output.

### 2.5 `dockitty-assert-plantuml-no-remote-include` (bin, `TK/scripts/assert-plantuml-no-remote-include.mjs`)

**Flags** (l.6-12, 60-61):

| Flag | Meaning |
|---|---|
| `--server` | Default `DK_PLANTUML_SERVER_URL`, then `http://localhost:8091/svg/` (l.163). |
| `--canary-host` | The address the service uses to reach the runner. |
| `--service-container` | Docker id or name of the service container. |
| `--canary-port` | Fixed canary port; random when absent. |
| `--astro-config` | Evaluates the site config for `plantumlAllowExternal`. Needs the site deps installed (l.108-145). |
| `--print-declared` | Prints the declared mode and exits. |

**Exit codes:** 0 pass, 1 failed check, 2 usage or configuration error. An empty flag value is exit 2 (l.76-78).

**Sandbox path** (`checkUnset`, l.170-224):
1. The canary listens on `0.0.0.0` (`plantuml-include-guard.mjs:137`).
2. Control: a plain diagram must render.
3. With `--service-container`, the probe `docker exec <c> curl -sf --max-time 5 -o /dev/null <canary>/reachability` proves the canary is reachable (`plantuml-include-guard.mjs:225-229`).
4. Two fixtures must render as errors with zero canary hits: `scripts/fixtures/plantuml-remote-include/includeurl.puml` and `include-url.puml`.
5. After a pass, it reads the container:
   - `checkServiceIdentity` (ports + network mode);
   - `checkUnsetProfile` (`plantuml-mode-check.mjs:530-536`): `PLANTUML_SECURITY_PROFILE === 'SANDBOX'` exactly, and no channel failures (`plantuml.*` env keys, `-D` security props, `PLANTUML_PROPERTY_FILE`, `@argfile`).
6. Without `--service-container` it only prints a "not proven" note (l.217-219).

**docker calls:** these five argv shapes only (`TK/scripts/plantuml-service-config.mjs:6-10`):
```
docker inspect --type container -f '{{json .Config.Env}}' <c>
docker inspect --type container -f '[{{json .Config.Entrypoint}},{{json .Config.Cmd}},{{json .Args}}]' <c>
docker inspect --type container -f '{{json .NetworkSettings.Ports}}' <c>
docker inspect --type container -f '{{json .HostConfig.NetworkMode}}' <c>
docker exec <c> curl -sf --max-time 5 -o /dev/null <url>
```
- The image must therefore carry `curl`. The pinned jetty image does, since doc-kitty's CI passes with it.
- The port check: `--server http://localhost:8091/svg/` requires the container to publish 8091 on `0.0.0.0`/`::` or loopback (guide l.1431-1438). The `ports: - 8091:8080` service mapping satisfies it.

**Name on GitHub runners:** `${{ job.services.plantuml.id }}` (doc-kitty `ci.yml:260,264`; allowlist lane `:420`). `docker` on the runner host talks to the same daemon, because the job is not containerized.
- Do **not** move the build into a `container:` job (for example the Playwright image). The service would then be reached by name, not localhost, the identity check would only note "not verified", and the job container would have no docker CLI.

**`--astro-config` interaction with core's test:** `tests/ci/test_docs_site_job.py:47-48,267-277` (`_DOCKITTY_CALL = r"\bdockitty-[a-z-]+\b"`) requires **every** line that calls a `dockitty-*` binary in `ci-router.yml`, `docs-site-build.yml` and `Makefile` to carry `--astro-config astro.config.mjs`.
- So core must run the check as `pnpm exec dockitty-assert-plantuml-no-remote-include … --astro-config astro.config.mjs`, **after** `pnpm install`, with `working-directory: site`.
- doc-kitty's own CI runs it before install via `node src/scripts/…`, which core cannot copy.
- Benefit: with `--astro-config`, the check reads `plantumlAllowExternal` from the real config, so a later opt-in cannot slip past it.
- Order: after install, before `pnpm run build`.

**doc-kitty #287 ("PlantUML include check for non-container services")** is a *planned follow-up* (guide l.1395-1401: "Letting an operator assert the allowlist instead is a planned follow-up ([#287])"). No code path exists at `5acb83c`.
- Non-container services can only use sandbox mode without `--service-container`, and that is a weaker pass (l.217-219).
- It does not affect core, which uses an inspectable service container.

### 2.6 doc-kitty's own CI (`5acb83c:.github/workflows/ci.yml`)

**`services:` block, l.192-206:**
```yaml
services:
  plantuml:
    image: plantuml/plantuml-server:jetty-v1.2026.9@sha256:065c66adc6728ba6dd353a29d4ada73f8358b68549a0f710c4bf46b43c103618
    ports:
      - 8091:8080
    env:
      PLANTUML_SECURITY_PROFILE: SANDBOX
```

**Job `env:`, l.207-222:** `DK_DIAGRAM_BUILD_RENDER: 'on'`, `DK_PLANTUML_SERVER_URL: http://localhost:8091/svg/`, `DK_BEOE_CACHE_DIR: ${{ github.workspace }}/.beoe-cache`.

**Mermaid render cache, l.225-236:** `actions/cache` on `.beoe-cache`, key = hash of docs + `src/lib/config.ts` + lockfile.

**Readiness wait, l.244-250:**
```sh
for i in $(seq 1 30); do
  if curl -sf -o /dev/null http://localhost:8091/; then echo "PlantUML ready"; exit 0; fi
  echo "waiting for PlantUML ($i/30)…"; sleep 2
done
echo "PlantUML did not become ready on :8091" >&2; exit 1
```

**Canary, l.258-264:**
```sh
GATEWAY=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}' "${{ job.services.plantuml.id }}")
node src/scripts/assert-plantuml-no-remote-include.mjs --server http://localhost:8091/svg/ \
  --canary-host "$GATEWAY" --service-container "${{ job.services.plantuml.id }}"
```

**Playwright install** (`5acb83c:.github/actions/build-example/action.yml:60-104`):
- Resolve the Playwright version from `@playwright/test/package.json` (l.75-79).
- `actions/cache` on `~/.cache/ms-playwright`, keyed `ms-playwright-${os}-${version}-chromium` (l.82-87).
- On a miss, `npx playwright install chromium` with 3 retries and a pause (l.89-99; doc-kitty #117: one 403 from `cdn.playwright.dev` failed a deploy).
- Always `npx playwright install-deps chromium` (l.101-104).

**Other workflows:**
- `deploy.yml:80-125` repeats the same services, env and readiness block.
- The `plantuml-allowlist` lane (`ci.yml:382-420`) is the #268 opt-in. Core does not use it, per the operator ruling.
- doc-kitty's a11y lane uses `container: mcr.microsoft.com/playwright:v1.62.1-noble` (l.440-441). It is tag-pinned, not digest-pinned.

### 2.7 Consumer guide's recommended digest (quote)
`5acb83c:docs/guides/consumer-setup.md:1159`:
```
    image: plantuml/plantuml-server:jetty-v1.2026.9@sha256:065c66adc6728ba6dd353a29d4ada73f8358b68549a0f710c4bf46b43c103618
```
- doc-kitty `ci.yml:194-198`: "multi-arch index digest of `jetty-v1.2026.9` (= `jetty` on 2026-10-18). Bump the tag and the digest together".
- doc-kitty enforces the equality with `plantuml-workflow-services.test.ts`.

## 3. Inventory of published diagrams

Method: a scratch script over `docs/` that uses `_dockitty_contract.is_excluded`, `is_published` and `_doc_status_of`, plus fence regexes. Cross-checked against current `site/dist`, which matches exactly.

**Mermaid: 24 fenced blocks in 11 published pages.** The issue's figure of "18" is stale.

| Page | Blocks |
|---|---|
| `adr/4.x/2026-10-07-2-governed-planning-application-seam.md` (l.20) | 1 |
| `adr/4.x/2026-10-12-2-charter-extraction-to-its-own-repository.md` | 1 |
| `architecture/00_landscape/README.md` | 1 |
| `architecture/acceptance-scenario-contract.md` | 1 |
| `architecture/activation-ledger-and-charter-contract.md` | 1 |
| `architecture/diagrams/01_context/README.md` | 4 |
| `architecture/diagrams/02_containers/README.md` | 3 |
| `architecture/diagrams/02_containers/runtime-execution-domain.md` | 3 |
| `architecture/diagrams/03_components/README.md` | 7 |
| `architecture/event-ledger-writers-and-readers.md` | 1 |
| `changelog/2x/model-to-task_type.md` (l.233) | 1 |

`changelog/2x/model-to-task_type.md` is `doc_status: deprecated`, still published, and immutable. Its block is an **indented fence inside a list**: check that the build renders it.

The `archive/**` pages hold 21 more Mermaid blocks, all excluded and correctly not counted.

**PlantUML: 8 fenced blocks in 4 published pages, no `.puml` files, no includes.**

| Page | Lines | Types |
|---|---|---|
| `architecture/doctrine-kinds.md` | 56, 82 | `@startyaml` ×2 |
| `architecture/doctrine-relationships.md` | 46 | `@startyaml` |
| `architecture/mission-gates.md` | 59, 82, 122 | `@startuml` ×3; one native ArchiMate, one with `skinparam componentStyle rectangle` |
| `architecture/mission-type-resolution.md` | 229, 260 | `@startyaml` ×2 |

- **Embedding:** all PlantUML is ` ```plantuml ` fenced blocks. No `.puml`, `.iuml` or `.plantuml` files exist under `docs/`, and there is no `!include`/`!includeurl` directive. The only `!include` hits are prose (`adr/3.x/2026-08-12-1…md:70`, `mission-gates.md:55`).
- The sandbox refusal therefore affects no current diagram.
- `architecture/diagrams/README.md` (l.90) is in the #6936 comment's list, but it only *describes* `@startyaml` in prose. It has no block.
- Doc-kitty's metadata (`' title:` / `%% title:`) is optional. No current block carries it, so figures get no accessible name or caption from it. The NFR-005 alt/aria text of ADR 2026-08-12-1 §"Accessibility" (l.114+) is produced today by `plantuml_render.py`.
  - **Parity gap: check whether the mission must add `' title:` / `' description:` lines to the 8 blocks.** That is a content edit in mutable `architecture/` pages, allowed. The 24 Mermaid blocks need the same check.
- The `@startyaml` blocks are bound to code models by the drift guard (`tests/docs/diagram_drift/guard.py`, `tests/docs/test_diagram_drift_guard.py`). Adding title lines must keep that guard green (it parses these blocks).

## 4. Gates and tests touched

### `tests/ci/test_docs_site_job.py` (389 lines)
- `_SHA_PIN = ^[^@\s]+@[0-9a-f]{40}$` (l.45). `_pin_violations` (l.163-166) checks only `steps[*].uses`.
  - A `services:` image is **not** checked, and no test anywhere checks a docker image digest. `grep @sha256` in `tests/` finds only `tests/docs/test_plantuml_invoke.py:30-31` (the DocFX jar and JRE pins).
  - Add a check over the shared workflow's `services.*.image` (must match `@sha256:[0-9a-f]{64}$`), with a tag-only mutant.
  - Better still, add a check that the CI digest equals the one in the Makefile or local helper, so local and CI run one renderer. That is a real drift guard, not a restatement.
- `_gate_order_violations` (l.212-233): extend it so that the canary runs after install and before the build, and the diagram surface runs after the build. Mutant tests in the same style (l.240-247).
- `test_no_step_swallows_a_failure` (l.250-256) forbids `|| true` and `set +e`. The readiness loop above complies, since it uses `exit 1`.
- `test_every_dockitty_call_passes_the_astro_config` (l.267-270) needs the canary call to carry `--astro-config astro.config.mjs` (§2.5).
- `_credential_violations` (l.168-177): `job.services.plantuml.id` is not a credential, and the services block carries no secret. OK.
- `test_scrub_documentation_copy_equals_the_router_group` (l.134-138): a path-filter change must update the scrub JSON as well.

### Other gates
- **`tests/ci/test_fork_guard.py`:** it governs only workflows with automated triggers and self-starting jobs. `docs-site-build.yml` is `workflow_call` only, so nothing changes.
- **`tests/architectural/test_dual_mode_contract.py`:** it asserts the reinstated-workflow set (`ci-router`, `module-tests`, …) for `workflow_dispatch` and `mode`. Not affected unless a new workflow file is added. Do not add one; keep everything in `docs-site-build.yml`.
- **`tests/release/test_release_ci_ownership.py`:** l.70-95 lists upstream workflow names, including `plantuml-egress-spike.yml` and `docs-pages.yml`. No change unless a workflow is added or renamed.
- **`scripts/ci/check_generated_docs_untouched.py`:** it refuses edits to `docs/development/docs-retrieval-index.yaml` and `page-inventory.yaml`, and **new** ADR era-table rows.
  - An ADR *amendment* (body edit of `adr/3.x/2026-08-12-1-…md`) is allowed: no new row.
  - Do not add a new ADR file to an era index in this PR, or let the regen bot do it.
- **Packaging (`tests/cross_cutting/packaging/test_packaging_safety.py:446-524`):** `site/**` is excluded from the sdist, and `scripts/`, `docs/` and `tests/` are forbidden trees. New site deps and wrapper scripts stay out of the wheel. No change.
- **DocFX PlantUML path, which must stay green and untouched:**
  - `scripts/docs/plantuml_render.py`, `plantuml_invoke.py`, `plantuml_pins.json` (jar 1.2025.4 sha256 `26518e14…`, JRE `eclipse-temurin@sha256:3097cbbe…`).
  - `tests/docs/test_plantuml_invoke.py`, `test_plantuml_render.py`, `test_plantuml_no_egress_corpus.py`, `test_plantuml_sandbox_negative.py`.
  - The jar restore/provision steps in the `ci-router.yml` `tests-docs` job (l.1426, 1447-1472) and in `docs-pages.yml:14-16,158-182`.
  - Retirement belongs to #6943 (S-17). **Do not touch** these, and do not alter the fenced PlantUML sources in ways `plantuml_render.py` cannot read (it recovers fences from DocFX HTML).
  - `tests/docs/test_diagram_drift_guard.py` reads the same blocks.

### Built-site check (`scripts/docs/site_built_check.py`, #7501)
- `SURFACES` (l.204-214) is pluggable: `name -> fn(dist, routes)`. `site_built_check_render.py` and `site_built_check_llms.py` are the pattern (module `SURFACE` + `surface`). A **diagram surface fits cleanly**: `scripts/docs/site_built_check_diagrams.py`, wired with one line in `SURFACES`.
- Proposed assertions over the BUILT site:
  1. No built HTML page carries `data-language="mermaid"`, `data-language="plantuml"`, or a `language-(mermaid|plantuml)` class outside a deliberate example. Today: 24 + 8 hits, so the check is non-vacuous on the current dist.
  2. No `class="plantuml-error"`.
  3. No `pre.mermaid` or client render script (client-mode residue, as in `diagrams.ts:579-589`).
  4. No `plantuml.com` URL in any built file (the output half of the C-001 guard).
  5. **Count parity:** for each published source page with N mermaid/plantuml fences, the built route has ≥N `<figure class="dk-diagram"` (`TK/lib/rehype/diagram-figure.ts:12,194`), each containing an inline `<svg`.
     - This needs the docs tree. The surface signature is `(dist, routes)`, so either read `docs/` via the contract (`route_of`, `is_published`) inside the module, as `_llms`/render do with the module-level docs path, or extend the signature.
     - Using `scripts/docs/_dockitty_contract.is_published` keeps one authority.
- Tests: fixture `dist` trees (clean passes; mutants with a leftover fence, an error div, or a missing figure each fail), as in `tests/docs/test_site_built_check_render.py`. New code needs ≥90% diff coverage (diff-cover gate) and Sonar complexity ≤15.
- **Path filter:** add the new module (or a `site_built_check*.py` glob) to `ci-router.yml:456-464` and the scrub copy (§1 gap).

### Acceptance (per #7484, lasting value)
1. The real canary run in CI. It is the only proof that SANDBOX holds on the actual service, and it red-fails on profile, port or channel drift.
2. The built-site diagram surface above. It proves "every published diagram is a static SVG" directly on `site/dist`, and it would catch a silent fall back to client mode, a toolkit regression or a new unrendered block.
3. One digest-equality test (CI vs local helper vs the ADR amendment text, if quoted), instead of YAML-shape restatements.

## 5. Risks

- **`@startyaml` (TL;DR 1).** Highest. Options:
  - (a) upstream fix in doc-kitty: `injectSkinparam` and the `astro-plantuml` wrapper must treat any `@start<type>` as the document opener. **check upstream; file it.**
  - (b) a core workaround, rewriting `@startyaml` sources. This conflicts with the drift guard and the ADR genre, so it is not recommended.
  - (c) ship Mermaid now and PlantUML after the upstream fix. That breaks the "done when" criterion.
  - Prove the failure first on a CI run (or locally with a docker daemon) before choosing.
- **CI time** (estimates, unmeasured here):
  - service image pull: about 15-30 s, in parallel with job setup;
  - Chromium download: about 30-60 s on a cache miss, about 5 s on a hit with an `actions/cache` keyed on the Playwright version;
  - `install-deps chromium` (apt): about 30-90 s on every run, because it is not cached;
  - render: 24 Mermaid in one Chromium plus 8 PlantUML HTTP calls, likely under 30 s cold, less with `DK_BEOE_CACHE_DIR` cached;
  - overall about +1.5-3 min on a 20-min-timeout job.
  - Consider a beoe cache keyed on `docs/**/*.md` + `site/pnpm-lock.yaml`.
- **Chromium pinning:**
  - The Chromium revision is fixed by the exact `playwright` version (its `browsers.json`), and the version is fixed by `site/pnpm-lock.yaml` integrity.
  - The browser zip itself is not digest-verified by us.
  - The download host has outages (doc-kitty #117), so mirror the 3-try retry loop.
  - Keep `playwright` exact (no `^`), and align it with doc-kitty's tested version (1.62.1 at v0.7.0).
  - `site_bump.py` does not track it, so a toolkit bump can leave it behind. Note this in the bump procedure (ADR D-2) or teach `site_bump` about it.
  - `pnpm.onlyBuiltDependencies` needs no change.
- **`--service-container` naming:** solved with `${{ job.services.plantuml.id }}` (§2.5). Remaining risks:
  - a failed `docker inspect` → `ServiceConfigError` → exit 1;
  - an empty expression → exit 2 (l.76-78), which is good, because it is loud;
  - a runner image without `docker`: GitHub-hosted ubuntu-24.04 has it.
- **How a red result looks:**
  - Canary: `assert-plantuml-no-remote-include: FAIL — <reason>`, exit 1. For example: `opt-in unset (sandbox), but the service's PLANTUML_SECURITY_PROFILE is not set (the image default is INTERNET)` (guide l.1215), probe failed, canary fetched, or port not published.
  - Readiness: `PlantUML did not become ready on :8091`.
  - Build: `[doc-kitty] astro-plantuml failed to render a plantuml diagram: … a diagram render error fails the build` (`diagram-figure.ts:356-358`); a Playwright "Executable doesn't exist" when Chromium is missing under a pinned build mode; `[doc-kitty] refusing to render PlantUML against "…plantuml.com…"`.
  - Built check: one line per finding from the new surface.
- **#6933 (redirects):** touches the same `site/astro.config.mjs` (comment l.12-13, integration options) and probably the same workflow. Expect a textual merge conflict only. No functional interplay, but the redirect stubs are HTML pages the diagram surface must ignore (they hold no code fences).
- **#6938 (cutover deploy):** calls `docs-site-build.yml` with `pages-artifact: true`. Services, env, Chromium and canary are inherited automatically, which is good: one definition.
  - The caller adds `pages: write` and `id-token: write` on its own job. The shared workflow stays `contents: read`, and the services block needs no extra permission.
  - Make sure the deploy path also runs the canary. It will, if the canary is a step in the shared job.
- **`.env.production` trap (TL;DR 4):** setting the variables there would silently auto-detect the mode and fall back to client, unless the surface check catches it. It would.
- **Local parity:** without a docker daemon or Chromium, a local `make docs-site` with `DK_DIAGRAM_BUILD_RENDER=build` fails. Document it, or add a preflight with the `docker run` line.
- **Accessibility parity:** see §3 (no `' title:` metadata today).

## 6. doc-kitty upstream references and gaps

| Issue | Status / meaning |
|---|---|
| #13 | Diagram build render (C-001 no plantuml.com, WP02/WP03); cited throughout `diagrams.ts`, `diagram-figure.ts`, `ci.yml`. |
| #117 | Chromium download 403; cache plus retry (`build-example/action.yml:70-74`). |
| #153 | Consumer guide explains `diagrams` (CHANGELOG l.1071). |
| #185 | Diagram expand button (CHANGELOG l.500). |
| #251 | Digest pin plus SANDBOX plus the no-remote-include bin (CHANGELOG l.302-315); #256 is the merged PR (b746098, per the #6936 comment). |
| #268 | External-include opt-in, ADR-0074 (CHANGELOG l.85-93); v0.7.0's stricter `--service-container` checks (CHANGELOG l.29-37). Core keeps it off (operator ruling 2026-11-01). |
| #287 | Assert a non-container service; planned only, no code at 5acb83c (guide l.1399-1401). Not needed by core. |
| #295 | `starlight.head` replaces toolkit head entries (core config comment). |
| #312 | Exported built-artifact check (`site_built_check.py` docstring). A diagram assertion would belong there too. |
| #247-#250 | Core's earlier gap filings (#6100 comment). |

**Gaps to file or check upstream:**
- **`@startyaml` and other non-`@startuml`/`@startjson` PlantUML documents.** `injectSkinparam` plus `astro-plantuml`'s `@startuml` wrapping break them. Check upstream; no reference found.
- **`plantuml-guard` has no bin and is scoped to the toolkit's own `lib/`.** The ADR's D-11 wording ("checks with `plantuml-guard.mjs`") assumes more than it does. Check upstream, or extend #312.
- **The consumer guide never names the Playwright package or version to add** for build mode. Check upstream.
- **No exported built-site diagram assertion** (doc-kitty's `assertPlantumlDemonstrator` in `assert-build-artifacts.mjs:1195-1260` is example-specific). Fold into #312.

## 7. 90-day churn (since 2026-08-12, `git log --oneline | wc -l`)

| File | Commits |
|---|---|
| `.github/workflows/ci-router.yml` | 116 (hot: conflict risk; keep the edit to the path filter only) |
| `Makefile` | 32 |
| `docs/architecture/doctrine-relationships.md` | 14 |
| `docs/architecture/doctrine-kinds.md` | 13 |
| `tests/ci/test_docs_site_job.py` | 9 |
| `docs/architecture/mission-gates.md` | 9 |
| `docs/architecture/mission-type-resolution.md` | 7 |
| `docs/adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md` | 4 |
| `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` | 4 |
| `site/pnpm-lock.yaml` | 3 |
| `site/astro.config.mjs`, `site/package.json`, `.github/workflows/docs-site-build.yml`, `scripts/docs/site_built_check.py` | 2 each |
| `site/.env.production` | 1 |

## ADR amendment notes (2026-08-12-1)
- The current text binds `--network=none` and the jar/JRE pins (l.61-77, 134).
- The amendment (per the #6936 comment) for the doc-kitty path:
  - the guarantee becomes "the renderer refuses every remote include, proven behaviourally by the canary check (`dockitty-assert-plantuml-no-remote-include --canary-host --service-container`)";
  - the service is `plantuml/plantuml-server:jetty-v1.2026.9@sha256:065c66ad…` with `PLANTUML_SECURITY_PROFILE=SANDBOX`;
  - external includes stay off (doc-kitty #268 not used);
  - the DocFX path keeps `--network=none` until #6943.
- Also bump `updated:` in the frontmatter.
- Note the PlantUML version change: DocFX pins 1.2025.4, doc-kitty's image is v1.2026.9. Rendering may differ slightly.
- ADR 2026-10-31-1 D-11 (l.242) says the egress path is restricted "in the server's configuration or refuses such includes at source". SANDBOX satisfies the first branch. No amendment is needed there, unless the `@startyaml` gap changes scope.
