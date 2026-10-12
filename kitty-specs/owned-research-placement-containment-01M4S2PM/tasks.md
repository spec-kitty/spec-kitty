# Tasks: Owned Research Placement Containment

**Mission**: owned-research-placement-containment-01M4S2PM
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Grounding**: [analysis-report.md](./analysis-report.md)
**Topology**: single_branch (sequential WPs) · **Target**: issue-5882-owned-research-placement-and-plan (PR-bound)

Two work packages, one per implementation concern. WP01 (the priority) wires the
owned checkout through `spec-kitty research`; WP02 completes the owned plan
authoring path (top-level `plan` forwarding) and surfaces the owned selector in
the research discovery prompt. Both are ATDD red-first through the pre-existing
`research` / `plan` entry points. Completion is recorded with
`spec-kitty agent tasks mark-status <Txxx> --status done`, not by ticking boxes.

## Subtask Index

| Task | Description | WP | Parallel |
|------|-------------|----|----------|
| T001 | ATDD: owned research placement reproduction (RED) | WP01 | |
| T002 | Add `--owned-checkout` to `research`; resolve ownership once | WP01 | |
| T003 | Thread `owned=` through the placement seam + validate owned plan | WP01 | |
| T004 | Validate green (owned + non-owned read-surface) | WP01 | |
| T005 | ATDD: top-level `plan` owned forwarding reproduction (RED) | WP02 | |
| T006 | Expose + forward `--owned-checkout` on top-level `plan` | WP02 | |
| T007 | Surface the owned selector in the research discovery prompt | WP02 | |
| T008 | Validate green + changelog | WP02 | |

## Work Packages

### WP01 — Research owned-checkout placement (#5882) · [tasks/WP01-research-owned-placement.md](./tasks/WP01-research-owned-placement.md)

- **Goal**: `spec-kitty research` honours an owned checkout (explicit `--owned-checkout` or auto-adopt from an owned cwd), scaffolds the four assets under `owned.mission_dir`, and never resolves/reads/writes the primary checkout.
- **Priority**: P1 · **Dependencies**: none (the priority slice).
- **Independent test**: owned R/P triple with a stale primary copy; real `research` writes under P, R byte-for-byte unchanged (`r_snapshot`).
- **Subtasks**: T001 T002 T003 T004 · **Risk**: three `_read_mission_dir_or_exit` calls must thread `owned=`; non-owned path must stay byte-for-byte identical.

### WP02 — Owned plan forwarding + discovery-prompt affordance (#5882) · [tasks/WP02-plan-forwarding-and-prompt.md](./tasks/WP02-plan-forwarding-and-prompt.md)

- **Goal**: Expose `--owned-checkout` on the top-level `plan` wrapper and forward it to the owned-aware `setup_plan` seam; note the owned selector in the research discovery prompt.
- **Priority**: P2 · **Dependencies**: WP01.
- **Independent test**: `spec-kitty plan --help` lists `--owned-checkout`; owned `plan` reaches the `setup_plan` seam with the validated owned fact.
- **Subtasks**: T005 T006 T007 T008 · **Risk**: top-level `plan` also runs an interactive interview keyed on `locate_project_root()` — already skipped in `--json`/agent mode (the owned path); interactive-owned interview resolution is a documented follow-up (C-003).
