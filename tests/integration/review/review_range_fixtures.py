"""Shared review-ready Mission fixtures for the WP review-range acceptance tests (#7578, WP05 / WP07).

Each builder leaves the reviewed work package ``WP02`` review-ready (``for_review`` or
``in_review``, never approved) and returns a :class:`ReviewFixture` carrying the facts the
acceptance assertions need: the expected implementation SHAs (oldest first), the exact
``CHANGED FILES`` lines, the out-of-map path, the SHAs and paths that must stay out of the
review (the lane-mate commit on WP02's own owned path among them), and the expected provenance.

Fixtures (:data:`REVIEW_READY` lists the four review-ready ones):

* ``single_branch_commit_to_target`` / ``single_branch_minted``: built on
  ``tests/integration/single_branch_window_support.build_template``; WP01 implements, commits once
  into WP02's owned paths and is approved; WP02 makes two implementation commits and one
  out-of-map commit and is submitted. On commit-to-target a WP03 commit lands after WP02's
  submission, so the branch has moved one commit past the submitted tip.
* ``lanes_with_coord``: WP01 and WP02 on one lane (the terminus builders); the review is opened
  from the repository root checkout. ``lanes``: the same Mission re-declared ``lanes``.
* ``lanes_stamp_stripped``: ``lanes`` with every ``lane_head`` / ``wp_window`` key removed from
  WP02's events, so its range is genuinely unavailable (a code-lane work package never uses event commits).

:func:`make_owned_range_unavailable` is the owned-checkout variant for the operator ruling Q7
cells: it strips an owned WP's stamps, drops its claim-base ref and makes its event commits
unresolvable, so the owned checkout's scoped range is genuinely unavailable.

Public helpers for both acceptance files: :func:`review_block`, :func:`run_printed_command`,
:func:`assert_no_patch_text` (the C-001 detector) and :func:`snapshot_tree`.

Templates are built once per test module (:class:`ReviewTemplates`) and copied per test.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status.models import Lane, StatusEvent
from tests._factories import provision_test_charter
from tests._support.status_seed import seed_status_event
from tests.consolidation import characterization_support as cs
from tests.integration import single_branch_window_support as sb
from tests.terminus.canceled_dependency_support import ACTOR, _approve, _commit_in
from tests.terminus.conftest import (
    _commit_planning_artifacts,
    _cut_coord_branch,
    _finish_coord_mission,
    _init_fixture_repo,
    _now_iso,
    _write_meta,
    pin_planning_commit,
)
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.mixed_lane_support import transition

__all__ = [
    "BASE_WINDOW_OPEN",
    "CITED_REFS",
    "DECLARED_TEXTS",
    "HARNESS_VARIABLES",
    "REVIEWED_WP",
    "REVIEW_READY",
    "TIP_SUBMISSION",
    "ReviewFixture",
    "ReviewTemplates",
    "assert_no_patch_text",
    "make_owned_range_unavailable",
    "recorded_window_ends",
    "review_block",
    "run_printed_command",
    "snapshot_tree",
    "strip_single_branch_stamps",
    "submitted_planning_lane_wp",
    "strip_stamps",
]

REVIEWED_WP = "WP02"
REVIEW_READY = ("single_branch_commit_to_target", "single_branch_minted", "lanes", "lanes_with_coord")

#: The provenance labels of a fully recorded range (contract ``review-context-block.md``).
BASE_WINDOW_OPEN = "window open"
TIP_SUBMISSION = "for_review submission"

#: WP02's ``requirement_refs``: a declared FR, a declared NFR, an ID the spec lacks, another Mission's ID.
CITED_REFS = ("FR-001", "NFR-001", "C-009", "other-mission#FR-002")
DECLARED_TEXTS = {"FR-001": "Things work.", "NFR-001": "Responses stay fast."}
SPEC_TEXT = "# Spec\n\n## Requirements\n\n- **FR-001**: Things work.\n- **NFR-001**: Responses stay fast.\n"

#: Agent containers export these; the code under test reads them, so the fixtures unset them (CLAUDE.md gotcha 5).
HARNESS_VARIABLES = (
    "SPEC_KITTY_NO_NAG",
    "SPEC_KITTY_NON_INTERACTIVE",
    "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS",
    "SPECIFY_REPO_ROOT",
)

_EVENTS = "status.events.jsonl"
_STAMP_KEYS = ("lane_head", "wp_window")
_OUT_OF_MAP = "docs/wp02-notes.md"
_PATCH_PREFIXES = ("diff --git", "@@ ", "+++ ", "--- a/")
_UNAVAILABLE_GAP = "not_recorded"

# single_branch shape
_SB_WP02_OWNED = "src/m2/"
_SB_LANE_MATE = "src/m2/from_wp01.py"
_SB_WP03 = "src/m3/real.py"

# lane shape
_LANE_WP01_PATH = "src/pkg/wp01.py"
_LANE_WP02_OWNED = "src/pkg/wp02/**"
_LANE_LANE_MATE = "src/pkg/wp02/seed.py"


# --------------------------------------------------------------------------- the fixture value


@dataclass(frozen=True)
class ReviewFixture:
    """A review-ready Mission copy plus the facts its review range must reproduce.

    ``repo`` is the repository root checkout the review is opened from. ``changed_files`` are the
    exact ``CHANGED FILES`` lines (``+<a> -<r>  <path>``). ``excluded_shas`` / ``excluded_paths``
    must never appear in the review range or its printed commands' output.
    ``unavailable_reason`` is set only for a fixture whose range is unavailable.
    """

    name: str
    root: Path
    repo: Path
    mission_slug: str
    wp_id: str
    implementation_shas: tuple[str, ...]
    changed_files: tuple[str, ...]
    out_of_map_paths: tuple[str, ...]
    out_of_map_only_commits: int
    excluded_shas: tuple[str, ...]
    excluded_paths: tuple[str, ...]
    status: str
    base_label: str
    tip_label: str
    moved_past: int
    expected_base: str | None = None
    expected_tip: str | None = None
    unavailable_reason: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    lane_mission: cs.ShapeMission | None = None

    @property
    def feature_dir(self) -> Path:
        return self.repo / "kitty-specs" / self.mission_slug

    def environment_variables(self) -> dict[str, str]:
        """The CLI environment of this copy (HOME / XDG isolation and the no-upgrade-check switch)."""
        return dict(self.env)

    @contextlib.contextmanager
    def environment(self) -> Iterator[pytest.MonkeyPatch]:
        """``chdir`` into :attr:`repo` with :meth:`environment_variables` set and the harness variables unset."""
        if self.lane_mission is not None:
            cs._ensure_bootstrapped_home(self.lane_mission.home)
        with pytest.MonkeyPatch.context() as patch:
            patch.chdir(self.repo)
            for key in HARNESS_VARIABLES:
                patch.delenv(key, raising=False)
            patch.delenv("SPEC_KITTY_ORIGIN_CHECK", raising=False)
            for key, value in self.environment_variables().items():
                patch.setenv(key, value)
            yield patch

    def rebased(self, dest_root: Path) -> ReviewFixture:
        """This fixture's facts on a copy of its whole root at *dest_root*."""
        if self.lane_mission is not None:
            copied = cs.copy_mission(self.lane_mission, dest_root)
            return replace(self, root=copied.root, repo=copied.repo, env=_lane_env(copied), lane_mission=copied)
        shutil.copytree(self.root, dest_root, symlinks=True)
        return replace(self, root=dest_root, repo=dest_root / "repo", env=_sb_env(dest_root))


