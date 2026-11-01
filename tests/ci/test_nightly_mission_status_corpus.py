"""Pin the nightly corpus compare against the pinned read-service binary, and that nothing runs ``contracts/tools`` (#6915).

The compare used to live in ``mission-status-api.yml`` ``nightly-corpus``, which built the service jar from ``services/``.
Core now pins one released build (ADR 2026-10-29-1 D-6), so the nightly job fetches the pinned native binary with the
sync-services action, starts it against this checkout and runs ``scripts/ci/mission_status_corpus_compare.py`` (research
D-7). The contract tools are the pinned ``contract-tools`` extra; no workflow step and no script runs a ``contracts/tools``
copy of them any more.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
NIGHTLY = WORKFLOWS / "ci-nightly.yml"
JOB = "mission-status-corpus"
SYNC_SERVICES = "./.github/actions/sync-services"
SYNC_PACKS = "./.github/actions/sync-packs"
COMPARE = "scripts/ci/mission_status_corpus_compare.py"
#: The workflows the cut-over deletes with ``contracts/`` itself (WP06); until then they still run their own copy.
RETIRING_WORKFLOWS = frozenset({"contracts.yml", "contracts-release.yml", "mission-status-api.yml"})
LOCAL_TOOLS = re.compile(r"(?<![\w/.-])contracts/tools/")


def _jobs(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs: dict[str, Any] = loaded["jobs"]
    return jobs


@pytest.fixture(scope="module")
def job() -> dict[str, Any]:
    jobs = _jobs(NIGHTLY)
    assert JOB in jobs, f"ci-nightly.yml has no {JOB} job"
    found: dict[str, Any] = jobs[JOB]
    return found


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = job["steps"]
    return steps


def _index(job: dict[str, Any], predicate: Any, what: str) -> int:
    hits = [i for i, step in enumerate(_steps(job)) if predicate(step)]
    assert len(hits) == 1, f"expected exactly one step that {what}, found {len(hits)}"
    return hits[0]


def _runs(step: dict[str, Any], needle: str) -> bool:
    return needle in str(step.get("run") or "")


def test_the_job_checks_out_full_history_installs_everything_and_syncs_packs(job: dict[str, Any]) -> None:
    checkout = _steps(job)[_index(job, lambda s: str(s.get("uses", "")).startswith("actions/checkout@"), "checks out")]
    assert (checkout.get("with") or {}).get("fetch-depth") == 0, "the oracle reads git history and `git ls-files`"
    _index(job, lambda s: _runs(s, "uv sync --frozen --all-extras"), "installs the fully synced environment")
    _index(job, lambda s: s.get("uses") == SYNC_PACKS, "syncs the packs")


def test_the_job_fetches_the_service_build_not_only_the_extras(job: dict[str, Any]) -> None:
    step = _steps(job)[_index(job, lambda s: s.get("uses") == SYNC_SERVICES, "uses the sync-services action")]
    assert str((step.get("with") or {}).get("extras-only", "false")).lower() != "true", "the compare needs the native binary"


def test_the_job_starts_the_pinned_binary_records_its_pid_and_compares_against_it(job: dict[str, Any]) -> None:
    sync = _index(job, lambda s: s.get("uses") == SYNC_SERVICES, "uses the sync-services action")
    locate = _index(job, lambda s: _runs(s, "SERVICE_BIN=") and _runs(s, "GITHUB_ENV"), "records the binary's cache path")
    start = _index(job, lambda s: _runs(s, '"$SERVICE_BIN"') and _runs(s, "--mission-status.port=8787"), "starts the binary")
    compare = _index(job, lambda s: _runs(s, COMPARE), "runs the compare")
    assert sync < locate < start < compare
    started = str(_steps(job)[start]["run"])
    assert '--mission-status.project-root="$GITHUB_WORKSPACE"' in started
    assert "SERVICE_PID=$!" in started, "the service is stopped by its recorded PID, never by a pattern"
    command = str(_steps(job)[compare]["run"])
    assert "--base-url http://127.0.0.1:8787" in command
    assert '--repo-root "$GITHUB_WORKSPACE"' in command
    assert "--report" in command
    assert "--tools-root" not in command, "the compare reads the pinned tools by default"


def test_the_job_never_builds_the_service(job: dict[str, Any]) -> None:
    text = yaml.safe_dump(job)
    for forbidden in ("gradlew", "setup-java", "setup-graalvm", "java -jar", "services/"):
        assert forbidden not in text, f"the nightly compare runs the pinned binary; it must not touch {forbidden!r}"


def test_the_report_is_uploaded_and_the_service_stopped_always(job: dict[str, Any]) -> None:
    compare = _index(job, lambda s: _runs(s, COMPARE), "runs the compare")
    upload = _index(job, lambda s: str(s.get("uses", "")).startswith("actions/upload-artifact@"), "uploads the report")
    stop = _index(job, lambda s: _runs(s, 'kill "$SERVICE_PID"'), "stops the service")
    assert compare < upload and compare < stop
    for index in (upload, stop):
        assert "always()" in str(_steps(job)[index].get("if", "")), _steps(job)[index]
    path = str((_steps(job)[upload].get("with") or {}).get("path", ""))
    assert "nightly-report.json" in path and "service.log" in path


def test_the_job_is_nightly_only_has_a_timeout_and_is_summarised(job: dict[str, Any]) -> None:
    assert "pull_request" not in yaml.safe_load(NIGHTLY.read_text(encoding="utf-8")).get(True, {}), "ci-nightly.yml has no PR trigger"
    assert 0 < int(job["timeout-minutes"]) <= 45
    summary = _jobs(NIGHTLY)["nightly-summary"]
    assert JOB in summary["needs"], "nightly-summary must list the corpus compare"
    assert f"needs.{JOB}.result" in yaml.safe_dump(summary)


def _run_strings(path: Path) -> list[str]:
    runs: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "run" and isinstance(value, str):
                    runs.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(yaml.safe_load(path.read_text(encoding="utf-8")))
    return runs


def _local_tools_runs() -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        if path.name in RETIRING_WORKFLOWS:
            continue
        found = [run for run in _run_strings(path) if LOCAL_TOOLS.search(run)]
        if found:
            hits[path.name] = found
    for path in sorted((REPO_ROOT / "scripts").rglob("*.sh")):
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if LOCAL_TOOLS.search(line) and not line.lstrip().startswith("#")]
        if lines:
            hits[str(path.relative_to(REPO_ROOT))] = lines
    return hits


def test_no_workflow_step_or_script_runs_a_local_contracts_tools_copy() -> None:
    assert _local_tools_runs() == {}


def test_the_local_tools_scan_sees_a_planted_run() -> None:
    assert LOCAL_TOOLS.search("uv run python contracts/tools/install_tools.py --pins x")
    assert not LOCAL_TOOLS.search('"$(python scripts/sync_services.py --extras-path read-service:contract_tools)/contracts/tools/install_tools.py"')
