"""Symlink-loop guard test for analysis_report._relativize_or_raise (#3189, WP03/T014).

CPython 3.11/3.12's non-strict ``Path.resolve()`` raises ``RuntimeError`` on a
symlink loop; ``_relativize_or_raise``'s ``except ValueError`` handler does not
catch it, so a loop artifact path crashed with an unsanitized ``RuntimeError``
instead of the documented, path-scrubbed ``PathRelativizationError``. On
3.13+ non-strict ``resolve()`` silently accepted the loop instead of refusing
it. Routing through ``kernel.resolution.resolve_rejecting_loops`` restores one
verdict, and the error message must still embed neither absolute path.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.analysis_report import PathRelativizationError, _relativize_or_raise


pytestmark = pytest.mark.fast

_SYMLINK_UNAVAILABLE_REASON = "os.symlink unavailable on this platform"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_loop_artifact_path_raises_relativization_error_without_leaking_paths(tmp_path: Path) -> None:
    governing_root = tmp_path / "repo"
    governing_root.mkdir()
    loop = governing_root / "spec.md"
    loop.symlink_to(loop)

    with pytest.raises(PathRelativizationError) as excinfo:
        _relativize_or_raise(loop, governing_root)

    message = str(excinfo.value)
    assert str(tmp_path) not in message
    assert str(governing_root) not in message
    assert str(loop) not in message
    assert "spec.md" in message


def test_in_root_artifact_returns_relative_string(tmp_path: Path) -> None:
    governing_root = tmp_path / "repo"
    governing_root.mkdir()
    artifact = governing_root / "spec.md"
    artifact.write_text("content", encoding="utf-8")

    assert _relativize_or_raise(artifact, governing_root) == "spec.md"
