"""#5538: ``pack_validator`` derives its artifact-kind vocabulary from ``ArtifactKind``.

``_plural_to_urn_kind`` used to be a hand-copied 8-entry plural→singular map
beside the derived authority. Two consequences are pinned here:

* **No second edit for a new kind.** Every ``ArtifactKind`` plural resolves to
  its URN kind, so a kind added to the enum is accepted by the validator
  without touching ``pack_validator``.
* **No false dangling edge for an asset.** ``assets`` sidecars are scanned, but
  the hand map had no ``assets`` entry, so their ``asset:<id>`` URNs were never
  registered and a DRG edge to a pack's own asset was reported as
  ``drg_dangling_edge``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from specify_cli.doctrine.pack_validator import (
    _artifact_schema_registry,
    _plural_to_urn_kind,
    validate_pack,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("kind", list(ArtifactKind), ids=lambda k: k.value)
def test_every_artifact_kind_plural_resolves_to_its_urn_kind(kind: ArtifactKind) -> None:
    assert _plural_to_urn_kind(kind.plural) == kind.value


def test_unknown_plural_resolves_to_none() -> None:
    assert _plural_to_urn_kind("not_a_kind") is None


def test_schema_registry_globs_come_from_the_authority() -> None:
    for plural, (glob, _model) in _artifact_schema_registry().items():
        assert glob == ArtifactKind.from_plural(plural).glob_pattern, plural


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


def test_edge_to_a_packs_own_asset_is_not_dangling(tmp_path: Path) -> None:
    _write(
        tmp_path / "directives" / "acme-001.directive.yaml",
        """
        schema_version: "1.0"
        id: ACME-001
        title: Brand guidelines
        intent: Use the company logo in generated documents.
        enforcement: advisory
        """,
    )
    _write(
        tmp_path / "assets" / "company-logo.asset.yaml",
        """
        id: company-logo
        title: Company logo
        mime: image/png
        path: company-logo.png
        """,
    )
    (tmp_path / "assets" / "company-logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    graph_header = """
        schema_version: "1.0"
        generated_at: STATIC
        generated_by: test
        nodes: []
        """
    _write(tmp_path / "root.graph.yaml", graph_header + "        edges: []\n")
    _write(
        tmp_path / "drg" / "010-brand.graph.yaml",
        graph_header
        + """
        edges:
          - source: directive:ACME-001
            target: asset:company-logo
            relation: requires
        """,
    )

    result = validate_pack(tmp_path)

    dangling = [issue.message for issue in result.errors if issue.category == "drg_dangling_edge"]
    assert dangling == []
    assert result.ok, [issue.message for issue in result.errors]
