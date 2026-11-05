"""``spec-kitty upgrade`` writes into a non-Mission worktree only when asked to (#7173).

FR-007: a plain ``upgrade`` writes and commits into **no** non-Mission
worktree under ``.worktrees/``. FR-008: ``--include-worktree PATH`` (repeatable)
and ``--all-worktrees`` opt worktrees in; an unknown path, or ``--no-worktrees``
combined with an opt-in flag, is refused with exit 2 before any write. FR-009:
the normal preview and the normal output name every worktree and its
disposition. FR-010: ``--plan-json`` carries the selection and the dispositions.

Mission and detached worktrees stay skipped whatever the selection (#5457).

The CLI tests drive the real ``spec-kitty upgrade`` on the older-version lanes
fixture: one Mission lane worktree plus two non-Mission worktrees on ``wip/``
branches. The unit tests pin :func:`worktree_dispositions` and
:func:`validate_named`; they import the module inside each test so that the CLI
tests fail on their assertions, not on a collection error, before the module
exists.
"""

from __future__ import annotations

import json
from typing import Any
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.integration.target_owned_fixtures import (
    METADATA_PATH,
    LanesProject,
    build_older_version_lanes_project,
    upgrade_commits_on,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

WIP_A = "wip/a"
WIP_B = "wip/b"
NOT_FOUND_CODE = "UPGRADE_WORKTREE_NOT_FOUND"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _head(cwd: Path) -> str:
    return _git(cwd, "rev-parse", "HEAD").strip()


def _metadata_bytes(checkout: Path) -> bytes | None:
    path = checkout / METADATA_PATH
    return path.read_bytes() if path.is_file() else None


def _state(checkout: Path) -> tuple[str, bytes | None, str]:
    return _head(checkout), _metadata_bytes(checkout), _git(checkout, "status", "--porcelain")


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout or "") + (result.stderr or "")


@dataclass
class _Fixture:
    project: LanesProject
    wip_a: Path
    wip_b: Path

    @property
    def lane(self) -> Path:
        return next(iter(self.project.lane_worktrees.values()))

    def rel(self, worktree: Path) -> str:
        return worktree.relative_to(self.project.repo).as_posix()

    def all_checkouts(self) -> list[Path]:
        return [self.project.repo, self.lane, self.wip_a, self.wip_b]


@pytest.fixture()
def fixture(tmp_path: Path) -> _Fixture:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=1)
    wip_a = project.extra_worktree(branch=WIP_A)
    wip_b = project.extra_worktree(branch=WIP_B)
    return _Fixture(project=project, wip_a=wip_a, wip_b=wip_b)


def _assert_untouched(fx: _Fixture, worktree: Path, branch: str, before: tuple[str, bytes | None, str]) -> None:
    assert _state(worktree) == before, worktree
    assert upgrade_commits_on(fx.project.repo, branch) == [], branch


def _assert_upgraded(fx: _Fixture, worktree: Path, branch: str, before: tuple[str, bytes | None, str]) -> None:
    assert _head(worktree) != before[0], worktree
    assert upgrade_commits_on(fx.project.repo, branch), branch
    assert _git(worktree, "status", "--porcelain") == "", worktree


def _not_selected_line(fx: _Fixture, worktree: Path, branch: str) -> str:
    rel = fx.rel(worktree)
    return f"{rel} ({branch}): skipped, not selected (use --include-worktree {rel} or --all-worktrees)"


# ---------------------------------------------------------------------------
# CLI behaviour
# ---------------------------------------------------------------------------


def test_default_upgrade_writes_no_non_mission_worktree(fixture: _Fixture) -> None:
    """FR-007 / SC-002: a plain ``upgrade --yes`` commits on no non-Mission branch,
    on the migrations path and on the no-migrations path (second run)."""
    fx = fixture
    before_a, before_b, before_lane = _state(fx.wip_a), _state(fx.wip_b), _state(fx.lane)
    root_head = _head(fx.project.repo)

    for _run in range(2):
        result = fx.project.run("upgrade", "--yes")
        assert result.returncode == 0, _output(result)
        _assert_untouched(fx, fx.wip_a, WIP_A, before_a)
        _assert_untouched(fx, fx.wip_b, WIP_B, before_b)
        assert _state(fx.lane) == before_lane
        # FR-009: the normal output names every worktree and its disposition.
        out = _output(result)
        assert "Worktrees:" in out, out
        assert _not_selected_line(fx, fx.wip_a, WIP_A) in out, out
        assert _not_selected_line(fx, fx.wip_b, WIP_B) in out, out
        assert f"{fx.rel(fx.lane)} ({_git(fx.lane, 'branch', '--show-current').strip()}): skipped, Mission worktree" in out, out

    # The repository root checkout is still upgraded and committed.
    assert _head(fx.project.repo) != root_head
    assert upgrade_commits_on(fx.project.repo, fx.project.target_branch)


