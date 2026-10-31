# Discovery: plugin wrapper uvx fallback (#6476)

Mission `plugin-wrapper-uvx-fallback-01M68ZHZ`, branch
`kitty/mission-plugin-wrapper-uvx-fallback-01M68ZHZ`, base `main` at `6f73b2a98e`.

## Decisions

### D-01 — Reproduce with the real `uvx`, not a stub, before touching the template

`uvx "spec-kitty-cli==4.0.0rc8" --version` on this machine (uv from `/usr/local/bin/uvx`,
network available) exits 1 and prints:

```
The following executables are available:
- spec-kitty
Use `uvx --from spec-kitty-cli spec-kitty` instead.
```

So uv resolves the distribution, inspects its entry points, and refuses because no
executable is named `spec-kitty-cli`. `pyproject.toml` declares
`name = "spec-kitty-cli"` with one `[project.scripts]` entry, `spec-kitty =
"specify_cli:main"`. The defect is confirmed on current `main`, not superseded, and not
fixed anywhere (`git log -S'uvx --from'` hits unrelated files; the wrapper module's
history ends at the #623/#497 probe fixes).

### D-02 — `--from` is the fix, not a console-script alias

`uvx --from "spec-kitty-cli==<version>" spec-kitty "$@"` names the requirement *and* the
executable, so both wrappers work with no distribution change. Adding a
`spec-kitty-cli` console script would also make the old form work, but it publishes a
second CLI name on every install — a distribution-surface decision, not a P2 wrapper
fix. Rejected (recorded in `traces/design-decisions.md`, spec C-002).

### D-03 — One compatibility rule: the supported series

The operator's triage comment on #6476 records a second failure: a bundle built from a
version that is not on PyPI (rc8 was unpublished at triage time) cannot resolve the
exact pin either. Both that and the issue's "prefer the pinned version over any
`spec-kitty` on PATH when the PATH version is outside the plugin's supported range"
bullet are answered by a single notion:

- **supported series** = `<major>.<minor>` of the version the bundle was built from;
- the PATH binary is used only when its `--version` reports that series;
- the uvx retry uses `spec-kitty-cli>=<version>,<<major>.<minor+1>` so an unpublished
  pin still resolves to the newest published release of the same line.

This costs no network probe at build time and no version registry at run time.

### D-04 — Prove it through the generated artefact, not the helper

Tests must execute the generated script (or assert its rendered content), not only
call `wrapper_bash_content`. A helper-level assertion would stay green if the build
wiring stopped calling it — the non-vacuity rule in
`tactic:acceptance-criteria-non-vacuity` ("exercise the production path").

## Evidence

- `src/specify_cli/tool_surface/bundles/claude_wrapper.py:36-58` (POSIX template) and
  `:60-88` (CMD template) — the broken `uvx "<dist>==<ver>"` form and the unconditional
  PATH probe; `:51`, `:83` — the `pip install spec-kitty-cli` remedy.
- `src/specify_cli/tool_surface/bundles/claude.py:244-247` and
  `src/specify_cli/tool_surface/bundles/projection.py:943-945` — the two render/apply
  call sites that must keep working unchanged.
- `tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py:225-260` — the existing
  subprocess test that stubs `uvx` and asserts the *broken* argv (`"uvx
  spec-kitty-cli==9.9.9 mission list"`); it is the red-first hook and must be rewritten
  to the fixed argv.
- `tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py:44-53, 225-236` — the
  content assertions that pin the old PATH probe and the old remedy text.
- `docs/guides/how-to/installation/install-claude-code-plugin.md:76-100` — the how-to
  that documents the broken resolution order and the `pip install` remedy.
- `spec-kitty --version` prints `spec-kitty-cli version 4.0.0rc8`: the version token is
  the last whitespace-separated token and is preceded by two words, so neither the
  wrapper nor a test may assume a bare version string.

## Open questions

- **None blocking.** `#6479` (does the Claude bundle keep a top-level `bin/`?) decides
  *where* this wrapper lives, not what it does; the wrapper keeps its current location
  here and the PR notes the dependency. If #6479 later drops `bin/`, this module's
  templates move with it without reverting any behaviour introduced here.
- Not decided here: whether the plugin should eventually ship a launcher that avoids
  `uvx` altogether (vendored wheel / pinned tool install). That is a distribution
  question for #6479's follow-up, and this fix does not preclude it.
