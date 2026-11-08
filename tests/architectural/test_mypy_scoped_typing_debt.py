"""Lock the scoped mypy invariant on three modules that carried pre-existing typing debt.

Each of these reported a ``no-any-return`` under the *narrow* mypy run a
contributor changing the file is told to do, while the hosted gate stayed green
because it does not scope-check these modules:

* ``src/specify_cli/cli/commands/charter/generate.py`` (#7141) — the validated
  owned root crossed the dynamic owned-checkout seam and came back as ``Any``.
* ``src/specify_cli/cli/commands/doctor.py`` (#7220) — ``_sanction_entry_snippet``
  imported from ``_charter_pack_collect`` resolved to ``Any`` under the
  ``specify_cli.*`` ``follow_imports = "skip"`` override.
* ``src/specify_cli/status/store.py`` (#6051) — ``EventStream`` is imported from a
  skipped module, so ``.transitions`` read as ``Any``.

Environment requirement: this test invokes mypy via ``sys.executable -m mypy``.
mypy lives in the ``dev`` group (a plain ``uv sync``) since #5064, so the default
lane environment satisfies it without ``--extra lint``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The scoped targets, each the exact file the reported error named.
SCOPED_TARGETS: tuple[str, ...] = (
    "src/specify_cli/cli/commands/charter/generate.py",  # #7141
    "src/specify_cli/cli/commands/doctor.py",  # #7220
    "src/specify_cli/status/store.py",  # #6051
)


@pytest.mark.slow  # mypy invocation is comparatively expensive
@pytest.mark.parametrize("target", SCOPED_TARGETS)
def test_scoped_module_is_mypy_strict_clean(target: str, tmp_path: Path) -> None:
    # A per-test --cache-dir keeps .mypy_cache/ out of the checkout (#6953,
    # test_spec_kitty_home_pin_census::test_no_mypy_subprocess_writes_a_cache_into_the_checkout).
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--cache-dir", str(tmp_path / "mypy_cache"), target],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"mypy --strict failed on {target}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
