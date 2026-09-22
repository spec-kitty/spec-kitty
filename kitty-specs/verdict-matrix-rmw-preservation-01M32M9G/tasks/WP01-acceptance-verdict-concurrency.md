---
work_package_id: WP01
title: '#4858 — acceptance-verdict concurrency lost-update (locked re-read + splice + atomic write)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-013
- FR-014
- FR-015
- FR-016
- FR-017
planning_base_branch: fix/verdict-matrix-rmw-preservation
merge_target_branch: fix/verdict-matrix-rmw-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/verdict-matrix-rmw-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/verdict-matrix-rmw-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-verdict-matrix-rmw-preservation-01M32M9G
base_commit: 320ec4fbbff137250c78fd8f54d6e1b79b42c21a
created_at: '2026-09-21T19:32:22.947462+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- Created by /spec-kitty.tasks 2026-09-21
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/acceptance_verdict.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/acceptance_verdict.py
- src/specify_cli/acceptance/matrix.py
- tests/specify_cli/acceptance/test_acceptance_verdict_command.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load implementer-ivan
```

Apply the resolved initialization, boundaries, directives, and tactics. State which you applied, then continue.

## Objective

Fix #4858 (P0): two concurrent `acceptance-verdict` invocations for **different** entries lose a
committed row because the write is an unlocked read-modify-write that overwrites the whole matrix
from a pre-check snapshot, flipping `overall_verdict` fail→pass. Make the write a **locked
re-read + single-row splice** routed through the **atomic** door, on flat AND coord layouts, for
both negative-invariant and criterion modes.

**Charter gates**: ATDD red-first (C-011) — the failing repro is a SEPARATE commit BEFORE the fix;
`kernel.locks` only (C-001, `test_lock_primitive_ban.py`); atomic write (C-003); no `--feature`
surface (C-004); no `src/specify_cli/__init__.py` change (C-009).

Read first: `../spec.md` (US1/US2/US3, FR-001..FR-009, FR-013..FR-017, C-001/002/003/010/012/013),
`../research.md`, `../contracts/verdict-matrix-preservation-contract.md`, `../research/grounding-4858.md`.

## Grounded facts (verified on baseline)

- `acceptance_verdict.py`: matrix read once at **L440-441** BEFORE the slow check
  `enforce_negative_invariants` (**L329** in `_run_negative_invariant_mode`); whole stale object
  written at **L335**. Criterion mode is structurally identical (`_run_criterion_mode`, mutate
  `matrix.criteria[idx]` then write).
- `matrix.py::write_acceptance_matrix` (**L389-405**): bare `path.write_text(json.dumps(...))`
  full overwrite. `write_and_commit_acceptance_matrix` already carries `entry_id` (confirmed).
- `status/locking.py::feature_status_lock(repo_root, lock_key, *, timeout=-1)`: git-common-dir
  keyed (spans primary + coord worktrees), cross-process, per-thread reentrant, bounded variant
  `BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS = 10.0`. `lock_key = matrix_dir.name`.
- `kernel.atomic.atomic_write(path, content: str|bytes, *, mkdir=False)` — clean `str` drop-in
  (same UTF-8 + trailing newline as the current write).
- `enforce_negative_invariants` and `_resolve_criterion_update` are imported/defined on the
  command module and are monkeypatchable at `specify_cli.cli.commands.agent.acceptance_verdict.*`.

## Subtasks

### T001 — Red-first: NI-mode concurrent lost-update harness (flat) [ATDD, commit FIRST]
Add `TestConcurrentVerdictLostUpdate` to `tests/specify_cli/acceptance/test_acceptance_verdict_command.py`
(reuse `_init_flat_mission`, `_git`, `_seed_matrix`). Deterministic serialized `read1 → full-run2 →
finish1` (NO real threads): wrap the **command-module binding**
`specify_cli.cli.commands.agent.acceptance_verdict.enforce_negative_invariants` with a **one-shot**
`nonlocal`-guarded wrapper that, on A's call, drives B's full invocation once (B runs the real
check + commits NI-B `still_present` with evidence), then delegates to the real check for A.
Assertions (US1 **S1 + S2**), all via **disk reload** `read_acceptance_matrix(matrix_dir)`:
- Mid-point (S2): after B finishes, before A resumes, on-disk matrix already contains NI-B (provenance).
- After A finishes (S1): NI-A (A's passing row) AND NI-B (`still_present` + evidence) both present;
  `overall_verdict == "fail"`. RED on base (NI-B dropped, verdict `pass`).
Commit as `test(#4858): failing concurrent-verdict lost-update repro (flat, NI mode)`.

### T002 — Red-first: coord variant + criterion-mode variant + gate spies [ATDD, same test commit]
Extend the failing suite (still before the fix):
- **Coord** (import `_build_coord_mission_for_matrix` — do NOT edit that fixture file): drive A with
  `repo_root=`primary and B with `repo_root=coord_root`; assert coord matrix path ≠ primary; same
  survival + `fail` outcome (US2 S1). Add the lock-key-equality assertion: both roots resolve the
  same `feature_status_lock` path under the common dir (US2 S2).
- **Reverse-role (US1 Scenario 3)**: a second NI-mode interleaving where **B commits a passing row
  and A commits a failing row**; assert (disk reload) BOTH rows survive and `overall_verdict ==
  "fail"`. This catches a splice that drops a *passing* sibling row — invisible to S1 (where A's
  own row is passing). Do NOT rely on S1 alone.
- **Criterion mode** (User Story 3): force interleaving at `_resolve_criterion_update`; both
  criterion rows survive, verdict stays `fail`.
- **Gate spies/ordering** (US1 S4–S9): spy `feature_status_lock` acquired with
  `lock_key == matrix_dir.name`, path under common dir; strict order
  `lock.__enter__ → read_acceptance_matrix → write → lock.__exit__` (re-read INSIDE lock);
  call-order check-before-lock; `write_acceptance_matrix` routes through `atomic_write`;
  fail-closed on timeout (patch `feature_status_lock` to raise → assert NO write + non-zero exit);
  reported `overall_verdict` == disk verdict.
Fold into the same red-first commit (or a second test commit) — all BEFORE any fix commit.

### T003 — Fix: locked re-read + single-row splice in acceptance_verdict.py (both modes)
Restructure both mode handlers:
1. Run the slow check OUTSIDE the lock (NI mode); compute the owned row's judged result.
2. **Materialize the coord worktree, then** acquire `feature_status_lock(repo_root, matrix_dir.name)`
   with the **bounded** timeout; on timeout **fail closed** (no write, structured non-zero error).
3. INSIDE the lock: re-read `read_acceptance_matrix(matrix_dir)` (surface == commit surface);
   splice ONLY the owned row —
   - NI: a **new replace-or-append helper** that inserts the already-judged row (do NOT reuse
     `_register_negative_invariant`, which resets to `pending`);
   - Criterion: recompute `index_by_id`/unknown-criterion from the re-read, then apply
     `_resolve_criterion_update` to the fresh row.
4. Write+commit via `write_and_commit_acceptance_matrix(..., entry_id=...)`.
5. Emit `overall_verdict` and the result payload from the **re-read+spliced** matrix.
Keep `matrix_dir` resolved once and reused as re-read base + write target (FR-003/C-013).

### T004 — Fix: atomic write at the shared writer (matrix.py)
Replace `write_acceptance_matrix`'s `path.write_text(...)` with
`kernel.atomic.atomic_write(path, json.dumps(matrix.to_dict(), indent=2) + "\n")` (tempfile in
`matrix_dir`, no residue). Add the `from kernel.atomic import atomic_write` import (sanctioned
`specify_cli → kernel` direction). Benefits all callers (C-003/FR-009/NFR-004).

### T005 — Verify red→green + blast radius
Confirm each new test is RED on the mission base and GREEN on the fix. Run the shared baseline
`make test-fast` **plus** the targeted surface:
`.venv/bin/python -m pytest tests/specify_cli/acceptance/ tests/acceptance/ tests/lanes/test_acceptance_matrix.py tests/integration/test_accept_matrix_coord_partition.py tests/integration/test_issue_2404_acceptance_matrix_write_surface.py -q`
plus `tests/architectural/test_lock_primitive_ban.py`. **Paste actual terminal output** (not
hand-typed counts) into the WP/PR *Tests run* section — the reviewer RE-RUNS these commands rather
than trusting recorded counts.

### T006 — Lint/type/format
`uv run --frozen ruff check src/specify_cli/cli/commands/agent/acceptance_verdict.py src/specify_cli/acceptance/matrix.py`;
`uv run --frozen ruff format --check` the touched files; `uv run --frozen mypy src/specify_cli/cli/commands/agent/acceptance_verdict.py src/specify_cli/acceptance/matrix.py` clean (no new `# type: ignore`).

## Definition of Done
- All FR-001..FR-009, FR-013 (acceptance), FR-014..FR-017 acceptance criteria pass.
- Red-first commit precedes the fix commit(s); reviewer can verify red-on-base → green-on-fix.
- `test_lock_primitive_ban.py` green; no raw `fcntl`/`msvcrt`/`filelock`; `write_if_changed` NOT
  activated. No `__init__.py` change. ruff + mypy clean.

## Risks / reviewer guidance
- **Killer mutant**: a re-read placed OUTSIDE the lock passes the serial harness but reopens the
  P0 — the strict `enter→read→write→exit` ordering assertion (T002) is what kills it. Verify it.
- **NI splice**: confirm the judged result is preserved (not reset to `pending`).
- **Fail-open**: verify a lock timeout NEVER writes.
- **Surface**: confirm the re-read surface equals the commit surface (coord materialized before lock).