def test_include_worktree_opts_in_only_the_named_worktree(fixture: _Fixture) -> None:
    fx = fixture
    before_a, before_b, before_lane = _state(fx.wip_a), _state(fx.wip_b), _state(fx.lane)

    result = fx.project.run("upgrade", "--yes", "--include-worktree", fx.rel(fx.wip_a))

    assert result.returncode == 0, _output(result)
    _assert_upgraded(fx, fx.wip_a, WIP_A, before_a)
    _assert_untouched(fx, fx.wip_b, WIP_B, before_b)
    assert _state(fx.lane) == before_lane
    out = _output(result)
    assert f"{fx.rel(fx.wip_a)} ({WIP_A}): upgraded and committed" in out, out
    assert _not_selected_line(fx, fx.wip_b, WIP_B) in out, out


def test_include_worktree_accepts_an_absolute_path_and_repeats(fixture: _Fixture) -> None:
    fx = fixture
    before_a, before_b = _state(fx.wip_a), _state(fx.wip_b)

    result = fx.project.run("upgrade", "--yes", "--include-worktree", str(fx.wip_a), "--include-worktree", fx.rel(fx.wip_b))

    assert result.returncode == 0, _output(result)
    _assert_upgraded(fx, fx.wip_a, WIP_A, before_a)
    _assert_upgraded(fx, fx.wip_b, WIP_B, before_b)


def test_all_worktrees_keeps_the_previous_behaviour(fixture: _Fixture) -> None:
    fx = fixture
    before_a, before_b, before_lane = _state(fx.wip_a), _state(fx.wip_b), _state(fx.lane)

    result = fx.project.run("upgrade", "--yes", "--all-worktrees")

    assert result.returncode == 0, _output(result)
    _assert_upgraded(fx, fx.wip_a, WIP_A, before_a)
    _assert_upgraded(fx, fx.wip_b, WIP_B, before_b)
    # A Mission worktree stays skipped even with --all-worktrees (#5457).
    assert _state(fx.lane) == before_lane


def test_dry_run_lists_every_worktree_and_writes_nothing(fixture: _Fixture) -> None:
    fx = fixture
    before = {checkout: _state(checkout) for checkout in fx.all_checkouts()}

    result = fx.project.run("upgrade", "--dry-run")

    assert result.returncode == 0, _output(result)
    assert {checkout: _state(checkout) for checkout in fx.all_checkouts()} == before
    out = _output(result)
    assert "Worktrees:" in out, out
    assert _not_selected_line(fx, fx.wip_a, WIP_A) in out, out
    assert _not_selected_line(fx, fx.wip_b, WIP_B) in out, out
    assert f"{fx.rel(fx.lane)} (" in out and "skipped, Mission worktree" in out, out


@pytest.mark.parametrize(
    "opt_in",
    [
        ("--include-worktree", ".worktrees/no-such-worktree"),
        ("--include-worktree", "README.md"),
        ("--include-worktree", ".worktrees/extra-1/.kittify"),
        ("--all-worktrees", "--include-worktree", ".worktrees/nope"),
    ],
    ids=["missing", "outside", "nested", "with-all-worktrees"],
)
def test_unknown_worktree_is_refused_before_any_write(fixture: _Fixture, opt_in: tuple[str, ...]) -> None:
    fx = fixture
    before = {checkout: _state(checkout) for checkout in fx.all_checkouts()}

    result = fx.project.run("upgrade", "--yes", *opt_in)

    assert result.returncode == 2, _output(result)
    assert NOT_FOUND_CODE in _output(result)
    assert {checkout: _state(checkout) for checkout in fx.all_checkouts()} == before


