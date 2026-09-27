"""Fast guards for ``_read_committed_meta_json``'s kernel L1 decode routing (#3330).

``tests/specify_cli/merge/test_baseline_module.py`` pins the same two error shapes
through a real git repo, but it is ``integration``+``git_repo``-marked and lives in a
shard the CI path filter does not run for ``src/specify_cli/merge/**`` changes. The
``fast-tests-merge`` shard (``tests/merge/``, ``--cov=src/specify_cli/merge``) feeds the
enforced critical-path diff-coverage gate, so the ``MetaDecodeError`` branches need a
fast, git-free guard here too.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.consolidation import baseline
from specify_cli.consolidation.baseline import BaselineMergeCommitError, _read_committed_meta_json

pytestmark = pytest.mark.fast


def _git_show_returning(stdout: str) -> object:
    """Stand-in for ``run_command`` that succeeds with *stdout* for ``git show``."""

    def _fake(args: list[str], **_: object) -> tuple[int, str, str]:
        assert args[:2] == ["git", "show"]
        return 0, stdout, ""

    return _fake


def test_committed_meta_invalid_json_routes_through_kernel_decode(tmp_path: Path) -> None:
    with patch.object(baseline, "run_command", _git_show_returning("{ not json at all")), pytest.raises(BaselineMergeCommitError, match="not valid JSON"):
        _read_committed_meta_json(tmp_path, "main", "kitty-specs/m/meta.json", "m")


def test_committed_meta_non_object_routes_through_kernel_decode(tmp_path: Path) -> None:
    with patch.object(baseline, "run_command", _git_show_returning("[1, 2, 3]")), pytest.raises(BaselineMergeCommitError, match="not a JSON object"):
        _read_committed_meta_json(tmp_path, "main", "kitty-specs/m/meta.json", "m")


def test_committed_meta_object_is_returned(tmp_path: Path) -> None:
    with (
        patch.object(
            baseline,
            "run_command",
            _git_show_returning('{"mission_number": 7}'),
        ),
        patch.object(
            baseline,
            "decode_meta",
            wraps=baseline.decode_meta,
        ) as decode_mock,
    ):
        meta = _read_committed_meta_json(tmp_path, "main", "kitty-specs/m/meta.json", "m")
    assert meta == {"mission_number": 7}
    decode_mock.assert_called_once_with('{"mission_number": 7}', on_malformed="raise")
