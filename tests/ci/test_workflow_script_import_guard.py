"""Regression guard: every workflow-invoked ``scripts/`` file must survive a bare-script run.

RED-FIRST for #5000: ``ci-fleet-verdict.yml`` invokes ``scripts/ci/fleet_verdict.py``
as a plain script (``python3 scripts/ci/fleet_verdict.py ...``), never ``python -m``
and never an installed console entry. A bare script run puts the *script's own
directory* (``scripts/ci/``) at ``sys.path[0]``, not the repository root, so its
module-level ``from scripts.ci.reconcile_retry import retry_with_backoff`` raised
``ModuleNotFoundError: No module named 'scripts'`` on every ``identify``/``report``
job run -- the ``identify`` job was red on every push (the regression landed in
commit 50777e5fc). ``scripts/ci/stale_running_sweep.py`` already carries the fix
for this exact defect class: resolve the repo root from ``__file__`` and insert it
onto ``sys.path`` before importing any ``scripts.*`` sibling.

This test closes the defect class by construction (DIRECTIVE_043) rather than
pinning one script: it derives the list of scripts every ``.github/workflows/*.yml``
file invokes as a bare script (``python``/``python3 <path>``, excluding ``-m``
module invocations, which already have the repo root on ``sys.path`` via the
interpreter's own module-mode bootstrap and are not exposed to this defect).

Scoping the executed set to the defect class (DIRECTIVE_043): a bare script run
can only raise ``ModuleNotFoundError: No module named 'scripts'`` if the script's
OWN source imports ``scripts`` or a ``scripts.*`` submodule -- that is the only
statement shape that resolves the ``scripts`` package name at all. A script that
never imports ``scripts.*`` cannot possibly exhibit this defect, under any cwd or
argument, so the derived workflow-invoked list is narrowed with an ``ast`` parse
of each script's own source (``_imports_scripts_package`` /
``_scripts_exposed_to_bare_script_import_defect`` below) down to exactly the
scripts that contain a module-level ``Import``/``ImportFrom`` naming ``scripts``
or ``scripts.*``. Excluding the rest is not "skipping to get a pass" -- a script
with no such import has no mechanism to raise this particular
``ModuleNotFoundError``, so running it under this guard would only ever add
unrelated hazard exposure (real file/network side effects from a script's actual
``--help``-agnostic logic) without covering any more of the defect class. Only
MODULE-level imports count: the failure happens at import time, before ``main()``
(or any other function) is ever called. "Module level" means every statement that
executes unconditionally as the module runs top to bottom -- not just a bare
top-level statement, but also one nested inside an ``if``/``try``/``except``/
``else``/``finally``/``with``/``for``/``while``/``match`` block, however deep,
because none of those defer execution the way a function body does
(op-rereview-001: the earlier version of this scan recursed only into ``ast.If``,
so a ``try: from scripts.ci.x import y`` / ``except ImportError:`` guard -- a real
alternative to the ``if``-guard style this repo uses today -- was silently
invisible to the scan). An import nested inside a ``def``/``async def`` function
body, or inside a ``lambda``, is correctly excluded: that body only executes if
and when the function is later called, which ``--help`` never does. ``class``
bodies are a deliberate middle case: unlike a function body, a ``class``
statement's body runs immediately -- at module-import time -- while building the
class object, so a module-level ``class Foo: from scripts.ci import bar`` is
exposed to the exact same ``ModuleNotFoundError`` as a bare or ``if``-guarded
import. This scan therefore DOES recurse into ``ClassDef`` bodies (see
``_nested_module_level_stmt_lists``) even though it treats ``FunctionDef``/
``AsyncFunctionDef`` as opaque; a ``ClassDef`` nested inside another ``ClassDef``
is then covered too, for free, since walking the outer body naturally reaches it.
A guard-protected import (``if <repo root not on sys.path>:
sys.path.insert(...)`` immediately followed by ``from scripts.x import y``) is
still scanned: it is a sibling MODULE-level statement that runs unconditionally
at import time, same as every guarded import in this repository's own fixed
scripts (``fleet_verdict.py``, ``stale_running_sweep.py``,
``wait_for_artifacts.py``, ``glossary_linker.py``, ``plantuml_render.py``,
``seo_verify.py`` at the time this scoping was added).

The workflow-invoked candidate list is derived by parsing each workflow's YAML
(``jobs.<job>.steps[].run``) with ``yaml.safe_load`` and scanning only those
``run:`` shell-block strings for the bare-script pattern -- never the workflow
file's raw text (op-rereview-002: a raw full-text scan also matches the pattern
inside an ordinary ``#``-comment line that is not inside any ``run:`` block at
all, e.g. a stale reference left behind after a script move/rename or a
descriptive comment mentioning a script by name). Parsing the YAML properly was
chosen over hardening the regex to skip ``#``-prefixed lines because walking the
parsed document to the actual ``run:`` strings is exact regardless of comment
placement, indentation, or block-scalar style, where a comment-stripping regex
would only ever approximate the same thing (and would still need to avoid
stripping a ``#`` that is legitimately inside quoted shell text). A workflow that
references a ``scripts/*.py`` path which does not exist on disk (a rename, a
moved file, a typo) is itself a real CI defect, not something to drop silently --
but that check must not run at collection time, inside the
``@pytest.mark.parametrize(...)`` call below, where an uncaught
``FileNotFoundError`` would fail collection of this ENTIRE file with a confusing
traceback instead of a clean, targeted assertion (op-rereview-002).
``_imports_scripts_package`` therefore treats a missing path as simply
not-provably-exposed (returns ``False``, never raises) at collection time, and
``test_workflow_invoked_scripts_resolve_to_real_files`` below asserts, at
ordinary test-execution time, that every derived path actually exists --
naming the offending path(s) if not.

The only assertion on the filtered set is the precise defect-class floor: no
``ModuleNotFoundError: No module named 'scripts'`` at import time. It does not
assert a blanket exit 0 for ``--help`` -- an argparse-based script's ``--help``
always exits via ``SystemExit(0)`` before reaching any real logic, but a script
without argparse handling (audited case by case below) may treat ``--help`` as
ordinary input and still return 0 through its own control flow; neither shape
raises this ``ModuleNotFoundError``, which is all this test asserts.

Mirrors the equivalent guard in ``tests/ci/test_wait_for_artifacts.py``
(``test_script_runs_as_a_bare_subprocess_without_import_error``, #4932) which
first established this exact repro shape (bare-script subprocess, ``PYTHONPATH``
stripped, no ``ModuleNotFoundError``) for one script; this test generalizes it to
every workflow-invoked script that can exhibit the defect, rather than
hand-adding one regression test per future script.

Subprocess isolation (op-review-001): each subprocess below runs with ``cwd`` set
to the test's own ``tmp_path`` and is invoked by the script's ABSOLUTE path, never
a repo-root-relative one. This still exercises the exact defect class -- the
``ModuleNotFoundError`` comes from ``sys.path[0]``, which a bare script run always
seeds from the script's OWN directory (``Path(sys.argv[0]).resolve().parent``),
never from the process cwd -- while denying every script a real repo-root cwd to
write into.

Every script in the ``scripts.*``-import-filtered set was individually audited
for side effects under ``<abs path> --help`` with ``cwd=tmp_path`` (writes outside
``tmp_path``, including ``__file__``-anchored paths, and network access):
- ``fleet_verdict.py``, ``stale_running_sweep.py``, ``glossary_linker.py``, and
  ``seo_verify.py`` are all argparse-based; ``--help`` is handled by argparse's
  own built-in action, which prints usage and exits via ``SystemExit(0)`` before
  any of the script's real logic (file I/O, network) runs.
- ``wait_for_artifacts.py`` has no argument parsing at all -- ``main()`` reads
  ``os.environ["SOURCE_RUN_ID"]`` unconditionally first and ignores ``argv``
  entirely, so ``--help`` is inert. In this test's subprocess environment those
  env vars are unset, so the read raises ``KeyError``, caught by the function's
  own documented always-exit-0 handler (``except Exception`` -> prints one
  ``::error::`` line -> ``return 0``), before either of the module's later env
  reads or its ``GitHub`` API client is ever constructed.
- ``plantuml_render.py`` also has no argparse handling: ``main()`` takes
  ``args[0]`` (here the literal string ``"--help"``) as a relative ``site_dir``.
  ``Path("--help").rglob("*.html")`` under ``cwd=tmp_path`` resolves to a
  non-existent directory and yields zero matches (``pathlib`` does not raise for
  a missing ``rglob`` root), so ``process_site`` writes nothing and never invokes
  its PlantUML/network seam, which only runs per matched page.
Every one of the six was additionally verified empirically (no new files outside
its own ``tmp_path``, no non-empty stderr, exit 0) when this scoping was added --
observed under CI's installed venv. Under a *non-installed* interpreter a script
may instead exit non-zero on a different transitive import (e.g. ``seo_verify.py``
-> ``kernel``); that is unrelated to this guard, whose sole assertion is the
absence of ``No module named 'scripts'``, so such a run neither passes nor fails
it spuriously.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# Spawns a real subprocess per parametrized script (~dozens of ms to low seconds
# each; one case measured 5.83s) -- legitimately slow, subprocess-fanning tests,
# so this is `integration` and NEVER `fast` (pytest.ini's `fast` marker is
# documented as "no subprocess/git overhead, sub-second per test"; see
# tests/ci/test_sonarcloud_branch_review.py's identical rationale comment). The
# `ci` module row in `.github/ci-module-registry.yml` selects the whole
# `tests/ci` directory by `test_dirs`, and `module-tests.yml`'s pytest invocation
# only ever deselects `performance`/`stress` -- so this marker change does not
# drop the file from the per-PR `ci` shard.
pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"

# Matches a bare `python3 scripts/ci/foo.py` / `python scripts/docs/bar.py` style
# invocation anywhere in a workflow step's `run:` shell text -- including
# mid-pipeline (`| python3 scripts/ci/foo.py`) and behind an explicit interpreter
# path (`.venv/bin/python scripts/ci/foo.py`) -- while excluding `python3 -m
# scripts.ci.foo`, which already runs with the repo root on `sys.path[0]` and is
# not exposed to this defect class. To keep the guard true "by construction" the
# interpreter also accepts a version suffix (`python3.11`/`python3.12`) and the
# script path accepts `-`/`.` in a segment (`scripts/ci/foo-bar.py`), so a future
# workflow adopting either spelling does not silently drop out of the guarded set.
_BARE_SCRIPT_INVOCATION = re.compile(r"(?<![\w.-])python3?(?:\.\d+)?\s+(?!-m\b)(scripts/[\w./-]+\.py)\b")


def _workflow_run_blocks(workflow_path: Path) -> list[str]:
    """Every job step's ``run:`` shell-block text in ``workflow_path``, from a real
    YAML parse -- never the file's raw text. See the module docstring
    (op-rereview-002) for why: a raw full-text regex scan also matches inside an
    ordinary ``#``-comment that sits outside every ``run:`` block."""
    document = yaml.safe_load(workflow_path.read_text(encoding="utf-8")) or {}
    jobs = document.get("jobs") or {}
    blocks: list[str] = []
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            run = step.get("run") if isinstance(step, dict) else None
            if isinstance(run, str):
                blocks.append(run)
    return blocks


