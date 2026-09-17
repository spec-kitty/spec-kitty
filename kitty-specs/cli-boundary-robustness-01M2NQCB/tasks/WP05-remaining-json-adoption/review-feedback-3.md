# WP05 independent review cycle3 — narrow changes requested

Reviewer: codex:gpt-6:reviewer-renata:reviewer, freshly loaded.
Official invocation: 562bcb8503034216886afd1c5e36a0b1. Reviewed HEAD60d2d0b1a.
Official prompt compared fully to cycle2: only invocation/topology/review-cycle metadata changed. Prior product review and R1/R2 closure remain valid. No product defect asserted here.

## R3 — MEDIUM: status golden fixture still specifies superseded error contract

File: tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/json/envelopes.json, entry mission_not_found_status.
Consumer: test_tasks_cli_contract.py:339, test_error_envelope_shape[mission_not_found_status].

Completed shared integration run fails at343: actual exit2 versus fixture exit1. Fixture also expects legacy {success:bool,error_code:str,error:str,handle:str}, so changing exit alone would expose a second obsolete assertion. The entry was unchanged by WP05.

Exact fixture invocation: status --json --mission no-such-mission. Independent baseline105ef7167 probe: JSON exit1, human exit2. Corrected WP05 candidate probe: JSON exit2, human exit2, canonical {ok:false,error:{code:MISSION_NOT_FOUND,message:...},handle:no-such-mission}; stderr empty. Product behavior is correct under ratified C2 and C4. Reverting status to exit1/legacy output would reintroduce the reviewed defect.

Required correction is test-only: update ONLY mission_not_found_status's exit_code to2 and json_shape to {error:{code:str,message:str},handle:str,ok:bool}. Preserve argv, stream, fixtures, test assertions and every unrelated entry, especially mission_not_found_list_tasks (still exit1/legacy shape by default contract). Root expressly authorized this narrow out-of-map fixture entry. No product change needed.

Validate both error-envelope parameter cases and relevant status selector boundary cases after correction. Existing integrated failure is red evidence; do not suppress/deselect the node or weaken shape/exit assertions.

## Evidence and disposition

Shared run:5035passed5failed14skipped2xfailed1411.19s. Four other failures exactly match documented baseline#4479/#4668/#4669. This fifth failure is an omitted adopted-contract fixture update. Full log parent/shared-cli-integration.log; independent probes parent/shared-cli-status-contract-{baseline,candidate}.log; detailed diagnosis parent/shared-cli-status-contract-diagnosis.md. No broad rerun performed.

Normal approved→for_review succeeded without force event01M2P6RFYMBXE6KX5EY23195KQ; official review then claimed. Prior approvals remain historical evidence. No lifecycle artifact hand-editing, product edit, issue-verdict change or publication.

## Eight mandatory checks

| Check | Verdict | Evidence |
|---|---|---|
| Dead code | PASS | Cycle2 live wiring unchanged |
| Synthetic-fixture test | PASS | Golden fixture drives actual production Typer app; failure is obsolete expectation |
| Silent empty return | PASS | No new source delta; canonical failure remains controlled |
| FR coverage | FAIL | Existing affected golden contract not updated to C2/C4, required CLI validation fails |
| Frozen surface | PASS | No edits; root authorizes only status fixture entry correction |
| Locked decision | PASS | Product satisfies ratified C2/C4; requested fixture aligns tests with them |
| Shared ownership | PASS | Explicit root scope extension, no other WP ownership overlap |
| Production fragility | PASS | No new product raise or behavior change requested |

REQUEST CHANGES for R3 only. Retain cycle2 product correction and remediate the stale fixture before approval.
