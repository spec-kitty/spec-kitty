---
doc_status: draft
updated: '2026-11-28'
---

# Workstream F: allocation of execution responsibilities

Audience: the architect and the synthesis reviewers. They know the ecosystem and need allocations, their states and the evidence for them. They do not need the background explained.

## Profile and directives applied

Profile `analyst-annie` (loaded with `spec-kitty agent profile show`). Charter context: `--action specify`. Directives applied:

- DIRECTIVE_032 (conceptual alignment): `evidence/F/coordination-responsibilities.txt` states, before any classification, how this workstream read each of the 15 execution responsibilities.
- DIRECTIVE_003 (decision documentation): every deviation below is recorded.
- DIRECTIVE_047 (audience-oriented writing).

Profile boundary: the profile avoids architecture choices. That fits the envelope, which asks for no verdict and no recommendation. No conflict arose.

## Method and tools

- Code was read at core `head` 5c4fc5a. The working tree differs from `head` only under `docs/` and `kitty-specs/`; checked with `git diff --stat`.
- Repositories read:
  - spec-kitty-events 646e330
  - spec-kitty-orchestrator 8be32b1
  - spec-kitty-mcp a6bdf6b
  - spec-kitty-container 1ff99fe
  - fleet-kitty e3b39b8
  - event-router 8f4bb64
  - spec-kitty-planning 89f52a4 (activity only; no execution plan found after 2026-10-15)
- Every execution ran in disposable clones under scratch:
  - Core used `/home/user/spec-kitty/.venv` Python 3.11.15 and pytest 9.0.3, with `PYTHONPATH=<clone>/src`.
  - The orchestrator ran in a uv 0.11.32 venv with Python 3.11 and pytest 9.2.0.
- CLI: spec-kitty-cli 4.0.0rc9. CodeGraph has no index here, so it was not used.

Executed checks:

- Named core test files: 14 batches, 1182 passed, 0 failed.
- `dispatch` in two forms: `--dry-run` (4 purposive requests) and a real Op, which was opened, listed by `doctor ops` and closed as abandoned.
- `orchestrator-api` help, `contract-version` and the removed verb.
- spec-kitty-orchestrator against core `head`: 90 unit and conformance tests, plus the fake-agent end-to-end selection.
- A timeout probe.

## Coverage

**Covered:**

- All 15 M07a items and all 15 M07b items.
- The orchestrator-api contract.
- Dispatch versus context preparation.
- Unit identifiers.
- Interruption and recovery.
- The external loci.
- The single case.
- The 25-cell operations matrix.

**Not covered:**

- Agents with real credentials (the orchestrator's `real_agents` tests).
- Fleet-kitty's runtime: read at README and grep level only.
- The interruption path of the `next` run (`run_lock`, `StaleAdvancePlan`).
- The Go "Orchestrator 2" implementation that ADR 2026-10-07-2 cites. Its repository is not attached.

## Measures

| Measure | Value | Findings |
|---|---|---|
| M07a locus | core runtime 11, external coordination system 2 (dispatch, supervision), none 2 (cancellation, attachment) | F-F-001 |
| M07a state | verified by execution 12, delegated by recorded intent 1 (dispatch), missing 2 | F-F-001, F-F-005 |
| M07a share verified | 12/14 = 85.7%, with X04 dispatch excluded as delegated (multi-agent-orchestration.md:18-21; ADR 2026-06-02-1/2). Core-locus items only: 11/11 | F-F-001 |
| M07b locus | core runtime 14; spec-kitty-events 1 (ordering of status events) | F-F-002 |
| M07b state / share | verified 15/15, nothing excluded | F-F-002 |
| orchestrator-api | 27 verbs; contract 1.31.0; 13 capabilities unavailable (leases, watch, remote serving, ...) | F-F-006 |
| Versioning | `merge-mission` removed inside 1.6.0 with no ledger entry; 2 of 3 consumers still name it | F-F-007, F-F-008, F-F-028 |
| API vs CLI | consolidate-mission takes 5 options, `consolidate` takes 33; attestation, resume and abort are CLI-only; the API's stale-lane remedy prints host CLI commands | F-F-009 |
| Dispatch vs context | dispatch selects a profile, builds context and writes an Op record. It starts nothing and records no pid, session or model | F-F-003, F-F-004, F-F-014 |
| Identifiers | 14 mapped. 8 are minted in core. Session and attempt exist only as events contracts. The Op-to-work-package join runs one way | F-F-013, F-F-015 |
| Interruption | 4 holders with tested recovery. Nothing records what a stopped executor was doing | F-F-017 |
| External loci | the orchestrator passed 9 of 10 end-to-end tests against `head` (the 1 failure is a stale version pin); mcp is an adapter; container is an environment; fleet-kitty is an issue-driven factory with no orchestrator-api use; event-router is bootstrap | F-F-018, F-F-019 |
| Operations matrix | 25 cells: verified 9, present but unverified 2, specified only 1, missing 13; attach missing for all 5 targets | F-F-021 |
| Single case | 15 log items: 9 corroborated, 4 partially, 2 uncorroborated | F-F-022, F-F-023 |

Findings: 28 in total, 26 observations and 2 interpretations (F-F-027, F-F-028).

## Deviations

1. **M07b says "commit the list".** The envelope forbids workstream commits. The list was written at 09:05:36Z, before any classification, for the coordinator to commit. Recorded in F-F-002.
2. **Single locus per item.** The rubric asks for one locus, but several responsibilities are split. Rule used: count the holder of the operative act; record advisory or record-only parts as the secondary locus in the CSVs. Two consequences:
   - X06 supervision is counted as external: core only detects; spec-kitty-orchestrator times out.
   - X07 cancellation is counted as missing: core only records, and no repository stops a running unit on request.
3. **Meaning of "verified".** "Verified by execution" means the named test files covering the responsibility pass at `head`. It does not mean every path is covered.
4. **X06 evidence is a probe.** X06 rests on a probe this workstream wrote, not on a project test: the orchestrator has no test for the timeout path. Marked in F-F-011.

## Blocked items

- **Core test runs: blocked, then unblocked.** The first 4 attempts were killed by the shared memory cgroup during conftest's first full scan for wall-clock assertions (about 2 GB). The content-addressed scan cache was copied from the main checkout, and then every batch ran (F-F-026). This is a coverage limit, not a finding about the code.
- **Real-agent end-to-end tests:** not attempted, for lack of credentials.

## Exploratory observations (not answers to a measure)

- **Self-declared policy.** The policy metadata is declared by the caller and never enforced. The default policy of spec-kitty-orchestrator declares `dangerous_flags: []`, while 7 of its 11 invokers pass flags that the host bans on declaration (F-F-010).
- **Model never recorded.** The model that ran a work package is recorded nowhere. The resolved-binding sentinel is always "absent", by design (#7013) (F-F-014).
- **Outbound seams unused.** The outbound event seams have no production registrant (F-F-016).
- **Documentation drift.** 4 statements in two execution documents disagree with code (F-F-020).
- **SkyKitty and fleet-kitty.** Core says the SkyKitty fleet is switched off. Fleet-kitty's README calls fleet-kitty active. No record links the two (F-F-019).
- **Native research artefacts unused.** The research Mission type defines native evidence artefacts. This investigation did not use them (F-F-022, single case).
