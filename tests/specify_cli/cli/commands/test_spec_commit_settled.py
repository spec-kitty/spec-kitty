"""``spec-commit`` on a settled default Mission (#7551, FR-002/FR-003/FR-011/FR-012, SC-001/SC-003).

After the first ``finalize-tasks`` settles a default Mission to ``lanes_with_coord``, the
repository root checkout returns to ``create_return_branch`` and the coordination worktree
holds the topic branch (coordination branch == Mission branch). Every scenario drives the
real ``spec-kitty spec-commit`` command (typer ``CliRunner`` on the real app, with the
process cwd set the way an operator stands) on the real ``make_default_mission`` +
``run_finalize`` fixture, and asserts where the commit landed with ``git``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

#: NFR-001: one single-file spec-commit on a settled Mission stays well under this (generous CI margin).
_NFR_001_BUDGET_SECONDS = 5.0


@pytest.fixture(autouse=True)
def _quiet_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


@pytest.fixture(params=["main", "dev"])
def settled(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DefaultMission:
    """A default Mission settled to ``lanes_with_coord``, root on protected ``main`` or unprotected ``dev``."""
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on=str(request.param))
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert git(mission.root, "branch", "--show-current") == mission.return_branch
    assert git(coord_root(mission), "branch", "--show-current") == mission.topic
    return mission


def coord_root(mission: DefaultMission) -> Path:
    return mission.coord_mission_dir.parents[1]


def spec_commit(cwd: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object]]:
    """Run the real ``spec-kitty spec-commit --json`` from *cwd*; returns ``(exit_code, payload)``."""
    from specify_cli import app as cli_app

    monkeypatch.chdir(cwd)
    result = CliRunner().invoke(cli_app, ["spec-commit", *args, "--json"], catch_exceptions=False)
    start = result.output.find("{")
    payload: dict[str, object] = json.loads(result.output[start:]) if start >= 0 else {"raw": result.output}
    return result.exit_code, payload


def rel(mission: DefaultMission, tail: str) -> str:
    return f"kitty-specs/{mission.slug}/{tail}"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def assert_on_topic(mission: DefaultMission, tail: str, text: str, subject: str) -> None:
    assert git(mission.root, "log", "-1", "--format=%s", mission.topic) == subject
    assert git(mission.root, "show", f"{mission.topic}:{rel(mission, tail)}") == text.rstrip("\n")


# ---------------------------------------------------------------------------
# (a)-(c): coordination-worktree cwd, relative Mission paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tail",
    [
        "traces/tooling-friction.md",  # (a) TRACER_FILE (COORD kind)
        "tasks/WP01-work/baseline-tests.json",  # (b) WORK_PACKAGE_TASK (PRIMARY kind)
        "decisions/DM-01SETTLED.md",  # (c) DECISION_LEDGER (PRIMARY kind)
        "decisions.events.jsonl",  # (c) DECISION_LOG (COORD kind)
    ],
)
def test_coord_cwd_relative_path_lands_on_topic(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch, tail: str) -> None:
    text = f"settled {tail}\n"
    write(settled.coord_mission_dir / tail, text)
    root_tip = git(settled.root, "rev-parse", "HEAD")

    code, payload = spec_commit(coord_root(settled), monkeypatch, rel(settled, tail), "-m", f"commit {tail}")

    assert code == 0, payload
    assert payload["committed"] is True
    assert_on_topic(settled, tail, text, f"commit {tail}")
    assert git(settled.root, "rev-parse", "HEAD") == root_tip
    assert not (settled.root / rel(settled, tail)).exists(), "nothing may be copied into the repository root checkout"


@pytest.mark.timing
def test_nfr_001_single_file_spec_commit_wall_clock(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: one warm single-file spec-commit from the coordination worktree, wall clock."""
    write(settled.coord_mission_dir / "traces" / "warm.md", "# warm\n")
    code, payload = spec_commit(coord_root(settled), monkeypatch, rel(settled, "traces/warm.md"), "-m", "warm-up")
    assert code == 0, payload
    write(settled.coord_mission_dir / "traces" / "timed.md", "# timed\n")

    started = time.perf_counter()
    code, payload = spec_commit(coord_root(settled), monkeypatch, rel(settled, "traces/timed.md"), "-m", "timed")
    elapsed = time.perf_counter() - started

    assert code == 0, payload
    print(f"NFR-001 spec-commit wall clock: {elapsed:.3f}s")
    assert elapsed < _NFR_001_BUDGET_SECONDS


# ---------------------------------------------------------------------------
# (d) root cwd, relative path to a file that exists only in the coordination worktree
# ---------------------------------------------------------------------------


