"""Direct unit tests for the create-mission phase helpers (#2056 WP05, T018).

The pre-decomposition ``create_mission`` was a 281-LOC monolith; WP05 split it
into ≤15-CC phase helpers. These tests exercise each helper's branches in
isolation: start-branch coherence/switch, mission-type selector resolution, the
PR-bound branch-strategy gate, the core-creation error funnel, the ``pr_bound``
meta write-back, the worktree navigation hint, and the JSON/human output
builders. The end-to-end command stays pinned by ``test_mission_create.py``,
``test_agent_feature.py`` and the WP01 golden harness.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.cli.commands.agent import mission_create as seam

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _mk_result(tmp_path: Path, **over: Any) -> Any:
    """Build a minimal ``MissionCreationResult`` stand-in."""
    from specify_cli.core.mission_creation import MissionCreationResult

    feature_dir = over.pop("feature_dir", tmp_path / "kitty-specs" / "001-demo")
    feature_dir.mkdir(parents=True, exist_ok=True)
    defaults: dict[str, Any] = {
        "feature_dir": feature_dir,
        "mission_slug": "001-demo",
        "mission_number": None,
        "meta": {"mission_id": "01ABC", "friendly_name": "Demo"},
        "target_branch": "main",
        "current_branch": "main",
    }
    defaults.update(over)
    return MissionCreationResult(**defaults)


# ---------------------------------------------------------------------------
# _resolve_start_branch_phase
# ---------------------------------------------------------------------------


def test_start_branch_phase_noop_when_absent(tmp_path: Path) -> None:
    # No exception, no switch attempted.
    seam._resolve_start_branch_phase(repo_root=tmp_path, start_branch=None, target_branch="main", json_output=True)


def test_start_branch_phase_rejects_target_mismatch(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit) as exc:
        seam._resolve_start_branch_phase(repo_root=tmp_path, start_branch="feat-a", target_branch="feat-b", json_output=True)
    assert exc.value.exit_code == 1


def test_start_branch_phase_switches_when_matching(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []
    from specify_cli.cli.commands.agent import mission as mission_module

    monkeypatch.setattr(mission_module, "_switch_to_start_branch", lambda _r, b: calls.append(b))
    seam._resolve_start_branch_phase(repo_root=tmp_path, start_branch="feat-a", target_branch="feat-a", json_output=True)
    assert calls == ["feat-a"]


def test_start_branch_phase_switch_failure_exits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission as mission_module

    def _boom(_r: object, _b: object) -> None:
        raise RuntimeError("switch failed")

    monkeypatch.setattr(mission_module, "_switch_to_start_branch", _boom)
    with pytest.raises(typer.Exit):
        seam._resolve_start_branch_phase(repo_root=tmp_path, start_branch="feat-a", target_branch=None, json_output=True)


# ---------------------------------------------------------------------------
# _resolve_mission_type_phase
# ---------------------------------------------------------------------------


def test_mission_type_phase_passthrough_when_none() -> None:
    assert seam._resolve_mission_type_phase(mission_type=None, mission=None, json_output=True) is None


def test_mission_type_phase_resolves_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    out = seam._resolve_mission_type_phase(mission_type="software-dev", mission=None, json_output=True)
    assert out == "software-dev"


def test_mission_type_phase_conflict_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    def _bad(**_k: object) -> None:
        raise typer.BadParameter("conflict")

    monkeypatch.setattr(seam, "resolve_selector", _bad)
    with pytest.raises(typer.Exit):
        seam._resolve_mission_type_phase(mission_type="a", mission="b", json_output=True)


# ---------------------------------------------------------------------------
# _enforce_branch_strategy_gate_phase
# ---------------------------------------------------------------------------


def test_branch_strategy_gate_passes_when_not_pr_bound() -> None:
    # Not PR-bound → gate is a no-op (no exception).
    seam._enforce_branch_strategy_gate_phase(
        pr_bound=False,
        current_branch="main",
        target_branch="main",
        branch_strategy=None,
        start_branch=None,
        json_output=True,
    )


def test_branch_strategy_gate_requires_confirmation_in_json() -> None:
    # PR-bound + on the merge target + no confirmation + json → structured exit.
    with pytest.raises(typer.Exit) as exc:
        seam._enforce_branch_strategy_gate_phase(
            pr_bound=True,
            current_branch="main",
            target_branch="main",
            branch_strategy=None,
            start_branch=None,
            json_output=True,
        )
    assert exc.value.exit_code == 1


def test_branch_strategy_gate_bypassed_by_already_confirmed() -> None:
    # already-confirmed bypasses the prompt → no exception.
    seam._enforce_branch_strategy_gate_phase(
        pr_bound=True,
        current_branch="main",
        target_branch="main",
        branch_strategy="already-confirmed",
        start_branch=None,
        json_output=True,
    )


# ---------------------------------------------------------------------------
# _run_create_core_phase error funnel
# ---------------------------------------------------------------------------


def test_run_create_core_phase_returns_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result = _mk_result(tmp_path)
    import specify_cli.core.mission_creation as core

    monkeypatch.setattr(core, "create_mission_core", lambda **_k: result)
    out = seam._run_create_core_phase(
        repo_root=tmp_path,
        mission_slug="001-demo",
        resolved_mission_type="software-dev",
        target_branch="main",
        friendly_name=None,
        purpose_tldr=None,
        purpose_context=None,
        pr_bound=False,
        force_recreate_coordination_branch=False,
        owned_create_root=None,
        json_output=True,
    )
    assert out is result


def test_run_create_core_phase_handles_creation_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.core.mission_creation as core

    def _boom(**_k: object) -> None:
        raise core.MissionCreationError("nope")

    monkeypatch.setattr(core, "create_mission_core", _boom)
    with pytest.raises(typer.Exit):
        seam._run_create_core_phase(
            repo_root=tmp_path,
            mission_slug="001-demo",
            resolved_mission_type=None,
            target_branch=None,
            friendly_name=None,
            purpose_tldr=None,
            purpose_context=None,
            pr_bound=False,
            force_recreate_coordination_branch=False,
            owned_create_root=None,
            json_output=True,
        )


def test_run_create_core_phase_carries_typed_error_code_into_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """#3861: the delegate's typed failure reason travels in the ``--json``
    error payload as ``error_code`` so scripted callers (the orchestrator-api
    ``specify`` verb) classify on the structured code, never on message
    prose. A generic ``MissionCreationError`` (no typed reason) still emits
    the bare ``{"error": ...}`` shape -- no code is invented for it."""

    import json

    import specify_cli.core.mission_creation as core

    def _dup(**_k: object) -> None:
        raise core.MissionAlreadyExistsError("A mission named '001-demo' of type 'software-dev' already exists and is not abandoned (#4033).")

    monkeypatch.setattr(core, "create_mission_core", _dup)
    with pytest.raises(typer.Exit):
        seam._run_create_core_phase(
            repo_root=tmp_path,
            mission_slug="001-demo",
            resolved_mission_type="software-dev",
            target_branch=None,
            friendly_name=None,
            purpose_tldr=None,
            purpose_context=None,
            pr_bound=False,
            force_recreate_coordination_branch=False,
            owned_create_root=None,
            json_output=True,
        )

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["error_code"] == "MISSION_ALREADY_EXISTS"
    assert "already exists" in payload["error"]


def test_run_create_core_phase_generic_error_omits_error_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """#3861 complement: a generic (unclassified) ``MissionCreationError``
    keeps the bare ``{"error": ...}`` payload -- no typed reason is invented,
    and downstream fallback classification (``MISSION_CREATE_FAILED``) owns
    the generic code."""

    import json

    import specify_cli.core.mission_creation as core

    def _boom(**_k: object) -> None:
        raise core.MissionCreationError("nope")

    monkeypatch.setattr(core, "create_mission_core", _boom)
    with pytest.raises(typer.Exit):
        seam._run_create_core_phase(
            repo_root=tmp_path,
            mission_slug="001-demo",
            resolved_mission_type=None,
            target_branch=None,
            friendly_name=None,
            purpose_tldr=None,
            purpose_context=None,
            pr_bound=False,
            force_recreate_coordination_branch=False,
            owned_create_root=None,
            json_output=True,
        )

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "error_code" not in payload
    assert payload["error"] == "nope"


# ---------------------------------------------------------------------------
# _print_worktree_navigation_hint
# ---------------------------------------------------------------------------


def test_worktree_hint_silent_without_worktree_term(capsys: pytest.CaptureFixture[str]) -> None:
    seam._print_worktree_navigation_hint("001-demo", "some other error")
    assert "main repository" not in capsys.readouterr().out


def test_worktree_hint_prints_when_worktree_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.cli.commands.agent import mission as mission_module

    monkeypatch.setattr(mission_module, "locate_project_root", lambda _c=None: tmp_path)
    seam._print_worktree_navigation_hint("001-demo", "cannot run inside worktree")
    out = capsys.readouterr().out
    assert "main repository" in out
    assert "001-demo" in out


# ---------------------------------------------------------------------------
# _build_create_payload / _emit_create_result_phase
# ---------------------------------------------------------------------------


def test_build_create_payload_shape(tmp_path: Path) -> None:
    payload = seam._build_create_payload(_mk_result(tmp_path))
    assert payload["result"] == "success"
    assert payload["mission_slug"] == "001-demo"
    assert payload["scaffold_only"] is True
    assert payload["plan_guard"] == "SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED"
    assert "origin_binding" in payload


def test_emit_create_result_json_marks_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    marked = {"hit": False}
    monkeypatch.setattr(seam, "mark_invocation_succeeded", lambda: marked.__setitem__("hit", True))
    emitted: dict[str, Any] = {}
    monkeypatch.setattr(seam, "_emit_json", lambda p: emitted.update(p))
    seam._emit_create_result_phase(_mk_result(tmp_path), resolved_mission_type="software-dev", json_output=True)
    assert marked["hit"] is True
    assert emitted["result"] == "success"
    assert "branch_context" in emitted  # branch contract injected


def test_emit_create_result_human(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    seam._emit_create_result_phase(_mk_result(tmp_path), resolved_mission_type="software-dev", json_output=False)
    out = capsys.readouterr().out
    assert "Mission created: 001-demo" in out


# ---------------------------------------------------------------------------
# WP10 fix-cycle-1, HIGH-3 (declared out-of-map: this file is not WP10-owned,
# but is the pre-existing test home for `_run_create_core_phase`, and WP10's
# own T055 already re-pointed two of its calls). An explicit --owned-checkout
# claim with no locatable project root must fail closed with the SAME typed
# `MissionCreationError` the function's own funnel already classifies --
# never silently degrade to an unowned create.
# ---------------------------------------------------------------------------


def test_mint_owned_create_root_fails_closed_when_no_repo_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """HIGH-3 fix-cycle-1, re-pointed in fix-cycle-2: the guard now lives in
    ``_mint_owned_create_root`` (called from ``create_mission`` itself,
    before any git operation -- fix-cycle-2 HIGH), not in
    ``_run_create_core_phase``."""
    import json

    with pytest.raises(typer.Exit):
        seam._mint_owned_create_root(None, tmp_path, mission_slug="001-demo", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "Could not locate project root" in payload["error"]


# ---------------------------------------------------------------------------
# WP10 fix-cycle-1, MEDIUM-7 (declared out-of-map, same rationale as HIGH-3
# above). The Risks section requires a one-line CLI pin of
# OWNED_CHECKOUT_IS_REPOSITORY_ROOT; this also covers the ActionContextError
# branch of _emit_create_core_error_and_exit, which otherwise has no test.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_agent_mission_create_owned_checkout_repository_root_refused_via_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import subprocess

    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.mission import app
    from tests._factories import provision_test_charter

    repo_root = tmp_path / "repository_root"
    repo_root.mkdir()
    (repo_root / ".kittify").mkdir()
    provision_test_charter(repo_root)
    (repo_root / "kitty-specs").mkdir()
    subprocess.run(["git", "init", "-b", "work"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_root, check=True, capture_output=True)

    runner = CliRunner()
    monkeypatch.chdir(repo_root)
    result = runner.invoke(
        app,
        ["create", "repo-root-refused", "--owned-checkout", str(repo_root), "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["success"] is False
    assert payload["error_code"] == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"
    assert "error" in payload
    assert not (repo_root / "kitty-specs" / "repo-root-refused").exists()


# ---------------------------------------------------------------------------
# WP10 fix-cycle-2, HIGH (formerly ADVISORY-13, now in scope; declared
# out-of-map, same rationale as the tests above). Pre-fix, `create_mission`
# computed `command_checkout = owned_checkout.resolve()` from the RAW,
# UNVALIDATED --owned-checkout claim and ran the start-branch switch, the
# current-branch read and the topology derivation against it BEFORE
# `resolve_owned_create_root` ever validated it -- a real git mutation of a
# checkout the validator goes on to refuse.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize(
    ("claim_kind", "expected_error_code"),
    [
        ("repository_root", "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"),
        ("foreign_repository", "OWNERSHIP_FOREIGN"),
    ],
)
def test_create_mission_never_switches_start_branch_before_owned_claim_is_validated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    claim_kind: str,
    expected_error_code: str,
) -> None:
    import json
    import subprocess

    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent import mission as mission_module
    from specify_cli.cli.commands.agent.mission import app
    from tests._factories import provision_test_charter

    def _init_repo(root: Path, branch: str) -> None:
        root.mkdir()
        (root / ".kittify").mkdir()
        provision_test_charter(root)
        (root / "kitty-specs").mkdir()
        subprocess.run(["git", "init", "-b", branch], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

    def _current_branch(root: Path) -> str:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()

    repository_root = tmp_path / "repository_root"
    _init_repo(repository_root, "work")

    if claim_kind == "repository_root":
        claim = repository_root
    else:
        claim = tmp_path / "foreign_repository"
        _init_repo(claim, "work")

    claim_branch_before = _current_branch(claim)

    switch_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(mission_module, "_switch_to_start_branch", lambda *args: switch_calls.append(args))

    runner = CliRunner()
    monkeypatch.chdir(repository_root)
    result = runner.invoke(
        app,
        [
            "create",
            "probe",
            "--owned-checkout",
            str(claim),
            "--start-branch",
            "side",
            "--target-branch",
            "side",
            "--json",
        ],
    )

    # The core assertion: the CLI never switched a branch in the claimed
    # checkout before the claim was validated -- regardless of whether that
    # checkout is R itself or an unrelated foreign repository.
    assert switch_calls == []
    assert _current_branch(claim) == claim_branch_before

    assert result.exit_code == 1
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["error_code"] == expected_error_code
    assert not (repository_root / "kitty-specs" / "probe").exists()
