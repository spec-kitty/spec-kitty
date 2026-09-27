"""Symlink-loop behaviour of ``invocation.writer.normalise_ref`` (#3189).

A reference that runs through a symlink loop cannot be resolved, so the
invocation trail records the caller's raw ``ref`` on every interpreter. Before
the fix, CPython 3.11/3.12 did exactly that (``RuntimeError`` fell into the
fallback), while 3.13+ returned the loop path unresolved and the trail
recorded a different, lexically normalised value.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.invocation.writer import normalise_ref

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SYMLINK_UNAVAILABLE_REASON = "os.symlink unavailable on this platform"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_loop_ref_is_recorded_verbatim(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    loop = tmp_path / "loop"
    loop.symlink_to("loop")

    assert normalise_ref("sub/../loop", tmp_path) == "sub/../loop"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_resolvable_symlink_ref_is_recorded_repo_relative(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "target.md").write_text("x", encoding="utf-8")
    (tmp_path / "link.md").symlink_to("target.md")

    assert normalise_ref("sub/../link.md", tmp_path) == "target.md"
