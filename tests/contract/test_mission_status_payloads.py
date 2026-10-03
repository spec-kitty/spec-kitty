"""Unit tests for the test-side payload helper of the reality check (FR-003 to FR-007, FR-009, FR-012).

Every derivation, projection and builder of ``_mission_status_payloads`` has a direct test here, with planted
violations and clean controls. The builders run against Missions written at run time into a temporary git
repository, so no committed Mission is read and nothing under ``kitty-specs/`` of this checkout is touched.
Planted leak values are assembled from fragments, so this source holds no literal host path or address.
"""

from __future__ import annotations

import json
from itertools import product
import re
import subprocess
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.status.aggregate import CoordAuthorityUnavailable, MissionMetadataUnavailable, MissionStatus
from specify_cli.status.lifecycle_events import LIFECYCLE_EVENT_TYPES
from specify_cli.status.models import ReviewOverride
from specify_cli.status.tail_reader import EMPTY_DIGEST
from tests.contract import _mission_status_payloads as helper

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
SLASH = chr(47)
AT = chr(64)
BACKSLASH = chr(92)
MISSION = "alpha-mission"
LATER = "2026-09-02T10:00:00+00:00"


def _home_path(tail: str = "project") -> str:
    return SLASH + "home" + SLASH + "someone" + SLASH + tail


def _email() -> str:
    return "someone" + AT + "example.invalid"


def _counts(**given: int) -> dict[str, int]:
    return {**dict.fromkeys(helper.STATUS_LANES, 0), **given}


@pytest.fixture(scope="module")
def tools() -> Iterator[helper.ContractTools]:
    with pytest.MonkeyPatch.context() as mp:
        yield helper.load_contract_tools(mp, REPO_ROOT)


@pytest.fixture(scope="module")
def contract(tools: helper.ContractTools) -> helper.Contract:
    return helper.Contract(tools, REPO_ROOT / "contracts" / "mission-status")


# ---------------------------------------------------------------------------
# Lifecycle, next action, readiness, project, ordering
# ---------------------------------------------------------------------------

LIFECYCLE_CASES: list[tuple[str, dict[str, int], int, str | None, str | None, str]] = [
    ("discarded wins over every lane", _counts(done=2), 2, "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z", "discarded"),
    ("no work packages is a draft", _counts(), 0, None, None, "draft"),
    ("no work packages stays a draft even when accepted", _counts(), 0, None, "2026-09-01T00:00:00Z", "draft"),
    ("claimed is active", _counts(claimed=1, planned=3), 4, None, None, "active"),
    ("in_progress is active", _counts(in_progress=1), 1, None, None, "active"),
    ("for_review is active", _counts(for_review=1, done=1), 2, None, None, "active"),
    ("in_review is active", _counts(in_review=1), 1, None, None, "active"),
    ("approved is active", _counts(approved=1), 1, None, None, "active"),
    ("planned alone is planned", _counts(planned=2), 2, None, None, "planned"),
    ("blocked alone reads as planned (pinned quirk)", _counts(blocked=2), 2, None, None, "planned"),
    ("blocked with done reads as planned", _counts(blocked=1, done=1), 2, None, None, "planned"),
    ("all done and not accepted is still active", _counts(done=3), 3, None, None, "active"),
    ("all done and accepted is done", _counts(done=3), 3, None, "2026-09-01T00:00:00Z", "done"),
    ("all canceled and accepted reads as done (pinned quirk)", _counts(canceled=2), 2, None, "2026-09-01T00:00:00Z", "done"),
    ("all canceled and not accepted is active", _counts(canceled=2), 2, None, None, "active"),
]


@pytest.mark.parametrize(("label", "counts", "total", "discarded", "accepted", "expected"), LIFECYCLE_CASES, ids=[case[0] for case in LIFECYCLE_CASES])
def test_the_lifecycle_rule_over_planted_lane_counts(
    label: str, counts: dict[str, int], total: int, discarded: str | None, accepted: str | None, expected: str
) -> None:
    assert helper.derive_lifecycle_status(counts, total, discarded, accepted) == expected, label


def test_every_lifecycle_value_is_reachable() -> None:
    reached = {case[5] for case in LIFECYCLE_CASES}
    assert reached == set(helper.LIFECYCLE_STATUSES)


ARTIFACTS = frozenset({"spec.md", "plan.md", "tasks.md"})
PHASE_CASES: list[tuple[str, dict[str, int], int, frozenset[str], frozenset[str], list[tuple[str, str]]]] = [
    (
        "nothing yet",
        _counts(),
        0,
        frozenset(),
        frozenset(),
        [
            ("pending", "artifact"),
            ("pending", "artifact"),
            ("pending", "artifact"),
            ("pending", "derived_from_status_lanes"),
            ("pending", "derived_from_status_lanes"),
        ],
    ),
    (
        "every artifact exists",
        _counts(planned=2),
        2,
        ARTIFACTS,
        frozenset(),
        [
            ("complete", "artifact"),
            ("complete", "artifact"),
            ("complete", "artifact"),
            ("pending", "derived_from_status_lanes"),
            ("pending", "derived_from_status_lanes"),
        ],
    ),
    (
        "lifecycle events stand in for missing files",
        _counts(),
        0,
        frozenset({"spec.md"}),
        frozenset({"SpecifyCompleted", "PlanCompleted", "TasksStarted"}),
        [
            ("complete", "artifact"),
            ("complete", "lifecycle_event"),
            ("in_progress", "lifecycle_event"),
            ("pending", "derived_from_status_lanes"),
            ("pending", "derived_from_status_lanes"),
        ],
    ),
    (
        "started markers only",
        _counts(),
        0,
        frozenset(),
        frozenset({"SpecifyStarted", "PlanStarted"}),
        [
            ("in_progress", "lifecycle_event"),
            ("in_progress", "lifecycle_event"),
            ("pending", "artifact"),
            ("pending", "derived_from_status_lanes"),
            ("pending", "derived_from_status_lanes"),
        ],
    ),
    (
        "implement in progress, review pending (claimed only)",
        _counts(claimed=1, planned=1),
        2,
        ARTIFACTS,
        frozenset(),
        [("complete", "artifact")] * 3 + [("in_progress", "derived_from_status_lanes"), ("pending", "derived_from_status_lanes")],
    ),
    (
        "implement complete once everything is under review, review in progress",
        _counts(for_review=1, approved=1),
        2,
        ARTIFACTS,
        frozenset(),
        [("complete", "artifact")] * 3 + [("complete", "derived_from_status_lanes"), ("in_progress", "derived_from_status_lanes")],
    ),
    (
        "both complete when every work package is done or canceled",
        _counts(done=1, canceled=1),
        2,
        ARTIFACTS,
        frozenset(),
        [("complete", "artifact")] * 3 + [("complete", "derived_from_status_lanes"), ("complete", "derived_from_status_lanes")],
    ),
    (
        "a done work package among planned ones starts both",
        _counts(done=1, planned=1),
        2,
        ARTIFACTS,
        frozenset(),
        [("complete", "artifact")] * 3 + [("in_progress", "derived_from_status_lanes"), ("in_progress", "derived_from_status_lanes")],
    ),
    (
        "blocked work packages have not left the starting lanes",
        _counts(blocked=2),
        2,
        ARTIFACTS,
        frozenset(),
        [("complete", "artifact")] * 3 + [("pending", "derived_from_status_lanes"), ("pending", "derived_from_status_lanes")],
    ),
]


