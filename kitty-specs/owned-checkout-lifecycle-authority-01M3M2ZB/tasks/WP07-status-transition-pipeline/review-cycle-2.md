---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T03:08:29Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review, cycle 2: CHANGES REQUESTED

Reviewer: reviewer-renata. Commits reviewed: 53506696e..ae11472fd. Base: 55610f516.

Cycle-1 items now resolved:
- HIGH-1: `== 5` pin.
- HIGH-2: T036 tests.
- HIGH-3: the mission_finalize mypy error.
- MEDIUM-4, MEDIUM-5 and MEDIUM-6.
- LOW-8: markers moved onto the call lines.

These are verified by red runs and by mutation (see the report). Three items remain.

## Blocking

**1. [HIGH] Two new mypy --strict errors in src/specify_cli/status/emit.py:81-82: `Name "_store" / "_reducer" already defined (possibly by an import) [no-redef]`.**
- Evidence: I ran the same 54-file invocation on the base and the head. It covers every src caller of `effective_root_kwargs`, `commit_for_mission`, `write_artifact`, `bootstrap_canonical_state`, `read_events_transactional`, `emit_inner_state_changed_transactional`, `MissionHandle(`, `TransitionRequest(`, `BookkeepingTransaction.acquire`, and the subtasks resolvers, plus the WP files and their callees. Base: 23 errors. Head: 25.
- Cause: the `if TYPE_CHECKING: from mission_runtime import OwnedCheckout` import that 01e925785 added to emit.py.
- Checks I ran:
  - Restoring the base emit.py makes both errors go away.
  - Deleting only that import and typing the dropped parameter as `object` also makes both go away (23 errors).
  - Switching the import to `mission_runtime.owned_checkout` does not help.
- Your 41-file set did not include the files that expose the cycle.
- Fix: do not import `mission_runtime` into emit.py. The parameter is dropped by design (D-1), so it does not need the concrete type. Then re-run the same full caller-set diff and record it: 0 new errors.

**2. [MEDIUM] The LOW-9 guards are new branches with no tests and no red commit, and they are parallel copies rather than the canonical collapse.**

The untested raises are:
- `bootstrap.py:146`: owned vs owned_mission;
- `bootstrap.py:151`: effective_root vs fact;
- `write_seam.py:529`: effective_root vs owned.

`git grep` over tests finds none of these messages. Under the cycle-2 ruling, every new behaviour needs a red commit before its fix. Sonar also needs new branches tested.

**Parallel rules.** The same two rules now exist in several copies with different semantics:
- *owned vs owned_mission.* `bootstrap.py` re-implements `TransitionRequest.owned_fact()` inline. Reuse the one canonical collapse instead: extract a module-level `collapse_owned(owned, owned_mission)` that `owned_fact()` also calls, or build via `owned_fact()`.
- *effective_root vs fact.* There are four checks, each different:
  - `_identity_for_request` raises `ActionContextError(OWNED_MISSION_PATH_REFUSED)` with a raw `!=`;
  - `MissionHandle.__post_init__` raises `TypeError` after `.resolve()`;
  - bootstrap raises `TypeError` with a raw `!=`;
  - write_seam raises `TypeError` with a raw `!=`.
- Required: one canonical checkout-agreement predicate, used by all of them. Decide deliberately whether it compares with `.resolve()`, and pin that choice with a test using a non-canonical path.

Add the tests as a red commit first, then the consolidation.

## Non-blocking (fix in the same pass)

3. [LOW] `status_transition.py`, the MEDIUM-4 comment above `identity = _identity_for_request(request)`: it still says the legacy branch "resolves and writes back onto `request.owned`". ae11472fd removed that write-back, so the comment is now false. Fix the wording.
4. [LOW] The `owned_mission` marker on the inner-state door sits on the internal call argument (`owned_mission=owned_mission,  # TRANSITIONAL(WP18)` at about :1693), not on the signature parameter (about :1639, unmarked). The DoD entry names "the inner-state door's `owned_mission=` alias", and WP18 deletes what the grep finds. Move the marker onto the signature parameter; the count stays 4.
5. [LOW] `emit._flat_subtasks_dir_resolver` gained a legacy `effective_root` parameter that has no marker (`# noqa: ARG001` only). Mark it TRANSITIONAL(WP18) and amend the DoD (18), or state in the Activity Log why the G4 gate is enough to delete it in WP18.
6. [LOW] The ae11472fd commit body says test_emit.py was updated "in the same commit". It was not: the commit touches no test file. Correct the record in the Activity Log.
7. [LOW] mission_finalize.py:2759: `effective_root_kwargs(owned.root if owned else None)` keeps a legacy `.root` read. `effective_root_kwargs` accepts the fact directly, so `effective_root_kwargs(owned)` works.