def _sb_env(root: Path) -> dict[str, str]:
    return {key: value for key, value in sb.cli_env(root).items() if key.startswith(("HOME", "XDG_", "SPEC_KITTY_"))}


def _lane_env(mission: cs.ShapeMission) -> dict[str, str]:
    return {"HOME": str(mission.home), "SPEC_KITTY_NO_UPGRADE_CHECK": "1", **mission.env}


# --------------------------------------------------------------------------- public helpers


_BLOCK_START = "REVIEW RANGE ("
_BLOCK_END_MARKERS = ("", "=" * 78)


def review_block(text: str) -> str:
    """The review-context block of *text*: from the ``REVIEW RANGE`` line through the last cited-requirement line.

    The block ends at the first blank line after ``CITED REQUIREMENTS:`` (the renderer follows it with a
    blank line and the anti-pattern checklist). Returns ``""`` when *text* carries no block.
    """
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith(_BLOCK_START)), None)
    if start is None:
        return ""
    block: list[str] = []
    seen_requirements = False
    for line in lines[start:]:
        if seen_requirements and line in _BLOCK_END_MARKERS:
            break
        seen_requirements = seen_requirements or line == "CITED REQUIREMENTS:"
        block.append(line)
    return "\n".join(block)


def run_printed_command(repo: Path, line: str) -> str:
    """Run one printed review command exactly as written, through ``bash -c`` in *repo* (``check=True``)."""
    proc = subprocess.run(["bash", "-c", line.strip()], cwd=repo, check=True, capture_output=True, text=True)
    return proc.stdout


