"""The review-range resolver (#7578, IC-03): one owner of a work package's review range and pathspecs.

``resolve_wp_review_range`` yields the range ``window open .. newest for_review submission`` with
provenance, the owned-file commit list, numstat and out-of-map split, on every topology:

* ``single_branch`` minted and commit-to-target, both stamped today (RECORDED); a commit-to-target
  Mission whose events predate the stamps keeps a range DERIVED from the event commits / the
  ``wp-base`` ref (pinned here by stripping the stamps);
* ``lanes`` and ``lanes_with_coord``, built through the production status shell
  (``tests/consolidation/characterization_support.build_two_wp_lane``).

Every Mission template is built once per module and copied for each test.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from kernel.git import GitCommandError
from specify_cli.lanes.claim_base import record_claim_base
from specify_cli.review import wp_range
from specify_cli.review.wp_range import FileChange, RangeCommit, RangeSource, RangeStatus, WpReviewRange, resolve_wp_review_range
from tests.consolidation import characterization_support as cs
from tests.integration import single_branch_window_support as sb
from tests.integration.review.review_range_fixtures import strip_single_branch_stamps
from tests._support.status_seed import seed_status_event
from tests.terminus.lanes_fixture import build_lanes_mission
from specify_cli.status.models import Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_EVENTS = "status.events.jsonl"
_REJECTED = json.dumps({"reviewer": "bob", "verdict": "changes_requested", "reference": "PR#1-rejected"})
_HARNESS_VARIABLES = ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE", "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS")
_IMPL_SUBJECT = "feat(WP01): implement m1 r1"
_M1 = ("src/m1/**",)
_BOOKKEEPING_PREFIX = "chore(spec-kitty)"


# --------------------------------------------------------------------------- templates


def _with_env(repo: Path, home: Path, patch: pytest.MonkeyPatch) -> None:
    patch.chdir(repo)
    for key, value in sb.cli_env(home).items():
        if key.startswith(("HOME", "XDG_", "SPEC_KITTY_")):
            patch.setenv(key, value)
    for key in _HARNESS_VARIABLES:
        patch.delenv(key, raising=False)


def _submit_wp01(m: sb.Mission) -> None:
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    sb.submit(m, "WP01")


class _SingleBranchTemplates:
    """``single_branch`` Missions: built once on first use, copied per test (the original never runs)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._built: dict[str, tuple[Path, str]] = {}

    def get(self, name: str) -> tuple[Path, str]:
        if name not in self._built:
            self._built[name] = self._build(name)
        return self._built[name]

    def _build(self, name: str) -> tuple[Path, str]:
        base, _, step = name.partition("+")
        if not step:
            return sb.build_template(self._root / name, commit_to_target=base == "ctt")
        source, slug = self.get(base)
        dest = self._root / name.replace("+", "_")
        repo = dest / "repo"
        shutil.copytree(source, repo, symlinks=True)
        with pytest.MonkeyPatch.context() as patch:
            _with_env(repo, dest, patch)
            _submit_wp01(sb.Mission(repo, slug, dest))
        return repo, slug


@pytest.fixture(scope="module")
def sb_templates(tmp_path_factory: pytest.TempPathFactory) -> _SingleBranchTemplates:
    return _SingleBranchTemplates(tmp_path_factory.mktemp("wp-range-sb"))


