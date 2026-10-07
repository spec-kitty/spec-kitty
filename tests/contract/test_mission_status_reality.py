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
import functools
import inspect
import itertools
import json
import os
import re
import subprocess
import textwrap
import time
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from kernel.clock import FrozenClock, parse_iso
from specify_cli.context import mission_resolver
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.git.remote_probes import _reset_remote_branch_lookup_cache
from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status.reducer import materialize_snapshot, materialize_to_json
from tests.contract import _mission_status_artifacts as artifacts
from tests.contract import _mission_status_detail as detail
from tests.contract import _mission_status_drift as drift
from tests.contract import _mission_status_memo as memo_module
from tests.contract import _mission_status_ops as ops_reader
from tests.contract import _mission_status_oracles as oracles
from tests.contract import _mission_status_payloads as helper
from tests.contract import _mission_status_project as project_builder
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


PRODUCTION_BUILD_INDEX = mission_resolver._build_index  # the uncached resolver walk, captured before any fixture patches it


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
    built = project_builder.build_project(REPO_ROOT, memo_module.ResolverMemo(), leak=tools.leak)
    project = built.body
    assert contract.errors(helper.SCHEMA_PROJECT, project) == []
    assert project["missionCount"] == len(overviews) == len(CASES)
    # The v1 build of the same project is the control: its Mission count and its latest activity are the builder's.
    assert project == helper.derive_project(
        helper.read_project_name(REPO_ROOT),
        overviews,
        spec_kitty_version=project["specKittyVersion"],
        schema_version=project["schemaVersion"],
        health=project["health"],
        current_branch=project["currentBranch"],
    )
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
    unpinned = {field.name for field in dataclasses.fields(FLOORS)} - set(PLAN_TIME_FLOORS) - set(P13_FLOORS)
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


# ===========================================================================
# The health, drift and Ops reads over the corpus (WP09; spec FR-025; AC-REALITY 1 to 3, AC-DRIFT 19, AC-CROSS 4)
# ===========================================================================
#
# Every corpus case is a test named ``test_corpus_*`` and is in exactly one disposition set. A case that reaches the coordination
# resolver (the Project build, the drift scan) takes a named skip when a configured remote cannot be reached; a case that does not
# (the Ops walk, the completion equality, the real listing bound, the AST test, the fingerprints) runs in every environment. The last
# test of the file counts the cases that ran and the cases that were skipped by name against the plan, so a case can neither vanish
# nor slip into the skip. Everything else below is a control on a repository built at run time (a plant and its control).

NOW = parse_iso("2026-10-07T09:00:00+00:00")
OPS_TREE = "kitty-ops"
CORPUS_TREES = (KITTY_SPECS, OPS_TREE)
BOUND_SECONDS = 120.0
LISTING_BOUND_SECONDS = 5.0
MIN_REPEATS = 5
OPS_PAGE_SIZE = 200
OFFLINE_SKIP = "offline: a configured remote cannot be reached, so the assertions that depend on the coordination resolver take this named skip"
ONLINE_SKIP = "online: this case asserts the outcome of an unreachable remote and runs only offline"
ORACLES_FILE = Path(__file__).with_name("_mission_status_oracles.py")
ANOMALY_FILE = "mission_status_health_drift_ops_expected.json"
READER_MODULES = frozenset(
    {"_mission_status_drift", "_mission_status_ops", "_mission_status_project", "_mission_status_artifacts", "_mission_status_detail", "_mission_status_payloads"}
)
READER_ALIASES = frozenset({"drift", "ops_reader", "project_builder", "artifacts", "detail", "helper"})
RESOLVER_USES = frozenset({"corpus_run", "scan_drift", "build_project", "memo_resolve", "ResolverMemo", "MissionStatus"})
FALLBACK_REASON = "coordination_branch_deleted"
KIND_ONE, KIND_TWO, KIND_THREE = oracles.KIND_DISAGREES, oracles.KIND_MISSING, oracles.KIND_BRANCH

ALWAYS_CASES = frozenset(
    {
        "test_corpus_ops_walk_equals_the_oracle_and_leaves_the_trees_as_found",
        "test_corpus_ops_skipped_count_and_named_list_equal_the_oracle",
        "test_corpus_ops_floors_and_evidence_kinds_equal_the_oracle",
        "test_corpus_completion_equals_is_mission_completed",
        "test_corpus_ops_listing_is_within_five_seconds",
        "test_corpus_the_oracles_neither_call_nor_import_a_reader",
        "test_corpus_case_dispositions_follow_the_resolver_use",
    }
)
RESOLVER_CASES = frozenset(
    {
        "test_corpus_drift_scan_is_a_200_and_the_resolver_ran_once_per_mission",
        "test_corpus_fallback_list_equals_the_independent_derivation",
        "test_corpus_missions_examined_plus_skipped_equals_discovered",
        "test_corpus_kinds_one_and_two_equal_the_oracle_and_meet_their_floors",
        "test_corpus_kind_three_equals_the_oracle",
        "test_corpus_project_report_equals_the_oracles",
        "test_corpus_per_mission_reports_equal_the_filtered_findings",
        "test_corpus_payloads_validate_and_leak_clean",
        "test_corpus_project_build_is_within_its_bound",
        "test_corpus_scan_is_within_its_bound",
        "test_corpus_combined_run_is_within_its_bound",
        "test_corpus_trees_are_unchanged_by_the_resolver_run",
    }
)
OFFLINE_ONLY_CASES = frozenset({"test_corpus_offline_scan_is_a_200_with_no_fallback_entry"})
CORPUS_CASES = ALWAYS_CASES | RESOLVER_CASES | OFFLINE_ONLY_CASES


@dataclass(frozen=True)
class CasePlan:
    """What an environment runs and what it skips by name, with the reason of each skip."""

    run: frozenset[str]
    skip: Mapping[str, str]


def case_plan(
    online: bool, always: frozenset[str] = ALWAYS_CASES, resolver: frozenset[str] = RESOLVER_CASES, offline_only: frozenset[str] = OFFLINE_ONLY_CASES
) -> CasePlan:
    """The corpus cases an online and an offline environment run; the resolver-dependent ones are the only skip offline."""
    if online:
        return CasePlan(always | resolver, dict.fromkeys(offline_only, ONLINE_SKIP))
    return CasePlan(always | offline_only, dict.fromkeys(resolver, OFFLINE_SKIP))


@dataclass
class CaseLedger:
    """The corpus cases that started, and the ones that took a named skip with the reason."""

    executed: set[str] = field(default_factory=set)
    skipped: dict[str, str] = field(default_factory=dict)


CASE_LEDGER = CaseLedger()


@pytest.fixture(scope="module")
def remote_state() -> oracles.RemoteState:
    """The network probe, outside every reader: ``git ls-remote --heads`` on each configured remote."""
    return oracles.probe_remotes(REPO_ROOT)


@pytest.fixture(autouse=True)
def case_ledger(request: pytest.FixtureRequest) -> None:
    """Record each corpus case as executed, or skip it by name when the environment cannot run it."""
    name = request.node.originalname if isinstance(request.node, pytest.Function) else request.node.name
    if name not in CORPUS_CASES:
        return
    plan = case_plan(request.getfixturevalue("remote_state").online)
    if name in plan.skip:
        CASE_LEDGER.skipped[name] = plan.skip[name]
        pytest.skip(plan.skip[name])
    CASE_LEDGER.executed.add(name)


def _names_in(function: ast.FunctionDef) -> set[str]:
    """The parameter names, plain names and attribute names a function mentions."""
    mentioned = {argument.arg for argument in function.args.args}
    for node in ast.walk(function):
        if isinstance(node, ast.Name):
            mentioned.add(node.id)
        elif isinstance(node, ast.Attribute):
            mentioned.add(node.attr)
    return mentioned


def disposition_problems(source: str, always: frozenset[str], resolver: frozenset[str], offline_only: frozenset[str]) -> list[str]:
    """Check that every ``test_corpus_*`` function is in exactly one disposition set and that the sets follow the resolver use.

    A case that runs in every environment must not reach the resolver; a case that takes the named skip offline must use the shared
    resolver run; every named case exists. A textual guard over direct references: a bypass through a helper is accepted at severity 1 to 2.
    """
    cases = {node.name: node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_corpus_")}
    problems = [f"{name}: a corpus case in no disposition set" for name in sorted(set(cases) - (always | resolver | offline_only))]
    problems += [f"{name}: named in a disposition set and defined nowhere" for name in sorted((always | resolver | offline_only) - set(cases))]
    problems += [f"{name}: in more than one disposition set" for name in sorted((always & resolver) | (always & offline_only) | (resolver & offline_only))]
    for name in sorted(always & set(cases)):
        reached = _names_in(cases[name]) & RESOLVER_USES
        problems += [f"{name}: runs in every environment but reaches the resolver ({sorted(reached)})"] if reached else []
    for name in sorted(resolver & set(cases)):
        if "corpus_run" not in _names_in(cases[name]):
            problems.append(f"{name}: takes the named skip offline but does not use the shared resolver run")
    return problems


# ---------------------------------------------------------------------------
# The independent expectations of this module (the ``expect_*`` oracle functions: AST-checked, they never call or import a reader)
# ---------------------------------------------------------------------------

FindingKey = tuple[str, str, str, str | None]
OpView = tuple[str, str | None, str | None, str | None, str | None]


def expect_discovered_ops(repo_root: Path) -> int:
    """The Op files of ``kitty-ops/`` by a directory listing and a name pattern: the discovered set of the Ops identity."""
    directory = repo_root / OPS_TREE
    pattern = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}[.]jsonl")
    return sum(1 for name in os.listdir(directory) if pattern.fullmatch(name)) if directory.is_dir() else 0


def expect_non_coordination_count(repo_root: Path) -> int:
    """The Missions whose ``meta.json`` declares no coordination branch, by a raw JSON scan: the independent count of AC-DRIFT row 19."""
    count = 0
    for meta_path in sorted((repo_root / KITTY_SPECS).glob("*/meta.json")):
        branch = json.loads(meta_path.read_bytes().decode("utf-8")).get("coordination_branch")
        count += 0 if isinstance(branch, str) and branch else 1
    return count


def expect_finding_keys(expected: oracles.DriftOracle) -> set[FindingKey]:
    """Every finding the drift oracles state, as ``(missionId, kind, artifactPath, sourceCode)``."""
    keys = {(item.mission_id, item.kind, item.artifact_path, item.source_code) for item in expected.findings}
    return keys | {(item.mission_id, item.kind, item.artifact_path, item.source_code) for item in expected.kind3.findings.values()}


def expect_op_views(scan: oracles.OpsScan) -> dict[str, OpView]:
    """Every served Op as ``(status, outcome, closedBy, completedAt, evidence class)`` by the oracle's direct scan."""
    return {key: (op.status, op.outcome, op.closed_by, op.completed_at, op.evidence_category) for key, op in scan.served.items()}


ORACLE_FUNCTIONS = (expect_discovered_ops, expect_non_coordination_count, expect_finding_keys, expect_op_views)


# ---------------------------------------------------------------------------
# Comparison helpers (they read what a reader returned; they are not oracles)
# ---------------------------------------------------------------------------


def reader_finding_keys(findings: Sequence[Mapping[str, Any]]) -> set[FindingKey]:
    return {(item["missionId"], item["kind"], item["artifactPath"], item["sourceCode"]) for item in findings}


def duplicate_problems(label: str, findings: Sequence[Mapping[str, Any]]) -> list[str]:
    """A finding served twice collapses in a set comparison, so the count must equal the number of distinct keys."""
    distinct = len(reader_finding_keys(findings))
    return [f"{label}: the reader served {len(findings)} findings for {distinct} distinct keys"] if len(findings) != distinct else []


def difference_problems(label: str, reader: Iterable[Any], oracle: Iterable[Any]) -> list[str]:
    """Both directions of a set comparison, each side named: what only the reader says and what only the oracle says."""
    left, right = set(reader), set(oracle)
    problems = []
    if left - right:
        problems.append(f"{label}: only the reader has {sorted(left - right, key=str)[:3]} ({len(left - right)} in all)")
    if right - left:
        problems.append(f"{label}: only the oracle has {sorted(right - left, key=str)[:3]} ({len(right - left)} in all)")
    return problems


