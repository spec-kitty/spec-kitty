"""Symlink-loop guard test for SaaSTrackerClient project-root resolution (#3189, WP03/T015).

``SaaSTrackerClient.__init__`` already catches ``(OSError, RuntimeError)``
around its ``Path.resolve()`` call, so the 3.11/3.12 ``RuntimeError`` for a
symlink loop already lands on the documented refusal. On 3.13+, non-strict
``resolve()`` silently accepts the loop instead of raising anything, so
construction succeeds with an unresolved, loop-shaped project root — a
verdict divergence from 3.11/3.12. Routing through
``kernel.resolution.resolve_rejecting_loops`` restores one interpreter-
invariant ``SaaSTrackerClientError`` (error_code
``project_root_resolution_failed``) on every interpreter, using a REAL
symlink loop rather than the module's own mocked-``RuntimeError`` regression
(``tests/tracker/test_saas_client.py::TestConstructorDefaults`` around line
923), which stays in place because it independently pins that
``RuntimeError`` is still caught.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.tracker.saas_client import SaaSTrackerClient, SaaSTrackerClientError


pytestmark = pytest.mark.fast

_SYMLINK_UNAVAILABLE_REASON = "os.symlink unavailable on this platform"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_loop_project_root_raises_client_error(tmp_path: Path) -> None:
    loop = tmp_path / "loop"
    loop.symlink_to(loop)

    with pytest.raises(SaaSTrackerClientError) as excinfo:
        SaaSTrackerClient(project_root=loop)

    assert excinfo.value.error_code == "project_root_resolution_failed"


def test_normal_project_root_constructs_client(tmp_path: Path) -> None:
    project_root = tmp_path / "proj"
    project_root.mkdir()

    client = SaaSTrackerClient(project_root=project_root)

    assert client._project_root == project_root.resolve()
