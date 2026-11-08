"""#3074 — ``_make_merge_env`` must resolve ``spec-kitty`` through ``shutil.which``.

The merge-env helper prepends only ``Path(sys.executable).parent`` — the
running interpreter's bin dir — to the subprocess PATH. A spec-kitty process
launched through a wrapper (an agent harness, ``uv run``, a console-script
shim) can have ``sys.executable`` in a directory that does NOT hold the
``spec-kitty`` entry point, so git's merge-driver invocation of
``spec-kitty merge-driver-event-log`` resolves a stale global copy (or
nothing) on the ambient PATH — the #87 failure mode resurfaced through a
different door.

The fix prepends the directory of ``shutil.which("spec-kitty")`` when the CLI
resolves on the ambient PATH, keeping the interpreter-bin prepend as the
fallback (the #87 contract).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from specify_cli.lanes.consolidation import _make_merge_env

pytestmark = pytest.mark.fast

_windows = pytest.mark.skipif(os.name == "nt", reason="POSIX executable naming (no spec-kitty.exe)")


def _strip_all_spec_kitty_from_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every PATH entry that can resolve ``spec-kitty`` (the #87 precondition)."""
    kept = [entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry and not (Path(entry) / "spec-kitty").is_file()]
    monkeypatch.setenv("PATH", os.pathsep.join(kept))
    assert shutil.which("spec-kitty") is None


@_windows
def test_which_dir_is_prepared_ahead_of_the_interpreter_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolvable ``spec-kitty`` on PATH puts ITS directory first.

    Pre-fix this is red: the env PATH's first entry is ``sys.executable``'s
    parent (a wrapper-launched interpreter living elsewhere), so the driver
    cannot find the CLI the ambient PATH resolves.
    """
    cli_dir = tmp_path / "cli-bin"
    cli_dir.mkdir()
    fake_cli = cli_dir / "spec-kitty"
    fake_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_cli.chmod(0o755)

    # The ambient PATH resolves the fake CLI ...
    monkeypatch.setenv("PATH", str(cli_dir))
    # ... while the running interpreter sits in a directory that does NOT hold
    # it (the wrapper / uv-run shape #3074 names).
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr(sys, "executable", str(elsewhere / "python"))

    env = _make_merge_env()

    first = env["PATH"].split(os.pathsep)[0]
    assert Path(first) == cli_dir, f"the directory of shutil.which('spec-kitty') must lead the subprocess PATH, got {first!r}"


@_windows
def test_fallback_prepends_interpreter_dir_without_which(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No resolvable ``spec-kitty`` anywhere → the pre-#3074 interpreter-bin prepend stands.

    Regression guard for the #87 tests' contract: with the CLI stripped from
    the ambient PATH, only the interpreter's bin dir can be prepended.
    """
    _strip_all_spec_kitty_from_path(monkeypatch)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr(sys, "executable", str(elsewhere / "python"))

    env = _make_merge_env()

    first = env["PATH"].split(os.pathsep)[0]
    assert Path(first) == elsewhere