def served_category(evidence: Mapping[str, Any] | None) -> str:
    """The class of a served evidence object in the oracle's vocabulary (a host path is served as the path token)."""
    if evidence is None:
        return oracles.CATEGORY_NONE
    if evidence["kind"] == "url":
        return oracles.CATEGORY_URL
    if evidence["kind"] == "repo_path":
        return oracles.CATEGORY_RELATIVE
    return oracles.CATEGORY_ABSOLUTE if evidence["value"] == ops_reader.PATH_TOKEN else oracles.CATEGORY_FREE_TEXT


def reader_op_view(item: Mapping[str, Any]) -> OpView:
    category = served_category(item["evidence"]) if item["status"] == "closed" else None
    return (item["status"], item["outcome"], item["closedBy"], item["completedAt"], category)


def new_floor_problems(measured: Mapping[str, int], floors: Any = FLOORS, *, only: Collection[str] | None = None) -> list[str]:
    """Each measured count of the new reads against its floor of D-P13, and a measured zero of a floored count (a floor over nothing proves nothing)."""
    wanted = {
        "missions_examined": floors.missions_examined,
        "ops_served": floors.ops_served,
        "spine_closed_ops": floors.spine_closed_ops,
        "evidence_none": floors.evidence_none,
        "evidence_absolute_path": floors.evidence_absolute_path,
        "evidence_free_text": floors.evidence_free_text,
        "evidence_relative_reference": floors.evidence_relative_reference,
        "evidence_url": floors.evidence_url,
        "kind1_findings": floors.kind1_findings,
        "kind2_findings": floors.kind2_findings,
        "completion_compared": floors.completion_compared,
    }
    if only is not None:
        wanted = {name: floor for name, floor in wanted.items() if name in only}
    problems = [f"{name} is {measured.get(name)}, floor {floor}" for name, floor in wanted.items() if measured.get(name, 0) < floor]
    problems += [f"{name} is zero: a floor over nothing proves nothing" for name, floor in wanted.items() if floor > 0 and measured.get(name, 0) == 0]
    return problems


P13_FLOORS: dict[str, int] = {
    "missions_examined": 540,
    "ops_served": 440,
    "spine_closed_ops": 5,
    "evidence_none": 330,
    "evidence_absolute_path": 28,
    "evidence_free_text": 50,
    "evidence_relative_reference": 25,
    "evidence_url": 0,
    "kind1_findings": 39,
    "kind2_findings": 27,
    "completion_compared": 490,
}


def p13_loosening(floors: Any) -> list[str]:
    return [f"{name} is {getattr(floors, name)}, plan-time floor {value}" for name, value in sorted(P13_FLOORS.items()) if getattr(floors, name) < value]


# ---------------------------------------------------------------------------
# Timing: the minimum of cold repeats (D-P16), the bound, and the cache guard
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Repeats:
    """The wall-clock seconds of each cold repeat and the files each repeat opened."""

    seconds: tuple[float, ...]
    opens: tuple[int, ...]

    @property
    def minimum(self) -> float:
        return min(self.seconds)


def timed_cold_repeats(run: Callable[[], int], *, repeats: int = MIN_REPEATS, timer: Callable[[], float] = time.perf_counter) -> Repeats:
    """Time ``run`` at least ``MIN_REPEATS`` times; ``run`` is one cold call and returns the number of files it opened. Never a retry."""
    if repeats < MIN_REPEATS:
        raise ValueError(f"{repeats} repeats: a timed bound needs at least {MIN_REPEATS}")
    seconds, opens = [], []
    for _ in range(repeats):
        started = timer()
        opens.append(run())
        seconds.append(timer() - started)
    return Repeats(tuple(seconds), tuple(opens))


def timing_problems(name: str, measured: float, bound: float, counts: str) -> list[str]:
    """One line when ``measured`` seconds exceed ``bound``; the discovered counts ride in the text."""
    return [f"{name}: {measured:.3f} s exceeds the {bound:g} s bound ({counts})"] if measured > bound else []


def counting_ops_fs(opened: list[int]) -> ops_reader.FileSystem:
    """The real file-system seam of the Ops reader with a counter on every file it opens (a fresh one per repeat)."""
    real = ops_reader.REAL_FS

    def open_binary(path: Path) -> bytes:
        opened[0] += 1
        return real.open_binary(path)

    return ops_reader.FileSystem(stat=real.stat, scandir=real.scandir, open_binary=open_binary)


def listing_problems(
    repo_root: Path, tools: helper.ContractTools, *, expected_files: int, repeats: int = MIN_REPEATS, timer: Callable[[], float] = time.perf_counter
) -> tuple[list[str], Repeats]:
    """The real ``kitty-ops/`` listing bound (AC-CROSS 4): the minimum of cold repeats of the production entry point, at most 5 s.

    Every repeat is a fresh call with a fresh counting seam, and the case asserts that every repeat opened every Op file, so a call that
    answered from a cache (a repeat that opened nothing) is never read as fast.
    """

    def one() -> int:
        opened = [0]
        outcome = ops_reader.list_ops(repo_root, tools=tools, page_size=OPS_PAGE_SIZE, fs=counting_ops_fs(opened))
        if outcome.status != 200:
            raise AssertionError(f"the listing answered {outcome.status}")
        return opened[0]

    measured = timed_cold_repeats(one, repeats=repeats, timer=timer)
    counts = f"{expected_files} discovered Op files, files opened per repeat {list(measured.opens)}"
    problems = timing_problems("the real Ops listing", measured.minimum, LISTING_BOUND_SECONDS, counts)
    problems += [
        f"repeat {index + 1} opened {count} files, fewer than the {expected_files} discovered: a cache was hit"
        for index, count in enumerate(measured.opens)
        if count < expected_files
    ]
    problems += ["the discovered Op file count is zero: a bound over nothing proves nothing"] if expected_files == 0 else []
    return problems, measured


@contextmanager
def memoising_listing() -> Iterator[None]:
    """The cache-the-result mutation: the Ops entry point answers every call after the first from a cache (plan-round ruling 9)."""
    original = ops_reader.list_ops
    cache: dict[Any, Any] = {}

    def memoised(repo_root: Path, **options: Any) -> Any:
        key = (repo_root, tuple(sorted((name, repr(value)) for name, value in options.items() if name != "fs")))
        if key not in cache:
            cache[key] = original(repo_root, **options)
        return cache[key]

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ops_reader, "list_ops", memoised)
        yield


# ---------------------------------------------------------------------------
# Read-only fingerprints of both corpus trees
# ---------------------------------------------------------------------------


def tree_problems(repo_root: Path, run: Callable[[], Any], trees: Sequence[str] = CORPUS_TREES) -> list[str]:
    """Run ``run`` between two fingerprints of each tree; a tree whose bytes, status or directory names moved is named."""
    before = {tree: tree_fingerprint(repo_root, tree) for tree in trees}
    run()
    after = {tree: tree_fingerprint(repo_root, tree) for tree in trees}
    return [f"{tree}/ changed while the reads ran (a reader wrote something)" for tree in trees if after[tree] != before[tree]]


# ---------------------------------------------------------------------------
# The corpus run: ONE execution of the Project build, the project-wide scan and the per-Mission reads (D-P5, NFR-001)
# ---------------------------------------------------------------------------


@dataclass
class CorpusRun:
    """What the shared resolver run produced and how long each part took (the three timing cases assert on these same durations)."""

    memo: memo_module.ResolverMemo
    project: project_builder.ProjectOutcome
    scan: drift.DriftOutcome
    per_mission: dict[str, drift.DriftOutcome]
    oracle: oracles.DriftOracle
    seconds_project: float
    seconds_scan: float
    seconds_per_mission: float
    tree_problems: list[str]
    index_problems: list[str]

    @property
    def seconds_combined(self) -> float:
        return self.seconds_project + self.seconds_scan + self.seconds_per_mission


def _per_mission_reads(memo: memo_module.ResolverMemo, names: Sequence[str]) -> dict[str, drift.DriftOutcome]:
    clock = FrozenClock(instant=NOW)
    return {name: drift.scan_drift(REPO_ROOT, memo, clock=clock, mission_id=oracles.mission_id_of(oracles.raw_meta(REPO_ROOT, name))) for name in names}


@pytest.fixture
def corpus_run(remote_state: oracles.RemoteState, tools: helper.ContractTools) -> CorpusRun:
    """The one shared resolver run. A function-scoped fixture on purpose: the case ledger (an autouse fixture of the same scope) decides the named
    offline skip first, which a module-scoped fixture would pre-empt; the run itself is executed once and cached."""
    if not remote_state.online:
        pytest.skip(OFFLINE_SKIP)
    return execute_corpus_run(tools)


@contextmanager
def production_index() -> Iterator[None]:
    """Restore the production ``_build_index`` (a fresh walk per call) for the duration of a timed block."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mission_resolver, "_build_index", PRODUCTION_BUILD_INDEX)
        yield


def production_index_problems() -> list[str]:
    """One line when the resolver's index walk is not the production one (a timed bound measured on a patched path proves nothing)."""
    if mission_resolver._build_index is PRODUCTION_BUILD_INDEX:
        return []
    return ["the timed block ran with a patched resolver index walk, not the production one"]


@functools.cache
def execute_corpus_run(tools: helper.ContractTools) -> CorpusRun:
    """Build the ``Project`` once and run the memoised drift scan and the per-Mission reads once, recording each duration."""
    _reset_remote_branch_lookup_cache()  # the timed run is cold: no remote probe answered earlier in this process is reused
    memo = memo_module.ResolverMemo()
    holder: dict[str, Any] = {}

    def run() -> None:
        holder["index_problems"] = production_index_problems()
        started = time.perf_counter()
        holder["project"] = project_builder.build_project(REPO_ROOT, memo, leak=tools.leak)
        holder["seconds_project"] = time.perf_counter() - started
        started = time.perf_counter()
        holder["scan"] = drift.scan_drift(REPO_ROOT, memo, clock=FrozenClock(instant=NOW))
        holder["seconds_scan"] = time.perf_counter() - started
        started = time.perf_counter()
        holder["per_mission"] = _per_mission_reads(memo, oracles.mission_names(REPO_ROOT))
        holder["seconds_per_mission"] = time.perf_counter() - started

    with production_index():
        problems = tree_problems(REPO_ROOT, run)
    expected = oracles.drift_oracle(REPO_ROOT, memo, NOW)
    return CorpusRun(
        memo,
        holder["project"],
        holder["scan"],
        holder["per_mission"],
        expected,
        holder["seconds_project"],
        holder["seconds_scan"],
        holder["seconds_per_mission"],
        problems,
        holder["index_problems"],
    )


def load_health_drift_ops_fixture() -> dict[str, Any]:
    return json.loads((REPO_ROOT / "tests" / "contract" / "fixtures" / ANOMALY_FILE).read_text(encoding="utf-8"))


def named_list_problems(label: str, derived: Iterable[str], observed: Iterable[str], pinned: Iterable[str]) -> list[str]:
    """A named list of the corpus, both ways: the reader's list equals the independent derivation (a stale or missing entry is named), and
    every pinned name is still on it. A name the derivation has that nobody pinned is only a new anomaly, never a failure here."""
    problems = difference_problems(f"{label} (reader against the independent derivation)", observed, derived)
    problems += [f"{label}: the pinned name {name!r} is no longer on the independently derived list" for name in sorted(set(pinned) - set(derived))]
    return problems


def _discovered_line(run: CorpusRun) -> str:
    return f"{len(run.oracle.names)} Missions discovered, {len(run.per_mission)} read one by one"