@pytest.mark.parametrize(("label", "counts", "total", "artifacts", "lifecycle", "expected"), PHASE_CASES, ids=[case[0] for case in PHASE_CASES])
def test_the_phase_rules_over_planted_lane_counts(
    label: str, counts: dict[str, int], total: int, artifacts: frozenset[str], lifecycle: frozenset[str], expected: list[tuple[str, str]]
) -> None:
    phases = helper.derive_phases(counts, total, artifacts, lifecycle)
    assert [phase["name"] for phase in phases] == list(helper.PHASE_NAMES), label
    assert [(phase["status"], phase["basis"]) for phase in phases] == expected, label


def test_an_unknown_phase_name_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown Mission phase"):
        helper.derive_phase_status("merge", _counts(), 0, frozenset(), frozenset())


def test_the_next_action_is_one_of_two_sentences_or_null() -> None:
    done = _counts(done=2)
    review = helper.derive_next_action("slug-x", None, True, done)
    consolidate = helper.derive_next_action("slug-x", None, False, done)
    assert review is not None and "accept --mission slug-x" in review
    assert consolidate is not None and "consolidate --mission slug-x" in consolidate
    assert helper.derive_next_action("slug-x", "2026-09-01T00:00:00Z", True, done) is None, "an accepted Mission has no next action"
    assert helper.derive_next_action("slug-x", None, False, _counts(done=1, planned=1)) is None
    assert helper.derive_next_action("slug-x", None, False, _counts(canceled=2)) is None, "a canceled-only Mission is not offered consolidation"
    assert helper.derive_next_action("slug-x", None, False, _counts()) is None


@pytest.mark.parametrize(("lane", "satisfied", "expected"), [("planned", True, True), ("planned", False, False), ("claimed", True, False), (None, True, False)])
def test_ready_to_start_needs_a_planned_lane_and_satisfied_dependencies(lane: str | None, satisfied: bool, expected: bool) -> None:
    assert helper.derive_ready_to_start(lane, satisfied) is expected


def _overview(mission_id: str, created: str, number: int | None = None) -> dict[str, Any]:
    return {"missionId": mission_id, "createdAt": created, "displayNumber": number}


def test_mission_count_is_the_number_of_overview_records() -> None:
    records = [_overview("A", "2026-09-01T00:00:00Z"), _overview("B", "2026-09-02T00:00:00Z")]
    assert helper.derive_project("spec-kitty", records) == {"name": "spec-kitty", "missionCount": 2}
    assert helper.derive_project("spec-kitty", [])["missionCount"] == 0


def test_overviews_order_by_created_instant_descending_then_mission_id_ascending() -> None:
    zulu = _overview("B", "2026-09-02T10:00:00Z")
    offset = _overview("A", "2026-09-02T12:00:00+02:00")  # the same instant as 10:00Z, so the id breaks the tie
    older = _overview("C", "2026-09-01T00:00:00+00:00")
    ordered = helper.order_overviews([older, zulu, offset])
    assert [item["missionId"] for item in ordered] == ["A", "B", "C"]
    assert helper.ordering_problems(ordered) == []


def test_strict_ordering_flags_inversions_ties_and_duplicate_ids_but_not_a_repeated_display_number() -> None:
    newer, older = _overview("A", "2026-09-02T00:00:00Z", 7), _overview("B", "2026-09-01T00:00:00Z", 7)
    assert helper.ordering_problems([newer, older]) == [], "control: a strict order with a repeated displayNumber is clean"
    assert any("inversion" in problem for problem in helper.ordering_problems([older, newer]))
    assert any("tie" in problem for problem in helper.ordering_problems([newer, _overview("A", "2026-09-02T00:00:00Z")]))
    assert any("duplicate missionId" in problem for problem in helper.ordering_problems([newer, older, _overview("A", "2026-08-01T00:00:00Z")]))


# ---------------------------------------------------------------------------
# Ratchet header format and the shrink-only ceiling
# ---------------------------------------------------------------------------

GOOD_HEADER = {"issue": "#5579", "owner": "@stijn-dejongh", "drain_by": "2026-12-31", "ceiling": 52}


def test_the_committed_header_is_well_formed_and_complete() -> None:
    expected = helper.load_expected(REPO_ROOT)
    header = expected["header"]
    assert helper.ratchet_header_problems(header) == []
    assert {"commit", "functions", "sample_rule", "issue", "owner", "drain_by"} <= set(header)
    assert header["commit"] == "d78aa2345"
    assert header["functions"] == ["_derive_mission_status", "_derive_next_action"]
    assert header["generator_committed"] is False


def test_the_clean_header_control_passes() -> None:
    assert helper.ratchet_header_problems(GOOD_HEADER) == []
    assert helper.ratchet_header_problems({**GOOD_HEADER, "owner": "@spec-kitty/maintainers", "issue": "5579"}) == []


@pytest.mark.parametrize("issue", ["TBD", "", "#", "issue 5579", "#55x9", None, 5579])
def test_a_malformed_issue_is_rejected(issue: Any) -> None:
    assert any("issue" in problem for problem in helper.ratchet_header_problems({**GOOD_HEADER, "issue": issue}))


@pytest.mark.parametrize("owner", ["maintainers", "@two words", "", "TBD", "stijn-dejongh", "@", "@/team", None])
def test_a_malformed_owner_is_rejected(owner: Any) -> None:
    assert any("owner" in problem for problem in helper.ratchet_header_problems({**GOOD_HEADER, "owner": owner}))


@pytest.mark.parametrize("drain_by", ["TBD", "", "2026-13-01", "2026-9-1", "31-12-2026", "v1.0.0", "2026-09-30", None])
def test_a_malformed_or_early_drain_date_is_rejected(drain_by: Any) -> None:
    assert any("drain_by" in problem for problem in helper.ratchet_header_problems({**GOOD_HEADER, "drain_by": drain_by}))


def test_a_missing_key_is_rejected() -> None:
    for key in ("issue", "owner", "drain_by", "ceiling"):
        trimmed = {name: value for name, value in GOOD_HEADER.items() if name != key}
        assert any(key in problem for problem in helper.ratchet_header_problems(trimmed)), key


@pytest.mark.parametrize("ceiling", [-1, True, "52", None])
def test_a_malformed_ceiling_is_rejected(ceiling: Any) -> None:
    assert any("ceiling" in problem for problem in helper.ratchet_header_problems({**GOOD_HEADER, "ceiling": ceiling}))


def test_the_ceiling_only_ever_moves_down() -> None:
    assert helper.ceiling_problem(52, 52) is None, "control: at the ceiling is clean"
    grew = helper.ceiling_problem(53, 52) or ""
    assert "grew" in grew and "commit its status snapshot together with its work package files" in grew, "the failure names the remedy"
    assert "header.ceiling" in grew and "may only be lowered" in grew and "never raise it" in grew
    assert helper.ceiling_problem(40, 52) == "stale ceiling: lower header.ceiling in tests/contract/fixtures/mission_status_expected.json to 40"