@pytest.mark.parametrize("opt_in", [("--all-worktrees",), ("--include-worktree", ".worktrees/extra-1")])
def test_no_worktrees_with_an_opt_in_flag_is_refused(fixture: _Fixture, opt_in: tuple[str, ...]) -> None:
    fx = fixture
    before = {checkout: _state(checkout) for checkout in fx.all_checkouts()}

    result = fx.project.run("upgrade", "--yes", "--no-worktrees", *opt_in)

    assert result.returncode == 2, _output(result)
    assert "--no-worktrees" in _output(result)
    assert {checkout: _state(checkout) for checkout in fx.all_checkouts()} == before


def test_no_worktrees_prints_one_skip_line(fixture: _Fixture) -> None:
    fx = fixture
    result = fx.project.run("upgrade", "--dry-run", "--no-worktrees")

    assert result.returncode == 0, _output(result)
    out = _output(result)
    assert "Worktrees: skipped (--no-worktrees)" in out, out
    assert "not selected" not in out, out


_CHECKOUT = Path(__file__).resolve().parents[2]


_FROZEN_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "mode",
        "intent",
        "target",
        "compatibility",
        "complete",
        "decision",
        "process_exit_code",
        "roots",
        "migrations",
        "effects",
        "dispositions",
        "diagnostics",
        "execution_artifacts",
        "commit_policy",
    }
)
_FROZEN_INTENT_KEYS = frozenset({"project_mode", "requested_target", "include_worktrees", "confirm"})


def _validate_full_plan(payload: dict[str, object]) -> None:
    """The plan validates against the UNMODIFIED frozen ``upgrade-plan`` schema (schema_version 1).

    The worktree report travels as ``info`` diagnostics: no key is added at the
    top level or under ``intent`` (#7173, FR-010).
    """
    import jsonschema
    from referencing import Registry, Resource

    schema = json.loads((_CHECKOUT / "kitty-specs/upgrade-preview-mission-health-01M1V6E1/contracts/upgrade-plan.schema.json").read_text())
    legacy = json.loads((_CHECKOUT / "kitty-specs/cli-upgrade-nag-lazy-project-migrations-01KQ6YDN/contracts/compat-planner.json").read_text())
    registry = Registry().with_resource(
        "https://spec-kitty.dev/contracts/cli-upgrade-nag-lazy-project-migrations/compat-planner.json",
        Resource.from_contents(legacy),
    )
    jsonschema.Draft202012Validator(schema, registry=registry).validate(payload)
    assert set(payload) <= _FROZEN_TOP_LEVEL_KEYS, set(payload) - _FROZEN_TOP_LEVEL_KEYS
    intent = payload["intent"]
    assert isinstance(intent, dict)
    assert set(intent) <= _FROZEN_INTENT_KEYS, set(intent) - _FROZEN_INTENT_KEYS


def _plan(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = result.stdout or ""
    payload = json.loads(stdout[stdout.index("{") :])
    assert isinstance(payload, dict)
    _validate_full_plan(payload)
    return payload


def _worktree_diagnostics(plan: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]]]:
    """``(selection message, {owner: diagnostic})`` of the plan's worktree ``info`` diagnostics."""
    worktree = [item for item in plan["diagnostics"] if item["code"].startswith("WORKTREE_")]
    assert all(item["severity"] == "info" for item in worktree), worktree
    selection = [item for item in worktree if item["code"] == "WORKTREE_SELECTION"]
    assert len(selection) == 1, worktree
    assert selection[0]["owner"] is None
    return selection[0]["message"], {item["owner"]: item for item in worktree if item["code"] != "WORKTREE_SELECTION"}


