"""FR-011 skip-if-green decision helper: every row of ``contracts/green-match.md``.

``decide`` (N1-N15, P1-P2) and ``effective_source`` (A1-A5) are exercised as pure
functions, plus the thin ``gh api`` edge through injected fake transports. All API
shapes come from recorded fixtures in ``tests/ci/fixtures/green_match`` (the tested-key
and green-match marker *names* are synthesized over the recorded artifact shape); no
test calls the live GitHub API.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from scripts.ci import green_match

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/green_match.py"
FIXTURES = Path(__file__).parent / "fixtures" / "green_match"

REPOSITORY = "spec-kitty/spec-kitty"
HEAD = "a5cd2d26a5f9384d639a9eea0d6cae8afdaf1506"
HEAD_REF = "fix/nightly-reds-5505-5506-5507"
BASE = "ecb5dd914af5de025b00cadeabb2bbc32066ed02"
MERGE = "a8f4ac8c897fee4067d20ddfb5552a03a1650d27"
OTHER_BASE = "f" * 40
PR = 5509
CURRENT_RUN_ID = 36900000001
WORKFLOW = "ci-router.yml"
KEY = green_match.TestedKey(pr=PR, head=HEAD, base=BASE)


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- builders


def make_event(**overrides: Any) -> green_match.EventMeta:
    base = green_match.EventMeta(
        event_name="pull_request",
        action="ready_for_review",
        pr_number=PR,
        head_sha=HEAD,
        merge_sha=MERGE,
        run_id=CURRENT_RUN_ID,
        run_attempt=1,
        workflow_file=WORKFLOW,
        repository=REPOSITORY,
        head_ref=HEAD_REF,
        head_repository=REPOSITORY,
    )
    return dataclasses.replace(base, **overrides)


def make_candidate(**overrides: Any) -> green_match.RunMeta:
    """The recorded CI Router run for the head, as a match candidate."""
    return dataclasses.replace(green_match.RunMeta.from_api(load("workflow-runs-by-head.json")["workflow_runs"][0]), **overrides)


def artifact_record(name: str, *, expired: bool = False, created_at: str = "2026-10-01T06:15:51Z", run_id: int = 0) -> dict[str, Any]:
    """A synthesized artifact record: recorded shape, only name/expired/created_at changed."""
    record: dict[str, Any] = json.loads(json.dumps(load("artifacts-by-name.json")["artifacts"][0]))
    record.update(name=name, expired=expired, created_at=created_at)
    if run_id:
        record["workflow_run"]["id"] = run_id
    return record


def markers_for(run: green_match.RunMeta, *names: str, expired: bool = False) -> dict[int, frozenset[str]]:
    records = [artifact_record(name, expired=expired) for name in names]
    return {run.id: green_match.live_marker_names({"artifacts": records})}


def merge_markers(*maps: dict[int, frozenset[str]]) -> dict[int, frozenset[str]]:
    merged: dict[int, frozenset[str]] = {}
    for mapping in maps:
        merged.update(mapping)
    return merged


GOOD = make_candidate()
OLDER = dataclasses.replace(GOOD, id=GOOD.id - 100, run_attempt=2)
NEWEST = dataclasses.replace(GOOD, id=GOOD.id + 100, run_attempt=3)
GOOD_MARKERS = markers_for(GOOD, KEY.marker_name)


@dataclasses.dataclass(frozen=True)
class Row:
    """One contract-table row: inputs plus the expected (type, reason, marker)."""

    event: dict[str, Any]
    tested: green_match.TestedKey | None
    candidates: list[green_match.RunMeta]
    markers: dict[int, frozenset[str]]
    kind: type
    reason: str
    marker: str


def run_row(
    *,
    event: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    markers: dict[int, frozenset[str]] | None = None,
    reason: str,
    marker: str | None = None,
) -> Row:
    """A 'must run' row: a green candidate (with matching marker unless overridden) that must NOT be matched."""
    cand = dataclasses.replace(GOOD, **(candidate or {}))
    return Row(
        event=event or {},
        tested=KEY,
        candidates=[cand],
        markers=GOOD_MARKERS if markers is None else markers,
        kind=green_match.Run,
        reason=reason,
        marker=KEY.marker_name if marker is None else marker,
    )


NO_GREEN = "no-green-run-for-key"
NOT_PR = "not-a-pull-request"

ROWS: dict[str, Row] = {}
for _name in ("push", "workflow_dispatch", "workflow_call", "schedule"):
    ROWS[f"N1-{_name}"] = run_row(event={"event_name": _name, "action": ""}, reason=NOT_PR, marker="")
for _action in ("opened", "synchronize", "reopened"):
    ROWS[f"N2-{_action}"] = run_row(event={"action": _action}, reason="not-ready-for-review")
ROWS["N3-rerun"] = run_row(event={"run_attempt": 2}, reason="re-run-never-suppressed")
ROWS["N4-no-run-for-head"] = Row({}, KEY, [], {}, green_match.Run, NO_GREEN, KEY.marker_name)
ROWS["N5-in_progress"] = run_row(candidate={"status": "in_progress", "conclusion": None}, reason=NO_GREEN)
ROWS["N5-queued"] = run_row(candidate={"status": "queued", "conclusion": None}, reason=NO_GREEN)
for _conclusion in ("failure", "cancelled", "timed_out", "action_required", "startup_failure", "neutral", "skipped"):
    ROWS[f"N6-{_conclusion}"] = run_row(candidate={"conclusion": _conclusion}, reason=NO_GREEN)
ROWS["N7-moved-base"] = run_row(markers=markers_for(GOOD, f"ci-tested-key-pr{PR}-base-{OTHER_BASE}"), reason=NO_GREEN)
ROWS["N8-different-pr"] = run_row(markers=markers_for(GOOD, f"ci-tested-key-pr{PR + 1}-base-{BASE}"), reason=NO_GREEN)
ROWS["N9-no-marker"] = run_row(markers={}, reason=NO_GREEN)
ROWS["N9-skip-run-never-chained"] = run_row(markers=markers_for(GOOD, f"ci-green-match-run-{GOOD.id}-attempt-1"), reason=NO_GREEN)
ROWS["N10-expired-marker"] = run_row(markers=markers_for(GOOD, KEY.marker_name, expired=True), reason=NO_GREEN)
ROWS["N11-merge-ref-unbound"] = Row({}, None, [GOOD], GOOD_MARKERS, green_match.Run, "merge-ref-unbound", "")
ROWS["N13-candidate-is-current-run"] = run_row(event={"run_id": GOOD.id}, reason=NO_GREEN)
ROWS["N14-other-workflow"] = run_row(candidate={"path": ".github/workflows/ci-modules.yml"}, reason=NO_GREEN)
ROWS["N14b-other-head"] = run_row(candidate={"head_sha": "1" * 40}, reason=NO_GREEN)
ROWS["N14c-other-event"] = run_row(candidate={"event": "push"}, reason=NO_GREEN)
ROWS["N14d-other-repository"] = run_row(candidate={"repository": "someone/else"}, reason=NO_GREEN)
# Identity binding: the marker NAME is PR-controlled, so the run object must belong to THIS PR.
ROWS["N16-forged-from-other-pr"] = run_row(candidate={"pull_numbers": (PR + 1,)}, reason=NO_GREEN)
ROWS["N16b-different-head-branch"] = run_row(candidate={"head_branch": "attacker/forged"}, reason=NO_GREEN)
ROWS["N16c-different-head-repository"] = run_row(candidate={"head_repository": "someone/fork"}, reason=NO_GREEN)
ROWS["N16d-pull-requests-not-listed"] = run_row(candidate={"pull_numbers": ()}, reason=NO_GREEN)
ROWS["N16e-event-head-ref-unknown"] = run_row(event={"head_ref": ""}, candidate={"head_branch": ""}, reason=NO_GREEN)
ROWS["N16f-event-head-repository-unknown"] = run_row(event={"head_repository": ""}, candidate={"head_repository": ""}, reason=NO_GREEN)
ROWS["P1b-other-pr-listed-alongside"] = Row(
    {},
    KEY,
    [dataclasses.replace(GOOD, pull_numbers=(PR + 1, PR))],
    GOOD_MARKERS,
    green_match.Skip,
    "matched-green-run",
    f"ci-green-match-run-{GOOD.id}-attempt-{GOOD.run_attempt}",
)
ROWS["P1-single-match"] = Row({}, KEY, [GOOD], GOOD_MARKERS, green_match.Skip, "matched-green-run", f"ci-green-match-run-{GOOD.id}-attempt-{GOOD.run_attempt}")
ROWS["P2-newest-of-many"] = Row(
    {},
    KEY,
    [OLDER, GOOD, NEWEST],
    merge_markers(markers_for(OLDER, KEY.marker_name), GOOD_MARKERS, markers_for(NEWEST, KEY.marker_name)),
    green_match.Skip,
    "matched-green-run",
    f"ci-green-match-run-{NEWEST.id}-attempt-{NEWEST.run_attempt}",
)


def evaluate(row: Row) -> green_match.Skip | green_match.Run:
    return green_match.decide(make_event(**row.event), row.tested, row.candidates, row.markers)


@pytest.mark.parametrize("row", [pytest.param(row, id=name) for name, row in ROWS.items()])
def test_decide_contract_row(row: Row) -> None:
    result = evaluate(row)
    assert type(result) is row.kind
    assert (result.reason, result.marker) == (row.reason, row.marker)


def test_skip_names_the_matched_run() -> None:
    result = evaluate(ROWS["P1-single-match"])
    assert isinstance(result, green_match.Skip)
    assert result.matched == GOOD
    newest = evaluate(ROWS["P2-newest-of-many"])
    assert isinstance(newest, green_match.Skip)
    assert newest.matched.id == NEWEST.id


@pytest.mark.parametrize("name", ["N7-moved-base", "N8-different-pr", "N9-no-marker", "N9-skip-run-never-chained", "N10-expired-marker"])
def test_decide_mutation_control_marker_conjunct_carries_the_decision(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the marker predicate neutered, rows that depend on it flip to Skip."""
    row = ROWS[name]
    assert isinstance(evaluate(row), green_match.Run)
    monkeypatch.setattr(green_match, "_has_marker", lambda markers, run_id, name: True)
    assert isinstance(evaluate(row), green_match.Skip)


