---
title: Events domain move — core-side plan
description: 'Core-side inventory, pin/fetch/launcher design and cut-over runbook for moving the Java event services to spec-kitty-events (ADR 2026-10-29-1).'
doc_status: active
type: explanation
audience: docs/context/audience/internal/maintainer.md
updated: '2026-10-29'
---
# Events domain move: core-side plan (session B)

**Status:** Signed off by the operator, 2026-10-29: the go is given and the issue moves are approved. The freeze gate and the governance records land first. The pin, fetch and launcher mechanism follows. The cut-over waits for spec-kitty-events' first `service-v*` release.

**Decision being executed:** operator and CEO, 2026-10-29. The Java event services (read: Mission Status Read API; write: Mission Write API / event-log write core) leave core for `spec-kitty/spec-kitty-events`, which becomes the canonical owner of the events domain. Binding: Gradle everywhere; history preserved (session A imports with filter-repo); a separate `service-vX.Y.Z` tag line in spec-kitty-events; core pins a service tag plus a sha256 per OS binary; `services/` is frozen in core from now on.

**Further operator decisions (2026-10-29, relayed by session A):**
- Layout in spec-kitty-events: `service/` (from `services/mission-status-api/`, via filter-repo `--path-rename`) plus `contracts/`, both imported with history in one pass.
- Contract bundles ride on `service-v*`. There are two release lines in total: PyPI `v*` and `service-v*`. Core's `contract-<module>-v*` line and `contracts-release.yml` retire at the cut-over.
- Events CI pins a core SHA for the lock-interop peer, the nightly corpus compare and golden regeneration.

Proposed assets per `service-v<ver>` release (session A):
- `mission-status-api-<ver>-{linux-x64,linux-arm64,macos-arm64,windows-x64.exe}`, each with a `.sha256`;
- `mission-status-api-<ver>.jar` (the JVM fallback);
- `contract-bundles-<ver>.tar.gz`, `contract-tools-<ver>.tar.gz` and `conformance-fixtures-<ver>.tar.gz`, each with a `.sha256`;
- `SHA256SUMS` and the SLSA attestation.

`command-cli` follows later under the same scheme.

---

## 1. What core holds today (Phase 0 inventory)

### 1.1 The service tree
- `services/mission-status-api/` is a standalone Gradle (Kotlin DSL) build: Spring Boot 4.1.1, GraalVM CE 25.0.2, package `org.speckitty.missionstatus`.
  - Root project `query-service`: the read-only, loopback HTTP read API.
  - `domain-model`: Mission status types, with no IO.
  - `event-log`: the JSONL codec, `StatusReducer` (a port of spec-kitty-events `reduce_parsed`), `LedgerLocks` (flock through FFM; interoperates with Python `kernel.locks`) and `TornTailRepair`.
  - `command-cli` (the write deployable) does not exist yet.
- Native targets: linux-x64, linux-arm64, macos-arm64, windows-x64. The release job is wired (tag `mission-status-api-v*`, asset plus `.sha256` per target, SLSA attestation), but **no release has ever been cut**. Binary size is therefore unknown.
- **No Python code launches either service.** The CLI wheel ships no server (ADR 2026-10-01-2 D-7). Python read paths stay native Python behind one read port (D-5).

### 1.2 Everything outside `services/` that couples to it

