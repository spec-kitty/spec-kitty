---
work_package_id: WP01
title: 'Host-safe Windows upgrade: close the follow_symlinks crash class + suppress phantom mode divergence'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: fix/windows-upgrade-mode-fidelity
merge_target_branch: fix/windows-upgrade-mode-fidelity
branch_strategy: Planning artifacts for this mission were generated on fix/windows-upgrade-mode-fidelity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/windows-upgrade-mode-fidelity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-windows-upgrade-mode-fidelity-01M35C25
base_commit: 53b60864ac417c47d4a7f31647e4f3c0f41ff10a
created_at: '2026-09-22T20:40:38.271931+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
history:
- event: created
  at: '2026-09-22T20:31:49Z'
  note: Initial generation from /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/skills/
create_intent:
- tests/architectural/test_no_follow_symlinks_apply_ban.py
- tests/architectural/_exemptions/no_follow_symlinks_apply.txt
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/kernel/no_follow.py
- src/specify_cli/skills/installer.py
- src/specify_cli/skills/command_installer.py
- src/specify_cli/tool_surface/providers/managed_skills.py
- tests/specify_cli/skills/test_installer.py
- tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py
- tests/architectural/test_no_follow_symlinks_apply_ban.py
- tests/architectural/_exemptions/no_follow_symlinks_apply.txt
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Host-safe Windows upgrade

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field (via `spec-kitty agent tasks status`) before starting. Address every feedback item before claiming done.

## Objective

Make `spec-kitty upgrade` behave correctly on Windows, where filesystems cannot carry POSIX
file modes. Two coupled defects, in two phases:

