#!/usr/bin/env python3
"""Escalate a red nightly suite into a deduped, triaged ``priority:P0`` issue (FR-007).

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
- **Triage on file (#5517)**: every issue a red files (or bumps) is triaged the
  way a maintainer would by hand: native issue type ``Bug``, labels
  ``priority:P0`` + ``from:ci``, milestone :data:`MILESTONE_TITLE` (resolved to
  its number by title through the API), and a native sub-issue link under
  :data:`PARENT_ISSUE_NUMBER`. A bumped issue is back-filled with whichever of
  these it lacks; a field a human already set is never overridden. Each step
  degrades on its own: a failed (or silently dropped) step never blocks filing
  or the other steps, and is reported as a ``::warning::`` annotation.
- **Mainline-only (#5169/#5172/#5265)**: only a run on ``refs/heads/main``
  may open, bump or close a P0. A ``workflow_dispatch`` on an unmerged branch
  is a diagnostic run -- its red is not main's red, and its green must never
  auto-close a real main P0. The workflow gates each escalation step on
  ``github.ref``; this script enforces the same gate independently
  (``--ref``, default ``$GITHUB_REF``) so it holds even if the workflow
  condition drifts. A missing/unknown ref fails closed: no escalation.
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
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

# Actions runs this script as a file (`python3 scripts/ci/nightly_escalation.py`),
# and the tests load it by path. `scripts.ci` resolves only with the repo root
# on the path. Resolve from this file, never the caller's cwd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.ci.nightly_xunit import (  # noqa: E402
    XunitRead,
    issue_evidence,
    read_xunit,
    recurrence_evidence,
    with_recorded_ids,
)

_API_ROOT = "https://api.github.com"
_MARKER_TEMPLATE = "<!-- nightly-escalation-key: {key} -->"
_P0_LABEL = "priority:P0"
_ISSUE_TITLE_TEMPLATE = "Nightly suite red: {key}"
_RUN_LINK_UNKNOWN = "(run link unavailable)"
_ISSUES_PATH = "issues"
_WARNING_TITLE = "Nightly escalation triage"
_PUSH_ACCESS_HINT = "the token may lack push access"

EXIT_OK = 0

CONCLUSION_SUCCESS = "success"
CONCLUSION_FAILURE = "failure"

# The only ref whose nightly verdict may touch a standing P0 (open/bump/close).
MAINLINE_REF = "refs/heads/main"

# Triage every escalation issue receives (#5517): the convention the
# hand-triaged nightly reds set (#5045, #5049, #5311, #5417-#5419, #5505-#5507).
BUG_ISSUE_TYPE = "Bug"
FROM_CI_LABEL = "from:ci"
ESCALATION_LABELS: tuple[str, ...] = (_P0_LABEL, FROM_CI_LABEL)
# Resolved to a milestone number by title at run time, never hard-coded as a number.
MILESTONE_TITLE = "4.0.0 release scope"
# "Test suite friction: red-on-main & stale tests" -- the parent of every nightly red.
PARENT_ISSUE_NUMBER = 5106


class EscalationError(RuntimeError):
    """A recoverable GitHub API failure -- degrades the step to fail-loud-only."""


def escalation_marker(suite_key: str) -> str:
    """Return the stable hidden dedup marker embedded in an issue's body."""
    return _MARKER_TEMPLATE.format(key=suite_key)


def escalation_allowed(ref: str | None) -> bool:
    """Return True only for a run on the mainline ref (exact match, fail-closed)."""
    return ref == MAINLINE_REF


def _non_mainline_summary(suite_key: str, ref: str | None) -> str:
    return f"skipped nightly P0 escalation for {suite_key!r}: ref {ref!r} is not {MAINLINE_REF!r} (branch runs never open, bump or close a P0)"


def _run_reference(run_url: str | None) -> str:
    return run_url if run_url else _RUN_LINK_UNKNOWN


def issue_title(suite_key: str) -> str:
    """Return the standing issue title for a suite key."""
    return _ISSUE_TITLE_TEMPLATE.format(key=suite_key)


