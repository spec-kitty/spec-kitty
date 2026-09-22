---
work_package_id: WP05
title: validate-encoding --fix repairs faithfully (#4896)
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-008
planning_base_branch: fix/user-content-preservation
merge_target_branch: fix/user-content-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/user-content-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/user-content-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-user-content-preservation-01M3549Q
base_commit: 4d3b7e5b42019d817dd0d4fc17187bc58c706509
created_at: '2026-09-22T18:43:45.131189+00:00'
subtasks:
- T016
- T017
- T018
- T019
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/text_sanitization.py
create_intent:
- tests/regressions/test_issue_4896_validate_encoding_faithful_fix.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/text_sanitization.py
- src/specify_cli/cli/commands/validate_encoding.py
- tests/cross_cutting/encoding/test_encoding_validation_functional.py
- tests/regressions/test_issue_4896_validate_encoding_faithful_fix.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load **python-pedro** via `/ad-hoc-profile-load` (profile YAML), then return.

## Objective

`spec-kitty validate-encoding --mission <slug> --fix` (the command the shipped `AGENTS.md`
tells agents to run) corrupts files while reporting `Fixed`, exit 0 (#4896): a single stray
byte triggers a whole-file cp1252 re-decode that mojibakes every multi-byte char, binaries
named `*.md` are rewritten, and CRLF is converted to LF file-wide. Make the fixer faithful.

## Ground truth (verified on main@d57619a900) — `text_sanitization.py::sanitize_file`

- `:161` — scope decided by `.md` **extension** only; binaries are in scope.
- `:166-180` — `read_text(encoding="utf-8-sig")`; on `UnicodeDecodeError` the WHOLE file is re-decoded cp1252 then latin-1, no per-byte scoping, no test that the file is actually cp1252.
- `:189` — `encoding_issue` forces a rewrite even when nothing changed.
- `:166` vs `:202` — universal-newline read + `open(..., "w", newline="")` write: CRLF→LF on read, never restored.
- Driver: `cli/commands/validate_encoding.py:125` (`sanitize_directory(feature_dir, pattern="**/*.md", …)`).

## Subtasks

### T016 — [RED FIRST] Regression repro
`tests/regressions/test_issue_4896_validate_encoding_faithful_fix.py` (`@pytest.mark.regression`),
real CLI over a fixture mission dir with: `mixed.md` (valid UTF-8 + one `0xE9` byte), a binary
named `binary.md` (PNG bytes), `crlf.md` (CRLF + one smart quote), controls `crlf-clean.md`,
`clean.md`:
- After `--fix`: every valid UTF-8 char in `mixed.md` intact (no `CafÃ` mojibake) — repaired stray byte OR refused with offset. (RED on base.)
- `binary.md` unchanged (skipped). (RED on base.)
- `crlf.md` keeps CRLF apart from the smart-quote substitution. (RED on base.)
- controls byte-identical; "Fixed" NOT printed for a file whose non-target bytes would change.
Capture RED output; commit tests first.

### T017 — Content-sniff text vs binary
- Classify by content (e.g. NUL-byte / non-text heuristic), not the `.md` extension; skip binaries entirely (never rewrite).

### T018 — Scope the fallback decode
- Do not whole-file re-decode as cp1252. Either repair only the offending byte(s) (report offsets) or refuse the file with its offending offset(s). No blind cp1252/latin-1 whole-file transcode.

### T019 — Preserve line endings + honest "Fixed"
- Detect and preserve the file's existing newline convention (do not universal-newline translate CRLF→LF). 
- Report "Fixed" ONLY when the result is a faithful repair (no non-target byte changed); do not force a rewrite when nothing legitimately changed (`:189`).

## Branch strategy

Planning base + merge target `fix/user-content-preservation`; PR later to upstream `main`. Worktree per lane from `lanes.json`.

## Definition of Done

- Regression RED on base, GREEN on fix; controls untouched; binary skipped; CRLF preserved.
- mypy --strict + ruff clean; complexity ≤ 15 (extract helpers for sniff/decode/newline).
- Scope: only `kitty-specs/<mission>/**/*.md` behaviour changes; do NOT redesign encoding-at-lifecycle (that is #644, out of scope).
- Targeted tests: `PWHEADLESS=1 .venv/bin/python -m pytest tests/regressions/test_issue_4896_*.py tests/cross_cutting/encoding/ -q` — record counts.

## Reviewer guidance (reviewer-renata, opus)

- No whole-file transcode; binaries never rewritten; line endings preserved.
- "Fixed" is honest (faithful repair only). Three corruptions (mojibake/binary/CRLF) each covered.
