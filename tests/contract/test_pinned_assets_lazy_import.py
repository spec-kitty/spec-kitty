"""Importing a test module never reads the pinned service cache (#6915).

The pinned extras of spec-kitty-events are read at TEST time and fail closed there. They are never read at
import, because jobs that only collect tests cannot see them: the shared test-universe collection, the
gate-coverage collection under its own temporary HOME, and any job that runs no ``sync-services`` step. An
import-time read made every such collection error out with ``SERVICE_BINARY_MISSING``.

This test imports, in a fresh interpreter whose cache is empty, every test module that reaches the pinned
assets. As a positive control, it first proves that the same interpreter really cannot read the extras.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast]

ROOT = Path(__file__).resolve().parents[2]
_MARKERS = ("pinned_service_assets", "_mission_status_payloads", "_mission_status_detail", "_mission_status_artifact_goldens")

_PROBE = r"""
import importlib, json, sys
from _pytest.outcomes import OutcomeException

modules = json.loads(sys.argv[1])
failures = {}
try:
    from tests.pinned_service_assets import pinned_extra
    pinned_extra("contracts")
    control = "read"
except OutcomeException as exc:
    control = str(exc)
for name in modules:
    try:
        importlib.import_module(name)
    except (OutcomeException, Exception) as exc:  # noqa: BLE001 - every failure is reported by module
        failures[name] = f"{type(exc).__name__}: {exc}"
print(json.dumps({"control": control, "failures": failures}))
"""


def _modules_reaching_the_pinned_assets() -> list[str]:
    found = []
    for path in sorted((ROOT / "tests").rglob("*.py")):
        if path.name == Path(__file__).name or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(marker in text for marker in _MARKERS):
            found.append(".".join(path.relative_to(ROOT).with_suffix("").parts))
    return found


def test_no_test_module_reads_the_pinned_cache_at_import(tmp_path: Path) -> None:
    modules = _modules_reaching_the_pinned_assets()
    assert len(modules) >= 10, f"control: the scan must find the pinned-asset readers, found {modules}"
    empty = tmp_path / "empty-cache"
    empty.mkdir()
    env = {**os.environ, "XDG_CACHE_HOME": str(empty), "HOME": str(tmp_path), "SPEC_KITTY_REAL_HOME_FOR_TESTS": str(tmp_path), "PYTHONPATH": str(ROOT)}
    result = subprocess.run([sys.executable, "-c", _PROBE, json.dumps(modules)], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert "SERVICE_" in report["control"], f"control: the empty cache must make a pinned read fail, got {report['control']!r}"
    assert report["failures"] == {}, "these test modules read the pinned cache at import; read it at test time instead"
