#!/usr/bin/env python3
"""Gate a release on a green nightly for the EXACT release SHA (FR-008).

A release must not publish on unproven tests. This helper makes the honest
nightly integration lane (``.github/workflows/ci-nightly.yml``) a release
precondition: before ``build-release`` runs, the ``nightly-gate`` job asks this
script whether a ``ci-nightly.yml`` run for the *exact* commit the release tag
points at concluded ``success``.

Contract (research.md D7 / contracts/ci-workflow-contract.md release section):

- Resolve ``<release_tag>`` -> ``release_sha``. Query ``ci-nightly.yml`` runs
  whose ``head_sha == release_sha``.
- A ``success`` run for that SHA already exists -> exit ``0`` (gate passes).
- Otherwise, with ``--dispatch``: ``workflow_dispatch`` ``ci-nightly.yml`` **by
  the tag ref** (``ref=<release_tag>`` -- ``workflow_dispatch`` CANNOT target a
  bare 40-hex SHA; the tag points at the release SHA so the resulting run's
  ``head_sha`` matches), input ``mode=full``; poll to terminal; exit ``0`` only
  if that run concluded ``success``, else non-zero.
- An in-flight nightly for the SHA -> wait for its terminal result (don't race),
  then decide -- regardless of ``--dispatch``.
- **Performance verdict (#7704)**: the ``performance`` job runs weekly (the
  Sunday ``ci-nightly.yml`` run, or any ``workflow_dispatch``), so a green run
  on the release SHA no longer implies it ran. The gate also requires a
  ``ci-nightly.yml`` run created in the last :data:`PERFORMANCE_VERDICT_MAX_AGE`
  whose performance job EXECUTED and concluded ``success`` (``skipped`` does
  not count), on the release SHA or on a ``main`` commit that is an ancestor of
  it. The performance job alone decides that verdict: a red stress or e2e job
  in the same run does not make it red. Without one, ``--dispatch``
  dispatches by the tag (a dispatched run always runs the performance job) and
  waits for both verdicts; without ``--dispatch`` the gate refuses and names
  the remedy.
- **Fail closed**: this is the OPPOSITE of the nightly-escalation degrade. A
  release runs in-repo with a token, so a missing token / repository / API error
  / red / missing / timed-out nightly all mean **do not publish** (non-zero).
  The token is never echoed (C-005), mirroring ``nightly_escalation.py``.

**Token (critical GitHub constraint)**: a ``workflow_dispatch`` issued from
Actions with the default ``GITHUB_TOKEN`` does NOT start a new run (documented
recursion guard). The ``nightly-gate`` job therefore feeds this script a
dedicated PAT / GitHub App token (secret ``RELEASE_NIGHTLY_DISPATCH_TOKEN``, read
here from ``GH_TOKEN`` / ``GITHUB_TOKEN``) and declares ``permissions: actions:
write``. Creating that secret is an operator prerequisite.

The module needs only the stdlib (urllib) plus the in-repo, stdlib-only
``kernel.clock`` (the clock door), so the gate step can run it with a bare
``python3`` from a checkout without installing the ``spec-kitty-cli`` package, mirroring
``scripts/ci/nightly_escalation.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# The clock comes through the single door (kernel.clock, FR-012), which is
# stdlib-only, so the gate still runs with a bare ``python3`` from a checkout
# (the capture_shard_timings.py pattern).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
from kernel.clock import UTC, datetime, now_utc, timedelta  # noqa: E402

_API_ROOT = "https://api.github.com"
_WORKFLOW_FILE = "ci-nightly.yml"
_NIGHTLY_MODE = "full"

EXIT_OK = 0
EXIT_FAILURE = 1

# GitHub Actions run states that are not yet terminal (`status`, not
# `conclusion`). A run in any of these may still turn green, so the gate waits
# rather than drawing a negative conclusion.
_IN_FLIGHT_STATUSES = frozenset({"queued", "in_progress", "requested", "waiting", "pending"})
_COMPLETED_STATUS = "completed"
_SUCCESS_CONCLUSION = "success"

# The performance verdict (#7704). The `performance` job's `name:` in
# ci-nightly.yml starts with this prefix (pinned by
# tests/ci/test_performance_weekly_cadence.py); the Actions jobs API reports
# that name. A weekly cadence leaves at most 7 days between scheduled runs.
PERFORMANCE_JOB_NAME_PREFIX = "Performance suite"
PERFORMANCE_VERDICT_MAX_AGE = timedelta(days=7)
_MAINLINE_BRANCH = "main"
_JOB_EXECUTED_CONCLUSION = "success"
# Job conclusions meaning the job did not run (a skipped job carries "skipped").
_NOT_EXECUTED_CONCLUSIONS = frozenset({"skipped"})
_CANCELLED_CONCLUSION = "cancelled"
# Compare statuses meaning the base commit is reachable from the head commit.
_ANCESTOR_COMPARE_STATUSES = frozenset({"ahead", "identical"})

# Poll cadence / ceiling defaults (seconds). Both overridable via the CLI.
_DEFAULT_POLL_INTERVAL_SECONDS = 30
_DEFAULT_TIMEOUT_SECONDS = 60 * 60

# Listing pagination for the performance verdict.
_PAGE_SIZE = 100
_MAX_PAGES = 10


class ReleaseGateError(RuntimeError):
    """A GitHub API / resolution failure. Always fail-closed (no publish)."""


@dataclass(frozen=True)
class ReleaseGateResult:
    """The gate decision plus a human-readable summary for the CI log."""

    passed: bool
    summary: str
    release_sha: str | None = None
    #: True when the only thing missing is a green performance verdict (#7704).
    performance_only: bool = False


class NightlyGateClient(Protocol):
    """The GitHub Actions operations the release gate depends on (mockable)."""

    def resolve_tag_sha(self, tag: str) -> str: ...

    def list_nightly_runs(self, head_sha: str) -> list[dict[str, Any]]: ...

    def dispatch_nightly(self, *, ref: str, mode: str) -> None: ...

    def list_recent_nightly_runs(self, since: datetime) -> list[dict[str, Any]]: ...

    def list_run_jobs(self, run_id: int) -> list[dict[str, Any]]: ...

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str) -> bool: ...


def _is_completed(run: dict[str, Any]) -> bool:
    return run.get("status") == _COMPLETED_STATUS


def _is_in_flight(run: dict[str, Any]) -> bool:
    return run.get("status") in _IN_FLIGHT_STATUSES


def _is_success(run: dict[str, Any]) -> bool:
    return _is_completed(run) and run.get("conclusion") == _SUCCESS_CONCLUSION


def _first_success(runs: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    return next((run for run in runs if _is_success(run)), None)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _performance_job_conclusion(jobs: Sequence[dict[str, Any]]) -> str | None:
    """The performance job's conclusion when it EXECUTED, else ``None`` (absent or ``skipped``)."""
    for job in jobs:
        if str(job.get("name", "")).startswith(PERFORMANCE_JOB_NAME_PREFIX):
            conclusion = job.get("conclusion")
            if isinstance(conclusion, str) and conclusion not in _NOT_EXECUTED_CONCLUSIONS:
                return conclusion
    return None


