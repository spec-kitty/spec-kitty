"""Unit tests for ``specify_cli.decisions.fork`` (WP17, T091/T092).

The ONE read-only detector shared by ``doctor decisions``, ``decision
verify``, coordination teardown and the consolidation preflight (NFR-004).
Table-driven over the four NFR-002 fork fixtures
(``tests/_factories/coord_mission.py::make_fork_fixture``) plus a
non-coordination control, per state (``single_home`` / ``prefix`` /
``forked`` / ``absent``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kernel.git import GitCommandError
from mission_runtime import MissionTopology
from specify_cli.decisions import fork
from specify_cli.decisions.fork import (
    DecisionsForkReport,
    LedgerHomeFinding,
    LedgerProbeError,
    SurfaceLog,
    StreamForkFinding,
    coordination_only_ledger,
    detect_decision_forks,
    ledger_is_coordination_only,
    read_coordination_ledger_raw,
)
from tests._factories.coord_mission import make_coord_mission, make_fork_fixture

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSING_COORD_BRANCH = "kitty/mission-does-not-exist"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------------------
# Value-object shape (data-model.md §4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("DM-01KXYZ.md", True),
        ("DM-.md", True),
        ("index.json", False),
        ("DM-01KXYZ.json", False),
        ("notes-DM-01KXYZ.md", False),
        ("dm-01kxyz.md", False),
    ],
)
def test_is_dm_file_matches_only_decision_moment_markdown(name: str, expected: bool) -> None:
    from specify_cli.decisions.fork import _dm_file_names, _is_dm_file

    assert _is_dm_file(name) is expected
    assert _dm_file_names([name]) == ({name} if expected else set())


def test_value_objects_are_frozen_dataclasses() -> None:
    log = SurfaceLog(surface="primary", source="worktree", ref=None, path="p", event_ids=())
    with pytest.raises(AttributeError):
        log.surface = "coordination"  # type: ignore[misc]

    finding = StreamForkFinding(
        stream="status.events.jsonl",
        state="absent",
        primary=None,
        coordination=None,
        decisions_only_on_primary=(),
        decisions_only_on_coordination=(),
        decisions_on_both=(),
    )
    with pytest.raises(AttributeError):
        finding.state = "forked"  # type: ignore[misc]

    ledger = LedgerHomeFinding(state="absent", entries_only_on_coordination=(), dm_files_only_on_coordination=())
    with pytest.raises(AttributeError):
        ledger.state = "primary"  # type: ignore[misc]

    report = DecisionsForkReport(mission_slug="m", topology=None, streams=(), ledger=ledger, forked=False, reconcile_steps=())
    with pytest.raises(AttributeError):
        report.forked = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# detect_decision_forks: table-driven over the four fork fixtures
# ---------------------------------------------------------------------------


def test_root_uncommitted_coord_untracked_is_forked(tmp_path: Path) -> None:
    """Fixture (a): neither side is committed; both read from their worktree."""
    fixture = make_fork_fixture(tmp_path, "root_uncommitted_coord_untracked", MissionTopology.COORD)

    report = detect_decision_forks(fixture.repo_root, fixture.mission_dir_name)

    assert report.forked is True
    status_finding = next(s for s in report.streams if s.stream == "status.events.jsonl")
    assert status_finding.state == "forked"
    assert status_finding.primary is not None and status_finding.primary.source == "worktree"
    assert status_finding.coordination is not None and status_finding.coordination.source == "worktree"
    assert status_finding.decisions_only_on_primary == fixture.decision_ids_root
    assert status_finding.decisions_only_on_coordination == fixture.decision_ids_coord
    assert status_finding.decisions_on_both == ()


def test_both_committed_is_forked_from_worktrees(tmp_path: Path) -> None:
    """Fixture (b): both sides committed; still read from their worktrees when present."""
    fixture = make_fork_fixture(tmp_path, "both_committed", MissionTopology.COORD)

    report = detect_decision_forks(fixture.repo_root, fixture.mission_dir_name)

    assert report.forked is True
    status_finding = next(s for s in report.streams if s.stream == "status.events.jsonl")
    assert status_finding.state == "forked"
    assert status_finding.primary is not None and status_finding.primary.source == "worktree"
    assert status_finding.coordination is not None and status_finding.coordination.source == "worktree"


def test_fresh_clone_is_forked_from_refs_no_worktree_materialized(tmp_path: Path) -> None:
    """Fixture (c): a clone of (b), no coordination worktree. The detector
    reads the coordination side from its branch ref and never materializes
    a worktree (FR-016 US4.1 read-only control)."""
    fixture = make_fork_fixture(tmp_path, "fresh_clone", MissionTopology.COORD)
    assert fixture.clone_root is not None

    worktree_list_before = _git(fixture.clone_root, "worktree", "list", "--porcelain")

    report = detect_decision_forks(fixture.clone_root, fixture.mission_dir_name)

    worktree_list_after = _git(fixture.clone_root, "worktree", "list", "--porcelain")
    assert worktree_list_before == worktree_list_after, "the detector must never materialize a coordination worktree"

    assert report.forked is True
    status_finding = next(s for s in report.streams if s.stream == "status.events.jsonl")
    assert status_finding.state == "forked"
    assert status_finding.primary is not None and status_finding.primary.source == "worktree"
    assert status_finding.coordination is not None and status_finding.coordination.source == "ref"
    assert status_finding.coordination.ref == fixture.coordination_branch


def test_ledger_only_on_coordination_is_not_a_stream_fork(tmp_path: Path) -> None:
    """Fixture (d): the ledger lives only on the coordination branch, with NO
    companion status-log decision row -- the stream comparison itself stays
    unforked (``absent``); the ledger home finding is the distinct signal."""
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)

    report = detect_decision_forks(fixture.repo_root, fixture.mission_dir_name)

    assert report.forked is False
    for finding in report.streams:
        assert finding.state in ("absent", "single_home")
    assert report.ledger.state == "coordination_only"
    assert ledger_is_coordination_only(report.ledger)
    assert set(report.ledger.entries_only_on_coordination) == set(fixture.decision_ids_coord)
    assert any("coordination_only" in step or "coordination branch" in step for step in report.reconcile_steps)


@pytest.mark.parametrize("stream", ["status_log", "decision_log", "both"])
def test_per_stream_selector_isolates_the_diverging_stream(tmp_path: Path, stream: str) -> None:
    """H2 binding correction: a fork in ONE stream never falsely flags the other."""
    fixture = make_fork_fixture(tmp_path, "both_committed", MissionTopology.COORD, stream=stream)  # type: ignore[arg-type]

    report = detect_decision_forks(fixture.repo_root, fixture.mission_dir_name)

    forked_streams = {s.stream for s in report.streams if s.state == "forked"}
    if stream == "both":
        assert forked_streams == {"status.events.jsonl", "decisions.events.jsonl"}
    elif stream == "status_log":
        assert forked_streams == {"status.events.jsonl"}
    else:
        assert forked_streams == {"decisions.events.jsonl"}


def test_no_decisions_control_is_absent_on_both_surfaces(tmp_path: Path) -> None:
    """A coordination-routed Mission with no decisions ever opened: both
    surfaces resolve (coordination is NOT ``None`` -- the branch/worktree
    exist), but every stream's event_ids are empty on both -> ``absent``."""
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="control")

    report = detect_decision_forks(coord.repo_root, coord.mission_dir_name)

    assert report.forked is False
    for finding in report.streams:
        assert finding.state == "absent"
        assert finding.coordination is not None
        assert finding.coordination.event_ids == ()
        assert finding.primary is not None
        assert finding.primary.event_ids == ()


