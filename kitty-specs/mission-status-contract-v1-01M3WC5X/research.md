# Research: Mission Status contract v1

Mission `mission-status-contract-v1-01M3WC5X` (#5558). Phase 0 output of the plan. Each entry gives the decision, the rationale, the alternatives considered, and the evidence. Everything marked **verified** was read or run on this checkout during planning; everything marked **to verify** is deliberately left to the named work package because it cannot be known offline (tool versions, generator behaviour).

## R-1 Contract resolution in the reality check (OQ-1)

- **Decision.** A Python reference resolver, `contracts/tools/contract_resolver.py`, is the only code that reads the split contract in Python. The reality check, the parity script and every `contracts/tools/` check import it. `contracts/tools/resolver_parity.py` proves in the contracts workflow that the resolver's fully dereferenced tree equals the CI bundle's.
- **Rationale.** The corpus-marker jobs (`tests-corpus` in `ci-router.yml` and `built-in-corpus-suite` in `packs.yml`) have no JVM and must not be edited (C-003, FR-017, SC-008). The reality check still has to give a real verdict in them and may never skip (FR-019). The resolver implements only what the contract uses, which keeps it small enough to prove equal.
- **Alternatives.** (a) Add a JDK and Gradle step to the two corpus jobs: edits two existing jobs, excluded by the spec. (b) Commit the bundle and read it: the bundle is a build product that is never committed (CL-5, FR-001). (c) Have the test download the CI artefact: makes a per-change test depend on another job, the network and artefact access from forks, and gives a local run no verdict. (d) A second resolver with no equality proof: excluded by the OQ-1 constraint ("no second unproven resolution authority").
- **Resolver scope (what it must support, and refuse).** Support: relative file `$ref` (including into `contracts/_shared/`), in-file JSON-pointer fragments, sibling keywords beside `$ref` (legal in 3.1), and the composition keywords `allOf`, `oneOf`, `anyOf`. Refuse loudly, with a stable message code: a URL `$ref`, an absolute-path `$ref`, a `~1` pointer, a cycle, an unresolved target, a non-mapping document. Output: one dereferenced tree plus the three counts (path items, schemas, resolved references) that the parity script prints.
- **Evidence.** Locked dependencies available: `jsonschema` 4.26.0 (with `referencing`), `rfc3339-validator`, `jsonpointer`, PyYAML 6.0.3, all importable in the repository's `.venv` (verified). `openapi-spec-validator` and `openapi-schema-validator` are **not** installed, so OpenAPI-document validation is the JVM tool's job and payload validation is `jsonschema` with the Draft 2020-12 validator, which is the 3.1 schema dialect.

## R-2 Gradle provisioning without a wrapper jar

- **Decision.** `contracts/tools/install_tools.py` downloads the pinned Gradle distribution archive over HTTPS, verifies its sha256 against `contracts/tools/pins.json`, and only then unpacks it. No `gradle-wrapper.jar` is committed.
- **Rationale.** R-10 of the spec prefers a pinned distribution over a committed binary. FR-018's parenthetical (`distributionSha256Sum`) is a wrapper-properties field and needs the wrapper, so the manifest check replaces it with the same guarantee: a missing or mismatching checksum fails before execution.
- **Alternatives.** Commit the wrapper (jar plus properties) and validate the jar with a validation action: adds a committed binary and a third-party action. A setup action that downloads Gradle by version: its checksum source is the same host as the download.
- **Dependency verification.** `gradle --write-verification-metadata sha256 <task>` (Java toolguide, `packs/built-in/toolguides/java-supply-chain.toolguide.yaml`) generates `contracts/gradle/verification-metadata.xml`; the build runs with strict verification. The Gradle plugin portal and Maven Central are the only repositories the build may use. The tamper test is a copy of the metadata with one checksum altered at run time.
- **To verify at IC-07.** The exact Gradle, plugin, vacuum and oasdiff versions, their publication dates and checksums (none are invented in the plan).

## R-3 Bundler fidelity spike (first task of IC-07)

- **Why.** The contract depends on constructs a Java OpenAPI toolchain may not round-trip cleanly: object-valued extension keywords on nested properties (`x-source`, structured `x-derived`, `x-provisional`), `unevaluatedProperties`, type arrays such as `["string","null"]`, `const`, sibling keywords beside `$ref`, `format: date-time`, `pattern`, a `text/event-stream` response with a schema, and `examples`. If the `openapi-yaml` generator drops or rewrites any of these, parity fails for reasons that are not the resolver's.
- **Plan.** Build one minimal module that uses every construct above, bundle it in the contracts workflow on the draft PR, and diff the bundle with the resolver's tree. The result is a table of **named normalisations** (a finite list, each with a planted test in the parity script's unit-test module); anything not on the list fails parity. Record the table here when known.
- **Escalation E-1.** If a construct the contract needs does not survive, the plan does not pick a replacement tool. Options in preference order: a longer documented normalisation list; a different Node-free bundler for the same validate step. The second changes CL-6 and is the maintainers' decision.
- **Status.** To verify. No JVM exists on the planning workstation, so this cannot be run before the draft PR.

