---
work_package_id: WP02
title: Run-wide charter synthesis lock
dependencies: []
requirement_refs:
- FR-002
- FR-003
- FR-011
- NFR-001
- NFR-003
- C-001
- C-002
- C-006
- SC-002
planning_base_branch: issue-6453-synthesis-record-integrity
merge_target_branch: issue-6453-synthesis-record-integrity
branch_strategy: Planning artifacts for this mission were generated on issue-6453-synthesis-record-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6453-synthesis-record-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-synthesis-record-integrity-01M5ZBC9
base_commit: 7beb0a62ac09a6ebf679ae660c60cdb6c57de5b6
created_at: '2026-10-27T19:27:07.486429+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Remediation
history:
- at: '2026-10-27T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/synthesis_lock.py
create_intent:
- src/charter/activation/synthesizer/synthesis_lock.py
- tests/charter/synthesizer/test_synthesis_lock.py
- tests/charter/synthesizer/test_synthesis_lock_cli.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/synthesizer/synthesis_lock.py
- src/charter/activation/api.py
- src/charter/activation/bundle_restamp.py
- src/specify_cli/cli/commands/charter/synthesize.py
- src/specify_cli/cli/commands/charter/resynthesize.py
- tests/charter/synthesizer/test_synthesis_lock.py
- tests/charter/synthesizer/test_synthesis_lock_cli.py
- tests/architectural/test_charter_activation_api_reexport.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Run-wide charter synthesis lock

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission synthesis-record-integrity-01M5ZBC9`).
- Address all feedback before your work is complete; record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Issue #6453: no charter/synthesis lock exists; concurrent `charter synthesize` / `charter resynthesize` runs interleave their writes. Operator decisions: run-wide lock per worktree in the git common dir (DM `01M5ZBD3K8FQQZ2KFANYVMX0JZ`); ~10 s wait then refuse with `CHARTER_SYNTHESIS_LOCK_HELD`, nothing written (DM `01M5ZBERXGAS37DZCNTPG1WMC0`); `restamp_bundle_hash` also takes it, other activation writers deferred to #6719 (DM `01M5ZCGGF4N7SWFM9MZF8Y4SBF`).

Done when:
- FR-002: a writing synthesize/resynthesize run holds the lock from just after `assert_charter_yaml_sound` to the end of the command; `--dry-run`, `--dry-run-evidence`, `--list-topics` take no lock.
- FR-003 / NFR-001: a run that cannot get the lock within the configured wait exits 1 with `CHARTER_SYNTHESIS_LOCK_HELD` naming the lock file; nothing is written (overlay, manifest, record, directive files byte-identical).
- FR-011: `restamp_bundle_hash` takes the lock (re-entrant).
- C-001: only `kernel.locks` is used (gate `tests/architectural/test_lock_primitive_ban.py`).
- C-002: `specify_cli` imports the lock only via `charter.activation.api`.

## Context & Constraints

- Spec US1, FR-002/003/011, NFR-001, C-001/002/006; plan IC-02 and "Design notes"; data-model "Synthesis lock".
- Placement precedent: `src/kernel/event_log_append.py:133-169` (`event_log_lock_path`, `event_log_lock`): `anchor.resolve()`, `git_common_dir`, `NotAGitRepositoryError` fallback, `GitTopologyUnavailableError` → named error, `sha256_digest(os.path.normcase(str(resolved)).encode())`, `[:32]`, `LOCK_DIRECTORY`, `LockAcquireTimeout` → named timeout error.
- Lock primitive: `kernel.locks.machine_file_lock(path, blocking=True, timeout_s=..., reentrant=True)` (`src/kernel/locks.py`); re-entrancy is thread-local and keyed on the resolved lock path.
- Error base: `kernel.errors.KittyInternalConsistencyError(code, body)`; both commands already render it with its code and exit 1 (`synthesize.py:713-735` incl. `--json` envelope with `"code"`; `resynthesize.py:275-279`).
- Charter: every module under `src/charter/` declares `__all__` (C-007); complexity ≤ 15; no new `noqa`/`type: ignore`.

## Branch Strategy

- **Planning base branch**: issue-6453-synthesis-record-integrity
- **Merge target branch**: issue-6453-synthesis-record-integrity

Execution worktrees are allocated per computed lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T006 – `synthesis_lock.py`

- **File**: `src/charter/activation/synthesizer/synthesis_lock.py` (new), with `__all__`.
- **Contents**:
  - `SYNTHESIS_LOCK_SUBDIRECTORY = "charter-synthesis"`, `SYNTHESIS_LOCK_TIMEOUT_S = 10.0`, `NON_GIT_LOCK_PATH = Path(".kittify/runtime/locks/charter-synthesis.lock")`.
  - `class SynthesisLockHeldError(KittyInternalConsistencyError)` code `CHARTER_SYNTHESIS_LOCK_HELD`; body names the lock file, says another `spec-kitty charter synthesize`/`resynthesize` run in this worktree holds it and nothing was written, and to retry after it finishes.
  - `class SynthesisLockUnavailableError(KittyInternalConsistencyError)` code `CHARTER_SYNTHESIS_LOCK_UNAVAILABLE` (git could not be invoked; make git runnable, then retry).
  - `synthesis_lock_path(repo_root: Path) -> Path` — resolved root; git → `<common>/<LOCK_DIRECTORY>/charter-synthesis/<digest>.lock`; no git → `repo_root / NON_GIT_LOCK_PATH`.
  - `@contextmanager synthesis_lock(repo_root: Path, *, timeout_s: float | None = None) -> Iterator[Path]` — `machine_file_lock(path, blocking=True, timeout_s=SYNTHESIS_LOCK_TIMEOUT_S if timeout_s is None else timeout_s, reentrant=True)`; `LockAcquireTimeout` → `SynthesisLockHeldError`. Read the module constant at call time (so tests can monkeypatch it).
- **Unit tests** (`tests/charter/synthesizer/test_synthesis_lock.py`): path in a git repo (under common dir, stable digest, symlinked root resolves to same path); non-git fallback path; git unusable → `SynthesisLockUnavailableError` (monkeypatch `git_common_dir`); spy on `machine_file_lock` asserting `blocking=True, timeout_s=10.0, reentrant=True`; same-thread re-entry does not deadlock; another thread holding it → `SynthesisLockHeldError` with a small injected timeout; crashed holder: a subprocess (`sys.executable -c`) acquires and `os._exit(0)`s, then acquiring succeeds; two worktree roots of one repository (`git worktree add`) get different lock paths.

### Subtask T007 – Export

- Add `synthesis_lock`, `SynthesisLockHeldError`, `SynthesisLockUnavailableError` to `src/charter/activation/api.py` imports and `__all__` (keep its existing style/order).
- The surface gate `tests/architectural/test_charter_activation_api_reexport.py` requires `_SEAM_TABLE == api.__all__`: add rows `("synthesis_lock", "charter.activation.synthesizer.synthesis_lock")`, `("SynthesisLockHeldError", ...)`, `("SynthesisLockUnavailableError", ...)` and run that gate.

### Subtask T008 – Restamp under the lock

- `src/charter/activation/bundle_restamp.py`: wrap the read-modify-write of `restamp_bundle_hash` in `synthesis_lock(repo_root)` (after the cheap `is_file()` early return is fine; the read must be inside). Re-entrant, so the call from `reach_only.append_synthesized_activations` inside a CLI run nests. Test: another thread holding the lock makes `restamp_bundle_hash` raise `SynthesisLockHeldError` with an injected short timeout and leaves the manifest unchanged; lock free → restamps (positive control). Put the new restamp tests in `tests/charter/synthesizer/test_synthesis_lock.py`. Existing restamp tests stay green.
- **Blast radius (callers that now take the lock and can raise the two new errors):** `pack_manager.py:1127`, `:1218`; `preset_application.py:708`; `compiler.py:623`; `org_charter.py:489`; `cli/commands/charter/interview.py:215`; `legacy_rename.py:477` (catches only `_READ_ERRORS`); migration `m_4_0_0rc8_promote_interview_selections.py:362`. No code change expected there (both errors are `KittyInternalConsistencyError`, rendered by the CLI); confirm with `tests/charter/test_activate_restamps_bundle_hash.py`, `tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py`, `tests/charter/test_pack_manager.py`, `tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py` (out-of-matrix: run locally).

### Subtask T009 – CLI wiring

- `src/specify_cli/cli/commands/charter/synthesize.py`: right after `assert_charter_yaml_sound(repo_root)` (~`:223`), and before `_converge_legacy_project_intent_directive` (~`:228`), enter the lock unless `dry_run or dry_run_evidence`; hold to the end of the command body (covers the fresh-project seed path ~`:252-300`, `synthesize()`, the activation append).
- `src/specify_cli/cli/commands/charter/resynthesize.py`: same, after `assert_charter_yaml_sound` (`:110`, before the convergence at `:112`), unless `list_topics`.
- Both bodies already carry `# noqa: C901`: use a `contextlib.ExitStack` created around the existing `try` (or a tiny helper `_hold_synthesis_lock(stack, repo_root, *, read_only)`) so no new branch lands in the body. Do NOT add new suppressions. Import from `charter.activation.api` only.
- The existing `except KittyInternalConsistencyError` branches render the refusal; confirm the `--json` envelopes carry the code.

