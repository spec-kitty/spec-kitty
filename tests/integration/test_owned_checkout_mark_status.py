"""Explicit mark-status writes only the selected single-branch checkout."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app as tasks_app
from tests.integration.test_explicit_checkout_commands import (
    SLUG,
    TARGET,
    checkouts,
    git,
    invoke,
    snapshot,
)
from tests.status.test_transition_request_owned import claim_counter
from specify_cli.workspace.context import clear_workspace_resolution_caches

__all__ = ["checkouts", "claim_counter"]
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture
def finalized_checkouts(checkouts: tuple[Path, Path, Path]) -> tuple[Path, Path, Path]:
    primary, owned, sibling = checkouts
    before = snapshot(primary), snapshot(sibling)
    mission = owned / "kitty-specs" / SLUG
    (mission / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\n- [ ] T001 Implement the local task\n",
        encoding="utf-8",
    )
    wp_file = mission / "tasks/WP01-test.md"
    wp_file.write_text(
        wp_file.read_text(encoding="utf-8").replace("subtasks: []", "subtasks: [T001]"),
        encoding="utf-8",
    )
    # Mirror the ``spec-kitty init`` ignore contract: the derived execution-state
    # projection (#4971) lands under ``.kittify/derived/`` and is never tracked.
    (owned / ".gitignore").write_text(".kittify/sync-state.json\n.kittify/derived/\n", encoding="utf-8")
    git(owned, "add", ".gitignore")
    git(owned, "commit", "-qm", "fixture: ignore checkout-local sync bookkeeping and derived views")
    result = invoke("finalize-tasks", owned)
    assert result.exit_code == 0, result.output
    assert git(owned, "branch", "--show-current") == TARGET
    assert git(owned, "status", "--porcelain") == ""
    assert not (primary / "kitty-specs" / SLUG).exists()
    assert not (sibling / "kitty-specs" / SLUG).exists()
    assert (snapshot(primary), snapshot(sibling)) == before
    return checkouts


def test_mark_status_updates_only_selected_checkout(
    finalized_checkouts: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary, owned, sibling = finalized_checkouts
    shadow = primary / "kitty-specs" / SLUG
    shutil.copytree(owned / "kitty-specs" / SLUG, shadow)
    (shadow / "tasks.md").write_text(
        (shadow / "tasks.md").read_text(encoding="utf-8").replace("T001", "T999"),
        encoding="utf-8",
    )
    shadow_wp = shadow / "tasks/WP01-test.md"
    shadow_wp.write_text(
        shadow_wp.read_text(encoding="utf-8").replace("T001", "T999"),
        encoding="utf-8",
    )
    monkeypatch.chdir(sibling)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(sibling))
    others_before = snapshot(primary), snapshot(sibling)
    owned_head_before = git(owned, "rev-parse", "HEAD")

    result = CliRunner().invoke(
        tasks_app,
        [
            "mark-status",
            "T001",
            "--status",
            "done",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"] == {"updated": 1, "already_satisfied": 0, "not_found": 0}
    assert payload["destination_ref"] == TARGET
    assert Path(payload["owned_checkout"]) == owned
    assert payload["state_applied"] is True
    assert payload["applied_wps"] == ["WP01"]
    assert len(payload["event_ids"]) == 1

    mission = owned / "kitty-specs" / SLUG
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["wp_id"] == "WP01"
    assert events[-1]["delta"]["subtasks"] == {"T001": "done"}
    state = json.loads((mission / "status.json").read_text(encoding="utf-8"))
    assert state["work_packages"]["WP01"]["subtasks"]["T001"] == "done"
    assert git(owned, "rev-parse", "HEAD") != owned_head_before
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == others_before


def test_flagless_mark_status_preserves_primary_lookup(
    finalized_checkouts: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-022 control: flagless from the repository root checkout has nothing to adopt.

    The FR-021 adoption row is ``test_mark_status_validates_ownership_exactly_once[flagless_from_inside_owned]``.
    """
    monkeypatch.chdir(finalized_checkouts[0])
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(finalized_checkouts[0]))
    before = tuple(snapshot(root) for root in finalized_checkouts)

    result = CliRunner().invoke(
        tasks_app,
        ["mark-status", "T001", "--status", "done", "--mission", SLUG, "--json"],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error_code"] == "MISSION_NOT_FOUND"
    assert payload["handle"] == SLUG
    assert tuple(snapshot(root) for root in finalized_checkouts) == before


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
        ("no_commit", "OWNED_OPTION_UNSUPPORTED"),
    ],
)
def test_owned_preflight_refuses_before_effects(
    checkouts: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    code: str,
) -> None:
    primary, owned, sibling = checkouts
    checkout = owned
    extra: list[str] = []
    include_mission = True
    if case == "nested":
        checkout = owned / "kitty-specs"
    elif case == "foreign":
        checkout = tmp_path / "foreign"
        checkout.mkdir()
        git(checkout, "init", "-q", "-b", "main")
    elif case == "missing_mission":
        include_mission = False
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
    elif case == "no_commit":
        extra = ["--no-auto-commit"]

    args = [
        "mark-status",
        "T001",
        "--status",
        "done",
        "--owned-checkout",
        str(checkout),
        "--json",
        *extra,
    ]
    if include_mission:
        args += ["--mission", SLUG]
    before = tuple(snapshot(root) for root in checkouts)

    result = CliRunner().invoke(tasks_app, args)

    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == code
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


