"""Fixture tests for ``scripts/ci/quality_gate_decision.py`` (WP02, FR-011).

The quality-gate aggregator guards every merge. This suite pins the decision
table from spec FR-011 / Adjudicated Decision 8 of mission
``ci-suite-map-bind-01KWNPMP`` BEFORE the script goes live in
``ci-quality.yml`` (WP03 wires it):

- FAIL iff ``filter_true AND job_skipped AND NOT full_run AND NOT draft_exempt``
- ``full_run = run_all OR catchall_unmatched``
- ``draft_exempt = job in draft_gated_jobs AND pr_is_draft``
- ``failure`` / ``cancelled`` still FAIL (existing semantics preserved)
- legitimately-skipped (filter false) still OK
- C-005 tripwire: ``quarantine-visibility`` must NEVER be in the blocking
  input set — any appearance is a loud contract error (exit code 2).

Job and group names are the real ones from ``.github/workflows/ci-quality.yml``
(testing doctrine: production-shaped test data). The job→groups mapping is
DATA assembled by the workflow (Decision 8) — a structural test asserts the
script hardcodes no job→group table.
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "quality_gate_decision.py"
_SCRIPT_MODULE_NAME = "quality_gate_decision"

_QUARANTINE_JOB = "quarantine-visibility"

#: Populated by the autouse ``_quality_gate_decision_module`` fixture below.
QGD: Any


@pytest.fixture(scope="module", autouse=True)
def _quality_gate_decision_module() -> Iterator[ModuleType]:
    """Load the script once for this module's tests.

    Dataclass field resolution on Python 3.11 looks the module up in
    ``sys.modules`` while the class body is being executed, so it must
    already be registered before ``exec_module`` runs. A module-scoped
    ``pytest.MonkeyPatch.context()`` — not the function-scoped ``monkeypatch``
    fixture, which a module-scoped fixture cannot depend on — keeps that
    registration and undoes it once every test in this module has run.
    """
    global QGD
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_SCRIPT_MODULE_NAME, _SCRIPT_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot build an import spec for {_SCRIPT_PATH}")
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _SCRIPT_MODULE_NAME, module)
        spec.loader.exec_module(module)
        QGD = module
        yield module


# ---------------------------------------------------------------------------
# Fixture payloads — real job/group names from ci-quality.yml.
# ---------------------------------------------------------------------------

_BASE_PAYLOAD: dict[str, Any] = {
    # GitHub `needs` context, job -> result (the blocking set WP03 passes).
    "needs": {
        "changes": "success",
        "lint": "success",
        "kernel-tests": "success",
        "fast-tests-sync": "success",
        "fast-tests-merge": "success",
        "fast-tests-core-misc": "success",
        "integration-tests-sync": "success",
        "integration-tests-core-misc": "success",
        "e2e-cross-cutting": "success",
        "build-wheel": "success",
        "uv-lock-check": "success",
    },
    # `changes` job outputs, filter group -> 'true'/'false' (dorny emits strings).
    "changes": {
        "sync": "true",
        "merge": "false",
        "core_misc": "true",
        "execution_context": "false",
        "release": "false",
        "e2e": "false",
    },
    # job -> gating filter groups. DATA: generated in-workflow by WP03 from the
    # same source as the `if:` expressions (Decision 8); always-run jobs
    # (lint, uv-lock-check, ...) simply have no entry.
    "job_groups": {
        "fast-tests-sync": ["sync"],
        "fast-tests-merge": ["merge"],
        "integration-tests-sync": ["sync"],
        "fast-tests-core-misc": ["core_misc", "execution_context"],
        "integration-tests-core-misc": ["core_misc", "execution_context"],
        "e2e-cross-cutting": ["e2e"],
    },
    "run_all": "false",
    "catchall_unmatched": "false",
    "pr_is_draft": "false",
    # The draft-gated jobs in ci-quality.yml today.
    "draft_gated_jobs": ["integration-tests-core-misc", "e2e-cross-cutting"],
    # Release-required semantics slot: when the `release` group is true these
    # must be `success`, not merely not-failed.
    "release_required_jobs": ["build-wheel", "uv-lock-check"],
}


def _payload() -> dict[str, Any]:
    return copy.deepcopy(_BASE_PAYLOAD)


def _run_main(
    payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, str]:
    """Invoke the script's CLI entry point with the payload on stdin."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    exit_code = QGD.main([])
    captured = capsys.readouterr()
    return int(exit_code), captured.out, captured.err


# ---------------------------------------------------------------------------
# Happy path + legitimate skips
# ---------------------------------------------------------------------------


def test_all_success_passes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code, out, _err = _run_main(_payload(), monkeypatch, capsys)
    assert exit_code == 0
    assert "| Job |" in out