@pytest.mark.parametrize("name", ["N5-in_progress", "N6-failure", "N13-candidate-is-current-run", "N14-other-workflow", "N14b-other-head"])
def test_decide_mutation_control_candidate_filter_carries_the_decision(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    row = ROWS[name]
    assert isinstance(evaluate(row), green_match.Run)
    monkeypatch.setattr(green_match, "_is_candidate", lambda run, event: True)
    assert isinstance(evaluate(row), green_match.Skip)


def _binding_without(dropped: str) -> Callable[[green_match.RunMeta, green_match.EventMeta], bool]:
    """``_bound_to_event`` with exactly one conjunct removed (the mutant under test)."""
    conjuncts: dict[str, Callable[[green_match.RunMeta, green_match.EventMeta], bool]] = {
        "head_branch": lambda run, event: bool(event.head_ref) and run.head_branch == event.head_ref,
        "head_repository": lambda run, event: bool(event.head_repository) and run.head_repository == event.head_repository,
        "pull_request": lambda run, event: event.pr_number in run.pull_numbers,
    }
    kept = [check for name, check in conjuncts.items() if name != dropped]
    return lambda run, event: all(check(run, event) for check in kept)


@pytest.mark.parametrize(
    ("dropped", "row"),
    [
        pytest.param("pull_request", "N16-forged-from-other-pr", id="drop-pr-number-check"),
        pytest.param("pull_request", "N16d-pull-requests-not-listed", id="drop-pr-listed-check"),
        pytest.param("head_branch", "N16b-different-head-branch", id="drop-head-branch-check"),
        pytest.param("head_branch", "N16e-event-head-ref-unknown", id="drop-head-branch-non-empty-check"),
        pytest.param("head_repository", "N16c-different-head-repository", id="drop-head-repository-check"),
        pytest.param("head_repository", "N16f-event-head-repository-unknown", id="drop-head-repository-non-empty-check"),
    ],
)
def test_decide_mutation_control_each_identity_binding_conjunct_carries_the_decision(dropped: str, row: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dropping any one new conjunct lets the forged-run row go green wrongly (Skip)."""
    assert isinstance(evaluate(ROWS[row]), green_match.Run)
    monkeypatch.setattr(green_match, "_bound_to_event", _binding_without(dropped))
    assert isinstance(evaluate(ROWS[row]), green_match.Skip)


@pytest.mark.parametrize("name", [name for name in ROWS if name.startswith("N16")])
def test_decide_mutation_control_identity_binding_as_a_whole(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(evaluate(ROWS[name]), green_match.Run)
    monkeypatch.setattr(green_match, "_bound_to_event", lambda run, event: True)
    assert isinstance(evaluate(ROWS[name]), green_match.Skip)


# ---------------------------------------------------------------------- fake transport


class FakeTransport:
    """Serves recorded fixtures by API path; an Exception value is raised."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.requested: list[str] = []

    def _route(self, path: str) -> Any:
        self.requested.append(path)
        if path not in self.routes:
            raise green_match.LookupFailure(f"no recorded response for {path}")
        value = self.routes[path]
        if isinstance(value, Exception):
            raise value
        return value

    def get(self, path: str) -> Any:
        return self._route(path)

    def get_all(self, path: str, field: str) -> list[Any]:
        return list(self._route(path)[field])


CANDIDATES_PATH = f"actions/workflows/{WORKFLOW}/runs?event=pull_request&head_sha={HEAD}&status=success&per_page=100"
COMMIT_PATH = f"git/commits/{MERGE}"


def marker_path(run_id: int, name: str) -> str:
    return f"actions/runs/{run_id}/artifacts?name={name}"


def api_routes(**overrides: Any) -> dict[str, Any]:
    routes: dict[str, Any] = {
        COMMIT_PATH: load("commit-merge-5509.json"),
        CANDIDATES_PATH: load("workflow-runs-by-head.json"),
        marker_path(GOOD.id, KEY.marker_name): {"artifacts": [artifact_record(KEY.marker_name)]},
    }
    routes.update(overrides)
    return routes


def decide_api(transport: FakeTransport, **event: Any) -> green_match.Skip | green_match.Run:
    return green_match.decide_from_api(make_event(**event), transport)


def test_api_p1_end_to_end_over_recorded_shapes() -> None:
    result = decide_api(FakeTransport(api_routes()))
    assert isinstance(result, green_match.Skip)
    assert (result.reason, result.marker) == ("matched-green-run", f"ci-green-match-run-{GOOD.id}-attempt-1")


def test_api_n10_expired_marker_runs() -> None:
    routes = api_routes(**{marker_path(GOOD.id, KEY.marker_name): {"artifacts": [artifact_record(KEY.marker_name, expired=True)]}})
    result = decide_api(FakeTransport(routes))
    assert isinstance(result, green_match.Run)
    assert (result.reason, result.marker) == (NO_GREEN, KEY.marker_name)


def test_api_n11_second_parent_must_equal_the_event_head() -> None:
    result = decide_api(FakeTransport(api_routes()), head_sha="1" * 40)
    assert isinstance(result, green_match.Run)
    assert (result.reason, result.marker) == ("merge-ref-unbound", "")


@pytest.mark.parametrize(
    ("broken", "marker"),
    [
        pytest.param(CANDIDATES_PATH, KEY.marker_name, id="N12-candidate-list-http-error"),
        pytest.param(marker_path(GOOD.id, KEY.marker_name), KEY.marker_name, id="N12-marker-lookup-http-error"),
        pytest.param(COMMIT_PATH, "", id="N12-commit-lookup-http-error"),
    ],
)
def test_api_n12_any_lookup_failure_runs_normally(broken: str, marker: str) -> None:
    routes = api_routes(**{broken: green_match.LookupFailure("gh API request failed (exit 1)")})
    result = decide_api(FakeTransport(routes))
    assert isinstance(result, green_match.Run)
    assert result.reason.startswith("lookup-failed: ")
    assert result.marker == marker


@pytest.mark.parametrize(
    "bad", [{"parents": []}, {}, {"parents": [{"sha": "x"}, {"sha": "y"}]}, {"parents": "nope"}], ids=["no-parents", "no-key", "not-hex", "wrong-type"]
)
def test_api_malformed_commit_payload_is_never_a_skip(bad: dict[str, Any]) -> None:
    result = decide_api(FakeTransport(api_routes(**{COMMIT_PATH: bad})))
    assert isinstance(result, green_match.Run)


def recorded_run(**overrides: Any) -> dict[str, Any]:
    """The recorded CI Router run object, with named top-level fields replaced."""
    return dict(load("workflow-runs-by-head.json")["workflow_runs"][0], **overrides)


def routes_with_run(run: dict[str, Any]) -> dict[str, Any]:
    return api_routes(**{CANDIDATES_PATH: {"workflow_runs": [run]}})


def test_recorded_run_carries_the_identity_fields_the_binding_reads() -> None:
    run = recorded_run()
    assert (run["head_branch"], run["head_repository"]["full_name"], [pr["number"] for pr in run["pull_requests"]]) == (HEAD_REF, REPOSITORY, [PR])


@pytest.mark.parametrize(
    "forged",
    [
        pytest.param({"pull_requests": [dict(recorded_run()["pull_requests"][0], number=PR + 1)]}, id="forged-from-other-pr"),
        pytest.param({"head_branch": "attacker/forged-workflow"}, id="different-head-branch"),
        pytest.param({"head_repository": {"full_name": "attacker/spec-kitty"}}, id="different-head-repository"),
        pytest.param({"head_repository": None}, id="head-repository-deleted"),
        pytest.param({"pull_requests": []}, id="pull-requests-empty-fork-pr"),
        pytest.param({"pull_requests": None}, id="pull-requests-null"),
        pytest.param({"pull_requests": "nope"}, id="pull-requests-wrong-type"),
        pytest.param({"pull_requests": [{"id": 1}, "x", {"number": True}]}, id="pull-requests-malformed-entries"),
        pytest.param({"head_branch": None}, id="head-branch-null"),
    ],
)
def test_api_forged_candidate_run_with_a_matching_marker_name_still_runs(forged: dict[str, Any]) -> None:
    """The marker name is attacker-writable; the candidate run's own identity must bind it to this PR."""
    run = recorded_run()
    run.update(forged)
    result = decide_api(FakeTransport(routes_with_run(run)))
    assert isinstance(result, green_match.Run)
    assert (result.reason, result.marker) == (NO_GREEN, KEY.marker_name)


@pytest.mark.parametrize("missing", ["pull_requests", "head_branch", "head_repository"])
def test_api_candidate_run_missing_an_identity_field_entirely_runs(missing: str) -> None:
    run = recorded_run()
    del run[missing]
    result = decide_api(FakeTransport(routes_with_run(run)))
    assert isinstance(result, green_match.Run)
    assert result.reason == NO_GREEN


def test_api_event_without_a_head_identity_never_skips() -> None:
    assert isinstance(decide_api(FakeTransport(api_routes()), head_ref="", head_repository=""), green_match.Run)


def test_api_fork_pr_event_matches_only_a_run_bound_to_the_fork_head() -> None:
    """A fork PR's run object lists no pull_requests, so it never matches (the PR is not provable): it runs."""
    fork = "contributor/spec-kitty"
    run = recorded_run(head_repository={"full_name": fork}, pull_requests=[])
    result = decide_api(FakeTransport(routes_with_run(run)), head_repository=fork)
    assert isinstance(result, green_match.Run)
    assert result.reason == NO_GREEN


def test_run_meta_from_api_reads_the_identity_fields() -> None:
    meta = green_match.RunMeta.from_api(recorded_run())
    assert (meta.head_branch, meta.head_repository, meta.pull_numbers) == (HEAD_REF, REPOSITORY, (PR,))
    bare = recorded_run()
    for field in ("head_branch", "head_repository", "pull_requests"):
        del bare[field]
    meta = green_match.RunMeta.from_api(bare)
    assert (meta.head_branch, meta.head_repository, meta.pull_numbers) == ("", "", ())


# WP16 mutation survivors: an artifact record without ``expired`` is not a live marker.


def test_live_marker_names_ignores_records_missing_expired() -> None:
    record = artifact_record(KEY.marker_name)
    del record["expired"]
    assert green_match.live_marker_names({"artifacts": [record]}) == frozenset()
    assert green_match.live_marker_names({"artifacts": [artifact_record(KEY.marker_name)]}) == frozenset({KEY.marker_name})
    assert green_match.live_marker_names({"artifacts": [dict(artifact_record(KEY.marker_name), expired=None)]}) == frozenset()


def test_api_marker_record_missing_expired_runs() -> None:
    record = artifact_record(KEY.marker_name)
    del record["expired"]
    result = decide_api(FakeTransport(api_routes(**{marker_path(GOOD.id, KEY.marker_name): {"artifacts": [record]}})))
    assert isinstance(result, green_match.Run)
    assert (result.reason, result.marker) == (NO_GREEN, KEY.marker_name)


def test_api_early_exits_make_no_candidate_lookups() -> None:
    transport = FakeTransport(api_routes())
    assert isinstance(decide_api(transport, action="synchronize"), green_match.Run)
    assert transport.requested == [COMMIT_PATH]
    push = FakeTransport({})
    assert isinstance(decide_api(push, event_name="push"), green_match.Run)
    assert push.requested == []


def test_api_candidate_marker_lookups_are_bounded_to_the_ten_newest() -> None:
    runs = [dict(load("workflow-runs-by-head.json")["workflow_runs"][0], id=1000 + index) for index in range(15)]
    routes = api_routes(**{CANDIDATES_PATH: {"workflow_runs": runs}})
    transport = FakeTransport(routes)
    for run in runs:
        routes[marker_path(run["id"], KEY.marker_name)] = {"artifacts": []}
    result = decide_api(transport)
    assert isinstance(result, green_match.Run)
    looked_up = [path for path in transport.requested if "artifacts?name=" in path]
    assert looked_up == [marker_path(1000 + index, KEY.marker_name) for index in range(14, 4, -1)]


# ------------------------------------------------------------ shared binding (D-27)


def test_bind_tested_base_returns_the_first_parent() -> None:
    assert green_match.bind_tested_base([BASE, HEAD], HEAD) == BASE


@pytest.mark.parametrize(
    "parents",
    [[BASE], [BASE, HEAD, HEAD], [BASE, OTHER_BASE], [], ["not-a-sha", HEAD]],
    ids=["one-parent", "octopus", "second-parent-is-not-head", "none", "first-parent-not-hex"],
)
def test_bind_tested_base_rejects_unbound_parents(parents: list[str]) -> None:
    with pytest.raises(ValueError, match="^tested merge parents do not bind the source run head$"):
        green_match.bind_tested_base(parents, HEAD)


def test_merge_reference_lifts_the_immutable_merge_and_pr_number() -> None:
    assert green_match.merge_reference(load("run-ci-modules-zero-selection.json"), REPOSITORY) == (MERGE, PR)


@pytest.mark.parametrize(
    "references",
    [
        [],
        [{"path": f"{REPOSITORY}/.github/workflows/module-tests.yml@{MERGE}", "sha": MERGE, "ref": "refs/heads/main"}],
        [{"path": f"{REPOSITORY}/.github/workflows/other.yml@{MERGE}", "sha": MERGE, "ref": f"refs/pull/{PR}/merge"}],
        [{"path": f"{REPOSITORY}/.github/workflows/module-tests.yml@{MERGE}", "sha": "short", "ref": f"refs/pull/{PR}/merge"}],
    ],
    ids=["none", "not-a-pull-merge-ref", "wrong-workflow", "sha-not-full"],
)
def test_merge_reference_requires_one_immutable_reference(references: list[dict[str, str]]) -> None:
    run = dict(load("run-ci-modules-zero-selection.json"), referenced_workflows=references)
    with pytest.raises(ValueError, match="^source run lacks one immutable PR merge workflow reference$"):
        green_match.merge_reference(run, REPOSITORY)


def test_merge_reference_rejects_two_references() -> None:
    run = load("run-ci-modules-zero-selection.json")
    run["referenced_workflows"] = run["referenced_workflows"] * 2
    with pytest.raises(ValueError, match="immutable PR merge workflow reference"):
        green_match.merge_reference(run, REPOSITORY)


# ----------------------------------------------------- effective-source: pure core

SOURCE_ID = 36900000007
SOURCE_MERGE = "b" * 40
SOURCE_STARTED = "2026-10-01T07:00:00Z"
MATCHED = load("run-ci-modules-zero-selection.json")
MATCHED_KEY = green_match.TestedKey(PR, HEAD, BASE)
GREEN_MATCH_NAME = f"ci-green-match-run-{MATCHED['id']}-attempt-{MATCHED['run_attempt']}"


def make_source(**overrides: Any) -> dict[str, Any]:
    source = dict(
        MATCHED,
        id=SOURCE_ID,
        run_attempt=1,
        run_started_at=SOURCE_STARTED,
        referenced_workflows=[
            {"path": f"{REPOSITORY}/.github/workflows/module-tests.yml@{SOURCE_MERGE}", "sha": SOURCE_MERGE, "ref": f"refs/pull/{PR}/merge"},
        ],
    )
    source.update(overrides)
    return source


def marker(name: str = GREEN_MATCH_NAME, *, created_at: str = "2026-10-01T07:05:00Z") -> dict[str, Any]:
    return artifact_record(name, created_at=created_at, run_id=SOURCE_ID)


def fetch_matched(overrides: dict[str, Any] | None = None) -> Callable[[int, int], dict[str, Any]]:
    run = dict(MATCHED, **(overrides or {}))

    def fetch(run_id: int, attempt: int) -> dict[str, Any]:
        if (run_id, attempt) != (MATCHED["id"], MATCHED["run_attempt"]):
            raise green_match.LookupFailure("matched run not found")
        return run

    return fetch


def identity_by_run(matched_key: green_match.TestedKey = MATCHED_KEY) -> Callable[[Mapping[str, Any]], green_match.TestedKey]:
    keys = {SOURCE_ID: KEY, MATCHED["id"]: matched_key}
    return lambda run: keys[run["id"]]


def resolve(
    *,
    source: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    matched: Callable[[int, int], dict[str, Any]] | None = None,
    identity: Callable[[Mapping[str, Any]], green_match.TestedKey] | None = None,
) -> green_match.Effective:
    return green_match.effective_source(
        source or make_source(),
        [marker()] if artifacts is None else artifacts,
        matched or fetch_matched(),
        identity or identity_by_run(),
    )


def test_effective_source_repoints_to_the_verified_matched_run() -> None:
    effective = resolve()
    assert effective == green_match.Effective(MATCHED["id"], MATCHED["run_attempt"], True, MATCHED["html_url"])


@pytest.mark.parametrize(
    "artifacts",
    [[], [artifact_record("module-tests-kernel-shard-1-of-1-attempt-1-reports", created_at="not-a-timestamp")], [artifact_record("selected-modules")]],
    ids=["none", "unrelated-with-garbage-timestamp", "selected-modules-only"],
)
def test_A2_no_marker_is_returned_unchanged(artifacts: list[dict[str, Any]]) -> None:
    assert resolve(artifacts=artifacts) == green_match.Effective(SOURCE_ID, 1, False, "")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        pytest.param({"matched": fetch_matched({"id": 1})}, "not found|id", id="A1-matched-run-missing"),
        pytest.param({"matched": lambda run_id, attempt: (_ for _ in ()).throw(green_match.LookupFailure("gone"))}, "gone", id="A1-lookup-raises"),
        pytest.param({"matched": fetch_matched({"conclusion": "failure"})}, "success", id="A1-not-success"),
        pytest.param({"matched": fetch_matched({"status": "in_progress", "conclusion": None})}, "completed", id="A1-not-completed"),
        pytest.param({"matched": fetch_matched({"status": "in_progress"})}, "not completed", id="A1-not-completed-yet-concluded-success"),
        pytest.param({"matched": fetch_matched({"status": "queued", "conclusion": "success"})}, "not completed", id="A1-queued-yet-concluded-success"),
        pytest.param({"matched": fetch_matched({"repository": {"full_name": "someone/else"}})}, "repository differs", id="A1-different-repository"),
        pytest.param({"matched": fetch_matched({"repository": None})}, "repository differs", id="A1-matched-repository-missing"),
        pytest.param(
            {"source": make_source(repository=None), "matched": fetch_matched({"repository": None})}, "repository differs", id="A1-both-repositories-missing"
        ),
        pytest.param({"matched": fetch_matched({"head_sha": "1" * 40})}, "head", id="A1-different-head"),
        pytest.param({"matched": fetch_matched({"path": ".github/workflows/ci-router.yml"})}, "workflow", id="A1-different-workflow"),
        pytest.param({"matched": fetch_matched({"event": "push"})}, "event", id="A1-different-event"),
        pytest.param({"identity": identity_by_run(green_match.TestedKey(PR, HEAD, OTHER_BASE))}, "identity", id="A1-different-tested-base"),
        pytest.param({"identity": identity_by_run(green_match.TestedKey(PR + 1, HEAD, BASE))}, "identity", id="A1-different-pr"),
        pytest.param(
            {"identity": lambda run: (_ for _ in ()).throw(ValueError("source run lacks one immutable PR merge workflow reference"))},
            "immutable",
            id="A1-identity-unbindable",
        ),
        pytest.param({"source": make_source(id=MATCHED["id"], run_attempt=MATCHED["run_attempt"])}, "itself|source", id="A1-marker-points-at-the-source-run"),
        pytest.param({"source": make_source(event="push")}, "event", id="A1-source-is-not-a-pull-request"),
        pytest.param({"artifacts": [marker(created_at="yesterday")]}, "timestamp", id="A4-malformed-marker-timestamp"),
        pytest.param({"source": make_source(run_started_at="2026-10-01 07:00")}, "timestamp", id="A4-malformed-source-timestamp"),
        pytest.param({"artifacts": [marker(), marker("ci-green-match-run-7-attempt-1")]}, "ambiguous", id="A5-two-distinct-markers"),
    ],
)
def test_effective_source_fails_closed(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(green_match.EffectiveSourceError, match=message):
        resolve(**kwargs)


def test_A1_matched_attempt_must_be_the_marker_attempt() -> None:
    wrong = dict(MATCHED, run_attempt=2)
    with pytest.raises(green_match.EffectiveSourceError):
        resolve(matched=lambda run_id, attempt: wrong)


def test_A3_a_dispatch_replay_of_a_skip_run_repoints_identically() -> None:
    """The core takes no event input, so a ``workflow_dispatch`` replay cannot differ."""
    assert "event" not in inspect.signature(green_match.effective_source).parameters
    assert resolve() == resolve()
    assert resolve().repointed is True


def test_A4_marker_from_an_earlier_attempt_does_not_repoint_a_later_attempt() -> None:
    """Attempt 1 skipped; "re-run all jobs" executed attempt 2. The old marker must not re-point it."""
    later = make_source(run_attempt=2, run_started_at="2026-10-01T09:00:00Z")
    assert resolve(source=later, artifacts=[marker(created_at="2026-10-01T07:05:00Z")]) == green_match.Effective(SOURCE_ID, 2, False, "")


def test_A4_marker_created_at_the_attempt_start_is_bound_to_it() -> None:
    assert resolve(artifacts=[marker(created_at=SOURCE_STARTED)]).repointed is True


@pytest.mark.parametrize(
    "name",
    [
        "ci-green-match-run-0-attempt-1",
        "ci-green-match-run-12-attempt-01",
        "xci-green-match-run-12-attempt-1",
        f"{GREEN_MATCH_NAME}\n",
        "ci-green-match-run-12-attempt-1-extra",
        "ci-green-match-run--5-attempt-1",
    ],
    ids=["zero-id", "leading-zero-attempt", "prefix", "trailing-newline", "suffix", "negative"],
)
def test_A5_names_failing_the_strict_pattern_are_ignored(name: str) -> None:
    assert resolve(artifacts=[marker(name)]) == green_match.Effective(SOURCE_ID, 1, False, "")


def test_A5_the_same_marker_listed_twice_is_not_ambiguous() -> None:
    assert resolve(artifacts=[marker(), marker()]).repointed is True


# ----------------------------------------------------- CLI edges (injected transport)


def effective_routes(*, artifacts: list[dict[str, Any]], matched: dict[str, Any] | None = None, matched_key_base: str = BASE) -> dict[str, Any]:
    source = make_source()
    return {
        f"actions/runs/{SOURCE_ID}/attempts/1": source,
        f"actions/runs/{SOURCE_ID}/artifacts?per_page=100": {"total_count": len(artifacts), "artifacts": artifacts},
        f"actions/runs/{MATCHED['id']}/attempts/{MATCHED['run_attempt']}": matched or MATCHED,
        f"git/commits/{SOURCE_MERGE}": {"sha": SOURCE_MERGE, "parents": [{"sha": BASE}, {"sha": HEAD}]},
        f"git/commits/{MERGE}": {"sha": MERGE, "parents": [{"sha": matched_key_base}, {"sha": HEAD}]},
    }


def effective_argv() -> list[str]:
    return ["effective-source", "--repository", REPOSITORY, "--run-id", str(SOURCE_ID), "--attempt", "1"]


def test_cli_effective_source_A2_prints_the_unchanged_source(capsys: pytest.CaptureFixture[str]) -> None:
    assert green_match.main(effective_argv(), transport=FakeTransport(effective_routes(artifacts=[]))) == 0
    assert capsys.readouterr().out.splitlines() == [f"run-id={SOURCE_ID}", "run-attempt=1", "repointed=false", "matched-run-url="]


def test_cli_effective_source_repoints_and_verifies_identity_over_the_commits_api(capsys: pytest.CaptureFixture[str]) -> None:
    transport = FakeTransport(effective_routes(artifacts=[marker()]))
    assert green_match.main(effective_argv(), transport=transport) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"run-id={MATCHED['id']}",
        f"run-attempt={MATCHED['run_attempt']}",
        "repointed=true",
        f"matched-run-url={MATCHED['html_url']}",
    ]
    assert f"git/commits/{SOURCE_MERGE}" in transport.requested
    assert f"git/commits/{MERGE}" in transport.requested


