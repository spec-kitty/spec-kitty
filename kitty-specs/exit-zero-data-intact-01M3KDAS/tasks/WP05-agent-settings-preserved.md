---
work_package_id: WP05
title: Agent settings file is never replaced (#4940)
dependencies:
- WP01
requirement_refs:
- FR-011
- FR-012
- FR-013
- FR-014
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-exit-zero-data-intact-01M3KDAS
base_commit: 45785d2ddc06e9cc4b11d3b806fb7a4b0ce606ac
created_at: '2026-09-28T11:25:51.249424+00:00'
subtasks:
- T023
- T024
- T025
- T026
- T027
- T028
- T029
phase: Phase 3 - Encoding-dependent fixes
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/session_presence/hooks/
create_intent:
- tests/specify_cli/session_presence/test_settings_encoding_4940.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/session_presence/hooks/claude_code_hook.py
- src/specify_cli/session_presence/writers/claude_code.py
- src/specify_cli/tool_surface/providers/session_presence.py
- src/specify_cli/cli/commands/agent/config.py
- src/specify_cli/live_work/install.py
- tests/specify_cli/session_presence/test_settings_encoding_4940.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Agent settings file is never replaced (#4940)

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/ad-hoc-profile-load` (role `implementer`, agent `claude`); then `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Feedback items are your TODO list.

---

## Objectives & Success Criteria

Issue #4940: `ClaudeCodeHookRegistrar._load` (`session_presence/hooks/claude_code_hook.py:~137-160`) does `path.read_text(encoding="utf-8")` inside `except (OSError, UnicodeDecodeError): return {}` — **before** the `preserve_invalid` backup branch. `register()` then saves a lint-only file over the user's settings. The issue's trigger is a cp1252/Latin-1 file (`"OWNER": "José"` saved by a Windows ANSI editor); UTF-16 files are lost the same way. Result: permissions (incl. deny rules), env, the user's hooks and Spec Kitty's own `SessionStart`/`Stop` hooks are gone, no backup, exit 0 `✓ Sync complete`.

Operator policy (Decision Moment `01M3KDD2GHGFS7J5616ZNQHE6Y`): decode **only provable** encodings (strict UTF-8, or a BOM for UTF-8/UTF-16/UTF-32). Never guess (no cp1252 detection). Anything else: leave the file byte-identical and fail non-zero.

Done means (FR-011–FR-014, contract table):
- FR-011: UTF-8-BOM and UTF-16 (BOM) settings files: every user entry and Spec Kitty session hooks preserved; new hook added.
- FR-012: before a file whose source encoding is not plain UTF-8 is rewritten (as UTF-8), its original bytes are kept via `asset_preservation.backup.backup_before_overwrite` (byte-exact `<path>.<timestamp>` sidecar).
- FR-013: the issue's cp1252 bytes → file byte-identical, exit 1, message names the file and says to re-save as UTF-8 — via `agent config sync --sync-hooks` AND `live-work install`.
- FR-014: every reader in the registrar (`_load` for `is_registered`/`register`/`unregister`, and `prepare_commands`/`apply_prepared` for the init/upgrade writer) uses `kernel.text_decode.decode_unambiguous` (from WP01).

## Context & Constraints

- Plan design decision **D6**; research **R4**; contract `contracts/failure-surface.md` row "agent config sync --sync-hooks, live-work install".
- `SettingsNotDecodableError` subclasses `kernel.errors.GuardedReadError` (kw-only `path: str | None`, `reason: str | None` — pass `path=str(path)`; `kernel/errors.py:~58`) and is defined **in `claude_code_hook.py`** (no new module). The root CLI hook `_run_app_with_error_hook` (`specify_cli/__init__.py:~451`) maps it to exit 1. **`CliRunner` bypasses that hook** → assert `result.exit_code != 0` and `isinstance(result.exception, SettingsNotDecodableError)`, or run a subprocess for the true exit code.
- Do NOT reuse `_preserve_invalid` for the re-encode backup — it writes decoded *text*, not bytes. Keep `_preserve_invalid` exactly as-is for the invalid-JSON / non-object path (a UTF-8-BOM file with invalid JSON must still get `settings.json.invalid.<uuid>`).
- Probes: `tool_surface/providers/session_presence.py:~712` (read-only doctor probe) must catch `SettingsNotDecodableError` and report the file as undecodable in its finding instead of a traceback. `session_presence/writers/claude_code.py:~85-90` `has_presence` returns `bool` and feeds the `m_3_3_0_session_presence_claude_code` migration's `detect` (False → `apply` → `prepare_commands`): it must **propagate** `SettingsNotDecodableError` (never return False on decode failure), so `spec-kitty upgrade` refuses non-zero with the file untouched and does not report that migration as successful. Mutating paths (register, unregister, apply_prepared) refuse non-zero.
- `is_registered` must NOT return False on decode failure (that would let `register` overwrite).
- Out of scope (follow-ups): `live_work/capability.py:322`, `agent/config.py` `_load_cursor_hooks`.

## Branch Strategy

- **Strategy**: lanes · **Planning base**: `claude/milestone-11-research-0rnnr4` · **Merge target**: `claude/milestone-11-research-0rnnr4`. Depends on WP01: `spec-kitty implement WP05` (the lane is based so `kernel.text_decode` is available; verify `python -c "import kernel.text_decode"` in the workspace first).

## Subtasks & Detailed Guidance

### Subtask T023 – Campsite + error type

- Read `claude_code_hook.py` end to end; fix any ruff/mypy findings in functions you touch (none known today). Define `SettingsNotDecodableError(GuardedReadError)` with a clear `reason`: "not valid UTF-8 and has no byte-order mark; re-save it as UTF-8". Separate commit.

### Subtask T024 – Red-first repros (`tests/specify_cli/session_presence/test_settings_encoding_4940.py`)

Mark `@pytest.mark.regression`; confirm FAIL; record. Fixture content (dict → bytes): `permissions.allow`, `permissions.deny: ["Read(./.env)"]`, `env: {"OWNER": "José"}`, a user `PreToolUse` hook, Spec Kitty `SessionStart` + `Stop` hooks. Encodings: (a) UTF-8-BOM, (b) UTF-16 with BOM (`"﻿"+json` encoded `utf-16-le`, and BE), (c) cp1252 (`json.dumps(..., ensure_ascii=False).encode("cp1252")`).

1. `spec-kitty agent config set lint_on_edit true` then `spec-kitty agent config sync --sync-hooks` (`_sync_claude_hooks` is at `cli/commands/agent/config.py:~736-757`, register ~:748, unregister ~:751, called ~:727; `✓ Sync complete` is printed at ~:705 after the hook sync, so propagation suppresses it) (CLI, scratch repo after `init --ai claude --non-interactive` — copy the setup from the issue's reproduction or `tests/specify_cli/cli/commands/test_lint_hooks.py`):
   - (a)/(b): all entries present after sync + lint hook added; a `settings.json.<timestamp>` byte-identical backup exists for (b) (and for (a), since it's not plain UTF-8).
   - (c): file bytes unchanged, non-zero exit, message names `.claude/settings.json`.
2. `spec-kitty live-work install claude` (and `spec-kitty live-work uninstall claude`; `HARNESS` is a required argument) with (c) → unchanged, non-zero. Note: uninstall with (c) is already byte-identical today (it no-ops); only its exit code is red. For (a) UTF-8-BOM the red is real today (stdlib `json.loads(text)` on a BOM-prefixed string fails → `.invalid.<uuid>` path → entries lost).
3. Init/upgrade writer path (`prepare_commands`/`apply_prepared` via `writers/claude_code.py:65`): with (b) a byte backup exists before the UTF-8 rewrite (today it silently re-encodes); with (c) `prepare_commands` raises `SettingsNotDecodableError` (FR-014). Plus a CLI test: `spec-kitty upgrade` in a project whose `.claude/settings.json` is fixture (c) → file byte-identical, non-zero exit, no success line for the session-presence migration.
5. NFR-003: every refusal assertion checks the file path AND the "re-save as UTF-8" remedy text.
4. Controls: plain UTF-8 file → behaviour identical to today (no backup, entries kept); invalid JSON (trailing comma) → existing `.invalid.<uuid>` path unchanged.

### Subtask T025 – `_load` / `_save` via the shared rule

- `_load(path, *, preserve_invalid=False) -> dict[str, object]`:
  - absent → `{}` (unchanged); `OSError` on read → keep today's behaviour only for absence races; a read that fails otherwise should propagate (don't swallow into `{}` — that's the bug class).
  - `raw = path.read_bytes()`; `decoded = decode_unambiguous(raw)`; `None` → `raise SettingsNotDecodableError(path=path, reason=...)`.
  - Keep `(text, source_encoding)`; JSON-decode `text`; invalid/non-object → existing `_preserve_invalid` path.
  - Remember `source_encoding` for this path (return it alongside, or store on the instance keyed by path) so `_save` knows whether to back up.
- `_save(path, data)`: if the loaded source encoding for `path` was not `"utf-8"`, call `backup_before_overwrite(path)` first (let backup failures raise — "Backup failures are re-raised to prevent silent data loss" per the existing docstring), then write UTF-8 as today.
- Keep each function ≤15 complexity; extract `_read_settings_text(path) -> tuple[str, str] | None`.

### Subtask T026 – `prepare_commands` / `apply_prepared`

- Replace `json.loads(raw)` (which auto-detects UTF-16/32 silently) with `decode_unambiguous(raw)`; `None` → raise `SettingsNotDecodableError` (today a `ValueError`/`UnicodeDecodeError` escapes — keep a typed error).
- If the source encoding isn't plain UTF-8 and the content changes, the prepared write must back up the original bytes first: either record the need on `PreparedPresenceFile` (if it has a free-form field — check its definition) or perform `backup_before_overwrite` in `apply_prepared` when `prepared.before` bytes don't round-trip as UTF-8. Choose the smallest correct change; explain in the Activity Log.

### Subtask T027 – Probes

- `tool_surface/providers/session_presence.py` (~:712): catch `SettingsNotDecodableError` and report a truthful finding (e.g. `"undecodable: re-save .claude/settings.json as UTF-8"`) consistent with how it already reports problems; test with fixture (c): no exception, finding mentions the file.
- `writers/claude_code.py` `has_presence` (~:85-90): propagate the error (do not catch); test that it raises for (c) and that `upgrade` surfaces it non-zero (T024-3).

### Subtask T028 – CLI surfacing

- `cli/commands/agent/config.py` `_sync_claude_hooks` (~:664-670) and the lint-hook disable path (~:751): let `SettingsNotDecodableError` propagate to the root error hook (exit 1) — do not catch-and-continue; make sure no `✓ Sync complete` is printed after a refusal (check ordering).
- `live_work/install.py` (~:92 register, ~:103/106 uninstall): same — propagate.
- Verify the true exit code with a subprocess test for `agent config sync --sync-hooks` (c).

### Subtask T029 – Convert and gate

```bash
uv run --frozen pytest tests/specify_cli/session_presence/ tests/specify_cli/cli/commands/test_lint_hooks.py -q
uv run --frozen pytest $(grep -rl "ClaudeCodeHookRegistrar\|live_work.install\|has_presence" tests --include=*.py | sort -u) -q
uv run --frozen pytest tests/architectural/test_cli_error_surface_seam.py tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check <changed> && uv run --frozen ruff format --check <changed>
uv run --frozen mypy --strict <changed src files>
make test-fast
```

Remove regression markers after green.

## Risks & Mitigations

- `test_overwrite_ownership_routing.py` may require overwrites to route through a sanctioned helper — read it before choosing where the backup call lives.
- Refusal now blocks uninstall/lint-disable on undecodable files: intended (data safety), covered by tests, mentioned in WP08 docs.

## Review Guidance

- NFR-001/002/003: red-first recorded; positive controls from the same fixture builder; refusals assert path + remedy.
- FR-014 scope: every reader **in `ClaudeCodeHookRegistrar`** (the `live_work/capability.py:322` probe is an out-of-scope follow-up).

- cp1252 fixture byte-identical after every mutating path; exit non-zero.
- UTF-16/BOM: all entries + session hooks kept; byte backup exists and equals the original.
- No `{}` fallback on decode failure anywhere in the registrar; `is_registered` never returns False on decode failure.
- `_preserve_invalid` path unchanged.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
