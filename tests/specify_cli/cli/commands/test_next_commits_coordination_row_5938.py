"""#5938: ``next`` commits the event row it writes into the coordination worktree.

Every ``spec-kitty next --result success`` appends a ``MissionNextInvoked`` row
to ``kitty-specs/<mission>/mission-events.jsonl``. On a coordination Mission that
file lives in the coordination worktree, and ``next`` left it untracked there,
so ``consolidate`` later refused ``MERGE_UNSAFE_WORKTREE_DIRTY`` on a file the
tool itself wrote. The #5669 ruling keeps the log real dirt for every gate, so
the fix is that ``next`` commits it; it is never exempted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.cli_mission_fixture_7545 import create_mission, dirty, flat, git, init_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(900)]


@pytest.fixture()
def mission(tmp_path: Path):
    repo, env = init_repo(tmp_path)
    return create_mission(repo, env, "beta", topology="coord")


def _next(mission):
    return mission.run("next", "--agent", "claude", "--mission", mission.slug, "--json", "--result", "success")


def test_next_leaves_the_coordination_worktree_clean(mission) -> None:
    coord = mission.coordination_worktree()
    assert dirty(coord) == []

    proc = _next(mission)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert dirty(coord) == []
    committed = git(coord, "show", "--name-only", "--format=%s", "HEAD").splitlines()
    assert committed[0].startswith("chore(next): record next invocation")
    assert f"kitty-specs/{mission.slug}/mission-events.jsonl" in committed


def test_next_never_commits_an_operator_file_in_the_coordination_worktree(mission) -> None:
    coord = mission.coordination_worktree()
    (coord / "operator-notes.md").write_text("mine\n", encoding="utf-8")

    proc = _next(mission)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert dirty(coord) == ["operator-notes.md"]


def test_a_lane_cut_after_next_still_moves_to_review(mission) -> None:
    """The committed row reaches lanes parented on the coordination branch.

    The lane guard must tolerate that inherited, tool-written log exactly like
    the inherited status pair; before the predicate, ``move-task --to
    for_review`` refused with "kitty-specs/ changes are not allowed on lane
    branches".
    """
    assert _next(mission).returncode == 0
    mission.run("implement", "WP01", "--mission", mission.slug, check=True)
    lane = next(path for path in sorted((mission.repo / ".worktrees").iterdir()) if "-lane-" in path.name)
    (lane / "src" / "beta").mkdir(parents=True)
    (lane / "src" / "beta" / "mod.py").write_text("B = 1\n", encoding="utf-8")
    git(lane, "add", "src/beta")
    git(lane, "commit", "-qm", "WP01: beta")
    mission.run("agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", mission.slug, check=True)

    proc = mission.run("agent", "tasks", "move-task", "WP01", "--to", "for_review", "--agent", "claude", "--mission", mission.slug)

    assert proc.returncode == 0, flat(proc)[-3000:]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("kitty-specs/m-01ABCDEF/mission-events.jsonl", True),
        ("kitty-specs\\m-01ABCDEF\\mission-events.jsonl", True),
        ("kitty-specs/m-01ABCDEF/research/mission-events.jsonl", False),
        ("src/app/mission-events.jsonl", False),
        ("kitty-specs/m-01ABCDEF/status.events.jsonl", False),
    ],
)
def test_mission_event_log_predicate(path: str, expected: bool) -> None:
    from specify_cli.mission_v1.events import is_mission_event_log_path

    assert is_mission_event_log_path(path) is expected


def test_commit_mission_event_log_stages_only_the_log(tmp_path: Path) -> None:
    """The shared committer commits the one log file and never an operator's edit."""
    from specify_cli.mission_v1.events import commit_mission_event_log

    repo, env = init_repo(tmp_path)
    mission = create_mission(repo, env, "epsilon", topology="coord")
    coord = mission.coordination_worktree()
    log = coord / "kitty-specs" / mission.slug / "mission-events.jsonl"
    log.write_text('{"type": "MissionNextInvoked"}\n', encoding="utf-8")
    (coord / "operator-notes.md").write_text("mine\n", encoding="utf-8")

    assert commit_mission_event_log(repo, mission.slug, log, coord) is None
    assert dirty(coord) == ["operator-notes.md"]
    # An already-committed row is a quiet no-op.
    assert commit_mission_event_log(repo, mission.slug, log, coord) is None