# ---------------------------------------------------------------------------
# Projection of single values
# ---------------------------------------------------------------------------


@pytest.fixture
def projector(tools: helper.ContractTools) -> helper.Projector:
    return helper.Projector(tools.leak, "m")


@pytest.mark.parametrize(
    ("stored", "projected"),
    [("claude", "claude"), ("claude:sonnet:implementer:implementer", "claude:sonnet:implementer:implementer"), ("finalize-tasks", "finalize-tasks")],
)
def test_a_plain_handle_string_becomes_the_tool_and_is_never_split(projector: helper.Projector, stored: str, projected: str) -> None:
    assert projector.actor(stored) == {"tool": projected, "role": None, "profile": None}


def test_user_and_finalize_tasks_project_to_a_tool_only(projector: helper.Projector) -> None:
    for stored in ("user", "finalize-tasks", "migration"):
        assert projector.actor(stored) == {"tool": stored, "role": None, "profile": None}


@pytest.mark.parametrize("stored", [_email(), "two words", "a" + SLASH + "b", "x" * 129, "", None, 7, ["claude"]])
def test_anything_else_projects_to_all_null(projector: helper.Projector, stored: Any) -> None:
    assert projector.actor(stored) == {"tool": None, "role": None, "profile": None}


def test_a_structured_actor_is_copied_field_by_field_and_the_model_is_dropped(projector: helper.Projector) -> None:
    stored = {"tool": "claude", "role": "reviewer", "profile": "reviewer-renata", "model": "sonnet"}
    assert projector.actor(stored) == {"tool": "claude", "role": "reviewer", "profile": "reviewer-renata"}
    mixed = {"tool": "claude", "role": _email(), "profile": None}
    assert projector.actor(mixed) == {"tool": "claude", "role": None, "profile": None}


def test_a_model_sentinel_reads_as_null(projector: helper.Projector) -> None:
    assert projector.handle("__resolved_model_absent__") is None
    assert projector.handle("sonnet") == "sonnet"


def test_a_strict_field_is_nulled_when_nullable_and_an_error_otherwise(projector: helper.Projector) -> None:
    leaked = SLASH + "work" + SLASH + "branch"
    assert projector.strict("main", "targetBranch", nullable=False) == "main"
    assert projector.strict(leaked, "mergeTargetBranch", nullable=True) is None
    assert projector.redactions == [("m", "mergeTargetBranch", "nulled")]
    with pytest.raises(helper.ProjectionError, match="not representable"):
        projector.strict(leaked, "targetBranch", nullable=False)
    with pytest.raises(helper.ProjectionError, match="missing"):
        projector.strict(None, "slug", nullable=False)
    assert projector.strict(None, "missionType", nullable=True) is None
    with pytest.raises(helper.ProjectionError):
        projector.strict("", "slug", nullable=False)


def test_a_strict_value_that_misses_its_pattern_is_not_representable(projector: helper.Projector) -> None:
    with pytest.raises(helper.ProjectionError):
        projector.strict("not a work package id", "wpId", nullable=False, pattern=re.compile(r"^WP[0-9]+$"))
    assert projector.strict_list(None, "dependencies") == []
    assert projector.strict_list(["WP01", "WP02"], "dependencies") == ["WP01", "WP02"]
    with pytest.raises(helper.ProjectionError, match="expected a list"):
        projector.strict_list("WP01", "dependencies")


def test_human_text_has_only_the_matching_substring_replaced(projector: helper.Projector) -> None:
    text = f"Moved notes from {_home_path()} and mailed {_email()} today"
    redacted = projector.human(text, "reason")
    assert redacted == "Moved notes from [path] and mailed [email] today"
    assert [(field, kind) for _, field, kind in projector.redactions] == [("reason", "path"), ("reason", "email")]


def test_clean_human_text_passes_through_untouched(projector: helper.Projector) -> None:
    for clean in ("~/.kittify Runtime Centralization", SLASH + "tmp burn-down: sync", "Nothing sensitive here.", ""):
        assert projector.human(clean, "title") == clean
    assert projector.human(None, "title") is None
    assert projector.redactions == []


def test_a_windows_path_in_prose_is_replaced_too(projector: helper.Projector) -> None:
    text = "see C:" + BACKSLASH + "Users" + BACKSLASH + "someone" + BACKSLASH + "notes for details"
    assert projector.human(text, "reason") == "see [path] for details"


def test_a_lane_is_null_for_the_non_display_lanes_and_an_error_for_an_unknown_one(projector: helper.Projector) -> None:
    assert projector.lane("genesis", "from") is None
    assert projector.lane("uninitialized", "from") is None
    assert projector.lane(None, "from") is None
    assert projector.lane("in_review", "to") == "in_review"
    with pytest.raises(helper.ProjectionError, match="not a status lane"):
        projector.lane("doing", "to")


def test_a_quoted_execution_mode_is_normalised() -> None:
    assert helper.normalise_quoted('"code_change"') == "code_change"
    assert helper.normalise_quoted("'planning_artifact'") == "planning_artifact"
    assert helper.normalise_quoted("code_change") == "code_change"
    assert helper.normalise_quoted('""') is None
    assert helper.normalise_quoted(None) is None


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("lanes", "lanes"),
        ("single_branch", "single_branch"),
        ("coord", "coord"),
        ("lanes_with_coord", "lanes_with_coord"),
        (None, "unknown"),
        ("flat", "unknown"),
        (3, "unknown"),
    ],
)
def test_topology_maps_to_unknown_when_unstamped_or_unrecognised(stored: Any, expected: str) -> None:
    assert helper.topology_of({"topology": stored}) == expected
    assert helper.topology_of({}) == "unknown"


# ---------------------------------------------------------------------------
# The fixture repository the builders run against
# ---------------------------------------------------------------------------


