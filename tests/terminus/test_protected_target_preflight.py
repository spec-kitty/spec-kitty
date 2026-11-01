"""A consolidation the status policy would refuse is refused up front (#5385).

A LANES mission (no coordination branch) whose recorded target is the protected
``main`` records its ``done`` bookkeeping on ``main``. The workflow mutation policy
refuses that write (``PROTECTED_BRANCH_REFUSED``), but pre-fix it only did so from
``_phase_record_done_and_project``: AFTER the squash had advanced ``main``. The
rollback door now restores that crash; this contract is stronger -- the
refusal happens BEFORE any branch moves and before a merge record is written
with the policy's own code, message and remedy.

The refusal comes from the transaction's own policy gate (probed lock-free),
never from a second "is this LANES and protected" rule. The controls below run on
the SAME fixture shape, so a preflight that refuses everything, or nothing, fails:

* an unprotected target (``develop``) consolidates;
* the operator hatch (``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS``) and an empty
  ``protection.protected_branches`` config are honoured;
* ``--target`` cannot launder the refusal (the status write target is the RECORDED
  meta target);
* a ``single_branch`` mission with ``commit_to_target`` and a coordination-topology
  mission are not refused on ``main``;
* an all-done mission writes no ``done`` bookkeeping, so it is not refused.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from tests.terminus.conftest import CoordMission, _approve_events, _event, _now_iso, blob_present_at, build_coord_mission, git_rev, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import flat, ref_shas, reflog_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REFUSAL_CODE = "PROTECTED_BRANCH_REFUSED"
_HATCH = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"
# The policy's own remedy for a coordination-less mission (``coordination/policy.py``).
_REMEDY = "Commit bookkeeping to a non-protected branch"
_PREFLIGHT_LINE = "Consolidation refused before any branch moved."
_EMPTY_PROTECTION = "protection:\n  protected_branches: []\n"


def _consolidate(mission: CoordMission, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *extra], env=env)


def _merge_records(mission: CoordMission) -> list[Path]:
    return sorted((mission.repo / ".kittify" / "runtime" / "merge").glob("*/state.json"))


def _reflogs(mission: CoordMission) -> dict[str, list[str]]:
    return {branch: reflog_shas(mission, branch) for branch in (mission.target_branch, mission.coord_branch)}


def _commit_protection_config(mission: CoordMission, text: str) -> None:
    """Write + commit ``.kittify/config.yaml`` (an uncommitted one trips the dirty-tree preflight first)."""
    config = mission.repo / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(text, encoding="utf-8")
    git(mission.repo, "add", str(config))
    git(mission.repo, "commit", "-qm", "chore: protection config")


def _assert_refused_before_any_mutation(
    mission: CoordMission,
    result: subprocess.CompletedProcess[str],
    before: dict[str, str],
    reflogs_before: dict[str, list[str]],
) -> None:
    output = flat(result)
    assert result.returncode == 1, f"the protected-target consolidation must be refused. output={output}"
    assert _REFUSAL_CODE in output, f"the refusal must carry the policy's error code. output={output}"
    assert _REMEDY in output, f"the refusal must carry the policy's remedy. output={output}"
    assert _PREFLIGHT_LINE in output, f"the refusal must come from the up-front preflight. output={output}"
    assert "Traceback" not in result.stderr, f"a policy refusal is not a crash. stderr={result.stderr}"
    assert ref_shas(mission) == before, f"no branch tip may move. output={output}"
    assert _reflogs(mission) == reflogs_before, f"no branch may move and come back either. output={output}"
    assert _merge_records(mission) == [], f"no merge record may be written. output={output}"
    assert not blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "no squashed content on the target"


def test_lanes_mission_on_protected_main_is_refused_before_any_mutation(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5385P")
    before, reflogs_before = ref_shas(mission), _reflogs(mission)

    result = _consolidate(mission)

    _assert_refused_before_any_mutation(mission, result, before, reflogs_before)


def test_dry_run_reports_the_policy_refusal_code(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5385D")
    before = ref_shas(mission)

    result = run_terminus(mission, ["consolidate", "--dry-run", "--mission", mission.slug, "--json"])

    assert result.returncode == 1, flat(result)
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload.get("error_code") == _REFUSAL_CODE, payload
    assert _REMEDY in str(payload.get("error")), payload
    assert ref_shas(mission) == before


def test_target_override_cannot_launder_the_recorded_protected_target(tmp_path: Path) -> None:
    """The status write target is the RECORDED meta target, never ``--target``."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5385T")
    git(mission.repo, "checkout", "-qb", "develop", "main")
    before, reflogs_before = ref_shas(mission), _reflogs(mission)
    develop_before = git(mission.repo, "rev-parse", "develop").stdout.strip()

    result = _consolidate(mission, "--target", "develop")

    _assert_refused_before_any_mutation(mission, result, before, reflogs_before)
    assert git(mission.repo, "rev-parse", "develop").stdout.strip() == develop_before, "the override target must not move either"