def issue_body(suite_key: str, run_url: str | None, *, report: XunitRead | None = None) -> str:
    """Return the body for a freshly created escalation issue (carries the marker)."""
    body = (
        f"The nightly `{suite_key}` suite failed on {_run_reference(run_url)}.\n\n"
        "This issue was opened automatically by the nightly red -> P0 escalation "
        "(`scripts/ci/nightly_escalation.py`, FR-007). It is deduped by the hidden "
        "marker below; a later failure comments here instead of opening a duplicate, "
        "and the next green nightly for this suite closes it automatically.\n\n"
        f"{escalation_marker(suite_key)}\n"
    )
    if report is None:
        return body
    marker = escalation_marker(suite_key)
    body = body.replace(marker, issue_evidence(report) + marker, 1)
    if report.problem is None:
        return with_recorded_ids(body, [item.test_id for item in report.failures])
    return body


def _recurrence_comment(suite_key: str, run_url: str | None, *, report: XunitRead | None = None, previous_body: str = "") -> str:
    text = f"The nightly `{suite_key}` suite failed again on {_run_reference(run_url)}."
    if report is None:
        return text
    return text + recurrence_evidence(previous_body, report)


def _recovery_comment(suite_key: str, run_url: str | None) -> str:
    return f"The nightly `{suite_key}` suite passed on {_run_reference(run_url)}; closing this escalation."


