"""Fast unit coverage for status preflight path classifiers."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.preflight import is_dossier_snapshot

pytestmark = pytest.mark.fast


@pytest.mark.parametrize(
    "candidate",
    [
        Path(".kittify/dossiers/my-mission/snapshot-latest.json"),
        "./kitty-specs/demo/.kittify/dossiers/demo/snapshot-latest.json",
        "kitty-specs\\demo\\.kittify\\dossiers\\demo\\snapshot-latest.json",
    ],
)
def test_is_dossier_snapshot_normalizes_supported_paths(candidate: str | Path) -> None:
    assert is_dossier_snapshot(candidate) is True


def test_is_dossier_snapshot_rejects_non_snapshot_file() -> None:
    assert is_dossier_snapshot("./kitty-specs/demo/spec.md") is False


def test_is_dossier_snapshot_filter_preserves_unrelated_paths() -> None:
    paths = [
        "src/specify_cli/status/preflight.py",
        "./kitty-specs/demo/.kittify/dossiers/demo/snapshot-latest.json",
        "kitty-specs/demo/spec.md",
    ]

    assert [p for p in paths if not is_dossier_snapshot(p)] == [
        "src/specify_cli/status/preflight.py",
        "kitty-specs/demo/spec.md",
    ]
