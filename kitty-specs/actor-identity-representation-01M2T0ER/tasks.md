# Tasks: Coord/lane actor-identity representation cluster

**Mission**: actor-identity-representation-01M2T0ER
**Branch**: `fix/actor-identity-representation` (planning + local merge target)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

## Execution note (one lane, serial)

All four WPs share source files (`work_package_lifecycle.py`, `workflow_executor.py`,
`tasks_move_task.py`), so `finalize-tasks` unions them into a **single lane** that executes
serially. They are authored as a **linear dependency chain** WP01 → WP02 → WP03 → WP04 so the
inherent `owned_files` overlap is exempt from the concurrent-overlap guard (it only flags
dependency-unordered pairs). Do not expect parallel lanes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first regression: fresh full-identity claim (once, resume, refuse, generic) | WP01 | |
| T002 | Reconcile `_actor_key`/`_actors_compatible` to a shared tool-scoped bare-string key | WP01 | |
| T003 | Align workspace-create claim and workflow claim; retain model/profile/role metadata | WP01 | |
| T004 | Representation × comparison matrix test + two-slot convergence assertion | WP01 | |
| T005 | Verify green; ruff/mypy/format; complexity ≤15 | WP01 | |
| T006 | Red-first regression: verdict attribution (approval+rejection, resolver, human) | WP02 | |
| T007 | Single completion-command render seam threads resolved `--agent` (all render sites) | WP02 | |
| T008 | Resolve active claimed reviewer from event log when `--agent` omitted; keep human case | WP02 | |
| T009 | Verify green; gates | WP02 | |
| T010 | Red-first canonical e2e regression: reject → fix-mode claim → for_review (no --force), named slots | WP03 | |
| T011 | Rejection genuinely releases claim (no reviewer re-stamp); reconcile 3 ownership authorities | WP03 | |
| T012 | Successful fix-mode claim records new implementer in the gate-read slot | WP03 | |
| T013 | Re-verify e2e on base; file scoped upstream follow-up if reducer residual bites (C-001) | WP03 | |
| T014 | Verify green; gates | WP03 | |
| T015 | Verify-first: live `move-task --agent` persistence on base (repro or evidence) | WP04 | |
| T016 | Regression: `move-task --agent` persists acting identity into reduced slot | WP04 | |
| T017 | Persist acting identity if reproducible; else close #3029 with evidence, no code change | WP04 | |
| T018 | Verify green; gates | WP04 | |

## Work Packages

### WP01 — Fresh full-identity claim reconciliation (#4665)

- **Goal**: A fresh `implement --agent <tool:model:profile:role>` claim moves the WP to
  `in_progress` and renders the prompt in one invocation, without self-conflict; same-identity
  resume is idempotent; different identity refused; generic-actor claims re-claimable.
- **Priority**: P1 (MVP-launch gating). **Dependencies**: none. **MVP**: yes.
- **Independent test**: live fresh-worktree compact-identity claim end-to-end + matrix unit.
- **Subtasks**: T001, T002, T003, T004, T005
- **Requirements**: FR-001, FR-002, FR-003, FR-010, NFR-002, NFR-003
- **Risks**: reconciling the key must NOT become a tuple/struct (breaks generic `in` test) and
  must NOT touch the byte-identical shared projection (C-002/C-005).
- **Prompt**: [tasks/WP01-fresh-full-identity-claim.md](./tasks/WP01-fresh-full-identity-claim.md) (~200 lines)

### WP02 — Reviewer verdict attribution (#4670)

- **Goal**: An agent's approval/rejection verdict is attributed to the reviewing agent (not the
  git user), with evidence retained; identity-omitting completions resolve the active reviewer;
  genuine human approvals stay human.
- **Priority**: P1. **Dependencies**: WP01. **Independent test**: real claim→handoff→completion.
- **Subtasks**: T006, T007, T008, T009
- **Requirements**: FR-004, FR-005, FR-006, NFR-001, NFR-003
- **Risks**: ≥5 independent render f-strings — prefer a single render seam or enumerated-site
  regression; do not just patch report text.
- **Prompt**: [tasks/WP02-reviewer-verdict-attribution.md](./tasks/WP02-reviewer-verdict-attribution.md) (~200 lines)

### WP03 — Fix-mode ownership after rejection (#4673)

- **Goal**: After rejection + successful fix-mode claim, the WP's owner is the new implementer;
  the implementer submits for review without `--force`; a different agent is still refused.
- **Priority**: P1 (MVP-launch). **Dependencies**: WP02. **Independent test**: canonical e2e state.
- **Subtasks**: T010, T011, T012, T013, T014
- **Requirements**: FR-007, FR-008, NFR-001, NFR-003
- **Risks**: three ownership authorities (C-006); the deepest reducer root may be upstream-owned
  (C-001) — hedge FR-007 honestly on live re-verification.
- **Prompt**: [tasks/WP03-fixmode-ownership.md](./tasks/WP03-fixmode-ownership.md) (~230 lines)

### WP04 — move-task --agent persistence (#3029, representation half)

- **Goal**: `move-task --agent <identity>` persists the acting identity into the reduced
  ownership slot; verify live first — close with evidence if already fixed.
- **Priority**: P2. **Dependencies**: WP03. **Independent test**: live persistence check.
- **Subtasks**: T015, T016, T017, T018
- **Requirements**: FR-009, NFR-003
- **Risks**: reported symptom partially stale — do NOT re-fix a working path; C-004 excludes the
  flag-drop / accept-gate-demotion alternatives and the #2993 precondition.
- **Prompt**: [tasks/WP04-move-task-agent-persistence.md](./tasks/WP04-move-task-agent-persistence.md) (~180 lines)

## Dependencies

```
WP01 → WP02 → WP03 → WP04   (linear; one lane, serial)
```

## MVP scope

WP01 alone unblocks the escalated #4665 (fresh full-identity claim). WP02–WP04 ride the same
lane in order.
