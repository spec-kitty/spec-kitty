"""Translate trusted Actions metadata into the fleet's exact-head comment protocol.

This reporter executes no PR code and never launches a test producer. Workflow
trigger declarations remain the authority for which existing gates apply.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from typing import Any, TypeAlias, cast

import yaml

from scripts.ci.reconcile_retry import retry_with_backoff

PR_WORKFLOWS = frozenset(
    {
        "ci-router.yml",
        "ci-modules.yml",
        "packs.yml",
        "ci-quality.yml",
        "ci-windows.yml",
        "release-readiness.yml",
        "check-spec-kitty-events-alignment.yml",
    }
)
AGGREGATE = "ci-aggregate.yml"
MARKER = "<!-- spec-kitty-actions-verdict-v1 -->"


def applicable_workflows(root: Path, pr: dict[str, Any], paths: list[str]) -> set[str]:
    """Derive the finite existing branch/path policy from trusted workflow YAML."""
    required = set()
    seen = set()
    for path in (root / ".github/workflows").iterdir():
        if path.suffix not in {".yml", ".yaml"}:
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        triggers = doc.get("on", doc.get(True, {}))
        if not isinstance(triggers, dict) or "pull_request" not in triggers:
            continue
        seen.add(path.name)
        trigger = triggers["pull_request"] or {}
        if set(trigger) - {"types", "branches", "paths"}:
            raise ValueError(f"unsupported PR trigger policy in {path.name}")
        branches = trigger.get("branches", ["*"])
        if not any(fnmatch.fnmatchcase(pr["base"]["ref"], p) for p in branches):
            continue
        patterns = trigger.get("paths")
        if patterns and not any(fnmatch.fnmatchcase(p, pattern) for p in paths for pattern in patterns):
            continue
        required.add(path.name)
    if seen != PR_WORKFLOWS:
        raise ValueError(f"PR workflow inventory changed: {sorted(seen ^ PR_WORKFLOWS)}")
    return required


def latest_run(runs: list[dict[str, Any]], *, workflow_id: int, repository: str, head: str, number: int, name: str) -> dict[str, Any] | None:
    valid = [
        r
        for r in runs
        if r.get("workflow_id") == workflow_id
        and r.get("repository", {}).get("full_name") == repository
        and r.get("head_sha") == head
        and r.get("event") == "pull_request"
        and r.get("path") == f".github/workflows/{name}"
        and any(
            p.get("number") == number
            and p.get("head", {}).get("sha") == head
            and p.get("base", {}).get("repo", {}).get("url") == f"https://api.github.com/repos/{repository}"
            for p in r.get("pull_requests", [])
        )
    ]
    return max(valid, key=lambda r: (r["id"], r["run_attempt"]), default=None)


def classify(runs: dict[str, dict[str, Any] | None], labels: set[str]) -> str:
    """Never turn absent, cancelled, skipped or incomplete evidence into green.

    A fully-terminal required set whose only non-success signal is a cancelled run
    (an infra/timeout kill, not a code failure) is ``infra-error``: never green, and
    never premature — every required run must be terminal first. It ranks after red
    (a real failure dominates a co-cancelled run), after deferred (an intentional skip
    label wins), and after the incomplete check (a pending or absent run stays running).
    """
    present = [r for r in runs.values() if r]
    if any(r.get("status") == "completed" and r.get("conclusion") in {"failure", "timed_out", "startup_failure", "action_required"} for r in present):
        return "red"
    if labels & {"pr:deferred", "pr:skip-ci"}:
        return "running"
    if not runs or len(present) != len(runs):
        return "running"
    if all(r.get("status") == "completed" for r in present) and any(r.get("conclusion") == "cancelled" for r in present):
        return "infra-error"
    return "green" if all(r.get("status") == "completed" and r.get("conclusion") == "success" for r in present) else "running"


def _http_failure(error: urllib.error.HTTPError, token: str) -> str:
    """Expose bounded GitHub diagnostics without credentials or raw responses."""
    message: Any = None
    try:
        with error:
            payload = json.loads(error.read(4096))
        if isinstance(payload, dict):
            message = payload.get("message")
    except (OSError, ValueError, RecursionError):
        pass

    def bounded(value: Any, limit: int) -> str:
        text = value if isinstance(value, str) else "unavailable"
        if token:
            text = text.replace(token, "[redacted]")
        # Quote control characters before bounding the final emitted text.
        return json.dumps(text, ensure_ascii=True)[:limit]

    headers = error.headers
    return (
        f"GitHub API HTTP {error.code}: message={bounded(message, 512)}; "
        f"request_id={bounded(headers.get('X-GitHub-Request-Id') if headers else None, 128)}; "
        f"accepted_permissions={bounded(headers.get('X-Accepted-GitHub-Permissions') if headers else None, 256)}"
    )


class GitHub:
    """Small authenticated API boundary; errors never include credentials."""

    def __init__(self, repository: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("invalid repository")
        self.repository = repository

    def request(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        token = os.environ["GH_TOKEN"]
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}/{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise ValueError(_http_failure(error, token)) from None

    def pages(self, path: str, field: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for page in range(1, 101):
            separator = "&" if "?" in path else "?"
            result = self.request(f"{path}{separator}per_page=100&page={page}")
            batch = result[field] if field else result
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise ValueError("API result exceeded bounded pagination; refusing incomplete evidence")


class GitHubCLI(GitHub):
    """Use an operator host's existing gh authentication, including its proxy."""

    def __init__(self, repository: str, *, wrapper: Path | None = None) -> None:
        super().__init__(repository)
        if wrapper is not None and not (wrapper.is_absolute() and wrapper.is_file() and os.access(wrapper, os.R_OK)):
            raise ValueError("gh API wrapper must be an absolute readable file")
        self.wrapper = wrapper

    def request(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        command = ["bash", str(self.wrapper)] if self.wrapper is not None else ["gh"]
        command.extend(["api", f"repos/{self.repository}/{path}"])
        with ExitStack() as resources:
            input_text = json.dumps(payload) if payload is not None else None
            if payload is not None:
                input_path = "-"
                if self.wrapper is not None:
                    # The canonical host wrapper retries gh, but cannot rewind stdin.
                    # NamedTemporaryFile is private (0600) and removed on every exit.
                    body = resources.enter_context(tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="spec-kitty-ci-", suffix=".json"))
                    body.write(input_text or "")
                    body.flush()
                    input_path, input_text = body.name, None
                command.extend(["--method", "POST", "--input", input_path])
            try:
                result = subprocess.run(command, input=input_text, capture_output=True, text=True, timeout=60)
            except (OSError, subprocess.TimeoutExpired):
                raise ValueError("gh API request could not complete") from None
            if result.returncode:
                # gh may print authentication diagnostics; never echo its captured output.
                raise ValueError(f"gh API request failed (exit {result.returncode})")
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                raise ValueError("gh API response was not valid JSON") from None


