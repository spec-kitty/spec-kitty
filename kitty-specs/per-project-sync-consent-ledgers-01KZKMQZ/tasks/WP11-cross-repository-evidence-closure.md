---
work_package_id: WP11
title: Coordinated core acceptance and immutable evidence
dependencies:
- WP09
- WP10
requirement_refs:
- FR-001
- FR-007
- FR-016
- FR-019
- FR-020
- FR-022
- FR-031
- FR-033
- FR-034
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- NFR-005
- NFR-006
- NFR-007
- C-002
- C-004
- C-005
- C-006
- C-007
- C-010
planning_base_branch: feat/per-project-sync-consent
merge_target_branch: feat/per-project-sync-consent
branch_strategy: Planning artifacts for this mission were generated on feat/per-project-sync-consent. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/per-project-sync-consent unless the human explicitly redirects the landing branch.
subtasks:
- T049
- T050
- T051
- T052
- T053
- T054
history:
- at: '2026-08-09T17:05:36Z'
  actor: planner
  action: Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/evidence/build_project_sync_consent_manifest.py
create_intent:
- tests/integration/test_project_sync_six_project.py
- tests/integration/test_project_sync_stale_generation.py
- tests/contract/test_cli_saas_sync_contract.py
- tests/sync/test_project_store_cross_platform.py
- tests/perf/test_project_discovery_benchmark.py
- tests/evidence/test_project_sync_consent_manifest.py
- scripts/benchmarks/bench_project_discovery.py
- scripts/evidence/build_project_sync_consent_manifest.py
- .github/workflows/project-sync-consent-evidence.yml
- docs/guides/project-sync-consent.md
execution_mode: code_change
owned_files:
- tests/integration/test_project_sync_six_project.py
- tests/integration/test_project_sync_stale_generation.py
- tests/contract/test_cli_saas_sync_contract.py
- tests/sync/test_project_store_cross_platform.py
- tests/perf/test_project_discovery_benchmark.py
- tests/evidence/test_project_sync_consent_manifest.py
- scripts/benchmarks/bench_project_discovery.py
- scripts/evidence/build_project_sync_consent_manifest.py
- .github/workflows/project-sync-consent-evidence.yml
- docs/guides/project-sync-consent.md
- CHANGELOG.md
role: implementer
tags: []
tracker_refs:
- Priivacy-ai/spec-kitty#3262
- Priivacy-ai/spec-kitty-saas#585
- Priivacy-ai/spec-kitty-saas#584
- Priivacy-ai/spec-kitty-saas#609
---

## ⚡ Do This First: Load Agent Profile

```text
/ad-hoc-profile-load python-pedro
```

Read every mission artifact, WP01's final censuses, and all merged WP outputs.
Require the explicit SaaS checkout/ref/contract digest attested by WP05, approved
SaaS WP08 evidence, and reviewed SaaS WP02 anti-rematerialization authority.
This package changes acceptance/evidence code, so it uses the Python
implementation profile rather than an architecture-only reviewer profile.

## Objective

Prove the core-owned half of coordinated acceptance and emit an immutable,
schema-versioned checksum manifest binding exact core/SaaS/tombstone commits,
canonical contract digest, tests, mutants, raw benchmark samples, retention
coordinates, and issue-to-WP ownership. Reference SaaS-owned evidence without
regenerating or claiming it.

## Hard prerequisites and exclusions

Inputs are explicit flags/paths for SaaS checkout, expected SaaS commit, canonical
contract SHA-256, SaaS WP02 evidence URI/checksum, and SaaS WP08 evidence
URI/checksum. Resolve and verify them; refuse ambient `../spec-kitty-saas`, branch
names without commits, dirty contract drift, or mismatched digests.

Hosted mutation uses only local/test SaaS or an explicitly authorized dynamically
discovered Upsun branch/develop environment. `team.spec-kitty.ai` is production and
read-only health at most. Never inspect, delete, move, reassign, or decide the
historical 1,322 events. Core evidence cannot close SaaS #585.

## Subtask T049 — Candidate and prerequisite attestation

