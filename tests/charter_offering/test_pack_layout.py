"""The ONE pack-layout resolution seam (FR-009, WP02 T007).

``resolve_pack_layout(pack_root, descriptor)`` is descriptor-first,
convention-fallback, and the single authority for *where a level's layout
files live*. The convention fallback delegates to the ``kernel.charter_pack_paths``
constants/helpers so no second filename authority is introduced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.packs.pack_descriptor import PackDescriptor
from charter.offering.packs.pack_layout import PackLayoutError, resolve_pack_layout
from kernel.charter_pack_paths import DRG_FRAGMENT, ORG_CHARTER_FILENAME, PROJECT_GRAPH_FILENAME

pytestmark = [pytest.mark.fast]


def _descriptor(level: str, **overrides: object) -> PackDescriptor:
    data: dict[str, object] = {
        "pack_id": "01ARWG13C000000000000000FG",
        "name": "acme",
        "pack_level": level,
    }
    if level == "built-in":
        data["pack_version"] = "1.0.0"
    data.update(overrides)
    return PackDescriptor.model_validate(data)


# ---------------------------------------------------------------------------
# Convention fallback (no pointer fields) reproduces the kernel authority.
# ---------------------------------------------------------------------------


def test_org_convention(tmp_path: Path) -> None:
    active, drg = resolve_pack_layout(tmp_path, _descriptor("org"))
    assert active == tmp_path / ORG_CHARTER_FILENAME
    assert drg == tmp_path / DRG_FRAGMENT


def test_project_convention(tmp_path: Path) -> None:
    active, drg = resolve_pack_layout(tmp_path, _descriptor("project"))
    assert active is None
    assert drg == tmp_path / PROJECT_GRAPH_FILENAME


def test_built_in_convention_drg_is_the_sharded_root_dir(tmp_path: Path) -> None:
    active, drg = resolve_pack_layout(tmp_path, _descriptor("built-in"))
    assert active is None
    # built-in ships sharded ``*.graph.yaml`` at the pack root; the seam returns
    # the root directory, which ``drg.loader.load_graph_or_dir`` accepts.
    assert drg == tmp_path


# ---------------------------------------------------------------------------
# Descriptor pointer wins when set (validated inside pack_root).
# ---------------------------------------------------------------------------


def test_pointer_fields_override_convention(tmp_path: Path) -> None:
    active, drg = resolve_pack_layout(
        tmp_path,
        _descriptor("org", active_charter="custom-charter.yaml", pack_drg="drg/custom.yaml"),
    )
    assert active == tmp_path / "custom-charter.yaml"
    assert drg == tmp_path / "drg" / "custom.yaml"


def test_pointer_in_project_level_overrides_the_none_convention(tmp_path: Path) -> None:
    active, _drg = resolve_pack_layout(tmp_path, _descriptor("project", active_charter="over.yaml"))
    assert active == tmp_path / "over.yaml"


# ---------------------------------------------------------------------------
# Escape rejection — a pointer may not leave pack_root.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["active_charter", "pack_drg"])
def test_dotdot_escape_is_rejected(tmp_path: Path, field: str) -> None:
    descriptor = _descriptor("org", **{field: "../evil.yaml"})
    with pytest.raises(PackLayoutError):
        resolve_pack_layout(tmp_path, descriptor)


def test_absolute_pointer_is_rejected(tmp_path: Path) -> None:
    descriptor = _descriptor("org", pack_drg="/etc/passwd")
    with pytest.raises(PackLayoutError):
        resolve_pack_layout(tmp_path, descriptor)
