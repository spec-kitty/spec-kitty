"""The runtime-state exemption must anchor on the CANONICAL planning path.

``_feature_dir_rel`` returned ``feature_dir`` relative to the repo root
verbatim. On a coord-topology mission the resolved ``feature_dir`` is the
STATUS-only ``-coord`` worktree husk, so that produced
``.worktrees/<mission>-coord/kitty-specs/<slug>`` -- a prefix no diff path
taken against the main repo root ever carries.

The effect was silent and exactly inverted: the runtime-state exemption
never fired for the topology that needs it, so a mission's own status.json
and status.events.jsonl blocked its own reviews, with the gate reporting
them as forbidden surfaces.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.bulk_edit.gate import _feature_dir_rel

pytestmark = [pytest.mark.unit, pytest.mark.fast]


REPO = Path("/repo")


class TestCanonicalisation:
    def test_plain_layout_is_unchanged(self) -> None:
        assert _feature_dir_rel(REPO / "kitty-specs/m-01XYZ", REPO) == "kitty-specs/m-01XYZ"

    def test_coord_husk_is_reduced_to_the_canonical_path(self) -> None:
        husk = REPO / ".worktrees/m-01XYZ-coord/kitty-specs/m-01XYZ"
        assert _feature_dir_rel(husk, REPO) == "kitty-specs/m-01XYZ"

    def test_lane_worktree_is_reduced_too(self) -> None:
        lane = REPO / ".worktrees/m-01XYZ-lane-a/kitty-specs/m-01XYZ"
        assert _feature_dir_rel(lane, REPO) == "kitty-specs/m-01XYZ"

    def test_the_rightmost_kitty_specs_wins(self) -> None:
        """A worktree nested under kitty-specs must not resolve to the outer one."""
        nested = REPO / "kitty-specs/outer/.worktrees/w/kitty-specs/m-01XYZ"
        assert _feature_dir_rel(nested, REPO) == "kitty-specs/m-01XYZ"

    def test_a_path_with_no_kitty_specs_is_passed_through(self) -> None:
        assert _feature_dir_rel(REPO / "some/other/dir", REPO) == "some/other/dir"

    def test_outside_the_repo_is_none(self) -> None:
        assert _feature_dir_rel(Path("/elsewhere/kitty-specs/m"), REPO) is None

    def test_a_bare_kitty_specs_dir_is_passed_through(self) -> None:
        """No slug component to pair with, so there is nothing to canonicalise."""
        assert _feature_dir_rel(REPO / "kitty-specs", REPO) == "kitty-specs"
