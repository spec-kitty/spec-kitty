"""Skip-if-green on ``ready_for_review`` (FR-011): the decision half, stdlib only.

Contract: ``kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/green-match.md``;
design: research.md D-15, D-16 and D-27, R3 section 1.

Two subcommands, each with a pure core and a thin ``gh api`` edge:

* ``decide`` runs inside the selection job of Router, Packs and CI Modules. It
  decides whether a ``ready_for_review`` run may skip because an earlier run of
  the same workflow already went green for the same *tested key*
  ``(PR, head SHA, first parent of the merge commit the run tested)``.
  **Fail-safe direction: never skip on doubt.** Any lookup error yields ``Run``
  with a ``::warning::`` and the process exits 0.
* ``effective-source`` runs first in CI Aggregate ``collect``. When the source
  run is a skip run (it carries a ``ci-green-match-run-<id>-attempt-<n>``
  marker) it re-points aggregation to the matched CI Modules run after
  re-verifying head, workflow, event, success and tested identity.
  **Fail-safe direction: never pass on doubt.** Any lookup error or mismatch
  exits 1 with ``re-run CI Modules to execute``.

``bind_tested_base`` and ``merge_reference`` are the single definition of the
merge-parent binding that ``aggregate_source.py`` also enforces (D-27).

The helper runs as a bare script before any dependency install, so it imports
the standard library only: no ``yaml``, no ``scripts.*``, and no ``datetime``
(the one timestamp comparison is on fixed-format UTC strings, validated first).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

FULL_SHA = re.compile(r"[0-9a-f]{40}")
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
WORKFLOW_FILE_PATTERN = re.compile(r"[a-z0-9-]+\.yml")
MERGE_REF_PATTERN = re.compile(r"refs/pull/([1-9][0-9]*)/merge")
GREEN_MATCH_NAME_PATTERN = re.compile(r"ci-green-match-run-([1-9][0-9]*)-attempt-([1-9][0-9]*)")
UTC_TIMESTAMP_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")

PULL_REQUEST = "pull_request"
READY_FOR_REVIEW = "ready_for_review"
SUCCESS = "success"
COMPLETED = "completed"
CI_MODULES_PATH = ".github/workflows/ci-modules.yml"
MODULE_TESTS_WORKFLOW = ".github/workflows/module-tests.yml"
MAX_CANDIDATE_LOOKUPS = 10
GH_TIMEOUT_SECONDS = 60

REASON_NOT_A_PULL_REQUEST = "not-a-pull-request"
REASON_MERGE_REF_UNBOUND = "merge-ref-unbound"
REASON_NOT_READY = "not-ready-for-review"
REASON_RE_RUN = "re-run-never-suppressed"
REASON_NO_GREEN_RUN = "no-green-run-for-key"
REASON_MATCHED = "matched-green-run"
REASON_LOOKUP_FAILED = "lookup-failed"
REASON_HEAD_NOT_UNIQUE = "head-not-unique-to-pr"

UNBOUND_PARENTS_MESSAGE = "tested merge parents do not bind the source run head"
NO_MERGE_REFERENCE_MESSAGE = "source run lacks one immutable PR merge workflow reference"
REPOINT_FAILURE_ADVICE = "re-run CI Modules to execute"
MALFORMED_JSON_MESSAGE = "gh API response was not valid JSON"
NON_OBJECT_PAYLOAD_MESSAGE = "gh API response was not a JSON object"


class LookupFailure(Exception):
    """An API lookup failed; the message never carries credentials or captured output."""


class EffectiveSourceError(Exception):
    """The skip run's matched run could not be verified; Aggregate must fail."""


_LOOKUP_ERRORS = (LookupFailure, KeyError, TypeError, ValueError)


class Transport(Protocol):
    """GitHub REST access, paths relative to ``repos/<owner>/<repo>/``."""

    def get(self, path: str) -> Any: ...

    def get_all(self, path: str, field: str) -> list[Any]: ...


# ----------------------------------------------------------------- value objects


