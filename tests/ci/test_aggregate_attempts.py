"""Execute the shipped collector with a partial rerun's Actions API evidence."""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.ci.test_aggregate_source import ROOT, git, source_fixture

pytestmark = pytest.mark.fast


def test_selector_respects_the_architectural_clock_import_boundary() -> None:
    from tests.architectural.test_clock_import_ban import collect_import_ban_violations

    assert collect_import_ban_violations([ROOT / "scripts/ci/select_source_artifacts.py"]) == []


def test_selector_runs_before_installation_from_an_unrelated_directory(tmp_path: Path) -> None:
    """Aggregate calls bare Python before dependency installation on its trusted checkout."""
    source = {"run_id": 42, "run_attempt": 2, "head_sha": "a" * 40}
    record = artifact("kernel", 1, 1)
    record["workflow_run"]["head_sha"] = source["head_sha"]
    execution = dict(job("kernel", 1), head_sha=source["head_sha"])
    inputs = [source, [{"jobs": [execution]}], [{"artifacts": [record]}]]
    paths = [tmp_path / name for name in ("source.json", "jobs.json", "artifacts.json")]
    for path, value in zip(paths, inputs, strict=True):
        path.write_text(json.dumps(value))
    # Disable site packages, user paths and PYTHONPATH. The source checkout
    # must supply its own zero-dependency clock, regardless of caller cwd.
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(ROOT / "scripts/ci/select_source_artifacts.py"), *map(str, paths)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["has-artifacts=true", f"artifact-pattern={record['name']}"]


def artifact(module: str, attempt: int, artifact_id: int) -> dict:
    return {
        "id": artifact_id,
        "name": f"module-tests-{module}-shard-1-of-1-attempt-{attempt}-reports",
        "expired": False,
        "created_at": f"2026-09-09T0{attempt}:05:00Z",
        "workflow_run": {"id": 42},
    }


def job(module: str, execution_attempt: int) -> dict:
    leaf = f"module-tests ({module} shard 1/1)"
    return {
        "run_id": 42,
        # GitHub projects inherited jobs onto the requested attempt, keeping
        # their original execution timestamps (observed on run 34302853928/2).
        "run_attempt": 2,
        "name": f"{leaf} / {leaf}",
        "status": "completed",
        "conclusion": "success",
        "started_at": f"2026-09-09T0{execution_attempt}:00:00Z",
        "completed_at": f"2026-09-09T0{execution_attempt}:10:00Z",
    }


def skipped_matrix_placeholder() -> dict:
    return {
        "run_id": 42,
        "run_attempt": 2,
        "name": "module-tests (${{ matrix.module }} shard ${{ matrix.shard }})",
        "status": "completed",
        "conclusion": "skipped",
    }


Record = dict[str, Any]
REPOSITORY = "spec-kitty/spec-kitty"
SKIP_RUN_ID = 41
MATCHED_RUN_ID, MATCHED_RUN_ATTEMPT = 42, 2
SKIP_RUN_STARTED_AT = "2026-09-09T00:30:00Z"
EFFECTIVE_SOURCE_OUTPUT = "effective-source-output"
REPOINT_ADVICE = "re-run CI Modules to execute"


def api_key(path: str) -> str:
    """The exact endpoint string the fake ``gh`` keys its responses on."""
    return f"repos/{REPOSITORY}/{path}"


def green_match_marker(run_id: int, attempt: int, created_at: str = "2026-09-09T00:40:00Z") -> Record:
    return {"id": 901, "name": f"ci-green-match-run-{run_id}-attempt-{attempt}", "expired": False, "created_at": created_at, "workflow_run": {"id": SKIP_RUN_ID}}


def selected_modules_record() -> Record:
    return {"id": 900, "name": "selected-modules", "expired": False, "created_at": "2026-09-09T00:35:00Z", "workflow_run": {"id": SKIP_RUN_ID}}


