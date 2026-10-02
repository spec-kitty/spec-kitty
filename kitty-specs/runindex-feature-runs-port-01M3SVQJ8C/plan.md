# Plan — RunIndex port

**Mission:** runindex-feature-runs-port · fixes #5390, #5389 · refs #2624

## Architecture

Introduce `src/runtime/next/run_index.py` — the **RunIndex** port, the single canonical
reader/writer of `.kittify/runtime/feature-runs.json`. It owns:

- the filename/path constants (`FEATURE_RUNS_FILENAME`, `_feature_runs_path`, lock-path);
- **token serialization** on write: `run_dir → repo-relative token` (`.as_posix()`);
- **read-time resolution + containment**: `token → absolute Path`, resolved against the
  **invoking** `repo_root`, expanding `${VAR}` via `kernel.env_expand.expand_raw_template`;
  refuse (raise `RunDirOutsideRepoError`) any resolved path escaping `repo_root`;
- **locked read-modify-write** via `kernel.locks.machine_file_lock` against a dedicated
  `feature-runs.json.lock` sidecar: acquire → re-read fresh → canonicalize/merge → re-check
  same mission → atomic replace.

`runtime_bridge_io.py` keeps its function names (`load_feature_runs`, `save_feature_runs`,
`get_or_start_run`, `_existing_run_ref`, `_resolve_run_dir_for_mission`, `_require_run_state`)
but their bodies delegate to the port so the compat/monkeypatch seams and the existing call
graph are preserved. `runtime_bridge.py` delegates stay thin. `state/contract.py` imports the
filename constant from the port (keeps the literal single-homed).

Layering: port imports `kernel.locks`, `kernel.env_expand`, `kernel.atomic`/`specify_cli.core.atomic`
(already used by the seam), stdlib. No new `runtime→specify_cli` edges beyond what the seam
already declares.

## Token contract

- Canonical token for any run: `Path(run_dir).relative_to(repo_root).as_posix()`
  (always `.kittify/runtime/runs/<run_id>` since run_store is deterministic).
- Read resolution: `expand_raw_template(token)` → if absolute, that's a legacy/foreign value:
  containment-check against `repo_root`; if inside, use it (healable); if outside, **refuse**.
  If relative, resolve `repo_root / token`, then containment-check.
- Heal rewrites any absolute entry to `.kittify/runtime/runs/<basename>` (canonical relative).

## Work packages (single implementer/reviewer, sequential — direct on branch)

- **WP00 — Campsite (distinct preceding step, behaviour-preserving):** hoist repeated
  entry-key literals (`run_id`/`run_dir`/`mission_type`/`mission_key`/`mission_id`/
  `mission_slug`) and the `runtime`/`runs` path segments to named constants in the seam;
  no functional change. Focused characterization test stays green.
- **WP01 — Red-first regression tests (ATDD):** issue-pinned `@pytest.mark.regression` tests
  through the real `next` entry point — copy, move, two-process concurrent start — RED on
  pre-fix code. Plus a port-level `never-persists-absolute` test (RED pre-fix).
- **WP02 — RunIndex port + rewire:** implement the port; delegate the seam functions; keep
  ≤15 complexity by extracting `_register_new_run`/`_reuse_existing_entry` helpers. GREEN.
- **WP03 — Heal migration + doctor:** `m_*_heal_run_index_paths` (`BaseMigration`,
  `describe_leaks`) + `cli/commands/_run_index_doctor.py` (`register(app)`); tests.
- **WP04 — Empty-allowlist gates:** (a) single-reader literal gate + self-mutation test;
  (b) never-persist-absolute behavioural gate.

## Testing (mission scope — NO heavy suites)
`make test-fast` + `tests/runtime/`, `tests/next/` (touched files), the migration/doctor test
files, and the SPECIFIC new gate files. Record commands + counts in the PR.

## Risk / point-cuts for the adversarial squad
- Owned-checkout arm (fresh from #5445): the token must resolve against the same `repo_root`
  the run_store used; verify owned runs still resolve.
- Legacy absolute-inside-repo (in-place old project) must keep working (not refused).
- Lock path must be a dedicated sidecar (never truncate the payload — kernel lock G1).
- Containment must use resolved real paths (symlink/`..` safe) and not break Windows posix
  token separators.