def _performance_job_executed(jobs: Sequence[dict[str, Any]]) -> bool:
    """True when the run's performance job ran and passed (``skipped`` does not count)."""
    return _performance_job_conclusion(jobs) == _JOB_EXECUTED_CONCLUSION


def _covers_release(client: NightlyGateClient, run: dict[str, Any], release_sha: str) -> bool:
    """The run's commit is the release SHA, or a ``main`` commit the release SHA descends from."""
    head_sha = run.get("head_sha")
    if head_sha == release_sha:
        return True
    if not isinstance(head_sha, str) or run.get("head_branch") != _MAINLINE_BRANCH:
        return False
    return client.is_ancestor(head_sha, release_sha)


@dataclass(frozen=True)
class PerformanceVerdict:
    """The newest completed covering run in the window whose performance job executed.

    It is the verdict whatever its conclusion: an older green run never outvotes
    a newer red one, so a release cannot publish past an open performance red.
    Only the performance job's conclusion decides ``green``; the run's own
    conclusion is kept for display (another job may have failed in that run).
    """

    run: dict[str, Any]
    job_conclusion: str

    @property
    def green(self) -> bool:
        return self.job_conclusion == _JOB_EXECUTED_CONCLUSION


def find_performance_verdict(client: NightlyGateClient, release_sha: str, *, now: datetime) -> PerformanceVerdict | None:
    """The newest completed nightly in the age limit that covers the release and executed the performance job.

    Runs still in flight are not verdicts yet; the poll loop waits for a
    dispatched one. ``None`` means no covering run executed the job in the window.
    """
    since = now - PERFORMANCE_VERDICT_MAX_AGE
    recent = []
    for run in client.list_recent_nightly_runs(since):
        created = _parse_timestamp(run.get("created_at"))
        if _is_completed(run) and created is not None and created >= since:
            recent.append((created, run))
    recent.sort(key=lambda pair: pair[0], reverse=True)
    for _, run in recent:
        if not _covers_release(client, run, release_sha):
            continue
        conclusion = _performance_job_conclusion(client.list_run_jobs(int(run["id"])))
        if conclusion is not None:
            return PerformanceVerdict(run, conclusion)
    return None


