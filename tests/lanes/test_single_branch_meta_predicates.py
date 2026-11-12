"""The pure ``meta.json`` readings of a ``single_branch`` Mission's branches (#7578).

:func:`single_branch_branches` is the one reading the lane-head stamp (``status.lane_head``) and the
consolidation window-stamp filter (``consolidation.commit_to_target_stamps``) share;
:func:`is_commit_to_target_meta` is the commit-to-target predicate built on it.
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.lanes.single_branch_landing import is_commit_to_target_meta, single_branch_branches

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TARGET = "main"
_MINTED = "kitty/mission-x"
_CTT_META: dict[str, Any] = {"topology": "single_branch", "target_branch": _TARGET}
_MINTED_META: dict[str, Any] = {**_CTT_META, "mission_branch": _MINTED}

_NOT_SINGLE_BRANCH = [
    pytest.param({"topology": "lanes", "target_branch": _TARGET}, id="lanes"),
    pytest.param({"target_branch": _TARGET}, id="no-stored-topology"),
    pytest.param({"topology": "single_branch"}, id="no-target"),
    pytest.param({"topology": "single_branch", "target_branch": ""}, id="empty-target"),
    pytest.param({"topology": "single_branch", "target_branch": 7}, id="non-string-target"),
]


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        pytest.param(_CTT_META, (_TARGET, _TARGET), id="commit-to-target"),
        pytest.param({**_CTT_META, "commit_to_target": True}, (_TARGET, _TARGET), id="commit-to-target-flagged"),
        pytest.param(_MINTED_META, (_MINTED, _TARGET), id="minted-mission-branch"),
    ],
)
def test_single_branch_branches_reads_write_and_target_branch(meta: dict[str, Any], expected: tuple[str, str]) -> None:
    assert single_branch_branches(meta) == expected


@pytest.mark.parametrize("meta", _NOT_SINGLE_BRANCH)
def test_single_branch_branches_is_none_without_a_stored_single_branch_target(meta: dict[str, Any]) -> None:
    assert single_branch_branches(meta) is None


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        pytest.param(_CTT_META, True, id="commit-to-target"),
        pytest.param({**_CTT_META, "commit_to_target": True}, True, id="commit-to-target-flagged"),
        pytest.param(_MINTED_META, False, id="minted-mission-branch"),
        *[pytest.param(param.values[0], False, id=param.id) for param in _NOT_SINGLE_BRANCH],
    ],
)
def test_is_commit_to_target_meta(meta: dict[str, Any], expected: bool) -> None:
    assert is_commit_to_target_meta(meta) is expected