def skip_run_scenario(repo: Path, run: Record, run_id: int) -> tuple[Record, Record]:
    """A CI Modules skip run with the matched run's tested identity but its own merge commit.

    Same parents, different message: a different SHA that names the same
    ``(pr, head, base)``, so the comparison is proven to be on tested identity.
    """
    matched_merge = run["referenced_workflows"][0]["sha"]
    base, head = (git(repo, "rev-parse", f"{matched_merge}^{n}") for n in (1, 2))
    tree = git(repo, "rev-parse", f"{matched_merge}^{{tree}}")
    skip_merge = git(repo, "commit-tree", tree, "-p", base, "-p", head, "-m", "skip run merge")
    git(repo, "update-ref", "refs/spec-kitty-tests/skip-merge", skip_merge)
    skip = copy.deepcopy(run)
    skip["id"], skip["run_attempt"], skip["run_started_at"] = run_id, 1, SKIP_RUN_STARTED_AT
    skip["referenced_workflows"] = [dict(skip["referenced_workflows"][0], sha=skip_merge, path=f"{REPOSITORY}/.github/workflows/module-tests.yml@{skip_merge}")]
    commits = {merge: {"parents": [{"sha": base}, {"sha": head}]} for merge in (matched_merge, skip_merge)}
    return skip, {api_key(f"git/commits/{merge}"): value for merge, value in commits.items()}


def write_fake_gh(bindir: Path) -> None:
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(
        f"#!{sys.executable}\nimport json, os, sys\n"
        "endpoint = next(a for a in sys.argv if a.startswith('repos/'))\n"
        "result = json.load(open(os.environ['FAKE_API']))[endpoint]\n"
        "print('\\n'.join(json.dumps(page) for page in result) if isinstance(result, list) else json.dumps(result))\n"
    )
    gh.chmod(0o755)


def build_api(
    repo: Path,
    run: Record,
    artifacts: list[Record],
    jobs: list[Record],
    source_run_id: int,
    artifacts_by_run: dict[int, list[Record]] | None,
    extra_api: Record | None,
) -> dict[str, Any]:
    pages = [{"jobs": jobs[:1]}, {"jobs": jobs[1:]}]
    api: dict[str, Any] = {
        api_key(f"actions/runs/{MATCHED_RUN_ID}/attempts/{MATCHED_RUN_ATTEMPT}"): run,
        api_key(f"actions/runs/{MATCHED_RUN_ID}/attempts/{MATCHED_RUN_ATTEMPT}/jobs?per_page=100"): pages,
        api_key(f"actions/runs/{MATCHED_RUN_ID}/artifacts?per_page=100"): [{"artifacts": artifacts[:1]}, {"artifacts": artifacts[1:]}],
    }
    if source_run_id != MATCHED_RUN_ID:
        skip, commits = skip_run_scenario(repo, run, source_run_id)
        api[api_key(f"actions/runs/{source_run_id}/attempts/1")] = skip
        api[api_key(f"actions/runs/{source_run_id}/attempts/1/jobs?per_page=100")] = pages
        api[api_key(f"actions/runs/{source_run_id}/artifacts?per_page=100")] = [
            {"artifacts": [selected_modules_record(), green_match_marker(MATCHED_RUN_ID, MATCHED_RUN_ATTEMPT)]}
        ]
        api.update(commits)
    for run_id, listing in (artifacts_by_run or {}).items():
        api[api_key(f"actions/runs/{run_id}/artifacts?per_page=100")] = [{"artifacts": listing}]
    api.update(extra_api or {})
    return api


