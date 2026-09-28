# Research: Python interpreter surface honesty

## R-1 — What exactly changed in Python 3.13?

- **Decision**: treat non-strict `Path.resolve()` on a symlink loop as the divergence root cause.
- **Evidence** (run locally, 2026-09-27, two-link loop `a -> b -> a`):

  | Interpreter | `resolve()` | `resolve(strict=True)` |
  |---|---|---|
  | 3.11.15 | `RuntimeError` (`__context__` = `OSError(ELOOP)`) | `RuntimeError` |
  | 3.12.3 | same as 3.11 (scout-confirmed) | same |
  | 3.13.12 | returns `…/a` (no exception) | `OSError(ELOOP)` |
  | 3.14.7 | same as 3.13 (scout-confirmed) | same |

  CPython 3.11's `pathlib.Path.resolve` performs a post-`realpath` `stat()` in non-strict mode specifically to surface loops. 3.13 dropped that probe when pathlib's resolution was reworked. The primitive re-instates exactly that probe.
- **Alternatives considered**:
  - `resolve(strict=True)` with a non-strict fallback. Rejected: two resolutions per call, and non-ELOOP strict failures (for example `NotADirectoryError`) must be re-classified by hand.
  - `os.path.realpath(strict=os.path.ALLOW_MISSING)`. Rejected: not available on every supported interpreter.
  - Adopting 3.13's semantics everywhere. Rejected: every affected guard was written for the raising contract, and several guard writes (a final-component loop symlink is replaced by a regular file on 3.13).

## R-2 — Which reported 3.13 reds are real divergence?

- **Decision**: 2 of 19. The remaining 17 are red on 3.11/3.12 too (`main` @ `f8aa22fe`) and stay out of scope (spec C-002).
- **Method**: identical node-ID lists on three local venvs built with `uv sync --frozen --all-extras`, `-n 4 --dist loadfile`.

## R-3 — Which other guards share the class?

- **Decision**: the enumerated list in spec FR-004, from the brownfield scout's confirmed runs on all four interpreters. No site became a containment *escape* on 3.13+ (the unresolved loop path still lies inside its root). The divergence is in the verdict: refusal becomes acceptance, a crash becomes a verdict, or a guard write replaces a symlink.

## R-4 — Is 3.14 installable today?

- **Decision**: yes. `uv sync --frozen --all-extras --python 3.14` succeeds (CPython 3.14.7, `uv 0.12.19`). A one-off fast/unit measurement on 3.14 against a 3.12 baseline is recorded in the PR (spec SC-004).

## R-5 — What does the 3.14 fast/unit tier show? (SC-004)

- **Run**: `.venv314` (CPython 3.14.7), `pytest -m "fast or unit" -n 4 --dist loadfile` on `main` @ `f8aa22fe`: **51 failed, 35,586 passed, 191 skipped** in 34m20s.
- **Classification**: the 51 failed node IDs were re-run on 3.12.3 (48 failed, 3 passed) and on 3.13.12 (50 failed, 1 passed).
  - **48** fail on 3.12 as well, so they are drift on `main`, not divergence (spec C-002).
  - **2** fail on 3.13 and 3.14 only. These are the two symlink-loop reds this mission fixes.
  - **1** (`tests/specify_cli/session_presence/test_manager.py::TestBuildContent::test_health_uses_fresh_prerelease_cache`) failed only inside the full 3.14 parallel run. It passes in isolation on 3.14 twice. It is order- or context-sensitive, not demonstrated divergence, and is listed in the PR for follow-up.
- **Conclusion**: on current `main`, the only demonstrated 3.13/3.14 interpreter divergence in the fast/unit tier is the symlink-loop class.