def test_control_unprotected_target_consolidates(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8="01M5385U")

    result = _consolidate(mission)

    output = flat(result)
    assert result.returncode == 0, output
    assert _REFUSAL_CODE not in output, output
    assert blob_present_at(mission.repo, "develop", "src/pkg/wp02.py"), output


def test_control_operator_hatch_is_not_refused(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5385H")

    result = _consolidate(mission, env={_HATCH: "1"})

    output = flat(result)
    assert _REFUSAL_CODE not in output, f"the hatch declares main unprotected; the preflight must honour it. output={output}"
    assert _PREFLIGHT_LINE not in output, output
    assert result.returncode == 0, output


def test_control_empty_protected_branch_config_is_not_refused(tmp_path: Path) -> None:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5385E")
    _commit_protection_config(mission, _EMPTY_PROTECTION)

    result = _consolidate(mission)

    output = flat(result)
    assert _REFUSAL_CODE not in output, f"an empty protected list protects nothing. output={output}"
    assert _PREFLIGHT_LINE not in output, output
    assert result.returncode == 0, output


def test_control_coordination_mission_on_main_is_not_refused(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), target_branch="main", mid8="01M5385C")

    result = _consolidate(mission)

    output = flat(result)
    assert _PREFLIGHT_LINE not in output, f"a coordination mission redirects its bookkeeping. output={output}"
    assert _REFUSAL_CODE not in output, output
    assert result.returncode == 0, output


