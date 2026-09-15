---
doc_status: active
updated: '2026-09-07'
---

The reinstated CI on this repository is the **primary/sole** CI producer. The pre-fork factory `.github/workflows/ci.yml` was a Blacksmith producer fenced to the `spec-kitty/EXPERIMENTAL-spec-kitty` repository; that repository is now **archived** and runs no Actions, so the fenced producer is **inert**. It is therefore **retired** (`never-restore`) rather than promoted — there is no second live producer to coexist with, and no surviving public job carries the private `blacksmith` runner or `SK_CI_TOKEN`. The restored public gates below resolve the released PyPI dependencies without private-repository credentials, and the nightly/full mode carries the whole-tree architectural + terminology + coverage signal Blacksmith formerly produced.

## Dispositions

Every `.github/workflows/*.yml` maps to exactly one disposition. The enforcer (`tests/release/test_release_ci_ownership.py`) asserts each disposition as an **exact set over the map ROWS below** — not over filesystem presence of the workflow file.

| disposition | meaning |
|---|---|
| restore | pre-fork workflow reinstated on stock runners |
| defer | pre-fork workflow not yet restored |
| never-restore | pre-fork or dead workflow retired forever (no live subject) |
| introduced | net-new workflow with no pre-fork ancestor (router, module-*, aggregate, sonar, nightly, packs) |

### Invariants