def test_plan_json_carries_selection_and_dispositions(fixture: _Fixture) -> None:
    fx = fixture
    before = {checkout: _state(checkout) for checkout in fx.all_checkouts()}

    default = _plan(fx.project.run("upgrade", "--plan-json"))
    selection, by_owner = _worktree_diagnostics(default)
    assert selection == "worktree selection: none"
    assert default["commit_policy"]["worktrees_enabled"] is False
    wip_a = by_owner[fx.rel(fx.wip_a)]
    assert wip_a["code"] == "WORKTREE_SKIPPED_NOT_SELECTED"
    assert wip_a["message"] == (f"{fx.rel(fx.wip_a)} ({WIP_A}): skipped, not selected (use --include-worktree {fx.rel(fx.wip_a)} or --all-worktrees)")
    assert by_owner[fx.rel(fx.wip_b)]["code"] == "WORKTREE_SKIPPED_NOT_SELECTED"
    assert by_owner[fx.rel(fx.lane)]["code"] == "WORKTREE_SKIPPED_MISSION"

    everything = _plan(fx.project.run("upgrade", "--plan-json", "--all-worktrees"))
    selection, by_owner = _worktree_diagnostics(everything)
    assert selection == "worktree selection: all"
    assert everything["commit_policy"]["worktrees_enabled"] is True
    assert by_owner[fx.rel(fx.wip_a)]["code"] == "WORKTREE_SELECTED"
    assert by_owner[fx.rel(fx.lane)]["code"] == "WORKTREE_SKIPPED_MISSION"

    named = _plan(fx.project.run("upgrade", "--plan-json", "--include-worktree", fx.rel(fx.wip_b)))
    selection, by_owner = _worktree_diagnostics(named)
    assert selection == f"worktree selection: named ({fx.rel(fx.wip_b)})"
    assert named["commit_policy"]["worktrees_enabled"] is True
    assert by_owner[fx.rel(fx.wip_b)]["code"] == "WORKTREE_SELECTED"
    assert by_owner[fx.rel(fx.wip_b)]["message"].endswith(": selected for upgrade")
    assert by_owner[fx.rel(fx.wip_a)]["code"] == "WORKTREE_SKIPPED_NOT_SELECTED"

    refused = fx.project.run("upgrade", "--plan-json", "--include-worktree", ".worktrees/nope")
    assert refused.returncode == 2
    assert any(item["code"] == NOT_FOUND_CODE for item in _plan(refused)["diagnostics"])

    assert {checkout: _state(checkout) for checkout in fx.all_checkouts()} == before


def test_plan_json_no_worktrees_reports_no_worktree(fixture: _Fixture) -> None:
    """``--no-worktrees`` excludes the worktree pass, so the plan carries no worktree diagnostic."""
    plan = _plan(fixture.project.run("upgrade", "--plan-json", "--no-worktrees"))
    assert [item for item in plan["diagnostics"] if item["code"].startswith("WORKTREE_")] == []
    assert plan["commit_policy"]["worktrees_enabled"] is False


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("--include-worktree", ".worktrees/nope"), "worktree selection: named (.worktrees/nope)"),
        (("--no-worktrees", "--all-worktrees"), "worktree selection: all"),
        (("--no-worktrees", "--include-worktree", ".worktrees/nope"), "worktree selection: named (.worktrees/nope)"),
    ],
)
def test_plan_json_refusal_carries_the_requested_selection(fixture: _Fixture, args: tuple[str, ...], expected: str) -> None:
    """A refused ``--plan-json`` names the selection the operator asked for, not ``none`` (FR-010)."""
    refused = fixture.project.run("upgrade", "--plan-json", *args)
    assert refused.returncode == 2, _output(refused)
    plan = _plan(refused)
    assert plan["diagnostics"][0]["severity"] == "error"
    selection, by_owner = _worktree_diagnostics(plan)
    assert selection == expected
    assert by_owner == {}


# ---------------------------------------------------------------------------
# Unit tests: the selection and disposition rules
# ---------------------------------------------------------------------------


def _git_worktree_project(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "worktree", "add", "-q", "-b", "wip/x", str(repo / ".worktrees" / "wip-x"))
    _git(repo, "worktree", "add", "-q", "-b", "wip/y", str(repo / ".worktrees" / "wip-y"))
    _git(repo, "worktree", "add", "-q", "-b", "kitty/mission-foo-01ABCDEF-lane-a", str(repo / ".worktrees" / "foo-lane-a"))
    _git(repo, "worktree", "add", "-q", "--detach", str(repo / ".worktrees" / "detached"))
    (repo / ".worktrees" / "stray-file").write_text("not a directory\n", encoding="utf-8")
    return repo


