"""Import-path invariants for the glossary domain.

FR-004 (unshim wave 2): the ``specify_cli.glossary`` registered shim was
deleted; the canonical package is top-level ``glossary``. This mirrors
``tests/runtime/next/test_import_paths.py::test_legacy_specify_cli_next_shim_is_gone``
so all three deleted shim domains carry a symmetric reintroduction lock
(aggregate-squad fold on PR #2328 — without it, a re-created
``specify_cli/glossary/`` re-export would escape every other gate: the
unregistered-shim scanner keys on ``__deprecated__`` and the registry pin
only catches a re-added registry row).
"""

from __future__ import annotations

import importlib
import sys

import pytest

pytestmark = pytest.mark.fast


def test_canonical_glossary_imports() -> None:
    """The canonical top-level ``glossary`` package serves the domain."""
    glossary = importlib.import_module("glossary")
    assert glossary.__file__ is not None
    assert "src/glossary/" in glossary.__file__.replace("\\", "/")


def test_legacy_specify_cli_glossary_shim_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004 (unshim wave 2): the ``specify_cli.glossary`` shim is deleted.

    Absence pin (refactor-stable): the legacy import path must not silently
    return — not as a re-export shim and not as a namespace package revived
    by leftover directories.
    """
    for name in [n for n in sys.modules if n == "specify_cli.glossary" or n.startswith("specify_cli.glossary.")]:
        monkeypatch.setitem(sys.modules, name, None)
        monkeypatch.delitem(sys.modules, name)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("specify_cli.glossary")
