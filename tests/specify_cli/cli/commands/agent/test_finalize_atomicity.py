"""FR-015/NFR-001: a failed ``finalize-tasks`` must leave no partial writes.

R-07 (`plan.md`, Staging Strategy) records that several writes -- WP
frontmatter, ``tasks.md``, the issue-matrix scaffold, and the canonical
``TasksStarted``/bootstrap status events -- land on disk BEFORE the finalize
commit itself is attempted. Without an explicit revert, a failure at (or
after) that commit step leaves those writes stranded, uncommitted, in the
working tree: a partial-write violation of the atomic-finalize contract.

This suite runs the REAL ``finalize-tasks`` CLI command (``CliRunner``
against the real ``mission`` Typer app, in a real git repository) with
exactly one internal seam replaced by a side effect that raises -- the git
commit boundary, ``commit_for_mission`` -- to simulate a failure that fires
after every prior write has already happened. It asserts the working tree,
HEAD and index are byte-identical to their pre-finalize state, using the
same porcelain-plus-content-hash oracle FR-015 requires (``git status
--porcelain --ignored`` is not sufficient on its own for a *rewritten*
already-tracked file whose byte length is unchanged, so every tracked file's
content is hashed too).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import finalize_status_surface
from specify_cli.cli.commands.agent.mission import app
from specify_cli.core.checkout_identity import CheckoutIdentity

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

runner = CliRunner()

MISSION_SLUG = "finalize-atomicity-01"
WORK_BRANCH = "kitty/mission-finalize-atomicity-01"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8")


@dataclass(frozen=True)
class RepoOracle:
    """FR-015's porcelain-plus-content-hash oracle (never mtimes)."""

    head: str
    porcelain: str
    file_hashes: dict[str, str]


def _take_oracle(repo: Path) -> RepoOracle:
    porcelain = _git(repo, "status", "--porcelain=v1", "--ignored", "--untracked-files=all").stdout
    file_hashes: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(repo):
        dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in filenames:
            path = Path(directory) / name
            relative = path.relative_to(repo).as_posix()
            file_hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251 -- file-integrity fingerprint, not a charter digest
    return RepoOracle(head=_git(repo, "rev-parse", "HEAD").stdout.strip(), porcelain=porcelain, file_hashes=file_hashes)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real, non-owned single-WP mission repo, HEAD on a real mission branch."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "atomicity-suite@example.com")
    _git(root, "config", "user.name", "Atomicity Suite")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("project: atomicity-suite\n", encoding="utf-8")

    feature_dir = root / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "slug": MISSION_SLUG,
                "mission_slug": MISSION_SLUG,
                "friendly_name": "Finalize atomicity",
                "mission_type": "software-dev",
                "target_branch": WORK_BRANCH,
                "created_at": "2026-09-01T00:00:00+00:00",
                "mission_id": "01FINALIZEATOMICITY000001",
                "mid8": "01FINALI",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-task.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "dependencies: []\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/module_wp01/**\n"
        "authoritative_surface: src/module_wp01/\n"
        "execution_mode: code_change\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "seed mission")
    _git(root, "checkout", "-q", "-b", WORK_BRANCH)
    return root


@pytest.fixture(autouse=True)
def _disable_saas_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.setattr(emit_module, "_saas_fan_out", lambda *a, **k: None)


def _run_finalize(repo_root: Path, mission_slug: str = MISSION_SLUG) -> tuple[int, str]:
    """Run the REAL ``finalize-tasks`` CLI command, isolating only ambient identity."""
    with (
        patch(
            "specify_cli.cli.commands.agent.mission_finalize.resolve_checkout_identity",
            side_effect=lambda _cwd, intent: CheckoutIdentity(
                invoking_root=repo_root,
                canonical_target=repo_root,
                is_owner=True,
                intent=intent,
            ),
        ),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=repo_root),
        patch(
            "specify_cli.cli.commands.agent.mission.run_git_preflight",
            return_value=type("P", (), {"passed": True})(),
        ),
    ):
        result = runner.invoke(
            app,
            ["finalize-tasks", "--mission", mission_slug, "--json"],
            catch_exceptions=False,
        )
    return result.exit_code, result.output