## R-4 Breaking-change baseline source (PQ-3)

- **Decision.** Rebuild the baseline from the latest tag matching `contract-<module>-v<semver>`: `git archive` of the module and `_shared/` at that tag into a temporary directory, built with the same pinned Gradle build, then compared with oasdiff against the candidate bundle.
- **Rationale.** Same build path for baseline and candidate; no dependency on a release host; works offline once tools are installed. FR-016 allows "rebuilt or downloaded as a verified release asset".
- **Alternative.** Download the release asset and verify its sha256: needs network access to the release host and trusts that the asset equals what the tag builds.
- **First release.** No tag exists. `breaking_check.py` prints a loud "no baseline" notice, writes it to the job summary, and allows it only when `info.version` is the module's initial version and `CHANGELOG.md` carries the initial entry. It fails in a shallow clone (`git rev-parse --is-shallow-repository`) or on any tag-listing error (D-12, FR-016).

## R-5 Router selection, simulated (verified)

`scripts.ci.gate_selection.select_gates` and `select_modules` were called with explicit path sets on a scratch copy of `ci-router.yml` with one added line, `- 'contracts/**'`, in the `corpus` filter group (no workflow file in the tree was modified).

| Changed paths | Today (no glob) | With the glob |
|---|---|---|
| `contracts/mission-status/openapi.yaml` | no test job selected; always-on lint jobs only | group `corpus`, job `tests-corpus`, no code shard, no module shard |
| `contracts/tools/<script>.py` plus `docs/x.md` | no test job | groups `corpus` and `docs`, `tests-corpus` selected, no code shard |
| `.github/CODEOWNERS` | no test job | nothing selected by the router (the contracts workflow's own path filter covers it) |
| `tests/contract/test_mission_status_reality.py` alone | no test job | no test job (accepted residual R-14: a change confined to the reality check selects nothing) |
| `scripts/ci/fleet_verdict.py`, `tests/ci/test_fleet_verdict.py` | module `ci` | module `ci` |
| `tests/architectural/test_ci_corpus_trigger_completeness.py` | group `architectural`, job `architectural-heavy` | same |

Consequence for tests: a `tests/contract/` module with only `fast` or `contract` markers is collected by no per-change job; every new module there carries `corpus` on one line and a registry row. A new test that must run on an edit confined to `.github/workflows/**` goes in `tests/ci/`, whose module row selects it.

## R-6 Hidden and easily missed gates (verified)

| Gate | What it pins | Effect on this Mission |
|---|---|---|
| `tests/release/test_pinning_inventory_fresh.py` | `tests/release/pinning_rule_inventory.json`, re-derived by `scripts/ci/derive_pinning_inventory.py` and compared byte for byte, including recorded line numbers in `scripts/ci/fleet_verdict.py`, `tests/ci/test_fleet_verdict.py`, `tests/ci/test_fleet_main.py` | Regenerate with the script after editing those files; new text must not reference its three subjects. Baseline green. |
| `tests/ci/test_workflow_script_import_guard.py` | Workflow-invoked bare scripts must not import `scripts.*` at module level | `contracts/tools/` scripts import only stdlib, locked dependencies and their siblings. |
| `tests/release/test_release_ci_ownership.py` | A frozen set of seven net-new workflows under the `introduced` disposition; a text scan of every workflow file for the retired private-repo fence | No row is added to the convergence map; the two new workflow files contain neither retired string. The on-disk workflow set is not asserted equal to the map, so two new files do not trip it (read, not assumed; run as part of the named set at implement start). |
| `tests/architectural/test_dual_mode_contract.py` | Dual-mode and dispatch contract over a discovered, listed set of reinstated workflows | The new workflows are not in its candidate list; run at implement start to confirm. |
| `tests/architectural/test_ci_router_transcription_guards.py` | Router filter groups equal the scrub JSON `groups` rows | `corpus` is not a scrub group row, so the added glob does not trip it. |
| `test_reusable_workflow_ceiling_respected` | At most 20 workflow files | 17 today (counted), 19 after. |

## R-7 Corpus measurements (verified, own-directory read, read-only)

A throwaway read-only script called `materialize_snapshot` for every `kitty-specs/*/` directory that has a `meta.json`; the working tree was unchanged afterwards (`git status` identical).

- 539 Missions with `meta.json` (this Mission's scaffold included), 2936 snapshot work packages, 0 exceptions, about 0.5 s total.
- These match the spec's figures (539 and 2936), so the floors of 500 Missions and 2800 snapshot work packages sit below the measured values with headroom.
- 3125 `tasks/WP*.md` files and the 52-Mission disagreement list are quoted from the spec and re-measured at implement start (IC-01), not copied.
- Write-path audit: `materialize_snapshot` reads through `read_event_stream` and `read_events_raw` (a read-only `open`), then reduces in memory; only `materialize` writes `status.json`. The reality check calls the first and never the second.

## R-8 Baseline (verified)

One invocation of the named gate files on the planning base: **265 passed, 1 skipped, 0 failed**, 68 s: corpus-trigger completeness, no-duplicate-suite, workflow-coherence, module-shard registry, fork guard, fleet verdict, fleet main, pinning-inventory freshness. The tree was identical to `main` for every file under test at that moment. The rest of the baseline (corpus-marked `tests/contract` modules, the router derivation guards, a CI job log for timing, floors) is taken at implement start; see the plan's Baseline section. No pre-existing red was found, so no tracker issue is owed under the Pre-existing Failure Reporting Rule at this point.

## R-9 Supply-chain evidence (DIRECTIVE_051, `supply-chain-install-safety`)

The plan adds dependencies in two ecosystems (JVM through Gradle; Go binaries). Python gains none. Results per threat-class control; none is silently skipped. "Result" is the design decision now; the measured outcome is recorded in the PR body by IC-07 and any adverse result needs explicit operator acknowledgement.

| Control | Design for this Mission | Result now | Evidence captured at IC-07 |
|---|---|---|---|
| 1 Registry authenticity | JVM artefacts only from the Gradle plugin portal and Maven Central, strict verification; Go binaries and the Gradle distribution only from their vendors' official HTTPS release locations; no mirror | Designed | The repositories block of the Gradle build; the download URLs in `pins.json` |
| 2 Package freshness | `pins.json` records each artefact's publication date; a version published less than 14 days before the pin date is adverse and needs operator acknowledgement | Designed | Dates in `pins.json`; the adverse list (empty expected) |
| 3 Deny-by-default lifecycle scripts | Gradle plugin resolution runs no install scripts; the Go binaries are downloaded and checksum-verified, never piped to a shell (no download-and-run one-liners); no package-manager install in the workflow | Designed | The workflow text, asserted by the SHA-pin and no-unpinned-install guard tests |
| 4 Lockfile-driven installs | `verification-metadata.xml` (sha256 for every resolved artefact, strict mode) and `pins.json` are the lock; Python uses the existing `uv.lock` through a frozen sync | Designed | The two files; the tamper fixtures |
| 5 Incident list and IoC posture | Before each pin, the vendor's advisory feed for the artefact is read and the result recorded; no incident package name is hard-coded in the repository | To do at IC-07 | The cited advisory feeds consulted and the result |

Adversarial challenge pass: **deferred to the orchestrator** (this plan author had no sub-agent budget); no contested finding exists to disposition. It is requested after the plan point-cut and before implementation, per the `adversarial-squad-deployment` procedure; the lenses that matter most are supply chain, gate non-vacuity and the bundler-fidelity risk.

## R-10 Event stream cursor naming (verified)

The spec's stream cursor `{offset, invariant}` maps to `TailCursor` in `specify_cli/status/tail_reader.py`, whose fields are `offset` and `content_invariant`; the empty-digest sentinel is the module constant `EMPTY_DIGEST` ("nothing consumed yet"). The contract field is `invariant`, so the citation names the class and the attribute `content_invariant`, which is a bare annotated class attribute. The citation check therefore must treat an annotated class-level target as a defined name (decision PQ-10); the spec's own example would otherwise not resolve. `ResumeRefused` in the same module carries the four refusal reasons the contract maps to `Problem` responses.

## R-11 Dashboard evidence is recoverable but not citable (verified)

The dashboard sources removed by #5545 and #5530 remain readable at the recorded base commit with `git show d78aa2345:src/specify_cli/dashboard/scanner.py` (an ancestor of this branch; `_derive_mission_status`, `_derive_next_action`, `get_workflow_status`, `build_mission_registry` and `scan_all_features` are present there). That is how the pinned expected-output fixture is produced once (IC-09) without reintroducing the code. No contract citation may point at a path that `git ls-files` does not list on the branch tip; the citation check enforces it.

## R-12 What is not known yet (honest list)

1. Bundler fidelity (R-3): needs CI.
2. Exact tool versions, dates and checksums (R-2, R-9): chosen at IC-07.
3. How `diff-cover` behaves on a pull request with no changed `src/` lines: read at implement start from an existing docs-only PR; baseline step 6.
4. Whole-job duration of `tests-corpus` after this Mission (NFR-001): measured from the first draft-PR run.
5. Whether the two new workflow files trip `test_dual_mode_contract.py` or the release-ownership guard: read as no; run as named files at implement start to confirm.
6. #5557 may merge before this Mission does and change the router, the registry and the gate files; the plan's edits are additive and re-verified after each rebase.
