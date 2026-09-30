---
title: 'Mission Review Report: windows-compatibility-hardening-01KP5R6K'
description: "Post-merge mission review for windows-compatibility-hardening-01KP5R6K: the reviewer's spec-to-code fidelity, coverage, and risk findings (2026-04-14)."
doc_status: deprecated
updated: '2026-08-12'
---
> **RETIRED (shipped)** — this review covered mission `windows-compatibility-hardening-01KP5R6K`,
> which squash-merged as `89bab26e5`. Retained as a historical mission-review snapshot;
> do not consult for current behavior.

# Mission Review Report: windows-compatibility-hardening-01KP5R6K

**Reviewer**: claude:opus-4.6:mission-reviewer
**Date**: 2026-04-14
**Mission**: `windows-compatibility-hardening-01KP5R6K` — Windows Compatibility Hardening Pass
**Baseline commit**: `51c7cd0b` (pre-mission scan audit starting point)
**Squash merge commit**: `46593f3b` (mission landing on `main`)
**HEAD at review**: `81b6ec62`
**WPs reviewed**: WP01–WP09 (all merged and marked `done` in `status.events.jsonl`)

---

## Executive Summary

**Verdict: FAIL (release-blocking — substantive spec gaps + staging-area hazard).**

> **Revision note (2026-04-14, second-pass review):** A sharper second review identified five substantive spec gaps in the committed code at `46593f3b` that the initial review missed. The revised verdict is FAIL on delivery merits, not just operational hazard. Sections "Second-Pass Findings" (below) supersede the equivalent PASS rows in the Summary Table and FR Coverage Matrix.

**Substantive delivery misses at `46593f3b`** (all independently verified):

1. `src/specify_cli/runtime/home.py:21-29` still resolves Windows to `user_data_dir("kittify")`. Combined with `windows_migrate.py:143-146` marking `~/.kittify` as messaging-only (`dest=None`), Windows keeps **two global-runtime roots** and never migrates the old one. Q3=C and FR-005 are not actually satisfied.
2. `migrate_cmd.py:77-80` calls `migrate_windows_state()` without `dry_run=`, so `spec-kitty migrate --dry-run` performs a real migration on Windows. FR-006 violated.
3. `windows_migrate.py:390-409` swallows `TimeoutError` internally. The CLI's `except TimeoutError: exit 69` is dead code; lock contention downgrades to a warning and the command continues. FR-007/FR-008 contract broken.
4. `tests/audit/test_no_legacy_path_literals.py:29` scans only `src/specify_cli/cli/`. `runtime/resolver.py:106-108` and `doctrine/resolver.py:114-116` both print `~/.kittify/` to stderr. SC-002 ("zero legacy path output") is not actually enforced.
5. `.github/workflows/ci-windows.yml:30-48` runs `python -m pytest` from the host Python after a `pipx install`; the pipx venv is never invoked. Separately, `tests/kernel/test_paths_unified_windows_root.py:28-29` asserts on `WindowsFileStorage.store_path`, which is not a public attribute of `FileFallbackStorage` — the test would `AttributeError` on first real Windows run.

**Operational hazard**: the working-tree state at the moment of review contains ~50 uncommitted staged deletions that, if committed, would roll back nearly every mission deliverable (`src/specify_cli/paths/` entire directory missing on disk; `ci-windows.yml` staged for deletion; `pyproject.toml` keyring guard staged to be reverted; hook template staged to be reverted to `python -m`). This state was not produced by any mission work — it appears to be a cleanup artifact of the post-merge worktree teardown or an unrelated safe-commit stash. It is **not** a committed regression and does not affect the git history, but it **is** a release-blocking hazard until cleared: any commit created from the current working tree will destroy the mission.

Action required before release:
1. Clear the staging hazard: `git restore --staged .` followed by `git checkout HEAD -- src/ .github/ pyproject.toml pytest.ini`.
2. Open a follow-up mission to address the five substantive findings below, or accept them as known issues with documented follow-up tickets.

---

## FR Coverage Matrix

All 19 Functional Requirements from `spec.md` are mapped to owning WP and test file(s). Severity column flags cases where coverage is thin or behavioral constraint is weak.

