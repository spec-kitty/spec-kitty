# Mission Specification: Windows upgrade POSIX-mode fidelity

**Mission Branch**: `fix/windows-upgrade-mode-fidelity`
**Created**: 2026-09-22
**Status**: Draft
**Input**: Folded from GitHub issues #4923 and #4927 (surfaced by the Windows verification report #4930)

## Summary

On Windows, filesystems cannot carry POSIX file modes. `spec-kitty upgrade` and the
managed command/skill surfaces it repairs currently treat a host-unrepresentable POSIX
mode as if it were real divergence, and pass a `follow_symlinks` flag the host does not
support. Two user-visible defects result: the upgrade **crashes** (#4923), and — where it
does complete — it **reports phantom repairs** on a project that is already converged
(#4927). This mission makes both surfaces host-aware so Windows users can upgrade cleanly,
without weakening POSIX correctness on real POSIX hosts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upgrade completes on Windows without crashing (Priority: P1)

A Windows user runs `spec-kitty upgrade` on a project with managed command/skill surfaces
to repair. Today the run aborts deterministically with
`NotImplementedError: utime: follow_symlinks unavailable on this platform`, leaving the
skills manifest partially applied. The user needs the upgrade to apply its managed-skill
writes and converge.

**Why this priority**: This is the released 4.0.0rc4 wheel's behavior on Windows today — the
command is unusable and each failed attempt leaves partial state. It blocks the MVP-launch
milestone for Windows users. It is P1.

**Independent Test**: Simulate a non-`follow_symlinks`-supporting host (mock the
host-detection seam) and drive the managed-skill write path with a regular-file effect;
the write completes and preserves mtime instead of raising.

**Acceptance Scenarios**:

1. **Given** a host where `os.utime` does not support `follow_symlinks`, **When** a
   managed-skill write carrying an mtime executes — a **backup-restore write** (`after`
   copies `before`, so `after.mtime_ns` is set, reaching line 981) or a symlink write —
   **Then** the mtime is applied without raising `NotImplementedError`. (Note: ordinary
   reconcile writes carry `after.mtime_ns=None` and never reach line 981, so the repro must
   use the backup-restore/symlink vector, not a plain reconcile write.)
2. **Given** a host where `os.chmod` does not support `follow_symlinks`, **When** a
   `chmod`-effect write executes via a **non-suppressed** chmod vector (the symlink
   mode-fix at :969 or the symlink-backup chmod at :172 — file-chmod at :963 no longer
   fires once FR-004 suppresses the phantom file chmod), **Then** the mode is applied
   without raising `NotImplementedError`.
3. **Given** the same host, **When** the full crash class is exercised, **Then** none of
   the five sites (`installer.py` 172/174/963/969/981) raises `NotImplementedError`.
4. **Given** a real POSIX host, **When** a symlink effect is applied, **Then** symlink
   semantics are preserved exactly (mode/mtime applied to the link itself, not its target)
   — the fix does not weaken POSIX behavior.

---

### User Story 2 - A converged Windows project reports zero outstanding repairs (Priority: P2)

A Windows user has already run `upgrade` to completion; `doctor tool-surfaces` reports the
project clean (0 missing, 0 stale). They run `spec-kitty upgrade --dry-run` and it reports
"Would repair 184 supporting surface paths" — a phantom count that never decreases, because
every managed file's Windows-representable mode differs from its planned POSIX mode. The
user needs the dry-run to agree with the auditor: a converged project has nothing to repair.

**Why this priority**: The two convergence signals disagree, so a user (or automation) cannot
trust `upgrade` to report a true converged state. It is confusing and erodes confidence in the
upgrade path, but it does not crash or corrupt state, so it is P2 relative to Story 1.

**Independent Test**: Simulate the Windows host so observed file modes are
host-representable but differ from planned POSIX modes; assert the surface planner emits **no**
`chmod` effect for file/symlink kinds whose *only* divergence is the host-unrepresentable
mode, and that `upgrade --dry-run` reports zero supporting-surface repairs on an otherwise
converged project.

**Acceptance Scenarios**:

1. **Given** a simulated Windows host and a converged project, **When** the surface planner
   stages effects, **Then** it emits no `chmod` effect whose sole cause is a
   host-unrepresentable POSIX-mode divergence on a file or symlink.
2. **Given** the same host and project, **When** `spec-kitty upgrade --dry-run` runs, **Then**
   it reports "Would repair 0 supporting surface paths" (consistent with a clean
   `doctor tool-surfaces`), and the count does not change across repeated runs.
3. **Given** a real POSIX host where a genuine mode divergence exists (a file whose mode
   really is wrong), **When** the planner stages effects, **Then** it still emits the
   `chmod` effect — real divergence is not suppressed.

### Edge Cases

- **Symlink effects on Windows**: symlinks are rare and privileged on Windows. The
  measurable requirement is narrow: the symlink branches (:174 utime, :969 chmod) **must not
  raise `NotImplementedError`** on a host lacking `follow_symlinks` support — i.e. the
  host-safe primitive skips the unsupported flag rather than crashing. Beyond "does not
  crash", Windows symlink mode/mtime fidelity is not asserted (untestable without a
  privileged Windows run) and is out of scope.
- **Genuine mode divergence on POSIX**: the mode-divergence suppression is strictly
  host-conditional — on a POSIX host a real `chmod` need is never suppressed.
- **Directory vs file/symlink**: the existing Windows relaxation already covers *directory*
  mode divergence; this mission extends the same host-aware treatment to file/symlink kinds
  without regressing the directory path.
- **Mixed effect batch**: a batch containing a real repair plus a phantom-mode file must
  still apply the real repair and only suppress the phantom one.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Host-safe timestamp/mode application | As a Windows user, I want managed-skill writes to apply mtime and mode without passing a `follow_symlinks` flag the host does not support, so that `upgrade` does not crash. The complete crash class is the five `follow_symlinks=False` chmod/utime sites in `skills/installer.py` — **{172, 174, 963, 969, 981}** — all of which raise `NotImplementedError` on Windows (`os.chmod`/`os.utime` are not in `os.supports_follow_symlinks`). (#4923) | High | Open |
| FR-002 | Close the class through the existing no-follow authority | As a maintainer, I want all five sites made host-safe through the **existing** `kernel.no_follow` authority (co-located with the no-`fchmod` handling already there), so no single missed site can crash the upgrade and no second no-follow authority is minted. The legitimate default-follow `os.utime` at `asset_preservation/backup.py:38` (no flag) is NOT part of the class and must not be swept into the fix or the gate. (#4923, DIRECTIVE_044) | High | Open |
| FR-003 | Preserve symlink semantics on POSIX | As a POSIX user, I want symlink effects to still apply mode/mtime to the link itself (not its target), so that the crash fix does not silently change symlink behavior. | High | Open |
| FR-004 | Suppress host-unrepresentable mode divergence in the project-skill projection | As a Windows user, I want the project-skill projection to emit no `chmod` effect for a file/symlink whose only divergence is a POSIX mode the host cannot represent, so a converged project reports zero repairs. The driver is `skills/installer.py`: the `write()` chmod branch (`elif before.mode != after.mode: action = "chmod"`, ~592–593) comparing the Windows-observed `before.mode` against the **fixed POSIX** `after.mode` computed by `_expected_project_entries` (~725, `S_IMODE(...) & ~0o222`), reached via the canonical/unchanged detection (~785–814). This is NOT `tool_surface/operations.py:_action` (a shared structural classifier used in effect validation) nor `tool_surface/bundles/projection.py:_stage_effect` (the plugin-bundle path, which the upgrade repair does not traverse) — those are explicitly out of scope. (#4927) | High | Open |
| FR-005 | Thread the file/symlink relaxation through the recheck/receipt seams | As a Windows user, I want the same host-aware mode relaxation applied at the completion-recheck/receipt seams (`installer.py:_command_parent_receipts` ~507, `tool_surface/providers/managed_skills.py:_recheck_command_completion` ~181), so that a legitimate managed-skill write on Windows does not fail the post-write recheck with `precondition_changed`/"output changed". Emission-side suppression alone is insufficient. (#4927) | High | Open |
| FR-006 | Dry-run agrees with the auditor on Windows | As a Windows user, I want `upgrade --dry-run` on a converged project to report zero supporting-surface repairs, consistent with `doctor tool-surfaces`, so that convergence is trustworthy. (#4927) | Medium | Open |
| FR-007 | Real divergence is never suppressed | As any user, I want genuine mode divergence (a file whose mode is actually wrong on a host that can represent it) to still produce a repair, so that suppression is strictly host-conditional. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Linux-CI verifiability with a faithful repro | Both fixes are verified without a Windows host, by mocking the host-detection seam (`kernel.paths.is_windows`). For FR-001/002 the repro seam **must raise** on `follow_symlinks=False` (patch `os.utime`/`Path.chmod`, or `os.supports_follow_symlinks`) — because pre-fix code passes the flag *unconditionally* and Linux accepts it, so an `is_windows` flip alone leaves the pre-fix path green. The dir-mode test helper `_simulate_windows_dir_modes` (which patches `Path.chmod` to a **no-op**) MUST NOT be reused for the crash repro: a no-op chmod masks the crash and passes for the wrong reason (DIRECTIVE_041). 100% of new acceptance scenarios run green in the standard Linux CI test tiers. | Testability | High | Open |
| NFR-002 | POSIX behavior preserved | On a real POSIX host, byte-for-byte identical mode/mtime results before and after this change for every existing skill-install/upgrade path; no existing installer/tool-surface test regresses. | Reliability | High | Open |
| NFR-003 | Non-vacuous, precisely-scoped architectural gate | The gate added for FR-002 fails when a new **chmod/utime `follow_symlinks=False`** call-site is introduced into the managed-skill apply surface (proven by a self-mutation test), and is shrink-only against a concrete current-offenders floor. It must NOT flag safe `follow_symlinks` uses (`stat`/`is_file`) or the legitimate default-follow `os.utime` at `backup.py:38`. Reuse the existing `tests/architectural/test_os_detection_ban.py` + `_os_detection_scan.py` + `_exemptions/` shrink-only pattern. | Maintainability | Medium | Open |
| NFR-004 | Quality gates clean | New/changed code passes `ruff`, `ruff format --check`, and `mypy` with zero new issues; every new branch/helper has a focused test in the same commit (Sonar new-code gate); complexity ≤ 15. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical host-safe authority | The host-safe timestamp/mode primitive lives in the **existing** `kernel.no_follow` module (which already owns the no-`fchmod` no-follow handling); call-sites consume it rather than re-implementing the guard, and no second no-follow authority is minted next to `kernel.paths.is_windows`. (DIRECTIVE_044) | Technical | High | Open |
| C-002 | Extend the host-aware relaxation to file/symlink without forking authority | The existing `windows_dir_mode_only_divergence` relaxation (`skills/command_installer.py`) is directory-only **by design**, and `tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py` explicitly pins `file→False` ("file modes are never relaxed"). FR-004 must extend host-aware file/symlink mode-divergence relaxation under the **same authority** — either by generalizing that helper (and updating its now-outdated pinned dir-only assertion per delete-the-assertion-not-the-test, DIRECTIVE_041) or by a coordinated sibling that shares the same host-detection seam. The plan resolves which; a second, independent divergence authority is prohibited. | Technical | High | Open |
| C-003 | Scope boundary | #4925 (`upgrade --yes` exits 1 on a no-op) is out of scope — untraced, not reproducible/red-first-testable on Linux, deferred pending a Windows trace. #4783 (terminology) and #4928 (gitignored-path write) are tracked elsewhere. | Business | High | Open |
| C-004 | Red-first per ADR 2026-07-17-1 | Each defect lands an issue-pinned `@pytest.mark.regression` repro that is RED through the pre-existing entry point before the fix; after the fix the repro is de-marked into a focused unit test. | Process | High | Open |

### Issue Matrix

| Issue | Scope | Verdict slot | Notes |
|-------|-------|--------------|-------|
| #4923 | in-scope | (WP resolves) | utime/chmod `follow_symlinks` crash on Windows (5 sites) — FR-001/002/003 |
| #4927 | in-scope | (WP resolves) | phantom chmod repairs on converged Windows project — FR-004/005/006/007 |
| #4930 | context-only | not-applicable | umbrella verification report; no code owed |
| #4925 | out-of-scope | not-applicable | deferred — untraced, needs a Windows run |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a simulated non-`follow_symlinks` host, the managed-skill write path completes 100% of the time (0 `NotImplementedError`), where it aborts 100% of the time today. (#4923)
- **SC-002**: On a simulated Windows host with a converged project, `upgrade --dry-run` reports exactly 0 supporting-surface repairs, down from 184, and matches `doctor tool-surfaces` (also 0). (#4927)
- **SC-003**: On a real POSIX host, 0 regressions across the installer, skills, and tool-surface test suites — mode/mtime results are unchanged.
- **SC-004**: A self-mutation test proves the FR-002 architectural gate rejects a newly-introduced unguarded `follow_symlinks` call-site (gate is non-vacuous).

## Assumptions

- The host-detection seam `kernel.paths.is_windows` is the canonical way to branch on host, and is patchable at call time in tests (established pattern, exercised by `tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py`).
- Fixing FR-004 (phantom-effect suppression) also drains the phantom effects that reach the FR-001 crash on a converged Windows project; the two fixes are complementary, not conflicting.
- The 184 count is exactly the plan's `chmod` count on the reporter's project; the mechanism (mode divergence per canonical project-skill file) is general, so the fix is validated by the mechanism, not the specific number. Command skills do not phantom-chmod (`command_installer.install_command` reuses the observed `before.mode`), so #4927's driver is confined to the canonical project-skill projection in `installer.py`.
- **FR-004 may newly surface #4925.** Once the phantom chmods are suppressed, a converged Windows `upgrade` becomes a genuine zero-effect no-op — precisely #4925's precondition (`--yes` exits 1 on a no-op). #4925 stays deferred (C-003), but the two are *sequentially related*, not independent: this fix is expected to make #4925 cleanly reproducible on Windows, which is why re-verification there is the deferred follow-up.