def test_cli_effective_source_A1_different_base_exits_1_without_a_token(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "ghs_supersecret")
    assert green_match.main(effective_argv(), transport=FakeTransport(effective_routes(artifacts=[marker()], matched_key_base=OTHER_BASE))) == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.startswith("::error::green-match source could not be verified (")
    assert out.err.rstrip().endswith("; re-run CI Modules to execute")
    assert "ghs_supersecret" not in out.err + out.out


def test_cli_effective_source_transport_failure_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    routes = effective_routes(artifacts=[marker()])
    routes[f"actions/runs/{SOURCE_ID}/artifacts?per_page=100"] = green_match.LookupFailure("gh API request failed (exit 1)")
    assert green_match.main(effective_argv(), transport=FakeTransport(routes)) == 1
    assert "re-run CI Modules to execute" in capsys.readouterr().err


@pytest.mark.parametrize("payload", [[], "text", 7, None], ids=["list", "string", "number", "null"])
def test_cli_effective_source_non_object_source_payload_is_an_error_line_not_a_traceback(payload: Any, capsys: pytest.CaptureFixture[str]) -> None:
    routes = effective_routes(artifacts=[])
    routes[f"actions/runs/{SOURCE_ID}/attempts/1"] = payload
    assert green_match.main(effective_argv(), transport=FakeTransport(routes)) == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.startswith("::error::green-match source could not be verified (gh API response was not a JSON object)")
    assert out.err.rstrip().endswith("; re-run CI Modules to execute")
    assert "Traceback" not in out.err


