# Contract: generated bundle wrapper runtime resolution

Applies to the two scripts `spec-kitty plugin build --target claude-code` writes into
the bundle: `bin/spec-kitty-wrapper` (POSIX bash) and `bin/spec-kitty-wrapper.cmd`
(cmd.exe). Rendered by `src/specify_cli/tool_surface/bundles/claude_wrapper.py`; the
tests in `tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py` are the
executable form of this contract.

## Inputs

| Input | Meaning |
| --- | --- |
| build version `V` | The CLI version that ran `plugin build`; substituted into both scripts. |
| supported series `S` | `<major>.<minor>` of `V` (e.g. `V=4.0.0rc8` → `S=4.0`). |
| pinned requirement | `spec-kitty-cli==V` |
| series requirement | `spec-kitty-cli>=V,<major>.(minor+1)`; empty when `V` has no readable series. |
| caller arguments | Forwarded verbatim (`"$@"` on POSIX, `%*` on CMD). |

## Resolution order

1. **PATH CLI inside the series.** `command -v spec-kitty` (POSIX) / `where spec-kitty`
   (CMD) succeeds, and `spec-kitty --version` prints a version token whose
   `<major>.<minor>` equals `S` → delegate to it and exit with its status.
   A missing binary, a failing `--version`, or a version outside `S` continues to step 2.
2. **Pinned requirement through uvx.** `uvx --from "<pinned requirement>" spec-kitty <args>`,
   taken only when `uvx --from "<pinned requirement>" spec-kitty --version` succeeds.
3. **Series requirement through uvx.** Same shape with the series requirement, taken only
   when its probe succeeds and the series requirement is non-empty.
4. **Refusal.** Exit 1 with a remedy naming `uv tool install spec-kitty-cli` or
   `pipx install spec-kitty-cli` (and `uvx` as the on-demand path).

A requirement that resolves is never retried against a different version: steps 2 and 3
probe for *resolution*, then exec the same requirement.

## Guarantees

- **G-1** Neither script invokes `uvx <distribution>` without `--from`; the distribution
  ships `spec-kitty`, not `spec-kitty-cli` (#6476).
- **G-2** A PATH CLI outside `S` is never executed (#6476).
- **G-3** An unpublished `V` still resolves inside `S`; an unreadable `V` yields no series
  requirement and no guessed range.
- **G-4** No path or content of the bundle outside `bin/` is touched by the wrapper.
- **G-5** No `pip install spec-kitty-cli` remedy is emitted from the wrappers.
- **G-6** POSIX: `set -euo pipefail` is in force and a failed probe never aborts the script.
- **G-7** CMD: `EXIT /B %ERRORLEVEL%` is never inside a parenthesized block (parse-time
  expansion would capture the preceding probe's status), `%*` forwards arguments, and the
  series requirement is quoted so `>`/`<` are not read as redirection.
- **G-8** Rendering is pure and offline: the same `V` renders byte-identical content.

## Out of scope

Where the bundle puts the wrapper (top-level `bin/`), manifest fields, and marketplace
sources are #6479's contract, not this one.
