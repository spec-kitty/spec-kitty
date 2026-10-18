"""Scheduled refresh of the architectural battery's per-file timings from nightly junit (#6365).

``.github/ci-shard-timings.json`` -> ``battery_file_durations[<suite>]`` weights the battery
partition (``scripts/ci/battery_partition_plugin.py``) and is checked by
``tests/ci/test_battery_roster_budgets.py``. Charter C-009 forbids capturing it from a local
run: its only valid source is the junit report of a CI battery run, folded in by the canonical
producer (``scripts/ci/capture_shard_timings.py --suite <suite> --from-junit <dir>``). Before
this script nothing ran that producer on a schedule, so the table stayed the 2026-10-01 census
seed while files were added and renamed, and the strict gate went red ("N of M base files have
no timing").

The ``recapture-shard-timings`` job of ``ci-shard-recapture.yml`` runs this script after the
module ``capture`` phase and before ``publish``:

1. **Find the junit.** The most recent completed ``ci-nightly.yml`` runs on ``main`` are
   listed (``gh run list``) and the ``architectural-backstop`` job's report artefact
   (:data:`ARTIFACT_NAME`) is downloaded from each (``gh run download``), newest first, until
   :data:`RUNS_WANTED` runs with at least one junit file are in hand. A run whose artefact is
   missing or expired, or holds no ``*.xml`` (a timed-out job), is skipped.
2. **Capture to a scratch file.** The producer runs in its own subprocess with ``--output`` (the
   committed file is never written by it), one ``--run-id nightly-<id>`` per run, so the
   provenance names the exact CI runs the medians came from.
3. **Decide** (:func:`needs_refresh`). The table is replaced only when the committed one is not
   a junit capture (the census seed), when its file set differs from the fresh capture's (files
   added, renamed or removed), or when it is older than :data:`MAX_AGE_DAYS`. A table whose file
   set is unchanged and recent is left alone, so a nightly run does not churn the proposal with
   new medians every day.
4. **Merge and report.** The battery tables are merged into the working-tree timings file (which
   may already hold the module captures of this run) and folded into the module phase's
   :class:`~scripts.ci.recapture_shard_timings.RecaptureResult`, re-emitted as the step's
   ``drift`` / ``result`` outputs for ``publish``. Exit status is 1 when the refresh failed (no
   usable nightly junit, or an invalid capture); the module captures are still published.

Credentials: the write PAT (``CHARTER_SHARD_RECAPTURE_TOKEN``) must not be in this step's
environment (refused, like the ``capture`` phase). The read-only workflow token arrives as
``GH_TOKEN`` (the job grants ``actions: read``) and is handed only to the two ``gh`` calls; the
producer subprocess runs from the scrubbed environment.

Invoked as ``python -m scripts.ci.recapture_battery_timings --junit-root DIR``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Same path guard as the sibling scripts: ``scripts.ci`` resolves only with the repo root on the path.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci import capture_shard_timings  # noqa: E402  (import after the path guard above)
from scripts.ci import recapture_shard_timings as recapture  # noqa: E402
from kernel.clock import datetime, now_utc, parse_iso, timedelta  # noqa: E402  (src/ is on the path once the producer is imported)

#: The battery suite this script refreshes (the producer's only ``--suite`` choice).
SUITE = "architectural"
#: The nightly workflow, and the artefact its ``architectural-backstop`` job uploads.
NIGHTLY_WORKFLOW = "ci-nightly.yml"
ARTIFACT_NAME = "ci-nightly-architectural-backstop-reports"
#: How many nightly runs feed the per-file median, and how many recent runs are looked at to find them.
RUNS_WANTED = 3
RUNS_SCANNED = 10
#: A table older than this is refreshed even when its file set is unchanged.
MAX_AGE_DAYS = 14
#: The producer only parses junit (no test code runs), so a short bound suffices.
PRODUCER_TIMEOUT_SECONDS = 10 * 60
#: The run-id prefix recorded in the provenance, followed by the GitHub Actions run id.
RUN_ID_PREFIX = "nightly-"

_GH_TOKEN_ENV_VAR = "GH_TOKEN"  # noqa: S105  # env-var name, not a secret value
_DURATIONS_KEY = "battery_file_durations"
_PROVENANCE_KEY = "battery_capture_provenance"
_SCRATCH_NAME = "battery-capture.json"


# --------------------------------------------------------------------------- #
# Pure decisions.                                                             #
# --------------------------------------------------------------------------- #


def suite_tables(payload: Mapping[str, Any], suite: str = SUITE) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """``(durations, provenance)`` of *suite* in *payload*; empty mappings when absent or malformed."""

    def entry(key: str) -> Mapping[str, Any]:
        table = payload.get(key)
        value = table.get(suite) if isinstance(table, Mapping) else None
        return value if isinstance(value, Mapping) else {}

    return entry(_DURATIONS_KEY), entry(_PROVENANCE_KEY)


def is_junit_capture(provenance: Mapping[str, Any], expected_run_ids: Sequence[str] | None = None) -> bool:
    """True when *provenance* records a junit capture by the canonical producer (and, when
    *expected_run_ids* is given, exactly those runs)."""
    if provenance.get("producer") != capture_shard_timings.BATTERY_PRODUCER or provenance.get("source") != "junit":
        return False
    return expected_run_ids is None or provenance.get("run_ids") == list(expected_run_ids)


def needs_refresh(committed: Mapping[str, Any], fresh: Mapping[str, Any], *, now: datetime, max_age_days: int = MAX_AGE_DAYS) -> str | None:
    """Why the committed suite tables should be replaced by *fresh* ones, or ``None`` to keep them.

    *committed* / *fresh* are whole timings payloads; *now* is an aware ``datetime``.
    """
    committed_durations, committed_provenance = suite_tables(committed)
    fresh_durations, _ = suite_tables(fresh)
    if not is_junit_capture(committed_provenance):
        return f"committed table is not a junit capture (producer {committed_provenance.get('producer')!r})"
    if set(committed_durations) != set(fresh_durations):
        added = len(set(fresh_durations) - set(committed_durations))
        removed = len(set(committed_durations) - set(fresh_durations))
        return f"file set changed ({added} added, {removed} removed)"
    captured_at = committed_provenance.get("captured_at")
    try:
        age = now - parse_iso(str(captured_at))
    except (TypeError, ValueError):
        return f"committed captured_at {captured_at!r} is not an ISO timestamp"
    if age > timedelta(days=max_age_days):
        return f"committed table is {age.days} days old (> {max_age_days})"
    return None


def merge_suite(payload: Mapping[str, Any], fresh: Mapping[str, Any], suite: str = SUITE) -> dict[str, Any]:
    """*payload* with *suite*'s two battery tables taken from *fresh* (every other key kept)."""
    durations, provenance = suite_tables(fresh, suite)
    return capture_shard_timings.merge_battery_capture(dict(payload), suite, durations, provenance)


