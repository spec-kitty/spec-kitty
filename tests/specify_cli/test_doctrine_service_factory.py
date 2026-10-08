"""Consumed factory boundary for activation-aware doctrine services."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.resolver import ActiveCharterService
from specify_cli.doctrine_service_factory import (
    build_active_charter_service,
)


pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


def test_factory_returns_the_charter_activation_wrapper(tmp_path: Path) -> None:
    """Callers receive the activation-aware public wrapper, not the raw service."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n",
        encoding="utf-8",
    )

    assert isinstance(build_active_charter_service(tmp_path), ActiveCharterService)