def verify_replay_checkout(root: Path, replay: dict[str, Any]) -> None:
    """An explicit replay may execute only the exact, clean reviewed revision."""
    sha = replay["reporter_sha"]
    if not isinstance(sha, str) or not re.fullmatch("[0-9a-f]{40}", sha):
        raise ValueError("replay requires a full reviewed reporter SHA")
    for key in ("host", "session"):
        if not isinstance(replay[key], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", replay[key]):
            raise ValueError(f"replay requires an explicit valid {key}")
    if type(replay["aggregate_run_id"]) is not int or replay["aggregate_run_id"] <= 0:
        raise ValueError("replay requires a positive aggregate run id")
    current = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"], text=True)
    if current != sha or dirty:
        raise ValueError("replay checkout is not the exact clean reviewed revision")


def snapshot(api: GitHub, root: Path, number: int, workflow_ids: dict[str, int], replay: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    pr = api.request(f"pulls/{number}")
    head = pr["head"]["sha"]
    if pr["state"] != "open" or not re.fullmatch("[0-9a-f]{40}", head):
        raise ValueError("PR is closed or has an invalid head")
    files = api.pages(f"pulls/{number}/files")
    if len({p["filename"] for p in files}) != pr["changed_files"]:
        raise ValueError("PR file list is incomplete; required gates cannot be determined")
    paths = [p["filename"] for p in files] + [p["previous_filename"] for p in files if "previous_filename" in p]
    required = applicable_workflows(root, pr, paths)
    runs: dict[str, Any] = {}
    found = api.pages(f"actions/runs?head_sha={head}&event=pull_request", "workflow_runs")
    for name in sorted(required):
        runs[name] = latest_run(found, workflow_id=workflow_ids[name], repository=api.repository, head=head, number=number, name=name)
    modules = runs.get("ci-modules.yml")
    runs[AGGREGATE] = None
    if modules:
        title = f"CI Aggregate source {modules['id']} attempt {modules['run_attempt']}"
        if replay is not None:
            aggregate = api.request(f"actions/runs/{replay['aggregate_run_id']}")
            if (
                aggregate.get("id") != replay["aggregate_run_id"]
                or aggregate.get("event") != "workflow_dispatch"
                or aggregate.get("head_sha") != replay["reporter_sha"]
                or aggregate.get("display_title") != title
                or aggregate.get("workflow_id") != workflow_ids[AGGREGATE]
                or aggregate.get("path") != f".github/workflows/{AGGREGATE}"
                or aggregate.get("repository", {}).get("full_name") != api.repository
            ):
                raise ValueError("manual aggregate does not bind the reviewed reporter and current source attempt")
            runs[AGGREGATE] = aggregate
        else:
            runs[AGGREGATE] = automatic_aggregate(api, workflow_ids[AGGREGATE], modules, title)
    elif replay is not None:
        raise ValueError("manual aggregate has no matching current source run")
    labels = {label["name"] for label in pr["labels"]}
    state = classify(runs, labels)
    evidence = {name: ({k: run.get(k) for k in ("id", "run_attempt", "status", "conclusion", "html_url")} if run else None) for name, run in sorted(runs.items())}
    result = {"head": head, "state": state, "runs": evidence, "labels": sorted(labels)}
    if replay is not None:
        result["replay"] = dict(replay)
    return pr, result


def automatic_aggregate(api: GitHub, workflow_id: int, modules: dict[str, Any], title: str) -> dict[str, Any] | None:
    """Find only the normal default-branch workflow_run aggregate evidence."""
    created = modules.get("created_at", "")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", created):
        raise ValueError("source run creation time missing; cannot bound aggregate lookup")
    query = urllib.parse.urlencode({"event": "workflow_run", "created": ">=" + created})
    aggregates = api.pages(f"actions/workflows/{workflow_id}/runs?{query}", "workflow_runs")
    matching = [
        r
        for r in aggregates
        if r.get("display_title") == title
        and r.get("workflow_id") == workflow_id
        and r.get("path") == f".github/workflows/{AGGREGATE}"
        and r.get("event") == "workflow_run"
        and r.get("repository", {}).get("full_name") == api.repository
    ]
    return max(matching, key=lambda r: (r["id"], r["run_attempt"]), default=None)


def comment_body(repository: str, evidence: dict[str, Any], reporter_id: int, attempt: int) -> str:
    state, head = evidence["state"], evidence["head"]
    provenance = evidence.get("replay", {})
    host = provenance.get("host", "github-actions")
    session = provenance.get("session", f"github-actions-{reporter_id}")
    scope = "main-push head" if evidence.get("scope") == "continuous-main-push" else "PR head"
    lines = [f"[ci] {state} @{head} on {host}", "", MARKER, f"Existing Actions gates for this exact {scope}; no additional test run.", ""]
    if state == "running":
        lines.append("Evidence is pending, incomplete, cancelled, or intentionally deferred; this is not a code failure verdict.")
    elif state == "infra-error":
        lines.append("A required run was cancelled (an infra or timeout kill), not a code failure; re-run the cancelled gate to release the head.")
    for name, run in evidence["runs"].items():
        lines.append(
            f"- {name}: {run['status']}/{run['conclusion']} ({run['html_url']}, attempt {run['run_attempt']})" if run else f"- {name}: awaiting matching run"
        )
    lines.extend(
        [
            "",
            "<!-- evidence: " + json.dumps(evidence, sort_keys=True) + " -->",
            "",
            "Verdict-Role: ci",
            "Verdict-Account-Class: bot",
            f"Verdict-Session: {session}",
            f"Verdict-Repo: {repository}",
            f"Verdict-Head: {head}",
            f"Verdict-Host: {host}",
            f"Verdict-Attempt: {attempt}",
            "Verdict-Contract-Version: 1",
        ]
    )
    return "\n".join(lines) + "\n"


# Retry-budget pair (PR-MERGED-004): fleet_main.py imports FLEET_MAX_ATTEMPTS,
# fleet_backoff_seconds and AlreadyReported from here rather than redefining them --
# plan.md treats fleet_verdict.py/fleet_main.py as one "fleet-verdict pair" sharing a
# single retry-budget rationale, and this module is already the canonical source
# fleet_main.py imports other shared symbols from (AGGREGATE, PR_WORKFLOWS, GitHub,
# automatic_aggregate, classify, comment_body).
FLEET_MAX_ATTEMPTS = 4


def fleet_backoff_seconds(attempt: int) -> float:
    """2s -> 4s -> 8s (plan.md's Retry Budget Rationale for the fleet-verdict pair)."""
    return float(2.0 * (2 ** (attempt - 1)))


class AlreadyReported:
    """The existing dedupe short-circuit fired; nothing to publish."""


class _Ready:
    """The two snapshots agreed; ready to publish this stabilized evidence."""

    def __init__(self, body: str) -> None:
        self.body = body


_Outcome: TypeAlias = AlreadyReported | _Ready | None


def _already_reported(api: GitHub, number: int, evidence: dict[str, Any]) -> bool:
    """Has an identical-latest-evidence comment already been posted for this head?

    Only identical latest evidence is suppressed. Append changes: editing an older
    comment would preserve created_at and leave a newer stale terminal dominant.
    """
    comments = api.pages(f"issues/{number}/comments")
    fingerprint = "<!-- evidence: " + json.dumps(evidence, sort_keys=True) + " -->"
    latest = next(
        (c for c in reversed(comments) if re.match(r"\[ci\] (?:green|red|running|infra-error|no suite) @" + evidence["head"] + r"\b", c.get("body", ""))), None
    )
    return bool(
        latest
        and latest.get("user", {}).get("type") == "Bot"
        and MARKER in latest.get("body", "")
        and (fingerprint in latest["body"] or (evidence["state"] == "running" and latest["body"].startswith("[ci] running @")))
    )


def _attempt(
    api: GitHub,
    root: Path,
    number: int,
    workflow_ids: dict[str, int],
    reporter_id: int,
    attempt: int,
    replay: dict[str, Any] | None,
) -> _Outcome:
    """One full snapshot -> dedupe-check -> re-snapshot -> compare cycle.

    Retries the WHOLE pair as one unit (FR-002/FR-007/C-003): the two snapshot reads
    below are never partially reused across attempts, and a disagreement here converts
    to ``None`` (a retry signal), never a fall-through publish of stale evidence.
    """
    pr, evidence = snapshot(api, root, number, workflow_ids, replay)
    if _already_reported(api, number, evidence):
        return AlreadyReported()
    final_pr, final_evidence = snapshot(api, root, number, workflow_ids, replay)
    if final_evidence != evidence or final_pr["head"]["sha"] != pr["head"]["sha"]:
        return None
    return _Ready(comment_body(api.repository, evidence, reporter_id, attempt))


def report(
    api: GitHub,
    root: Path,
    number: int,
    workflow_ids: dict[str, int],
    reporter_id: int,
    attempt: int,
    *,
    replay: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> None:
    """PR-MERGED-003 (stated decision): ``dry_run`` is checked AFTER the retry loop
    here, deliberately, unlike ``fleet_main.py::report()`` which checks it BEFORE
    and prints a single unstabilized snapshot. This module's ``--dry-run`` exists
    for manual replay debugging (see ``main()``'s ``--aggregate-run-id`` path),
    where the point is to preview the EXACT comment a live run would post --
    including the already-reported dedup check and the two-snapshot stability
    compare -- so it deliberately pays the same up-to-``FLEET_MAX_ATTEMPTS``x
    ``fleet_backoff_seconds`` backoff latency (worst case ~14s) as a real run.
    ``fleet_main.py``'s ``--dry-run`` is a cheap unstabilized preview instead; that
    asymmetry is intentional, not drafting drift -- do not "fix" one to match the
    other without re-deciding this rationale.
    """
    if replay is not None:
        verify_replay_checkout(root, replay)

    def attempt_once() -> AlreadyReported | _Ready | None:
        return _attempt(api, root, number, workflow_ids, reporter_id, attempt, replay)

    # mypy cannot solve T for Callable[[], T | None] against a Union-returning callback
    # (it joins to `object` instead of `AlreadyReported | _Ready`); attempt_once()'s own
    # signature above is the real, checked contract, so this narrows what mypy could not.
    outcome = cast(
        "AlreadyReported | _Ready | None",
        retry_with_backoff(
            attempt_once,
            max_attempts=FLEET_MAX_ATTEMPTS,
            backoff_seconds=fleet_backoff_seconds,
            sleep=time.sleep,
        ),
    )
    if outcome is None:
        print(f"[ci] deferred (pr #{number}): evidence did not stabilize within retry budget")
        return
    if isinstance(outcome, AlreadyReported):
        return
    if replay is not None:
        verify_replay_checkout(root, replay)
    if dry_run:
        print(outcome.body, end="")
    else:
        api.request(f"issues/{number}/comments", {"body": outcome.body})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path)
    parser.add_argument("--pr", type=int)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--reporter-id", type=int, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--aggregate-run-id", type=int, help="Explicit manual Aggregate replay; never used by automatic reporting")
    parser.add_argument("--reviewed-reporter-sha")
    parser.add_argument("--reporter-host")
    parser.add_argument("--reporter-session")
    parser.add_argument("--gh-cli", action="store_true", help="Use the operator host's existing gh authentication for replay")
    parser.add_argument("--gh-api-wrapper", type=Path, help="Absolute host-side gh-api-retry-exec.sh path for --gh-cli replay")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.gh_api_wrapper is not None and not args.gh_cli:
        parser.error("--gh-api-wrapper requires --gh-cli")
    replay = None
    if args.aggregate_run_id is not None:
        if not args.pr or args.event or not all((args.reviewed_reporter_sha, args.reporter_host, args.reporter_session)):
            parser.error("manual replay requires --pr, reviewed SHA, host and session, without --event")
        replay = {
            "aggregate_run_id": args.aggregate_run_id,
            "reporter_sha": args.reviewed_reporter_sha,
            "host": args.reporter_host,
            "session": args.reporter_session,
        }
    elif args.gh_cli or args.reviewed_reporter_sha or args.reporter_host or args.reporter_session:
        parser.error("operator provenance and gh transport require explicit manual replay")
    api = GitHubCLI(args.repository, wrapper=args.gh_api_wrapper) if args.gh_cli else GitHub(args.repository)
    definitions = api.pages("actions/workflows", "workflows")
    ids = {Path(w["path"]).name: w["id"] for w in definitions if w["path"].startswith(".github/workflows/")}
    if not (PR_WORKFLOWS | {AGGREGATE}) <= ids.keys():
        raise ValueError("required Actions workflow definition missing")
    if args.pr:
        report(api, Path(__file__).resolve().parents[2], args.pr, ids, args.reporter_id, args.attempt, replay=replay, dry_run=args.dry_run)
        return
    event = json.loads(args.event.read_text(encoding="utf-8"))
    trigger = event["workflow_run"]
    name = Path(trigger["path"]).name
    if name not in PR_WORKFLOWS | {AGGREGATE} or trigger["workflow_id"] != ids[name]:
        raise ValueError("unrecognized triggering workflow")
    source = api.request(f"actions/runs/{trigger['id']}")
    if (
        source.get("id") != trigger["id"]
        or source.get("workflow_id") != ids[name]
        or source.get("path") != f".github/workflows/{name}"
        or source.get("repository", {}).get("full_name") != api.repository
    ):
        raise ValueError("triggering run does not match the trusted workflow")
    if name == AGGREGATE:
        match = re.fullmatch(r"CI Aggregate source ([1-9][0-9]*) attempt ([1-9][0-9]*)", source["display_title"])
        if not match or source.get("event") != "workflow_run":
            return
        source = api.request(f"actions/runs/{match.group(1)}")
        if (
            source.get("workflow_id") != ids["ci-modules.yml"]
            or source.get("path") != ".github/workflows/ci-modules.yml"
            or source.get("repository", {}).get("full_name") != api.repository
        ):
            raise ValueError("aggregate source is not CI Modules")
    if source.get("event") == "push" and source.get("head_branch") == "main":
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("main=true\n")
        return
    if source.get("event") != "pull_request" or source.get("repository", {}).get("full_name") != api.repository:
        return
    references = source.get("pull_requests", [])
    if not references:
        # Fork workflow_run payloads can omit PR references. Discover recipients
        # only: latest_run still refuses to use unassociated runs as green proof.
        references = [
            pr
            for pr in api.pages(f"commits/{source['head_sha']}/pulls")
            if pr.get("head", {}).get("sha") == source["head_sha"] and pr.get("base", {}).get("repo", {}).get("full_name") == api.repository
        ]
    numbers = sorted({pr["number"] for pr in references})
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write("prs=" + json.dumps(numbers) + "\n")


if __name__ == "__main__":
    main()
