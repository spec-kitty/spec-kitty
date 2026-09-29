"""Shared fixtures for adversarial tests."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class AttackVector:
    """Represents a single malicious or edge-case input being tested."""

    name: str  # Descriptive name
    input: str | bytes  # The malicious input
    category: str  # Category (path, csv, git, migration, config)
    expected: str  # Expected behavior (reject, warn, handle)
    description: str  # Human-readable description


@pytest.fixture
def malformed_csv_factory(tmp_path: Path) -> Callable[[AttackVector, str], Path]:
    """Factory fixture for creating malformed CSV files."""

    def _create(vector: AttackVector, filename: str = "test.csv") -> Path:
        csv_path = tmp_path / filename
        if isinstance(vector.input, bytes):
            csv_path.write_bytes(vector.input)
        else:
            csv_path.write_text(vector.input, encoding="utf-8")
        return csv_path

    return _create


# =============================================================================
# PLATFORM DETECTION FIXTURES (T005)
# =============================================================================


def _symlinks_supported() -> bool:
    """Check if symlinks are supported on this platform."""
    with tempfile.TemporaryDirectory() as tmp:
        test_dir = Path(tmp)
        target = test_dir / "target"
        link = test_dir / "link"
        target.mkdir()
        try:
            link.symlink_to(target)
            return True
        except OSError:
            return False  # Windows without elevation or restricted


@pytest.fixture(scope="session")
def symlinks_supported() -> bool:
    """Session fixture indicating whether symlinks work on this platform."""
    return _symlinks_supported()


@pytest.fixture
def symlink_factory(tmp_path: Path, symlinks_supported: bool) -> Callable[[str | Path, str], Path | None]:
    """Factory fixture for creating symlinks with platform awareness.

    Returns None if symlinks not supported, allowing tests to skip gracefully.
    """

    def _create(target: str | Path, link_name: str) -> Path | None:
        if not symlinks_supported:
            return None
        link_path = tmp_path / link_name
        # Ensure parent directory exists
        link_path.parent.mkdir(parents=True, exist_ok=True)
        link_path.symlink_to(target)
        return link_path

    return _create