@dataclass(frozen=True)
class EventMeta:
    """The pull-request event this run is deciding for."""

    event_name: str
    action: str
    pr_number: int
    head_sha: str
    merge_sha: str
    run_id: int
    run_attempt: int
    workflow_file: str
    repository: str
    # The PR's head branch and head repository, from the (trusted) event payload.
    # A candidate run must be bound to the same ones; empty means "unknown", and
    # unknown never matches.
    head_ref: str = ""
    head_repository: str = ""
    base_ref: str = ""


@dataclass(frozen=True)
class TestedKey:
    """What a run actually tested: PR, head, and the first parent of its merge commit."""

    pr: int
    head: str
    base: str

    @property
    def marker_name(self) -> str:
        return f"ci-tested-key-pr{self.pr}-base-{self.base}"


@dataclass(frozen=True)
class RunMeta:
    """A prior workflow run, as listed by the Actions API."""

    id: int
    run_attempt: int
    path: str
    event: str
    status: str
    conclusion: str | None
    head_sha: str
    html_url: str
    repository: str
    head_branch: str = ""
    head_repository: str = ""
    pull_numbers: tuple[int, ...] = ()

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> RunMeta:
        return cls(
            id=int(raw["id"]),
            run_attempt=int(raw.get("run_attempt", 1)),
            path=str(raw["path"]),
            event=str(raw["event"]),
            status=str(raw["status"]),
            conclusion=None if raw.get("conclusion") is None else str(raw["conclusion"]),
            head_sha=str(raw["head_sha"]),
            html_url=str(raw.get("html_url", "")),
            repository=str(raw["repository"]["full_name"]),
            head_branch=str(raw.get("head_branch") or ""),
            head_repository=str((raw.get("head_repository") or {}).get("full_name") or ""),
            pull_numbers=_pull_numbers(raw.get("pull_requests")),
        )


def _pull_numbers(listed: Any) -> tuple[int, ...]:
    """PR numbers a run object lists; anything malformed lists none (fail-safe: no match)."""
    if not isinstance(listed, list):
        return ()
    return tuple(entry["number"] for entry in listed if isinstance(entry, Mapping) and type(entry.get("number")) is int)


@dataclass(frozen=True)
class Skip:
    """Skip the selection step: ``matched`` already went green for the tested key."""

    reason: str
    marker: str
    matched: RunMeta


@dataclass(frozen=True)
class Run:
    """Execute normally; ``marker`` names the artifact this run must upload ('' for none)."""

    reason: str
    marker: str


@dataclass(frozen=True)
class Effective:
    """The CI Modules run Aggregate must read, and whether it differs from the source."""

    run_id: int
    run_attempt: int
    repointed: bool
    matched_run_url: str


# ------------------------------------------------------ shared binding (D-27)


def bind_tested_base(parents: Sequence[str], head: str) -> str:
    """The tested base: first parent of a PR merge commit whose second parent is ``head``."""
    if len(parents) != 2 or parents[1] != head or not all(FULL_SHA.fullmatch(parent) for parent in parents):
        raise ValueError(UNBOUND_PARENTS_MESSAGE)
    return parents[0]


def merge_reference(run: Mapping[str, Any], repository: str) -> tuple[str, int]:
    """The immutable ``refs/pull/N/merge`` commit and PR number a CI Modules run tested."""
    # The PR projection on a run object is LIVE: after a push its head/base
    # change even on old run records, and it is empty for fork PRs. The
    # referenced_workflows entry is the immutable Actions resolution of the
    # reusable shard workflow actually executed.
    references = run.get("referenced_workflows", [])
    matches = [
        (ref.get("sha"), MERGE_REF_PATTERN.fullmatch(ref.get("ref", "")))
        for ref in references
        if isinstance(ref.get("sha"), str) and FULL_SHA.fullmatch(ref["sha"]) and ref.get("path") == f"{repository}/{MODULE_TESTS_WORKFLOW}@{ref['sha']}"
    ]
    if len(matches) != 1:
        raise ValueError(NO_MERGE_REFERENCE_MESSAGE)
    tested, match = matches[0]
    if match is None:
        raise ValueError(NO_MERGE_REFERENCE_MESSAGE)
    return str(tested), int(match.group(1))


