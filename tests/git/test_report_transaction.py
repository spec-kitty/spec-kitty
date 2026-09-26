"""NUL-delimited Git boundaries used by report-only recording."""

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.report_transaction import _dirty_paths, _index

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_rename_keeps_both_unusual_path_endpoints(tmp_path: Path):
    def git(*args: str):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "work")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    old, new = "old\nname.md", "new\tname.md"
    (tmp_path / old).write_text("same content\n")
    git("add", "--", old)
    git("-c", "commit.gpgsign=false", "commit", "-qm", "seed")
    git("mv", "--", old, new)
    assert _dirty_paths(tmp_path) == {old, new}
    entries = _index(tmp_path, "analysis-report.md")
    assert len(entries) == 1
    assert entries[0].endswith(new.encode())