def _checkout(template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sb.Mission:
    source, slug = template
    repo = tmp_path / "repo"
    shutil.copytree(source, repo, symlinks=True)
    _with_env(repo, tmp_path, monkeypatch)
    return sb.Mission(repo, slug, tmp_path)


def _adapt_topology(mission: cs.ShapeMission, topology: str) -> None:
    """Re-declare a two-WP coordination Mission as *topology* (``lanes`` reads the repository root log)."""
    meta_path = mission.feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["topology"] = topology
    if topology == "lanes":
        meta.pop("coordination_branch", None)
        coord_log = next(log for log in cs._event_logs(mission.repo) if log.parent != mission.feature_dir)
        shutil.copyfile(coord_log, mission.feature_dir / _EVENTS)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cs._git(mission.repo, "add", "-A", "kitty-specs")
    cs._git(mission.repo, "commit", "-qm", f"test: declare the Mission {topology}")


class _LaneTemplates:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._built: dict[str, cs.ShapeMission] = {}

    def copy(self, name: str, dest: Path) -> cs.ShapeMission:
        if name not in self._built:
            self._built[name] = self._build(name)
        return cs.copy_mission(self._built[name], dest / name)

    def _build(self, name: str) -> cs.ShapeMission:
        if name == "coord":
            return cs.build_two_wp_lane(self._root / name, mid8="01M77R01")
        mission = cs.copy_mission(self.copy("coord", self._root / f"src-{name}"), self._root / name)
        _adapt_topology(mission, name)
        return mission


@pytest.fixture(scope="module")
def lane_templates(tmp_path_factory: pytest.TempPathFactory) -> _LaneTemplates:
    return _LaneTemplates(tmp_path_factory.mktemp("wp-range-lanes"))


@pytest.fixture
def lane_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    yield


# --------------------------------------------------------------------------- observations


def _sb_events(m: sb.Mission, wp_id: str = "WP01") -> list[dict[str, Any]]:
    log = m.repo / "kitty-specs" / m.slug / _EVENTS
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [row for row in rows if row.get("wp_id") == wp_id]


def _of(rows: list[dict[str, Any]], to_lane: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("to_lane") == to_lane]


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row.get("policy_metadata") or {})


def _open_sha(row: dict[str, Any]) -> str:
    return str(_meta(row)["wp_window"]["open_sha"])


def _event_commit(m: sb.Mission, event_id: str) -> str:
    return sb.git(m.repo, "log", "--format=%H", f"-S{event_id}", "HEAD", "--", f"kitty-specs/{m.slug}/{_EVENTS}")


def _subjects(found: WpReviewRange) -> list[str]:
    return [commit.subject for commit in found.commits]


def _resolve_sb(m: sb.Mission, owned: tuple[str, ...] = _M1) -> WpReviewRange:
    return resolve_wp_review_range(m.repo, m.slug, "WP01", owned_files=owned)


def _resolve_lane(mission: cs.ShapeMission, wp_id: str, owned: tuple[str, ...] = ("src/**",)) -> WpReviewRange:
    with cs.mission_environment(mission):
        return resolve_wp_review_range(mission.repo, mission.slug, wp_id, owned_files=owned)


def _strip_stamps_sb(m: sb.Mission) -> None:
    strip_single_branch_stamps(m.repo, m.repo / "kitty-specs" / m.slug, "WP01")


def _strip_stamps_lane(mission: cs.ShapeMission, wp_id: str) -> None:
    def _edit(event: dict[str, Any]) -> dict[str, Any] | None:
        metadata = event.get("policy_metadata") or {}
        if event.get("wp_id") != wp_id or not metadata:
            return None
        return {**event, "policy_metadata": {k: v for k, v in metadata.items() if k not in ("lane_head", "wp_window")} or None}

    cs.rewrite_events(mission, _edit, f"test: strip {wp_id}'s stamps")


# --------------------------------------------------------------------------- value objects


def test_unavailable_range_carrying_a_base_is_refused() -> None:
    with pytest.raises(ValueError, match="UNAVAILABLE"):
        WpReviewRange(
            wp_id="WP01",
            base="a" * 40,
            tip=None,
            base_source=RangeSource.RECORDED_WINDOW,
            tip_source=RangeSource.NONE,
            gap=None,
            status=RangeStatus.UNAVAILABLE,
        )


def test_available_range_without_a_tip_is_refused() -> None:
    with pytest.raises(ValueError, match="UNAVAILABLE"):
        WpReviewRange(
            wp_id="WP01",
            base="a" * 40,
            tip=None,
            base_source=RangeSource.RECORDED_WINDOW,
            tip_source=RangeSource.NONE,
            gap=None,
            status=RangeStatus.DERIVED,
        )


