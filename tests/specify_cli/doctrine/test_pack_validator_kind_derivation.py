"""#5538: ``pack_validator`` derives its artifact-kind vocabulary from ``ArtifactKind``.

``_plural_to_urn_kind`` used to be a hand-copied 8-entry plural→singular map
beside the derived authority. Two consequences are pinned here:

* **No false dangling edge for an asset.** ``assets`` sidecars are scanned, but
  the hand map had no ``assets`` entry, so their ``asset:<id>`` URNs were never
  registered and a DRG edge to a pack's own asset was reported as
  ``drg_dangling_edge``. The fail-closed variants (no manifest, or a manifest
  that fails its schema) must still report the edge as dangling.
* **The inverse stays honest.** ``_kind_singular`` maps every plural the intent
  pass reports back to the org universe's key (``mission_step_contracts`` is
  keyed ``mission_steps`` there).

(The plural -> kind round-trip itself is pinned in
``tests/doctrine/test_artifact_kinds.py``.)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from specify_cli.doctrine.pack_validator import (
    _SINGULAR_TO_PLURAL_AUGMENTATION,
    _kind_singular,
    _plural_to_urn_kind,
    validate_pack,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_unknown_plural_resolves_to_none() -> None:
    """The wrapper turns ``ArtifactKind.from_plural``'s ``KeyError`` into ``None`` (callers skip URN registration)."""
    assert _plural_to_urn_kind("not_a_kind") is None


@pytest.mark.parametrize(
    ("singular", "plural"),
    sorted(_SINGULAR_TO_PLURAL_AUGMENTATION.items()),
    ids=lambda value: value,
)
def test_kind_singular_inverts_every_plural_the_intent_pass_reports(singular: str, plural: str) -> None:
    """``mission_step_contracts`` is the trap: the org universe keys it on ``mission_steps``."""
    assert _kind_singular(plural) == singular


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


_ASSET_MANIFEST = """
    id: company-logo
    title: Company logo
    mime: image/png
    path: company-logo.png
    """
#: Same manifest minus the required ``path``: it fails the asset schema.
_ASSET_MANIFEST_SCHEMA_INVALID = """
    id: company-logo
    title: Company logo
    mime: image/png
    """


@pytest.mark.parametrize(
    ("manifest", "dangling_expected"),
    [
        pytest.param(_ASSET_MANIFEST, False, id="declared-asset"),
        pytest.param(None, True, id="no-asset-manifest"),
        pytest.param(_ASSET_MANIFEST_SCHEMA_INVALID, True, id="manifest-fails-schema"),
    ],
)
def test_edge_to_an_asset_dangles_unless_the_pack_declares_it(tmp_path: Path, manifest: str | None, dangling_expected: bool) -> None:
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
    if manifest is not None:
        _write(tmp_path / "assets" / "company-logo.asset.yaml", manifest)
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
    assert bool(dangling) is dangling_expected, [issue.message for issue in result.errors]
    assert result.ok is not dangling_expected