| FR ID | Description (brief) | WP Owner | Test File(s) (representative) | Adequacy | Finding |
|-------|---------------------|----------|------------------------------|----------|---------|
| FR-001 | Windows auth uses file-backed store | WP03 | `tests/auth/secure_storage/test_from_environment_platform_split.py`, `tests/packaging/test_windows_no_keyring.py` | ADEQUATE | — |
| FR-002 | Platform-explicit storage selector | WP03 | `test_from_environment_platform_split.py` | ADEQUATE | — |
| FR-003 | Tracker credentials at `%LOCALAPPDATA%\spec-kitty\tracker` | WP05 | `tests/tracker/test_credentials_windows_paths.py` | ADEQUATE (windows_ci only) | — |
| FR-004 | Sync/daemon state at `%LOCALAPPDATA%\spec-kitty\sync` | WP05 | `tests/sync/test_daemon_windows_paths.py` | ADEQUATE (windows_ci only) | — |
| FR-005 | `kernel/paths.py` + unified root | WP05 | `tests/kernel/test_paths_unified_windows_root.py` | ADEQUATE (windows_ci only) | — |
| FR-006 | One-time idempotent migration | WP02, WP04 | `tests/paths/test_windows_migrate.py` (5 tests) | ADEQUATE | — |
| FR-007 | Migration contention safety | WP02 | `test_windows_migrate.py::test_concurrent_lock_contention` | ADEQUATE (windows_ci only) | — |
| FR-008 | Actionable migration error messages | WP02 | `test_windows_migrate.py` | PARTIAL | See RISK-3 below |
| FR-009 | Hook pins absolute `sys.executable` | WP06 | `tests/policy/test_hook_installer_rendering.py` | ADEQUATE | — |
| FR-010 | Hook executes on Git for Windows | WP06 | `tests/policy/test_hook_installer_execution.py` | ADEQUATE (windows_ci only) | — |
| FR-011 | Hook tests validate execution | WP06 | `test_hook_installer_execution.py` (real git commit) | ADEQUATE (windows_ci only) | — |
| FR-012 | User-facing path rendering helper | WP01, WP04 | `tests/paths/test_render_runtime_path.py` | ADEQUATE | — |
| FR-013 | Stale literals replaced in `migrate_cmd.py`, `status.py` | WP04 | `tests/audit/test_no_legacy_path_literals.py` | ADEQUATE (static grep) | — |
| FR-014 | Worktree symlink-vs-copy fallback | WP08 | `tests/core/test_worktree_symlink_fallback.py` | ADEQUATE (windows_ci only) | — |
| FR-015 | Blocking `windows-latest` CI job | WP07 | `.github/workflows/ci-windows.yml` (workflow itself) | PARTIAL | See DRIFT-1 |
| FR-016 | Curated Windows-critical suite | WP07 | `pytest.ini` marker + 9 `windows_ci` test files | ADEQUATE | — |
| FR-017 | Every confirmed bug has native-Windows test | WP08 | `tests/regressions/test_issue_{101,71,105}_*.py`, upgraded `test_issue_586_*.py` | ADEQUATE (windows_ci only) | — |
| FR-018 | Second-pass repo-wide audit | WP09 | `architecture/2026-04-14-windows-compatibility-hardening.md` (audit report) | PARTIAL | See DRIFT-2 |
| FR-019 | Docs updated for Windows path story | WP09 | `CLAUDE.md`, `docs/architecture/windows-state.md`, 2 ADRs | ADEQUATE | — |

**Legend:** ADEQUATE = test constrains the required behavior in production. PARTIAL = test exists but has a weakness documented in a DRIFT/RISK row. MISSING = no test found. None of the 19 FRs are MISSING.

---

## Drift Findings

### DRIFT-1: FR-015 "blocking" status depends on out-of-repo branch protection config

**Type**: NFR-MISS (enforcement not verifiable in-repo)
**Severity**: MEDIUM
**Spec reference**: FR-015, C-004 ("Windows CI job added in this mission is blocking on pull requests, not nightly-only")
**Evidence**:
- `.github/workflows/ci-windows.yml` exists and triggers on `pull_request` + `push` to `main`.
- `.github/workflows/protect-main.yml` references `release-readiness` as a required status check — **not** `ci-windows / windows-critical`.
- No PR in this repo can be verified to have failed on `ci-windows` because the mission landed via local squash merge, not via a PR. The workflow may execute on the next PR but its blocking status is not guaranteed.

**Analysis**: FR-015 explicitly promises "blocking on pull requests". The workflow runs on every PR, but "blocking" requires that a failing `ci-windows` status prevents merge. That is a branch-protection configuration on `main`, which is held in GitHub Settings and is not versioned in this repo. WP07's `T044` correctly documented this as a "Post-merge action required" note (maintainer must add the check), but until that action is executed on GitHub, C-004 is not actually enforced. The mission can reasonably claim FR-015 delivery (the workflow exists) but cannot claim C-004 closure until branch protection is updated.

