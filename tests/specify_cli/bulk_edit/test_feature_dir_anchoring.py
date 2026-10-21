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
    @pytest.mark.parametrize(
        "feature_dir,expected",
        [
            # plain layout is unchanged
            (REPO / "kitty-specs/m-01XYZ", "kitty-specs/m-01XYZ"),
            # coord husk and lane worktree reduce to the canonical path
            (REPO / ".worktrees/m-01XYZ-coord/kitty-specs/m-01XYZ", "kitty-specs/m-01XYZ"),
            (REPO / ".worktrees/m-01XYZ-lane-a/kitty-specs/m-01XYZ", "kitty-specs/m-01XYZ"),
            # the rightmost kitty-specs wins
            (REPO / "kitty-specs/outer/.worktrees/w/kitty-specs/m-01XYZ", "kitty-specs/m-01XYZ"),
            # nothing to canonicalise: passed through
            (REPO / "some/other/dir", "some/other/dir"),
            (REPO / "kitty-specs", "kitty-specs"),
        ],
    )
    def test_reduced_to_the_canonical_path(self, feature_dir: Path, expected: str) -> None:
        assert _feature_dir_rel(feature_dir, REPO) == expected

    def test_outside_the_repo_is_none(self) -> None:
        assert _feature_dir_rel(Path("/elsewhere/kitty-specs/m"), REPO) is None
