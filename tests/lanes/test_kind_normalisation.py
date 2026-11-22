"""Pure rule: a docs work package is recorded as ``code_change`` in a lane topology (#7809)."""

from __future__ import annotations

import pytest

from specify_cli.ownership.kind_normalisation import (
    KindRewrite,
    normalise_kinds_for_lane_topology,
    _paths_outside_kitty_specs,
)
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind

pytestmark = [pytest.mark.fast, pytest.mark.unit]

CODE = WorkProductKind.CODE_CHANGE
PLANNING = WorkProductKind.PLANNING_ARTIFACT


def _manifest(mode: WorkProductKind, *owned: str) -> OwnershipManifest:
    return OwnershipManifest(execution_mode=mode, owned_files=owned, authoritative_surface=owned[0] if owned else "")


@pytest.mark.parametrize(
    ("owned", "expected"),
    [
        (("kitty-specs/m/spec.md",), ()),
        (("./kitty-specs/m/**",), ()),
        (("kitty-specs",), ()),
        (("docs/x.md", "kitty-specs/m/a.md"), ("docs/x.md",)),
        (("docs/**", "src/a.py"), ("docs/**", "src/a.py")),
        (("kitty-specs-other/a.md",), ("kitty-specs-other/a.md",)),
        ((), ()),
    ],
)
def test_paths_outside_kitty_specs(owned: tuple[str, ...], expected: tuple[str, ...]) -> None:
    assert _paths_outside_kitty_specs(owned) == expected


def test_docs_wp_is_rewritten_to_code_change() -> None:
    manifests = {"WP01": _manifest(CODE, "src/a.py"), "WP02": _manifest(PLANNING, "docs/x.md")}
    result = normalise_kinds_for_lane_topology(manifests, started_wp_ids=frozenset())
    assert result.manifests["WP02"].execution_mode == CODE
    assert result.manifests["WP02"].owned_files == ("docs/x.md",)
    assert result.manifests["WP01"] is manifests["WP01"]
    assert result.rewritten == (KindRewrite("WP02", ("docs/x.md",), owns_kitty_specs_paths=False),)
    assert result.mixed == ()
    assert result.rewritten[0].as_payload() == {
        "wp_id": "WP02",
        "from": "planning_artifact",
        "to": "code_change",
        "paths_outside_kitty_specs": ["docs/x.md"],
    }


def test_kitty_specs_only_and_empty_planning_wps_are_unchanged() -> None:
    manifests = {"WP01": _manifest(PLANNING, "kitty-specs/m/research.md"), "WP02": _manifest(PLANNING)}
    result = normalise_kinds_for_lane_topology(manifests, started_wp_ids=frozenset())
    assert result.rewritten == ()
    assert result.manifests == manifests


def test_started_wp_is_never_rewritten() -> None:
    manifests = {"WP03": _manifest(PLANNING, "docs/x.md")}
    result = normalise_kinds_for_lane_topology(manifests, started_wp_ids=frozenset({"WP03"}))
    assert result.rewritten == ()
    assert result.manifests["WP03"].execution_mode == PLANNING


def test_mixed_wp_is_rewritten_and_flagged() -> None:
    manifests = {"WP03": _manifest(PLANNING, "kitty-specs/m/notes.md", "docs/x.md")}
    result = normalise_kinds_for_lane_topology(manifests, started_wp_ids=frozenset())
    assert result.manifests["WP03"].execution_mode == CODE
    assert result.mixed == (KindRewrite("WP03", ("docs/x.md",), owns_kitty_specs_paths=True),)


def test_rewrites_are_in_work_package_order() -> None:
    manifests = {"WP05": _manifest(PLANNING, "docs/b.md"), "WP02": _manifest(PLANNING, "docs/a.md")}
    result = normalise_kinds_for_lane_topology(manifests, started_wp_ids=frozenset())
    assert [rewrite.wp_id for rewrite in result.rewritten] == ["WP02", "WP05"]
