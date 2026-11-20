# Tasks: API-claimed and canceled WPs reach acceptance

Planning base / merge target: `issue-5781-api-claim-accept-readiness`.

## Work Package WP01: One claim sidecar and one planned release (IC-01, IC-02)

**Dependencies**: None

Requirement refs: FR-004, FR-006

Subtasks:

| ID | Description | Parallel |
|----|-------------|----------|
| T001 | Red: acceptance tests through `orchestrator-api start-implementation`, `transition --to claimed` and `agent status emit --to claimed` assert the snapshot `agent` slot = the actor and a `--policy` `agent` key cannot override it | |
| T002 | Red: acceptance test through `orchestrator-api transition --to planned` asserts the claim slots are released, `implementer_of_record` kept, and another implementer claims unforced (API and host) | |
| T003 | `status/emit.py`: `claim_policy_metadata(shell_pid: int \| None, agent, *, extra=None)` | |
| T004 | Wire the builder into the API claim paths and `agent status emit --to claimed` | |
| T005 | New `status/claim_release.py` planned-release delta; `move-task` reuses it; API `--to planned` sends it as the transition's annotation | |
| T006 | `consolidation/done_bookkeeping.py`: reviewer fallback reads the latest `approved` transition's actor, with a test | |

## Work Package WP02: Accept readiness from the implementer authority (IC-03)

**Dependencies**: WP01

Requirement refs: FR-001, FR-002, FR-003, FR-005, FR-007

Subtasks:

| ID | Description | Parallel |
|----|-------------|----------|
| T008 | Red: API-claimed Mission accepted by `accept-mission` (lanes and lanes_with_coord), and a claim without a sidecar raises no metadata issue | |
| T009 | Red: cancel variants X/P/V on host `accept` and `accept-mission`; a synthetic cancel still refuses | |
| T010 | Red: every printed repair command runs and clears the issue; no-hint lanes print no command | |
| T011 | `status/review_roles.py::implementer_claim_target(lane)` | |
| T012 | `acceptance/summary_core.py` + `acceptance/__init__.py`: gate via the implementer of record, canceled exemption, derived hint | |
| T013 | `orchestrator_api/consolidation.py`: `accept_mission` uses `mission_terminal_acceptability` (#5818) | |
| T014 | `tests/utils.py` seeds a real claim event; re-rule the #4934 test; re-pin the hint-string tests | |
| T007 | Drop the injected `{"agent": actor}` masking in `tests/agent/test_orchestrator_commands_integration.py` (moved from WP01: it masks the accept gate, not the claim) | |
| T015 | `CONTRACT_VERSION` 1.30.0 with its comment block; update the orchestrator-api skill contract doc | |