def test_unavailable_factory_names_the_gap_and_keeps_the_pathspecs() -> None:
    found = WpReviewRange.unavailable("WP03", "no_submission", ("src/**",))

    assert found.status is RangeStatus.UNAVAILABLE
    assert (found.base, found.tip, found.gap) == (None, None, "no_submission")
    assert found.base_source is RangeSource.NONE and found.tip_source is RangeSource.NONE
    assert found.owned_pathspecs == ("src/**",)
    assert found.commits == () and found.files == () and found.moved_past == 0


def test_an_unreadable_status_surface_is_unavailable_never_a_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("meta.json not found")

    monkeypatch.setattr(wp_range, "resolve_status_read", _broken)

    found = resolve_wp_review_range(tmp_path, "missing-mission", "WP01", owned_files=["src/**"])

    assert found.status is RangeStatus.UNAVAILABLE
    assert found.gap == "status_unreadable"
    assert found.owned_pathspecs == ("src/**",)


# --------------------------------------------------------------------------- recorded ranges


def test_minted_single_branch_range_is_recorded_from_window_open_to_submission(
    sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)
    rows = _sb_events(m)

    found = _resolve_sb(m)

    assert found.status is RangeStatus.RECORDED
    assert found.base == _open_sha(_of(rows, "claimed")[0])
    assert found.base_source is RangeSource.RECORDED_WINDOW
    assert found.tip == _meta(_of(rows, "for_review")[-1])["lane_head"]
    assert found.tip_source is RangeSource.RECORDED_SUBMISSION
    assert found.gap is None
    assert _subjects(found) == [_IMPL_SUBJECT]
    assert all(len(commit.sha) == 40 for commit in found.commits)


@pytest.mark.parametrize("topology", ["lanes", "lanes_with_coord"])
def test_lane_range_is_recorded_from_window_open_to_submission(lane_templates: _LaneTemplates, tmp_path: Path, lane_env: None, topology: str) -> None:
    mission = lane_templates.copy(topology, tmp_path)
    rows = [row for row in cs._events(mission) if row.get("wp_id") == "WP02"]

    found = _resolve_lane(mission, "WP02")

    assert found.status is RangeStatus.RECORDED
    assert found.base == _open_sha(_of(rows, "claimed")[0])
    assert found.base_source is RangeSource.RECORDED_WINDOW
    assert found.tip == _meta(_of(rows, "for_review")[-1])["lane_head"]
    assert found.tip_source is RangeSource.RECORDED_SUBMISSION
    assert _subjects(found) == [f"feat({mission.slug}): WP02 work"]
    assert found.files == (FileChange(cs.WP02_PATH, 2, 0),)


def test_lane_mate_commits_are_not_in_the_range(lane_templates: _LaneTemplates, tmp_path: Path, lane_env: None) -> None:
    mission = lane_templates.copy("lanes_with_coord", tmp_path)
    wp01_work = cs._git(mission.repo, "log", "--format=%H", "-1", mission.lane_branches["WP01"], "--", cs.WP01_PATH)

    wp01 = _resolve_lane(mission, "WP01")
    wp02 = _resolve_lane(mission, "WP02")

    assert [commit.sha for commit in wp01.commits] == [wp01_work]
    assert wp01_work not in [commit.sha for commit in wp02.commits]
    assert cs.WP01_PATH not in [change.path for change in wp02.files]


# --------------------------------------------------------------------------- derived ranges


