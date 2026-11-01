---
title: Code grounding — events-service cut-over (#6915 gaps 3 and 11)
type: reference
audience: docs/context/audience/internal/maintainer.md
updated: '2026-11-01'
---

# Code grounding: events-service cut-over

Read-only pass, 2026-11-01, on `origin/main` at `dc9a09d3` (branch `issue-6915-events-service-cutover`).
Nothing was edited before this note. Sources: the repository at that commit, the clone of
`spec-kitty/spec-kitty-events` at `9796adcc`, and the release `service-v0.1.0-rc.1`.

## 0. The release to pin

- `service-v0.1.0-rc.1` is a pre-release, target `main`. Assets: `mission-status-api-0.1.0-rc.1-{linux-x64,linux-arm64,macos-arm64,windows-x64.exe}` (89–96 MB each), `mission-status-api-0.1.0-rc.1.jar` (20.7 MB), `contract-bundles-`, `contract-tools-`, `conformance-fixtures-0.1.0-rc.1.tar.gz`, each with a `.sha256`, plus `SHA256SUMS`. No `command-cli` (write service): out of scope.
- `sha256sum --check --ignore-missing SHA256SUMS`: OK for the three tarballs, the jar and linux-x64 (the four assets downloaded for inspection).
- `gh attestation verify` fails in this sandbox before checking anything: `error creating Sigstore verifier: no valid Sigstore verifiers could be initialized` (the Sigstore trust root cannot be fetched here). The REST API reports one attestation for the linux-x64 digest (`GET /repos/spec-kitty/spec-kitty-events/attestations/sha256:e78c8311…` → 1). Attestation verification is therefore **not** done here; the PR says so.
- Tarball contents:
  - `conformance-fixtures`: `conformance/` (the whole conformance corpus incl. `manifest.json`, `resolver-cases.json`), `artifact-conformance/{cases,golden}.json`, `event-log/torn-tail/repair-cases.json`, `leak-patterns.json`, `nativesmoke/requests.json`. **Byte-identical** to core's copies under `services/mission-status-api/src/{test,main}/resources/` and `services/mission-status-api/event-log/src/test/resources/torn-tail/` (`diff -rq`).
  - `contract-bundles`: only `bundle/mission-status/openapi.yaml` and `bundle/mission-write/openapi.yaml`. Each equals `contract_resolver.resolve(contracts/<module>).tree` (whole-dict compare): no `$ref`, titles and schema `examples` lists kept. No split sources (no `schemas/*.yaml`, no `examples/*.yaml`, no `CHANGELOG.md`).
  - `contract-tools`: `contracts/tools/*.py`, `pins.json`, `enum_pins.json`. The five tools the Python oracle loads (`contract_resolver`, `leak_patterns`, `schema_formats`, `fixture_builder`, `leak_scan`) and `install_tools.py` are identical to core's. `bundle.py`, `gradle_pin_check.py`, `tamper_check.py`, `pins.json` differ (events-side Gradle unification, events#147). No `tools/fixtures/` and no `negative_cases.json`.
- **Live evidence:** the pinned linux-x64 binary started with `--mission-status.project-root=<checkout> --mission-status.port=8787` answers `/api/v1/project` in ~1 s, and `scripts/ci/mission_status_corpus_compare.py --base-url http://127.0.0.1:8787 --repo-root .` reports `compared 677 Missions: 678 rows equal, 0 rows not equal`, exit 0. The CLI and the bundle are baked into the binary at its build (events `service/build.gradle.kts` `bundleContract`), so the nightly needs no bundle step.

## 1. Inventory and drift against plan.md §1.2

110 files outside `services/`, `contracts/` and `kitty-specs/` reference them (`git grep`). By area:

| Area | Files (key lines) | Cut-over action |
|---|---|---|
| Service workflow | `.github/workflows/mission-status-api.yml` | delete; its `nightly-corpus` job is the **only** consumer of a binary and is re-homed (below) |
| Contracts workflows | `contracts.yml`, `contracts-release.yml` | delete |
| Router | `ci-router.yml`: glossary torn-tail glob :353-354; `ci` group `services/mission-status-api/**` :480-486; `contract_tools` group :514-590 (both workflows, conformance globs); `corpus` group `contracts/**` :399; jobs `tests-corpus-blocking` :1282-1318, `tests-contract-tools` :1329-1365 | drop `services/` globs and the two workflow globs; narrow `contracts/**` to `contracts/fixtures/**`; add `pins/**` + sync-services files to the groups whose tests now read the pin; add `uses: ./.github/actions/sync-services` to both jobs |
| Module registry | `.github/ci-module-registry.yml` :267-268 (glossary torn-tail), :425 + :461-463 (`ci` services root), :969 (`fast_gate` entry for the freeze test), :772-782 prose | drop; mirror in `tests/release/ci_retirement_scrub.json` :171, :252 (verbatim mirror is pinned by `test_ci_module_wiring::test_scrub_carries_the_ci_group_verbatim`), :287-290 |
| Fleet verdict | `scripts/ci/fleet_verdict.py:46-47` (`contracts.yml`, `mission-status-api.yml`), `ci-fleet-verdict.yml:5` (`Contracts`, `Mission Status API`) | drop both; **drift:** plan names only "Mission Status API" |
| Ownership/attrs | `.github/CODEOWNERS` :13-14 `/contracts/`, :34-35 `/services/mission-status-api/`; `.gitattributes:38` conformance `-text` | narrow `/contracts/` to `/contracts/fixtures/`; drop the rest |
| NOTICE / charter | `NOTICE:19-27` Gradle wrapper block; charter Attribution line naming it | drop |
| pyproject | sdist `exclude` :267-271 (`services/**`, `contracts/**`); mutmut `also_copy` :2615 `contracts/`; wheel `force-include "pins" = "specify_cli/_pins"` :219-228; sdist include `pins/**` | drop `services/**`; keep `contracts/**` exclude and `also_copy` (fixtures remain); pins wiring already present |
| Nightly / sonar / dev setup | `ci-nightly.yml:1522` `python contracts/tools/gradle_pin_check.py`, `:1532` `install_tools.py`; `sonar.yml:257` `install_tools.py`; `scripts/dev/cloud-session-setup.sh:72-73` | read the tools from the pinned `contract-tools` asset. **Drift:** plan §1.2 lists these as "Not coupled"; they execute `contracts/tools/*.py`. **Gotcha:** the released `gradle_pin_check.py` bare run (`check_all`) always scans the `contracts/` subproject, which core no longer has; the module's public `check_acceptance_jvm(root)` covers only acceptance-jvm, so core calls that through a small wrapper. Upstream gap: an `--acceptance-jvm` flag on the tool |
| acceptance-jvm | `README.md:12,24,27,65-66,84-85` (install command), `build.gradle:13,21-22`, `settings.gradle:6-9` comments | docs/comment pointers to the pinned tools |
| CI scripts | `mission_status_gate_checks.py` (native tag floor; only `mission-status-api.yml`) | delete with its test (moved to events, ported there per events `service.yml` comments) |
| | `mission_status_corpus_compare.py` (imports `tests.contract._mission_status_*`; tools from `<repo>/contracts/tools`) | stays (ADR D-7); tools come from the pinned asset |
| | `lock_interop_peer.py` (no read of `services/`; docstring only) | stays (ADR D-7; events CI runs it at a pinned core SHA) |
| Python runtime | `write_service_protocol.py`, event bridge, `kernel.locks`, `kernel.event_log_append` | untouched (ADR D-7) |
| Docs | ADRs, architecture pages, `ci-gate-mechanics.md`, `events-in-core.md`, `lock-interop-spike.md`, roadmap, CLAUDE.md, AGENTS.md, charter | pointer edits only; `docs/architecture/event-ledger-writers-and-readers.md` was frozen (ADR D-1/D-9) — it moves to events; core keeps a pointer |

Other drift since the plan was written:
- `tests/ci/test_sync_services.py` (not in the plan) carries a ratchet: once any `pins/*.source.yaml` exists, some workflow job must `uses: ./.github/actions/sync-services`, and `:257-264` asserts `sync-services` is **not** in `dev-setup` "until the first real pin". Both flip in this PR.
- `tests/ci/test_contracts_routing.py` (not in the plan) pins `contracts/**` in the corpus group.
- `tests/architectural/test_no_duplicate_suite_execution.py:190` allowlists `contracts-release.yml`.
- `tests/architectural/test_scenario_contract.py:253` loads `contracts/tools/codeowners_check.py`.
- The corpus job (`tests-corpus-blocking`) never fetched a binary; it reads `contracts/mission-status` and `contracts/tools` in place. The binary comparison lived only in `mission-status-api.yml` `nightly-corpus` (dispatch-only, jar built from `services/`); the plan does not re-home it.

## 2. What stays in `contracts/`

`contracts/fixtures/fixture_01..05*.json` (5 files). The only loader is `tests/contract/test_handoff_fixtures.py:284` (`FIXTURES_DIR`). acceptance-jvm, `src/`, `scripts/` and workflows do not read them. They stay, unfrozen (ADR D-9).

## 3. Contract and golden consumers, and how each reads the pin

Classes: (a) unit test of a `contracts/tools` script; (b) reads goldens present in `conformance-fixtures`; (c) reads contract sources; (d) pins Gradle/workflow files.

| Consumer | Class | After the cut-over |
|---|---|---|
| 25 tool tests: `test_{breaking_check,bundle,citation_check,client_smoke,codeowners_check,contract_resolver,enum_pin_check,event_mapping_check,example_check,fixture_builder,gradle_pin_check,install_tools,layout_check,leak_patterns,leak_scan,lint_ruleset,no_pytest_scan,provisional_check,release_check,resolver_parity,run_negative_cases,schema_formats,structure_check,tamper_check,verify_pins}.py` | (a) | delete: they test the tool scripts, which live in events now (the released copies differ for 4 tools and lack `tools/fixtures/`). **Residual:** spec-kitty-events has no Python tests for `contracts/tools` yet (no `test_tamper*`, `test_bundle*` in its `tests/`); porting them is events-side work |
| `test_mission_status_examples.py`, `test_mission_status_contract_1_1.py` | (c), source layout | delete: they prove the split-source layout and contract evolution (`CHANGELOG.md`, `_index.yaml`, planted bad example), which the bundle cannot carry. Same residual |
| `_mission_status_conformance.py` :51-52, `test_mission_status_conformance.py` :38, :117-119 | (b) | repoint the two constants at the extracted `conformance-fixtures` (`conformance/`, `leak-patterns.json`); the scratch copy keeps its layout |
| `_mission_status_artifact_goldens.py` :40-42, `test_mission_status_artifact_goldens.py` | (b) | repoint at `artifact-conformance/`; the `--write` regeneration mode goes (regeneration happens in events against a pinned core SHA, ADR consequences) |
| `tests/glossary/test_torn_tail_repair_goldens.py` :26 | (b) | repoint at `event-log/torn-tail/repair-cases.json`; drop the rewrite `__main__` |
| `_mission_status_payloads.py` :112 (`WpId.yaml`), :556 (`contracts/tools`), `Contract(tools, module_dir)` | (c)+tools | tools from extracted `contract-tools`; module dir = `bundle/mission-status` (the resolver accepts a `$ref`-free `openapi.yaml`); schema files read by **title** from the bundle |
| `_mission_status_detail.py` :78; `test_mission_status_{detail,drift,ops,project,reality,artifacts,payloads}.py` | (c) | same: bundle dir + schema-by-title. `test_mission_status_project.py:701` reads the raw `Project.yaml`, which differs from the inlined bundle node: check what it asserts; `test_mission_status_payloads.py:1090` globs `examples/{title}.*.yaml`: re-key to the schema's `examples` list |
| `test_mission_write_contract.py` :33-35, :92, :295, :330 | (c) | bundle `bundle/mission-write`; examples by schema title and index (file names are lost in the bundle); `:330` reads `openapi.yaml` without the resolver and still passes on the bundle |
| `tests/contract/_loader.py` | helper | stays (used by the oracle helpers and `test_scenario_contract`) |
| `tests/architectural/test_scenario_contract.py:253` | tool | load `codeowners_check.py` from the extracted `contract-tools` |
| acceptance-jvm (`install_tools.py`, `gradle_pin_check.py`) in `ci-nightly.yml`, `sonar.yml`, `cloud-session-setup.sh` | tools | from the extracted `contract-tools` (plan Q5: fetched, not copied) |
| `tests/ci/test_mission_status_api_build.py` (~2,900 lines), `test_mission_status_gate_checks.py`, `test_contracts_workflows.py`, `test_mission_status_routing.py` | (d) | delete (their workflows/scripts are gone; events carries the build pins). `test_contracts_workflows.py`'s rule "every `tests/contract` module has one home" moves to a rewritten routing test if still meaningful |

**One reader for the pinned assets.** Tests, the corpus script and the workflows all need "the extracted directory of extra X of service Y's pin". Today `scripts/sync_services.py` fetches and verifies the tarballs into `${XDG_CACHE_HOME:-~/.cache}/spec-kitty/services/<service>/<tag>/` but does not unpack them. The design: `sync_services.py` also unpacks each verified extras archive (safe extraction, keyed by the archive's sha256) and exposes the path (`--extras-path <service>:<extra>`); a test helper resolves the same path and **fails** (never skips) with `SERVICE_BINARY_MISSING … run make sync-services` when the asset is absent. Kernel is not used for this: `test_no_dead_symbols.py` requires every `kernel` `__all__` name to have a `src/` caller, and only scripts and tests unpack.

**Fast tier.** None of the (b)/(c) tests run in `make test-fast` (`tests/unit tests/status tests/cli tests/specify_cli/runtime`), so `make test-fast` needs no sync. They run in the router jobs `tests-corpus-blocking` and `tests-contract-tools` and in the glossary module shard.

## 4. Gates touched, and how each stays honest

| Gate | Today | After |
|---|---|---|
| `tests/architectural/test_events_import_frozen.py` | pins tree ids of `services` and 9 `contracts/` paths + the architecture page; requires them to exist | **deleted** with `services/`, as its docstring and ADR D-9 prescribe; its `fast_gate` registry entry goes too |
| `tests/ci/test_service_pins_gate.py` | parametrised over `pins/*.source.yaml`: `load_service_pin` + `check_pin(online=False)`; two planted non-vacuity tests | goes live (one real pin), unchanged |
| `tests/ci/test_sync_services.py` | wiring ratchet; asserts `sync-services` not in `dev-setup` | the ratchet is satisfied by real wiring; the dev-setup assertion flips (positive assertion) |
| `test_shared_package_boundary.py`, `test_pyproject_shape.py` | no `services`/`contracts`/`pins` references | unchanged; run to prove it |
| `test_gate_selection_authority.py:252-265` (`test_a_services_only_diff_selects_the_ci_module`) | 4 `services/` paths select `ci` | re-point to a pins-only diff selecting `ci` (keeps the authority check non-vacuous) |
| `test_module_shard_registry.py:744-751` | `ci` roots include `services/mission-status-api/**` | drop that root |
| `test_ci_module_wiring.py:59-66` | `_ROOTS` includes the services root | drop it |
| `test_release_asset_download_owner.py` | only `src/specify_cli/services` | unchanged (no new HTTP download point: extraction reads the already-verified cache) |
| `test_no_duplicate_suite_execution.py:190` | allowlists `contracts-release.yml` | drop the entry (shrink) |
| `test_contracts_routing.py` | `contracts/**` in the corpus group | re-point to `contracts/fixtures/**` |
| `test_fleet_verdict.py`, `test_fleet_main.py` | expect `Contracts` and `Mission Status API` | rewrite without them (retarget the tag-push case) |
| packaging guards `tests/cross_cutting/packaging/test_packaging_safety.py` | no service binary in wheel/sdist, pins shipped | unchanged; must stay green; `release.yml` wheel checks gain an explicit "pins in, no binary" assertion |
| `_baselines.yaml`, `dead_symbol_allowlist.yaml` (`write_service_protocol`, #6195) | prose/entries | unchanged (drains with #6195) |

No allowlist grows. Two gates shrink (registry entry, duplicate-suite allowlist entry).

## 5. Nightly corpus compare

- Today: `mission-status-api.yml` job `nightly-corpus`, `workflow_dispatch` only (no cron). Builds a contract bundle and the jar from `services/`, starts it on 8787 against the checkout, runs the compare script, uploads the report.
- After: a job in `ci-nightly.yml` (scheduled with the rest of the nightly): checkout (full history), uv sync, sync-packs, **sync-services** (host native linux-x64 + extras), start the pinned binary from the cache against the checkout, run the same compare script, upload the report, stop by PID. No JDK, no Gradle. Events keeps its own `nightly-corpus` (its jar against a pinned core SHA); core's job compares **the build core pins** against core's live corpus, which is the conformance ADR D-6 asks for.
- The compare script reads its five tools from the extracted `contract-tools` (today `<repo>/contracts/tools`).

## 6. Interactions

- **PR #6949** (companion services wheel, #6904; operator decision 1 on #6915 rules against it for now). Files: `.github/workflows/release.yml` (+108), `RELEASE_CHECKLIST.md` (+31), `AGENTS.md`, the ADR (+18), `docs/changelog/CHANGELOG.md`, `docs/development/docs-retrieval-index.yaml`, `docs/plans/events-domain-move/{plan.md,companion-wheel-research.md}`, and its own `kitty-specs/companion-services-wheel-01M694B1/`. **Textual overlap** with this PR: `release.yml`, `RELEASE_CHECKLIST.md`, `AGENTS.md`, the ADR, the changelog and `plan.md`. This PR does not build on it, does not touch its kitty-specs, and keeps its own `release.yml` edit to one fetch+check step pair and one wheel assertion, so a later rebase of either is small.
- Events CI pins core `512567ee` (`service/core-pin.json`) for the lock-interop peer and its nightly corpus. Deleting core's `services/` does not affect those jobs (they read core's `scripts/ci/` and `tests/contract/`, which stay). The `tests.contract._mission_status_*` imports the compare script needs stay importable.

## 7. Churn (90 days; history deepened to 2026-10-08, so counts are a floor)

`services/` 56 commits (last: #6193, 2026-10-29; frozen since), `contracts/` 7, `mission-status-api.yml` 15, `contracts.yml` 2, `ci-router.yml` 35, `ci-module-registry.yml` 15, `tests/contract/` 33, `tests/ci/` 92, `acceptance-jvm/` 29, `pyproject.toml` 40, `Makefile` 5, `release.yml` 4, `RELEASE_CHECKLIST.md` 2, `CODEOWNERS` 4, `NOTICE` 1, `pins/` and `scripts/sync_services.py` 1 each (#6590). `ci-router.yml`, `tests/ci/` and `pyproject.toml` are hot: rebase late, keep hunks small.

## 8. Decisions this grounding forces (carried into the spec/plan)

1. `make dev-setup` runs `sync-services` for the **extras only** (≈230 KB): contributors need the goldens, the bundles and the tools, not a 95 MB read-service binary (ADR D-6 keeps the read service off user machines; a contributor machine needs it only for the nightly compare). `make sync-services` stays "everything for this host".
2. CI jobs that run conformance suites use the action in extras-only mode; only the nightly compare and the release pin check fetch the binary.
3. Tests that need a pinned asset fail closed with a remedy; none skips.
4. Tests that prove the contract **source layout** or the **tools themselves** are deleted, not repointed (they belong to events); listed as a residual.
