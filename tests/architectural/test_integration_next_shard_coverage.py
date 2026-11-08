"""Every integration + next test file runs exactly once across the nightly shards (#7456, #6787).

``ci-nightly.yml`` runs ``tests/integration`` and ``tests/next`` as four independent
``integration-next-shard-<N>`` jobs. A split is only as good as its boundaries, so this gate proves
against the LIVE tree, on every run, that

1. the shards' files are pairwise disjoint and their union is exactly the enumerated file universe
   (no gap, no duplicate);
2. the node ids pytest really collects for each shard's ``@argsfile`` union to the node ids it
   collects for the unsharded ``pytest tests/integration tests/next``, with no id twice -- so the
   enumeration cannot silently lose a collectable file;
3. no shard is empty, and a new test file lands in exactly one shard;
4. ``ci-nightly.yml`` defines exactly the declared shard jobs, each wired to its own selector call,
   argsfile, exit variable, report, suite key and fail-loud step, and each is in
   ``nightly-summary.needs``.

The self-mutation controls prove the checkers are not vacuous: a dropped file, a duplicated file,
a shard job removed from the workflow and a shard renumbered wrongly are each reported by name.
"""

from __future__ import annotations

import functools
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from scripts.ci.integration_next_shard import (
    JOB_KEY_PREFIX,
    ROOTS,
    SHARD_COUNT,
    SHARD_JOB_KEYS,
    load_file_durations,
    plan_shards,
)
from scripts.ci.shard_select import enumerate_base_files
from tests.architectural._gate_coverage import load_spliced_workflow

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"
_COLLECT_TIMEOUT_SECONDS = 300


def partition_defects(files: Sequence[str], parts: Mapping[str, frozenset[str]]) -> list[str]:
    """One named message per gap, duplicate or empty shard; ``[]`` when every file is owned exactly once."""
    problems = [f"shard {key} owns no file" for key, owned in parts.items() if not owned]
    owners: dict[str, list[str]] = {}
    for key, owned in parts.items():
        for file in owned:
            owners.setdefault(file, []).append(key)
    problems.extend(f"{file} runs in {len(keys)} shards ({', '.join(sorted(keys))})" for file, keys in sorted(owners.items()) if len(keys) > 1)
    problems.extend(f"{file} runs in no shard" for file in sorted(set(files) - set(owners)))
    problems.extend(f"{file} is owned by a shard but is not in the file universe" for file in sorted(set(owners) - set(files)))
    return problems


def _live_files() -> tuple[str, ...]:
    return enumerate_base_files(ROOTS, root=_REPO_ROOT)


def _live_parts() -> dict[str, frozenset[str]]:
    partition = plan_shards(_live_files(), load_file_durations(), SHARD_COUNT)
    return dict(partition.parts)


def workflow_wiring_defects(jobs: Mapping[str, object], summary_needs: Sequence[str]) -> list[str]:
    """One named message per way the nightly workflow's shard jobs disagree with the selector's declaration."""
    problems: list[str] = []
    present = sorted(key for key in jobs if key.startswith(JOB_KEY_PREFIX) or key == "integration-next")
    if present != sorted(SHARD_JOB_KEYS):
        problems.append(f"ci-nightly.yml defines integration-next jobs {present}, expected exactly {sorted(SHARD_JOB_KEYS)}")
    for number, key in enumerate(SHARD_JOB_KEYS, start=1):
        job = jobs.get(key)
        if not isinstance(job, dict):
            continue
        run_text = "\n".join(str(step.get("run") or "") for step in job.get("steps") or [])
        args_file = f"out/reports/integration-next-shard-{number}.args"
        expected = (
            f"integration_next_shard.py --shard {number}/{SHARD_COUNT} --out {args_file}",
            f"pytest @{args_file}",
            "--dist loadfile",
            "-n auto",
            f"--junitxml=out/reports/xunit-nightly-integration-next-shard-{number}.xml",
            f"INTEGRATION_NEXT_SHARD_{number}_EXIT=$code",
            f'--suite-key "{key}"',
            f"--suite-key {key} --xunit out/reports/xunit-nightly-integration-next-shard-{number}.xml",
        )
        problems.extend(f"{key}: expected `{needle}` in its run steps" for needle in expected if needle not in run_text)
        if "-ne 5" in run_text:
            problems.append(f"{key}: a directory lane must not exempt pytest exit 5 (a vanished shard is a lost signal)")
        if key not in summary_needs:
            problems.append(f"{key}: missing from nightly-summary.needs")
    return problems


def test_declared_shard_count_matches_the_job_keys() -> None:
    assert SHARD_COUNT >= 2, "non-vacuity: the lane must be split"
    assert len(SHARD_JOB_KEYS) == SHARD_COUNT
    assert [key.removeprefix(JOB_KEY_PREFIX) for key in SHARD_JOB_KEYS] == [str(n) for n in range(1, SHARD_COUNT + 1)]


def test_every_file_runs_in_exactly_one_shard() -> None:
    files = _live_files()
    assert len(files) >= 150, f"non-vacuity: expected >=150 integration + next test files, enumerated {len(files)}"
    parts = _live_parts()
    assert sorted(parts) == [f"{n}/{SHARD_COUNT}" for n in range(1, SHARD_COUNT + 1)]
    assert partition_defects(files, parts) == []


