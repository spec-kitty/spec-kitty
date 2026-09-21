---
work_package_id: WP06
title: Credential write-safety
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-011
planning_base_branch: fix/local-write-safety
merge_target_branch: fix/local-write-safety
branch_strategy: Planning artifacts for this mission were generated on fix/local-write-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/local-write-safety unless the human explicitly redirects the landing branch.
subtasks:
- T019
- T020
- T021
history:
- at: '2026-09-20T16:18:00Z'
  by: claude
  note: Authored by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/zeitgeist_client/
create_intent:
- tests/unit/test_credential_write_safety.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/zeitgeist_client/credentials.py
- src/specify_cli/tracker/credentials.py
- src/specify_cli/paths/windows_paths.py
- tests/unit/test_credential_write_safety.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load` (+ `charter context --action implement`); apply and state.

## Objective
Close the "credential 0600-by-construction" class on **both** plaintext-secret transports and
retire zeitgeist's competing runtime-root chmod ladder so `~/.spec-kitty = 0700` has a single owner.

## Context
- `tracker/credentials.py:~130` writes the token with `write_text` then `os.chmod(0o600)` → a 0644 exposure window (#4760).
- `zeitgeist_client/credentials.py:~262` uses `os.open(..., O_CREAT|O_TRUNC, 0o600)` (0600 ok) but **no `O_NOFOLLOW`** (#4812), and hand-rolls a 3-level `chmod(0o700)` ladder at `:220-224` on the runtime root.
- Depends on **WP01** (consume the canonical `kernel.no_follow` helper; `O_EXCL` is appropriate here — fresh temp, unlike the persistent lock).
- **Class boundary**: in scope = zeitgeist + tracker (plaintext-secret transports). Auth session-blob/salt (`auth/secure_storage/file_fallback.py:278/:136`, `auth/session_hot_path.py:137`) are deliberately **out** (ciphertext / non-secret, read-side 0600 verification) — do not touch.
- See `../research.md` D7.

## Subtasks

### T019 — tracker credentials 0600-by-construction
- Replace `write_text`+`chmod` with `os.open(path, O_CREAT|O_EXCL|O_WRONLY, 0o600)` (via the canonical helper) so the file is owner-only from creation — no world-readable window.

### T020 — zeitgeist no-follow + retire the 0700 ladder into a single root owner
- Add `O_NOFOLLOW` (via the helper) to the temp write. Retire the hand-rolled 3-level `chmod(0o700)` ladder (`:219-224`). Establish `~/.spec-kitty = 0700` through **one** canonical owner: put/keep the root-0700 establishment in `get_runtime_root()` (`src/specify_cli/paths/windows_paths.py`) so WP02/WP07 consume it read-only rather than each self-establishing 0700 (avoids the FR-011 split-brain). If the ladder must stay, record a real rationale (not a one-line dodge).

### T021 — Create-mode proof (structural + interception — NOT a post-hoc stat)
- **Do not** assert "final mode == 0600" after the write: tracker's buggy `write_text`+`chmod` already ends at 0600, so a post-hoc stat is green on the bug and cannot be red-first. Instead, for **both** transports prove the *creation* mode:
  - **Structural**: assert the create goes through `os.open(..., O_CREAT|O_EXCL|O_WRONLY, 0o600)` (via the helper) **and** spy `os.chmod` to assert it is **not** called on the credential path after the write (no post-hoc narrowing).
  - **Interception**: monkeypatch/​spy `os.open` to capture the *creation* mode argument and assert it is `0o600`.
- Assert a symlink planted at the temp/target path is refused. Isolated HOME. Capture the red run (tracker fails the `chmod`-not-called assertion today).

## Branch Strategy
Base/merge `fix/local-write-safety`. Depends on WP01. `spec-kitty agent action implement WP06 --agent claude`.

## Definition of Done (non-fakeable)
- Both transports proven **0600-at-creation** via the create-mode structural + interception checks (O_CREAT|O_EXCL|0600 + `os.chmod` asserted-not-called on the cred path) — a post-hoc final-mode stat is explicitly rejected (SC-005).
- Symlink-plant refused on both paths (SC-001).
- Root-0700 has a **single owner** (`get_runtime_root`); WP02/WP07 consume it — no per-file re-establishment. Ladder retired, or a real recorded rationale.
- Auth writers untouched (out of class, documented).
- **Red-first evidence**: PR "Tests run" includes the failing-on-buggy-code output (tracker `chmod`-not-called assertion) so red-first is verifiable.
- Isolated HOME. ruff + mypy clean; complexity ≤15.

## Risks & Reviewer Guidance
- **Risk**: a chmod-after-write survives somewhere. Reviewer: confirm no `write_text`/`write_bytes`+`chmod` remains on a credential path in the two files.
- **Risk**: re-litigating `file_fallback:278`. Reviewer: it is out of scope by the stated class boundary.