def test_control_finalize_succeeds_and_mutates_the_repo(repo: Path) -> None:
    """Same-fixture control: an unpatched finalize succeeds and DOES change the oracle."""
    before = _take_oracle(repo)
    exit_code, output = _run_finalize(repo)
    assert exit_code == 0, output
    after = _take_oracle(repo)
    assert after != before
    assert (repo / "kitty-specs" / MISSION_SLUG / "lanes.json").is_file()


def _write_overlap_mission_real_repo(root: Path, *, target_branch: str, spec_suffix: str = "") -> Path:
    """A real-git 4-WP mission with two genuine ownership-manifest overlaps.

    Modeled on ``test_finalize_lane_dependency_cycle``'s ``_write_cyclic_
    mission`` WP shape (WP01/WP04 share ``src/a.py``, WP02/WP03 share
    ``src/b.py``), but against a real git repository with a real,
    non-protected ``target_branch``: that module's fixture only ever runs
    through ``_common_patches`` (which mocks ``validate_ownership`` itself,
    among other seams), never a real, unpatched ``finalize-tasks``
    invocation, so it never actually exercises the real ownership-overlap
    gate the way this test does.
    """
    mission_dir = root / "kitty-specs" / MISSION_SLUG
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "a.py").write_bytes(b"# a\n")
    (root / "src" / "b.py").write_bytes(b"# b\n")
    (mission_dir / "spec.md").write_text(
        "---\ntitle: Cyclic finalize\n---\n\n## Requirements\n\n" + "\n".join(f"- FR-{i:03d}: Requirement {i}" for i in range(1, 5)) + "\n" + spec_suffix,
        encoding="utf-8",
    )
    dependencies = {"WP01": ["WP02"], "WP02": [], "WP03": ["WP04"], "WP04": []}
    sections = ["# Tasks"]
    for wp_id, deps in dependencies.items():
        text = "Depends on " + ", ".join(deps) + "." if deps else "No dependencies."
        sections.append(f"## {wp_id}\n\n{text}")
    (mission_dir / "tasks.md").write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_slug": MISSION_SLUG, "target_branch": target_branch}),
        encoding="utf-8",
    )
    owned_files = {"WP01": "src/a.py", "WP02": "src/b.py", "WP03": "src/b.py", "WP04": "src/a.py"}
    for index, (wp_id, deps) in enumerate(dependencies.items(), start=1):
        dependency_yaml = "dependencies:\n" + "".join(f"  - {dep}\n" for dep in deps) if deps else "dependencies: []\n"
        (tasks_dir / f"{wp_id}-test.md").write_text(
            "---\n"
            f'work_package_id: "{wp_id}"\n'
            f'title: "Test {wp_id}"\n'
            f"requirement_refs:\n  - FR-{index:03d}\n"
            'execution_mode: "code_change"\n'
            f"owned_files:\n  - {owned_files[wp_id]}\n"
            'authoritative_surface: "src/"\n'
            f"{dependency_yaml}"
            "---\n\n"
            f"# {wp_id}\n",
            encoding="utf-8",
        )
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "seed cyclic mission")
    return mission_dir