def test_corpus_drift_scan_is_a_200_and_the_resolver_ran_once_per_mission(corpus_run: CorpusRun) -> None:
    """With the remotes reachable the project-wide scan is a 200 and no resolver outcome but the named fallback occurs (AC-REALITY 1)."""
    run = corpus_run
    assert run.scan.status == 200, f"the project-wide drift read answered {run.scan.status} {run.scan.body.get('code')} ({_discovered_line(run)})"
    assert run.scan.body["truncated"] is False, "the report was truncated at its cap"
    outcomes = [type(entry.outcome).__name__ for entry in run.memo.entries() if isinstance(entry.outcome, Exception)]
    unexpected = sorted({name for name in outcomes if name != "CoordinationBranchDeleted"})
    assert unexpected == [], f"a resolver outcome other than the named fallback occurred: {unexpected}"
    names = run.oracle.names
    assert names, "no Mission was discovered"
    assert run.memo.runs == len(names) == len(run.memo.entries()), f"the resolver ran {run.memo.runs} times for {len(names)} Missions"
    assert all(run.memo.lookup((REPO_ROOT.resolve(), name)) is not None for name in names), "a Mission has no memo entry"
    assert run.oracle.resolver_errors == {}, f"a resolver exception outside the named fallback: {run.oracle.resolver_errors}"


def raised_the_named_fallback(run: CorpusRun) -> set[str]:
    """The Missions whose memo entry holds ``CoordinationBranchDeleted``."""
    found = set()
    for name in run.oracle.names:
        entry = run.memo.lookup((REPO_ROOT.resolve(), name))
        assert entry is not None, f"{name}: the resolver has no memo entry"
        if isinstance(entry.outcome, CoordinationBranchDeleted):
            found.add(name)
    return found


def test_corpus_fallback_list_equals_the_independent_derivation(corpus_run: CorpusRun) -> None:
    """The fallback Missions equal the independent derivation both ways, and each one raised ``CoordinationBranchDeleted`` through the memo."""
    run = corpus_run
    problems = difference_problems("scan fallbacks", run.scan.fallbacks, run.oracle.fallbacks)
    problems += difference_problems("scan fallback reasons", run.scan.fallbacks.items(), run.oracle.fallbacks.items())
    problems += difference_problems("Missions that raised CoordinationBranchDeleted", raised_the_named_fallback(run), run.oracle.fallbacks)
    if run.oracle.remote_present:
        problems.append(f"derived but present as remote-tracking ref (the resolver judges these present): {run.oracle.remote_present}")
    print(f"drift coordination fallbacks (environment-dependent, never floored): {len(run.scan.fallbacks)} {sorted(run.scan.fallbacks)}")
    assert not problems, "; ".join(problems)
    assert all(reason == FALLBACK_REASON for reason in run.scan.fallbacks.values())


def test_corpus_missions_examined_plus_skipped_equals_discovered(corpus_run: CorpusRun) -> None:
    """Examined plus named skipped equals discovered for Missions, with the legacy manifests on a named list and no stale entry."""
    run = corpus_run
    discovered, examined = len(run.oracle.names), run.project.body["missionCount"]
    skipped_for_kind_three = run.oracle.kind3.legacy
    counts = f"{examined} examined and {len(skipped_for_kind_three)} skipped of {discovered} discovered"
    assert discovered > 0, counts
    assert examined == discovered, counts
    assert len(run.per_mission) == discovered, counts
    pinned = [item["mission"] for item in load_health_drift_ops_fixture()["legacy_lane_manifests"]]
    problems = named_list_problems("legacy lane manifests", run.oracle.kind3.legacy, run.scan.legacy_manifests, pinned)
    assert not problems, f"{counts}: {'; '.join(problems)}"
    assert len(skipped_for_kind_three) <= run.oracle.kind3.population, counts
    floors = new_floor_problems({"missions_examined": examined}, only=("missions_examined",))
    assert not floors, f"{counts}: {'; '.join(floors)}"


def test_corpus_kinds_one_and_two_equal_the_oracle_and_meet_their_floors(corpus_run: CorpusRun) -> None:
    run = corpus_run
    wanted = {key for key in expect_finding_keys(run.oracle) if key[1] in {KIND_ONE, KIND_TWO}}
    got = {key for key in reader_finding_keys(run.scan.body["findings"]) if key[1] in {KIND_ONE, KIND_TWO}}
    problems = difference_problems("kinds 1 and 2", got, wanted)
    problems += duplicate_problems("kinds 1 and 2", [item for item in run.scan.body["findings"] if item["kind"] in {KIND_ONE, KIND_TWO}])
    assert not problems, "; ".join(problems)
    counts = {"kind1_findings": sum(1 for key in got if key[1] == KIND_ONE), "kind2_findings": sum(1 for key in got if key[1] == KIND_TWO)}
    floors = new_floor_problems(counts, only=counts)
    assert not floors, f"{counts}: {'; '.join(floors)}"


def test_corpus_kind_three_equals_the_oracle(corpus_run: CorpusRun) -> None:
    """Kind 3 is clone-dependent: no count is pinned, and the corpus is asserted equal to the oracle."""
    run = corpus_run
    wanted = {key for key in expect_finding_keys(run.oracle) if key[1] == KIND_THREE}
    got = {key for key in reader_finding_keys(run.scan.body["findings"]) if key[1] == KIND_THREE}
    problems = difference_problems("kind 3", got, wanted)
    problems += duplicate_problems("kind 3", [item for item in run.scan.body["findings"] if item["kind"] == KIND_THREE])
    assert not problems, "; ".join(problems)
    assert run.oracle.kind3.population > 0, "no Mission is both not completed and holding a lane manifest: the comparison would prove nothing"


def test_corpus_project_report_equals_the_oracles(corpus_run: CorpusRun) -> None:
    """The ``Project`` counts and fallbacks against the oracles, and the branch against an independent read of ``HEAD``."""
    run = corpus_run
    body = run.project.body
    assert body["missionCount"] == len(run.oracle.names) > 0
    problems = difference_problems("project fallbacks", run.project.fallbacks, run.oracle.fallbacks)
    assert not problems, "; ".join(problems)
    assert all(reason == "CoordinationBranchDeleted" for reason in run.project.fallbacks.values())
    assert body["currentBranch"] == oracles.current_branch(REPO_ROOT)


def test_corpus_per_mission_reports_equal_the_filtered_findings(corpus_run: CorpusRun) -> None:
    run = corpus_run
    findings = run.scan.body["findings"]
    problems = []
    for name, outcome in sorted(run.per_mission.items()):
        mission_id = oracles.mission_id_of(oracles.raw_meta(REPO_ROOT, name))
        if outcome.status != 200:
            problems.append(f"{name}: the per-Mission read answered {outcome.status}")
        elif outcome.body["findings"] != [item for item in findings if item["missionId"] == mission_id]:
            problems.append(f"{name}: the per-Mission findings differ from the project-wide findings filtered to it")
    assert not problems, f"{_discovered_line(run)}: {'; '.join(problems[:5])}"
    assert sum(len(outcome.body["findings"]) for outcome in run.per_mission.values()) == len(findings) > 0


def payload_problems(contract: helper.Contract, tools: helper.ContractTools, title: str, payload: Any) -> list[str]:
    """Schema errors and leaks of one payload (the checks every corpus payload goes through)."""
    return [f"{title}: {line}" for line in contract.errors(title, payload)] + [f"{title}: leak {line}" for line in helper.payload_leaks(payload, tools)]


def test_corpus_payloads_validate_and_leak_clean(corpus_run: CorpusRun, tools: helper.ContractTools, contract: helper.Contract) -> None:
    run = corpus_run
    before = helper.LEDGER.snapshot()
    problems = payload_problems(contract, tools, helper.SCHEMA_PROJECT, run.project.body)
    problems += payload_problems(contract, tools, helper.SCHEMA_DRIFT_REPORT, run.scan.body)
    problems += payload_wiring_problems(before, helper.LEDGER.snapshot(), 2)
    assert not problems, "; ".join(problems[:5])


def test_corpus_project_build_is_within_its_bound(corpus_run: CorpusRun) -> None:
    run = corpus_run
    problems = run.index_problems + timing_problems("one Project build", run.seconds_project, BOUND_SECONDS, _discovered_line(run))
    assert not problems and run.project.body["missionCount"] >= FLOORS.missions_examined, "; ".join(problems)


def test_corpus_scan_is_within_its_bound(corpus_run: CorpusRun) -> None:
    """``seconds_scan`` is the warm reduction only; the combined case carries the resolver-inclusive bound (Project plus scan plus per-Mission)."""
    run = corpus_run
    problems = run.index_problems + timing_problems("one project-wide scan", run.seconds_scan, BOUND_SECONDS, _discovered_line(run))
    assert not problems and len(run.oracle.names) >= FLOORS.missions_examined, "; ".join(problems)


def test_corpus_combined_run_is_within_its_bound(corpus_run: CorpusRun) -> None:
    """The memoised pass, the Project build and the per-Mission reductions together, from the same execution as the two bounds above."""
    run = corpus_run
    detail = f"project {run.seconds_project:.1f} s, scan {run.seconds_scan:.1f} s, per-Mission {run.seconds_per_mission:.1f} s; {_discovered_line(run)}"
    problems = run.index_problems + timing_problems("the combined run", run.seconds_combined, BOUND_SECONDS, detail)
    print(f"combined run: {detail}")
    assert not problems and len(run.per_mission) >= FLOORS.missions_examined, "; ".join(problems)


def test_the_timed_block_runs_the_production_index_walk_and_a_patched_one_is_refused() -> None:
    """The module-wide identity-index patch is active here, so the guard must see it; inside ``production_index`` it must not."""
    assert mission_resolver._build_index is not PRODUCTION_BUILD_INDEX, "the autouse patch is not active: the plant proves nothing"
    assert production_index_problems(), "a timed run under the patched index walk was not refused"
    with production_index():
        assert mission_resolver._build_index is PRODUCTION_BUILD_INDEX
        assert production_index_problems() == []
    assert production_index_problems(), "the production walk was not re-patched after the timed block"


def test_corpus_trees_are_unchanged_by_the_resolver_run(corpus_run: CorpusRun) -> None:
    assert corpus_run.tree_problems == []


def test_corpus_offline_scan_is_a_200_with_no_fallback_entry() -> None:
    """With a remote unreachable the scan is still a 200 read from each Mission's own directory, and names no fallback (operator ruling at WP07)."""
    outcome = drift.scan_drift(REPO_ROOT, memo_module.ResolverMemo(), clock=FrozenClock(instant=NOW))
    assert outcome.status == 200, f"offline the project-wide read answered {outcome.status} {outcome.body.get('code')}"
    assert outcome.fallbacks == {}, f"offline the scan named fallbacks: {sorted(outcome.fallbacks)[:3]}"


# ---------------------------------------------------------------------------
# The Ops cases: no resolver, no network
# ---------------------------------------------------------------------------


@dataclass
class OpsWalk:
    """The Ops listing walked page by page."""

    items: list[dict[str, Any]]
    pages: int
    total: int
    skipped_count: int
    skipped_ids: tuple[str, ...]
    skip_reasons: Mapping[str, str]
    problems: list[str]


def walk_ops(repo_root: Path, contract: helper.Contract, tools: helper.ContractTools, page_size: int = OPS_PAGE_SIZE) -> OpsWalk:
    """Walk ``GET /ops/invocations`` to its last page, validating every page against the contract; the problems name each fault."""
    items: list[dict[str, Any]] = []
    problems: list[str] = []
    cursor: str | None = None
    pages = 0
    before = helper.LEDGER.snapshot()
    outcome: ops_reader.OpsOutcome | None = None
    while True:
        outcome = ops_reader.list_ops(repo_root, tools=tools, page_size=page_size, cursor=cursor)
        pages += 1
        if outcome.status != 200:
            problems.append(f"page {pages} answered {outcome.status}")
            break
        problems += [f"page {pages}: {line}" for line in payload_problems(contract, tools, helper.SCHEMA_OPS_PAGE, outcome.body)]
        items += outcome.body["items"]
        info = outcome.body["pageInfo"]
        if bool(info["hasNextPage"]) != (info["nextPageCursor"] is not None):
            problems.append(f"page {pages}: hasNextPage and nextPageCursor disagree")
        if not info["hasNextPage"]:
            break
        cursor = info["nextPageCursor"]
    assert outcome is not None
    problems += payload_wiring_problems(before, helper.LEDGER.snapshot(), pages)
    return OpsWalk(items, pages, outcome.body.get("totalCount", 0), outcome.body.get("skippedCount", 0), outcome.skipped_ids, outcome.skip_reasons, problems)