def test_worktree_dispositions_follow_the_selection(tmp_path: Path) -> None:
    from specify_cli.upgrade.worktree_selection import (
        DispositionAction,
        WorktreeSelection,
        worktree_dispositions,
    )

    repo = _git_worktree_project(tmp_path)
    worktrees_dir = repo / ".worktrees"

    none = worktree_dispositions(worktrees_dir, WorktreeSelection.none())
    assert [d.path.name for d in none] == ["detached", "foo-lane-a", "wip-x", "wip-y"]
    assert {d.path.name: d.action for d in none} == {
        "detached": DispositionAction.SKIP_MISSION,
        "foo-lane-a": DispositionAction.SKIP_MISSION,
        "wip-x": DispositionAction.SKIP_NOT_SELECTED,
        "wip-y": DispositionAction.SKIP_NOT_SELECTED,
    }
    assert {d.path.name: d.branch for d in none} == {
        "detached": None,
        "foo-lane-a": "kitty/mission-foo-01ABCDEF-lane-a",
        "wip-x": "wip/x",
        "wip-y": "wip/y",
    }

    every = worktree_dispositions(worktrees_dir, WorktreeSelection.all())
    assert {d.path.name: d.action for d in every}["wip-x"] is DispositionAction.UPGRADE
    assert {d.path.name: d.action for d in every}["foo-lane-a"] is DispositionAction.SKIP_MISSION

    named = worktree_dispositions(worktrees_dir, WorktreeSelection.named_paths([worktrees_dir / "wip-y"]))
    assert {d.path.name: d.action for d in named} == {
        "detached": DispositionAction.SKIP_MISSION,
        "foo-lane-a": DispositionAction.SKIP_MISSION,
        "wip-x": DispositionAction.SKIP_NOT_SELECTED,
        "wip-y": DispositionAction.UPGRADE,
    }
    # Naming a Mission worktree never opts it in (#5457).
    mission_named = worktree_dispositions(worktrees_dir, WorktreeSelection.named_paths([worktrees_dir / "foo-lane-a"]))
    assert {d.path.name: d.action for d in mission_named}["foo-lane-a"] is DispositionAction.SKIP_MISSION

    assert worktree_dispositions(repo / "absent", WorktreeSelection.all()) == []


def test_selection_json(tmp_path: Path) -> None:
    from specify_cli.upgrade.worktree_selection import WorktreeSelection

    assert WorktreeSelection.none().to_json() == {"mode": "none", "named": []}
    assert WorktreeSelection.all().to_json() == {"mode": "all", "named": []}
    named = WorktreeSelection.named_paths([tmp_path / "b", tmp_path / "a"])
    assert named.to_json() == {"mode": "named", "named": [str(tmp_path / "b"), str(tmp_path / "a")]}
    assert named.to_json(relative_to=tmp_path) == {"mode": "named", "named": ["b", "a"]}


def test_validate_named_accepts_relative_and_absolute_children(tmp_path: Path) -> None:
    from specify_cli.upgrade.worktree_selection import validate_named

    repo = _git_worktree_project(tmp_path)
    resolved = validate_named(repo, [Path(".worktrees/wip-x"), repo / ".worktrees" / "wip-y"])
    assert resolved == [(repo / ".worktrees" / "wip-x").resolve(), (repo / ".worktrees" / "wip-y").resolve()]
    assert validate_named(repo, []) == []


@pytest.mark.parametrize(
    "bad",
    [".worktrees/missing", "README.md", ".worktrees/wip-x/sub", ".worktrees", ".worktrees/stray-file", "../elsewhere"],
    ids=["missing", "outside", "nested", "the-root", "not-a-directory", "escapes"],
)
def test_validate_named_refuses_what_is_not_a_direct_child(tmp_path: Path, bad: str) -> None:
    from specify_cli.upgrade.worktree_selection import UnknownWorktreeError, validate_named

    repo = _git_worktree_project(tmp_path)
    (repo / ".worktrees" / "wip-x" / "sub").mkdir()
    (tmp_path / "elsewhere").mkdir()
    with pytest.raises(UnknownWorktreeError) as excinfo:
        validate_named(repo, [Path(bad)])
    assert excinfo.value.path == Path(bad)
    assert excinfo.value.code == NOT_FOUND_CODE
    assert bad in str(excinfo.value)