def assert_no_patch_text(text: str) -> None:
    """The C-001 detector: no line of *text* starts like unified-diff patch text."""
    offending = [line for line in text.splitlines() if line.startswith(_PATCH_PREFIXES)]
    assert not offending, f"patch text found (C-001): {offending[:3]}"


def snapshot_tree(path: Path) -> dict[str, bytes]:
    """Every regular file under *path* (``.git`` excluded) as ``relative path -> bytes``."""
    snapshot: dict[str, bytes] = {}
    for directory, subdirectories, files in os.walk(path):
        subdirectories[:] = sorted(name for name in subdirectories if name != ".git")
        for name in files:
            full = Path(directory) / name
            if full.is_file() and not full.is_symlink():
                snapshot[str(full.relative_to(path))] = full.read_bytes()
    return snapshot


def _strip_rows(rows: list[dict[str, Any]], wp_id: str) -> list[dict[str, Any]]:
    stripped = []
    for row in rows:
        metadata = row.get("policy_metadata") or {}
        if row.get("wp_id") == wp_id and metadata:
            row = {**row, "policy_metadata": {key: value for key, value in metadata.items() if key not in _STAMP_KEYS} or None}
        stripped.append(row)
    return stripped


def strip_stamps(fixture: ReviewFixture, wp_id: str = REVIEWED_WP) -> None:
    """Remove every ``lane_head`` / ``wp_window`` key from *wp_id*'s events in every copy of the log, committed."""
    if fixture.lane_mission is not None:

        def _edit(event: dict[str, Any]) -> dict[str, Any] | None:
            metadata = event.get("policy_metadata") or {}
            if event.get("wp_id") != wp_id or not any(key in metadata for key in _STAMP_KEYS):
                return None
            return _strip_rows([event], wp_id)[0]

        cs.rewrite_events(fixture.lane_mission, _edit, f"test: strip {wp_id}'s stamps")
        return
    strip_single_branch_stamps(fixture.repo, fixture.feature_dir, wp_id)


def strip_single_branch_stamps(repo: Path, feature_dir: Path, wp_id: str) -> None:
    """Remove every ``lane_head`` / ``wp_window`` key from *wp_id*'s events in a ``single_branch`` Mission's log, committed.

    The result is a log as it was before the stamps existed, e.g. a commit-to-target Mission recorded before #7578.
    """
    log = feature_dir / _EVENTS
    _write_rows(log, _strip_rows(_read_rows(log), wp_id))
    sb.git(repo, "add", "-A", "kitty-specs")
    sb.git(repo, "commit", "-qm", f"test: strip {wp_id}'s stamps")


