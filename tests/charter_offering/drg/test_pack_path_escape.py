"""The one pack-path containment finding type and its predicate (#7263).

``PackPathEscape`` is what every surface that judges a pack-declared path
consumes: ``doctor charter-packs``, ``charter status``, ``charter org validate``
and the pack-skill reader. These tests pin its two serialised faces (the
operator message and the ``doctor charter-packs`` JSON record of #6418, which
must stay byte-identical) and :func:`path_containment_fault`, the finding form
of the shared containment primitive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.org_pack_config import (
    ORG_ASSET_PATH_ESCAPE,
    ORG_FRAGMENT_BODY_PATH_ESCAPE,
    PACK_SKILL_BODY_PATH_ESCAPE,
    PackPathEscape,
    path_containment_fault,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_fragment_node_message_and_record_keep_the_6418_shape() -> None:
    escape = PackPathEscape(code=ORG_FRAGMENT_BODY_PATH_ESCAPE, pack="acme", subject="n1", kind="directives", path="../x.md", reason="why")

    assert escape.message == "org pack 'acme': node 'n1' (directives) body_path '../x.md' is not contained in the pack root: why"
    assert escape.as_dict() == {
        "code": "ORG_FRAGMENT_BODY_PATH_ESCAPE",
        "pack": "acme",
        "node": "n1",
        "kind": "directives",
        "body_path": "../x.md",
        "reason": "why",
    }
    # Key order is part of the JSON contract the doctor prints.
    assert list(escape.as_dict()) == ["code", "pack", "node", "kind", "body_path", "reason"]


def test_asset_message_and_record_keep_the_6418_shape() -> None:
    escape = PackPathEscape(code=ORG_ASSET_PATH_ESCAPE, pack="acme", subject="logo", path="/etc/hostname", reason="why")

    assert escape.message == "org pack 'acme': asset 'logo' path '/etc/hostname' is not contained in the pack's assets/ root: why"
    assert list(escape.as_dict().items()) == [
        ("code", "ORG_ASSET_PATH_ESCAPE"),
        ("pack", "acme"),
        ("asset", "logo"),
        ("path", "/etc/hostname"),
        ("reason", "why"),
    ]


def test_pack_skill_message_names_the_skill_not_an_org_pack() -> None:
    escape = PackPathEscape(code=PACK_SKILL_BODY_PATH_ESCAPE, pack="/p/skills", subject="land-pr", path="../o.md", reason="why")

    assert escape.message == "skill 'land-pr' body_path '../o.md' is not contained in its skill directory: why"
    assert escape.as_dict()["skill"] == "land-pr"


def test_an_unknown_code_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="unknown pack path escape code"):
        PackPathEscape(code="SOMETHING_ELSE", pack="acme", subject="x", path="y", reason="z")


@pytest.mark.parametrize(
    ("relative_path", "fragment"),
    [
        ("/etc/passwd", "absolute"),
        ("C:\\Windows\\system.ini", "absolute"),
        ("\\\\server\\share\\x", "absolute"),
        ("../outside.md", "'..'"),
        ("nested/../inside.md", "'..'"),
    ],
)
def test_path_containment_fault_names_why_a_path_escapes(tmp_path: Path, relative_path: str, fragment: str) -> None:
    reason = path_containment_fault(tmp_path, relative_path)

    assert reason is not None
    assert fragment in reason


def test_path_containment_fault_reports_a_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    try:
        (root / "link.md").symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"cannot create symlink: {exc}")

    reason = path_containment_fault(root, "link.md")

    assert reason is not None
    assert "resolves outside root" in reason


def test_path_containment_fault_turns_an_unresolvable_path_into_a_reason(tmp_path: Path) -> None:
    # A NUL byte makes ``Path.resolve`` raise ValueError; it is a finding, never a crash.
    assert path_containment_fault(tmp_path, "a\x00b.md") is not None


def test_a_contained_path_is_not_a_fault_whether_or_not_it_exists(tmp_path: Path) -> None:
    (tmp_path / "here.md").write_text("x", encoding="utf-8")

    assert path_containment_fault(tmp_path, "here.md") is None
    assert path_containment_fault(tmp_path, "missing/not-yet.md") is None
