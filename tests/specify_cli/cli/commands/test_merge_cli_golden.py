"""Golden CLI characterization harness for ``spec-kitty merge`` (mission #2057).

This is the **byte-identity proof** for the merge.py god-module decomposition.
It captures the public ``spec-kitty merge`` CLI surface against the PRE-refactor
module and re-asserts it after every seam move. The contract it freezes lives at
``kitty-specs/decompose-merge-god-module-01KVXHDK/contracts/cli-surface-contract.md``.

WP01 authors this FIRST (ATDD / C-005): it gates the entire WP chain. Every later
WP must keep this green. Any drift in help text, flags/defaults, the dry-run JSON
key set, or the headline error/exit-code paths is a behavior change and must fail.

The command is exercised through the **real registered command object**
(``merge_module.merge``), registered exactly as ``cli/commands/__init__.py:216``
does (``app.command()(merge_module.merge)``) — NOT a hand-rolled re-wrap of the
inner logic. This pins registration alongside the surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
import typer
from typer.testing import CliRunner

from specify_cli import __version__ as SPEC_KITTY_VERSION
from specify_cli.cli import commands as commands_module
from specify_cli.cli.commands import merge as merge_module
from specify_cli.post_merge.review_artifact_consistency import (
    REJECTED_REVIEW_ARTIFACT_CONFLICT,
)
from specify_cli.status.models import Lane, ReviewResult
from tests.reliability.fixtures import (
    WorkPackageSpec,
    append_status_event,
    create_mission_fixture,
    write_work_package,
)
from tests.reliability.fixtures.mission import MissionFixture

pytestmark = pytest.mark.fast


# --- Frozen contract data (cli-surface-contract.md) -------------------------

# The one-line help (docstring) must be byte-identical.
EXPECTED_ONE_LINE_HELP = "Merge a lane-based mission into its target branch."

# The EXACT set of every long option the parser exposes. This is the
# load-bearing flag-surface contract (#2057): byte-identity of the parser option
# set, derived from the live ``click.Command.params`` and compared with strict
# set-equality (no missing, no extra). The previous substring-on-help-text check
# silently accepted prefix-preserving renames such as ``--push`` -> ``--push-remote``
# (``"--push" in out`` stays True). Exact set-equality catches both renames and
# any new/dropped flag.
# NOTE: ``--feature`` was removed in mission feature-alias-removal-01KW0N87 (WP01).
EXPECTED_PARSER_LONG_FLAGS = frozenset(
    {
        "--strategy",
        "--delete-branch",
        "--keep-branch",
        "--remove-worktree",
        "--keep-worktree",
        "--push",
        "--target",
        "--dry-run",
        "--json",
        "--mission",
        "--resume",
        "--abort",
        "--context",
        "--keep-workspace",
        "--allow-sparse-checkout",
        "--yes",
        "--skip-review-artifact-check",
        "--note",
        # #2745 (WP05): the direct-on-target completion affordance — completes a
        # merge-ready mission that has no lane branch. ``--no-lanes`` is the alias.
        "--skip-lanes",
        "--no-lanes",
    }
)

# The exact visible/hidden partition of the parser's long options, keyed on each
# ``click.Option.hidden`` attribute (NOT on rendered help-text width). After WP01
# removed ``--feature``, there are no hidden flags — every option is visible.
EXPECTED_VISIBLE_LONG_FLAGS = EXPECTED_PARSER_LONG_FLAGS
EXPECTED_HIDDEN_LONG_FLAGS: frozenset[str] = frozenset()

# The exact key set of the clean ``--dry-run --json`` payload (contract §2).
EXPECTED_DRY_RUN_PAYLOAD_KEYS = frozenset(
    {
        "spec_kitty_version",
        "mission_slug",
        "target_branch",
        "strategy",
        "delete_branch",
        "remove_worktree",
        "push",
        "mission_branch",
        "lanes",
        "would_assign_mission_number",
        "retention",  # added for the #3131 merge-retention forecast (2026-09-02)
    }
)


def _build_merge_app() -> typer.Typer:
    """Register the real ``merge`` command object exactly as the host CLI does.

    Mirrors ``cli/commands/__init__.py`` ``app.command()(merge_module.merge)``
    (the registration call asserted by the surface contract). We register the
    canonical command object, not a re-wrap, so the registered command and its
    parsed options are pinned.
    """
    app = typer.Typer()
    app.command()(merge_module.merge)
    return app


def _live_parser_long_flags() -> frozenset[str]:
    """Enumerate the merge command's actual long option strings from the parser.

    Derives the set from the real ``click.Command.params`` (each ``Option`` exposes
    primary ``.opts`` and toggle ``.secondary_opts`` such as ``--keep-branch``),
    keeping only ``--long`` forms. ``add_completion=False`` keeps Typer from
    injecting ``--install-completion`` / ``--show-completion`` so the set is purely
    the merge surface. After WP01 ``--feature`` was removed entirely; all
    remaining options are visible.
    """
    app = typer.Typer(add_completion=False)
    app.command()(merge_module.merge)
    command = typer.main.get_command(app)
    if isinstance(command, click.Group):
        command = next(iter(command.commands.values()))
    flags: set[str] = set()
    for param in command.params:
        if isinstance(param, click.Option):
            for opt in (*param.opts, *param.secondary_opts):
                if opt.startswith("--"):
                    flags.add(opt)
    return frozenset(flags)


def _live_parser_visibility_partition() -> tuple[frozenset[str], frozenset[str]]:
    """Partition the merge command's long options by ``click.Option.hidden``.

    Returns ``(visible_long_flags, hidden_long_flags)`` derived from the live
    parser params (``add_completion=False`` so Typer injects no completion
    options). Visibility is read straight off each option's ``.hidden`` attribute,
    so the result is independent of terminal width / Rich help wrapping. This is
    the load-bearing source for the visible-vs-hidden contract: a flag flipping
    ``hidden`` moves it between the two sets and breaks the assertion.
    """
    app = typer.Typer(add_completion=False)
    app.command()(merge_module.merge)
    command = typer.main.get_command(app)
    if isinstance(command, click.Group):
        command = next(iter(command.commands.values()))
    visible: set[str] = set()
    hidden: set[str] = set()
    for param in command.params:
        if isinstance(param, click.Option):
            longs = [
                opt
                for opt in (*param.opts, *param.secondary_opts)
                if opt.startswith("--")
            ]
            (hidden if param.hidden else visible).update(longs)
    return frozenset(visible), frozenset(hidden)


# --- Registration -----------------------------------------------------------


def test_merge_is_registered_as_top_level_command() -> None:
    """``merge`` is registered once as a top-level command on the host app."""
    names: set[str | None] = set()
    for cmd in _registered_top_level_commands():
        callback = cmd.callback
        names.add(cmd.name or (callback.__name__ if callback is not None else None))
    assert "merge" in names


def _registered_top_level_commands() -> list[typer.models.CommandInfo]:
    import sys

    from specify_cli import app

    saved = sys.argv[:]
    sys.argv = ["spec-kitty", "--help"]
    try:
        commands_module.register_commands(app)
    finally:
        sys.argv = saved
    return list(app.registered_commands)


# --- Help / flag surface (T002) ---------------------------------------------


def test_help_pins_one_line_help_and_every_visible_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``merge --help`` prints the frozen one-liner and every visible flag.

    The help is rendered through Rich, which wraps long option names at the
    terminal width. We pin a wide terminal so every option name renders in full
    — the contract is the option *set*, not the wrapping behavior.
    """
    monkeypatch.setenv("COLUMNS", "200")
    runner = CliRunner()
    result = runner.invoke(_build_merge_app(), ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert EXPECTED_ONE_LINE_HELP in out

    # Load-bearing flag-surface assertion (#2057): exact bidirectional
    # set-equality against the live parser option set. This is the byte-identity
    # proof — it fails on a missing flag, an extra flag, OR a prefix-preserving
    # rename (e.g. ``--push`` -> ``--push-remote``) that the old
    # ``flag in out`` substring check on the Rich-wrapped help silently passed.
    live_flags = _live_parser_long_flags()
    assert live_flags == EXPECTED_PARSER_LONG_FLAGS, (
        "merge parser flag surface drifted\n"
        f"  unexpected (new/renamed): {sorted(live_flags - EXPECTED_PARSER_LONG_FLAGS)}\n"
        f"  missing (removed/renamed): {sorted(EXPECTED_PARSER_LONG_FLAGS - live_flags)}"
    )

    # Visible-vs-hidden contract, width-INDEPENDENTLY (#2057): partition the live
    # parser's long options by each ``click.Option.hidden`` attribute and pin both
    # halves against frozen sets. Reading ``.hidden`` off the params — NOT scanning
    # the Rich-rendered help text — makes this deterministic regardless of terminal
    # width AND gives it the teeth the total-set equality above lacks: it catches a
    # visible->hidden flip (an operator flag, e.g. ``--push``, silently gaining
    # ``hidden=True`` and vanishing from help) and a hidden->visible flip (the
    # legacy ``--feature`` alias leaking into help). The former substring scan
    # (``assert flag in out``) derived "visible" from a static tuple and never read
    # ``.hidden``, so a visible->hidden regression passed green.
    visible_long_flags, hidden_long_flags = _live_parser_visibility_partition()
    assert visible_long_flags == EXPECTED_VISIBLE_LONG_FLAGS, (
        "visible (non-hidden) parser flag surface drifted\n"
        f"  unexpectedly visible: {sorted(visible_long_flags - EXPECTED_VISIBLE_LONG_FLAGS)}\n"
        f"  no longer visible (hidden/removed): "
        f"{sorted(EXPECTED_VISIBLE_LONG_FLAGS - visible_long_flags)}"
    )
    assert hidden_long_flags == EXPECTED_HIDDEN_LONG_FLAGS, (
        "hidden parser flag surface drifted\n"
        f"  unexpectedly hidden: {sorted(hidden_long_flags - EXPECTED_HIDDEN_LONG_FLAGS)}\n"
        f"  no longer hidden (leaked into help): "
        f"{sorted(EXPECTED_HIDDEN_LONG_FLAGS - hidden_long_flags)}"
    )
    # The hidden legacy alias must NOT appear in visible help (short one-token
    # substring, width-independent).
    assert "--feature" not in out


def test_feature_alias_is_rejected_by_the_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--feature`` is fully removed; the parser rejects it with exit 2.

    After mission feature-alias-removal-01KW0N87 WP01, ``--feature`` is no
    longer a registered option on merge. Passing it must produce Typer's
    "No such option: --feature" error (exit 2), confirming hard removal.
    """
    runner = CliRunner()
    result = runner.invoke(_build_merge_app(), ["--dry-run", "--feature", "no-such-mission"])
    assert result.exit_code == 2
    assert "No such option" in result.output


# --- --json gate (T003) -----------------------------------------------------


def test_json_without_dry_run_errors_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``merge --json`` (no --dry-run) prints the exact gate error and exits 1.

    The ``--json``-without-``--dry-run`` gate runs AFTER ``_validate_target_branch``
    in the command body. On a PR-merge CI checkout the default ``main`` target
    does not exist locally, so the target-branch preflight would fire first and
    emit a different error. Stub it to a no-op so the test deterministically
    reaches the gate it is named for, regardless of whether ``main`` exists.

    ``--mission`` must name a RESOLVABLE mission: the #4631 fix (mission
    ``consistent-mission-handle-resolution-01KVXHDK``) makes an unresolvable
    handle fail early with the canonical ``Mission not found: <handle>`` (T004
    below pins that path), which would pre-empt this gate before it is ever
    reached. Use a real fixture mission so resolution succeeds and the flow
    reaches the ``--json``-without-``--dry-run`` check.
    """
    mission = create_mission_fixture(tmp_path)
    monkeypatch.chdir(mission.repo_root)
    _patch_dry_run_git_boundaries(monkeypatch, mission)
    runner = CliRunner()
    result = runner.invoke(
        _build_merge_app(), ["--json", "--mission", mission.mission_slug]
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload == {
        "spec_kitty_version": SPEC_KITTY_VERSION,
        "error": "--json is currently supported with --dry-run only.",
    }


# --- Headline error / exit-code paths (T004) --------------------------------


def test_resume_with_no_interrupted_merge_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``merge --resume`` with no state prints the no-op message and exits 1.

    ``--mission`` must name a RESOLVABLE mission: ``_dispatch_resume`` gates on
    the canonical ``Mission not found: <handle>`` BEFORE the no-interrupted-merge
    check (#4631), so an unresolvable handle would exit 1 on the not-found path
    instead of the resume-specific one this test pins. Use a real fixture
    mission (with no merge state written) so resolution succeeds and the flow
    reaches the no-interrupted-merge check.
    """
    mission = create_mission_fixture(tmp_path)
    monkeypatch.chdir(mission.repo_root)
    _patch_dry_run_git_boundaries(monkeypatch, mission)
    runner = CliRunner()
    result = runner.invoke(
        _build_merge_app(), ["--resume", "--mission", mission.mission_slug]
    )
    assert result.exit_code == 1
    assert "No interrupted merge to resume." in result.stdout


def test_unresolved_mission_slug_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the mission slug cannot be resolved at all, dry-run exits 1 with the canonical remediation.

    The unresolved path is reached when no ``--mission`` is given and the current
    branch is not a mission branch (slug resolution yields ``None``). We pin that
    resolution outcome and the resulting headline error/exit-code.
    """
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._enforce_git_preflight", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._resolve_mission_slug", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._resolve_target_branch",
        lambda *a, **kw: ("main", "cli"),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._validate_target_branch", lambda *a, **kw: None
    )
    runner = CliRunner()
    result = runner.invoke(_build_merge_app(), ["--dry-run"])
    assert result.exit_code == 1
    assert "Mission slug could not be resolved. Use --mission <slug>." in result.stdout


def test_unresolved_mission_slug_non_dry_run_exits_two(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-dry-run merge with no resolvable mission slug exits 2 (T006 / FR-003).

    The ``if not resolved_mission:`` terminal in the real-merge path (merge.py)
    must produce exit code 2 — the canonical "no selector" signal — not 1.
    This pin guards against regression of that specific branch.
    """
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._enforce_git_preflight", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._resolve_mission_slug", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._resolve_target_branch",
        lambda *a, **kw: ("main", "cli"),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._validate_target_branch", lambda *a, **kw: None
    )
    runner = CliRunner()
    result = runner.invoke(_build_merge_app(), [])
    assert result.exit_code == 2
    assert "Mission slug could not be resolved. Use --mission <slug>." in result.stdout


# --- Clean dry-run JSON payload key set (T004) ------------------------------


def _patch_dry_run_git_boundaries(monkeypatch: pytest.MonkeyPatch, mission: MissionFixture) -> None:
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._enforce_git_preflight", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge.find_repo_root", lambda: mission.repo_root
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge.get_main_repo_root",
        lambda _repo: mission.repo_root,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._validate_target_branch",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.merge._resolve_target_branch",
        lambda *a, **kw: ("main", "cli"),
    )


def _write_lanes_json(mission: MissionFixture) -> None:
    lanes_json = mission.mission_dir / "lanes.json"
    lanes_json.write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": mission.mission_slug,
                "mission_id": mission.mission_id,
                "mission_branch": f"kitty/mission-{mission.mission_slug}",
                "target_branch": "main",
                "lanes": [
                    {
                        "lane_id": "lane-a",
                        "wp_ids": ["WP01"],
                        "write_scope": [],
                        "predicted_surfaces": [],
                        "depends_on_lanes": [],
                        "parallel_group": 0,
                    }
                ],
                "computed_at": "2026-05-14T12:00:00+00:00",
                "computed_from": "dependency_graph+ownership",
                "planning_artifact_wps": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_retention_spec(mission: MissionFixture) -> None:
    (mission.mission_dir / "spec.md").write_text(
        "\n".join(
            [
                "# Mission",
                "",
                "## Constraints",
                "",
                "| ID | Title | Constraint | Category | Priority | Status |",
                "|----|-------|------------|----------|----------|--------|",
                (
                    "| C-005 | Retention | Keep branches and worktrees after merge "
                    "unless separately directed. | Operational | High | Accepted |"
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_clean_dry_run_json_payload_key_set_is_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``merge --dry-run --json`` on a clean mission carries exactly the contract keys."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KVXHDKGOLDEN0000000001",
    )
    _write_lanes_json(mission)
    monkeypatch.chdir(mission.repo_root)
    _patch_dry_run_git_boundaries(monkeypatch, mission)

    runner = CliRunner()
    result = runner.invoke(
        _build_merge_app(),
        ["--mission", mission.mission_slug, "--dry-run", "--json"],
    )
    assert result.exit_code == 0, (
        f"expected exit 0, got {result.exit_code}\nstdout={result.stdout}"
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert frozenset(payload) == EXPECTED_DRY_RUN_PAYLOAD_KEYS
    assert payload["spec_kitty_version"] == SPEC_KITTY_VERSION
    assert payload["mission_slug"] == mission.mission_slug
    assert payload["target_branch"] == "main"
    # Default strategy is SQUASH; default delete/remove are True; push False.
    assert payload["strategy"] == "squash"
    assert payload["delete_branch"] is True
    assert payload["remove_worktree"] is True
    assert payload["push"] is False


def test_retained_mission_requires_explicit_cleanup_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retained mission blocks default cleanup and honors explicit choices."""
    mission = create_mission_fixture(tmp_path)
    _write_retention_spec(mission)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KVXHDKRETENTION00000001",
    )
    _write_lanes_json(mission)
    monkeypatch.chdir(mission.repo_root)
    _patch_dry_run_git_boundaries(monkeypatch, mission)

    runner = CliRunner()
    default_result = runner.invoke(
        _build_merge_app(),
        ["--mission", mission.mission_slug, "--dry-run", "--json"],
    )
    assert default_result.exit_code == 1
    payload = json.loads(default_result.stdout.strip().splitlines()[-1])
    assert payload["blocked"] is True
    assert payload["diagnostic_code"] == "MISSION_RETENTION_CLEANUP_CONFLICT"

    explicit_result = runner.invoke(
        _build_merge_app(),
        [
            "--mission",
            mission.mission_slug,
            "--delete-branch",
            "--remove-worktree",
            "--dry-run",
            "--json",
        ],
    )
    assert explicit_result.exit_code == 0
    explicit_payload = json.loads(explicit_result.stdout.strip().splitlines()[-1])
    assert explicit_payload["delete_branch"] is True
    assert explicit_payload["remove_worktree"] is True

    keep_result = runner.invoke(
        _build_merge_app(),
        [
            "--mission",
            mission.mission_slug,
            "--keep-branch",
            "--keep-worktree",
            "--dry-run",
            "--json",
        ],
    )
    assert keep_result.exit_code == 0
    keep_payload = json.loads(keep_result.stdout.strip().splitlines()[-1])
    assert keep_payload["delete_branch"] is False
    assert keep_payload["remove_worktree"] is False


def test_real_merge_with_retention_never_reaches_default_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default cleanup is blocked before the real merge executor is entered."""
    mission = create_mission_fixture(tmp_path)
    _write_retention_spec(mission)
    monkeypatch.chdir(mission.repo_root)
    _patch_dry_run_git_boundaries(monkeypatch, mission)

    real_merge_calls: list[dict[str, object]] = []

    def fail_if_called(**kwargs: object) -> None:
        real_merge_calls.append(dict(kwargs))
        raise AssertionError("default cleanup reached the real merge executor")

    monkeypatch.setattr(merge_module, "_run_real_merge", fail_if_called)
    runner = CliRunner()
    result = runner.invoke(_build_merge_app(), ["--mission", mission.mission_slug])
    assert result.exit_code == 1
    assert "MISSION_RETENTION_CLEANUP_CONFLICT" in result.stdout
    assert real_merge_calls == []


# --- REJECTED_REVIEW_ARTIFACT_CONFLICT emission (T004) ----------------------


def _write_rejected_review_artifact(mission: MissionFixture) -> None:
    from specify_cli.review.artifacts import ReviewCycleArtifact

    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    artifact = ReviewCycleArtifact(
        cycle_number=1,
        wp_id="WP01",
        mission_slug=mission.mission_slug,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-05-14T12:00:00+00:00",
        body="# Review\n\nVerdict: rejected\n",
    )
    artifact.write(artifact_dir / "review-cycle-1.md")


def test_dry_run_json_emits_rejected_review_artifact_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rejected latest review-cycle on an approved WP blocks dry-run with the conflict code.

    WP06 repoint: ``find_rejected_review_artifact_conflicts`` is pure-event
    post-WP05 (verdict-seam-write-unification-01KZ9Q35, FR-013) -- it no
    longer reads ``review-cycle-N.md`` frontmatter at all. The on-disk
    artifact is written only as realistic surrounding state; the
    ``review_result`` event on the SAME transition is what the gate
    actually consults.
    """
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KVXHDKGOLDEN0000000002",
        review_result=ReviewResult(
            reviewer="reviewer-renata",
            verdict="changes_requested",
            reference=f"review-cycle://{mission.mission_slug}/WP01-regression-harness/review-cycle-1.md",
        ),
    )
    _write_rejected_review_artifact(mission)
    _write_lanes_json(mission)
    monkeypatch.chdir(mission.repo_root)
    _patch_dry_run_git_boundaries(monkeypatch, mission)

    runner = CliRunner()
    result = runner.invoke(
        _build_merge_app(),
        ["--mission", mission.mission_slug, "--dry-run", "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["blocked"] is True
    assert payload["diagnostic_code"] == REJECTED_REVIEW_ARTIFACT_CONFLICT
    assert payload["blockers"][0]["diagnostic_code"] == REJECTED_REVIEW_ARTIFACT_CONFLICT