def _read_rows(log: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_owned_range_unavailable(owned_root: Path, mission_dir: Path, mission_slug: str, wp_id: str, *, ambiguous: bool = False) -> None:
    """Make an owned (``single_branch``) checkout's scoped review range for *wp_id* genuinely unavailable.

    Strips *wp_id*'s ``lane_head`` / ``wp_window`` stamps (committed) and drops its ``wp-base``
    claim-base ref, so neither end of the range has a recorded value or a claim-base ref; then its
    ``claimed`` and ``for_review`` events lose their event commits:

    * default: their ids are rewritten to ids no commit introduced (left uncommitted);
    * ``ambiguous=True``: their lines are removed and re-added in two commits, so several commits
      introduced each event.

    The work package still reduces to ``for_review``.
    """
    log = mission_dir / _EVENTS
    rows = _strip_rows(_read_rows(log), wp_id)
    _write_rows(log, rows)
    sb.git(owned_root, "add", "-A")
    sb.git(owned_root, "commit", "-qm", f"test: strip {wp_id}'s stamps")
    subprocess.run(
        ["git", "update-ref", "-d", f"refs/spec-kitty/wp-base/{mission_slug}/{wp_id}"],
        cwd=owned_root,
        check=False,
        capture_output=True,
    )
    ends = [row for row in rows if row.get("wp_id") == wp_id and row.get("to_lane") in ("claimed", "for_review")]
    if ambiguous:
        _write_rows(log, [row for row in rows if row not in ends])
        sb.git(owned_root, "commit", "-qam", f"test: remove {wp_id}'s claim and submission lines")
        _write_rows(log, rows)
        sb.git(owned_root, "commit", "-qam", f"test: re-add {wp_id}'s claim and submission lines")
        return
    fresh = iter(("01KW2E7B0NCMMTC1A1MZZZZZZ1", "01KW2E7B0NCMMTC1A1MZZZZZZ2"))
    for row in ends:
        row["event_id"] = next(fresh, row["event_id"])
    # Deliberately NOT committed: the fresh ids live only in the working tree.
    _write_rows(log, rows)


def recorded_window_ends(events_log: Path, wp_id: str = REVIEWED_WP) -> tuple[str, str]:
    """*wp_id*'s recorded window open (first ``claimed``) and submitted tip (last ``for_review`` ``lane_head``), read from *events_log*."""
    return _window_ends(_read_rows(events_log), wp_id)


def _write_rows(log: Path, rows: list[dict[str, Any]]) -> None:
    log.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


# --------------------------------------------------------------------------- planning lane (operator ruling Q10)


_PLANNING_WP = "WP02"
_PLANNING_AT = {
    Lane.CLAIMED: "2026-11-12T00:00:01+00:00",
    Lane.IN_PROGRESS: "2026-11-12T00:00:02+00:00",
    Lane.FOR_REVIEW: "2026-11-12T00:00:03+00:00",
}


@dataclass(frozen=True)
class PlanningLaneSubmission:
    """A submitted planning-lane work package of a ``lanes`` Mission and the commits its derived range reads."""

    repo: Path
    slug: str
    wp_id: str
    owned_files: tuple[str, ...]
    claim: str
    work: str
    work_path: str
    tip: str


def _seed_planning_event(repo: Path, feature_dir: Path, slug: str, from_lane: Lane, to_lane: Lane) -> str:
    """Append one unstamped planning-WP transition to the repository root log and commit it alone (as ``move-task`` does)."""
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"01M77Q10{to_lane.value.upper().replace('_', '')}".ljust(26, "A")[:26],
            mission_slug=slug,
            wp_id=_PLANNING_WP,
            from_lane=from_lane,
            to_lane=to_lane,
            at=_PLANNING_AT[to_lane],
            actor="tester",
            force=True,
            execution_mode="direct_repo",
        ),
    )
    cs._git(repo, "add", "-A", "kitty-specs")
    cs._git(repo, "commit", "-qm", f"chore(spec-kitty): {_PLANNING_WP} {to_lane.value}")
    return cs._git(repo, "rev-parse", "HEAD")


