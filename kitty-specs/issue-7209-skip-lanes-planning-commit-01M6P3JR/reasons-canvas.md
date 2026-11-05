# REASONS Canvas — `--skip-lanes` evidence window

> Mission: issue-7209-skip-lanes-planning-commit-01M6P3JR
> Generated: 2026-11-05
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: `spec-kitty consolidate --skip-lanes` synthesizes the `LanesManifest` it needs for a direct-on-target Mission (`entry_preflight._synthesize_no_lane_manifest`) with `planning_commit_sha` unset, so `wp_evidence.lane_evidence_window` returns `None` for every approved work package and the #6715 evidence axis refuses `EVIDENCE_WINDOW_UNCOMPUTABLE` on every Mission the flag exists to serve. The recovery line names `finalize-tasks`, which records a planning commit in a `lanes.json` that this topology does not have.
- Acceptance: [spec.md](spec.md) FR-001 through FR-004 and SC-001 through SC-004 — a real window resolved from target history, a base that is deterministic and never fabricated, a working remedy when nothing is resolvable, and the owned-files / independent-review refusals unchanged.
- Definition of done: the three red `--skip-lanes` nodes in `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py` green through the real Typer command, new focused tests for the resolution and the refusal text, independent review of the aggregate diff, changelog fragment and the `--skip-lanes` doc note, draft PR flipped to ready. No gate weakened; no merge by the implementer.

## Entities
- Synthesized no-lane manifest: the in-memory `LanesManifest` the executor builds when `--skip-lanes` is given and no `lanes.json` exists; its single lane is the canonical planning lane and its `mission_branch` equals the target branch.
- Mission start boundary: the target-branch commit immediately before the first commit that introduced `kitty-specs/<slug>/`; the evidence-window base this Mission records for the synthesized manifest.
- Evidence window: `base..tip` tree diff, judged per approved work package against its authored `owned_files`; the tip is the target branch for the synthesized planning lane.
- `LanesManifest.planning_commit_sha`: the existing recorded field. No new field, no `lanes.json` schema change.

## Approach
- Record the base on the synthesized manifest instead of teaching the evidence axis a second window rule: `lane_evidence_window` stays the one authority for "what is the window".
- Derive the base from history only — earliest target-branch commit touching `kitty-specs/<slug>/`, then its first parent, so a Mission whose first commit carries code with its planning artifacts still yields a non-empty window. A root introducing commit is its own base.
- Fail closed, never fabricate: any git error or an absent mission directory yields no base, which keeps today's `EVIDENCE_WINDOW_UNCOMPUTABLE` refusal. Nothing passes vacuously.
- Make the refusal's recovery honest for both shapes: keep `finalize-tasks` for a recorded-but-unpinned `lanes.json` (#7210) and add the no-`lanes.json` remedy (commit the planning artifacts on the target) in the same line, without changing the code that leads it.
- Keep the gates: no attestation for the window code; `IMPLEMENTATION_MISSING` and `REVIEW_NOT_INDEPENDENT` keep refusing through the synthesized window exactly as through a recorded one.

## Structure
- Production: `src/specify_cli/consolidation/entry_preflight.py` (resolve and record the base), `src/specify_cli/consolidation/wp_evidence.py` (message and recovery text for the no-planning-commit case).
- Reused, not edited: `kernel.git.run_git`, `consolidation.git_probes.commit_parents`, `wp_evidence.lane_evidence_window`, `reconciliation.build_approved_wp_set`, `_synthesize_no_lane_manifest`'s planning-lane shape.
- Tests: the pre-existing `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py` is the red-first entry point (its WP task file gains the `owned_files` a real Mission declares); a focused module proves the resolution, its non-vacuity pairing, the fail-closed case and the refusal text.
- Docs: `docs/guides/how-to/missions/merge-mission.md` (`--skip-lanes` row/notes), changelog fragment under `docs/changelog/unreleased/`.

## Operations
1. Ground the issue, claim it, specify/plan/tasks through the canonical commands.
2. Red first: confirm the three `--skip-lanes` nodes fail with `EVIDENCE_WINDOW_UNCOMPUTABLE` on the pre-fix tree, then commit the fixture update + new failing tests.
3. Implement the base resolution, then the refusal text, one commit each.
4. Run the targeted suites (`tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`, the new module, `tests/consolidation/test_wp_evidence.py`, `tests/consolidation/test_lane_evidence_axis.py`), `ruff check`/`ruff format --check`, and the changelog style check.
5. Wrap up: accept, issue verdict, independent review of the aggregate diff, consolidate/compact/rebase, changelog fragment, draft PR, then flip when green. The operator merges.

## Norms
- Canonical command surfaces and the resolved mission handle; targeted staging only.
- Python typing/lint standards; no new dependency; no new configuration key; no schema change.
- New-code coverage on changed lines ≥90%; the reviewer reads the real diff and live evidence.
- Terminology: Mission (not feature); work package; lane; evidence window; direct-on-target.

## Safeguards
- Do not weaken an evidence gate: `IMPLEMENTATION_MISSING`, `REVIEW_NOT_INDEPENDENT`, `OWNERSHIP_UNRESOLVED` and `IMPLEMENTATION_UNREADABLE` keep their codes, their order and their strictness on the synthesized window.
- Do not add an attestation or a `--skip-evidence` style opt-out.
- Do not fabricate a base from a timestamp, the current tip, or a generated value; only a commit that exists on the target branch qualifies.
- Do not touch the coordination-teardown seam of #7198/#7199 or the accept-diagnostics work of #7222/#7223.
- No full heavy suite in-mission; no main push; no merge; no auto-merge.

## Deviations (append-only)