def test_root_cwd_relative_path_reanchors_to_holder(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    tail = "traces/approach.md"
    write(settled.coord_mission_dir / tail, "# approach\n")
    root_tip = git(settled.root, "rev-parse", "HEAD")

    code, payload = spec_commit(settled.root, monkeypatch, rel(settled, tail), "-m", "root cwd tracer")

    assert code == 0, payload
    assert_on_topic(settled, tail, "# approach\n", "root cwd tracer")
    assert git(settled.root, "rev-parse", "HEAD") == root_tip


# ---------------------------------------------------------------------------
# (e)+(g) root-only copy is refused (never copied); the printed remedy is followable
# ---------------------------------------------------------------------------


def test_root_only_copy_is_refused_and_remedy_is_followable(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    tail = "traces/stray.md"
    stray = write(settled.root / rel(settled, tail), "# stray\n")
    holder_copy = settled.coord_mission_dir / tail
    topic_tip = git(settled.root, "rev-parse", settled.topic)

    code, payload = spec_commit(settled.root, monkeypatch, rel(settled, tail), "-m", "stray tracer")

    assert code != 0, payload
    surfaces = payload["surfaces"]
    assert isinstance(surfaces, list)
    reasons = {fate["reason"] for surface in surfaces for fate in surface.get("refused", [])}
    assert reasons == {"WRONG_SURFACE"}, payload
    message = str(payload.get("error") or "")
    assert str(holder_copy) in message, message
    assert "git -C" not in message
    assert not holder_copy.exists(), "the root copy must never be copied into the coordination worktree"
    assert git(settled.root, "rev-parse", settled.topic) == topic_tip

    # (g) SC-003: do exactly what the remedy says -- move it into the named holder path -- and re-run.
    holder_copy.parent.mkdir(parents=True, exist_ok=True)
    stray.rename(holder_copy)
    code, payload = spec_commit(settled.root, monkeypatch, rel(settled, tail), "-m", "stray tracer")

    assert code == 0, payload
    assert_on_topic(settled, tail, "# stray\n", "stray tracer")


def test_edited_root_copy_beside_holder_copy_is_refused(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    """A root copy whose bytes differ from the holder copy is refused, never silently dropped."""
    tail = "spec.md"
    holder_copy = settled.coord_mission_dir / tail
    holder_text = holder_copy.read_text(encoding="utf-8")
    root_copy = write(settled.root / rel(settled, tail), "# EDITED AT ROOT\n")
    topic_tip = git(settled.root, "rev-parse", settled.topic)

    code, payload = spec_commit(settled.root, monkeypatch, rel(settled, tail), "-m", "root spec edit")

    assert code != 0, payload
    surfaces = payload["surfaces"]
    assert isinstance(surfaces, list)
    reasons = {fate["reason"] for surface in surfaces for fate in surface.get("refused", [])}
    assert reasons == {"WRONG_SURFACE"}, payload
    message = str(payload.get("error") or "")
    assert str(holder_copy) in message, message
    assert str(root_copy) in message, message
    assert holder_copy.read_text(encoding="utf-8") == holder_text, "the root copy must never be copied over the holder copy"
    assert git(settled.root, "rev-parse", settled.topic) == topic_tip


# ---------------------------------------------------------------------------
# (f) control: absolute coordination-worktree path from the root (works today)
# ---------------------------------------------------------------------------


def test_absolute_holder_path_from_root_commits(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    tail = "traces/tooling-friction.md"
    path = write(settled.coord_mission_dir / tail, "# friction\n")

    code, payload = spec_commit(settled.root, monkeypatch, str(path), "-m", "absolute tracer", "--mission", settled.slug)

    assert code == 0, payload
    assert_on_topic(settled, tail, "# friction\n", "absolute tracer")


# ---------------------------------------------------------------------------
# #5501 re-check: a mixed decision/trace batch reports every path committed
# ---------------------------------------------------------------------------


def test_mixed_batch_reports_every_path_committed(settled: DefaultMission, monkeypatch: pytest.MonkeyPatch) -> None:
    tails = ("decisions/DM-01MIXED.md", "traces/mixed.md")
    for tail in tails:
        write(settled.coord_mission_dir / tail, f"{tail}\n")

    code, payload = spec_commit(coord_root(settled), monkeypatch, *(rel(settled, tail) for tail in tails), "-m", "mixed batch")

    assert code == 0, payload
    arguments = payload["arguments"]
    assert isinstance(arguments, list)
    assert [argument["fate"] for argument in arguments] == ["committed", "committed"], arguments
    for tail in tails:
        assert git(settled.root, "show", f"{settled.topic}:{rel(settled, tail)}") == tail
