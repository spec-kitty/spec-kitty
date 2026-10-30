# REASONS Canvas — Bound failed-synthesis staging retention

> Mission: bound-failed-staging-retention-01M66YJ3
> Generated: 2026-10-30
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: every refused `charter synthesize` preserves `.kittify/charter/.staging/<run_id>.failed/` and nothing prunes it, so repeated refusals accumulate without bound (#6723, split from #4226).
- Acceptance: [spec.md](spec.md), FR-001 through FR-009 and SC-001 through SC-007; newest 3 kept, latest failure always diagnosable, live staging untouched, overflowing trees reduced.
- Definition of done: failing-first test through the existing staging lifecycle and the CLI refusal path, scoped production change, targeted green evidence, independent review, draft PR flipped to ready for review. No merge by the implementer.

## Entities
- Failed staging directory (`.staging/<run_id>.failed/` with `cause.yaml`) and in-progress staging directory (`.staging/<run_id>/`) keep their existing meanings; [spec.md](spec.md#key-entities-include-if-the-mission-involves-data).
- Retention bound = 3, owned by one module default. No new entity, no new state file, no schema change.

## Approach
- Put the bound in the `StagingDir` lifecycle (`src/charter/activation/synthesizer/staging.py`), specifically after `commit_to_failed` has preserved the current run; every refusing caller (synthesize, resynthesize, orchestrator, dry-run) already routes through it.
- Order candidates by modification time with a name tiebreak; delete only `*.failed` entries beyond the bound through `PathGuard.rmtree`.
- Tradeoff: a count bound over "replace an older directory with the same cause". Same-cause replacement needs to read and compare every old `cause.yaml` and destroys the comparison history; the count bound is predictable and testable. No config knob (no second consumer, and a typo would gate a deletion path).

## Structure
- Production: `src/charter/activation/synthesizer/staging.py` (new retention helper + call from `commit_to_failed`), plus the operator-facing hint in `src/specify_cli/cli/commands/charter/synthesize.py`.
- Tests: `tests/charter/synthesizer/test_staging_atomicity.py` (lifecycle) and a focused file for the retention cases (`tests/charter/synthesizer/test_staging_retention_6723.py`), including one CLI refusal case that reuses the "synthesized once" fixture pattern from `test_collision_refusal_6510.py`.
- Docs: `docs/context/governance-files.md` `.staging` row, the atomicity ADR's retention statements, `docs/changelog/CHANGELOG.md` under `[Unreleased]`.
- One WP; implementer owns product/tests, an independent reviewer checks the diff, planner owns this reasoning. No pack, contract, migration or orchestration change.

## Operations
1. Opening campsite check of the staging module and its callers; record that no tidy step is needed or name it.
2. Write the failing-first tests through `StagingDir.create`/`commit_to_failed` and the real CLI refusal; run and commit RED before the production change.
3. Apply the bounded retention helper, preserving `PathGuard` as the write seam and the "never mask the original failure" contract.
4. Run the targeted charter-synthesizer suite plus the CLI/synthesizer blast radius, ruff/mypy, and independent review; record commands and counts.
5. Prepare a draft PR to `main`, follow CI to green, flip to ready for review. No merge, no auto-merge, no `main` push.

## Norms
- Canonical sources only; no copying structure from older missions or `packs/built-in/`.
- Python typing/lint/format standards, no broad suppressions; no new dependency, version or config key.
- New-code coverage ≥90% on changed lines; independent reviewer reads the actual diff, not a summary.
- The number 3 is stated in code, CLI text, docs and changelog from one constant.

## Safeguards
- Never delete the current run's preserved failure, a live (non-`.failed`) staging directory, or any entry that is not a preserved failure.
- Retention never raises: an OSError while listing or removing is suppressed so the original synthesis failure is reported.
- No recursive walk into preserved contents; no `shutil.rmtree` outside `PathGuard`; no allowlist change.
- `cause.yaml` remains `{reason, traceback, timestamp}`; synthesis, validation and promotion semantics unchanged.
- All work on `issue-6723-bound-failed-staging-retention`; unrelated `kitty-ops/` and mission scaffolding stay out of the change commits; no `main` mutation, no merge.

## Deviations (append-only)
