"""FR-014 (#5443): the sweeping commit helpers must stay deleted.

``GitVCS.commit`` staged ``git add -A`` and ran a pathspec-less ``git commit``;
``init_git_repo`` ran ``git add .`` plus a pathspec-less commit. Neither had a
product caller. These checks pin the named symbols so they cannot return.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.unit, pytest.mark.fast]


def test_git_vcs_has_no_sweeping_commit() -> None:
    from specify_cli.core.vcs.git import GitVCS

    assert not hasattr(GitVCS, "commit")


def test_vcs_protocol_declares_no_commit() -> None:
    from specify_cli.core.vcs.protocol import VCSProtocol

    assert "commit" not in VCSProtocol.__dict__


def test_core_exports_no_init_git_repo() -> None:
    import specify_cli.core as core
    import specify_cli.core.git_ops as git_ops

    assert not hasattr(core, "init_git_repo")
    assert "init_git_repo" not in core.__all__
    assert not hasattr(git_ops, "init_git_repo")
    assert "init_git_repo" not in git_ops.__all__
