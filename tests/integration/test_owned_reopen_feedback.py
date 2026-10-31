"""Actual owned CLI forwarding, preserving canonical FSM and actor authority."""

from collections.abc import Callable
from pathlib import Path
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner, Result

from tests.integration.conftest import OwnedCheckouts, make_owned_checkouts as make_owned_checkouts, _git
from tests.terminus.conftest import pin_planning_commit
from tests._support.status_seed import seed_status_event
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.lanes.persistence import require_lanes_json, write_lanes_json
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import read_events
from specify_cli.consolidation.preflight import _independent_reviewer_confirmed

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _snapshot(root: Path) -> tuple[str, dict[str, bytes]]:
    return (
        _git(root, "rev-parse", "HEAD"),
        {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts},
    )


def _fixture(factory: Callable[..., OwnedCheckouts], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, approved: bool) -> tuple[OwnedCheckouts, Path]:
    home = tmp_path / "runtime-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.delenv("SPEC_KITTY_PACKS_ROOT", raising=False)
    case = factory(wp_ids=("WP01",))
    fd = case.mission_dir
    p = case.owned_root
    meta = json.loads((fd / "meta.json").read_text())
    meta.update(status_phase=1, mission_branch=case.target_branch)
    (fd / "meta.json").write_text(json.dumps(meta) + "\n")
    wp = fd / "tasks/WP01-owned.md"
    text = (
        wp.read_text()
        .replace("owned_files: []", "owned_files: [src/wp01/**]")
        .replace("authoritative_surface: app.py", "authoritative_surface: src/wp01/")
        .replace("execution_mode: code_change", "execution_mode: code_change\nagent_profile: unrelated-frontmatter-profile")
    )
    wp.write_text(text)
    manifest = require_lanes_json(fd)
    manifest.mission_branch = case.target_branch
    write_lanes_json(fd, manifest)
    _git(p, "add", ".")
    _git(p, "commit", "-qm", "controlled finalized planning fixture")
    pin_planning_commit(p, fd, commit_message="record actual planning pin")
    code = p / "src/wp01/main.zig"
    code.parent.mkdir(parents=True)
    code.write_text("pub fn answer() u8 { return 42; }\n")
    _git(p, "add", ".")
    _git(p, "commit", "-qm", "controlled implementation after planning")
    chain = [("genesis", "planned")]
    if approved:
        chain += [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved")]
    for i, (old, new) in enumerate(chain):
        seed_status_event(
            fd,
            StatusEvent(
                event_id=f"controlled-old-{i}",
                mission_slug=case.mission_slug,
                wp_id="WP01",
                from_lane=old,
                to_lane=new,
                actor="codex",
                at=f"2026-10-30T00:00:0{i}Z",
                force=False,
                execution_mode="direct_repo",
            ),
        )
    feedback = p / "review-feedback.md"
    feedback.write_text("# Independent review\n\nReopen this implementation for correction and a genuine new independent review.\n")
    _git(p, "add", ".")
    _git(p, "commit", "-qm", "persist controlled fixture state and feedback")
    monkeypatch.chdir(p)
    return case, feedback


def _move(case: OwnedCheckouts, target: str, profile: str, *extra: str) -> Result:
    with (
        patch("specify_cli.runtime.agent_commands.ensure_global_agent_commands", side_effect=AssertionError("global command writes forbidden")) as commands,
        patch("specify_cli.runtime.agent_skills.ensure_global_agent_skills", side_effect=AssertionError("global skill writes forbidden")) as skills,
    ):
        result = CliRunner().invoke(
            tasks_app,
            [
                "move-task",
                "WP01",
                "--mission",
                case.mission_slug,
                "--owned-checkout",
                str(case.owned_root),
                "--to",
                target,
                "--agent",
                "codex",
                "--profile",
                profile,
                "--note",
                "Controlled actual CLI forwarding proof",
                *extra,
            ],
        )
        assert commands.call_count == skills.call_count == 0
    return result


@pytest.mark.parametrize("kind", ["provided", "absent", "missing", "directory"])
def test_owned_approved_reopen_feedback_contract(
    make_owned_checkouts: Callable[..., OwnedCheckouts], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    case, feedback = _fixture(make_owned_checkouts, tmp_path, monkeypatch, approved=True)
    primary = _snapshot(case.repository_root)
    sibling = _snapshot(case.sibling)
    before = _snapshot(case.owned_root)
    old = list(read_events(case.mission_dir))
    extra = []
    if kind != "absent":
        path = feedback if kind == "provided" else (tmp_path / "missing.md" if kind == "missing" else tmp_path)
        extra = ["--review-feedback-file", str(path)]
    result = _move(case, "in_progress", "implementer-ivan", *extra)
    assert _snapshot(case.repository_root) == primary
    assert _snapshot(case.sibling) == sibling
    if kind in ("missing", "directory"):
        assert result.exit_code == 1, result.output
        assert _snapshot(case.owned_root) == before
        assert list(read_events(case.mission_dir)) == old
        return
    assert result.exit_code == 0, result.output
    events = list(read_events(case.mission_dir))
    assert [e.to_dict() for e in events[: len(old)]] == [e.to_dict() for e in old]
    event = events[-1]
    assert event.to_lane == "in_progress"
    if kind == "provided":
        assert event.force is False, event.to_dict()
        assert event.review_ref == str(feedback.resolve())
    else:
        # Existing FR-015 explicitly promotes the missing-ref backward move.
        # Preserve that policy honestly; this case is never called force-free.
        assert event.force is True, event.to_dict()
        assert event.review_ref is None
    assert event.actor == {"tool": "codex", "profile": "implementer-ivan", "model": None, "role": "implementer"}


def test_explicit_profiles_preserved_on_actual_owned_hops(
    make_owned_checkouts: Callable[..., OwnedCheckouts], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, _ = _fixture(make_owned_checkouts, tmp_path, monkeypatch, approved=False)
    primary = _snapshot(case.repository_root)
    sibling = _snapshot(case.sibling)
    for target, profile in [
        ("claimed", "implementer-ivan"),
        ("in_progress", "implementer-ivan"),
        ("for_review", "implementer-ivan"),
        ("in_review", "reviewer-renata"),
        ("approved", "reviewer-renata"),
    ]:
        result = _move(case, target, profile, *(["--reviewer", "reviewer-renata"] if target == "approved" else []))
        assert result.exit_code == 0, (target, result.output)
        event = list(read_events(case.mission_dir))[-1]
        assert event.to_lane == target
        assert event.force is False, event.to_dict()
        assert event.actor == {"tool": "codex", "profile": profile, "model": None, "role": "reviewer" if target in ("in_review", "approved") else "implementer"}
    assert _independent_reviewer_confirmed(case.mission_dir, "WP01") is True
    assert _snapshot(case.repository_root) == primary
    assert _snapshot(case.sibling) == sibling
