"""One required-floor reader with per-pack provenance (WP04: R3, FR-013, D-05, D-18).

``read_org_required_provenance`` walks every declared org pack and each pack's
``extends:`` chain once, through the canonical resolver. Strict mode refuses an
unreadable or malformed declared pack, a cycle and a dangling base; it never
widens. The non-strict readers (the overlay, ``read_org_required_ids``) read the
same iterator and stay lenient.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.activation.activation_ledger import ActiveCharterConfigError
from charter.activation.org_pack_discovery import (
    RequiringPack,
    _iter_org_charter_docs,
    _read_org_required_selections,
    read_org_required_ids,
    read_org_required_provenance,
)
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_D_STEM = "003-decision-documentation-requirement"


def _project(tmp_path: Path, packs: dict[str, str | None]) -> Path:
    """Declare *packs* (name -> ``org-charter.yaml`` body; ``None`` leaves the pack directory out)."""
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, body in packs.items():
        if body is not None:
            pack = tmp_path / "org-packs" / name
            pack.mkdir(parents=True, exist_ok=True)
            (pack / "org-charter.yaml").write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        lines += [f"      - name: {name}", f"        local_path: org-packs/{name}"]
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


_BASE = """
    schema_version: 1
    required_tactics: [base-tactic]
"""
_OVERLAY = """
    schema_version: 1
    extends: base
    required_tactics: [overlay-tactic]
"""


def test_provenance_through_an_extends_chain(tmp_path: Path) -> None:
    root = _project(tmp_path, {"base": _BASE, "overlay": _OVERLAY})

    provenance = read_org_required_provenance(root, ArtifactKind.TACTIC, strict=True)

    assert provenance["base-tactic"] == (RequiringPack("base"), RequiringPack("base", via="overlay"))
    assert provenance["overlay-tactic"] == (RequiringPack("overlay"),)


def test_union_over_two_declared_packs(tmp_path: Path) -> None:
    body = "schema_version: 1\nrequired_tactics: [shared]\n"
    root = _project(tmp_path, {"one": body, "two": body})

    assert read_org_required_provenance(root, ArtifactKind.TACTIC, strict=True) == {"shared": (RequiringPack("one"), RequiringPack("two"))}


def test_ids_are_normalised_to_stems(tmp_path: Path) -> None:
    root = _project(tmp_path, {"acme": "schema_version: 1\nrequired_directives: [DIRECTIVE_003]\n"})

    assert read_org_required_provenance(root, ArtifactKind.DIRECTIVE, strict=True) == {_D_STEM: (RequiringPack("acme"),)}


def test_no_declared_pack_requires_nothing(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")

    assert read_org_required_provenance(tmp_path, ArtifactKind.DIRECTIVE, strict=True) == {}


def test_a_pack_without_an_org_charter_requires_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path, {"acme": "schema_version: 1\n"})
    (root / "org-packs" / "acme" / "org-charter.yaml").unlink()

    assert read_org_required_provenance(root, ArtifactKind.DIRECTIVE, strict=True) == {}


@pytest.mark.parametrize(
    ("packs", "needle"),
    [
        ({"one": "schema_version: 1\nextends: two\n", "two": "schema_version: 1\nextends: one\n"}, "Cycle"),
        ({"acme": "schema_version: 1\nextends: missing\n"}, "missing"),
        ({"acme": "required_tactics: [unclosed\n"}, "acme"),
        ({"acme": "- just\n- a list\n"}, "acme"),
        ({"acme": ""}, "acme"),
        ({"acme": "required_tactics: not-a-list\n"}, "required_tactics"),
        ({"acme": None}, "acme"),
    ],
    ids=["cycle", "dangling-base", "unparseable", "not-a-mapping", "empty", "non-list-required", "missing-pack-dir"],
)
def test_strict_mode_refuses_what_it_cannot_read(tmp_path: Path, packs: dict[str, str | None], needle: str) -> None:
    root = _project(tmp_path, packs)

    with pytest.raises(ActiveCharterConfigError) as excinfo:
        read_org_required_provenance(root, ArtifactKind.TACTIC, strict=True)

    assert needle in excinfo.value.body


def test_strict_mode_refuses_an_invalid_pack_registry(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("charter_packs:\n  org:\n    packs:\n      - local_path: 7\n", encoding="utf-8")

    with pytest.raises(ActiveCharterConfigError):
        read_org_required_provenance(tmp_path, ArtifactKind.TACTIC, strict=True)


def test_non_strict_mode_skips_what_it_cannot_read(tmp_path: Path) -> None:
    root = _project(tmp_path, {"bad": "required_tactics: [unclosed\n", "good": "schema_version: 1\nrequired_tactics: [t]\n"})

    assert read_org_required_provenance(root, ArtifactKind.TACTIC, strict=False) == {"t": (RequiringPack("good"),)}
    assert read_org_required_ids(root, ArtifactKind.TACTIC) == ["t"]


def test_non_strict_mode_falls_back_to_the_declared_pack_on_a_cycle(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        {"one": "schema_version: 1\nextends: two\nrequired_tactics: [t1]\n", "two": "schema_version: 1\nextends: one\nrequired_tactics: [t2]\n"},
    )

    assert read_org_required_ids(root, ArtifactKind.TACTIC) == ["t1", "t2"]


def test_the_iterator_yields_declared_member_and_document(tmp_path: Path) -> None:
    root = _project(tmp_path, {"base": _BASE, "overlay": _OVERLAY})

    triples = [(declared, member) for declared, member, _raw in _iter_org_charter_docs(root)]

    assert triples == [("base", "base"), ("overlay", "overlay"), ("overlay", "base")]


def test_the_overlay_includes_extends_inherited_requirements(tmp_path: Path) -> None:
    root = _project(tmp_path, {"base": _BASE, "overlay": _OVERLAY})

    assert _read_org_required_selections(root)["tactics"] == ["base-tactic", "overlay-tactic"]
    assert read_org_required_ids(root, ArtifactKind.TACTIC) == ["base-tactic", "overlay-tactic"]