def _red_performance_summary(release_sha: str, tag: str, verdict: PerformanceVerdict) -> str:
    run = verdict.run
    if verdict.job_conclusion == _CANCELLED_CONCLUSION:
        return (
            f"the newest performance verdict covering {release_sha} was cancelled: run {run.get('id')} "
            f"({run.get('head_sha')}, {run.get('created_at')}); an older green run does not outvote it. Dispatch "
            f"ci-nightly again by the release tag (gh workflow run {_WORKFLOW_FILE} --ref {tag}), or run this gate with --dispatch"
        )
    return (
        f"the newest performance verdict covering {release_sha} is red: the performance job of run {run.get('id')} "
        f"({run.get('head_sha')}, {run.get('created_at')}) concluded {verdict.job_conclusion!r}; an older green run does not outvote it. "
        f"Fix the red, then dispatch ci-nightly by the release tag (gh workflow run {_WORKFLOW_FILE} --ref {tag}), or run this gate with --dispatch"
    )


def _missing_performance_summary(release_sha: str, tag: str) -> str:
    days = PERFORMANCE_VERDICT_MAX_AGE.days
    return (
        f"no ci-nightly run in the last {days} days in which the performance job executed and passed, "
        f"on {release_sha} or a main ancestor of it (the performance job runs weekly, Sundays); "
        f"remedy: dispatch ci-nightly by the release tag (gh workflow run {_WORKFLOW_FILE} --ref {tag}), "
        "or run this gate with --dispatch"
    )


@dataclass(frozen=True)
class _Verdicts:
    """Both release preconditions, evaluated on one snapshot."""

    same_sha_green: bool
    performance: PerformanceVerdict | None

    @property
    def passed(self) -> bool:
        return self.same_sha_green and self.performance is not None and self.performance.green

    def refusal(self, release_sha: str, tag: str) -> str:
        if self.performance is not None:
            return _red_performance_summary(release_sha, tag, self.performance)
        return _missing_performance_summary(release_sha, tag)


def _evaluate(client: NightlyGateClient, release_sha: str, runs: Sequence[dict[str, Any]], now: Callable[[], datetime]) -> _Verdicts:
    if _first_success(runs) is None:
        return _Verdicts(False, None)
    return _Verdicts(True, find_performance_verdict(client, release_sha, now=now()))


