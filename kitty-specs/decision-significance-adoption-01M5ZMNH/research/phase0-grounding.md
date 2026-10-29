# Phase 0 grounding — decision-significance adoption (M13)

Grounded on `origin/main` `d4a1b0e4` (2026-10-27) and `spec-kitty-events` `v11.3.0`.

## 1. Upstream release state

- PyPI had only `spec-kitty-events` 11.0.0 when M13 started. 11.1.0, 11.2.0 and 11.2.1 were never published: the `v11.2.0` publish run (run 39272308876) failed in acceptance on `tests/test_version_not_amended.py::test_real_repo_unreleased_version_with_src_change_passes`, which asserted the tip version is untagged and so could never pass on a tag build.
- Fixed in spec-kitty-events#144 (issue #143, merged 2026-10-27). The operator released **11.3.0** (it carries #92 too), which is the version this mission adopts.

## 2. 11.0.0 → 11.3.0 delta (safe-adoption checklist step 1)

| Area | Change | Effect on core |
|------|--------|----------------|
| `diary.py`, `status.py` (reducers) | none | no reducer verdict delta; no A/B run needed (checklist step 5) |
| `strict.py` | `_REQUIRED_SCHEMA_VERSION` bound to `lifecycle.SCHEMA_VERSION` (still `3.0.0`) | none |
| envelope | snapshot differs only in `resolved_version` | snapshot committed for 11.3.0 |
| `decision_significance` (new, 11.1.0/11.2.0) | `RaciRoleBinding` (`actor_id` required, non-empty), `ResolvedRaciSnapshot` (same three provenance rules as core), `SignificanceEvaluatedPayload`, `DecisionTimeoutExpiredPayload`, `HUMAN_IN_CHARGE_ACTOR_ID`, `UNKNOWN_ACTOR_ID` | adopted by #6445 |
| `conformance.validators` | `SignificanceEvaluated`, `DecisionTimeoutExpired` added to the validator map | core's only `validate_event` caller on events (`migration/mission_state.py:1059`) validates envelopes synthesized from status rows, never these types |
| `cloudevents` (new, 11.3.0, #92) | envelope profiles, registry, upcaster | not imported by core |
| producer registry | `run.decision.timeoutexpired.v1` row | relevant to #6446 only |

Java read API: `StatusReducer.PORTED_EVENTS_VERSION = "11.0.0"` is coupled to the conformance manifest (`ManifestCouplingTest`), not the lock. The reducer is unchanged, so there is nothing to port (checklist step 6).

## 3. Code grounding (re-verified cited lines)

| Issue citation | Current location | Note |
|---|---|---|
| `significance.py:485-521` local payloads | `significance.py:485-521` | unchanged |
| `schema.py:79-120` local RACI models | `RACIRoleBinding` 79, `RACIAssignment` 87, `ResolvedRACIBinding` 109-136 | unchanged |
| `raci.py:49-68` inferred defaults | `raci.py:49-68` | unchanged |
| `engine.py:494` persistence | `engine.py:488-491` (`_record_significance`) | drifted 6 lines |
| `engine.py:828` soft gate | `engine.py:824` | drifted 4 lines |
| `events.py:96,133,178` emitter | Protocol `emit_decision_timeout_expired` 97; `NullEmitter` 133; no-op 194 | drifted |

- Resolution is best-effort: `engine.py:356-362` and `414-421` try `resolve_raci` and, on `MissionRuntimeError`, persist bare `infer_raci` output whose ids are `None`. That fallback is what the operator's sentinel table targets.
- `resolve_raci` fills a missing id from `mission_owner_id` / `agent_id` / `service_id` inputs (`raci.py:199-265`). Putting sentinels into `infer_raci`'s output would skip that lookup, hence the operator's split ruling (Decision Moment `01M5ZMPA58JS7K7S4S40CH7H1M`): an authoring-side binding with an optional id stays local; everything resolved or persisted uses the package models; sentinels apply once at the resolution boundary.
- Persisted RACI and significance data is never re-validated on read: `MissionRunSnapshot.decisions` is `dict[str, Any]`, and nothing reads the run event log's `SignificanceEvaluated` rows. Old null ids need no migration.
- Model users: `engine.py`, `events.py`, `raci.py`, `schema.py`, `significance.py`, `specify_cli/events/decision_log.py`, `runtime/next/runtime_bridge_retrospective.py`; tests `tests/next/test_internal_runtime_coverage.py`, `tests/runtime/test_bridge_engine.py`, `tests/specify_cli/events/test_decision_log.py`.

## 4. #6446 (timeout persistence) — out of scope

- ADR 2026-10-22-1 routes every new event write through the EventBridge port. The merged port (#6603, `specify_cli/events/event_bridge.py`) carries only `WorkPackageTransition`; it has no door for a run-log decision event.
- No production code detects a decision timeout: `emit_decision_timeout_expired` is declared, forwarded and buffered, never called.
- Operator ruling (Decision Moment `01M5ZMPFCN3BFSEQ8VTN6MT3HF`): leave #6446 open and blocked; the note is on the issue.

## 5. Related surfaces and coordination

- Mission M4 (#4848, branch `issue-4848-decision-open-lock`, not pushed at grounding time) changes `specify_cli/decisions/` (the opened-event lock and fold). No overlap with the runtime significance/RACI models; this mission does not touch `specify_cli/decisions/` (C-004).
- spec-kitty-events #92 (envelope/registry) is released in 11.3.0; core does not adopt the `cloudevents` package here, so nothing pre-empts #6447/#6449.
- Open core PRs at grounding time: #6716 (#6193 lock-interop spike), #6620, #5540 — none touch these files.
- Architectural gates in the blast radius: `tests/architectural/test_shared_package_boundary.py`, `test_pyproject_shape.py`, `test_events_tracker_public_imports.py`.

## 6. Tidy-first candidates

- None needed before the functional change. `significance.py` and `schema.py` lose classes; `raci.py` gains one small mapping helper. Complexity stays well under 15.
