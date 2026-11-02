# Implementation Plan: Charter reported paths are POSIX on every OS (#7044)

**Branch**: `issue-7044-charter-reported-paths-posix` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/charter-reported-paths-posix-7044-01M6EJRR/spec.md`
**Input**: Mission specification from `kitty-specs/charter-reported-paths-posix-7044-01M6EJRR/spec.md`

## Summary

Three charter CLI sites render a repository-relative path with
`str(Path.relative_to(repo_root))`, whose separator follows the host OS, so Windows
envelopes and text output spell `.kittify\charter\charter.md` where Linux and macOS spell
`.kittify/charter/charter.md`. The fix gives the CLI the seam #6277 introduced for
`charter synthesize` — `kernel.charter_pack_paths.repo_relative_posix(path, repo_root)`,
which keeps the separator swap in `kernel.paths.to_posix()` — and routes
`charter generate --json`, `charter interview --json`, their two text lines, the
missing/malformed-interview error and `_common._display_path()` through it. Red-first: a new
regression module simulates Windows path rendering on POSIX and fails 6 of its 7 tests before
the change.

## Technical Context

**Language/Version**: Python 3.11 (repo `pyproject.toml` floor; CI matrix covers 3.11–3.13)
**Primary Dependencies**: `typer` (CLI), `rich` (text output), `pytest` + `typer.testing.CliRunner` (tests); no new dependency
**Storage**: filesystem paths under `.kittify/charter/`; no datastore
**Testing**: `pytest`, module-level regression test through the real Typer app; Windows rendering simulated by patching `Path.relative_to` (never `os.name` — see `tests/kernel/test_is_windows_seam.py`)
**Target Platform**: every OS the CLI ships to, including Windows (that is the defect)
**Project Type**: single Python package with a `src/kernel` floor, `src/charter` domain layer and `src/specify_cli` CLI layer
**Performance Goals**: N/A — two string renderings per command invocation
**Constraints**: no envelope shape, field-name, ordering or exit-code change; POSIX output byte-identical to `main`
**Scale/Scope**: 1 new kernel function (21 lines, shared with #6277), 3 source files touched at 6 call sites, 1 new test module, 1 changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| **Single canonical authority** | The spelling rule lives once, in `kernel.charter_pack_paths.repo_relative_posix()`; the separator swap stays in `kernel.paths.to_posix()`. No site decides its own spelling (C-001, C-002). |
| **Layer rule: `kernel` imports nothing upward** | The new helper lives in `kernel` and imports only `kernel.paths`. The CLI imports it downward. Verified: no `charter`/`specify_cli` import enters `kernel`. |
| **ATDD-first / red-first** | The regression module is written first and must fail through the pre-existing entry points (`charter generate`, `charter interview`, `_display_path`) before the fix; non-vacuity control included (NFR-003). |
| **DIRECTIVE_024 locality of change** | Six call-site substitutions plus one helper; no refactor of the charter CLI, no widening into `charter synthesize` (#6277 / PR #7045, C-003). |
| **DIRECTIVE_041 tests guard real behaviour** | One module guards the standing invariant "a reported repo-relative path is POSIX on every OS", with a positive control and a real-entry-point test, not a helper-only test. |
| **NO_FULL_HEAVY_SUITES_IN_MISSION** | Scoped suites only (`tests/specify_cli/cli/commands/charter`, `tests/charter`, `tests/agent/cli/commands`), plus targeted static checks. |
| **Per-PR changelog fragment** | `docs/changelog/unreleased/<pr>.fixed.md`; `docs/changelog/CHANGELOG.md` untouched. |
| **Self-review / draft-PR-first** | Draft PR with the five-section template, `pr:pause-ci`, flip only when the head is green. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-reported-paths-posix-7044-01M6EJRR/
├── plan.md              # This file
├── research.md          # Discovery findings (D-001..D-005)
├── spec.md              # FR/NFR/C/SC
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

No `data-model.md`, `quickstart.md` or `contracts/` for this mission: no entity, no new
contract, and the envelopes' shape is deliberately unchanged (NFR-001).

### Source Code (repository root)

```
src/
├── kernel/
│   ├── charter_pack_paths.py     # + repo_relative_posix(path, repo_root) -> str  (the seam)
│   └── paths.py                  # unchanged: to_posix() is the separator seam
└── specify_cli/cli/commands/charter/
    ├── _common.py                # _display_path(): in-repo -> repo_relative_posix, else str(path)
    ├── generate.py               # charter_path envelope value, "Charter:" line, rel_path in the interview error
    └── interview.py              # interview_path envelope value, "Interview file:" line

tests/specify_cli/cli/commands/charter/
└── test_charter_reported_paths_posix.py   # new red-first regression module

docs/changelog/unreleased/
└── <pr>.fixed.md               # user-facing fragment
```

## Phase 0 — Research (complete)

See `research.md`. Decisions that shape the design: D-001 (defect reproduces on `main`),
D-002 (the seam is #6277's helper and PR #7045 owns it; this Mission adds the identical
function text so either landing order leaves one definition), D-003 (the two text lines and
the interview error are the same defect), D-004 (keep `_display_path()`'s out-of-repo
fallback), D-005 (simulate Windows rendering, never `os.name`).

## Phase 1 — Design

**The seam** (`src/kernel/charter_pack_paths.py`), identical text to PR #7045's addition:

```python
def repo_relative_posix(path: Path, repo_root: Path) -> str:
    """Return *path* as a repo-relative POSIX string. ..."""
    return to_posix(path.relative_to(repo_root))
