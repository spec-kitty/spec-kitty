# Grounding report — Issue #4858 (P0)

**Baseline:** branch `main` @ `32cfc272ee92ff65d2a45375abc760476b702d56` (confirmed via `git rev-parse HEAD`; working tree clean).
**Verdict: the bug reproduces exactly as reported.** There is a genuine unlocked read-modify-write / lost-update on the whole acceptance matrix. No lock, no CAS, no re-read-under-lock, and no content merge exists anywhere on this path today.

---

## Confirmed mechanism (file:line)

The command reads the entire matrix ONCE, before either mode's mutation/verification runs, and later writes that whole (now-stale) in-memory object back wholesale.

`src/specify_cli/cli/commands/agent/acceptance_verdict.py`:
- **L440-441** — the read, performed BEFORE any mode dispatch or custom check:
  ```python
  matrix_dir = _matrix_read_dir(repo_root, mission_slug)
  matrix = read_acceptance_matrix(matrix_dir)
  ```
- **L450-464** — negative-invariant dispatch; the read `matrix` object is threaded straight into `_run_negative_invariant_mode(...)`.
- **`_run_negative_invariant_mode`, L314-331** — mutates that same in-memory object: `_register_negative_invariant(matrix, ...)` (L314) then runs the custom check `enforce_negative_invariants(repo_root, matrix.negative_invariants)` (L329, a slow `subprocess` grep/command). The check therefore runs strictly AFTER the L441 read.
- **L335-342** — `write_and_commit_acceptance_matrix(repo_root, mission_slug, matrix_dir, matrix, entry_id=..., message=...)` writes the WHOLE `matrix` object back.
- Criterion mode is structurally identical: `_run_criterion_mode` mutates `matrix.criteria[idx]` (L268) and writes the whole object at L270-277.

`src/specify_cli/acceptance/matrix.py`:
- **`write_and_commit_acceptance_matrix`, L408-473** — the `_stage()` thunk (L460-461) calls `write_acceptance_matrix(matrix_dir, matrix)`.
- **`write_acceptance_matrix`, L389-405** — a full-file overwrite:
  ```python
  path.write_text(json.dumps(matrix.to_dict(), indent=2) + "\n", encoding="utf-8")
  ```
  `matrix.to_dict()` (L337-349) serializes ALL criteria + ALL negative_invariants from the stale snapshot. `overall_verdict` is a computed property (L310-335), so it recomputes from whatever rows the stale object carries.

