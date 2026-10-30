# Tasks: `doctor ops` sweeps Op records in every checkout

Mission: `doctor-ops-sweep-linked-worktrees-01M66YNF` · Branch: `issue-6661-doctor-ops-sweep-linked-worktrees` (plans and lands here; it reaches `main` through a PR) · Topology: `single_branch` (one WP; it runs in the write checkout)

## WP01 — Sweep Op records across every checkout (code_change)

Prompt: [tasks/WP01-doctor-ops-checkout-sweep.md](tasks/WP01-doctor-ops-checkout-sweep.md) · Requirements: FR-001..FR-006, NFR-001..NFR-003, C-001..C-004, SC-001..SC-005

- T001 Red-first: a git-backed test that seeds an open Op record in a linked worktree and asserts `spec-kitty doctor ops --json` (run from the root checkout) lists it as `../lane/kitty-ops/<id>.jsonl` and exits 1. RED on the base: today it returns `[]` and exits 0.
- T002 Red-first: the sweep half — `--close-stale --threshold 0` closes the worktree Op through the worktree's own executor, so the lane's `kitty-ops/op-closures.jsonl` holds that closure and the root's does not. RED on the base (the record is never even enumerated).
- T003 Promote `_repository_checkouts` to public `repository_checkouts` in `src/specify_cli/invocation/op_custody.py` (docstring, `__all__`, existing caller). It stays the only enumeration of checkouts.
- T004 `src/specify_cli/doctor/ops.py`: add `list_orphan_ops_across_checkouts(repo_root)` — project root first, then `repository_checkouts`, de-duplicated by resolved path, each checkout read with its own `list_orphan_ops` (its own closure spine). `close_stale_ops` enumerates through it and keeps one cached `ProfileInvocationExecutor(record_root=<owning checkout>)` per checkout, with `repo_root` still owning governance and the propagator. Per-op outcomes, error isolation and the `commit` vocabulary are unchanged.
- T005 `src/specify_cli/cli/commands/doctor.py`: render each listed record relative to the project root (`os.path.relpath`, `/` separators) in the human table and the `--json` payload, so an out-of-root record shows as `../lane/kitty-ops/<id>.jsonl` instead of raising `ValueError`. Payload shape stays `[{"path": ...}]`.
- T006 `src/specify_cli/session_presence/open_ops.py`: docstring states the deliberate boundary (single checkout, no git, budget preserved); `tests/specify_cli/session_presence/test_open_ops.py` pins it — `list_orphan_ops` spawns no git subprocess and a worktree Op is not reported there.
- T007 Tests for the rest of the contract: degraded paths (non-git directory, failing `git worktree list` behave as today), deterministic ordering (root first, then git order), exactly one `git worktree list` per run, and the root-only case byte-identical to today.
