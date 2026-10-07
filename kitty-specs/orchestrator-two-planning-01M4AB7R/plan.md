# Implementation Plan: Orchestrator 2 governed mission and planning API

**Branch**: `issue-5846-orchestrator-two` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

## Summary

Close the API-only authoring gap using a shared planning application service and thin concern modules. Preserve the current envelope/verbs and Stijn's #5664 structure. Advertise a Python semantic delivery profile; do not claim full Go journal, execution or transport conformance.

## Planning Answers

- Full mission/specification/plan/tasks journey is mandatory, established in Lynn's conversation.
- Existing decisions, placement, commit, status, finalizer and native next remain sole authorities.
- Python host remains local CLI transport with bounded inline content and content-digest revisions.
- Reviewable PRs target main; the operator authorized publication and review requests. Merge remains with fleet.

## Technical Context

**Language/Version**: Python 3.11+, Typer, existing mission_runtime/events/tracker dependencies, Pydantic/ruamel YAML.
**Storage**: Existing filesystem/event/Git authority and host-local content provenance.
**Target Platform**: Linux/Windows CLI transport. Content limits: 256 KiB/artifact, 1 MiB/batch, 64 entries initially; explicit unsupported larger reference-store operations. Cooperative per-mission lock plus optimistic content hashes; no universal atomic journal promise.

## Charter Check

ATDD red first per WP; shared service authority; bounded registered kinds; no raw state writes. Independent reviewer distinct from implementer. Relevant module tests and named architectural gates only. No release bump, main push/merge, full heavy sweep, or new SaaS behavior.

## Application Design

- New shared design service owns registered kind resolution, bounded artifact descriptors/submission, stale target/parent checks, prerequisite predicates and host commit outcomes. Refactor/reuse specification guards currently in mission_setup_plan; do not duplicate them.
- API authoring accepts a closed set: specification, plan, registered support documents/contracts, structured wps.yaml and declared package prompts. File locations come from placement/template/manifest authority. Neither meta, events, status, runtime files nor generated tasks.md are writable.
- Validate the entire batch before effects, recheck inside per-mission lock, materialize atomically per file and commit only owned files via commit_for_mission/ProtectionPolicy. Explicit materialized-but-uncommitted failures preserve reconciliation evidence; no success on ambiguous effects.
- Host-owned content receipts persist each accepted artifact digest and its spec/plan/context parent digests; finalization compares recorded provenance to current inputs. Receipts are content provenance, never runtime phase state. Artifact revision is SHA256 of exact bytes; absent is explicit. Plan requires current spec digest; packages require spec/plan/outline digests. Context digest covers stable canonical resolved template/governance bytes, excluding session-dependent first_load/reference fields and absolute paths. Submissions never advance runtime. All design artifacts are immutable once packages are finalized or executing through this authoring surface. Scaffold success with phase_complete=false remains successful scaffolding; only blocked/error is refusal.
- Context discovery reads resolved mission types/templates/action doctrine and canonical specify/plan interview questions. Interview recording uses existing decisions service and stable stage/question identity. Only resolved, nonempty canonical interview answers satisfy interview completion; deferred/canceled decisions do not. Pending decisions block completion; completion is native runtime action, not an invented stage ledger.
- next adapter calls existing next command in process with explicit parameters. Preserve read-only query, run-index, charset/governance preflight, invocation/result pairing, decision and commit behavior. Parse complete multiline JSON. Report inner blocked/decision-required results honestly.
- tasks delegates finalization and remains authoritative for manifests, requirements, ownership, status bootstrap and planning pin. Additional stale-parent/pending-decision gates precede it. Scaffold success is distinct from phase completion.

## Stijn Reconciliation

#5664 concern split is baseline. #5735 shared implementation service and #5532 status-reader convergence are pending: use current claim/status authority, avoid competing reducers, document seams. #5231 contract coverage remains compatibility work, no blanket close claim.

## Project Structure

- src/specify_cli/design/ (shared authoring authority)
- src/specify_cli/orchestrator_api/design_authoring.py (thin artifact projection)
- src/specify_cli/orchestrator_api/design_context.py (context/interview projection)
- src/specify_cli/orchestrator_api/runtime_next.py (native next projection)
- Existing commands/envelope/upstream_contract and API docs updated for capability census.
- tests/specify_cli/orchestrator_api/ owns user-visible acceptance and refusal controls.

## Implementation Concern Map

### IC-01 — Governed content handoff

- Purpose: close manual artifact/commit bridges without lifecycle bypass.
- Relevant requirements: FR-001, FR-003, FR-004, NFR-001, NFR-002.
- Affected surfaces: design application service, design_authoring, design_phase guards.
- Sequencing: none.
- Risks: topology placement, parent freshness, unrelated dirt, partial commit effects.

### IC-02 — Governed discovery and advancement

- Purpose: transport complete workflow context/interviews and canonical runtime actions.
- Relevant requirements: FR-002, FR-005, FR-006, FR-007.
- Affected surfaces: design_context, runtime_next, API registration/contract discovery.
- Sequencing: none; service interfaces coordinated with IC-01.
- Risks: read-only queries bootstrapping runs, prompt bodies inaccessible, duplicate decision authority.

### IC-03 — Client proof and public mapping

- Purpose: prove the complete journey and expose compatibility/unsupported behavior honestly.
- Relevant requirements: FR-001, FR-004, FR-006, FR-007, NFR-003, C-001, C-002, C-003.
- Affected surfaces: acceptance tests, API docs, contract census fixtures.
- Sequencing: after IC-01 and IC-02.
- Risks: acceptance using manual file/Git bridges; false full-Go claims.

## Validation

Fail-first acceptance through current orchestrator-api entry point. Real API-only client creates, retrieves context, records/resolves interview decisions, submits/readbacks spec and plan, submits valid manifest/prompts, finalizes and queries ready work. Cover single_branch and coordination placement. Negative controls: stale target/parent/context, pending decisions, placeholders, bad requirements/graphs, traversal/symlink/state-write/bounds, inner blocked plan, read-only next. Existing API/contract/doc census and directly affected canonical service files, ruff and mypy. No whole-repo or heavy-suite run.

## Complexity Tracking

No charter exceptions. New service is the content-authoring authority; runtime/state/commit authority remains unchanged.