def _workflow_invoked_scripts() -> list[str]:
    """Every distinct ``scripts/...py`` path any workflow runs as a bare script,
    matched only inside actual ``run:`` shell text (op-rereview-002)."""
    found: set[str] = set()
    # GitHub Actions honours both extensions, so discover `*.yaml` as well as
    # `*.yml` -- a future workflow saved as `.yaml` must not be invisible here.
    for workflow in sorted([*_WORKFLOWS_DIR.glob("*.yml"), *_WORKFLOWS_DIR.glob("*.yaml")]):
        for run_block in _workflow_run_blocks(workflow):
            found.update(_BARE_SCRIPT_INVOCATION.findall(run_block))
    return sorted(found)


def _imported_module_names(stmt: ast.stmt) -> list[str]:
    """Every module name a single ``Import``/``ImportFrom`` statement binds."""
    if isinstance(stmt, ast.Import):
        return [alias.name for alias in stmt.names]
    if isinstance(stmt, ast.ImportFrom) and stmt.module:
        return [stmt.module]
    return []


def _is_scripts_module(name: str) -> bool:
    return name == "scripts" or name.startswith("scripts.")


def _nested_module_level_stmt_lists(stmt: ast.stmt) -> list[list[ast.stmt]]:
    """Every statement list nested directly inside ``stmt`` that still runs
    unconditionally at module-load time whenever ``stmt`` itself does -- i.e.
    every branch of every compound statement EXCEPT the ones that defer
    execution until later (``FunctionDef``/``AsyncFunctionDef`` bodies, which
    only run when called; see the module docstring, op-rereview-001).

    ``ast.ClassDef`` bodies ARE included on purpose: unlike a function body, a
    class body executes immediately when the ``class`` statement itself runs
    (that is how the class's attributes and methods get bound), so a
    module-level ``class Foo: from scripts.ci import bar`` is exposed to the
    exact same ``ModuleNotFoundError`` as an import inside an ``if``/``try``/
    ``with`` block. ``ast.Lambda`` is deliberately absent from this table: its
    body is a single expression, which can never itself be an
    ``Import``/``ImportFrom`` statement, so there is nothing to recurse into.
    """
    if isinstance(stmt, (ast.Try, ast.TryStar)):
        return [stmt.body, stmt.orelse, stmt.finalbody, *(handler.body for handler in stmt.handlers)]
    if isinstance(stmt, ast.Match):
        return [case.body for case in stmt.cases]
    if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
        return [stmt.body, stmt.orelse]
    if isinstance(stmt, (ast.With, ast.AsyncWith, ast.ClassDef)):
        return [stmt.body]
    return []


