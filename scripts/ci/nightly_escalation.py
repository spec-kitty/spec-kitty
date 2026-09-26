#!/usr/bin/env python3
"""Escalate a red nightly suite into a deduped ``priority:P0`` issue (FR-007).

The nightly workflow (``.github/workflows/ci-nightly.yml``) runs its expensive
suites run-all-regardless (``if: always()`` + terminal fail-loud, #4212). A red
suite reliably fails its job, but a job going red on a scheduled run relies on
someone reading the run logs (Decision Moment DM-01M3CZWF). This helper closes
that gap: after each nightly suite it opens (or updates) ONE standing
``priority:P0`` GitHub issue per suite, deduped by a stable hidden body marker,
and closes it again once the suite recovers.

Contract (research.md D6):

- ``--conclusion failure`` -> find the one open issue carrying
  ``<!-- nightly-escalation-key: <key> -->``; comment on it if it exists, else
  create a ``priority:P0`` issue carrying that marker plus a link to the failing
  run. INV-5: at most one open issue per key.
- ``--conclusion success`` -> if an open issue with the key exists, comment that
  the suite recovered and close it.
- **Fail-closed toward the workflow**: if the GitHub token / API is unavailable
  (fork, outage) the helper prints a warning to stderr and exits ``0`` -- it
  degrades to fail-loud-only (the suite's own red still fails the job) and never
  crashes the workflow. It never echoes the token (C-005).

The GitHub credential is the Actions ``GITHUB_TOKEN`` (read from ``GH_TOKEN`` or
``GITHUB_TOKEN``); the repository defaults to ``GITHUB_REPOSITORY``. The module
is stdlib-only so the escalation step can run it with a bare ``python3`` without
installing the ``spec-kitty-cli`` package.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Any, Protocol, cast

_API_ROOT = "https://api.github.com"
_MARKER_TEMPLATE = "<!-- nightly-escalation-key: {key} -->"
_P0_LABEL = "priority:P0"
_ISSUE_TITLE_TEMPLATE = "Nightly suite red: {key}"
_RUN_LINK_UNKNOWN = "(run link unavailable)"

EXIT_OK = 0

CONCLUSION_SUCCESS = "success"
CONCLUSION_FAILURE = "failure"


class EscalationError(RuntimeError):
    """A recoverable GitHub API failure -- degrades the step to fail-loud-only."""


def escalation_marker(suite_key: str) -> str:
    """Return the stable hidden dedup marker embedded in an issue's body."""
    return _MARKER_TEMPLATE.format(key=suite_key)


def _run_reference(run_url: str | None) -> str:
    return run_url if run_url else _RUN_LINK_UNKNOWN


def issue_title(suite_key: str) -> str:
    """Return the standing issue title for a suite key."""
    return _ISSUE_TITLE_TEMPLATE.format(key=suite_key)


def issue_body(suite_key: str, run_url: str | None) -> str:
    """Return the body for a freshly created escalation issue (carries the marker)."""
    return (
        f"The nightly `{suite_key}` suite failed on {_run_reference(run_url)}.\n\n"
        "This issue was opened automatically by the nightly red -> P0 escalation "
        "(`scripts/ci/nightly_escalation.py`, FR-007). It is deduped by the hidden "
        "marker below; a later failure comments here instead of opening a duplicate, "
        "and the next green nightly for this suite closes it automatically.\n\n"
        f"{escalation_marker(suite_key)}\n"
    )


def _recurrence_comment(suite_key: str, run_url: str | None) -> str:
    return f"The nightly `{suite_key}` suite failed again on {_run_reference(run_url)}."


def _recovery_comment(suite_key: str, run_url: str | None) -> str:
    return f"The nightly `{suite_key}` suite passed on {_run_reference(run_url)}; closing this escalation."


class IssueClient(Protocol):
    """The GitHub-issue operations the escalation flow depends on (mockable)."""

    def find_open_issue_by_marker(self, marker: str) -> dict[str, Any] | None: ...

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> dict[str, Any]: ...

    def comment_on_issue(self, number: int, body: str) -> dict[str, Any]: ...

    def close_issue(self, number: int) -> dict[str, Any]: ...


