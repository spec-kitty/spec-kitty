"""Direct unit tests for the branch-context seam (#2056 WP05, Seam B).

Exercises the relocated branch-resolution helpers in
``specify_cli.cli.commands.agent.mission_branch_context`` directly: the branch
contract injector (legacy + primary-recommendation shapes), the local/remote ref
probe, the primary-branch recommender's fallback ladder, the start-branch
switcher's validation/switch paths, the planning-branch resolver's override vs.
meta precedence, the feature-target resolver, and ``_get_current_branch``. The
end-to-end ``branch-context`` command stays pinned by ``test_agent_feature.py``
and the WP01 golden harness; these add the focused branch coverage.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import mission as mission_mod
from specify_cli.cli.commands.agent import mission_branch_context as seam
from specify_cli.core import git_ops as core_git_ops

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# _inject_branch_contract
# ---------------------------------------------------------------------------


def test_inject_branch_contract_legacy_shape_omits_primary() -> None:
    """Without ``primary_branch`` the payload carries no recommendation keys."""
    out = seam._inject_branch_contract({}, target_branch="main", current_branch="main")
    assert out["current_branch"] == "main"
    assert out["target_branch"] == "main"
    assert out["branch_matches_target"] is True
    assert out["branch_context"]["matches_target"] is True
    assert "primary_branch" not in out
    assert "recommended_strategy" not in out


def test_inject_branch_contract_current_differs_from_target() -> None:
    out = seam._inject_branch_contract({}, target_branch="main", current_branch="feat-x")
    assert out["current_branch"] == "feat-x"
    assert out["branch_matches_target"] is False
    assert "Completed changes must merge into main" in str(out["branch_strategy_summary"])


def test_inject_branch_contract_on_primary_recommends_feature_branch() -> None:
    out = seam._inject_branch_contract({}, target_branch="main", current_branch="main", primary_branch="main")
    assert out["current_is_primary"] is True
    assert out["recommended_strategy"] == "feature-branch"
    assert "dedicated topic branch" in str(out["branch_recommendation_reason"])
    assert out["branch_context"]["recommended_strategy"] == "feature-branch"


def test_inject_branch_contract_off_primary_recommends_stay() -> None:
    out = seam._inject_branch_contract({}, target_branch="feat-x", current_branch="feat-x", primary_branch="main")
    assert out["current_is_primary"] is False
    assert out["recommended_strategy"] == "stay"
    assert "staying on it is fine" in str(out["branch_recommendation_reason"])


# ---------------------------------------------------------------------------
# _git_local_or_remote_branch_exists
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


def test_branch_exists_true_when_local_ref_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam.subprocess, "run", lambda *a, **k: _Result(0))
    assert seam._git_local_or_remote_branch_exists(tmp_path, "main") is True


def test_branch_exists_false_when_no_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam.subprocess, "run", lambda *a, **k: _Result(1))
    assert seam._git_local_or_remote_branch_exists(tmp_path, "ghost") is False


# ---------------------------------------------------------------------------
# _resolve_primary_branch_for_recommendation
# ---------------------------------------------------------------------------


# FR-007 fold: ``_resolve_primary_branch_for_recommendation`` now delegates to
# the canonical ``git_ops.resolve_primary_branch(..., bias=False)``, so the git
# calls route through ``core_git_ops.subprocess`` — the patch target moves there
# in lockstep with the fold. The no-feature-bias contract is unchanged.


def test_primary_recommendation_uses_symbolic_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Sym:
        returncode = 0
        stdout = "refs/remotes/origin/develop\n"
        stderr = ""

    monkeypatch.setattr(core_git_ops.subprocess, "run", lambda *a, **k: _Sym())
    assert seam._resolve_primary_branch_for_recommendation(tmp_path, "feat-x") == "develop"


def test_primary_recommendation_falls_back_to_current_when_common(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(core_git_ops.subprocess, "run", lambda *a, **k: _Result(1))
    # symbolic-ref fails (returncode 1) → current is a common primary → returned.
    assert seam._resolve_primary_branch_for_recommendation(tmp_path, "master") == "master"


def test_primary_recommendation_ignores_feature_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No-feature-bias contract (the reason the recommender diverges from the
    plain feature-biased resolver): with origin/HEAD unresolved and the current
    branch a ticket branch, the recommender returns the common primary (main),
    NOT the ticket branch. FR-007's fold must preserve this."""

    def fake_run(args: list[str], *a: object, **k: object) -> _Result:
        if "symbolic-ref" in args:
            return _Result(1)
        # no-feature-bias existence probe accepts a local ref for ``main``.
        if args[-1] == "refs/heads/main":
            return _Result(0)
        return _Result(1)

    monkeypatch.setattr(core_git_ops.subprocess, "run", fake_run)
    assert seam._resolve_primary_branch_for_recommendation(tmp_path, "feat/ticket-9") == "main"