# ---------------------------------------------------------------------------
# Review cycle 2: the post-run block reports what the run did; a plain
# directory and a symlink that escapes .worktrees/ follow validate_named
# ---------------------------------------------------------------------------


def test_selected_plain_directory_reports_nothing_written(fixture: _Fixture) -> None:
    """A selected directory with nothing to upgrade is reported as such, never as committed."""
    fx = fixture
    plain = fx.project.repo / ".worktrees" / "plain"
    plain.mkdir()

    result = fx.project.run("upgrade", "--yes", "--include-worktree", ".worktrees/plain")

    assert result.returncode == 0, _output(result)
    assert list(plain.iterdir()) == []
    out = _output(result)
    assert ".worktrees/plain (not a git worktree): selected, nothing to upgrade (nothing written)" in out, out
    assert "(detached)" not in out, out
    assert ".worktrees/plain (not a git worktree): upgraded" not in out, out


def test_symlink_escaping_worktrees_is_never_selected(fixture: _Fixture, tmp_path: Path) -> None:
    """``--all-worktrees`` does not write through a symlink to elsewhere, and no failing hint is offered."""
    fx = fixture
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / ".kittify").mkdir(parents=True)
    (elsewhere / ".kittify" / "metadata.yaml").write_text("spec_kitty:\n  version: '0.0.1'\n", encoding="utf-8")
    before = (elsewhere / ".kittify" / "metadata.yaml").read_bytes()
    (fx.project.repo / ".worktrees" / "esc").symlink_to(elsewhere, target_is_directory=True)

    preview = fx.project.run("upgrade", "--dry-run", "--all-worktrees")
    assert preview.returncode == 0, _output(preview)
    assert ".worktrees/esc (not a git worktree): skipped, resolves outside .worktrees/ (cannot be selected)" in _output(preview)
    assert "--include-worktree .worktrees/esc" not in _output(preview)

    _, by_owner = _worktree_diagnostics(_plan(fx.project.run("upgrade", "--plan-json", "--all-worktrees")))
    escaping = [item for item in by_owner.values() if "esc" in str(item["owner"])]
    assert len(escaping) == 1, by_owner
    assert escaping[0]["code"] == "WORKTREE_SKIPPED_NOT_SELECTED"
    assert escaping[0]["message"].endswith("skipped, resolves outside .worktrees/ (cannot be selected)")

    result = fx.project.run("upgrade", "--yes", "--all-worktrees")
    assert result.returncode == 0, _output(result)
    assert sorted(p.name for p in elsewhere.rglob("*")) == [".kittify", "metadata.yaml"]
    assert (elsewhere / ".kittify" / "metadata.yaml").read_bytes() == before
    assert "skipped, resolves outside .worktrees/ (cannot be selected)" in _output(result)

    refused = fx.project.run("upgrade", "--yes", "--include-worktree", ".worktrees/esc")
    assert refused.returncode == 2
    assert NOT_FOUND_CODE in _output(refused)


def test_dry_run_preview_uses_the_future_tense(fixture: _Fixture) -> None:
    fx = fixture
    result = fx.project.run("upgrade", "--dry-run", "--include-worktree", fx.rel(fx.wip_a))
    assert result.returncode == 0, _output(result)
    assert f"{fx.rel(fx.wip_a)} ({WIP_A}): will be upgraded and committed" in _output(result)


def test_cli_rejects_worktree_opt_in(tmp_path: Path) -> None:
    """``--cli`` takes no project, so a worktree opt-in is refused rather than ignored."""
    from tests.upgrade.test_worktree_stamp_guard import _invoke_upgrade

    tmp_path.mkdir(exist_ok=True)
    for args in (["--cli", "--all-worktrees"], ["--cli", "--include-worktree", ".worktrees/x"]):
        result = _invoke_upgrade(args, cwd=tmp_path)
        assert result.exit_code == 2, result.output
        assert "--cli" in result.output


def test_conflict_refused_outside_a_project(tmp_path: Path) -> None:
    """``--no-worktrees`` with an opt-in is refused before the outside-a-project guidance path."""
    from tests.upgrade.test_worktree_stamp_guard import _invoke_upgrade

    result = _invoke_upgrade(["--no-worktrees", "--all-worktrees"], cwd=tmp_path)
    assert result.exit_code == 2, result.output
    assert "--no-worktrees" in result.output


