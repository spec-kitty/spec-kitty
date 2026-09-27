# Research: Accept fails closed on a stale or pending acceptance matrix

## Grounding (2026-09-27, main @ 5469c4d7)

| Issue | Still real? | Evidence |
|---|---|---|
| #4891 | No, fixed on main | `acceptance/gates_core.py:174` routes through `require_lanes_json`; `docs/changelog/CHANGELOG.md:66`; `tests/cross_cutting/misc/test_acceptance_support.py::test_accept_fails_closed_when_lanes_json_is_absent`. Closed with rationale. The CLI-level pin is FR-008. |
| #4974 | Yes | `gates_core.py:519` reads the snapshot; checks run at `:559` and `:567`; `:589` writes it back unconditionally; the verdict is judged from the snapshot at `:594`. No `feature_status_lock` anywhere in `acceptance/` or `accept.py`. |
| #4887 | Yes | The only locked RMW is the private `_locked_reread_splice_and_write` in `acceptance_verdict.py:205` (with a twin in `issue_verdict.py`). |
| #4934 | Yes | `orchestrator_api/commands.py:2033` never reads `summary.ok` and calls `record_acceptance` unconditionally. It also bypasses the #4891 fix. |

## Decisions

- **D1: Seam location is `acceptance/matrix.py`.** Rationale: it sits next to the writers it guards, with no layer change (all of it is `specify_cli`). Rejected: a generic helper in `status/`, which would invert ownership. Converging `issue_verdict.py` is deferred (C-005).
- **D2: Row ownership rule.** Accept contributes a row only if the row was pending in accept's snapshot, accept judged it, it is still pending in the fresh matrix, and its definition is unchanged. The definition-equality condition closes the re-registration case (architect lens finding 2).
- **D3: Checks run outside the lock.** Negative-invariant subprocesses have no timeout. Holding the lock across them would push every concurrent verdict writer into the 10 s fail-closed timeout.
- **D4: Pre-stamp guard (FR-010).** The lock is held across the verdict re-check and the in-process `record_acceptance` write only. The git commit happens after the lock is released, so no git hook or subprocess can deadlock on the lock. A verdict landing after the stamp is a post-accept verdict, which is out of scope.
- **D5: accept-mission uses `MISSION_NOT_READY`.** It is already in `upstream_contract.json` `allowed_error_codes`. `CONTRACT_VERSION` 1.6.0 goes to 1.7.0 as a behavioural tightening; `MIN_PROVIDER_VERSION` is unchanged.
- **D6: Post-consolidation routing is deferred.** `verify_deferred_invariants` has no production caller. Its ownership model (it re-judges `deferred_to_consolidation` rows) differs from accept's (pending rows). It is allowlisted in the gate with this rationale.

## Adversarial squad dispositions (post-spec)

| Finding | Lens | Disposition |
|---|---|---|
| Pending-only splice is wrong for post-consolidation | architect | changed: FR-006 routing deferred (D6) |
| Ownership rule needs definition equality | architect | accepted: D2 and a new edge case |
| Gate-to-stamp TOCTOU | architect, reviewer | accepted: FR-010 and SC-005 |
| Gate must cover both unlocked writers, alias and attribute calls | architect, reviewer | accepted: FR-006 |
| accept-mission writes the matrix; "nothing recorded" undefined | reviewer | accepted: US3 and SC-003 define it (no `accepted_at`, `acceptance_mode` or `acceptance_history`, HEAD unchanged); the working-tree write is deferred |
| Two orchestrator fixtures will break | reviewer | accepted: a shared acceptable fixture in IC-04 |
| Envelope keys not concrete | reviewer | accepted: FR-007 names the keys |
| `mode: auto` payload label | reviewer | deferred_with_rationale: unrelated contract field |
| `strict_metadata` | reviewer | accepted: pinned strict, matching the host default |
| Compound-fix half-by-half proof; FR-002 wiring; FR-005 positive control | reviewer | accepted: SC-001 and SC-006, FR-002 control |
| SC-004 vs ratchet rows | reviewer | accepted: scoped to [build] |
| `populate_criteria_from_review_evidence` status TOCTOU | architect | deferred_with_rationale: a status-side race, different class |
| Scaffold create-if-absent unlocked | architect | deferred_with_rationale: allowlisted blind creator |
