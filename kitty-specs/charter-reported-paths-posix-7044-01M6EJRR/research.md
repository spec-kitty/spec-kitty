# Discovery (research.md) — charter reported paths are POSIX on every OS (#7044)

## Scope of the step

Discovery before specification: what the defect is, whether it still reproduces on current
`main`, where the reporting sites are, what the sanctioned seam is, and what is out of scope
because a sibling Mission owns it.

## Decisions

### D-001 — The defect reproduces on current `main`, through the real CLI entry points

Grounded by running the two commands that own the affected envelopes in a scratch git
repository, under a Windows *path-rendering* simulation (the technique #6277 used):

```
interview.interview_path = '.kittify\\charter\\interview\\answers.yaml'
generate.charter_path   = '.kittify\\charter\\charter.md'
```

Both envelope values carried `\` where Linux/macOS report `/`. The source sites are unchanged
from the issue's line numbers on `origin/main` (`9aed3a8012`):

- `src/specify_cli/cli/commands/charter/generate.py:671` — `"charter_path": str(charter_path.relative_to(repo_root))`
- `src/specify_cli/cli/commands/charter/interview.py:523` — `"interview_path": str(answers_path.relative_to(repo_root))`
- `src/specify_cli/cli/commands/charter/_common.py:108` — `_display_path()` returns `str(path.relative_to(repo_root))`

`git log -S "repo_relative_posix" -- src/` shows no commit on `main` that fixed these, so the
issue was not superseded.

### D-002 — The seam is `kernel.charter_pack_paths.repo_relative_posix()`, and #7045 owns it

#6277's fix (PR #7045, branch `issue-6277-charter-synthesize-json-posix-paths`, still open and
not merged) adds to `src/kernel/charter_pack_paths.py`:

```python
def repo_relative_posix(path: Path, repo_root: Path) -> str:
    return to_posix(path.relative_to(repo_root))
```

Delegating the separator swap to `kernel.paths.to_posix()` keeps the *normalisation* rule in
one place (#2836) while the new helper decides *what* is reported. That is the seam this issue
names, and it is not on `main` yet.

**Decision:** this Mission adds the *identical* function text at the identical location, and
routes its three sites through it. If #7045 lands first, this branch rebases onto a tree that
already has the same hunk (identical additions merge cleanly) and this PR's remaining diff is
only the generate/interview/_common call sites; if this lands first, #6277's PR keeps the
definition and drops its duplicate on rebase. Either order leaves exactly one definition.
The alternative — a private copy in the CLI layer — is rejected by C-002 (no second spelling
authority) and the alternative of waiting on an unmerged, `CONFLICTING` sibling PR would block
a P2 defect indefinitely.

### D-003 — The text surfaces in the same two files are part of the same defect

`generate.py` and `interview.py` also print `Charter: {charter_path.relative_to(repo_root)}`
(`generate.py:690`), `Interview file: {answers_path.relative_to(repo_root)}`
(`interview.py:543`), and interpolate `rel_path = answers_path.relative_to(repo_root)`
(`generate.py:343`) into the missing/malformed-interview error message — which also reaches
`--json` consumers through `_emit_error`'s `error` string. The issue names `_display_path()`
because it "feeds the human-readable output of other charter verbs"; the same rule has to hold
for these verbs' own text lines, or the fix leaves the copy-paste surface halfway done.

### D-004 — `_display_path()` keeps a fallback for paths outside the repository

`_display_path()` is called with roots that are not always the repo (for example
`_status_collectors.py:163` passes `canonical_root`, and `_display_path(input_root, repo_root)`
at `:212`). `Path.relative_to()` raises `ValueError` there, and the current code returns
`str(path)`. The fix keeps that shape: the in-repo branch renders POSIX, the out-of-repo
fallback stays `str(path)` — an absolute path outside the repository is not a
repository-relative path, so the issue's rule does not reach it and a Windows user copying it
into a shell should get the native spelling.

### D-005 — Non-vacuity: simulate Windows rendering, never fake `os.name`

`tests/kernel/test_is_windows_seam.py` documents that faking `os.name` flips `pathlib` to
`WindowsPath` mid-run and crashes pytest. #6277's regression module therefore patches
`Path.relative_to` so that results under `.kittify` are `PureWindowsPath` (`str()` renders `\`,
`as_posix()` renders `/`), with a control test proving a bare `str(relative_to(...))` really
produces a backslash. This Mission reuses that harness shape, restricted to `.kittify` results
so unrelated callers keep real `Path` access paths.

## Evidence

- Issue #7044 body, labels (`windows`, `priority:P2`, `domain:cli`), and its stated line
  numbers — all still accurate on `origin/main`.
- PR #7045 (fixes #6277): `+21` lines in `src/kernel/charter_pack_paths.py` adding
  `repo_relative_posix`; open, `CONFLICTING`, not merged.
- `src/kernel/paths.py:472` `to_posix()` — the single separator-normalisation seam; docstring
  forbids scattered `str.replace("\\", "/")` (#2836).
- `src/specify_cli/cli/commands/charter/_status_collectors.py` — the `_display_path()` call
  sites (`:163`, `:212`, `:238`, `:266`, `:290`, `:319`, `:329`, `:359`).
- `tests/specify_cli/cli/commands/charter/test_status_collectors_legacy_md_shape.py:97` and
  `tests/charter/test_presence_gate_bundle_authority.py:121` already expect POSIX values, so
  the change must keep them green unchanged.
- `docs/changelog/unreleased/README.md` — per-PR changelog fragment shape (`<pr>.fixed.md`).

## Open questions (for specify/plan)

- Q-001: Should the regression module live beside the existing charter CLI tests
  (`tests/specify_cli/cli/commands/charter/`) or extend #6277's module? Separate module chosen:
  #6277's file is not on `main`, and merging them would make a two-PR conflict out of an
  unrelated file. Answered in plan.
- Q-002: Does any contract file pin the envelope path spelling? Checked `contracts/`: no
  schema documents `charter_path`/`interview_path` spelling, and POSIX output on POSIX hosts is
  byte-identical, so no contract edit is needed.
- Q-003: Is the docs surface affected? No CLI reference text names a path spelling; only the
  user-facing changelog fragment is required.