def _init_overlap_repo(tmp_path: Path, *, spec_suffix: str = "") -> Path:
    """A real git repo on ``WORK_BRANCH`` holding the 4-WP ownership-overlap mission."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "atomicity-suite@example.com")
    _git(root, "config", "user.name", "Atomicity Suite")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("project: atomicity-suite\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "seed repo")
    _git(root, "checkout", "-q", "-b", WORK_BRANCH)
    _write_overlap_mission_real_repo(root, target_branch=WORK_BRANCH, spec_suffix=spec_suffix)
    return root


def test_ownership_overlap_refusal_leaves_no_partial_writes(tmp_path: Path) -> None:
    """FR-015: the ownership-manifest-overlap refusal (R-07) leaves no partial writes.

    ``_validate_ownership_manifests`` runs AFTER the WP frontmatter flush and
    the ``tasks.md`` regeneration (see the call order in ``finalize_tasks``),
    so a real ownership overlap -- WP01 and WP04 both claiming ``src/a.py``,
    WP02 and WP03 both claiming ``src/b.py`` -- is a genuine post-write
    refusal, exercised here through the real, UNPATCHED ``finalize-tasks``
    command (``CliRunner`` against the real ``mission`` app) against a real
    git repository. Asserts the pre/post oracle (HEAD, porcelain, and every
    tracked/untracked/ignored file's content hash) is identical.
    """
    root = _init_overlap_repo(tmp_path)

    before = _take_oracle(root)
    exit_code, output = _run_finalize(root)

    assert exit_code != 0, output
    assert "Ownership validation failed" in output, output
    after = _take_oracle(root)
    assert after.head == before.head, "HEAD moved despite the ownership-overlap refusal"
    assert after.porcelain == before.porcelain, f"working tree left dirty:\n{after.porcelain!r}"
    assert after.file_hashes == before.file_hashes, "a file's content changed despite the ownership-overlap refusal"


def test_commit_failure_mid_finalize_leaves_no_partial_writes(repo: Path) -> None:
    """FR-015/NFR-001: a commit-step failure must not strand any prior write.

    Patches the ONE git-commit boundary, ``commit_for_mission``, to raise
    after every earlier finalize write (WP frontmatter, ``tasks.md``, the
    issue-matrix scaffold, the canonical bootstrap/``TasksStarted`` status
    events) has already landed on disk per R-07 -- the latest possible
    injection point, and the most realistic one (a real commit can fail on
    a full disk, a lock, or a git-hook rejection after everything else
    already succeeded).

    This single ``mission_slug`` fixture has no coordination surface (a
    flat, non-owned repository-root mission), so ``_scaffold_acceptance_
    matrix_if_lane_based``'s declared home resolves to ``planning_dir``
    itself: the acceptance-matrix write takes the bare, non-committing path
    (``scaffold_acceptance_matrix(..., repo_root=None)``) and rides the SAME
    ``commit_for_mission`` call this test patches, instead of landing
    through its own earlier, separate commit (the gap this test originally
    pinned as ``xfail`` before that fix). Patching the ONE remaining commit
    boundary therefore now covers the acceptance-matrix write too.
    """
    before = _take_oracle(repo)

    with patch(
        "specify_cli.coordination.commit_router.commit_for_mission",
        side_effect=RuntimeError("simulated commit failure (T070)"),
    ):
        exit_code, output = _run_finalize(repo)

    assert exit_code != 0, output
    after = _take_oracle(repo)
    assert after.head == before.head, "HEAD moved despite the commit failing"
    assert after.porcelain == before.porcelain, f"working tree left dirty:\n{after.porcelain!r}"
    assert after.file_hashes == before.file_hashes, "a file's content changed despite the commit failing"


def _add_foreign_vcs_field(repo: Path) -> None:
    """Leave an uncommitted ``vcs`` field in meta.json (``implement --no-auto-commit``'s shape, SK3466-REV-001)."""
    meta_path = repo / "kitty-specs" / MISSION_SLUG / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["vcs"] = "git"
    meta["vcs_locked_at"] = "2026-09-01T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")


def test_post_commit_failure_with_foreign_meta_field_keeps_the_landed_finalize_commit(repo: Path) -> None:
    """HIGH (review cycle 1): a failure AFTER the finalize commit must never unwind it.

    A foreign uncommitted ``vcs`` field makes ``_meta_json_delta_is_finalize_
    attributable`` exclude meta.json from the commit, so
    ``meta_commit_progress.committed`` (meta.json rode the commit) stays False
    even though the finalize commit DID land. The atomicity guards used to key
    off that flag and so wrongly reverted the durable commit's artifacts.
    """
    _add_foreign_vcs_field(repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    head_when_report_runs: list[str] = []

    def _fail_after_commit(*_args: object, **_kwargs: object) -> None:
        head_when_report_runs.append(_git(repo, "rev-parse", "HEAD").stdout.strip())
        raise RuntimeError("simulated post-commit failure")

    with patch("specify_cli.cli.commands.agent.mission_finalize._emit_success_report", side_effect=_fail_after_commit):
        exit_code, output = _run_finalize(repo)

    assert exit_code != 0, output
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_when_report_runs and head_when_report_runs[0] != head_before, "the finalize commit had not landed when the report ran"
    assert head_after == head_when_report_runs[0], "HEAD moved after the finalize commit landed"
    lanes = repo / "kitty-specs" / MISSION_SLUG / "lanes.json"
    assert lanes.is_file(), "the guard deleted an artifact of the already-durable finalize commit"
    porcelain = _git(repo, "status", "--porcelain", "--", f"kitty-specs/{MISSION_SLUG}").stdout
    # Only the foreign meta.json edit may remain dirty; every finalize artifact is committed.
    assert porcelain.splitlines() == [f" M kitty-specs/{MISSION_SLUG}/meta.json"], porcelain


def test_issue_matrix_scaffold_refusal_leaves_no_stray_commit_or_dirty_tree(tmp_path: Path) -> None:
    """HIGH (review cycle 1): the issue-matrix scaffold must not commit before the gates.

    ``spec.md`` cites ``#4242`` so ``_scaffold_issue_matrix_if_present``
    authors ``issue-matrix.json``. It used to commit that file on its own
    BEFORE the ownership gate refused, stranding a commit and (once the byte
    guard deleted the committed file) a dirty tree. Like the acceptance
    matrix, it must ride the single final commit.
    """
    root = _init_overlap_repo(tmp_path, spec_suffix="\nTracks #4242.\n")
    before = _take_oracle(root)

    exit_code, output = _run_finalize(root)

    assert exit_code != 0, output
    assert "Ownership validation failed" in output, output
    after = _take_oracle(root)
    assert after.head == before.head, "the issue-matrix scaffold left a stray commit"
    assert after.porcelain == before.porcelain, f"working tree left dirty:\n{after.porcelain!r}"
    assert after.file_hashes == before.file_hashes


def test_issue_matrix_scaffold_rides_the_single_final_commit_on_success(repo: Path) -> None:
    """Control for the fold: a successful finalize commits issue-matrix.json exactly once, in the final commit."""
    spec = repo / "kitty-specs" / MISSION_SLUG / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\nTracks #4242.\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "cite an issue")
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    exit_code, output = _run_finalize(repo)

    assert exit_code == 0, output
    rel = f"kitty-specs/{MISSION_SLUG}/issue-matrix.json"
    assert (repo / rel).is_file()
    touching = _git(repo, "log", "--format=%H", f"{head_before}..HEAD", "--", rel).stdout.split()
    assert len(touching) == 1, f"issue-matrix.json committed {len(touching)} times"
    assert touching[0] == _git(repo, "log", "-1", "--format=%H", f"{head_before}..HEAD", "--", f"kitty-specs/{MISSION_SLUG}/lanes.json").stdout.strip()
    assert _git(repo, "status", "--porcelain", "--", f"kitty-specs/{MISSION_SLUG}").stdout.strip() == ""


def _install_lane_cycle_wps(mission_dir: Path) -> None:
    """Replace the mission's WPs with the 4-WP acyclic-WP / cyclic-LANE shape (T070 step 1).

    Rule 1 (``lanes/compute.py::find_overlap_pairs``) unions WPs whose
    ``owned_files`` overlap with NO ``scope: codebase-wide`` exemption, while
    ownership VALIDATION exempts a codebase-wide WP from every pair. So WP03
    and WP04 (codebase-wide) sharing WP02's / WP01's file collapse {WP01,WP04}
    and {WP02,WP03} into two lanes without tripping ownership validation, and
    WP01->WP02 plus WP03->WP04 close a 2-lane cycle -- a genuine, UNPATCHED
    post-write ``LANE_DEPENDENCY_CYCLE`` refusal.
    """
    for stale in (mission_dir / "tasks").glob("WP*.md"):
        stale.unlink()
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nDepends on WP02.\n\n## WP02\n\nNo dependencies.\n\n## WP03\n\nDepends on WP04.\n\n## WP04\n\nNo dependencies.\n",
        encoding="utf-8",
    )
    wp_specs = {
        "WP01": ("src/one.py", ["WP02"], False),
        "WP02": ("src/two.py", [], False),
        "WP03": ("src/two.py", ["WP04"], True),
        "WP04": ("src/one.py", [], True),
    }
    for wp_id, (owned_file, deps, codebase_wide) in wp_specs.items():
        dep_yaml = "dependencies:\n" + "".join(f"  - {d}\n" for d in deps) if deps else "dependencies: []\n"
        scope_yaml = "scope: codebase-wide\n" if codebase_wide else ""
        (mission_dir / "tasks" / f"{wp_id}-cycle.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Cycle fixture\n{dep_yaml}"
            f"requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [{owned_file}]\n"
            f"authoritative_surface: {owned_file}\nexecution_mode: code_change\n{scope_yaml}"
            f"create_intent:\n  - {owned_file}\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )


def _assert_oracle_unchanged(before: RepoOracle, after: RepoOracle, why: str) -> None:
    assert after.head == before.head, f"HEAD moved despite {why}"
    assert after.porcelain == before.porcelain, f"working tree left dirty after {why}:\n{after.porcelain!r}"
    assert after.file_hashes == before.file_hashes, f"a file's content changed despite {why}"


def test_lane_cycle_refusal_leaves_no_partial_writes(repo: Path) -> None:
    """T070 step 1 (primary row), non-owned: a real post-write lane-cycle refusal leaves nothing behind."""
    _install_lane_cycle_wps(repo / "kitty-specs" / MISSION_SLUG)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture: cyclic collapsed lanes")
    before = _take_oracle(repo)

    exit_code, output = _run_finalize(repo)

    assert exit_code != 0, output
    assert "LANE_DEPENDENCY_CYCLE" in output, output
    assert "Ownership validation failed" not in output, "fixture leaked an ownership overlap instead of exercising the lane-cycle gate"
    _assert_oracle_unchanged(before, _take_oracle(repo), "the lane-cycle refusal")


def test_lane_glob_revalidation_refusal_leaves_no_partial_writes(repo: Path) -> None:
    """T070 row: the lane-compute glob RE-validation (``LaneGlobValidationError``) refuses after the writes.

    The earlier ownership-stage glob check (``mission_finalize`` calls
    ``validate_glob_matches`` once) already passed; only the SECOND call, inside
    ``compute_and_write_lanes``, is made to fail. That binding lives in
    ``lanes.compute_and_persist`` (a distinct name from the finalize module's),
    so this patches exactly the one seam the re-validation branch needs -- a
    literal-path zero-match cannot survive the earlier check to reach it.
    """
    from specify_cli.ownership.validation import GlobValidationResult

    before = _take_oracle(repo)

    with patch(
        "specify_cli.lanes.compute_and_persist.validate_glob_matches",
        return_value=GlobValidationResult(errors=["src/gone.py matches zero files (simulated)"]),
    ):
        exit_code, output = _run_finalize(repo)

    assert exit_code != 0, output
    assert "ownership_literal_path_errors" in output, output
    _assert_oracle_unchanged(before, _take_oracle(repo), "the lane-glob re-validation refusal")


def _mission_dir_hashes(mission_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(mission_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251 -- file-integrity fingerprint, not a charter digest
        for path in sorted(mission_dir.rglob("*"))
        if path.is_file()
    }


def test_coord_topology_lane_cycle_refusal_leaves_every_branch_and_checkout_as_found(tmp_path: Path) -> None:
    """A non-owned ``coord`` Mission's real lane-cycle refusal is a whole-checkout no-op (#5641).

    The refusal fires after the bootstrap committed the per-WP seeds to the
    coordination branch (``typer.Exit`` path, like the commit-failure guard
    below). The Mission directory, the
    coordination branch and every checkout's tracked state must be as found.
    """
    from mission_runtime import MissionTopology
    from tests.integration.test_placement_partition_golden_path import _create_mission, _init_git_repo

    root = tmp_path / "coord-repo"
    root.mkdir()
    _init_git_repo(root)
    result = _create_mission(root, "coord-lane-cycle-5343", MissionTopology.COORD)
    mission_dir = result.feature_dir
    (mission_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n| ID | Requirement | Acceptance Criteria | Status |\n| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    (mission_dir / "tasks").mkdir(exist_ok=True)
    _install_lane_cycle_wps(mission_dir)
    _git(root, "add", "kitty-specs")
    _git(root, "commit", "-q", "-m", "fixture: coord mission with cyclic collapsed lanes")
    before = _mission_dir_hashes(mission_dir)
    surface_before = _branches_and_checkouts(root)

    exit_code, output = _run_finalize(root, result.mission_slug)

    assert exit_code != 0, output
    assert "LANE_DEPENDENCY_CYCLE" in output, output
    assert _mission_dir_hashes(mission_dir) == before, "the mission directory was not restored"
    assert _branches_and_checkouts(root) == surface_before, "the refusal left coordination commits or a dirty checkout behind"


def _branches_and_checkouts(root: Path) -> dict[str, str]:
    """Every local branch tip, plus every checkout's tracked-file status against its own HEAD."""
    state = {"refs/heads": _git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads").stdout}
    for line in _git(root, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            checkout = Path(line.removeprefix("worktree "))
            state[f"status {checkout.relative_to(root).as_posix()}"] = _git(checkout, "status", "--porcelain=v1", "--untracked-files=no").stdout
    return state


def _two_wp_mission(tmp_path: Path, topology_name: str) -> tuple[Path, str]:
    """A real two-WP Mission of ``topology_name``, created on a non-protected topic branch and ready to finalize."""
    from mission_runtime import MissionTopology
    from tests.integration.test_placement_partition_golden_path import _create_mission, _init_git_repo

    root = tmp_path / "repo"
    root.mkdir()
    _init_git_repo(root)
    _git(root, "checkout", "-q", "-b", WORK_BRANCH)
    result = _create_mission(root, f"final-commit-fail-{topology_name.lower().replace('_', '-')}", MissionTopology[topology_name])
    mission_dir = result.feature_dir
    (mission_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n| ID | Requirement | Acceptance Criteria | Status |\n| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    (mission_dir / "tasks").mkdir(exist_ok=True)
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nNo dependencies.\n", encoding="utf-8")
    for wp_id, owned_file in (("WP01", "src/one.py"), ("WP02", "src/two.py")):
        (mission_dir / "tasks" / f"{wp_id}-work.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Work {wp_id}\ndependencies: []\nrequirement_refs: [FR-001]\nsubtasks: []\n"
            f"owned_files: [{owned_file}]\nauthoritative_surface: {owned_file}\nexecution_mode: code_change\n"
            f"create_intent:\n  - {owned_file}\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )
    _git(root, "add", "kitty-specs")
    _git(root, "commit", "-q", "-m", "fixture: two-WP mission ready to finalize")
    return root, result.mission_slug


def _run_finalize_failing_the_final_commit(
    root: Path,
    mission_slug: str,
    *,
    before_failing: Callable[[], None] = lambda: None,
    during_status_writes: Callable[[], None] = lambda: None,
) -> tuple[int, str]:
    """Run the real ``finalize-tasks``, failing ONLY its final ``TASKS_INDEX`` commit.

    The per-WP status commits go through the transactional status emitter, not
    ``commit_for_mission``, so every earlier write and commit runs for real.
    ``during_status_writes`` runs after the seeds and before the status-write
    window closes (at the lane computation); ``before_failing`` runs after it,
    just before the final commit fails.
    """
    from mission_runtime import MissionArtifactKind
    from specify_cli.cli.commands.agent import mission_finalize
    from specify_cli.coordination import commit_router

    real_commit_for_mission = commit_router.commit_for_mission
    real_compute_and_write_lanes = mission_finalize._compute_and_write_lanes

    def _fail_only_the_final_commit(*args: object, **kwargs: object) -> object:
        if kwargs.get("kind") is MissionArtifactKind.TASKS_INDEX:
            before_failing()
            raise RuntimeError("simulated final commit failure")
        return real_commit_for_mission(*args, **kwargs)

    def _lanes_after_a_foreign_hook(*args: object, **kwargs: object) -> object:
        during_status_writes()
        return real_compute_and_write_lanes(*args, **kwargs)

    with (
        patch("specify_cli.coordination.commit_router.commit_for_mission", side_effect=_fail_only_the_final_commit),
        patch("specify_cli.cli.commands.agent.mission_finalize._compute_and_write_lanes", side_effect=_lanes_after_a_foreign_hook),
    ):
        exit_code, output = _run_finalize(root, mission_slug)
    assert "simulated final commit failure" in output, f"the run did not fail at the final commit:\n{output}"
    return exit_code, output


@pytest.mark.regression
@pytest.mark.parametrize("topology_name", ["COORD", "LANES_WITH_COORD", "LANES", "SINGLE_BRANCH"])
def test_final_commit_failure_leaves_every_branch_and_checkout_as_found(tmp_path: Path, topology_name: str) -> None:
    """A failed final commit leaves no per-WP status commits behind (guard for #5641, fixed).

    ``_run_commit_pipeline`` seeds every WP as ``planned`` BEFORE the final
    commit, and each seed is a commit of its own on the status surface -- the
    coordination branch for ``coord`` / ``lanes_with_coord``, the current
    branch for a non-owned ``lanes`` / ``single_branch`` Mission. Before the
    fix only an OWNED checkout got its HEAD back, so the status surface kept
    the seed commits and a ``lanes`` / ``single_branch`` checkout was left
    dirty against its own HEAD. Every branch tip and every checkout's tracked
    state must be what it was before the run.
    """
    root, mission_slug = _two_wp_mission(tmp_path, topology_name)
    before = _branches_and_checkouts(root)

    exit_code, output = _run_finalize_failing_the_final_commit(root, mission_slug)

    assert exit_code != 0, output
    assert _branches_and_checkouts(root) == before, "the failed finalize-tasks run left commits or a dirty checkout behind"


def _status_surface_checkout(root: Path) -> Path:
    """The checkout the status commits land in: the repository root, or the coordination worktree when there is one."""
    checkouts = [Path(line.removeprefix("worktree ")) for line in _git(root, "worktree", "list", "--porcelain").stdout.splitlines() if line.startswith("worktree ")]
    return next((checkout for checkout in checkouts if checkout != root), root)


def _status_writer_would_wait(root: Path, mission_slug: str) -> bool:
    """Whether another thread's status write for the Mission must wait for the lock (it times out within 0.2s)."""
    from specify_cli.status.locking import FeatureStatusLockTimeoutError, feature_status_lock

    waited: list[bool] = []

    def _write_status() -> None:
        try:
            with feature_status_lock(root, mission_slug, timeout=0.2):
                waited.append(False)
        except FeatureStatusLockTimeoutError:
            waited.append(True)

    writer = threading.Thread(target=_write_status)
    writer.start()
    writer.join()
    return waited == [True]


@pytest.mark.parametrize(
    ("topology_name", "foreign_commit_lands", "kept_files_listable"),
    [
        ("LANES", "after_status_writes", True),
        ("LANES", "during_status_writes", True),
        ("COORD", "during_status_writes", True),
        ("LANES", "after_status_writes", False),
    ],
)
def test_final_commit_failure_never_rewrites_a_foreign_commit_and_names_the_seeds_it_left(
    tmp_path: Path, topology_name: str, foreign_commit_lands: str, kept_files_listable: bool
) -> None:
    """A status-surface branch that gained a commit this run did not make is never forced back (#5641, FR-002/FR-003).

    A foreign commit lands on the status surface's branch -- the current branch
    of a ``lanes`` Mission, the coordination branch of a ``coord`` one -- either
    after the per-WP seed commits (the branch moved after the run's last status
    write) or between them and the failing final commit (inside the status-write
    window, where the run's own commits and the foreign one share the range the
    restore would rewrite). The restore must leave the branch where it is,
    keep the foreign commit and its file (here inside the Mission directory, which
    the byte restore otherwise rewrites), leave every checkout's tracked files
    consistent with their own HEAD, and report every commit it could not undo as
    a ``status_commits_not_undone`` warning.
    """
    root, mission_slug = _two_wp_mission(tmp_path, topology_name)
    surface = _status_surface_checkout(root)
    seeded_from = _git(surface, "rev-parse", "HEAD").stdout.strip()
    foreign_file = surface / "kitty-specs" / mission_slug / "foreign-note.txt"
    foreign_sha: list[str] = []

    def _foreign_commit() -> None:
        if foreign_commit_lands == "during_status_writes":
            # Another process's status write for this Mission (a `move-task`, say) must wait out the
            # window: a commit touching only the Mission's own status files is otherwise
            # indistinguishable from the run's seeds, and the restore would move the branch over it.
            assert _status_writer_would_wait(root, mission_slug), "the Mission status lock is not held across the status-write window"
        foreign_file.write_text("someone else's work\n", encoding="utf-8")
        _git(surface, "add", str(foreign_file.relative_to(surface)))
        _git(surface, "commit", "-q", "-m", "foreign: someone else's commit")
        foreign_sha.append(_git(surface, "rev-parse", "HEAD").stdout.strip())

    hooks = {"after_status_writes": "before_failing", "during_status_writes": "during_status_writes"}
    real_git = finalize_status_surface._git

    def _git_that_cannot_list_a_diff(cwd: Path, *args: str) -> str | None:
        return None if args[0] == "diff" else real_git(cwd, *args)

    with patch.object(finalize_status_surface, "_git", side_effect=real_git if kept_files_listable else _git_that_cannot_list_a_diff):
        exit_code, output = _run_finalize_failing_the_final_commit(root, mission_slug, **{hooks[foreign_commit_lands]: _foreign_commit})

    assert exit_code != 0, output
    assert foreign_sha, "fixture: the foreign commit never landed"
    _git(surface, "merge-base", "--is-ancestor", foreign_sha[0], "HEAD")  # raises when the foreign commit became unreachable
    assert _git(surface, "rev-parse", "HEAD").stdout.strip() != seeded_from, "the branch was moved back over the foreign commit"
    dirty = {name: status for name, status in _branches_and_checkouts(root).items() if name.startswith("status ") and status}
    if not kept_files_listable:
        # Fail closed: nothing under the Mission directory is rewritten, so the run's own uncommitted
        # edits to the WP files stay too -- but never a file a kept commit changed.
        dirty = {name: "".join(f"{line}\n" for line in status.splitlines() if "/tasks/WP" not in line) for name, status in dirty.items()}
        dirty = {name: status for name, status in dirty.items() if status}
    assert not dirty, f"a checkout was left modified against its own HEAD: {dirty}"
    assert foreign_file.read_text(encoding="utf-8") == "someone else's work\n", "the foreign commit's file was removed from disk"
    warnings = [json.loads(line) for line in output.splitlines() if line.startswith("{") and '"warning"' in line]
    leftover = next(w for w in warnings if w["warning"] == "status_commits_not_undone")
    undone_range = f"{seeded_from}..HEAD~1" if foreign_commit_lands == "after_status_writes" else f"{seeded_from}..HEAD"
    named = _git(surface, "rev-list", undone_range).stdout.split()
    assert [entry.split()[0] for entry in leftover["commits"]] == [_git(surface, "rev-parse", "--short", sha).stdout.strip() for sha in named]
    assert len(named) >= 2, "fixture: expected at least one seed commit per WP"
    if foreign_commit_lands == "during_status_writes":
        assert _git(surface, "rev-parse", "--short", foreign_sha[0]).stdout.strip() in [entry.split()[0] for entry in leftover["commits"]]
        assert "did not make" in leftover["detail"]
    if not kept_files_listable:
        assert "left as they are" in leftover["detail"]