Verify core HEAD, SaaS candidate HEAD, contract digest, SaaS WP08 evidence
checksum, and tombstone commit/evidence checksum. Persist sanitized immutable
identities. Sequence is SaaS WP04 contract -> core WP05 consumer -> core
WP06–WP09 and reviewed SaaS WP02/WP08 -> WP11. Fail closed if any input
is floating, missing, or inconsistent.

## Subtask T050 — Core conforming six-project proof

Create deterministic A–F projects from the contract matrix. Capture exact
sanitized CLI HTTP/WebSocket bytes and prove only admitted A appears; B–F markers
and IDs are absent. Core owns this omission evidence. It does not submit B–F to
the server: SaaS owns bypass/legacy refusal and zero durable/readable/activity/
audit/dossier/anomaly/broadcast side effects.

## Subtask T051 — Real stale-generation parking

Against local/test or an explicitly authorized branch environment, admit A at g,
prepare/pause a real CLI write, advance server authority, then release stale g.
Assert correlated `project_not_admitted`, terminal parking for only that row, no
transient retry, and no revival after readmission. Core owns client parking;
SaaS owns server refusal/side-effect evidence.

## Subtask T052 — Cross-platform physical isolation

Cover Linux/macOS/Windows path and UUID forms, Unicode display names, symlinks,
same slug/different UUID, and same UUID/multiple worktrees. Instrument connections,
filesystem/table opens over capture, select, send, result, retry, migrate,
diagnose, purge, and opt-out. A operations must open no B resources. A shared
resolver mutant must make the test fail.

## Subtask T053 — Reproducible discovery benchmark

Generate 100 deterministic stores: 80 fresh deny hints and 20 authority reads.
Record OS/filesystem/storage/CPU/Python/SQLite/commit/seed and raw JSON samples.
Warm is 200 randomized scans in one warmed process; process-cold is 30 fresh
processes without claiming OS-cache eviction. Correctness requires zero payload
table opens for denied projects. Documented local-SSD release gates are warm p95
<=500 ms and process-cold p95 <=1 s; CI timing is advisory.

## Subtask T054 — Immutable manifest, retention, docs, and issue closure map

Run named mutants (shared store, ambient grant, removed final gate, cross-paired
context, grant-valued hint, ordinary sealed-history selection). Generate
`build/evidence/project-sync-consent/<core-commit>/manifest.json` with schema
version, exact candidate commits/digest, command/result records, artifact paths,
SHA-256 for every raw file, producer/owner (`core` or `saas`), non-overlapping
claim, creation time, and retention URI/expiry. CI uploads the immutable bundle
for at least 90 days; release/tracker evidence records the persistent retention
coordinate and checksum before closure.

Update the issue matrix with explicit WP mappings and tracker-ready evidence that
separates core recurrence prevention, SaaS admission/anti-rematerialization evidence, and the
still-open historical Human-in-Charge disposition. Write dated Divio guidance
and changelog. Run full charter gates after consolidation.

## Branch Strategy

Run `spec-kitty agent action implement WP11 --agent <name>` only after WP09/WP10
approval and all external prerequisites attest. Use the computed lane and
governed merge. Do not push, open a PR, deploy, or mutate hosted state without
separate authorization.

## Test strategy

Commit the core six-project exact-byte test red-first. Run all owned tests, the
benchmark correctness gate, full architecture suite, pinned contract harness,
mutations, ruff, strict mypy, and charter-approved full suite. Verify the manifest
test detects one-byte artifact changes, candidate mismatch, duplicate ownership,
and missing/expired retention metadata.

## Definition of Done

- Exact candidate commits and canonical contract digest are verified.
- Core CLI bytes contain only A; SaaS bypass evidence is referenced, not copied.
- Stale-generation refusal parks terminally on the client.
- Cross-platform isolation and benchmark gates pass with raw samples.
- Manifest checksums, ownership, retention, and issue mappings verify.
- Evidence preserves production and historical-cohort exclusions.

## Risks and reviewer guidance

Reject ambient sibling discovery, floating refs, a single scenario claimed as
both omission and refusal, duplicated evidence ownership, mutable/no-checksum
bundles, missing retention, mocked tombstones, or performance claims without raw
samples and runtime metadata. Verify production cannot be selected accidentally.