@pytest.mark.parametrize("payload", [[], "text", None], ids=["list", "string", "null"])
def test_cli_effective_source_non_object_commit_payload_exits_1_with_an_error_line(payload: Any, capsys: pytest.CaptureFixture[str]) -> None:
    routes = effective_routes(artifacts=[marker()])
    routes[f"git/commits/{SOURCE_MERGE}"] = payload
    assert green_match.main(effective_argv(), transport=FakeTransport(routes)) == 1
    err = capsys.readouterr().err
    assert err.startswith("::error::green-match source could not be verified (")
    assert "Traceback" not in err


def test_cli_effective_source_rejects_a_source_run_that_is_not_the_requested_attempt(capsys: pytest.CaptureFixture[str]) -> None:
    routes = effective_routes(artifacts=[])
    routes[f"actions/runs/{SOURCE_ID}/attempts/1"] = dict(make_source(), run_attempt=2)
    assert green_match.main(effective_argv(), transport=FakeTransport(routes)) == 1
    assert "re-run CI Modules to execute" in capsys.readouterr().err


# -------------------------------------------------------------- decide CLI edge


def decide_env(tmp_path: Path, *, action: str = "ready_for_review", event_name: str = "pull_request", attempt: str = "1") -> dict[str, str]:
    payload = tmp_path / "event.json"
    payload.write_text(
        json.dumps({"action": action, "pull_request": {"number": PR, "head": {"sha": HEAD, "ref": HEAD_REF, "repo": {"full_name": REPOSITORY}}}}), encoding="utf-8"
    )
    return {
        "GITHUB_EVENT_NAME": event_name,
        "GITHUB_EVENT_PATH": str(payload),
        "GITHUB_SHA": MERGE,
        "GITHUB_RUN_ID": str(CURRENT_RUN_ID),
        "GITHUB_RUN_ATTEMPT": attempt,
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "GH_TOKEN": "ghs_supersecret",
    }