def _fixture_rows() -> list[dict[str, Any]]:
    t = "2026-09-01T10:{minute}:00+00:00".format
    leaked_reason = f"checked {_home_path('notes')} with {_email()}"
    return [
        helper.lifecycle_row(1, "MissionCreated", t(minute="00"), aggregate_id=helper.fixture_ulid(1), payload={"actor": _email()}),
        helper.lifecycle_row(2, "SpecifyStarted", t(minute="01")),
        helper.lifecycle_row(3, "SpecifyCompleted", t(minute="02")),
        helper.lifecycle_row(4, "PlanStarted", t(minute="03")),
        helper.lifecycle_row(5, "WPCreated", t(minute="04"), aggregate_id="WP01"),
        helper.transition_row(1, "WP01", "genesis", "planned", at=t(minute="05"), actor="finalize-tasks", reason="canonical bootstrap"),
        helper.transition_row(2, "WP02", "genesis", "planned", at=t(minute="05"), actor="finalize-tasks"),
        helper.transition_row(
            3,
            "WP01",
            "planned",
            "claimed",
            at=t(minute="06"),
            actor={"tool": "claude", "role": "implementer", "profile": "implementer-ivan", "model": "sonnet"},
            policy_metadata={"agent": "claude"},
        ),
        helper.annotation_row(
            1,
            "WP01",
            {
                "agent": "claude",
                "assignee": "real-assignee",
                "role": "implementer",
                "agent_profile": "implementer-ivan",
                "model": "__resolved_model_absent__",
                "subtasks": {"T001": "done", "T002": "planned"},
            },
            at=t(minute="07"),
        ),
        helper.transition_row(4, "WP01", "claimed", "in_progress", at=t(minute="08"), actor="claude"),
        helper.transition_row(5, "WP01", "in_progress", "for_review", at=t(minute="09"), actor="claude", force=True, reason=leaked_reason),
        helper.transition_row(
            6,
            "WP01",
            "for_review",
            "approved",
            at=t(minute="10"),
            actor=_email(),
            review_result={"reviewer": "reviewer-renata", "verdict": "approved", "reference": f"cycle at {_home_path('cycle')}"},
        ),
        helper.annotation_row(2, "WP01", {"review": {"at": t(minute="11"), "actor": "operator", "wp_id": "WP01", "reason": "out of band"}}, at=t(minute="11")),
        helper.transition_row(7, "WP03", "genesis", "planned", at=t(minute="12"), actor="finalize-tasks"),
        helper.transition_row(8, "WP03", "planned", "canceled", at=t(minute="13"), actor="user", reason="superseded by WP01"),
    ]


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("status-fixture-repo")
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("project:\n  slug: fixture-project\n", encoding="utf-8")
    helper.write_fixture_mission(
        root,
        MISSION,
        meta={"mission_number": 12, "topology": "lanes", "accepted_at": None, "baseline_merge_commit": "a" * 40, "friendly_name": "Alpha " + _email()},
        work_packages={
            "WP01": {
                "dependencies": [],
                "phase": "Foundations",
                "execution_mode": '"code_change"',
                "agent": "stale-agent",
                "assignee": "stale-assignee",
                "lane": "done",
                "requirement_refs": ["FR-001"],
                "owned_files": ["src/example.py"],
                "tracker_refs": ["#5558"],
                "subtasks": ["T001", "T002"],
                "role": "implementer",
                "agent_profile": "implementer-ivan",
                "model": "sonnet",
            },
            "WP02": {"dependencies": ["WP01"]},
            "WP03": {"dependencies": ["WP01"]},
            "WP04": {"dependencies": ["WP02"], "title": "A file with no events"},
        },
        rows=_fixture_rows(),
        planning_files=["spec.md"],
    )
    helper.write_fixture_mission(
        root,
        "empty-mission",
        meta={"mission_id": helper.fixture_ulid(2), "mission_slug": "empty-mission", "slug": "empty-mission", "created_at": "2026-09-03T00:00:00Z"},
    )
    return root


@pytest.fixture(scope="module")
def source(fixture_repo: Path) -> helper.MissionSource:
    return helper.load_source(fixture_repo, MISSION)


def _payloads(source: helper.MissionSource, tools: helper.ContractTools) -> tuple[helper.Projector, dict[str, Any]]:
    projector = helper.Projector(tools.leak, source.name)
    files = {item.metadata.work_package_id: item for item in helper.read_authored_files(source.own_dir)}
    return projector, {wp_id: helper.build_work_package(source, item, projector) for wp_id, item in files.items()}


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def test_the_overview_carries_the_snapshot_and_the_meta_values(source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract) -> None:
    projector = helper.Projector(tools.leak, MISSION)
    overview = helper.build_overview(source, projector)
    assert contract.errors(helper.SCHEMA_OVERVIEW, overview) == []
    assert helper.payload_leaks(overview, tools) == []
    assert overview["missionId"] == helper.fixture_ulid(1)
    assert overview["mid8"] == helper.fixture_ulid(1)[:8]
    assert overview["displayNumber"] == 12
    assert overview["topology"] == "lanes"
    assert overview["wpTotal"] == 3, "WP04 has a file and no events: it is not counted (D-4)"
    assert overview["statusLaneCounts"] == _counts(planned=1, approved=1, canceled=1)
    assert overview["blockedCount"] == 0
    assert overview["lifecycleStatus"] == "active"
    assert overview["friendlyName"] == "Alpha [email]"
    assert [field for _, field, _ in projector.redactions] == ["friendlyName"]
    assert overview["lastActivityAt"] == "2026-09-01T10:13:00+00:00"
    assert overview["lastEventId"] == source.snapshot.last_event_id
    assert overview["eventCount"] == source.snapshot.event_count
    assert overview["streamCursor"]["offset"] == (source.read_dir / "status.events.jsonl").stat().st_size
    assert overview["nextAction"] is not None and MISSION in overview["nextAction"], "a merge baseline and no acceptance"
    assert overview["progress"]["semantics"] == "weighted_readiness"
    assert overview["progress"]["doneCount"] == 0


