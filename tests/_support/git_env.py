"""Git environment helpers shared by tests that exercise the git read caches."""

from __future__ import annotations

import pytest

_INHERITED_GIT_CONFIG_ENV = ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS")


def remove_inherited_git_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop ``GIT_CONFIG_COUNT``/``GIT_CONFIG_PARAMETERS`` so a git read cache is not bypassed by the harness.

    Agent containers export them for credential and URL rewrites (CI does not), and the read caches bypass
    themselves by design when they are set. Call this from a module's autouse fixture.
    """
    for name in _INHERITED_GIT_CONFIG_ENV:
        monkeypatch.delenv(name, raising=False)