1. Every `.github/workflows/*.yml` maps to exactly one disposition.
2. `introduced` and `restore` workflows use **stock runners** (`blacksmith` never appears) and carry **no `SK_CI_TOKEN`** on public jobs.
3. Any de-defer (`defer`→`restore`) or net-new (`∅`→`introduced`) edits this map **in the same change** (C-001 lockstep).
4. The enforcer **runs on every workflow-changing PR** (not only a tag push).
5. Adding `introduced` must not weaken the existing three-set assertions — deleting any row reds the enforcer (self-mutation / non-vacuity, SO#5).

The `introduced` set is **frozen** at exactly the seven net-new workflow names this mission adds: `sonar.yml`, `ci-router.yml`, `module-tests.yml`, `ci-modules.yml`, `ci-aggregate.yml`, `ci-nightly.yml`, `packs.yml`. An eighth net-new workflow is not representable in the exact set and **reopens WP01** (documented) rather than being appended silently downstream.

## Disposition rows

| path | disposition | reason |
|---|---|---|
| `.github/workflows/ci.yml` | never-restore | Dead EXPERIMENTAL-fenced Blacksmith producer: fenced to the archived `spec-kitty/EXPERIMENTAL-spec-kitty` repo (runs no Actions), so it is inert. Retired in lockstep with its enforcing seam; the reinstated CI on this repo is the primary/sole producer (FR-017 / C-010). |
| `.github/workflows/ci-quality.yml` | restore | Restored as the reduced five-job interim producer on stock runners: `lint`, `build-wheel`, `clean-install-verification`, `uv-lock-check`, and `quality-gate`. It **runs no test suite**: a sixth job, the per-PR `sonarcloud` reporter (spec-kitty#3993), ran the fast tier under `pytest --cov` between 2026-09-06 and 2026-09-14 and was retired by spec-kitty#4334 — it re-measured what the `ci-modules` shards had already measured for the same commit, and the per-change Sonar report now reads that measurement from `ci-aggregate.yml`'s `sonar-pr` job. While it existed, this row said five and the file had six; the count is now pinned by `tests/release/test_release_ci_ownership.py::test_reduced_ci_quality_has_exact_jobs`, and the no-suite property by `tests/architectural/test_no_duplicate_suite_execution.py`. |
| `.github/workflows/protect-main.yml` | restore | Restored on `ubuntu-latest` so the promoted tree has the Phase-1 exit check-run; rebase-merge association checking is retained. |
| `.github/workflows/ci-windows.yml` | restore | Restored on stock runners with the obsolete `tests/sync/*` path filters removed. |
| `.github/workflows/docs-pages.yml` | restore | Restored on `ubuntu-latest`; the existing docs build scripts and Pages deployment contract are live on this tree. |
| `.github/workflows/check-spec-kitty-events-alignment.yml` | restore | Restored on `ubuntu-latest`; its drift script and pinned metadata surfaces are live on this tree. |
| `.github/workflows/all-contributors-normalize.yml` | never-restore | Pre-fork contributor automation is not part of the MVP and has no current contributor-data contract. |
| `.github/workflows/all-contributors-sync.yml` | never-restore | Pre-fork contributor automation is not part of the MVP and has no current contributor-data contract. |
| `.github/workflows/canonical-producer-lint.yml` | defer | The producer lint is potentially useful, but restoring it requires a current docs-producer ownership audit after the interim topology lands. |
| `.github/workflows/docs-build-pr.yml` | defer | A PR-side docs build can be reduced later; `docs-pages.yml` provides the required deploy-side producer for this phase. |
| `.github/workflows/docs-freshness.yml` | defer | Current docs tests already cover freshness invariants; a separate workflow needs path-scope reconciliation first. |
| `.github/workflows/doctrine-charter-tests.yml` | defer | Its suites belong to the factory CI topology; restoring a second producer before topology reconciliation would duplicate authority. |
| `.github/workflows/module-doctrine-fast.yml` | defer | The reduced `ci-quality.yml` intentionally excludes the old modular suite topology; any restored parallel fast selector must also exclude `timing` (#94). |
| `.github/workflows/module-doctrine-integration.yml` | defer | The reduced `ci-quality.yml` intentionally excludes the old modular suite topology. |
| `.github/workflows/module-kernel.yml` | defer | The reduced `ci-quality.yml` intentionally excludes the old modular suite topology. |
| `.github/workflows/module-packs.yml` | defer | The reduced `ci-quality.yml` intentionally excludes the old modular suite topology. |
| `.github/workflows/orchestrator-boundary.yml` | never-restore | It guards the pre-fork orchestrator boundary rather than the current programme topology. |
| `.github/workflows/plantuml-egress-spike.yml` | never-restore | The spike is superseded by the pinned, no-egress PlantUML render path in `docs-pages.yml`. |
| `.github/workflows/plugin-validate.yml` | defer | Plugin validation is valuable but outside the interim CI producer and needs a current plugin-surface audit. |
| `.github/workflows/regen-assets.yml` | defer | Generated-asset regeneration needs a current ownership and artifact audit before another producer is added. |
| `.github/workflows/ui-e2e.yml` | defer | Cross-repo E2E belongs to the e2e repository and factory CI topology, not this interim CLI producer. |
| `.github/workflows/release.yml` | restore | Restored on `ubuntu-latest` with the wheel-content gate re-pointed to `src/charter/offering` and its bundled skills. |
| `.github/workflows/release-readiness.yml` | restore | Restored on `ubuntu-latest`; the cutover guard runs from source without resolving the CLI's git direct references. |
| `.github/workflows/scripts/check-release-exists.sh` | defer | Release script; owned by the P3.4b release topology sibling. |
| `.github/workflows/scripts/create-github-release.sh` | defer | Release script; owned by the P3.4b release topology sibling. |
| `.github/workflows/scripts/create-release-packages.sh` | defer | Release script; owned by the P3.4b release topology sibling. |
| `.github/workflows/scripts/generate-release-notes.sh` | defer | Release script; owned by the P3.4b release topology sibling. |
| `.github/workflows/scripts/get-next-version.sh` | defer | Release script; owned by the P3.4b release topology sibling. |
| `.github/workflows/scripts/update-version.sh` | defer | Release script; owned by the P3.4b release topology sibling. |
| `.github/workflows/drift-detector.yml` | never-restore | The CLI-to-SaaS sync transport is deleted; the workflow's subject no longer exists. |
| `.github/workflows/project-sync-consent-evidence.yml` | never-restore | The CLI-to-SaaS sync transport is deleted; the workflow's subject no longer exists. |
| `.github/workflows/review-verdict-durability.yml` | never-restore | Programme verdict durability is owned by GitHub comments and the planning provenance contract, not this pre-fork workflow. |
| `.github/workflows/teamspace-mission-state-readiness.yml` | never-restore | The pre-fork teamspace readiness surface is not part of the current MVP topology. |
| `.github/workflows/performance.yml` | never-restore | Performance pipelines are out of the MVP; timing coverage remains in the local full suite. |
| `.github/workflows/ci-flake-report.yml` | never-restore | Flake classification is the deterministic CI and merge agents' responsibility, not a separate GitHub Actions producer. |
| `.github/workflows/mutation-remediation.md` | never-restore | Documentation for an absent mutation workflow; it has no live subject on this tree. |
| `.github/workflows/ci-router.yml` | introduced | Net-new path-router that classifies a PR's changed files and dispatches the eligible module/aggregate suites; no pre-fork ancestor. |
| `.github/workflows/module-tests.yml` | introduced | Net-new reusable module test-runner (per-module roots, coverage target, tier, shards); no pre-fork ancestor. |
| `.github/workflows/ci-modules.yml` | introduced | Net-new matrix caller that fans `module-tests.yml` across the registry-declared modules; no pre-fork ancestor. |
| `.github/workflows/ci-aggregate.yml` | introduced | Net-new artefact-aggregation + diff-coverage gate over the module runs; no pre-fork ancestor. |
| `.github/workflows/sonar.yml` | introduced | Net-new SonarQube analysis producer; no pre-fork ancestor on this tree. |
| `.github/workflows/ci-nightly.yml` | introduced | Net-new nightly/full-mode interpreter carrying the whole-tree arch + terminology + coverage signal; no pre-fork ancestor. |
| `.github/workflows/packs.yml` | introduced | Net-new packs/doctrine-asset verification producer; no pre-fork ancestor. |