# In-process runs with a stub migration: the "failed" and "no worktree migrations" outcomes.


def _stub_project(tmp_path: Path) -> tuple[Path, Path]:
    from tests.upgrade.test_worktree_stamp_guard import _add_worktree, _init_repo

    root = tmp_path / "repo"
    _init_repo(root)
    worktree = _add_worktree(root, "wip-f", "wip/f")
    return root, worktree


def _register_worktree_stub(*, runs_on_worktrees: bool, succeeds: bool) -> None:
    from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
    from specify_cli.upgrade.registry import MigrationRegistry
    from tests.upgrade.test_worktree_stamp_guard import _TARGET_VERSION

    MigrationRegistry.clear()

    class _Stub(BaseMigration):
        migration_id = "test_7173_worktree_outcome_stub"
        description = "#7173 worktree outcome stub"
        target_version = _TARGET_VERSION

        def detect(self, project_path: Path) -> bool:
            return True

        def can_apply(self, project_path: Path) -> tuple[bool, str]:
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
            if succeeds:
                return MigrationResult(success=True, changes_made=["stub applied"])
            return MigrationResult(success=False, errors=["stub failure for #7173"])

    _Stub.runs_on_worktrees = runs_on_worktrees
    MigrationRegistry.register(_Stub)


def test_failed_worktree_migration_is_reported_as_failed(tmp_path: Path) -> None:
    from specify_cli.upgrade.registry import MigrationRegistry
    from tests.upgrade.test_worktree_stamp_guard import _TARGET_VERSION, _invoke_upgrade

    root, worktree = _stub_project(tmp_path)
    head_before = _head(worktree)
    try:
        _register_worktree_stub(runs_on_worktrees=True, succeeds=False)
        result = _invoke_upgrade(["--target", _TARGET_VERSION, "--yes", "--include-worktree", ".worktrees/wip-f"], cwd=root)
    finally:
        MigrationRegistry.clear()

    assert result.exit_code == 1, result.output
    assert ".worktrees/wip-f (wip/f): selected, migrations failed here, nothing committed (see errors)" in result.output
    assert "upgraded and committed" not in result.output
    assert _head(worktree) == head_before