def _parent_shas(commit: Any) -> list[str]:
    parents = commit.get("parents") if isinstance(commit, Mapping) else None
    if not isinstance(parents, list) or not all(isinstance(parent, Mapping) and isinstance(parent.get("sha"), str) for parent in parents):
        raise ValueError(UNBOUND_PARENTS_MESSAGE)
    return [parent["sha"] for parent in parents]


# ------------------------------------------------------------------- decide (pure)


def live_marker_names(response: Mapping[str, Any]) -> frozenset[str]:
    """Names of the non-expired artifacts in an ``artifacts?name=`` API response."""
    return frozenset(str(record["name"]) for record in response["artifacts"] if record.get("expired") is False)


def _has_marker(markers: Mapping[int, frozenset[str]], run_id: int, name: str) -> bool:
    return name in markers.get(run_id, frozenset())


def _bound_to_event(run: RunMeta, event: EventMeta) -> bool:
    """The run's own identity matches this pull request's head and lists this PR number.

    The tested-key marker NAME is uploaded by a PR-controlled run, so on its own it
    proves nothing about which PR produced it. This is the first of two bindings: the
    run must share the event's head branch and head repository, and its
    ``pull_requests`` must list this PR. That field is NOT proof of authorship: GitHub
    fills it live with every open PR whose head matches, so a second PR from the same
    branch (a different base, a modified workflow) lists both numbers. The second
    binding, ``head_is_unique``, closes that. ``pull_requests`` is empty for fork PRs;
    empty or unknown means no match, so such a run executes normally (fail-safe).
    """
    return (
        bool(event.head_ref)
        and run.head_branch == event.head_ref
        and bool(event.head_repository)
        and run.head_repository == event.head_repository
        and event.pr_number in run.pull_numbers
    )


def head_is_unique(event: EventMeta, pulls: Any) -> bool:
    """The head names exactly one PR ever opened from it, and that PR is this one.

    ``pulls`` is the ``pulls?head=<owner>:<ref>&state=all&per_page=100`` listing. With
    ``state=all`` a PR closed since still counts, so a forged second PR cannot be
    hidden by closing it. Fail-safe: anything but exactly one well-formed entry for
    this PR (a second PR, none, a non-list, or a full page that may hide more) is False.
    """
    if not isinstance(pulls, list) or len(pulls) != 1 or not isinstance(pulls[0], Mapping):
        return False
    pull = pulls[0]
    base = pull.get("base")
    head = pull.get("head")
    return (
        type(pull.get("number")) is int
        and pull["number"] == event.pr_number
        and bool(event.base_ref)
        and isinstance(base, Mapping)
        and base.get("ref") == event.base_ref
        and isinstance(head, Mapping)
        and head.get("sha") == event.head_sha
    )


def _head_pulls_path(event: EventMeta) -> str:
    if not (event.head_ref and event.head_repository):
        raise LookupFailure("event head identity is unknown")
    owner = event.head_repository.split("/", 1)[0]
    return f"pulls?head={quote(owner, safe='')}:{quote(event.head_ref, safe='/')}&state=all&per_page=100"


def _is_candidate(run: RunMeta, event: EventMeta) -> bool:
    """A completed, successful, same-workflow ``pull_request`` run for this PR and head (never this run)."""
    return (
        run.id != event.run_id
        and run.path == f".github/workflows/{event.workflow_file}"
        and run.event == PULL_REQUEST
        and run.status == COMPLETED
        and run.conclusion == SUCCESS
        and run.head_sha == event.head_sha
        and run.repository == event.repository
        and _bound_to_event(run, event)
    )


