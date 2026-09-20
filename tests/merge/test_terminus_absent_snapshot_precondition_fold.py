"""Pre-PR adversarial-squad FINDING 3 (MEDIUM) — terminus-safety-invariant-01M2XFT7.

``_assert_mission_terminal_ready`` (``merge/executor.py``) builds its
``relevant`` mapping as::

    relevant = {wp_id: work_packages[wp_id] for wp_id in run.all_wp_ids if wp_id in work_packages}

A WP declared in ``run.all_wp_ids`` (lanes.json — not acceptably-cancelled)
but ABSENT from the reduced status snapshot (``work_packages``, produced by
``status.reduce(status.read_events(...))``) is silently DROPPED from
``relevant`` rather than reported missing. ``mission_terminal_acceptability``
then evaluates over the SMALLER dict — and for the degenerate case where
``relevant`` ends up empty, returns ``(True, [])`` (its own documented
"vacuous case of no WPs at all"), so the precondition PASSES for a mission
that has recorded no status event whatsoever for its only WP. This is a
fail-OPEN gap in a gate that is supposed to be fail-CLOSED (contrast US1-6,
which correctly refuses a cancellation-without-provenance WP that IS present
in the snapshot).

The fix folds every WP absent from the snapshot into ``missing`` (refuse),
never dropping it silently — a WP the reducer has no record of at all is
strictly less evidence of readiness than an ``in_progress`` one.

RED before the fix: the merge proceeds (lane consolidation + bake) despite
WP01 never having recorded so much as a ``claimed``/``in_progress`` event.
GREEN after: refuses, naming WP01, before any mutation — mirrors
``test_issue_4764_terminus_safety.py``'s harness and assertion shape.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kernel.clock import now_utc_iso

# Import the status package before any coordination submodule (production import
# order) to avoid the known ``coordination -> transaction -> status`` cycle when a
# test module imports ``merge`` first under ``PYTHONPATH=src``.
import specify_cli.status  # noqa: F401  # import-order guard (see comment above)

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

MID8 = "01M2ABS3"
MISSION_ID = "01M2ABS300000000000000ABS3"
MISSION_SLUG = f"terminus-absent-snapshot-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
WP_ID = "WP01"
LANE_ID = "lane-a"
LANE_CODE = "src/absent_snapshot_feature.py"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _branch_tip(repo: Path, branch: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "FOLD-F3 absent-from-snapshot precondition fail-open regression",
        "purpose_context": ("a WP declared in lanes.json but absent from the reduced status snapshot must refuse, not pass vacuously"),
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(feature_dir: Path) -> LanesManifest:
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_SLUG,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=(WP_ID,),
                write_scope=(LANE_CODE,),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _write_wp_file(feature_dir: Path) -> None:
    (feature_dir / "tasks" / f"{WP_ID}-work.md").write_text(
        f"---\nwork_package_id: {WP_ID}\ntitle: {WP_ID} work\nagent: implementer-bot\n---\n# {WP_ID}\n",
        encoding="utf-8",
    )


def _bootstrap_coord_mission_absent_snapshot(repo: Path) -> Path:
    """WP01 is declared in lanes.json/tasks, but ``status.events.jsonl`` carries
    NO event for it at all — the reduced snapshot has no entry for WP01
    whatsoever (distinct from an ``in_progress``/unreviewed entry, #4764's
    shape, which IS present in the snapshot)."""
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    _write_wp_file(feature_dir)
    # Genuinely empty event log — no status event for WP01 (or any WP) exists.
    (feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap absent-snapshot mission")

    _git(repo, "branch", COORD_BRANCH)
    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_ID}"
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / LANE_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def absent_snapshot() -> int:\n    return 1\n", encoding="utf-8")
    _git(repo, "add", LANE_CODE)
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): lane code for {WP_ID}")
    _git(repo, "checkout", "main")

    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)
    return feature_dir


@contextlib.contextmanager
def _external_mocks() -> Iterator[dict[str, MagicMock]]:
    """Mock ONLY side effects outside the precondition + git/status bookkeeping —
    same seam set as ``tests/merge/test_issue_4764_terminus_safety.py``."""
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch("specify_cli.merge.executor._enforce_review_artifact_consistency"),
        "status_history": patch("specify_cli.merge.executor._enforce_canonical_status_history"),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "bake": patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch", return_value=None),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.merge.executor.has_remote", return_value=False),
    }
    with contextlib.ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = MagicMock(mode="warn")
        mocks["policy"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["run_check"].return_value = stale_report
        yield mocks


def test_wp_declared_but_absent_from_snapshot_refuses_merge_not_vacuous_pass(
    tmp_path: Path,
) -> None:
    """FOLD-F3: a WP present in ``run.all_wp_ids`` (declared via lanes.json) but
    with NO status event on the read surface at all must be folded into
    ``missing`` and refuse the merge — never silently dropped from the
    ``relevant`` dict and treated as vacuously acceptable."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission_absent_snapshot(repo)

    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_ID}"
    pre_lane_tip = _branch_tip(repo, lane_branch)
    pre_coord_tip = _branch_tip(repo, COORD_BRANCH)
    pre_primary_meta = (feature_dir / "meta.json").read_text(encoding="utf-8")

    with (
        _external_mocks(),
        patch("specify_cli.cli.console.console.print") as mock_print,
        pytest.raises(BaseException) as excinfo,  # noqa: PT011 — asserted below
    ):
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
        )

    exit_code = getattr(excinfo.value, "exit_code", None)
    assert exit_code not in (0, None), f"merge must exit non-zero, got {excinfo.value!r}"

    printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
    assert WP_ID in printed, f"refusal must name the WP absent from the snapshot: {printed!r}"
    assert "merge-ready" in printed.lower() or "review approval" in printed.lower()

    assert _branch_tip(repo, lane_branch) == pre_lane_tip, "no lane consolidation may occur"
    assert _branch_tip(repo, COORD_BRANCH) == pre_coord_tip, "no bake/done write may occur"
    assert (feature_dir / "meta.json").read_text(encoding="utf-8") == pre_primary_meta, "primary meta.json must be unchanged"
