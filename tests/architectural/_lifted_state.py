"""Single home of the state-doctor runtime-root tests (#5015).

``tests/state/test_doctor_spec_kitty_home.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_state.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.paths import get_runtime_root
from specify_cli.state.doctor import StateRootsReport, check_state_roots


def _global_sync_root(report: StateRootsReport) -> Path:
    """Return the resolved global-sync root from a state-roots report."""
    root: Path = next(r.resolved_path for r in report.roots if r.name == "global_sync")
    return root


def test_reported_root_matches_runtime_root_with_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SPEC_KITTY_HOME set: reported global-sync root == base == env value."""
    env_root = tmp_path / "custom-home"
    env_root.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(env_root))

    report = check_state_roots(tmp_path)

    assert _global_sync_root(report) == get_runtime_root().base == env_root


def test_reported_root_matches_runtime_root_without_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SPEC_KITTY_HOME unset: reported root == base (default ~/.spec-kitty)."""
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    report = check_state_roots(tmp_path)

    assert _global_sync_root(report) == get_runtime_root().base
    assert _global_sync_root(report) == tmp_path / ".spec-kitty"
