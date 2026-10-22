"""Regression: the acceptance/verify/merge surface hard-rejects pre-3.0 layout.

Squad review (PR #2168, Blocker 1 / #1057) found a silent regression: retiring
the pre-3.0 readers made the acceptance engine *warn-and-skip* a pre-3.0
(legacy lane-directory) mission. ``_iter_work_packages`` then yielded ZERO work
packages, so ``AcceptanceSummary.all_done`` was **vacuously True** and ``accept``
auto-committed an unmigrated mission whose real WPs still sat in
``tasks/planned/`` — "all acceptance checks passed" on un-done work.

These tests pin the contract: a pre-3.0 mission reaching the accept / verify /
merge surface must **exit 1** with the ``spec-kitty upgrade`` migration message
and write **nothing** (no acceptance commit), matching the guarded task
commands. The engine-level test pins the same hard reject at
``collect_feature_summary`` so accept AND verify inherit it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.acceptance import collect_feature_summary
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.upgrade.pre30_guard import Pre30LayoutError
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "099-legacy-pre30-mission"
_UPGRADE_HINT = "spec-kitty upgrade"
_GUARD_MARKER = "Pre-3.0 layout detected"


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _pre30_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Build a real git repo whose mission uses the pre-3.0 lane-directory layout.

    The mission carries the full acceptance surface — spec/plan/tasks present, a
    ``status.events.jsonl`` showing WP01 ``done``, and NO ``lanes.json`` — so that
    WITHOUT the guard the summary is vacuously ``all_done`` and ``accept`` would
    auto-commit. The work package itself lives in ``tasks/planned/WP01.md`` (the
    legacy lane directory the retired reader no longer sees).
    """
    repo = tmp_path / "repo"
    fd = repo / "kitty-specs" / _SLUG
    (fd / "tasks" / "planned").mkdir(parents=True)
    # A ``.kittify/`` marker gives ``locate_project_root`` a definite project
    # boundary at ``repo`` (WP04 C-A1 fixture hardening): without one,
    # repo-root detection falls back to a bare ``.git`` walk-up that can
    # escape past this fixture into an unrelated ancestor project.
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(parents=True)
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )

    (fd / "tasks" / "planned" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nagent: claude\nshell_pid: '12345'\n"
        "assignee: pedro\ntitle: Legacy work package\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (fd / "spec.md").write_text("# Spec\n\nReal spec content.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nReal plan content.\n", encoding="utf-8")
    (fd / "tasks.md").write_text("# Tasks\n\n## WP01\n\nNo unchecked checkboxes.\n", encoding="utf-8")
    (fd / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KW0LEGACY0000000000000099",
                "mission_slug": _SLUG,
                "friendly_name": "Legacy pre-3.0 mission",
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    seed_status_event(
        fd,
        StatusEvent(
            event_id="01KW0LEGACYEVENT0000000001",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.DONE,
            at="2026-06-26T00:00:00+00:00",
            actor="claude",
            force=False,
            execution_mode="direct_repo",
            mission_id="01KW0LEGACY0000000000000099",
        ),
    )

    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-qm", "seed legacy mission")
    return repo, fd


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


# ---------------------------------------------------------------------------
# Engine: collect_feature_summary must hard-reject, never vacuously pass
# ---------------------------------------------------------------------------


def test_collect_feature_summary_rejects_pre30(tmp_path: Path) -> None:
    """The acceptance engine raises Pre30LayoutError for a pre-3.0 mission.

    Before the fix the engine warn-skipped, returning a vacuously ``all_done``
    summary (``ok``) that let ``accept`` commit an unmigrated mission.
    """
    repo, fd = _pre30_repo(tmp_path)
    # WP09 (read-surface-ssot-closeout-01KWZV91/FR-001): ``collect_feature_summary``
    # no longer calls ``resolve_feature_dir_for_mission`` directly — it routes
    # through ``mission_runtime.placement_seam(...).read_dir(PRIMARY_METADATA)``
    # (a function-local import, so patching the ``mission_runtime`` source
    # attribute — not a ``specify_cli.acceptance`` module attribute — is what
    # actually intercepts the call). Mock the seam object so
    # ``placement_seam(...).read_dir(...)`` still returns ``fd``.
    mock_seam = MagicMock()
    mock_seam.read_dir.return_value = fd
    with (
        patch(
            "mission_runtime.placement_seam",
            return_value=mock_seam,
        ),
        patch(
            "specify_cli.acceptance._primary_anchor_feature_dir",
            return_value=fd,
        ),
        pytest.raises(Pre30LayoutError) as exc_info,
    ):
        collect_feature_summary(repo, _SLUG)
    message = str(exc_info.value)
    assert _GUARD_MARKER in message
    assert _UPGRADE_HINT in message


# ---------------------------------------------------------------------------
# accept (real CLI): exit 1 + migration message + NO acceptance commit
# ---------------------------------------------------------------------------
#
# FR-009: the standalone ``tasks_cli.accept_command`` / ``verify_command`` /
# ``merge_command`` guard tests were retired with the standalone tasks surface
# (WP03/FR-004). The hard-reject contract is now pinned on the real
# ``spec-kitty accept`` surface below; verify/merge inherit the same reject from
# the shared engine guard that ``test_collect_feature_summary_rejects_pre30``
# covers at the source.


def test_accept_cli_hard_rejects_pre30_and_commits_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``spec-kitty accept`` on a pre-3.0 mission exits 1 and writes nothing.

    Pins ``accept.py``'s ``except Pre30LayoutError`` branch directly: the engine
    raises, accept emits the ``spec-kitty upgrade`` instruction and exits 1
    WITHOUT creating an acceptance commit. Removing that handler (letting the
    vacuous all-done summary fall through and auto-commit) makes this fail.
    """
    repo, _fd = _pre30_repo(tmp_path)
    head_before = _head(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(
        cli_app,
        ["accept", "--mission", _SLUG, "--mode", "local", "--actor", "tester", "--json"],
    )

    assert result.exit_code == 1, result.output
    assert _UPGRADE_HINT in result.output
    # No acceptance commit was created.
    assert _head(repo) == head_before