def ops_walk_problems(walk: OpsWalk, scan: oracles.OpsScan, discovered: int) -> list[str]:
    """The Ops walk against the oracle's direct scan: identity, order, every field, the counts, and examined plus skipped equals discovered."""
    problems = list(walk.problems)
    ids = [item["invocationId"] for item in walk.items]
    if len(ids) != len(set(ids)):
        problems.append("an Op was served twice across the pages")
    problems += difference_problems("served Ops", ids, scan.served)
    expected = expect_op_views(scan)
    problems += [
        f"{item['invocationId']}: the reader says {reader_op_view(item)}, the oracle says {expected[item['invocationId']]}"
        for item in walk.items
        if item["invocationId"] in expected and reader_op_view(item) != expected[item["invocationId"]]
    ][:5]
    order = [(parse_iso(item["startedAt"]), item["invocationId"]) for item in walk.items]
    if order != sorted(order, reverse=True):
        problems.append("the Ops are not newest first")
    served, skipped = len(scan.served), len(scan.skipped)
    if walk.total != served or walk.skipped_count != skipped:
        problems.append(f"totalCount {walk.total} and skippedCount {walk.skipped_count}, the oracle serves {served} and skips {skipped}")
    if discovered == 0 or served + skipped != discovered or walk.total + walk.skipped_count != discovered:
        problems.append(f"{walk.total} served and {walk.skipped_count} skipped of {discovered} discovered Op files")
    return problems


@pytest.fixture(scope="module")
def ops_walk(contract: helper.Contract, tools: helper.ContractTools) -> tuple[OpsWalk, list[str]]:
    """The real Ops walk, taken once between two fingerprints of both corpus trees."""
    holder: dict[str, OpsWalk] = {}
    problems = tree_problems(REPO_ROOT, lambda: holder.update(walk=walk_ops(REPO_ROOT, contract, tools)))
    return holder["walk"], problems


def test_corpus_ops_walk_equals_the_oracle_and_leaves_the_trees_as_found(ops_walk: tuple[OpsWalk, list[str]]) -> None:
    walk, tree = ops_walk
    assert tree == []
    problems = ops_walk_problems(walk, oracles.scan_ops(REPO_ROOT), expect_discovered_ops(REPO_ROOT))
    assert not problems, "; ".join(problems[:5])
    assert walk.pages >= 1 and len(walk.items) > 0


def test_corpus_ops_skipped_count_and_named_list_equal_the_oracle(ops_walk: tuple[OpsWalk, list[str]]) -> None:
    """``skippedCount`` equals the oracle's skipped list, which is the named legacy-completion list, with no stale entry."""
    walk, _ = ops_walk
    scan = oracles.scan_ops(REPO_ROOT)
    assert walk.skipped_count == len(scan.skipped) == len(walk.skipped_ids)
    assert set(scan.skipped.values()) <= {oracles.SKIP_LEGACY_COMPLETION}, (
        f"an Op is skipped for a reason that is not the named one: {sorted(set(scan.skipped.values()))}"
    )
    pinned = load_health_drift_ops_fixture()["legacy_completion_ops"]
    problems = named_list_problems("Ops with a legacy completion line", scan.legacy_completions(), walk.skipped_ids, pinned)
    assert not problems, "; ".join(problems)
    assert set(walk.skip_reasons.values()) == {ops_reader.SKIP_LEGACY_COMPLETION}, "the reader skips an Op for a reason outside the named list"


def ops_floor_counts(scan: oracles.OpsScan) -> dict[str, int]:
    """The measured counts of the Ops floors, from the oracle's own-file completions."""
    own = [op for op in scan.served.values() if op.own_file_completion]
    by_category = {
        name: sum(1 for op in own if op.evidence_category == name)
        for name in (oracles.CATEGORY_NONE, oracles.CATEGORY_ABSOLUTE, oracles.CATEGORY_FREE_TEXT, oracles.CATEGORY_RELATIVE, oracles.CATEGORY_URL)
    }
    return {
        "ops_served": len(scan.served),
        "spine_closed_ops": sum(1 for op in scan.served.values() if op.spine_closed),
        "evidence_none": by_category[oracles.CATEGORY_NONE],
        "evidence_absolute_path": by_category[oracles.CATEGORY_ABSOLUTE],
        "evidence_free_text": by_category[oracles.CATEGORY_FREE_TEXT],
        "evidence_relative_reference": by_category[oracles.CATEGORY_RELATIVE],
        "evidence_url": by_category[oracles.CATEGORY_URL],
    }


def test_corpus_ops_floors_and_evidence_kinds_equal_the_oracle(ops_walk: tuple[OpsWalk, list[str]]) -> None:
    walk, _ = ops_walk
    scan = oracles.scan_ops(REPO_ROOT)
    counts = ops_floor_counts(scan)
    served_classes = Counter(served_category(item["evidence"]) for item in walk.items if item["status"] == "closed")
    assert sum(served_classes.values()) == sum(1 for op in scan.served.values() if op.status == "closed")
    floors = new_floor_problems(counts, only=counts)
    assert not floors, f"{counts}: {'; '.join(floors)}"
    spine_named = load_health_drift_ops_fixture()["spine_closed_ops"]
    on_spine = sorted(op.invocation_id for op in scan.served.values() if op.spine_closed)
    assert not named_list_problems("Ops closed by the spine", on_spine, on_spine, spine_named)
    assert counts["ops_served"] == walk.total


# ---------------------------------------------------------------------------
# AC-DRIFT 19, corpus half: completion reads the own directory
# ---------------------------------------------------------------------------


def reader_completion(repo_root: Path, name: str, now: Any = NOW) -> bool:
    """The reader's completion test for a Mission whose read directory is its own directory."""
    own = repo_root / KITTY_SPECS / name
    ctx = drift.ScanContext(repo_root, memo_module.ResolverMemo(), now, drift.REAL_FS, drift.list_local_branches)
    return drift.completion_of(ctx, own, drift.read_meta(own))


def completion_equality_problems(repo_root: Path, *, floor: int, completion: Callable[[Path, str], bool] = reader_completion) -> tuple[list[str], int]:
    """The reader's completion against ``is_mission_completed`` for every Mission declaring no coordination branch, with the discovered-count guard."""
    pairs = oracles.completion_pairs(repo_root, oracles.mission_names(repo_root), NOW)
    independent = expect_non_coordination_count(repo_root)
    compared = len(pairs)
    problems = [
        f"{name}: the reader says {completion(repo_root, name)}, is_mission_completed says {expected}"
        for name, expected in sorted(pairs.items())
        if completion(repo_root, name) != expected
    ]
    counts = f"{compared} compared of {independent} Missions declaring no coordination branch (floor {floor})"
    if compared == 0:
        problems.append(f"no Mission was compared: a count of zero proves nothing ({counts})")
    if compared != independent:
        problems.append(f"the compared count differs from the independent meta.json scan ({counts})")
    if compared < floor:
        problems.append(f"fewer Missions compared than the floor ({counts})")
    return problems, compared


def test_corpus_completion_equals_is_mission_completed() -> None:
    problems, compared = completion_equality_problems(REPO_ROOT, floor=FLOORS.completion_compared)
    assert not problems, "; ".join(problems[:5])
    assert compared >= FLOORS.completion_compared


# ---------------------------------------------------------------------------
# AC-CROSS 4, corpus half: the real kitty-ops/ listing
# ---------------------------------------------------------------------------


def test_corpus_ops_listing_is_within_five_seconds(tools: helper.ContractTools) -> None:
    problems, measured = listing_problems(REPO_ROOT, tools, expected_files=expect_discovered_ops(REPO_ROOT))
    print(
        f"real kitty-ops listing: minimum {measured.minimum:.4f} s of {len(measured.seconds)} cold repeats, margin {LISTING_BOUND_SECONDS / measured.minimum:.0f}x"
    )
    assert not problems, "; ".join(problems)


# ---------------------------------------------------------------------------
# The AST independence of the oracles (D-P14)
# ---------------------------------------------------------------------------


def reader_references(tree: ast.AST) -> list[str]:
    """Every import of, and every use of the alias of, a reader module in ``tree`` (a textual guard: a bypass is accepted at severity 1 to 2)."""
    found: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or "", *(f"{node.module}.{alias.name}" for alias in node.names)]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names = [node.value]
        found.update(name for name in names if any(reader in name for reader in READER_MODULES))
        # any importlib use (or __import__) can build a reader name by concatenation, so the use itself is the finding
        found.update(f"an import of {name}" for name in names if name.split(".")[0] == "importlib")
        if isinstance(node, ast.Name) and node.id in {"importlib", "__import__"}:
            found.add(f"the name {node.id}")
        if isinstance(node, ast.Name) and node.id in READER_ALIASES:
            found.add(f"the name {node.id}")
    return sorted(found)


def function_tree(function: Callable[..., Any]) -> ast.AST:
    return ast.parse(textwrap.dedent(inspect.getsource(function)))


def test_corpus_the_oracles_neither_call_nor_import_a_reader() -> None:
    """The oracle module and the oracle functions of this module never call or import a reader module."""
    oracle_source = ast.parse(ORACLES_FILE.read_text(encoding="utf-8"))
    assert reader_references(oracle_source) == []
    imported = {alias.name for node in ast.walk(oracle_source) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module or "" for node in ast.walk(oracle_source) if isinstance(node, ast.ImportFrom)}
    assert any(name.startswith("tests.contract") for name in imported), (
        "the oracle module imports nothing from tests/contract: the memo import is the one expected, so the guard saw no source"
    )
    for function in ORACLE_FUNCTIONS:
        assert reader_references(function_tree(function)) == [], function.__name__
    assert len(ORACLE_FUNCTIONS) == 4


def test_corpus_case_dispositions_follow_the_resolver_use() -> None:
    assert disposition_problems(Path(__file__).read_text(encoding="utf-8"), ALWAYS_CASES, RESOLVER_CASES, OFFLINE_ONLY_CASES) == []


# ---------------------------------------------------------------------------
# Controls on repositories built at run time: each plant beside its control, against the oracles and the readers
# ---------------------------------------------------------------------------

RETIRED_TERM = "fea" + "ture"
LANE_PATH = ("planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done")
LANE_ID = "lane-a"
SNAPSHOT_NAME = "status.json"
LOG_NAME = "status.events.jsonl"
DHO_NAMES = {
    1: "m-clean",
    2: "m-drift",
    3: "m-terminal",
    4: "m-provenance",
    5: "m-corrupt",
    6: "m-undecodable",
    7: "m-no-log",
    8: "m-no-snapshot",
    9: "m-branch-gap",
    10: "m-branch-ok",
    11: "m-planned",
    12: "m-merged",
    13: "m-legacy",
    14: "m-coord",
}


