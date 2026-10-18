# Tasks: Fix plan-mission guard/manifest artifact-vocabulary mismatch

**Mission**: plan-guard-artifact-vocabulary-01M57FKP (#6388)
**Branch**: `fix/plan-guard-artifact-vocabulary` → PR to `main` (operator merges)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Tests-included (red-first). Two work packages, write-scope-separable (parallel lanes).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: cross-family parity test (real gather) + vocabulary-coherence corpus guard + plan presence/guard assertions — RED pre-fix | WP01 | |
| T002 | Reconcile `plan/expected-artifacts.yaml`: re-key goals/draft→specify/plan, re-path goals.md→spec.md, fix stale header comment | WP01 | |
| T003 | Update change-together mirrors: `test_configured_artifact_name.py` + `test_manifest.py` | WP01 | |
| T004 | guard_failure_paths regression for plan specify (non-empty on genuine miss) | WP01 | |
| T005 | Verify green: parity + coherence + guard_failure_paths; `test_bridge_parity::test_coverage_floor_is_met` not re-tripped; required/presence assertions | WP01 | |
| T006 | Validate WP01 blast radius (narrow, foreground) | WP01 | |
| T007 | Reconcile `packs/built-in/missions/plan/mission.yaml` (`required:` + `workflow.phases` → action vocabulary) | WP02 | [P] |
| T008 | Reconcile duplicate `src/specify_cli/missions/plan/mission.yaml` | WP02 | [P] |
| T009 | Update doc `mission-comparison-matrix.md` (plan artifacts) | WP02 | [P] |
| T010 | Verify WP02: no runtime consumer impact, no test reds from the descriptive change | WP02 | [P] |

---

## WP01 — Manifest reconcile + verification + hardening (P0 core)

**Goal**: Reconcile `packs/built-in/missions/plan/expected-artifacts.yaml` to the runtime action
vocabulary so a committed `spec.md` reads present at the plan `specify` guard and `guard_failure_paths`
is restored; add the cross-family parity test (through the real `gather_artifact_presence`), the
vocabulary-coherence CI guard, and the `guard_failure_paths` regression; update the change-together
mirrors. **Do NOT touch `_evaluate_plan_guards`.**

**Priority**: P1 (MVP) · **Dependencies**: none · **Prompt**: [tasks/WP01-manifest-reconcile.md](./tasks/WP01-manifest-reconcile.md)

**Independent test**: On a plan mission dir with committed spec.md, `gather_artifact_presence(...,
step_id="specify")` ⊇ {spec.md} and `_evaluate_plan_guards` returns `[]`;
`required_artifacts_for('specify','plan')=={spec.md}`; a missing-spec.md case yields non-empty
`guard_failure_paths`; the parity + coherence guards are red pre-fix, green post-fix.

Included subtasks: T001, T002, T003, T004, T005, T006

---

## WP02 — Descriptive mission.yaml + doc reconcile

**Goal**: Reconcile the two descriptive `mission.yaml` copies' `required:`/`workflow.phases` and the
reference doc to the action vocabulary (no `goals.md` phantom). Confirmed descriptive-only (no runtime
consumer on the gather/guard path).

**Priority**: P2 · **Dependencies**: none (disjoint write scope from WP01) · **Prompt**: [tasks/WP02-descriptive-reconcile.md](./tasks/WP02-descriptive-reconcile.md)

**Independent test**: Both `mission.yaml` copies and the doc reference the action vocabulary
(`specify/research/plan/review`, `spec.md`/`plan.md`); the full charter/mission test suites stay green
(no runtime behavior change).

Included subtasks: T007, T008, T009, T010

---

## Sequencing & MVP

- **MVP = WP01** (the P0 unblock + its guardrails). WP02 is descriptive coherence.
- WP01 and WP02 have disjoint write scopes → separate lanes, runnable in parallel.

## Guardrails (both WPs)

- **Do NOT modify `_evaluate_plan_guards`** (`src/runtime/next/runtime_bridge_cores.py`) — the guard is correct.
- One canonical vocabulary = the runtime step-contract action ids; manifest + both mission.yaml derive from it.
- Keep the `MISSION_GOALS` artifact kind (removal is a separate campsite follow-up).
- The parity test MUST route through the real `gather_artifact_presence`, never synthetic `present_artifacts=`.
- **Shard-masking caution**: WP01's *source* edit is in `packs/`, but its tests live in `tests/runtime`/`tests/next`/`tests/architectural` — run those dirs locally regardless of what the per-PR shard router selects.
- Defect #2 (`profile_hint`, charter#42) is out of scope; verification is at the gather/guard structural level.
- Do NOT run `make test-full`; do NOT regenerate `.github/ci-shard-timings.json`.
- #6388 is the owning gating issue (issue-matrix verdict required before WP approval).
