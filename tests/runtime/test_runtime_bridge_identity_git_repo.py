"""Real-git companion to ``tests/runtime/test_runtime_bridge_identity.py``.

2026-08-04 (PR #3175 landing fold, marker-correctness gates): this class was
originally the "WP08 (#3155) regression — corrupt meta.json must degrade, not
raise" section of ``test_runtime_bridge_identity.py``. It seeds a *real* git
repository via ``subprocess.run(["git", ...])`` (``_init_repo``/``_seed``)
because ``_mission_routes_through_coordination`` reads coordination-branch
existence off real git refs — a mock cannot stand in for that.

Two ``tests/architectural/test_pytest_marker_correctness.py`` gates fired on
the pre-split file: Rule 1 (a subprocess/git user must carry the ``git_repo``
marker so CI's ``-m git_repo`` gate actually selects it — it did not) and
Rule 2 (a file carrying ``fast`` must not invoke subprocess — the module-level
``pytestmark`` applied ``fast`` to this class too, poisoning the inner
developer loop's ``-m fast`` profile with real git subprocess calls). Every
other test in the sibling file is pure ``unittest.mock.patch`` with no
subprocess — genuinely fast — so per the Rule 2 fix-hint's explicit split
option (docs/context/testing-taxonomy.md → 'Fast'/'Git Repo'), this class
moved here with ``git_repo`` in place of ``fast`` rather than stripping
``fast`` from the whole original file.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from runtime.next.runtime_bridge_decision_log import _mission_routes_through_coordination

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _init_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "runtime-bridge@example.test"],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Runtime Bridge Test"], cwd=repo_root, check=True)


class TestMissionRoutesThroughCoordinationCorruptMeta:
    """``_mission_routes_through_coordination`` must degrade on corrupt meta.json.

    ``read_topology`` (WP08, #3155) surfaces corrupt/non-object ``meta.json`` as
    the typed :class:`specify_cli.core.paths.MissionMetaReadError` (a
    ``RuntimeError`` subclass) rather than a bare ``ValueError``. This call
    site's except-clause only listed ``(FileNotFoundError, ValueError,
    OSError)``, so a corrupt meta propagated uncaught here, contradicting the
    function's own docstring ("Missing/malformed meta degrades to non-coord").
    """

    _MISSION_ID = "01KVRJ6PQ8ZB2H7M3N4P5R6S7T"
    _MID8 = _MISSION_ID[:8]
    _SLUG = f"rb-corrupt-meta-{_MID8}"

    def _seed(self, repo_root: Path) -> Path:
        _init_repo(repo_root)
        feature_dir = repo_root / "kitty-specs" / self._SLUG
        feature_dir.mkdir(parents=True)
        meta = {
            "mission_id": self._MISSION_ID,
            "mid8": self._MID8,
            "mission_slug": self._SLUG,
            "coordination_branch": f"kitty/mission-{self._SLUG}",
        }
        (feature_dir / "meta.json").write_text(
            json.dumps(meta, sort_keys=True, indent=2), encoding="utf-8"
        )
        subprocess.run(["git", "add", "kitty-specs"], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "seed mission"], cwd=repo_root, check=True
        )
        subprocess.run(
            ["git", "branch", f"kitty/mission-{self._SLUG}"], cwd=repo_root, check=True
        )
        return feature_dir

    def test_valid_coord_meta_routes_true(self, tmp_path: Path) -> None:
        """Sanity: a readable coord-declaring meta routes True (the pre-corruption baseline)."""
        self._seed(tmp_path)
        assert _mission_routes_through_coordination(self._SLUG, tmp_path) is True

    def test_corrupt_meta_degrades_to_false_not_raise(self, tmp_path: Path) -> None:
        """RED on pre-fix code: corrupt meta.json raised MissionMetaReadError uncaught.

        Post-fix, the except-clause catches it and returns False (the
        documented degrade-to-non-coord arm) rather than propagating.
        """
        feature_dir = self._seed(tmp_path)
        (feature_dir / "meta.json").write_text("{ not valid json", encoding="utf-8")

        assert _mission_routes_through_coordination(self._SLUG, tmp_path) is False, (
            "corrupt meta.json must degrade _mission_routes_through_coordination "
            "to False, not raise MissionMetaReadError"
        )
