"""WP04 (mission-handle-resolution-consistency, FR-004/FR-005): merge truthfully
reports an unknown ``--mission`` handle.

``spec-kitty merge`` used to mislead an operator who fat-fingered ``--mission``:
the fresh flow tripped over the phantom mission dir and raised
``MissingLanesError`` ("lanes.json is required … run task-finalization"), and
``--resume`` reported "No interrupted merge to resume" — both blame the wrong
thing. The fix routes BOTH callers through the canonical
:func:`mission_not_found_message` so a bad handle reads "Mission not found:
<handle>" everywhere.

The footgun this file guards against: ``merge --abort`` DELIBERATELY tolerates an
unresolvable handle (it must clean up a partial-state mission whose primary dir is
already gone), so the not-found gate lives at the two live callers (fresh /
resume), NOT in the shared ``_resolve_slug_or_exit`` helper. The abort case here
proves the tolerance survives.

These are CLI-boundary tests (tmp_path kitty-specs + ``CliRunner``; no real git
worktree), so they run in ``fast-tests-merge`` — mirroring
``tests/merge/test_2959_skip_review_artifact_check.py``. Without a marker the file
is orphaned by the CI collection-completeness gates.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import specify_cli.cli.commands.merge as merge_mod

pytestmark = pytest.mark.fast

_PHANTOM_HANDLE = "zznope"
_NOT_FOUND = f"Mission not found: {_PHANTOM_HANDLE}"


def _make_mission(specs_dir: Path, slug: str, mission_id: str) -> None:
    """Create a minimal but real mission directory under ``kitty-specs/``."""
    mission_dir = specs_dir / slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": mission_id, "mission_slug": slug, "friendly_name": slug}),
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text(f"# {slug}\n", encoding="utf-8")


@pytest.fixture
def repo_with_two_missions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo root with two real missions and NO interrupted merge state."""
    specs_dir = tmp_path / "kitty-specs"
    _make_mission(specs_dir, "alpha-mission-aaaa1111", "01AAAA1111000000000000000A")
    _make_mission(specs_dir, "beta-mission-bbbb2222", "01BBBB2222000000000000000B")

    # Run as if from the main repo (require_main_repo reads Path.cwd()); point
    # the command's repo-root resolver at the tmp tree.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
    return tmp_path


def _app() -> typer.Typer:
    app = typer.Typer()
    app.command()(merge_mod.merge)
    return app


def test_fresh_unknown_handle_reports_mission_not_found(repo_with_two_missions: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(a) Fresh ``merge --mission zznope`` → canonical not-found, non-zero.

    NOT the misleading "lanes.json is required" MissingLanesError.
    """
    # The git preflight runs before the fresh not-found gate; neutralize it so
    # the gate is the only thing that can fire.
    monkeypatch.setattr(merge_mod, "_enforce_git_preflight", lambda *a, **k: None)

    result = CliRunner().invoke(_app(), ["--mission", _PHANTOM_HANDLE])

    assert result.exit_code != 0, result.output
    assert _NOT_FOUND in result.output
    assert "lanes.json is required" not in result.output


def test_resume_unknown_handle_reports_mission_not_found(
    repo_with_two_missions: Path,
) -> None:
    """(b) ``merge --resume --mission zznope`` → canonical not-found.

    NOT "No interrupted merge to resume": the unknown-handle refusal pre-empts
    the no-state check.
    """
    result = CliRunner().invoke(_app(), ["--resume", "--mission", _PHANTOM_HANDLE])

    assert result.exit_code != 0, result.output
    assert _NOT_FOUND in result.output
    assert "No interrupted merge to resume" not in result.output


def test_abort_unknown_handle_stays_tolerant(repo_with_two_missions: Path) -> None:
    """(c) ``merge --abort --mission zznope`` → tolerant cleanup, NOT a hard not-found.

    Abort must clean up a partial-state mission whose primary dir may already be
    gone, so the handle-resolution stays non-raising and the not-found gate is
    never applied here.
    """
    result = CliRunner().invoke(_app(), ["--abort", "--mission", _PHANTOM_HANDLE])

    assert result.exit_code == 0, result.output
    assert _NOT_FOUND not in result.output
