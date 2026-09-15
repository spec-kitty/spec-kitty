"""Explicit move-task writes only the selected single-branch checkout."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from tests.integration.test_explicit_checkout_commands import (
    SLUG,
    TARGET,
    checkouts,
    git,
    invoke,
    snapshot,
)

__all__ = ["checkouts"]
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_owned_gate_baseline_reads_selected_mission_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = tmp_path / "kitty-specs" / SLUG
    wp = mission / "tasks" / "WP01-test.md"
    captured: list[Path] = []
    monkeypatch.setattr(
        move_task_module.BaselineTestResult,
        "load",
        lambda path: captured.append(path),
    )
    state = SimpleNamespace(
        owned=SimpleNamespace(root=tmp_path),
        wp=SimpleNamespace(path=wp),
        feature_dir=mission,
    )

    move_task_module._mt_resolve_gate_baseline(state)

    assert captured == [mission / "tasks" / "WP01-test" / "baseline-tests.json"]


@pytest.fixture
def finalized_checkouts(checkouts: tuple[Path, Path, Path]) -> tuple[Path, Path, Path]:
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(sibling)
    (owned / ".gitignore").write_text(".kittify/sync-state.json\n", encoding="utf-8")
    git(owned, "add", ".gitignore")
    git(owned, "commit", "-qm", "fixture: ignore checkout-local sync bookkeeping")
    result = invoke("finalize-tasks", owned)
    assert result.exit_code == 0, result.output
    mission = owned / "kitty-specs" / SLUG
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["to_lane"] for row in events if row.get("wp_id") == "WP01"] == ["planned"]
    assert git(owned, "branch", "--show-current") == TARGET
    assert git(owned, "status", "--porcelain") == ""
    assert not (primary / "kitty-specs" / SLUG).exists()
    assert not (sibling / "kitty-specs" / SLUG).exists()
    assert (snapshot(primary), snapshot(sibling)) == before
    return checkouts


def test_finalized_work_is_readable_in_selected_checkout(finalized_checkouts):
    primary, owned, sibling = finalized_checkouts
    before = tuple(snapshot(root) for root in finalized_checkouts)
    result = invoke("check-prerequisites", owned, "--include-tasks")
    assert result.exit_code == 0, result.output
    assert Path(json.loads(result.output)["paths"]["feature_dir"]) == owned / "kitty-specs" / SLUG
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


def test_flagless_move_task_preserves_primary_lookup(finalized_checkouts):
    before = tuple(snapshot(root) for root in finalized_checkouts)
    result = CliRunner().invoke(
        tasks_app,
        ["move-task", "WP01", "--to", "doing", "--agent", "codex", "--mission", SLUG, "--json"],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error_code"] == "MISSION_NOT_FOUND"
    assert payload["handle"] == SLUG
    assert tuple(snapshot(root) for root in finalized_checkouts) == before


@pytest.mark.parametrize("caller", ["owned", "primary", "sibling"])
@pytest.mark.parametrize("shadow", [False, True], ids=["unique", "same_slug"])
def test_move_task_starts_work_finalized_in_linked_checkout(finalized_checkouts, monkeypatch, caller, shadow):
    primary, owned, sibling = finalized_checkouts
    if shadow:
        for other in (primary, sibling):
            mission = other / "kitty-specs" / SLUG
            shutil.copytree(owned / "kitty-specs" / SLUG, mission)
            events_path = mission / "status.events.jsonl"
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
            for event in events:
                if event.get("wp_id") == "WP01" and "to_lane" in event:
                    event["wp_id"] = "WP99"
            events_path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
            # A same-slug SHADOW work package on the non-selected partition. It
            # must be a READABLE WP file (valid frontmatter, no dependencies), not
            # a malformed stub: the in-lock dependency gate resolves WP readiness
            # from the primary partition, and the fail-closed policy (mission
            # fsm-write-path-integrity-01M1TZV6) refuses the transition when it
            # meets an unparseable WP file. The point of the fixture is that
            # move-task still resolves the OWNED checkout's WP over this shadow —
            # not that a corrupt shadow blocks the move.
            (mission / "tasks/WP01-test.md").write_text(
                "---\nwork_package_id: WP01\ntitle: not the selected work package\n"
                "dependencies: []\nrequirement_refs: []\nsubtasks: []\nowned_files: []\n"
                "authoritative_surface: app.py\nexecution_mode: code_change\n---\n\n"
                "# not the selected work package\n",
                encoding="utf-8",
            )
    cwd = {"owned": owned, "primary": primary, "sibling": sibling}[caller]
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(cwd))
    before = tuple(snapshot(root) for root in finalized_checkouts)
    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "codex",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--note",
            "owned note",
            "--assignee",
            "worker",
            "--tracker-ref",
            "test-123",
            "--json",
        ],
    )
    assert (snapshot(primary), snapshot(sibling)) == (before[0], before[2])
    if result.exit_code:
        # A failed lookup must not seed status or stage/commit anything.
        assert snapshot(owned) == before[1]
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert Path(payload["path"]) == owned / "kitty-specs" / SLUG / "tasks/WP01-test.md"
    assert Path(payload["status_events_path"]) == owned / "kitty-specs" / SLUG / "status.events.jsonl"
    mission = owned / "kitty-specs" / SLUG
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    transitions = [row for row in events if row.get("wp_id") == "WP01" and "to_lane" in row]
    assert transitions[-1]["to_lane"] == "in_progress"
    assert transitions[-1]["actor"] == "codex"
    assert git(owned, "branch", "--show-current") == TARGET
    assert git(owned, "rev-parse", "HEAD") != before[1][0]
    assert git(owned, "status", "--porcelain") == ""
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["agent"] == "codex"
    assert state["assignee"] == "worker"
    assert state["tracker_refs"] == ["test-123"]
    committed = git(owned, "show", f"HEAD:kitty-specs/{SLUG}/status.events.jsonl")
    assert json.loads(committed.splitlines()[-1])["delta"]["note"] == "owned note"


def test_owned_move_task_completes_with_sync_active(finalized_checkouts, monkeypatch):
    """#3980: the ``OWNED_SYNC_UNSUPPORTED`` refusal is gone — an owned
    ``move-task --to doing`` completes with hosted sync on (the fan-out
    handlers on the emit seam are bounded and non-raising, and the Zeitgeist
    moment handler no-ops without a session/team)."""
    primary, owned, sibling = finalized_checkouts
    monkeypatch.chdir(owned)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(owned))
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    before = tuple(snapshot(root) for root in finalized_checkouts)

    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "codex",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (snapshot(primary), snapshot(sibling)) == (before[0], before[2])
    mission = owned / "kitty-specs" / SLUG
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    transitions = [row for row in events if row.get("wp_id") == "WP01" and "to_lane" in row]
    assert transitions[-1]["to_lane"] == "in_progress"


@pytest.mark.parametrize(
    "case,code",
    [
        ("nested", "OWNERSHIP_NESTED"),
        ("foreign", "OWNERSHIP_FOREIGN"),
        ("missing_mission", "FEATURE_CONTEXT_UNRESOLVED"),
        ("protected", "OWNED_BRANCH_REFUSED"),
        ("wrong_branch", "OWNED_BRANCH_REFUSED"),
        ("staged", "OWNED_INDEX_REFUSED"),
        ("topology", "OWNED_TOPOLOGY_UNSUPPORTED"),
        ("done", "OWNED_TRANSITION_UNSUPPORTED"),
        ("force", "OWNED_OPTION_UNSUPPORTED"),
        ("skip", "OWNED_OPTION_UNSUPPORTED"),
        ("no_commit", "OWNED_OPTION_UNSUPPORTED"),
        ("bad_pid", "OWNED_INPUT_INVALID"),
    ],
)
def test_owned_preflight_refuses_before_effects(checkouts, tmp_path, monkeypatch, case, code):
    primary, owned, sibling = checkouts
    checkout = owned
    target = "doing"
    extra = []
    if case == "nested":
        checkout = owned / "kitty-specs"
    elif case == "foreign":
        checkout = tmp_path / "foreign"
        checkout.mkdir()
        git(checkout, "init", "-q", "-b", "main")
    elif case == "protected":
        with (primary / ".kittify/config.yaml").open("a", encoding="utf-8") as config:
            config.write("\nprotection:\n  protected_branches: [main, codex/owned]\n")
    elif case == "wrong_branch":
        git(owned, "checkout", "-qb", "codex/wrong")
    elif case == "staged":
        (owned / "app.py").write_text("VALUE = 999\n", encoding="utf-8")
        git(owned, "add", "app.py")
    elif case == "topology":
        path = owned / "kitty-specs" / SLUG / "meta.json"
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["topology"] = "coord"
        path.write_text(json.dumps(meta), encoding="utf-8")
    elif case in ("review", "done"):
        target = "for_review" if case == "review" else "done"
    elif case in ("force", "skip", "no_commit"):
        extra = [{"force": "--force", "skip": "--skip-pre-review-gate", "no_commit": "--no-auto-commit"}[case]]
    elif case == "bad_pid":
        extra = ["--shell-pid", "not-a-number"]
    args = ["move-task", "WP01", "--to", target, "--owned-checkout", str(checkout), "--json", *extra]
    if case != "missing_mission":
        args += ["--mission", SLUG]
    before = tuple(snapshot(root) for root in checkouts)
    result = CliRunner().invoke(tasks_app, args)
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == code
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


@pytest.mark.parametrize("explicit", [False, True])
def test_context_error_envelope_is_opt_in(checkouts, monkeypatch, explicit):
    from mission_runtime import ActionContextError
    from specify_cli.cli.commands.agent import tasks_move_task

    def fail_context(*args):
        raise ActionContextError("TEST_CONTEXT", "context refused")

    monkeypatch.setattr(tasks_move_task, "_mt_resolve_targets", fail_context)
    args = ["move-task", "WP01", "--to", "doing", "--json"]
    if explicit:
        args += ["--owned-checkout", str(checkouts[1])]
    before = tuple(snapshot(root) for root in checkouts)
    result = CliRunner().invoke(tasks_app, args)
    assert result.exit_code == 1, result.output
    expected = {"error": "context refused"}
    if explicit:
        expected["error_code"] = "TEST_CONTEXT"
    assert json.loads(result.output) == expected
    assert tuple(snapshot(root) for root in checkouts) == before


def test_claim_start_with_pid_and_repeated_start_refused(finalized_checkouts):
    primary, owned, sibling = finalized_checkouts
    before = snapshot(primary), snapshot(sibling)
    mission = owned / "kitty-specs" / SLUG
    for target, expected_lane, assignee in [
        ("claimed", "claimed", "first"),
        ("doing", "in_progress", "second"),
    ]:
        result = CliRunner().invoke(
            tasks_app,
            [
                "move-task",
                "WP01",
                "--to",
                target,
                "--agent",
                "codex",
                "--shell-pid",
                str(os.getpid()),
                "--assignee",
                assignee,
                "--mission",
                SLUG,
                "--owned-checkout",
                str(owned),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
        assert state["lane"] == expected_lane
        assert state["assignee"] == assignee
        assert state["agent"] == "codex"
        assert state["shell_pid"] == os.getpid()
        assert git(owned, "status", "--porcelain") == ""
        assert (snapshot(primary), snapshot(sibling)) == before
    owned_before = snapshot(owned)
    repeated = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "codex",
            "--assignee",
            "third",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert repeated.exit_code == 1, repeated.output
    assert json.loads(repeated.output)["code"] == "invalid_transition"
    assert snapshot(owned) == owned_before
    assert (snapshot(primary), snapshot(sibling)) == before


def test_move_task_enters_review_against_selected_checkout_planning_commit(finalized_checkouts, monkeypatch):
    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    mission = owned / "kitty-specs" / SLUG

    started = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "codex",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert started.exit_code == 0, started.output

    manifest = json.loads((mission / "lanes.json").read_text(encoding="utf-8"))
    planning_commit = manifest["planning_commit_sha"]
    assert len(planning_commit) == 40
    git(owned, "cat-file", "-e", f"{planning_commit}^{{commit}}")

    (owned / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    git(owned, "add", "app.py")
    git(owned, "commit", "-qm", "test: implement owned work package")
    implementation_commit = git(owned, "rev-parse", "HEAD")
    assert implementation_commit != planning_commit
    assert git(owned, "merge-base", planning_commit, implementation_commit) == planning_commit

    monkeypatch.chdir(primary)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(primary))
    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--agent",
            "codex",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["new_lane"] == "for_review"
    assert Path(payload["path"]) == mission / "tasks/WP01-test.md"
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["lane"] == "for_review"
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == other_before


def test_owned_review_auto_commits_selected_checkout_deliverables(finalized_checkouts):
    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    started = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "codex",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert started.exit_code == 0, started.output

    (owned / "app.py").write_text("VALUE = 3\n", encoding="utf-8")
    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--agent",
            "codex",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert git(owned, "show", "HEAD:app.py") == "VALUE = 3"
    messages = git(owned, "log", "--format=%s", "--all").splitlines()
    assert "chore(WP01): commit lane deliverables for review" in messages
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == other_before


def test_owned_review_refuses_status_only_commits(finalized_checkouts):
    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    started = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "implementer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert started.exit_code == 0, started.output
    before_review = git(owned, "rev-parse", "HEAD")

    submitted = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--agent",
            "implementer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert submitted.exit_code == 1, submitted.output
    assert json.loads(submitted.output)["error_code"] == "OWNED_IMPLEMENTATION_MISSING"
    assert git(owned, "rev-parse", "HEAD") == before_review
    mission = owned / "kitty-specs" / SLUG
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["lane"] == "in_progress"
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == other_before


def test_owned_review_refuses_auto_commit_outside_owned_files(finalized_checkouts):
    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    started = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "implementer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert started.exit_code == 0, started.output
    before_review = git(owned, "rev-parse", "HEAD")
    (owned / "app.py").write_text("VALUE = 5\n", encoding="utf-8")
    (owned / "unrelated.txt").write_text("private draft\n", encoding="utf-8")

    submitted = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--agent",
            "implementer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert submitted.exit_code == 1, submitted.output
    assert json.loads(submitted.output)["error_code"] == "OWNED_DELIVERABLE_SCOPE_REFUSED"
    assert git(owned, "rev-parse", "HEAD") == before_review
    assert git(owned, "status", "--porcelain").splitlines() == ["M app.py", "?? unrelated.txt"]
    assert (snapshot(primary), snapshot(sibling)) == other_before


@pytest.mark.parametrize("invalid_base", [None, "f" * 40, "HEAD"])
def test_owned_review_refuses_invalid_planning_commit_before_effects(finalized_checkouts, monkeypatch, invalid_base):
    primary, owned, _sibling = finalized_checkouts
    started = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "codex",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert started.exit_code == 0, started.output

    lanes_path = owned / "kitty-specs" / SLUG / "lanes.json"
    manifest = json.loads(lanes_path.read_text(encoding="utf-8"))
    manifest["planning_commit_sha"] = git(owned, "rev-parse", "HEAD") if invalid_base == "HEAD" else invalid_base
    lanes_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.chdir(primary)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(primary))
    before = tuple(snapshot(root) for root in finalized_checkouts)
    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--agent",
            "codex",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "OWNED_REVIEW_BASE_INVALID"
    assert tuple(snapshot(root) for root in finalized_checkouts) == before


def _advance_owned_work_to_review(owned: Path) -> Path:
    mission = owned / "kitty-specs" / SLUG
    started = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "implementer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert started.exit_code == 0, started.output
    (owned / "app.py").write_text("VALUE = 4\n", encoding="utf-8")
    submitted = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--agent",
            "implementer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert submitted.exit_code == 0, submitted.output
    return mission


def test_owned_review_and_approval_write_only_selected_checkout(finalized_checkouts):
    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    mission = _advance_owned_work_to_review(owned)

    claimed = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "in_review",
            "--reviewer",
            "reviewer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    approved = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "approved",
            "--reviewer",
            "reviewer",
            "--approval-ref",
            "approval:local-review",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert approved.exit_code == 0, approved.output
    payload = json.loads(approved.output)
    assert payload["new_lane"] == "approved"
    assert payload["verdict_durably_persisted"] is True
    cycle = mission / "tasks" / "WP01-test" / "review-cycle-1.md"
    assert cycle.is_file()
    assert "reviewer_agent: reviewer" in cycle.read_text(encoding="utf-8")
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    transitions = [row for row in events if row.get("wp_id") == "WP01" and "to_lane" in row]
    assert [row["to_lane"] for row in transitions] == ["planned", "claimed", "in_progress", "for_review", "in_review", "approved"]
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["lane"] == "approved"
    assert state["agent"] == "implementer"
    assert state["role"] == "reviewer"
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == other_before


def test_owned_approval_summary_rides_event_and_note_stays_whole_in_reason(finalized_checkouts):
    """#4327 acceptance, at the canonical ``move-task`` door: a valid gist
    plus a long multi-line local note keeps the prose WHOLE in ``reason``,
    puts the pointer in the pointer slot, and carries the one-line gist on
    the persisted ``approved`` event — one hop, one event row."""
    primary, owned, sibling = finalized_checkouts
    mission = _advance_owned_work_to_review(owned)
    claimed = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "in_review",
            "--reviewer",
            "reviewer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert claimed.exit_code == 0, claimed.output

    long_note = (
        "Approved after re-running the baseline suite locally;\n"
        "the review artifact carries the reproduction command\n"
        "and the full verification transcript, including the\n"
        "focus-time regression the reviewer called out.\n"
    )
    approved = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "approved",
            "--reviewer",
            "reviewer",
            "--approval-ref",
            "approval:local-review",
            "--summary",
            "Approved after the focus-time fix",
            "--note",
            long_note,
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert approved.exit_code == 0, approved.output
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    approved_rows = [row for row in events if row.get("wp_id") == "WP01" and row.get("to_lane") == "approved"]
    assert len(approved_rows) == 1
    row = approved_rows[0]
    assert row["summary"] == "Approved after the focus-time fix"
    # Pointer-only (#4327): the durable review-cycle artifact's canonical
    # pointer rides the slot (FR-006 derives review_ref from the persisted
    # verdict's reference) — never the note's prose.
    assert row["review_ref"] == "review-cycle://owned-01M1A900/WP01-test/review-cycle-1.md"
    # The full multi-line note stays whole in reason — never truncated,
    # never folded into the pointer slot (only surrounding whitespace is
    # trimmed, as every note already is at input).
    assert row["reason"] == long_note.strip()


def test_owned_rejection_with_long_note_keeps_pointer_ref_and_carries_summary(finalized_checkouts, tmp_path):
    """#4327 widened acceptance (controller scope check, door 2): a rejection
    out of ``in_review`` with a long multi-line ``--note`` puts a POINTER in
    ``review_ref`` — never the note's prose, which pre-#4327 flowed there via
    the ``st.note_text`` fallback — carries the bounded gist in ``summary``,
    and keeps the full prose whole in ``reason``."""
    primary, owned, sibling = finalized_checkouts
    mission = _advance_owned_work_to_review(owned)
    claimed = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "in_review",
            "--reviewer",
            "reviewer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    feedback = tmp_path / "review-feedback.md"
    feedback.write_text("The focus-time fix regressed the baseline;\nrework the guard before resubmitting.\n", encoding="utf-8")

    long_note = (
        "Rejected after the baseline run showed the focus-time regression;\n"
        "the reviewer's transcript names the failing case\n"
        "and the reproduction command, and the rework plan\n"
        "restates the guard invariant the fix broke.\n"
    )
    rejected = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--reviewer",
            "reviewer",
            "--review-feedback-file",
            str(feedback),
            "--note",
            long_note,
            "--summary",
            "Rework: fix the focus-time regression",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert rejected.exit_code == 0, rejected.output
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    planned_rows = [row for row in events if row.get("wp_id") == "WP01" and row.get("to_lane") == "planned"]
    # One bootstrap planned row (finalize-tasks) + exactly one rejection hop.
    assert len(planned_rows) == 2
    row = planned_rows[-1]
    # The bounded gist rides the new inline attr.
    assert row["summary"] == "Rework: fix the focus-time regression"
    # Pointer-only (#4327): the rejection's review_ref is the review-cycle
    # pointer (or the synthetic ``review:<WP>`` token when no pointer
    # applies) — never the note's prose.
    assert row["review_ref"].startswith(("review-cycle://", "feedback://", "rev://")) or row["review_ref"] == "review:WP01"
    assert "\n" not in row["review_ref"]
    # The full multi-line rejection rationale stays whole in reason (the
    # backward-hop prefix naming the pointer is pre-existing behavior) —
    # never truncated, never folded into the pointer slot alone.
    assert long_note.strip() in row["reason"]


def test_owned_approval_emit_failure_compensates_selected_verdict(finalized_checkouts, monkeypatch):
    from specify_cli.cli.commands.agent import tasks_move_task

    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    mission = _advance_owned_work_to_review(owned)
    claimed = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "in_review",
            "--reviewer",
            "reviewer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert claimed.exit_code == 0, claimed.output

    def fail_after_verdict(*args, **kwargs):
        raise RuntimeError("injected owned transition failure")

    monkeypatch.setattr(tasks_move_task, "_mt_execute", fail_after_verdict)
    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "approved",
            "--reviewer",
            "reviewer",
            "--approval-ref",
            "approval:local-review",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 1, result.output
    cycle_rel = f"kitty-specs/{SLUG}/tasks/WP01-test/review-cycle-1.md"
    assert not (owned / cycle_rel).exists()
    assert cycle_rel not in git(owned, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["lane"] == "in_review"
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == other_before


def test_owned_failed_compensation_reports_durable_selected_verdict(finalized_checkouts, monkeypatch):
    from specify_cli.cli.commands.agent import tasks_move_task
    from specify_cli.cli.commands.agent.tasks_verdict_persistence import VerdictRevertError

    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    mission = _advance_owned_work_to_review(owned)
    claimed = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "in_review",
            "--reviewer",
            "reviewer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert claimed.exit_code == 0, claimed.output

    def fail_after_verdict(*args, **kwargs):
        raise RuntimeError("injected owned transition failure")

    def fail_compensation(*args, **kwargs):
        raise VerdictRevertError("injected owned compensation failure")

    monkeypatch.setattr(tasks_move_task, "_mt_execute", fail_after_verdict)
    monkeypatch.setattr(tasks_move_task, "revert_committed_verdict_write", fail_compensation)
    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "approved",
            "--reviewer",
            "reviewer",
            "--approval-ref",
            "approval:local-review",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "error"
    assert payload["verdict_durably_persisted"] is True
    assert payload["durability_classification"] == "durable"
    assert "injected owned transition failure" in payload["error"]
    assert "injected owned compensation failure" in payload["error"]
    cycle_rel = f"kitty-specs/{SLUG}/tasks/WP01-test/review-cycle-1.md"
    assert (owned / cycle_rel).is_file()
    assert cycle_rel in git(owned, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    assert payload["evidence_ref"] == cycle_rel
    assert payload["destination_ref"] == TARGET
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["lane"] == "in_review"
    assert state["agent"] == "implementer"
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == other_before


def test_owned_rejection_writes_review_and_releases_runtime_claim(finalized_checkouts, tmp_path):
    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    mission = _advance_owned_work_to_review(owned)
    claimed = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "in_review",
            "--reviewer",
            "reviewer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    feedback = tmp_path / "review-feedback.md"
    feedback.write_text("Нужно исправить реализацию.\n", encoding="utf-8")

    rejected = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--reviewer",
            "reviewer",
            "--review-feedback-file",
            str(feedback),
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert rejected.exit_code == 0, rejected.output
    payload = json.loads(rejected.output)
    assert payload["new_lane"] == "planned"
    assert payload["runtime_claim_released"] is True
    cycle = mission / "tasks" / "WP01-test" / "review-cycle-1.md"
    assert cycle.is_file()
    assert "reviewer_agent: reviewer" in cycle.read_text(encoding="utf-8")
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["lane"] == "planned"
    assert state.get("agent") is None
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == other_before


def test_annotation_failure_does_not_report_success(finalized_checkouts, monkeypatch):
    from mission_runtime import ActionContextError
    from specify_cli.coordination import status_transition

    primary, owned, sibling = finalized_checkouts
    before = snapshot(primary), snapshot(sibling)

    def unavailable(*args, **kwargs):
        raise ActionContextError("OWNED_TRANSACTION_UNAVAILABLE", "annotation unavailable")

    monkeypatch.setattr(status_transition, "emit_inner_state_changed_transactional", unavailable)
    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--agent",
            "codex",
            "--note",
            "not saved",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "error"
    assert payload["error_code"] == "OWNED_TRANSACTION_UNAVAILABLE"
    assert payload["transition_applied"] is True
    assert payload["verdict_durably_persisted"] is False
    mission = owned / "kitty-specs" / SLUG
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["lane"] == "in_progress"
    committed = git(owned, "show", f"HEAD:kitty-specs/{SLUG}/status.events.jsonl")
    assert not any(json.loads(line).get("delta", {}).get("note") == "not saved" for line in committed.splitlines())
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == before


def test_owned_rejection_annotation_failure_retains_durable_evidence(finalized_checkouts, monkeypatch, tmp_path):
    from mission_runtime import ActionContextError
    from specify_cli.coordination import status_transition

    primary, owned, sibling = finalized_checkouts
    other_before = snapshot(primary), snapshot(sibling)
    mission = _advance_owned_work_to_review(owned)
    claimed = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "in_review",
            "--reviewer",
            "reviewer",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    feedback = tmp_path / "review-feedback.md"
    feedback.write_text("Нужно исправить реализацию.\n", encoding="utf-8")

    def unavailable(*args, **kwargs):
        raise ActionContextError("OWNED_TRANSACTION_UNAVAILABLE", "annotation unavailable")

    monkeypatch.setattr(status_transition, "emit_inner_state_changed_transactional", unavailable)
    result = CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--reviewer",
            "reviewer",
            "--review-feedback-file",
            str(feedback),
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "error"
    assert payload["error_code"] == "OWNED_TRANSACTION_UNAVAILABLE"
    assert payload["transition_applied"] is True
    assert payload["verdict_durably_persisted"] is True
    cycle_rel = f"kitty-specs/{SLUG}/tasks/WP01-test/review-cycle-1.md"
    assert (owned / cycle_rel).is_file()
    assert cycle_rel in git(owned, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert state["lane"] == "planned"
    assert state["review_result"]["reference"].endswith("review-cycle-1.md")
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == other_before


def test_owned_ports_read_and_commit_only_selected_mission(checkouts):
    from mission_runtime import MissionArtifactKind
    from specify_cli.agent_tasks_ports import MissionHandle, RealCoordCommitRouter, RealFsReader
    from specify_cli.git.protection_policy import ProtectionPolicy

    primary, owned, sibling = checkouts
    mission = owned / "kitty-specs" / SLUG
    handle = MissionHandle(primary, SLUG, effective_root=owned)
    reader = RealFsReader()
    before = snapshot(primary), snapshot(sibling)
    assert reader.planning_read_dir(handle, kind=MissionArtifactKind.TASKS_INDEX) == mission
    assert reader.wp_tasks_dir(handle) == mission / "tasks"
    assert reader.primary_anchor_dir(handle) == mission
    spec = mission / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nOwned port edit.\n", encoding="utf-8")
    result = RealCoordCommitRouter().commit_artifact(
        handle,
        [spec],
        "owned artifact",
        kind=MissionArtifactKind.WORK_PACKAGE_TASK,
        policy=ProtectionPolicy.resolve(primary),
    )
    assert result.status == "committed"
    assert result.placement_ref == TARGET
    assert "Owned port edit." in git(owned, "show", f"HEAD:kitty-specs/{SLUG}/spec.md")
    assert (snapshot(primary), snapshot(sibling)) == before