# ---------------------------------------------------------------------------
# coordination_only_ledger / read_coordination_ledger_raw
# ---------------------------------------------------------------------------


def test_coordination_only_ledger_control_post_fix_is_primary(tmp_path: Path) -> None:
    """A post-fix Mission with no ledger content at all yields ``absent``
    (the PRIMARY positive-control state is proven by the doctor repair test,
    which writes a real PRIMARY ledger then re-diagnoses)."""
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="no-decisions")

    ledger = coordination_only_ledger(coord.repo_root, coord.mission_dir_name)

    assert ledger.state == "absent"
    assert not ledger_is_coordination_only(ledger)


def _point_meta_at_missing_coordination_branch(root_mission_dir: Path) -> None:
    """Declare a coordination branch that does not exist (the branch is already gone)."""
    meta_path = root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["coordination_branch"] = _MISSING_COORD_BRANCH
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def _failing_tree_entry(*_args: object, **_kwargs: object) -> object:
    """A listing probe that fails on a ref that DOES resolve."""
    raise GitCommandError(argv=("ls-tree",), cwd=Path("."), returncode=128, stderr="fatal: simulated ls-tree failure")


def test_readable_coordination_ref_without_a_ledger_is_genuine_absence(tmp_path: Path) -> None:
    """A resolvable ref whose ``decisions/`` dir and ``index.json`` are absent is NOT a probe error."""
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="absent-ledger")

    ledger = coordination_only_ledger(coord.repo_root, coord.mission_dir_name)

    assert ledger.state == "absent"