def resolve_effective_source(
    steps: list[Record], repo: Path, env: dict[str, str], tmp_path: Path, trigger: tuple[int, int]
) -> subprocess.CompletedProcess[str] | None:
    """Run the shipped effective-source step and thread its real outputs into ``env``.

    This models ``${{ steps.effective-source.outputs.* }}`` honestly: the values
    come from the executed step's own ``$GITHUB_OUTPUT``, never from a constant.
    Returns the failed process when the step fails (``collect`` stops there).
    """
    step = next((s for s in steps if s.get("id") == "effective-source"), None)
    if step is None:
        env.update(SOURCE_RUN_ID=str(trigger[0]), SOURCE_RUN_ATTEMPT=str(trigger[1]))
        return None
    out = tmp_path / EFFECTIVE_SOURCE_OUTPUT
    step_env = dict(env, TRIGGER_RUN_ID=str(trigger[0]), TRIGGER_RUN_ATTEMPT=str(trigger[1]), GH_TOKEN="dummy", GITHUB_OUTPUT=str(out))
    result = subprocess.run(["bash", "-c", step["run"]], cwd=repo, env=step_env, capture_output=True, text=True)
    if result.returncode:
        return result
    outputs = dict(line.split("=", 1) for line in out.read_text().splitlines())
    env.update(SOURCE_RUN_ID=outputs["run-id"], SOURCE_RUN_ATTEMPT=outputs["run-attempt"])
    return None