def _pass_summary(release_sha: str, verdicts: _Verdicts) -> str:
    perf = verdicts.performance.run if verdicts.performance is not None else {}
    return f"nightly for {release_sha} concluded success; performance verdict from run {perf.get('id')} ({perf.get('head_sha')}, {perf.get('created_at')})"


def _poll_to_terminal(
    client: NightlyGateClient,
    release_sha: str,
    *,
    deadline: float,
    poll_interval: float,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
    baseline_ids: frozenset[int] | None,
    tag: str,
    now: Callable[[], datetime],
) -> ReleaseGateResult:
    """Wait until a nightly for ``release_sha`` concludes, then decide.

    Both verdicts passing ends the wait. When ``baseline_ids`` is given, only runs
    OUTSIDE that set can drive a negative verdict -- on the dispatch path the
    freshly dispatched run, on the in-flight path the runs that were still in
    flight when the wait began -- so a pre-existing red run never stands in for
    the awaited one, and a run that has not yet appeared keeps the gate waiting. A negative verdict is drawn only once the relevant
    run(s) are terminal with nothing still in flight; the deadline fails closed.
    """
    while True:
        runs = client.list_nightly_runs(release_sha)
        verdicts = _evaluate(client, release_sha, runs, now)
        if verdicts.passed:
            return ReleaseGateResult(True, _pass_summary(release_sha, verdicts), release_sha)

        candidates = runs if baseline_ids is None else [run for run in runs if int(run.get("id", 0)) not in baseline_ids]
        if any(_is_completed(run) for run in candidates) and not any(_is_in_flight(run) for run in candidates):
            # A red run among the ones waited for is the news; say it before any missing-verdict text.
            if verdicts.same_sha_green and all(_is_success(run) for run in candidates if _is_completed(run)):
                return ReleaseGateResult(False, verdicts.refusal(release_sha, tag), release_sha, performance_only=True)
            return ReleaseGateResult(False, f"nightly for {release_sha} concluded non-success", release_sha)

        if monotonic() >= deadline:
            return ReleaseGateResult(False, f"timed out waiting for a nightly for {release_sha} to conclude", release_sha)
        sleep(poll_interval)


def run_release_gate(
    client: NightlyGateClient,
    *,
    tag: str,
    dispatch: bool,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    poll_interval: float = _DEFAULT_POLL_INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = now_utc,
) -> ReleaseGateResult:
    """Decide whether the release for ``tag`` may publish (pure orchestration).

    Driven in the unit tests with a fake client + fake clock to cover
    green-exists, dispatch->green, dispatch->red, in-flight->wait, and the
    no-nightly-without-dispatch fail-closed path.
    """
    client = _CachingClient(client)
    release_sha = client.resolve_tag_sha(tag)
    runs = client.list_nightly_runs(release_sha)

    verdicts = _evaluate(client, release_sha, runs, now)
    if verdicts.passed:
        return ReleaseGateResult(True, f"{_pass_summary(release_sha, verdicts)}; gate passes", release_sha)

    # An in-flight nightly for the SHA: wait for its terminal result rather than
    # racing it with a fresh dispatch (contract), regardless of --dispatch.
    # One deadline bounds the whole gate, so a wait followed by a dispatch never
    # takes twice ``timeout``.
    deadline = monotonic() + timeout
    if any(_is_in_flight(run) for run in runs):
        # Runs already completed before the wait are not what is being waited for:
        # an older red run on the same commit must not stand in for the awaited one.
        already_completed = frozenset(int(run.get("id", 0)) for run in runs if _is_completed(run))
        waited = _poll_to_terminal(
            client,
            release_sha,
            deadline=deadline,
            poll_interval=poll_interval,
            sleep=sleep,
            monotonic=monotonic,
            baseline_ids=already_completed,
            tag=tag,
            now=now,
        )
        # The awaited run went green but brought no green performance verdict
        # (a Monday-Saturday run skips the job): --dispatch still supplies one.
        if waited.passed or not (dispatch and waited.performance_only):
            return waited
        runs = client.list_nightly_runs(release_sha)

    if not dispatch:
        if verdicts.same_sha_green:
            return ReleaseGateResult(False, verdicts.refusal(release_sha, tag), release_sha, performance_only=True)
        return ReleaseGateResult(
            False,
            f"no green nightly for {release_sha} and --dispatch not set; refusing to publish",
            release_sha,
        )

    baseline_ids = frozenset(int(run.get("id", 0)) for run in runs)
    client.dispatch_nightly(ref=tag, mode=_NIGHTLY_MODE)
    return _poll_to_terminal(
        client,
        release_sha,
        deadline=deadline,
        poll_interval=poll_interval,
        sleep=sleep,
        monotonic=monotonic,
        baseline_ids=baseline_ids,
        tag=tag,
        now=now,
    )