def _has_module_level_scripts_import(stmts: list[ast.stmt]) -> bool:
    """True if a MODULE-level statement in ``stmts`` imports ``scripts`` or a
    ``scripts.*`` submodule. See the module docstring for why only module-level
    imports count -- including ones nested arbitrarily deep inside ``if``,
    ``try``/``except``/``else``/``finally``, ``with``, ``for``, ``while``,
    ``match``, or ``class`` bodies, but never inside a ``def``/``async def``
    body (op-rereview-001)."""
    for stmt in stmts:
        if any(_is_scripts_module(name) for name in _imported_module_names(stmt)):
            return True
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue  # only executes when called, never at module-load time
        for nested_stmts in _nested_module_level_stmt_lists(stmt):
            if _has_module_level_scripts_import(nested_stmts):
                return True
    return False


def _imports_scripts_package(script_path: Path) -> bool:
    """True if ``script_path`` can raise ``ModuleNotFoundError: No module named
    'scripts'`` -- i.e. its own source imports ``scripts``/``scripts.*`` at
    module level.

    A missing ``script_path`` returns ``False`` rather than raising: this
    function is called from inside a ``@pytest.mark.parametrize(...)`` call at
    COLLECTION time (op-rereview-002), where an uncaught ``FileNotFoundError``
    would fail collection of the whole test file with a confusing traceback
    instead of a clean, targeted assertion. A workflow referencing a
    nonexistent script is a real defect and IS still caught -- just at ordinary
    test-execution time, by ``test_workflow_invoked_scripts_resolve_to_real_files``.
    """
    if not script_path.exists():
        return False
    tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    return _has_module_level_scripts_import(tree.body)