def decide(
    event: EventMeta,
    tested: TestedKey | None,
    candidates: Sequence[RunMeta],
    markers: Mapping[int, frozenset[str]],
    head_unique: Callable[[], bool] | None = None,
) -> Skip | Run:
    """Skip only when a prior green run for the same tested key proves the work was done.

    ``head_unique`` is consulted only once a candidate matches; it reports whether the
    head identifies exactly this PR (``head_is_unique``). Absent or False means Run.
    """
    if event.event_name != PULL_REQUEST:
        return Run(REASON_NOT_A_PULL_REQUEST, "")
    if tested is None:
        return Run(REASON_MERGE_REF_UNBOUND, "")
    key_marker = tested.marker_name
    if event.action != READY_FOR_REVIEW:
        return Run(REASON_NOT_READY, key_marker)
    if event.run_attempt != 1:
        return Run(REASON_RE_RUN, key_marker)
    eligible = sorted((run for run in candidates if _is_candidate(run, event)), key=lambda run: run.id, reverse=True)
    for run in eligible:
        if _has_marker(markers, run.id, key_marker):
            if head_unique is None or not head_unique():
                return Run(REASON_HEAD_NOT_UNIQUE, key_marker)
            return Skip(REASON_MATCHED, f"ci-green-match-run-{run.id}-attempt-{run.run_attempt}", run)
    return Run(REASON_NO_GREEN_RUN, key_marker)


# ------------------------------------------------------------ decide (API edge)


def _resolve_tested(event: EventMeta, transport: Transport) -> TestedKey | None:
    """Bind the merge commit's parents to the event head via the commits API."""
    if not FULL_SHA.fullmatch(event.merge_sha):
        raise LookupFailure("merge commit is not a full SHA")
    commit = transport.get(f"git/commits/{event.merge_sha}")
    try:
        base = bind_tested_base(_parent_shas(commit), event.head_sha)
    except ValueError:
        return None
    return TestedKey(event.pr_number, event.head_sha, base)


def _gather_candidates(event: EventMeta, tested: TestedKey, transport: Transport) -> tuple[list[RunMeta], dict[int, frozenset[str]]]:
    listing = transport.get(f"actions/workflows/{event.workflow_file}/runs?event={PULL_REQUEST}&head_sha={event.head_sha}&status={SUCCESS}&per_page=100")
    runs = [RunMeta.from_api(raw) for raw in listing["workflow_runs"]]
    eligible = sorted((run for run in runs if _is_candidate(run, event)), key=lambda run: run.id, reverse=True)[:MAX_CANDIDATE_LOOKUPS]
    markers = {run.id: live_marker_names(transport.get(f"actions/runs/{run.id}/artifacts?name={tested.marker_name}")) for run in eligible}
    return eligible, markers


def _decide(event: EventMeta, transport: Transport | None) -> tuple[Skip | Run, TestedKey | None]:
    if event.event_name != PULL_REQUEST:
        return decide(event, None, [], {}), None
    tested: TestedKey | None = None
    try:
        api = transport if transport is not None else GhTransport(event.repository)
        tested = _resolve_tested(event, api)
        early = decide(event, tested, [], {})
        if tested is None or isinstance(early, Skip) or early.reason != REASON_NO_GREEN_RUN:
            return early, tested
        candidates, markers = _gather_candidates(event, tested, api)
        return decide(event, tested, candidates, markers, lambda: head_is_unique(event, api.get(_head_pulls_path(event)))), tested
    except _LOOKUP_ERRORS as error:
        return Run(f"{REASON_LOOKUP_FAILED}: {type(error).__name__}", tested.marker_name if tested else ""), tested


# ----------------------------------------------------------- effective-source (pure)


def _bound_markers(source_run: Mapping[str, Any], artifacts: Sequence[Mapping[str, Any]]) -> set[tuple[int, int]]:
    """Green-match markers uploaded by THIS attempt of the source run (A4, A5)."""
    named = [(match, record) for record in artifacts if (match := GREEN_MATCH_NAME_PATTERN.fullmatch(str(record.get("name", ""))))]
    if not named:
        return set()
    started = source_run.get("run_started_at")
    if not isinstance(started, str) or not UTC_TIMESTAMP_PATTERN.fullmatch(started):
        raise EffectiveSourceError("source attempt start is not a fixed-format UTC timestamp")
    bound: set[tuple[int, int]] = set()
    for match, record in named:
        created = record.get("created_at")
        if not isinstance(created, str) or not UTC_TIMESTAMP_PATTERN.fullmatch(created):
            raise EffectiveSourceError("green-match marker timestamp is not a fixed-format UTC timestamp")
        if created >= started:
            bound.add((int(match.group(1)), int(match.group(2))))
    return bound