def collect(
    tmp_path: Path,
    artifacts: list[Record],
    jobs: list[Record],
    *,
    event: str = "workflow_run",
    source_run_id: int = MATCHED_RUN_ID,
    extra_api: Record | None = None,
    artifacts_by_run: dict[int, list[Record]] | None = None,
    patch_api: Callable[[dict[str, Any]], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    repo, run, _ = source_fixture(tmp_path)
    run.update(run_attempt=MATCHED_RUN_ATTEMPT, status="completed", conclusion="success")
    for record in artifacts:
        record["workflow_run"].setdefault("head_sha", run["head_sha"])
    for record in jobs:
        record.setdefault("head_sha", run["head_sha"])
    api_data = build_api(repo, run, artifacts, jobs, source_run_id, artifacts_by_run, extra_api)
    if patch_api:
        patch_api(api_data)
    api = tmp_path / "api.json"
    api.write_text(json.dumps(api_data))
    bindir = tmp_path / "bin"
    write_fake_gh(bindir)
    (repo / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    output = tmp_path / "outputs"
    env = dict(
        os.environ,
        PATH=f"{bindir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
        FAKE_API=str(api),
        SOURCE_REPOSITORY=REPOSITORY,
        RUNNER_TEMP=str(tmp_path),
        GITHUB_OUTPUT=str(output),
    )
    steps = yaml.safe_load((ROOT / ".github/workflows/ci-aggregate.yml").read_text())["jobs"]["collect"]["steps"]
    trigger = (source_run_id, MATCHED_RUN_ATTEMPT if source_run_id == MATCHED_RUN_ID else 1)
    failed = resolve_effective_source(steps, repo, env, tmp_path, trigger)
    if failed:
        return failed
    prepare = next(s for s in steps if s.get("name", "").startswith("Prepare exact source"))
    result = subprocess.run(["bash", "-c", prepare["run"]], cwd=repo, env=env, capture_output=True, text=True)
    if result.returncode:
        return result
    # The pre-existing reconcile entrypoint consumes the verified registry.
    (repo / "out/aggregate/source/ci-module-registry.yml").write_text(
        "modules:\n- {module: kernel, tier: standard, shard_count: 1}\n- {module: charter, tier: standard, shard_count: 1}\n"
    )
    selection = next((s for s in steps if s.get("id") == "select-current"), None)
    if selection:
        result = subprocess.run(["bash", "-c", selection["run"]], cwd=repo, env=env, capture_output=True, text=True)
        if result.returncode:
            return result
    context = {
        "github.event.workflow_run.run_attempt": "2" if event == "workflow_run" else "",
        "inputs.source_run_attempt": "2" if event == "workflow_dispatch" else "",
    }
    if output.exists():
        context.update({f"steps.select-current.outputs.{k}": v for k, v in (line.split("=", 1) for line in output.read_text().splitlines())})
    download = next(s for s in steps if s.get("id") == "download-current")
    condition = download.get("if")
    should_download = True
    if condition:
        key, expected = condition.split("==")
        should_download = context.get(key.strip()) == expected.strip(" '")
    pattern = re.sub(r"\$\{\{\s*(.*?)\s*\}\}", lambda m: next(context[k.strip()] for k in m[1].split("||") if k.strip() in context), download["with"]["pattern"])
    # Model download-artifact's minimatch against returned names, including
    # brace alternatives. Only this remote action boundary is substituted.
    patterns = pattern[1:-1].split(",") if pattern.startswith("{") else [pattern]
    for record in artifacts:
        if should_download and any(fnmatchcase(record["name"], p) for p in patterns):
            module = record["name"].split("-shard-")[0].removeprefix("module-tests-")
            directory = repo / "out/aggregate/current" / record["name"]
            directory.mkdir(parents=True, exist_ok=True)
            for name in record.get("coverage_names", [f"coverage-standard-{module}-shard1-of-1.xml"]):
                (directory / name).write_text("<coverage/>")
    reconcile = next(s for s in steps if s.get("id") == "reconcile")
    return subprocess.run(["bash", "-c", reconcile["run"]], cwd=repo, env=env, capture_output=True, text=True)


@pytest.mark.parametrize("event", ["workflow_run", "workflow_dispatch"])
def test_partial_rerun_collects_carried_forward_shard_and_latest_replacement(tmp_path: Path, event: str) -> None:
    result = collect(tmp_path, [artifact("kernel", 1, 1), artifact("charter", 1, 2), artifact("charter", 2, 3)], [job("kernel", 1), job("charter", 2)], event=event)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "resolved 2/2" in result.stdout


def test_manual_replay_uses_requested_attempt_after_a_newer_rerun(tmp_path: Path) -> None:
    result = collect(
        tmp_path,
        [artifact("kernel", 1, 1), artifact("charter", 2, 2), artifact("kernel", 3, 3), artifact("charter", 3, 4)],
        [job("kernel", 1), job("charter", 2)],
        event="workflow_dispatch",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_empty_matrix_placeholder_job_contributes_no_execution() -> None:
    """A diff-scoped PR selecting zero modules empties ci-modules.yml's matrix.

    Its test job then skips cleanly (documented, intended), and GitHub Actions
    emits one placeholder job for that skipped matrix job whose name is the
    un-interpolated template, e.g. "module-tests (${{ matrix.module }} shard
    ${{ matrix.shard }})", never an expanded shard name. select_artifacts must
    treat that placeholder as "no shard ran" rather than raise.
    """
    from scripts.ci.select_source_artifacts import select_artifacts

    source = {"run_id": 42, "run_attempt": 2, "head_sha": "a" * 40}
    record = artifact("kernel", 1, 1)
    record["workflow_run"]["head_sha"] = source["head_sha"]
    execution = dict(job("kernel", 1), head_sha=source["head_sha"])
    placeholder = {
        "run_id": 42,
        "run_attempt": 2,
        "head_sha": source["head_sha"],
        "name": "module-tests (${{ matrix.module }} shard ${{ matrix.shard }})",
        "status": "completed",
        "conclusion": "skipped",
    }
    assert select_artifacts(source, [execution, placeholder], [record]) == [record["name"]]


def test_selection_binds_timestamps_inclusively_and_normalizes_offsets() -> None:
    from scripts.ci.select_source_artifacts import select_artifacts

    source = {"run_id": 42, "run_attempt": 2, "head_sha": "a" * 40}
    record = artifact("kernel", 1, 1)
    record["workflow_run"]["head_sha"] = source["head_sha"]
    execution = dict(job("kernel", 1), head_sha=source["head_sha"])
    for created in ("2026-09-09T01:00:00Z", "2026-09-09T01:10:00Z", "2026-09-08T20:05:00-05:00"):
        record["created_at"] = created
        assert select_artifacts(source, [execution], [record]) == [record["name"]]
    for created in ("2026-09-09T00:59:59Z", "2026-09-09T01:10:01Z"):
        record["created_at"] = created
        assert select_artifacts(source, [execution], [record]) == []


def test_skipped_literal_matrix_placeholder_is_a_valid_empty_selection() -> None:
    from scripts.ci.select_source_artifacts import select_artifacts

    source = {"run_id": 42, "run_attempt": 2, "head_sha": "a" * 40}

    assert select_artifacts(source, [skipped_matrix_placeholder()], []) == []


def test_skipped_literal_matrix_placeholder_reaches_reconciliation(tmp_path: Path) -> None:
    result = collect(tmp_path, [], [skipped_matrix_placeholder()])

    assert result.returncode != 0
    assert "unrecognized module shard job name" not in result.stdout + result.stderr
    assert "registry-expected shard(s) missing" in result.stdout


@pytest.mark.parametrize("status,conclusion", [("in_progress", None), ("completed", "success"), ("completed", "failure")])
def test_literal_matrix_placeholder_fails_closed_unless_completed_and_skipped(status: str, conclusion: str | None) -> None:
    from scripts.ci.select_source_artifacts import select_artifacts

    source = {"run_id": 42, "run_attempt": 2, "head_sha": "a" * 40}
    execution = dict(skipped_matrix_placeholder(), status=status, conclusion=conclusion)

    with pytest.raises(ValueError, match="unrecognized module shard job name"):
        select_artifacts(source, [execution], [])


@pytest.mark.parametrize("mutation", ["rerun_without_upload", "expired", "future_only", "absent"])
def test_missing_current_evidence_never_borrows_an_old_report(tmp_path: Path, mutation: str) -> None:
    records = [artifact("kernel", 1, 1), artifact("charter", 2, 2)]
    executions = [job("kernel", 1), job("charter", 2)]
    if mutation == "rerun_without_upload":
        executions[0] = job("kernel", 2)
    elif mutation == "expired":
        records[0]["expired"] = True
    elif mutation == "future_only":
        records[0] = artifact("kernel", 3, 3)
    else:
        records.pop(0)
    result = collect(tmp_path, records, executions)
    assert result.returncode != 0
    assert "registry-expected shard(s) missing" in result.stdout


@pytest.mark.parametrize(
    "mutation,diagnostic",
    [
        ("foreign_run", "artifact does not belong"),
        ("foreign_head", "artifact does not belong"),
        ("job_run", "job does not belong"),
        ("job_head", "job does not belong"),
        ("job_attempt", "job does not belong"),
        ("job_running", "has not completed"),
        ("missing_start", "missing execution/upload timestamp"),
        ("missing_end", "missing execution/upload timestamp"),
        ("missing_created", "missing execution/upload timestamp"),
        ("naive_created", "has no timezone"),
        ("reversed_interval", "ambiguous source shard execution"),
        ("duplicate_job", "ambiguous source shard execution"),
        ("duplicate_artifact", "multiple artifacts"),
        ("duplicate_name_outside_execution", "multiple artifacts"),
        ("duplicate_execution_artifact", "multiple artifacts"),
        ("bad_job_name", "unrecognized module shard job name"),
    ],
)
def test_ambiguous_provenance_fails_closed(mutation: str, diagnostic: str) -> None:
    from scripts.ci.select_source_artifacts import select_artifacts

    source = {"run_id": 42, "run_attempt": 2, "head_sha": "a" * 40}
    record = artifact("kernel", 1, 1)
    record["workflow_run"]["head_sha"] = source["head_sha"]
    execution = dict(job("kernel", 1), head_sha=source["head_sha"])
    records, executions = [record], [execution]
    if mutation in {"foreign_run", "foreign_head"}:
        record["workflow_run"].update({"foreign_run": {"id": 43}, "foreign_head": {"head_sha": "b" * 40}}[mutation])
    elif mutation == "job_run":
        execution["run_id"] = 43
    elif mutation == "job_head":
        execution["head_sha"] = "b" * 40
    elif mutation == "job_attempt":
        execution["run_attempt"] = 3
    elif mutation == "job_running":
        execution["status"] = "in_progress"
    elif mutation == "missing_start":
        execution.pop("started_at")
    elif mutation == "missing_end":
        execution.pop("completed_at")
    elif mutation == "missing_created":
        record.pop("created_at")
    elif mutation == "naive_created":
        record["created_at"] = "2026-09-09T01:05:00"
    elif mutation == "reversed_interval":
        execution["completed_at"] = "2026-09-09T00:00:00Z"
    elif mutation == "duplicate_job":
        executions.append(dict(execution))
    elif mutation == "duplicate_artifact":
        records.append(dict(record, id=2))
    elif mutation == "duplicate_name_outside_execution":
        records.append(dict(record, id=2, created_at="2026-09-09T02:05:00Z"))
    elif mutation == "duplicate_execution_artifact":
        records.append(dict(record, id=2, name=record["name"].replace("attempt-1", "attempt-2")))
    else:
        execution["name"] = "module-tests (kernel shard 1/1) / other"
    with pytest.raises(ValueError, match=diagnostic):
        select_artifacts(source, executions, records)


def test_selector_cli_outputs_safe_patterns_for_empty_or_one_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from scripts.ci.select_source_artifacts import main

    source = {"run_id": 42, "run_attempt": 2, "head_sha": "a" * 40}
    record = artifact("kernel", 1, 1)
    record["workflow_run"]["head_sha"] = source["head_sha"]
    execution = dict(job("kernel", 1), head_sha=source["head_sha"])
    paths = [tmp_path / name for name in ("source.json", "jobs.json", "artifacts.json")]
    paths[0].write_text(json.dumps(source))
    paths[1].write_text(json.dumps([{"jobs": [{"name": "Generate module-shard matrix"}]}, {"jobs": [execution]}]))
    monkeypatch.setattr(sys, "argv", ["select_source_artifacts.py", *map(str, paths)])
    for records, pattern in (([], ""), ([record], record["name"])):
        paths[2].write_text(json.dumps([{"artifacts": [{"name": "unrelated-report"}]}, {"artifacts": records}]))
        main()
        assert capsys.readouterr().out == f"has-artifacts={str(bool(records)).lower()}\nartifact-pattern={pattern}\n"


def test_empty_selection_cannot_download_a_sentinel_named_artifact(tmp_path: Path) -> None:
    forged = {
        "name": "no-source-shard-reports",
        "workflow_run": {"id": 42},
        "coverage_names": ["coverage-standard-kernel-shard1-of-1.xml", "coverage-standard-charter-shard1-of-1.xml"],
    }
    result = collect(tmp_path, [forged], [job("kernel", 1), job("charter", 2)])
    assert result.returncode != 0, "collector accepted unselected coverage from the sentinel-named artifact"
    assert "registry-expected shard(s) missing" in result.stdout


# --- skip-if-green re-point (mission ci-runtime-stabilisation, FR-011) -------------------------


def _read_source_run_id(tmp_path: Path) -> int:
    return int(json.loads((tmp_path / "repo/out/aggregate/source/source.json").read_text())["run_id"])


def _matched_evidence() -> tuple[list[Record], list[Record]]:
    return [artifact("kernel", 1, 1), artifact("charter", 1, 2), artifact("charter", 2, 3)], [job("kernel", 1), job("charter", 2)]


@pytest.mark.parametrize("event", ["workflow_run", "workflow_dispatch"])
def test_green_match_source_is_repointed_to_the_matched_run(tmp_path: Path, event: str) -> None:
    """A skip run (41) carries a marker naming 42/2; Aggregate reads 42/2 (A1; A3 for a dispatch replay)."""
    artifacts, jobs = _matched_evidence()

    result = collect(tmp_path, artifacts, jobs, event=event, source_run_id=SKIP_RUN_ID)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "resolved 2/2" in result.stdout
    assert _read_source_run_id(tmp_path) == MATCHED_RUN_ID
    effective = dict(line.split("=", 1) for line in (tmp_path / EFFECTIVE_SOURCE_OUTPUT).read_text().splitlines())
    assert (effective["run-id"], effective["run-attempt"], effective["repointed"]) == ("42", "2", "true")


def _break_matched_failed(api: dict[str, Any]) -> None:
    api[api_key("actions/runs/42/attempts/2")]["conclusion"] = "failure"


def _break_missing_run(api: dict[str, Any]) -> None:
    del api[api_key("actions/runs/42/attempts/2")]


def _break_different_head(api: dict[str, Any]) -> None:
    api[api_key("actions/runs/42/attempts/2")]["head_sha"] = "b" * 40


def _break_different_workflow(api: dict[str, Any]) -> None:
    api[api_key("actions/runs/42/attempts/2")]["path"] = ".github/workflows/ci-router.yml"


def _break_different_tested_base(api: dict[str, Any]) -> None:
    matched = api[api_key("actions/runs/42/attempts/2")]
    commit = api[api_key(f"git/commits/{matched['referenced_workflows'][0]['sha']}")]
    commit["parents"][0] = {"sha": "c" * 40}


def _break_two_markers(api: dict[str, Any]) -> None:
    listing = api[api_key(f"actions/runs/{SKIP_RUN_ID}/artifacts?per_page=100")]
    listing[0]["artifacts"].append(dict(green_match_marker(43, 1), id=902))


UNVERIFIABLE_MARKERS = {
    "missing-run": _break_missing_run,
    "matched-failed": _break_matched_failed,
    "different-head": _break_different_head,
    "different-workflow": _break_different_workflow,
    "different-tested-base": _break_different_tested_base,
    "two-markers": _break_two_markers,
}


@pytest.mark.parametrize("case", sorted(UNVERIFIABLE_MARKERS))
def test_unverifiable_green_match_fails_collect(tmp_path: Path, case: str) -> None:
    """An unverifiable marker is never an empty-selection green: collect fails and says what to do (A1)."""
    artifacts, jobs = _matched_evidence()

    result = collect(tmp_path, artifacts, jobs, source_run_id=SKIP_RUN_ID, patch_api=UNVERIFIABLE_MARKERS[case])

    assert result.returncode != 0, result.stdout + result.stderr
    assert REPOINT_ADVICE in result.stdout + result.stderr
    assert not (tmp_path / "repo/out/aggregate/source/source.json").exists()


def test_marker_from_an_earlier_attempt_does_not_repoint(tmp_path: Path) -> None:
    """A marker uploaded before the requested attempt started is not this attempt's decision (A4)."""
    own_artifacts = [dict(artifact("kernel", 1, 11), workflow_run={"id": SKIP_RUN_ID}), dict(artifact("charter", 1, 12), workflow_run={"id": SKIP_RUN_ID})]
    own_jobs = [dict(job("kernel", 1), run_id=SKIP_RUN_ID, run_attempt=1), dict(job("charter", 1), run_id=SKIP_RUN_ID, run_attempt=1)]
    stale_marker = green_match_marker(MATCHED_RUN_ID, MATCHED_RUN_ATTEMPT, created_at="2026-09-09T00:10:00Z")

    result = collect(tmp_path, own_artifacts, own_jobs, source_run_id=SKIP_RUN_ID, artifacts_by_run={SKIP_RUN_ID: [stale_marker, *own_artifacts]})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "resolved 2/2" in result.stdout
    assert _read_source_run_id(tmp_path) == SKIP_RUN_ID
    assert "repointed=false" in (tmp_path / EFFECTIVE_SOURCE_OUTPUT).read_text().splitlines()


def test_no_marker_source_is_byte_identical_to_today(tmp_path: Path) -> None:
    """A source without a marker passes through effective-source unchanged (A2)."""
    artifacts, jobs = _matched_evidence()

    result = collect(tmp_path, artifacts, jobs)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "resolved 2/2" in result.stdout
    assert _read_source_run_id(tmp_path) == MATCHED_RUN_ID
    effective = (tmp_path / EFFECTIVE_SOURCE_OUTPUT).read_text().splitlines()
    assert effective[:3] == ["run-id=42", "run-attempt=2", "repointed=false"]