def test_control_all_done_mission_is_not_refused(tmp_path: Path) -> None:
    """An all-done run writes no ``done`` bookkeeping, so there is nothing for the policy to refuse."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="main", mid8="01M5385A")
    events_path = mission.feature_dir / "status.events.jsonl"
    with events_path.open("a", encoding="utf-8") as fh:
        for wp in ("WP01", "WP02"):
            fh.write(json.dumps(_event(mission, wp, "approved", "done"), sort_keys=True) + "\n")
    git(mission.repo, "add", str(events_path))
    git(mission.repo, "commit", "-qm", "chore: record WP01/WP02 done")

    result = _consolidate(mission)

    output = flat(result)
    assert _PREFLIGHT_LINE not in output, f"an all-done run must not be refused up front. output={output}"
    assert _REFUSAL_CODE not in output, f"an all-done run writes no done bookkeeping for the policy to refuse. output={output}"
    assert result.returncode == 0, output


def _build_commit_to_target_single_branch(tmp_path: Path, mid8: str) -> CoordMission:
    """A ``single_branch`` mission created with ``--commit-to-target`` on protected ``main``.

    Shape per ``contracts/single-branch-execution.md``: ``meta.commit_to_target`` is
    ``true`` (the mission-scoped protection bypass), no mission branch is minted, and
    ``lanes.json`` holds ONE ``lane-planning`` lane whose ``mission_branch`` is the
    target. The approved WP's code is committed on ``main`` itself.
    """
    mission = build_lanes_mission(tmp_path, wps=(), target_branch="main", mid8=mid8)
    # The finalize-tasks planning commit the real flow records in lanes.json; here it is the repo
    # tip BEFORE the WP01 code commit below, so the #5939 evidence window planning_commit..main
    # contains src/pkg/wp01.py (axis (a) implementation-evidence passes). Without it the manifest
    # has no planning_commit_sha and the fail-closed backstop correctly refuses an uncomputable
    # window -- this fixture just predates finalize-tasks, so it completes the manifest here.
    planning_commit = git_rev(mission.repo, "HEAD")
    meta_path = mission.feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(topology="single_branch", commit_to_target=True)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_lanes_json(
        mission.feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission.slug,
            mission_id=mission.mission_id,
            mission_branch="main",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-planning",
                    wp_ids=("WP01",),
                    write_scope=("src/pkg/wp01.py",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at=_now_iso(),
            computed_from="single-branch-commit-to-target-fixture",
            planning_commit_sha=planning_commit,
        ),
    )
    # owned_files so the #5939 evidence axis can attribute the WP01 code commit to WP01.
    (mission.feature_dir / "tasks" / "WP01-work.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 work\nowned_files:\n  - src/pkg/wp01.py\n---\n# WP01\n", encoding="utf-8"
    )
    events = [json.dumps(e, sort_keys=True) + "\n" for e in _approve_events(mission, "WP01")]
    (mission.feature_dir / "status.events.jsonl").write_text("".join(events), encoding="utf-8")
    code = mission.repo / "src" / "pkg" / "wp01.py"
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_text("def wp01() -> int:\n    return 1\n", encoding="utf-8")
    git(mission.repo, "add", ".")
    git(mission.repo, "commit", "-qm", "feat: WP01 on main (commit_to_target)")
    git(mission.repo, "branch", "-D", mission.coord_branch)
    return mission


def test_control_single_branch_commit_to_target_is_not_refused(tmp_path: Path) -> None:
    mission = _build_commit_to_target_single_branch(tmp_path, "01M5385S")

    result = _consolidate(mission)

    output = flat(result)
    assert _PREFLIGHT_LINE not in output, f"commit_to_target lets this mission's own writes reach main. output={output}"
    assert _REFUSAL_CODE not in output, output
    assert result.returncode == 0, output


def test_resume_after_a_crash_points_at_abort_instead_of_claiming_nothing_moved(tmp_path: Path) -> None:
    """A ``--resume`` refused up front must not claim no branch moved: an earlier attempt did.

    Crash residue (advanced ``main`` + mission branch + a resumable record) comes
    from the hard-killed real run of ``test_abort_restores_snapshot``; the ``--resume``
    itself is the unpatched real CLI, so the up-front preflight refuses it.
    """
    from tests.terminus.test_abort_restores_snapshot import _crashed_lanes_run

    mission, _before = _crashed_lanes_run(tmp_path, "01M5385R")
    crashed = ref_shas(mission)

    result = _consolidate(mission, "--resume")

    output = flat(result)
    assert result.returncode == 1, output
    assert _REFUSAL_CODE in output, output
    assert "spec-kitty consolidate --abort" in output, f"the refusal must point at --abort to restore the earlier attempt. output={output}"
    assert _PREFLIGHT_LINE not in output, f"a resume must not claim no branch moved. output={output}"
    assert ref_shas(mission) == crashed, f"the refused resume itself moves nothing. output={output}"


# --------------------------------------------------------------------------- #
# #6464: a --target override may not land on a protected branch
#
# The recorded-target probe above reads the Mission's RECORDED target, so an
# operator who retargets the branch-integration step with ``--target main`` used
# to squash-commit the Mission straight onto the protected branch: that commit is
# a raw ``git commit`` in an ephemeral worktree (``lanes/consolidation.py::
# _merge_branch_into``), so the workflow mutation policy never saw it. The guard
# below refuses before any branch moves.
#
# The fixture's checkout sits ON the override target on purpose: the pre-existing
# ``MERGE_UNSAFE_PRIMARY_OFF_TARGET`` guard refuses a run whose checkout is not on
# the resolved target, so a fixture left on ``develop`` would pass for the wrong
# reason and prove nothing about this guard.
# --------------------------------------------------------------------------- #
_RECORDED_TARGET = "develop"
_OVERRIDE_TARGET = "main"
_OVERRIDE_REMEDY_TARGET = f"'{_RECORDED_TARGET}'"


def _build_override_fixture(tmp_path: Path, mid8: str) -> CoordMission:
    """A Mission recorded for ``develop``, with a protected ``main`` checked out."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch=_RECORDED_TARGET, mid8=mid8)
    git(mission.repo, "branch", _OVERRIDE_TARGET)
    git(mission.repo, "checkout", "-q", _OVERRIDE_TARGET)
    return mission