def _verify_matched(source_run: Mapping[str, Any], matched: Mapping[str, Any], marker: tuple[int, int]) -> None:
    source_repository = (source_run.get("repository") or {}).get("full_name")
    matched_repository = (matched.get("repository") or {}).get("full_name")
    checks = (
        ((matched.get("id"), matched.get("run_attempt")) == marker, "matched run id or attempt does not match the green-match marker"),
        (marker[0] != source_run.get("id"), "matched run is the source run itself"),
        (matched.get("path") == CI_MODULES_PATH, "matched run is not a CI Modules workflow run"),
        (matched.get("event") == PULL_REQUEST, "matched run event is not pull_request"),
        (matched.get("status") == COMPLETED, "matched run is not completed"),
        (matched.get("conclusion") == SUCCESS, "matched run did not conclude with success"),
        (matched.get("head_sha") == source_run.get("head_sha"), "matched run head differs from the source run head"),
        (matched_repository is not None and matched_repository == source_repository, "matched run repository differs from the source run repository"),
    )
    for passed, message in checks:
        if not passed:
            raise EffectiveSourceError(message)


def effective_source(
    source_run: Mapping[str, Any],
    source_artifacts: Sequence[Mapping[str, Any]],
    matched_run: Callable[[int, int], Mapping[str, Any]],
    identity_of: Callable[[Mapping[str, Any]], TestedKey],
) -> Effective:
    """Re-point a skip run to the run it matched, or return the source run unchanged (A2).

    ``matched_run(id, attempt)`` fetches a run attempt; ``identity_of(run)`` derives its
    tested key from its own immutable merge reference. The marker NAME is written by a
    PR-controlled run, so every conjunct is re-verified: a forged name can only point
    at a run with the same head, workflow, event, success and tested identity.
    """
    source = Effective(int(source_run["id"]), int(source_run["run_attempt"]), False, "")
    markers = _bound_markers(source_run, source_artifacts)
    if not markers:
        return source
    if len(markers) > 1:
        raise EffectiveSourceError("ambiguous green-match markers bound to this attempt")
    if source_run.get("event") != PULL_REQUEST:
        raise EffectiveSourceError("source run event is not pull_request")
    marker = next(iter(markers))
    try:
        matched = matched_run(*marker)
    except _LOOKUP_ERRORS as error:
        raise EffectiveSourceError(f"matched run {marker[0]} attempt {marker[1]} could not be fetched: {error}") from None
    _verify_matched(source_run, matched, marker)
    try:
        identities = (identity_of(source_run), identity_of(matched))
    except _LOOKUP_ERRORS as error:
        raise EffectiveSourceError(f"tested identity could not be derived: {error}") from None
    if identities[0] != identities[1]:
        raise EffectiveSourceError("tested identity of the matched run differs from the source run")
    return Effective(marker[0], marker[1], True, str(matched.get("html_url", "")))


# ------------------------------------------------------------------ gh transport


def _decode_documents(text: str) -> list[Any]:
    """Every JSON document in ``text`` (``gh api --paginate`` concatenates one per page)."""
    decoder = json.JSONDecoder()
    documents: list[Any] = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        try:
            document, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            raise LookupFailure(MALFORMED_JSON_MESSAGE) from None
        documents.append(document)
    if not documents:
        raise LookupFailure(MALFORMED_JSON_MESSAGE)
    return documents


