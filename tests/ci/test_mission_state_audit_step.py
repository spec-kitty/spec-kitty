"""Behaviour of the ``mission-state audit`` step body under ``bash -e`` (spec-kitty#6058, FR-007).

GitHub runs ``run:`` steps with ``bash -e``. The step used to redirect the auditor's output and read
``$?`` on the next line, so a failing audit aborted the step before any output: 0 log lines, no
summary. These tests extract the REAL ``run:`` text from ``ci-router.yml`` and execute it with the
same flags GitHub uses, against a stub ``uv`` that plays the auditor (fixture JSON, chosen exit code)
and runs the real renderer script, so the workflow text and the renderer are exercised together.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from specify_cli.audit.models import TEAMSPACE_BLOCKER_CODES

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / ".github" / "workflows" / "ci-router.yml"
JOB = "mission-state-audit"
STEP_NAME = "Audit every Mission's state"
UPLOAD_PIN = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
REAL_FIXTURE = Path(__file__).parent / "fixtures" / "mission_state_audit_real_trimmed.json"

SNAPSHOT_DRIFT_SLUG = "drifted-mission-01AAAAAA"
WARNING_BLOCKER_SLUG = "identity-mission-01BBBBBB"
PLAIN_WARNING_SLUG = "noisy-mission-01CCCCCC"

needs_tools = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None, reason="bash and jq are required to run the step body")


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(ROUTER.read_text(encoding="utf-8"))
    return list(workflow["jobs"][JOB]["steps"])


def _audit_index() -> int:
    return next(i for i, step in enumerate(_steps()) if step.get("name") == STEP_NAME)


def _step_body() -> str:
    return str(_steps()[_audit_index()]["run"])


def _finding(code: str, severity: str, artifact: str, detail: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "artifact_path": artifact, "detail": detail}


def _mission(slug: str, findings: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "mission_slug": slug,
        "has_errors": any(f["severity"] == "error" for f in findings),
        "has_teamspace_blockers": bool(findings),
        "findings": findings,
    }


def _report(missions: list[dict[str, Any]]) -> dict[str, Any]:
    errors = sum(f["severity"] == "error" for m in missions for f in m["findings"])
    return {
        "repo_summary": {
            "total_missions": len(missions),
            "missions_with_teamspace_blockers": sum(m["has_teamspace_blockers"] for m in missions),
            "findings_by_severity": {"error": errors},
        },
        "missions": missions,
    }


def _blocking_report() -> dict[str, Any]:
    return _report(
        [
            _mission(SNAPSHOT_DRIFT_SLUG, [_finding("SNAPSHOT_DRIFT", "error", "status.json", "snapshot drifted")]),
            # A blocker code at warning severity: only the code set makes it a blocker.
            _mission(WARNING_BLOCKER_SLUG, [_finding("IDENTITY_MISSING", "warning", "meta.json", "no mission_id")]),
            _mission(PLAIN_WARNING_SLUG, [_finding("MISSING_EVIDENCE", "warning", "tasks/x.md", "plain warning")]),
        ]
    )


STUB_UV = """\
#!/usr/bin/env bash
# Stub uv: plays the auditor for `spec-kitty doctor ...`, runs the real renderer for `python ...`.
if [ "$4" = "spec-kitty" ]; then
  cat "$STUB_AUDIT_STDOUT"
  exit "$STUB_AUDIT_EXIT"
fi
if [ "$4" = "python" ]; then
  if [ -n "${STUB_RENDERER_EXIT:-}" ]; then
    echo "stub renderer crashed" >&2
    exit "$STUB_RENDERER_EXIT"
  fi
  shift 4
  exec "$STUB_PYTHON" "$@"