def test_a_mission_with_no_event_log_is_a_draft_with_the_empty_cursor(fixture_repo: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    empty = helper.load_source(fixture_repo, "empty-mission")
    overview = helper.build_overview(empty, helper.Projector(tools.leak, "empty-mission"))
    assert contract.errors(helper.SCHEMA_OVERVIEW, overview) == []
    assert overview["lifecycleStatus"] == "draft"
    assert overview["wpTotal"] == 0 and overview["lastEventId"] is None and overview["lastActivityAt"] is None
    assert overview["streamCursor"] == {"offset": 0, "invariant": EMPTY_DIGEST}
    assert overview["topology"] == "unknown", "no stored topology"
    assert overview["displayNumber"] is None


def test_a_discarded_mission_projects_as_discarded(fixture_repo: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    helper.write_fixture_mission(fixture_repo, "discarded-mission", meta={"mission_id": helper.fixture_ulid(3), "discarded_at": "2026-09-05T00:00:00Z"})
    overview = helper.build_overview(helper.load_source(fixture_repo, "discarded-mission"), helper.Projector(tools.leak, "discarded-mission"))
    assert contract.errors(helper.SCHEMA_OVERVIEW, overview) == []
    assert overview["lifecycleStatus"] == "discarded" and overview["discardedAt"] == "2026-09-05T00:00:00Z"


def test_a_mission_without_an_identity_has_a_null_mid8_and_is_refused_as_an_overview(fixture_repo: Path, tools: helper.ContractTools) -> None:
    helper.write_fixture_mission(fixture_repo, "legacy-mission", meta={"mission_id": None})
    legacy = helper.load_source(fixture_repo, "legacy-mission")
    with pytest.raises(helper.ProjectionError, match="missionId"):
        helper.build_overview(legacy, helper.Projector(tools.leak, "legacy-mission"))


def test_the_detail_lists_the_file_backed_work_packages_sorted_with_five_phases(
    source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract
) -> None:
    detail = helper.build_detail(source, helper.Projector(tools.leak, MISSION))
    assert contract.errors(helper.SCHEMA_DETAIL, detail) == []
    assert [item["wpId"] for item in detail["workPackages"]] == ["WP01", "WP02", "WP03", "WP04"]
    assert detail["wpTotal"] == 3 and len(detail["workPackages"]) == 4, "wpTotal may differ from the number of files"
    assert [(phase["name"], phase["status"]) for phase in detail["phases"]] == [
        ("specify", "complete"),
        ("plan", "in_progress"),
        ("tasks", "pending"),
        ("implement", "in_progress"),
        ("review", "in_progress"),
    ]
    summaries = {item["wpId"]: item for item in detail["workPackages"]}
    assert summaries["WP04"]["statusLane"] is None and summaries["WP04"]["readyToStart"] is False, "no events: a null lane is never ready"
    assert summaries["WP04"]["readiness"] == {"satisfied": False, "unsatisfied": ["WP02"]}
    assert summaries["WP02"]["readiness"] == {"satisfied": True, "unsatisfied": []}
    assert summaries["WP02"]["readyToStart"] is True, "planned with its dependency approved"
    assert summaries["WP01"]["subtaskProgress"] == {"done": 1, "total": 2}


def test_a_release_marker_is_not_an_override(tools: helper.ContractTools) -> None:
    """All four fields empty clears an override; it is the only record projected as null."""
    marker = {"at": "", "actor": "", "wp_id": "", "reason": ""}
    assert helper.review_override(marker, helper.Projector(tools.leak, "m"), "WP01") is None
    assert helper.review_override(None, helper.Projector(tools.leak, "m"), "WP01") is None
    assert helper.review_override({}, helper.Projector(tools.leak, "m"), "WP01") is None


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ({"at": "", "actor": "operator", "wp_id": "WP01", "reason": "out of band"}, {"complete": False, "at": None, "actor": "operator", "reason": "out of band"}),
        (
            {"at": "2026-09-01T10:11:00+00:00", "actor": "", "wp_id": "WP01", "reason": "out of band"},
            {"complete": False, "at": "2026-09-01T10:11:00+00:00", "actor": None, "reason": "out of band"},
        ),
        (
            {"at": "2026-09-01T10:11:00+00:00", "actor": "operator", "wp_id": "WP01", "reason": ""},
            {"complete": False, "at": "2026-09-01T10:11:00+00:00", "actor": "operator", "reason": None},
        ),
        (
            {"at": "2026-09-01T10:11:00+00:00", "actor": "operator", "wp_id": "", "reason": "out of band"},
            {"complete": False, "at": "2026-09-01T10:11:00+00:00", "actor": "operator", "reason": "out of band"},
        ),
        (
            {"at": "2026-09-01T10:11:00+00:00", "actor": "operator", "reason": "out of band"},
            {"complete": False, "at": "2026-09-01T10:11:00+00:00", "actor": "operator", "reason": "out of band"},
        ),
        (
            {"at": None, "actor": "operator", "wp_id": "WP01", "reason": "out of band"},
            {"complete": False, "at": None, "actor": "operator", "reason": "out of band"},
        ),
        (
            {"at": "2026-09-01T10:11:00+00:00", "actor": "operator", "wp_id": "   ", "reason": "out of band"},
            {"complete": True, "at": "2026-09-01T10:11:00+00:00", "actor": "operator", "reason": "out of band"},
        ),
        (
            {"at": "   ", "actor": "operator", "wp_id": "WP01", "reason": ""},
            {"complete": False, "at": None, "actor": "operator", "reason": None},
        ),
    ],
    ids=["blank-at", "blank-actor", "blank-reason", "blank-wp-id", "missing-wp-id", "null-at", "whitespace-wp-id", "whitespace-at-partial"],
)
def test_a_partial_review_override_is_shown_as_incomplete_never_hidden(
    tools: helper.ContractTools, contract: helper.Contract, stored: dict[str, Any], expected: dict[str, Any]
) -> None:
    """The code keeps a partial record (it blocks the merge gate); the contract shows it with complete false and null blanks.

    Whitespace is a value, as in the code: a whitespace-only wp_id is complete (``bool("   ")`` is true).
    """
    projected = helper.review_override(stored, helper.Projector(tools.leak, "m"), "WP01")

    assert projected == expected
    assert contract.errors(helper.SCHEMA_REVIEW_OVERRIDE, projected) == []


def test_a_complete_review_override_needs_the_work_package_id_too(tools: helper.ContractTools, contract: helper.Contract) -> None:
    stored = {"at": "2026-09-01T10:11:00+00:00", "actor": "operator", "wp_id": "WP01", "reason": "out of band"}

    projected = helper.review_override(stored, helper.Projector(tools.leak, "m"), "WP01")

    assert projected == {"complete": True, "at": "2026-09-01T10:11:00+00:00", "actor": "operator", "reason": "out of band"}
    assert contract.errors(helper.SCHEMA_REVIEW_OVERRIDE, projected) == []


def test_resolved_state_comes_from_the_snapshot_not_from_stale_frontmatter(
    source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract
) -> None:
    projector, payloads = _payloads(source, tools)
    first = payloads["WP01"]
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, first) == []
    assert first["statusLane"] == "approved", "the frontmatter says done"
    assert first["assignment"]["agent"] == "claude" and first["assignment"]["assignee"] == "real-assignee"
    assert first["assignment"]["model"] is None, "the absent-model sentinel reads as null"
    assert first["assignment"]["role"] == "implementer" and first["assignment"]["agentProfile"] == "implementer-ivan"
    assert first["authored"] == {"role": "implementer", "agentProfile": "implementer-ivan", "model": "sonnet", "subtasks": ["T001", "T002"]}
    assert first["executionMode"] == "code_change", "the quoted value is normalised"
    assert first["phaseLabel"] == "Foundations" and first["ownedFiles"] == ["src/example.py"] and first["trackerRefs"] == ["#5558"]
    assert first["subtasks"] == {"T001": "done", "T002": "planned"}
    assert first["forceCount"] == 1 and first["implementerOfRecord"] == "claude"
    assert first["actor"] == {"tool": None, "role": None, "profile": None}, "the latest actor was an e-mail address"
    assert first["review"]["latestResult"] == {"reviewer": "reviewer-renata", "verdict": "approved", "reference": "cycle at [path]"}
    assert first["review"]["override"] == {"complete": True, "at": "2026-09-01T10:11:00+00:00", "actor": "operator", "reason": "out of band"}
    assert first["cancellation"] is None and first["staleness"] is None
    assert "promptMarkdown" not in first
    redacted = {(field, kind) for _, field, kind in projector.redactions}
    assert ("WP01.history.reason", "path") in redacted and ("WP01.history.reason", "email") in redacted
    assert ("WP01.review.latestResult.reference", "path") in redacted


def test_history_lists_transitions_only_oldest_first(source: helper.MissionSource, tools: helper.ContractTools) -> None:
    _, payloads = _payloads(source, tools)
    history = payloads["WP01"]["history"]
    assert [(entry["fromStatusLane"], entry["toStatusLane"]) for entry in history] == [
        (None, "planned"),
        ("planned", "claimed"),
        ("claimed", "in_progress"),
        ("in_progress", "for_review"),
        ("for_review", "approved"),
    ]
    assert {entry["kind"] for entry in history} == {"transition"}, "annotation and lifecycle rows never appear"
    assert history[0]["actor"] == {"tool": "finalize-tasks", "role": None, "profile": None}
    assert history[1]["actor"] == {"tool": "claude", "role": "implementer", "profile": "implementer-ivan"}
    assert history[3]["force"] is True and history[4]["reviewVerdict"] == "approved" and history[0]["reviewVerdict"] is None
    assert [entry["at"] for entry in history] == sorted(entry["at"] for entry in history)