def test_a_new_test_file_lands_in_exactly_one_shard() -> None:
    files = (*_live_files(), "tests/integration/test_brand_new_file_7456.py")
    parts = plan_shards(files, load_file_durations(), SHARD_COUNT).parts
    assert partition_defects(files, parts) == []
    assert sum("tests/integration/test_brand_new_file_7456.py" in owned for owned in parts.values()) == 1


def test_partition_is_independent_of_enumeration_order() -> None:
    files = _live_files()
    durations = load_file_durations()
    assert plan_shards(files, durations, SHARD_COUNT).parts == plan_shards(tuple(reversed(files)), durations, SHARD_COUNT).parts


def _collect(args: Sequence[str]) -> tuple[str, ...]:
    result = subprocess.run(  # noqa: S603 -- our own interpreter, fixed arguments
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-o", "addopts=", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=_COLLECT_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, f"collection failed ({result.returncode}): {result.stdout[-2000:]}{result.stderr[-2000:]}"
    return tuple(line for line in result.stdout.splitlines() if "::" in line)


@functools.cache
def _collected_full() -> tuple[str, ...]:
    return _collect(ROOTS)


def test_collected_node_ids_of_the_shards_union_to_the_unsharded_selection(tmp_path: Path) -> None:
    full = _collected_full()
    assert len(full) >= 1500, f"non-vacuity: expected >=1500 collected tests, got {len(full)}"
    sharded: list[str] = []
    for key, owned in sorted(_live_parts().items()):
        args_file = tmp_path / f"shard-{key.split('/')[0]}.args"
        args_file.write_text("\n".join(sorted(owned)) + "\n", encoding="utf-8")
        ids = _collect([f"@{args_file}"])
        assert ids, f"shard {key} collected zero tests"
        sharded.extend(ids)
    duplicates = sorted({node for node in sharded if sharded.count(node) > 1})
    assert duplicates == [], f"node ids collected by more than one shard: {duplicates[:5]}"
    assert sorted(sharded) == sorted(full), (
        f"shards miss {sorted(set(full) - set(sharded))[:5]} / add {sorted(set(sharded) - set(full))[:5]} against the unsharded collection"
    )


def test_workflow_shard_jobs_are_wired_consistently() -> None:
    workflow = load_spliced_workflow(_WORKFLOW_PATH)
    jobs = workflow["jobs"]
    assert workflow_wiring_defects(jobs, jobs["nightly-summary"]["needs"]) == []


# ---------------------------------------------------------------------------
# Self-mutation controls (charter Standing Order #5): the checkers above are not vacuous.
# ---------------------------------------------------------------------------


def test_control_a_dropped_file_is_reported() -> None:
    files = _live_files()
    parts = _live_parts()
    victim = sorted(parts["1/4"])[0]
    broken = {key: owned - {victim} for key, owned in parts.items()}
    assert partition_defects(files, broken) == [f"{victim} runs in no shard"]


def test_control_a_duplicated_file_is_reported() -> None:
    files = _live_files()
    parts = _live_parts()
    victim = sorted(parts["1/4"])[0]
    broken = {**parts, "2/4": parts["2/4"] | {victim}}
    assert partition_defects(files, broken) == [f"{victim} runs in 2 shards (1/4, 2/4)"]


def test_control_an_empty_shard_and_a_phantom_file_are_reported() -> None:
    files = _live_files()
    parts = {"1/2": frozenset(files), "2/2": frozenset({"tests/integration/test_phantom.py"})}
    assert partition_defects(files, parts) == ["tests/integration/test_phantom.py is owned by a shard but is not in the file universe"]
    assert partition_defects(files, {"1/2": frozenset(files), "2/2": frozenset()}) == ["shard 2/2 owns no file"]


def test_control_a_shard_job_missing_from_the_workflow_is_reported() -> None:
    jobs = dict(load_spliced_workflow(_WORKFLOW_PATH)["jobs"])
    needs = list(jobs["nightly-summary"]["needs"])
    del jobs[SHARD_JOB_KEYS[-1]]
    problems = workflow_wiring_defects(jobs, needs)
    assert len(problems) == 1 and "expected exactly" in problems[0], problems


def test_control_a_miswired_shard_is_reported() -> None:
    jobs = dict(load_spliced_workflow(_WORKFLOW_PATH)["jobs"])
    needs = [key for key in jobs["nightly-summary"]["needs"] if key != SHARD_JOB_KEYS[0]]
    job = dict(jobs[SHARD_JOB_KEYS[1]])
    job["steps"] = [{**step, "run": str(step.get("run") or "").replace("--shard 2/4", "--shard 1/4")} for step in job["steps"]]
    jobs[SHARD_JOB_KEYS[1]] = job
    problems = workflow_wiring_defects(jobs, needs)
    assert f"{SHARD_JOB_KEYS[0]}: missing from nightly-summary.needs" in problems
    assert any(problem.startswith(f"{SHARD_JOB_KEYS[1]}: expected `integration_next_shard.py --shard 2/4") for problem in problems), problems