class _CachingClient:
    """Memoizes the answers that cannot change during one gate run (#7704).

    Ancestry between two commits and the jobs of a COMPLETED run are fixed, so the
    poll loop does not repeat those calls against the token's rate budget.
    """

    def __init__(self, inner: NightlyGateClient) -> None:
        self._inner = inner
        self._ancestry: dict[tuple[str, str], bool] = {}
        self._jobs: dict[int, list[dict[str, Any]]] = {}

    def resolve_tag_sha(self, tag: str) -> str:
        return self._inner.resolve_tag_sha(tag)

    def list_nightly_runs(self, head_sha: str) -> list[dict[str, Any]]:
        return self._inner.list_nightly_runs(head_sha)

    def dispatch_nightly(self, *, ref: str, mode: str) -> None:
        self._inner.dispatch_nightly(ref=ref, mode=mode)

    def list_recent_nightly_runs(self, since: datetime) -> list[dict[str, Any]]:
        return self._inner.list_recent_nightly_runs(since)

    def list_run_jobs(self, run_id: int) -> list[dict[str, Any]]:
        # Only completed runs reach this call (find_performance_verdict), so their jobs are final.
        # A re-run of that run during the wait is not seen; a cached red then errs toward no publish.
        if run_id not in self._jobs:
            self._jobs[run_id] = self._inner.list_run_jobs(run_id)
        return self._jobs[run_id]

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str) -> bool:
        key = (ancestor_sha, descendant_sha)
        if key not in self._ancestry:
            self._ancestry[key] = self._inner.is_ancestor(ancestor_sha, descendant_sha)
        return self._ancestry[key]


def _redact(text: str, token: str) -> str:
    return text.replace(token, "[redacted]") if token else text


