---
affected_files: []
cycle_number: 1
mission_slug: host-aware-mode-predicate-01M7X6B1
reproduction_command:
reviewed_at: '2026-11-21T06:30:30Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review feedback, cycle 1 (claude::reviewer-renata)

Verdict: changes requested. Two gate-strength gaps, both small and inside the owned files.
Everything else holds: the four adjudicated sites are real exact comparisons, the scan of the
pre-fix tree (merge-base 873ca367) flags 14 unadjudicated sites covering every file WP02 fixed,
the live mutation and self-mutation tests work, the Windows selected-bundle test fails when
`_finish_selected_stage` is reverted to `replace(expected, mode=effect.after.mode)` (and the
gate flags that revert as P3), and ruff, format, mypy and C901 are clean.

## Blocking

### B1. An adjudication entry exempts every future comparison in its function (hidden allowlist widening)

`_unadjudicated` keys on `(path, qualname, pattern)`. One entry therefore suppresses *any number* of
P1 findings in that function, including a new one with the #4927 defect shape. Reproduced: adding

    if current.state.mode != effect.after.mode:
        chmod_fd(...)

inside `projection._finalize_staged_directories` gives two P1 findings (lines 1100 and 1103), and
`_unadjudicated` returns `[]`. The same holds for `observe_bundle_path`, `_unique_members` and
`installer._archive_existing_path`. The table is then an allowlist that can grow silently, which the
charter's ratchet doctrine (Standing Order #5, Burn-down (a)) does not allow.

Fix: make each entry name exactly one comparison. Either key on the comparison's normalized source
(`ast.unparse(node)`, robust to line moves) or carry an expected `count` per key and fail when the live
count differs in either direction. Add a self-mutation test: a second mode comparison in an adjudicated
function is reported.

### B2. A comparison against a planned mode is missed when the observed side is held in a local variable

P1 needs *both* operands to carry `.mode`/`.st_mode`/`S_IMODE`. Extracting a variable from the original
#4927 site (`installer.py`, pre-fix line 1040) defeats it:

    current = stat.S_IMODE(path.lstat().st_mode)
    if current != after.mode:       # not reported

Probed shapes that also slip through: `o.mode != p` with `p = effect.after.mode`; `getattr(o, "mode") != a.mode`;
`stat.S_IMODE(st.st_mode) != mode` (parameter named `mode`); `st.st_mode & 0o777 != expected_mode`.

Fix (zero cost on the live tree, verified): add a pattern for an `==`/`!=` comparison where any operand is a
planned mode (`<x>.after.mode`, `after.mode`, `planned.mode`), whatever the other side is. On the live tree
it has 0 hits outside the authority functions. Recommended as well: treat a `Name` matching a mode token
(`mode`, `*_mode`) and `getattr(x, "mode"|"st_mode")` as mode-carrying in `_carries_mode`; that also adds
0 live findings. Add self-mutation cases for each new shape.

Accepted residuals (record in the module docstring): `operator.eq/ne`, `__eq__`, `match`, `in {…}`,
dict-lookup and arithmetic-equality shapes, and a helper defined outside the scan roots.

## Non-blocking

- N1. Changelog: the WP asked for a maintainer note naming the one host-aware predicate and the architectural
  gate (#4810); the fragment cites #4810 but does not mention the gate. The C-006 change (a read-only state
  that differs on Windows is now drift and repaired) is described correctly.
- N2. `tests/specify_cli/tool_surface/bundles/test_selected_bundle_windows.py:79` has `# type: ignore[arg-type]`
  without an inline rationale (CLAUDE.md asks for one). The file is outside `owned_files`; acceptable under
  ownership-map leeway, but say so in the WP history.
- N3. For the record: the gate is not on the `architectural-fast` roster. It runs in the heavy architectural
  battery (`architectural-heavy`), which runs on every `src/**` or `tests/architectural/**` change. That covers
  its whole read scope, so it does gate every relevant PR. Measured call time is under 1 s (NFR-004 met).
- N4. Floors (60 files / 1200 comparisons, against 77 / 1616 live) are reasonable. Removing all of `runtime/`
  would still pass, but the non-empty-root check and the stale-entry anchors cover that.