```

- It *raises* `ValueError` for a path outside `repo_root`; the caller decides the fallback.
  That keeps `_display_path()`'s existing try/except meaningful instead of hiding the
  distinction inside the helper.
- Both parameters are `Path`: an already-rendered string can be normalised unsafely, and a
  relative string would double its own prefix.

**Call sites**

| File | Site | Before | After |
| --- | --- | --- | --- |
| `generate.py` | `:671` envelope | `str(charter_path.relative_to(repo_root))` | `repo_relative_posix(charter_path, repo_root)` |
| `generate.py` | `:690` text | `f"Charter: {charter_path.relative_to(repo_root)}"` | `f"Charter: {_display_path(charter_path, repo_root)}"` |
| `generate.py` | `:343` error path | `rel_path = answers_path.relative_to(repo_root)` | `rel_path = _display_path(answers_path, repo_root)` |
| `interview.py` | `:523` envelope | `str(answers_path.relative_to(repo_root))` | `repo_relative_posix(answers_path, repo_root)` |
| `interview.py` | `:543` text | `f"Interview file: {answers_path.relative_to(repo_root)}"` | `f"Interview file: {_display_path(answers_path, repo_root)}"` |
| `_common.py` | `:106` helper | `str(path.relative_to(repo_root))` | `repo_relative_posix(path, repo_root)`, `except ValueError: return str(path)` |

Text sites go through `_display_path()` rather than calling the helper directly, so the
out-of-repo fallback (D-004) is uniform for both `--json` and text and there is one
CLI-side entry point for "how a charter verb shows a path".

The two **envelope** values are the exception: they call `repo_relative_posix()` directly and
therefore *raise* `ValueError` for a path outside the repository instead of degrading to
`str(path)`. That is deliberate — `charter_path`/`interview_path` are built from the repo root by
construction, so a value outside it is a broken invariant, and an envelope is the wrong place to
launder it into a native absolute path. The human-facing fallback stays where a reader can act on
it: the text line and the error message.

**Import shape.** `_common.py` takes its first `kernel` import here (it imported only `charter.*`
and `specify_cli.task_utils` before); the layer rule permits it, because `kernel` is the floor and
`kernel.charter_pack_paths` imports only `kernel.paths`. `generate.py` and `interview.py` import
`_display_path` from `_common` (the package already re-exports it in
`charter/__init__.py.__all__`), and import `repo_relative_posix` from
`kernel.charter_pack_paths`. No lazy import is needed: `kernel` is already imported transitively
on these paths.

**Test design** (`tests/specify_cli/cli/commands/charter/test_charter_reported_paths_posix.py`):

1. `install_windows_path_rendering(monkeypatch)` — patches `Path.relative_to` so results whose
   first part is `.kittify` come back as `PureWindowsPath`; `str()` renders `\`, `as_posix()`
   renders `/`. Restricted to `.kittify` so unrelated callers keep real `Path` access paths.
2. Control: a bare `str(relative_to(...))` under the simulation contains `\` (non-vacuity).
3. `charter interview --defaults --json` → `interview_path == ".kittify/charter/interview/answers.yaml"`, no `\`, and the file exists at that path.
4. `charter generate --from-interview --json` → `charter_path == ".kittify/charter/charter.md"`, no `\`, resolvable on disk.
5. `charter generate --from-interview` text output → `Charter: .kittify/charter/charter.md`; `charter interview --defaults` text → `Interview file: .kittify/charter/interview/answers.yaml`.
6. Missing-interview `charter generate --from-interview` → error message contains the POSIX path.
7. `_display_path()` unit: in-repo → POSIX under the simulation; out-of-repo → unchanged `str(path)`, no raise (FR-005 positive/negative pair on one fixture).

The module is written first and run against unfixed source to record which tests fail
(expectation: 4 of 5 behavioural tests red, the control green).

**Half-by-half proof.** The fix has two independent parts — the envelope sites (FR-001,
FR-002) and `_display_path()` (FR-003, FR-004). Reverting either part alone must turn a
distinct subset of the module red; recorded in the review/test notes.

## Phase 2 — Task shape

One work package (single implementation surface, one cohesive invariant). The WP carries
WP01's tests red-first, the six call-site substitutions, the changelog fragment and the
scoped verification list. No lane parallelism: the sites are five lines in three files that
share one helper, so splitting them would create a second source of truth mid-mission.

## Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Duplicate `repo_relative_posix` when PR #7045 merges | Identical function text and location, so the identical-addition hunk merges cleanly; whichever lands second keeps one definition. Named in `## Deferred` on the PR. |
| A golden test compares status text and moves | POSIX output is byte-identical by construction; the existing suites must pass with no expectation edited (NFR-002). Any move is treated as a regression to investigate, not as an update. |
| `_display_path()` callers passing a non-under-`.kittify` path | Helper only re-flavours `.kittify` results, so unrelated callers still receive real `Path`s; the out-of-repo case keeps `str(path)`. |
| Simulated-Windows test passing vacuously | Control assertion (NFR-003) plus the recorded pre-fix red run. |
| Losing the `--json` error path | Test 6 exercises `charter generate --from-interview` with the file absent, which is the `_emit_error` path, under `--json` too. |
