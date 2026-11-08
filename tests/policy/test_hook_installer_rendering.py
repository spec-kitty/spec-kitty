"""Tests for pre-commit hook rendering shape (T035).

Verifies the generated hook has the correct structure: #!/bin/sh shebang,
a single quoted exec line with the absolute interpreter, LF line endings,
and mode 0o700.  No windows_ci marker — pure-Python rendering check.
"""

import os
import stat
import sys
from pathlib import Path

from specify_cli.policy.hook_installer import HOOK_MODE, HookInstallRecord, install


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

def test_hook_rendering_shape(tmp_path: Path) -> None:
    """Install into a fake repo .git dir and assert the rendered hook shape."""
    # Fake repo with .git dir (not a real git repo — install() only needs the dir)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    record = install(repo)
    hook = repo / ".git" / "hooks" / "pre-commit"
    assert hook.is_file(), "pre-commit hook file must exist after install"

    content = hook.read_text(encoding="utf-8")

    # LF line endings — no CRLF allowed (Git for Windows sh.exe fails on CRLF shebang)
    assert "\r\n" not in content, "Hook must use LF line endings, not CRLF"

    lines = content.splitlines()
    assert lines[0] == "#!/bin/sh", f"First line must be #!/bin/sh, got {lines[0]!r}"

    # Two exec lines by design (#254): the pinned-interpreter primary path,
    # guarded by an `-x` check, and the PATH-resolved `spec-kitty` fallback
    # the hook takes when the pinned interpreter has gone stale (e.g. a
    # pipx -> uv migration moved it). Exactly one of the two ever runs.
    exec_lines = [line for line in lines if line.strip().startswith("exec ")]
    assert len(exec_lines) == 2, (
        f"Expected exactly two 'exec ' lines (primary + fallback), "
        f"found {len(exec_lines)}: {exec_lines}"
    )
    primary_line, fallback_line = exec_lines

    # Interpreter must appear in double quotes (handles paths with spaces).
    # Symlinks are intentionally preserved (issue #669) so venv/pipx interpreters
    # keep their sys.prefix — so we expect the abspath of sys.executable, not its
    # resolved target.
    expected = os.path.abspath(sys.executable)
    assert f'"{expected}"' in primary_line, (
        f'Expected quoted interpreter "{expected}" in exec line: {primary_line!r}'
    )
    assert "-m specify_cli.policy.commit_guard_hook" in primary_line, (
        f"Expected module invocation in exec line: {primary_line!r}"
    )
    assert '"$@"' in primary_line, f'Expected "$@" in exec line: {primary_line!r}'

    # Fallback (#254): PATH-resolved `spec-kitty commit-guard-hook`, guarded
    # by `command -v` so it's only reached when the primary path is gone.
    assert "spec-kitty commit-guard-hook" in fallback_line, (
        f"Expected the install-agnostic fallback in the second exec line: {fallback_line!r}"
    )
    assert '"$@"' in fallback_line, f'Expected "$@" in fallback exec line: {fallback_line!r}'
    assert "command -v spec-kitty" in content, (
        "Fallback exec must be guarded by a PATH check ('command -v spec-kitty')"
    )

    # A remedy naming an actual command must be present for the case where
    # BOTH the pinned interpreter and the PATH fallback are unavailable (#254).
    assert "spec-kitty migrate repin-hooks" in content, (
        "Hook must name a concrete remedy when both entrypoints are unavailable"
    )

    # No PATH-based python/python3/py literals (the whole point of this WP)
    assert "python3 " not in content, "Hook must not contain bare 'python3 ' lookup"
    assert "python " not in content, "Hook must not contain bare 'python ' lookup"

    # Mode 0o700
    mode = stat.S_IMODE(os.stat(hook).st_mode)
    assert mode == HOOK_MODE, f"Expected mode {oct(HOOK_MODE)}, got {oct(mode)}"

    # HookInstallRecord fields
    assert isinstance(record, HookInstallRecord)
    assert record.shebang == "#!/bin/sh"
    assert record.module == "specify_cli.policy.commit_guard_hook"
    assert record.interpreter == Path(os.path.abspath(sys.executable))
    assert record.mode == HOOK_MODE
    assert record.hook_path == hook
