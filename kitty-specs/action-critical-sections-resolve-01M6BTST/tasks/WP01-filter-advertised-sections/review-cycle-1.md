---
affected_files: []
cycle_number: 1
mission_slug: action-critical-sections-resolve-01M6BTST
reproduction_command:
reviewed_at: '2026-11-01T16:31:47Z'
reviewer_agent: user
wp_id: WP01
---

# WP01 review — round 1

Verdict: **REJECT** — one blocking finding (dead code).

## Findings

### F1 (blocking) — `_resolves_in_charter` has no production caller

`src/charter/activation/context_renderers/section_bodies.py` adds
`_resolves_in_charter(charter_content, heading)`, but
`render_critical_section_bodies` does the resolution inline with
`if (body := _extract_section_body(...))`. Nothing in `src/` or `tests/` calls
the new predicate:

```
$ grep -rn "_resolves_in_charter" src/ tests/
src/charter/activation/context_renderers/section_bodies.py:def _resolves_in_charter(...)
src/charter/activation/context_renderers/section_bodies.py:    """Return whether *heading* resolves ...
```

The anti-pattern checklist item 1 (dead code) fails: a new private helper with
zero call sites is dead weight and its docstring (the resolution rule) is now a
second, unenforced description of the behaviour.

Fix (either is acceptable):
- make the renderer call it, or
- replace it with a helper that returns the resolved body and use that helper
  in the comprehension (`body = _extract_section_body(...); return body or
  None`), keeping one parse per heading and deleting the unused predicate.

After the fix, re-run the T005 command list; no other code change is required.

## Anti-pattern checklist

1. Dead code — **FAIL** (F1).
2. Synthetic-fixture test — PASS: the new tests call `build_charter_context`
   and `build_charter_context_include`, and fail on the unpatched renderer.
3. Silent empty return — PASS: `return ""` when nothing resolves is documented
   in the function's Notes, the module docstring and an inline comment.
4. FR coverage — PASS: FR-001/002/003/004 covered by the new file, FR-005 by
   the red-first proof, FR-006 belongs to WP02.
5. Present-section behaviour preserved — PASS: the ATDD anchors in
   `tests/specify_cli/next/test_wp_prompt_governance_contract.py` are untouched
   and green (26 passed).
6. No `--feature` usage in changed lines — PASS.

## Evidence reviewed

- Diff: `src/charter/activation/context_renderers/section_bodies.py`,
  `bootstrap_text.py` (comment only), `tests/charter/test_context_section_bodies.py`,
  `tests/charter/test_context_display_charter_md.py`,
  `tests/charter/test_context_action_critical_minimal.py`.
- Red-first: `test_consumer_charter_advertises_no_section_it_does_not_have`
  failed before the renderer change (3 failed / 3 passed) and passes after
  (6/6).
- `ruff check` clean, `mypy` clean on both touched source files.
- Out-of-map edit (`test_context_display_charter_md.py`) is justified in the WP
  history and only updates the two expectations that encoded the removed
  advertising.
