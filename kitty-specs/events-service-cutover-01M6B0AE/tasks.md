# Work Packages: Events service cut-over in core

**Inputs**: `kitty-specs/events-service-cutover-01M6B0AE/` — spec.md, plan.md, research.md, research/code-grounding.md, data-model.md, contracts/sync-services-cli.md, quickstart.md
**Topology**: `single_branch` — WPs run one after another in the repository root checkout on `issue-6915-events-service-cutover`.
**Tests**: required (the spec makes every FR test-backed; ATDD-first per the charter).

Completion is event-sourced: record it with `spec-kitty agent tasks mark-status T### --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red acceptance tests: extras-only, unpack, `--extras-path`, dev-setup assertion flipped | WP01 | |
| T002 | Vendor `pins/read-service.source.yaml` with `spec-kitty service vendor` | WP01 | |
| T003 | `--extras-only` in `scripts/sync_services.py` | WP01 | |
| T004 | Verified unpack, `extras_root()`, `--extras-path` | WP01 | |
| T005 | Action `extras-only` input, `make dev-setup`, comments, `pins/README.md` | WP01 | |
| T006 | Local proof: `make sync-services`, `ARGS=--check`, pin gate, sync tests | WP01 | |
| T007 | `tests/pinned_service_assets.py` (fails closed) + its tests | WP02 | |
| T008 | Mission-status conformance reads the pinned fixtures | WP02 | |
| T009 | Artifact goldens read the pinned fixtures; drop the rewrite mode | WP02 | |
| T010 | Glossary torn-tail goldens read the pinned fixtures; drop the rewrite mode | WP02 | |
| T011 | Oracle tools from the pinned contract tools; `Contract` on the bundle; schema-by-title helper | WP03 | |
| T012 | Mission-status contract tests on the bundle (detail, drift, ops, project, reality, artifacts, payloads) | WP03 | |
| T013 | Mission-write contract test on the bundle | WP03 | |
| T014 | `test_scenario_contract` loads `codeowners_check` from the pinned tools | WP03 | [P] |
| T015 | Corpus compare script reads the pinned tools (`--tools-root`) | WP03 | [P] |
| T016 | Router: sync-services in the two conformance jobs; path groups re-pointed | WP04 | |
| T017 | Module shards fetch the pinned extras (glossary torn-tail goldens) | WP04 | |
| T018 | Registry, retirement scrub, fleet verdict re-pointed | WP04 | |
| T019 | Routing/wiring/fleet tests re-pointed; services-only routing case → pins-only | WP04 | |
| T020 | Red workflow tests: nightly compare job, no workflow runs `contracts/tools/` | WP05 | |
| T021 | Nightly corpus compare on the pinned native binary (`ci-nightly.yml`) | WP05 | |
| T022 | acceptance-jvm Gradle pin check wrapper over the pinned tool | WP05 | |
| T023 | acceptance-bdd, sonar and cloud setup install tools from the pinned tools | WP05 | |
| T024 | Red absence test for the removed copies | WP06 | |
| T025 | Delete `services/`, moving `contracts/`, the three workflows | WP06 | |
| T026 | Delete freeze gate, build-pin tests, tool/source-layout tests, gate-checks script | WP06 | |
| T027 | Drop CODEOWNERS, `.gitattributes`, NOTICE, sdist exclude, duplicate-suite allowlist entries | WP06 | |
| T028 | Red release-workflow tests | WP07 | |
| T029 | `release.yml`: fetch + check service pins beside the packs check; wheel holds pins, no binary | WP07 | |
| T030 | `RELEASE_CHECKLIST.md` service-pin steps | WP07 | |
| T031 | CLAUDE.md, AGENTS.md, charter: pin built, services gone | WP08 | |
| T032 | Docs pointers to spec-kitty-events; plan and reference pages | WP08 | [P] |
| T033 | Changelog Unreleased entry | WP08 | [P] |

## Phase 1 — Foundation

### WP01 — Read-service pin and fetch tooling (P1)

Prompt: [tasks/WP01-pin-and-fetch-tooling.md](tasks/WP01-pin-and-fetch-tooling.md)

- **Goal**: core holds a verified pin of `service-v0.1.0-rc.1`; the fetch tooling can fetch the extras only and unpack them into a digest-keyed directory; `make dev-setup` fetches the extras.
- **Independent test**: `make sync-services ARGS=--check` passes after `make sync-services`; `tests/ci/test_service_pins_gate.py` has a live case; `tests/ci/test_sync_services.py` green except its wiring ratchet (red by design until WP04 — the acceptance test of FR-005).
- **Subtasks**: T001, T002, T003, T004, T005, T006
- **Dependencies**: none
- **Risks**: `vendor` refusal → stop and report (C-001). Tar member safety.

## Phase 2 — Consumers read the pin

### WP02 — Test reader and golden repoint (P1)

Prompt: [tasks/WP02-test-reader-and-goldens.md](tasks/WP02-test-reader-and-goldens.md)

- **Goal**: one fail-closed test reader; conformance, artifact-golden and torn-tail tests read the pinned fixtures.
- **Subtasks**: T007, T008, T009, T010
- **Dependencies**: WP01
- **Risks**: the conformance test copies trees into a scratch dir at a fixed relative layout.

### WP03 — Oracle and contract tests on the bundle (P1)

Prompt: [tasks/WP03-oracle-on-bundle.md](tasks/WP03-oracle-on-bundle.md)

- **Goal**: the Python oracle, the mission-status/mission-write contract tests, the scenario contract and the corpus script read the pinned bundle and tools.
- **Subtasks**: T011, T012, T013, T014, T015
- **Dependencies**: WP02 (uses its reader)
- **Risks**: direct `schemas/<X>.yaml` and `examples/<file>` reads must keep their meaning.

## Phase 3 — CI

### WP04 — Router, registry and fleet wiring (P1)

Prompt: [tasks/WP04-router-registry-fleet.md](tasks/WP04-router-registry-fleet.md)

- **Goal**: the conformance jobs and module shards fetch the pinned extras; routing names no `services/` path; fleet verdict forgets the removed workflows.
- **Subtasks**: T016, T017, T018, T019
- **Dependencies**: WP03
- **Risks**: `ci-router.yml` is hot; several tests pin job shapes.

### WP05 — Nightly compare and acceptance-jvm tools (P2)

Prompt: [tasks/WP05-nightly-and-acceptance-jvm.md](tasks/WP05-nightly-and-acceptance-jvm.md)

- **Goal**: a nightly job compares the pinned native binary with the oracle; acceptance-jvm tools come from the pin.
- **Subtasks**: T020, T021, T022, T023
- **Dependencies**: WP04
- **Risks**: the released `gradle_pin_check.py` bare run scans a missing `contracts/` subproject.

## Phase 4 — Remove and release

### WP06 — Remove the copies and their coupling (P2)

Prompt: [tasks/WP06-remove-copies.md](tasks/WP06-remove-copies.md)

- **Subtasks**: T024, T025, T026, T027
- **Dependencies**: WP05
- **Risks**: a missed reference; the freeze gate is deleted per its own exit clause (C-004).

### WP07 — Release verifies the service pins (P2)

Prompt: [tasks/WP07-release-pin-check.md](tasks/WP07-release-pin-check.md)

- **Subtasks**: T028, T029, T030
- **Dependencies**: WP06
- **Risks**: textual overlap with PR #6949 — keep the hunks minimal.

## Phase 5 — Polish

### WP08 — Governance, docs and changelog (P3)

Prompt: [tasks/WP08-governance-and-docs.md](tasks/WP08-governance-and-docs.md)

- **Subtasks**: T031, T032, T033
- **Dependencies**: WP07
- **Risks**: the charter wins over CLAUDE.md; terminology guard.

## Dependency chain

WP01 → WP02 → WP03 → WP04 → WP05 → WP06 → WP07 → WP08 (strictly sequential, `single_branch`).

MVP: WP01 (the pin and its tooling) — every later WP reads it.