**Lost-update timeline (two distinct invariants, earlier-started finishes last):**
1. P1 reads matrix (L441) — snapshot S1.
2. P2 reads matrix (L441) — snapshot S2 (does not yet contain P1's terminal judgement).
3. P1 registers+checks NI-A → `still_present` (NI-FAIL), writes whole S1+NI-A, git commit → `committed`.
4. P2 registers+checks NI-B (passes), writes whole S2+NI-B. S2 never saw P1's NI-A terminal row, so the write DROPS NI-A's committed `still_present`. `overall_verdict` recomputes fail→pass. Both invocations exit 0 / `write_status: committed`.

The whole-object overwrite is the defect: even byte-serialized git commits cannot save it, because the on-disk file content is fully replaced from the stale snapshot.

## Current locking/commit surface

- **No application-level lock on the read→verify→write span.** Grepped `src/specify_cli/coordination/commit_router.py`, `write_seam.py`, `src/specify_cli/acceptance/**`, and `acceptance_verdict.py` for `feature_status_lock` / `status.locking` — **NONE**. The acceptance-verdict path never acquires the per-mission status lock.
- **The commit is routed, not locked.** `write_and_commit_acceptance_matrix` → `coordination/write_seam.py::write_artifact` (L418-510) → `_probe_write_target` then `commit_for_mission` (or the E2 `_commit_post_consolidation_write` bypass). `write_artifact`'s only guarantees are FR-011 zero-write refusal on unroutable target and FR-005 probe-before-stage (`_materialize_files`, L272-288). Neither serializes an RMW.
- **`commit_for_mission` does not touch matrix content.** Its `_merge_group_results` (commit_router.py L653+) merges per-PARTITION-GROUP git commit outcomes, NOT matrix rows — there is no content-level CAS/merge/re-read of `acceptance-matrix.json`.
- **Only git's own `.git/index.lock` serializes the commit step.** That protects the git index, not the earlier L441 read nor the full-file `write_text`. As the reporter states: serializing the commit does not protect the earlier read.
- **A ready-made, correct lock primitive already exists and is unused here:** `src/specify_cli/status/locking.py::feature_status_lock(repo_root, lock_key, *, timeout=-1)` (L277-297). It is keyed on the git **common dir** (`feature_status_lock_path`, L147-158 → `_git_common_dir`), so it coordinates the SAME lock file across the primary checkout AND coordination worktrees (critical for the coord-partition reproduction), is cross-process (`kernel.locks.machine_file_lock`), re-entrant per thread, and offers a bounded-timeout variant (`BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS = 10.0`). `lock_key` MUST be the mission directory name (`feature_dir.name`), never a bare slug (FR-004/C-003).

## Fix seam options (do NOT implement)

The invariant to restore: the read used to build the write, the row mutation/verification, and the write-back must be one atomic critical section against intervening row changes — and the write must merge the single changed row into the CURRENT on-disk matrix, not overwrite it from a pre-check snapshot.

**Option A — locked re-read + single-row merge at the command seam (recommended).**
In `acceptance_verdict.py`, wrap the mutate→write in `feature_status_lock`. Because the custom check (`enforce_negative_invariants`) is slow, the clean shape is: run the check to determine the one row's outcome, then INSIDE the lock RE-READ the matrix from disk (`read_acceptance_matrix(matrix_dir)`), splice in ONLY the row this invocation owns (`entry_id` — the criterion id or invariant id), and write+commit. This guarantees no sibling row (e.g. a concurrently-committed NI-FAIL) is clobbered. Files changed: `acceptance_verdict.py` (`acceptance_verdict`, `_run_criterion_mode`, `_run_negative_invariant_mode`). `lock_key` = `matrix_dir.name` / `feature_dir.name`.

**Option B — locked RMW pushed into the write chokepoint (`matrix.py`).**
`write_and_commit_acceptance_matrix` already receives `entry_id`. Give it a "merge one row" contract: acquire `feature_status_lock`, re-read on-disk matrix, replace exactly the `entry_id` criterion/invariant from the passed `matrix`, then stage+commit — all under the lock. This makes every writer (verdict command, and any future caller) safe at one locus, but the function currently takes the whole matrix and does not know whether `entry_id` is a criterion vs invariant; the contract must disambiguate (e.g. an explicit section arg, or look the id up in both lists). Files changed: `acceptance/matrix.py` (`write_and_commit_acceptance_matrix`, possibly a new merge helper); `acceptance_verdict.py` callers unchanged in shape.

**Option C — content CAS on matrix hash.**
Capture a hash of the on-disk file at L441; before writing, re-read and compare; on mismatch, re-read + re-merge (retry loop). More moving parts than A/B and still needs the per-row merge to be correct; a lock is simpler and matches existing doctrine (`status/locking.py` exists precisely to close unlocked-writer races). Not recommended standalone.

Whichever option: the mutation must be a **single-row merge** into the freshly re-read matrix, and the lock must be the git-common-dir-keyed `feature_status_lock` so it holds across coord worktrees. Note `enforce_negative_invariants` (a subprocess grep) ideally runs OUTSIDE the held lock to keep the critical section short; only the re-read+merge+write is locked.

## Test coverage & fixtures

- `tests/specify_cli/acceptance/test_acceptance_verdict_command.py` (533 lines): covers overall_verdict-is-computed (`TestOverallVerdictIsComputedNotStored`), determinism/no-IO, #2318 persist-on-accept, `write_and_commit` behavior, and `TestAcceptanceVerdictCommand` — records/persists verdict, FR-012 idempotent re-run is a no-op (`write_status == "unchanged"`, HEAD unchanged), unknown criterion → exit 1, invalid result → exit 2, and coord-surface landing (no stranded primary copy). **No concurrency / lost-update / lock test.**
  - Fixtures: `_git(repo_root, *args)` (L55) — subprocess git helper; `_init_flat_mission(tmp_path, slug)` (L87) — minimal real flat mission on non-default branch `matrix-verdict-work` with `.kittify/config.yaml`, `meta.json` (minted shape-valid ULID via `_mission_id_for`, L71); `_head` (L64); `_seed_matrix` (L373, seeds one pending `FR-001`). The coord fixture is IMPORTED: `from tests.integration.test_accept_matrix_coord_partition import _build_coord_mission_for_matrix` (L43-44).
- `tests/integration/test_accept_matrix_coord_partition.py` (620 lines): #2404 coord-topology characterization across all three production write paths (spec-commit, finalize-tasks, accept residual); pins resolved coord dir against `CoordinationWorkspace.resolve`. **No concurrency test.**
  - `_build_coord_mission_for_matrix(tmp_path)` (L115): builds a real COORD-topology mission via golden-path primitives (`_init_git_repo`/`_create_mission`/`_commit`/`_materialize_coord_worktree` from `test_placement_partition_golden_path.py`), seeds a real `lanes.json` keyed on the minted `mission_id`/`mid8` (`write_single_lane_manifest`), and returns `(result, coord_root, coord_feature_dir)` — where `coord_feature_dir = coord_root/kitty-specs/<slug>` is the exact path the placement seam resolves ACCEPTANCE_MATRIX to. Asserts coord ≠ primary (non-vacuous) and that the coord worktree lazily materializes.
- Confirmed via grep across `tests/specify_cli/acceptance/`, `tests/integration/test_accept_matrix_coord_partition.py`, `tests/lanes/test_acceptance_matrix.py`: **zero** references to `concurren*`, `threading`, `Thread(`, `Process(`, `lost update`, `feature_status_lock`, or `race`. No existing regression guards the reported behavior.

## Regression test to add

A failing-first test that drives two overlapping `acceptance-verdict --negative-invariant` invocations for two DISTINCT invariant ids, where the earlier-STARTED one finishes LAST, and asserts:
- Both rows survive on disk with their evidence intact (NI-A `still_present` AND NI-B present).
- `overall_verdict` stays `fail` if EITHER row fails (fail is not silently flipped to pass).
- Both invocations report `write_status: committed`.
- Add BOTH a flat variant (`_init_flat_mission`) and a coord variant (`_build_coord_mission_for_matrix`), since the reporter states it reproduces on both layouts and the coord surface is where the shared-lock-across-worktrees behavior matters.
- Determinism: force the "earlier reads first, finishes last" interleaving deterministically — e.g. monkeypatch/wrap `enforce_negative_invariants` (or `read_acceptance_matrix`) so P1's read happens, then P2 fully completes its commit, then P1's check+write proceeds against its stale snapshot. Avoid real threads for determinism; a serialized two-phase harness (read1 → full-run2 → finish1) reproduces the lost update reliably. A green post-fix run proves the locked re-read+merge preserves the sibling row.

Home: `tests/specify_cli/acceptance/test_acceptance_verdict_command.py` (new `TestConcurrentVerdictLostUpdate` class) reusing existing fixtures; the coord case can live alongside in the same file (it already imports the coord fixture).

## Blast radius (per CLAUDE.md test policy)

- **Source likely to change:** `src/specify_cli/cli/commands/agent/acceptance_verdict.py` (Option A) and/or `src/specify_cli/acceptance/matrix.py` (Option B); reuses existing `src/specify_cli/status/locking.py` (no change expected there).
- **Baseline:** `make test-fast` (`tests/unit tests/status tests/cli tests/specify_cli/runtime`).
- **Targeted module + owning-subsystem dirs:**
  - `tests/specify_cli/acceptance/` (owns `acceptance_verdict.py` command tests, negative-invariant authoring, gate cores).
  - `tests/acceptance/` (owns `src/specify_cli/acceptance/**` — matrix, gates_core, post_consolidation, provenance/deferral, scaffold).
  - `tests/lanes/test_acceptance_matrix.py`.
  - `tests/integration/test_accept_matrix_coord_partition.py` and `tests/integration/test_issue_2404_acceptance_matrix_write_surface.py` (coord write-surface).
  - If `matrix.py`'s `write_and_commit_acceptance_matrix` signature/contract changes: also `tests/specify_cli/test_acceptance*.py`, `tests/specify_cli/test_canonical_acceptance.py`, and any `write_seam`/`commit_router` coverage the call threads through.
  - If `status/locking.py` is touched at all: its owning tests (grep `feature_status_lock` under `tests/`).
- **No cross-cutting config change expected** (no pytest.ini/pyproject/conftest/markers), so `tests/architectural/` is not mandated unless the fix adds a new guard-capability call site or import edge.
- Record exact commands + passed/failed counts in the PR's *Tests run* section; watch for the baseline-red gotcha (attribute unrelated reds before folding).