class GitHubActionsClient:
    """Minimal authenticated GitHub Actions REST client; never leaks the token."""

    def __init__(self, repository: str, token: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ReleaseGateError("invalid repository (expected 'owner/repo')")
        if not token:
            raise ReleaseGateError("no GitHub token available")
        self._repository = repository
        self._token = token

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            raise ReleaseGateError(f"GitHub API HTTP {error.code} for {method} {_redact(url, self._token)}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ReleaseGateError(f"GitHub API request failed: {_redact(str(error), self._token)}") from None
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise ReleaseGateError(f"GitHub API response was not valid JSON: {error}") from None

    def resolve_tag_sha(self, tag: str) -> str:
        """Resolve a tag ref to its commit SHA (annotated or lightweight)."""
        url = f"{_API_ROOT}/repos/{self._repository}/commits/{urllib.parse.quote(tag)}"
        result = self._request("GET", url)
        sha = result.get("sha") if isinstance(result, dict) else None
        if not isinstance(sha, str) or not sha:
            raise ReleaseGateError(f"could not resolve tag {tag!r} to a commit SHA")
        return sha

    def list_nightly_runs(self, head_sha: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"head_sha": head_sha, "per_page": 100})
        url = f"{_API_ROOT}/repos/{self._repository}/actions/workflows/{_WORKFLOW_FILE}/runs?{query}"
        result = self._request("GET", url)
        runs = result.get("workflow_runs", []) if isinstance(result, dict) else []
        return [run for run in runs if isinstance(run, dict)]

    def dispatch_nightly(self, *, ref: str, mode: str) -> None:
        url = f"{_API_ROOT}/repos/{self._repository}/actions/workflows/{_WORKFLOW_FILE}/dispatches"
        self._request("POST", url, {"ref": ref, "inputs": {"mode": mode}})

    def _paged(self, url_without_page: str, key: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, _MAX_PAGES + 1):
            result = self._request("GET", f"{url_without_page}&page={page}")
            batch = result.get(key, []) if isinstance(result, dict) else []
            items.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < _PAGE_SIZE:
                return items
        raise ReleaseGateError(f"more than {_MAX_PAGES} pages of {key}; refusing to judge a truncated listing")

    def list_recent_nightly_runs(self, since: datetime) -> list[dict[str, Any]]:
        stamp = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        query = urllib.parse.urlencode({"created": f">={stamp}", "status": _COMPLETED_STATUS, "per_page": _PAGE_SIZE})
        url = f"{_API_ROOT}/repos/{self._repository}/actions/workflows/{_WORKFLOW_FILE}/runs?{query}"
        return self._paged(url, "workflow_runs")

    def list_run_jobs(self, run_id: int) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"filter": "latest", "per_page": _PAGE_SIZE})
        return self._paged(f"{_API_ROOT}/repos/{self._repository}/actions/runs/{int(run_id)}/jobs?{query}", "jobs")

    def is_ancestor(self, ancestor_sha: str, descendant_sha: str) -> bool:
        for sha in (ancestor_sha, descendant_sha):
            if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
                raise ReleaseGateError(f"not a commit SHA: {sha!r}")
        url = f"{_API_ROOT}/repos/{self._repository}/compare/{ancestor_sha}...{descendant_sha}"
        result = self._request("GET", url)
        status = result.get("status") if isinstance(result, dict) else None
        if not isinstance(status, str):
            raise ReleaseGateError(f"could not compare {ancestor_sha} with {descendant_sha}")
        return status in _ANCESTOR_COMPARE_STATUSES


def resolve_token() -> str | None:
    """Return the dispatch token from ``GH_TOKEN``/``GITHUB_TOKEN`` (or ``None``)."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    return None


def _fail_closed(message: str) -> int:
    print(f"error: {message} (fail-closed: no publish on unproven tests)", file=sys.stderr)
    return EXIT_FAILURE


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Fail-closed (non-zero) on any non-success or unavailability."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--tag", required=True, help="the release tag to gate (e.g. 'v3.2.0')")
    parser.add_argument("--dispatch", action="store_true", help="dispatch ci-nightly.yml by the tag ref if no green run exists")
    parser.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT_SECONDS, help="seconds to wait for a nightly to conclude")
    parser.add_argument("--poll-interval", type=int, default=_DEFAULT_POLL_INTERVAL_SECONDS, help="seconds between run-status polls")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repo (default: $GITHUB_REPOSITORY)")
    args = parser.parse_args(argv)

    token = resolve_token()
    if not token:
        # OPPOSITE of the nightly-escalation degrade: a release must not publish
        # on unproven tests, so an absent token is a hard failure. Never echo it.
        return _fail_closed("no GitHub token available (secret RELEASE_NIGHTLY_DISPATCH_TOKEN)")
    if not args.repo:
        return _fail_closed("repository unavailable (--repo / $GITHUB_REPOSITORY)")

    try:
        client = GitHubActionsClient(args.repo, token)
        result = run_release_gate(
            client,
            tag=args.tag,
            dispatch=args.dispatch,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
        )
    except ReleaseGateError as exc:
        return _fail_closed(str(exc))

    if result.passed:
        print(result.summary)
        return EXIT_OK
    return _fail_closed(result.summary)


if __name__ == "__main__":
    raise SystemExit(main())
