#!/usr/bin/env python3
"""Deterministic data collector for "WTF happened" executive debriefs.

Stage A of the debrief pipeline (the executive-debrief-generation procedure). This
module NEVER makes editorial judgements — it queries GitHub and emits a single
JSON document of facts. Every number in a rendered debrief must trace back to a
field here; the synthesis stage may only cluster, narrate and label these
facts, never invent an issue or a count.

Two scope modes, one JSON contract:

  * window  — "what landed since <T>": merged PRs + closed issues in a time
              window (the "What landed since Friday morning" style).
  * scope   — "open issues in <milestone/label/query>": the current backlog
              snapshot (the "Milestone 11 overview" style).

The GitHub CLI (`gh`) is invoked with GITHUB_TOKEN unset so it uses the keyring
token (full `repo` scope) rather than a possibly-narrow env token — the same
discipline the maintainer runbook prescribes.

Usage
-----
    # window mode (across both repos)
    python packs/internal/assets/debrief/collect-debrief.py window \
        --repo spec-kitty/spec-kitty --repo spec-kitty/spec-kitty-planning \
        --since 2026-09-26T06:00:00Z --until 2026-09-28T05:50:00Z \
        --out debrief.json

    # scope mode (a milestone)
    python packs/internal/assets/debrief/collect-debrief.py scope \
        --repo spec-kitty/spec-kitty --milestone 11 --out milestone-11.json

The emitted JSON is the sole input to the synthesis stage.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Route timestamps through the kernel clock door (FR-012a/b — no raw stdlib
# datetime or wall-clock reads outside kernel.clock). Resolve src/ from the
# script path (this file sits at packs/internal/assets/debrief/) so the bare
# `python packs/internal/assets/debrief/collect-debrief.py` invocation still
# works with PYTHONPATH unset.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
from kernel.clock import now_utc, now_utc_iso  # noqa: E402

#: gh JSON fields we pull for a PR / issue. Kept narrow and explicit so the
#: contract is stable and the synthesis stage knows exactly what it may cite.
_PR_FIELDS = "number,title,author,mergedAt,labels,url"
_ISSUE_FIELDS = "number,title,author,closedAt,createdAt,labels,url,stateReason,milestone"

#: Priority labels, most-severe first, for the metric tiles.
_PRIORITY_LABELS = ("priority:P0", "priority:P1", "priority:P2", "priority:P3")

#: Per-repo cap on the detail lists (PRs / issues) fetched for clustering and
#: valid_refs. Headline counts use the search total_count, not these lists, so
#: the cap never undercounts a tile — it only bounds the clustered detail.
_LIST_CAP = 1000


class CollectorError(RuntimeError):
    """A gh query failed or returned something unusable — fail closed."""


def _run_gh(args: list[str]) -> str:
    """Run a `gh` command with GITHUB_TOKEN unset; return stdout.

    Factored out as the single subprocess seam so tests can stub it without a
    live network or a real GitHub token.
    """
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)  # keyring token has full repo scope (runbook)
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment guard
        raise CollectorError("gh CLI not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise CollectorError(f"gh {' '.join(args)} failed (exit {exc.returncode}): {exc.stderr.strip()}") from exc
    return proc.stdout


def _gh_json(args: list[str]) -> Any:
    """Run a gh command that emits JSON and parse it, failing closed."""
    raw = _run_gh(args)
    try:
        return json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise CollectorError(f"gh returned non-JSON for {' '.join(args)}") from exc


def _label_names(item: dict[str, Any]) -> list[str]:
    return [label["name"] for label in item.get("labels", [])]


def _priority_of(item: dict[str, Any]) -> str | None:
    # Resolve by severity (the _PRIORITY_LABELS order), not the issue's own
    # label order, so a mislabelled [P1, P0] issue resolves to P0.
    labels = set(_label_names(item))
    for label in _PRIORITY_LABELS:
        if label in labels:
            return label
    return None


def _main_sha(repo: str) -> str:
    """Short SHA of the repo's main tip — anchors the report to a state."""
    sha = _run_gh(["api", f"repos/{repo}/commits/main", "--jq", ".sha"]).strip()
    return sha[:10]