def test_history_is_ordered_by_time_then_event_id_whatever_order_the_log_was_written_in(tmp_path: Path, tools: helper.ContractTools) -> None:
    """The log is written out of order, and two transitions share an instant with their event ids in the opposite order."""
    t = "2026-09-01T10:{minute}:00+00:00".format
    written_order = [
        helper.transition_row(4, "WP01", "in_progress", "for_review", at=t(minute="08")),
        helper.transition_row(2, "WP01", "planned", "claimed", at=t(minute="06")),
        helper.transition_row(3, "WP01", "claimed", "in_progress", at=t(minute="08")),
        helper.transition_row(1, "WP01", "genesis", "planned", at=t(minute="05")),
    ]
    helper.write_fixture_mission(tmp_path, MISSION, work_packages={"WP01": {"dependencies": []}}, rows=written_order)
    shuffled = helper.load_source(tmp_path, MISSION)
    assert [row["event_id"] for row in shuffled.rows if "to_lane" in row] == [row["event_id"] for row in written_order], "the reader keeps the file order"
    _, payloads = _payloads(shuffled, tools)
    history = payloads["WP01"]["history"]
    assert [entry["eventId"] for entry in history] == [helper.fixture_ulid(1000 + number) for number in (1, 2, 3, 4)]
    assert [entry["toStatusLane"] for entry in history] == ["planned", "claimed", "in_progress", "for_review"]
    assert history[2]["at"] == history[3]["at"], "the tie is broken by the event id, not by the file order"


def test_a_canceled_work_package_carries_its_cancellation(source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract) -> None:
    _, payloads = _payloads(source, tools)
    canceled = payloads["WP03"]
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, canceled) == []
    assert canceled["statusLane"] == "canceled"
    assert canceled["cancellation"] == {"reasonSource": "operator", "reason": "superseded by WP01"}
    assert canceled["readyToStart"] is False


def test_a_work_package_with_no_events_reads_as_empty_state(source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract) -> None:
    _, payloads = _payloads(source, tools)
    bare = payloads["WP04"]
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, bare) == []
    assert bare["title"] == "A file with no events"
    assert bare["statusLane"] is None and bare["lastTransitionAt"] is None and bare["lastEventId"] is None
    assert bare["forceCount"] == 0 and bare["subtasks"] == {} and bare["subtaskProgress"] == {"done": 0, "total": 0}
    assert bare["assignment"] == dict.fromkeys(("agent", "assignee", "role", "agentProfile", "agentProfileVersion", "model", "provider"))
    assert bare["history"] == [] and bare["review"] == {"latestResult": None, "override": None}
    assert bare["actor"] == {"tool": None, "role": None, "profile": None}


def test_the_prompt_body_is_returned_only_on_request(source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract) -> None:
    projector = helper.Projector(tools.leak, MISSION)
    authored = next(item for item in helper.read_authored_files(source.own_dir) if item.metadata.work_package_id == "WP02")
    with_prompt = helper.build_work_package(source, authored, projector, include_prompt=True)
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, with_prompt) == []
    assert "Body of WP02" in with_prompt["promptMarkdown"]
    assert "promptMarkdown" not in helper.build_work_package(source, authored, projector)
    authored_text = {**with_prompt, "promptMarkdown": "see " + _home_path() + " and " + _email()}
    assert helper.payload_leaks(authored_text, tools) == [], "authored markdown is excluded from corpus payload scans"


def test_a_planted_leak_in_a_built_payload_is_found_and_the_clean_control_is_not(source: helper.MissionSource, tools: helper.ContractTools) -> None:
    _, payloads = _payloads(source, tools)
    clean = payloads["WP01"]
    assert helper.payload_leaks(clean, tools) == []
    emailed = {**clean, "title": "Fix for " + _email()}
    assert any("EMAIL" in finding for finding in helper.payload_leaks(emailed, tools))
    pathed = {**clean, "mergeTargetBranch": _home_path("branch")}
    assert any("HOST_PATH" in finding for finding in helper.payload_leaks(pathed, tools))
    named = {**clean, "feedback" + "Path": "x"}
    assert any("FORBIDDEN_PROPERTY_NAME" in finding for finding in helper.payload_leaks(named, tools))


def test_the_contract_rejects_an_unknown_lane_and_an_extra_property(source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract) -> None:
    _, payloads = _payloads(source, tools)
    clean = payloads["WP01"]
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, clean) == []
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, {**clean, "statusLane": "doing"}), "an unknown status lane must fail"
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, {**clean, "extra": 1}), "an extra property must fail"
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, {key: value for key, value in clean.items() if key != "history"}), "a missing required property must fail"


def test_an_unusable_work_package_id_is_a_projection_error(source: helper.MissionSource, tools: helper.ContractTools) -> None:
    authored = helper.read_authored_files(source.own_dir)[0]
    broken = helper.AuthoredWorkPackage(authored.path, authored.metadata.model_copy(update={"work_package_id": "not a wp id"}), authored.body)
    with pytest.raises(helper.ProjectionError, match="wpId"):
        helper.build_work_package(source, broken, helper.Projector(tools.leak, MISSION))


def test_a_mission_without_a_tasks_directory_has_no_authored_files(tmp_path: Path) -> None:
    assert helper.read_authored_files(tmp_path) == []
    assert helper.count_work_package_files(tmp_path) == 0


def test_the_project_name_is_read_from_the_config(fixture_repo: Path, tmp_path: Path) -> None:
    assert helper.read_project_name(fixture_repo) == "fixture-project"
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("project: {}\n", encoding="utf-8")
    with pytest.raises(helper.ProjectionError, match="project.slug"):
        helper.read_project_name(tmp_path)


# ---------------------------------------------------------------------------
# Event projection
# ---------------------------------------------------------------------------


def test_only_transitions_and_the_seven_lifecycle_types_are_forwarded(source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract) -> None:
    projector = helper.Projector(tools.leak, MISSION)
    projection = helper.project_events(helper.fixture_ulid(1), source.rows, projector)
    kinds = [kind for kind, _ in projection.events]
    assert kinds.count("status-transition") == 8 and kinds.count("mission-lifecycle") == 4
    for kind, event in projection.events:
        title = helper.SCHEMA_TRANSITION_EVENT if kind == "status-transition" else helper.SCHEMA_LIFECYCLE_EVENT
        assert contract.errors(title, event) == [], event
        assert event["missionId"] == helper.fixture_ulid(1), "the identity of meta.json, never aggregate_id"
    assert dict(projection.dropped) == {"annotation": 2, "WPCreated": 1}


def test_the_projector_work_package_rule_is_the_contracts_wpid_pattern() -> None:
    document = yaml.safe_load((REPO_ROOT / "contracts" / "mission-status" / "schemas" / "WpId.yaml").read_text(encoding="utf-8"))
    assert document["pattern"] == helper.WP_ID_PATTERN and document["maxLength"] == helper.WP_ID_MAX_LENGTH
    assert helper.is_wp_id("WP01") and helper.is_wp_id("WP100")
    for bad in ("WP1", "wp01", "WP-01", "01", "WP01 ", "", None, 1, "WP" + "0" * 70):
        assert not helper.is_wp_id(bad), bad


