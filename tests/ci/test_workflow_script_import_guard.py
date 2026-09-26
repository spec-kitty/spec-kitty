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
(or any other function) is ever called, so an import nested inside a function or
class body -- which only executes if that function is later called, which
``--help`` never does -- cannot exhibit this defect under this harness and is
correctly excluded from the scan. A guard-protected import (``if <repo root not
on sys.path>: sys.path.insert(...)`` immediately followed by
``from scripts.x import y``) is still scanned: it is a sibling MODULE-level
statement that runs unconditionally at import time, same as every guarded import
in this repository's own fixed scripts (``fleet_verdict.py``,
``stale_running_sweep.py``, ``wait_for_artifacts.py``, ``glossary_linker.py``,
``plantuml_render.py``, ``seo_verify.py`` at the time this scoping was added).

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
its own ``tmp_path``, no non-empty stderr, exit 0) when this scoping was added.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

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
# invocation anywhere in a workflow's `run:` shell text -- including mid-pipeline
# (`| python3 scripts/ci/foo.py`) and behind an explicit interpreter path
# (`.venv/bin/python scripts/ci/foo.py`) -- while excluding `python3 -m
# scripts.ci.foo`, which already runs with the repo root on `sys.path[0]` and is
# not exposed to this defect class.
_BARE_SCRIPT_INVOCATION = re.compile(r"(?<![\w.-])python3?\s+(?!-m\b)(scripts/[\w/]+\.py)\b")


def _workflow_invoked_scripts() -> list[str]:
    """Every distinct ``scripts/...py`` path any workflow runs as a bare script."""
    found: set[str] = set()
    for workflow in sorted(_WORKFLOWS_DIR.glob("*.yml")):
        found.update(_BARE_SCRIPT_INVOCATION.findall(workflow.read_text(encoding="utf-8")))
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


def _has_module_level_scripts_import(stmts: list[ast.stmt]) -> bool:
    """True if a MODULE-level statement in ``stmts`` imports ``scripts`` or a
    ``scripts.*`` submodule. See the module docstring for why only module-level
    imports (including ones nested in a top-level ``if`` guard) count."""
    for stmt in stmts:
        if any(_is_scripts_module(name) for name in _imported_module_names(stmt)):
            return True
        if isinstance(stmt, ast.If) and _has_module_level_scripts_import(stmt.body + stmt.orelse):
            return True
    return False


def _imports_scripts_package(script_path: Path) -> bool:
    """True if ``script_path`` can raise ``ModuleNotFoundError: No module named
    'scripts'`` -- i.e. its own source imports ``scripts``/``scripts.*`` at
    module level."""
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