# ---------------------------------------------------------------------------
# _switch_to_start_branch
# ---------------------------------------------------------------------------


def test_switch_to_start_branch_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        seam._switch_to_start_branch(tmp_path, "   ")


def test_switch_to_start_branch_rejects_none_repo() -> None:
    with pytest.raises(ValueError, match="project root"):
        seam._switch_to_start_branch(None, "feat-x")


def test_switch_to_start_branch_noop_when_already_on_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam.subprocess, "run", lambda *a, **k: _Result(0))  # check-ref-format ok
    monkeypatch.setattr(seam, "get_current_branch", lambda _root: "feat-x")
    assert seam._switch_to_start_branch(tmp_path, "feat-x") == "feat-x"


def test_switch_to_start_branch_rejects_invalid_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Bad:
        returncode = 1
        stdout = ""
        stderr = "bad name"

    monkeypatch.setattr(seam.subprocess, "run", lambda *a, **k: _Bad())
    with pytest.raises(ValueError, match="Invalid --start-branch"):
        seam._switch_to_start_branch(tmp_path, "bad..name")


# ---------------------------------------------------------------------------
# _resolve_planning_branch
# ---------------------------------------------------------------------------


def test_resolve_planning_branch_override_wins(tmp_path: Path) -> None:
    assert seam._resolve_planning_branch(tmp_path, tmp_path, target_branch_override="release") == "release"


def test_resolve_planning_branch_blank_override_falls_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "load_mission_target_branch", lambda _fd: "main")
    assert seam._resolve_planning_branch(tmp_path, tmp_path, target_branch_override="   ") == "main"


def test_resolve_planning_branch_reads_meta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "load_mission_target_branch", lambda _fd: "prog/2056")
    assert seam._resolve_planning_branch(tmp_path, tmp_path) == "prog/2056"


# ---------------------------------------------------------------------------
# _resolve_feature_target_branch
# ---------------------------------------------------------------------------


def test_resolve_feature_target_branch_prefers_meta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # FR-008 / #2139: the meta.json read now delegates to the single
    # read_target_branch_from_meta authority (imported into this module),
    # not a local _read_feature_meta helper.
    monkeypatch.setattr(seam, "read_target_branch_from_meta", lambda _fd: "release")
    assert seam._resolve_feature_target_branch(tmp_path, tmp_path) == "release"


def test_resolve_feature_target_branch_falls_back_to_current(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "read_target_branch_from_meta", lambda _fd: None)
    monkeypatch.setattr(seam, "get_current_branch", lambda _root: "feat-y")
    assert seam._resolve_feature_target_branch(tmp_path, tmp_path) == "feat-y"


def test_resolve_feature_target_branch_defaults_to_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "read_target_branch_from_meta", lambda _fd: None)
    monkeypatch.setattr(seam, "get_current_branch", lambda _root: None)
    assert seam._resolve_feature_target_branch(tmp_path, tmp_path) == "main"


# ---------------------------------------------------------------------------
# _get_current_branch
# ---------------------------------------------------------------------------


def test_get_current_branch_returns_rev_parse_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Rev:
        returncode = 0
        stdout = "feat-z\n"
        stderr = ""

    monkeypatch.setattr(seam.subprocess, "run", lambda *a, **k: _Rev())
    assert seam._get_current_branch(tmp_path) == "feat-z"


def test_get_current_branch_falls_back_to_primary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam.subprocess, "run", lambda *a, **k: _Result(1))
    monkeypatch.setattr("specify_cli.core.git_ops.resolve_primary_branch", lambda _root: "main")
    assert seam._get_current_branch(tmp_path) == "main"


def test_branch_context_reports_invoking_linked_worktree_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """#2938/#3124: branch context belongs to the invoking checkout."""
    primary = tmp_path / "primary"
    primary.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=primary, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "seed",
        ],
        cwd=primary,
        check=True,
    )
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "op/invoking", str(linked)],
        cwd=primary,
        check=True,
    )
    monkeypatch.chdir(linked)
    monkeypatch.setattr(mission_mod, "locate_project_root", lambda: primary)
    monkeypatch.setattr(mission_mod, "is_git_repo", lambda _root: True)
    monkeypatch.setattr(
        mission_mod,
        "_resolve_primary_branch_for_recommendation",
        lambda _root, _current: "main",
    )

    result = CliRunner().invoke(mission_mod.app, ["branch-context", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output[result.output.find("{") : result.output.rfind("}") + 1])
    assert payload["repo_root"] == str(primary.resolve())
    assert payload["current_branch"] == "op/invoking"
    assert payload["target_branch"] == "op/invoking"
