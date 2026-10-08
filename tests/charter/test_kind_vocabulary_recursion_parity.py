"""Resolver-side org/project recursion parity (WP02 / T008, T009, T013).

Red-first: on `main` the charter-activation resolver emits the flat org dir and
the layer dirs with ``recursive=False``, so a nested org/project artifact that
loads at runtime (and lists via ``pack_manager``) is NOT resolved for
``charter activate`` — the #3426 list-vs-activate divergence. After WP02 the
resolver derives recursion from the same shared authority the loader consults.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.kind_vocabulary import (
    UnknownArtifactIdError,
    resolve_artifact_urn,
)
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.fast, pytest.mark.unit]


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


# ── T008: nested org styleguide resolves (closes #3426) ───────────────────────


def test_nested_org_styleguide_resolves(tmp_path: Path) -> None:
    """A styleguide under ``styleguides/writing/`` in an org pack activates."""
    pack = tmp_path / "orgpack"
    _write(
        pack / "styleguides" / "writing" / "wp02sg.styleguide.yaml",
        {"id": "wp02-nested-styleguide"},
    )
    urn = resolve_artifact_urn(
        ArtifactKind.STYLEGUIDE,
        "wp02sg",
        doctrine_root=tmp_path / "doctrine_root",
        org_roots=[pack],
    )
    assert urn == "styleguide:wp02-nested-styleguide"


# ── T009: nested org + project tactic resolve ─────────────────────────────────


def test_nested_org_tactic_resolves(tmp_path: Path) -> None:
    pack = tmp_path / "orgpack"
    _write(
        pack / "tactics" / "testing" / "wp02t.tactic.yaml",
        {"id": "wp02-nested-tactic"},
    )
    urn = resolve_artifact_urn(
        ArtifactKind.TACTIC,
        "wp02t",
        doctrine_root=tmp_path / "doctrine_root",
        org_roots=[pack],
    )
    assert urn == "tactic:wp02-nested-tactic"


def test_nested_project_tactic_resolves(tmp_path: Path) -> None:
    """The project layer (``<project pack root>/tactic/``) also recurses."""
    proj = tmp_path / "project"
    _write(
        proj / "doctrine" / "tactic" / "sub" / "wp02p.tactic.yaml",
        {"id": "wp02-project-tactic"},
    )
    urn = resolve_artifact_urn(
        ArtifactKind.TACTIC,
        "wp02p",
        doctrine_root=tmp_path / "doctrine_root",
        layer_roots={"project": proj / "doctrine"},
    )
    assert urn == "tactic:wp02-project-tactic"


# ── T013: loader↔resolver parity for the exercised kinds ──────────────────────


def test_resolver_matches_loader_for_nested_org_tactic(tmp_path: Path) -> None:
    """The resolver discovers exactly what the loader discovers for a nested org tactic."""
    from charter.offering.tactics.repository import TacticRepository

    pack = tmp_path / "orgpack"
    built_in = tmp_path / "built-in"
    built_in.mkdir()
    _write(pack / "tactics" / "deep" / "parity.tactic.yaml", {"id": "parity-tactic"})
    # A valid tactic for the loader (needs schema fields, not just id).
    _write(
        pack / "tactics" / "deep" / "parity.tactic.yaml",
        {
            "schema_version": "1.0",
            "id": "parity-tactic",
            "name": "Parity",
            "steps": [{"title": "step"}],
        },
    )

    # Loader discovers it.
    repo = TacticRepository(built_in_dir=built_in, org_dirs=[pack / "tactics"])
    assert repo.get("parity-tactic") is not None

    # Resolver discovers it (same nested file, same recursion authority).
    urn = resolve_artifact_urn(
        ArtifactKind.TACTIC,
        "parity",
        doctrine_root=tmp_path / "doctrine_root",
        org_roots=[pack],
    )
    assert urn == "tactic:parity-tactic"


def test_flat_org_styleguide_still_resolves(tmp_path: Path) -> None:
    """NFR-002: a flat (non-nested) org artifact still resolves unchanged."""
    pack = tmp_path / "orgpack"
    _write(pack / "styleguides" / "flat.styleguide.yaml", {"id": "flat-sg"})
    urn = resolve_artifact_urn(
        ArtifactKind.STYLEGUIDE,
        "flat",
        doctrine_root=tmp_path / "doctrine_root",
        org_roots=[pack],
    )
    assert urn == "styleguide:flat-sg"


def test_missing_config_id_still_raises(tmp_path: Path) -> None:
    """A genuinely absent artifact still fails closed (no silent fallback)."""
    with pytest.raises(UnknownArtifactIdError):
        resolve_artifact_urn(
            ArtifactKind.STYLEGUIDE,
            "does-not-exist-wp02",
            doctrine_root=tmp_path / "doctrine_root",
            org_roots=[tmp_path / "empty"],
        )
