# Contract: root-walk boundaries and the harness temp root

**Mission**: `test-harness-temp-ceiling-01M6G9V8` (#7076). Supersedes nothing; it records the
contract #7022/#7056 established and #7076 completed.

## 1. The walks

`specify_cli.core.paths.locate_project_root(start=None)` and
`specify_cli.task_utils.support.find_repo_root(start=None)` take a start path and **no boundary
argument**. A caller cannot bound a walk; the boundary is the environment's.

```python
def locate_project_root(start: Path | None = None) -> Path | None: ...
def find_repo_root(start: Path | None = None) -> Path: ...   # raises TaskCliError when none
```

Passing `stop=` is a `TypeError`. It was accepted until #7076; every caller was a test, and the
ceiling below covers what it did.

## 2. The boundary: `GIT_CEILING_DIRECTORIES`

| Rule | Behaviour |
| --- | --- |
| A listed directory | **Examined**, and the walk stops after it (one step looser than git, which does not examine it unless the search starts there). #7022's shipped semantics, pinned by `tests/specify_cli/core/test_paths.py`. |
| A relative entry | Ignored, as git ignores it. |
| Comparison | Both sides resolved, so a symlinked temp root (`/var` → `/private/var`) matches. |
| Read time | Per call. No module constant, no cache — a `monkeypatch.setenv` in a test takes effect. |
| Absolute entry above the start | Not examined; the walk stops before it. |

`tests/unit/test_root_walk_has_one_boundary.py` is the conformance test for both rows that matter
to a caller: below the ceiling resolves nothing, at the ceiling resolves the project.

## 3. The harness's temp root

`tests/conftest.py::pytest_configure` calls, in this order:

1. `install_run_basetemp(config, now)` — gives the run a private basetemp (or honours an explicit
   `--basetemp`).
2. `install_git_ceilings(harness_git_ceilings(config, _worker_home_base(config)), os.environ)` —
   lists the run basetemp and the worker's isolated home as ceilings.
3. `install_temp_root(config, os.environ)` — points `TMPDIR`/`TEMP`/`TMP` at `<basetemp>/tmp`,
   creates it, resets `tempfile.tempdir`, and registers the guard fixture.

Consequences a test may rely on:

| Guarantee | Why it holds |
| --- | --- |
| `tempfile.gettempdir()` is below the run's basetemp | The install, plus the ceiling entry that basetemp already is. |
| Everything `tempfile` creates is inside the ceiling — and inside a git work tree **only** if the test makes one there | The ceiling stops discovery above the basetemp. |
| Temp artifacts vanish with the run | They live inside the basetemp, which `run_basetemp` wipes on success and reaps on failure. No second reaper. |
| The root exists before any test body | The guard fixture resolves `getbasetemp()` (pytest's one reset of a given basetemp) and re-creates `<basetemp>/tmp` immediately after. Without it, `tempfile` silently falls back to the platform temp root. |
| A child environment built from scratch keeps the boundary | Each such helper merges `tests/_support/temp_root.py::harness_env()` — the ceiling and the temp-root triple only. |

## 4. What a test may still do locally

Narrowing the ceiling for one test stays supported and is the sanctioned pattern:

```python
monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
```

It is narrower than the run-wide ceiling, which is what makes a "nothing here" verdict
deterministic under xdist. `tests/_support/git_ceiling.py`'s `install_git_ceilings` keeps an
existing value verbatim and only appends, so a per-test narrowing is never re-normalised.