def _assert_override_refused_before_any_mutation(
    mission: CoordMission,
    result: subprocess.CompletedProcess[str],
    before: dict[str, str],
    reflogs_before: dict[str, list[str]],
    main_before: str,
) -> None:
    output = flat(result)
    assert result.returncode == 1, f"the protected override must be refused. output={output}"
    assert "→ main" not in output, f"the squash must never reach the protected branch. output={output}"
    assert _REFUSAL_CODE in output, f"the refusal must carry the policy's error code. output={output}"
    assert _PREFLIGHT_LINE in output, f"the refusal must come from the up-front preflight. output={output}"
    assert _OVERRIDE_REMEDY_TARGET in output, f"the remedy must name the Mission's recorded target. output={output}"
    assert _HATCH in output, f"the remedy must name the operator hatch. output={output}"
    assert "Traceback" not in result.stderr, f"a policy refusal is not a crash. stderr={result.stderr}"
    assert ref_shas(mission) == before, f"no branch tip may move. output={output}"
    assert _reflogs(mission) == reflogs_before, f"no branch may move and come back either. output={output}"
    assert _merge_records(mission) == [], f"no merge record may be written. output={output}"
    assert git(mission.repo, "rev-parse", _OVERRIDE_TARGET).stdout.strip() == main_before, "the protected branch must keep its tip"
    assert not blob_present_at(mission.repo, _OVERRIDE_TARGET, "src/pkg/wp01.py"), "no squashed content on the protected branch"


@pytest.mark.regression
def test_target_override_onto_protected_main_is_refused_before_any_mutation(tmp_path: Path) -> None:
    """#6464: ``consolidate --target main`` on a Mission recorded for ``develop`` never commits to ``main``."""
    mission = _build_override_fixture(tmp_path, "01M6464O")
    main_before = git(mission.repo, "rev-parse", _OVERRIDE_TARGET).stdout.strip()
    before, reflogs_before = ref_shas(mission), _reflogs(mission)

    result = _consolidate(mission, "--target", _OVERRIDE_TARGET)

    _assert_override_refused_before_any_mutation(mission, result, before, reflogs_before, main_before)


def test_control_target_override_within_the_recorded_target_is_not_refused(tmp_path: Path) -> None:
    """Restating the recorded target with ``--target`` is not a retarget, so nothing is refused."""
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch=_RECORDED_TARGET, mid8="01M6464W")

    result = _consolidate(mission, "--target", _RECORDED_TARGET)

    output = flat(result)
    assert result.returncode == 0, output
    assert _REFUSAL_CODE not in output, output
    assert _PREFLIGHT_LINE not in output, output
    assert blob_present_at(mission.repo, _RECORDED_TARGET, "src/pkg/wp02.py"), output


def test_control_target_override_hatch_stands_the_guard_down(tmp_path: Path) -> None:
    """The operator hatch unprotects the branch for every decision, this guard included."""
    mission = _build_override_fixture(tmp_path, "01M6464H")

    result = _consolidate(mission, "--target", _OVERRIDE_TARGET, env={_HATCH: "1"})

    output = flat(result)
    assert _REFUSAL_CODE not in output, f"the hatch declares main unprotected; the guard must stand down. output={output}"
    assert _PREFLIGHT_LINE not in output, output
    assert "→ main" in output, f"with the hatch the landing proceeds; the guard refused it anyway. output={output}"


@pytest.mark.regression
def test_dry_run_reports_the_target_override_refusal(tmp_path: Path) -> None:
    """``--dry-run`` may not promise a landing the real run refuses."""
    mission = _build_override_fixture(tmp_path, "01M6464D")
    before = ref_shas(mission)

    result = run_terminus(mission, ["consolidate", "--dry-run", "--mission", mission.slug, "--json", "--target", _OVERRIDE_TARGET])

    output = flat(result)
    assert result.returncode == 1, output
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload.get("error_code") == _REFUSAL_CODE, payload
    assert _OVERRIDE_REMEDY_TARGET in str(payload.get("error")), payload
    assert ref_shas(mission) == before, "a refused forecast moves nothing"
