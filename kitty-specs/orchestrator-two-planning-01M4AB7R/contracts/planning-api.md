# Governed external planning contract

Delivery: Python `orchestrator-api` contract **1.11.0**, additive to the existing seven-key JSON envelope and 21 commands. The canonical public request/response reference is [orchestrator-api.md](../../../docs/api/orchestrator-api.md#governed-planning-delivery-python-profile). The amended [Go specification PR](https://github.com/spec-kitty/spec-kitty-redesign/pull/9) defines the corresponding semantic lifecycle.

## Client operations

- `design-context` discovers resolved templates, governance, bounded content and canonical interview slots. Pre-creation calls explicitly select an activated Mission type; an existing Mission's type is immutable.
- `interview-record` submits nonempty answers to canonical specification/planning question IDs through native Decision Moment authority. Mutations require policy metadata.
- `artifact-read` returns registered canonical content with its exact SHA-256 revision, or explicit absence.
- `artifact-submit` accepts a closed batch, target revisions, accepted parent revisions and context digest. Inline JSON or bounded UTF-8 stdin carries content; the host owns placement, validation and Git commits.
- `design-validate` reads canonical prerequisites without completing a stage.
- `next` delegates native query, input decisions, issuance and completion. Queries do not persist runtime state. Successful completion validates the native persisted issued action, never a pending input or planner preview.
- Existing `specify`, `plan` and `tasks` remain scaffold/finalization authorities. Scaffold success is not stage completion.

## Invariants and delivery limits

Invalid or stale batches refuse before content effects. Accepted lineage is stored in trusted host metadata, rather than inferred only from caller-provided digests. Unresolved interviews, stale parents and unfinished content refuse completion/finalization. Finalized design content is immutable; disagreement between snapshot and event-log proof fails closed.

Limits are discoverable in `contract-version`: 256 KiB per artifact, 1 MiB per batch, 2 MiB request JSON and 64 entries. Context and interview bounds are published separately.

Files and Git commits precede receipt persistence; partial-effect failures require reconciliation. Locks coordinate API writers. Receipts are host-local and nonportable between clones. This profile does not claim Go leases, fences, asynchronous operations, watches, durable replay or immutable work generations.

## Executable verification

`tests/specify_cli/orchestrator_api/test_planning_client_journey.py` verifies API-only authoring/finalization for single-branch and coordination topologies, actual runtime state preservation, native input handling and issued-action completion. Authoring/context unit tests verify bounds, revisions, lineage and typed refusals. The closed verb/error census lives in `src/specify_cli/core/upstream_contract.json`.

Go ProgressService and the unfinished Mission UI contract are documented in the proposed ADR. Native status-read convergence remains with #5532 and #5631; no Java dependency or alternate status reducer ships here.