def test_stamped_commit_to_target_range_is_recorded_from_window_open_to_submission(
    sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = _checkout(sb_templates.get("ctt+submitted"), tmp_path, monkeypatch)
    rows = _sb_events(m)

    found = _resolve_sb(m)

    assert found.status is RangeStatus.RECORDED
    assert found.base == _open_sha(_of(rows, "claimed")[0])
    assert found.base_source is RangeSource.RECORDED_WINDOW
    assert found.tip == _meta(_of(rows, "for_review")[-1])["lane_head"]
    assert found.tip_source is RangeSource.RECORDED_SUBMISSION
    assert found.gap is None
    assert _subjects(found) == [_IMPL_SUBJECT]


def test_pre_stamp_commit_to_target_range_is_derived_from_the_event_commits(
    sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit-to-target Mission whose events predate the window stamps keeps the derived range."""
    m = _checkout(sb_templates.get("ctt+submitted"), tmp_path, monkeypatch)
    rows = _sb_events(m)
    _strip_stamps_sb(m)

    found = _resolve_sb(m)

    assert found.status is RangeStatus.DERIVED
    assert found.base == _event_commit(m, _of(rows, "claimed")[0]["event_id"])
    assert found.base_source is RangeSource.EVENT_COMMIT
    assert found.tip == _event_commit(m, _of(rows, "for_review")[-1]["event_id"])
    assert found.tip_source is RangeSource.EVENT_COMMIT
    assert found.gap == "not_recorded"
    assert _subjects(found) == [_IMPL_SUBJECT]


def test_pre_stamp_commit_to_target_range_prefers_the_claim_base_ref(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without window stamps, a commit-to-target Mission's claim-base ref beats the claim event's commit."""
    m = _checkout(sb_templates.get("ctt"), tmp_path, monkeypatch)
    claim_base = record_claim_base(m.repo, m.repo, m.slug, "WP01")
    _submit_wp01(m)
    _strip_stamps_sb(m)

    found = _resolve_sb(m)

    assert found.status is RangeStatus.DERIVED
    assert found.base == claim_base
    assert found.base_source is RangeSource.CLAIM_BASE_REF
    assert found.tip_source is RangeSource.EVENT_COMMIT
    assert _subjects(found) == [_IMPL_SUBJECT]


def test_foreign_commit_on_the_target_touching_only_other_paths_is_excluded(
    sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = _checkout(sb_templates.get("ctt"), tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    foreign = sb.commit_file(m, "src/shared.py", "A = 2\n", "feat: someone else's change on main")
    sb.submit(m, "WP01")

    found = _resolve_sb(m)

    assert foreign not in [commit.sha for commit in found.commits]
    assert _subjects(found) == [_IMPL_SUBJECT]
    assert found.out_of_map == ("src/shared.py",)
    assert found.out_of_map_only_commits == 1


def test_rework_after_a_review_rejection_keeps_the_first_opener(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted"), tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    first = sb.implement(m, "WP01")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")
    sb.emit(m, "WP01", "in_review", "bob")
    sb.emit(m, "WP01", "planned", "bob", "--review-result-json", _REJECTED, "--reason", "changes requested")
    sb.commit_file(m, "docs/review-notes.md", "notes\n", "docs: review notes")
    sb.claim(m, "WP01")
    fix = sb.commit_file(m, "src/m1/fix.py", "FIXED = True\n", "fix(WP01): address review")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "rework handed to review")
    rows = _sb_events(m)
    claims = _of(rows, "claimed")
    assert len(claims) == 2, "precondition: the rework re-claimed the work package"
    assert _of(rows, "planned")[-1].get("from_lane") == "in_review", "precondition: a review rejection, not a rewind"

    found = _resolve_sb(m)

    assert found.status is RangeStatus.RECORDED
    assert found.base == _open_sha(claims[0])
    assert found.base != _open_sha(claims[1]), "the second claim's open point would hide the first attempt"
    assert found.tip == _meta(_of(rows, "for_review")[-1])["lane_head"]
    assert {first, fix} <= {commit.sha for commit in found.commits}


def test_submission_of_a_rewound_cycle_is_ignored(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted"), tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")
    sb.emit(m, "WP01", "in_progress", "alice", "--force", "--reason", "taken back", "--review-ref", "taken-back")
    sb.emit(m, "WP01", "planned", "alice", "--force", "--reason", "rewound: start over")
    sb.claim(m, "WP01")
    assert _of(_sb_events(m), "for_review"), "precondition: the previous cycle was submitted"

    found = _resolve_sb(m)

    assert found.status is RangeStatus.UNAVAILABLE
    assert found.gap == "no_submission"


def test_lane_mission_before_windows_falls_back_to_the_opener_lane_head(lane_templates: _LaneTemplates, tmp_path: Path, lane_env: None) -> None:
    mission = lane_templates.copy("lanes_with_coord", tmp_path)
    cs.set_window_state(mission, "WP02", "not_recorded")
    rows = [row for row in cs._events(mission) if row.get("wp_id") == "WP02"]

    found = _resolve_lane(mission, "WP02")

    assert found.status is RangeStatus.DERIVED
    assert found.base == _meta(_of(rows, "claimed")[0])["lane_head"]
    assert found.base_source is RangeSource.OPENER_LANE_HEAD
    assert found.gap == "not_recorded"
    assert _subjects(found) == [f"feat({mission.slug}): WP02 work"]


def test_leading_lane_branch_missing_opener_is_skipped(lane_templates: _LaneTemplates, tmp_path: Path, lane_env: None) -> None:
    mission = lane_templates.copy("lanes_with_coord", tmp_path)
    cs.set_window_state(mission, "WP02", "lane_branch_missing", openers=[0])
    rows = [row for row in cs._events(mission) if row.get("wp_id") == "WP02"]

    found = _resolve_lane(mission, "WP02")

    assert found.status is RangeStatus.RECORDED
    assert found.base == _open_sha(_of(rows, "in_progress")[0])
    assert found.base_source is RangeSource.RECORDED_WINDOW
    assert found.gap is None


def test_recorded_open_off_the_lane_falls_back_and_names_the_gap(lane_templates: _LaneTemplates, tmp_path: Path, lane_env: None) -> None:
    mission = lane_templates.copy("lanes_with_coord", tmp_path)
    cs.set_window_state(mission, "WP02", "not_on_lane")
    rows = [row for row in cs._events(mission) if row.get("wp_id") == "WP02"]
    off_lane = _open_sha(_of(rows, "claimed")[0])

    found = _resolve_lane(mission, "WP02")

    assert found.base != off_lane
    assert found.base == _meta(_of(rows, "claimed")[0])["lane_head"]
    assert found.base_source is RangeSource.OPENER_LANE_HEAD
    assert found.gap == "not_on_lane"
    assert found.status is RangeStatus.DERIVED


def test_single_branch_without_stamps_falls_back_to_event_commits(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)
    rows = _sb_events(m)
    _strip_stamps_sb(m)

    found = _resolve_sb(m)

    assert found.status is RangeStatus.DERIVED
    assert found.base == _event_commit(m, _of(rows, "claimed")[0]["event_id"])
    assert found.base_source is RangeSource.EVENT_COMMIT
    assert found.tip == _event_commit(m, _of(rows, "for_review")[-1]["event_id"])
    assert found.tip_source is RangeSource.EVENT_COMMIT
    assert _subjects(found) == [_IMPL_SUBJECT]


def test_lane_mission_without_stamps_never_uses_event_commits(lane_templates: _LaneTemplates, tmp_path: Path, lane_env: None) -> None:
    mission = lane_templates.copy("lanes_with_coord", tmp_path)
    _strip_stamps_lane(mission, "WP02")

    found = _resolve_lane(mission, "WP02")

    assert found.status is RangeStatus.UNAVAILABLE
    assert (found.base, found.tip) == (None, None)


def test_no_submission_is_unavailable_with_a_reason(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted"), tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")

    found = _resolve_sb(m)

    assert found.status is RangeStatus.UNAVAILABLE
    assert (found.base, found.tip, found.gap) == (None, None, "no_submission")
    assert found.owned_pathspecs == _M1


# --------------------------------------------------------------------------- listing


def test_plain_submission_has_not_moved_past_its_tip(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)

    found = _resolve_sb(m)

    assert sb.tip(m, "HEAD") != found.tip, "precondition: status commits follow the submission"
    assert found.moved_past == 0


def test_an_implementation_commit_after_the_tip_counts_as_moved_past(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)
    sb.commit_file(m, "src/m1/after.py", "AFTER = 1\n", "feat(WP01): after the submission")

    found = _resolve_sb(m)

    assert found.moved_past == 1


def test_out_of_map_paths_are_flagged_and_out_of_map_only_commits_counted(
    sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = _checkout(sb_templates.get("minted"), tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    docs = sb.commit_file(m, "docs/other.md", "other\n", "docs: outside the owned files")
    (m.repo / "src" / "m1" / "mixed.py").write_text("MIXED = 1\n", encoding="utf-8")
    (m.repo / "src" / "shared.py").write_text("A = 3\n", encoding="utf-8")
    sb.git(m.repo, "add", "src")
    sb.git(m.repo, "commit", "-qm", "feat(WP01): mixed change")
    sb.submit(m, "WP01")

    found = _resolve_sb(m)

    assert docs not in [commit.sha for commit in found.commits]
    assert _subjects(found) == [_IMPL_SUBJECT, "feat(WP01): mixed change"]
    assert found.out_of_map == ("docs/other.md", "src/shared.py")
    assert found.out_of_map_only_commits == 1


def test_numstat_values_are_exact_and_cover_owned_paths_only(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted"), tmp_path, monkeypatch)
    sb.commit_file(m, "src/m1/old.py", "a\nb\n", "chore: an owned file before the claim")
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    sb.commit_file(m, "src/m1/old.py", "a\nx\ny\nz\n", "feat(WP01): rework old")
    sb.commit_file(m, "src/m1/new.py", "1\n2\n3\n4\n5\n", "feat(WP01): new file")
    (m.repo / "src" / "m1" / "blob.bin").write_bytes(b"\x00\x01\x02binary")
    sb.git(m.repo, "add", "src/m1/blob.bin")
    sb.git(m.repo, "commit", "-qm", "feat(WP01): binary")
    sb.commit_file(m, "docs/other.md", "other\n", "docs: outside the owned files")
    sb.submit(m, "WP01")

    found = _resolve_sb(m)

    assert found.files == (
        FileChange("src/m1/blob.bin", None, None),
        FileChange("src/m1/new.py", 5, 0),
        FileChange("src/m1/old.py", 3, 1),
        FileChange("src/m1/real.py", 2, 0),
    )


def test_no_owned_files_leaves_the_range_unscoped(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted"), tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    docs = sb.commit_file(m, "docs/other.md", "other\n", "docs: outside the owned files")
    sb.submit(m, "WP01")

    found = _resolve_sb(m, owned=())

    assert found.owned_pathspecs == ()
    assert found.out_of_map == ()
    assert found.out_of_map_only_commits == 0
    shas = [commit.sha for commit in found.commits]
    assert docs in shas and _IMPL_SUBJECT in _subjects(found)
    assert not [subject for subject in _subjects(found) if "status transition" in subject]
    assert "docs/other.md" in [change.path for change in found.files]


def test_mission_dir_ownership_excludes_mission_bookkeeping(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)
    root = f"kitty-specs/{m.slug}/"
    excludes = (f":(exclude){root}tasks/**", f":(exclude){root}tasks.md", f":(exclude){root}{_EVENTS}", f":(exclude){root}status.json")

    research = _resolve_sb(m, owned=(f"{root}research/**",))
    whole_dir = _resolve_sb(m, owned=(f"{root}**",))
    code_only = _resolve_sb(m)

    assert research.owned_pathspecs == (f"{root}research/**", *excludes)
    assert whole_dir.owned_pathspecs == (f"{root}**", *excludes)
    assert not [subject for subject in _subjects(whole_dir) if subject.startswith(_BOOKKEEPING_PREFIX)]
    assert code_only.owned_pathspecs == _M1
    assert not [subject for subject in _subjects(code_only) if subject.startswith(_BOOKKEEPING_PREFIX)]


def test_merge_commit_inside_the_range_lists_what_git_log_lists(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Merge handling (module docstring): the list is ``git log``'s default walk, the stat is the tree diff."""
    m = _checkout(sb_templates.get("minted"), tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    branch = m.mission_branch
    sb.git(m.repo, "switch", "-q", "-c", "side")
    side = sb.commit_file(m, "src/m1/side.py", "SIDE = 1\n", "feat(WP01): side work")
    sb.git(m.repo, "switch", "-q", branch)
    main_line = sb.commit_file(m, "src/m1/main_line.py", "MAIN = 1\n", "feat(WP01): main-line work")
    sb.git(m.repo, "merge", "-q", "--no-ff", "-m", "merge side work", "side")
    merge = sb.tip(m, "HEAD")
    sb.submit(m, "WP01")

    found = _resolve_sb(m)

    shas = [commit.sha for commit in found.commits]
    assert {side, main_line} <= set(shas)
    assert merge in shas, "git log lists a merge whose combined diff touches the owned files"
    assert {"src/m1/side.py", "src/m1/main_line.py"} <= {change.path for change in found.files}


def test_resolution_is_deterministic(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)

    assert _resolve_sb(m) == _resolve_sb(m)


def test_a_failed_listing_keeps_the_range_and_names_the_failure(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)

    def _broken(*_args: object, **_kwargs: object) -> object:
        raise GitCommandError(argv=("diff",), cwd=m.repo, returncode=128, stderr="boom")

    monkeypatch.setattr(wp_range, "numstat_entries", _broken)

    found = _resolve_sb(m)

    assert found.status is RangeStatus.RECORDED
    assert found.files == () and found.out_of_map == ()
    assert _subjects(found) == [_IMPL_SUBJECT]
    assert found.listing_gap is not None and "numstat" in found.listing_gap


def test_range_commit_is_a_plain_value() -> None:
    assert RangeCommit("a" * 40, "subject") == RangeCommit("a" * 40, "subject")


# --------------------------------------------------------------------------- review cycle 1


def _set_opener_lane_head(mission: cs.ShapeMission, wp_id: str, sha: str) -> None:
    """Rewrite the ``lane_head`` stamp of *wp_id*'s first opening event (in every event-log copy)."""
    seen: dict[Path, bool] = {}

    def _edit(event: dict[str, Any]) -> dict[str, Any] | None:
        if not cs._is_opening(event, wp_id) or seen.get(Path("first")):
            return None
        seen[Path("first")] = True
        return {**event, "policy_metadata": {**(event.get("policy_metadata") or {}), "lane_head": sha}}

    with cs.deterministic_commit_dates(mission.repo):
        for log in cs._event_logs(mission.repo):
            seen.clear()
            cs._rewrite_one(log, _edit, f"test: {wp_id}'s opener lane_head off the lane")


def test_opener_lane_head_off_the_lane_is_never_a_base(lane_templates: _LaneTemplates, tmp_path: Path, lane_env: None) -> None:
    mission = lane_templates.copy("lanes_with_coord", tmp_path)
    cs.set_window_state(mission, "WP02", "not_recorded")
    off_lane = cs._not_on_lane_sha(mission, "WP02")
    _set_opener_lane_head(mission, "WP02", off_lane)
    rows = [row for row in cs._events(mission) if row.get("wp_id") == "WP02"]
    assert _meta(_of(rows, "claimed")[0])["lane_head"] == off_lane, "precondition: the opener stamp is off the lane"

    found = _resolve_lane(mission, "WP02")

    assert found.base != off_lane
    assert found.status is RangeStatus.UNAVAILABLE
    assert found.gap == "not_recorded"


def test_pre_stamp_commit_to_target_stale_claim_base_ref_off_the_tip_is_skipped(
    sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without window stamps, a claim-base ref that never landed on the target falls through to the event commit."""
    m = _checkout(sb_templates.get("ctt"), tmp_path, monkeypatch)
    stale = sb.git(m.repo, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "test: a commit that never lands on the target")
    sb.git(m.repo, "update-ref", f"refs/spec-kitty/wp-base/{m.slug}/WP01", stale)
    _submit_wp01(m)
    rows = _sb_events(m)
    _strip_stamps_sb(m)

    found = _resolve_sb(m)

    assert found.status is RangeStatus.DERIVED
    assert found.base != stale
    assert found.base_source is RangeSource.EVENT_COMMIT
    assert found.base == _event_commit(m, _of(rows, "claimed")[0]["event_id"])
    assert _subjects(found) == [_IMPL_SUBJECT]


def test_claim_base_read_that_cannot_start_git_falls_through(sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)
    rows = _sb_events(m)
    _strip_stamps_sb(m)

    def _no_git(*_args: object, **_kwargs: object) -> object:
        raise OSError("git cannot be started")

    monkeypatch.setattr(wp_range, "read_claim_base", _no_git)

    found = _resolve_sb(m)

    assert found.base_source is RangeSource.EVENT_COMMIT
    assert found.base == _event_commit(m, _of(rows, "claimed")[0]["event_id"])


def test_bookkeeping_excludes_follow_the_mission_directory_not_the_handle(
    sb_templates: _SingleBranchTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = _checkout(sb_templates.get("minted+submitted"), tmp_path, monkeypatch)
    mid8 = json.loads((m.repo / "kitty-specs" / m.slug / "meta.json").read_text(encoding="utf-8"))["mission_id"][:8]
    assert mid8 != m.slug

    by_handle = resolve_wp_review_range(m.repo, mid8, "WP01", owned_files=_M1)

    assert by_handle.status is RangeStatus.RECORDED, by_handle
    assert by_handle.out_of_map == (), "status files are bookkeeping, never out of the owned map"
    assert by_handle.moved_past == 0
    assert by_handle == _resolve_sb(m)


# --------------------------------------------------------------------------- planning lane (operator ruling Q10)


_PLANNING_WP = "WP02"


def _seed_and_commit(mission: Any, event_id: str, from_lane: Lane, to_lane: Lane) -> str:
    """Append one unstamped *wp* event to the repository root log and commit it alone (as ``move-task`` does)."""
    seed_status_event(
        mission.feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=mission.slug,
            wp_id=_PLANNING_WP,
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-11-12T00:00:00+00:00",
            actor="tester",
            force=True,
            execution_mode="direct_repo",
        ),
    )
    cs._git(mission.repo, "add", "-A", "kitty-specs")
    cs._git(mission.repo, "commit", "-qm", f"chore(spec-kitty): status {event_id}")
    return cs._git(mission.repo, "rev-parse", "HEAD")


def _submitted_planning_wp(tmp_path: Path) -> tuple[Any, str, str, str]:
    """A ``lanes`` Mission whose planning-lane WP02 is claimed, commits its research on the target and is submitted.

    Returns the Mission, the claim event commit, the work commit and the submission event commit.
    The planning lane is never stamped (C-009), so none of WP02's events carries a stamp.
    """
    mission = build_lanes_mission(tmp_path, wps=("WP01",), with_planning_lane_wp=True, approve_planning_wp=False, mid8="01M77Q10")
    claim = _seed_and_commit(mission, "01M77Q10CLAIMAAAAAAAAAAAAA", Lane.PLANNED, Lane.CLAIMED)
    research = mission.feature_dir / "research" / f"{_PLANNING_WP}.md"
    research.parent.mkdir(parents=True, exist_ok=True)
    research.write_text("# WP02 research\n", encoding="utf-8")
    cs._git(mission.repo, "add", "-A", "kitty-specs")
    cs._git(mission.repo, "commit", "-qm", "docs: WP02 research")
    work = cs._git(mission.repo, "rev-parse", "HEAD")
    _seed_and_commit(mission, "01M77Q10PROGAAAAAAAAAAAAAA", Lane.CLAIMED, Lane.IN_PROGRESS)
    tip = _seed_and_commit(mission, "01M77Q10REVWAAAAAAAAAAAAAA", Lane.IN_PROGRESS, Lane.FOR_REVIEW)
    return mission, claim, work, tip


def test_planning_lane_wp_on_a_lanes_mission_gets_the_derived_event_commit_range(tmp_path: Path, lane_env: None) -> None:
    """Operator ruling Q10 (spec edge case): a never-stamped planning-lane WP uses the derived range, not UNAVAILABLE."""
    mission, claim, work, tip = _submitted_planning_wp(tmp_path)

    found = resolve_wp_review_range(mission.repo, mission.slug, _PLANNING_WP, owned_files=(f"kitty-specs/{mission.slug}/research/**",))

    assert found.status is RangeStatus.DERIVED
    assert (found.base, found.base_source) == (claim, RangeSource.EVENT_COMMIT)
    assert (found.tip, found.tip_source) == (tip, RangeSource.EVENT_COMMIT)
    assert found.gap == "not_recorded"
    assert [commit.sha for commit in found.commits] == [work]
    assert [change.path for change in found.files] == [f"kitty-specs/{mission.slug}/research/{_PLANNING_WP}.md"]