def run_escalation(
    client: IssueClient,
    *,
    suite_key: str,
    conclusion: str,
    run_url: str | None = None,
) -> str:
    """Apply the dedup/open/close policy for one suite; return a human summary.

    Pure orchestration over an :class:`IssueClient` -- the unit tests drive it
    with a fake client to cover create / update-existing / close-on-green.
    """
    marker = escalation_marker(suite_key)
    existing = client.find_open_issue_by_marker(marker)

    if conclusion == CONCLUSION_FAILURE:
        if existing is not None:
            number = int(existing["number"])
            client.comment_on_issue(number, _recurrence_comment(suite_key, run_url))
            return f"updated existing escalation issue #{number} for {suite_key!r}"
        created = client.create_issue(
            title=issue_title(suite_key),
            body=issue_body(suite_key, run_url),
            labels=[_P0_LABEL],
        )
        return f"created escalation issue #{int(created['number'])} for {suite_key!r}"

    if conclusion != CONCLUSION_SUCCESS:
        # Defense-in-depth (FIND-3, #5034): the CLI's argparse `choices`
        # already rejects anything but "success"/"failure", but this function
        # is also called directly (tests, any future caller with a looser
        # contract). Without this guard, a stray "cancelled"/"skipped"/""
        # would silently fall through to the close-on-green path below and
        # close a standing P0 for a suite that never actually passed.
        raise ValueError(f"unknown nightly suite conclusion {conclusion!r}; expected {CONCLUSION_SUCCESS!r} or {CONCLUSION_FAILURE!r}")

    # conclusion == success
    if existing is not None:
        number = int(existing["number"])
        client.comment_on_issue(number, _recovery_comment(suite_key, run_url))
        client.close_issue(number)
        return f"closed escalation issue #{number} for {suite_key!r} (suite recovered)"
    return f"no open escalation issue for {suite_key!r}; nothing to do (suite green)"


class GitHubIssueClient:
    """Minimal authenticated GitHub REST client; errors never leak the token."""

    def __init__(self, repository: str, token: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise EscalationError("invalid repository (expected 'owner/repo')")
        if not token:
            raise EscalationError("no GitHub token available")
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
            raise EscalationError(f"GitHub API HTTP {error.code} for {method} {_redact(url, self._token)}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise EscalationError(f"GitHub API request failed: {_redact(str(error), self._token)}") from None
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise EscalationError(f"GitHub API response was not valid JSON: {error}") from None

    def find_open_issue_by_marker(self, marker: str) -> dict[str, Any] | None:
        query = f'repo:{self._repository} type:issue state:open "{marker}"'
        url = f"{_API_ROOT}/search/issues?q={urllib.parse.quote(query)}&per_page=100"
        result = self._request("GET", url)
        items = result.get("items", []) if isinstance(result, dict) else []
        # Search is full-text/fuzzy: keep only issues whose body actually carries
        # the exact marker, and prefer the oldest (lowest number) for determinism.
        matches = [item for item in items if isinstance(item, dict) and marker in (item.get("body") or "")]
        if not matches:
            return None
        return min(matches, key=lambda item: int(item["number"]))

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> dict[str, Any]:
        url = f"{_API_ROOT}/repos/{self._repository}/issues"
        return cast("dict[str, Any]", self._request("POST", url, {"title": title, "body": body, "labels": list(labels)}))

    def comment_on_issue(self, number: int, body: str) -> dict[str, Any]:
        url = f"{_API_ROOT}/repos/{self._repository}/issues/{number}/comments"
        return cast("dict[str, Any]", self._request("POST", url, {"body": body}))

    def close_issue(self, number: int) -> dict[str, Any]:
        url = f"{_API_ROOT}/repos/{self._repository}/issues/{number}"
        return cast("dict[str, Any]", self._request("PATCH", url, {"state": "closed"}))


def _redact(text: str, token: str) -> str:
    return text.replace(token, "[redacted]") if token else text


def resolve_token() -> str | None:
    """Return the Actions token from ``GH_TOKEN``/``GITHUB_TOKEN`` (or ``None``)."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Always exits ``0`` on a missing token / API error."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--suite-key", required=True, help="stable dedup key for the nightly suite (e.g. 'integration')")
    parser.add_argument("--conclusion", required=True, choices=(CONCLUSION_SUCCESS, CONCLUSION_FAILURE), help="the suite's conclusion")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repo (default: $GITHUB_REPOSITORY)")
    parser.add_argument("--run-url", default=None, help="link to the failing/passing workflow run")
    args = parser.parse_args(argv)

    token = resolve_token()
    if not token or not args.repo:
        # Fail-closed toward the workflow: degrade to fail-loud-only (the suite's
        # own red already failed its job). Never echo the token.
        missing = "GitHub token" if not token else "repository (--repo / $GITHUB_REPOSITORY)"
        print(f"warning: {missing} unavailable; skipping nightly P0 escalation (fail-loud only)", file=sys.stderr)
        return EXIT_OK

    try:
        client = GitHubIssueClient(args.repo, token)
        summary = run_escalation(client, suite_key=args.suite_key, conclusion=args.conclusion, run_url=args.run_url)
    except EscalationError as exc:
        print(f"warning: nightly P0 escalation degraded (fail-loud only): {exc}", file=sys.stderr)
        return EXIT_OK
    print(summary)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
