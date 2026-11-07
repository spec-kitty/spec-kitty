"""The VCS layer creates no workspace and hides no files.

The legacy WP worktree creators (``core/worktree.py::create_wp_workspace`` /
``create_feature_worktree`` and ``GitVCS.create_workspace``) had no production
caller and were removed (Mission ``lane-worktree-model-hardening-01M6QY1M``
WP09): every lane checkout comes from ``lanes/lane_checkout.py``. Their routing
tests went with them.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestNoWorkspaceCreationInVCS:
    """The VCS layer creates no worktree and keeps no file-hiding hook."""

    def test_git_vcs_has_no_create_workspace(self) -> None:
        from specify_cli.core.vcs.git import GitVCS
        from specify_cli.core.vcs.protocol import VCSProtocol

        assert not hasattr(GitVCS, "create_workspace"), "lane checkouts come from lanes/lane_checkout.py only"
        assert not hasattr(VCSProtocol, "create_workspace")

    def test_git_vcs_has_no_apply_sparse_checkout_method(self) -> None:
        """Legacy sparse helper must not exist on GitVCS."""
        from specify_cli.core.vcs.git import GitVCS

        assert not hasattr(GitVCS, "_apply_sparse_checkout"), "_apply_sparse_checkout must be deleted from GitVCS"

    def test_core_worktree_has_no_workspace_creators(self) -> None:
        from specify_cli.core import worktree

        for name in ("create_wp_workspace", "create_feature_worktree", "_create_workspace_with_fallback"):
            assert not hasattr(worktree, name), name