def read_outputs(tmp_path: Path) -> dict[str, str]:
    lines = (tmp_path / "output.txt").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines)


def run_decide(tmp_path: Path, env: dict[str, str], transport: FakeTransport, *extra: str) -> int:
    return green_match.main(["decide", "--workflow", WORKFLOW, "--marker-dir", str(tmp_path / "markers"), *extra], transport=transport, environ=env)


def test_cli_decide_skip_writes_outputs_notice_summary_and_marker_body(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_decide(tmp_path, decide_env(tmp_path), FakeTransport(api_routes())) == 0
    name = f"ci-green-match-run-{GOOD.id}-attempt-1"
    assert read_outputs(tmp_path) == {
        "skip": "true",
        "reason": "matched-green-run",
        "marker": name,
        "matched-run-id": str(GOOD.id),
        "matched-run-attempt": "1",
        "matched-run-url": GOOD.html_url,
    }
    assert "::notice::" in capsys.readouterr().out
    assert GOOD.html_url in (tmp_path / "summary.md").read_text(encoding="utf-8")
    body = json.loads((tmp_path / "markers" / f"{name}.json").read_text(encoding="utf-8"))
    assert body == {"pr": PR, "head": HEAD, "base": BASE, "merge_sha": MERGE, "workflow": WORKFLOW, "run_id": CURRENT_RUN_ID, "run_attempt": 1, "decision": "skip"}


def test_cli_decide_run_records_the_tested_key_marker(tmp_path: Path) -> None:
    assert run_decide(tmp_path, decide_env(tmp_path, action="synchronize"), FakeTransport(api_routes())) == 0
    outputs = read_outputs(tmp_path)
    assert (outputs["skip"], outputs["reason"], outputs["marker"]) == ("false", "not-ready-for-review", KEY.marker_name)
    assert (outputs["matched-run-id"], outputs["matched-run-attempt"], outputs["matched-run-url"]) == ("", "", "")
    body = json.loads((tmp_path / "markers" / f"{KEY.marker_name}.json").read_text(encoding="utf-8"))
    assert body["decision"] == "run"
    assert body["base"] == BASE


def test_event_from_environment_reads_the_head_identity(tmp_path: Path) -> None:
    event = green_match.event_from_environment(decide_env(tmp_path), WORKFLOW)
    assert (event.head_ref, event.head_repository) == (HEAD_REF, REPOSITORY)


@pytest.mark.parametrize("head", [{"sha": HEAD}, {"sha": HEAD, "ref": HEAD_REF, "repo": None}], ids=["no-ref-no-repo", "head-repo-deleted"])
def test_event_from_environment_unknown_head_identity_is_empty_and_never_skips(tmp_path: Path, head: dict[str, Any]) -> None:
    env = decide_env(tmp_path)
    Path(env["GITHUB_EVENT_PATH"]).write_text(json.dumps({"action": "ready_for_review", "pull_request": {"number": PR, "head": head}}), encoding="utf-8")
    event = green_match.event_from_environment(env, WORKFLOW)
    assert not (event.head_ref and event.head_repository)
    assert run_decide(tmp_path, env, FakeTransport(api_routes())) == 0
    assert read_outputs(tmp_path)["skip"] == "false"


def test_cli_decide_forged_other_pr_run_runs_and_records_the_marker(tmp_path: Path) -> None:
    forged = recorded_run(pull_requests=[dict(recorded_run()["pull_requests"][0], number=PR + 1)])
    assert run_decide(tmp_path, decide_env(tmp_path), FakeTransport(routes_with_run(forged))) == 0
    outputs = read_outputs(tmp_path)
    assert (outputs["skip"], outputs["reason"], outputs["marker"]) == ("false", NO_GREEN, KEY.marker_name)


def test_cli_decide_non_pull_request_writes_no_marker(tmp_path: Path) -> None:
    env = decide_env(tmp_path, event_name="push")
    assert run_decide(tmp_path, env, FakeTransport({})) == 0
    assert read_outputs(tmp_path)["marker"] == ""
    assert not (tmp_path / "markers").exists()


def test_cli_decide_lookup_failure_warns_runs_and_never_leaks_the_token(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    routes = api_routes(**{CANDIDATES_PATH: green_match.LookupFailure("gh API request failed (exit 1)")})
    assert run_decide(tmp_path, decide_env(tmp_path), FakeTransport(routes)) == 0
    out = capsys.readouterr().out
    assert "::warning::" in out
    assert "ghs_supersecret" not in out
    assert read_outputs(tmp_path)["skip"] == "false"
    assert read_outputs(tmp_path)["reason"].startswith("lookup-failed: ")


@pytest.mark.parametrize("breakage", ["missing-event-file", "unreadable-json", "bad-sha"])
def test_cli_decide_unexpected_failure_still_exits_0_with_a_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str], breakage: str) -> None:
    env = decide_env(tmp_path)
    if breakage == "missing-event-file":
        env["GITHUB_EVENT_PATH"] = str(tmp_path / "absent.json")
    elif breakage == "unreadable-json":
        Path(env["GITHUB_EVENT_PATH"]).write_text("{", encoding="utf-8")
    else:
        env["GITHUB_SHA"] = "zzz"
    assert run_decide(tmp_path, env, FakeTransport(api_routes())) == 0
    assert "::warning::" in capsys.readouterr().out
    assert read_outputs(tmp_path)["skip"] == "false"


