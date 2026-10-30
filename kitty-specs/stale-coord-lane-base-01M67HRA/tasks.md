# Tasks: A stale coordination branch is reported, and the agent path can act

**Mission**: stale-coord-lane-base-01M67HRA (#6753)
**Branch**: `issue-6753-stale-coord-lane-base` → PR to `main` (operator merges)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Tests-included mission (red-first discipline), two work packages with disjoint write
scopes. Both halves of the bug are pinned: the silence around a stale base
(WP01) and the missing `--base` on the path agents are told to use (WP02).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: coord fixture whose target advanced → no stale-base warning today (RED) | WP01 | |
| T002 | Probe helper: target tip vs the ref the lane is cut from (`current`/`stale`/`unknown`) | WP01 | |
| T003 | Emit the warning once on the FRESH_COORD arm, naming base ref, target, tip, remedy | WP01 | |
| T004 | Positive control on the same fixture: current base stays silent; unresolvable target stays silent | WP01 | |
| T005 | Parentage ratchet: the stale cut still parents on the coordination branch (FR-003) | WP01 | |
| T006 | Validate WP01: `tests/specify_cli/lanes` + `tests/lanes` allocator suites green | WP01 | |
| T007 | Red-first: `agent action implement --base` exits 2 "No such option" today (RED) | WP02 | [P] |
| T008 | Add `base` to `ImplementRequest` and thread it into the create-path dispatch | WP02 | [P] |
| T009 | Option surface on `agent action implement`, help text mirroring top-level `implement` | WP02 | [P] |
| T010 | Positive control: same invocation without `--base` captures `None`; reuse refusal intact | WP02 | [P] |
| T011 | Validate WP02: `tests/specify_cli/cli/commands/agent` + `tests/agent` green | WP02 | [P] |

---

## WP01 — Report a stale lane base at fresh coord allocation

**Goal**: A fresh code lane on a coordination-topology Mission whose coordination
branch no longer contains the target tip prints one `WARNING:` naming the base ref,
the target branch, the missing target commit and the runnable remedy — while the
lane still parents on the coordination branch, and nothing is printed when the base
is current or the probe cannot answer.

**Priority**: P1 (MVP) · **Dependencies**: none · **Prompt**: [tasks/WP01-stale-base-warning.md](./tasks/WP01-stale-base-warning.md)

**Independent test**: Build a coord fixture, advance `main` past the coordination
branch, allocate a fresh lane, and capture stdout; then re-run on the same fixture
with the coordination branch holding the `main` tip and confirm silence. Both
assertions come from one shared fixture so the warning case and the silent case
cannot drift.

Included subtasks: T001, T002, T003, T004, T005, T006

---

## WP02 — `--base` on `agent action implement`

**Goal**: `spec-kitty agent action implement <WP> --agent <name> --base <ref>`
accepts the option and threads it to the same allocator seam the internal
`spec-kitty implement --base` already uses, so the documented, dispatched path can
act on WP01's remedy; every existing base-refusal route still fires unchanged.

**Priority**: P1 · **Dependencies**: none (disjoint write scope; conceptual
follow-on to WP01) · **Prompt**: [tasks/WP02-agent-action-implement-base.md](./tasks/WP02-agent-action-implement-base.md)

**Independent test**: Invoke the `agent action implement` CLI command on a fixture
with and without `--base`, and observe the value reaching the create-path dispatch
(`"main"` vs `None`); separately, an already-allocated lane plus `--base` still
raises the reuse-route `UnhonorableBaseError`.

Included subtasks: T007, T008, T009, T010, T011

---

## Requirement coverage

| Requirement | Owner |
| --- | --- |
| FR-001, FR-002, FR-003, FR-006 | WP01 |
| FR-004, FR-005 | WP02 |
| NFR-001, NFR-002, NFR-003 | WP01 |
| SC-001, SC-002 | WP01 |
| SC-003, SC-004 | WP02 |
