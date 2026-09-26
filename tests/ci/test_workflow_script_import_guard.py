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
interpreter's own module-mode bootstrap and are not exposed to this defect) and
runs each one exactly as CI does -- ``[sys.executable, script, "--help"]``, cwd the
repo root, ``PYTHONPATH`` stripped from the environment -- so a future script that
copies the same unguarded ``from scripts.`` import is caught here too, not just at
the next red push.

The only assertion is the precise defect-class floor: no
``ModuleNotFoundError: No module named 'scripts'`` at import time. It deliberately
does NOT assert a blanket exit 0 for ``--help`` across the whole set: at least one
workflow-invoked script (``reconcile_shards.py``) has no argparse ``--help``
handling and always runs its real logic (which needs files ``--help`` does not
provide), and this repository's own contributor test policy (AGENTS.md's
"stale-venv false reds") notes that an optional dependency such as ``coverage``
(consumed by ``validate_diff_coverage.py``) can be legitimately absent from a
given dev venv without that being a defect in the script's import wiring. Neither
condition has anything to do with the ``scripts.`` package resolving; both are
allowed to leave a non-zero exit code, so long as it is not this one bare-script
``ModuleNotFoundError``.

Mirrors the equivalent guard in ``tests/ci/test_wait_for_artifacts.py``
(``test_script_runs_as_a_bare_subprocess_without_import_error``, #4932) which
first established this exact repro shape (bare-script subprocess, ``PYTHONPATH``
stripped, no ``ModuleNotFoundError``) for one script; this test generalizes it to
every workflow-invoked script mechanically, rather than hand-adding one regression
test per future script.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

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


def test_workflow_invoked_scripts_is_a_non_vacuous_floor() -> None:
    """The derived script list must actually cover the regressed script (and its
    already-fixed sibling), or the parametrized guard below would pass vacuously."""
    scripts = _workflow_invoked_scripts()
    assert "scripts/ci/fleet_verdict.py" in scripts
    assert "scripts/ci/stale_running_sweep.py" in scripts
    assert "scripts/ci/fleet_main.py" not in scripts, "fleet_main.py is invoked via `-m`, not as a bare script"


@pytest.mark.parametrize("script", _workflow_invoked_scripts(), ids=lambda s: s)
def test_workflow_invoked_script_survives_bare_run_without_module_not_found(script: str) -> None:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    proc = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = proc.stdout + proc.stderr
    assert "No module named 'scripts'" not in combined, combined