def test_cli_decide_rejects_an_unsafe_workflow_argument(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        green_match.main(["decide", "--workflow", "../etc/passwd"], transport=FakeTransport({}), environ=decide_env(tmp_path))


def test_cli_output_values_with_newlines_use_the_delimiter_form(tmp_path: Path) -> None:
    path = tmp_path / "out.txt"
    green_match.write_outputs(str(path), {"plain": "a", "multi": "x\ny"})
    text = path.read_text(encoding="utf-8")
    assert "plain=a\n" in text
    match = re.search(r"multi<<(\S+)\nx\ny\n\1\n", text)
    assert match is not None


# ---------------------------------------------------------------- gh transport edge


def fake_gh(tmp_path: Path, body: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f"#!/usr/bin/env python3\n{body}\n", encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def test_gh_transport_parses_concatenated_paginated_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = fake_gh(
        tmp_path,
        "import sys\nprint(sys.argv[1:], file=open(sys.argv[0] + '.args', 'w'))\n"
        'sys.stdout.write(\'{"artifacts": [{"name": "a"}]}{"artifacts": [{"name": "b"}]}\\n\')',
    )
    monkeypatch.setenv("PATH", env["PATH"])
    transport = green_match.GhTransport(REPOSITORY)
    assert transport.get_all("actions/runs/1/artifacts?per_page=100", "artifacts") == [{"name": "a"}, {"name": "b"}]
    args = (tmp_path / "bin" / "gh.args").read_text(encoding="utf-8")
    assert f"repos/{REPOSITORY}/actions/runs/1/artifacts?per_page=100" in args
    assert "--paginate" in args


def test_gh_transport_get_returns_one_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", fake_gh(tmp_path, "print('{\"id\": 7}')")["PATH"])
    assert green_match.GhTransport(REPOSITORY).get("actions/runs/7") == {"id": 7}


@pytest.mark.parametrize(
    "body",
    [
        "import sys\nprint('Authorization: Bearer ghs_supersecret', file=sys.stderr)\nprint('ghs_supersecret')\nsys.exit(1)",
        "print('ghs_supersecret is not json')",
        "print('')",
    ],
    ids=["non-zero-exit", "invalid-json", "empty"],
)
def test_gh_transport_errors_are_redacted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    monkeypatch.setenv("PATH", fake_gh(tmp_path, body)["PATH"])
    with pytest.raises(green_match.LookupFailure) as caught:
        green_match.GhTransport(REPOSITORY).get("actions/runs/7")
    assert "ghs_supersecret" not in str(caught.value)


def test_gh_transport_missing_binary_is_a_lookup_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(green_match.LookupFailure):
        green_match.GhTransport(REPOSITORY).get("actions/runs/7")


def test_gh_transport_rejects_a_malformed_repository() -> None:
    with pytest.raises(ValueError, match="invalid repository"):
        green_match.GhTransport("not a repo")


# --------------------------------------------------------- T068: bare-run and bans


def test_helper_runs_bare_without_site_packages(tmp_path: Path) -> None:
    """The selection jobs call the helper before any ``uv sync``: stdlib plus the file only."""
    result = subprocess.run([sys.executable, "-I", "-S", str(SCRIPT), "--help"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr


def test_helper_decide_runs_bare_end_to_end_for_a_non_pull_request_event(tmp_path: Path) -> None:
    env = {"PATH": os.environ["PATH"], "GITHUB_EVENT_NAME": "push", "GITHUB_OUTPUT": str(tmp_path / "output.txt")}
    result = subprocess.run([sys.executable, "-I", "-S", str(SCRIPT), "decide", "--workflow", WORKFLOW], cwd=tmp_path, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert read_outputs(tmp_path)["skip"] == "false"


def test_helper_respects_the_clock_import_boundary() -> None:
    from tests.architectural.test_clock_import_ban import collect_import_ban_violations

    assert collect_import_ban_violations([SCRIPT]) == []


def test_helper_imports_no_yaml_and_no_scripts_module_at_any_depth() -> None:
    """Keeps WP18's pre-install placement safe by construction."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative imports need a package"
            imported.add((node.module or "").split(".")[0])
    assert imported, "the scan must see the helper's imports"
    assert not imported & {"yaml", "scripts", "specify_cli", "kernel", "charter", "datetime"}
    assert imported <= set(sys.stdlib_module_names)