# --------------------------------------------------------------------------- #
# window mode
# --------------------------------------------------------------------------- #
def collect_window(repos: list[str], since: str, until: str) -> dict[str, Any]:
    """Merged PRs + closed/opened issues across `repos` within [since, until]."""
    merged_prs: list[dict[str, Any]] = []
    closed_issues: list[dict[str, Any]] = []
    detail_sampled = False

    for repo in repos:
        merged_search = f"merged:{since}..{until}"
        page = _gh_json(["pr", "list", "--repo", repo, "--state", "merged", "--search", merged_search, "--limit", str(_LIST_CAP), "--json", _PR_FIELDS])
        detail_sampled = detail_sampled or len(page) >= _LIST_CAP
        merged_prs.extend(_normalise_pr(pr, repo) for pr in page)

        closed_search = f"closed:{since}..{until}"
        page = _gh_json(["issue", "list", "--repo", repo, "--state", "closed", "--search", closed_search, "--limit", str(_LIST_CAP), "--json", _ISSUE_FIELDS])
        detail_sampled = detail_sampled or len(page) >= _LIST_CAP
        closed_issues.extend(_normalise_issue(issue, repo) for issue in page)

    # Headline counts come from the search API total_count (exact), NOT len() of
    # the --limit-capped lists, so a large window (e.g. a quarter) is never
    # silently undercounted. The lists above stay capped for clustering,
    # authorship, and valid_refs; `detail_sampled` flags when they are a sample.
    prs_merged = sum(_search_count(r, f"is:pr merged:{since}..{until}") for r in repos)
    issues_closed = sum(_search_count(r, f"is:issue closed:{since}..{until}") for r in repos)
    p0_closed = sum(_search_count(r, f"is:issue closed:{since}..{until} label:priority:P0") for r in repos)
    issues_opened = sum(_search_count(r, f"is:issue created:{since}..{until}") for r in repos)
    p0_open = sum(_open_priority_count(repo, "priority:P0") for repo in repos)

    close_reasons = Counter(issue["close_reason"] for issue in closed_issues)
    authors = Counter(pr["author"] for pr in merged_prs)

    metrics = {
        "prs_merged": prs_merged,
        "issues_closed": issues_closed,
        "issues_closed_by_reason": dict(close_reasons),
        "p0_closed": p0_closed,
        "issues_opened": issues_opened,
        "p0_open": p0_open,
        # True when a detail list hit the fetch cap: headline counts stay exact,
        # but by_reason / authors / clusters are then over a sample of that cap.
        "detail_sampled": detail_sampled,
    }
    return _envelope(
        mode="window",
        repos=repos,
        filters={"since": since, "until": until},
        main_shas={repo: _main_sha(repo) for repo in repos},
        metrics=metrics,
        pull_requests=merged_prs,
        closed_issues=closed_issues,
        open_issues=[],
        authors=dict(authors),
    )


# --------------------------------------------------------------------------- #
# scope mode
# --------------------------------------------------------------------------- #
def collect_scope(
    repos: list[str],
    milestone: str | None,
    label: str | None,
    query: str | None,
) -> dict[str, Any]:
    """Open issues in a milestone / label / free-text query across `repos`."""
    open_issues: list[dict[str, Any]] = []
    for repo in repos:
        args = ["issue", "list", "--repo", repo, "--state", "open", "--limit", "1000", "--json", _ISSUE_FIELDS]
        if milestone:
            args += ["--milestone", milestone]
        if label:
            args += ["--label", label]
        if query:
            args += ["--search", query]
        for issue in _gh_json(args):
            open_issues.append(_normalise_issue(issue, repo))

    by_priority = Counter(i["priority"] for i in open_issues if i["priority"])
    epics = sum(1 for i in open_issues if "epic" in i["labels"])

    metrics = {
        "open_issues": len(open_issues),
        "by_priority": {p: by_priority.get(p, 0) for p in _PRIORITY_LABELS},
        "epics": epics,
    }
    return _envelope(
        mode="scope",
        repos=repos,
        filters={"milestone": milestone, "label": label, "query": query},
        main_shas={repo: _main_sha(repo) for repo in repos},
        metrics=metrics,
        pull_requests=[],
        closed_issues=[],
        open_issues=open_issues,
        authors={},
    )


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _search_count(repo: str, query: str) -> int:
    """Exact count for a repo-scoped search query, via search API total_count.

    `query` carries its own `is:issue`/`is:pr` qualifier so the caller controls
    whether PRs, issues, or both are counted.
    """
    result = _gh_json(["api", "-X", "GET", "search/issues", "-f", f"q=repo:{repo} {query}", "--jq", "{total: .total_count}"])
    return int(result.get("total", 0)) if isinstance(result, dict) else 0


def _search_issue_count(repo: str, search: str) -> int:
    """Exact issue count for a search, via the search API total_count."""
    return _search_count(repo, f"is:issue {search}")


def _open_priority_count(repo: str, label: str) -> int:
    return _search_issue_count(repo, f"is:open label:{label}")


