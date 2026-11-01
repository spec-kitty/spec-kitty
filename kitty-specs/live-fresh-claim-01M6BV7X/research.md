# Discovery: Live Fresh-Claim Coverage (#6311)

Mission: `live-fresh-claim-01M6BV7X` · Issue: spec-kitty/spec-kitty#6311
Grounding baseline: `origin/main` @ `287a226cfe`, `spec-kitty-cli 4.0.0rc8`.

## Decisions

### D1 — This is a verified-already-fixed report, not a new defect

The reported refusal was retested live, twice, on throwaway lanes-topology
missions created by the real CLI (`/tmp/repro-6311`, since deleted):

```
spec-kitty specify "repro-lanes-claim" --mission-type software-dev --topology lanes
… author spec/plan/tasks, finalize-tasks …
spec-kitty agent action implement WP01 --mission <slug> \
    --agent claude:opus-5.5:python-pedro:implementer
```

Result: exit 0, `✓ Lane worktree ready`, `✓ Claimed WP01 (agent:
claude:opus-5.5:python-pedro:implementer …)`, prompt file rendered. One
invocation. The recorded event log for that mission reads

```
WP01 planned -> claimed      actor= claude:opus-5.5:python-pedro:implementer
WP01 claimed -> in_progress  actor= claude:opus-5.5:python-pedro:implementer
WP01 (inner-state)           actor= {'tool': 'claude', 'model': 'opus-5.5',
                                     'profile': 'python-pedro', 'role': 'implementer'}
```

— both representations of one agent, no conflict.

The rest of the reporter's lifecycle also passes with compact actors:
`agent tasks mark-status T001 --agent <compact>`, `agent tasks move-task
--to for_review --agent <compact>`, `agent action review --agent
<compact:reviewer>`, and the approve move with the 3-segment form
(`claude:opus-5.5:reviewer-renata`) that the tool itself prints.

### D2 — What actually holds the bug off (two independent mechanisms)

1. `status/work_package_lifecycle.py::_actor_key` parses a compact
   `tool:model:profile:role` **string** down to the same bare-tool key a
   structured **dict** yields (reusing `parse_agent_boundary_string`) — #4665,
   `e455ce26c1`. `_actors_compatible` and `review_roles._actor_key` both bind it.
2. `cli/commands/agent/workflow_executor.py::_implementer_actor` now emits a
   structured actor dict at the start-claim site (#6400), so the claim pair is
   dict-vs-dict even before the projection reconciles.
3. (Backstop) `_admits_implementer_of_record` (#5377) admits the implementer of
   record on an `in_progress` resume, which covers the `allow_generic_existing`
   miss even if one projection is naive.

Measured directly: with the pre-`e455ce26c1` `_actor_key` restored in-process
(compact string projected verbatim, in both modules), the same live command
fails exactly as reported —

```
Error: WP WP01 is already claimed for implementation by 'claude:opus-5.5:python-pedro:implementer'
exit 1
```

Removing the shim: exit 0. So the reported symptom is real *for that code*, and
the shipped fix is what prevents it.

### D3 — The gap worth closing is the live path, not another unit test

Existing coverage of this defect is deliberately indirect:

- `tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py`
  states in its header that it pre-fakes the lane worktree and monkeypatches git
  (`safe_commit`, target checkout) away; only the claim/status side runs real.
- `tests/status/test_actor_identity_reconciliation_4665.py` and
  `tests/status/test_work_package_lifecycle.py` drive `start_implementation_status`
  directly against a seeded event log.
- `tests/status/test_system_actor_6722.py`, `tests/unit/status/test_review_roles.py`
  pin the projection itself.

Nothing runs the **documented user command** against a **real allocator-created
lane worktree** and asserts the prompt is rendered. That is the seam the triage
comment on #6311 called out ("the test header explicitly bounds its
pre-faked-workspace/monkeypatched git harness"). A duplicate unit assertion here
would violate DIRECTIVE_041 (no test that guards nothing new), so the mission
adds exactly one live guard and no production change.

## Evidence

- `src/specify_cli/status/work_package_lifecycle.py:116-158` — `_actor_key`, the
  reconciliation point; `:330-400` — the `planned`/`claimed`/`in_progress`
  branches and `_admits_implementer_of_record`.
- `src/specify_cli/cli/commands/agent/workflow_executor.py:1016-1037` —
  `_implementer_actor` (structured claim actor, #6400).
- `src/specify_cli/cli/commands/implement_claim.py:350-383` —
  `_start_wp_implementation_status`, the workspace-create claim site.
- `src/specify_cli/cli/commands/agent/workflow.py:1690-1740` — the single
  resolution path: `agent action implement` calls `top_level_implement` only when
  the lane worktree is absent, which is what produces the two-claim pair on a
  fresh WP.
- `git log -1 e455ce26c1` — the #4665 fix commit message names this exact
  symptom.

## Open questions

- None blocking. Whether #6311 should simply be closed as
  `verified-already-fixed` once this guard lands is a maintainer call; the
  Mission records that verdict in its issue matrix with this evidence.
