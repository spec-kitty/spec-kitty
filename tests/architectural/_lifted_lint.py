"""Single home of the canonical-producer lint loader and its two round-trip invariants (#5015).

``tests/lint/test_canonical_producers.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_lint.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

# Load the lint module by file path. The script lives in scripts/ which is
# not a Python package on PYTHONPATH; importlib lets us treat it as a module
# without polluting sys.path semantics.
_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lint_canonical_producers.py"


_LINT_MODULE_NAME = "lint_canonical_producers"


#: Populated by the autouse ``_lint_module`` fixture below, once per module.
lint: ModuleType


@pytest.fixture(scope="module", autouse=True)
def _lint_module() -> Iterator[ModuleType]:
    """Load the lint script once for this module's tests.

    ``dataclass()`` on a class defined in a dynamically-loaded module looks
    the class up via ``sys.modules[cls.__module__]``, so the module must be
    registered there before ``exec_module`` runs. A module-scoped
    ``pytest.MonkeyPatch.context()`` — not the function-scoped ``monkeypatch``
    fixture, which a module-scoped fixture cannot depend on — keeps that
    registration and undoes it once every test in this module has run.
    """
    global lint
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_LINT_MODULE_NAME, _SCRIPT_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _LINT_MODULE_NAME, module)
        spec.loader.exec_module(module)
        lint = module
        yield module


def _write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


def _lint_source(tmp_path: Path, source: str, name: str = "candidate.py") -> list[Any]:
    path = _write(tmp_path, name, source)
    findings: list[Any] = lint.lint_paths([path])
    return findings


def test_lint_clean_canonical_construction_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        from spec_kitty_events.lifecycle import WPApprovedPayload

        def make():
            return WPApprovedPayload(
                wp_id="WP01",
                actor="claude",
            )
        """,
    )
    assert findings == []


def test_lint_hand_rolled_event_dict_fires_cp001(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def f():
            x = {"event_type": "WPApproved", "payload": {"wp_id": "WP01"}}
            return x
        """,
    )
    codes = [f.code for f in findings]
    assert "CP001" in codes
    assert all(f.path.name == "candidate.py" for f in findings)