def submitted_planning_lane_wp(tmp_path: Path) -> PlanningLaneSubmission:
    """A ``lanes`` Mission whose planning-lane WP02 is claimed, commits its research on the target and is submitted.

    The planning lane is never stamped (C-009), so none of WP02's events carries a stamp; each
    transition is committed alone on the target branch, where the planning work lands too.
    """
    mission = build_lanes_mission(tmp_path, wps=("WP01",), with_planning_lane_wp=True, approve_planning_wp=False, mid8="01M77Q10")
    claim = _seed_planning_event(mission.repo, mission.feature_dir, mission.slug, Lane.PLANNED, Lane.CLAIMED)
    work_path = f"kitty-specs/{mission.slug}/research/{_PLANNING_WP}.md"
    (mission.repo / work_path).parent.mkdir(parents=True, exist_ok=True)
    (mission.repo / work_path).write_text(f"# {_PLANNING_WP} research\n", encoding="utf-8")
    cs._git(mission.repo, "add", "-A", "kitty-specs")
    cs._git(mission.repo, "commit", "-qm", f"docs: {_PLANNING_WP} research")
    work = cs._git(mission.repo, "rev-parse", "HEAD")
    _seed_planning_event(mission.repo, mission.feature_dir, mission.slug, Lane.CLAIMED, Lane.IN_PROGRESS)
    tip = _seed_planning_event(mission.repo, mission.feature_dir, mission.slug, Lane.IN_PROGRESS, Lane.FOR_REVIEW)
    return PlanningLaneSubmission(
        repo=mission.repo,
        slug=mission.slug,
        wp_id=_PLANNING_WP,
        owned_files=(f"kitty-specs/{mission.slug}/research/**",),
        claim=claim,
        work=work,
        work_path=work_path,
        tip=tip,
    )


# --------------------------------------------------------------------------- single_branch builders


def _set_requirement_refs(wp_file: Path) -> None:
    text = wp_file.read_text(encoding="utf-8")
    refs = "requirement_refs:\n" + "".join(f"- {ref}\n" for ref in CITED_REFS)
    replaced = re.sub(r"requirement_refs:(?: \[[^\]]*\]\n|\n(?:\s*- [^\n]*\n)+)", refs, text, count=1)
    assert replaced != text, f"fixture precondition: no requirement_refs in {wp_file}"
    wp_file.write_text(replaced, encoding="utf-8")


def _sb_prepare_planning(m: sb.Mission) -> None:
    feature_dir = m.repo / "kitty-specs" / m.slug
    (feature_dir / "spec.md").write_text(SPEC_TEXT, encoding="utf-8")
    wp02 = next((feature_dir / "tasks").glob("WP02*.md"))
    _set_requirement_refs(wp02)
    sb.git(m.repo, "add", "-A", "kitty-specs")
    sb.git(m.repo, "commit", "-qm", "test: WP02 cites four requirements")


def _window_ends(rows: list[dict[str, Any]], wp_id: str = REVIEWED_WP) -> tuple[str, str]:
    """WP02's recorded window open (first ``claimed``) and submitted tip (last ``for_review`` ``lane_head``), read from the log."""
    mine = [row for row in rows if row.get("wp_id") == wp_id]
    opener = next(row for row in mine if row.get("to_lane") == "claimed")
    submission = [row for row in mine if row.get("to_lane") == "for_review"][-1]
    return str(opener["policy_metadata"]["wp_window"]["open_sha"]), str(submission["policy_metadata"]["lane_head"])


def _numstat_line(added: int, path: str) -> str:
    return f"+{added} -0  {path}"