def test_commit_mission_event_log_reports_a_refusal_instead_of_raising(tmp_path: Path) -> None:
    from specify_cli.mission_v1.events import commit_mission_event_log

    repo, env = init_repo(tmp_path)
    mission = create_mission(repo, env, "zeta", topology="coord")
    outside = tmp_path / "elsewhere.jsonl"
    outside.write_text("x\n", encoding="utf-8")

    warning = commit_mission_event_log(repo, mission.slug, outside, mission.coordination_worktree())

    assert warning is not None
    assert "commit it before consolidate" in warning


def test_answer_decision_commits_the_row_and_surfaces_a_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``orchestrator-api answer-decision`` mirrors ``next``: it commits the row it wrote
    into a coordination worktree through the same committer and reports a refusal in
    its ``warnings``. Driven through the existing answer-decision harness (a flat
    Mission); the emitter is wrapped to report a coordination-worktree write.
    """
    from runtime.next import next_invocation_lifecycle
    from runtime.next.next_invocation_lifecycle import MissionNextInvokedWrite
    from tests.specify_cli.orchestrator_api import test_answer_decision as harness

    mission_slug = "wp03-answer-decision-row"
    mission_type = "wp03-answer-decision-row-mission"
    repo_root = harness._scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP03ROWCOMMITULID00001")
    harness._write_input_requiring_mission(repo_root, mission_type)
    agent = "wp03-agent"
    harness._next(repo_root, agent, mission_slug)
    decision_id = harness._next(repo_root, agent, mission_slug)["decision_id"]

    real_emit = next_invocation_lifecycle.emit_mission_next_invoked
    committed: list[tuple[str, Path]] = []

    def _emit_in_coordination(*args, **kwargs):
        write = real_emit(*args, **kwargs)
        assert write is not None
        return MissionNextInvokedWrite(write.log_path, write.surface_root, in_coordination_worktree=True)

    def _refusing_commit(_repo_root: Path, slug: str, log_path: Path, _checkout_root: Path) -> str:
        from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed

        committed.append((slug, log_path))
        raise SafeCommitRecoveryFailed("restore failed", orphan_stash_ref="refs/stash-orphan-answer", commit_sha=None)

    # ``answer-decision`` imports the seam function-locally, so patch it at its home.
    monkeypatch.setattr(next_invocation_lifecycle, "emit_mission_next_invoked", _emit_in_coordination)
    monkeypatch.setattr("specify_cli.mission_v1.events.commit_mission_event_log", _refusing_commit)

    result = harness._run_answer_decision(
        repo_root,
        ["--mission", mission_slug, "--agent", agent, "--result", "success", "--answer", "yes", "--decision-id", decision_id, "--policy", harness._POLICY],
    )

    envelope = harness._envelope(result)
    assert envelope["success"] is True, envelope
    assert [slug for slug, _ in committed] == [mission_slug]
    # The recovery failure (not just a plain refusal) reaches ``warnings`` with its orphan stash ref.
    assert any("refs/stash-orphan-answer" in warning for warning in envelope["data"]["warnings"]), envelope["data"]["warnings"]


def test_next_commits_its_row_in_the_repository_root_checkout_too(tmp_path: Path) -> None:
    """On a single_branch Mission the row is written into the repository root checkout: committed there as well."""
    repo, env = init_repo(tmp_path)
    mission = create_mission(repo, env, "theta", topology="single_branch")

    proc = _next(mission)

    assert proc.returncode == 0, flat(proc)[-2000:]
    assert f"kitty-specs/{mission.slug}/mission-events.jsonl" not in dirty(repo)
    assert f"kitty-specs/{mission.slug}/mission-events.jsonl" in git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()


@pytest.mark.parametrize(("landed", "expected"), [(False, True), (True, False)])
def test_a_landed_missions_row_is_never_committed(tmp_path: Path, landed: bool, expected: bool) -> None:
    from runtime.next.next_invocation_lifecycle import MissionNextInvokedWrite

    write = MissionNextInvokedWrite(tmp_path / "mission-events.jsonl", tmp_path, in_coordination_worktree=False, mission_landed=landed)

    assert write.should_commit is expected


@pytest.mark.parametrize(
    ("raised", "in_coordination", "expected_substrings"),
    [
        # A failed staging restore names the orphan stash, in every checkout (the root checkout included).
        ("recovery", False, ["refs/stash-orphan", "git stash pop --index", "did land"]),
        ("recovery", True, ["refs/stash-orphan"]),
        # A plain refusal blocks consolidate only for the coordination worktree's copy.
        ("refusal", True, ["could not commit the row"]),
        ("refusal", False, []),
    ],
)
def test_commit_event_row_surfaces_a_recovery_failure_with_its_stash_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raised: str, in_coordination: bool, expected_substrings: list[str]
) -> None:
    from runtime.next.next_invocation_lifecycle import MissionNextInvokedWrite
    from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
    from specify_cli.mission_v1 import events

    def _commit(*_args: object) -> str:
        if raised == "recovery":
            raise SafeCommitRecoveryFailed("restore failed", orphan_stash_ref="refs/stash-orphan", commit_sha="abc123")
        return "could not commit the row"

    monkeypatch.setattr(events, "commit_mission_event_log", _commit)
    write = MissionNextInvokedWrite(tmp_path / "mission-events.jsonl", tmp_path, in_coordination_worktree=in_coordination)
    warnings: list[str] = []

    events.commit_event_row(tmp_path, "m", write, warn=warnings.append)

    text = "\n".join(warnings)
    assert bool(warnings) is bool(expected_substrings)
    for fragment in expected_substrings:
        assert fragment in text


def test_next_dispatch_surfaces_a_recovery_failure_with_its_stash_ref_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Wiring: ``next``'s advancing path commits through ``commit_event_row``, so the orphan stash ref reaches stderr."""
    from runtime.next.decision import Decision, DecisionKind
    from runtime.next.next_invocation_lifecycle import MissionNextInvokedWrite
    from specify_cli.cli.commands import next_cmd
    from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
    from specify_cli.mission_v1 import events

    write = MissionNextInvokedWrite(tmp_path / "mission-events.jsonl", tmp_path, in_coordination_worktree=False)

    def _commit(*_args: object) -> str:
        raise SafeCommitRecoveryFailed("restore failed", orphan_stash_ref="refs/stash-orphan-next", commit_sha="abc123")

    monkeypatch.setattr(events, "commit_mission_event_log", _commit)
    monkeypatch.setattr(next_cmd, "_pair_previous_lifecycle_record", lambda *a, **k: None)
    prompt = tmp_path / "WP01-prompt.md"
    prompt.write_text("# WP01\n", encoding="utf-8")
    # A real Decision (#7623): a hand-rolled stand-in drifts each time the command reads a new field.
    decision = Decision(
        kind=DecisionKind.step,
        agent="claude",
        mission_slug="m",
        mission="software-dev",
        mission_state="implement",
        timestamp="2026-11-13T00:00:00+00:00",
        action="implement",
        wp_id="WP01",
        prompt_file=str(prompt),
    )
    monkeypatch.setattr(next_cmd, "decide_next", lambda *a, **k: decision)
    monkeypatch.setattr(next_cmd, "_emit_mission_next_invoked", lambda *a, **k: write)
    monkeypatch.setattr(next_cmd, "_write_issuance_lifecycle_record", lambda *a, **k: None)
    monkeypatch.setattr(next_cmd, "_print_decision", lambda *a, **k: None)

    next_cmd._dispatch_advancing_mode("claude", "m", "success", tmp_path, False, None, None, owned=None)

    err = capsys.readouterr().err
    assert "refs/stash-orphan-next" in err
    assert "git stash pop --index" in err
