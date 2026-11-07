# Decision Moment `01M6R0B954ZPQN5NV4R1ZRE7NY`

- **Mission:** `lane-worktree-model-hardening-01M6QY1M`
- **Origin flow:** `plan`
- **Slot key:** `plan.topology.unprotected-lanes-base`
- **Input key:** `oq2_lanes_base`
- **Status:** `resolved`
- **Created:** `2026-11-06T08:42:02.276351+00:00`
- **Resolved:** `2026-11-06T08:42:04.564720+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

OQ-2: when settlement picks lanes on an unprotected target, how do the topic branch's planning commits reach the target?

## Options

_(none)_

## Final answer

lanes from the topic branch. Nothing in our previous decisions should prevent the coordination branch/worktree to be the topic branch itself, as the coordination designation is a configurable target. corroborate this. [Corroborated 2026-11-06: coordination_branch is a meta.json key (~32 readers) and its default name uses mission_branch_name, the topic-branch grammar; reconstruct-from-slug paths yield the same name. Caveat: git forbids one branch in two worktrees, so settlement moves the root checkout off the topic branch before the coordination worktree checks it out.]

## Rationale

Operator answer, stijn-dejongh, 2026-11-06 (plan open questions).

## Change log

- `2026-11-06T08:42:02.276351+00:00` - opened
- `2026-11-06T08:42:04.564720+00:00` - resolved (final_answer="lanes from the topic branch. Nothing in our previous decisions should prevent the coordination branch/worktree to be the topic branch itself, as the coordination designation is a configurable target. corroborate this. [Corroborated 2026-11-06: coordination_branch is a meta.json key (~32 readers) and its default name uses mission_branch_name, the topic-branch grammar; reconstruct-from-slug paths yield the same name. Caveat: git forbids one branch in two worktrees, so settlement moves the root checkout off the topic branch before the coordination worktree checks it out.]")
