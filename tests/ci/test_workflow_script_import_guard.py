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
runs each one exactly as CI invokes it -- ``[sys.executable, <absolute script
path>, "--help"]``, ``PYTHONPATH`` stripped from the environment -- so a future
script that copies the same unguarded ``from scripts.`` import is caught here
too, not just at the next red push. ``cwd`` is deliberately NOT the repo root;
see "Subprocess isolation" below.

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

Subprocess isolation (op-review-001): each subprocess below runs with ``cwd`` set
to the test's own ``tmp_path`` and is invoked by the script's ABSOLUTE path, never
a repo-root-relative one. This still exercises the exact defect class -- the
``ModuleNotFoundError`` comes from ``sys.path[0]``, which a bare script run always
seeds from the script's OWN directory (``Path(sys.argv[0]).resolve().parent``),
never from the process cwd -- while denying every script a real repo-root cwd to
write into. Concretely, this closes the hazard ``reconcile_shards.py`` has: it
carries no argparse/``--help`` handling and unconditionally runs
``resolved_dir.mkdir(parents=True, exist_ok=True)`` against its cwd-relative
default (``out/aggregate/coverage/``) before failing on a missing registry file --
previously this created a real, ``.gitignore``d ``out/aggregate/coverage/`` under
the repo root on every test run, invisible to ``git status`` and colliding with
``ci-aggregate.yml``'s own identical path contract on a persistent dev checkout.
With ``cwd=tmp_path`` that same relative default resolves harmlessly inside the
test's disposable directory instead.

Every other workflow-invoked script that lacks ``--help`` handling was audited for
the same class of hazard (cwd-relative writes or network calls) at the time this
isolation was added:
- ``scripts/ci/router_gate.py`` only reads ``sys.stdin`` (empty under pytest's
  captured stdin) and writes nothing.
- ``scripts/docs/plantuml_render.py`` treats ``--help`` as a literal, nonexistent
  ``site_dir`` positional and globs zero files under it; it writes nothing.
- ``scripts/release/extract_changelog.py`` only reads a cwd-relative
  ``CHANGELOG.md`` (absent under ``tmp_path``, so it exits 1 without writing).
- ``scripts/docs/generate_kitty_specs_docs.py`` is a DIFFERENT hazard shape this
  cwd change cannot neutralize: its output directory (``DEST``) is resolved from
  ``Path(__file__).resolve().parents[2]`` -- the script's own real repo-root
  location, not the process cwd -- so it unconditionally
  ``shutil.rmtree()``-and-regenerates the real (``.gitignore``d, but
  reproducible-from-tracked-source) ``docs/kitty-specs/`` on every run regardless
  of ``cwd``. Reported as a follow-up (out of locality-of-change scope for this
  fix, same as op-review-003): a future mission should give it argparse
  ``--help`` handling or an overridable output root, mirroring
  ``reconcile_shards.py``'s own remediation options.
Every argparse-based script in the parametrized set (the rest of the list) exits
via argparse's own ``--help`` handling before reaching any file or network I/O, so
none of them are exposed to either hazard shape.
"""

from __future__ import annotations

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


def test_workflow_invoked_scripts_is_a_non_vacuous_floor() -> None:
    """The derived script list must actually cover the regressed script (and its
    already-fixed sibling), or the parametrized guard below would pass vacuously."""
    scripts = _workflow_invoked_scripts()
    assert "scripts/ci/fleet_verdict.py" in scripts
    assert "scripts/ci/stale_running_sweep.py" in scripts
    assert "scripts/ci/fleet_main.py" not in scripts, "fleet_main.py is invoked via `-m`, not as a bare script"


@pytest.mark.parametrize("script", _workflow_invoked_scripts(), ids=lambda s: s)
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