### Subtask T010 – CLI tests

- New `tests/charter/synthesizer/test_synthesis_lock_cli.py`. Reuse fixtures/helpers from the existing synthesize/resynthesize CLI tests (find them: `grep -rln "charter.*synthesize" tests/charter tests/specify_cli`), e.g. the `charter_cwd_isolation` fixture used by `test_synthesize_activation_append.py`.
- Hold the lock **from another thread** (same-thread re-entry would make the test vacuous), monkeypatch `SYNTHESIS_LOCK_TIMEOUT_S` to `0.2`:
  - `charter synthesize` exits 1, output contains `CHARTER_SYNTHESIS_LOCK_HELD` and the lock path; snapshot bytes of `.kittify/charter/` and the project pack root before/after are identical.
  - Positive control on the same fixture with the lock free: exit 0 and files written.
  - `--json`: envelope `result == "failure"` and `code == "CHARTER_SYNTHESIS_LOCK_HELD"`.
  - `charter synthesize --dry-run`, `charter synthesize --dry-run-evidence` and `charter resynthesize --list-topics` complete while the lock is held.
  - `charter resynthesize --topic <t>` refuses with the code.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/synthesizer/test_synthesis_lock.py tests/charter/synthesizer/test_synthesis_lock_cli.py tests/charter/synthesizer/ -q
uv run --frozen pytest tests/architectural/test_lock_primitive_ban.py tests/architectural/test_charter_activation_api_reexport.py -q
uv run --frozen pytest tests/charter/test_activate_restamps_bundle_hash.py tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py tests/charter/test_pack_manager.py tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py -q
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy <touched src files>
```

## Risks & Mitigations

- Vacuous same-thread tests → hold from another thread; always pair with a lock-free positive control.
- No test waits 10 s → monkeypatch the constant.
- A test fixture that is not a git repo → exercises the `.kittify/runtime/locks/` fallback; make sure the dir is created (`kernel.locks` `_ensure_dir`).

## Review Guidance

- Lock taken before the legacy convergence and held to the end; read-only modes skip it.
- No raw lock primitive; no new `noqa`; `__all__` present.
- Refusal leaves files byte-identical (test proves it).

## Progress & Status

Use `spec-kitty agent tasks add-history WP02 --note "..."`, `mark-status`, and `spec-kitty agent tasks status`.
