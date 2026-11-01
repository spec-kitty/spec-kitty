# REASONS Canvas — An honest pre-review gate reason for a planning-lane WP

> Mission: pre-review-planning-lane-gate-honest-reason-01M67HTS
> Generated: 2026-10-30
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: a planning-lane WP that committed its deliverables on the target branch gets the pre-review gate reason "no changed files detected for this WP", which its own commit contradicts ([research.md](research.md), D-1).
- Acceptance: [spec.md](spec.md), FR-001 through FR-004 and SC-001 through SC-004; the planning-lane arm records a truthful reason, the code-change control keeps the old one, no dispatch happens, nothing blocks.
- Definition of done: failing-first reproduction, scoped fix at the one short-circuit, targeted green evidence including the code-change control, independent review, changelog + review-gates doc, PR only. No merge performed by an implementation agent.

## Entities
- Pre-review gate verdict (`no_coverage` outcome + `reason`) and the planning-lane WP have their existing meanings in the review-gate and lane domains; [spec.md](spec.md).
- The planning-lane WP is identified through the existing execution-mode and lane seams (`WorkProductKind.PLANNING_ARTIFACT`, `is_planning_lane`); no new entity or model.
- Use Mission terminology; `planning_artifact` and `lane-planning` are existing canonical domain values, quoted as values, never paraphrased.

## Approach
- Reinterpret one short-circuit: the empty-diff arm selects its reason by asking the planning-lane question first, instead of claiming a census it never ran.
- Do not touch gate policy (binding resolution, scope selection, dispatch, aggregation, the two hard-stops) — C-001. The issue asks for the record to be honest, not for the gate to become a different gate.
- Tradeoff: keep the cheap skip rather than starting to inspect a committed diff. Inspecting the committed range is #2741's larger scope and stays out (research D-2); this mission closes the message acceptance only.

## Structure
- Candidate production surface: `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` (`_mt_collect_transition_gate_verdicts` short-circuit plus one small classification helper).
- Existing authorities: `specify_cli.lanes.compute.is_planning_lane`, `specify_cli.ownership.models.WorkProductKind`, `specify_cli.lanes.persistence.read_lanes_json` via `placement_seam(...).read_dir(MissionArtifactKind.LANE_STATE)`.
- Tests: a new focused module under `tests/specify_cli/cli/commands/agent/` driving the real `move-task` entry point on a real git fixture; existing pre-review gate modules must stay green unmodified.
- Docs: `docs/development/how-to/review-gates.md` (the inherited-limitation note) and `docs/changelog/CHANGELOG.md` under [Unreleased].
- Two work packages: WP01 owns product/tests, WP02 owns docs; reviewers are independent, the planner owns this reasoning and sequencing only.

## Operations
1. Opening campsite check of the touched surface; record a no-enabler conclusion or a distinct behaviour-preserving tidy step, never broaden scope.
2. Write the failing-first reproduction through the real `move-task` path and run it RED on `main`'s code before touching production.
3. Apply the bounded reason selection; verify the code-change control, the no-dispatch assertion and the transition-applied assertion on the same fixture.
4. Run targeted module tests, the pre-review gate neighbours, and scoped quality checks; record commands and counts, plus the red→green commits.
5. Parent operator prepares the PR to `main`; no merge, no auto-merge, no `main` push.

## Norms
- Canonical sources only; explicit `--mission` handle on every command; targeted staging.
- Python typing/lint/format standards, no broad suppressions, no new dependencies.
- New-code coverage ≥90% on changed lines; independent reviewer verifies the real diff and live targeted evidence.
- Do not claim planning evidence as implementation tests.

## Safeguards
- Never weaken, skip, xfail or silence a gate to make this land — the change must be provably non-weakening (NFR-002, C-001).
- Never introduce a second planning-lane literal or a second `lanes.json` reader; ask the existing seams (C-002).
- Preserve today's non-planning empty-diff wording exactly (FR-003) and today's fail-open envelopes.
- No pre-existing red may be papered over; classify and cite it in the PR's Deferred section.
- No credentials or machine-local paths in commits or artifacts; no merge, no auto-merge, no `main` push.

## Deviations (append-only)

2026-10-30 — WP01 — Approved out-of-map edit to `src/specify_cli/cli/commands/agent/tasks_move_task.py` — Adding native callables to the `tasks_move_task_gates` seam makes the seam-pin gate (`tests/specify_cli/cli/commands/agent/test_tasks_move_task_seams.py`) require an identity re-export on `tasks_move_task`, so the four new helpers/constants join that existing re-export block. No behaviour in that file; owned_files unchanged (the seam-pin invariant, not new scope).