def _build_single_branch(base: Path, *, commit_to_target: bool) -> ReviewFixture:
    repo, slug = sb.build_template(base, commit_to_target=commit_to_target)
    m = sb.Mission(repo, slug, base)
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(repo)
        for key, value in _sb_env(base).items():
            patch.setenv(key, value)
        for key in HARNESS_VARIABLES:
            patch.delenv(key, raising=False)
        _sb_prepare_planning(m)
        sb.claim(m, "WP01")
        wp01_work = sb.implement(m, "WP01")
        lane_mate = sb.commit_file(m, _SB_LANE_MATE, "FROM_WP01 = True\n", "feat(WP01): seed an m2 helper")
        sb.submit(m, "WP01")
        sb.approve(m, "WP01")
        sb.claim(m, "WP02")
        first = sb.commit_file(m, f"{_SB_WP02_OWNED}real.py", "VALUE = 'WP02'\nREVISION = 1\n", "feat(WP02): implement m2")
        second = sb.commit_file(m, f"{_SB_WP02_OWNED}extra.py", "A = 1\nB = 2\nC = 3\n", "feat(WP02): extra m2 helpers")
        sb.commit_file(m, _OUT_OF_MAP, "notes\n", "docs(WP02): notes outside the owned files")
        sb.submit(m, "WP02")
        later: tuple[str, ...] = ()
        if commit_to_target:
            later = (sb.commit_file(m, _SB_WP03, "VALUE = 'WP03'\n", "feat(WP03): implement m3"),)
    return ReviewFixture(
        name="single_branch_commit_to_target" if commit_to_target else "single_branch_minted",
        root=base,
        repo=repo,
        mission_slug=slug,
        wp_id=REVIEWED_WP,
        implementation_shas=(first, second),
        changed_files=(_numstat_line(3, f"{_SB_WP02_OWNED}extra.py"), _numstat_line(2, f"{_SB_WP02_OWNED}real.py")),
        out_of_map_paths=(_OUT_OF_MAP,),
        out_of_map_only_commits=1,
        excluded_shas=(wp01_work, lane_mate, *later),
        excluded_paths=("src/m1/real.py", _SB_LANE_MATE, *((_SB_WP03,) if later else ())),
        status="recorded",
        base_label=BASE_WINDOW_OPEN,
        tip_label=TIP_SUBMISSION,
        moved_past=len(later),
        expected_base=_window_ends(_read_rows(m.repo / "kitty-specs" / slug / _EVENTS))[0],
        expected_tip=_window_ends(_read_rows(m.repo / "kitty-specs" / slug / _EVENTS))[1],
        env=_sb_env(base),
    )


# --------------------------------------------------------------------------- lane builders


def _lane_wp_file(wp: str, owned: str, refs: tuple[str, ...]) -> str:
    refs_yaml = "".join(f"- {ref}\n" for ref in refs)
    return f"---\nwork_package_id: {wp}\ntitle: {wp} work\ndependencies: []\nsubtasks: []\nrequirement_refs:\n{refs_yaml}owned_files:\n- {owned}\n---\n# {wp}\n"


def _bootstrap_lane(tmp_path: Path, *, mid8: str) -> tuple[Any, LanesManifest]:
    """One coordination Mission whose one code lane ``lane-a`` holds WP01 and WP02 (WP02 cites :data:`CITED_REFS`)."""
    slug = f"review-range-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch="main")
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01", "WP02"),
                write_scope=("src/pkg",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=_now_iso(),
        computed_from="review-range-fixture",
    )
    write_lanes_json(mission.feature_dir, manifest)
    pin_planning_commit(mission.repo, mission.feature_dir)
    tasks = mission.feature_dir / "tasks"
    (tasks / "WP01-work.md").write_text(_lane_wp_file("WP01", _LANE_WP01_PATH, ("FR-001",)), encoding="utf-8")
    (tasks / "WP02-work.md").write_text(_lane_wp_file("WP02", _LANE_WP02_OWNED, CITED_REFS), encoding="utf-8")
    (mission.feature_dir / "spec.md").write_text(SPEC_TEXT, encoding="utf-8")
    (mission.feature_dir / _EVENTS).write_text("", encoding="utf-8")
    provision_test_charter(mission.repo)
    cs._git(mission.repo, "add", "-f", "--", ".kittify/charter/activation.yaml")
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap the review-range Mission")
    _cut_coord_branch(mission)
    _finish_coord_mission(mission)
    return mission, read_lanes_json(mission.feature_dir) or manifest


