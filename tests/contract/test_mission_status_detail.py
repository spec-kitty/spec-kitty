"""Tests of the reference work package detail reader of the ``mission-status`` contract (FR-001 to FR-008, FR-016, FR-020, FR-022).

Every rule of ``_mission_status_detail`` has a test with a clean twin: a negative case alone would pass against a
reader that refuses everything, so each refusal is paired with the accepted form of the same shape. Missions are
written at run time into a temporary directory, so no committed Mission is read and nothing under ``kitty-specs/``
of this checkout is touched. Leaking values (host paths, addresses, credentials) are assembled from fragments, so
this source holds none of them as a literal. Real git is used only in the change-state matrix, in a scratch
repository with a scratch HOME.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import json
import os
import re
import shutil
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from kernel.git import GitCommandError, GitPath, status_entries
from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent.tasks_move_task import _mt_matches_owned_file
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from specify_cli.policy.commit_guard import _matches_any_glob
from tests._factories.coord_mission import make_coord_mission
from tests.contract import _mission_status_artifacts as art
from tests.contract import _mission_status_detail as det
from tests.contract import _mission_status_payloads as helper

pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "contracts" / "mission-status"
MISSION = "alpha-mission"
MISSION_ID = helper.fixture_ulid(1)
BODY_TEXT = "# Body\n"
FAULT_NOT_FIRED = "the injected fault did not fire"
INJECTED_FAULT = "injected fault"


@pytest.fixture(scope="module")
def tools() -> Iterator[helper.ContractTools]:
    with pytest.MonkeyPatch.context() as mp:
        yield helper.load_contract_tools(mp, REPO_ROOT)


@dataclass
class Fired:
    """How often an injected fault fired; a test that expects it fails, never skips, at zero."""

    count: int = 0


def _ctx(root: Path, tools: helper.ContractTools, fs: art.FileSystem = art.REAL_FS) -> art.ReaderContext:
    return art.ReaderContext(repo_root=root, tools=tools, fs=fs)


def _frontmatter(wp_id: str | None, **fields: Any) -> str:
    """The text of a work package file: a frontmatter block with the id and a title, then a body."""
    header: dict[str, Any] = {} if wp_id is None else {"work_package_id": wp_id, "title": f"Title of {wp_id}"}
    header.update(fields)
    return "---\n" + yaml.safe_dump(header, sort_keys=True) + "---\n\n" + BODY_TEXT


def _put(mission_dir: Path, files: Mapping[str, str | bytes]) -> None:
    """Write ``files`` (relative path to text or bytes) below ``mission_dir``, creating directories."""
    for relative, content in files.items():
        target = mission_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")


def _build(root: Path, files: Mapping[str, str | bytes] | None = None) -> Path:
    """One fixture Mission under ``root`` (no work package yet) with the given files; returns its directory."""
    mission_dir = helper.write_fixture_mission(root, MISSION)
    _put(mission_dir, files or {})
    return mission_dir


def _detail(ctx: art.ReaderContext, wp_id: str, host: det.HostCapability = det.NO_WORKTREES) -> det.DetailOutcome:
    return det.build_work_package_detail(ctx, MISSION_ID, wp_id, host)


_WIRED: dict[str, Any] = {}


@pytest.fixture(scope="module", autouse=True)
def _wired(tools: helper.ContractTools) -> Iterator[None]:
    """The resolved contract and the tools, for the helpers that check every outcome a test builds."""
    _WIRED["tools"] = tools
    _WIRED["contract"] = helper.Contract(tools, MODULE_DIR)
    yield
    _WIRED.clear()


def _ok(outcome: det.DetailOutcome) -> dict[str, Any]:
    """The body of a 200, after checking what every detail built must satisfy: the schema, no leak, and the invariants."""
    assert outcome.status == 200, f"the detail answered {outcome.status} {outcome.body.get('code')}"
    body = outcome.body
    assert _WIRED["contract"].errors(helper.SCHEMA_WORK_PACKAGE_DETAIL, body) == []
    assert helper.payload_leaks(body, _WIRED["tools"]) == []
    assert det.invariant_problems(body) == []
    return body


def _refused(outcome: det.DetailOutcome, status: int, code: str) -> None:
    assert (outcome.status, outcome.body.get("code")) == (status, code), f"{outcome.status} {outcome.body}"
    assert _WIRED["contract"].errors(helper.SCHEMA_DETAIL_REFUSAL, outcome.body) == [], "a refusal is a WorkPackageDetailRefusal"


# ---------------------------------------------------------------------------
# Work package identity (D-P6, OD-3): which file is authored, which ids exist
# ---------------------------------------------------------------------------


def test_an_id_held_by_two_files_is_served_by_the_first_regular_file_in_byte_order(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(
        tmp_path,
        {
            "tasks/WP01-b-second.md": _frontmatter("WP01", owned_files=["second/**"]),
            "tasks/WP01-a-first.md": _frontmatter("WP01", owned_files=["first/**"]),
        },
    )
    ctx = _ctx(tmp_path, tools)
    assert det.work_package_universe(ctx, mission_dir) == ["WP01"], "an id held by two files is one work package"
    body = _ok(_detail(ctx, "WP01"))
    assert [entry["pattern"] for entry in body["ownedFiles"]] == ["first/**"], "the first file in byte order is the authored file"
    assert body["artifactReferences"]["prompt"] == {"path": "tasks/WP01-a-first.md", "kind": "work_package_prompt"}


def test_a_symlinked_work_package_file_is_skipped_and_its_id_is_not_found_unless_a_regular_file_holds_it(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"elsewhere/WP05-real.md": _frontmatter("WP05"), "tasks/WP06-regular.md": _frontmatter("WP06")})
    (mission_dir / "tasks" / "WP05-link.md").symlink_to(mission_dir / "elsewhere" / "WP05-real.md")
    ctx = _ctx(tmp_path, tools)
    assert det.work_package_universe(ctx, mission_dir) == ["WP06"], "a symlinked work package file is skipped like an unparseable one"
    _refused(_detail(ctx, "WP05"), 404, "not_found")
    _ok(_detail(ctx, "WP06"))
    _put(mission_dir, {"tasks/WP05-zzz-regular.md": _frontmatter("WP05")})
    assert det.work_package_universe(ctx, mission_dir) == ["WP05", "WP06"], "a regular file holding the id makes it a work package"
    _ok(_detail(ctx, "WP05"))


def test_a_file_whose_name_prefix_and_frontmatter_id_disagree_is_keyed_by_the_frontmatter_id(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"tasks/WP07-misnamed.md": _frontmatter("WP08")})
    ctx = _ctx(tmp_path, tools)
    assert det.work_package_universe(ctx, mission_dir) == ["WP08"]
    _refused(_detail(ctx, "WP07"), 404, "not_found")
    body = _ok(_detail(ctx, "WP08"))
    assert body["wpId"] == "WP08"
    assert body["artifactReferences"]["prompt"] is None, "the prompt file is keyed by name, and no file name starts with WP08 and a hyphen"


def test_a_notes_file_carrying_a_valid_id_is_a_work_package_without_a_prompt(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"tasks/WP-notes.md": _frontmatter("WP09"), "tasks/WP-other.md": _frontmatter(None)})
    ctx = _ctx(tmp_path, tools)
    assert det.work_package_universe(ctx, mission_dir) == ["WP09"], "a notes file with no valid id is not a work package"
    body = _ok(_detail(ctx, "WP09"))
    assert body["artifactReferences"]["prompt"] is None
    assert body["reviewCycles"] == [], "a work package with no prompt file has no review cycle directory"
    _refused(_detail(ctx, "WP-notes"), 404, "not_found")


def test_a_directory_named_like_a_work_package_file_is_skipped_and_never_raises(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"tasks/WP02-fine.md": _frontmatter("WP02")})
    (mission_dir / "tasks" / "WP01.md").mkdir()
    ctx = _ctx(tmp_path, tools)
    assert det.work_package_universe(ctx, mission_dir) == ["WP02"]
    _refused(_detail(ctx, "WP01"), 404, "not_found")
    _ok(_detail(ctx, "WP02"))


def test_a_file_with_unparseable_frontmatter_is_skipped_and_the_others_still_answer(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(
        tmp_path,
        {"tasks/WP01-broken.md": "---\nwork_package_id: [unclosed\n---\n", "tasks/WP02-fine.md": _frontmatter("WP02"), "tasks/WP03-bare.md": "no frontmatter\n"},
    )
    ctx = _ctx(tmp_path, tools)
    assert det.work_package_universe(ctx, mission_dir) == ["WP02"]
    _refused(_detail(ctx, "WP01"), 404, "not_found")
    _ok(_detail(ctx, "WP02"))


# ---------------------------------------------------------------------------
# Shared fixtures: Missions with work packages, status rows, leaking values assembled from fragments
# ---------------------------------------------------------------------------

STAMP = "2026-09-01T10:{minute}:00+00:00".format
SLASH = chr(47)
FIXTURE_TASKS = """# Tasks

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Table title | WP01 | |
| T004 | | WP01 | |
| T006 | Belongs to the next package | WP02 | |

## WP01 - Work

- [ ] T002 Checkbox title
- [x] T003 [P] **Bold parallel title**
- [ ] T005 First row wins
- [ ] T005 Second row is ignored
- [ ] T009 ****

## WP02 - Next

