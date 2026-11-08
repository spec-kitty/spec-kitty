"""Regression guard for #5179: the docs-freshness script must run as a bare file.

``python scripts/docs/check_docs_freshness.py --ci`` is the invocation the
mission-wrap-up docs step uses. A bare script run puts the *script's own
directory* (``scripts/docs/``) on ``sys.path[0]``, never the repository root, so
its lazy ``from scripts.docs... import ...`` sub-check imports raise
``ModuleNotFoundError: No module named 'scripts'`` unless the script anchors the
repo root itself. The orchestrator's module-level imports are all outside
``scripts`` (``kernel`` resolves from the installed package), which is why a
``--help`` smoke run would not have caught this and why the lazy import sites
are exercised directly here.

Kept out of ``tests/docs/test_check_docs_freshness.py`` because that module is
marked ``fast`` and pytest's marker rules forbid subprocesses under it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "docs" / "check_docs_freshness.py"


def test_the_script_anchors_the_repo_root_before_its_lazy_scripts_imports(tmp_path: Path) -> None:
    """Executing the script from a foreign cwd makes ``scripts.*`` importable.

    The probe imports the script by file path (as a bare run does), then imports
    the two siblings its sub-check helpers reach lazily. Without the repo-root
    guard the second step raises ``No module named 'scripts'``; nothing else in
    the probe touches the filesystem or the network.
    """
    probe = (
        "import importlib.util\n"
        "import sys\n"
        f"spec = importlib.util.spec_from_file_location('cdf_probe', {str(_SCRIPT)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n"
        "import scripts.docs.inventory_lockfile\n"
        "import scripts.docs.docs_index\n"
    )
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "No module named 'scripts'" not in result.stderr