@pytest.fixture
def scratch_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Real git runs with a scratch HOME and no system or global configuration; the returned directory is the build area."""
    home = tmp_path / "scratch-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    area = tmp_path / "area"
    area.mkdir()
    return area


def _git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


def new_git_repo(area: Path, name: str) -> Path:
    """A fresh repository whose ``HEAD`` points at ``main`` (unborn until a commit)."""
    repo = area / name
    repo.mkdir()
    helper.git_init(repo)
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    return repo


def _stamp(minutes: int) -> str:
    return f"2026-09-01T10:{minutes % 60:02d}:00+00:00"


def lane_rows(plan: Mapping[str, str]) -> list[dict[str, Any]]:
    """The event rows that bring each work package of ``plan`` from genesis to its lane along the usual path."""
    rows: list[dict[str, Any]] = []
    number = 1
    for wp_id, lane in plan.items():
        previous = "genesis"
        for step in LANE_PATH[: LANE_PATH.index(lane) + 1]:
            rows.append(helper.transition_row(number, wp_id, previous, step, at=_stamp(number)))
            previous, number = step, number + 1
    return rows


def replay_text(mission_dir: Path) -> str:
    """The snapshot text the reducer gives for the Mission directory (what ``materialize`` would write)."""
    return str(materialize_to_json(materialize_snapshot(mission_dir)))


def edit_snapshot(mission_dir: Path, change: Callable[[dict[str, Any]], None]) -> None:
    document = json.loads((mission_dir / SNAPSHOT_NAME).read_text(encoding="utf-8"))
    change(document)
    (mission_dir / SNAPSHOT_NAME).write_text(json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def current_manifest(slug: str, number: int, lanes: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    return {
        "version": 1,
        "mission_slug": slug,
        "mission_id": helper.fixture_ulid(number),
        "mission_branch": f"kitty/mission-{slug}",
        "target_branch": "main",
        "lanes": [
            {"lane_id": lane_id, "wp_ids": list(wp_ids), "write_scope": [], "predicted_surfaces": [], "depends_on_lanes": [], "parallel_group": 0}
            for lane_id, wp_ids in lanes.items()
        ],
        "computed_at": "2026-09-01T10:00:00+00:00",
        "computed_from": "fixture",
    }


def dho_mission(
    repo: Path,
    number: int,
    plan: Mapping[str, str],
    *,
    snapshot: str | bytes | None = "replay",
    log: bool = True,
    meta: Mapping[str, Any] | None = None,
    lanes: Mapping[str, Any] | None = None,
) -> Path:
    """One fixture Mission; ``snapshot`` is ``"replay"`` (equal to the replay), text or bytes written as given, or None (no file)."""
    name = DHO_NAMES[number]
    mission_dir = helper.write_fixture_mission(repo, name, meta={"mission_id": helper.fixture_ulid(number), **(meta or {})}, rows=lane_rows(plan), lanes=lanes)
    if snapshot == "replay":
        (mission_dir / SNAPSHOT_NAME).write_text(replay_text(mission_dir), encoding="utf-8")
    elif isinstance(snapshot, bytes):
        (mission_dir / SNAPSHOT_NAME).write_bytes(snapshot)
    elif snapshot is not None:
        (mission_dir / SNAPSHOT_NAME).write_text(snapshot, encoding="utf-8")
    if not log:
        (mission_dir / LOG_NAME).unlink()
    return mission_dir


def _set_lane(wp_id: str, lane: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document["work_packages"][wp_id]["lane"] = lane

    return change


def _set_actor(document: dict[str, Any]) -> None:
    document["work_packages"]["WP01"]["actor"] = "someone-else"


def dho_repo(area: Path) -> Path:
    """Fourteen Missions: one clean control and one plant for each way the oracles answer (kinds 1 to 3, completion, legacy, fallback)."""
    repo = new_git_repo(area, "dho")
    in_progress, done = {"WP01": "in_progress"}, {"WP01": "done"}
    dho_mission(repo, 1, in_progress)
    edit_snapshot(dho_mission(repo, 2, {"WP01": "approved"}), _set_lane("WP01", "planned"))
    edit_snapshot(dho_mission(repo, 3, done), _set_lane("WP01", "approved"))
    edit_snapshot(dho_mission(repo, 4, in_progress), _set_actor)
    dho_mission(repo, 5, in_progress, snapshot="[]")
    dho_mission(repo, 6, in_progress, snapshot=bytes([0xFF, 0xFE, 0x00]))
    dho_mission(repo, 7, in_progress, log=False)
    dho_mission(repo, 8, in_progress, snapshot=None)
    slug_9, slug_10, slug_11, slug_12 = (DHO_NAMES[number] for number in (9, 10, 11, 12))
    dho_mission(repo, 9, in_progress, lanes=current_manifest(slug_9, 9, {LANE_ID: ["WP01"]}))
    dho_mission(repo, 10, in_progress, lanes=current_manifest(slug_10, 10, {LANE_ID: ["WP01"]}))
    dho_mission(repo, 11, {"WP01": "planned"}, lanes=current_manifest(slug_11, 11, {LANE_ID: ["WP01"]}))
    dho_mission(repo, 12, in_progress, meta={"merged_at": "2026-09-02T10:00:00+00:00"}, lanes=current_manifest(slug_12, 12, {LANE_ID: ["WP01"]}))
    dho_mission(repo, 13, in_progress, lanes={"version": 1, RETIRED_TERM + "_slug": DHO_NAMES[13], "mission_id": helper.fixture_ulid(13), "lanes": []})
    dho_mission(repo, 14, {"WP01": "planned"}, meta={"coordination_branch": "kitty/coord-gone"})
    helper.commit_all(repo)
    _git(repo, "branch", code_lane_branch_name(slug_10, LANE_ID))
    _git(repo, "branch", f"kitty/mission-{slug_10}")
    return repo


def dho_expected_keys() -> set[FindingKey]:
    """The findings of the planted repository, written out here from the facts of each plant (never taken from a read)."""

    def mission(number: int) -> str:
        return helper.fixture_ulid(number)

    return {
        (mission(2), KIND_ONE, SNAPSHOT_NAME, "SNAPSHOT_DRIFT"),
        (mission(3), KIND_ONE, SNAPSHOT_NAME, "SNAPSHOT_DRIFT_TERMINAL"),
        (mission(4), KIND_ONE, SNAPSHOT_NAME, "SNAPSHOT_DRIFT_PROVENANCE"),
        (mission(5), KIND_ONE, SNAPSHOT_NAME, "CORRUPT_JSON"),
        (mission(6), KIND_ONE, SNAPSHOT_NAME, "CORRUPT_JSON"),
        (mission(7), KIND_TWO, LOG_NAME, None),
        (mission(8), KIND_TWO, SNAPSHOT_NAME, None),
        (mission(9), KIND_THREE, "lanes.json", None),
    }


def drift_agreement_problems(repo: Path) -> list[str]:
    """The reader's project-wide drift read of ``repo`` against the independent oracles, in every channel (findings, fallbacks, named list)."""
    memo = memo_module.ResolverMemo()
    outcome = drift.scan_drift(repo, memo, clock=FrozenClock(instant=NOW))
    if outcome.status != 200:
        return [f"the scan answered {outcome.status} {outcome.body.get('code')}"]
    expected = oracles.drift_oracle(repo, memo, NOW)
    problems = difference_problems("findings", reader_finding_keys(outcome.body["findings"]), expect_finding_keys(expected))
    problems += duplicate_problems("findings", outcome.body["findings"])
    problems += difference_problems("fallbacks", outcome.fallbacks.items(), expected.fallbacks.items())
    problems += difference_problems("legacy manifests", outcome.legacy_manifests, expected.kind3.legacy)
    return problems


def test_a_finding_served_twice_is_a_problem_that_a_set_comparison_does_not_see() -> None:
    finding = {"missionId": "m", "kind": KIND_THREE, "artifactPath": "lanes.json", "sourceCode": None}
    assert difference_problems("x", reader_finding_keys([finding, dict(finding)]), reader_finding_keys([finding])) == []
    assert duplicate_problems("x", [finding, dict(finding)]) == ["x: the reader served 2 findings for 1 distinct keys"]
    assert duplicate_problems("x", [finding]) == []


def test_the_kind_one_wrapper_turns_an_undecodable_snapshot_into_corrupt_json(tmp_path: Path) -> None:
    """The oracle wrapper over the classifier: an undecodable snapshot is ``CORRUPT_JSON`` as in the reader; an unreadable one is dropped (a 500 there)."""
    undecodable, unreadable, clean = tmp_path / "undecodable", tmp_path / "unreadable", tmp_path / "clean"
    for directory in (undecodable, unreadable, clean):
        helper.write_fixture_mission(tmp_path, directory.name, rows=lane_rows({"WP01": "in_progress"}))
    (tmp_path / "kitty-specs" / "undecodable" / SNAPSHOT_NAME).write_bytes(bytes([0xFF, 0xFE]))
    (tmp_path / "kitty-specs" / "unreadable" / SNAPSHOT_NAME).mkdir()
    clean_dir = tmp_path / "kitty-specs" / "clean"
    (clean_dir / SNAPSHOT_NAME).write_text(replay_text(clean_dir), encoding="utf-8")
    assert oracles.snapshot_codes(tmp_path / "kitty-specs" / "undecodable") == ["CORRUPT_JSON"]
    assert oracles.snapshot_codes(tmp_path / "kitty-specs" / "unreadable") == []
    assert oracles.snapshot_codes(clean_dir) == []


def test_the_oracles_state_the_planted_drift_findings_directly(scratch_git: Path) -> None:
    """The oracles over the planted repository equal the findings written out from the plants, and name the fallback and the legacy manifest."""
    repo = dho_repo(scratch_git)
    expected = oracles.drift_oracle(repo, memo_module.ResolverMemo(), NOW)
    assert expect_finding_keys(expected) == dho_expected_keys()
    assert expected.fallbacks == {DHO_NAMES[14]: FALLBACK_REASON}
    assert expected.kind3.legacy == (DHO_NAMES[13],)
    assert expected.names == sorted(DHO_NAMES.values())
    assert expected.resolver_errors == {} and expected.remote_present == []
    assert expected.kind3.completed == 2 and expected.kind3.population == 4


def test_the_reader_equals_the_oracles_on_the_planted_repository(scratch_git: Path) -> None:
    assert drift_agreement_problems(dho_repo(scratch_git)) == []


def _mutant_kind_two_names_the_present_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        drift, "kind2", lambda has_log: drift.raw_finding(drift.KIND_MISSING, drift.EVENT_LOG_FILE if has_log else drift.SNAPSHOT_FILE, None, [], None)
    )


def _mutant_planned_only_lane_is_expected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drift, "expected_lane_ids", lambda manifest, lanes_by_wp: [lane.lane_id for lane in manifest.lanes if lane.lane_id != "lane-planning"])


def _mutant_merge_marker_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drift, "merged_at_of", lambda meta: None)


def _mutant_terminal_read_as_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drift, "classify_variant", lambda computed, persisted: drift.CODE_DRIFT)


def _mutant_legacy_manifest_read_as_current(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drift, "is_legacy_manifest", lambda data: False)


def _mutant_fallback_reason_renamed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drift, "FALLBACK_REASON", "gone")


DRIFT_MUTANTS: dict[str, Callable[[pytest.MonkeyPatch], None]] = {
    "kind 2 names the present file": _mutant_kind_two_names_the_present_file,
    "a planned-only lane is expected": _mutant_planned_only_lane_is_expected,
    "the merge marker is ignored": _mutant_merge_marker_ignored,
    "a terminal difference is read as an error": _mutant_terminal_read_as_error,
    "a legacy manifest is read as a current one": _mutant_legacy_manifest_read_as_current,
    "the fallback reason is renamed": _mutant_fallback_reason_renamed,
}


