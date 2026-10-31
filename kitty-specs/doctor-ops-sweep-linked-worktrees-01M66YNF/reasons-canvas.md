# REASONS Canvas — `doctor ops` across linked worktrees

> Mission: doctor-ops-sweep-linked-worktrees-01M66YNF
> Generated: 2026-10-30
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: Op records are written in the invoking checkout since #6564/#6664, but `doctor ops` lists and sweeps only `<project root>/kitty-ops` (#6661). Worktree Ops are invisible and never closed; the sweep under-reports on the workflow it exists for.
- Acceptance: [spec.md](spec.md) FR-001..FR-006 and SC-001..SC-005 — every checkout listed, each closure on its owning checkout's spine, root-relative listing paths, session-presence scan unchanged and git-free, today's behavior without git.
- Definition of done: failing-first test through `spec-kitty doctor ops`, scoped production fix, targeted green evidence, independent review, changelog + docs, PR only. No merge performed by an implementation agent.

## Entities
- Checkout (repository root checkout or linked worktree) is the unit that owns `kitty-ops/` and its append-only closure spine.
- Op record (`kitty-ops/<invocation_id>.jsonl`) and closure spine (`kitty-ops/op-closures.jsonl`) keep their existing meanings from [docs/architecture/trail-model.md](../../docs/architecture/trail-model.md); no new entity is introduced.
- "Orphan Op" stays "no completed event and no closure on its own checkout's spine".

## Approach
- Reuse the custody enumeration (`git worktree list` in `invocation/op_custody.py`) instead of writing a second walk; the checkout set has one owner.
- Give the sweep one executor per owning checkout, so the spine append, the auto-commit and the closed-id cache land where the record is. Governance stays on the project root.
- Keep `list_orphan_ops` single-checkout: the session-start surface has a published no-git, sub-second budget and widening it needs its own decision (D1 in [research.md](research.md)).
- Tradeoff: doctor pays one `git worktree list` subprocess per run (NFR-001) in exchange for a correct repository-wide sweep.

## Structure
- `src/specify_cli/invocation/op_custody.py`: promote the private checkout enumeration to a public `repository_checkouts`.
- `src/specify_cli/doctor/ops.py`: checkout-aware listing helper; `close_stale_ops` builds one executor per owning checkout.
- `src/specify_cli/cli/commands/doctor.py`: root-relative path rendering for the table and `--json` (no schema change).
- `src/specify_cli/session_presence/open_ops.py`: docstring boundary only, no behavior change.
- Tests: `tests/specify_cli/invocation/test_doctor_ops.py` plus a git-backed multi-worktree module under `tests/specify_cli/invocation/`.
- One work package; implementer owns production and tests, reviewer is independent.

## Operations
1. Reproduce red: a git repository with a linked worktree and an open Op, then `doctor ops --json` from the root checkout — RED before the fix.
2. Commit the failing test, then implement the enumeration and the per-checkout sweep.
3. Verify both halves: listing (exit 1, `../lane/...` path) and sweep (each spine holds only its own closure, second run clean).
4. Run targeted invocation, doctor and session-presence suites plus ruff/mypy on the touched files; record commands and counts.
5. Update changelog and the affected docs (`trail-model.md`, `ops-vs-missions.md`, `cli-commands.md` if the help text changes).
6. Parent operator prepares the PR; no merge, no auto-merge, no push to `main`.

## Norms
- Canonical terminology: Mission, Op, Op record, closure spine, checkout, worktree. Never "feature".
- Python 3.11+, full type hints, ruff and mypy clean, no broad `except Exception` beyond the sweep's existing per-op isolation.
- Targeted test runs only; no full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).
- Changelog entry under `[Unreleased]`, impact-first, `(#6661)`, before/after, under 1,200 characters.

## Safeguards
- Never mutate a per-record `<id>.jsonl` (archive freeze); the sweep writes only the spine, through `complete_invocation`.
- Never close or write into a checkout it cannot resolve as one of this repository's checkouts; `git worktree list` is the only source of the set.
- A failing checkout or a failing close never aborts the rest of the sweep, and never turns a fresh Op into a swept one.
- No new flags, config keys, environment variables or transports; the `doctor ops --json` payload shape is frozen.
- No path outside the repository root is printed absolute; no machine-local path in a commit.