| Area | Files | At cut-over |
|---|---|---|
| Service workflow | `.github/workflows/mission-status-api.yml` (contract-bundle, jvm, native ×4, lock-interop ×3, gate, release, nightly-corpus) | remove; the jobs move to spec-kitty-events |
| CI routing | `ci-router.yml` (glossary group: torn-tail path; `ci` group: `services/**`; contract_tools: the conformance paths; the `tests (corpus-blocking)` job), `.github/ci-module-registry.yml` (glossary and `ci` roots), `tests/release/ci_retirement_scrub.json` | drop the `services/` roots; repoint the corpus job at fixtures fetched from the pin |
| Fleet verdict | `ci-fleet-verdict.yml` (`workflow_run.workflows`), `scripts/ci/fleet_verdict.py` `PR_WORKFLOWS` | drop "Mission Status API" |
| CI scripts | `scripts/ci/mission_status_gate_checks.py` (moves), `mission_status_corpus_compare.py` (Python oracle: stays in core, runs against the pinned binary), `lock_interop_peer.py` (Python peer: stays in core; events CI pins a core ref to run it) | per row |
| Ownership and attributes | `.github/CODEOWNERS` (`/services/mission-status-api/`, `/contracts/`), `.gitattributes` (conformance `-text`) | drop |
| Python runtime | `src/specify_cli/status/write_service_protocol.py` (client shapes), `src/runtime/next/event_bridge.py` and `_internal_runtime/events.py` (`bind_event_bridge`), `src/specify_cli/events/event_bridge.py` (`LocalFileEventBridge`), `src/kernel/locks.py`, `src/kernel/event_log_append.py` | **all stay in core** (client side) |
| Service pin tests | `tests/ci/test_mission_status_api_build.py` (~2,900 lines pinning the Gradle files and the workflow), `test_mission_status_gate_checks.py`, `test_mission_status_routing.py`, `test_lock_interop_peer.py`, `test_ci_module_wiring.py`, `test_fleet_verdict.py`, `test_fleet_main.py`, `test_contracts_workflows.py` | move to events (build pins) or rewrite against the lockfile (routing, fleet) |
| Architectural gates | `test_gate_selection_authority.py:255-263` (a services-only diff selects `ci`), `test_module_shard_registry.py:744`, `test_no_dead_modules.py` plus `_baselines.yaml` and `dead_symbol_allowlist.yaml` (`write_service_protocol`, until #6195) | update the services case; the dead-symbol entry stays |
| Goldens read from `services/` by Python tests | `tests/contract/_mission_status_conformance.py` (`conformance/`, `leak-patterns.json`), `_mission_status_artifact_goldens.py` and `test_mission_status_artifact_goldens.py` (`artifact-conformance/golden.json`), `tests/glossary/test_torn_tail_repair_goldens.py` (`torn-tail/repair-cases.json`) | fetch from the pinned fixtures asset (§3.4) |
| Python oracle on `contracts/` | `tests/contract/_mission_status_*.py`, `test_mission_status_*.py`, `test_mission_write_contract.py`, `fixtures/mission_write_refusal_parity.yaml`, `tests/specify_cli/status/test_write_service_protocol.py` | stay; repoint at the pinned `contract-bundles-<ver>.tar.gz` |
| Contracts | `contracts/{mission-status,mission-write,_shared,fixtures,lint,tools}` with its own Gradle build, `contracts.yml`, `contracts-release.yml` (tags `contract-<module>-v*`), plus contract-tool tests (`test_gradle_pin_check.py`, `test_tamper_check.py`, `test_bundle.py`, `test_client_smoke.py`) | **moves (decided)**: remove from core except `fixtures/fixture_0*.json`; retire `contracts.yml` and `contracts-release.yml`; move the contract-tool tests; acceptance-jvm fetches `install_tools.py` and `gradle_pin_check.py` from the pinned `service-v*` release (Q5, decided) |
| Packaging | `pyproject.toml` sdist excludes `services/**` and `contracts/**`; `also_copy` lists `contracts/`; `test_packaging_safety.py:240-254`; `NOTICE:19-25` (Gradle wrapper under `services/`); charter licence line 665 | drop the stale excludes and NOTICE entry; the guard keeps asserting that nothing is bundled |
| Docs | ADRs 2026-10-01-2, 10-03-1, 10-12-2, 10-13-2, 10-14-1, 10-16-1, 10-22-1, 10-27-1; `docs/architecture/{event-ledger-writers-and-readers,status-model}.md` and the C4 `01_context`, `02_containers`, `00_landscape`, `04_implementation_mapping`; `docs/development/reference/{ci-gate-mechanics,lock-interop-spike,events-in-core}.md`; `docs/plans/4-0-0-milestone-roadmap.md`; CLAUDE.md and AGENTS.md (Team Kitty producer line); charter lines 22-25, 620, 665 | pointer edits to the spec-kitty-events docs; history stays |
| Not coupled | `acceptance-jvm/` (its own Gradle build, no `services/` reference), `sonar.yml` and `sonar-project.properties` (scan only acceptance-jvm), the Makefile, `scripts/dev/cloud-session-setup.sh` (Java setup for acceptance-jvm only) | none |

### 1.3 Precedents
- **Packs pin** (`packs/*.source.yaml`, `charter.offering.packs.pack_pin`/`pack_fetch`, `scripts/sync_packs.py`, `make sync-packs`, `.github/actions/sync-packs`, `charter pack vendor`, `hatch_build.py`). It digest-verifies into `${XDG_CACHE_HOME}/spec-kitty/open-packs/<sha>/`, re-hashes on every read, and gives a poisoned cache no trust. It fetches a **git subtree** through `kernel.git.remote`, not a release asset.
- **Charter service:** no launcher, fetch or binary code exists in core (#6590 is unbuilt). The planned shape: a CLI-started, read-only, loopback, per-worktree daemon with a token; it fails closed (ADR 2026-10-03-1 Amend. 2026-10-19, spec-kitty-charter ADR-0011).
- **Write service:** shapes only (`write_service_protocol.py`, ADR 2026-10-27-1). One daemon per **git common dir**, endpoint file `<gcd>/spec-kitty-write-service/endpoint.json`. The launcher (#6676) is unbuilt. ADR 2026-10-22-1 D-5: native image, then JVM jar, else a named refusal; no Python fallback writer.

## 2. In-flight work that must merge first

None of the open PRs or pushed branches touches `services/`. The `pr/5529-*` branches are stale; that work already landed. Last `services/` commit on main: #6193, 2026-10-29.

| Session / PR | Overlap with the move | Order |
|---|---|---|
| M5 #6400, PR #6774 | `src/specify_cli/status/emit.py`, `event_log_merge.py` (the Python write path that the client cut-over later rewires) | merge before the cut-over PR |
| M3 #6457, PR #6748 | `pyproject.toml` | merge before the cut-over PR (it textually overlaps the sdist-exclude edit) |
| M11 #6610, PR #6740 | event-log retention (Python); no file overlap | any order |
| M16 #5875 (PR #6775), M6 #6354, M8 #6557, M9 #6510, #6715 | none | any order |
| Unpushed work in live sessions | unknown from the outside | ask each live session before the cut-over |

## 3. Design: one pinned-service mechanism (serves #6590, #6676 and this move)

### 3.1 Lockfile, one per service: `pins/<service>.source.yaml`

Shaped like `packs/*.source.yaml`.

```yaml
# Pin lockfile: which released build of this service core consumes. Bump with
# `spec-kitty service vendor --service <name> --tag <tag>`; never edit by hand.
service: write-service            # write-service | read-service | charter-service
repository: https://github.com/spec-kitty/spec-kitty-events
tag: service-v0.1.0               # immutable release tag; the resolved commit is recorded too
commit: <40-hex>
protocol_versions: [1]            # must intersect write_service_protocol.SUPPORTED_PROTOCOL_VERSIONS
requires_core: '>=4.0.0rc9,<5'
assets:
  linux-x64:     {name: <deployable>-<ver>-linux-x64, sha256: <64-hex>}
  linux-arm64:   {name: <deployable>-<ver>-linux-arm64, sha256: <64-hex>}
  macos-arm64:   {name: <deployable>-<ver>-macos-arm64, sha256: <64-hex>}
  windows-x64:   {name: <deployable>-<ver>-windows-x64.exe, sha256: <64-hex>}
  jvm:           {name: <deployable>-<ver>.jar, sha256: <64-hex>}   # D-5 fallback
contracts:       {name: contract-bundles-<ver>.tar.gz,            sha256: <64-hex>}   # oracle tests, write-protocol client
fixtures:        {name: conformance-fixtures-<ver>.tar.gz,        sha256: <64-hex>}   # CI only
tools:           {name: contract-tools-<ver>.tar.gz,              sha256: <64-hex>}   # acceptance-jvm: install_tools.py, gradle_pin_check.py, pins.json
```

### 3.2 Fetch and verify (Python, `kernel` layer)
- A new `kernel.service_artifacts` module: `load_service_pin`, `fetch_asset(pin, target, cache_root)`, `verify_asset`.
- Cache: `${XDG_CACHE_HOME}/spec-kitty/services/<service>/<tag>/<asset>`, re-verified by sha256 on every resolve; a mismatch is deleted and refetched. A binary with no pinned sha256 is never executed.
- Transport: HTTPS GET of the release asset URL. The remote-contact gate (`test_remote_contact_owner.py`) covers git argv only. An HTTP download is new remote contact, so I propose giving it one owner (`kernel.net.release_assets`) and a sibling gate, rather than scattering `urllib` calls.
- `make sync-services` and `scripts/sync_services.py --service all [--offline] [--check]`, plus `.github/actions/sync-services` (cache key `hashFiles('pins/*.source.yaml')`), mirror the packs tooling one for one.
- `spec-kitty service vendor --service <s> --tag <t> [--check]` bumps a pin by downloading every asset and recording its digest. It is the single documented bump path, and a `packs.yml`-style pin gate catches drift.

### 3.3 Launcher (Python, `specify_cli`)
- One `ServiceLauncher` with a per-service policy:
  - write service: scope = git common dir, endpoint file per ADR 2026-10-27-1, launch-when-down;
  - read service: per worktree, loopback, read-only; started by a consumer, not by the CLI write path;
  - charter service: per worktree, token (ADR 2026-10-03-1).
- Resolution order: `SPEC_KITTY_<SERVICE>_BINARY` (an explicit path, still digest-checked against the pin unless `--unpinned-dev` is set), then the cached native asset for the host target, then the JVM jar if a JDK 25 is present (D-5), then a refusal.
- Fail-closed codes, each with a remedy: `SERVICE_BINARY_MISSING`, `SERVICE_BINARY_DIGEST_MISMATCH`, `SERVICE_UNSUPPORTED_PLATFORM`, `SERVICE_UNHEALTHY`, `SERVICE_VERSION_MISMATCH` (protocol or instance), plus the existing `WRITE_SERVICE_ENDPOINT_*`. **No Python fallback writer.** Reads keep working with no binary present (2026-10-01-2 D-5).
- Process identity is recorded (pid plus start time plus instance_id), not the pid alone. Stale-daemon recovery follows `service.lock`.

### 3.4 Shipping the binary to users: the open decision (Q1)

| Option | How | For | Against |
|---|---|---|---|
| **A. First-run digest-verified fetch** | Universal `py3-none-any` wheel ships only the pins. The launcher fetches the host asset on first need into the cache and verifies its sha256. `spec-kitty service fetch` pre-fetches; `SPEC_KITTY_SERVICE_ASSET_DIR` serves air-gapped installs. | One mechanism for dev, CI and users. The wheel stays small and pure. No PyPI size risk. Release pipeline unchanged. | Needs network on the first write (offline first-run refuses, with a remedy). Adds a runtime download point (mitigated: the sha256 is pinned in the signed wheel). Proxy and corporate-egress friction. |
| **B. Platform wheels** | `hatch_build.py` fetches and verifies the host asset at build time and force-includes it. Releases ship per-OS wheels plus an sdist. | Works offline after `pip install`. No runtime download. | Core stops being a pure wheel: 4+ wheels per release and a cibuildwheel-like pipeline. Wheel size grows by every bundled service (write, then charter), and a binary over ~100 MB hits PyPI's per-file cap. Unsupported platforms get an sdist that must fetch at build time anyway. |
| **C. Hybrid** | A plus an optional companion `spec-kitty-services` platform wheel (the `[native]` extra) that pre-provides the binaries. The launcher prefers the companion, then the cache, then the fetch. | Offline installs supported; the core wheel stays pure. | Two release pipelines; the companion's size limits still apply. |

**Recommendation: A now, built so C can be added later without changing the launcher** (the resolution order already has an install-provided slot). The binary size is unknown until session A's first native build. If it comes in under ~60 MB and offline installs matter for 4.0.0 GA, revisit B or C.

## 4. Cut-over runbook (ordered; each step gated on the previous)

0. **Now (prep, this branch only):** this plan, the ADR draft, the charter/CLAUDE.md/AGENTS.md drafts, the pin schema. No `main` change.
1. **Freeze, on a go signal:** a `tests/architectural/test_services_frozen.py` gate (fails on any diff under `services/` against a recorded tree digest, with a planted-violation non-vacuity test) plus a CODEOWNERS note. Announce on #6409, #6676 and #6117 (comment text drafted for approval).
2. **All in-flight sessions merged** (§2); confirm that no live session holds unpushed `services/` or `contracts/` work.
3. **Session A:** filter-repo import (`service/` plus `contracts/`), Gradle unification, CI (pinned to the frozen core SHA), and the first `service-v*` pre-release with per-OS assets, the jar, the contract-bundles and conformance-fixtures assets, `SHA256SUMS` and attestation.
4. **Core PR 1 (pre-cut-over, can merge while `services/` still exists):** the pin mechanism (`kernel.service_artifacts`, `sync-services`, the composite action, `service vendor`), the launcher skeleton with fail-closed codes, and the ADR plus charter/CLAUDE.md amendments. The pins point at A's pre-release. CI fetches and verifies the pin.
5. **Core PR 2 (cut-over):**
   - remove `services/` and `mission-status-api.yml`, plus the ci-router, module-registry, fleet-verdict, CODEOWNERS and `.gitattributes` entries;
   - move the build-pin tests (or delete them, since A re-homes them) and repoint the goldens tests at the fixtures asset;
   - repoint the nightly corpus compare at the pinned binary;
   - remove `contracts/` (except `fixtures/fixture_0*.json`), `contracts.yml` and `contracts-release.yml`; repoint acceptance-jvm's tool use at the fetched contract tools;
   - drop the stale NOTICE, pyproject excludes and `also_copy` entries;
   - add docs pointers;
   - run the packaging guards, `test_pyproject_shape.py`, `test_shared_package_boundary.py`, `test_gate_selection_authority.py`, `test_module_shard_registry.py` and `test_ci_module_wiring.py`.
6. **Issue moves, on approval:** listed in §5.
7. **Later (spec-kitty-events side):** `command-cli` write service released → core bumps the write-service pin → #6195 binds `bind_event_bridge` to the client → the dead-symbol allowlist entry for `write_service_protocol` drains.

## 5. Issue retarget proposals (none actioned)

| Issue | Proposal |
|---|---|
| #6117 epic, #6159, #6194–#6199 | transfer to spec-kitty-events (Java write core); core keeps a tracking issue for the client bind (#6195's CLI half) |
| #6676 | split: native build and per-OS release → events; CLI launcher plus fail-closed codes → core (implemented with §3.3) |
| #6409, #957, #5528 | transfer to events (read-API routes); #957 and #5528 split if a contract or Python oracle half remains in core |
| #6268 | transfer to events (Java reducer port) |
| #6609 | split: Java reducer → events; the CLI's Python reducer path stays in core |
| #6185, #5533, #6193, #6675 | closed; nothing to move |
| #6608 | stays in core as the event-native epic; its Java children move, while its Python children (#6610–#6613, #6438, #6412, #6446) stay |
| #6692 | ADR on the Java writer: fold into the new ADR (§6) or close as superseded |
| #6590 | stays in core; implemented by the same pin mechanism |

Session A owns the events-side list; this is the core-side cross-check.

## 6. ADR and governance drafts (to write after the Q answers)
- New ADR `docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md`. It amends 2026-10-01-2 (D-7, D-9 to D-12: in-repo becomes external), 2026-10-22-1 (D-5: where the binary comes from), 2026-10-27-1 (the launcher's binary source), 2026-10-14-1 (the writer's home), and 3.x 2026-04-25-1 (events = PyPI package **plus** a pinned service binary). Modelled on the charter precedents.
- Charter "Shared Package Boundaries" amendment, plus CLAUDE.md/AGENTS.md pointer updates (Team Kitty producer line, Shared Package Boundary, Modularity SSOT).

## 7. Operator decisions (2026-10-29)
- **Q1 shipping:** option A, first-run digest-verified fetch; the wheel stays pure. The resolution order keeps an install-provided slot, so option C remains possible later.
- **Q2 contracts:** move with the services; the bundles ride on `service-v*`.
- **Q3 read service:** CI-only pin. The CLI never launches it; ADR 2026-10-01-2 D-7 holds.
- **Q4 freeze gate:** a small standalone PR once the live mission sessions have merged.
- **Q5 acceptance-jvm tools:** fetched from the pinned `service-v*` release, not copied. Session A publishes them as a separate `contract-tools-<ver>.tar.gz` (`contracts/tools/*.py`, `pins.json`, `enum_pins.json`; no fixtures), so `contract-bundles` stays pure contract data.
