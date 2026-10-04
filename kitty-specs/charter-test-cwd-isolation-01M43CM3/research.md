# Research: Charter CLI tests independent of invoking checkout

## R-01 — Where the fix belongs

- **Decision**: Test-side isolation; no product change.
- **Rationale**: In production the guard's probe point and repository-root resolution both derive from the process working directory, so they cannot disagree. They split only under the test patch seam re-exported at `src/specify_cli/cli/commands/charter/__init__.py:16-23`. `find_repo_root` follows a linked worktree to the repository root checkout (`generate.py:431-437`), so probing the resolved root would hide the condition the guard exists to catch.
- **Alternatives considered**: (b) derive the probe point from the resolved root — rejected, reintroduces the split the guard closed. (c) stub `resolve_charter_write_root` in tests — rejected, removes the guard from the tests that exercise the write path.

## R-02 — Shape of the shared fixture

- **Decision**: Opt-in fixture returning a callable that sets working directory and `find_repo_root` to one project root; default `tmp_path`.
- **Rationale**: The existing copies only `chdir(tmp_path)` and rely on each test's own patch; affected tests use different project roots (`tmp_path / "mock_repo"`, plain `tmp_path`). A callable serves both. Opt-in because `tests/cli/commands/test_charter_json_error_contract.py` has tests that need the invoking checkout's working directory.
- **Alternatives considered**: autouse isolation for all charter tests — rejected (C-003). A fourth per-file copy — rejected (C-004).

## R-03 — Recurrence check: runtime tripwire over static census

- **Decision**: Autouse call-through wrapper on the guard at its three call sites; violation when the probed path is inside the invoking checkout; failure at teardown.
- **Rationale**: Post-spec review found five patch/invoke spellings across 21 files, mixed files, and helper-indirected invokes. A static per-file census is evadable; the runtime check is per test and spelling-independent, and it fires from a repository root checkout, where the leak is otherwise invisible. Precedent for an autouse checkout-related fixture in the root conftest: `_neutralize_worktree_detection`.
- **Alternatives considered**: AST census with allowlist — rejected as evadable and as standing debt. Running the suite from a real worktree in CI — out of scope (cost).
- **Known limit**: commands started as a separate process are not seen.

## R-04 — Pinned-rule inventory

- **Finding**: `tests/release/pinning_rule_inventory.json` lists `tests/cli/commands/test_charter_json_error_contract.py::_isolate_cwd_from_worktree_guard` (subject `retiring-step`, form `docstring-or-comment`, not a dependency) because the copy's docstring mentions the `make test-fast` target. `tests/release/test_pinning_inventory_fresh.py` requires the file to match its derivation.
- **Decision**: Remove the copy, re-derive the inventory with `scripts/ci/derive_pinning_inventory.py` (no flag regenerates; `--check` verifies), and keep the `make test-fast` literal out of the new support modules so no new rule is minted. The script itself should need no edit.
- **Pre-existing red**: the inventory is already stale on the base branch (a fresh derivation adds `tests/_support/p0_repro.py::<module-docstring>`); reported as #5660 and cleared by the same regeneration.

## R-05 — Finding stragglers

- **Decision**: One bounded discovery run in IC-03: the test files that reference the charter command app, started once with the tripwire on.
- **Rationale**: The known set came from a linked-worktree run of those same files (about 4 minutes). The tripwire reports the same set from any checkout, so the run doubles as proof. It is a named-file run, not a directory or suite sweep.

## R-06 — Smoke test remedy

- **Finding**: The guard runs before the dry-run branch (`synthesize.py:212` vs `:393`), so the subprocess must not start in a linked worktree. The test asserts `Evidence dry-run summary` and `Code signals:`.
- **Decision**: Run the subprocess in a seeded tmp Python project; keep both assertions.

## R-07 — Issues

- Closes: #5317, #5601, and #5660 (the pinning inventory was already stale on the base branch; IC-01 regenerates it).
- #5317's acceptance-test half: not reproducible on current `main` or at base `99352f08`; verdict "verified, no work".
- Not this cause: see #5140. Guard defects: see #5411, #4250. Earlier per-file fix: see #4873.