class IssueClient(Protocol):
    """The GitHub-issue operations the escalation flow depends on (mockable)."""

    def find_open_issue_by_marker(self, marker: str) -> dict[str, Any] | None: ...

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> dict[str, Any]: ...

    def comment_on_issue(self, number: int, body: str) -> dict[str, Any]: ...

    def close_issue(self, number: int) -> dict[str, Any]: ...

    def add_labels(self, number: int, labels: Sequence[str]) -> list[dict[str, Any]]: ...

    def set_issue_type(self, number: int, type_name: str) -> dict[str, Any]: ...

    def find_milestone_number(self, title: str) -> int | None: ...

    def set_milestone(self, number: int, milestone_number: int) -> dict[str, Any]: ...

    def add_sub_issue(self, parent_number: int, sub_issue_id: int) -> dict[str, Any]: ...

    def update_issue_body(self, number: int, body: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Triage (#5517): each step fills one missing field, verifies GitHub kept it,
# and raises EscalationError otherwise. GitHub silently DROPS labels, type and
# milestone it will not let the caller set, so a 2xx alone is not proof.
# ---------------------------------------------------------------------------
def _emit_warning(message: str) -> None:
    """Report a degraded step loudly: a ``::warning::`` annotation on the run."""
    print(f"::warning title={_WARNING_TITLE}::{message}", file=sys.stderr)


def _label_names(labels: Any) -> set[str]:
    if not isinstance(labels, list):
        return set()
    return {str(label.get("name")) if isinstance(label, dict) else str(label) for label in labels}


def _field_name(issue: Any, field: str, attribute: str) -> str | None:
    """Return ``issue[field][attribute]`` (e.g. the type's name), or ``None``."""
    value = issue.get(field) if isinstance(issue, dict) else None
    return value.get(attribute) if isinstance(value, dict) else None


def _ensure_labels(client: IssueClient, number: int, issue: dict[str, Any]) -> None:
    missing = [label for label in ESCALATION_LABELS if label not in _label_names(issue.get("labels"))]
    if not missing:
        return
    applied = _label_names(client.add_labels(number, missing))
    dropped = [label for label in missing if label not in applied]
    if dropped:
        raise EscalationError(f"GitHub did not apply label(s) {dropped} ({_PUSH_ACCESS_HINT})")


def _ensure_issue_type(client: IssueClient, number: int, issue: dict[str, Any]) -> None:
    if issue.get("type"):
        return  # a type is already set; never override a human's triage
    updated = client.set_issue_type(number, BUG_ISSUE_TYPE)
    if _field_name(updated, "type", "name") != BUG_ISSUE_TYPE:
        raise EscalationError(f"GitHub accepted the request but did not set type {BUG_ISSUE_TYPE!r} ({_PUSH_ACCESS_HINT})")


def _ensure_milestone(client: IssueClient, number: int, issue: dict[str, Any]) -> None:
    if issue.get("milestone"):
        return  # a milestone is already set; never override a human's triage
    milestone_number = client.find_milestone_number(MILESTONE_TITLE)
    if milestone_number is None:
        raise EscalationError(f"no open milestone titled {MILESTONE_TITLE!r}")
    updated = client.set_milestone(number, milestone_number)
    if _field_name(updated, "milestone", "title") != MILESTONE_TITLE:
        raise EscalationError(f"GitHub accepted the request but did not set milestone {MILESTONE_TITLE!r} ({_PUSH_ACCESS_HINT})")


def _ensure_parent(client: IssueClient, number: int, issue: dict[str, Any]) -> None:
    if issue.get("parent_issue_url"):
        return  # already a sub-issue of some parent; never re-parent it
    issue_id = issue.get("id")
    # sub_issue_id is the issue's numeric database id, NOT its number.
    if not isinstance(issue_id, int) or isinstance(issue_id, bool):
        raise EscalationError(f"issue #{number} carries no numeric database id to link")
    client.add_sub_issue(PARENT_ISSUE_NUMBER, issue_id)


_TriageStep = Callable[[IssueClient, int, dict[str, Any]], None]
_TRIAGE_STEPS: tuple[tuple[str, _TriageStep], ...] = (
    ("labels", _ensure_labels),
    ("issue type", _ensure_issue_type),
    ("milestone", _ensure_milestone),
    (f"parent #{PARENT_ISSUE_NUMBER}", _ensure_parent),
)
# A malformed API response surfaces as one of these; it degrades one step, never the filing.
_TRIAGE_FAILURES = (EscalationError, LookupError, TypeError, ValueError, AttributeError)


def triage_issue(client: IssueClient, issue: dict[str, Any], *, warn: Callable[[str], None] = _emit_warning) -> list[str]:
    """Fill in the escalation triage ``issue`` lacks; return the names of failed steps.

    Every step runs independently: a failure is reported through ``warn`` and
    the remaining steps still run. Nothing here can undo or abort the filing.
    """
    number = int(issue["number"])
    failed: list[str] = []
    for step_name, step in _TRIAGE_STEPS:
        try:
            step(client, number, issue)
        except _TRIAGE_FAILURES as exc:
            warn(f"issue #{number} is filed, but setting its {step_name} failed: {exc}. Triage that field by hand.")
            failed.append(step_name)
    return failed


def _triage_note(failed: list[str]) -> str:
    return f" (triage incomplete: {', '.join(failed)})" if failed else ""


def _record_failure_ids(client: IssueClient, number: int, previous_body: str, report: XunitRead | None, warn: Callable[[str], None]) -> None:
    """Store this run's failure ids on the issue so the next recurrence can diff them."""
    if report is None or report.problem is not None:
        return
    try:
        client.update_issue_body(number, with_recorded_ids(previous_body, [item.test_id for item in report.failures]))
    except EscalationError as exc:
        warn(f"issue #{number} was commented, but recording its failing tests failed: {exc}")


def run_escalation(
    client: IssueClient,
    *,
    suite_key: str,
    conclusion: str,
    ref: str | None,
    run_url: str | None = None,
    report: XunitRead | None = None,
    warn: Callable[[str], None] = _emit_warning,
) -> str:
    """Apply the dedup/open/close policy for one suite; return a human summary.

    Pure orchestration over an :class:`IssueClient` -- the unit tests drive it
    with a fake client to cover create / update-existing / close-on-green.
    ``ref`` is required (no default) so no caller can bypass the mainline
    gate by omission: a non-mainline ref returns before the client is touched.
    A filed or bumped issue is then triaged (:func:`triage_issue`); a triage
    failure is reported through ``warn`` and noted in the summary, never raised.
    """
    if not escalation_allowed(ref):
        return _non_mainline_summary(suite_key, ref)

    marker = escalation_marker(suite_key)
    existing = client.find_open_issue_by_marker(marker)

    if conclusion == CONCLUSION_FAILURE:
        if existing is not None:
            number = int(existing["number"])
            previous = str(existing.get("body") or "")
            client.comment_on_issue(number, _recurrence_comment(suite_key, run_url, report=report, previous_body=previous))
            _record_failure_ids(client, number, previous, report, warn)
            failed = triage_issue(client, existing, warn=warn)
            return f"updated existing escalation issue #{number} for {suite_key!r}{_triage_note(failed)}"
        created = client.create_issue(
            title=issue_title(suite_key),
            body=issue_body(suite_key, run_url, report=report),
            labels=list(ESCALATION_LABELS),
        )
        failed = triage_issue(client, created, warn=warn)
        return f"created escalation issue #{int(created['number'])} for {suite_key!r}{_triage_note(failed)}"

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
        self._repo_url = f"{_API_ROOT}/repos/{repository}"

    def _issue_url(self, number: int) -> str:
        return f"{self._repo_url}/{_ISSUES_PATH}/{number}"

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
        url = f"{self._repo_url}/{_ISSUES_PATH}"
        return cast("dict[str, Any]", self._request("POST", url, {"title": title, "body": body, "labels": list(labels)}))

    def comment_on_issue(self, number: int, body: str) -> dict[str, Any]:
        return cast("dict[str, Any]", self._request("POST", f"{self._issue_url(number)}/comments", {"body": body}))

    def close_issue(self, number: int) -> dict[str, Any]:
        return cast("dict[str, Any]", self._request("PATCH", self._issue_url(number), {"state": "closed"}))

    def add_labels(self, number: int, labels: Sequence[str]) -> list[dict[str, Any]]:
        return cast("list[dict[str, Any]]", self._request("POST", f"{self._issue_url(number)}/labels", {"labels": list(labels)}))

    def set_issue_type(self, number: int, type_name: str) -> dict[str, Any]:
        return cast("dict[str, Any]", self._request("PATCH", self._issue_url(number), {"type": type_name}))

    def find_milestone_number(self, title: str) -> int | None:
        # One page of open milestones: a repository keeps far fewer than 100 open.
        result = self._request("GET", f"{self._repo_url}/milestones?state=open&per_page=100")
        milestones = result if isinstance(result, list) else []
        for milestone in milestones:
            if isinstance(milestone, dict) and milestone.get("title") == title:
                return int(milestone["number"])
        return None

    def set_milestone(self, number: int, milestone_number: int) -> dict[str, Any]:
        return cast("dict[str, Any]", self._request("PATCH", self._issue_url(number), {"milestone": milestone_number}))

    def add_sub_issue(self, parent_number: int, sub_issue_id: int) -> dict[str, Any]:
        url = f"{self._issue_url(parent_number)}/sub_issues"
        return cast("dict[str, Any]", self._request("POST", url, {"sub_issue_id": sub_issue_id}))

    def update_issue_body(self, number: int, body: str) -> dict[str, Any]:
        return cast("dict[str, Any]", self._request("PATCH", self._issue_url(number), {"body": body}))


def _redact(text: str, token: str) -> str:
    return text.replace(token, "[redacted]") if token else text


def resolve_token() -> str | None:
    """Return the Actions token from ``GH_TOKEN``/``GITHUB_TOKEN`` (or ``None``)."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    return None


def _report_for(suite_key: str, conclusion: str, xunit: str | None) -> XunitRead | None:
    """Load the suite report for a red run. A green run does not need it."""
    if conclusion != CONCLUSION_FAILURE or not xunit:
        return None
    report = read_xunit(Path(xunit))
    if report.problem:
        _emit_warning(f"{suite_key}: {report.problem}")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Always exits ``0`` on a missing token / API error."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--suite-key", required=True, help="stable dedup key for the nightly suite (e.g. 'integration')")
    parser.add_argument("--conclusion", required=True, choices=(CONCLUSION_SUCCESS, CONCLUSION_FAILURE), help="the suite's conclusion")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repo (default: $GITHUB_REPOSITORY)")
    parser.add_argument("--run-url", default=None, help="link to the failing/passing workflow run")
    parser.add_argument("--xunit", default=None, help="junit xml the suite wrote; missing or unreadable degrades to the exit-code message")
    parser.add_argument(
        "--ref",
        default=os.environ.get("GITHUB_REF"),
        help=f"the run's git ref (default: $GITHUB_REF); only {MAINLINE_REF} escalates",
    )
    args = parser.parse_args(argv)

    if not escalation_allowed(args.ref):
        # Checked before the token so a branch run never builds an API client.
        print(_non_mainline_summary(args.suite_key, args.ref))
        return EXIT_OK

    token = resolve_token()
    if not token or not args.repo:
        # Fail-closed toward the workflow: degrade to fail-loud-only (the suite's
        # own red already failed its job). Never echo the token.
        missing = "GitHub token" if not token else "repository (--repo / $GITHUB_REPOSITORY)"
        print(f"warning: {missing} unavailable; skipping nightly P0 escalation (fail-loud only)", file=sys.stderr)
        return EXIT_OK

    try:
        client = GitHubIssueClient(args.repo, token)
        report = _report_for(args.suite_key, args.conclusion, args.xunit)
        summary = run_escalation(
            client,
            suite_key=args.suite_key,
            conclusion=args.conclusion,
            ref=args.ref,
            run_url=args.run_url,
            report=report,
        )
    except EscalationError as exc:
        print(f"warning: nightly P0 escalation degraded (fail-loud only): {exc}", file=sys.stderr)
        return EXIT_OK
    print(summary)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