def test_legitimately_skipped_filter_false_is_ok(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    # `merge` filter is false, so fast-tests-merge skipping is legitimate.
    payload["needs"]["fast-tests-merge"] = "skipped"
    exit_code, out, _err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 0
    assert "fast-tests-merge" in out


# ---------------------------------------------------------------------------
# Improperly-skipped mapped suite (the FR-011 core arm)
# ---------------------------------------------------------------------------


def test_improperly_skipped_mapped_suite_fails_naming_job(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    # `sync` filter matched but the job never ran; no full-run, not draft.
    payload["needs"]["fast-tests-sync"] = "skipped"
    exit_code, out, err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 1
    assert "fast-tests-sync" in out
    assert "improperly skipped" in (out + err).lower()


@pytest.mark.parametrize("full_run_flag", ["run_all", "catchall_unmatched"])
def test_full_run_supersede_makes_skip_ok(
    full_run_flag: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _payload()
    payload["needs"]["fast-tests-sync"] = "skipped"
    payload[full_run_flag] = "true"
    exit_code, _out, _err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Draft exemption (FR-013 makes this safe; GitHub blocks draft merges natively)
# ---------------------------------------------------------------------------


def test_draft_exempt_skip_is_ok(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    payload["needs"]["integration-tests-core-misc"] = "skipped"
    payload["pr_is_draft"] = "true"
    exit_code, _out, _err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 0


def test_draft_gated_job_skipped_on_ready_pr_fails(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    payload["needs"]["integration-tests-core-misc"] = "skipped"
    payload["pr_is_draft"] = "false"
    exit_code, out, _err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 1
    assert "integration-tests-core-misc" in out


# ---------------------------------------------------------------------------
# Existing semantics preserved: failure / cancelled always FAIL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_result", ["failure", "cancelled"])
def test_failure_and_cancelled_still_fail(
    bad_result: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _payload()
    # Even on a filter-false job: failures always block.
    payload["needs"]["fast-tests-merge"] = bad_result
    exit_code, out, _err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 1
    assert "fast-tests-merge" in out


# ---------------------------------------------------------------------------
# C-005 tripwire: quarantine-visibility must never enter the blocking set
# ---------------------------------------------------------------------------


def _inject_needs(payload: dict[str, Any]) -> None:
    payload["needs"][_QUARANTINE_JOB] = "success"


def _inject_job_groups(payload: dict[str, Any]) -> None:
    payload["job_groups"][_QUARANTINE_JOB] = ["core_misc"]


def _inject_draft_gated(payload: dict[str, Any]) -> None:
    payload["draft_gated_jobs"].append(_QUARANTINE_JOB)


def _inject_release_required(payload: dict[str, Any]) -> None:
    payload["release_required_jobs"].append(_QUARANTINE_JOB)


@pytest.mark.parametrize(
    "inject",
    [_inject_needs, _inject_job_groups, _inject_draft_gated, _inject_release_required],
    ids=["needs", "job_groups", "draft_gated_jobs", "release_required_jobs"],
)
def test_quarantine_visibility_in_input_is_loud_error(
    inject: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _payload()
    inject(payload)
    exit_code, _out, err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 2
    assert _QUARANTINE_JOB in err
    assert "C-005" in err


# ---------------------------------------------------------------------------
# Step-summary table snapshot
# ---------------------------------------------------------------------------


def test_summary_table_includes_every_job_with_verdict(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    payload["needs"]["fast-tests-sync"] = "skipped"  # one FAIL row
    _exit_code, out, _err = _run_main(payload, monkeypatch, capsys)
    for job in payload["needs"]:
        row = next(
            (line for line in out.splitlines() if line.startswith(f"| {job} |")),
            None,
        )
        assert row is not None, f"summary table is missing a row for {job}"
        assert ("OK" in row) or ("FAIL" in row)


# ---------------------------------------------------------------------------
# Release-required semantics slot
# ---------------------------------------------------------------------------


def test_release_required_job_must_succeed_when_release_changed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    payload["changes"]["release"] = "true"
    # skipped is normally OK for an always-run job, but not when release-required.
    payload["needs"]["build-wheel"] = "skipped"
    exit_code, out, _err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 1
    assert "build-wheel" in out


def test_release_arm_inactive_when_release_unchanged(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    payload["changes"]["release"] = "false"
    payload["needs"]["build-wheel"] = "skipped"
    exit_code, _out, _err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Input contract
# ---------------------------------------------------------------------------


def test_needs_accepts_github_native_object_shape(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    # `toJSON(needs)` yields job -> {"result": ..., "outputs": {...}}.
    payload["needs"] = {job: {"result": result, "outputs": {}} for job, result in payload["needs"].items()}
    exit_code, _out, _err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 0


def test_unknown_group_reference_is_contract_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    payload["job_groups"]["fast-tests-sync"] = ["phantom_group"]
    exit_code, _out, err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 2
    assert "phantom_group" in err


def test_invalid_result_value_is_contract_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _payload()
    payload["needs"]["lint"] = "sucess"  # typo'd result must not pass silently
    exit_code, _out, err = _run_main(payload, monkeypatch, capsys)
    assert exit_code == 2
    assert "lint" in err


def test_malformed_json_is_contract_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
    exit_code = int(QGD.main([]))
    _captured = capsys.readouterr()
    assert exit_code == 2


# ---------------------------------------------------------------------------
# Decision 8 structural guard: the script carries NO hardcoded job→group table
# ---------------------------------------------------------------------------


def test_script_hardcodes_no_job_group_table() -> None:
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    # The only job name the script may know is the C-005 tripwire target.
    for forbidden in ("fast-tests-", "integration-tests-", "e2e-cross-cutting"):
        assert forbidden not in source, f"quality_gate_decision.py must consume the job set as data (Decision 8); found hardcoded job name fragment {forbidden!r}"