@pytest.mark.parametrize("bad_id", ["WP1", "wp01", "legacy-7", "", None], ids=["one-digit", "lower-case", "legacy", "empty", "null"])
def test_a_transition_whose_work_package_id_fails_the_contract_rule_is_dropped_counted_and_never_forwarded(
    bad_id: Any, source: helper.MissionSource, tools: helper.ContractTools, contract: helper.Contract
) -> None:
    good = next(row for row in source.rows if "to_lane" in row)
    planted = {**good, "wp_id": bad_id, "event_id": "PLANTED"}
    projection = helper.project_events(helper.fixture_ulid(1), [planted, good], helper.Projector(tools.leak, MISSION))

    assert [event["eventId"] for kind, event in projection.events if kind == "status-transition"] == [good["event_id"]]
    assert projection.dropped == {helper.DROPPED_INVALID_WP_ID: 1}
    for kind, event in projection.events:
        assert contract.errors(helper.SCHEMA_TRANSITION_EVENT if kind == "status-transition" else helper.SCHEMA_LIFECYCLE_EVENT, event) == []


@pytest.mark.parametrize("event_type", sorted(helper.LIFECYCLE_ALLOW_LIST))
def test_each_of_the_seven_lifecycle_types_is_forwarded(event_type: str, tools: helper.ContractTools, contract: helper.Contract) -> None:
    row = {**helper.lifecycle_row(1, event_type, LATER), "tail_offset": 10, "tail_invariant": "0" * 64}
    projection = helper.project_events(helper.fixture_ulid(1), [row], helper.Projector(tools.leak, "m"))
    assert [kind for kind, _ in projection.events] == ["mission-lifecycle"] and not projection.dropped
    assert contract.errors(helper.SCHEMA_LIFECYCLE_EVENT, projection.events[0][1]) == []


@pytest.mark.parametrize("event_type", sorted(set(LIFECYCLE_EVENT_TYPES) - helper.LIFECYCLE_ALLOW_LIST))
def test_every_other_runtime_lifecycle_type_is_dropped_and_counted(event_type: str, tools: helper.ContractTools) -> None:
    projection = helper.project_events(helper.fixture_ulid(1), [helper.lifecycle_row(1, event_type, LATER)], helper.Projector(tools.leak, "m"))
    assert projection.events == [] and projection.dropped == {event_type: 1}


def test_an_unknown_row_kind_is_dropped_never_forwarded(tools: helper.ContractTools) -> None:
    rows: list[dict[str, Any]] = [
        {"event_id": "x", "weird": True},
        {"event_id": "y", "type": "RetrospectiveCaptured", "record_path": SLASH + "somewhere"},
        {"event_id": "z", "event_type": "FutureLifecycleType", "timestamp": LATER},
        {"event_id": "w", "kind": "annotation"},
    ]
    projection = helper.project_events(helper.fixture_ulid(1), rows, helper.Projector(tools.leak, "m"))
    assert projection.events == []
    assert dict(projection.dropped) == {"unknown-row": 1, "RetrospectiveCaptured": 1, "FutureLifecycleType": 1, "annotation": 1}


def test_the_events_carry_the_tail_readers_cursor_after_each_row(source: helper.MissionSource, tools: helper.ContractTools) -> None:
    projection = helper.project_events(helper.fixture_ulid(1), source.rows, helper.Projector(tools.leak, MISSION))
    offsets = [event["streamCursor"]["offset"] for _, event in projection.events]
    assert offsets == sorted(offsets) and offsets[-1] <= source.cursor.offset
    assert all(re.fullmatch(r"[0-9a-f]{64}", event["streamCursor"]["invariant"]) for _, event in projection.events)


def test_the_types_dropped_by_design_are_listed() -> None:
    assert helper.undeclared_lifecycle_types() == sorted(set(LIFECYCLE_EVENT_TYPES) - helper.LIFECYCLE_ALLOW_LIST)
    assert "WPCreated" in helper.undeclared_lifecycle_types() and "MissionCreated" not in helper.undeclared_lifecycle_types()


# ---------------------------------------------------------------------------
# Reader chain, own-directory pass, floors and the pinned fixture
# ---------------------------------------------------------------------------


class _Status:
    def __init__(self, read_dir: Path) -> None:
        self.read_dir = read_dir


def _stub_load(mp: pytest.MonkeyPatch, behaviour: Callable[..., Any]) -> None:
    mp.setattr(MissionStatus, "load", classmethod(lambda cls, repo_root, slug: behaviour(repo_root, slug)))


def _raise(error: Exception) -> Callable[..., Any]:
    def behave(repo_root: Path, slug: str) -> Any:
        raise error

    return behave


def _unavailable(kind: str, root: Path) -> Exception:
    place = root / "kitty-specs" / MISSION
    error: Exception
    if kind == "CoordAuthorityUnavailable":
        error = CoordAuthorityUnavailable(mission_slug=MISSION, coord_candidate=root / "coord", primary_candidate=place)
    elif kind == "MissionMetadataUnavailable":
        error = MissionMetadataUnavailable(mission_slug=MISSION, meta_path=place / "meta.json", primary_candidate=place, reason="unreadable")
    else:
        error = CoordinationBranchDeleted(
            repo_root=root, mission_slug=MISSION, mid8="01234567", coordination_branch="kitty/coord", coord_candidate=root / "coord", primary_candidate=place
        )
    return error


