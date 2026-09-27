"""Symlink-loop guard tests for upgrade.skill_update.is_external_symlink (#3189, WP03/T013).

CPython 3.11/3.12's non-strict ``Path.resolve()`` raises ``RuntimeError`` when
it encounters a symlink loop; ``is_external_symlink``'s ``except OSError``
handler does not catch it, so a loop symlink crashed the caller instead of
being treated as ``False`` like every other resolution failure its authored
contract already covers. Routing through
``kernel.resolution.resolve_rejecting_loops`` restores the interpreter-invariant
``False`` verdict.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.upgrade.skill_update import is_external_symlink


pytestmark = pytest.mark.fast

_SYMLINK_UNAVAILABLE_REASON = "os.symlink unavailable on this platform"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_loop_symlink_is_not_reported_external(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    loop = repo / "SKILL.md"
    loop.symlink_to(loop)

    assert is_external_symlink(loop, repo) is False


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_symlink_targeting_outside_repo_is_external(tmp_path: Path) -> None:
    external = tmp_path / "home" / "canonical.md"
    external.parent.mkdir(parents=True)
    external.write_text("canonical", encoding="utf-8")

    repo = tmp_path / "repo"
    repo.mkdir()
    link = repo / "SKILL.md"
    os.symlink(external, link)

    assert is_external_symlink(link, repo) is True