def _normalise_pr(pr: dict[str, Any], repo: str) -> dict[str, Any]:
    return {
        "repo": repo,
        "number": pr["number"],
        "ref": f"#{pr['number']}",
        "title": pr["title"],
        "author": (pr.get("author") or {}).get("login", "unknown"),
        "merged_at": pr.get("mergedAt"),
        "labels": _label_names(pr),
        "url": pr.get("url"),
    }


def _normalise_issue(issue: dict[str, Any], repo: str) -> dict[str, Any]:
    reason = (issue.get("stateReason") or "").lower()
    labels = _label_names(issue)
    # Bucket the close reason the way the debrief tiles do. "duplicate" is not a
    # native GitHub reason, so derive it from the label when present.
    if "duplicate" in labels:
        close_reason = "duplicate"
    elif reason == "completed":
        close_reason = "fixed"
    elif reason == "not_planned":
        close_reason = "not_planned"
    else:
        close_reason = reason or "unknown"
    return {
        "repo": repo,
        "number": issue["number"],
        "ref": f"#{issue['number']}",
        "title": issue["title"],
        "author": (issue.get("author") or {}).get("login", "unknown"),
        "closed_at": issue.get("closedAt"),
        "created_at": issue.get("createdAt"),
        "labels": labels,
        "priority": _priority_of(issue),
        "milestone": (issue.get("milestone") or {}).get("title"),
        "close_reason": close_reason,
        # TODO(verify): linked-PR verification ("closed as fixed" vs "verified
        # fixed") needs a timeline query per issue; until then synthesis must
        # treat close_reason as GitHub's word, not proof of a shipped fix.
        "verified_fixed": None,
        "url": issue.get("url"),
    }


def _envelope(**parts: Any) -> dict[str, Any]:
    """Assemble the final JSON contract, including the hallucination-guard set.

    `valid_refs` is every #ref the collector saw. The synthesis stage MUST
    reject any #ref in its output that is not in this set — that is how the
    pipeline stays honest about not inventing issues.
    """
    refs = sorted(
        {item["ref"] for item in parts["pull_requests"]} | {item["ref"] for item in parts["closed_issues"]} | {item["ref"] for item in parts["open_issues"]}
    )
    return {
        "meta": {
            "generated_at": now_utc_iso(),
            "mode": parts["mode"],
            "repos": parts["repos"],
            "filters": parts["filters"],
            "main_shas": parts["main_shas"],
            # The Method footer is generated from these fields — never typed.
            "method": (
                "Merged PRs and issues were read from GitHub via `gh` "
                f"({parts['mode']} mode) with the filters above; headline counts "
                "come from the search API total, not estimated. Close reason "
                "follows GitHub's own state_reason; 'verified_fixed' (a linked "
                "closing PR) is not yet computed."
                + (
                    " The per-issue/PR detail (clusters, authorship, close-reason "
                    "breakdown) is a sample of the fetch cap for this window; the "
                    "headline counts remain exact."
                    if parts["metrics"].get("detail_sampled")
                    else ""
                )
            ),
        },
        "metrics": parts["metrics"],
        "authors": parts["authors"],
        "pull_requests": parts["pull_requests"],
        "closed_issues": parts["closed_issues"],
        "open_issues": parts["open_issues"],
        "valid_refs": refs,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", action="append", required=True, dest="repos", metavar="OWNER/NAME", help="Repo to include (repeatable).")
    common.add_argument("--out", type=str, default="-", help="Output JSON path, or '-' for stdout (default).")

    win = sub.add_parser("window", parents=[common], help="Time-window debrief.")
    win.add_argument("--since", required=True, help="ISO8601 start (e.g. 2026-09-26T06:00:00Z).")
    win.add_argument("--until", default=None, help="ISO8601 end (default: now, UTC).")

    scope = sub.add_parser("scope", parents=[common], help="Milestone/label/query snapshot.")
    scope.add_argument("--milestone", default=None, help="Milestone number or title.")
    scope.add_argument("--label", default=None, help="Label to filter on.")
    scope.add_argument("--query", default=None, help="Free-text gh search query.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "window":
            until = args.until or now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
            payload = collect_window(args.repos, args.since, until)
        else:
            if not (args.milestone or args.label or args.query):
                raise CollectorError("scope mode needs --milestone, --label, or --query")
            payload = collect_scope(args.repos, args.milestone, args.label, args.query)
    except CollectorError as exc:
        print(f"collect-debrief: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"wrote {args.out} ({len(payload['valid_refs'])} refs)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