- [ ] T007 Other package title
"""


def _email() -> str:
    return "someone" + chr(64) + "example.invalid"


def _home_path(tail: str = "project") -> str:
    return SLASH + "home" + SLASH + "someone" + SLASH + tail


def _token() -> str:
    return "gh" + "p" + chr(95) + "a" * 36


def _planned(number: int, wp_id: str) -> dict[str, Any]:
    return helper.transition_row(number, wp_id, "genesis", "planned", at=STAMP(minute="05"), actor="finalize-tasks")


def _mission(
    root: Path,
    work_packages: Mapping[str, Mapping[str, Any]],
    *,
    tasks_md: str | bytes | None = None,
    rows: list[dict[str, Any]] | None = None,
    files: Mapping[str, str | bytes] | None = None,
    lanes: Mapping[str, Any] | None = None,
) -> Path:
    """A fixture Mission with the given work packages; every work package that has no row of its own is planned."""
    events = list(rows) if rows is not None else [_planned(number, wp_id) for number, wp_id in enumerate(work_packages, start=1)]
    mission_dir = helper.write_fixture_mission(root, MISSION, work_packages=work_packages, rows=events, lanes=lanes)
    if isinstance(tasks_md, bytes):
        (mission_dir / "tasks.md").write_bytes(tasks_md)
    elif tasks_md is not None:
        (mission_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")
    _put(mission_dir, files or {})
    return mission_dir


def _titles(body: Mapping[str, Any]) -> dict[str, str | None]:
    return {entry["id"]: entry["title"] for entry in body["subtasks"]}


# ---------------------------------------------------------------------------
# Subtask titles and lanes (FR-003)
# ---------------------------------------------------------------------------

ROSTER = ["T001", "T002", "T003", "T004", "T005", "T006", "T008", "T009"]


def test_subtask_titles_come_from_both_row_formats_and_the_roster_keeps_its_authored_order(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {"subtasks": ROSTER}, "WP02": {}}, tasks_md=FIXTURE_TASKS)
    body = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    assert [entry["id"] for entry in body["subtasks"]] == ROSTER
    assert _titles(body) == {
        "T001": "Table title",
        "T002": "Checkbox title",
        "T003": "Bold parallel title",
        "T004": None,  # a table row with an empty title cell
        "T005": "First row wins",
        "T006": None,  # its table row names another work package
        "T008": None,  # no row at all
        "T009": None,  # a title that is only an empty bold pair
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Plain", "Plain"),
        ("  padded  ", "padded"),
        ("[P] Parallel", "Parallel"),
        ("[P]**Bold parallel**", "Bold parallel"),
        ("**Bold**", "Bold"),
        ("** spaced **", "spaced"),
        ("**", "**"),
        ("****", None),
        ("   ", None),
        ("", None),
        ("[P]", None),
        ("a **inner** b", "a **inner** b"),
        ("**one** and **two**", "one** and **two"),
    ],
)
def test_the_title_cleaning_rule_drops_the_tag_strips_one_bold_pair_and_never_returns_an_empty_string(raw: str, expected: str | None) -> None:
    assert det.clean_title(raw) == expected


def test_a_missing_tasks_file_gives_null_titles_and_never_a_failure(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {"subtasks": ["T001", "T002"]}})
    body = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    assert _titles(body) == {"T001": None, "T002": None}


def test_a_work_package_without_a_subtasks_key_has_an_empty_roster(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}}, tasks_md=FIXTURE_TASKS)
    assert _ok(_detail(_ctx(tmp_path, tools), "WP01"))["subtasks"] == []


def test_an_undecodable_tasks_file_fails_the_read_and_never_gives_null_titles(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {"subtasks": ["T001"]}}, tasks_md=b"| T001 | caf" + bytes([0xE9]) + b" | WP01 |\n")
    _refused(_detail(_ctx(tmp_path, tools), "WP01"), 500, "source_unreadable")


def test_a_subtask_lane_is_the_recorded_state_and_null_when_none_is_recorded(tmp_path: Path, tools: helper.ContractTools) -> None:
    rows = [_planned(1, "WP01"), helper.annotation_row(1, "WP01", {"subtasks": {"T001": "done", "T002": "planned"}}, at=STAMP(minute="07"))]
    _mission(tmp_path, {"WP01": {"subtasks": ["T001", "T002", "T003"]}}, tasks_md=FIXTURE_TASKS, rows=rows)
    body = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    assert {entry["id"]: entry["statusLane"] for entry in body["subtasks"]} == {"T001": "done", "T002": "planned", "T003": None}


def test_a_work_package_with_no_events_has_null_subtask_lanes(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {"subtasks": ["T001"]}}, tasks_md=FIXTURE_TASKS, rows=[])
    body = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    assert body["subtasks"] == [{"id": "T001", "title": "Table title", "statusLane": None}]


def test_a_title_holding_a_credential_is_withheld_and_one_holding_a_path_or_address_is_redacted(tmp_path: Path, tools: helper.ContractTools) -> None:
    tasks_md = (
        "## WP01 - Work\n\n"
        f"- [ ] T001 holds {_token()}\n"
        f"- [ ] T002 holds {_home_path('notes')} and {_email()}\n"
        "- [ ] T003 /tmp burn-down: sync\n"
        "- [ ] T004 ~/.kittify Runtime Centralization\n"
        "- [ ] T005 clean twin\n"
    )
    _mission(tmp_path, {"WP01": {"subtasks": ["T001", "T002", "T003", "T004", "T005"]}}, tasks_md=tasks_md)
    titles = _titles(_ok(_detail(_ctx(tmp_path, tools), "WP01")))
    assert titles["T001"] is None, "a title that holds a credential is withheld"
    assert titles["T002"] == "holds [path] and [email]"
    assert titles["T003"] == "/tmp burn-down: sync", "a real v1 title passes through unchanged"
    assert titles["T004"] == "~/.kittify Runtime Centralization", "a real v1 title passes through unchanged"
    assert titles["T005"] == "clean twin"


def test_rows_inside_a_fence_and_after_the_section_closed_are_not_rows_of_the_work_package(tmp_path: Path, tools: helper.ContractTools) -> None:
    tasks_md = (
        "## WP01 - Work\n\n- [ ] T001 real\n\n```\n- [ ] T002 fenced\n```\n\n"
        "## WP02 - Next\n\n- [ ] T003 other\n\n## WP01 again\n\n- [ ] T004 after the section closed\n"
    )
    _mission(tmp_path, {"WP01": {"subtasks": ["T001", "T002", "T003", "T004"]}, "WP02": {}}, tasks_md=tasks_md)
    assert _titles(_ok(_detail(_ctx(tmp_path, tools), "WP01"))) == {"T001": "real", "T002": None, "T003": None, "T004": None}


# ---------------------------------------------------------------------------
# Dependencies (FR-004)
# ---------------------------------------------------------------------------


def test_a_dependency_carries_its_own_title_and_its_status_lane(tmp_path: Path, tools: helper.ContractTools) -> None:
    rows = [
        _planned(1, "WP01"),
        helper.transition_row(2, "WP01", "planned", "claimed", at=STAMP(minute="06"), actor="claude"),
        _planned(3, "WP02"),
    ]
    _mission(tmp_path, {"WP01": {"title": "Contract slice"}, "WP02": {"dependencies": ["WP01"]}}, rows=rows)
    body = _ok(_detail(_ctx(tmp_path, tools), "WP02"))
    assert body["dependencies"] == [{"wpId": "WP01", "title": "Contract slice", "statusLane": "claimed"}]


def test_a_dependency_without_events_or_without_a_work_package_has_a_null_lane_and_its_id_as_title(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(
        tmp_path,
        {"WP01": {"dependencies": ["WP03", "WP77"]}, "WP03": {"title": "No events"}},
        rows=[_planned(1, "WP01")],
    )
    body = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    assert body["dependencies"] == [
        {"wpId": "WP03", "title": "No events", "statusLane": None},  # a file with no events: no lane is invented
        {"wpId": "WP77", "title": "WP77", "statusLane": None},  # names no work package of the Mission: kept, id as title
    ]


@pytest.mark.parametrize("title", ["", "   ", "\t"])
def test_a_dependency_whose_title_is_empty_or_blank_shows_its_id_and_never_an_empty_string(title: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {"title": title}, "WP02": {"dependencies": ["WP01"]}})
    entry = _ok(_detail(_ctx(tmp_path, tools), "WP02"))["dependencies"][0]
    assert entry["title"] == "WP01"


def test_a_dependency_title_with_a_credential_shows_the_id_and_one_with_a_path_is_redacted(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(
        tmp_path,
        {
            "WP01": {"title": f"holds {_token()}"},
            "WP02": {"title": f"holds {_home_path()} and {_email()}"},
            "WP03": {"title": "clean twin"},
            "WP04": {"dependencies": ["WP01", "WP02", "WP03"]},
        },
    )
    titles = [entry["title"] for entry in _ok(_detail(_ctx(tmp_path, tools), "WP04"))["dependencies"]]
    assert titles == ["WP01", "holds [path] and [email]", "clean twin"]


def test_the_dependency_ids_keep_their_authored_order(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}, "WP02": {}, "WP03": {}, "WP04": {"dependencies": ["WP03", "WP01", "WP02"]}})
    assert [entry["wpId"] for entry in _ok(_detail(_ctx(tmp_path, tools), "WP04"))["dependencies"]] == ["WP03", "WP01", "WP02"]


# ---------------------------------------------------------------------------
# Review cycles (FR-005)
# ---------------------------------------------------------------------------

WP_SLUG = "WP01-fixture"  # the stem of the prompt file ``write_fixture_mission`` writes for WP01
CYCLE_DIR = f"tasks/{WP_SLUG}"
FIRST_POINTER = f"review-cycle://{MISSION}/{WP_SLUG}/review-cycle-1.md"
SECOND_POINTER = f"review-cycle://{MISSION}/{WP_SLUG}/review-cycle-2.md"
OFFSET_TIME = "2026-09-21T09:15:00+00:00"


def _cycle_text(number: int = 1, *, reviewed_at: str = OFFSET_TIME, reviewer: str = "reviewer-renata") -> str:
    header = {"cycle_number": number, "wp_id": "WP01", "mission_slug": MISSION, "reviewer_agent": reviewer, "reviewed_at": reviewed_at, "affected_files": []}
    return "---\n" + yaml.safe_dump(header, sort_keys=True) + "---\n\nFeedback.\n"


def _verdict_row(number: int, reference: str, verdict: str, *, wp_id: str = "WP01") -> dict[str, Any]:
    return helper.transition_row(
        number,
        wp_id,
        "for_review",
        "approved" if verdict == "approved" else "planned",
        at=STAMP(minute=f"{10 + number:02d}"),
        actor="claude",
        review_result={"reviewer": "reviewer-renata", "verdict": verdict, "reference": reference},
    )


def _cycles(root: Path, tools: helper.ContractTools, wp_id: str = "WP01") -> list[dict[str, Any]]:
    return _ok(_detail(_ctx(root, tools), wp_id))["reviewCycles"]


def test_cycles_are_listed_in_ascending_number_not_in_text_order(tmp_path: Path, tools: helper.ContractTools) -> None:
    files = {f"{CYCLE_DIR}/review-cycle-{number}.md": _cycle_text(number) for number in (10, 2, 1)}
    _mission(tmp_path, {"WP01": {}}, files=files)
    assert [cycle["cycleNumber"] for cycle in _cycles(tmp_path, tools)] == [1, 2, 10]


def test_a_work_package_with_no_cycle_file_has_an_empty_list(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}})
    assert _cycles(tmp_path, tools) == []


def test_a_cycle_carries_the_stored_time_the_reviewer_the_pointer_and_the_link(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}}, files={f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text()})
    assert _cycles(tmp_path, tools) == [
        {
            "cycleNumber": 1,
            "reviewedAt": OFFSET_TIME,
            "reviewer": "reviewer-renata",
            "verdict": None,
            "feedbackReference": FIRST_POINTER,
            "artifactPath": f"{CYCLE_DIR}/review-cycle-1.md",
        }
    ]


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("2026-09-21T09:15:00Z", "2026-09-21T09:15:00Z"),
        ("2026-09-21T09:15:00+00:00", "2026-09-21T09:15:00+00:00"),
        ("2026-09-21T09:15:00.123+02:00", "2026-09-21T09:15:00.123+02:00"),
        ("2026-09-21", None),  # date only: null, never midnight
        ("2026-09-21T09:15:00", None),  # no offset
        ("yesterday", None),
    ],
)
def test_the_review_time_is_the_stored_string_only_when_it_is_a_date_time_with_an_offset(
    stored: str, expected: str | None, tmp_path: Path, tools: helper.ContractTools
) -> None:
    _mission(tmp_path, {"WP01": {}}, files={f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text(reviewed_at=stored)})
    assert _cycles(tmp_path, tools)[0]["reviewedAt"] == expected


def test_a_reviewer_that_is_no_handle_is_null(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}}, files={f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text(reviewer=_email()), f"{CYCLE_DIR}/review-cycle-2.md": _cycle_text(2)})
    assert [cycle["reviewer"] for cycle in _cycles(tmp_path, tools)] == [None, "reviewer-renata"]


def test_the_verdict_is_matched_by_the_full_pointer_and_the_last_event_wins(tmp_path: Path, tools: helper.ContractTools) -> None:
    other_mission = f"review-cycle://other-mission/{WP_SLUG}/review-cycle-1.md"
    rows = [
        _planned(1, "WP01"),
        _verdict_row(2, FIRST_POINTER, "changes_requested"),
        _verdict_row(3, FIRST_POINTER, "approved"),  # two events for one pointer: the last wins
        _verdict_row(4, other_mission, "changes_requested"),  # another Mission segment: matches nothing
        _verdict_row(5, f"approval://{MISSION}/WP01", "approved"),  # an approval reference is no pointer
        _verdict_row(6, "  " + SECOND_POINTER + "  ", "changes_requested"),  # the reference is trimmed
    ]
    files = {f"{CYCLE_DIR}/review-cycle-{number}.md": _cycle_text(number) for number in (1, 2, 3)}
    _mission(tmp_path, {"WP01": {}}, files=files, rows=rows)
    assert [(cycle["cycleNumber"], cycle["verdict"]) for cycle in _cycles(tmp_path, tools)] == [(1, "approved"), (2, "changes_requested"), (3, None)]


def test_an_event_of_another_work_package_never_sets_a_verdict(tmp_path: Path, tools: helper.ContractTools) -> None:
    rows = [_planned(1, "WP01"), _planned(2, "WP02"), _verdict_row(3, FIRST_POINTER, "approved", wp_id="WP02")]
    _mission(tmp_path, {"WP01": {}, "WP02": {}}, files={f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text()}, rows=rows)
    assert _cycles(tmp_path, tools)[0]["verdict"] is None


def test_the_verdict_is_never_read_from_the_cycle_file(tmp_path: Path, tools: helper.ContractTools) -> None:
    text = _cycle_text().replace("---\n\nFeedback", "verdict: approved\n---\n\nFeedback", 1)
    _mission(tmp_path, {"WP01": {}}, files={f"{CYCLE_DIR}/review-cycle-1.md": text})
    assert _cycles(tmp_path, tools)[0]["verdict"] is None


def test_an_unparseable_cycle_file_is_an_entry_with_null_parsed_members_and_the_number_from_its_name(tmp_path: Path, tools: helper.ContractTools) -> None:
    rows = [_planned(1, "WP01"), _verdict_row(2, SECOND_POINTER, "changes_requested")]
    _mission(tmp_path, {"WP01": {}}, files={f"{CYCLE_DIR}/review-cycle-2.md": "not a cycle file\n", f"{CYCLE_DIR}/review-cycle-1.md": b"\xff\xfe"}, rows=rows)
    first, second = _cycles(tmp_path, tools)
    assert (first["cycleNumber"], first["reviewedAt"], first["reviewer"]) == (1, None, None)
    assert (second["cycleNumber"], second["reviewedAt"], second["reviewer"]) == (2, None, None)
    assert second["verdict"] == "changes_requested", "the verdict comes from the events, not from the file"
    assert second["feedbackReference"] == SECOND_POINTER and second["artifactPath"] == f"{CYCLE_DIR}/review-cycle-2.md"


def test_a_directory_name_the_pointer_builder_refuses_keeps_the_entry_with_a_null_pointer(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _mission(tmp_path, {"WP01": {}}, files={"tasks/WP01-a b/review-cycle-1.md": _cycle_text()})
    (mission_dir / "tasks" / "WP01-fixture.md").rename(mission_dir / "tasks" / "WP01-a b.md")
    (entry,) = _cycles(tmp_path, tools)
    assert entry["feedbackReference"] is None and entry["verdict"] is None
    assert entry["cycleNumber"] == 1 and entry["artifactPath"] == "tasks/WP01-a b/review-cycle-1.md", "the entry is kept, never dropped and never fabricated"
    assert det.cycle_pointer(MISSION, "WP01-ab", "review-cycle-1.md") is not None, "clean twin: a segment the builder accepts gives a pointer"


@pytest.mark.parametrize("name", ["review-cycle-0.md", "review-cycle-01.md", "review-cycle-1.txt", "review-cycle-1.md.bak", "review-cycle-.md", "notes.md"])
def test_a_file_that_is_not_named_like_a_cycle_is_not_a_cycle(name: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}}, files={f"{CYCLE_DIR}/{name}": _cycle_text(), f"{CYCLE_DIR}/review-cycle-3.md": _cycle_text(3)})
    assert [cycle["cycleNumber"] for cycle in _cycles(tmp_path, tools)] == [3], name


def test_two_prompt_files_for_one_work_package_the_first_in_byte_order_decides_the_cycle_directory(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(
        tmp_path,
        {},
        files={
            "tasks/WP01-a-first.md": _frontmatter("WP01"),
            "tasks/WP01-b-second.md": _frontmatter("WP01"),
            "tasks/WP01-a-first/review-cycle-1.md": _cycle_text(1),
            "tasks/WP01-b-second/review-cycle-2.md": _cycle_text(2),
        },
    )
    assert [cycle["cycleNumber"] for cycle in _cycles(tmp_path, tools)] == [1]


def test_a_notes_file_is_no_prompt_so_its_directory_is_never_a_cycle_directory(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {}, files={"tasks/WP-notes.md": _frontmatter("WP09"), "tasks/WP-notes/review-cycle-1.md": _cycle_text(1)})
    assert _cycles(tmp_path, tools, "WP09") == []


def test_a_symlinked_work_package_directory_is_not_entered_and_a_symlinked_cycle_file_has_null_members_and_no_link(
    tmp_path: Path, tools: helper.ContractTools
) -> None:
    mission_dir = _mission(tmp_path, {"WP01": {}, "WP02": {}}, files={"elsewhere/review-cycle-1.md": _cycle_text(1), "real/review-cycle-2.md": _cycle_text(2)})
    (mission_dir / "tasks" / "WP02-fixture").symlink_to(mission_dir / "real", target_is_directory=True)
    (mission_dir / "tasks" / "WP01-fixture").mkdir()
    (mission_dir / "tasks" / "WP01-fixture" / "review-cycle-1.md").symlink_to(mission_dir / "elsewhere" / "review-cycle-1.md")
    assert _cycles(tmp_path, tools, "WP02") == [], "a symlinked tasks/<wp-slug>/ directory is not entered"
    (entry,) = _cycles(tmp_path, tools, "WP01")
    assert (entry["cycleNumber"], entry["reviewedAt"], entry["reviewer"], entry["artifactPath"]) == (1, None, None, None)
    assert entry["feedbackReference"] == FIRST_POINTER


def test_a_symlinked_tasks_directory_hides_every_cycle(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _mission(tmp_path, {"WP01": {}}, files={f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text()})
    real = mission_dir / "real-tasks"
    (mission_dir / "tasks").rename(real)
    (mission_dir / "tasks").symlink_to(real, target_is_directory=True)
    body = det.build_work_package_detail(_ctx(tmp_path, tools), MISSION_ID, "WP01", det.NO_WORKTREES)
    assert body.status == 404, "a symlinked tasks/ directory holds no work package file the reader follows"


# ---------------------------------------------------------------------------
# Workspace (FR-006): the lane matrix, without git state (the real-git matrix is further down)
# ---------------------------------------------------------------------------

CAPABLE = det.HostCapability(git=True, worktrees=True)
LANE_BRANCH = f"kitty/mission-{MISSION}-lane-a"


def _lanes(*lanes: tuple[str, list[str]], target_branch: str = "main") -> dict[str, Any]:
    return {
        "version": 1,
        "mission_slug": MISSION,
        "mission_id": MISSION_ID,
        "mission_branch": f"kitty/mission-{MISSION}",
        "target_branch": target_branch,
        "lanes": [
            {"lane_id": lane_id, "wp_ids": wp_ids, "write_scope": [], "predicted_surfaces": [], "depends_on_lanes": [], "parallel_group": 0}
            for lane_id, wp_ids in lanes
        ],
        "computed_at": STAMP(minute="00"),
        "computed_from": "fixture",
    }


def _workspace(root: Path, tools: helper.ContractTools, host: det.HostCapability = det.NO_WORKTREES) -> dict[str, Any]:
    return _ok(_detail(_ctx(root, tools), "WP01", host))["workspace"]


def test_a_mission_without_lanes_has_null_lane_members_and_no_worktree(tmp_path: Path, tools: helper.ContractTools) -> None:
    helper.git_init(tmp_path)
    _mission(tmp_path, {"WP01": {"planning_base_branch": "main"}})
    assert _workspace(tmp_path, tools, CAPABLE) == {"laneId": None, "laneBranch": None, "planningBranch": "main", "worktreePresent": False}


def test_a_work_package_in_no_lane_has_null_lane_members(tmp_path: Path, tools: helper.ContractTools) -> None:
    helper.git_init(tmp_path)
    _mission(tmp_path, {"WP01": {}, "WP02": {}}, lanes=_lanes(("lane-a", ["WP02"])))
    assert _workspace(tmp_path, tools, CAPABLE) == {"laneId": None, "laneBranch": None, "planningBranch": None, "worktreePresent": False}


def test_a_code_lane_names_its_branch_and_has_no_worktree_until_it_is_created(tmp_path: Path, tools: helper.ContractTools) -> None:
    helper.git_init(tmp_path)
    _mission(tmp_path, {"WP01": {"execution_mode": "code_change"}}, lanes=_lanes(("lane-a", ["WP01"])))
    expected = {"laneId": "lane-a", "laneBranch": LANE_BRANCH, "planningBranch": None, "worktreePresent": False}
    assert _workspace(tmp_path, tools, CAPABLE) == expected, "recorded in lanes.json but not created: false"
    assert _workspace(tmp_path, tools) == expected, "a host without worktrees reports false whatever exists"


def test_a_planning_lane_is_never_a_present_worktree_and_has_no_lane_branch(tmp_path: Path, tools: helper.ContractTools) -> None:
    helper.git_init(tmp_path)
    _mission(tmp_path, {"WP01": {"execution_mode": "planning_artifact"}}, lanes=_lanes(("lane-planning", ["WP01"])))
    workspace = _workspace(tmp_path, tools, CAPABLE)
    assert workspace["worktreePresent"] is False, "a planning-artifact work package resolves to the repository checkout, never a lane worktree"
    assert (workspace["laneId"], workspace["laneBranch"]) == ("lane-planning", None)


def test_a_malformed_lanes_file_fails_the_read_and_is_never_null(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _mission(tmp_path, {"WP01": {}}, files={"lanes.json": "{ not json"})
    _refused(_detail(_ctx(tmp_path, tools), "WP01"), 500, "source_unreadable")
    (mission_dir / "lanes.json").write_text(json.dumps(_lanes(("lane-a", ["WP01"]))), encoding="utf-8")
    _ok(_detail(_ctx(tmp_path, tools), "WP01"))  # clean twin: the same Mission with a well-formed manifest answers


def test_a_manifest_missing_a_required_key_is_malformed(tmp_path: Path, tools: helper.ContractTools) -> None:
    broken = _lanes(("lane-a", ["WP01"]))
    del broken["target_branch"]
    _mission(tmp_path, {"WP01": {}}, lanes=broken)
    _refused(_detail(_ctx(tmp_path, tools), "WP01"), 500, "source_unreadable")


@pytest.mark.parametrize("lane_id", ["lane a", "lane/a", "-lane", "a" * 65])
def test_a_lane_id_that_fails_the_schema_pattern_projects_to_null_with_its_branch(lane_id: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}}, lanes=_lanes((lane_id, ["WP01"])))
    workspace = _workspace(tmp_path, tools)
    assert (workspace["laneId"], workspace["laneBranch"]) == (None, None)


def test_a_planning_branch_over_the_cap_projects_to_null_and_an_absent_one_is_null(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {"planning_base_branch": "b" * 256}})
    assert _workspace(tmp_path, tools)["planningBranch"] is None
    other = tmp_path / "twin"
    other.mkdir()
    _mission(other, {"WP01": {"planning_base_branch": "b" * 255}})
    assert _workspace(other, tools)["planningBranch"] == "b" * 255


def test_the_lane_branch_of_a_code_lane_ignores_the_target_branch_and_the_planning_lane_has_none(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}, "WP02": {}}, lanes=_lanes(("lane-a", ["WP01"]), ("lane-planning", ["WP02"]), target_branch="release/3.x"))
    assert _workspace(tmp_path, tools)["laneBranch"] == LANE_BRANCH
    planning = _ok(_detail(_ctx(tmp_path, tools), "WP02"))["workspace"]
    assert (planning["laneId"], planning["laneBranch"]) == ("lane-planning", None), (
        "lane_branch_name returns the target branch for the planning lane: that is no lane branch"
    )


# ---------------------------------------------------------------------------
# Artifact references (FR-008): eligibility only, no listing walk and no content open
# ---------------------------------------------------------------------------


@dataclass
class Io:
    opens: list[Path] = field(default_factory=list)
    scandirs: list[Path] = field(default_factory=list)


def _counting_fs(io: Io) -> art.FileSystem:
    real = art.REAL_FS

    def open_binary(path: Path) -> art.OpenFile:
        io.opens.append(Path(path))
        return real.open_binary(path)

    def scandir(path: Path) -> list[str]:
        io.scandirs.append(Path(path))
        return real.scandir(path)

    return dataclasses.replace(real, open_binary=open_binary, scandir=scandir)


def _references(root: Path, tools: helper.ContractTools, wp_id: str = "WP01") -> dict[str, Any]:
    return _ok(_detail(_ctx(root, tools), wp_id))["artifactReferences"]


def _answers_200(root: Path, tools: helper.ContractTools, path: str) -> bool:
    return art.read_content(_ctx(root, tools), MISSION_ID, [path]).status == 200


def test_the_references_name_the_prompt_and_the_specification_when_they_are_eligible(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}}, files={"spec.md": "# Spec\n"})
    references = _references(tmp_path, tools)
    assert references == {"prompt": {"path": f"tasks/{WP_SLUG}.md", "kind": "work_package_prompt"}, "spec": {"path": "spec.md", "kind": "spec"}}
    assert all(_answers_200(tmp_path, tools, reference["path"]) for reference in references.values()), "a link never points at a file the content read refuses"


def test_a_missing_symlinked_or_directory_specification_is_null(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _mission(tmp_path, {"WP01": {}})
    assert _references(tmp_path, tools)["spec"] is None, "absent"
    (mission_dir / "spec.md").mkdir()
    assert _references(tmp_path, tools)["spec"] is None, "a directory"
    (mission_dir / "spec.md").rmdir()
    _put(mission_dir, {"elsewhere.md": "# Elsewhere\n"})
    (mission_dir / "spec.md").symlink_to(mission_dir / "elsewhere.md")
    assert _references(tmp_path, tools)["spec"] is None, "a symlink is never followed"


def test_the_prompt_is_the_first_regular_file_in_byte_order_and_never_another_work_packages(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _mission(
        tmp_path,
        {"WP02": {}},
        files={
            "tasks/WP01-b-regular.md": _frontmatter("WP01"),
            "tasks/WP01-c-regular.md": _frontmatter("WP01"),
            "tasks/WP-notes.md": _frontmatter(None),
            "tasks/WP1-x.md": _frontmatter(None),
        },
    )
    (mission_dir / "tasks" / "WP01-a-link.md").symlink_to(mission_dir / "tasks" / "WP01-c-regular.md")
    assert _references(tmp_path, tools)["prompt"] == {"path": "tasks/WP01-b-regular.md", "kind": "work_package_prompt"}, "the symlink sorts first and is skipped"
    assert _references(tmp_path, tools, "WP02")["prompt"] == {"path": "tasks/WP02-fixture.md", "kind": "work_package_prompt"}


def test_a_work_package_with_no_prompt_file_has_a_null_prompt_even_when_another_package_has_one(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP02": {}}, files={"tasks/WP01.md": _frontmatter("WP01")})
    assert _references(tmp_path, tools)["prompt"] is None, "tasks/WP01.md has no hyphen after the id: it is no prompt file"


def test_a_prompt_below_a_symlinked_tasks_directory_is_not_named(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _mission(tmp_path, {"WP01": {}, "WP02": {}})
    outside = mission_dir / "real-tasks"
    outside.mkdir()
    (outside / "WP03-x.md").write_text(_frontmatter("WP03"), encoding="utf-8")
    (mission_dir / "tasks" / "WP03-link").symlink_to(outside, target_is_directory=True)
    assert _references(tmp_path, tools)["prompt"] == {"path": f"tasks/{WP_SLUG}.md", "kind": "work_package_prompt"}, (
        "a symlinked directory beside it changes nothing"
    )


def _past_the_cap(root: Path) -> Path:
    """A Mission whose listing is truncated before ``spec.md``, the prompt and the cycle file (they sort after 1001 files of ``aaa/``)."""
    files: dict[str, str | bytes] = {f"aaa/f{number:04d}.md": "x\n" for number in range(art.MAX_LISTING_ENTRIES + 1)}
    files.update({"spec.md": "# Spec\n", f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text(), "tasks.md": FIXTURE_TASKS})
    return _mission(root, {"WP01": {"subtasks": ["T001"]}}, files=files)


def test_the_links_do_not_depend_on_the_listing_cap(tmp_path: Path, tools: helper.ContractTools) -> None:
    _past_the_cap(tmp_path)
    listing = art.list_artifacts(_ctx(tmp_path, tools), MISSION_ID).body
    paths = [entry["path"] for entry in listing["entries"]]
    assert listing["truncated"] is True and len(paths) == art.MAX_LISTING_ENTRIES
    assert "spec.md" not in paths and f"{CYCLE_DIR}/review-cycle-1.md" not in paths, "control: the listing really is cut before them"
    body = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    assert body["artifactReferences"]["spec"] == {"path": "spec.md", "kind": "spec"}
    assert body["artifactReferences"]["prompt"] == {"path": f"tasks/{WP_SLUG}.md", "kind": "work_package_prompt"}
    assert body["reviewCycles"][0]["artifactPath"] == f"{CYCLE_DIR}/review-cycle-1.md"
    for path in ("spec.md", f"tasks/{WP_SLUG}.md", f"{CYCLE_DIR}/review-cycle-1.md"):
        assert _answers_200(tmp_path, tools, path), f"{path} is readable by path although the listing is cut"


def test_the_detail_walks_no_listing_and_opens_no_artifact_for_its_links(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _past_the_cap(tmp_path)
    io = Io()
    _ok(det.build_work_package_detail(_ctx(tmp_path, tools, _counting_fs(io)), MISSION_ID, "WP01", det.NO_WORKTREES))
    assert io.scandirs, "control: the directory reads were counted"
    assert set(io.scandirs) <= {mission_dir / "tasks", mission_dir / CYCLE_DIR}, f"a directory outside tasks/ was read: {sorted(set(io.scandirs))}"
    assert io.opens == [mission_dir / "tasks.md"], f"only the task list is a source to open; the links open nothing: {io.opens}"


# ---------------------------------------------------------------------------
# Surfaces (D-P9, ledger SK-310, SK-348): planning files from the primary directory, status from the status surface
# ---------------------------------------------------------------------------


def test_a_coordination_mission_reads_planning_files_from_primary_and_status_from_coordination(tmp_path: Path, tools: helper.ContractTools) -> None:
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)
    mission_id = json.loads((coord.root_mission_dir / "meta.json").read_text(encoding="utf-8"))["mission_id"]
    wp_slug = "WP01-primary"
    _put(
        coord.root_mission_dir,
        {
            f"tasks/{wp_slug}.md": _frontmatter("WP01", dependencies=["WP02"]),
            "tasks/WP02-primary.md": _frontmatter("WP02"),
            "spec.md": "# Spec\n",
            f"tasks/{wp_slug}/review-cycle-1.md": _cycle_text(1),  # a stranded record in the primary directory (SK-348): shown
        },
    )
    _put(coord.coord_mission_dir, {f"tasks/{wp_slug}/review-cycle-2.md": _cycle_text(2)})  # only on the coordination surface: not shown (AD-18)
    rows = [_planned(1, "WP02"), helper.transition_row(2, "WP02", "planned", "claimed", at=STAMP(minute="06"), actor="claude", mission_slug=coord.mission_dir_name)]
    log = coord.coord_mission_dir / "status.events.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        handle.write("".join(json.dumps({**row, "mission_id": mission_id}, sort_keys=True) + "\n" for row in rows))
    ctx = art.ReaderContext(repo_root=coord.repo_root, tools=tools)
    body = det.build_work_package_detail(ctx, mission_id, "WP01", det.NO_WORKTREES)
    assert body.status == 200, f"{body.status} {body.body}"
    detail = body.body
    assert detail["dependencies"] == [{"wpId": "WP02", "title": "Title of WP02", "statusLane": "claimed"}], "the lane comes from the coordination status surface"
    assert [(cycle["cycleNumber"], cycle["reviewedAt"], cycle["reviewer"], cycle["artifactPath"]) for cycle in detail["reviewCycles"]] == [
        (1, OFFSET_TIME, "reviewer-renata", f"tasks/{wp_slug}/review-cycle-1.md")
    ], "a cycle only on the coordination surface is not shown, a stranded primary record is, read from the primary directory"
    assert detail["artifactReferences"]["spec"] == {"path": "spec.md", "kind": "spec"}, "the planning files are found on the primary surface"


# ---------------------------------------------------------------------------
# The owned-files matcher and its parity with the two repository copies (D-P3, FR-007 rule 3)
# ---------------------------------------------------------------------------

BACKSLASH = chr(92)
# (pattern, path, expected): the FR-022 glob and directory cases, all of them cases on which the repository's two copies agree.
GLOB_CASES: list[tuple[str, str, bool]] = [
    ("src/foo/**", "src/foobar/x.py", False),
    ("src/foo/**", "src/foo/x.py", True),
    ("src/foo/**", "src/foo/a/b.py", True),
    ("src/foo", "src/foo/x.py", True),
    ("src/foo", "src/foobar/x.py", False),
    ("[x]/*", "[x]/y", True),
    ("*.py", "src/x.py", True),
    ("src/*.py", "src/a/x.py", True),
    ("src/foo/*", "src/foo/a/b.py", True),
    ("a/*/c", "a/c/z", True),
    ("src/**/x.py", "src/x.py", False),
    ("src/**/x.py", "src/a/b/x.py", True),
    ("**/x.py", "x.py", False),
    ("**/x.py", "a/x.py", True),
    ("a/**/b/**/c", "a/x/b/y/c", True),
    ("a/**/b/**/c", "a/b/c", False),
    ("src/{a,b}.py", "src/a.py", False),
    ("src/{a,b}.py", "src/{a,b}.py", True),
]
# (pattern, path, expected, the commit guard's copy agrees): four normalisation cases; the two it does not normalise are the known divergences.
NORMALISATION_CASES: list[tuple[str, str, bool, bool]] = [
    ("src/foo/**", "./src/foo/x.py", True, False),
    ("src/foo/**", f"src{BACKSLASH}foo{BACKSLASH}x.py", True, False),
    ("src/foo/**", "././src/foo/x.py", False, True),  # only one leading ./ is removed
    ("./src/foo/**", "src/foo/x.py", False, True),  # the pattern is used as authored
]


@pytest.mark.parametrize(("pattern", "path", "expected"), GLOB_CASES)
def test_the_matcher_gives_the_stated_result_on_every_glob_and_directory_case(pattern: str, path: str, expected: bool) -> None:
    assert det.matches_owned_file(path, pattern) is expected


@pytest.mark.parametrize(("pattern", "path", "expected"), GLOB_CASES)
def test_the_matcher_agrees_with_both_repository_copies_on_every_glob_case(pattern: str, path: str, expected: bool) -> None:
    assert _mt_matches_owned_file(path, (pattern,)) is expected, "the move-task copy"
    assert _matches_any_glob(path, [pattern]) is expected, "the commit-guard copy"
    assert det.matches_owned_file(path, pattern) is expected


@pytest.mark.parametrize(("pattern", "path", "expected", "guard_agrees"), NORMALISATION_CASES)
def test_the_matcher_normalises_like_the_move_task_copy_and_the_two_known_divergences_are_pinned(
    pattern: str, path: str, expected: bool, guard_agrees: bool
) -> None:
    assert det.matches_owned_file(path, pattern) is expected
    assert _mt_matches_owned_file(path, (pattern,)) is expected, "the reader reproduces the move-task copy, which normalises inside"
    assert (_matches_any_glob(path, [pattern]) is expected) is guard_agrees, "the commit-guard copy receives git-relative paths and does not normalise"


def test_exactly_two_normalisation_cases_diverge_from_the_commit_guard_copy() -> None:
    assert [(case[0], case[1]) for case in NORMALISATION_CASES if not case[3]] == [NORMALISATION_CASES[0][:2], NORMALISATION_CASES[1][:2]]


def test_the_matcher_is_not_fnmatchcase_a_case_difference_follows_the_platform_like_the_copies() -> None:
    for pattern, path in (("SRC/*.py", "src/x.py"), ("src/*.PY", "src/x.py")):
        assert det.matches_owned_file(path, pattern) is _mt_matches_owned_file(path, (pattern,)) is _matches_any_glob(path, [pattern])


# ---------------------------------------------------------------------------
# The change-state derivation over a faked git seam (the real-git matrix is further down)
# ---------------------------------------------------------------------------

FAKE_WORKTREE = Path("fake-worktree")
SEAM_SENTINEL = "merge-base-sha"


def _view(*, lane_id: str | None = "lane-a", branch: str | None = LANE_BRANCH, present: bool = True, target: str | None = "main") -> det.WorkspaceView:
    workspace = {"laneId": lane_id, "laneBranch": branch, "planningBranch": None, "worktreePresent": present}
    return det.WorkspaceView(workspace, FAKE_WORKTREE if present else None, target)


@dataclass
class Seam:
    """Counts the calls of the three git seams the derivation uses, answering from fixed values."""

    branch: str | None = LANE_BRANCH
    merge_base: str | None = SEAM_SENTINEL
    paths: tuple[str, ...] = ()
    branch_calls: int = 0
    merge_base_calls: int = 0
    change_calls: int = 0
    timeouts: list[float | None] = field(default_factory=list)

    def install(self, mp: pytest.MonkeyPatch) -> Seam:
        def get_current_branch(path: Path) -> str | None:
            self.branch_calls += 1
            return self.branch

        def git_merge_base(repo: Path, ref_a: str, ref_b: str) -> str | None:
            self.merge_base_calls += 1
            assert (ref_a, ref_b) == ("HEAD", "main"), "the merge base is taken between HEAD and the manifest's target branch"
            return self.merge_base

        def changed(cwd: Path, *revs: str, renames: bool = False, timeout: float | None = None) -> tuple[GitPath, ...]:
            self.change_calls += 1
            self.timeouts.append(timeout)
            assert revs == (SEAM_SENTINEL, "HEAD") and renames is False, "committed changes only, a rename lists both names"
            return tuple(GitPath.parse(path) for path in self.paths)

        mp.setattr(det, "get_current_branch", get_current_branch)
        mp.setattr(det, "git_merge_base", git_merge_base)
        mp.setattr(det, "changed_paths", changed)
        return self


def _states(view: det.WorkspaceView, patterns: list[str], host: det.HostCapability = CAPABLE) -> list[str]:
    return det.change_states(host, view, patterns)


def test_a_determined_change_set_gives_changed_and_unchanged_and_the_query_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    seam = Seam(paths=("src/foo/x.py", "docs/a.md")).install(monkeypatch)
    assert _states(_view(), ["src/foo/**", "src/foo", "docs/*.md", "other/**", "src/foobar.py"]) == ["changed", "changed", "changed", "unchanged", "unchanged"]
    assert seam.timeouts == [det.GIT_TIMEOUT_SECONDS], "the change set is asked once per work package, with a fixed timeout"
    assert det.GIT_TIMEOUT_SECONDS == 30.0


def test_a_glob_matching_nothing_is_unchanged_when_determined_and_an_empty_change_set_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    Seam(paths=()).install(monkeypatch)
    assert _states(_view(), ["a/**", "b.py"]) == ["unchanged", "unchanged"]


@pytest.mark.parametrize(
    ("label", "view", "host"),
    [
        ("a host without git", _view(), det.HostCapability(git=False, worktrees=True)),
        ("a host without worktrees", _view(), det.HostCapability(git=True, worktrees=False)),
        ("a host without either", _view(), det.NO_WORKTREES),
        ("the planning lane", _view(lane_id="lane-planning", branch=None), CAPABLE),
        ("no lane", _view(lane_id=None, branch=None), CAPABLE),
        ("no lane branch", _view(branch=None), CAPABLE),
        ("no present worktree", _view(present=False), CAPABLE),
        ("no target branch", _view(target=None), CAPABLE),
    ],
)
def test_a_precondition_that_does_not_hold_gives_unknown_and_git_is_not_asked(
    label: str, view: det.WorkspaceView, host: det.HostCapability, monkeypatch: pytest.MonkeyPatch
) -> None:
    seam = Seam(paths=("src/x.py",)).install(monkeypatch)
    assert _states(view, ["src/**", "other"], host) == ["unknown", "unknown"], label
    assert (seam.branch_calls, seam.merge_base_calls, seam.change_calls) == (0, 0, 0), f"{label}: git must not be invoked"


def test_a_head_on_another_branch_or_detached_is_not_determined(monkeypatch: pytest.MonkeyPatch) -> None:
    for branch in ("some-other-branch", None):
        seam = Seam(branch=branch, paths=("src/x.py",)).install(monkeypatch)
        assert _states(_view(), ["src/**"]) == ["unknown"], branch
        assert seam.branch_calls == 1 and seam.merge_base_calls == 0, "the branch is checked before anything else is asked"


def test_a_merge_base_that_is_not_found_is_unknown_and_never_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    seam = Seam(merge_base=None, paths=("src/x.py",)).install(monkeypatch)
    assert _states(_view(), ["src/**", "elsewhere/**"]) == ["unknown", "unknown"]
    assert seam.change_calls == 0


@pytest.mark.parametrize("target", ["--output=x", "-b", "a b", "a;b", "", "x" * 256, "bad" + chr(0)])
def test_a_target_branch_that_is_not_a_plain_branch_name_gives_unknown_and_git_is_not_invoked(target: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seam = Seam(paths=("src/x.py",)).install(monkeypatch)
    assert _states(_view(target=target), ["src/**"]) == ["unknown"]
    assert (seam.branch_calls, seam.merge_base_calls, seam.change_calls) == (0, 0, 0)


def test_a_brace_pattern_is_unknown_whatever_the_change_set_and_its_neighbours_stay_determined(monkeypatch: pytest.MonkeyPatch) -> None:
    Seam(paths=("src/a.py", "src/{a,b}.py")).install(monkeypatch)
    assert _states(_view(), ["src/{a,b}.py", "src/a.py", "src/c.py"]) == ["unknown", "changed", "unchanged"]


def test_the_invariants_hold_on_a_built_detail_and_a_planted_violation_is_reported() -> None:
    clean = {"workspace": {"laneId": "lane-a", "worktreePresent": False}, "ownedFiles": [{"changeState": "unknown"}]}
    assert det.invariant_problems(clean) == []
    assert det.invariant_problems({**clean, "ownedFiles": [{"changeState": "changed"}]}), "changed without a worktree"
    assert det.invariant_problems({"workspace": {"laneId": "lane-planning", "worktreePresent": True}, "ownedFiles": []}), "a planning lane with a worktree"
    assert det.invariant_problems({"workspace": {"laneId": None, "worktreePresent": True}, "ownedFiles": []}), "no lane with a worktree"
    assert det.invariant_problems({"workspace": {"laneId": "lane-a", "worktreePresent": True}, "ownedFiles": [{"changeState": "changed"}]}) == []


# ---------------------------------------------------------------------------
# The assembled outcome (T035): absence, unreadable sources, leak withholding, determinism
# ---------------------------------------------------------------------------


def test_an_unknown_mission_work_package_or_ill_formed_identifier_is_not_found(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}}, rows=[_planned(1, "WP01"), _planned(2, "WP99")])  # WP99 is present only in the status log
    ctx = _ctx(tmp_path, tools)
    _ok(_detail(ctx, "WP01"))
    _refused(_detail(ctx, "WP02"), 404, "not_found")
    _refused(_detail(ctx, "WP99"), 404, "not_found")
    for wp_id in ("wp01", "WP1", "", "../WP01", "WP01/x", "WP01 "):
        _refused(_detail(ctx, wp_id), 404, "not_found")
    for mission_id in (helper.fixture_ulid(2), "not-a-ulid", "", MISSION_ID[:-1] + "i"):
        _refused(det.build_work_package_detail(ctx, mission_id, "WP01", det.NO_WORKTREES), 404, "not_found")


def test_a_refusal_carries_no_path_no_mission_directory_and_no_content(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {}}, files={"lanes.json": "{ broken"})
    for outcome in (_detail(_ctx(tmp_path, tools), "WP01"), _detail(_ctx(tmp_path, tools), "WP02")):
        rendered = json.dumps(outcome.body)
        assert str(tmp_path) not in rendered and MISSION not in rendered and "lanes" not in rendered, rendered


def test_a_work_package_file_with_no_status_events_is_a_200_with_null_lanes(tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {"subtasks": ["T001"], "dependencies": ["WP02"]}, "WP02": {}}, tasks_md=FIXTURE_TASKS, rows=[])
    body = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    assert [entry["statusLane"] for entry in body["subtasks"] + body["dependencies"]] == [None, None]


def test_an_ambiguous_mission_handle_fails_the_read_with_source_unreadable(tmp_path: Path, tools: helper.ContractTools, monkeypatch: pytest.MonkeyPatch) -> None:
    _mission(tmp_path, {"WP01": {}})
    fired = Fired()

    def ambiguous(*args: Any, **kwargs: Any) -> Any:
        fired.count += 1
        raise MissionSelectorAmbiguous(handle="alpha", candidates=["alpha-one", "alpha-two"])

    monkeypatch.setattr(det, "reconstruct_wp_view", ambiguous)
    _refused(_detail(_ctx(tmp_path, tools), "WP01"), 500, "source_unreadable")
    assert fired.count == 1, FAULT_NOT_FIRED


@pytest.mark.parametrize("error", [PermissionError, IsADirectoryError, OSError])
def test_a_work_package_file_that_cannot_be_read_fails_the_read_while_the_others_are_not_turned_into_404(
    error: type[OSError], tmp_path: Path, tools: helper.ContractTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mission(tmp_path, {"WP01": {}, "WP02": {}})
    fired = Fired()
    real = det.read_authored_wp_frontmatter

    def unreadable(path: Path) -> Any:
        if path.name == "WP02-fixture.md":
            fired.count += 1
            raise error(INJECTED_FAULT)
        return real(path)

    monkeypatch.setattr(det, "read_authored_wp_frontmatter", unreadable)
    _refused(_detail(_ctx(tmp_path, tools), "WP01"), 500, "source_unreadable")
    assert fired.count >= 1, FAULT_NOT_FIRED


@pytest.mark.parametrize("call", ["lstat", "scandir", "open_binary"])
def test_a_failure_of_the_file_system_seam_on_a_source_gives_source_unreadable_never_a_wrong_answer(call: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    _mission(tmp_path, {"WP01": {"subtasks": ["T001"]}}, tasks_md=FIXTURE_TASKS, files={f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text()})
    fired = Fired()
    target = {"lstat": "tasks.md", "scandir": WP_SLUG, "open_binary": "tasks.md"}[call]
    real = getattr(art.REAL_FS, call)

    def faulty(path: Path) -> Any:
        if Path(path).name == target:
            fired.count += 1
            raise PermissionError(INJECTED_FAULT)
        return real(path)

    outcome = _detail(_ctx(tmp_path, tools, dataclasses.replace(art.REAL_FS, **{call: faulty})), "WP01")
    _refused(outcome, 500, "source_unreadable")
    assert fired.count >= 1, FAULT_NOT_FIRED


class _ServedFile:
    """An open handle that serves ``data`` and honours the size of a bounded read."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def fstat(self) -> Any:
        raise AssertionError("the tasks.md read does not stat the handle")

    def read(self, size: int) -> bytes:
        return self._data[:size]

    def close(self) -> None:
        return None