**Remediation outside the mission**: the maintainer documented as the action owner for T044 must update branch protection on `Priivacy-ai/spec-kitty` → `main` and include `ci-windows / windows-critical` as a required check.

---

### DRIFT-2: FR-018 test adequacy — audit completeness is documentation, not enforcement

**Type**: PUNTED-FR (partial)
**Severity**: LOW
**Spec reference**: FR-018 ("A second-pass repo-wide audit MUST be executed searching for [15 keyword sets]; each finding MUST be either fixed, covered by new CI, or filed as a follow-up issue")
**Evidence**:
- Audit report committed at `architecture/2026-04-14-windows-compatibility-hardening.md` (1417 hits classified).
- 3 GitHub follow-up issues filed (#629, #630, #631) with `windows` label.
- `tests/audit/test_no_legacy_path_literals.py` enforces one slice of the audit (legacy path literals in CLI) as a regression guard.
- **No test enforces that the other 14 keyword categories were actually audited.**

**Analysis**: FR-018 says the audit "MUST be executed." The audit was executed and the report is committed, so the delivery is arguably complete. But there is no automated regression guard that prevents future reintroduction of, e.g., `shell=True` in subprocess calls or `import fcntl` outside guarded blocks. The audit is a point-in-time snapshot, not a durable constraint. This is a spec-drafting gap more than an implementation gap — FR-018 stopped at "audit once" rather than "audit forever". Implementers correctly filed follow-up issues for residuals (#630 covers the `shell=True` finding), so the outcome is defensible. But the audit test in `tests/audit/` covers only 1 of 7 pattern categories.

**Classification**: LOW severity because (a) the fixes in WP01–WP08 actually removed or guarded the risks that FR-018 cared about, and (b) follow-ups are filed. A future mission that wants to harden this further could expand `tests/audit/` into a full matrix. Recording as drift for transparency, not as a release blocker.

---

## Risk Findings

### RISK-1: Working-tree staging area contains mass rollback of mission deliverables

**Type**: CROSS-WP-INTEGRATION (post-merge artifact, not a coded regression)
**Severity**: CRITICAL (for any commit made from the current working tree)
**Location**: Git staging area at the time of review; `<reviewer-working-directory>` (working directory)
**Trigger condition**: Any developer who commits from the current staged state will land a revert of nearly every mission deliverable on `main`.

**Evidence**:
- `git status --short` reports ~50 staged changes, including deletions of `ci-windows.yml`, `src/specify_cli/encoding.py`, `src/specify_cli/paths/__init__.py`, `src/specify_cli/paths/windows_paths.py`, `src/specify_cli/paths/windows_migrate.py`, `src/specify_cli/auth/secure_storage/windows_storage.py`, and ~30 test files.
- Verification: `ls src/specify_cli/paths/` returns `No such file or directory`, while `git show HEAD:src/specify_cli/paths/__init__.py` succeeds.
- `git show HEAD --stat` only shows the `status.events.jsonl` update (2 files). The code at HEAD is correct. The rollback is entirely in the index/working tree.
- `git stash list` shows `stash@{0}: spec-kitty-safe-commit:<uuid>` — consistent with the `spec-kitty` safe-commit / cleanup machinery having prepared a partial revert that was never undone.

**Analysis**: This is not a defect in the mission implementation. The committed history at HEAD is clean and correct; all 9 WPs merged as intended. The staging area appears to have been polluted by a post-merge cleanup step (possibly the `spec-kitty merge` command's worktree teardown interacting with a safe-commit pre-prepared stash). The risk is purely operational: if a future commit creates a new snapshot from the current working tree, it will appear to revert the mission.

**User-visible impact if committed**: the next version of the CLI would lose all Windows hardening. #603 would need to be reopened. The delivered CI job would disappear. The hook installer would regress to `python -m ...`.

**Remediation (not performed by this review)**:
```bash
git restore --staged .
git checkout HEAD -- src/ .github/ pyproject.toml pytest.ini
```
After restoration, `git status` should show only unrelated files (like `kitty-specs/*/status.json` sync drift from other missions) and none of the mission's deliverables.

---

### RISK-2: `install_commit_guard()` legacy wrapper silently swallows `RuntimeError`

**Type**: ERROR-PATH (silent failure candidate)
**Severity**: MEDIUM
**Location**: `src/specify_cli/policy/hook_installer.py:97-119` (legacy `install_commit_guard(worktree_path, repo_root)` wrapper)
**Trigger condition**: `sys.executable` resolves to a path that does not exist (uninstalled/migrated virtualenv, broken pipx shim, corrupted symlink on CI runners).

**Evidence**:
```python
def install_commit_guard(worktree_path: Path, repo_root: Path) -> Path | None:
    try:
        record = install(repo_root)
        return record.hook_path
    except Exception:
        return None
```

**Analysis**: The new `install(repo_root)` (WP06) correctly raises `RuntimeError` when `Path(sys.executable).resolve(strict=False)` does not point to a file. But the legacy wrapper `install_commit_guard` catches `Exception` and returns `None`. Callers that branch on `None` will think hook installation was skipped intentionally and proceed silently. FR-009 (absolute interpreter pin) is preserved at the `install()` level; the regression is specifically at the wrapper that existing call sites use. Per FR-011 ("tests MUST validate executable behavior, not just that the hook file was written"), a wrapper that eats hook install failures undermines the intent of FR-011.

**Mitigation path**: a small follow-up that replaces `except Exception: return None` with `except (OSError, RuntimeError) as exc: logger.error("Hook install failed: %s", exc); return None`, preserving compatibility while surfacing the failure in the CLI log. Not release-blocking for this mission because the `install()` primary API is correct; the wrapper is legacy glue. File as follow-up.

---

### RISK-3: FR-008 "actionable error messages" test adequacy

**Type**: TEST-ADEQUACY
**Severity**: LOW
**Location**: `tests/paths/test_windows_migrate.py` vs. NFR-005 / FR-008
**Trigger condition**: Migration encounters a real-world failure (permission denied, cross-volume with readonly target, network drive fault) that the test suite did not simulate.

**Evidence**:
- The 5 migrated tests cover happy-path (absent, moved, quarantined, idempotent, dry-run). The `windows_ci`-marked concurrency test covers lock contention.
- No test covers: `PermissionError` during `os.replace`, disk-full during `shutil.copytree` fallback, unresolvable `%LOCALAPPDATA%` (real environment).
- FR-008 states "CLI MUST surface a clear, actionable error and MUST NOT silently continue writing to the legacy location." The implementation does construct actionable messages in `_render_migration_summary()` (WP04), but the error-path content is not asserted.

**Analysis**: The migration's error branch exists in code (`except OSError as exc: outcomes.append(MigrationOutcome(status='error', error=str(exc), ...))`) but no test validates that, e.g., a `PermissionError` produces a message that names the specific path and tells the user what to do. NFR-005 asks for actionable error paths and explicitly notes "Verified by test assertions." The test is PARTIAL on this axis. Low severity because the code path is correct; what's missing is adversarial test coverage.

---

## Silent Failure Candidates

| Location | Condition | Silent result | Spec impact |
|---|---|---|---|
| `src/specify_cli/policy/hook_installer.py:118` | Any exception in `install()` including `RuntimeError` for missing `sys.executable` | `install_commit_guard` returns `None`; caller assumes intentional skip | FR-009/FR-011: hook may silently fail to install on broken interpreter |
| `src/specify_cli/paths/windows_migrate.py:202` (lock release) | `msvcrt.locking(…, LK_UNLCK, 1)` raises `OSError` | `except OSError: pass` — no log | Low — lock is advisory, file will close next. Documented concern only. |
| `src/specify_cli/paths/windows_paths.py` `render_runtime_path()` | Path is not under `$HOME` (POSIX tilde branch) | Returns absolute path string | Intentional fallback — PASS |
| `src/specify_cli/encoding.py:ensure_utf8_on_windows()` | `stream.reconfigure()` raises `OSError/ValueError` (non-TTY or redirected) | `except (OSError, ValueError): continue` | Intentional and documented — PASS |

---

## Security Notes

| Finding | Location | Risk class | Severity | Recommendation |
|---|---|---|---|---|
| No new `shell=True` subprocess calls in mission diff | `git diff 51c7cd0b..HEAD -- src/` | — | INFO | Clean. Existing `shell=True` usages (caught by WP09 audit) filed as #630. |
| No new HTTP calls in mission diff | `git diff` grep for `httpx\|requests\|urllib` returns 0 | — | INFO | Clean. |
| `_migration_lock()` uses `msvcrt.locking` with LK_NBLCK and retry-with-timeout | `windows_migrate.py:180-210` | LOCK-TOCTOU | LOW | Lock is acquired before the destination check; read-modify-write is inside the lock. No TOCTOU. |
| `open(lock_path, "a+b")` not in a `with` statement | `windows_migrate.py:672` | RESOURCE-LEAK | LOW | Managed by explicit `try/finally` + `lock_file.close()`. `# noqa: SIM115` applied. Acceptable. |
| `WindowsFileStorage` writes under `%LOCALAPPDATA%\spec-kitty\auth\` | `windows_storage.py` | PATH-TRAVERSAL | LOW | Path is derived from `platformdirs.user_data_dir("spec-kitty", …)` + literal `"auth"` subdir. No user-supplied segment. PASS. |
| `migrate_windows_state()` uses `Path.home()`, `platformdirs.user_data_dir`, and literal segments only | `windows_migrate.py` full module | PATH-TRAVERSAL | INFO | No user input is used in any path construction. PASS. |
| Pre-commit hook template embeds `sys.executable` as a double-quoted string in `#!/bin/sh` | `hook_installer.py:HOOK_TEMPLATE` | SHELL-INJECTION | LOW | `sys.executable` is controlled by the installed interpreter, not by user input. Risk is present only if a user installs a Python with a maliciously crafted path — out of scope. Quote handling is correct. PASS. |

No CRITICAL or HIGH security findings. The mission does not introduce new attack surface.

---

## Cross-WP Integration Check

| Shared file | WPs that touched it | Final state at HEAD | Status |
|---|---|---|---|
| `pyproject.toml` | WP03 (keyring marker) | `"keyring>=24.0; sys_platform != \"win32\""` present | PASS |
| `pytest.ini` | WP03 (lane-a) + WP06 (lane-b) | `windows_ci` marker present with merged description | PASS (merge conflict resolved) |
| `.github/workflows/ci-quality.yml` | WP07 | 34 pytest invocations updated to exclude `windows_ci` | PASS |
| `.github/workflows/ci-windows.yml` | WP07 (new) | Blocking `windows-latest` job present | PASS (blocking enforcement: DRIFT-1) |
| `src/specify_cli/auth/secure_storage/__init__.py` | WP03 | `TYPE_CHECKING` + `sys.platform` guard on `keychain` import | PASS |
| `src/specify_cli/paths/windows_migrate.py` | WP01 (stub) + WP02 (impl) | Full implementation present; WP01 stub replaced | PASS |
| `src/specify_cli/cli/commands/doctor.py` | Not originally in any WP; added to WP04 owned_files during cycle-2 fix | Legacy literals replaced via `render_runtime_path` | PASS (ownership reconciled in WP04 cycle 2 review) |
| `src/specify_cli/cli/commands/init.py` | Same as above | 3 docstring literals replaced during WP04 cycle 2 | PASS |

No dropped exports, no integration ruptures.

---

## Review History Signal

WPs with rejection cycles in this mission:

- **WP04**: 1 rejection (cycle 1). Reviewer caught two real bugs (`CliRunner(mix_stderr=False)` incompatible with installed Typer 0.24.1; audit regex too narrow to catch `doctor.py:181-182`). Implementer fixed both cleanly in cycle 2; reviewer verified and approved. Healthy rejection — no arbiter override, no forced transitions.

All other WPs (WP01, WP02, WP03, WP05, WP06, WP07, WP08, WP09) approved on first review. No arbiter overrides, no `--force` approvals. The review history is clean.

---

## Second-Pass Findings (supersede equivalent PASS rows above)

### DRIFT-3: Two global-runtime roots on Windows; `~/.kittify` state is not migrated

**Type**: LOCKED-DECISION VIOLATION + PUNTED-FR
**Severity**: HIGH
**Spec reference**: Q3=C (unified Windows root), FR-005 ("kernel/paths.py and the unified storage root MUST agree on a single `%LOCALAPPDATA%\spec-kitty\` root"), FR-006 (migration of legacy state)
**Evidence**:
- `src/specify_cli/runtime/home.py:21-29` at `46593f3b`:
  ```python
  def get_kittify_home() -> Path:
      if env_home := os.environ.get("SPEC_KITTY_HOME"):
          return Path(env_home)
      if _is_windows():
          from platformdirs import user_data_dir
          return Path(user_data_dir("kittify"))
      return Path.home() / ".kittify"
  ```
- `src/specify_cli/paths/windows_migrate.py:143-146`:
  ```python
  LegacyWindowsRoot(
      id="kittify_home",
      path=home / ".kittify",
      dest=None,  # messaging-only; no state to move
  ),
  ```

**Analysis**: WP05 changed `src/kernel/paths.py` to use `"spec-kitty"` as the `platformdirs` app name on Windows, but `src/specify_cli/runtime/home.py` is a separate shim that was never touched. Many runtime consumers import `get_kittify_home()` from that shim, so they continue reading/writing `%LOCALAPPDATA%\kittify\`. The unified-root claim is false: Windows has two runtime roots after this mission — `%LOCALAPPDATA%\spec-kitty\` (new, per WP05) and `%LOCALAPPDATA%\kittify\` (old, still active).

Compounding this, `windows_migrate.py` explicitly marks the `kittify_home` entry as messaging-only with `dest=None` — meaning `~/.kittify` (or its Windows equivalent) is never migrated even when it exists with real state. Upgraded Windows users who previously ran spec-kitty will have their runtime state stranded at the old `kittify` root with no migration path.

**Remediation scope**: either (a) update `runtime/home.py` to call `get_runtime_root().base` on Windows AND add `kittify_home` → `root.base` migration in `windows_migrate.py`, or (b) document the dual-root as the intentional state (which contradicts the spec's locked Q3=C decision). Option (a) is the correct path.

---

### DRIFT-4: `spec-kitty migrate --dry-run` mutates Windows state on the dry run

**Type**: CONTRACT-VIOLATION
**Severity**: HIGH
**Spec reference**: FR-006 ("Migration MUST be idempotent; dry-run MUST compute outcomes without moving anything"), `contracts/cli-migrate.md` ("`dry_run=True`: computes outcomes without filesystem side effects")
**Evidence**: `src/specify_cli/cli/commands/migrate_cmd.py:77-80` at `46593f3b`:
```python
if sys.platform == "win32":
    from specify_cli.paths.windows_migrate import migrate_windows_state
    try:
        outcomes = migrate_windows_state()
    except TimeoutError as exc:
        ...
```

The call site does not forward the global `--dry-run` flag. `migrate_windows_state(dry_run=False)` is the default, so a preview invocation performs a real migration.

**Analysis**: `migrate_windows_state()` accepts `dry_run: bool = False` but the CLI never plumbs the flag through. A user running `spec-kitty migrate --dry-run` on a fresh upgrade expects to see what WOULD be moved, and instead has their state moved for real. This is a direct violation of both the FR and the contract document WP04 owned.

**Trigger condition**: any Windows user who runs `spec-kitty migrate --dry-run` as their first migration invocation.

---

### DRIFT-5: Lock contention no longer exits with code 69; the CLI continues

**Type**: CONTRACT-VIOLATION + SILENT-FAILURE
**Severity**: MEDIUM
**Spec reference**: FR-007 (contention safety), FR-008 (actionable error), `contracts/cli-migrate.md` ("Lock contention → exit code 69 (EX_UNAVAILABLE)")
**Evidence**:
- `src/specify_cli/paths/windows_migrate.py:390-409` at `46593f3b`:
  ```python
  try:
      with _migration_lock(root.base):
          ...
  except TimeoutError as exc:
      # Lock contention: emit error outcomes for all three roots
      error_msg = str(exc)
      for legacy in legacy_roots:
          outcomes.append(MigrationOutcome(status="error", error=error_msg, ...))
  ```
- `src/specify_cli/cli/commands/migrate_cmd.py:78-83`:
  ```python
  try:
      outcomes = migrate_windows_state()
  except TimeoutError as exc:
      console.print(f"[red]{exc}[/red]")
      raise typer.Exit(69)
  _render_windows_migration_summary(console, outcomes)
  ```

**Analysis**: The CLI expects `migrate_windows_state()` to raise `TimeoutError` so it can exit 69. The migration function instead catches the `TimeoutError` internally and converts it into a list of `status="error"` outcomes. The `except TimeoutError` branch at the call site is dead code. `_render_windows_migration_summary()` then prints the error outcomes as warnings and the `migrate` command continues to the per-project migration phase. Under contention, the user sees a warning and the command keeps going.

This is a two-layer silent failure: (1) the wrapped exception is not propagated, and (2) the CLI keeps executing downstream logic after a failed migration.

**Remediation scope**: either (a) make `migrate_windows_state()` re-raise `TimeoutError` for the lock-contention case specifically (distinct from per-root OS errors), or (b) inspect outcomes in the CLI and `raise typer.Exit(69)` if any outcome is `status="error"` with a lock-contention error message. Option (a) preserves the contract cleanly.

---

### DRIFT-6: SC-002 "zero legacy path output" is not enforced end-to-end

**Type**: NFR-MISS (test adequacy)
**Severity**: MEDIUM
**Spec reference**: SC-002 ("Windows users see 0 references to `~/.kittify` or `~/.spec-kitty` in CLI output, help text, status messages, or migration messages")
**Evidence**:
- `tests/audit/test_no_legacy_path_literals.py:29` at `46593f3b`:
  ```python
  root = pathlib.Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "cli"
  for py in root.rglob("*.py"):
      ...
  ```
  (Scope is `src/specify_cli/cli/` only.)
- `src/specify_cli/runtime/resolver.py:106-108`:
  ```python
  print(
      "Note: Run `spec-kitty migrate` to clean up legacy project files and use the global runtime (~/.kittify/).",
      file=sys.stderr,
  )
  ```
- `src/doctrine/resolver.py:114-116`: identical stderr message (mirrored copy).

**Analysis**: The audit test covers one tree (`src/specify_cli/cli/`) but the mission's delivered claim is about **all** CLI output. The `_emit_migrate_nudge()` helpers in `runtime/resolver.py` and `doctrine/resolver.py` print `~/.kittify/` to stderr — this is user-facing output, emitted on every non-migrated invocation until the nudge fires once per process. Windows users will see this message verbatim, including the literal `~/.kittify/`.

SC-002 is overstated. The acceptance criterion reads "Windows users see 0 references... in CLI output" but the audit test verifies only the CLI command tree. Either the test scope needs to expand to `src/specify_cli/**` and `src/doctrine/**` (with an allowlist for non-user-facing occurrences), or the resolver nudges need to emit via `render_runtime_path()` for the actual runtime root. Given the dual-root issue in DRIFT-3, the nudge is also factually misleading on Windows — it tells users to migrate to `~/.kittify`, which is neither the canonical new root nor a path that exists in the same form on Windows (`%USERPROFILE%\.kittify\` vs `%LOCALAPPDATA%\kittify\`).

---

### RISK-4: CI workflow does not exercise the pipx install topology it claims

**Type**: CROSS-WP-INTEGRATION + TEST-ADEQUACY
**Severity**: MEDIUM
**Location**: `.github/workflows/ci-windows.yml:30-48`
**Evidence**:
```yaml
- name: Install spec-kitty-cli (editable) + test deps
  run: |
    pipx install --editable . --force
    pipx inject spec-kitty-cli pytest pytest-cov
...
- name: Run Windows-critical suite
  run: |
    python -m pytest -m windows_ci --maxfail=1 -v
```

**Analysis**: The `pipx install` step creates a venv at the pipx location with `spec-kitty-cli` installed editable; the `pipx inject` step installs `pytest` and `pytest-cov` into that same venv. But the final step invokes `python -m pytest` using the **host Python** (the one provisioned by `actions/setup-python@v5`), not the pipx venv's Python. The pipx venv is never invoked.

In practice this may still work because `pipx install --editable .` makes `spec-kitty-cli` available via the `-e` link to the checkout, and the host Python can import the package from `src/` (because `pytest.ini` has `pythonpath = . src`). But:
1. The stated intent per WP07/R-07 was to test the pipx install topology — users install via pipx, CI should validate that install path. The current workflow does not.
2. `pipx runpip` commands (the keyring-absence check) validate the pipx venv's pip, but the pytest run bypasses that venv. Any discrepancy between host Python and pipx Python (e.g., different keyring transitive pulls, different `platformdirs` versions) will go undetected.

**Remediation scope**: change the pytest invocation to `pipx runpip spec-kitty-cli install pytest pytest-cov && pipx run --spec . pytest -m windows_ci --maxfail=1 -v`, or equivalent, so the same Python that has `spec-kitty-cli` installed is the one running the tests.

---

### RISK-5: `tests/kernel/test_paths_unified_windows_root.py` references a nonexistent attribute

**Type**: DEAD-TEST (would fail on first real Windows run)
**Severity**: MEDIUM
**Location**: `tests/kernel/test_paths_unified_windows_root.py:28-29`
**Evidence**:
```python
auth = WindowsFileStorage()
assert base_str in str(auth.store_path).lower(), (
    f"Auth store_path {auth.store_path} is not under unified root {root.base}"
)
```

`WindowsFileStorage` inherits from `EncryptedFileStorage` (alias for `FileFallbackStorage`). Per `file_fallback.py`, the `__init__` docstring explicitly names its param `base_dir`, and the class does not expose a public `store_path` attribute. `WindowsFileStorage.__init__` calls `super().__init__(store_path=store_path)` — this would itself raise `TypeError` unless `FileFallbackStorage.__init__` accepts `store_path` as a kwarg (which its documented signature does not).

**Analysis**: This test is `@pytest.mark.windows_ci` so it never runs on POSIX CI. It was approved in the WP05 review based on code inspection without a Windows CI run. On the first `windows-latest` invocation, this test will fail at import or at the attribute access, and the entire curated Windows suite will halt at `--maxfail=1`.

This is a cascading risk: when DRIFT-1/3/4/5 are addressed and the suite eventually runs on `windows-latest`, this test will block the run before any of the other `windows_ci` tests execute. The implementer either wrote against a refactored API that never landed, or copy-pasted a hypothetical API from the contract doc.

**Remediation scope**: audit the inheritance chain, determine the actual attribute name used by `FileFallbackStorage` to store the resolved directory, and update the assertion. Or add the missing `store_path` property to `WindowsFileStorage` as a deliberate public surface.

---

## Final Verdict

**FAIL — release-blocking on delivery merits + operational hazard.**

### Verdict rationale

The first-pass review (above the Second-Pass Findings section) was overly optimistic. A sharper read of the `46593f3b` tree surfaces five substantive spec gaps that block release:

- **DRIFT-3 (HIGH)**: Two runtime roots on Windows, no migration of the old `kittify` root.
- **DRIFT-4 (HIGH)**: `--dry-run` mutates state for real.
- **DRIFT-5 (MEDIUM)**: Lock contention downgrades to warning, no exit-69.
- **DRIFT-6 (MEDIUM)**: SC-002 not actually enforced; legacy-path messages still in user output.
- **RISK-4 (MEDIUM)**: CI doesn't exercise the pipx topology.
- **RISK-5 (MEDIUM)**: Unified-root cross-module test references a nonexistent attribute.

DRIFT-3 and DRIFT-4 alone are release-blocking: the first means Windows users who upgrade will have their runtime state orphaned at the old root forever, and the second means the documented safe-preview command mutates production state. DRIFT-5 means lock contention silently converts a failure into a warning. These are not documentation gaps — they are contract breaches that the per-WP review cycles did not catch.

The implementation is close to the spec but not at the spec. The gap is small and fixable in a follow-up mission; several of the findings are one-line fixes (forwarding `dry_run`, adding `~/.kittify` to the migration source map, raising `TimeoutError` from `migrate_windows_state`, widening the audit test scope).

**Combined with RISK-1 (working-tree staging-area hazard)**: release is not safe.

### Open items (blocking)

- **DRIFT-3 (HIGH)**: file a follow-up mission or issue to unify `runtime/home.py` with `paths/windows_paths.py` and add `~/.kittify` to the Windows migration source set.
- **DRIFT-4 (HIGH)**: one-line fix in `migrate_cmd.py` to forward the `dry_run` flag to `migrate_windows_state()`.
- **DRIFT-5 (MEDIUM)**: two-line fix in `windows_migrate.py` to re-raise `TimeoutError` OR CLI-side fix to inspect outcomes for lock-contention error messages and exit 69.
- **DRIFT-6 (MEDIUM)**: expand `tests/audit/test_no_legacy_path_literals.py` scope to `src/specify_cli/**` and `src/doctrine/**`, fix the resolver nudges.
- **RISK-4 (MEDIUM)**: CI workflow change to actually invoke pytest from the pipx venv.
- **RISK-5 (MEDIUM)**: fix or remove the `auth.store_path` assertion in the cross-module test.

### Open items (non-blocking, first-pass findings retained)

### Open items (non-blocking, post-restoration)

- **DRIFT-1 (MEDIUM)**: Maintainer must add `ci-windows / windows-critical` to `main` branch protection. Documented in WP07's T044 note; pending out-of-repo action.
- **DRIFT-2 (LOW)**: Consider expanding `tests/audit/test_no_legacy_path_literals.py` into a broader regression guard covering more FR-018 keyword categories. Filed as implicit follow-up under the WP09 audit report.
- **RISK-2 (MEDIUM)**: `install_commit_guard()` legacy wrapper silently swallows `RuntimeError`. Small follow-up to log or re-raise. Not a regression — pre-existing behavior preserved by WP06.
- **RISK-3 (LOW)**: Add adversarial tests for migration error paths (PermissionError, disk-full, unresolvable LOCALAPPDATA) to strengthen NFR-005 assertion coverage. Nice-to-have, not blocking.
- **#629, #630, #631**: Already-filed GitHub follow-ups. Schedule per normal backlog.
- **First 10 runs of `ci-windows` on `main`** (NFR-006): tracking item; will verify post-enforcement.

### Mission-level assessment

As a piece of software engineering, this mission is a success: clean specification, disciplined WP decomposition, one honest rejection cycle caught real bugs, no arbiter overrides, clean merge. The implementation will make the next Windows user's life materially better and closes a long-standing open issue (#603). Release gate should flip GREEN the moment the staging-area hazard is cleared.