@pytest.mark.parametrize("kind", ["CoordAuthorityUnavailable", "MissionMetadataUnavailable", "CoordinationBranchDeleted"])
def test_an_unavailable_coordination_surface_falls_back_to_the_own_directory(kind: str, fixture_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_load(monkeypatch, _raise(_unavailable(kind, fixture_repo)))
    read_dir, reason = helper.resolve_read_dir(fixture_repo, MISSION)
    assert read_dir == fixture_repo / "kitty-specs" / MISSION and reason == kind


def test_a_read_directory_outside_the_checkout_falls_back_and_one_inside_it_is_used(fixture_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    own = fixture_repo / "kitty-specs" / MISSION
    _stub_load(monkeypatch, lambda repo_root, slug: _Status(tmp_path / "elsewhere"))
    assert helper.resolve_read_dir(fixture_repo, MISSION) == (own, "read directory outside this checkout")
    coord = fixture_repo / ".worktrees" / "coord" / "kitty-specs" / MISSION
    _stub_load(monkeypatch, lambda repo_root, slug: _Status(coord))
    assert helper.resolve_read_dir(fixture_repo, MISSION) == (coord, None)
    _stub_load(monkeypatch, lambda repo_root, slug: _Status(own))
    assert helper.resolve_read_dir(fixture_repo, MISSION) == (own, None)


def test_the_real_reader_chain_resolves_a_plain_mission_to_its_own_directory(fixture_repo: Path) -> None:
    read_dir, reason = helper.resolve_read_dir(fixture_repo, MISSION)
    assert read_dir == fixture_repo / "kitty-specs" / MISSION and reason is None


def test_the_own_directory_pass_counts_snapshot_files_lanes_lifecycle_and_topology(fixture_repo: Path) -> None:
    by_name = {item.name: item for item in helper.own_directory_pass(fixture_repo)}
    alpha = by_name[MISSION]
    assert (alpha.snapshot_work_packages, alpha.work_package_files) == (3, 4)
    assert alpha.lane_counts == _counts(planned=1, approved=1, canceled=1) and alpha.lifecycle == "active" and alpha.topology == "lanes"
    assert by_name["empty-mission"].lifecycle == "draft" and by_name["empty-mission"].topology == "unknown"
    assert helper.disagreement_list(by_name.values()) == [(MISSION, 3, 4)], "a file with no events is counted, never dropped"


def test_the_floors_fail_on_a_small_corpus_and_name_each_gap(fixture_repo: Path) -> None:
    failures = helper.floor_failures(helper.own_directory_pass(fixture_repo))
    text = "; ".join(failures)
    assert "Missions with a meta.json" in text and "snapshot work packages" in text and "work package files" in text
    assert "no Mission has a work package in the blocked lane" in text and "no Mission reads as done" in text and "no Mission has the topology coord" in text


def test_the_floors_pass_on_a_corpus_that_meets_them() -> None:
    lanes = dict.fromkeys(helper.STATUS_LANES, 1)
    topologies = (*helper.TOPOLOGIES, helper.UNKNOWN_TOPOLOGY)
    kinds = ("active", "planned", "done", "draft")
    corpus = [helper.OwnMission(f"m{index}", 6, 7, lanes, kinds[index % 4], topologies[index % 5]) for index in range(helper.FLOORS.missions)]
    assert helper.floor_failures(corpus) == []
    assert helper.floor_failures(corpus[:-1]) != [], "one Mission fewer than the floor must fail"


def test_an_empty_enumeration_and_a_non_mission_directory_are_handled(tmp_path: Path) -> None:
    assert helper.enumerate_missions(tmp_path) == []
    (tmp_path / "kitty-specs" / "not-a-mission").mkdir(parents=True)
    assert helper.enumerate_missions(tmp_path) == []
    with pytest.raises(helper.EmptyCaseListError):
        helper.require_cases([])
    assert helper.require_cases(["a"]) == ["a"]


def test_the_pinned_fixture_agrees_with_the_helper_and_covers_every_documented_quirk() -> None:
    expected = helper.load_expected(REPO_ROOT)
    assert {"active", "planned", "done", "draft", "discarded"} <= helper.sample_covers(expected)
    labels = {entry["mission"] for entry in expected["sample"]}
    assert "blocked-only-reads-as-planned" in labels and "all-canceled-with-acceptedAt-reads-as-done" in labels
    synthetic = [entry for entry in expected["sample"] if entry["kind"] == "synthetic"]
    assert helper.expected_mismatches({"sample": synthetic}, lambda label: {}) == []


def test_altering_the_helper_rule_makes_the_comparison_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = helper.load_expected(REPO_ROOT)
    synthetic = {"sample": [entry for entry in expected["sample"] if entry["kind"] == "synthetic"]}
    assert helper.expected_mismatches(synthetic, lambda label: {}) == [], "control: the unmodified helper agrees"
    real_rule = helper.derive_lifecycle_status

    def mutated(counts: Mapping[str, int], total: int, discarded: str | None, accepted: str | None) -> str:
        # The mutation drops the blocked-reads-as-planned quirk: blocked alone becomes active.
        return "active" if counts.get("blocked") and not counts.get("planned") else real_rule(counts, total, discarded, accepted)

    monkeypatch.setattr(helper, "derive_lifecycle_status", mutated)
    assert any("blocked-only-reads-as-planned" in problem for problem in helper.expected_mismatches(synthetic, lambda label: {}))


def test_a_real_entry_whose_lane_counts_moved_is_reported_as_a_stale_sample() -> None:
    entry = {"mission": "m", "kind": "real", "statusLaneCounts": _counts(done=2), "expected": {"lifecycleStatus": "active", "nextAction": None}}
    moved = {"statusLaneCounts": _counts(done=3), "lifecycleStatus": "active", "nextAction": None}
    assert "stale sample" in helper.expected_mismatches({"sample": [entry]}, lambda label: moved)[0]
    same = {"statusLaneCounts": _counts(done=2), "lifecycleStatus": "done", "nextAction": None}
    assert "lifecycleStatus is 'done'" in helper.expected_mismatches({"sample": [entry]}, lambda label: same)[0]
    assert helper.expected_mismatches({"sample": [entry]}, lambda label: {**same, "lifecycleStatus": "active"}) == []


def test_a_malformed_pinned_fixture_is_refused(tmp_path: Path) -> None:
    target = tmp_path / helper.EXPECTED_FIXTURE
    target.parent.mkdir(parents=True)
    for bad in ('{"header": {}, "sample": []}', '{"header": [], "sample": [1]}', "[]"):
        target.write_text(bad, encoding="utf-8")
        with pytest.raises(ValueError, match="header and a non-empty sample"):
            helper.load_expected(tmp_path)


def test_the_fixture_directory_lists_exactly_what_git_tracks_and_holds_no_archive() -> None:
    directory = REPO_ROOT / "tests" / "contract" / "fixtures"
    on_disk = sorted(path.relative_to(REPO_ROOT).as_posix() for path in directory.rglob("*") if path.is_file())
    tracked = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "--", "tests/contract/fixtures"], capture_output=True, text=True, check=True).stdout.split()
    assert on_disk == sorted(tracked), "find and git ls-files must list the same files"
    assert not [name for name in on_disk if name.endswith(".zip")], "fixtures are never archives"
    assert json.loads((directory / "mission_status_expected.json").read_text(encoding="utf-8"))


def test_projected_completeness_is_the_code_rule_for_every_whitespace_and_empty_combination(tools: helper.ContractTools) -> None:
    """Mirror ``ReviewOverride`` itself over all 81 blank/whitespace/filled combinations of its four members."""
    values = ("", "   ", "x")
    for at, actor, wp_id, reason in product(values, repeat=4):
        code = ReviewOverride(at=at, actor=actor, wp_id=wp_id, reason=reason)
        stored = {"at": "2026-09-01T10:11:00+00:00" if at == "x" else at, "actor": actor, "wp_id": wp_id, "reason": reason}
        projector = helper.Projector(tools.leak, "m")
        if code.is_release_sentinel:
            assert helper.review_override(stored, projector, "WP01") is None, stored
        elif code.complete and at == "   ":
            with pytest.raises(helper.ProjectionError, match="not representable"):
                helper.review_override(stored, projector, "WP01")
        else:
            shown = helper.review_override(stored, projector, "WP01")
            assert shown is not None and shown["complete"] is code.complete, stored


def test_an_all_whitespace_record_is_not_a_release_marker(tools: helper.ContractTools) -> None:
    """The code keeps it (it is truthy), so the projection never hides it as null."""
    record = {"at": "   ", "actor": "   ", "wp_id": "   ", "reason": "   "}
    assert not ReviewOverride(**record).is_release_sentinel
    with pytest.raises(helper.ProjectionError, match="not representable"):
        helper.review_override(record, helper.Projector(tools.leak, "m"), "WP01")
