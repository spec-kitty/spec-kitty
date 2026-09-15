"""Select reports belonging to the jobs retained by an exact CI Modules attempt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Actions executes this trusted-checkout script before installing dependencies.
# Resolve from the script, never the caller's cwd or the fetched source PR.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from kernel.clock import datetime  # noqa: E402


ARTIFACT = re.compile(r"module-tests-([A-Za-z0-9._-]+)-shard-([1-9][0-9]*)-of-([1-9][0-9]*)-attempt-([1-9][0-9]*)-reports")
JOB = re.compile(r"(module-tests \(([A-Za-z0-9._-]+) shard ([1-9][0-9]*)/([1-9][0-9]*)\)) / \1")
SKIPPED_MATRIX_PLACEHOLDER = "module-tests (${{ matrix.module }} shard ${{ matrix.shard }})"


def timestamp(value: Any) -> datetime:
    """Require timezone-aware API timestamps; missing evidence is not a match."""
    if not isinstance(value, str):
        raise ValueError("missing execution/upload timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("execution/upload timestamp has no timezone")
    return parsed


def select_artifacts(source: dict[str, Any], jobs: list[dict[str, Any]], artifacts: list[dict[str, Any]]) -> list[str]:
    """Bind same-run reports to each shard's actual execution, including reuse.

    The attempt jobs API projects carried-forward successes into attempt N with
    their original started_at/completed_at. run_attempt alone cannot distinguish
    them from rerun jobs. An upload must belong to that execution interval, and
    its name must never exceed N, even when replaying after attempt N+1.
    """
    executions = {}
    for job in jobs:
        name = job.get("name", "")
        match = JOB.fullmatch(name)
        if match is None:
            # An empty diff-scoped module matrix (ci-modules.yml) skips its
            # test job cleanly and by design; GitHub Actions still emits one
            # placeholder job for that skipped matrix job, carrying the
            # un-interpolated matrix template as its name rather than an
            # expanded shard name. Such a placeholder ran no shard.
            if name == SKIPPED_MATRIX_PLACEHOLDER and job.get("status") == "completed" and job.get("conclusion") == "skipped":
                continue
            if name.startswith("module-tests"):
                raise ValueError("unrecognized module shard job name")
            continue
        key = match.group(2, 3, 4)
        if job.get("run_id") != source["run_id"] or job.get("head_sha") != source["head_sha"] or job.get("run_attempt") != source["run_attempt"]:
            raise ValueError("job does not belong to the requested source run, head and attempt")
        if job.get("status") != "completed":
            raise ValueError("source shard job has not completed")
        interval = timestamp(job.get("started_at")), timestamp(job.get("completed_at"))
        if interval[0] > interval[1] or key in executions:
            raise ValueError("ambiguous source shard execution")
        executions[key] = interval

    selected: dict[tuple[str, ...], str] = {}
    seen_names: set[str] = set()
    for artifact in artifacts:
        match = ARTIFACT.fullmatch(artifact.get("name", ""))
        if match is None or int(match[4]) > source["run_attempt"]:
            continue
        key = match.group(1, 2, 3)
        if key not in executions:
            continue
        if artifact["name"] in seen_names:
            raise ValueError("multiple artifacts share a source report name")
        seen_names.add(artifact["name"])
        run = artifact.get("workflow_run", {})
        if run.get("id") != source["run_id"] or run.get("head_sha") != source["head_sha"]:
            raise ValueError("artifact does not belong to the requested source run and head")
        created = timestamp(artifact.get("created_at"))
        start, end = executions[key]
        if not start <= created <= end or artifact.get("expired") is not False:
            continue
        if key in selected:
            raise ValueError("multiple artifacts belong to the same shard execution")
        selected[key] = artifact["name"]
    return sorted(selected.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("jobs", type=Path)
    parser.add_argument("artifacts", type=Path)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    # gh api --paginate | jq --slurp . produces one object per response page.
    jobs = [job for page in json.loads(args.jobs.read_text(encoding="utf-8")) for job in page["jobs"]]
    artifacts = [artifact for page in json.loads(args.artifacts.read_text(encoding="utf-8")) for artifact in page["artifacts"]]
    names = select_artifacts(source, jobs, artifacts)
    # download-artifact's pinned minimatch supports brace alternatives. Only
    # validated ASCII artifact names enter this expression or GITHUB_OUTPUT.
    pattern = "{" + ",".join(names) + "}" if len(names) > 1 else next(iter(names), "")
    print(f"has-artifacts={str(bool(names)).lower()}")
    print(f"artifact-pattern={pattern}")


if __name__ == "__main__":
    main()
