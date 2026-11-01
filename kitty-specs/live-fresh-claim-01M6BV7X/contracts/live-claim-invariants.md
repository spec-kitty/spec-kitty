# Contract: live fresh-claim invariants (#6311)

Guard: `tests/specify_cli/cli/commands/agent/test_implement_live_fresh_claim_6311.py`

This Mission adds no production behaviour; it pins the behaviour the documented
implement flow already has. These are the invariants the guard asserts, stated so
a future change can be judged against them rather than against a test diff.

## I1 — One invocation claims (FR-001)

Given a finalized lanes mission whose WP01 sits in `planned` and whose lane
worktree does not exist, one invocation of

```
spec-kitty agent action implement WP01 --mission <slug> --agent <compact identity>
```

exits 0, prints no `already claimed`, renders the implement prompt, and leaves
WP01 in `in_progress`.

**Refusal boundary.** An invocation whose claim is refused is a genuine
ownership conflict, never a representation artefact: the same logical agent
arriving as a compact `tool:model:profile:role` string at one emit site and as a
structured `{tool, model, profile, role}` actor at the other MUST reconcile
(`status/work_package_lifecycle.py::_actor_key`).

## I2 — The claim records the compact identity's tool (FR-002)

The claim events carry an actor whose tool is the compact identity's tool
(`claude` for `claude:opus-5.5:python-pedro:implementer`), whether the event
recorded a string or a structured actor. A later resume therefore compares like
with like.

## I3 — Resume is a lane no-op (FR-003)

Re-invoking under the same compact identity exits 0 and leaves the WP's lane
sequence unchanged. An off-axis annotation (resume refresh) is permitted; a
re-transition is not.

## I4 — A different tool is refused (FR-004)

An invocation under a different tool still fails with `already claimed`. This is
the positive control: without it, I1–I3 could pass by admitting everything.

## I5 — Real plumbing, not a fixture (FR-005)

The guard runs against a real git repository and asserts that the lane worktree
is a real git worktree (`git -C <path> rev-parse --is-inside-work-tree` returns
`true`). No `git` call, `safe_commit`, target-branch checkout, or workspace
creation is monkeypatched, and no claim event is seeded.