def _scripts_exposed_to_bare_script_import_defect() -> list[str]:
    """Narrow the workflow-invoked set to the actual defect class: only scripts
    whose own source can raise the ``scripts`` package ``ModuleNotFoundError``."""
    return [script for script in _workflow_invoked_scripts() if _imports_scripts_package(_REPO_ROOT / script)]


def test_workflow_invoked_scripts_is_a_non_vacuous_floor() -> None:
    """Both the raw derived list and its scripts.*-import-filtered subset must
    actually cover the regressed script (and its already-fixed sibling), or the
    parametrized guard below would pass vacuously."""
    scripts = _workflow_invoked_scripts()
    assert "scripts/ci/fleet_verdict.py" in scripts
    assert "scripts/ci/stale_running_sweep.py" in scripts
    assert "scripts/ci/fleet_main.py" not in scripts, "fleet_main.py is invoked via `-m`, not as a bare script"

    filtered = _scripts_exposed_to_bare_script_import_defect()
    assert "scripts/ci/fleet_verdict.py" in filtered
    assert "scripts/ci/stale_running_sweep.py" in filtered


def test_workflow_invoked_scripts_resolve_to_real_files() -> None:
    """A workflow invoking a ``scripts/*.py`` path that does not exist on disk is
    itself a real CI defect (a rename, a moved file, a typo) -- fail with a
    clear, targeted assertion naming the missing path(s) rather than let
    collection crash opaquely (op-rereview-002; see ``_imports_scripts_package``
    for why this check cannot live at collection time)."""
    missing = [script for script in _workflow_invoked_scripts() if not (_REPO_ROOT / script).exists()]
    assert not missing, f"workflow(s) invoke script path(s) that do not exist on disk: {sorted(missing)}"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("if True:\n    import scripts.ci.foo\n", True, id="if-guard"),
        pytest.param(
            "try:\n    from scripts.ci import foo\nexcept ImportError:\n    foo = None\n",
            True,
            id="try-except-importerror",
        ),
        pytest.param(
            "import contextlib\nwith contextlib.suppress(ImportError):\n    import scripts.ci.foo\n",
            True,
            id="with-block",
        ),
        pytest.param("def f():\n    import scripts.ci.foo\n", False, id="function-body-excluded"),
        pytest.param("import os\nimport sys\n", False, id="no-import"),
        pytest.param(
            "try:\n    pass\nexcept ValueError:\n    pass\nelse:\n    import scripts.ci.foo\n",
            True,
            id="try-else",
        ),
        pytest.param("try:\n    pass\nfinally:\n    import scripts.ci.foo\n", True, id="try-finally"),
        pytest.param("class Foo:\n    import scripts.ci.foo\n", True, id="class-body-included"),
        pytest.param(
            "match 1:\n    case 1:\n        import scripts.ci.foo\n    case _:\n        pass\n",
            True,
            id="match-case",
        ),
        pytest.param("async def f():\n    import scripts.ci.foo\n", False, id="async-function-body-excluded"),
    ],
)
def test_has_module_level_scripts_import_filter(source: str, expected: bool) -> None:
    """Pure-logic coverage of the AST recursion itself (op-rereview-001) -- feeds
    synthetic source strings straight to the helper, no subprocess and no
    filesystem beyond an in-memory ``ast.parse``."""
    tree = ast.parse(source)
    assert _has_module_level_scripts_import(tree.body) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("run_text", "expected"),
    [
        pytest.param("python3 scripts/ci/foo.py", "scripts/ci/foo.py", id="python3"),
        pytest.param("python scripts/docs/bar.py --write", "scripts/docs/bar.py", id="python-with-args"),
        pytest.param(".venv/bin/python scripts/ci/foo.py", "scripts/ci/foo.py", id="explicit-interpreter-path"),
        pytest.param("cat x | python3 scripts/ci/foo.py", "scripts/ci/foo.py", id="mid-pipeline"),
        pytest.param("python3.11 scripts/ci/foo.py", "scripts/ci/foo.py", id="version-suffixed-interpreter"),
        pytest.param("python3.12 scripts/ci/foo_bar.py", "scripts/ci/foo_bar.py", id="version-suffixed-minor"),
        pytest.param("python3 scripts/ci/foo-bar.py", "scripts/ci/foo-bar.py", id="hyphenated-filename"),
        pytest.param("python3 scripts/ci/foo.bar.py", "scripts/ci/foo.bar.py", id="dotted-filename"),
        pytest.param("python3 -m scripts.ci.foo", None, id="module-mode-excluded"),
        pytest.param("mypython3 scripts/ci/foo.py", None, id="interpreter-substring-excluded"),
    ],
)
def test_bare_script_invocation_regex(run_text: str, expected: str | None) -> None:
    """Pure-logic coverage of the discovery regex: it must catch every bare
    `python[3[.N]] scripts/....py` spelling (including version-suffixed
    interpreters and `-`/`.` in a filename) while still excluding `-m` module
    mode and an interpreter-name substring like `mypython3`."""
    match = _BARE_SCRIPT_INVOCATION.search(run_text)
    assert (match.group(1) if match else None) == expected


@pytest.mark.parametrize("script", _scripts_exposed_to_bare_script_import_defect(), ids=lambda s: s)
def test_workflow_invoked_script_survives_bare_run_without_module_not_found(script: str, tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    proc = subprocess.run(
        [sys.executable, str(_REPO_ROOT / script), "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = proc.stdout + proc.stderr
    assert "No module named 'scripts'" not in combined, combined
