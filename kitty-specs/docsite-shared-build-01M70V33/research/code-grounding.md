# Code grounding: one shared docs-site build definition (#6937 remainder)

Read-only survey, written before specifying. Base: `origin/main` at `366ff233`.

## Issue scope

#6937 asked for the required gate (done by #7417: `docs-site` is in `router-gate.needs`,
no `continue-on-error`, `ADVISORY_JOB_NAMES` empty) and for D-11's "the deploy workflow and
the job share one build definition". Only the second half is open
([comment 6721090900](https://github.com/spec-kitty/spec-kitty/issues/6937#issuecomment-6721090900)).
ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-11 ends: "The deploy
workflow builds with the same steps, so main can never deploy a site no pull request built."
The deploy switch itself is #6938 (out of scope). The operator chose a **reusable workflow**
(not a composite action) on 2026-11-09, because #6936 needs job-level `services:`, which a
composite action cannot declare.

## Current state

- **The job.** `.github/workflows/ci-router.yml:1756-1810`: header comment, then
  `docs-site` (`name: docs site (doc-kitty build)`, `needs: [changes]`,
  `if: needs.changes.outputs.docs_site == 'true'`, `timeout-minutes: 20`). Steps: checkout
  (SHA), `python3 -m scripts.docs.site_contract --check` (`PYTHONPATH: .:src`),
  `pnpm/action-setup` (SHA), `actions/setup-node` (SHA, pnpm cache), `pnpm install
  --frozen-lockfile`, `pnpm run build`, `actions/upload-artifact` (SHA) of `site/dist`.
- **Path filter.** `ci-router.yml:455-460` `docs_site`: `docs/**`, `site/**`,
  `scripts/docs/_dockitty_contract.py`, `scripts/docs/site_contract.py`,
  `.github/workflows/ci-router.yml`. Its documentation copy is
  `tests/release/ci_retirement_scrub.json:340-350`, equality-pinned by
  `tests/ci/test_docs_site_job.py::test_scrub_documentation_copy_equals_the_router_group`.
  `.github/workflows/**` is also in `ci_config` (`ci-router.yml:575-576`).
- **Required-ness.** `router-gate.needs` lists `docs-site` (`ci-router.yml:1843`).
  `scripts/ci/router_gate.py:111-127` classifies EVERY jobs-API row of the run by display
  name (not only `needs:`), so a called workflow's job row (GitHub names it
  `<caller name> / <callee name>`) is classified like any other: a red row blocks.
- **The deploy.** `.github/workflows/docs-pages.yml` builds DocFX and deploys with
  `actions/upload-pages-artifact@v5` + `actions/deploy-pages@v5` (tag-pinned; that file is
  outside the SHA-pin test). It stays untouched here.
- **Existing reusable-workflow precedent.** `ci-modules.yml:429` and `ci-nightly.yml:1069`
  call `./.github/workflows/module-tests.yml` (`on: workflow_call`).

## Gates and tests touched

| Test / gate | Effect of a reusable workflow |
|---|---|
| `tests/ci/test_docs_site_job.py` (280 lines) | `_job()` / `_run_text()` read `jobs.docs-site.steps`; after extraction the caller has no `steps`, so the SHA-pin, credential, frozen-install, contract-check and no-swallow checks would pass **vacuously**. They must follow `uses:` into the called workflow. The router-row tests use `_job()['name']`; the real row name becomes `<caller> / <callee>`. |
| `tests/architectural/test_dual_mode_contract.py` | Discovers a fixed candidate list (`REINSTATED_WORKFLOW_CANDIDATES`); a new `workflow_call` file is not in it. Pins the `needs:`==all-jobs invariant of `router-gate`; the caller job stays a job key, so it holds. |
| `tests/release/test_release_ci_ownership.py` | Pins docs-pages' probe/configure job and `main`-only deploy (D-12) at `:419-440`; `INTRODUCED_WORKFLOWS` is a frozen set read from `docs/convergence/interim-ci-producer.md` map rows, which does not list every workflow (`pr-pause-ci.yml`, `docs-index-regen.yml`, `ci-fleet-verdict.yml` have no row). A new workflow needs no row. Untouched. |
| `tests/ci/test_fork_guard.py` | Guards workflows with automated triggers (push/schedule/workflow_run); `workflow_call` is not one. |
| Workflow-wide scans (`test_workflow_run_shell_syntax.py`, `test_workflow_script_import_guard.py`, `test_pause_ci_unlabel.py`, `test_fleet_verdict.py`, `test_fleet_main.py`, `test_merge_queue_wiring.py`, `test_sync_services.py`) | Glob every `*.yml`; the new file must satisfy them. The required-check set (`router gate`, `CI Modules gate`, `Clean install verification`) is unchanged. |
| `scripts/ci/gate_selection.py` | Loads the `docs_site` filter from the router; adding the new workflow path there selects `docs-site` when the shared definition changes. |
| `tests/docs/test_site_scaffold.py`, `tests/docs/test_site_bump.py` | Not affected (no `site/` change). |
| Packaging safety | `.github/` is not in the wheel/sdist; not affected. |

## Interactions with the other slices

- Lands **after** the pin bump (#7480) and **before** #6932/#6934/#6935, #6933 and #6936,
  which will add their gate steps (frontmatter, links, redirect coverage, PlantUML service)
  to the shared workflow instead of the router job (resliced plan, operator-approved
  2026-11-09).
- #6936's `services:` container and Playwright install go in the called workflow's job.
- #6938 will call the same workflow from the deploy with a Pages-artifact upload; this
  mission provides that input and a test pinning that the deploy can reuse it.

## 90-day churn (`git log --since=90.days origin/main`)

| File | Commits |
|---|---|
| `.github/workflows/ci-router.yml` | 114 (hot: rebase early, keep the edit local to the job block + filter) |
| `tests/release/test_release_ci_ownership.py` | 38 |
| `tests/release/ci_retirement_scrub.json` | 25 |
| `.github/workflows/docs-pages.yml` | 14 (untouched) |
| `tests/architectural/test_dual_mode_contract.py` | 9 |
| `scripts/ci/router_gate.py` | 5 |
| `tests/ci/test_docs_site_job.py` | 4 |
| `tests/ci/test_fork_guard.py` | 2 |
