"""The reality check: the ``mission-status`` contract against this repository's own Missions (FR-019).

Every Mission directory of the checkout that holds a ``meta.json`` is one parametrised case. The case builds
the overview, the detail and every work package payload and every projected event with the test-side helper,
validates each against the resolved contract (never a skip: an unavailable contract or resolver fails), scans
each for leaks, and re-reads the status snapshot independently to prove the payload carries the snapshot's
values. The numbers that are pinned (floors, the shrink-only disagreement ceiling) come from a cheap
own-directory pass, so the same figures hold in a developer clone and in CI.

Hard rule (the spec-phase incident): nothing here may write to ``kitty-specs/``. The status readers used are
the read-only ones (``materialize_snapshot``, the tail reader, ``load_meta``); the writing ``materialize`` is
never called. The module proves it: a module-scoped fixture fingerprints every tracked file under
``kitty-specs/`` (bytes and ``git status``) before the first case and asserts the same fingerprint after the
last one.

Non-vacuity (FR-025): the case list comes from the same enumeration as the floors pass, an empty list is a
collection error, and the LAST test of this file asserts that the generated cases equal the Missions with a
``meta.json`` and that every one of them actually executed. That count is complete only when the file runs in
definition order in one process: the router's corpus job runs this module serially (no ``-n``), which holds
today. The module must stay serial or run under ``--dist loadfile``; the module-scoped index cache and the
counter assume it.

A Mission that fails validation is never fixed by editing its data. It is a contract gap (fix the schema and
log it as a pre-release shape change), a reader defect, or a data defect (the ratchet in the pinned fixture).
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import os
import re
import subprocess
import textwrap
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from specify_cli.context import mission_resolver
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status.reducer import materialize_snapshot
from tests.contract import _mission_status_artifacts as artifacts
from tests.contract import _mission_status_detail as detail
from tests.contract import _mission_status_payloads as helper
from tests.contract._mission_status_payloads import (
    FLOORS,
    EmptyCaseListError,
    EmptyFingerprintError,
    enumerate_missions,
    floor_failures,
    own_directory_pass,
    require_cases,
    tree_fingerprint,
)

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
KITTY_SPECS = "kitty-specs"
MODULE_DIR = REPO_ROOT / "contracts" / "mission-status"
SLASH = chr(47)
AT = chr(64)

# Collected at import: an empty enumeration is a collection error, never a silent skip.
CASES: list[str] = require_cases(enumerate_missions(REPO_ROOT))

# Every label of a row the projection drops on purpose, with the reason it is not a contract event. The set is explicit so a new row kind
# in a committed log is a decision (map it into the contract, or add it here with its reason), never a silent drop. The lifecycle types
# dropped by design are the helper's own declaration (one source of truth), not a second hand-kept list.
_NOT_A_FORWARDED_TYPE = "not a status transition or one of the seven forwarded lifecycle types"
KNOWN_DROPPED_LABELS: dict[str, str] = {
    **dict.fromkeys(helper.undeclared_lifecycle_types(), "lifecycle type outside the seven the contract forwards (spec FR-007)"),
    "annotation": "assignment and subtask deltas: folded into the snapshot, not an event of the contract",
    "DecisionPointOpened": f"decision-moment row: {_NOT_A_FORWARDED_TYPE}",
    "DecisionPointResolved": f"decision-moment row: {_NOT_A_FORWARDED_TYPE}",
    "RetrospectiveCaptured": f"retrospective row: {_NOT_A_FORWARDED_TYPE}",
    "RetrospectiveCaptureFailed": f"retrospective row: {_NOT_A_FORWARDED_TYPE}",
}

# Filled by the per-Mission case; read by the counting test, which is the last test of the file.
EXECUTED: set[str] = set()


@dataclass
class CaseResult:
    """What one Mission produced: counts for the corpus-level tests and every failure found."""

    overview: dict[str, Any]
    work_packages: int = 0
    events: int = 0
    kinds: Counter[str] = field(default_factory=Counter)
    dropped: Counter[str] = field(default_factory=Counter)
    redactions: list[tuple[str, str, str]] = field(default_factory=list)
    fallback: str | None = None
    seconds: float = 0.0
    failures: list[str] = field(default_factory=list)


CASE_RESULTS: dict[str, CaseResult] = {}


@pytest.fixture(scope="module", autouse=True)
def kitty_specs_is_left_untouched() -> Iterator[None]:
    """Fingerprint every tracked file under ``kitty-specs/`` before the run and compare after it."""
    before = tree_fingerprint(REPO_ROOT, KITTY_SPECS)
    assert before.files > 0, "the read-only proof hashed zero files, so it would prove nothing"
    yield
    after = tree_fingerprint(REPO_ROOT, KITTY_SPECS)
    assert after == before, "the reality check changed something under kitty-specs/ (a reader wrote state)"


@pytest.fixture(scope="module", autouse=True)
def identity_index_is_walked_once(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Walk each real checkout's ``kitty-specs/`` identity index once per module instead of once per reader call.

    Every status and frontmatter reader resolves its Mission handle through ``_build_index``, a fresh walk of
    every ``meta.json`` (the production resolver is deliberately uncached). Over this checkout's whole corpus
    that is about 1900 walks of 540 directories and was most of this module's run time. The walk is a pure
    function of the tree, and the read-only fingerprint fixture above proves the tree is unchanged for the
    whole module, so one walk per root is reused (in a lane worktree the readers resolve to the primary
    checkout, a second root). A planted repository lives under pytest's base temp directory and is always walked
    fresh, and every reader still runs for every Mission: only the directory listing is shared.
    """
    original = mission_resolver._build_index
    planted_under = tmp_path_factory.getbasetemp().resolve()
    walked: dict[Path, list[mission_resolver.ResolvedMission]] = {}

    def once(repo_root: Path) -> list[mission_resolver.ResolvedMission]:
        root = Path(repo_root).resolve()
        if root.is_relative_to(planted_under):
            return original(repo_root)
        if root not in walked:
            walked[root] = original(repo_root)
        return list(walked[root])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mission_resolver, "_build_index", once)
        yield


@pytest.fixture(scope="module")
def tools() -> Iterator[helper.ContractTools]:
    with pytest.MonkeyPatch.context() as mp:
        yield helper.load_contract_tools(mp, REPO_ROOT)


@pytest.fixture(scope="module")
def contract(tools: helper.ContractTools) -> helper.Contract:
    """The resolved module. If the resolver or the contract is unavailable this raises: there is no skip path."""
    return helper.Contract(tools, MODULE_DIR)


# ---------------------------------------------------------------------------
# The per-Mission case
# ---------------------------------------------------------------------------

_PLAIN_HANDLE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def snapshot_equality_problems(payload: Mapping[str, Any], state: Mapping[str, Any] | None) -> list[str]:
    """The payload's lane, agent and assignee against an independently re-read snapshot state.

    A value that does not fit the handle shape is projected to null, so it is compared as null. A work package
    with no snapshot entry must read as a null lane.
    """

    def handle(value: Any) -> str | None:
        return value if isinstance(value, str) and _PLAIN_HANDLE.match(value) and not (value.startswith("__") and value.endswith("__")) else None

    helper.LEDGER.snapshot_comparisons += 1
    if state is None:
        return [] if payload["statusLane"] is None else [f"{payload['wpId']}: a lane without a snapshot entry"]
    lane = str(state.get("lane"))
    wanted = {
        "statusLane": None if lane in helper.NON_DISPLAY_LANES else lane,
        "agent": handle(state.get("agent")),
        "assignee": handle(state.get("assignee")),
    }
    got = {"statusLane": payload["statusLane"], "agent": payload["assignment"]["agent"], "assignee": payload["assignment"]["assignee"]}
    return [f"{payload['wpId']}: {key} is {got[key]!r}, the snapshot has {wanted[key]!r}" for key in wanted if got[key] != wanted[key]]


def lane_accounting_problem(overview: Mapping[str, Any], work_packages: Mapping[str, Mapping[str, Any]]) -> str | None:
    """``wpTotal`` must equal the lane counts plus the work packages in a non-display lane (genesis, uninitialized).

    A lane outside the eleven cannot be read at all (the event store refuses it), so the only way a work package goes uncounted is a
    non-display lane, which a log row can still name, or a counting defect in the overview builder.
    """
    counted = sum(overview["statusLaneCounts"].values())
    hidden = sum(1 for state in work_packages.values() if str(state.get("lane")) in helper.NON_DISPLAY_LANES)
    if counted + hidden == overview["wpTotal"]:
        return None
    return f"wpTotal {overview['wpTotal']} is not the {counted} counted work packages plus {hidden} in a non-display lane"


def _first(errors: list[str]) -> str:
    return errors[0] + (f" (+{len(errors) - 1} more)" if len(errors) > 1 else "")


