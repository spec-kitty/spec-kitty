# Verdict ledger — #5353 slice 3 (tests/cli)

PR: https://github.com/spec-kitty/spec-kitty/pull/5430

Totals: 92 flagged — KEEP 37 · FIX 17 · RETIRE 17 · DEFER 21 (A: 10/2/1/0; B: 27/15/16/21).

# Plan — #5353 slice 3, `tests/cli` (orchestrator rulings + ownership map)

Base: local branch `issue-5353-cli-test-quality` (tip at dispatch time). Verdicts: `verdicts-A.md`, `verdicts-B.md` (same folder). Read the verdict detail for every item you own before you start.

Counts in: A 10 KEEP / 2 FIX / 1 RETIRE; B 27 KEEP / 15 FIX / 16 RETIRE / 21 DEFER.

## Rulings

1. **Product fix (O owns, the ONLY `src/` edit in this PR): `retrospect._maybe_auto_commit` fails silently.**
   `src/specify_cli/cli/commands/retrospect.py::_maybe_auto_commit` ends in `except Exception: pass`, so a failed
   `git add`/`git commit` is invisible to the operator: the record is not committed and nothing says so. Fix: keep it
   non-fatal (the record write already succeeded), but surface a one-line warning on stderr naming the failure (the
   git stderr, or the exception) so the operator can commit by hand; `--json` output must stay parseable (warning to
   stderr only, or a field in the payload — pick what matches this module's existing warning convention).
   Red-first through the pre-existing entry point: drive `retrospect create` (or `backfill`) with `CliRunner` against
   a real tmp git repo with auto-commit on and a `git add` that genuinely fails (e.g. a path outside the repo, which
   Bundle A showed yields `fatal: ... is outside repository`), assert the warning; it must be red on `main`.
   Also CHECK (do not necessarily fix) the coord-topology claim: whether the canonical events path for a coord mission
   lies in the coord worktree so the single `git add` from repo root fails. Record the finding in your red-proofs file.
   Routing commits per owning checkout is OUT of scope (deferred); the warning is the fix.
   Commit as its own `fix(cli): …` commit, before the test commits.
2. **P3 (`--proposal-id` bypasses the accepted-only filter)**: product question, DEFERRED. G8 must pin the
   accepted-only default and the dry-run default only; do NOT pin the bypass behaviour either way.
3. **P4 (dead `ensure_sync_daemon` kwarg), P6 (sidecar term lacks isolated guard), P8 (headless-login e2e 301 s
   timeout)**: DEFERRED (outside `tests/cli` or product debt).
4. **D1 (test_retrospect.py harness rewrite, 20 tests) and D2 (real LANES done-bookkeeping guard)**: DEFERRED.
5. `test_charter_json_error_contract.py`: KEEP as is.
6. Scanner false positives (`skip-or-xfail` on string literals, `literal-source-scan` on fixture reads): DEFERRED
   (scanner follow-up, not this PR).

## Ownership map (disjoint)

### Implementer O — python-pedro, Opus (oracle design + the product fix)
- `src/specify_cli/cli/commands/retrospect.py` (ruling 1 only)
- `tests/cli/commands/test_retrospect.py`: A-G2 (the two FIXes + full-argv tightening of
  `test_auto_commit_enabled_calls_git`) and B-G7 (`TestMaybeAutoCommit` real-git: `test_auto_commit_disabled`,
  `test_auto_commit_enabled_calls_git`, `test_auto_commit_file_outside_repo_root`), plus the red-first test for ruling 1.
  Do NOT rewrite the rest of the file (D1).
- `tests/cli/commands/test_retrospect_update_persisted.py`: B-G7 FIX (real event-log row instead of the emit spy).
- `tests/cli/commands/test_auth_login.py`: B-G1 (RETIRE 3, FIX 3, `canonical_home` isolation).
- `tests/cli/commands/test_merge_strategy.py`: B-G5 (real `consolidate --strategy` test; closes P1 coverage gap).
- `tests/cli/test_agent_retrospect_synthesize.py`: B-G8 (closes P2 coverage gap; see ruling 2).

### Implementer S — python-pedro, Sonnet (mechanical)
- `tests/cli/commands/test_auth_logout.py`: A-G1 RETIRE `test_logout_impl_is_importable`, B-G2 RETIRE
  `test_logout_local_cleanup_failure_exits_1`, add `canonical_home` isolation.
- `tests/cli/commands/test_charter_bundle_coverage.py`, `tests/cli/commands/test_charter_orchestration.py`,
  `tests/cli/commands/test_charter_rendering.py`: B-G3 retirements.
- `tests/cli/commands/test_merge_status_commit.py`, `tests/cli/commands/test_implement_base_flag.py`,
  `tests/cli/test_doctrine_org_commands.py`: B-G4 (D2 stays deferred).
- `tests/cli/commands/test_doctor_mission_state.py`: B-G6.
- `tests/cli/test_events_tail.py`: B-G9.
- `tests/cli/test_init_templates_preservation.py`, `tests/cli/test_mission_agnostic_flag.py`: A-G3 nits.
- S edits NO `src/` file.

Shared files: `ruff.toml` only if a per-file-ignore entry becomes stale (shrink-only; remove the entry in the same
commit that clears it). Nobody else touches conftest, fixtures under `tests/auth/`, `tests/terminus/`, or markers.

## Protocol (both implementers)

- FIX: plant break in `src/` → old test GREEN → fixed test RED → `git checkout -- src/` → fixed test GREEN →
  `git diff --stat src/` before every commit (O: only ruling-1 changes; S: empty).
- RETIRE: the named guard goes RED on the same break before deletion; confirm the guard is not vacuous.
- If a verdict proves wrong, change it and record why in your red-proofs file. Never force it.
- Evidence: `red-proofs-{O,S}.md` untracked in your worktree root. Do NOT commit it.

---
# Bundle A verdicts — `tests/cli` test-quality pass (#5353 slice 3)

Reviewer: reviewer-renata. Question: *can this test ever fail, and is its oracle precise?*
Rubric: test-desiderata-and-boundaries styleguide, DIRECTIVE_041, development-assist-test-cleanup,
test-suite-quality-assessment, TEST_QUALITY_TRIAGE.

All planted breaks were run in the private worktree
`/tmp/claude-0/-home-user-spec-kitty/65dfc8f8-e730-5de4-8262-f4d275e276bc/scratchpad/review-A`
(detached at `c34481d76`), then reverted with `git checkout -- src/`. `git status --porcelain src/` was
empty after each run. Nothing was planted in `/home/user/spec-kitty`.
Test command: `PYTHONPATH=$PWD/src .venv/bin/python -m pytest <file>[::node] -p no:cacheprovider -rA`.

**Counts: 13 flagged. 10 KEEP, 2 FIX, 1 RETIRE, 0 SPLIT-BY-KIND, 0 DEFER.**
Five of the 13 static flags are scanner false positives: L137 zeitgeist, L249 init-templates,
L55, L62 and L69 mission-agnostic. Every KEEP below was either proved by a planted break or is a
false positive with a named reason.

## 1. Summary

| File | Test | Flag | Verdict | One-line reason |
|---|---|---|---|---|
| `tests/cli/commands/test_auth_logout.py` | `test_logout_impl_is_importable` | type-only-assert | **RETIRE** | Renaming `logout_impl` turns all 9 `runner.invoke(app, ["logout"…])` tests in the same file red (verified). The `callable()` pin adds nothing. |
| `tests/cli/commands/test_charter_package_exports.py` | `test_charter_all_exports_are_defined` | type-only-assert | KEEP | `hasattr` over `__all__` is the exact contract. It goes red on a planted undefined `__all__` entry (verified). Ruff F822 does **not** cover `__init__.py`: it stayed green on the same break (verified). |
| `tests/cli/commands/test_retrospect.py` | `TestMaybeAutoCommit::test_auto_commit_raises_is_nonfatal` | no-assertion | KEEP | The oracle is "does not raise". It goes red when `get_auto_commit_default` is moved outside the `try` (verified). |
| `tests/cli/commands/test_retrospect.py` | `TestMaybeAutoCommit::test_auto_commit_file_outside_repo_root` | no-assertion | **FIX** | Vacuous: the outer `except Exception: pass` swallows any break in the fallback. It stayed green with the `ValueError` fallback deleted (verified). |
| `tests/cli/commands/test_retrospect.py` | `TestBackfillDiscovery::test_discover_missions_skips_non_dirs` | type-only-assert | **FIX** | `isinstance(result, list)` is always true. It stayed green with `continue`→`break` in the discovery loop (verified). |
| `tests/cli/commands/test_retrospect.py` | `TestBackfillDiscovery::test_discover_missions_unstattable_entry_is_not_silently_skipped` | skip-or-xfail | KEEP | The skip is an honest environment guard (root, or mode bits ignored), not a masked defect. #3194 is the fixed defect it pins. It skips here (uid 0) and runs on GitHub-hosted non-root runners. |
| `tests/cli/commands/test_retrospect.py` | `TestSummaryCmdExtended::test_summary_unstattable_mission_candidate_is_not_silently_skipped` | skip-or-xfail | KEEP | Same guard as above. The oracle is precise: exit 2 plus the `I/O error reading corpus` message. |
| `tests/cli/commands/test_zeitgeist_operability_cli.py` | `test_drill_outcome_color` | skip-or-xfail | KEEP | Scanner false positive: there is no skip or xfail, only the parametrize value `"skipped: drain off"`. It is an exact-equality oracle on a pure function. |
| `tests/cli/test_init_templates_preservation.py` | `test_local_full_copy_source_absent_preserves_pre_existing_operator_templates` | literal-source-scan | KEEP | Scanner false positive: it reads the operator's **fixture file** on disk, not source code. The oracle is on-disk state plus the `not package-owned` diagnostic. One redundant assert is a nit. |
| `tests/cli/test_mission_agnostic_flag.py` | `test_observed_command_accepts_and_ignores_mission` | no-assertion | KEEP | `make_context` raises `NoSuchOption` when broken. It goes red when `MissionAgnosticCommand.get_params` drops the option (verified). |
| `tests/cli/test_mission_agnostic_flag.py` | `test_observed_command_accepts_equals_form` | no-assertion | KEEP | Same as the previous row (verified red). |
| `tests/cli/test_mission_agnostic_flag.py` | `test_sub_app_used_as_leaf_command_accepts_mission` | type-only-assert | KEEP | `isinstance` is not the only oracle: `make_context` also parses. It goes red when `MissionAgnosticGroup.get_params` drops the option (verified). |
| `tests/cli/test_mission_brief.py` | `test_clear_is_idempotent` | no-assertion | KEEP | The oracle is "does not raise". It goes red with `missing_ok=False` in `clear_mission_brief` (verified). |

## 2. Per-test detail

### 2.1 `test_auth_logout.py::test_logout_impl_is_importable` (L358) — RETIRE

- **What it does:** it imports `logout_impl` from `specify_cli.cli.commands._auth_logout` and asserts `callable(...)`.
- **Why it is redundant:** the dispatch shell `src/specify_cli/cli/commands/auth.py:82` does the same lazy import on every `logout` invocation. Every CliRunner test in `TestAuthLogoutCommand` in the same file drives that path and asserts `exit_code == 0` / `"Logged out"` or the error exit.
- **Covering guard:**
  - `tests/cli/commands/test_auth_logout.py::TestAuthLogoutCommand` (9 tests), for example `test_logout_success_revoked` and `test_logout_force_skips_server`.
  - The guard is not vacuous: each test asserts the exit code, stdout, and storage-delete interactions.
- **Planted break:** in `src/specify_cli/cli/commands/_auth_logout.py`, rename `async def logout_impl(` to `async def logout_impl_renamed(` and update `__all__`.
  - Result: **all 9 guard tests FAILED**, and the retired test FAILED too. Verified.
- **Action:** delete the test and its section banner. The file needs no other change.

### 2.2 `test_charter_package_exports.py::test_charter_all_exports_are_defined` (L14) — KEEP

- **Flag:** `type-only-assert` (`hasattr`). Here `hasattr` *is* the contract: "every name in `__all__` resolves".
- **Can it fail?** Yes. Planted break: append `"_planted_missing_name"` to `__all__` in `src/specify_cli/cli/commands/charter/__init__.py`.
  - Result: the test FAILED. Verified.
- **Is there a cheaper guard?** The expected answer was ruff F822 (undefined-export). On the same break, `ruff check` printed "All checks passed!", also with `--select F822` (ruff 0.15.12). In stable mode F822 skips `__init__.py`, so this test is the only guard.
- **Nit, optional:**
  - The `__all__` here is a legacy test-patch surface (roughly 70 private names).
  - Shrinking it is product work, outside this pass.

### 2.3 `test_retrospect.py::TestMaybeAutoCommit::test_auto_commit_raises_is_nonfatal` (L1202) — KEEP

- **Contract:** a config-read failure inside `_maybe_auto_commit` (`src/specify_cli/cli/commands/retrospect.py:209`) is non-fatal.
- **Oracle:** the implicit "does not raise". That is the whole contract.
- **Planted break:** move `if not get_auto_commit_default(repo_root): return` above the `try:`.
  - Result: the test FAILED. Verified.
- **Nit, optional:**
  - Patch `subprocess.run` and assert it is not called, so the test also pins that a config failure means no commit attempt.
  - It is not a separate verdict.

### 2.4 `test_retrospect.py::TestMaybeAutoCommit::test_auto_commit_file_outside_repo_root` (L1213) — FIX

- **Weakness:**
  - The test promises that files outside repo_root still work, with a fallback to `str`.
  - It asserts nothing, and the function under test ends in `except Exception: pass`.
  - Any break in the `ValueError` fallback raises inside the `try` and is swallowed, so the test can never fail.
- **Planted break:** in `src/specify_cli/cli/commands/retrospect.py::_maybe_auto_commit`, replace the inner `try: rel_files.append(str(f.relative_to(repo_root))) / except ValueError: rel_files.append(str(f))` with the bare `rel_files.append(str(f.relative_to(repo_root)))`.
  - Result: the current test **PASSED**. Verified: the break is swallowed, so git is never called.
- **Stronger oracle:** keep the `subprocess.run` mock. It sits at a true process boundary.
  ```python
  assert mock_subprocess.call_args_list[0].args[0] == ["git", "add", "--", "/nonexistent/nonexistent_file.yaml"]
  assert mock_subprocess.call_args_list[1].args[0] == ["git", "commit", "-m", "test"]
  ```
  - On the planted break, `subprocess.run` is never called, so `call_args_list[0]` raises `IndexError` and the test goes red.
- **Caveat, and why this needs oracle design (Opus-grade):**
  - The fallback the test names is dead in practice. `git add -- <abs path outside repo>` exits with `fatal: ... is outside repository`, and the error is swallowed. See suspected bug P1.
  - The implementer should pin the argv mapping as above and note P1 in the PR.
  - If the product decides to skip or warn on outside-root files instead, the test must follow that decision. Do not pin the dead behaviour as desirable in the test name or docstring. Rename the test to what it asserts, for example `..._passes_absolute_path_through_to_git_add`.
- **Same-defect siblings in this class, tighten in the same edit:**
  - `test_auto_commit_enabled_calls_git` (L1164) checks argv with `"git" in` and `"add" in` membership. Pin the full argv lists instead: `["git","add","--","file.yaml"]` and `["git","commit","-m","test commit message"]`. That catches a lost relative-path conversion, which the current membership check does not.
  - In `test_auto_commit_failure_is_nonfatal`, `assert result is None` is tautological because the function is `-> None`. The real oracle is "does not raise". Drop the assert or leave it; this is harmless.

### 2.5 `test_retrospect.py::TestBackfillDiscovery::test_discover_missions_skips_non_dirs` (L1433) — FIX

- **Weakness:** `assert isinstance(result, list)` is true for every return value of `_discover_missions_for_backfill` (`retrospect.py:510`). The only real oracle is "does not crash".
- **Planted break:** in `src/specify_cli/cli/commands/retrospect.py::_discover_missions_for_backfill`, change `if not safe_is_dir(entry): continue` to `... break`.
  - That aborts discovery at the first non-directory, so every mission sorted after it is silently dropped.
  - Result: the current test **PASSED**. Verified.
- **Stronger oracle:** seed the file *and* one real mission dir that sorts after it.
  - Name the file `0-not-a-dir.txt`; `"0-"` sorts before `"01KS…"`.
  - Reuse the `not_completed` fixture shape from `test_discover_missions_not_completed_excluded` (L1528): `MISSION_ID_COMPLETED` / `MISSION_SLUG_COMPLETED` with no `completed_at`. Then assert:
  ```python
  assert [(c["mission_id"], c.get("skip_reason")) for c in result] == [(MISSION_ID_COMPLETED, "not_completed")]
  ```
  - On `break` the result is `[]` and the test goes red. On a mutation that emits a candidate for the file, there is an extra row and the test goes red.
- **Grade:** mechanical (Sonnet-grade). The oracle is fully specified above.

### 2.6 `test_retrospect.py::TestBackfillDiscovery::test_discover_missions_unstattable_entry_is_not_silently_skipped` (L1447) — KEEP

- **Skip audit:**
  - The skip is keyed on `tests/_support/eacces.mode_bits_enforced(canary)`, which probes a real file after `chmod 0o000`.
  - That is an environment guard: running as root, or a filesystem that ignores mode bits.
  - It is not an advisory signal, it does not depend on checkout topology, and it does not mask a defect.
- **Issue:** #3194 is the *fixed* defect this pins (`safe_is_dir`). No tracking issue is needed for an environment skip.
- **Evidence:** it SKIPPED in this container (uid 0) with the honest message.
  - The CI jobs in `.github/workflows/module-tests.yml:102` and `ci-modules.yml:88` use `runs-on: ubuntu-24.04`, a non-root `runner` user with no `container:`, so the test executes there.
- **Oracle:** `pytest.raises(OSError)` is precise enough for an adapter-layer helper.
- **Optional hardening (not required):** a root-proof variant that monkeypatches `os.stat` on the symlink path to raise `PermissionError`. It would run everywhere, but it would not exercise real mode bits, which is the stated purpose. Leave it as is.

### 2.7 `test_retrospect.py::TestSummaryCmdExtended::test_summary_unstattable_mission_candidate_is_not_silently_skipped` (L1833) — KEEP

- **Skip:** same guard and reasoning as 2.6. It SKIPPED here as root and runs on CI.
- **Oracle:** operator-facing and precise: `exit_code == 2` plus `"I/O error reading corpus"` in the ANSI-stripped output. This matches core rigour for an exit-code contract.

### 2.8 `test_zeitgeist_operability_cli.py::test_drill_outcome_color` (L137) — KEEP

- **Scanner false positive:**
  - The file contains no `skip` or `xfail` marker. The detector matched the parametrize value `"skipped: drain off"` and the docstring word "skip".
  - The test pins `_drill_outcome_color` (`src/specify_cli/cli/commands/zeitgeist.py:906`) with exact equality across all three branches.
  - Any mutation of a branch goes red, for example `startswith("skipped")` → `"red"`.
- **Scanner note:** the `skip-or-xfail` detector should match decorators and `pytest.skip` / `pytest.xfail` calls, not string literals.

### 2.9 `test_init_templates_preservation.py::test_local_full_copy_source_absent_preserves_pre_existing_operator_templates` (L249) — KEEP

- **Scanner false positive:**
  - `read_text()` reads the operator template the test seeded, which is on-disk state after a real `init` CLI run. It is not a scan of the source code.
  - The oracle checks the exit code, the file surviving in place with the exact bytes, and the `not package-owned` diagnostic (`src/specify_cli/asset_preservation/guard.py:186`).
- **Break it would catch:**
  - Setting `templates_dir_created_this_run = True` unconditionally at `src/specify_cli/cli/commands/init.py:1138` makes the cleanup guard remove the tree, so `survived_in_place` goes red.
  - This is the exact #4931 re-arm the docstring names. It was not executed because the KEEP stands on reading alone.
- **Nit, optional:**
  - `assert survived_in_place or survived_in_backup` is immediately followed by the strictly stronger `assert survived_in_place`, so the first assert is dead weight.
  - Keep only the second, and move the diagnostic message onto it.

### 2.10 / 2.11 `test_mission_agnostic_flag.py::test_observed_command_accepts_and_ignores_mission` (L55), `…::test_observed_command_accepts_equals_form` (L62) — KEEP

- **Implicit oracle:** `click.Command.make_context` raises `NoSuchOption` (a `UsageError`) when `--mission` is not a param. It also crashes on the foreign-click `_param_default_explicit` class that the opts-only tree scan in `test_every_leaf_command_accepts_mission` cannot see. So these tests add real-tree *parsing* coverage.
- **Planted break:** in `src/specify_cli/cli/helpers.py`, make `MissionAgnosticCommand.get_params` return `super().get_params(ctx)`.
  - Result: both tests FAILED. Verified.
- **Nit, optional:**
  - `_resolve()` silently stops at the deepest matching group when a name is missing.
  - If `agent profile list` were renamed, the test would still go red, but with a misleading `NoSuchOption` on the `profile` group.
  - Make `_resolve` fail loudly, for example with `assert not rest, f"unresolved: {rest}"`.

### 2.12 `test_mission_agnostic_flag.py::test_sub_app_used_as_leaf_command_accepts_mission` (L69) — KEEP

- The `isinstance(leaf, MissionAgnosticGroup)` is backed by a real `make_context` parse.
- **Planted break:** in `src/specify_cli/cli/helpers.py`, make `MissionAgnosticGroup.get_params` return `super().get_params(ctx)`.
  - Result: the test FAILED, together with the tree-wide and walker guards. Verified.

### 2.13 `test_mission_brief.py::test_clear_is_idempotent` (L155) — KEEP

- **Oracle:** "does not raise" is the whole idempotency contract of `clear_mission_brief` (`src/specify_cli/mission_brief.py:273`).
- **Planted break:** at `src/specify_cli/mission_brief.py:277`, change `unlink(missing_ok=True)` to `missing_ok=False`.
  - Result: FAILED with `FileNotFoundError`. Verified.
- **Placement nit:**
  - `tests/cli/test_mission_brief.py` tests the domain module `specify_cli.mission_brief`, not a CLI command, and its docstring says "Unit tests".
  - It belongs beside `tests/.../test_mission_brief_missing_vs_corrupt.py`.
  - Relocation is out of scope for this pass; note it for the tests/cli layout owner.

### Same-pattern siblings noted (outside the flagged set, not verdicted)

- **`test_retrospect.py` has several imprecise `>= N` count oracles** where the fixture seeds an exact number:
  - L1593, 1597, 1627: `created >= 1`
  - L1653, 1680, 2195: `len(failed) >= 1`
  - L1831: `len(missions) >= 2`, with exactly 2 seeded
  - L1997, 2026, 2246, 2292: `len(matching) >= 1`

  These are candidates for `==` plus identity (mission ids and slugs). They are the same imprecise-oracle class, so they belong to Group 2 if picked up. They need a per-test read to confirm the fixture cardinality.

## 3. Suspected product bugs

### P1 — `retrospect` auto-commit fails silently, and the outside-root fallback can never succeed (confirmed)

`src/specify_cli/cli/commands/retrospect.py::_maybe_auto_commit` (L209–240) wraps the whole stage-and-commit in `except Exception: pass`, and prints nothing. Consequences:

1. **The outside-root fallback is dead code.** `str(f)` is passed to `git add -- <abs path>`, and git refuses paths outside the work tree. Repro (scratch git repo, `get_auto_commit_default` patched to `True`):
   ```
   _maybe_auto_commit(repo, [<scratch>/outside.yaml], "msg")  -> returns None, no exception
   git log --oneline                                          -> only "init" (nothing committed)
   git add -- <scratch>/outside.yaml  -> fatal: '<...>/outside.yaml' is outside repository at '<...>/r'
   ```
2. **Every other failure is silent too**: a hook rejection, nothing to commit, or a pathspec error. `retrospect create` / `backfill` report success while the record stays uncommitted.
   - This conflicts with the CLAUDE.md Sonar rule: "Do not leave empty or effect-free exception handlers."
   - `S110` is ignored in ruff config only as "redundant with SIM105", not as an allowance.
3. **Suspected, not verified.** `create` and `backfill` stage `record_path` together with `_canonical_events_path(...)` (L426, L842) in **one** `git add`.
   - For coord topologies, `resolve_status_surface` points at the coordination surface, which may be inside a linked worktree (`.worktrees/…`) that the primary checkout cannot stage.
   - If so, the single `git add` fails, and the retrospective record is not committed either, silently.
   - Repro to run: create a `lanes_with_coord` mission and complete it, set `auto_commit: true`, run `spec-kitty retrospect create --mission <slug>`, then check `git status` for the uncommitted `retrospective.yaml`.

Recommendation: file a bug. The minimal fix is to surface a warning with git's stderr on failure. Beyond that, the product must decide what to do with outside-root paths (skip and warn, or commit on the owning checkout). Test 2.4 must follow that decision.

### Not a product bug (recorded so nobody chases it)

Ruff F822 does not guard `__all__` in package `__init__.py` files (stable mode). The charter `__all__` test is the only guard for that package. See 2.2.

## 4. Implementation grouping (disjoint files)

| Group | Grade | Test files | Src files | Work |
|---|---|---|---|---|
| **G1 — logout retire** | Mechanical (Sonnet) | `tests/cli/commands/test_auth_logout.py` | none | Delete `test_logout_impl_is_importable` and its banner. Run the file: 9 pass. |
| **G2 — retrospect oracles** | Oracle design (Opus) | `tests/cli/commands/test_retrospect.py` | none. Read-only reference: `src/specify_cli/cli/commands/retrospect.py`. The product fix for P1 is a separate issue/PR, not in this group. | FIX 2.4 (argv oracle, rename, reference P1) and FIX 2.5 (file plus a sorting-later mission, exact candidate list). Tighten `test_auto_commit_enabled_calls_git` to full argv. Optionally sweep the `>= N` siblings in §2 after checking fixture cardinality. Show each planted break from §2 going red in the PR body. |
| **G3 — nits (optional)** | Mechanical (Sonnet) | `tests/cli/test_init_templates_preservation.py`, `tests/cli/test_mission_agnostic_flag.py` | none | Drop the redundant disjunctive assert (2.9). Make `_resolve` fail loudly on an unresolved path (2.10). |
| **No change** | — | `tests/cli/commands/test_charter_package_exports.py`, `tests/cli/commands/test_zeitgeist_operability_cli.py`, `tests/cli/test_mission_brief.py` | — | KEEP as is. The mission-brief relocation is noted for the layout owner only. |
| **Follow-up issue (not a test group)** | — | — | `src/specify_cli/cli/commands/retrospect.py` | P1: silent auto-commit failure. Its fix PR must own `test_retrospect.py::TestMaybeAutoCommit`, so schedule it after G2 lands, to avoid overlapping on that file. |
| **Scanner follow-up (optional)** | Mechanical | — | `packs/internal/assets/test-quality-scan.py` | Stop `skip-or-xfail` from matching string literals (2.8). Stop `literal-source-scan` from firing on reads of test-seeded fixture files (2.9). |

---
# Bundle B verdicts: does the harness test the CLI, or its own mocks?

Reviewer: reviewer-renata (profile loaded). Slice: #5353 slice 3, `tests/cli`, 79 flagged tests in 21 files.
Rubric: `test-desiderata-and-boundaries` (anti-patterns *over-mocking*, *stubbing a new gate out of an old harness*, *self-constructed oracle*), DIRECTIVE_041, `development-assist-test-cleanup`, `test-suite-quality-assessment`.

**Planted-break method.** Breaks were planted only in the private worktree
`scratchpad/review-B` (detached at `c34481d76`) and reverted after each run with `git checkout -- src/`. `git status --porcelain src/` came back empty every time. The shared checkout's `src/` was never touched. "VERIFIED" below means the break was planted and the named test files were run. "READ" means the verdict comes from reading the code only.

**Verdict counts:** KEEP 27 · FIX 15 · RETIRE 16 · DEFER 21 (total 79). No SPLIT-BY-KIND verdicts.

---

## 1. Summary table

Abbreviations: TB = true-boundary patch, CP = patch of the CLI's own collaborator, OM = over-mocking, IA = interaction-assert, PA = private-attr.

| File | Test | Flags | True-boundary patches | Collaborator patches | Verdict | Reason (one line) |
|---|---|---|---|---|---|---|
| test_auth_endpoint_unconfigured.py | test_login_exits_nonzero_with_guidance_and_no_http_call | IA | SecureStorage.from_environment (keyring), `_run_browser_flow` (network wrapper) | – | KEEP | Only boundaries are patched. It asserts exit≠0 and the guidance text; `assert_not_called` is the "no HTTP" contract. |
| test_auth_login.py | test_default_dispatches_to_browser_flow | OM | – | get_token_manager, `_run_browser_flow`, `_run_device_flow` | RETIRE | `tests/auth/integration/test_browser_login_e2e.py::test_full_browser_login_happy_path` covers it with the HTTP boundary only. VERIFIED. |
| test_auth_login.py | test_headless_dispatches_to_device_flow | OM | – | same | RETIRE | `test_headless_login_e2e.py::test_full_device_flow_happy_path` covers it. VERIFIED. |
| test_auth_login.py | test_missing_env_uses_configured_sync_server_url | IA | – | get_token_manager, `_run_browser_flow` | FIX | It asserts the URL handed to the CLI's own wrapper, not the URL the network flow is built with. A break in the wrapper stays green. VERIFIED. |
| test_auth_login.py | test_force_reauthenticates_even_when_logged_in | IA | – | get_token_manager (MagicMock TM), `_run_browser_flow` | RETIRE | `test_browser_login_e2e.py::test_login_force_resets_session` asserts the delete plus the new write. VERIFIED. |
| test_auth_login.py | test_warns_on_retired_first_party_target_without_rejecting | IA | – | same | FIX | Same URL-at-wrapper weakness as above (the "proceeds against the configured target" half). VERIFIED. |
| test_auth_login.py | test_force_mints_fresh_credentials_on_mismatch | IA | – | same | FIX | Core rigour (issuer boundary). Nothing checks that fresh credentials are persisted for the resolved target. VERIFIED. |
| test_auth_logout.py | test_not_logged_in | IA | SecureStorage | – | KEEP | Boundary only. Asserts exit 0, stdout, and no delete. |
| test_auth_logout.py | test_logout_success_revoked | IA | SecureStorage, RevokeFlow.revoke (network) | – | KEEP | Boundary only. Asserts stdout, delete, and no token leak. |
| test_auth_logout.py | test_logout_server_failure_still_clears_local | IA | same | – | KEEP | FR-004 contract, observable. |
| test_auth_logout.py | test_logout_network_error_still_clears_local | IA | same | – | KEEP | Same. |
| test_auth_logout.py | test_logout_no_refresh_token_still_clears_local | IA | same | – | KEEP | Same. |
| test_auth_logout.py | test_logout_local_cleanup_failure_exits_1 | OM | SecureStorage, revoke | get_token_manager (MagicMock) | RETIRE | Duplicates `test_logout_storage_delete_failure_propagates` (same file), which runs the real TokenManager. VERIFIED. |
| test_auth_logout.py | test_logout_force_skips_server | IA | same | – | KEEP | "No revoke under `--force`" is the contract. |
| test_auth_logout.py | test_logout_missing_saas_url_still_attempts_revoke_and_cleans_up_locally | IA | same | – | KEEP | The revoke attempt is the contract; asserted at the network boundary. |
| test_charter_bundle_coverage.py | test_validate_exits_zero_when_all_checks_pass | OM, PA | – | 7: repo-root resolver, `_classify_paths`, `_classify_gitignore`, `_enumerate_out_of_scope_files`, `_collect_provenance_validation_errors`, `validate_synthesis_state`, `_bundle_compatibility_error` | RETIRE | Every check is stubbed out (stubbed gate). `tests/charter/test_bundle_validate_cli.py` covers it for real. VERIFIED. |
| test_charter_bundle_coverage.py | test_validate_json_output_contains_result_key | OM, PA | – | same 7 | RETIRE | `test_bundle_validate_cli.py::test_validate_json_shape_matches_contract` covers the shape. VERIFIED (see 2.3). |
| test_charter_json_error_contract.py | test_resynthesize_json_unresolved_topic_error_is_parseable | OM | `_collect_evidence_result` (evidence/corpus fetch) | find_repo_root, `_build_synthesis_request`, pipeline.run (fault injection) | KEEP | Asserts the operator-facing `--json` error envelope and exit 2; the patches only steer into the error branch. |
| test_charter_json_error_contract.py | test_resynthesize_json_keeps_evidence_warnings_inside_payload | OM, PA | same | `_list_resynthesis_topics` | KEEP | A break at the `if not json_output` guard turns it red. VERIFIED. |
| test_charter_json_error_contract.py | test_interview_json_keeps_org_prefill_messages_inside_payload | OM | – | 9 patches (interview internals) | KEEP | A break at the `if not json_output` guard turns it red (VERIFIED). It carries extra patches; trim opportunistically. |
| test_charter_orchestration.py | test_interview_defaults_exits_zero_and_writes_answers | OM | – | 7, including `write_interview_answers` | RETIRE | Named "writes answers" but mocks the write and never checks it. `tests/agent/cli/commands/test_charter_cli.py::test_interview_defaults_writes_answers` covers it. VERIFIED. |
| test_charter_orchestration.py | test_interview_defaults_json_output | OM | – | 7 | RETIRE | Same guard. VERIFIED. |
| test_charter_orchestration.py | test_status_exits_zero_with_human_output | OM | – | `_collect_charter_sync_status`, `_collect_synthesis_status` | RETIRE | Asserts only that "Charter" (the title) appears. `test_charter_cli.py::test_status_command_synced` covers it. VERIFIED. |
| test_charter_orchestration.py | test_context_exits_zero_for_known_action | OM | – | build_charter_context, BOOTSTRAP_ACTIONS | RETIRE | Weak disjunctive assert. Guard: `tests/charter/test_context_org_chain.py::TestContextCliTwoPackChain::test_pack_two_directive_present_in_cli_text_output`. VERIFIED. |
| test_charter_orchestration.py | test_context_json_output_has_success_key | OM | – | same | RETIRE | `test_charter_cli.py::test_context_bootstrap_then_compact` covers it. VERIFIED. |
| test_charter_rendering.py | test_context_renders_action_name_in_output | OM | – | same | RETIRE | Weak disjunctive assert. Same guard as the human-mode context test above. VERIFIED. |
| test_charter_rendering.py | test_context_json_uses_same_depth_as_rendered_context | OM | resolve_org_roots, org-charter loader (org packs on disk) | build_charter_context{,_json} | KEEP | Pins a consistency contract between two builders; `depth=result.depth`→`None` turns it red. READ. |
| test_charter_rendering.py | test_context_include_renders_selector_without_action | IA | resolve_org_roots | build_charter_context_include | KEEP | Asserts output. The interaction assert pins the selector-parse contract (`action=None`). Real include behaviour lives in `tests/charter/test_context_include.py`. |
| test_charter_rendering.py | test_activation_stanza_include_command_is_registered_cli_surface | IA | resolve_org_roots | include builder | KEEP | #1464 regression: a real stanza is parsed by the real Typer surface. |
| test_doctor_mission_state.py | test_fix_names_audit_trail_and_quarantine_with_json_parity | OM | – | repair_repo → MagicMock report with a hand-authored `to_json` | FIX | The JSON-parity half is a self-constructed oracle: it echoes the test's own `to_json` payload. VERIFIED. |
| test_implement_base_flag.py | test_implement_base_flag_creates_workspace_from_ref | OM, PA | `_saas_fan_out` | 10, including 3 gates (`_ensure_planning_artifacts_committed_git`, `run_preflight_or_abort`, `require_main_repo`) | RETIRE | Oracle is vacuous: with only `main`, any lane descends from `main`. Guard: `tests/specify_cli/lanes/test_lane_base_honoring.py::TestAC1SeamLevelRedFirst`. VERIFIED. |
| test_implement_base_flag.py | test_implement_base_flag_invalid_ref_fails_clearly | OM, fake-short-ulid | – | 9, including `require_lanes_json` | FIX | Asserts exit 1 only. It stays green when base validation silently falls through. VERIFIED. |
| test_merge_status_commit.py | test_mark_wp_merged_done_uses_lightweight_emit_path | IA | – | read state, `_has_transition_to`, emit | RETIRE | Pins `ensure_sync_daemon=False`, a dead sync-residue kwarg. Done-emission is covered by the real-merge class in the same file. VERIFIED. |
| test_merge_status_commit.py | test_done_events_committed_to_git | OM, PA, long | `_saas_fan_out` | 17, including reconciliation claim+phase, merge gates, policy | DEFER | Stubbed-gate harness for LANES/legacy topology. No real LANES guard yet (target shape in section 4). |
| test_merge_status_commit.py | test_modern_coord_done_events_land_on_target_history | OM, PA, long | `_saas_fan_out` | 17 | RETIRE | Superseded by `TestRealMergeCommitsBookkeeping` (same file, real `consolidate`). VERIFIED. |
| test_merge_strategy.py | test_strategy_squash_passed_to_integrate_mission_into_target | IA | – | 22 (`_patched_lane_based_merge_dependencies`), including 5 gates | FIX | Core rigour. It calls the private executor and bypasses the CLI; the CLI→executor strategy threading is unguarded. VERIFIED. |
| test_merge_strategy.py | test_default_strategy_is_squash | IA | – | same | FIX | It tests the function's default argument, not the CLI precedence default. VERIFIED. |
| test_merge_strategy.py | test_lane_to_mission_does_not_receive_strategy | IA | – | same | FIX | Proves only a missing kwarg on a mock, not that lane→mission produces a merge commit. |
| test_retrospect.py | test_create_success_json | OM, PA | – | 8 (`_resolve_handle`, `_check_mission_completed` gate, resolve_policy, generator, emit, auto-commit…) | DEFER | Whole-file harness rewrite (section 4). |
| test_retrospect.py | test_create_record_exists_error_json | OM | – | 6, writer faked to raise | DEFER | The on-disk file is already seeded; the real writer would raise. Harness rewrite. |
| test_retrospect.py | test_create_overwrite_flag | OM, PA | – | 8 | DEFER | Mode captured via a spy; should assert the on-disk record instead. |
| test_retrospect.py | test_create_update_flag | OM, PA | – | 8 | DEFER | Same. |
| test_retrospect.py | test_create_success_rich_output | OM, PA | – | 8 | DEFER | Weak disjunctive assert. |
| test_retrospect.py | test_fabricate_empty_creates_record_when_missing | OM, long | – | 5 | DEFER | `exit_code != 1 or …` is near-vacuous. |
| test_retrospect.py | TestMaybeAutoCommit::test_auto_commit_disabled | IA | subprocess.run (global) | get_auto_commit_default | FIX | git in a tmp repo is cheap; assert that no commit was made. |
| test_retrospect.py | TestMaybeAutoCommit::test_auto_commit_enabled_calls_git | IA | subprocess.run (global) | get_auto_commit_default | FIX | Asserts only that "git"/"commit" appear in argv. A `--dry-run` commit stays green. VERIFIED. |
| test_retrospect.py | test_create_policy_resolution_error_json | OM | – | 4, policy fault-injected | DEFER | The fault injection is legitimate; the resolver/completion stubs are not. |
| test_retrospect.py | test_create_policy_resolution_error_non_json | OM | – | 4 | DEFER | Same. |
| test_retrospect.py | test_create_generator_file_not_found | OM | – | 5 | DEFER | Same. |
| test_retrospect.py | test_create_generator_generic_exception | OM | – | 5 | DEFER | Same. |
| test_retrospect.py | test_create_write_gen_record_generic_exception | OM | – | 6 | DEFER | Same. |
| test_retrospect.py | test_create_record_exists_non_json | OM | – | 6 | DEFER | Same as record_exists_json. |
| test_retrospect.py | test_backfill_process_candidate_real_run_success | OM | – | 6, writer returns an unwritten path | DEFER | Named "writes record"; the record is never written or checked. |
| test_retrospect.py | test_backfill_process_candidate_file_not_found | OM | – | 3 | DEFER | Fault injection; fold into the harness. |
| test_retrospect.py | test_backfill_process_candidate_generic_exception | OM | – | 3 | DEFER | Same. |
| test_retrospect.py | test_backfill_emit_failures_flag | OM, IA | – | 4, including the emit_capture_failed spy | DEFER | Should assert a RetrospectiveCaptureFailed row in the event log. |
| test_retrospect.py | test_backfill_no_json_rich_output | OM | – | 6 | DEFER | `len(output) > 0` is vacuous. |
| test_retrospect.py | test_backfill_no_json_with_failures_shows_failure_list | OM | – | 3 | DEFER | Disjunctive assert. |
| test_retrospect.py | test_backfill_process_candidate_record_exists_error | OM | – | 4 | DEFER | The real writer would raise. |
| test_retrospect.py | test_backfill_generic_exception_with_emit_failures | OM, IA | – | 4 | DEFER | Same as emit_failures_flag. |
| test_retrospect_update_persisted.py | test_emit_captured_spy_matches_persisted_record_on_disk | IA | – | 7, emit_captured spied | FIX | "report ≡ event ≡ disk" is checked against a spy, never against the event on disk. VERIFIED. |
| test_routes_command.py | test_cache_miss_under_drain_off_prints_guidance_without_building_a_gateway | IA | `_gateway_for` (SaaS gateway), resolve_credentials (keyring) | – | KEEP | "No network under drain-off" is the contract; stdout asserted. |
| test_routes_command.py | test_json_stays_parseable_under_drain_off | IA | `_gateway_for` | – | KEEP | Exact JSON payload asserted. |
| test_agent_retrospect_missing_record.py | test_existing_record_json_includes_synthesized_outcome | OM | – | resolver, read_record, apply_proposals | KEEP | Envelope contract (`status`/`outcome`). Low risk; fold into the D1 harness when it lands. |
| test_agent_retrospect_synthesize.py | test_generator_record_dryrun_exit0 | IA | – | resolver, apply_proposals | KEEP | A real on-disk record is read; the apply seam is a separate domain. |
| test_agent_retrospect_synthesize.py | test_generator_record_apply_exit0 | IA | – | same | KEEP | Same. |
| test_agent_retrospect_synthesize.py | test_proposal_id_filter_passed_to_apply_proposals | OM, IA | – | read_record (MagicMock, `proposals=[]`), apply_proposals | FIX | Every proposal set is empty, so the accepted-only filter is never exercised. VERIFIED. |
| test_agent_retrospect_synthesize.py | test_dry_run_is_true_by_default_in_apply_call | OM, IA | – | same | FIX | "Without `--apply` nothing mutates" is never checked on disk. |
| test_agent_retrospect_synthesize.py | test_apply_flag_sets_dry_run_false | OM, IA | – | same | FIX | Same. |
| test_agent_retrospect_synthesize.py | test_actor_id_forwarded | OM, IA | – | same | KEEP | The flag→actor mapping is the contract, and it has no cheaper observable. Low risk. |
| test_auth_logout_mismatch.py | test_logout_targets_config_only_issuer_host | IA | SecureStorage, `httpx.AsyncClient` | – | KEEP | Exemplary: HTTP boundary only; asserts the POST URL, stdout, and delete. |
| test_auth_logout_mismatch.py | test_logout_refuses_attacker_env_override_but_still_tears_down_locally | IA | same | – | KEEP | Exemplary. |
| test_doctrine_org_commands.py | test_doctrine_org_validate_calls_validate_pack_with_check_drg_root_true | IA | – | validate_pack | RETIRE | `test_doctrine_org_validate_catches_drg_only_fragment_after_init` (same file) is the behavioural twin. VERIFIED. |
| test_events_tail.py | test_no_write_syscall_reachable_on_any_code_path | OM | – | resolve_mission_handle; Path.open spy | FIX | The spy watches only `Path.open`: a builtin `open(..., "a")` write is invisible, and so are `"at"`/`"wt"` modes. VERIFIED. |
| test_implement_bulk_edit_planning.py | test_occurrence_map_planning_wp_does_not_require_acknowledgement | IA | – | 6, including create_lane_workspace and 2 unrelated gates | KEEP | Isolates the bulk-edit gate; asserts output plus "blocked before side effect". |
| test_implement_bulk_edit_planning.py | test_active_rewrite_wp_still_requires_acknowledgement | IA | – | same | KEEP | Asserts exit 1, the remedy flag in output, and that no workspace was created. |
| test_implement_bulk_edit_planning.py | test_non_utf8_spec_without_bulk_edit_signal_does_not_block_implement | IA | – | same | KEEP | Same. |
| test_tasks_finalize_lanes_minting.py | test_finalize_tasks_never_seeds_events_without_lanes | OM (false positive) | – | locate_project_root, `_find_mission_slug`, target-branch check | KEEP | Asserts on-disk `lanes.json` and the event log (real state). |
| test_tasks_finalize_lanes_minting.py | test_finalize_tasks_is_idempotent_once_lanes_exist | OM (false positive) | – | same | KEEP | Byte-identical `lanes.json` across runs. |

No flagged Bundle B test relies on `tests/cli/__snapshots__`.

---

## 2. Per-test and per-cluster detail

### 2.1 Auth login: `tests/cli/commands/test_auth_login.py`

**The seam is in the wrong place.** Most tests patch `_auth_login._run_browser_flow`/`_run_device_flow`. These are the CLI's own wrappers. They hold the error handling, `tm.set_session(session)`, and the `saas_base_url` handed to the network flow. The true boundary is one level down. `AuthorizationCodeFlow`/`DeviceCodeFlow` (or `PublicHttpClient`/`httpx.AsyncClient`) is the network edge, and `SecureStorage.from_environment` is the keyring edge. The file's own `TestAuthLoginSaasLineRendering` and escaping tests already use the flow-class seam. `tests/auth/integration/` has the full HTTP-boundary harness (`FakeSecureStorage`).

**Isolation.** The autouse fixture sets `SPEC_KITTY_SAAS_URL` but not `SPEC_KITTY_HOME`. `test_login_proceeds_even_if_teamspace_mission_state_is_blocked` does not patch `get_token_manager` or `SecureStorage`, so it reads the per-worker HOME auth state. Its exit code depends on whether an earlier test left a session there. `TokenManager` also publishes a session hot-path summary under the runtime root. Fix: use the `canonical_home` fixture (`tests/conftest.py`) in the autouse fixture.

- **RETIRE `test_default_dispatches_to_browser_flow`** → guard `tests/auth/integration/test_browser_login_e2e.py::TestBrowserLoginE2E::test_full_browser_login_happy_path`. It asserts `auth_method == "authorization_code"` and that the browser launched. Break (VERIFIED guard red): `src/specify_cli/cli/commands/_auth_login.py:160` `elif headless:` → `elif True:`.
- **RETIRE `test_headless_dispatches_to_device_flow`** → guard `tests/auth/integration/test_headless_login_e2e.py::TestHeadlessLoginE2E::test_full_device_flow_happy_path`. It asserts `BrowserLauncher.launch` is not called and `auth_method == "device_code"`. Break (VERIFIED red): line 160 `elif headless:` → `elif False:`. The guard took **301 s** to go red, because the real loopback server waited out its 5-minute timeout. See section 3, finding P8.
- **RETIRE `test_force_reauthenticates_even_when_logged_in`** → guard `test_browser_login_e2e.py::TestBrowserLoginE2E::test_login_force_resets_session` (`deletes >= 1`, exactly one new write). Break (VERIFIED red): line 156 `tm.clear_session()` → `pass`.
- **FIX `test_missing_env_uses_configured_sync_server_url`** and **FIX `test_warns_on_retired_first_party_target_without_rejecting`** (same shape).
  - Weakness: `mock_browser.call_args.args[1] == url` checks what `login_impl` passed to its own wrapper. It does not check what reaches the network flow.
  - Stronger oracle: patch `specify_cli.auth.flows.authorization_code.AuthorizationCodeFlow` (returning a `_make_session()`) plus `SecureStorage.from_environment` → `FakeSecureStorage`. Assert `mock_flow_cls.call_args.kwargs["saas_base_url"] == "https://configured.example"` (or `https://app.spec-kitty.ai`), keep the stdout warning asserts, and assert `fake_storage.writes[0].issuer_url` equals the configured URL.
  - Planted break (VERIFIED current green): `_auth_login.py:210` (in `_run_browser_flow`) `saas_base_url=saas_url,` → `saas_base_url=DEFAULT_HOSTED_SAAS_URL,`. The fixed test goes red on the constructor kwarg.
- **FIX `test_force_mints_fresh_credentials_on_mismatch`** (core rigour: issuer boundary).
  - Weakness: a MagicMock TokenManager plus the mocked wrapper. `clear_session.assert_called_once()` is the only evidence, and nothing proves that fresh credentials for the resolved target were persisted.
  - Stronger oracle: seed `FakeSecureStorage(initial=_make_session(issuer_url="https://app.spec-kitty.ai"))` and patch `PublicHttpClient` as in `test_browser_login_e2e.py`. Run `login --force` and assert:
    - exit 0;
    - `fake_storage.deletes >= 1`;
    - `len(fake_storage.writes) == 1`;
    - `writes[0].issuer_url == "https://saas.test"`;
    - the old token is not in stdout.
  - Planted break (VERIFIED current green, e2e harness red): `_auth_login.py:239` `tm.set_session(session)` → `pass`. The line-210 URL break also stays green in the current test.

### 2.2 Auth logout: `tests/cli/commands/test_auth_logout.py`

Seven KEEP. They patch only `SecureStorage.from_environment` (keyring) and `RevokeFlow.revoke` (the network edge). They assert exit code, stdout and `storage.delete`, where the storage mock is the boundary. Isolation: no `SPEC_KITTY_HOME` pin. It is harmless while storage is patched, but add `canonical_home` for hygiene.

- **RETIRE `test_logout_local_cleanup_failure_exits_1`**. It replaces the TokenManager with a MagicMock. The same contract (clear fails → exit 1, no "Logged out") is driven through the real `TokenManager.clear_session` by `test_logout_storage_delete_failure_propagates`, which is in the same file and not flagged. Break (VERIFIED guard red): `_auth_logout.py` `raise typer.Exit(code=1)` → `return`.

`tests/cli/test_auth_logout_mismatch.py`: both KEEP. This is the model harness for Bundle B: `httpx.AsyncClient` plus storage only, and it asserts the POST URL, the refusal text, and the local teardown.

### 2.3 Charter bundle, orchestration, rendering (retire cluster)

These files are "Bucket A/C coverage" tests. They stub the collaborators that do the work and then assert a title substring or `exit_code == 0`. Real-repo guards exist for every contract.

- **RETIRE both `TestValidateCLI` tests** (`test_charter_bundle_coverage.py`). This is the textbook stubbed-gate pattern: all seven checks are patched to "pass". Guards are in `tests/charter/test_bundle_validate_cli.py`: `test_validate_fails_on_missing_tracked_file`, `test_validate_passes_on_compliant_bundle`, `test_validate_json_shape_matches_contract`. Break (VERIFIED): `src/specify_cli/cli/commands/charter_bundle.py:388` `not tracked_missing` → `True`. The flagged tests stay green (3 passed); the guard goes red. Keep the non-flagged `test_validate_exits_nonzero_when_resolver_raises_not_inside_repo`.
- **RETIRE `test_interview_defaults_exits_zero_and_writes_answers`** and **`test_interview_defaults_json_output`**. Guard: `tests/agent/cli/commands/test_charter_cli.py::test_interview_defaults_writes_answers` (real run; asserts the file exists at `payload["interview_path"]`). Break (VERIFIED): `charter/interview.py:414` `write_interview_answers(...)` → `pass`. Both flagged tests stay green; the guard goes red.
- **RETIRE `test_status_exits_zero_with_human_output`**. Guard: `test_charter_cli.py::test_status_command_synced`. Break (VERIFIED): `charter/_status_collectors.py:152` `"stale" if stale else "synced"` → `"stale"`. The flagged test stays green; the guard goes red.
- **RETIRE `test_context_json_output_has_success_key`**. Guard: `test_charter_cli.py::test_context_bootstrap_then_compact`. Break (VERIFIED): `charter/context.py:168` `"mode": result.mode` → `"mode": "compact"`. The flagged test stays green; the guard goes red.
- **RETIRE `test_context_exits_zero_for_known_action`** and **`test_context_renders_action_name_in_output`** (`test_charter_rendering.py`).
  - Guard: `tests/charter/test_context_org_chain.py::TestContextCliTwoPackChain::test_pack_two_directive_present_in_cli_text_output`, a real human-mode run.
  - Break (VERIFIED guard red): `context.py:210` `console.print(result.text, markup=False)` → `pass`.
  - A break both flagged tests miss (READ): `context.py` `if result.mode == "bootstrap":` → `if False:`. The mocks use mode `full`/`incremental`, so they never reach that branch.
- **KEEP `test_charter_json_error_contract.py` (3)**. The asserted contract is the operator-facing `--json` envelope; the patches only steer execution into branches. VERIFIED red on:
  - `charter/resynthesize.py:118` `if not json_output:` → `if True:`;
  - `charter/interview.py:208` `if not json_output:` → `if True:`.

  Campsite note: the interview test's six patches of `charter.activation.interview.*` (QUESTION_ORDER etc.) are unnecessary under `--defaults`. Trim them when the file is next touched.
- **KEEP the three rendering tests.**
  - `test_context_json_uses_same_depth_as_rendered_context` pins depth consistency between the two builders. Its inner asserts go red on `depth=result.depth` → `depth=None` (READ).
  - The two `--include` tests assert output. Their interaction asserts pin the selector-parse contract (`action=None`) and the #1464 stanza→CLI round-trip.

### 2.4 Doctor: `test_doctor_mission_state.py::TestFixModeCharacterization::test_fix_names_audit_trail_and_quarantine_with_json_parity`: FIX

- Weakness: `repair_repo` returns a MagicMock whose `to_json.return_value` is authored by the test. The `--json` half of "parity" therefore compares the CLI's output with the test's own string (self-constructed oracle). Only the pretty half exercises CLI logic.
- Stronger oracle: build a real `specify_cli.migration.mission_state.RepairReport` with a real per-mission result (`quarantined_rows=2`, `manifest_path`, `quarantine_root_path`), and patch `repair_repo` to return it. Repair itself is fault-free domain logic; running it for real on a tmp repo with a quarantinable row is better if cheap. Keep the pretty and JSON asserts.
- Planted break (VERIFIED current green): `src/specify_cli/migration/mission_state.py:402` `"quarantine_root_path": self.quarantine_root_path,` → `"quarantine_root_path": None,`. The fixed test goes red on `emitted["quarantine_root_path"]`, because `_mission_state_doctor.py:215` writes `report.to_json()`.

### 2.5 Implement `--base`: `tests/cli/commands/test_implement_base_flag.py`

- **RETIRE `test_implement_base_flag_creates_workspace_from_ref`**.
  - Its oracle is vacuous: the repo has only `main`, `--base main` equals the target, and every lane descends from `main` anyway.
  - Break (VERIFIED): `src/specify_cli/cli/commands/implement.py:2171` `base=effective_base,` → `base=None,`. The flagged file stays green (5 passed).
  - The guard `tests/specify_cli/lanes/test_lane_base_honoring.py::TestAC1SeamLevelRedFirst::test_explicit_base_replaces_coord_parent_on_no_dep_lane` (divergent base) goes red.
- **FIX `test_implement_base_flag_invalid_ref_fails_clearly`** (core rigour: "no fallback").
  - Weakness: it asserts only `exit_code == 1`, and the run exits 1 for some other reason even when base validation is skipped.
  - Stronger oracle:
    - capture console output and assert `Base ref 'totally-bogus-ref-xyz' does not resolve`;
    - assert no `kitty/mission-068-test-lane-a` branch and no `.worktrees/...-lane-a` directory exist afterwards;
    - use a real 26-char ULID `mission_id` in `_setup_feature` and the manifest (currently `"068-test"`, which the scanner flags as fake-short-ulid);
    - drop the `require_lanes_json` patch, because `_setup_feature` already writes `lanes.json`.
  - Planted break (VERIFIED current green): `implement.py:1623` `_raise_base_ref_unresolved(base)` → `return None, lanes_manifest`.
  - Hygiene in the same file:
    - the autouse `_bypass_charter_preflight` fixture builds a result and patches nothing (dead code);
    - `patch("specify_cli.core.context_validation.require_main_repo", lambda f: f)` is a no-op, because the decorator was applied at import.

### 2.6 Merge status commit: `tests/cli/commands/test_merge_status_commit.py`

The file already contains the fix pattern. `TestRealMergeCommitsBookkeeping` (module-scoped real `spec-kitty consolidate` on `build_coord_mission`) explicitly "replaces the three ~25-patch mock harnesses that stubbed those gates".

- **RETIRE `test_modern_coord_done_events_land_on_target_history`**. It stubs `_capture_reconciliation_claim`, `_phase_reconcile_before_teardown`, merge gates and policy (stubbed-gate pattern, #5001). Guard: `TestRealMergeCommitsBookkeeping::test_status_pair_with_done_event_is_committed_on_target`. Break (VERIFIED guard red, 40 s): insert `return` at the top of `src/specify_cli/consolidation/done_bookkeeping.py::_mark_wp_merged_done`.
- **RETIRE `test_mark_wp_merged_done_uses_lightweight_emit_path`**. Its only assertion is `kwargs["ensure_sync_daemon"] is False`. That kwarg is sync residue: it flows through `status/emit.py:1565` and `coordination/outbound.py:119` as `ensure_daemon=` into `fire_saas_fanout(**kwargs)`, and nothing consumes it (grep over `src/`). The live behaviour (a done event is emitted for an approved WP) is covered by the same guard and the same break as above (VERIFIED).
- **DEFER `test_done_events_committed_to_git`** (LANES/legacy topology, `mission_id=None`). No real LANES-topology guard for "done events committed on target" was found. Target shape: D2 in section 4.

### 2.7 Merge strategy: `tests/cli/commands/test_merge_strategy.py` (three flagged): FIX as one replacement

- Weakness:
  - 22 patches through `_patched_lane_based_merge_dependencies`, including five gates: `_enforce_target_branch_sync_preflight`, `_check_mission_branch`, `_pre_mutation_safety_preflight`, and the reconciliation claim and phase.
  - The tests call the private `_run_lane_based_consolidation` directly, bypassing the CLI.
  - They assert kwargs on a mocked `integrate_mission_into_target`.
  - The CLI precedence (`--strategy` > config > SQUASH, `consolidate.py:937`) and the threading (`_run_real_merge`, `consolidate.py:691`) are unguarded.
- Planted break (VERIFIED): `src/specify_cli/cli/commands/consolidate.py:691` `strategy=resolved_strategy,` → `strategy=MergeStrategy.MERGE,`. `test_merge_strategy.py` stays green (28 passed) and so does `tests/specify_cli/cli/commands/test_merge_cli_golden.py` (11 passed).
- Stronger oracle: one parametrized real test on `tests.terminus.conftest.build_coord_mission` + `run_terminus`, marked `slow` like `TestRealMergeCommitsBookkeeping`.
  - `consolidate --mission <slug> --yes` (default) and `--strategy squash`: assert the integration commit on the target has **one** parent, and that no lane tip is an ancestor of the target.
  - `--strategy merge`: assert **two** parents, and that lane tips are ancestors.
  - FR-007: with `--keep-branch`, assert every lane tip is an ancestor of the mission branch, i.e. lane→mission is a true merge regardless of strategy.
  - Confirm the exact parent-count shapes red-first on the current tree before relying on them.
- Then delete `_patched_lane_based_merge_dependencies` and `_make_mock_lanes_manifest` if no longer used. The non-flagged config and push-hint tests stay.

### 2.8 Retrospect: `tests/cli/commands/test_retrospect.py` (22) + `test_retrospect_update_persisted.py` (1)

- Harness diagnosis:
  - The fixtures already write a real `kitty-specs/<slug>/meta.json` and a done-state `status.events.jsonl`.
  - Every `create` test still patches `_resolve_handle`, `_check_mission_completed` (the completion gate), `resolve_policy`, `generate_retrospective`, and `emit_captured`/`_maybe_auto_commit`.
  - The generator is local and deterministic. `emit_captured` appends to the local event log; its only network edge is `_fanout_live_work_retrospective`.
  - So the whole command could run for real, but the harness asserts on mocks. The fix is a whole-file rewrite, recorded as **D1** (section 4). Twenty tests go there.
- **FIX `TestMaybeAutoCommit::test_auto_commit_enabled_calls_git` + `test_auto_commit_disabled`** (in-PR, small):
  - `git init` `tmp_path`, write `.kittify/config.yaml` with the auto-commit setting, and drop the `subprocess.run` and `get_auto_commit_default` patches.
  - Enabled: assert `git log -1 --format=%s` equals the message and the file is tracked.
  - Disabled: assert HEAD is unchanged.
  - Planted break (VERIFIED current green, 5 passed): `src/specify_cli/cli/commands/retrospect.py:233` `["git", "commit", "-m", message]` → `["git", "commit", "--dry-run", "-m", message]`.
- **FIX `test_retrospect_update_persisted.py::test_emit_captured_spy_matches_persisted_record_on_disk`**:
  - Replace the `emit_captured` spy with the real emitter; patch only `specify_cli.retrospective.lifecycle_events._fanout_live_work_retrospective`.
  - Read the `RetrospectiveCaptured` row from the mission's `status.events.jsonl`, and assert its `findings_status` and counts equal the on-disk YAML and the reported JSON.
  - Planted break (VERIFIED current green, 2 passed): `src/specify_cli/retrospective/lifecycle_events.py:459` `findings_status=record.findings_status,` → `findings_status="ran_no_findings",`.
  - Note: this file imports helpers from `test_retrospect.py`, so it is grouped with that file.

### 2.9 Agent retrospect synthesize: `tests/cli/test_agent_retrospect_synthesize.py`

- **FIX `test_proposal_id_filter_passed_to_apply_proposals`, `test_dry_run_is_true_by_default_in_apply_call`, `test_apply_flag_sets_dry_run_false`**. Replace them with one parametrized real-record test.
  - Weakness: `read_record` returns a MagicMock with `proposals = []`. The default approved set (`agent_retrospect.py:617`, accepted-only) is therefore always empty, and the "dry-run mutates nothing" contract is never checked on disk.
  - Stronger oracle: write a real retrospective record with two `add_glossary_term` proposals, one `accepted` and one `pending`, with evidence reachable in a real event log. Do not patch `read_record` or `apply_proposals`. Assert:
    - (a) default (no `--apply`): envelope `dry_run: true`, and no glossary artifact or provenance file under `.kittify/glossary/`;
    - (b) `--apply`: only the accepted proposal's artifact exists;
    - (c) `--apply --proposal-id <pending-id>`: behaviour per the product ruling in P3.
  - Planted break (VERIFIED current green, 29 passed across this file and `test_agent_retrospect_missing_record.py`): `src/specify_cli/cli/commands/agent_retrospect.py:618` `p.id for p in all_proposals if p.state.status == "accepted"` → `p.id for p in all_proposals`. That break makes `--apply` apply pending or rejected proposals. `tests/integration/retrospective/test_next_mission_sees_change.py` calls `apply_proposals` directly, so it does not guard the CLI filter.
- KEEP `test_generator_record_dryrun_exit0` and `test_generator_record_apply_exit0` (a real record is read), and `test_actor_id_forwarded` (flag mapping, low risk).
- KEEP `test_agent_retrospect_missing_record.py::test_existing_record_json_includes_synthesized_outcome` (envelope contract); fold it into D1 later.

### 2.10 Events tail: `tests/cli/test_events_tail.py::test_no_write_syscall_reachable_on_any_code_path`: FIX

- Weakness: the spy wraps only `Path.open`, with an enumerated mode set that lacks `"at"`, `"wt"` and `"xt"`. It cannot see builtin `open()`, `os.open`, `os.replace` or tempfile atomic writes.
- Stronger oracle: before each invocation, snapshot `(relpath, size, mtime_ns, sha256)` for every file under `tmp_path`, and snapshot the directory listing; assert both are identical afterwards. Optionally also run with the mission dir `chmod 0o555` via `tests/_support/eacces.mode_bits_enforced` and assert that the same exit codes still occur.
- Planted break (VERIFIED current green): after `events.py:150` (`log_path = mission_event_log_path(...)`) insert `open(log_path, "a").close()`.

### 2.11 KEEP clusters without further change

- `test_routes_command.py` (2): `_gateway_for` is the SaaS gateway factory. "Not built under drain-off" is the contract, and stdout/JSON are asserted exactly.
- `test_implement_bulk_edit_planning.py` (3): these isolate the bulk-edit gate. `create_lane_workspace` (heavy git worktree) is mocked, and its `assert_not_called` is the "refused before side effect" observable, alongside exit code and remedy text. Minor: `mission_id=f"mission-{slug}"` is not a ULID. Replace it opportunistically.
- `test_tasks_finalize_lanes_minting.py` (2): false-positive flag, with only three patches. They assert on-disk `lanes.json` and event-log state. Optional: `git init` instead of stubbing `_ensure_target_branch_checked_out`.

---

## 3. Suspected product bugs and findings (with evidence)

| # | Severity | Finding | Evidence |
|---|---|---|---|
| P1 | High (coverage gap on a core-rigour contract) | Nothing guards `consolidate --strategy` threading from the CLI to the executor. | Break at `consolidate.py:691` (`strategy=MergeStrategy.MERGE`) → `test_merge_strategy.py` 28 passed, `test_merge_cli_golden.py` 11 passed. Remedy: G5. |
| P2 | High (coverage gap on a doctrine-mutation contract) | Nothing guards the rule that synthesize `--apply` defaults to *accepted* proposals only. | Break at `agent_retrospect.py:618` (drop the `status == "accepted"` filter) → 29 passed. Remedy: G8. |
| P3 | Product question | `--proposal-id` bypasses the accepted-state filter. `approved_ids = set(proposal_id)` (`agent_retrospect.py:614`), and `apply_proposals` applies any id in that set (`doctrine_synthesizer/apply.py:476`), so an operator can apply a pending or rejected proposal by id. If that is deliberate, document it; otherwise refuse non-accepted ids. | READ. |
| P4 | Debt (sync residue) | `ensure_sync_daemon` → `ensure_daemon` is threaded through `status/emit.py` (default `True`, forwarded at :1565) and `coordination/outbound.py:119` into `fire_saas_fanout(**kwargs)`, and nothing consumes it. The sync daemon was deleted (CLAUDE.md "sync is dead"). `test_mark_wp_merged_done_uses_lightweight_emit_path` pins it. | `grep -rn ensure_daemon src/` finds only the two forwarding sites. |
| P5 | Low | Silent failures in `retrospect create`. `with contextlib.suppress(Exception): emit_captured(...)` (retrospect.py ~418) drops the `RetrospectiveCaptured` event with no warning, so the record exists but the event log disagrees. `_maybe_auto_commit` has `except Exception: pass` (retrospect.py:238), so a failed auto-commit is invisible. That is also a Sonar empty-handler case. | READ. |
| P6 | Observation (outside Bundle B) | `charter bundle validate`: removing `and not sidecar_errors` from the overall gate (`charter_bundle.py:446`) leaves `test_validate_reports_provenance_yaml_parse_error` green, because other failures keep it red. The provenance-sidecar term may lack an isolated guard. | VERIFIED: 1 passed with the break planted. |
| P7 | Test hygiene | `test_implement_base_flag.py` has a dead autouse fixture and a no-op `require_main_repo` patch. `test_auth_login.py` and `test_auth_logout.py` do not pin `SPEC_KITTY_HOME`. `test_login_proceeds_even_if_teamspace_mission_state_is_blocked` runs the real `SecureStorage.from_environment`, so it can read the per-worker HOME, or an OS keyring backend, and depends on the env auth state. | READ. |
| P8 | Harness hazard | `tests/auth/integration/test_headless_login_e2e.py` has no timeout. When headless dispatch breaks, it starts the real browser loopback flow and waits out the 5-minute callback timeout: 301 s before it went red. It should patch `BrowserLauncher.launch` with a side effect that fails fast, or the loopback server. | VERIFIED (`login-dispatch` run). |

---

## 4. DEFER items (become issues)

**D1: rewrite the `tests/cli/commands/test_retrospect.py` harness (20 tests).**

Tests covered:
- `test_create_success_json`, `test_create_record_exists_error_json`, `test_create_overwrite_flag`, `test_create_update_flag`, `test_create_success_rich_output`;
- `test_fabricate_empty_creates_record_when_missing`;
- `test_create_policy_resolution_error_json`, `_non_json`, `test_create_generator_file_not_found`, `test_create_generator_generic_exception`, `test_create_write_gen_record_generic_exception`, `test_create_record_exists_non_json`;
- `test_backfill_process_candidate_real_run_success`, `_file_not_found`, `_generic_exception`, `test_backfill_emit_failures_flag`, `test_backfill_no_json_rich_output`, `test_backfill_no_json_with_failures_shows_failure_list`;
- `TestSummaryCmdExtended::test_backfill_process_candidate_record_exists_error`, `test_backfill_generic_exception_with_emit_failures`.

Target shape:
1. A `retrospect_project` fixture:
   - a `git init` tmp repo with the `canonical_home` fixture;
   - `.kittify/config.yaml` with an auto-commit toggle;
   - `kitty-specs/<slug>/meta.json` with a real ULID;
   - spec/plan/tasks artifacts;
   - status events written through the production seam (`emit_status_transition`) rather than hand-rolled JSON (DIRECTIVE_041, "delegate to the production seam");
   - `monkeypatch.chdir(repo)`.
2. Drive `retrospect create/backfill/synthesize` with `CliRunner`. Patch only `lifecycle_events._fanout_live_work_retrospective` (Zeitgeist edge) and freeze the clock. Never patch `_resolve_handle`, `_check_mission_completed`, `resolve_policy`, `generate_retrospective` or `write_gen_record`.
3. Use fault injection only for branches no real fixture reaches, such as a generator crash (`RuntimeError`). A malformed `config.yaml` should be real, to reach `PolicyResolutionError`. A seeded existing record should be real, to reach `RecordExistsError`.
4. Assert:
   - the exit code and JSON payload;
   - the canonical record YAML on disk (overwrite replaces it; update merges the union);
   - `RetrospectiveCaptured`/`RetrospectiveCaptureFailed` rows in `status.events.jsonl`;
   - `git log` for auto-commit.
5. Coordinate with Bundle A: its five no-assertion/type-only/skip tests are in the same file.

**D2: real LANES-topology done-bookkeeping guard (`test_merge_status_commit.py::test_done_events_committed_to_git`).**

Target shape:
- Use `tests/terminus/lanes_fixture.py` (it already exists; it defaults the target to `develop`, avoiding the protected-`main` crash #5385).
- Run a real `spec-kitty consolidate --mission <slug> --yes`.
- Assert `git show develop:kitty-specs/<slug>/status.events.jsonl` has a `done` event for every WP and `status.json` agrees.
- Then retire the 17-patch mock.

It is deferred only to cap this PR's FIX budget; a single implementer could pull it into G4.

---

## 5. Implementation grouping

No two groups share a file. **No `src/` file is edited by any group**: every group is test-side. Product findings P3–P5 and P8 become separate issues. `[Opus]` marks oracle-design work; `[Sonnet]` marks mechanical work.

| Group | Grade | Test files (edit) | src files read (not edited) | Contents | Bundle A overlap |
|---|---|---|---|---|---|
| **G1 auth-login seam** | Opus (oracle design) | `tests/cli/commands/test_auth_login.py` | `src/specify_cli/cli/commands/_auth_login.py` | RETIRE 3; FIX 3 (move to the flow-class/`PublicHttpClient` + `FakeSecureStorage` boundary, imported from `tests/auth/integration/conftest.py` without editing it); add `canonical_home` to the autouse fixture. | none |
| **G2 auth-logout** | Sonnet | `tests/cli/commands/test_auth_logout.py` | `_auth_logout.py` | RETIRE `test_logout_local_cleanup_failure_exits_1`; add `canonical_home`. | **Overlap:** Bundle A owns `test_logout_impl_is_importable` in this file. Land both in one commit, or assign the file to one implementer. |
| **G3 charter retirements** | Sonnet | `tests/cli/commands/test_charter_bundle_coverage.py`, `tests/cli/commands/test_charter_orchestration.py`, `tests/cli/commands/test_charter_rendering.py` | `charter_bundle.py`, `charter/{interview,context,_status_collectors}.py` | RETIRE 2 + 5 + 1; each PR note cites its guard and break from 2.3. `test_charter_json_error_contract.py` is left untouched (KEEP). | none |
| **G4 merge/implement/org retirements + base FIX** | Sonnet | `tests/cli/commands/test_merge_status_commit.py`, `tests/cli/commands/test_implement_base_flag.py`, `tests/cli/test_doctrine_org_commands.py` | `consolidation/done_bookkeeping.py`, `cli/commands/implement.py`, `cli/commands/doctrine.py` | RETIRE 2 (merge_status) + 1 (base) + 1 (org); FIX invalid-ref (message + no-branch assert, real ULID, drop the dead fixture and no-op patch). D2 is optional if capacity allows. | none |
| **G5 merge strategy real test** | Opus (oracle design) | `tests/cli/commands/test_merge_strategy.py` | `cli/commands/consolidate.py`, `consolidation/executor.py`; imports `tests/terminus/conftest.py` without editing it | Replace the 3 flagged tests with one parametrized slow real-`consolidate` test (parent-count / ancestry oracle; confirm the shapes red-first); remove the unused mock helpers. | none |
| **G6 doctor parity** | Sonnet | `tests/cli/commands/test_doctor_mission_state.py` | `migration/mission_state.py`, `cli/commands/_mission_state_doctor.py` | FIX: real `RepairReport` in place of the MagicMock `to_json`. | none |
| **G7 retrospect small FIXes** | Sonnet | `tests/cli/commands/test_retrospect.py` (`TestMaybeAutoCommit` only), `tests/cli/commands/test_retrospect_update_persisted.py` | `cli/commands/retrospect.py`, `retrospective/lifecycle_events.py` | FIX the auto-commit pair (real git); FIX the emit spy → real event-log row. Do not refactor the shared helpers that `test_retrospect_update_persisted.py` imports. | **Overlap:** Bundle A owns 5 tests in `test_retrospect.py`. Same file, so land both in one commit or give the file to one implementer. D1 (whole-file rewrite) is a separate issue. |
| **G8 synthesize accepted-only / dry-run** | Opus (oracle design) | `tests/cli/test_agent_retrospect_synthesize.py` | `cli/commands/agent_retrospect.py`, `doctrine_synthesizer/apply.py` | FIX 3 → one parametrized real-record test (accepted vs pending proposal; dry-run leaves disk untouched). Wait on the P3 ruling for case (c), or pin the current behaviour and name the ruling. | none |
| **G9 events-tail read-only oracle** | Sonnet | `tests/cli/test_events_tail.py` | `cli/commands/events.py` | FIX: filesystem snapshot oracle in place of the `Path.open` spy. | none |

Split between two implementers:
- **Opus:** G1, G5, G8.
- **Sonnet:** G2, G3, G4, G6, G7, G9.

Bundle A files listed as out of scope for Bundle B have no Bundle B edits: `test_mission_agnostic_flag.py`, `test_mission_brief.py`, `test_charter_package_exports.py`, `test_zeitgeist_operability_cli.py`, `test_init_templates_preservation.py`. The only shared files are `test_auth_logout.py` (G2) and `test_retrospect.py` (G7).
