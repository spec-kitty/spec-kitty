"""The per-invocation startup owners include the legacy-location discard (#6488).

The discard runs from the CLI's startup owners list, which is the only production caller
of :func:`kernel.user_dirs_legacy.discard_legacy_locations`. A refactor that silently drops
the owner would leave the pre-convergence directories on disk forever with every other test
still green, so the wiring itself is pinned here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import specify_cli
from tests.kernel._user_dirs_pins import fake_platform

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_DISCARD_LABEL = "per-user cache locations"


def test_the_discard_owner_is_registered() -> None:
    labels = [label for label, _owner in specify_cli._startup_owners(["spec-kitty", "next"])]
    assert _DISCARD_LABEL in labels


def test_the_discard_owner_runs_first() -> None:
    """It is a handful of stats, and it must not race the assets that create new dirs."""
    owners = specify_cli._startup_owners(["spec-kitty", "next"])
    assert owners[0][0] == _DISCARD_LABEL


def test_the_doctor_skills_path_keeps_the_discard_owner() -> None:
    """``doctor skills`` skips the agent-commands repair, not the cache clean-up."""
    owners = specify_cli._startup_owners(["spec-kitty", "doctor", "skills"])
    labels = [label for label, _owner in owners]
    assert _DISCARD_LABEL in labels
    assert "agent commands" not in labels


def test_the_owner_calls_the_kernel_discard(monkeypatch: pytest.MonkeyPatch) -> None:
    import kernel.user_dirs_legacy as legacy

    calls: list[int] = []
    monkeypatch.setattr(legacy, "discard_legacy_locations", lambda: calls.append(1) or ())

    specify_cli._discard_legacy_user_dirs()

    assert calls == [1]


def test_the_owner_is_safe_on_a_fresh_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An empty home has nothing to discard; the owner is a no-op, not an error."""
    fake_platform(monkeypatch, tmp_path, "linux", {})
    specify_cli._discard_legacy_user_dirs()
