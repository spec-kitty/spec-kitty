"""Fixture wiring for ``tests/specify_cli/feedback/``.

Every test in this tree gets a ``tmp_path``-backed per-user config directory
so no test ever reads or writes the real user profile.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def feedback_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the Feedback Survey config-dir resolver under ``tmp_path``."""
    config_dir = tmp_path / "user-config" / "spec-kitty"
    monkeypatch.setattr("specify_cli.feedback.preferences.resolve_config_dir", lambda: config_dir)

    from specify_cli.feedback.preferences import preferences_path

    resolved = preferences_path()
    assert resolved.is_relative_to(tmp_path), f"preferences path escaped tmp_path: {resolved}"
    return config_dir
