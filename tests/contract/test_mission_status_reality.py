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

import re
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from specify_cli.context import mission_resolver
from specify_cli.status.reducer import materialize_snapshot
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
# in a committed log is a decision (map it into the contract, or add it here with its reason), never a silent drop.
KNOWN_DROPPED_LABELS: dict[str, str] = {
    "annotation": "assignment and subtask deltas: folded into the snapshot, not an event of the contract",
    "WPCreated": "lifecycle type outside the seven the contract forwards (spec FR-007)",
    "ReviewerSelfApproval": "lifecycle type outside the seven the contract forwards (spec FR-007)",
    "DecisionPointOpened": "decision-moment row: not a status transition or one of the seven forwarded lifecycle types",
    "DecisionPointResolved": "decision-moment row: not a status transition or one of the seven forwarded lifecycle types",
    "RetrospectiveCaptured": "retrospective row: not a status transition or one of the seven forwarded lifecycle types",
    "RetrospectiveCaptureFailed": "retrospective row: not a status transition or one of the seven forwarded lifecycle types",
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
    repository, or with a planted defect in each work package payload, and the three checks must catch it. A run
    with either is never cached. Every check is also counted, and the case fails when a check ran fewer times than
    the payloads it should have covered, so removing a check from this function cannot leave the case green.
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
    wanted = (("contract validation", validations, payloads), ("leak scan", leak_scans, payloads), ("snapshot comparison", comparisons, work_packages))
    return [f"the {name} ran {ran} times for {expected} payloads: the check is not wired into the case" for name, ran, expected in wanted if ran != expected]


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
    subprocess.run([*git, "init", "-q"], check=True)
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


def _commit_all(repo: Path) -> None:
    git = ["git", "-C", str(repo), "-c", "user.name=fixture", "-c", "user.email=fixture.invalid"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "fixture"], check=True)


def test_the_byte_digest_alone_sees_a_rewrite_that_git_status_cannot(tmp_path: Path) -> None:
    """A committed file that is already modified keeps the porcelain line ` M` however it is rewritten again.

    Only the digest of its bytes can notice a reader rewriting such a file (a dirty local tree, an uncommitted
    snapshot), so this is the control of the digest half of the fingerprint: equal porcelain, different digest.
    """
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    target = tmp_path / KITTY_SPECS / "m" / "status.json"
    target.parent.mkdir(parents=True)
    target.write_text("aaaa", encoding="utf-8")
    _commit_all(tmp_path)
    target.write_text("bbbb", encoding="utf-8")
    dirty = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert dirty.porcelain == (f" M {KITTY_SPECS}/m/status.json",), "control: the file is modified before the first fingerprint"
    assert tree_fingerprint(tmp_path, KITTY_SPECS) == dirty, "control: nothing changed, so the fingerprint is stable"

    target.write_text("cccc", encoding="utf-8")  # same length, still ` M`

    rewritten = tree_fingerprint(tmp_path, KITTY_SPECS)
    assert rewritten.porcelain == dirty.porcelain, "git status cannot see this rewrite"
    assert rewritten.digest != dirty.digest, "the byte digest must"
    assert rewritten != dirty


def test_an_ignored_file_is_part_of_the_fingerprint(tmp_path: Path) -> None:
    """``git status`` omits ignored files (``*.lock`` under ``kitty-specs/`` is ignored in this repository)."""
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".gitignore").write_text("*.lock\n", encoding="utf-8")
    tracked = tmp_path / KITTY_SPECS / "m" / "status.json"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("{}", encoding="utf-8")
    _commit_all(tmp_path)
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
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
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
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    helper.write_fixture_mission(tmp_path, "discarded-control", meta={"discarded_at": "2026-09-05T00:00:00+00:00"})
    overview = helper.build_overview(helper.load_source(tmp_path, "discarded-control"), helper.Projector(tools.leak, "discarded-control"))
    assert contract.errors(helper.SCHEMA_OVERVIEW, overview) == []
    assert overview["lifecycleStatus"] == "discarded"


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


# Keep this test LAST in the file: under ``--dist loadfile`` the file runs on one worker in
# definition order, so the case counter is complete when it runs.
def test_every_generated_case_executed_and_the_count_is_not_vacuous() -> None:
    with_meta = enumerate_missions(REPO_ROOT)
    assert len(CASES) == len(with_meta) >= FLOORS.missions, "the case list must equal the Missions with a meta.json"
    assert set(CASES) == EXECUTED, f"{len(CASES) - len(EXECUTED)} generated cases did not execute"
    payloads = sum(CASE_RESULTS[mission].work_packages for mission in CASES)
    assert payloads >= FLOORS.work_package_payloads, f"{payloads} work package payloads validated, floor {FLOORS.work_package_payloads}"
