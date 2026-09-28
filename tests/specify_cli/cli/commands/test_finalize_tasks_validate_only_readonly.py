"""``finalize-tasks --validate-only`` is read-only (AC-C1, FR-002, #1861 Part 1).

Mission ``coordination-merge-stabilization-01KTXRVR`` / WP02 / T005.

Contract (``contracts/class-c-validate-only-readonly.md``):

GIVEN a repository where the mission target branch differs from the currently
checked-out branch, WHEN the operator runs ``finalize-tasks --validate-only``,
THEN ``git symbolic-ref HEAD`` is byte-identical before and after, AND
``git status --porcelain`` output is byte-identical before and after (no
staging, no checkout, no writes), AND validation results are identical to
those produced by the commit-phase run's validation step.

The fixture mirrors ``test_sc6_planning_placement_e2e.py`` (the canonical
finalize-tasks coordination-topology e2e harness): a real spec-kitty git repo
(``protected_target_repo``) with a coordination-topology mission whose
``meta.json`` target branch is ``main`` while HEAD is parked on a genuinely
different planning branch (the #1861 shape: an eager checkout-positioning
call would mutate HEAD onto the target here).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app

from tests.git.protected_target_fixtures import (  # noqa: F401 — pytest fixture re-export
    ProtectedTargetRepo,
    protected_target_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

# A 26-char mission id; mid8 is its first 8 chars (mirrors the SC6 harness).
_MISSION_ID = "01T005VALIDATEONLY00000001"
_MID8 = _MISSION_ID[:8]

# The branch the operator is parked on when running finalize. write-surface-
# coherence (FR-002 / D-3): planning artifacts land on the primary feature
# target_branch — a NON-protected branch the operator is ON. So the planning
# branch IS the mission ``target_branch`` here; the commit-phase lands on it
# directly, and ``--validate-only`` performs ZERO git mutations regardless.
_PLANNING_BRANCH = "feat/planning-work"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _git_bytes(repo: Path, *args: str) -> bytes:
    """Raw stdout bytes of a git command — for byte-identical AC-C1 captures."""
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True).stdout


def _parse_json_from_output(output: str) -> dict[str, object]:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return dict(json.loads(stripped))
    raise ValueError(f"No JSON object found in finalize-tasks output:\n{output}")


def _write_wp(tasks_dir: Path, wp_id: str) -> None:
    (tasks_dir / f"{wp_id}-task.md").write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"dependencies: []\n"
        f"requirement_refs: [FR-001]\n"
        f"subtasks: []\n"
        f"owned_files:\n"
        f"  - src/module_{wp_id.lower()}/**\n"
        f"authoritative_surface: src/module_{wp_id.lower()}/\n"
        f"execution_mode: code_change\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )


def _write_spec(feature_dir: Path) -> None:
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )


def _write_tasks_md(feature_dir: Path, wp_ids: list[str]) -> None:
    sections = "\n".join(f"## Work Package {wp}\n\n**Dependencies**: None\n" for wp in wp_ids)
    (feature_dir / "tasks.md").write_text(f"# Tasks\n\n{sections}\n", encoding="utf-8")


def _scaffold_coord_mission_on_divergent_branch(repo: Path, target_branch: str) -> str:
    """Coordination-topology mission whose ``meta.json`` target genuinely
    differs from HEAD (the #1861 shape).

    Mirrors the SC6 ``_scaffold_mission`` shape: artifacts committed on
    ``target_branch`` (the mission's recorded planning target -- the
    fixture's protected ``main``), a coordination branch minted off the seed
    commit, and HEAD then parked on a *different*, unrelated planning branch
    (``_PLANNING_BRANCH``). Resolution of the mission's target branch is
    metadata-only (``meta.json``'s ``target_branch`` field, read by
    ``_resolve_planning_branch``) -- it never reads the current checkout --
    so the mission stays fully resolvable with HEAD elsewhere. Returns the
    mission dirname.
    """
    mission_slug = "vo-mission"
    mission_dirname = f"{mission_slug}-{_MID8}"
    feature_dir = repo / "kitty-specs" / mission_dirname
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta: dict[str, object] = {
        "mission_slug": mission_dirname,
        "mission_id": _MISSION_ID,
        "mid8": _MID8,
        # The recorded target is the fixture's protected branch -- genuinely
        # different from the planning branch HEAD is parked on below, so
        # divergence is real, not incidental.
        "target_branch": target_branch,
        "coordination_branch": f"kitty/mission-{mission_slug}-{_MID8}",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")

    _write_wp(tasks_dir, "WP01")
    _write_spec(feature_dir)
    _write_tasks_md(feature_dir, ["WP01"])

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _git(repo, "branch", f"kitty/mission-{mission_slug}-{_MID8}")

    # HEAD moves to an unrelated planning branch, away from the recorded
    # target_branch -- ``--validate-only`` must mutate NOTHING regardless.
    _git(repo, "checkout", "-q", "-b", _PLANNING_BRANCH)

    return mission_dirname


def _run_finalize(repo: Path, mission_slug: str, *extra_args: str) -> Result:
    with (
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=repo,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_git_preflight",
            return_value=type("P", (), {"passed": True})(),
        ),
    ):
        return runner.invoke(
            app,
            ["finalize-tasks", "--mission", mission_slug, "--json", *extra_args],
            catch_exceptions=False,
        )


@pytest.fixture(autouse=True)
def _disable_saas_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_saas_fan_out", lambda *a, **k: None)


class TestValidateOnlyIsReadOnly:
    """AC-C1: --validate-only performs ZERO git mutations."""

    def test_head_and_porcelain_byte_identical_and_nothing_staged(
        self,
        protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    ) -> None:
        repo = protected_target_repo.repo_root
        protected_target_repo.assert_is_spec_kitty_project()
        target_branch = protected_target_repo.target_branch
        mission_slug = _scaffold_coord_mission_on_divergent_branch(repo, target_branch)

        head_before = _git_bytes(repo, "symbolic-ref", "HEAD")
        porcelain_before = _git_bytes(repo, "status", "--porcelain")
        assert head_before.decode().strip().endswith(_PLANNING_BRANCH), (
            "fixture precondition violated: HEAD must start on the planning "
            "branch so any mutation by --validate-only (which must be "
            "ZERO) is observable against this known starting state"
        )
        assert not head_before.decode().strip().endswith(f"/{target_branch}"), (
            "fixture precondition violated: HEAD must genuinely differ from "
            f"the mission's recorded target_branch ({target_branch!r}) -- "
            "otherwise this is not the #1861 divergent-branch shape at all"
        )

        result = _run_finalize(repo, mission_slug, "--validate-only")

        assert result.exit_code == 0, (
            "--validate-only must succeed even though HEAD "
            f"({_PLANNING_BRANCH!r}) differs from the mission's target_branch "
            f"({target_branch!r}) -- failed (exit {result.exit_code}):\n"
            f"{result.output}"
        )

        head_after = _git_bytes(repo, "symbolic-ref", "HEAD")
        porcelain_after = _git_bytes(repo, "status", "--porcelain")
        staged_after = _git_bytes(repo, "diff", "--cached", "--name-only")

        assert head_after == head_before, f"--validate-only CHECKED OUT a branch (read-only contract violated): HEAD {head_before!r} -> {head_after!r}"
        assert porcelain_after == porcelain_before, (
            f"--validate-only changed the working tree / index (read-only contract violated):\nbefore: {porcelain_before!r}\nafter:  {porcelain_after!r}"
        )
        assert staged_after == b"", f"--validate-only staged files: {staged_after!r}"

    def test_validation_findings_match_commit_phase_run(
        self,
        protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    ) -> None:
        """AC-C1 (4): validate-only findings == the commit-phase run's
        validation findings on the same fixture.

        Uses a non-protected ``target_branch`` (matching HEAD) so the real
        commit-phase run below can actually land -- unlike the read-only
        tests above, this one exercises the write path and is not itself
        asserting the divergent-branch read-only contract.
        """
        repo = protected_target_repo.repo_root
        mission_slug = _scaffold_coord_mission_on_divergent_branch(repo, _PLANNING_BRANCH)

        validate_result = _run_finalize(repo, mission_slug, "--validate-only")
        assert validate_result.exit_code == 0, validate_result.output
        validate_payload = _parse_json_from_output(validate_result.output)
        assert validate_payload.get("result") == "validation_passed", validate_payload

        commit_result = _run_finalize(repo, mission_slug)
        assert commit_result.exit_code == 0, commit_result.output
        commit_payload = _parse_json_from_output(commit_result.output)
        assert commit_payload.get("result") == "success", commit_payload

        # The validation findings shared by both payload shapes must agree.
        assert validate_payload["wp_count"] == commit_payload["wp_count"]
        assert validate_payload["updated_wp_count"] == commit_payload["updated_wp_count"]
        assert validate_payload["ownership_warnings"] == commit_payload["ownership_warnings"]

    def test_positive_control_probe_detects_a_real_head_mutation(
        self,
        protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    ) -> None:
        """Non-vacuity check: the byte-identical HEAD probe above is not a
        tautology -- it genuinely observes a checkout change when one occurs.

        Same fixture as ``test_head_and_porcelain_byte_identical_and_nothing_
        staged``, but instead of invoking ``--validate-only`` this performs a
        real ``git checkout <target_branch>`` directly. If the probe could
        never fail, the read-only assertions above would be worthless; this
        proves it can.
        """
        repo = protected_target_repo.repo_root
        target_branch = protected_target_repo.target_branch
        _scaffold_coord_mission_on_divergent_branch(repo, target_branch)

        head_before = _git_bytes(repo, "symbolic-ref", "HEAD")

        _git(repo, "checkout", "-q", target_branch)

        head_after = _git_bytes(repo, "symbolic-ref", "HEAD")

        assert head_after != head_before, (
            "positive control failed: checking out the target branch did not "
            "change the observed HEAD, so the byte-identical assertion above "
            "would never catch a real mutation"
        )
        assert head_after.decode().strip().endswith(f"/{target_branch}")