class GhTransport:
    """``gh api`` through the host's own authentication; errors never echo captured output."""

    def __init__(self, repository: str) -> None:
        if not REPOSITORY_PATTERN.fullmatch(repository):
            raise ValueError("invalid repository")
        self.repository = repository

    def _run(self, path: str, *, paginate: bool) -> list[Any]:
        command = ["gh", "api", *(["--paginate"] if paginate else []), f"repos/{self.repository}/{path}"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            raise LookupFailure("gh API request could not complete") from None
        if result.returncode:
            # gh may print authentication diagnostics; never echo its captured output.
            raise LookupFailure(f"gh API request failed (exit {result.returncode})")
        return _decode_documents(result.stdout)

    def get(self, path: str) -> Any:
        documents = self._run(path, paginate=False)
        if len(documents) != 1:
            raise LookupFailure(MALFORMED_JSON_MESSAGE)
        return documents[0]

    def get_all(self, path: str, field: str) -> list[Any]:
        rows: list[Any] = []
        for document in self._run(path, paginate=True):
            try:
                rows.extend(document[field])
            except (KeyError, TypeError):
                raise LookupFailure(MALFORMED_JSON_MESSAGE) from None
        return rows


# --------------------------------------------------------------- CLI: GitHub I/O


def write_outputs(path: str, values: Mapping[str, str]) -> None:
    """Append ``key=value`` lines to ``$GITHUB_OUTPUT``; multi-line values use the delimiter form."""
    lines = []
    for key, value in values.items():
        if "\n" in value:
            delimiter = "ghadelimiter_" + hashlib.sha256(value.encode()).hexdigest()[:16]
            lines.append(f"{key}<<{delimiter}\n{value}\n{delimiter}")
        else:
            lines.append(f"{key}={value}")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _emit_outputs(environ: Mapping[str, str], values: Mapping[str, str]) -> None:
    target = environ.get("GITHUB_OUTPUT")
    if target:
        write_outputs(target, values)
    else:
        for key, value in values.items():
            print(f"{key}={value}")


def event_from_environment(environ: Mapping[str, str], workflow_file: str) -> EventMeta:
    """Build the event from the Actions environment; non-PR events need no payload."""
    name = environ.get("GITHUB_EVENT_NAME", "")
    repository = environ.get("GITHUB_REPOSITORY", "")
    if name != PULL_REQUEST:
        return EventMeta(name, "", 0, "", "", 0, 0, workflow_file, repository)
    payload = json.loads(Path(environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    pull_request = payload["pull_request"]
    head, merge = str(pull_request["head"]["sha"]), environ["GITHUB_SHA"]
    head_repo = pull_request["head"].get("repo") or {}
    if not (FULL_SHA.fullmatch(head) and FULL_SHA.fullmatch(merge) and REPOSITORY_PATTERN.fullmatch(repository)):
        raise ValueError("event identity is malformed")
    return EventMeta(
        event_name=name,
        action=str(payload["action"]),
        pr_number=int(pull_request["number"]),
        head_sha=head,
        merge_sha=merge,
        run_id=int(environ["GITHUB_RUN_ID"]),
        run_attempt=int(environ["GITHUB_RUN_ATTEMPT"]),
        workflow_file=workflow_file,
        repository=repository,
        head_ref=str(pull_request["head"].get("ref") or ""),
        head_repository=str(head_repo.get("full_name") or ""),
        base_ref=str((pull_request.get("base") or {}).get("ref") or ""),
    )


def _marker_body(event: EventMeta, tested: TestedKey, decision: str) -> dict[str, Any]:
    return {
        "pr": tested.pr,
        "head": tested.head,
        "base": tested.base,
        "merge_sha": event.merge_sha,
        "workflow": event.workflow_file,
        "run_id": event.run_id,
        "run_attempt": event.run_attempt,
        "decision": decision,
    }


def _decision_outputs(result: Skip | Run) -> dict[str, str]:
    matched = result.matched if isinstance(result, Skip) else None
    return {
        "skip": "true" if isinstance(result, Skip) else "false",
        "reason": result.reason,
        "marker": result.marker,
        "matched-run-id": str(matched.id) if matched else "",
        "matched-run-attempt": str(matched.run_attempt) if matched else "",
        "matched-run-url": matched.html_url if matched else "",
    }


def _announce_skip(environ: Mapping[str, str], workflow_file: str, matched: RunMeta) -> None:
    print(f"::notice::green-match: skipping {workflow_file}; matched green run {matched.html_url}")
    summary = environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"green-match: skipped {workflow_file}, matched green run {matched.html_url}\n")


def _decide_command(args: argparse.Namespace, transport: Transport | None, environ: Mapping[str, str]) -> int:
    try:
        event = event_from_environment(environ, args.workflow)
        result, tested = _decide(event, transport)
        if isinstance(result, Run) and result.reason.startswith(REASON_LOOKUP_FAILED):
            print(f"::warning::green-match {result.reason}; running normally")
        if result.marker and tested is not None:
            marker_dir = Path(args.marker_dir)
            marker_dir.mkdir(parents=True, exist_ok=True)
            body = _marker_body(event, tested, "skip" if isinstance(result, Skip) else "run")
            (marker_dir / f"{result.marker}.json").write_text(json.dumps(body, sort_keys=True) + "\n", encoding="utf-8")
        if isinstance(result, Skip):
            _announce_skip(environ, args.workflow, result.matched)
    except Exception as error:  # fail safe: any unexpected failure means "run normally"
        result = Run(f"{REASON_LOOKUP_FAILED}: {type(error).__name__}", "")
        print(f"::warning::green-match {result.reason}; running normally")
    _emit_outputs(environ, _decision_outputs(result))
    return 0


def _effective_command(args: argparse.Namespace, transport: Transport | None) -> int:
    try:
        api = transport if transport is not None else GhTransport(args.repository)
        source = api.get(f"actions/runs/{args.run_id}/attempts/{args.attempt}")
        if not isinstance(source, Mapping):
            raise EffectiveSourceError(NON_OBJECT_PAYLOAD_MESSAGE)
        if (source.get("id"), source.get("run_attempt")) != (args.run_id, args.attempt):
            raise EffectiveSourceError("source run is not the requested run attempt")
        artifacts = api.get_all(f"actions/runs/{args.run_id}/artifacts?per_page=100", "artifacts")

        def fetch(run_id: int, attempt: int) -> Mapping[str, Any]:
            return dict(api.get(f"actions/runs/{run_id}/attempts/{attempt}"))

        def identity_of(run: Mapping[str, Any]) -> TestedKey:
            merge, number = merge_reference(run, args.repository)
            head = str(run["head_sha"])
            return TestedKey(number, head, bind_tested_base(_parent_shas(api.get(f"git/commits/{merge}")), head))

        effective = effective_source(source, artifacts, fetch, identity_of)
    except (EffectiveSourceError, *_LOOKUP_ERRORS) as error:
        print(f"::error::green-match source could not be verified ({error}); {REPOINT_FAILURE_ADVICE}", file=sys.stderr)
        return 1
    for key, value in (
        ("run-id", effective.run_id),
        ("run-attempt", effective.run_attempt),
        ("repointed", "true" if effective.repointed else "false"),
        ("matched-run-url", effective.matched_run_url),
    ):
        print(f"{key}={value}")
    return 0


def _workflow_file(value: str) -> str:
    if not WORKFLOW_FILE_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("workflow must be a bare .github/workflows file name such as ci-router.yml")
    return value


def _repository(value: str) -> str:
    if not REPOSITORY_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("repository must look like owner/name")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    decide_parser = commands.add_parser("decide", help="decide whether this ready_for_review run may skip")
    decide_parser.add_argument("--workflow", required=True, type=_workflow_file)
    decide_parser.add_argument("--marker-dir", default="green-match-marker", help="where to write the marker artifact body")
    decide_parser.add_argument("--transport", choices=("gh",), default="gh")
    effective_parser = commands.add_parser("effective-source", help="re-point a skip run's source to the run it matched")
    effective_parser.add_argument("--repository", required=True, type=_repository)
    effective_parser.add_argument("--run-id", required=True, type=int)
    effective_parser.add_argument("--attempt", required=True, type=int)
    effective_parser.add_argument("--transport", choices=("gh",), default="gh")
    return parser


def main(argv: Sequence[str] | None = None, *, transport: Transport | None = None, environ: Mapping[str, str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    env = os.environ if environ is None else environ
    if args.command == "decide":
        return _decide_command(args, transport, env)
    return _effective_command(args, transport)


if __name__ == "__main__":
    sys.exit(main())