fi
echo "unexpected uv invocation: $*" >&2
exit 99
"""


def _run_step(
    tmp_path: Path, stdout_text: str, audit_exit: int, renderer_exit: int | None = None, body: str | None = None
) -> tuple[subprocess.CompletedProcess[str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(STUB_UV, encoding="utf-8")
    uv.chmod(uv.stat().st_mode | stat.S_IEXEC)
    audit_stdout = tmp_path / "audit-stdout.txt"
    audit_stdout.write_text(stdout_text, encoding="utf-8")
    runner_temp = tmp_path / "runner_temp"
    runner_temp.mkdir()
    summary = tmp_path / "summary.md"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_STEP_SUMMARY": str(summary),
        "STUB_AUDIT_STDOUT": str(audit_stdout),
        "STUB_AUDIT_EXIT": str(audit_exit),
        "STUB_PYTHON": sys.executable,
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
    }
    if renderer_exit is not None:
        env["STUB_RENDERER_EXIT"] = str(renderer_exit)
    # GitHub runs `run:` steps as `bash -e {0}`; `-c` is the same shell with the body given inline.
    proc = subprocess.run(
        ["bash", "-e", "-c", body if body is not None else _step_body()],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return proc, summary


def _summary_text(summary: Path) -> str:
    return summary.read_text(encoding="utf-8") if summary.exists() else ""


@needs_tools
def test_a_failing_audit_lists_every_blocker_in_log_and_summary(tmp_path: Path) -> None:
    proc, summary = _run_step(tmp_path, json.dumps(_blocking_report()), audit_exit=1)

    assert proc.returncode == 1, proc.stderr
    for slug, code in ((SNAPSHOT_DRIFT_SLUG, "SNAPSHOT_DRIFT"), (WARNING_BLOCKER_SLUG, "IDENTITY_MISSING")):
        assert slug in proc.stdout and code in proc.stdout
    assert "spec-kitty agent status materialize --mission " + SNAPSHOT_DRIFT_SLUG in proc.stdout
    assert "spec-kitty doctor mission-state --audit --mission " + WARNING_BLOCKER_SLUG in proc.stdout
    assert "::error" in proc.stdout
    assert PLAIN_WARNING_SLUG not in proc.stdout
    text = _summary_text(summary)
    assert "| Mission | Code | Artifact | Detail | Remedy |" in text
    assert SNAPSHOT_DRIFT_SLUG in text and WARNING_BLOCKER_SLUG in text
    assert PLAIN_WARNING_SLUG not in text


@needs_tools
def test_a_clean_audit_passes_and_says_so(tmp_path: Path) -> None:
    proc, summary = _run_step(tmp_path, json.dumps(_report([_mission("clean-01DDDDDD", [])])), audit_exit=0)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "No TeamSpace blockers" in _summary_text(summary)


@needs_tools
def test_no_json_and_a_failing_audit_reports_and_keeps_the_audit_status(tmp_path: Path) -> None:
    # A raw line starting with `::` (e.g. from a repo-controlled slug) must not be read as a workflow command,
    # and the dump is size-capped.
    hostile = "Traceback: boom\n::set-env name=PWNED::1\n::add-mask::x\n" + "pad\n" * 40000
    proc, summary = _run_step(tmp_path, hostile, audit_exit=2)

    assert proc.returncode == 2
    assert "produced no JSON report (exit 2)" in proc.stdout
    assert "::error::" in proc.stdout
    assert "Traceback: boom" in proc.stdout
    commands = [line for line in proc.stdout.splitlines() if line.startswith("::")]
    assert len(commands) == 1 and commands[0].startswith("::error::"), commands
    assert ": :set-env name=PWNED::1" in proc.stdout
    assert len(proc.stdout) < 70000, "the raw dump is capped"
    assert "no JSON report" in _summary_text(summary)


@needs_tools
def test_no_json_and_a_zero_exit_still_fails(tmp_path: Path) -> None:
    proc, _ = _run_step(tmp_path, "not json at all\n", audit_exit=0)

    assert proc.returncode == 1
    assert "produced no JSON report (exit 0)" in proc.stdout


@needs_tools
def test_a_renderer_failure_never_masks_the_audit_status(tmp_path: Path) -> None:
    proc, summary = _run_step(tmp_path, json.dumps(_blocking_report()), audit_exit=1, renderer_exit=3)

    assert proc.returncode == 1
    assert "renderer failed" in proc.stdout
    assert "uploaded artifact" in proc.stdout
    assert "No TeamSpace blockers" not in _summary_text(summary), "a failed renderer must not write a passing summary"


def test_the_report_is_uploaded_even_when_the_audit_fails() -> None:
    steps = _steps()
    upload = steps[_audit_index() + 1]
    audit_body = _step_body()

    assert str(upload["if"]).strip() == "always()"
    assert upload["uses"].startswith(UPLOAD_PIN)
    assert upload["with"]["name"] == "mission-state-audit-${{ github.run_attempt }}"
    written = next(line for line in audit_body.splitlines() if line.startswith("report="))
    assert written.split("/", 1)[1].strip('"') == upload["with"]["path"].removeprefix("${{ runner.temp }}/")
    assert "$RUNNER_TEMP" in written


@needs_tools
@pytest.mark.skipif(not REAL_FIXTURE.exists(), reason="trimmed real-report fixture not present")
def test_a_realistic_report_lists_every_blocker(tmp_path: Path) -> None:
    """SC-005: a trimmed copy of the real report (blockers of several codes) is listed in full."""
    report = json.loads(REAL_FIXTURE.read_text(encoding="utf-8"))
    expected = [
        (m["mission_slug"], f["code"]) for m in report["missions"] for f in m["findings"] if f["severity"] == "error" or f["code"] in TEAMSPACE_BLOCKER_CODES
    ]
    assert expected, "the fixture must carry blockers"

    started = time.monotonic()
    proc, summary = _run_step(tmp_path, json.dumps(report), audit_exit=1)
    elapsed = time.monotonic() - started

    assert proc.returncode == 1, proc.stderr
    text = _summary_text(summary)
    for slug, code in expected:
        assert any(slug in line and code in line for line in proc.stdout.splitlines() if line.startswith("::error title"))
        assert any(slug in line and code in line for line in text.splitlines())
    assert elapsed < 30, f"step took {elapsed:.1f}s"


def test_the_step_keeps_the_auditor_argv_token_for_token() -> None:
    body = textwrap.dedent(_step_body())

    assert "spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json" in body
