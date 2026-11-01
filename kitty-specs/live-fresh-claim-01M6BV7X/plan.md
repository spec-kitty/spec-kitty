# Implementation Plan: Live Fresh-Claim Coverage (#6311)

**Mission**: live-fresh-claim-01M6BV7X · **Branch**: `issue-6311-live-fresh-claim`
**Input**: [spec.md](./spec.md) · [research.md](./research.md)

## Summary

Add one integration test module that drives the real `agent action implement`
CLI on a real git repository with a real lanes manifest, so the fresh
compact-actor claim is exercised end to end: allocator-created lane worktree,
claim, prompt rendering. No production code changes; no gate changes.

## Technical Context

- Language/runtime: Python 3.11, `pytest`, `typer.testing.CliRunner`.
- Entry point under test: `specify_cli.cli.commands.agent.workflow.app` command
  `implement` — the documented `spec-kitty agent action implement` surface.
- Fixture surface: a throwaway git repository in `tmp_path` with a mission
  directory (`meta.json`, `lanes.json`, WP prompt), one committed baseline, and
  the mission's status log seeded at `planned` only — the state
  `finalize-tasks` leaves behind. No claim event is seeded, no worktree is
  pre-created, `git` is **not** monkeypatched.
- Unknowns resolved in [research.md](./research.md): the defect does not
  reproduce on `main`; the guard's discriminating power was proven live by
  restoring the pre-`e455ce26c1` comparison layer.

## Constitution Check

- Single canonical authority: the test asserts through the one public CLI
  surface, not an internal seam; no second authority is introduced.
- ATDD-first: acceptance scenarios in `spec.md` map 1:1 onto test functions.
- Locality of change (DIRECTIVE_024): one new test module, zero production
  files.
- DIRECTIVE_041: no duplicated coverage — only the live path is added.
- Test-first for a defect that is already fixed upstream: the red baseline is
  the pre-fix comparison layer; the red evidence is recorded in the module
  docstring from a live run, not fabricated.

## Phase Plan

1. **WP01 — live fresh-claim guard.** New module
   `tests/specify_cli/cli/commands/agent/test_implement_live_fresh_claim_6311.py`
   with four scenarios (fresh claim completes once; recorded claim identity;
   same-identity resume; different-tool refusal) plus the real-worktree
   assertion.
2. **Verification.** Run the new module, the neighbouring #4665/#6311 modules,
   `ruff`, `mypy` on the touched path, and the diff-cover-relevant subset.

## Project Structure

- `tests/specify_cli/cli/commands/agent/test_implement_live_fresh_claim_6311.py` (new)
- `kitty-specs/live-fresh-claim-01M6BV7X/` (planning artifacts)

## Risks

- **Real-git flakiness**: mitigated by an isolated `tmp_path` repo, an explicit
  committer identity, and no reliance on the host checkout.
- **Slow pivot**: the module is marked `integration` + `git_repo` so it stays out
  of the fast suite; measured budget < 60 s (NFR-001).
- **Vacuous pass**: the different-tool refusal scenario (FR-004) is the positive
  control — it proves the positive scenario is not passing because everything is
  admitted.