def test_missing_coordination_branch_is_an_empty_coordination_side(tmp_path: Path) -> None:
    """A coordination ref that does not resolve holds no ledger: absence, never a probe error."""
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)
    _point_meta_at_missing_coordination_branch(fixture.root_mission_dir)

    ledger = coordination_only_ledger(fixture.repo_root, fixture.mission_dir_name)

    assert ledger.state == "absent"
    assert not ledger_is_coordination_only(ledger)
    assert fork._child_names_at_ref(fixture.repo_root, _MISSING_COORD_BRANCH, "kitty-specs") == []
    assert fork._text_at_ref(fixture.repo_root, _MISSING_COORD_BRANCH, "kitty-specs/x/decisions/index.json") is None


def test_failed_listing_on_an_existing_ref_raises_a_probe_error_not_an_empty_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ref resolves but the probe then fails: that must not read as "no ledger"."""
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)
    monkeypatch.setattr(fork, "tree_entry", _failing_tree_entry)

    with pytest.raises(LedgerProbeError) as excinfo:
        coordination_only_ledger(fixture.repo_root, fixture.mission_dir_name)

    assert excinfo.value.ref == fixture.coordination_branch


def test_failed_tree_listing_on_an_existing_ref_raises_a_probe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)
    monkeypatch.setattr(fork, "tree_paths", _failing_tree_entry)

    with pytest.raises(LedgerProbeError):
        fork._child_names_at_ref(fixture.repo_root, fixture.coordination_branch, "kitty-specs")


def test_doctor_report_tolerates_an_unreadable_coordination_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``detect_decision_forks`` (the ``doctor decisions`` consumer) degrades to the PRIMARY verdict."""
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)
    monkeypatch.setattr(fork, "tree_entry", _failing_tree_entry)

    report = detect_decision_forks(fixture.repo_root, fixture.mission_dir_name)

    assert report.ledger.state == "absent"
    assert any("could not be read" in step for step in report.reconcile_steps)


def test_read_coordination_ledger_raw_returns_none_without_coordination(tmp_path: Path) -> None:
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="no-ledger")
    index_document, dm_contents = read_coordination_ledger_raw(coord.repo_root, "nonexistent-mission-dir")
    assert index_document is None
    assert dm_contents == {}


def test_non_coordination_mission_reports_primary_only(tmp_path: Path) -> None:
    """No ``coordination_branch`` declared in ``meta.json`` (legacy mission,
    or a LANES/SINGLE_BRANCH topology) -- T091 step 4: every stream degrades
    to PRIMARY-only, ``coordination`` is ``None``, and the ledger is never
    reported ``coordination_only`` (``COORD_BRANCH_UNDECLARED_AND_ABSENT``
    territory, never a fork)."""
    import json

    mission_slug = "legacy-no-coord"
    mission_dir = tmp_path / "kitty-specs" / mission_slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01LEGACY0000000000000000A", "mission_slug": mission_slug, "target_branch": "main"}),
        encoding="utf-8",
    )
    (mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    report = detect_decision_forks(tmp_path, mission_slug)

    assert report.forked is False
    for finding in report.streams:
        assert finding.coordination is None
        assert finding.state == "absent"
    assert report.ledger.state == "absent"
    assert not ledger_is_coordination_only(report.ledger)
