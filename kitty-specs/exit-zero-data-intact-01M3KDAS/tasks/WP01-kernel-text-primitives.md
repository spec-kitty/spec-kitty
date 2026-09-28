---
work_package_id: WP01
title: Kernel text primitives (decode_unambiguous, normalize_newlines)
dependencies: []
requirement_refs:
- FR-014
- NFR-006
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/text_decode.py
create_intent:
- src/kernel/text_decode.py
- tests/kernel/test_text_decode.py
- tests/charter/test_encoding_recovery_bom_delegation.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/kernel/text_decode.py
- src/charter/encoding_recovery.py
- src/charter/hasher.py
- tests/kernel/test_text_decode.py
- tests/charter/test_encoding_recovery_bom_delegation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Kernel text primitives

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load governance: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` in the event log (`spec-kitty agent tasks status --mission exit-zero-data-intact-01M3KDAS`). If this WP was returned, every feedback item is your TODO list.

---

## Objectives & Success Criteria

Create one canonical, **standard-library-only**, **non-guessing** decode rule and one newline normaliser in `kernel`, and make `charter` reuse them so there is a single definition (DIRECTIVE_044, C-002, C-003). This WP is the foundation for WP05 (settings file, #4940) and WP06 (CRLF skills, #4998).

Done means:
- `kernel.text_decode.decode_unambiguous(data: bytes) -> tuple[str, str] | None` exists. It returns `(text, source_encoding)` only when a BOM or strict UTF-8 proves the encoding; otherwise `None`. It never calls `charset_normalizer`.
- `kernel.text_decode.normalize_newlines(text: str) -> str` converts CRLF and lone CR to LF and changes nothing else.
- `charter.encoding_recovery.recover()` delegates its BOM + strict-UTF-8 steps to the kernel helper, its public behaviour for every currently-tested input is unchanged, and a UTF-32-LE BOM input is now reported as `utf-32-le` (a latent bug: today it is decoded as UTF-16-LE with embedded NULs because `FF FE 00 00` starts with the UTF-16-LE BOM `FF FE`).
- `charter.hasher.hash_content` calls `normalize_newlines` for its CRLF/CR step with byte-identical hashes.

## Context & Constraints

- Spec: `kitty-specs/exit-zero-data-intact-01M3KDAS/spec.md` (FR-014, C-002, C-003). Plan: `plan.md` design decisions **D1** and **D5**. Research: `research.md` R4, R5.
- `kernel` is declared zero-dependency (`src/kernel/pyproject.toml`), but no test enforces it (`kernel/yaml_io.py` already imports ruamel). **Your new file must import only the standard library.** Reviewers will check.
- Do NOT touch `kernel/meta_decode.py`; its strict-UTF-8 rule is deliberate and pinned by `tests/architectural/test_meta_decode_l1.py`.
- `charset_normalizer` stays imported only where `tests/architectural/test_encoding_recovery_unification.py` allows it (charter). Never import it in kernel.

## Branch Strategy

- **Strategy**: lanes (populated by finalize-tasks)
- **Planning base branch**: `claude/milestone-11-research-0rnnr4`
- **Merge target branch**: `claude/milestone-11-research-0rnnr4`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty implement WP01` and work only in the resolved workspace.

## Subtasks & Detailed Guidance

### Subtask T001 – Create `src/kernel/text_decode.py`

