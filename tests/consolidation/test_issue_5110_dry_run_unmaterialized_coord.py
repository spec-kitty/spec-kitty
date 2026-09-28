"""#5110 — ``consolidate --dry-run`` must fail closed on an unmaterialized coord worktree.

``CoordinationWorktreeUnmaterialized`` (#4959) derives from
``StatusReadPathNotFound(Exception)``, so it escaped the dry-run forecast's
``except (RuntimeError, OSError)`` and surfaced as a raw traceback — and, under
``--json``, as no JSON at all. The real consolidation path already renders the
exception's own remediation and exits 1 (``executor.py``'s STATUS_STATE read);
the dry run must do the same and keep ``--json`` output valid.

Driven through the real ``spec-kitty consolidate --dry-run`` typer command on a
coord-topology mission whose coordination branch exists but whose coordination
worktree has been removed from disk (the fresh-clone / CI window).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.consolidation.test_issue_4764_terminus_safety import (
    MID8,
    MISSION_SLUG,
    _approved_event,
    _bootstrap_coord_mission,
    _git,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_UNMATERIALIZED_CODE = "COORDINATION_WORKTREE_UNMATERIALIZED"


@pytest.fixture
def unmaterialized_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_coord_mission(repo, wp_event=_approved_event())
    coord_path = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    _git(repo, "worktree", "remove", "--force", str(coord_path))
    assert not coord_path.exists(), "precondition: the coordination worktree is unmaterialized"
    monkeypatch.chdir(repo)
    return repo


def _dry_run(*extra: str) -> tuple[int, str, BaseException | None]:
    result = CliRunner().invoke(cli_app, ["consolidate", "--mission", MISSION_SLUG, "--dry-run", *extra])
    return result.exit_code, result.output, result.exception


def test_5110_dry_run_on_unmaterialized_coord_exits_1_with_readable_message(unmaterialized_repo: Path) -> None:
    code, output, exc = _dry_run()

    assert code == 1, f"expected a handled exit 1, got {code} ({exc!r}):\n{output}"
    assert isinstance(exc, SystemExit), f"the dry run raised instead of failing closed: {exc!r}"
    assert "Traceback" not in output
    assert "unmaterialized" in output, output
    assert "Dry run aborted" in output, output


def test_5110_dry_run_json_on_unmaterialized_coord_emits_valid_json_error(unmaterialized_repo: Path) -> None:
    code, output, exc = _dry_run("--json")

    assert code == 1, f"expected a handled exit 1, got {code} ({exc!r}):\n{output}"
    assert isinstance(exc, SystemExit), f"the dry run raised instead of failing closed: {exc!r}"
    payload = json.loads(output.strip().splitlines()[-1])
    assert payload["error_code"] == _UNMATERIALIZED_CODE, payload
    assert "unmaterialized" in payload["error"], payload
