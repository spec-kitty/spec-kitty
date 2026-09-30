---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T18:12:51Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback, cycle 2 (reviewer-renata)

Verdict: **changes requested, one narrow item.** All 7 blocking and 3 should-fix findings from cycle 1 are resolved; each was re-verified by probe. Red-first commit `909d15374` is genuinely red against the prior code: 15 failed, 69 passed, and every failure maps to a cycle-1 finding. The G4 AnnAssign double-count fix is correct, with no false negatives: a class field, an annotated local with an `effective_root` value, and an annotated `self.effective_root` target each give the expected hits. ruff, format, C901 ≤ 11 and `mypy --strict` are clean on all 6 files. There are exactly 5 + 1 `TRANSITIONAL(WP18)` markers and no `type: ignore`.

## Blocking: `str.casefold()` is not Windows path semantics, and it fails open in the `files()` containment check

The cycle-1 fix replaced `os.path.normcase` with `str(p).casefold()` in `_same_path` and `_is_within` (`src/mission_runtime/owned_checkout.py`). `casefold()` does full Unicode case folding: `"ß"` becomes `"ss"`, `"ﬁ"` becomes `"fi"`, and so on. Windows, NTFS and Python's own `PureWindowsPath` / `ntpath.normcase` do not; they apply a simple lowercase/upcase mapping. Probe results with `is_windows` forced True:

```
_same_path(Path('/r/Straße'), Path('/r/STRASSE'))                                  -> True   (wrong)
ntpath.normcase('C:/r/Straße') == ntpath.normcase('C:/r/STRASSE')                   -> False
PureWindowsPath('C:/r/Straße') == PureWindowsPath('C:/r/STRASSE')                  -> False
_is_within(Path('/o/kitty-specs/strasse/x.md'), Path('/o/kitty-specs/straße'))     -> True   (fail-open)
```

`OwnedCheckout.files()` uses `_is_within` as its containment check (`OWNED_MISSION_PATH_REFUSED`). On Windows it would accept a file in the *sibling* directory `strasse/` as inside the mission dir `straße/`. That is a fail-open regression from both the cycle-1 code and the original `OwnedMission.files` (`Path.relative_to`, i.e. `PureWindowsPath` semantics). It also departs from T001 step 4, which says to compare `os.path.normcase(str(p))` on Windows.

The motivation was that `os.path.normcase` is a no-op on POSIX, so the branch cannot be forced on Linux. That is valid, and the fix keeps it testable: use **`ntpath.normcase`**. It is importable and behaves identically on every OS, and it is exactly `os.path.normcase` on Windows (lowercase plus `/` becomes `\`). Keep the `kernel_paths.is_windows()` call-time lookup as it is.

Add a regression test with `is_windows` forced True:
- `_same_path(Path("/r/Straße"), Path("/r/STRASSE"))` is False;
- `_is_within(Path("/o/kitty-specs/strasse/x.md"), Path("/o/kitty-specs/straße"))` is False;
- the existing ASCII case-variant tests stay green.

Commit it red-first, then the fix. Also update the two docstrings that currently explain the casefold choice.

## Non-blocking

- `test_no_dead_symbols` still flags only `mission_runtime.owned_checkout::OwnedCheckoutPathRefused`. That is the accepted transient, judged at the mission tip. Do not allowlist it.