def run_case(
    mission: str,
    tools: helper.ContractTools,
    contract: helper.Contract,
    *,
    repo_root: Path = REPO_ROOT,
    tamper_work_package: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> CaseResult:
    """Build and check every payload of one Mission; the result is cached so the corpus-level tests reuse it.

    ``repo_root`` and ``tamper_work_package`` exist for the controls: they run this very function on a planted
    repository, or with a planted defect in each work package payload, and the schema, leak and snapshot-equality
    checks must catch it; a control may also patch the helper's builders to plant a defect the accounting check
    must catch. A run with either argument is never cached. The schema, leak and snapshot checks are also counted,
    and the case fails when one ran fewer times than the payloads it should have covered, so removing one of them
    from this function cannot leave the case green.
    """
    controlled = repo_root != REPO_ROOT or tamper_work_package is not None
    if not controlled and mission in CASE_RESULTS:
        return CASE_RESULTS[mission]
    started = time.perf_counter()
    ran_before = helper.LEDGER.snapshot()
    source = helper.load_source(repo_root, mission)
    projector = helper.Projector(tools.leak, mission)
    result = CaseResult(overview=helper.build_overview(source, projector), fallback=source.fallback)
    problems = result.failures
    payloads = 0

    def check(title: str, payload: Mapping[str, Any], label: str) -> None:
        nonlocal payloads
        payloads += 1
        errors = contract.errors(title, payload)
        if errors:
            problems.append(f"{mission}: {label}: {_first(errors)}")
        problems.extend(f"{mission}: {label}: leak {finding}" for finding in helper.payload_leaks(payload, tools))

    check(helper.SCHEMA_OVERVIEW, result.overview, "overview")
    fresh = materialize_snapshot(source.read_dir)  # an independent re-read: the helper's intermediate is not reused
    if result.overview["wpTotal"] != len(fresh.work_packages):
        problems.append(f"{mission}: wpTotal {result.overview['wpTotal']} differs from the snapshot's {len(fresh.work_packages)} work packages")
    if (accounting := lane_accounting_problem(result.overview, fresh.work_packages)) is not None:
        problems.append(f"{mission}: {accounting}")
    files = helper.read_authored_files(source.own_dir)
    check(helper.SCHEMA_DETAIL, helper.build_detail(source, projector, files), "detail")
    for authored in files:
        payload = helper.build_work_package(source, authored, projector)
        if tamper_work_package is not None:
            payload = tamper_work_package(payload)
        wp_id = payload["wpId"]
        check(helper.SCHEMA_WORK_PACKAGE, payload, f"work package {wp_id}")
        problems.extend(f"{mission}: {line}" for line in snapshot_equality_problems(payload, fresh.work_packages.get(wp_id)))
        result.work_packages += 1
    projection = helper.project_events(str(result.overview["missionId"]), source.rows, projector)
    for kind, event in projection.events:
        title = helper.SCHEMA_TRANSITION_EVENT if kind == "status-transition" else helper.SCHEMA_LIFECYCLE_EVENT
        check(title, event, f"{kind} event {event['eventId']}")
        result.kinds[kind] += 1
        result.events += 1
    problems.extend(f"{mission}: {line}" for line in _wiring_problems(helper.LEDGER.snapshot(), ran_before, payloads, result.work_packages))
    result.dropped = projection.dropped
    result.redactions = projector.redactions
    result.seconds = time.perf_counter() - started
    if not controlled:
        CASE_RESULTS[mission] = result
    return result


def _wiring_problems(after: tuple[int, int, int], before: tuple[int, int, int], payloads: int, work_packages: int) -> list[str]:
    """One line per check that did not run once for every payload (or work package) the case built."""
    validations, leak_scans, comparisons = (end - start for end, start in zip(after, before, strict=True))
    ran = {"contract validation": validations, "leak scan": leak_scans, "snapshot comparison": comparisons}
    return ran_problems(ran, {"contract validation": payloads, "leak scan": payloads, "snapshot comparison": work_packages}, into="the case")


# One case per Mission, id = the Mission directory name. Each case is built lazily (nothing is shared
# between cases but the resolved contract) so the 60 s per-case budget holds for the first case too.
@pytest.mark.parametrize("mission", CASES)
def test_mission_payloads_validate_against_the_contract_and_the_snapshot(mission: str, tools: helper.ContractTools, contract: helper.Contract) -> None:
    result = run_case(mission, tools, contract)
    EXECUTED.add(mission)
    assert not result.failures, "\n".join(result.failures)


def _all_results(tools: helper.ContractTools, contract: helper.Contract) -> dict[str, CaseResult]:
    return {mission: run_case(mission, tools, contract) for mission in CASES}


# ---------------------------------------------------------------------------
# Floors and the read-only proof
# ---------------------------------------------------------------------------


def test_the_own_directory_pass_meets_every_floor() -> None:
    own = own_directory_pass(REPO_ROOT)
    failures = floor_failures(own)
    assert not failures, "; ".join(failures)


def test_an_empty_case_list_is_a_collection_error(tmp_path: Path) -> None:
    assert enumerate_missions(tmp_path) == []
    with pytest.raises(EmptyCaseListError):
        require_cases(enumerate_missions(tmp_path))


def test_the_hash_proof_sees_a_changed_file_and_refuses_to_hash_nothing(tmp_path: Path) -> None:
    git = ["git", "-C", str(tmp_path)]
    helper.git_init(tmp_path)
    with pytest.raises(EmptyFingerprintError):
        tree_fingerprint(tmp_path, KITTY_SPECS)
    target = tmp_path / KITTY_SPECS / "m" / "status.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    subprocess.run([*git, "add", KITTY_SPECS], check=True)
    control = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert tree_fingerprint(tmp_path, KITTY_SPECS) == control, "control: an untouched tree keeps its fingerprint"
    target.write_text('{"changed": true}', encoding="utf-8")
    assert tree_fingerprint(tmp_path, KITTY_SPECS) != control, "a rewritten tracked file must change the fingerprint"
    target.write_text("{}", encoding="utf-8")
    assert tree_fingerprint(tmp_path, KITTY_SPECS) == control
    (target.parent / "created.json").write_text("{}", encoding="utf-8")
    assert tree_fingerprint(tmp_path, KITTY_SPECS) != control, "a new untracked file must change the fingerprint"


def test_the_byte_digest_alone_sees_a_rewrite_that_git_status_cannot(tmp_path: Path) -> None:
    """A committed file that is already modified keeps the porcelain line ` M` however it is rewritten again.

    Only the digest of its bytes can notice a reader rewriting such a file (a dirty local tree, an uncommitted
    snapshot), so this is the control of the digest half of the fingerprint: equal porcelain, different digest.
    """
    helper.git_init(tmp_path)
    target = tmp_path / KITTY_SPECS / "m" / "status.json"
    target.parent.mkdir(parents=True)
    target.write_text("aaaa", encoding="utf-8")
    helper.commit_all(tmp_path)
    target.write_text("bbbb", encoding="utf-8")
    dirty = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert dirty.porcelain == (f" M {KITTY_SPECS}/m/status.json",), "control: the file is modified before the first fingerprint"
    assert tree_fingerprint(tmp_path, KITTY_SPECS) == dirty, "control: nothing changed, so the fingerprint is stable"

    target.write_text("cccc", encoding="utf-8")  # same length, still ` M`

    rewritten = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert rewritten.porcelain == dirty.porcelain, "git status cannot see this rewrite"
    assert rewritten.digest != dirty.digest, "the byte digest must"
    assert rewritten != dirty


def test_a_created_empty_directory_changes_the_fingerprint_that_git_cannot_see(tmp_path: Path) -> None:
    """A reader that only creates an empty directory leaves ``git ls-files`` and ``git status`` as they were.

    The old signals (the file count and the porcelain lines) are blind to it; the directory names under the path
    are part of the fingerprint now (FR-014), so the new fingerprint is not.
    """
    helper.git_init(tmp_path)
    tracked = tmp_path / KITTY_SPECS / "m" / "status.json"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("{}", encoding="utf-8")
    helper.commit_all(tmp_path)
    control = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert tree_fingerprint(tmp_path, KITTY_SPECS) == control, "control: an untouched tree keeps its fingerprint"

    (tracked.parent / "reader-scratch").mkdir()
    created = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert (created.files, created.porcelain) == (control.files, control.porcelain), "the old signals cannot see an empty directory"
    assert created != control, "a created empty directory must change the fingerprint"
    assert created.directories == control.directories + 1
    assert created.digest != control.digest, "the directory names are part of the digest, not only counted"

    (tracked.parent / "reader-scratch").rename(tracked.parent / "reader-other")
    renamed = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert renamed.directories == created.directories and renamed.digest != created.digest, "a renamed empty directory keeps the count and changes the digest"

    (tracked.parent / "reader-other").rmdir()
    assert tree_fingerprint(tmp_path, KITTY_SPECS) == control, "removing it restores the fingerprint"


def test_an_ignored_file_is_part_of_the_fingerprint(tmp_path: Path) -> None:
    """``git status`` omits ignored files (``*.lock`` under ``kitty-specs/`` is ignored in this repository)."""
    helper.git_init(tmp_path)
    (tmp_path / ".gitignore").write_text("*.lock\n", encoding="utf-8")
    tracked = tmp_path / KITTY_SPECS / "m" / "status.json"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("{}", encoding="utf-8")
    helper.commit_all(tmp_path)
    control = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert tree_fingerprint(tmp_path, KITTY_SPECS) == control, "control: an untouched tree keeps its fingerprint"

    ignored = tracked.parent / "reader.lock"
    ignored.write_text("1", encoding="utf-8")
    created = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert created != control, "a created ignored file must change the fingerprint"
    assert created.files == control.files + 1

    ignored.write_text("2", encoding="utf-8")
    assert tree_fingerprint(tmp_path, KITTY_SPECS) != created, "a rewritten ignored file must change the fingerprint"


def test_the_floors_are_pinned_below_the_measured_corpus() -> None:
    assert FLOORS.missions >= 500
    assert FLOORS.work_package_payloads >= 3000
    assert FLOORS.snapshot_work_packages >= 2800


# ---------------------------------------------------------------------------
# Corpus-level assertions
# ---------------------------------------------------------------------------


# Corpus-level tests carry an explicit timeout: they may build every Mission themselves when run alone, and
# the budget for the whole module is 120 s (the per-case budget is 60 s).
@pytest.mark.timeout(120)
def test_overviews_order_strictly_and_missions_are_unique(tools: helper.ContractTools, contract: helper.Contract) -> None:
    overviews = [result.overview for result in _all_results(tools, contract).values()]
    ordered = helper.order_overviews(overviews)
    assert helper.ordering_problems(ordered) == [], "createdAt descending then missionId ascending, strictly, with unique missionIds"
    assert len(ordered) == len(CASES)


@pytest.mark.timeout(120)
def test_the_project_counts_the_overview_records(tools: helper.ContractTools, contract: helper.Contract) -> None:
    overviews = [result.overview for result in _all_results(tools, contract).values()]
    project = helper.derive_project(helper.read_project_name(REPO_ROOT), overviews)
    assert contract.errors(helper.SCHEMA_PROJECT, project) == []
    assert project["missionCount"] == len(overviews) == len(CASES)
    assert helper.payload_leaks(project, tools) == []


def test_the_disagreement_list_does_not_grow_beyond_the_pinned_missions() -> None:
    header = helper.load_expected(REPO_ROOT)["header"]
    assert helper.ratchet_header_problems(header) == []
    listed = helper.disagreement_list(own_directory_pass(REPO_ROOT))
    problem = helper.grown_problem([name for name, _, _ in listed], header["disagreeing_missions"])
    detail = "\n".join(f"  {name}: {snapshot} snapshot work packages, {files} files" for name, snapshot, files in listed)
    assert problem is None, f"{problem} (tracker {header['issue']}, owner {header['owner']}, drain by {header['drain_by']})\n{detail}"


def test_the_pinned_disagreement_list_is_not_stale() -> None:
    header = helper.load_expected(REPO_ROOT)["header"]
    measured = [name for name, _, _ in helper.disagreement_list(own_directory_pass(REPO_ROOT))]
    assert helper.stale_problem(measured, header["disagreeing_missions"]) is None, helper.stale_problem(measured, header["disagreeing_missions"])


@pytest.mark.timeout(120)
def test_the_helper_agrees_with_the_pinned_dashboard_derivation(tools: helper.ContractTools, contract: helper.Contract) -> None:
    expected = helper.load_expected(REPO_ROOT)
    assert helper.ratchet_header_problems(expected["header"]) == []
    problems = helper.expected_mismatches(expected, lambda name: run_case(name, tools, contract).overview)
    assert not problems, "\n".join(problems)
    assert {"active", "planned", "done", "draft", "discarded"} <= helper.sample_covers(expected)


@pytest.mark.timeout(120)
def test_both_row_derived_event_kinds_occur_in_the_committed_logs(tools: helper.ContractTools, contract: helper.Contract) -> None:
    results = _all_results(tools, contract)
    kinds: Counter[str] = Counter()
    for result in results.values():
        kinds.update(result.kinds)
    assert kinds["status-transition"] > 0 and kinds["mission-lifecycle"] > 0, dict(kinds)


@pytest.mark.timeout(120)
def test_no_row_is_dropped_for_a_reason_nobody_decided(tools: helper.ContractTools, contract: helper.Contract) -> None:
    """A transition with an unusable work package id, a row of no known kind and a row label nobody has classified are all silent drops otherwise."""
    dropped: Counter[str] = Counter()
    for result in _all_results(tools, contract).values():
        dropped.update(result.dropped)
    invalid, unknown = dropped[helper.DROPPED_INVALID_WP_ID], dropped[helper.DROPPED_UNKNOWN_ROW]
    assert invalid == 0, f"{invalid} status transitions were dropped for a work package id the contract does not accept"
    assert unknown == 0, f"{unknown} rows carry no event_type, type or kind: they are not an event of any known kind"
    unclassified = sorted(set(dropped) - KNOWN_DROPPED_LABELS.keys() - {helper.DROPPED_INVALID_WP_ID, helper.DROPPED_UNKNOWN_ROW})
    assert not unclassified, (
        f"rows labelled {unclassified} are dropped and nobody decided that: map them into the contract, or add each to KNOWN_DROPPED_LABELS with a reason"
    )


# ---------------------------------------------------------------------------
# Controls on one shared fixture
# ---------------------------------------------------------------------------

CONTROL_MISSION = "control-mission"


@pytest.fixture(scope="module")
def control_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One Mission whose frontmatter deliberately disagrees with its event log, written at run time."""
    root = tmp_path_factory.mktemp("status-controls")
    helper.git_init(root)
    stamp = "2026-09-01T10:{minute}:00+00:00".format
    rows = [
        helper.transition_row(1, "WP01", "genesis", "planned", at=stamp(minute="01"), actor="finalize-tasks"),
        helper.transition_row(2, "WP01", "planned", "claimed", at=stamp(minute="02"), actor="claude", policy_metadata={"agent": "real-agent"}),
        helper.annotation_row(1, "WP01", {"agent": "real-agent", "assignee": "real-assignee"}, at=stamp(minute="03")),
        helper.transition_row(3, "WP01", "claimed", "in_progress", at=stamp(minute="04"), actor="claude"),
    ]
    helper.write_fixture_mission(
        root,
        CONTROL_MISSION,
        work_packages={"WP01": {"lane": "done", "agent": "stale-agent", "assignee": "stale-assignee", "dependencies": []}},
        rows=rows,
        planning_files=["spec.md"],
    )
    return root


def _control_payload(control_repo: Path, tools: helper.ContractTools) -> tuple[dict[str, Any], Mapping[str, Any]]:
    source = helper.load_source(control_repo, CONTROL_MISSION)
    authored = helper.read_authored_files(source.own_dir)[0]
    payload = helper.build_work_package(source, authored, helper.Projector(tools.leak, CONTROL_MISSION))
    return payload, materialize_snapshot(source.read_dir).work_packages["WP01"]


def test_snapshot_equality_positive_control_projects_the_snapshot_not_the_frontmatter(control_repo: Path, tools: helper.ContractTools) -> None:
    payload, state = _control_payload(control_repo, tools)
    assert payload["statusLane"] == "in_progress" and payload["assignment"]["agent"] == "real-agent" and payload["assignment"]["assignee"] == "real-assignee"
    assert snapshot_equality_problems(payload, state) == []


def test_snapshot_equality_negative_control_fails_when_the_frontmatter_value_is_patched_in(control_repo: Path, tools: helper.ContractTools) -> None:
    payload, state = _control_payload(control_repo, tools)
    patched = {**payload, "statusLane": "done", "assignment": {**payload["assignment"], "agent": "stale-agent", "assignee": "stale-assignee"}}
    problems = snapshot_equality_problems(patched, state)
    assert len(problems) == 3 and "statusLane" in problems[0] and "agent" in problems[1] and "assignee" in problems[2]
    assert snapshot_equality_problems({**payload, "statusLane": "planned"}, None), "a lane without a snapshot entry is not representable"
    assert snapshot_equality_problems({**payload, "statusLane": None}, None) == []


def test_run_case_reports_a_work_package_the_lane_counts_do_not_account_for(
    control_repo: Path, tools: helper.ContractTools, contract: helper.Contract, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Planted control: a counting defect that drops a held lane from ``statusLaneCounts`` must fail the case on ``wpTotal``."""
    real = helper.lane_counts_of
    monkeypatch.setattr(helper, "lane_counts_of", lambda snapshot: {**real(snapshot), "in_progress": 0})

    result = run_case(CONTROL_MISSION, tools, contract, repo_root=control_repo)

    assert any("wpTotal 1 is not the 0 counted work packages" in failure for failure in result.failures), result.failures


def test_run_case_is_clean_on_the_control_mission_and_runs_every_check_for_every_payload(
    control_repo: Path, tools: helper.ContractTools, contract: helper.Contract
) -> None:
    """Control: the same function the corpus cases use, on a planted repository, finds nothing and counts its checks."""
    before = helper.LEDGER.snapshot()

    result = run_case(CONTROL_MISSION, tools, contract, repo_root=control_repo)

    assert result.failures == [] and result.work_packages == 1
    validations, leak_scans, comparisons = (end - start for end, start in zip(helper.LEDGER.snapshot(), before, strict=True))
    assert validations == leak_scans >= 2 and comparisons == 1, "overview, detail, the work package and its events were each checked"
    assert CONTROL_MISSION not in CASE_RESULTS, "a controlled run is never cached"


def _plant(**changes: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return lambda payload: {**payload, **changes}


def test_run_case_reports_a_planted_leak(control_repo: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    """The e-mail is planted after the projector's redaction, as a defect in a field the redaction does not reach."""
    planted = _plant(lastEventId="someone" + AT + "example.invalid")

    result = run_case(CONTROL_MISSION, tools, contract, repo_root=control_repo, tamper_work_package=planted)

    assert any("leak" in failure and "EMAIL" in failure for failure in result.failures), result.failures
    assert not any("is 'done'" in failure for failure in result.failures)


def test_run_case_reports_a_planted_schema_defect(control_repo: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    result = run_case(CONTROL_MISSION, tools, contract, repo_root=control_repo, tamper_work_package=_plant(statusLane="doing"))

    assert any("work package WP01" in failure and "statusLane" in failure and "leak" not in failure for failure in result.failures), result.failures


def test_run_case_reports_a_frontmatter_value_that_disagrees_with_the_snapshot(control_repo: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    """``done`` is a valid lane (the frontmatter says so) but the snapshot says in_progress: only the equality check can see it."""
    result = run_case(CONTROL_MISSION, tools, contract, repo_root=control_repo, tamper_work_package=_plant(statusLane="done"))

    assert [failure for failure in result.failures if "statusLane is 'done', the snapshot has 'in_progress'" in failure], result.failures
    assert not any("leak" in failure for failure in result.failures)


def test_a_check_that_did_not_run_for_every_payload_is_a_failure() -> None:
    """The wiring guard itself: fewer runs than payloads is named, with the check, for each of the three checks."""
    assert _wiring_problems((4, 4, 2), (0, 0, 0), 4, 2) == []
    problems = _wiring_problems((0, 0, 0), (0, 0, 0), 4, 2)
    assert [line.split(" ran ")[0] for line in problems] == ["the contract validation", "the leak scan", "the snapshot comparison"]
    assert len(_wiring_problems((4, 4, 0), (0, 0, 0), 4, 2)) == 1


@pytest.mark.timeout(120)
def test_a_real_payload_validates_and_each_planted_defect_fails(tools: helper.ContractTools, contract: helper.Contract) -> None:
    mission = next(name for name in CASES if run_case(name, tools, contract).work_packages)
    source = helper.load_source(REPO_ROOT, mission)
    projector = helper.Projector(tools.leak, mission)
    real = helper.build_work_package(source, helper.read_authored_files(source.own_dir)[0], projector)
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, real) == [] and helper.payload_leaks(real, tools) == [], "control: a real payload is clean"
    planted_email = {**real, "title": "Fix for someone" + AT + "example.invalid"}
    planted_path = {**real, "mergeTargetBranch": SLASH + "home" + SLASH + "someone" + SLASH + "branch"}
    assert any("EMAIL" in finding for finding in helper.payload_leaks(planted_email, tools))
    assert any("HOST_PATH" in finding for finding in helper.payload_leaks(planted_path, tools))
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, {**real, "statusLane": "doing"}), "an unknown status lane must fail validation"
    assert contract.errors(helper.SCHEMA_WORK_PACKAGE, {**real, "unexpected": True}), "an extra property must fail validation"


@pytest.mark.timeout(120)
def test_the_overview_builder_never_reads_a_work_package_file(tools: helper.ContractTools, contract: helper.Contract, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = next(name for name in CASES if run_case(name, tools, contract).work_packages)
    touched = helper.work_package_trap(monkeypatch)
    source = helper.load_source(REPO_ROOT, mission)
    overview = helper.build_overview(source, helper.Projector(tools.leak, mission))
    assert touched() == [] and overview["wpTotal"] == len(source.snapshot.work_packages), "the overview needs no tasks/WP*.md read (D-4)"
    with pytest.raises(AssertionError, match="read a work package file"):
        helper.build_detail(source, helper.Projector(tools.leak, mission))
    assert touched(), "negative control: the trap fires when a work package file is read"


def test_a_duplicate_mission_id_fails_and_a_repeated_display_number_passes(tools: helper.ContractTools, contract: helper.Contract) -> None:
    first, second = (run_case(name, tools, contract).overview for name in CASES[:2])
    same_number = [{**first, "displayNumber": 7}, {**second, "displayNumber": 7}]
    assert helper.ordering_problems(helper.order_overviews(same_number)) == [], "displayNumber is never an identifier"
    same_id = [first, {**second, "missionId": first["missionId"]}]
    assert any("duplicate missionId" in problem for problem in helper.ordering_problems(helper.order_overviews(same_id)))


def test_an_e_mail_actor_projects_to_all_null_and_tool_handles_to_a_tool_only(tools: helper.ContractTools) -> None:
    projector = helper.Projector(tools.leak, "m")
    assert projector.actor("someone" + AT + "example.invalid") == {"tool": None, "role": None, "profile": None}
    for handle in ("user", "finalize-tasks"):
        assert projector.actor(handle) == {"tool": handle, "role": None, "profile": None}


def test_discarded_has_a_fixture_built_positive_control(tmp_path: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    """``discarded`` occurs in no committed Mission, so a fixture-built payload is its positive control (the floors rely on it)."""
    helper.git_init(tmp_path)
    helper.write_fixture_mission(tmp_path, "discarded-control", meta={"discarded_at": "2026-09-05T00:00:00+00:00"})
    overview = helper.build_overview(helper.load_source(tmp_path, "discarded-control"), helper.Projector(tools.leak, "discarded-control"))
    assert contract.errors(helper.SCHEMA_OVERVIEW, overview) == []
    assert overview["lifecycleStatus"] == "discarded"


def test_the_values_the_corpus_floors_leave_out_have_a_fixture_built_control(tmp_path: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    """Claimed, for_review, in_review, blocked, canceled and lanes_with_coord sit on only a few Missions, so the floors do not require them.

    One fixture Mission holds a work package in each of those lanes under that topology, and the very function the corpus cases use must
    project it clean: every enum value of the contract is validated at least once without a status change to a real Mission turning the job red.
    """
    assert set(helper.CORPUS_LANES).isdisjoint(helper.CONTROL_LANES) and {*helper.CORPUS_LANES, *helper.CONTROL_LANES} == set(helper.STATUS_LANES), (
        "every lane is classified once"
    )
    assert set(helper.CORPUS_TOPOLOGIES).isdisjoint(helper.CONTROL_TOPOLOGIES) and {*helper.CORPUS_TOPOLOGIES, *helper.CONTROL_TOPOLOGIES} == {
        *helper.TOPOLOGIES,
        helper.UNKNOWN_TOPOLOGY,
    }
    helper.git_init(tmp_path)
    stamp = "2026-09-01T10:{minute:02d}:00+00:00".format
    path = {
        "WP01": ("claimed",),
        "WP02": ("claimed", "in_progress", "for_review"),
        "WP03": ("claimed", "in_progress", "for_review", "in_review"),
        "WP04": ("blocked",),
        "WP05": ("canceled",),
    }
    rows, number = [], 0
    for wp_id, lanes in path.items():
        for source, target in zip(("genesis", "planned", *lanes), ("planned", *lanes), strict=False):
            number += 1
            rows.append(helper.transition_row(number, wp_id, source, target, at=stamp(minute=number)))
    helper.write_fixture_mission(
        tmp_path, "transient-control", meta={"topology": "lanes_with_coord"}, work_packages=dict.fromkeys(path, {"dependencies": []}), rows=rows
    )

    result = run_case("transient-control", tools, contract, repo_root=tmp_path)

    assert result.failures == [], result.failures
    assert all(result.overview["statusLaneCounts"][lane] > 0 for lane in helper.CONTROL_LANES), result.overview["statusLaneCounts"]
    assert result.overview["topology"] in helper.CONTROL_TOPOLOGIES and result.work_packages == len(path)


# ---------------------------------------------------------------------------
# Report and the counting test (LAST)
# ---------------------------------------------------------------------------


def _report_lines(results: dict[str, CaseResult], own: list[Any], header: dict[str, Any], listed: list[Any]) -> list[str]:
    dropped: Counter[str] = Counter()
    fallbacks: Counter[str] = Counter()
    for result in results.values():
        dropped.update(result.dropped)
        if result.fallback:
            fallbacks[result.fallback] += 1
    slowest = sorted(((result.seconds, name) for name, result in results.items()), reverse=True)[:3]
    redactions = [(mission, field_name, kind) for result in results.values() for mission, field_name, kind in result.redactions]
    lines = [
        f"reality check: {len(results)} Missions projected, {sum(r.work_packages for r in results.values())} work package payloads validated, "
        f"{sum(r.events for r in results.values())} events validated",
        f"own-directory pass: {sum(i.snapshot_work_packages for i in own)} snapshot work packages, {sum(i.work_package_files for i in own)} work package files",
        f"disagreement list: {len(listed)} Missions, ceiling {header['ceiling']} "
        f"(tracker {header['issue']}, owner {header['owner']}, drain by {header['drain_by']})",
        f"coordination fallbacks (environment-dependent, never floored): {sum(fallbacks.values())} {dict(fallbacks)}",
        f"rows dropped by the allow-list: {dict(sorted(dropped.items()))}",
        f"lifecycle types dropped by design: {helper.undeclared_lifecycle_types()}",
        f"slowest cases: {[(name, round(seconds, 2)) for seconds, name in slowest]}",
        f"redactions: {len(redactions)}",
    ]
    lines.extend(f"redaction: {mission} {field_name} {kind}" for mission, field_name, kind in redactions)
    return lines


@pytest.mark.timeout(120)
def test_the_run_report(tools: helper.ContractTools, contract: helper.Contract, capsys: pytest.CaptureFixture[str]) -> None:
    """Print what the run established (shown in the CI log without -s) and prove every required section is in it."""
    results = _all_results(tools, contract)
    own = own_directory_pass(REPO_ROOT)
    header = helper.load_expected(REPO_ROOT)["header"]
    lines = _report_lines(results, own, header, helper.disagreement_list(own))
    with capsys.disabled():
        print("\n" + "\n".join(lines))
    assert results
    assert re.match(r"reality check: \d+ Missions projected, \d+ work package payloads validated, \d+ events validated$", lines[0]), lines[0]
    for prefix in ("disagreement list: ", "coordination fallbacks (", "rows dropped by the allow-list: ", "redactions: "):
        assert sum(line.startswith(prefix) for line in lines) == 1, f"the report must carry exactly one {prefix.strip()!r} section"
    assert f"ceiling {header['ceiling']} " in next(line for line in lines if line.startswith("disagreement list: ")), "the ceiling is printed"
    redaction_count = int(next(line for line in lines if line.startswith("redactions: ")).split(": ")[1])
    assert sum(line.startswith("redaction: ") for line in lines) == redaction_count, "every redaction is printed with its Mission and field"
    assert all(line.count(" ") >= 3 for line in lines if line.startswith("redaction: "))


# ---------------------------------------------------------------------------
# The reality extension over the real tree (WP08, FR-021)
#
# Everything in this section that DISCOVERS something (Missions, work package ids, files, cycles, refused Missions, status-log-only
# ids, the expected outcome of a file) is a plain scan of the tree that shares no code with ``_mission_status_artifacts`` or
# ``_mission_status_detail``: the reader under test is only ever the thing being compared against it.
# ---------------------------------------------------------------------------

_ROOT_STATUS_RECORDS = frozenset({"status.events.jsonl", "status.json"})
_WORK_PACKAGE_ID = re.compile(r"^WP[0-9]{2,}$")
_PROMPT_FILE = re.compile(r"^WP[0-9]{2,}-.*[.]md$")
_CYCLE_FILE = re.compile(r"^review-cycle-([1-9][0-9]*)[.]md$")
_TABLE_ROW = re.compile(r"^[|]\s*(T[0-9]{3,})\s*[|]")
_CHECKBOX_ROW = re.compile(r"^-\s*\[[ xX]\]\s*(T[0-9]{3,})\b")
_RFC3339_WITH_OFFSET = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:[.][0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$")
_DATE_ONLY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_MODIFIED_AT = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_NUL_BYTE = bytes(1)
_CONTENT_CAP = 262_144
_SOURCE_UNREADABLE = "source_unreadable"
_NOT_FOUND = "not_found"
# The Problem code of each refused status, written out here on purpose: the oracle does not import the reader's table.
_ORACLE_CODES = {413: "artifact_too_large", 415: "artifact_not_text", 422: "artifact_secret"}
FIXTURE_NAME = "mission_status_artifacts_expected.json"


@dataclass(frozen=True)
class ScannedMission:
    """A directory under ``kitty-specs/`` holding a ``meta.json``, found by a plain directory listing."""

    name: str
    mission_id: str
    directory: Path


def scan_missions(repo_root: Path) -> dict[str, ScannedMission]:
    """Mission id to the Mission, one entry per ``meta.json`` carrying an id (the first directory in name order keeps an id two hold)."""
    base = repo_root / KITTY_SPECS
    found: dict[str, ScannedMission] = {}
    for name in sorted(os.listdir(base)):
        meta = base / name / "meta.json"
        if not meta.is_file():
            continue
        mission_id = json.loads(meta.read_text(encoding="utf-8"))["mission_id"]
        found.setdefault(mission_id, ScannedMission(name, mission_id, base / name))
    return found


def _plain_frontmatter(path: Path) -> dict[str, Any] | None:
    """The YAML frontmatter mapping of a markdown file read with the plain YAML loader, or ``None`` when there is none or it does not parse."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.split("\n")
    if not text.startswith("---"):
        return None
    closing = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if closing is None:
        return None
    try:
        data = yaml.safe_load("\n".join(lines[1:closing]))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(item for item in value if isinstance(item, str)) if isinstance(value, list) else ()


def _subtask_ids(value: Any) -> tuple[str, ...]:
    """The authored roster as v1 reads it: each item as text, trimmed, empty ones dropped, repeats dropped, order kept.

    A roster written as ``{id, title, status}`` mappings (Mission 058 does) therefore yields the text of each mapping, which is
    what v1 serves today; the detail must agree with v1 (FR-021), so the oracle states the same rule instead of improving on it.
    """
    if not isinstance(value, list):
        return ()
    roster: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in roster:
            roster.append(text)
    return tuple(roster)


@dataclass(frozen=True)
class ScannedWorkPackage:
    """One distinct work package id of a Mission: the first file in byte order that holds it, and what its frontmatter lists."""

    wp_id: str
    file_name: str
    holders: int
    subtasks: tuple[str, ...]
    dependencies: tuple[str, ...]
    owned_files: tuple[str, ...]


def _is_regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def scan_work_packages(mission: ScannedMission) -> dict[str, ScannedWorkPackage]:
    """The distinct valid ``work_package_id`` of the regular ``tasks/WP*.md`` files of a Mission, by a plain scan (a symlinked ``tasks/`` is not entered)."""
    tasks = mission.directory / "tasks"
    if tasks.is_symlink() or not tasks.is_dir():
        return {}
    first: dict[str, ScannedWorkPackage] = {}
    holders: Counter[str] = Counter()
    for name in sorted(os.listdir(tasks), key=lambda entry: entry.encode("utf-8")):
        if not (name.startswith("WP") and name.endswith(".md")) or not _is_regular(tasks / name):
            continue
        data = _plain_frontmatter(tasks / name) or {}
        wp_id = data.get("work_package_id")
        if not isinstance(wp_id, str) or not _WORK_PACKAGE_ID.fullmatch(wp_id):
            continue
        holders[wp_id] += 1
        first.setdefault(
            wp_id,
            ScannedWorkPackage(wp_id, name, 0, _subtask_ids(data.get("subtasks")), _strings(data.get("dependencies")), _strings(data.get("owned_files"))),
        )
    return {
        wp_id: ScannedWorkPackage(wp_id, found.file_name, holders[wp_id], found.subtasks, found.dependencies, found.owned_files) for wp_id, found in first.items()
    }


def scan_refused_missions(repo_root: Path) -> dict[str, str]:
    """Mission id to its directory name for every Mission whose ``lanes.json`` has ``feature_slug`` and no ``mission_slug``.

    The product's own reader refuses that legacy shape (``CorruptLanesError``), so by FR-006 every work package of such a Mission answers 500
    ``source_unreadable``. This scan reads the JSON directly and never calls the reader under test.
    """
    refused: dict[str, str] = {}
    for mission in scan_missions(repo_root).values():
        lanes = mission.directory / "lanes.json"
        if not lanes.is_file():
            continue
        try:
            data = json.loads(lanes.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and "feature_slug" in data and "mission_slug" not in data:
            refused[mission.mission_id] = mission.name
    return refused


def scan_event_rows(directory: Path) -> list[dict[str, Any]]:
    """The JSON object rows of a Mission's own ``status.events.jsonl`` (a line that is not an object is skipped)."""
    log = directory / "status.events.jsonl"
    if not log.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def scan_status_log_only_ids(mission: ScannedMission, universe: set[str]) -> set[str]:
    """Valid work package ids named by the status log rows that no work package file holds (the detail answers 404 for them)."""
    named = {row.get("wp_id") for row in scan_event_rows(mission.directory)}
    return {wp_id for wp_id in named if isinstance(wp_id, str) and _WORK_PACKAGE_ID.fullmatch(wp_id) and wp_id not in universe}


def scan_prompt_stem(mission: ScannedMission, wp_id: str) -> str | None:
    """The stem of the first regular ``WP<digits>-*.md`` file in byte order whose name starts with ``<wp_id>-``: the cycle directory name."""
    tasks = mission.directory / "tasks"
    if tasks.is_symlink() or not tasks.is_dir():
        return None
    for name in sorted(os.listdir(tasks), key=lambda entry: entry.encode("utf-8")):
        if name.startswith(wp_id + "-") and _PROMPT_FILE.fullmatch(name) and _is_regular(tasks / name):
            return name.removesuffix(".md")
    return None


@dataclass(frozen=True)
class ScannedCycle:
    """One ``review-cycle-N.md`` file and what an independent read of it and of the status log says about it."""

    number: int
    path: str
    pointer: str
    parsed: bool
    reviewed_at: str | None
    verdict: str | None


def _cycle_verdict(rows: list[dict[str, Any]], wp_id: str, pointer: str, verdicts: frozenset[str]) -> str | None:
    verdict = None
    for row in rows:
        result = row.get("review_result")
        if row.get("wp_id") != wp_id or "to_lane" not in row or not isinstance(result, dict):
            continue
        reference = result.get("reference")
        if isinstance(reference, str) and reference.strip() == pointer:
            value = result.get("verdict")
            verdict = value if value in verdicts else None
    return verdict


def scan_cycles(mission: ScannedMission, wp_id: str, rows: list[dict[str, Any]], verdicts: frozenset[str]) -> list[ScannedCycle]:
    """The review cycle files of one work package, ascending by number, by a plain directory scan and the product's own cycle parser."""
    stem = scan_prompt_stem(mission, wp_id)
    directory = mission.directory / "tasks" / (stem or "")
    if stem is None or (mission.directory / "tasks").is_symlink() or directory.is_symlink() or not directory.is_dir():
        return []
    cycles = []
    for name in os.listdir(directory):
        match = _CYCLE_FILE.fullmatch(name)
        if match is None:
            continue
        pointer = f"review-cycle://{mission.name}/{stem}/{name}"
        parsed, reviewed_at = False, None
        if _is_regular(directory / name):
            try:
                artifact = ReviewCycleArtifact.from_file(directory / name)
            except (ValueError, OSError):
                artifact = None
            if artifact is not None:
                parsed, reviewed_at = True, artifact.reviewed_at
        cycles.append(ScannedCycle(int(match.group(1)), f"tasks/{stem}/{name}", pointer, parsed, reviewed_at, _cycle_verdict(rows, wp_id, pointer, verdicts)))
    return sorted(cycles, key=lambda cycle: cycle.number)


def scan_table_and_checkbox_rows(mission: ScannedMission) -> tuple[set[str], int, int]:
    """The subtask ids that a ``tasks.md`` row names, the number of table rows and the number of checkbox rows (two regular expressions)."""
    tasks_md = mission.directory / "tasks.md"
    if not _is_regular(tasks_md):
        return set(), 0, 0
    ids: set[str] = set()
    table = checkbox = 0
    for line in tasks_md.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if (found := _TABLE_ROW.match(stripped)) is not None:
            table += 1
            ids.add(found.group(1))
        elif (found := _CHECKBOX_ROW.match(stripped)) is not None:
            checkbox += 1
            ids.add(found.group(1))
    return ids, table, checkbox


# ---------------------------------------------------------------------------
# The byte-level oracle (plan D-P8): the expected outcome of an eligible file from its raw bytes alone
# ---------------------------------------------------------------------------


def oracle_outcome(tools: helper.ContractTools, data: bytes) -> int:
    """413 above the cap; else 415 for a NUL byte, then 415 for a strict UTF-8 decode failure; else 422 for a credential; else 200 (in that order)."""
    if len(data) > _CONTENT_CAP:
        return 413
    if _NUL_BYTE in data:
        return 415
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return 415
    if any(pattern.search(text) for pattern in tools.leak.SECRET_PATTERNS):
        return 422
    return 200


_COUPLED_NAMES = frozenset({"artifacts", "_decide_bytes", "read_file", "list_artifacts", "has_credential", "redact", "classify"})


def oracle_coupling(function: Callable[..., Any]) -> list[str]:
    """The names of the reader (or its helpers) that a function mentions: the oracle must mention none, so it cannot agree by construction."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    return sorted(names & _COUPLED_NAMES)


def scan_eligible_files(mission: ScannedMission) -> list[str]:
    """The relative paths of the regular, non-symlink files below a Mission directory other than the two root status records, in byte order."""
    found: list[str] = []
    for directory, subdirectories, files in os.walk(mission.directory, followlinks=False):
        subdirectories.sort()
        for file_name in files:
            full = Path(directory) / file_name
            relative = full.relative_to(mission.directory).as_posix()
            if not full.is_symlink() and relative not in _ROOT_STATUS_RECORDS:
                found.append(relative)
    return sorted(found, key=lambda path: path.encode("utf-8"))


# ---------------------------------------------------------------------------
# The examinations: build everything a service would answer, compare it with the independent scans, count what ran
# ---------------------------------------------------------------------------

VERDICTS = frozenset(yaml.safe_load((MODULE_DIR / "schemas" / "ReviewVerdict.yaml").read_text(encoding="utf-8"))["enum"])


def count_problems(name: str, *, examined: int, discovered: int, floor: int) -> list[str]:
    """The shared rule of every count: nothing examined, a shortfall against the independent count and a count under the floor all fail."""
    counts = f"{name}: {examined} examined of {discovered} discovered, floor {floor}"
    problems = []
    if examined == 0 or discovered == 0:
        problems.append(f"{counts}: a zero count proves nothing")
    if examined != discovered:
        problems.append(f"{counts}: examined differs from discovered")
    if examined < floor:
        problems.append(f"{counts}: under the floor")
    return problems


def ran_problems(ran: Mapping[str, int], expected: Mapping[str, int], *, into: str = "the examination") -> list[str]:
    """One line per check that did not run exactly once for every payload (or comparison) it is owed."""
    return [
        f"the {name} ran {ran.get(name, 0)} times for {wanted} payloads: the check is not wired into {into}"
        for name, wanted in expected.items()
        if ran.get(name, 0) != wanted
    ]


def _ledger_delta(before: tuple[int, int, int]) -> dict[str, int]:
    validations, leak_scans, _ = (end - start for end, start in zip(helper.LEDGER.snapshot(), before, strict=True))
    return {"contract validation": validations, "leak scan": leak_scans}


@dataclass
class ArtifactExam:
    """What the listing and the content read produced for every Mission, against the independent walk and the byte-level oracle."""

    discovered_missions: int = 0
    missions: int = 0
    discovered_files: int = 0
    listed_files: int = 0
    content_examined: int = 0
    readable_true: int = 0
    readable_false: int = 0
    redacted_files: int = 0
    missions_without_lanes: int = 0
    oracle_checks: int = 0
    payloads: int = 0
    statuses: Counter[int] = field(default_factory=Counter)
    kinds: Counter[str] = field(default_factory=Counter)
    entries: dict[tuple[str, str], tuple[str, bool]] = field(default_factory=dict)
    refusals: dict[tuple[str, str], tuple[int, str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


@dataclass
class DetailExam:
    """What the work package detail produced for every distinct work package id, against the independent scans."""

    discovered: int = 0
    examined: int = 0
    refused: dict[str, int] = field(default_factory=dict)
    expected_refused: dict[str, int] = field(default_factory=dict)
    status_log_only: int = 0
    status_log_only_not_found: int = 0
    subtask_ids: int = 0
    independent_subtask_ids: int = 0
    owned_file_entries: int = 0
    independent_owned_file_entries: int = 0
    dependency_entries: int = 0
    independent_dependency_entries: int = 0
    table_rows: int = 0
    checkbox_rows: int = 0
    titled_subtasks: int = 0
    review_cycle_files: int = 0
    independent_cycle_files: int = 0
    missions_with_cycles: int = 0
    unparseable_cycles: int = 0
    verdict_cycles: int = 0
    independent_verdict_cycles: int = 0
    date_only_cycles: int = 0
    comparisons: int = 0
    non_comparable_missions: int = 0
    v1_controls: int = 0
    payloads: int = 0
    no_prompt: set[tuple[str, str]] = field(default_factory=set)
    duplicate_ids: dict[str, list[str]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def refused_total(self) -> int:
        return sum(self.refused.values())


@dataclass
class CorpusExam:
    artifacts: ArtifactExam
    details: DetailExam
    fingerprint_before: Any = None
    fingerprint_after: Any = None


def _content_problems(mission: ScannedMission, path: str, data: bytes, body: Mapping[str, Any]) -> list[str]:
    """A 200 envelope against the file's own bytes: size, path, encoding, and that the text changed exactly when ``redacted`` says it did."""
    text = data.decode("utf-8")
    problems = []
    if body["sizeBytes"] != len(data) or body["path"] != path or body["encoding"] != "utf-8":
        problems.append(f"{mission.name}/{path}: the envelope disagrees with the file ({body['sizeBytes']} bytes, {len(data)} on disk)")
    if body["redacted"] is False and body["content"] != text:
        problems.append(f"{mission.name}/{path}: redacted is false but the content differs from the file")
    if body["redacted"] is True and body["content"] == text:
        problems.append(f"{mission.name}/{path}: redacted is true but the content equals the file")
    return problems


def _examine_listing_entry(
    ctx: artifacts.ReaderContext, tools: helper.ContractTools, contract: helper.Contract, mission: ScannedMission, entry: Mapping[str, Any], exam: ArtifactExam
) -> None:
    path = entry["path"]
    data = (mission.directory / path).read_bytes()
    expected = oracle_outcome(tools, data)
    exam.oracle_checks += 1
    if entry["readable"] != (expected == 200) or entry["sizeBytes"] != len(data) or not _MODIFIED_AT.fullmatch(entry["modifiedAt"]):
        exam.problems.append(
            f"{mission.name}/{path}: the listing says readable={entry['readable']} size={entry['sizeBytes']}, the bytes say {expected} and {len(data)}"
        )
    exam.entries[(mission.name, path)] = (entry["kind"], entry["readable"])
    exam.kinds[entry["kind"]] += 1
    exam.listed_files += 1
    exam.readable_true += int(entry["readable"])
    exam.readable_false += int(not entry["readable"])
    outcome = artifacts.read_content(ctx, mission.mission_id, [path])
    exam.content_examined += 1
    exam.statuses[outcome.status] += 1
    exam.oracle_checks += 1
    if outcome.status != expected:
        exam.problems.append(f"{mission.name}/{path}: the content read answered {outcome.status}, the bytes say {expected}")
    if entry["readable"] != (outcome.status == 200):  # a wiring guard (true by construction), not the oracle
        exam.problems.append(f"{mission.name}/{path}: wiring guard: readable is not the content read's 200")
    schema = helper.SCHEMA_ARTIFACT_CONTENT if outcome.status == 200 else helper.SCHEMA_ARTIFACT_REFUSAL
    exam.payloads += 1
    exam.problems.extend(f"{mission.name}/{path}: schema {error}" for error in contract.errors(schema, outcome.body))
    exam.problems.extend(f"{mission.name}/{path}: leak {finding}" for finding in helper.payload_leaks(outcome.body, tools))
    if outcome.status == 200:
        exam.redacted_files += int(outcome.body["redacted"] is True)
        if expected == 200:  # a wrongly served file is already a problem above, and its bytes may not even decode
            exam.problems.extend(_content_problems(mission, path, data, outcome.body))
    else:
        exam.refusals[(mission.name, path)] = (outcome.status, str(outcome.body.get("code")))
        if outcome.body.get("code") != _ORACLE_CODES.get(expected):
            exam.problems.append(f"{mission.name}/{path}: the refusal code is {outcome.body.get('code')}, the cause is {expected}")


def examine_artifacts(ctx: artifacts.ReaderContext, contract: helper.Contract, repo_root: Path) -> ArtifactExam:
    """The listing of every Mission against an independent walk, and every listed file's content read against the byte-level oracle."""
    exam = ArtifactExam()
    before = helper.LEDGER.snapshot()
    missions = scan_missions(repo_root)
    exam.discovered_missions = len(missions)
    for mission in missions.values():
        expected = scan_eligible_files(mission)
        exam.discovered_files += len(expected)
        exam.missions_without_lanes += int(not (mission.directory / "lanes.json").is_file())
        listing = artifacts.list_artifacts(ctx, mission.mission_id)
        if listing.status != 200:
            exam.problems.append(f"{mission.name}: the listing answered {listing.status} {listing.body.get('code')}")
            continue
        exam.payloads += 1
        exam.problems.extend(f"{mission.name}: listing schema {error}" for error in contract.errors(helper.SCHEMA_ARTIFACT_LISTING, listing.body))
        exam.problems.extend(f"{mission.name}: listing leak {finding}" for finding in helper.payload_leaks(listing.body, ctx.tools))
        shown = expected[: artifacts.MAX_LISTING_ENTRIES]
        if [entry["path"] for entry in listing.body["entries"]] != shown or listing.body["truncated"] != (len(expected) > len(shown)):
            exam.problems.append(f"{mission.name}: the listing and the independent walk disagree")
            continue
        exam.missions += 1
        for entry in listing.body["entries"]:
            _examine_listing_entry(ctx, ctx.tools, contract, mission, entry, exam)
    exam.problems.extend(ran_problems(_ledger_delta(before), {"contract validation": exam.payloads, "leak scan": exam.payloads}))
    exam.problems.extend(ran_problems({"oracle comparison": exam.oracle_checks}, {"oracle comparison": exam.listed_files + exam.content_examined}))
    return exam


def detail_invariant_problems(body: Mapping[str, Any]) -> list[str]:
    """What a detail built for a host without worktrees must satisfy besides the schema: the invariants, no worktree and no determined change state."""
    problems = list(detail.invariant_problems(body))
    if body["workspace"]["worktreePresent"] is not False:
        problems.append("worktreePresent is not false for a host without worktrees")
    problems.extend(f"changeState {entry['changeState']} for {entry['pattern']}" for entry in body["ownedFiles"] if entry["changeState"] != "unknown")
    return problems


def v1_control_problems(body: Mapping[str, Any], v1: Mapping[str, Any]) -> list[str]:
    """The detail against the v1 payload built from the SAME authored file: subtask ids, dependency ids and owned-file patterns must be identical."""
    problems = []
    if [entry["id"] for entry in body["subtasks"]] != v1["authored"]["subtasks"]:
        problems.append("subtasks[].id differs from the v1 authored.subtasks")
    if [entry["wpId"] for entry in body["dependencies"]] != v1["dependencies"]:
        problems.append("dependencies[].wpId differs from the v1 dependencies")
    if [entry["pattern"] for entry in body["ownedFiles"]] != v1["ownedFiles"]:
        problems.append("ownedFiles[].pattern differs from the v1 ownedFiles")
    return problems


def lane_control_problems(body: Mapping[str, Any], v1: Mapping[str, Any], snapshot_lanes: Mapping[str, Any], projector: helper.Projector) -> list[str]:
    """FR-021 lane control: each subtask and dependency lane against the status snapshot, read here and not through the detail reader.

    A subtask lane is the lane the v1 payload records for that id; a dependency lane is the snapshot lane of that work package, null when it has none.
    """
    problems = []
    for entry in body["subtasks"]:
        wanted = projector.lane(v1["subtasks"].get(entry["id"]), "subtasks.statusLane")
        if entry["statusLane"] != wanted:
            problems.append(f"subtask {entry['id']}: statusLane {entry['statusLane']!r}, the status snapshot says {wanted!r}")
    for entry in body["dependencies"]:
        state = snapshot_lanes.get(entry["wpId"])
        wanted = projector.lane(None if state is None else state.get("lane"), "dependencies.statusLane")
        if entry["statusLane"] != wanted:
            problems.append(f"dependency {entry['wpId']}: statusLane {entry['statusLane']!r}, the status snapshot says {wanted!r}")
    return problems


def independent_list_problems(body: Mapping[str, Any], scanned: ScannedWorkPackage) -> list[str]:
    """The detail's three lists against the frontmatter lists of a plain YAML read of the file the reader chose."""
    problems = []
    if tuple(entry["id"] for entry in body["subtasks"]) != scanned.subtasks:
        problems.append("subtasks differ from the frontmatter list")
    if tuple(entry["wpId"] for entry in body["dependencies"]) != scanned.dependencies:
        problems.append("dependencies differ from the frontmatter list")
    if tuple(entry["pattern"] for entry in body["ownedFiles"]) != scanned.owned_files:
        problems.append("owned files differ from the frontmatter list")
    return problems


def cycle_problems(entries: Sequence[Mapping[str, Any]], scanned: Sequence[ScannedCycle], comparable: bool) -> list[str]:
    """Each served review cycle against its independently scanned file: number, pointer, path, parse outcome and (when the log is the Mission's own) verdict."""
    if [entry["cycleNumber"] for entry in entries] != [cycle.number for cycle in scanned]:
        return ["the cycle numbers differ from the cycle files on disk"]
    problems = []
    for entry, cycle in zip(entries, scanned, strict=True):
        wanted_at = cycle.reviewed_at if cycle.parsed and cycle.reviewed_at and _RFC3339_WITH_OFFSET.fullmatch(cycle.reviewed_at) else None
        if entry["feedbackReference"] != cycle.pointer or entry["artifactPath"] != cycle.path or entry["reviewedAt"] != wanted_at:
            problems.append(f"cycle {cycle.number}: pointer, path or reviewedAt differ from the file ({entry['reviewedAt']!r} against {wanted_at!r})")
        if not cycle.parsed and entry["reviewer"] is not None:
            problems.append(f"cycle {cycle.number}: an unparseable file has a reviewer")
        if comparable and entry["verdict"] != cycle.verdict:
            problems.append(f"cycle {cycle.number}: verdict {entry['verdict']!r}, the status log says {cycle.verdict!r}")
    return problems


@dataclass(frozen=True)
class _DetailContext:
    """What one Mission's work packages share: the independent scans, the v1 authored files and the status rows."""

    work_packages: Mapping[str, ScannedWorkPackage]
    refused: Mapping[str, str]
    authored: Mapping[str, helper.AuthoredWorkPackage]
    projector: helper.Projector
    row_ids: set[str]
    rows: list[dict[str, Any]]
    comparable_log: bool


def _refused_detail_problems(mission: ScannedMission, wp_id: str, outcome: detail.DetailOutcome, refused: Mapping[str, str]) -> list[str]:
    """A non-200 answer is only acceptable for a Mission on the independently derived refused list, and then only as 500 ``source_unreadable``."""
    if mission.mission_id not in refused:
        return [f"{mission.name}/{wp_id}: refused {outcome.status} {outcome.body.get('code')} but the Mission is not on the independently derived refused list"]
    if (outcome.status, outcome.body.get("code")) != (500, _SOURCE_UNREADABLE):
        return [f"{mission.name}/{wp_id}: a listed Mission answered {outcome.status} {outcome.body.get('code')}, not 500 {_SOURCE_UNREADABLE}"]
    return []


def _examine_work_package(
    ctx: artifacts.ReaderContext,
    tools: helper.ContractTools,
    contract: helper.Contract,
    mission: ScannedMission,
    wp_id: str,
    opened: detail.OpenedMission,
    exam: DetailExam,
    context: _DetailContext,
) -> None:
    scanned = context.work_packages[wp_id]
    outcome = detail.build_work_package_detail(ctx, mission.mission_id, wp_id, detail.NO_WORKTREES, opened=opened)
    exam.payloads += 1
    if outcome.status != 200:
        exam.problems.extend(_refused_detail_problems(mission, wp_id, outcome, context.refused))
        exam.refused[mission.name] = exam.refused.get(mission.name, 0) + 1
        exam.problems.extend(f"{mission.name}/{wp_id}: refusal schema {error}" for error in contract.errors(helper.SCHEMA_DETAIL_REFUSAL, outcome.body))
        exam.problems.extend(f"{mission.name}/{wp_id}: refusal leak {finding}" for finding in helper.payload_leaks(outcome.body, tools))
        return
    body = outcome.body
    exam.examined += 1
    where = f"{mission.name}/{wp_id}"
    exam.problems.extend(f"{where}: schema {error}" for error in contract.errors(helper.SCHEMA_WORK_PACKAGE_DETAIL, body))
    exam.problems.extend(f"{where}: leak {finding}" for finding in helper.payload_leaks(body, tools))
    exam.problems.extend(f"{where}: {problem}" for problem in detail_invariant_problems(body))
    if mission.mission_id in context.refused:
        exam.problems.append(f"{where}: a Mission on the refused list answered 200 (a stale entry)")
    exam.comparisons += 1
    if opened.index[wp_id].name != scanned.file_name:
        exam.problems.append(f"{where}: the reader chose {opened.index[wp_id].name}, the independent scan chose {scanned.file_name}")
    exam.problems.extend(f"{where}: {problem}" for problem in independent_list_problems(body, scanned))
    v1 = helper.build_work_package(opened.source, context.authored[opened.index[wp_id].name], context.projector)
    exam.v1_controls += 1
    exam.problems.extend(f"{where}: {problem}" for problem in v1_control_problems(body, v1))
    exam.problems.extend(f"{where}: {problem}" for problem in lane_control_problems(body, v1, opened.source.snapshot.work_packages, context.projector))
    exam.subtask_ids += len(body["subtasks"])
    exam.independent_subtask_ids += len(scanned.subtasks)
    exam.owned_file_entries += len(body["ownedFiles"])
    exam.independent_owned_file_entries += len(scanned.owned_files)
    exam.dependency_entries += len(body["dependencies"])
    exam.independent_dependency_entries += len(scanned.dependencies)
    for entry in body["subtasks"]:
        if entry["title"] is not None:
            exam.titled_subtasks += 1
            if entry["id"] not in context.row_ids:
                exam.problems.append(f"{where}: subtask {entry['id']} has a title and no tasks.md row names it")
    if body["artifactReferences"]["prompt"] is None:
        exam.no_prompt.add((mission.name, wp_id))
    _examine_cycles(mission, wp_id, body, exam, context)


def _examine_cycles(mission: ScannedMission, wp_id: str, body: Mapping[str, Any], exam: DetailExam, context: _DetailContext) -> None:
    scanned = scan_cycles(mission, wp_id, context.rows, VERDICTS)
    served = body["reviewCycles"]
    exam.review_cycle_files += len(served)
    exam.independent_cycle_files += len(scanned)
    exam.unparseable_cycles += sum(1 for cycle in scanned if not cycle.parsed)
    exam.date_only_cycles += sum(1 for cycle in scanned if cycle.parsed and cycle.reviewed_at is not None and _DATE_ONLY.fullmatch(cycle.reviewed_at))
    exam.problems.extend(f"{mission.name}/{wp_id}: {problem}" for problem in cycle_problems(served, scanned, context.comparable_log))
    if context.comparable_log:
        exam.verdict_cycles += sum(1 for entry in served if entry["verdict"] is not None)
        exam.independent_verdict_cycles += sum(1 for cycle in scanned if cycle.verdict is not None)


def examine_details(ctx: artifacts.ReaderContext, contract: helper.Contract, repo_root: Path) -> DetailExam:
    """The detail of every distinct work package id of every Mission, with the host capability of a host without worktrees."""
    exam = DetailExam()
    before = helper.LEDGER.snapshot()
    tools = ctx.tools
    refused = scan_refused_missions(repo_root)
    for mission in scan_missions(repo_root).values():
        scanned = scan_work_packages(mission)
        exam.discovered += len(scanned)
        if duplicated := sorted(wp_id for wp_id, found in scanned.items() if found.holders > 1):
            exam.duplicate_ids[mission.name] = duplicated
        if mission.mission_id in refused:
            exam.expected_refused[mission.name] = len(scanned)
        row_ids, table, checkbox = scan_table_and_checkbox_rows(mission)
        exam.table_rows += table
        exam.checkbox_rows += checkbox
        opened = detail.open_mission(ctx, mission.mission_id)
        if isinstance(opened, detail.DetailOutcome):
            exam.problems.append(f"{mission.name}: the Mission could not be opened ({opened.status} {opened.body.get('code')})")
            continue
        if set(opened.index) != set(scanned):
            exam.problems.append(f"{mission.name}: the reader's universe differs from the independent scan")
            continue
        context = _DetailContext(
            work_packages=scanned,
            refused=refused,
            authored={authored.path.name: authored for authored in helper.read_authored_files(opened.source.own_dir)},
            projector=helper.Projector(tools.leak, mission.name),
            row_ids=row_ids,
            rows=scan_event_rows(mission.directory),
            comparable_log=opened.source.read_dir.resolve() == mission.directory.resolve(),
        )
        exam.non_comparable_missions += int(not context.comparable_log)
        cycle_files_before = exam.independent_cycle_files
        for wp_id in sorted(scanned):
            _examine_work_package(ctx, tools, contract, mission, wp_id, opened, exam, context)
        exam.missions_with_cycles += int(exam.independent_cycle_files > cycle_files_before)
        for wp_id in sorted(scan_status_log_only_ids(mission, set(scanned))):
            exam.status_log_only += 1
            answer = detail.build_work_package_detail(ctx, mission.mission_id, wp_id, detail.NO_WORKTREES, opened=opened)
            if (answer.status, answer.body.get("code")) == (404, _NOT_FOUND):
                exam.status_log_only_not_found += 1
            else:
                exam.problems.append(f"{mission.name}/{wp_id}: a work package named only by the status log answered {answer.status}, not 404")
    exam.problems.extend(_detail_count_problems(exam))
    exam.problems.extend(ran_problems(_ledger_delta(before), {"contract validation": exam.payloads, "leak scan": exam.payloads}))
    exam.problems.extend(
        ran_problems(
            {"independent comparison": exam.comparisons, "v1 control": exam.v1_controls}, {"independent comparison": exam.examined, "v1 control": exam.examined}
        )
    )
    return exam


def _detail_count_problems(exam: DetailExam) -> list[str]:
    """The independent counts against the examined counts, before any numeric floor (a floor of zero here: only the equality)."""
    pairs = (
        ("subtask ids", exam.subtask_ids, exam.independent_subtask_ids),
        ("owned file entries", exam.owned_file_entries, exam.independent_owned_file_entries),
        ("dependency entries", exam.dependency_entries, exam.independent_dependency_entries),
        ("review cycle files", exam.review_cycle_files, exam.independent_cycle_files),
        ("verdict cycles", exam.verdict_cycles, exam.independent_verdict_cycles),
        ("status-log-only ids answered 404", exam.status_log_only_not_found, exam.status_log_only),
    )
    problems = [problem for name, served, scanned in pairs for problem in count_problems(name, examined=served, discovered=scanned, floor=0)]
    problems.extend(count_problems("work packages examined plus refused", examined=exam.examined + exam.refused_total, discovered=exam.discovered, floor=0))
    return problems


# ---------------------------------------------------------------------------
# The pinned anomaly fixture and the floors
# ---------------------------------------------------------------------------


def load_anomaly_fixture(repo_root: Path) -> dict[str, Any]:
    """The authored fixture beside ``mission_status_expected.json``: the named anomalies of the corpus (no generated values)."""
    return json.loads((repo_root / "tests" / "contract" / "fixtures" / FIXTURE_NAME).read_text(encoding="utf-8"))


def _named_content_problems(exam: ArtifactExam, items: Sequence[Mapping[str, Any]]) -> tuple[list[str], set[tuple[str, str]]]:
    problems, named = [], set()
    for item in items:
        key = (item["mission"], item["path"])
        named.add(key)
        got, wanted = exam.refusals.get(key), (item["status"], item["code"])
        if got != wanted:
            problems.append(f"{key[0]}/{key[1]}: named as {wanted}, now {got}")
    return problems, named


def anomaly_fixture_problems(exam: CorpusExam, fixture: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """The pinned anomalies as a subset check: every named entry must still be present and behave as stated; an unnamed new one is only reported.

    An archived Mission cannot be edited, and a new Mission may add an anomaly of its own, so only a vanished or changed NAMED entry fails.
    """
    problems, named_content = _named_content_problems(exam.artifacts, fixture["refused_content"])
    unnamed = [
        f"{mission}/{path}: {status} {code}" for (mission, path), (status, code) in sorted(exam.artifacts.refusals.items()) if (mission, path) not in named_content
    ]
    named_prompt = {(item["mission"], item["wp_id"]) for item in fixture["no_prompt_file"]}
    for item in fixture["no_prompt_file"]:
        key = (item["mission"], item["wp_id"])
        if key not in exam.details.no_prompt:
            problems.append(f"{key[0]}/{key[1]}: named as a work package with no prompt file, but it has one now")
        if exam.artifacts.entries.get((item["mission"], item["file"]), ("absent", False))[0] != "other":
            problems.append(f"{item['mission']}/{item['file']}: named as a file that is no prompt (kind other)")
    unnamed.extend(f"{mission}/{wp_id}: a work package with no prompt file" for mission, wp_id in sorted(exam.details.no_prompt - named_prompt))
    named_duplicates = {item["mission"]: sorted(item["wp_ids"]) for item in fixture["duplicate_work_package_ids"]}
    for mission, wp_ids in named_duplicates.items():
        if exam.details.duplicate_ids.get(mission) != wp_ids:
            problems.append(f"{mission}: named as holding duplicate work package ids {wp_ids}, now {exam.details.duplicate_ids.get(mission)}")
    unnamed.extend(f"{mission}: duplicate work package ids {ids}" for mission, ids in sorted(exam.details.duplicate_ids.items()) if mission not in named_duplicates)
    named_refused = {item["mission"]: item["work_packages"] for item in fixture["refused_missions"]}
    for mission, count in named_refused.items():
        if exam.details.refused.get(mission) != count or exam.details.expected_refused.get(mission) != count:
            now, scanned = exam.details.refused.get(mission), exam.details.expected_refused.get(mission)
            problems.append(f"{mission}: named as refused for all {count} work packages, now refused {now} and the independent scan expects {scanned}")
    unnamed.extend(
        f"{mission}: refused Mission of {count} work packages" for mission, count in sorted(exam.details.expected_refused.items()) if mission not in named_refused
    )
    return problems, unnamed


def extension_floor_problems(exam: CorpusExam) -> list[str]:
    """Every extension floor against the successful (200) counts: the second guard, after examined equals discovered."""
    details, listed = exam.details, exam.artifacts
    counts = {
        "detail_work_packages": (details.examined, FLOORS.detail_work_packages),
        "status_log_only": (details.status_log_only, FLOORS.status_log_only),
        "subtask_ids": (details.subtask_ids, FLOORS.subtask_ids),
        "table_rows": (details.table_rows, FLOORS.table_rows),
        "checkbox_rows": (details.checkbox_rows, FLOORS.checkbox_rows),
        "owned_file_entries": (details.owned_file_entries, FLOORS.owned_file_entries),
        "dependency_entries": (details.dependency_entries, FLOORS.dependency_entries),
        "review_cycle_files": (details.review_cycle_files, FLOORS.review_cycle_files),
        "missions_with_cycles": (details.missions_with_cycles, FLOORS.missions_with_cycles),
        "unparseable_cycles": (details.unparseable_cycles, FLOORS.unparseable_cycles),
        "verdict_cycles": (details.verdict_cycles, FLOORS.verdict_cycles),
        "artifact_entries": (listed.listed_files, FLOORS.artifact_entries),
        "readable_true": (listed.readable_true, FLOORS.readable_true),
        "redacted_files": (listed.redacted_files, FLOORS.redacted_files),
        "missions_without_lanes": (listed.missions_without_lanes, FLOORS.missions_without_lanes),
    }
    problems = [f"{name} is {measured}, floor {floor}" for name, (measured, floor) in counts.items() if measured < floor]
    problems.extend(f"{name} is zero: a floor over nothing proves nothing" for name, (measured, _) in counts.items() if measured == 0)
    anomalies = {"date-only cycles": details.date_only_cycles, "unreadable files": listed.readable_false, "duplicate-id Missions": len(details.duplicate_ids)}
    problems.extend(f"{name}: none found, the anomaly floor is 1" for name, found in anomalies.items() if found < 1)
    missing_kinds = sorted(set(artifacts.ARTIFACT_KINDS) - set(listed.kinds))
    problems.extend([f"no listing entry of kind {missing_kinds}"] if missing_kinds else [])
    return problems


@pytest.fixture(scope="module")
def corpus_exam(tools: helper.ContractTools, contract: helper.Contract) -> CorpusExam:
    """Examine the whole corpus once for every corpus-level test of the extension, between two fingerprints of ``kitty-specs/``."""
    ctx = artifacts.ReaderContext(repo_root=REPO_ROOT, tools=tools, mission_dirs=artifacts.index_missions(REPO_ROOT))
    before = tree_fingerprint(REPO_ROOT, KITTY_SPECS)
    exam = CorpusExam(examine_artifacts(ctx, contract, REPO_ROOT), examine_details(ctx, contract, REPO_ROOT))
    exam.fingerprint_before, exam.fingerprint_after = before, tree_fingerprint(REPO_ROOT, KITTY_SPECS)
    return exam


# ---------------------------------------------------------------------------
# The reality extension: independent counts, floors, the pinned anomaly fixture (WP08, FR-021)
# ---------------------------------------------------------------------------


def test_the_new_floors_are_pinned_below_the_measured_corpus(corpus_exam: CorpusExam) -> None:
    """Every numeric floor of the extension is met by a figure measured here, and none was raised above a measurement."""
    problems = extension_floor_problems(corpus_exam)
    assert not problems, "; ".join(problems)
    assert FLOORS.detail_work_packages >= 3000 and FLOORS.artifact_entries >= 14000


# The floors as the contracts note (section D) fixed them at plan time. A floor may be raised, never lowered: each is pinned here with ``>=``.
PLAN_TIME_FLOORS: dict[str, int] = {
    "detail_work_packages": 3000,
    "status_log_only": 26,
    "subtask_ids": 14000,
    "table_rows": 12000,
    "checkbox_rows": 8300,
    "owned_file_entries": 13000,
    "dependency_entries": 3100,
    "review_cycle_files": 1200,
    "missions_with_cycles": 210,
    "unparseable_cycles": 150,
    "verdict_cycles": 290,
    "artifact_entries": 14000,
    "readable_true": 14000,
    "redacted_files": 970,
    "missions_without_lanes": 72,
}


def floor_loosening(floors: Any) -> list[str]:
    return [f"{name} is {getattr(floors, name)}, plan-time floor {value}" for name, value in sorted(PLAN_TIME_FLOORS.items()) if getattr(floors, name) < value]


def test_every_new_floor_is_pinned_at_or_above_its_plan_time_value() -> None:
    assert floor_loosening(FLOORS) == []
    unpinned = {field.name for field in dataclasses.fields(FLOORS)} - set(PLAN_TIME_FLOORS)
    assert unpinned == {"missions", "work_package_payloads", "snapshot_work_packages"}, f"a new floor without a pin: {sorted(unpinned)}"


@pytest.mark.parametrize("name", sorted(PLAN_TIME_FLOORS))
def test_a_floor_loosened_to_one_is_red(name: str) -> None:
    """Mutant: each new floor set to 1 (and to one below plan time) fails the pin."""
    for loosened in (1, PLAN_TIME_FLOORS[name] - 1):
        assert floor_loosening(dataclasses.replace(FLOORS, **{name: loosened})), f"{name}={loosened} was not caught"


def test_no_mission_is_skipped_by_the_verdict_comparison(corpus_exam: CorpusExam) -> None:
    """The verdict comparison is skipped for a Mission whose events are read from elsewhere; today that is no Mission at all."""
    assert corpus_exam.details.non_comparable_missions == 0


def test_details_examined_plus_refused_equals_discovered(corpus_exam: CorpusExam) -> None:
    exam = corpus_exam.details
    counts = f"{exam.examined} examined and {exam.refused_total} refused of {exam.discovered} discovered work packages"
    assert exam.problems == [], f"{counts}: {exam.problems[:5]}"
    assert exam.examined > 0 and exam.discovered > 0, counts
    assert exam.examined + exam.refused_total == exam.discovered, counts


def test_every_refusal_is_on_the_independently_derived_list_and_no_entry_is_stale(corpus_exam: CorpusExam) -> None:
    exam = corpus_exam.details
    assert exam.expected_refused, "the independent scan found no refused Mission: the named list would be vacuous"
    assert exam.refused == exam.expected_refused, f"refused {exam.refused}, the independent scan expects {exam.expected_refused}"


def test_artifact_listing_and_content_examined_equals_discovered(corpus_exam: CorpusExam) -> None:
    exam = corpus_exam.artifacts
    counts = (
        f"{exam.missions} Missions examined of {exam.discovered_missions} discovered, "
        f"{exam.listed_files} listed and {exam.content_examined} read of {exam.discovered_files} discovered files"
    )
    assert exam.problems == [], f"{counts}: {exam.problems[:5]}"
    assert exam.missions == exam.discovered_missions > 0, counts
    assert exam.listed_files == exam.discovered_files > 0, counts
    assert exam.content_examined == exam.discovered_files, counts


def test_the_pinned_anomaly_fixture_names_still_behave_as_stated(corpus_exam: CorpusExam) -> None:
    problems, unnamed = anomaly_fixture_problems(corpus_exam, load_anomaly_fixture(REPO_ROOT))
    for line in unnamed:
        print(f"unnamed anomaly (reported, never a failure): {line}")
    assert not problems, "; ".join(problems)


def test_a_zero_or_short_count_fails_the_check() -> None:
    assert count_problems("things", examined=3, discovered=3, floor=3) == []
    assert count_problems("things", examined=0, discovered=0, floor=0), "zero examined is a failure whatever the floor"
    assert count_problems("things", examined=2, discovered=3, floor=1), "examined short of discovered fails"
    assert count_problems("things", examined=3, discovered=3, floor=4), "a count under its floor fails"


# ---------------------------------------------------------------------------
# Controls on one shared fixture repository: the same examination, run on a repository built at run time
# ---------------------------------------------------------------------------

CLEAN_MISSION = "exam-clean"
LEGACY_MISSION = "exam-legacy"
CLEAN_CYCLE_DIR = "tasks/WP01-fixture"
CLEAN_POINTER = f"review-cycle://{CLEAN_MISSION}/WP01-fixture/review-cycle-1.md"
EXAM_STAMP = "2026-09-01T10:{minute}:00+00:00".format


def _fragments_path() -> str:
    return SLASH + "home" + SLASH + "someone" + SLASH + "work"


def _fragments_email() -> str:
    return "someone" + AT + "example.invalid"


def _fragments_token() -> str:
    return "gh" + "p_" + "a" * 36


def _cycle_text(number: int, reviewed_at: str) -> str:
    header = {
        "cycle_number": number,
        "wp_id": "WP01",
        "mission_slug": CLEAN_MISSION,
        "reviewer_agent": "reviewer-renata",
        "reviewed_at": reviewed_at,
        "affected_files": [],
    }
    return "---\n" + yaml.safe_dump(header, sort_keys=True) + "---\n\nFeedback.\n"


def _exam_files() -> dict[str, str | bytes]:
    """One file of each class the oracle decides: ok, redacted, the cap boundary, every refusal and every order of two causes."""
    filler = b"a" * _CONTENT_CAP
    latin1 = bytes([0x63, 0x61, 0x66, 0xE9])
    credential = _fragments_token().encode("utf-8")
    return {
        "spec.md": f"contact {_fragments_email()} or look in {_fragments_path()}\n",
        "ok/plain.txt": "plain text\n",
        "ok/boundary.txt": filler,
        "big/over.txt": filler + b"a",
        "big/over-with-nul.bin": filler + _NUL_BYTE,
        "big/over-with-secret.txt": credential + filler,
        "bin/nul.bin": b"abc" + _NUL_BYTE + b"def",
        "bin/latin1.txt": latin1,
        "bin/nul-and-secret.txt": credential + _NUL_BYTE,
        "bin/latin1-and-secret.txt": latin1 + credential,
        "secret/token.txt": b"token " + credential + b"\n",
        # Redaction would hide these credentials (the host path and the e-mail address swallow the token), so only a reader
        # that decides on the credential BEFORE redacting answers 422 (AD-17: a credential is never served masked).
        "secret/path-glued.txt": _fragments_path().encode("utf-8") + SLASH.encode("utf-8") + credential + b"\n",
        "secret/email-glued.txt": credential + AT.encode("utf-8") + b"example.invalid\n",
        f"{CLEAN_CYCLE_DIR}/review-cycle-1.md": _cycle_text(1, "2026-09-02T10:00:00Z"),
        f"{CLEAN_CYCLE_DIR}/review-cycle-2.md": "no frontmatter in this cycle file\n",
        f"{CLEAN_CYCLE_DIR}/review-cycle-3.md": _cycle_text(3, "2026-09-03"),
    }


def _write_exam_repo(root: Path) -> None:
    helper.git_init(root)
    rows = [
        helper.transition_row(1, "WP01", "genesis", "planned", at=EXAM_STAMP(minute="01"), actor="finalize-tasks"),
        helper.transition_row(2, "WP01", "planned", "claimed", at=EXAM_STAMP(minute="02")),
        helper.transition_row(3, "WP01", "claimed", "in_progress", at=EXAM_STAMP(minute="03")),
        helper.transition_row(4, "WP01", "in_progress", "for_review", at=EXAM_STAMP(minute="04")),
        helper.transition_row(
            5,
            "WP01",
            "for_review",
            "approved",
            at=EXAM_STAMP(minute="05"),
            review_result={"reviewer": "reviewer-renata", "verdict": "approved", "reference": CLEAN_POINTER},
        ),
        helper.transition_row(6, "WP09", "genesis", "planned", at=EXAM_STAMP(minute="06"), actor="finalize-tasks"),
        helper.transition_row(7, "WP02", "genesis", "planned", at=EXAM_STAMP(minute="07"), actor="finalize-tasks"),
        helper.annotation_row(8, "WP01", {"subtasks": {"T001": "done", "T002": "planned"}}, at=EXAM_STAMP(minute="08")),
    ]
    helper.write_fixture_mission(
        root,
        CLEAN_MISSION,
        meta={"mission_id": helper.fixture_ulid(1)},
        work_packages={
            "WP01": {"dependencies": ["WP02"], "subtasks": ["T001", "T002"], "owned_files": ["src/a.py", "src/b/**"]},
            "WP02": {"dependencies": [], "subtasks": ["T003"], "owned_files": []},
        },
        rows=rows,
        files=_exam_files(),
        tasks_md="| T001 | first | WP01 |\n| T002 | second | WP01 |\n- [ ] T003 third\n",
    )
    legacy = {"feature_slug": LEGACY_MISSION, "target_branch": "main", "lanes": []}
    helper.write_fixture_mission(
        root,
        LEGACY_MISSION,
        meta={"mission_id": helper.fixture_ulid(2)},
        work_packages={"WP01": {}, "WP02": {}},
        lanes=legacy,
        files={"notes.md": "legacy mission\n"},
    )


@pytest.fixture(scope="module")
def exam_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("exam-repo")
    _write_exam_repo(root)
    return root


def _exam_ctx(root: Path, tools: helper.ContractTools) -> artifacts.ReaderContext:
    return artifacts.ReaderContext(repo_root=root, tools=tools, mission_dirs=artifacts.index_missions(root))


def _examine_repo(root: Path, tools: helper.ContractTools, contract: helper.Contract) -> tuple[ArtifactExam, DetailExam]:
    ctx = _exam_ctx(root, tools)
    return examine_artifacts(ctx, contract, root), examine_details(ctx, contract, root)


def test_the_examination_is_clean_on_the_fixture_repository_and_meets_its_expectations(
    exam_repo: Path, tools: helper.ContractTools, contract: helper.Contract
) -> None:
    """Positive control of every check above: the same functions the corpus uses, on a repository with one of each case, find nothing."""
    listed, details = _examine_repo(exam_repo, tools, contract)

    assert listed.problems == [] and details.problems == [], (listed.problems[:3], details.problems[:3])
    assert (listed.statuses[413], listed.statuses[415], listed.statuses[422]) == (3, 4, 3) and listed.statuses[200] > 0, listed.statuses
    assert (details.examined, details.refused, details.expected_refused) == (2, {LEGACY_MISSION: 2}, {LEGACY_MISSION: 2})
    assert (details.review_cycle_files, details.unparseable_cycles, details.verdict_cycles, details.date_only_cycles) == (3, 1, 1, 1)
    assert (details.status_log_only, details.status_log_only_not_found) == (1, 1)
    assert listed.redacted_files >= 1 and listed.readable_false == 10


def test_the_planted_422_boundary_and_order_cases_are_decided_as_the_oracle_says(exam_repo: Path, tools: helper.ContractTools) -> None:
    root = exam_repo / KITTY_SPECS / CLEAN_MISSION
    wanted = {
        "ok/boundary.txt": 200,
        "big/over.txt": 413,
        "big/over-with-nul.bin": 413,
        "big/over-with-secret.txt": 413,
        "bin/nul-and-secret.txt": 415,
        "bin/latin1-and-secret.txt": 415,
        "secret/token.txt": 422,
        "secret/path-glued.txt": 422,
        "secret/email-glued.txt": 422,
        "bin/nul.bin": 415,
    }
    assert {path: oracle_outcome(tools, (root / path).read_bytes()) for path in wanted} == wanted


def _mutant_reader(*, checks: Sequence[str], cap: int = _CONTENT_CAP) -> Callable[..., artifacts.ArtifactOutcome]:
    """A reader that decides in a different order (or skips a rule), standing in for ``read_file`` in BOTH places that call it."""

    def read_file(ctx: artifacts.ReaderContext, mission_dir: Path, path: str) -> artifacts.ArtifactOutcome:
        data = (mission_dir / path).read_bytes()
        text = data.decode("utf-8", errors="replace")
        refusals = {
            "size": (len(data) > cap, artifacts.ARTIFACT_TOO_LARGE),
            "nul": (_NUL_BYTE in data, artifacts.ARTIFACT_NOT_TEXT),
            "utf8": (data.decode("utf-8", errors="replace").encode("utf-8") != data, artifacts.ARTIFACT_NOT_TEXT),
            "secret": (artifacts.has_credential(ctx.tools, text), artifacts.ARTIFACT_SECRET),
            "secret_after_redaction": (artifacts.has_credential(ctx.tools, artifacts.redact(ctx.tools, text)[0]), artifacts.ARTIFACT_SECRET),
        }
        for name in checks:
            refused, code = refusals[name]
            if refused:
                return artifacts.refusal(code)
        content, changed = artifacts.redact(ctx.tools, text)
        body = {
            "path": path,
            "kind": artifacts.classify(path),
            "mediaType": artifacts.media_type_of(path),
            "encoding": artifacts.ENCODING,
            "sizeBytes": len(data),
            "redacted": changed,
            "content": content,
        }
        return artifacts.ArtifactOutcome(200, body)

    return read_file


MUTANTS: dict[str, dict[str, Any]] = {
    "415 decided before 413": {"checks": ("nul", "utf8", "size", "secret")},
    "422 decided before 415": {"checks": ("size", "secret", "nul", "utf8")},
    "a NUL byte is text": {"checks": ("size", "utf8", "secret")},
    "a credential is served": {"checks": ("size", "nul", "utf8")},
    "the size cap is exclusive": {"checks": ("size", "nul", "utf8", "secret"), "cap": _CONTENT_CAP - 1},
    "no encoding check": {"checks": ("size", "nul", "secret")},
    "redacted before the credential check": {"checks": ("size", "nul", "utf8", "secret_after_redaction")},
}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_consistently_wrong_reader_is_killed_by_the_oracle(
    name: str, exam_repo: Path, tools: helper.ContractTools, contract: helper.Contract, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wrong rule is applied to the listing's ``readable`` and to the content read alike, so only the byte-level oracle can see it."""
    monkeypatch.setattr(artifacts, "read_file", _mutant_reader(**MUTANTS[name]))

    listed = examine_artifacts(_exam_ctx(exam_repo, tools), contract, exam_repo)

    assert listed.problems, f"the mutation was not killed: {name}"


def test_the_glued_credentials_are_hidden_by_redaction_and_still_refused(exam_repo: Path, tools: helper.ContractTools) -> None:
    """The premise of the redact-first mutant: each file loses its credential when redacted, so the order of decision is observable."""
    root = exam_repo / KITTY_SPECS / CLEAN_MISSION
    for name in ("secret/path-glued.txt", "secret/email-glued.txt"):
        text = (root / name).read_text(encoding="utf-8")
        assert artifacts.has_credential(tools, text), name
        assert not artifacts.has_credential(tools, artifacts.redact(tools, text)[0]), f"{name}: redaction no longer hides the credential"
        assert oracle_outcome(tools, text.encode("utf-8")) == 422


def test_the_oracle_neither_calls_nor_imports_the_reader(tools: helper.ContractTools, exam_repo: Path) -> None:
    """Independence guard: the oracle states the rules from the bytes; the same check run on a coupled oracle goes red."""
    assert oracle_coupling(oracle_outcome) == []
    assert "oracle_outcome" not in inspect.getsource(artifacts), "the reader must not call the test oracle either"

    def coupled(tools: helper.ContractTools, data: bytes) -> int:
        return artifacts._decide_bytes(tools, "x", len(data), data).status

    assert oracle_coupling(coupled) == ["_decide_bytes", "artifacts"]
    data = (exam_repo / KITTY_SPECS / CLEAN_MISSION / "secret/token.txt").read_bytes()
    assert coupled(tools, data) == oracle_outcome(tools, data) == 422, "the coupled stand-in agrees today, so only the structural check can see it"


def test_readable_decided_by_size_alone_is_killed(exam_repo: Path, tools: helper.ContractTools, contract: helper.Contract, monkeypatch: pytest.MonkeyPatch) -> None:
    real = artifacts.list_artifacts

    def by_size(ctx: artifacts.ReaderContext, mission_id: str) -> artifacts.ArtifactOutcome:
        outcome = real(ctx, mission_id)
        if outcome.status == 200:
            outcome.body["entries"] = [{**entry, "readable": entry["sizeBytes"] <= _CONTENT_CAP} for entry in outcome.body["entries"]]
        return outcome

    monkeypatch.setattr(artifacts, "list_artifacts", by_size)

    assert examine_artifacts(_exam_ctx(exam_repo, tools), contract, exam_repo).problems, "the mutation was not killed: readable decided by size alone"


def test_a_removed_schema_or_leak_check_turns_the_examination_red(
    exam_repo: Path, tools: helper.ContractTools, contract: helper.Contract, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wiring guard: a check that no longer reaches its callee is a named problem for every payload, in both examinations."""
    with monkeypatch.context() as patched:
        patched.setattr(helper, "payload_leaks", lambda payload, tools, **kwargs: [])
        listed, details = _examine_repo(exam_repo, tools, contract)
    assert any("leak scan ran 0 times" in problem for problem in listed.problems), listed.problems[:2]
    assert any("leak scan ran 0 times" in problem for problem in details.problems), details.problems[:2]
    with monkeypatch.context() as patched:
        patched.setattr(contract, "errors", lambda title, payload: [])
        listed, details = _examine_repo(exam_repo, tools, contract)
    assert any("contract validation ran 0 times" in problem for problem in listed.problems), listed.problems[:2]
    assert any("contract validation ran 0 times" in problem for problem in details.problems), details.problems[:2]


def test_the_wiring_guard_names_each_check_that_ran_too_few_times() -> None:
    assert ran_problems({"leak scan": 4, "contract validation": 4}, {"leak scan": 4, "contract validation": 4}) == []
    problems = ran_problems({}, {"leak scan": 4, "contract validation": 4, "oracle comparison": 2})
    assert [line.split(" ran ")[0] for line in problems] == ["the leak scan", "the contract validation", "the oracle comparison"]
    assert ran_problems({"leak scan": 5}, {"leak scan": 4}), "more runs than payloads is as wrong as fewer"


# ---- refusals and the refused list ----------------------------------------------------------------------------------


def test_a_refusal_outside_the_independently_derived_list_fails(tmp_path: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    """A ``lanes.json`` that is not JSON is refused by the reader too, but the independent scan does not list it: that is a failure, never a skip."""
    helper.git_init(tmp_path)
    helper.write_fixture_mission(tmp_path, "broken", work_packages={"WP01": {}})
    (tmp_path / KITTY_SPECS / "broken" / "lanes.json").write_text("{ not json", encoding="utf-8")

    details = examine_details(_exam_ctx(tmp_path, tools), contract, tmp_path)

    assert details.refused == {"broken": 1} and details.expected_refused == {}
    assert any("not on the independently derived refused list" in problem for problem in details.problems), details.problems


def test_a_listed_mission_that_answers_200_is_a_stale_entry(
    tmp_path: Path, tools: helper.ContractTools, contract: helper.Contract, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The independent scan lists the legacy Mission; if the reader stops refusing it (here a manifest that reads as absent) the pin is stale."""
    helper.git_init(tmp_path)
    helper.write_fixture_mission(tmp_path, LEGACY_MISSION, work_packages={"WP01": {}}, lanes={"feature_slug": LEGACY_MISSION, "lanes": []})
    ctx = _exam_ctx(tmp_path, tools)
    control = examine_details(ctx, contract, tmp_path)
    assert control.refused == control.expected_refused == {LEGACY_MISSION: 1}, "control: refused exactly as listed"
    assert not [problem for problem in control.problems if "refus" in problem or "stale" in problem], control.problems

    monkeypatch.setattr(detail, "read_lanes_json", lambda directory: None)  # a Mission with no manifest reads as no lane: 200

    stale = examine_details(ctx, contract, tmp_path)

    assert stale.refused == {} and any("stale entry" in problem for problem in stale.problems), stale.problems


def test_the_anomaly_fixture_check_fails_on_a_vanished_or_changed_named_entry_and_only_reports_a_new_one(corpus_exam: CorpusExam) -> None:
    fixture = load_anomaly_fixture(REPO_ROOT)
    assert anomaly_fixture_problems(corpus_exam, fixture) == ([], [])
    changed = {**fixture, "refused_content": [{**fixture["refused_content"][0], "status": 415}, *fixture["refused_content"][1:]]}
    assert any("named as" in problem for problem in anomaly_fixture_problems(corpus_exam, changed)[0])
    dropped = {**fixture, "refused_content": fixture["refused_content"][1:]}
    problems, unnamed = anomaly_fixture_problems(corpus_exam, dropped)
    assert problems == [] and len(unnamed) == 1, "an unnamed anomaly is reported, never a failure"
    wrong_count = {**fixture, "refused_missions": [{**fixture["refused_missions"][0], "work_packages": 8}]}
    assert any("named as refused for all 8" in problem for problem in anomaly_fixture_problems(corpus_exam, wrong_count)[0]), (
        "a pinned count that differs is a stale pin"
    )
    stale = {
        **fixture,
        "refused_missions": [*fixture["refused_missions"], {"mission": "a-mission-that-answers-200", "work_packages": 1, "code": "source_unreadable"}],
    }
    assert any("a-mission-that-answers-200" in problem for problem in anomaly_fixture_problems(corpus_exam, stale)[0])
    gone = {**fixture, "no_prompt_file": [{**fixture["no_prompt_file"][0], "wp_id": "WP99"}], "duplicate_work_package_ids": []}
    problems, unnamed = anomaly_fixture_problems(corpus_exam, gone)
    assert any("WP99" in problem for problem in problems) and any("duplicate work package ids" in line for line in unnamed)


# ---- the v1 controls, the cycle checks and the detail mutations ---------------------------------------------------------


def _clean_detail_and_v1(exam_repo: Path, tools: helper.ContractTools) -> tuple[dict[str, Any], dict[str, Any], ScannedWorkPackage]:
    ctx = _exam_ctx(exam_repo, tools)
    mission = scan_missions(exam_repo)[helper.fixture_ulid(1)]
    body = detail.build_work_package_detail(ctx, mission.mission_id, "WP01", detail.NO_WORKTREES).body
    opened = detail.open_mission(ctx, mission.mission_id)
    assert isinstance(opened, detail.OpenedMission)
    authored = {item.path.name: item for item in helper.read_authored_files(opened.source.own_dir)}[opened.index["WP01"].name]
    v1 = helper.build_work_package(opened.source, authored, helper.Projector(tools.leak, mission.name))
    return body, v1, scan_work_packages(mission)["WP01"]


def test_the_v1_controls_hold_on_the_fixture_and_each_planted_mismatch_fails(exam_repo: Path, tools: helper.ContractTools) -> None:
    body, v1, scanned = _clean_detail_and_v1(exam_repo, tools)
    assert v1_control_problems(body, v1) == [] and independent_list_problems(body, scanned) == [], (
        "control: the real detail agrees with v1 and with the frontmatter"
    )
    planted = {
        "subtasks[].id": {**body, "subtasks": [{**body["subtasks"][0], "id": "T999"}, *body["subtasks"][1:]]},
        "dependencies[].wpId": {**body, "dependencies": [{**body["dependencies"][0], "wpId": "WP77"}]},
        "ownedFiles[].pattern": {**body, "ownedFiles": body["ownedFiles"][:-1]},
    }
    for needle, payload in planted.items():
        assert any(needle in problem for problem in v1_control_problems(payload, v1)), f"the v1 control did not see a planted {needle} mismatch"
        assert independent_list_problems(payload, scanned), f"the frontmatter control did not see a planted {needle} mismatch"


def test_the_cycle_checks_hold_on_the_fixture_and_each_planted_mismatch_fails(exam_repo: Path, tools: helper.ContractTools) -> None:
    body, _v1, _scanned = _clean_detail_and_v1(exam_repo, tools)
    mission = scan_missions(exam_repo)[helper.fixture_ulid(1)]
    scanned = scan_cycles(mission, "WP01", scan_event_rows(mission.directory), VERDICTS)
    assert [cycle.verdict for cycle in scanned] == ["approved", None, None] and [cycle.parsed for cycle in scanned] == [True, False, True]
    assert cycle_problems(body["reviewCycles"], scanned, True) == [], "control: the served cycles agree with the files and the log"
    served = body["reviewCycles"]
    planted = (
        [{**served[0], "verdict": None}, *served[1:]],
        [{**served[0], "reviewedAt": "2026-01-01T00:00:00Z"}, *served[1:]],
        [served[0], {**served[1], "reviewer": "reviewer-renata"}, served[2]],
        [served[0], {**served[1], "feedbackReference": None}, served[2]],
        [{**served[2], "reviewedAt": "2026-09-03T00:00:00Z"}] + served[:2],
        served[:2],
    )
    for index, entries in enumerate(planted):
        assert cycle_problems(entries, scanned, True), f"the cycle check did not see planted mismatch {index}"
    assert cycle_problems([{**served[0], "verdict": None}, *served[1:]], scanned, False) == [], "a log from another surface is not compared"


_REAL_SUBTASKS = detail.subtask_entries
_REAL_DEPENDENCIES = detail.dependency_entries
DETAIL_MUTANTS: dict[str, tuple[str, Callable[..., Any]]] = {
    "the dependencies are dropped": ("dependency_entries", lambda *args, **kwargs: []),
    "the subtasks are reversed": ("subtask_entries", lambda *args, **kwargs: list(reversed(_REAL_SUBTASKS(*args, **kwargs)))),
    "the review cycles are dropped": ("review_cycles", lambda *args, **kwargs: []),
    "the subtask lanes are nulled": ("subtask_entries", lambda *args, **kwargs: [{**entry, "statusLane": None} for entry in _REAL_SUBTASKS(*args, **kwargs)]),
    "the dependency lanes are nulled": (
        "dependency_entries",
        lambda *args, **kwargs: [{**entry, "statusLane": None} for entry in _REAL_DEPENDENCIES(*args, **kwargs)],
    ),
}


@pytest.mark.parametrize("name", sorted(DETAIL_MUTANTS))
def test_a_defective_detail_reader_is_killed(
    name: str, exam_repo: Path, tools: helper.ContractTools, contract: helper.Contract, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, replacement = DETAIL_MUTANTS[name]
    monkeypatch.setattr(detail, target, replacement)

    details = examine_details(_exam_ctx(exam_repo, tools), contract, exam_repo)

    assert details.problems, f"the mutation was not killed: {name}"


# ---- planted payload defects on one shared fixture Mission ----------------------------------------------------------------


def _payload_problems(contract: helper.Contract, tools: helper.ContractTools, title: str, payload: Mapping[str, Any]) -> list[str]:
    return [*contract.errors(title, payload), *helper.payload_leaks(payload, tools)]


def _clean_payloads(exam_repo: Path, tools: helper.ContractTools) -> dict[str, tuple[str, dict[str, Any]]]:
    ctx = _exam_ctx(exam_repo, tools)
    mission_id = helper.fixture_ulid(1)
    return {
        "detail": (helper.SCHEMA_WORK_PACKAGE_DETAIL, detail.build_work_package_detail(ctx, mission_id, "WP01", detail.NO_WORKTREES).body),
        "listing": (helper.SCHEMA_ARTIFACT_LISTING, artifacts.list_artifacts(ctx, mission_id).body),
        "content": (helper.SCHEMA_ARTIFACT_CONTENT, artifacts.read_content(ctx, mission_id, ["ok/plain.txt"]).body),
        "refusal": (helper.SCHEMA_ARTIFACT_REFUSAL, artifacts.read_content(ctx, mission_id, ["secret/token.txt"]).body),
    }


def _planted(kind: str, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The same payload with one planted defect each: a host path, an address, a credential, an unknown lane, an extra property, an absolute pointer."""
    if kind == "detail":
        subtask = payload["subtasks"][0]
        return {
            "host path": {**payload, "subtasks": [{**subtask, "title": f"see {_fragments_path()}"}]},
            "e-mail address": {**payload, "subtasks": [{**subtask, "title": f"ask {_fragments_email()}"}]},
            "credential": {**payload, "subtasks": [{**subtask, "title": _fragments_token()}]},
            "unknown lane": {**payload, "subtasks": [{**subtask, "statusLane": "doing"}]},
            "extra property": {**payload, "unexpected": True},
            "absolute pointer": {**payload, "reviewCycles": [{**payload["reviewCycles"][0], "feedbackReference": SLASH + "etc" + SLASH + "passwd"}]},
            "absolute artifact path": {**payload, "reviewCycles": [{**payload["reviewCycles"][0], "artifactPath": _fragments_path()}]},
        }
    if kind == "listing":
        entry = payload["entries"][0]
        return {
            "absolute pointer": {**payload, "entries": [{**entry, "path": SLASH + "etc" + SLASH + "passwd"}]},
            "host path": {**payload, "entries": [{**entry, "path": _fragments_path()}]},
            "unknown kind": {**payload, "entries": [{**entry, "kind": "diary"}]},
            "extra property": {**payload, "unexpected": True},
            "credential": {**payload, "missionId": _fragments_token()},
        }
    if kind == "content":
        return {
            "host path": {**payload, "content": f"see {_fragments_path()}"},
            "e-mail address": {**payload, "content": f"ask {_fragments_email()}"},
            "credential": {**payload, "content": _fragments_token()},
            "extra property": {**payload, "unexpected": True},
            "absolute pointer": {**payload, "path": SLASH + "etc" + SLASH + "passwd"},
        }
    return {
        "extra property": {**payload, "unexpected": True},
        "credential": {**payload, "detail": _fragments_token()},
        "host path": {**payload, "detail": f"see {_fragments_path()}"},
        "e-mail address": {**payload, "detail": f"ask {_fragments_email()}"},
    }


def test_each_real_payload_is_clean_and_each_planted_defect_is_found(exam_repo: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    """One shared fixture Mission: the four payload kinds a service answers validate and scan clean; each planted defect is found by the schema or the scan."""
    clean = _clean_payloads(exam_repo, tools)
    planted_count = 0
    for kind, (title, payload) in clean.items():
        assert _payload_problems(contract, tools, title, payload) == [], f"control: the real {kind} payload is clean"
        for defect, planted in _planted(kind, payload).items():
            planted_count += 1
            assert _payload_problems(contract, tools, title, planted), f"the planted {defect} in a {kind} payload was not found"
    assert planted_count == 7 + 5 + 5 + 4


def test_the_new_readers_leave_the_corpus_tree_as_they_found_it(corpus_exam: CorpusExam) -> None:
    """The corpus examination read every Mission directory between two fingerprints (bytes, ``git status``, ignored files and directory names).

    The fingerprint is the very one whose sensitivity to a created empty directory, a rewritten file and an ignored file is planted
    above (``test_a_created_empty_directory_changes_the_fingerprint_that_git_cannot_see``); no second planted control is written here.
    """
    assert corpus_exam.fingerprint_before.files > 0 and corpus_exam.fingerprint_before.directories > 0
    assert corpus_exam.fingerprint_after == corpus_exam.fingerprint_before, "a new reader wrote something under kitty-specs/"


# Keep this test LAST in the file: under ``--dist loadfile`` the file runs on one worker in
# definition order, so the case counter is complete when it runs.
def test_every_generated_case_executed_and_the_count_is_not_vacuous() -> None:
    with_meta = enumerate_missions(REPO_ROOT)
    assert len(CASES) == len(with_meta) >= FLOORS.missions, "the case list must equal the Missions with a meta.json"
    assert set(CASES) == EXECUTED, f"{len(CASES) - len(EXECUTED)} generated cases did not execute"
    payloads = sum(CASE_RESULTS[mission].work_packages for mission in CASES)
    assert payloads >= FLOORS.work_package_payloads, f"{payloads} work package payloads validated, floor {FLOORS.work_package_payloads}"