- **Purpose**: the single non-guessing decode rule and newline normaliser.
- **Steps**:
  1. Module docstring: explain "provable encodings only" (BOM or strict UTF-8), why no guessing (#4940 policy, Decision Moment `01M3KDD2GHGFS7J5616ZNQHE6Y`), and that `charter.encoding_recovery` layers cp1252 detection on top.
  2. BOM constants, checked in this order (longest/most specific first — UTF-32 before UTF-16):
     - `b"\x00\x00\xfe\xff"` → codec `"utf-32"`, source `"utf-32-be"`
     - `b"\xff\xfe\x00\x00"` → codec `"utf-32"`, source `"utf-32-le"`
     - `b"\xef\xbb\xbf"` → codec `"utf-8-sig"`, source `"utf-8-sig"`
     - `b"\xff\xfe"` → codec `"utf-16"`, source `"utf-16-le"`
     - `b"\xfe\xff"` → codec `"utf-16"`, source `"utf-16-be"`
     The source-encoding strings MUST match what `charter.encoding_recovery` reports today (`utf-8-sig`, `utf-16-le`, `utf-16-be`, `utf-8`) — tests pin them.
  3. `decode_unambiguous(data: bytes) -> tuple[str, str] | None`: try BOMs in order; on a BOM match decode with the codec (the `utf-16`/`utf-32`/`utf-8-sig` codecs strip the BOM). If the bytes after a BOM fail to decode, return `None` (not provable). Else try `data.decode("utf-8")` (strict) → `(text, "utf-8")`. Else `None`. Empty bytes → `("", "utf-8")`.
  4. Export `detect_bom(data: bytes) -> tuple[str, str] | None` returning `(codec, source_encoding)` for a recognised BOM (no decoding). `decode_unambiguous` is built on it. **Charter delegation MUST use `detect_bom` (not `decode_unambiguous`) for its BOM step** — see T003. `__all__ = ["decode_unambiguous", "detect_bom", "normalize_newlines"]`.
  5. `normalize_newlines(text: str) -> str`: `text.replace("\r\n", "\n").replace("\r", "\n")`. Nothing else (no BOM strip, no `strip()`).
- **Files**: `src/kernel/text_decode.py` (new, ~70 lines).
- **Notes**: type-annotate fully; mypy strict clean; complexity well under 15.

### Subtask T002 – Unit tests `tests/kernel/test_text_decode.py`

- **Purpose**: pin the rule.
- **Cases** (parametrise):
  - strict UTF-8 ASCII and non-ASCII (`"José".encode()`) → `("…", "utf-8")`.
  - UTF-8 BOM → text without `﻿`, `"utf-8-sig"`.
  - UTF-16-LE BOM and UTF-16-BE BOM (`"﻿{...}".encode("utf-16-le")` etc.) → decoded, `"utf-16-le"`/`"utf-16-be"`.
  - UTF-32-LE and UTF-32-BE BOM → `"utf-32-le"`/`"utf-32-be"` (and NOT utf-16 — this is the ordering regression).
  - cp1252 bytes `'{"env":{"OWNER":"Jos\xe9"}}'` (i.e. `b'...Jos\xe9...'`) → `None`.
  - BOM followed by undecodable bytes (e.g. `b"\xff\xfe" + b"\x00\xd8"` lone surrogate) → `None`.
  - empty bytes → `("", "utf-8")`.
  - `normalize_newlines`: `"a\r\nb\rc\n"` → `"a\nb\nc\n"`; mixed; no-op on LF; BOM char preserved (`"﻿x\r\n"` → `"﻿x\n"`); leading/trailing whitespace preserved.
- **Files**: `tests/kernel/test_text_decode.py` (new). Mark `pytest.mark.fast` if that's the local convention for `tests/kernel/` (check neighbouring files).

### Subtask T003 – Delegate charter's BOM/strict steps; fix UTF-32 ordering (red-first)

- **Purpose**: one definition (DIRECTIVE_044) and fix the latent UTF-32-LE mis-decode.
- **Red first**: create `tests/charter/test_encoding_recovery_bom_delegation.py` with a test asserting `recover("﻿{}".encode("utf-32-le")).source_encoding == "utf-32-le"` and the decoded text has no NUL characters. Mark it `@pytest.mark.regression` and confirm it FAILS on the unmodified code (today it reports `utf-16-le`). Record the failing output in the Activity Log.
- **Steps**:
  1. In `src/charter/encoding_recovery.py`, rewrite `_recover_from_bom` to call `kernel.text_decode.detect_bom` and then `data.decode(codec)` itself — so a BOM followed by undecodable bytes still **raises `UnicodeDecodeError`** exactly as today (today `recover(b"\xff\xfe\x00\xd8")` raises; it must NOT silently fall through to strict-UTF-8/cp1252 guessing). Add a test pinning that raise. `_recover_strict_utf8` may use `decode_unambiguous`'s strict path or keep its own `data.decode("utf-8")` — one definition preferred. Both wrap results and wrap the result into `EncodingRecoveryResult` exactly as today (`confidence=1.0`, `ambiguous=False`, `candidates=()`, `normalization_applied=True` for BOM results / `False` for strict UTF-8, `bypass_used=False`).
  2. Remove the now-unused private BOM constants from charter if nothing else references them (grep first; keep `CP1252_CODEC`).
  3. Keep `recover()`'s control flow identical otherwise (BOM → strict → single-byte).
  4. After green, convert the regression test into a normal focused test (remove the `regression` marker) and add a test that `recover()`'s BOM/strict results equal `decode_unambiguous` results for the same inputs (proves delegation).
- **Files**: `src/charter/encoding_recovery.py`, `tests/charter/test_encoding_recovery_bom_delegation.py`.

### Subtask T004 – `hash_content` uses `normalize_newlines`

- **Purpose**: one newline rule.
- **Steps**: in `src/charter/hasher.py` (~line 40) replace `.replace("\r\n", "\n").replace("\r", "\n")` with `normalize_newlines(...)`, keeping the `lstrip("﻿")` before and `.strip()` after. Hashes must be byte-identical: add a small test in `tests/kernel/test_text_decode.py` or reuse an existing hasher test (run `grep -rl hash_content tests/charter`) to prove LF/CRLF/CR inputs still hash equal and unchanged vs a pinned digest.
- **Parallel?**: yes, after T001.

### Subtask T005 – Gate run

Run and record commands + pass counts in the Activity Log:

```bash
uv run --frozen pytest tests/kernel/test_text_decode.py tests/charter/test_encoding_recovery_bom_delegation.py tests/charter/test_encoding_recovery.py -q
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_encoding_recovery_unification.py tests/architectural/test_meta_decode_l1.py tests/architectural/test_ruff_format_enforcement.py -q
uv run --frozen pytest $(grep -rl "hash_content\|hasher" tests/charter --include=*.py) -q
uv run --frozen ruff check src/kernel/text_decode.py src/charter/encoding_recovery.py src/charter/hasher.py tests/kernel/test_text_decode.py tests/charter/test_encoding_recovery_bom_delegation.py
uv run --frozen ruff format --check src/kernel src/charter tests/kernel tests/charter
uv run --frozen mypy --strict src/kernel/text_decode.py src/charter/encoding_recovery.py src/charter/hasher.py
make test-fast
```

Never run `make test-full` or the bare `tests/architectural/` directory (C-005).

## Test Strategy

Red-first for the UTF-32 correction (T003). Unit tests for the kernel helper. Non-regression for `recover()` (existing `tests/charter/test_encoding_recovery.py` must stay green unchanged) and `hash_content`.

## Risks & Mitigations

- **Behaviour change in `recover()`** for UTF-32-LE BOM input: intentional and pinned; mention in the commit message. UTF-32 BOM support is a deliberate, recorded extension of the operator's "provable encodings" policy (a BOM is proof), noted in plan D1.
- **BOM + undecodable bytes** must keep raising in `recover()` (pinned by test); only the kernel `decode_unambiguous` returns `None` for it. UTF-32 BOM support is a deliberate, recorded extension of the operator's "provable encodings" policy (a BOM is proof), noted in plan D1.
- **BOM + undecodable bytes** must keep raising in `recover()` (pinned by test); only the kernel `decode_unambiguous` returns `None` for it. UTF-32 BOM support is a deliberate, recorded extension of the operator's "provable encodings" policy (a BOM is proof), noted in plan D1.
- **BOM + undecodable bytes** must keep raising in `recover()` (pinned by test); only the kernel `decode_unambiguous` returns `None` for it.
- **Kernel purity**: reviewers grep the new file's imports.
- **Unification gate** may pin where BOM logic lives: read `test_encoding_recovery_unification.py` before editing; if it pins a symbol location, update the pin deliberately in this WP (never skip or weaken it) and explain in the Activity Log.

## Review Guidance

- New kernel module imports only stdlib; no `charset_normalizer`.
- `recover()` outputs identical for all pre-existing tests; UTF-32 fix pinned.
- Regression marker removed after green; red-first failure recorded.
- mypy strict + ruff + format clean.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