@pytest.mark.parametrize("name", sorted(DRIFT_MUTANTS))
def test_a_consistently_wrong_drift_reader_is_killed_by_the_oracle(name: str, scratch_git: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = dho_repo(scratch_git)
    assert drift_agreement_problems(repo) == [], "the control: the unmutated reader agrees"
    DRIFT_MUTANTS[name](monkeypatch)
    assert drift_agreement_problems(repo), f"the mutation was not killed: {name}"


def coordination_repo(
    area: Path,
    label: str,
    remote: str | None,
    *,
    branch_kind: str = "absent",
    meta: Mapping[str, Any] | None = None,
    extra_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[Path, str]:
    """A repository whose Mission declares ``kitty/coord-gone``, held as ``branch_kind`` says (``origin`` is ``remote``)."""
    repo = new_git_repo(area, label)
    mission_dir = dho_mission(repo, 14, {"WP01": "planned"}, meta={"coordination_branch": "kitty/coord-gone", **(meta or {})})
    if extra_rows:
        with (mission_dir / LOG_NAME).open("a", encoding="utf-8") as log:
            log.writelines(json.dumps(row, sort_keys=True) + "\n" for row in extra_rows)
    helper.commit_all(repo)
    if branch_kind == "local-head":
        _git(repo, "branch", "kitty/coord-gone")
    if remote is not None:
        _git(repo, "remote", "add", "origin", remote)
    if branch_kind in {"remote-tracking", "remote-only"}:
        _git(repo, "branch", "kitty/coord-gone")
        _git(repo, "push", "-q", "origin", "kitty/coord-gone")
        _git(repo, "branch", "-D", "kitty/coord-gone")
    if branch_kind == "remote-only":
        _git(repo, "update-ref", "-d", "refs/remotes/origin/kitty/coord-gone")
    return repo, DHO_NAMES[14]


def test_the_fallback_derivation_agrees_with_the_resolver_and_each_arm_it_does_not_mirror_is_pinned(scratch_git: Path) -> None:
    """The derivation beside the resolver for each arm: agreement on absent and on a local head, and the four arms the derivation does not mirror (FRESH3-002)."""
    bare = scratch_git / "bare.git"
    bare.mkdir()
    _git(bare, "init", "--bare", "-q")
    merged, reopened = (
        {"merged_at": "2026-09-02T10:00:00+00:00"},
        helper.lifecycle_row(1, "MissionReopened", "2026-09-03T10:00:00+00:00", aggregate_id=DHO_NAMES[14]),
    )
    arms = {
        "absent": coordination_repo(scratch_git, "absent", None),
        "local-head": coordination_repo(scratch_git, "local-head", None, branch_kind="local-head"),
        "remote-tracking": coordination_repo(scratch_git, "tracking", str(bare), branch_kind="remote-tracking"),
        "remote-only": coordination_repo(scratch_git, "remote-only", str(bare), branch_kind="remote-only"),
        "stored topology without coordination": coordination_repo(scratch_git, "topology", None, meta={"topology": "lanes"}),
        "merged and reopened": coordination_repo(scratch_git, "reopened", None, meta=merged, extra_rows=[reopened]),
    }
    # arm: (the resolver raises the named fallback, the derivation lists the Mission, the Mission is also a remote-tracking ref)
    wanted = {
        "absent": (True, True, False),
        "local-head": (False, False, False),
        "remote-tracking": (False, True, True),
        "remote-only": (False, True, False),
        "stored topology without coordination": (False, True, False),
        "merged and reopened": (True, False, False),
    }
    for arm, (repo, name) in arms.items():
        _reset_remote_branch_lookup_cache()
        memo = memo_module.ResolverMemo()
        outcome = drift.scan_drift(repo, memo, clock=FrozenClock(instant=NOW))
        expected = oracles.drift_oracle(repo, memo, NOW)
        got = (name in outcome.fallbacks, name in expected.fallbacks, expected.remote_present == [name])
        assert outcome.status == 200 and got == wanted[arm], f"{arm}: (resolver raises, derivation lists, remote-tracking) is {got}, pinned {wanted[arm]}"
    _reset_remote_branch_lookup_cache()


def test_the_probe_sees_an_unreachable_remote_and_the_offline_outcome_is_pinned_on_it(scratch_git: Path) -> None:
    """An unreachable remote is offline (a 200, no fallback entry); a reachable one that lacks the branch is online (the fallback); no remote is online."""
    bare = scratch_git / "bare.git"
    bare.mkdir()
    _git(bare, "init", "--bare", "-q")
    unreachable, name = coordination_repo(scratch_git, "unreachable", str(scratch_git / "no-such-remote"))
    reachable, _ = coordination_repo(scratch_git, "reachable", str(bare))
    local, _ = coordination_repo(scratch_git, "local", None)
    offline_state, online_state, none_state = (oracles.probe_remotes(repo, timeout=10.0) for repo in (unreachable, reachable, local))
    assert (offline_state.online, offline_state.unreachable) == (False, ("origin",))
    assert (online_state.online, online_state.remotes) == (True, ("origin",))
    assert (none_state.online, none_state.remotes) == (True, ())
    for repo, state in ((unreachable, offline_state), (reachable, online_state), (local, none_state)):
        _reset_remote_branch_lookup_cache()
        outcome = drift.scan_drift(repo, memo_module.ResolverMemo(), clock=FrozenClock(instant=NOW))
        assert outcome.status == 200
        assert outcome.fallbacks == ({} if not state.online else {name: FALLBACK_REASON}), repo.name
    _reset_remote_branch_lookup_cache()


# ---------------------------------------------------------------------------
# Ops controls: a fixture repository with one Op of each shape
# ---------------------------------------------------------------------------

OP_STARTED = "2026-10-01T10:{minute:02d}:00+00:00"
OP_CLOSED = "2026-10-01T11:{minute:02d}:00+00:00"
OPS_EVIDENCE_PATH = SLASH + "srv" + SLASH + "data" + SLASH + "out.txt"
OPS_EVIDENCE_URL = "https" + "://example.invalid/page"
OPS_EVIDENCE_RELATIVE = "docs/plan.md"
OPS_EVIDENCE_TEXT = "reviewed the plan and found it sound"


def op_started(number: int) -> dict[str, Any]:
    return {
        "event": "started",
        "invocation_id": helper.fixture_ulid(number),
        "profile_id": "python-pedro",
        "action": "implement",
        "request_text": "request text of the operator",
        "actor": "claude",
        "mode_of_work": "task_execution",
        "governance_context_hash": "0123456789abcdef",
        "governance_context_available": True,
        "router_confidence": "exact",
        "started_at": OP_STARTED.format(minute=number),
    }


def op_completed(number: int, **fields: Any) -> dict[str, Any]:
    return {
        "event": "completed",
        "invocation_id": helper.fixture_ulid(number),
        "completed_at": OP_CLOSED.format(minute=number),
        "outcome": "done",
        "closed_by": "agent",
        **fields,
    }


def _write_lines(path: Path, lines: Sequence[Any]) -> None:
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


def ops_repo(area: Path) -> Path:
    """Ten Ops: open, closed with each class of evidence, spine-closed, a legacy completion with and without a spine record, and an empty file."""
    repo = area / "ops"
    directory = repo / OPS_TREE
    directory.mkdir(parents=True)
    legacy = {"event": "completed", "invocation_id": helper.fixture_ulid(8), "completed_at": OP_CLOSED.format(minute=8), "outcome": "done"}
    shapes: dict[int, list[Any]] = {
        1: [op_started(1)],
        2: [op_started(2), op_completed(2)],
        3: [op_started(3), op_completed(3, evidence_ref=OPS_EVIDENCE_PATH)],
        4: [op_started(4), op_completed(4, evidence_ref=OPS_EVIDENCE_URL)],
        5: [op_started(5), op_completed(5, evidence_ref=OPS_EVIDENCE_RELATIVE)],
        6: [op_started(6), op_completed(6, evidence_ref=OPS_EVIDENCE_TEXT)],
        7: [op_started(7)],
        8: [op_started(8), legacy],
        9: [op_started(9), {**legacy, "invocation_id": helper.fixture_ulid(9)}],
    }
    for number, lines in shapes.items():
        _write_lines(directory / f"{helper.fixture_ulid(number)}.jsonl", lines)
    (directory / f"{helper.fixture_ulid(10)}.jsonl").write_bytes(b"")
    spine = [op_completed(7, outcome="abandoned", closed_by="doctor_sweep"), op_completed(9, outcome="abandoned", closed_by="doctor_sweep")]
    _write_lines(directory / "op-closures.jsonl", spine)
    return repo


def ops_expected_views() -> dict[str, OpView]:
    """The Ops of the planted repository as the facts of each plant fix them (never taken from a read)."""
    closed = [OP_CLOSED.format(minute=number) for number in range(11)]
    kinds = {2: "none", 3: "absolute_path", 4: "url", 5: "relative_reference", 6: "free_text"}
    views: dict[str, OpView] = {helper.fixture_ulid(1): ("open", None, None, None, None)}
    views.update({helper.fixture_ulid(number): ("closed", "done", "agent", closed[number], kind) for number, kind in kinds.items()})
    views[helper.fixture_ulid(7)] = ("closed", "abandoned", "doctor_sweep", closed[7], "none")
    views[helper.fixture_ulid(9)] = ("closed", "abandoned", "doctor_sweep", closed[9], "none")
    return views


def ops_agreement_problems(repo: Path, contract: helper.Contract, tools: helper.ContractTools) -> list[str]:
    """The reader's Ops walk (three Ops a page, so the cursor is walked) against the oracle's direct scan."""
    walk = walk_ops(repo, contract, tools, page_size=3)
    return ops_walk_problems(walk, oracles.scan_ops(repo), expect_discovered_ops(repo))


def test_the_ops_oracle_states_the_planted_ops_directly(scratch_git: Path) -> None:
    scan = oracles.scan_ops(ops_repo(scratch_git))
    assert expect_op_views(scan) == ops_expected_views()
    assert scan.skipped == {helper.fixture_ulid(8): oracles.SKIP_LEGACY_COMPLETION, helper.fixture_ulid(10): oracles.SKIP_UNREADABLE}
    assert scan.legacy_completions() == [helper.fixture_ulid(8)]
    counts = ops_floor_counts(scan)
    assert counts["ops_served"] == 8 and counts["spine_closed_ops"] == 2 and counts["evidence_url"] == 1
    assert (counts["evidence_none"], counts["evidence_absolute_path"], counts["evidence_free_text"], counts["evidence_relative_reference"]) == (1, 1, 1, 1)


def test_the_ops_reader_equals_the_oracle_on_the_planted_repository(scratch_git: Path, contract: helper.Contract, tools: helper.ContractTools) -> None:
    assert ops_agreement_problems(ops_repo(scratch_git), contract, tools) == []


def _ops_mutant_spine_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ops_reader, "read_spine", lambda fs, ops_dir: {})


def _ops_mutant_host_path_read_as_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ops_reader, "is_host_path", lambda value: False)


def _ops_mutant_legacy_completion_served_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ops_reader, "closure_of", lambda own, spine: own.completion)


def _ops_mutant_skipped_not_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ops_reader, "page_counts", lambda served, skipped, profile: (len(served), 0))


def _ops_mutant_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ops_reader, "order_ops", lambda served: sorted(served, key=lambda op: (op.micros, op.item["invocationId"])))


def _ops_mutant_relative_reference_read_as_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ops_reader, "is_repo_path_candidate", lambda value, tools: False)


OPS_MUTANTS: dict[str, Callable[[pytest.MonkeyPatch], None]] = {
    "the spine is ignored": _ops_mutant_spine_ignored,
    "a host path is read as text": _ops_mutant_host_path_read_as_text,
    "a legacy completion is served open": _ops_mutant_legacy_completion_served_open,
    "the skipped Ops are not counted": _ops_mutant_skipped_not_counted,
    "the Ops are served oldest first": _ops_mutant_oldest_first,
    "a relative reference is read as text": _ops_mutant_relative_reference_read_as_text,
}