def test_no_worktree_migrations_reports_nothing_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Migrations are pending but none runs on worktrees: the selected worktree is
    untouched, and the pass reports it as nothing written (runner level: the CLI
    re-discovers the real migrations, several of which do run on worktrees).
    With no migration pending and the version moving, the worktree pass does not
    run: the preview and the post-run block still name the selected worktree as not written."""
    from specify_cli.upgrade.registry import MigrationRegistry
    from tests.upgrade.test_worktree_stamp_guard import _invoke_upgrade
    from specify_cli.cli.commands.upgrade import _run_line
    from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
    from specify_cli.upgrade.runner import MigrationRunner
    from specify_cli.upgrade.worktree_selection import WorktreeOutcome, WorktreeSelection
    from tests.upgrade.test_worktree_stamp_guard import _TARGET_VERSION

    root, worktree = _stub_project(tmp_path)
    before = _state(worktree)

    class _MainOnly(BaseMigration):
        migration_id = "test_7173_main_only_stub"
        description = "#7173 main-only stub"
        target_version = _TARGET_VERSION
        runs_on_worktrees = False

        def detect(self, project_path: Path) -> bool:
            raise AssertionError(f"a main-only migration must not be probed in a worktree: {project_path}")

        def can_apply(self, project_path: Path) -> tuple[bool, str]:
            raise AssertionError(project_path)

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
            raise AssertionError((project_path, dry_run))

    result = MigrationRunner(root)._upgrade_worktrees(_TARGET_VERSION, [_MainOnly()], dry_run=False, auto_commit=True, worktree_selection=WorktreeSelection.all())

    (run,) = result["worktree_results"]
    assert run.outcome is WorktreeOutcome.NOTHING_TO_UPGRADE
    assert _state(worktree) == before
    assert _run_line(run, root, auto_commit=True) == "  .worktrees/wip-f (wip/f): selected, nothing to upgrade (nothing written)"

    monkeypatch.setattr(MigrationRegistry, "get_applicable", classmethod(lambda cls, *a, **k: []))
    args = ["--target", _TARGET_VERSION, "--yes", "--include-worktree", ".worktrees/wip-f"]
    preview = _invoke_upgrade([*args, "--dry-run"], cwd=root)
    assert preview.exit_code == 0, preview.output
    assert ".worktrees/wip-f (wip/f): selected, nothing to upgrade (nothing will be written)" in preview.output
    assert "will be upgraded" not in preview.output
    real = _invoke_upgrade(args, cwd=root)
    assert real.exit_code == 0, real.output
    assert ".worktrees/wip-f (wip/f): selected, nothing to upgrade (nothing written)" in real.output
    assert _state(worktree) == before


def test_dispositions_mark_plain_directories_and_escaping_symlinks(tmp_path: Path) -> None:
    from specify_cli.upgrade.worktree_selection import DispositionAction, WorktreeSelection, validate_named, worktree_dispositions

    repo = _git_worktree_project(tmp_path)
    worktrees_dir = repo / ".worktrees"
    (worktrees_dir / "plain").mkdir()
    (tmp_path / "elsewhere").mkdir()
    (worktrees_dir / "esc").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    (worktrees_dir / "alias").symlink_to(worktrees_dir / "wip-x", target_is_directory=True)

    by_name = {d.path.name: d for d in worktree_dispositions(worktrees_dir, WorktreeSelection.all())}
    assert by_name["plain"].git_worktree is False and by_name["plain"].branch is None
    assert by_name["plain"].action is DispositionAction.UPGRADE
    assert by_name["wip-x"].git_worktree is True
    for name in ("esc", "alias"):
        assert by_name[name].selectable is False
        assert by_name[name].action is DispositionAction.SKIP_NOT_SELECTED
    # The same rule as validate_named: the plain directory is a valid target, the escape is not.
    assert validate_named(repo, [Path(".worktrees/plain")]) == [(worktrees_dir / "plain").resolve()]
    from specify_cli.upgrade.worktree_selection import UnknownWorktreeError

    with pytest.raises(UnknownWorktreeError):
        validate_named(repo, [Path(".worktrees/esc")])


def test_run_outcome_and_lines(tmp_path: Path) -> None:
    from specify_cli.cli.commands.upgrade import _preview_line, _run_line
    from specify_cli.upgrade.runner import _worktree_outcome
    from specify_cli.upgrade.worktree_selection import (
        DispositionAction,
        WorktreeDisposition,
        WorktreeOutcome,
        WorktreeRunResult,
    )

    assert _worktree_outcome(failed=True, wrote=True, committed=False) is WorktreeOutcome.FAILED
    assert _worktree_outcome(failed=False, wrote=True, committed=True) is WorktreeOutcome.UPGRADED_COMMITTED
    assert _worktree_outcome(failed=False, wrote=True, committed=False) is WorktreeOutcome.UPGRADED_NOT_COMMITTED
    assert _worktree_outcome(failed=False, wrote=False, committed=False) is WorktreeOutcome.NOTHING_TO_UPGRADE

    selected = WorktreeDisposition(path=tmp_path / ".worktrees" / "a", branch="wip/a", action=DispositionAction.UPGRADE)
    detached = WorktreeDisposition(path=tmp_path / ".worktrees" / "d", branch=None, action=DispositionAction.SKIP_MISSION)
    assert _preview_line(selected, tmp_path, auto_commit=False, pass_runs=True).endswith(".worktrees/a (wip/a): will be upgraded, not committed (auto-commit off)")
    assert _preview_line(detached, tmp_path, auto_commit=True, pass_runs=True).endswith(".worktrees/d (detached): skipped, Mission worktree")
    not_committed = WorktreeRunResult(disposition=selected, outcome=WorktreeOutcome.UPGRADED_NOT_COMMITTED)
    assert _run_line(not_committed, tmp_path, auto_commit=False).endswith("upgraded, not committed (auto-commit off)")
    assert _run_line(not_committed, tmp_path, auto_commit=True).endswith("upgraded, not committed (see warnings)")
    committed = WorktreeRunResult(disposition=selected, outcome=WorktreeOutcome.UPGRADED_COMMITTED)
    assert _run_line(committed, tmp_path, auto_commit=True).endswith(".worktrees/a (wip/a): upgraded and committed")
