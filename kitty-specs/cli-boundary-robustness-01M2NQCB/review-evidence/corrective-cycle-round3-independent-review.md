# Independent Review — Stale-Mock Exhaustive Sweep (PR #4674)

**Verdict: APPROVED**

Reviewer note: given the track record (this is round 3 of the same defect
class slipping past prior "fixes"), I did not trust the handoff's
classification table or its "high confidence" narrative. Every claim below
was independently re-derived: fresh greps, fresh reads of every hit, my own
pytest runs (not a re-read of the implementer's logs), and my own diff of
the actual mission baseline for new keyword-only parameters, not just the
one function the implementer named.

## 1. Commit contents — test-only, no drift

```
git show --name-only 41287f5c6   # core
git show --name-only 4b991e31c   # review-pr
```
Both touch exactly one file: `tests/test_dashboard/test_dashboard_preflight.py`
(+17/-2 in each). No `src/` changes, no `SAAS_SYNC` references, no unrelated
files. `diff` of the two commits' actual code changes (message text
stripped) is byte-identical between checkouts — only the commit messages
differ (review-pr's message additionally documents the sweep methodology).

`review-pr` chain: `4b991e31c` sits directly on `42757f0ad` (the "correct
verdict — third stale-mock instance found by CI" addendum commit).
`git show --stat 42757f0ad` confirms it only touches
`.../review-evidence/mission-review.md`; the new commit does not touch that
file, so the addendum is undisturbed.

## 2. Red → green reproduced independently

Both checkouts already had a warm `.venv` (uv 0.12.6); ran
`uv sync --frozen --all-extras` in both (132 packages, no changes) before
testing.

**Core checkout**, GREEN at HEAD:
```
.venv/bin/pytest tests/test_dashboard/test_dashboard_preflight.py -q
→ 12 passed in 1.55s
```

**Core checkout**, RED reproduced by checking out the pre-fix version of
just the test file (`git checkout 41287f5c6~1 -- tests/.../test_dashboard_preflight.py`),
running, then restoring (`git checkout 41287f5c6 -- <file>`; `git status`
clean afterward):
```
2 failed, 10 passed in 1.31s
TypeError: test_dashboard_command_persists_passed_advisory_warning.<locals>.<lambda>()
  got an unexpected keyword argument 'json_output'
TypeError: test_dashboard_command_non_git_project_exits_1_with_git_init_advice.<locals>.<lambda>()
  got an unexpected keyword argument 'json_output'
```
Matches the handoff's claimed failure mode exactly, independently
reproduced (not read from a log).

**review-pr checkout**, GREEN at HEAD (own run, not core's):
```
.venv/bin/pytest tests/test_dashboard/test_dashboard_preflight.py -q
→ 12 passed in 1.49s
```

## 3. Independent re-derivation of exhaustiveness (the critical part)

### 3a. Fresh grep for `get_project_root_or_exit` in both checkouts

```
grep -rln "get_project_root_or_exit" tests/ | sort | md5
```
→ identical hash in both checkouts, 14 files, matching the handoff's claim.

Classified every occurrence myself (not the handoff's table):

| File | Mechanism | Verdict |
|---|---|---|
| `tests/agent/test_commands.py` (3 sites) | named `fake_project_root` with correct `*, json_output: bool = False` (one variant also takes positional `repo_root`/`_repo`) | fixed correctly |
| `tests/dashboard/test_duplicate_prefix_rendering.py` (2 sites) | named `fake_project_root(*, json_output: bool = False)` | fixed correctly |
| `tests/test_dashboard/test_dashboard_preflight.py` (2 sites) | named `fake_project_root(*, json_output: bool = False)` (this sweep's fix) | fixed correctly |
| `tests/specify_cli/cli/commands/test_selector_resolution.py` (3), `test_wp03_no_selector_exit2.py` (2), `test_active_mission_removal.py` (2), `test_research_read_surface.py` (1) | `patch(..., return_value=...)` / `patch(...) as mock_root` | MagicMock, immune |
| `tests/integration/test_coord_loop_depgraph.py` (3), `tests/contract/test_feature_alias_scope.py` (1, docstring/patch target string) | `patch(...)` on module path | MagicMock, immune |
| `tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py`, `test_next_research_unsafe_mission_slug.py` | `patch(...)` | MagicMock, immune |
| `tests/specify_cli/cli/test_helpers.py`, `test_cli_boundary_json_seam.py` | direct calls to the real function (testing its contract) | not applicable |
| `tests/contract/test_no_selector_guard.py` | prose mention only, no mock | not applicable |

No bare zero-arg (or otherwise signature-mismatched) `lambda` mocking
`get_project_root_or_exit` remains anywhere in either checkout. This
matches the handoff's claim, independently re-verified line by line.

### 3b. Siblings in `helpers.py` with a new keyword-only param

Read `src/specify_cli/cli/helpers.py` in full and ran
`git diff be490214baa3cb1ee54b153e254b48f572ca40a1 HEAD -- src/specify_cli/cli/helpers.py`
(mission baseline is a real, resolvable ancestor of HEAD). The diff shows
exactly one function signature gaining a new keyword-only parameter as
part of this mission:

```
-def get_project_root_or_exit(start: Path | None = None) -> Path:
+def get_project_root_or_exit(start: Path | None = None, *, json_output: bool = False) -> Path:
```

`exit_git_resolution_failure(exc, project_root, *, json_output: bool = False)`
already had `json_output` **before** this mission — its diff only changes
the JSON-emission body (`typer.echo(json.dumps(...))` → `console.emit_json(json_error(...))`),
not its signature. The handoff's framing of it as a "sibling that gained
the same new keyword-only param" is technically imprecise (it did not gain
the param in this mission), but the practical conclusion — no lambda mocks
of it exist — is correct and independently confirmed: only direct
real-function calls in `test_helpers.py` and `test_cli_boundary_json_seam.py`
reference it.

`check_version_compatibility` and `git_resolution_failure_message` take no
such keyword — confirmed by reading the file directly.

### 3c. `locate_project_root` claim spot-checked

Three definitions found via `grep -rn "^def locate_project_root" src/`:
- `specify_cli/__init__.py:71` — `def locate_project_root() -> Path | None:`
- `specify_cli/core/paths.py:188` — `def locate_project_root(start: Path | None = None, *, stop: Path | None = None) -> Path | None:`
- `specify_cli/core/project_resolver.py:8` — `def locate_project_root(start: Path | None = None) -> Path | None:`

None show up in the `src/` diff against the mission baseline
(`git diff be490214b HEAD -- src/`) at all — none of these three files are
in the changed-file list for this mission. So the `stop=` keyword-only
param on the `core/paths.py` variant predates this mission and is not a
mission-introduced signature change. The ~90 `lambda: X` / `lambda cwd: X`
mocks of `locate_project_root` across `tests/next/`, `tests/doctor/`,
`tests/audit/`, `tests/architectural/`, etc. are pre-existing test debt
against a stable signature, not instances of this mission's defect class.
Confirmed by reading the diff, not by trusting the assertion.

### 3d. Broader pass — other CLI-boundary helpers with new keyword-only params

Ran `git diff be490214b HEAD -- src/` (31 files changed) and grepped the
added (`+`) lines for new function signatures and for hunks where an
existing `def` line was replaced with one gaining `json_output: bool`.
Only one such **existing-function signature change** appears in the whole
mission diff:

```
-def get_project_root_or_exit(start: Path | None = None) -> Path:
+def get_project_root_or_exit(start: Path | None = None, *, json_output: bool = False) -> Path:
```

Several genuinely **new** functions were introduced with `json_output`
already part of their signature from birth (`resolve_project_root_or_exit`
in `_doctor_shared.py`, `_status_error`, `_glossary_error`,
`mission_type_error_boundary`, `_workspace_read_boundary`,
`_emit_mission_error`, `_report_ambiguous_selector`, `json_output_guard`,
etc.). These can't have "stale" mocks predating their own existence, but I
checked anyway: grepped tests/ for lambda mocks of every one of them —
zero hits. `_emit_selector_error` looked at first glance like it might have
gained the param, but its diff shows it already had
`*, json_output: bool = False` before this mission; only its body was
refactored to use the shared `json_error`/`console.emit_json` contract.

No second category of "same pattern, different keyword name" defect was
found.

## 4. Checkout hygiene

- `git status --short` clean in both checkouts, before and after my
  red/green reproduction (I restored the file with `git checkout <fix-commit> -- <path>`
  immediately after the RED check).
- Neither checkout has pushed: `git log --oneline @{u}..` shows the fix
  commits (and, in core's case, several prior commits) still ahead of
  `origin/fix/cli-boundary-robustness` and `origin/issue-4600-cli-boundary-robustness`
  respectively — nothing pushed to origin.
- No full-suite run was performed by me (only the single affected test
  file, in each checkout, matching the task's "spot-check is fine" guidance
  for the red/green reproduction step).
- Process audit: `ps aux | grep -i "pytest\|spec-kitty\|uv sync"` shows no
  leftover pytest/uv processes from this review. The one unrelated hit
  (`python -m http.server 4173 --directory .../training/app`) predates this
  session and is outside its working directories — not something I started
  or am responsible for cleaning up.

## Conclusion

The implementer's core claim holds up under independent, skeptical
re-derivation: this was in fact the last remaining lambda-mock instance of
the `get_project_root_or_exit(..., *, json_output=...)` defect class, the
fix is test-only and correctly shaped, red/green is real (reproduced
myself, not read from a log), and a broader sweep across every
keyword-only-parameter addition introduced by this mission (not just the
one function named in the handoff) turned up no second category of the
same defect. The one imprecision in the handoff (calling
`exit_git_resolution_failure` a function that "gained" the param in this
mission, when it already had it) is cosmetic and does not change the
conclusion.

**APPROVED.**