def _build_lanes_with_coord(base: Path) -> ReviewFixture:
    mission, manifest = _bootstrap_lane(base, mid8="01M77R05")
    slug = mission.slug
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    wp01_work = _commit_in(tree, _LANE_WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
    lane_mate = _commit_in(tree, _LANE_LANE_MATE, "SEED = True\n", f"feat({slug}): WP01 seeds a WP02 helper")
    _approve(mission, "WP01", reference="review-WP01")
    transition(mission, "WP02", "planned", actor=ACTOR)
    transition(mission, "WP02", "claimed", actor=ACTOR)
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP02", manifest)
    transition(mission, "WP02", "in_progress", actor=ACTOR)
    first = _commit_in(tree, "src/pkg/wp02/impl.py", "def wp02() -> int:\n    return 2\n", f"feat({slug}): WP02 work")
    second = _commit_in(tree, "src/pkg/wp02/extra.py", "A = 1\nB = 2\nC = 3\n", f"feat({slug}): WP02 extra helpers")
    _commit_in(tree, _OUT_OF_MAP, "notes\n", f"docs({slug}): WP02 notes outside the owned files")
    transition(mission, "WP02", "for_review", actor=ACTOR, subtasks_complete=True)
    mission.lane_branches.update({"WP01": branch, "WP02": branch})
    shape = cs._from_coord(mission, "coord", subject_wp="WP02", window_wps=("WP01", "WP02"))
    return ReviewFixture(
        name="lanes_with_coord",
        root=shape.root,
        repo=shape.repo,
        mission_slug=slug,
        wp_id=REVIEWED_WP,
        implementation_shas=(first, second),
        changed_files=(_numstat_line(3, "src/pkg/wp02/extra.py"), _numstat_line(2, "src/pkg/wp02/impl.py")),
        out_of_map_paths=(_OUT_OF_MAP,),
        out_of_map_only_commits=1,
        excluded_shas=(wp01_work, lane_mate),
        excluded_paths=(_LANE_WP01_PATH, _LANE_LANE_MATE),
        status="recorded",
        base_label=BASE_WINDOW_OPEN,
        tip_label=TIP_SUBMISSION,
        moved_past=0,
        expected_base=_window_ends(cs._events(shape))[0],
        expected_tip=_window_ends(cs._events(shape))[1],
        env=_lane_env(shape),
        lane_mission=shape,
    )


def _adapt_to_lanes(fixture: ReviewFixture) -> ReviewFixture:
    """Re-declare a coordination Mission ``lanes``: drop the coordination branch and read the repository root log."""
    meta_path = fixture.feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["topology"] = "lanes"
    meta.pop("coordination_branch", None)
    coord_log = next(log for log in cs._event_logs(fixture.repo) if log.parent != fixture.feature_dir)
    shutil.copyfile(coord_log, fixture.feature_dir / _EVENTS)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cs._git(fixture.repo, "add", "-A", "kitty-specs")
    cs._git(fixture.repo, "commit", "-qm", "test: declare the Mission lanes")
    return replace(fixture, name="lanes")


# --------------------------------------------------------------------------- templates


class ReviewTemplates:
    """Builds each fixture template once (on first use) and hands out per-test copies."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._built: dict[str, ReviewFixture] = {}

    def checkout(self, name: str, dest: Path) -> ReviewFixture:
        """A fresh copy of fixture *name* under *dest* (the template itself is never touched)."""
        return self._template(name).rebased(dest / name)

    def _template(self, name: str) -> ReviewFixture:
        if name not in self._built:
            self._built[name] = self._build(name)
        return self._built[name]

    def _build(self, name: str) -> ReviewFixture:
        root = self._root / name
        if name == "single_branch_commit_to_target":
            return _build_single_branch(root, commit_to_target=True)
        if name == "single_branch_minted":
            return _build_single_branch(root, commit_to_target=False)
        if name == "lanes_with_coord":
            return _build_lanes_with_coord(root)
        if name == "lanes":
            return _adapt_to_lanes(self.checkout("lanes_with_coord", self._root / "src-lanes"))
        if name == "lanes_stamp_stripped":
            fixture = self.checkout("lanes", self._root / "src-stripped")
            strip_stamps(fixture)
            return replace(
                fixture,
                name=name,
                implementation_shas=(),
                expected_base=None,
                expected_tip=None,
                changed_files=(),
                status="unavailable",
                base_label="",
                tip_label="",
                unavailable_reason=_UNAVAILABLE_GAP,
            )
        raise ValueError(f"unknown review fixture {name!r}")