@pytest.mark.parametrize("name", sorted(OPS_MUTANTS))
def test_a_consistently_wrong_ops_reader_is_killed_by_the_oracle(
    name: str, scratch_git: Path, contract: helper.Contract, tools: helper.ContractTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = ops_repo(scratch_git)
    assert ops_agreement_problems(repo, contract, tools) == [], "the control: the unmutated reader agrees"
    OPS_MUTANTS[name](monkeypatch)
    assert ops_agreement_problems(repo, contract, tools), f"the mutation was not killed: {name}"


def test_a_removed_schema_check_turns_the_ops_walk_red(
    scratch_git: Path, contract: helper.Contract, tools: helper.ContractTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wiring guard of the Ops walk: when the schema check never reaches the contract, the walk reports every page it did not validate."""
    repo = ops_repo(scratch_git)
    assert walk_ops(repo, contract, tools, page_size=3).problems == []
    monkeypatch.setattr(contract, "errors", lambda title, instance: [])
    problems = walk_ops(repo, contract, tools, page_size=3).problems
    assert any("contract validation" in line for line in problems), "a walk that validated no page must be red"


def test_the_ops_identity_fails_on_an_empty_directory_a_short_walk_and_a_page_that_fails(
    scratch_git: Path, contract: helper.Contract, tools: helper.ContractTools
) -> None:
    """A walk over no Op file proves nothing; a walk that reads fewer Ops than the directory holds, or a page that answers a refusal, is reported."""
    repo = ops_repo(scratch_git)
    scan = oracles.scan_ops(repo)
    walk = walk_ops(repo, contract, tools, page_size=3)
    assert ops_walk_problems(walk, scan, expect_discovered_ops(repo)) == []
    reversed_walk = dataclasses.replace(walk, items=list(reversed(walk.items)))
    assert any("newest first" in line for line in ops_walk_problems(reversed_walk, scan, expect_discovered_ops(repo))), "an oldest-first walk must be reported"
    assert ops_walk_problems(walk, scan, 0), "zero discovered files must fail"
    assert ops_walk_problems(walk, scan, expect_discovered_ops(repo) + 1), "a walk short of the discovered files must fail"
    assert ops_walk_problems(dataclasses.replace(walk, problems=["page 1 answered 500"]), scan, expect_discovered_ops(repo))
    empty = oracles.scan_ops(scratch_git)
    assert empty.served == {} and empty.skipped == {} and expect_discovered_ops(scratch_git) == 0


# ---------------------------------------------------------------------------
# Floors, named lists, dispositions, offline plans
# ---------------------------------------------------------------------------


def test_every_new_floor_is_pinned_at_or_above_its_plan_time_value_and_below_a_measure() -> None:
    assert p13_loosening(FLOORS) == []
    new_fields = {field_.name for field_ in dataclasses.fields(FLOORS)} - set(PLAN_TIME_FLOORS) - {"missions", "work_package_payloads", "snapshot_work_packages"}
    assert new_fields == set(P13_FLOORS), f"a floor without a pin or a pin without a floor: {sorted(new_fields ^ set(P13_FLOORS))}"
    assert {name: getattr(FLOORS, name) for name in P13_FLOORS} == P13_FLOORS


@pytest.mark.parametrize("name", sorted(P13_FLOORS))
def test_a_new_floor_loosened_to_one_is_red(name: str) -> None:
    """Mutant: each floor set to one (and to one below plan time) fails the pin; a floor of zero is loosened only by going below zero."""
    for loosened in {value for value in (1, P13_FLOORS[name] - 1) if value < P13_FLOORS[name]}:
        assert p13_loosening(dataclasses.replace(FLOORS, **{name: loosened})), f"{name}={loosened} was not caught"


def test_a_measured_count_under_its_floor_or_zero_is_reported() -> None:
    enough = {name: value + 1 for name, value in P13_FLOORS.items()}
    assert new_floor_problems(enough) == []
    for name, value in P13_FLOORS.items():
        if value > 0:
            assert new_floor_problems({**enough, name: value - 1}), f"{name} under its floor was not reported"
            assert new_floor_problems({**enough, name: 0}), f"{name} at zero was not reported"
    assert new_floor_problems({**enough, "evidence_url": 0}) == [], "a fixture-only floor of zero is met by zero"


def test_a_stale_or_vanished_named_entry_fails_both_ways() -> None:
    assert named_list_problems("list", ["a", "b"], ["a", "b"], ["a"]) == []
    assert named_list_problems("list", ["a", "b"], ["a"], ["a"]), "an entry the reader lacks must fail"
    assert named_list_problems("list", ["a"], ["a", "stale"], ["a"]), "a stale entry the oracle does not derive must fail"
    assert named_list_problems("list", ["a"], ["a"], ["a", "vanished"]), "a pinned name that is gone must fail"
    assert named_list_problems("list", ["a", "new"], ["a", "new"], ["a"]) == [], "an unpinned new anomaly is only reported"


DISPOSITION_PLANTS: dict[str, str] = {
    "a resolver case that does not use the shared run": "def test_corpus_a(): pass\n",
    "an always-run case that reaches the resolver": "def test_corpus_b(corpus_run): pass\n",
    "an always-run case that builds a scan": "def test_corpus_c():\n    scan_drift()\n",
    "an unlisted corpus case": "def test_corpus_d(): pass\n",
}


def test_the_dispositions_catch_each_plant_and_pass_the_control() -> None:
    control = "def test_corpus_a(corpus_run): pass\ndef test_corpus_b(): pass\ndef test_corpus_c(): pass\n"
    assert disposition_problems(control, frozenset({"test_corpus_b", "test_corpus_c"}), frozenset({"test_corpus_a"}), frozenset()) == []
    sets = {
        "a resolver case that does not use the shared run": (frozenset(), frozenset({"test_corpus_a"})),
        "an always-run case that reaches the resolver": (frozenset({"test_corpus_b"}), frozenset()),
        "an always-run case that builds a scan": (frozenset({"test_corpus_c"}), frozenset()),
        "an unlisted corpus case": (frozenset(), frozenset()),
    }
    for name, source in DISPOSITION_PLANTS.items():
        always, resolver = sets[name]
        assert disposition_problems(source, always, resolver, frozenset()), f"the plant was not caught: {name}"
    assert disposition_problems(control, frozenset({"test_corpus_b", "test_corpus_c", "test_corpus_gone"}), frozenset({"test_corpus_a"}), frozenset()), (
        "a name defined nowhere"
    )


def offline_plan_problems(plan: CasePlan, must_run: frozenset[str], must_skip: frozenset[str]) -> list[str]:
    """What an offline plan must run and must skip, named independently of the registry; a case in neither list is a surprise."""
    problems = [f"{name}: must run offline and is skipped" for name in sorted(must_run & set(plan.skip))]
    problems += [f"{name}: must be skipped offline and runs" for name in sorted(must_skip & plan.run)]
    problems += [f"{name}: skipped offline but not named as resolver-dependent" for name in sorted(set(plan.skip) - must_skip)]
    return problems


OFFLINE_MUST_RUN = frozenset(
    {
        "test_corpus_ops_walk_equals_the_oracle_and_leaves_the_trees_as_found",
        "test_corpus_ops_skipped_count_and_named_list_equal_the_oracle",
        "test_corpus_ops_floors_and_evidence_kinds_equal_the_oracle",
        "test_corpus_completion_equals_is_mission_completed",
        "test_corpus_ops_listing_is_within_five_seconds",
        "test_corpus_the_oracles_neither_call_nor_import_a_reader",
        "test_corpus_case_dispositions_follow_the_resolver_use",
        "test_corpus_offline_scan_is_a_200_with_no_fallback_entry",
    }
)
OFFLINE_MUST_SKIP = frozenset(
    {
        "test_corpus_drift_scan_is_a_200_and_the_resolver_ran_once_per_mission",
        "test_corpus_fallback_list_equals_the_independent_derivation",
        "test_corpus_missions_examined_plus_skipped_equals_discovered",
        "test_corpus_kinds_one_and_two_equal_the_oracle_and_meet_their_floors",
        "test_corpus_kind_three_equals_the_oracle",
        "test_corpus_project_report_equals_the_oracles",
        "test_corpus_per_mission_reports_equal_the_filtered_findings",
        "test_corpus_payloads_validate_and_leak_clean",
        "test_corpus_project_build_is_within_its_bound",
        "test_corpus_scan_is_within_its_bound",
        "test_corpus_combined_run_is_within_its_bound",
        "test_corpus_trees_are_unchanged_by_the_resolver_run",
    }
)


def test_the_offline_plan_skips_only_the_named_resolver_cases_and_each_plant_is_caught() -> None:
    assert offline_plan_problems(case_plan(False), OFFLINE_MUST_RUN, OFFLINE_MUST_SKIP) == []
    online = case_plan(True)
    assert online.skip.keys() == OFFLINE_ONLY_CASES and online.run == ALWAYS_CASES | RESOLVER_CASES
    completion = "test_corpus_completion_equals_is_mission_completed"
    listing = "test_corpus_ops_listing_is_within_five_seconds"
    project_bound = "test_corpus_project_build_is_within_its_bound"
    plants = {
        "the completion equality moved into the skip": case_plan(False, ALWAYS_CASES - {completion}, RESOLVER_CASES | {completion}),
        "the real listing moved into the skip": case_plan(False, ALWAYS_CASES - {listing}, RESOLVER_CASES | {listing}),
        "the Project build run offline": case_plan(False, ALWAYS_CASES | {project_bound}, RESOLVER_CASES - {project_bound}),
    }
    for name, plan in plants.items():
        assert offline_plan_problems(plan, OFFLINE_MUST_RUN, OFFLINE_MUST_SKIP), f"the plant was not caught: {name}"
    assert OFFLINE_MUST_RUN | OFFLINE_MUST_SKIP == CORPUS_CASES


# ---------------------------------------------------------------------------
# Timing, the cache-the-result mutation, the completion guard, the fingerprints, the AST plants
# ---------------------------------------------------------------------------


def test_the_minimum_of_at_least_five_cold_repeats_is_the_figure_and_fewer_is_refused() -> None:
    ticks = iter([0.0, 9.0, 10.0, 11.0, 20.0, 29.0, 30.0, 39.0, 40.0, 49.0])
    measured = timed_cold_repeats(lambda: 3, timer=lambda: next(ticks))
    assert measured.seconds == (9.0, 1.0, 9.0, 9.0, 9.0) and measured.minimum == 1.0 and measured.opens == (3,) * 5
    with pytest.raises(ValueError, match="at least 5"):
        timed_cold_repeats(lambda: 1, repeats=MIN_REPEATS - 1)


def test_a_planted_over_bound_listing_fails_and_a_cache_hit_is_never_read_as_fast(scratch_git: Path, tools: helper.ContractTools) -> None:
    repo = ops_repo(scratch_git)
    files = expect_discovered_ops(repo)
    control, measured = listing_problems(repo, tools, expected_files=files)
    assert control == [] and len(measured.seconds) == MIN_REPEATS and all(count >= files for count in measured.opens)
    clock = itertools.count(0, 6)
    slow, _ = listing_problems(repo, tools, expected_files=files, timer=lambda: float(next(clock)))
    assert any("exceeds" in line for line in slow), "a 6 s listing must fail the 5 s bound"
    assert listing_problems(repo, tools, expected_files=0)[0], "a bound over no file proves nothing"
    assert timing_problems("combined", 121.0, BOUND_SECONDS, "counts") and not timing_problems("combined", 120.0, BOUND_SECONDS, "counts")


def test_the_cache_the_result_mutation_turns_the_real_listing_case_red(tools: helper.ContractTools) -> None:
    """A memoising real-directory listing is red in the real case: every repeat after the first opened no Op file (plan-round ruling 9)."""
    files = expect_discovered_ops(REPO_ROOT)
    assert listing_problems(REPO_ROOT, tools, expected_files=files)[0] == [], "the control: the real listing is clean"
    with memoising_listing():
        problems, measured = listing_problems(REPO_ROOT, tools, expected_files=files)
    assert any("a cache was hit" in line for line in problems), f"the mutation was not killed: opens per repeat {measured.opens}"
    assert measured.opens[0] >= files and set(measured.opens[1:]) == {0}


def test_the_completion_guard_fails_on_zero_missions_a_disagreement_and_a_short_count(scratch_git: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = dho_repo(scratch_git)
    control, compared = completion_equality_problems(repo, floor=1)
    assert control == [] and compared == len(DHO_NAMES) - 1, "the control: every Mission but the coordination one is compared"
    assert completion_equality_problems(scratch_git, floor=1)[0], "a planted zero-Mission directory must fail"
    assert completion_equality_problems(repo, floor=compared + 1)[0], "a count under its floor must fail"
    flipped = completion_equality_problems(repo, floor=1, completion=lambda root, name: not reader_completion(root, name))[0]
    assert len(flipped) == compared, "a reader that is wrong everywhere must be reported for every Mission"
    assert expect_non_coordination_count(repo) == compared
    pairs = oracles.completion_pairs(repo, oracles.mission_names(repo), NOW)
    monkeypatch.setattr(oracles, "completion_pairs", lambda root, names, now: dict(list(pairs.items())[1:]))
    short = completion_equality_problems(repo, floor=1)[0]
    assert any("independent meta.json scan" in line for line in short), "a comparison that left one Mission out must differ from the independent count"


def _tracked_repo(area: Path) -> Path:
    repo = new_git_repo(area, "tracked")
    helper.write_fixture_mission(repo, "m1", rows=lane_rows({"WP01": "planned"}))
    ops = repo / OPS_TREE
    ops.mkdir()
    (ops / f"{helper.fixture_ulid(1)}.jsonl").write_text(json.dumps(op_started(1)) + "\n", encoding="utf-8")
    helper.commit_all(repo)
    return repo


def _rewrite_an_op_file(repo: Path) -> None:
    (repo / OPS_TREE / f"{helper.fixture_ulid(1)}.jsonl").write_text(json.dumps(op_started(2)) + "\n", encoding="utf-8")


def _create_a_file_in_kitty_specs(repo: Path) -> None:
    (repo / KITTY_SPECS / "m1" / "left-behind.txt").write_text("written by a reader\n", encoding="utf-8")


def _create_an_empty_directory_in_kitty_ops(repo: Path) -> None:
    (repo / OPS_TREE / "cache").mkdir()


WRITING_READERS: dict[str, tuple[Callable[[Path], None], str]] = {
    "a reader that rewrites an Op file": (_rewrite_an_op_file, OPS_TREE),
    "a reader that leaves a file in a Mission directory": (_create_a_file_in_kitty_specs, KITTY_SPECS),
    "a reader that creates an empty directory in kitty-ops": (_create_an_empty_directory_in_kitty_ops, OPS_TREE),
}


@pytest.mark.parametrize("name", sorted(WRITING_READERS))
def test_a_reader_that_writes_into_a_corpus_tree_is_caught_and_a_reading_one_is_not(name: str, scratch_git: Path, tools: helper.ContractTools) -> None:
    repo = _tracked_repo(scratch_git)
    assert tree_problems(repo, lambda: ops_reader.list_ops(repo, tools=tools)) == [], "the control: a read leaves both trees as found"
    writer, tree = WRITING_READERS[name]
    problems = tree_problems(repo, lambda: writer(repo))
    assert problems and tree in problems[0], f"the writing reader was not caught: {name}"


AST_PLANTS: dict[str, str] = {
    "an import of a reader module": "import tests.contract._mission_status_drift\n",
    "a from-import of a reader module": "from tests.contract import _mission_status_ops as reader\n",
    "a from-import of a reader name": "from tests.contract._mission_status_project import build_project\n",
    "the alias of a reader": "def oracle(x):\n    return drift.scan_drift(x)\n",
    "an obfuscated dynamic import": "import importlib\nimportlib.import_module('tests.contract._mission_status_' + 'ops')\n",
    "a from-import of importlib": "from importlib import import_module\nimport_module('tests.contract._mission_status_' + 'ops')\n",
    "a builtin dynamic import": "__import__('tests.contract._mission_status_' + 'ops')\n",
    "a dynamic import by name": "import importlib\nimportlib.import_module('tests.contract._mission_status_artifacts')\n",
}


def test_the_reader_reference_guard_sees_each_way_a_reader_can_be_reached() -> None:
    assert reader_references(ast.parse("from tests.contract import _mission_status_memo as memo\nimport json\n")) == []
    for name, source in AST_PLANTS.items():
        assert reader_references(ast.parse(source)), f"the plant was not caught: {name}"


def test_the_oracle_functions_of_this_module_are_the_four_it_declares() -> None:
    """The functions the AST test checks are exactly the ``expect_*`` functions defined in this file."""
    declared = {
        node.name for node in ast.parse(Path(__file__).read_text(encoding="utf-8")).body if isinstance(node, ast.FunctionDef) and node.name.startswith("expect_")
    }
    assert declared == {function.__name__ for function in ORACLE_FUNCTIONS}


# ---------------------------------------------------------------------------
# Payload controls on one shared fixture: a real payload validates, each planted defect fails
# ---------------------------------------------------------------------------


def _shared_payloads(area: Path, tools: helper.ContractTools, contract: helper.Contract) -> dict[str, tuple[str, dict[str, Any]]]:
    repo = dho_repo(area)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("project:\n  slug: dho\n", encoding="utf-8")
    memo = memo_module.ResolverMemo()
    project = project_builder.build_project(repo, memo, leak=tools.leak).body
    report = drift.scan_drift(repo, memo, clock=FrozenClock(instant=NOW)).body
    page = ops_reader.list_ops(ops_repo(area), tools=tools).body
    return {"project": (helper.SCHEMA_PROJECT, project), "drift": (helper.SCHEMA_DRIFT_REPORT, report), "ops": (helper.SCHEMA_OPS_PAGE, page)}


def _payload_plants(kind: str, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The same payload with one planted defect each: a host path, an address, a credential, an unknown enum value and an extra property."""
    host, address, token = _fragments_path(), _fragments_email(), _fragments_token()
    if kind == "project":
        return {
            "host path": {**payload, "name": host},
            "e-mail address": {**payload, "name": address},
            "credential": {**payload, "name": token},
            "unknown enum value": {**payload, "health": "unwell"},
            "extra property": {**payload, "unexpected": True},
        }
    if kind == "drift":
        finding = payload["findings"][0]
        return {
            "host path": {**payload, "findings": [{**finding, "summary": f"see {host}"}]},
            "e-mail address": {**payload, "findings": [{**finding, "summary": f"ask {address}"}]},
            "credential": {**payload, "findings": [{**finding, "summary": token}]},
            "unknown enum value": {**payload, "findings": [{**finding, "severity": "fatal"}]},
            "extra property": {**payload, "unexpected": True},
        }
    item = payload["items"][0]
    return {
        "host path": {**payload, "items": [{**item, "action": host}]},
        "e-mail address": {**payload, "items": [{**item, "action": address}]},
        "credential": {**payload, "items": [{**item, "action": token}]},
        "unknown enum value": {**payload, "items": [{**item, "status": "stuck"}]},
        "extra property": {**payload, "unexpected": True},
    }


def payload_wiring_problems(before: tuple[int, int, int], after: tuple[int, int, int], payloads: int) -> list[str]:
    """The schema check and the leak scan each ran once for every payload: a removed check turns the case red (the wiring guard)."""
    validations, leak_scans = after[0] - before[0], after[1] - before[1]
    return ran_problems(
        {"contract validation": validations, "leak scan": leak_scans}, {"contract validation": payloads, "leak scan": payloads}, into="the payload check"
    )


def test_a_real_payload_of_each_new_read_is_clean_and_each_planted_defect_is_found(
    scratch_git: Path, tools: helper.ContractTools, contract: helper.Contract
) -> None:
    clean = _shared_payloads(scratch_git, tools, contract)
    planted = 0
    for kind, (title, payload) in clean.items():
        before = helper.LEDGER.snapshot()
        assert payload_problems(contract, tools, title, payload) == [], f"control: the real {kind} payload is clean"
        assert payload_wiring_problems(before, helper.LEDGER.snapshot(), 1) == []
        for defect, plant in _payload_plants(kind, payload).items():
            planted += 1
            assert payload_problems(contract, tools, title, plant), f"the planted {defect} in a {kind} payload was not found"
    assert planted == 15
    before = helper.LEDGER.snapshot()
    assert payload_wiring_problems(before, before, 1), "a payload check that ran neither check must be reported"


def ledger_problems(ledger: CaseLedger, plan: CasePlan) -> list[str]:
    """The corpus cases that ran and the ones skipped by name against the plan of the environment: nothing missing, nothing extra, no skip unnamed."""
    problems = [f"{name}: planned to run and did not" for name in sorted(plan.run - ledger.executed)]
    problems += [f"{name}: ran but is not in the plan" for name in sorted(ledger.executed - plan.run)]
    problems += [f"{name}: planned for a named skip and did not skip" for name in sorted(set(plan.skip) - set(ledger.skipped))]
    problems += [f"{name}: skipped with no name in the plan" for name in sorted(set(ledger.skipped) - set(plan.skip))]
    return problems


def offline_annotation(state: oracles.RemoteState, skipped: Mapping[str, str], environ: Mapping[str, str]) -> str | None:
    """A GitHub Actions warning for a run that took the named offline skips, so a green offline run is visible on the pull request; None otherwise."""
    if environ.get("GITHUB_ACTIONS") != "true" or state.online or not skipped:
        return None
    remotes = ", ".join(state.unreachable)
    names = ", ".join(sorted(skipped))
    return (
        f"::warning title=Corpus reality check ran offline::remote(s) {remotes} could not be reached, "
        f"so {len(skipped)} resolver-dependent cases took their named skip: {names}"
    )


def test_the_offline_annotation_is_emitted_only_on_actions_when_offline_with_skips() -> None:
    offline = oracles.RemoteState(remotes=("origin",), unreachable=("origin",))
    online = oracles.RemoteState(remotes=("origin",), unreachable=())
    skipped = {"test_a": OFFLINE_SKIP, "test_b": OFFLINE_SKIP}
    on_actions = {"GITHUB_ACTIONS": "true"}
    annotation = offline_annotation(offline, skipped, on_actions)
    assert annotation is not None and annotation.startswith("::warning ") and "origin" in annotation and "2 resolver-dependent cases" in annotation
    assert "test_a" in annotation and "test_b" in annotation
    assert offline_annotation(offline, skipped, {}) is None, "outside GitHub Actions nothing is annotated"
    assert offline_annotation(online, skipped, on_actions) is None, "an online run is not annotated"
    assert offline_annotation(offline, {}, on_actions) is None, "a run with no named skip is not annotated"


def test_the_case_ledger_fails_on_a_vanished_case_and_on_a_case_that_slipped_into_the_skip() -> None:
    plan = case_plan(False)
    complete = CaseLedger(set(plan.run), dict(plan.skip))
    assert ledger_problems(complete, plan) == []
    vanished = CaseLedger(set(plan.run) - {"test_corpus_completion_equals_is_mission_completed"}, dict(plan.skip))
    assert ledger_problems(vanished, plan), "a planned case that never ran must be reported"
    slipped = CaseLedger(
        set(plan.run) - {"test_corpus_completion_equals_is_mission_completed"}, {**plan.skip, "test_corpus_completion_equals_is_mission_completed": OFFLINE_SKIP}
    )
    assert ledger_problems(slipped, plan), "a case that slipped into the named skip must be reported"
    assert ledger_problems(CaseLedger(set(), {}), case_plan(True)), "an empty ledger proves nothing"


# Keep this test LAST in the file: under ``--dist loadfile`` the file runs on one worker in
# definition order, so the case counter is complete when it runs.
def test_every_generated_case_executed_and_the_count_is_not_vacuous(remote_state: oracles.RemoteState, capsys: pytest.CaptureFixture[str]) -> None:
    annotation = offline_annotation(remote_state, CASE_LEDGER.skipped, os.environ)
    if annotation is not None:
        with capsys.disabled():  # past the capture, so the runner log carries it
            print("\n" + annotation, flush=True)  # a workflow command is read only at the start of a line
    assert ledger_problems(CASE_LEDGER, case_plan(remote_state.online)) == [], (
        "a corpus case of the health, drift and Ops reads did not run, or ran when it should have skipped by name"
    )
    assert len(CORPUS_CASES) == 20
    with_meta = enumerate_missions(REPO_ROOT)
    assert len(CASES) == len(with_meta) >= FLOORS.missions, "the case list must equal the Missions with a meta.json"
    assert set(CASES) == EXECUTED, f"{len(CASES) - len(EXECUTED)} generated cases did not execute"
    payloads = sum(CASE_RESULTS[mission].work_packages for mission in CASES)
    assert payloads >= FLOORS.work_package_payloads, f"{payloads} work package payloads validated, floor {FLOORS.work_package_payloads}"