- **Phase A (#4923)** — `spec-kitty upgrade` crashes on Windows with
  `NotImplementedError: utime: follow_symlinks unavailable on this platform`. Close the whole
  class of `follow_symlinks=False` chmod/utime calls in the skill installer through the
  existing `kernel.no_follow` authority, and guard it with a non-vacuous architectural gate.
- **Phase B (#4927)** — on a converged Windows project, `upgrade --dry-run` reports "Would
  repair 184 supporting surface paths" while `doctor tool-surfaces` is clean, because every
  managed file's Windows-representable mode differs from its planned POSIX mode. Extend the
  host-aware mode-divergence relaxation to file/symlink kinds so no phantom `chmod` is emitted,
  and thread it through the recheck seams.

**Do Phase A first.** Once Phase B suppresses the file chmod, the `:963` crash vector stops
firing — so Phase A's crash repro must land on a still-live vector first (see T003/F7).

## Context

**Mission**: `windows-upgrade-mode-fidelity-01M35C25` (folds GitHub #4923 + #4927; #4925 deferred).

Read `spec.md`, `plan.md`, and `research.md` in the mission dir first — `research.md` records
the verified root cause and every adversarial finding's disposition. Key verified facts:

- On Windows, `os.utime`/`os.chmod` are **not** in `os.supports_follow_symlinks`, so
  `follow_symlinks=False` raises `NotImplementedError`. Linux *accepts* the flag, so a repro
  that only flips `is_windows` will NOT reproduce the crash — the repro seam must actually
  raise (see T003).
- The canonical default-follow pattern for regular files is `asset_preservation/backup.py:38`
  (`os.utime(dest, ns=...)`, no flag). That call is **legitimate** and must NOT be swept into
  the fix or flagged by the gate.
- `kernel.no_follow` already owns the no-`fchmod` no-follow handling (`chmod_fd`, etc.) — it is
  the canonical home for the new host-safe helpers. Do **not** mint a new helper elsewhere.

## Phase A — #4923: close the crash class

### T001 — Host-safe helpers in `kernel.no_follow`

**Purpose**: One canonical authority for "apply mode/mtime, skipping an unsupported
`follow_symlinks` flag" — so every call-site consumes it instead of re-guarding.

**Steps**:
1. In `src/kernel/no_follow.py`, add a host-safe `utime` helper, e.g.
   `utime_no_follow(path, *, ns)` — apply `os.utime(path, ns=ns, follow_symlinks=False)` when
   `os.utime in os.supports_follow_symlinks`, else fall back to `os.utime(path, ns=ns)`
   (default follow). For a regular file the two are equivalent; the guard only matters for a
   symlink target on a host that supports the flag.
2. Add a host-safe path-`chmod` helper, e.g. `chmod_no_follow(path, mode)` — same guard shape
   against `os.chmod in os.supports_follow_symlinks`.
3. Preserve POSIX symlink semantics: on a host that supports the flag, still pass
   `follow_symlinks=False` so mode/mtime land on the link itself (FR-003). The fallback only
   applies where the host cannot represent it.
4. Keep the helpers small (complexity ≤ 15); add module docstring rationale referencing #4923.

**Files**: `src/kernel/no_follow.py`.

### T002 — Migrate the five installer sites

**Purpose**: Route all five `follow_symlinks=False` sites through the T001 helpers.

**Steps**: In `src/specify_cli/skills/installer.py`, replace at each site:
- `172` `backup_path.chmod(before.mode, follow_symlinks=False)` → `chmod_no_follow(...)`
- `174` `os.utime(backup_path, ns=..., follow_symlinks=False)` → `utime_no_follow(...)`
- `963` `path.chmod(after.mode, follow_symlinks=False)` → `chmod_no_follow(...)`
- `969` `path.chmod(after.mode, follow_symlinks=False)` → `chmod_no_follow(...)`
- `981` `os.utime(path, ns=..., follow_symlinks=False)` → `utime_no_follow(...)`

Line numbers are guidance — grep `follow_symlinks` in the file and convert exactly these five
(chmod/utime), leaving safe `stat`/`is_file`/`lstat` uses untouched.

**Files**: `src/specify_cli/skills/installer.py`.

### T003 — Red-first repro for #4923 (must RAISE)

**Purpose**: Prove the crash through the pre-existing entry point before the fix, and prove the
fix removes it — without passing for the wrong reason.

**Steps**:
1. In `tests/specify_cli/skills/test_installer.py`, add `@pytest.mark.regression` test(s) pinned
   to #4923. Simulate the Windows host by making the flag unsupported: patch
   `os.supports_follow_symlinks` to exclude `os.utime`/`os.chmod`, OR patch `os.utime`/`Path.chmod`
   to raise `NotImplementedError` when called with `follow_symlinks=False`. Do **NOT** reuse
   `_simulate_windows_dir_modes` (it patches `Path.chmod` to a no-op, which masks the crash).
2. Drive the managed-skill write path: an **mtime-carrying** vector for the utime crash
   (backup-restore write, where `after` copies `before` so `after.mtime_ns` is set and line 981
   is reached; or a symlink write). For the chmod crash use a **non-suppressed** vector (:172
   symlink-backup chmod or :969 symlink mode-fix) — not the :963 file chmod, which Phase B
   removes.
3. Assert the test is RED (raises `NotImplementedError`) before T001/T002, and GREEN after.

**Files**: `tests/specify_cli/skills/test_installer.py`.

### T004 — Non-vacuous architectural gate

**Purpose**: Close the class by construction so no new unguarded call-site can reappear.

**Steps**:
1. Add `tests/architectural/test_no_follow_symlinks_apply_ban.py` modeled on the existing
   `tests/architectural/test_os_detection_ban.py` + `_os_detection_scan.py` + `_exemptions/`
   shrink-only pattern. Scope the scan to **chmod/utime calls with `follow_symlinks=False`** in
   the managed-skill apply surface (`src/specify_cli/skills/`, `src/specify_cli/tool_surface/`).
2. Do NOT flag safe `follow_symlinks` uses (`stat`/`is_file`) or the legitimate default-follow
   `os.utime` at `asset_preservation/backup.py:38`.
3. Seed `tests/architectural/_exemptions/no_follow_symlinks_apply.txt` with the concrete current
   floor (ideally empty after T002) — shrink-only.
4. Include a **self-mutation test**: assert the gate fails when a synthetic unguarded call-site
   is introduced (proves non-vacuity, NFR-003).

**Files**: `tests/architectural/test_no_follow_symlinks_apply_ban.py`, `tests/architectural/_exemptions/no_follow_symlinks_apply.txt`.

## Phase B — #4927: suppress phantom mode divergence

### T005 — Extend the host-aware relaxation to file/symlink

**Purpose**: The existing `windows_dir_mode_only_divergence` (`src/specify_cli/skills/command_installer.py`)
relaxes host-unrepresentable mode divergence for **directories only**. Generalize it to
file/symlink kinds under the same authority (C-002 — do not fork a second divergence authority).

**Steps**:
1. Generalize the helper (or add a coordinated sibling sharing the same `kernel.paths.is_windows`
   seam) so it returns True when the sole divergence between observed and planned state is a
   POSIX mode the host cannot represent — for file and symlink kinds, not just directory.
2. Keep it strictly host-conditional: on a POSIX host it must never relax a genuine mode
   divergence (FR-007).

**Files**: `src/specify_cli/skills/command_installer.py`.

### T006 — Apply the relaxation at the project-skill projection

**Purpose**: Stop the phantom `chmod` at its source — the `installer.py` project-skill projection.

**Steps**:
1. At the `write()` chmod branch (`elif before.mode != after.mode: action = "chmod"`, ~592-593),
   consult the T005 relaxation before emitting a `chmod` effect: when the only divergence is a
   host-unrepresentable POSIX mode (Windows-observed `before.mode` vs the fixed POSIX
   `after.mode` from `_expected_project_entries`, ~725), do not emit the effect.
2. Verify against the canonical/unchanged detection (~785-814) so a converged file yields no
   effect at all on Windows.

**Files**: `src/specify_cli/skills/installer.py`.

### T007 — Thread the relaxation through the recheck/receipt seams + fix pinned assertion

**Purpose**: Emission-side suppression alone is insufficient — the recheck seams reject
file-mode divergence and would fail a legitimate Windows write with `precondition_changed`.

**Steps**:
1. Apply the same host-aware relaxation at `installer.py:_command_parent_receipts` (~507) and
   `src/specify_cli/tool_surface/providers/managed_skills.py:_recheck_command_completion` (~181),
   so a real managed-skill write on Windows does not trip "Completed command output changed".
2. `tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py` pins
   `windows_dir_mode_only_divergence(file→False)` ("file modes are never relaxed"). That
   assertion is now outdated — update it to reflect file/symlink relaxation on Windows
   (delete-the-assertion-not-the-test: change the assertion because the contract changed, do not
   delete the whole test).

**Files**: `src/specify_cli/skills/installer.py`, `src/specify_cli/tool_surface/providers/managed_skills.py`, `tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py`.

### T008 — Red-first repro for #4927

**Purpose**: Prove the phantom count on a converged simulated-Windows project, and that the fix
drives it to zero, consistent with the auditor.

**Steps**:
1. Add `@pytest.mark.regression` test(s) pinned to #4927. Simulate Windows via `kernel.paths.is_windows`
   so observed file modes are host-representable but differ from planned POSIX modes.
2. Assert (RED before T005-T007): the projection emits a `chmod` effect per managed file (a
   non-zero supporting-surface repair count) while the auditor is clean.
3. Assert (GREEN after): zero supporting-surface repairs, stable across repeated runs, matching
   a clean `doctor tool-surfaces`. Add a POSIX-host assertion that a genuine mode divergence
   still emits a chmod (FR-007).

**Files**: `tests/specify_cli/skills/test_installer.py` (and/or the tool_surface host-aware test).

### T009 — De-mark repros; run the blast radius

**Purpose**: Transitional repros become focused unit tests once green (never left `regression`);
prove no POSIX regression.

**Steps**:
1. Convert the T003/T008 repros from `@pytest.mark.regression` into focused unit tests in their
   proper home once passing.
2. Run and record (per §6 test policy):
   - `.venv/bin/python -m pytest tests/specify_cli/skills/ tests/specify_cli/tool_surface/ -q`
   - `.venv/bin/python -m pytest tests/architectural/test_no_follow_symlinks_apply_ban.py tests/architectural/test_os_detection_ban.py -q`
   - `make test-fast`
   - `uv run --frozen ruff check <changed> && uv run --frozen ruff format --check <changed>` and `mypy` on changed modules.

## Branch Strategy

Planning happened on `fix/windows-upgrade-mode-fidelity`. `spec-kitty implement WP01` materializes
this WP in its computed lane worktree (from `lanes.json`); completed changes merge back into
`fix/windows-upgrade-mode-fidelity`. The mission PR targets upstream `main`. Do not branch from
or merge to any other ref without explicit operator redirection.

## Definition of Done

- [ ] All five installer `follow_symlinks=False` chmod/utime sites route through `kernel.no_follow` (FR-001/002).
- [ ] POSIX symlink semantics preserved (FR-003); no existing installer/tool-surface test regresses (NFR-002).
- [ ] Converged simulated-Windows project emits zero supporting-surface repairs; dry-run matches `doctor tool-surfaces` (FR-004/005/006).
- [ ] Genuine POSIX mode divergence still produces a repair (FR-007).
- [ ] Non-vacuous, shrink-only arch gate with a self-mutation proof; excludes safe/legit sites (NFR-003).
- [ ] Both defects have a red-first repro that raised for the right reason pre-fix (C-004, NFR-001); repros de-marked post-fix.
- [ ] ruff/format/mypy clean on changed code; new branches/helpers have focused tests; complexity ≤ 15 (NFR-004).
- [ ] `## Tests run` recorded with commands + pass/fail counts.

## Reviewer guidance

Verify the crash repro actually RAISES pre-fix (not a no-op mock). Verify the gate fails under
self-mutation (non-vacuous) and does not flag `backup.py:38`. Verify FR-007 (real POSIX
divergence not suppressed). Confirm the pinned dir-only assertion was updated because the
contract changed, not deleted to go green.

## Activity Log

- 2026-09-22: WP created from /spec-kitty.tasks.