def _tasks_md_of_size(size: int) -> bytes:
    body = FIXTURE_TASKS.encode("utf-8")
    return body + b" " * (size - len(body))


@pytest.mark.parametrize(("extra", "status"), [(0, 200), (1, 500)])
def test_the_tasks_md_cap_is_inclusive_at_four_mebibytes_and_one_byte_more_is_source_unreadable(
    extra: int, status: int, tmp_path: Path, tools: helper.ContractTools
) -> None:
    _mission(tmp_path, {"WP01": {"subtasks": ["T001"]}}, tasks_md=FIXTURE_TASKS)
    served = _tasks_md_of_size(det.MAX_TASKS_MD_BYTES + extra)
    real = art.REAL_FS.open_binary

    def open_binary(path: Path) -> art.OpenFile:
        return _ServedFile(served) if Path(path).name == "tasks.md" else real(path)

    outcome = _detail(_ctx(tmp_path, tools, dataclasses.replace(art.REAL_FS, open_binary=open_binary)), "WP01")
    if status == 200:
        _ok(outcome)
    else:
        _refused(outcome, 500, "source_unreadable")


def test_a_mission_directory_that_cannot_be_statted_is_source_unreadable_and_an_absent_one_is_not_found(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _mission(tmp_path, {"WP01": {}})
    fired = Fired()
    real = art.REAL_FS.lstat

    def faulty(path: Path) -> Any:
        if Path(path) == mission_dir:
            fired.count += 1
            raise PermissionError(INJECTED_FAULT)
        return real(path)

    _refused(_detail(_ctx(tmp_path, tools, dataclasses.replace(art.REAL_FS, lstat=faulty)), "WP01"), 500, "source_unreadable")
    assert fired.count == 1, FAULT_NOT_FIRED
    ctx = art.ReaderContext(repo_root=tmp_path, tools=tools, mission_dirs={MISSION_ID: tmp_path / "kitty-specs" / "absent"})
    _refused(_detail(ctx, "WP01"), 404, "not_found")


def test_a_withheld_title_is_a_reader_guarantee_and_a_planted_pass_through_is_reported_by_the_leak_scan(
    tmp_path: Path, tools: helper.ContractTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks_md = f"## WP01 - Work\n\n- [ ] T001 holds {_token()}\n- [ ] T002 clean twin\n"
    _mission(tmp_path, {"WP01": {"subtasks": ["T001", "T002"], "dependencies": ["WP02"]}, "WP02": {"title": f"holds {_token()}"}}, tasks_md=tasks_md)
    clean = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    assert helper.payload_leaks(clean, tools) == [], "clean twin: the withheld titles leave nothing to report"
    assert (clean["subtasks"][0]["title"], clean["dependencies"][0]["title"]) == (None, "WP02")
    with monkeypatch.context() as mp:
        mp.setattr(det, "human_text", lambda tools, projector, value, where: value)  # the withholding stops
        leaking = _detail(_ctx(tmp_path, tools), "WP01").body
    codes = {finding.rpartition(": ")[2] for finding in helper.payload_leaks(leaking, tools)}
    assert tools.leak.CODE_CREDENTIAL in codes, "the planted pass-through is reported as a credential"


def test_an_event_holding_an_absolute_feedback_path_never_reaches_the_detail_and_the_pointer_does(tmp_path: Path, tools: helper.ContractTools) -> None:
    feedback = _home_path("cycle") + "/review-cycle-1.md"
    reference = {"reviewer": "reviewer-renata", "verdict": "changes_requested", "reference": FIRST_POINTER, "feedback_path": feedback}
    row = helper.transition_row(2, "WP01", "for_review", "planned", at=STAMP(minute="10"), actor="claude", review_result=reference)
    _mission(tmp_path, {"WP01": {}}, files={f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text()}, rows=[_planned(1, "WP01"), row])
    body = _ok(_detail(_ctx(tmp_path, tools), "WP01"))
    (cycle,) = body["reviewCycles"]
    assert (cycle["feedbackReference"], cycle["verdict"]) == (FIRST_POINTER, "changes_requested")
    assert feedback not in json.dumps(body) and _home_path() not in json.dumps(body), "the pointer is present, never the path"


def _rich_mission(root: Path) -> None:
    helper.git_init(root)
    rows = [_planned(1, "WP01"), _planned(2, "WP02"), _verdict_row(3, FIRST_POINTER, "approved")]
    _mission(
        root,
        {"WP01": {"subtasks": ["T001", "T002"], "dependencies": ["WP02"], "owned_files": ["src/**", "docs/a.md"], "planning_base_branch": "main"}, "WP02": {}},
        tasks_md=FIXTURE_TASKS,
        files={f"{CYCLE_DIR}/review-cycle-1.md": _cycle_text(), "spec.md": "# Spec\n"},
        rows=rows,
        lanes=_lanes(("lane-a", ["WP01"]), ("lane-planning", ["WP02"])),
    )


def test_two_builds_of_an_unchanged_mission_are_byte_identical(tmp_path: Path, tools: helper.ContractTools) -> None:
    _rich_mission(tmp_path)
    for host in (det.NO_WORKTREES, CAPABLE):
        ctx = _ctx(tmp_path, tools)
        first, second = (json.dumps(_ok(_detail(ctx, "WP01", host)), sort_keys=True) for _ in range(2))
        assert first == second, host


def test_the_review_cycles_are_the_same_with_and_without_a_materialised_coordination_worktree(tmp_path: Path, tools: helper.ContractTools) -> None:
    shown: list[list[dict[str, Any]]] = []
    references: list[Any] = []
    for label, materialized in (("with", True), ("without", False)):
        coord = make_coord_mission(tmp_path / label, MissionTopology.COORD, materialized=materialized)
        mission_id = json.loads((coord.root_mission_dir / "meta.json").read_text(encoding="utf-8"))["mission_id"]
        _put(coord.root_mission_dir, {"tasks/WP01-primary.md": _frontmatter("WP01"), "tasks/WP01-primary/review-cycle-1.md": _cycle_text(1), "spec.md": "# Spec\n"})
        if materialized:
            _put(coord.coord_mission_dir, {"tasks/WP01-primary/review-cycle-2.md": _cycle_text(2)})
        outcome = det.build_work_package_detail(art.ReaderContext(repo_root=coord.repo_root, tools=tools), mission_id, "WP01", det.NO_WORKTREES)
        body = _ok(outcome)
        # the Mission directory name carries a time-derived identity, so the pointer is compared after its own Mission segment is checked
        assert [cycle["feedbackReference"] for cycle in body["reviewCycles"]] == [f"review-cycle://{coord.mission_dir_name}/WP01-primary/review-cycle-1.md"]
        shown.append([{key: value for key, value in cycle.items() if key != "feedbackReference"} for cycle in body["reviewCycles"]])
        references.append(body["artifactReferences"])
    assert shown[0] == shown[1] and [cycle["cycleNumber"] for cycle in shown[0]] == [1]
    assert references[0] == references[1]


# ---------------------------------------------------------------------------
# Real git: the workspace matrix and the change states through the REAL kernel.git seam
# ---------------------------------------------------------------------------


@pytest.fixture
def scratch_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """No global or system git configuration is read, so a repository's default branch and behaviour never depend on the machine."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return done.stdout.strip()


@dataclass
class Scenario:
    """A scratch repository on ``main`` with one Mission, and the lane worktree of its work package on the lane branch."""

    root: Path
    mission_dir: Path
    worktree: Path
    ctx: art.ReaderContext

    def commit(self, files: Mapping[str, str | None] | None = None, *, remove: tuple[str, ...] = (), move: tuple[tuple[str, str], ...] = ()) -> None:
        """One commit on the lane branch: write ``files`` (a ``None`` value is not written), ``git rm`` and ``git mv`` the rest."""
        for old, new in move:
            (self.worktree / new).parent.mkdir(parents=True, exist_ok=True)
            _git(self.worktree, "mv", old, new)
        for name in remove:
            _git(self.worktree, "rm", "-q", name)
        _put(self.worktree, {name: text for name, text in (files or {}).items() if text is not None})
        helper.commit_all(self.worktree)

    def detail(self, host: det.HostCapability = CAPABLE) -> dict[str, Any]:
        return _ok(_detail(self.ctx, "WP01", host))

    def states(self, host: det.HostCapability = CAPABLE) -> list[str]:
        return [entry["changeState"] for entry in self.detail(host)["ownedFiles"]]


def _scenario(
    root: Path,
    tools: helper.ContractTools,
    patterns: list[str],
    *,
    base: Mapping[str, str] | None = None,
    target_branch: str = "main",
    fs: art.FileSystem = art.REAL_FS,
) -> Scenario:
    """The Mission (one work package owning ``patterns``) committed on ``main`` with the ``base`` files, then its lane worktree."""
    helper.git_init(root)
    _git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    mission_dir = _mission(
        root,
        {"WP01": {"execution_mode": "code_change", "owned_files": patterns}},
        lanes=_lanes(("lane-a", ["WP01"]), target_branch=target_branch),
    )
    _put(root, {"README.md": "base\n", **(base or {})})  # the repository's own files, beside kitty-specs/
    helper.commit_all(root)
    worktree = root / ".worktrees" / f"{MISSION}-lane-a"
    _git(root, "worktree", "add", "-q", "-b", LANE_BRANCH, str(worktree), "main")
    return Scenario(root, mission_dir, worktree, art.ReaderContext(repo_root=root, tools=tools, fs=fs))


def test_a_real_lane_worktree_is_present_and_a_committed_owned_file_is_changed_where_an_untouched_one_is_not(
    tmp_path: Path, tools: helper.ContractTools, scratch_git: None
) -> None:
    scenario = _scenario(
        tmp_path, tools, ["src/edited.py", "src/untouched.py", "src/*.py", "docs/**"], base={"src/edited.py": "1\n", "src/untouched.py": "1\n", "docs/a.md": "1\n"}
    )
    scenario.commit({"src/edited.py": "2\n"})
    detail = scenario.detail()
    assert detail["workspace"] == {"laneId": "lane-a", "laneBranch": LANE_BRANCH, "planningBranch": None, "worktreePresent": True}
    assert [(entry["pattern"], entry["isGlob"], entry["changeState"]) for entry in detail["ownedFiles"]] == [
        ("src/edited.py", False, "changed"),
        ("src/untouched.py", False, "unchanged"),
        ("src/*.py", True, "changed"),
        ("docs/**", True, "unchanged"),
    ]


def test_the_same_repository_with_a_host_that_has_no_worktrees_is_unknown_and_not_present(tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    scenario = _scenario(tmp_path, tools, ["src/edited.py"], base={"src/edited.py": "1\n"})
    scenario.commit({"src/edited.py": "2\n"})
    assert scenario.states() == ["changed"], "control: the capable host determines it"
    for host in (det.NO_WORKTREES, det.HostCapability(git=True, worktrees=False), det.HostCapability(git=False, worktrees=True)):
        detail = scenario.detail(host)
        assert [entry["changeState"] for entry in detail["ownedFiles"]] == ["unknown"], host
        assert detail["workspace"]["worktreePresent"] is (host.worktrees), host


# (label, owned pattern, base files, files committed on the lane branch, expected): each case builds its own repository
CHANGE_CASES: list[tuple[str, str, dict[str, str], dict[str, str], str]] = [
    ("directory glob and a sibling prefix", "src/foo/**", {}, {"src/foobar/x.py": "1\n"}, "unchanged"),
    ("directory glob and its own file", "src/foo/**", {}, {"src/foo/x.py": "1\n"}, "changed"),
    ("a plain directory entry covers its files", "src/foo", {}, {"src/foo/x.py": "1\n"}, "changed"),
    ("a plain directory entry and a sibling prefix", "src/foo", {}, {"src/foobar/x.py": "1\n"}, "unchanged"),
    ("a literal glob character in the directory", "[x]/*", {}, {"[x]/y": "1\n"}, "changed"),
    ("a star crosses a slash", "*.py", {}, {"src/x.py": "1\n"}, "changed"),
    ("a star crosses a slash inside a directory", "src/*.py", {}, {"src/a/x.py": "1\n"}, "changed"),
    ("a trailing star below a directory", "src/foo/*", {}, {"src/foo/a/b.py": "1\n"}, "changed"),
    ("a middle star strips by the prefix rule", "a/*/c", {}, {"a/c/z": "1\n"}, "changed"),
    ("no zero-directory double star", "src/**/x.py", {}, {"src/x.py": "1\n"}, "unchanged"),
    ("a double star over directories", "src/**/x.py", {}, {"src/a/b/x.py": "1\n"}, "changed"),
    ("a leading double star needs a directory", "**/x.py", {}, {"x.py": "1\n"}, "unchanged"),
    ("a leading double star over a directory", "**/x.py", {}, {"a/x.py": "1\n"}, "changed"),
    ("two double stars over directories", "a/**/b/**/c", {}, {"a/x/b/y/c": "1\n"}, "changed"),
    ("two double stars without directories", "a/**/b/**/c", {}, {"a/b/c": "1\n"}, "unchanged"),
    ("a brace pattern with an expansion and a literal both changed", "src/{a,b}.py", {}, {"src/a.py": "1\n", "src/{a,b}.py": "1\n"}, "unknown"),
    ("a brace pattern with nothing changed", "src/{a,b}.py", {}, {"other.py": "1\n"}, "unknown"),
    ("an owned file that is not changed", "src/untouched.py", {"src/untouched.py": "1\n"}, {"other.py": "1\n"}, "unchanged"),
]


@pytest.mark.parametrize(("label", "pattern", "base", "committed", "expected"), CHANGE_CASES, ids=[case[0] for case in CHANGE_CASES])
def test_change_state_through_real_git(
    label: str, pattern: str, base: dict[str, str], committed: dict[str, str], expected: str, tmp_path: Path, tools: helper.ContractTools, scratch_git: None
) -> None:
    scenario = _scenario(tmp_path, tools, [pattern], base=base)
    scenario.commit(committed)
    assert scenario.states() == [expected], label


def test_a_deleted_owned_file_is_changed_and_a_rename_is_changed_under_both_names(tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    scenario = _scenario(
        tmp_path,
        tools,
        ["src/deleted.py", "src/old-name.py", "src/new-name.py", "src/kept.py"],
        base={"src/deleted.py": "d\n" * 20, "src/old-name.py": "r\n" * 20, "src/kept.py": "k\n"},
    )
    scenario.commit(remove=("src/deleted.py",), move=(("src/old-name.py", "src/new-name.py"),))
    assert scenario.states() == ["changed", "changed", "changed", "unchanged"]


def test_an_uncommitted_edit_a_staged_edit_and_an_untracked_file_are_unchanged(tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    owned = ["u/edited.py", "u/staged.py", "u/untracked.py", "c/committed.py"]
    scenario = _scenario(tmp_path, tools, owned, base={"u/edited.py": "1\n", "u/staged.py": "1\n"})
    scenario.commit({"c/committed.py": "1\n"})
    _put(scenario.worktree, {"u/edited.py": "2\n", "u/staged.py": "2\n", "u/untracked.py": "2\n"})
    _git(scenario.worktree, "add", "u/staged.py")
    assert scenario.states() == ["unchanged", "unchanged", "unchanged", "changed"], "only the committed change counts"


def test_a_detached_head_and_a_head_on_another_branch_are_unknown(tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    scenario = _scenario(tmp_path, tools, ["src/x.py"], base={"src/x.py": "1\n"})
    scenario.commit({"src/x.py": "2\n"})
    assert scenario.states() == ["changed"], "control: on the lane branch it is determined"
    _git(scenario.worktree, "checkout", "-q", "-b", "some-other-branch")
    other = scenario.detail()
    assert [entry["changeState"] for entry in other["ownedFiles"]] == ["unknown"] and other["workspace"]["worktreePresent"] is True
    _git(scenario.worktree, "checkout", "-q", "--detach")
    assert scenario.states() == ["unknown"]


def test_a_target_branch_that_does_not_resolve_is_unknown_and_never_unchanged(tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    scenario = _scenario(tmp_path, tools, ["src/x.py"], base={"src/x.py": "1\n"}, target_branch="no-such-branch")
    scenario.commit({"src/x.py": "2\n"})
    assert scenario.states() == ["unknown"]


def test_a_planning_artifact_work_package_resolves_to_the_checkout_and_is_never_a_present_worktree(
    tmp_path: Path, tools: helper.ContractTools, scratch_git: None
) -> None:
    helper.git_init(tmp_path)
    _git(tmp_path, "symbolic-ref", "HEAD", "refs/heads/main")
    _mission(tmp_path, {"WP01": {"execution_mode": "planning_artifact", "owned_files": ["docs/**"]}}, lanes=_lanes(("lane-planning", ["WP01"])))
    helper.commit_all(tmp_path)
    detail = _ok(_detail(_ctx(tmp_path, tools), "WP01", CAPABLE))
    assert detail["workspace"]["worktreePresent"] is False, "the repository checkout exists, but it is no lane worktree"
    assert (detail["workspace"]["laneId"], detail["workspace"]["laneBranch"]) == ("lane-planning", None)
    assert [entry["changeState"] for entry in detail["ownedFiles"]] == ["unknown"]


def test_a_directory_without_a_git_entry_is_a_husk_and_not_a_present_worktree(tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    scenario = _scenario(tmp_path, tools, ["src/x.py"], base={"src/x.py": "1\n"})
    assert scenario.detail()["workspace"]["worktreePresent"] is True, "control: the real worktree is present"
    (scenario.worktree / ".git").unlink()
    detail = scenario.detail()
    assert detail["workspace"]["worktreePresent"] is False and [entry["changeState"] for entry in detail["ownedFiles"]] == ["unknown"]


# ---------------------------------------------------------------------------
# Fault injection: every failure of a git call is "not determined", never an exception and never unchanged
# ---------------------------------------------------------------------------

REAL_GET_CURRENT_BRANCH = det.get_current_branch
REAL_GIT_MERGE_BASE = det.git_merge_base
REAL_CHANGED_PATHS = det.changed_paths


def _raising(error: BaseException, fired: Fired) -> Any:
    def raiser(*args: Any, **kwargs: Any) -> Any:
        fired.count += 1
        raise error

    return raiser


def _vanishing_merge_base(worktree: Path, fired: Fired) -> Any:
    """``git_merge_base`` after the worktree directory was removed between the existence check and the call."""

    def merge_base(repo: Path, ref_a: str, ref_b: str) -> str | None:
        shutil.rmtree(worktree)
        fired.count += 1
        return REAL_GIT_MERGE_BASE(repo, ref_a, ref_b)

    return merge_base


def _refused_path(fired: Fired) -> Any:
    """``changed_paths`` over output holding a path ``GitPath`` refuses (the ``..`` component a crafted name would carry)."""

    def changed(cwd: Path, *revs: str, **kwargs: Any) -> Any:
        REAL_CHANGED_PATHS(cwd, *revs, **kwargs)
        fired.count += 1
        return (GitPath.parse("src/x.py"), GitPath.parse("a/../b"))

    return changed


def _timed_out(worktree: Path) -> GitCommandError:
    return GitCommandError(argv=("diff", "--name-only"), cwd=worktree, returncode=-1, stderr="timed out", timed_out=True)


FAULTS = (
    "branch-permission",
    "branch-timeout",
    "merge-base-not-a-directory",
    "merge-base-vanished",
    "merge-base-nul",
    "changed-timeout",
    "changed-parse",
    "changed-refused-path",
)
# the guard each fault is caught by: the tuple of exceptions the reader catches around that seam
FAULT_GUARDS = {
    "branch-permission": "_GIT_SEAM_ERRORS",
    "branch-timeout": "_GIT_SEAM_ERRORS",
    "merge-base-not-a-directory": "_GIT_SEAM_ERRORS",
    "merge-base-vanished": "_GIT_SEAM_ERRORS",
    "merge-base-nul": "_GIT_SEAM_ERRORS",
    "changed-timeout": "_CHANGE_SET_ERRORS",
    "changed-parse": "_CHANGE_SET_ERRORS",
    "changed-refused-path": "_CHANGE_SET_ERRORS",
}


def _inject(mp: pytest.MonkeyPatch, kind: str, worktree: Path, fired: Fired) -> None:
    if kind == "branch-permission":
        mp.setattr(det, "get_current_branch", _raising(PermissionError(INJECTED_FAULT), fired))
    elif kind == "branch-timeout":
        mp.setattr(det, "get_current_branch", _raising(subprocess.TimeoutExpired(cmd="git", timeout=1), fired))
    elif kind == "merge-base-not-a-directory":
        mp.setattr(det, "git_merge_base", _raising(NotADirectoryError(INJECTED_FAULT), fired))
    elif kind == "merge-base-vanished":
        mp.setattr(det, "git_merge_base", _vanishing_merge_base(worktree, fired))
    elif kind == "merge-base-nul":
        mp.setattr(det, "git_merge_base", _raising(ValueError("embedded null byte"), fired))
    elif kind == "changed-timeout":
        mp.setattr(det, "changed_paths", _raising(_timed_out(worktree), fired))
    elif kind == "changed-parse":
        mp.setattr(det, "changed_paths", _raising(ValueError("not a normalized repository-relative path"), fired))
    elif kind == "changed-refused-path":
        mp.setattr(det, "changed_paths", _refused_path(fired))
    else:
        raise AssertionError(kind)


def _fault_problems(root: Path, tools: helper.ContractTools, kind: str) -> list[str]:
    """Run the detail with ``kind`` injected into a real determined scenario; the problems found (none when the fault is handled)."""
    scenario = _scenario(root, tools, ["src/x.py", "src/*.py"], base={"src/x.py": "1\n"})
    scenario.commit({"src/x.py": "2\n"})
    fired = Fired()
    with pytest.MonkeyPatch.context() as mp:
        _inject(mp, kind, scenario.worktree, fired)
        try:
            outcome = _detail(scenario.ctx, "WP01", CAPABLE)
        except Exception as error:  # the mutation under test removes a guard, so any exception is a finding
            return [f"{kind}: {type(error).__name__} escaped the reader"]
    problems = [] if fired.count else [f"{kind}: {FAULT_NOT_FIRED}"]
    if outcome.status != 200:
        return [*problems, f"{kind}: the detail answered {outcome.status}"]
    states = [entry["changeState"] for entry in outcome.body["ownedFiles"]]
    if states != ["unknown", "unknown"]:
        problems.append(f"{kind}: states {states}, expected every entry unknown")
    return problems


@pytest.mark.parametrize("kind", FAULTS)
def test_a_failing_git_call_makes_every_entry_unknown_and_never_raises_or_reads_as_unchanged(
    kind: str, tmp_path: Path, tools: helper.ContractTools, scratch_git: None
) -> None:
    assert _fault_problems(tmp_path, tools, kind) == []


def test_a_target_branch_that_looks_like_an_option_gives_unknown_and_git_is_never_invoked(tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    (tmp_path / "option").mkdir()
    (tmp_path / "plain").mkdir()
    scenario = _scenario(tmp_path / "option", tools, ["src/x.py"], base={"src/x.py": "1\n"}, target_branch="--output=" + str(tmp_path / "hit"))
    scenario.commit({"src/x.py": "2\n"})
    calls = Fired()
    with pytest.MonkeyPatch.context() as mp:
        for name in ("get_current_branch", "git_merge_base", "changed_paths"):
            real = getattr(det, name)

            def counted(*args: Any, _real: Any = real, **kwargs: Any) -> Any:
                calls.count += 1
                return _real(*args, **kwargs)

            mp.setattr(det, name, counted)
        assert scenario.states() == ["unknown"]
    assert calls.count == 0, "no git call may be made with an option-like branch name"
    assert not (tmp_path / "hit").exists(), "the option never reached git"
    clean = _scenario(tmp_path / "plain", tools, ["src/x.py"], base={"src/x.py": "1\n"})
    clean.commit({"src/x.py": "2\n"})
    assert clean.states() == ["changed"], "clean twin: a plain target branch is determined"


# ---------------------------------------------------------------------------
# Mutations the change-state tests must kill: each is applied by a test, which then runs the check that must fail
# ---------------------------------------------------------------------------


def _states_of(root: Path, tools: helper.ContractTools, patterns: list[str], **scenario_args: Any) -> list[str]:
    scenario = _scenario(root, tools, patterns, **scenario_args)
    return scenario.states()


def _expect(label: str, got: object, expected: object) -> list[str]:
    return [] if got == expected else [f"{label}: {got!r}, expected {expected!r}"]


def _check_unresolved_base(root: Path, tools: helper.ContractTools) -> list[str]:
    scenario = _scenario(root, tools, ["src/x.py", "src/other.py"], base={"src/x.py": "1\n", "src/other.py": "1\n"}, target_branch="no-such-branch")
    scenario.commit({"src/x.py": "2\n"})
    return _expect("a base that does not resolve", scenario.states(), ["unknown", "unknown"])


def _check_only_committed(root: Path, tools: helper.ContractTools) -> list[str]:
    scenario = _scenario(root, tools, ["u/edited.py", "u/staged.py", "u/untracked.py"], base={"u/edited.py": "1\n", "u/staged.py": "1\n"})
    scenario.commit({"c/other.py": "1\n"})
    _put(scenario.worktree, {"u/edited.py": "2\n", "u/staged.py": "2\n", "u/untracked.py": "2\n"})
    _git(scenario.worktree, "add", "u/staged.py")
    return _expect("uncommitted, staged and untracked paths", scenario.states(), ["unchanged"] * 3)


def _check_deletion(root: Path, tools: helper.ContractTools) -> list[str]:
    scenario = _scenario(root, tools, ["src/deleted.py"], base={"src/deleted.py": "d\n"})
    scenario.commit(remove=("src/deleted.py",))
    return _expect("a deleted owned file", scenario.states(), ["changed"])


def _check_rename(root: Path, tools: helper.ContractTools) -> list[str]:
    scenario = _scenario(root, tools, ["src/old-name.py", "src/new-name.py"], base={"src/old-name.py": "r\n" * 20})
    scenario.commit(move=(("src/old-name.py", "src/new-name.py"),))
    return _expect("a renamed owned file by its old and its new name", scenario.states(), ["changed", "changed"])


def _check_detached(root: Path, tools: helper.ContractTools) -> list[str]:
    scenario = _scenario(root, tools, ["src/x.py"], base={"src/x.py": "1\n"})
    scenario.commit({"src/x.py": "2\n"})
    _git(scenario.worktree, "checkout", "-q", "--detach")
    return _expect("a detached HEAD", scenario.states(), ["unknown"])


def _check_base_is_the_target_branch(root: Path, tools: helper.ContractTools) -> list[str]:
    scenario = _scenario(root, tools, ["a/first.py", "b/second.py"], base={"README.md": "base\n"})
    scenario.commit({"a/first.py": "1\n"})
    scenario.commit({"b/second.py": "1\n"})
    return _expect("two commits on the lane branch", scenario.states(), ["changed", "changed"])


def _check_brace(root: Path, tools: helper.ContractTools) -> list[str]:
    scenario = _scenario(root, tools, ["src/{a,b}.py"])
    scenario.commit({"src/a.py": "1\n", "src/{a,b}.py": "1\n"})
    return _expect("a brace pattern with an expansion and a literal both changed", scenario.states(), ["unknown"])


def _check_matcher(root: Path, tools: helper.ContractTools) -> list[str]:
    cases = [(pattern, path, expected) for pattern, path, expected in GLOB_CASES]
    cases += [(pattern, path, expected) for pattern, path, expected, _agrees in NORMALISATION_CASES]
    return [
        f"{pattern!r} vs {path!r}: {det.matches_owned_file(path, pattern)}, expected {expected}"
        for pattern, path, expected in cases
        if det.matches_owned_file(path, pattern) is not expected
    ]


def _check_planning_worktree(root: Path, tools: helper.ContractTools) -> list[str]:
    helper.git_init(root)
    _git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    _mission(root, {"WP01": {"execution_mode": "planning_artifact"}}, lanes=_lanes(("lane-planning", ["WP01"])))
    helper.commit_all(root)
    outcome = _detail(_ctx(root, tools), "WP01", CAPABLE)
    return _expect("a planning-artifact work package", outcome.body["workspace"]["worktreePresent"], False)


def _fault_check(kind: str) -> Any:
    return lambda root, tools: _fault_problems(root, tools, kind)


def _normalised(path: str) -> str:
    return path.replace(BACKSLASH, "/").removeprefix("./")


def _matcher_mutation(replacement: Any) -> Any:
    return lambda mp, root: mp.setattr(det, "matches_owned_file", replacement)


def _star_stays_in_a_segment(path: str, pattern: str) -> bool:
    regex = fnmatch.translate(pattern).replace(".*", "[^/]*")
    prefix = pattern.replace("/**", "").replace("/*", "").rstrip("/")
    return re.match(regex, _normalised(path)) is not None or bool(prefix and _normalised(path).startswith(prefix + "/"))


def _with_zero_directory_double_star(path: str, pattern: str) -> bool:
    forms = {pattern, pattern.replace("/**/", "/"), pattern.removeprefix("**/")}
    return any(fnmatch.fnmatch(_normalised(path), form) for form in forms) or _original_matcher(path, pattern)


def _original_matcher(path: str, pattern: str) -> bool:
    return ORIGINAL_MATCHER(path, pattern)


ORIGINAL_MATCHER = det.matches_owned_file


def _without_the_directory_prefix_rule(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(_normalised(path), pattern)


def _prefix_without_a_segment_boundary(path: str, pattern: str) -> bool:
    prefix = pattern.replace("/**", "").replace("/*", "").rstrip("/")
    return fnmatch.fnmatch(_normalised(path), pattern) or bool(prefix and _normalised(path).startswith(prefix))


def _prefix_of_a_trailing_star_only(path: str, pattern: str) -> bool:
    prefix = pattern.removesuffix("/**").removesuffix("/*").rstrip("/")
    return fnmatch.fnmatch(_normalised(path), pattern) or bool(prefix and _normalised(path).startswith(prefix + "/"))


def _without_normalisation(path: str, pattern: str) -> bool:
    prefix = pattern.replace("/**", "").replace("/*", "").rstrip("/")
    return fnmatch.fnmatch(path, pattern) or bool(prefix and path.startswith(prefix + "/"))


def _with_brace_expansion(path: str, pattern: str) -> bool:
    head, _, rest = pattern.partition("{")
    options, _, tail = rest.partition("}")
    expanded = [head + option + tail for option in options.split(",")] if options else [pattern]
    return any(ORIGINAL_MATCHER(path, form) for form in expanded)


def _mutate_none_as_unchanged(mp: pytest.MonkeyPatch, root: Path) -> None:
    mp.setattr(det, "git_merge_base", lambda repo, ref_a, ref_b: REAL_GIT_MERGE_BASE(repo, ref_a, ref_b) or "HEAD")


def _mutate_count_uncommitted(mp: pytest.MonkeyPatch, root: Path) -> None:
    def with_status(cwd: Path, *revs: str, **kwargs: Any) -> Any:
        return (*REAL_CHANGED_PATHS(cwd, *revs, **kwargs), *(entry.path for entry in status_entries(cwd)))

    mp.setattr(det, "changed_paths", with_status)


def _mutate_ignore_deletions(mp: pytest.MonkeyPatch, root: Path) -> None:
    mp.setattr(det, "changed_paths", lambda cwd, *revs, **kwargs: REAL_CHANGED_PATHS(cwd, *revs, diff_filter="d", **kwargs))


def _mutate_ignore_the_old_name(mp: pytest.MonkeyPatch, root: Path) -> None:
    mp.setattr(det, "changed_paths", lambda cwd, *revs, **kwargs: REAL_CHANGED_PATHS(cwd, *revs, **{**kwargs, "renames": True}))


def _mutate_accept_detached(mp: pytest.MonkeyPatch, root: Path) -> None:
    mp.setattr(det, "get_current_branch", lambda path: REAL_GET_CURRENT_BRANCH(path) or LANE_BRANCH)


def _mutate_other_base(mp: pytest.MonkeyPatch, root: Path) -> None:
    mp.setattr(det, "git_merge_base", lambda repo, ref_a, ref_b: _git(Path(repo), "rev-parse", "HEAD~1"))


def _mutate_brace_literal(mp: pytest.MonkeyPatch, root: Path) -> None:
    mp.setattr(det, "_matchable", lambda pattern: True)


def _mutate_brace_expanded(mp: pytest.MonkeyPatch, root: Path) -> None:
    mp.setattr(det, "_matchable", lambda pattern: True)
    mp.setattr(det, "matches_owned_file", _with_brace_expansion)


def _mutate_worktree_present_by_existence_alone(mp: pytest.MonkeyPatch, root: Path) -> None:
    def resolver(repo_root: Path, slug: str, wp_id: str) -> Any:
        real = _real_resolver(repo_root, slug, wp_id)
        return SimpleNamespace(runs_in_checkout_root=False, exists=real.exists, worktree_path=real.worktree_path)

    mp.setattr(det, "resolve_workspace_for_wp", resolver)


REAL_RESOLVER = det.resolve_workspace_for_wp


def _real_resolver(repo_root: Path, slug: str, wp_id: str) -> Any:
    return REAL_RESOLVER(repo_root, slug, wp_id)


def _remove_guard(name: str) -> Any:
    return lambda mp, root: mp.setattr(det, name, ())


MUTATIONS: dict[str, tuple[Any, Any]] = {
    "a git helper None read as unchanged": (_mutate_none_as_unchanged, _check_unresolved_base),
    "uncommitted or untracked paths counted": (_mutate_count_uncommitted, _check_only_committed),
    "deletions ignored": (_mutate_ignore_deletions, _check_deletion),
    "the old side of a rename ignored": (_mutate_ignore_the_old_name, _check_rename),
    "a detached HEAD accepted": (_mutate_accept_detached, _check_detached),
    "a base other than the target branch": (_mutate_other_base, _check_base_is_the_target_branch),
    "a brace pattern matched literally": (_mutate_brace_literal, _check_brace),
    "a brace pattern expanded": (_mutate_brace_expanded, _check_brace),
    "a star that does not cross a slash": (_matcher_mutation(_star_stays_in_a_segment), _check_matcher),
    "a zero-directory double star": (_matcher_mutation(_with_zero_directory_double_star), _check_matcher),
    "the directory-prefix rule dropped": (_matcher_mutation(_without_the_directory_prefix_rule), _check_matcher),
    "a prefix without the segment boundary": (_matcher_mutation(_prefix_without_a_segment_boundary), _check_matcher),
    "a prefix rule for a trailing star only": (_matcher_mutation(_prefix_of_a_trailing_star_only), _check_matcher),
    "a matcher that normalises nothing": (_matcher_mutation(_without_normalisation), _check_matcher),
    "worktreePresent decided by existence alone": (_mutate_worktree_present_by_existence_alone, _check_planning_worktree),
    **{f"the guard removed for {kind}": (_remove_guard(FAULT_GUARDS[kind]), _fault_check(kind)) for kind in FAULTS},
}
SPEC_MUTATION_KEYWORDS = (
    "None",
    "uncommitted",
    "deletions",
    "old side",
    "star",
    "zero-directory",
    "directory-prefix rule dropped",
    "segment boundary",
    "trailing star only",
    "normalises nothing",
    "brace pattern matched literally",
    "brace pattern expanded",
    "detached",
    "base other",
)


def test_the_mutation_list_covers_every_mutation_the_specification_names() -> None:
    names = " | ".join(MUTATIONS)
    missing = [needle for needle in SPEC_MUTATION_KEYWORDS if needle not in names]
    assert missing == [], f"no mutation covers: {missing}"
    assert len(MUTATIONS) == 15 + len(FAULTS)


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_the_unmutated_reader_passes_the_check_each_mutation_must_fail(name: str, tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    problems = MUTATIONS[name][1](tmp_path, tools)
    assert problems == [], f"{name}: the check fails on the correct reader: {problems}"


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_planted_defect_is_killed_by_its_check(name: str, tmp_path: Path, tools: helper.ContractTools, scratch_git: None) -> None:
    mutate, check = MUTATIONS[name]
    with pytest.MonkeyPatch.context() as mp:
        mutate(mp, tmp_path)
        problems = check(tmp_path, tools)
    if not problems:
        pytest.fail(f"the mutation was not killed: {name}")
