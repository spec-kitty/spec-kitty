---
affected_files: []
cycle_number: 1
mission_slug: feedback-slash-command-validation-01M3VZBD
reproduction_command:
reviewed_at: '2026-10-01T19:50:50Z'
reviewer_agent: cursor
wp_id: WP01
---

**Issue 1 (blocking, FR NFC)**: `normalize_comment` output is not always NFC. `_clean_comment_text` runs `unicodedata.normalize("NFC", ...)` FIRST, then strips Cc/Cf characters. A format char between a base and a combining mark defeats composition: `normalize_comment("e\u200b\u0301")` returns `"e\u0301"` (decomposed; `unicodedata.is_normalized("NFC", out)` is False). Fix: strip escapes/Cc/Cf and collapse whitespace first, then NFC-normalize last (before the length check and truncation, so the cap and the combining-mark guard operate on the final text). Add table cases for it (e.g. `"e\u200b\u0301"` -> `"\u00e9"`, and a ZWSP-split base+mark at the 2000 boundary) plus an invariant test that every COMMENT_CASES output satisfies `unicodedata.is_normalized("NFC", out)`.

**Issue 2 (minor, recommended)**: 8-bit C1 introducers are removed as bare Cc characters but their payload leaks through: `normalize_comment("a\x9b31mb")` -> `"a31mb"` (C1 CSI `\x9b`, also OSC `\x9d`, DCS etc.). Extend `_ESCAPE_SEQUENCE` to treat `\x9b` like `\x1b[` and `\x9d` like `\x1b]`, and add table cases.

Everything else passed: rating/email strictness, aggregation + no-send, callers use hardened parsers, 443 feedback tests pass, ruff/format/mypy strict clean, no noqa/type-ignore, tables meet sizes and 40 table tests fail against the old payload.py (non-vacuous), NFR-001 measured ~0.4 ms vs 10 ms budget. Whitespace-collapse (newlines to one space) is acceptable per spec and documented in the docstring.
