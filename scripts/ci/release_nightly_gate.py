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

The module is stdlib-only (urllib) so the gate step can run it with a bare
``python3`` without installing the ``spec-kitty-cli`` package, mirroring
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
from typing import Any, Protocol

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

# Poll cadence / ceiling defaults (seconds). Both overridable via the CLI.
_DEFAULT_POLL_INTERVAL_SECONDS = 30
_DEFAULT_TIMEOUT_SECONDS = 60 * 60


class ReleaseGateError(RuntimeError):
    """A GitHub API / resolution failure. Always fail-closed (no publish)."""


@dataclass(frozen=True)
class ReleaseGateResult:
    """The gate decision plus a human-readable summary for the CI log."""

    passed: bool
    summary: str
    release_sha: str | None = None


class NightlyGateClient(Protocol):
    """The GitHub Actions operations the release gate depends on (mockable)."""

    def resolve_tag_sha(self, tag: str) -> str: ...

    def list_nightly_runs(self, head_sha: str) -> list[dict[str, Any]]: ...

    def dispatch_nightly(self, *, ref: str, mode: str) -> None: ...


def _is_completed(run: dict[str, Any]) -> bool:
    return run.get("status") == _COMPLETED_STATUS


def _is_in_flight(run: dict[str, Any]) -> bool:
    return run.get("status") in _IN_FLIGHT_STATUSES


def _is_success(run: dict[str, Any]) -> bool:
    return _is_completed(run) and run.get("conclusion") == _SUCCESS_CONCLUSION


def _first_success(runs: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    return next((run for run in runs if _is_success(run)), None)


def _poll_to_terminal(
    client: NightlyGateClient,
    release_sha: str,
    *,
    deadline: float,
    poll_interval: float,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
    baseline_ids: frozenset[int] | None,
) -> ReleaseGateResult:
    """Wait until a nightly for ``release_sha`` concludes, then decide.

    Any ``success`` run for the SHA passes the gate immediately. When
    ``baseline_ids`` is given (the dispatch path) only runs OUTSIDE that set --
    the freshly dispatched run -- can drive a negative verdict, so a pre-existing
    red run never short-circuits a dispatch, and a run that has not yet appeared
    keeps the gate waiting. A negative verdict is drawn only once the relevant
    run(s) are terminal with nothing still in flight; the deadline fails closed.
    """
    while True:
        runs = client.list_nightly_runs(release_sha)
        if _first_success(runs) is not None:
            return ReleaseGateResult(True, f"nightly for {release_sha} concluded success", release_sha)

        candidates = runs if baseline_ids is None else [run for run in runs if int(run.get("id", 0)) not in baseline_ids]
        if any(_is_completed(run) for run in candidates) and not any(_is_in_flight(run) for run in candidates):
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
) -> ReleaseGateResult:
    """Decide whether the release for ``tag`` may publish (pure orchestration).

    Driven in the unit tests with a fake client + fake clock to cover
    green-exists, dispatch->green, dispatch->red, in-flight->wait, and the
    no-nightly-without-dispatch fail-closed path.
    """
    release_sha = client.resolve_tag_sha(tag)
    runs = client.list_nightly_runs(release_sha)

    if _first_success(runs) is not None:
        return ReleaseGateResult(True, f"nightly for {release_sha} already green; gate passes", release_sha)

    # An in-flight nightly for the SHA: wait for its terminal result rather than
    # racing it with a fresh dispatch (contract), regardless of --dispatch.
    if any(_is_in_flight(run) for run in runs):
        return _poll_to_terminal(
            client,
            release_sha,
            deadline=monotonic() + timeout,
            poll_interval=poll_interval,
            sleep=sleep,
            monotonic=monotonic,
            baseline_ids=None,
        )

    if not dispatch:
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
        deadline=monotonic() + timeout,
        poll_interval=poll_interval,
        sleep=sleep,
        monotonic=monotonic,
        baseline_ids=baseline_ids,
    )


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
