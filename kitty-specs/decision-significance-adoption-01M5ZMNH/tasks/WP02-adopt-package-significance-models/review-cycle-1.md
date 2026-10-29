---
affected_files: []
cycle_number: 1
mission_slug: decision-significance-adoption-01M5ZMNH
reproduction_command:
reviewed_at: '2026-10-28T05:53:26Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (reviewer-renata)

Verdict: changes requested. One blocking finding. Everything else checks out (see "Verified" below).

## Blocking

### F1 (MEDIUM): new blank-template-id branch in `_given_or_input_id` has no test

- **Where:** `src/runtime/next/_internal_runtime/raci.py`, `_given_or_input_id` (the `binding.actor_id.strip()` check), reached through `_resolve_actor` and `_resolve_actor_optional`.
- **What:** a template `RACIRoleSpec` whose `actor_id` is `""` or whitespace is no longer kept as given. It is now looked up from the runtime inputs; an R/A role that still fails escalates with `MissionRuntimeError`, and a C/I role gets the sentinel. On base, `_resolve_actor` / `_resolve_actor_optional` returned the binding unchanged whenever `actor_id is not None`, so `""` / `"   "` were persisted.
- **Why it matters:** the change is correct and in fact needed. Without it a `""` template id would reach `spec_kitty_events.RaciRoleBinding(actor_id="")`, whose `min_length=1` raises a pydantic `ValidationError`. The engine fallbacks (`engine.py` `_evaluate_audit_significance`, `_record_step_raci`) only catch `MissionRuntimeError`, so that error would crash `next`. Keeping a whitespace id would also break the spec's rule that no role is recorded with an empty id. But it is behaviour beyond the ruling ("resolved from inputs as today"), and it guards against a crash, and no test exercises it. The existing tests cover only `actor_id=None` and non-blank ids (`test_decision_significance_adoption.py` (b), `test_internal_runtime_coverage.py`). The blank tests in (d) go through `bind_actor` on the soft-gate path, not `_given_or_input_id`. Deleting the `.strip()` from `_given_or_input_id` leaves every test green. CLAUDE.md "Sonar Expectations" says every new branch or helper needs tests in the same PR.
- **Required fix:** add a focused test through `resolve_raci` with an explicit `RACIAssignment` (`raci_override_reason` set) that covers:
  1. responsible `actor_id="  "` and accountable `actor_id=""`, with `agent_id` / `mission_owner_id` in the inputs, resolve to the input ids;
  2. the same assignment with `{}` inputs raises `MissionRuntimeError` matching "RACI escalation", not a pydantic `ValidationError`;
  3. a consulted or informed role with `actor_id=""` and no input gets its sentinel (`UNKNOWN_ACTOR_ID` for llm or service, `HUMAN_IN_CHARGE_ACTOR_ID` for human).

  A parametrized test in `tests/next/test_decision_significance_adoption.py` is enough. Also update the `resolve_raci` docstring ("with no actor_id") to say "no or blank actor_id", so it matches the code.

## Non-blocking (fix if convenient)

- N1: The soft-gate test calls the private `engine._record_soft_gate` with `ActorIdentity.model_construct`. This is justified. `RuntimeActorIdentity` refuses an empty id, and `_audit_denial_reason` requires `actor.actor_id == mission_owner_id` before a medium-band answer is recorded, so no public path reaches the sentinel branch. Add a one-line comment saying that branch is defensive.
- N2: `ruff format --check --force-exclude` over the changed files reports only 1 file checked. The others are on the formatter ratchet, which is fine.

## Verified (no action needed)

- Authoring/resolved split: `RACIRoleSpec` is used only by `RACIAssignment` and the resolution inputs. Resolved and persisted roles use the package `RaciRoleBinding` / `ResolvedRaciSnapshot`. `ResolvedRACIBinding`, the local `SignificanceEvaluatedPayload` and `TimeoutExpiredPayload` are deleted, and grep finds no remnants in `src/`, `tests/` or `docs/`.
- Sentinels are imported from `spec_kitty_events`; none is hard-coded. The package values are `human-in-charge` / `UNKNOWN`.
- Input-based resolution still runs first. The R/A fail-closed escalation is unchanged, unresolved C/I roles get the sentinel, and the provenance fields (`inferred_rule` / `override_reason`) satisfy the package validator on both paths.
- `infer_raci` returns a snapshot filled with sentinels. The engine fallbacks are unchanged, and the soft gate uses `bind_actor`. `_raci_binding` reads only `source` / `override_reason`, so it is unaffected.
- No new append or write path. `src/specify_cli/decisions/` is untouched, and only public `spec_kitty_events` imports are used.
- `noqa` / `type: ignore` count on the touched src files: 14 on base `7b9de3f5a`, 14 on head (the `# noqa: ARG001` moved with `_inferred_assignment`). C901 is clean. `mypy --strict` on the touched src shows the same 13 errors on base and head.