# --------------------------------------------------------------------------- #
# Edges: gh, the producer, the files.                                         #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class JunitRun:
    """One nightly run's downloaded report directory."""

    run_id: str
    directory: Path


def _gh_env(token: str) -> dict[str, str]:
    env = recapture._scrubbed_env()
    env[_GH_TOKEN_ENV_VAR] = token
    return env


def _list_nightly_run_ids(repository: str, token: str) -> list[str]:
    """The most recent completed nightly runs on ``main``, newest first."""
    proc = recapture._run_subprocess_or_die(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repository,
            "--workflow",
            NIGHTLY_WORKFLOW,
            "--branch",
            "main",
            "--status",
            "completed",
            "--limit",
            str(RUNS_SCANNED),
            "--json",
            "databaseId",
        ],
        step="gh run list",
        env=_gh_env(token),
        capture_output=True,
        text=True,
    )
    try:
        runs = json.loads(proc.stdout)
    except ValueError as exc:
        print(f"::error::gh run list returned non-JSON output: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if not isinstance(runs, list):
        print(f"::error::gh run list returned {type(runs).__name__}, not a list", file=sys.stderr)
        raise SystemExit(1)
    return [str(run["databaseId"]) for run in runs if isinstance(run, Mapping) and isinstance(run.get("databaseId"), int)]


def _download(run_id: str, root: Path, repository: str, token: str) -> JunitRun | None:
    """Download one run's battery report into ``root/<run_id>``; ``None`` when it holds no junit."""
    directory = root / run_id
    proc = subprocess.run(
        ["gh", "run", "download", run_id, "--repo", repository, "--name", ARTIFACT_NAME, "--dir", str(directory)],
        env=_gh_env(token),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(f"::notice::nightly run {run_id}: no {ARTIFACT_NAME} artefact ({proc.stderr.strip() or f'exit {proc.returncode}'}) -- skipped")
        return None
    if not any(directory.rglob("*.xml")):
        print(f"::notice::nightly run {run_id}: {ARTIFACT_NAME} holds no junit file -- skipped")
        return None
    return JunitRun(run_id, directory)


def collect_junit_runs(root: Path, repository: str, token: str) -> list[JunitRun]:
    """Up to :data:`RUNS_WANTED` downloaded nightly runs, newest first."""
    runs: list[JunitRun] = []
    for run_id in _list_nightly_run_ids(repository, token):
        if len(runs) == RUNS_WANTED:
            break
        downloaded = _download(run_id, root, repository, token)
        if downloaded is not None:
            runs.append(downloaded)
    return runs


def _run_ids(runs: Sequence[JunitRun]) -> list[str]:
    return [f"{RUN_ID_PREFIX}{run.run_id}" for run in runs]


def capture_fresh(runs: Sequence[JunitRun], scratch: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Run the producer into *scratch*; ``(payload, None)`` on a valid capture, else ``(None, why)``."""
    cmd = [sys.executable, "-m", "scripts.ci.capture_shard_timings", "--suite", SUITE]
    for run, run_id in zip(runs, _run_ids(runs), strict=True):
        cmd += ["--from-junit", str(run.directory), "--run-id", run_id]
    cmd += ["--output", str(scratch)]
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=recapture._scrubbed_env(), check=False, timeout=PRODUCER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return None, f"producer timed out after {PRODUCER_TIMEOUT_SECONDS}s"
    except OSError as exc:
        return None, f"producer could not run ({type(exc).__name__}: {exc})"
    if proc.returncode != 0:
        return None, f"producer exited {proc.returncode}"
    try:
        payload = json.loads(scratch.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"producer output unreadable ({type(exc).__name__})"
    if not isinstance(payload, dict):
        return None, "producer output is not a mapping"
    durations, provenance = suite_tables(payload)
    if not durations or not is_junit_capture(provenance, _run_ids(runs)):
        return None, "producer wrote no junit provenance for these runs"
    return payload, None


# --------------------------------------------------------------------------- #
# The step.                                                                   #
# --------------------------------------------------------------------------- #


def _module_result() -> recapture.RecaptureResult:
    """The module ``capture`` phase's result, or an empty one (with a warning) when it left none."""
    raw = os.environ.get(recapture.RESULT_ENV_VAR, "").strip()
    if not raw:
        print(f"::warning::{recapture.RESULT_ENV_VAR} is empty (the module capture left no result); reporting the battery refresh alone")
        return recapture.RecaptureResult()
    try:
        return recapture.RecaptureResult.from_json(raw)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"::error::{recapture.RESULT_ENV_VAR} is not a recapture result: {exc!r}", file=sys.stderr)
        raise SystemExit(1) from exc


def _with_battery(result: recapture.RecaptureResult, *, refreshed: bool, failure: str | None) -> recapture.RecaptureResult:
    reasons = dict(result.reasons)
    if failure is not None:
        reasons[recapture.battery_reason_key(SUITE)] = failure
    return recapture.RecaptureResult(
        drifted=result.drifted,
        captured=result.captured,
        failed=result.failed,
        deferred=result.deferred,
        reasons=reasons,
        battery_captured=(*result.battery_captured, SUITE) if refreshed else result.battery_captured,
        battery_failed=(*result.battery_failed, SUITE) if failure is not None else result.battery_failed,
    )


def _refresh(junit_root: Path, token: str) -> tuple[bool, str | None]:
    """``(refreshed, failure)`` -- write the fresh tables into the working tree when they are due."""
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    junit_root.mkdir(parents=True, exist_ok=True)
    runs = collect_junit_runs(junit_root, repository, token)
    if not runs:
        return False, f"no {ARTIFACT_NAME} junit in the last {RUNS_SCANNED} completed nightly runs"
    fresh, failure = capture_fresh(runs, junit_root / _SCRATCH_NAME)
    if fresh is None:
        return False, failure
    current = recapture._read_timings()
    why = needs_refresh(current, fresh, now=now_utc())
    if why is None:
        print(f"battery `{SUITE}` timings are current (file set unchanged, captured within {MAX_AGE_DAYS} days) -- left as committed")
        return False, None
    recapture._write_timings(merge_suite(current, fresh))
    print(f"battery `{SUITE}` timings refreshed from runs {', '.join(run.run_id for run in runs)}: {why}")
    return True, None


def run(junit_root: Path) -> int:
    """Refresh the battery tables and re-emit the combined result; 1 when the refresh failed."""
    if recapture._refuse_if_token_present():
        return 1
    token = os.environ.get(_GH_TOKEN_ENV_VAR, "").strip()
    result = _module_result()
    refreshed: bool = False
    failure: str | None = f"{_GH_TOKEN_ENV_VAR} is not set -- cannot download the nightly junit"
    if token:
        refreshed, failure = _refresh(junit_root, token)
    if failure is not None:
        print(f"::error::battery `{SUITE}` timings not refreshed: {failure}", file=sys.stderr)
    combined = _with_battery(result, refreshed=refreshed, failure=failure)
    recapture._write_github_output(drift=str(combined.publishable).lower(), result=combined.to_json())
    if refreshed or failure is not None:
        recapture._write_job_summary(combined.summary_table())
    return 1 if failure is not None else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recapture_battery_timings", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--junit-root", type=Path, required=True, help="scratch directory the nightly junit artefacts are downloaded into")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    return run(args.junit_root)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