def test_owned_materialization_failure_rolls_back_without_ambient_writes(
    finalized_checkouts: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.coordination import transaction

    before = tuple(snapshot(root) for root in finalized_checkouts)

    def fail_materialize(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected materialization failure")

    monkeypatch.setattr(transaction._reducer, "materialize", fail_materialize)
    result = CliRunner().invoke(
        tasks_app,
        [
            "mark-status",
            "T001",
            "--status",
            "done",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(finalized_checkouts[1]),
            "--json",
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error_code"] == "MARK_STATUS_FAILED"
    assert payload["state_applied"] is False
    assert payload["event_ids"] == []
    assert payload["dirty"] is False
    assert tuple(snapshot(root) for root in finalized_checkouts) == before


@pytest.fixture
def multi_wp_finalized_checkouts(
    finalized_checkouts: tuple[Path, Path, Path],
) -> tuple[Path, Path, Path]:
    primary, owned, sibling = finalized_checkouts
    mission = owned / "kitty-specs" / SLUG
    tasks_md = mission / "tasks.md"
    tasks_md.write_text(
        tasks_md.read_text(encoding="utf-8") + "\n## Work Package WP02\n\n**Dependencies**: WP01\n\n- [ ] T002 Implement the second local task\n",
        encoding="utf-8",
    )
    (mission / "tasks/WP02-test.md").write_text(
        "---\nwork_package_id: WP02\ntitle: Second local task\n"
        "dependencies: [WP01]\nrequirement_refs: [FR-001]\n"
        "subtasks: [T002]\nowned_files: [app.py]\n"
        "authoritative_surface: app.py\nexecution_mode: code_change\n---\n\n# Task\n",
        encoding="utf-8",
    )
    git(owned, "add", ".")
    git(owned, "commit", "-qm", "fixture: add second work package")
    before = snapshot(primary), snapshot(sibling)
    result = invoke("finalize-tasks", owned)
    assert result.exit_code == 0, result.output
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == before
    return finalized_checkouts


def test_multi_wp_failure_reports_committed_prefix(
    multi_wp_finalized_checkouts: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mission_runtime import ActionContextError
    from specify_cli.coordination import status_transition

    primary, owned, sibling = multi_wp_finalized_checkouts
    original = status_transition.emit_inner_state_changed_transactional
    calls = 0

    def fail_second(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ActionContextError("TEST_SECOND_WP", "second work package refused")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        status_transition,
        "emit_inner_state_changed_transactional",
        fail_second,
    )
    others_before = snapshot(primary), snapshot(sibling)
    head_before = git(owned, "rev-parse", "HEAD")
    result = CliRunner().invoke(
        tasks_app,
        [
            "mark-status",
            "T001",
            "T002",
            "--status",
            "done",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error_code"] == "TEST_SECOND_WP"
    assert payload["state_applied"] is True
    assert payload["applied_wps"] == ["WP01"]
    assert len(payload["event_ids"]) == 1
    state = json.loads((owned / "kitty-specs" / SLUG / "status.json").read_text(encoding="utf-8"))["work_packages"]
    assert state["WP01"]["subtasks"]["T001"] == "done"
    assert state["WP02"].get("subtasks", {}).get("T002") != "done"
    assert git(owned, "rev-parse", "HEAD") != head_before
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == others_before


def test_concurrent_event_is_not_claimed_in_failure_envelope(
    multi_wp_finalized_checkouts: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mission_runtime import ActionContextError
    from specify_cli.coordination import status_transition

    primary, owned, sibling = multi_wp_finalized_checkouts
    original = status_transition.emit_inner_state_changed_transactional
    calls = 0
    foreign_event_ids: list[str] = []

    def interleave_then_fail(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        if calls == 2:
            foreign_kwargs = dict(kwargs)
            foreign_kwargs["actor"] = "concurrent-writer"
            foreign_kwargs["operation"] = "concurrent annotation"
            event = original(*args, **foreign_kwargs)
            foreign_event_ids.append(event.event_id)
            raise ActionContextError("TEST_INTERLEAVED", "current writer failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        status_transition,
        "emit_inner_state_changed_transactional",
        interleave_then_fail,
    )
    others_before = snapshot(primary), snapshot(sibling)
    result = CliRunner().invoke(
        tasks_app,
        [
            "mark-status",
            "T001",
            "T002",
            "--status",
            "done",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error_code"] == "TEST_INTERLEAVED"
    assert payload["applied_wps"] == ["WP01"]
    assert len(payload["event_ids"]) == 1
    assert foreign_event_ids and foreign_event_ids[0] not in payload["event_ids"]
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == others_before


def test_post_commit_recovery_reports_only_exact_commit_events(
    finalized_checkouts: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.coordination import status_transition

    primary, owned, sibling = finalized_checkouts
    original = status_transition.emit_inner_state_changed_transactional
    committed_event_ids: list[str] = []

    class RecoveryAfterCommit(RuntimeError):
        def __init__(self, commit_sha: str) -> None:
            super().__init__("injected recovery failure after commit")
            self.commit_sha = commit_sha

    def commit_then_fail(*args: object, **kwargs: object):
        event = original(*args, **kwargs)
        committed_event_ids.append(event.event_id)
        raise RecoveryAfterCommit(git(owned, "rev-parse", "HEAD"))

    monkeypatch.setattr(
        status_transition,
        "emit_inner_state_changed_transactional",
        commit_then_fail,
    )
    others_before = snapshot(primary), snapshot(sibling)
    result = CliRunner().invoke(
        tasks_app,
        [
            "mark-status",
            "T001",
            "--status",
            "done",
            "--mission",
            SLUG,
            "--owned-checkout",
            str(owned),
            "--json",
        ],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error_code"] == "MARK_STATUS_FAILED"
    assert payload["state_applied"] is True
    assert payload["applied_wps"] == ["WP01"]
    assert payload["event_ids"] == committed_event_ids
    assert git(owned, "status", "--porcelain") == ""
    assert (snapshot(primary), snapshot(sibling)) == others_before


# ---------------------------------------------------------------------------
# WP16/T089 (FR-003 / NFR-002): exactly one ownership validation per owned
# task-family command invocation, counted at the ownership-claim primitive so a
# re-introduced local validator call (the #3866 class) goes red.
# ---------------------------------------------------------------------------


def _reset_counting(claim_counter: list[Path | None]) -> None:
    """Clear the process-global resolution caches and the counter before a counted run."""
    clear_workspace_resolution_caches()
    claim_counter.clear()


@pytest.mark.parametrize("flagged", [True, False], ids=["flag_given", "flagless_from_inside_owned"])
def test_mark_status_validates_ownership_exactly_once(
    finalized_checkouts: tuple[Path, Path, Path],
    claim_counter: list[Path | None],
    flagged: bool,
) -> None:
    _primary, owned, _sibling = finalized_checkouts
    args = ["mark-status", "T001", "--status", "done", "--mission", SLUG, "--json"]
    if flagged:
        args += ["--owned-checkout", str(owned)]
    _reset_counting(claim_counter)

    result = CliRunner().invoke(tasks_app, args)

    assert result.exit_code == 0, result.output
    assert len(claim_counter) == 1, claim_counter


def test_flagless_mark_status_from_repository_root_checkout_validates_nothing(
    finalized_checkouts: tuple[Path, Path, Path],
    claim_counter: list[Path | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary, _owned, _sibling = finalized_checkouts
    monkeypatch.chdir(primary)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(primary))
    _reset_counting(claim_counter)

    result = CliRunner().invoke(tasks_app, ["mark-status", "T001", "--status", "done", "--mission", SLUG, "--json"])

    assert result.exit_code == 1, result.output
    assert claim_counter == []


@pytest.mark.parametrize("command", ["spec-commit", "check-prerequisites"])
def test_owned_authoring_command_validates_ownership_exactly_once(
    checkouts: tuple[Path, Path, Path],
    claim_counter: list[Path | None],
    command: str,
) -> None:
    _primary, owned, _sibling = checkouts
    if command == "spec-commit":
        spec = owned / "kitty-specs" / SLUG / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\nCounted edit.\n", encoding="utf-8")
    _reset_counting(claim_counter)

    result = invoke(command, owned)

    assert result.exit_code == 0, result.output
    assert len(claim_counter) == 1, claim_counter


def test_owned_mark_status_threads_the_fact_and_never_consults_get_main_repo_root(
    finalized_checkouts: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The owned arm reads the validated fact directly: the annotation emitter receives
    ``owned=`` (never a bare root), and the ``tasks`` namespace's ``get_main_repo_root``
    seam is never consulted (WP16)."""
    from mission_runtime import OwnedCheckout
    from specify_cli.cli.commands.agent import tasks
    from specify_cli.coordination import status_transition

    _primary, owned, _sibling = finalized_checkouts
    seen: list[dict[str, object]] = []
    real_emit = status_transition.emit_inner_state_changed_transactional

    def _recording(*args: object, **kwargs: object) -> object:
        seen.append(kwargs)
        return real_emit(*args, **kwargs)

    def _forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("an owned run must not consult get_main_repo_root")

    monkeypatch.setattr(status_transition, "emit_inner_state_changed_transactional", _recording)
    monkeypatch.setattr(tasks, "get_main_repo_root", _forbidden)

    result = CliRunner().invoke(
        tasks_app,
        ["mark-status", "T001", "--status", "done", "--mission", SLUG, "--owned-checkout", str(owned), "--json"],
    )

    assert result.exit_code == 0, result.output
    assert len(seen) == 1
    fact = seen[0]["owned"]
    assert isinstance(fact, OwnedCheckout)
    assert fact.owned_root == owned.resolve()
    assert "effective_root" not in seen[0]
