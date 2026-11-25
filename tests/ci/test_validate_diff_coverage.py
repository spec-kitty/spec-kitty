"""The critical-path statement validator reports honestly when nothing is scored (#7789).

An empty scored diff (no changed executable critical-path statement) used to
print "changed executable critical statements have coverage evidence", and
diff-cover then passed with "No lines with coverage information": two green
lines that applied no gate at all. The validator now says the gate was not
applied, as a workflow notice and a step-summary line.
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import pytest

from scripts.ci import validate_diff_coverage
from scripts.ci.validate_diff_coverage import GATE_NOT_APPLIED, validate

pytestmark = [pytest.mark.fast]

EVIDENCE_LINE = "have coverage evidence"
COVERAGE_XML = (
    '<coverage><sources><source>.</source></sources><packages><package name="kernel">'
    '<classes><class name="example" filename="src/kernel/example.py"><lines>'
    '<line number="1" hits="1"/><line number="2" hits="1"/>'
    "</lines></class></classes></package></packages></coverage>"
)
CODE_DIFF = (
    "diff --git a/src/kernel/example.py b/src/kernel/example.py\n"
    "--- a/src/kernel/example.py\n"
    "+++ b/src/kernel/example.py\n"
    "@@ -1,1 +1,2 @@\n"
    " value = 1\n"
    "+new_value = 2\n"
)


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, diff: str, sources: dict[str, str]) -> tuple[Path, Path]:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    diff_file = tmp_path / "critical.diff.patch"
    diff_file.write_text(diff, encoding="utf-8")
    sources_file = tmp_path / "critical-sources.json"
    sources_file.write_text(json.dumps(sources), encoding="utf-8")
    report = tmp_path / "coverage.xml"
    report.write_text(COVERAGE_XML, encoding="utf-8")
    output = tmp_path / "statement.diff.patch"
    validate(diff_file, sources_file, [report], [], output)
    return output, summary


def test_empty_scored_diff_says_the_gate_was_not_applied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    output, summary = _run(tmp_path, monkeypatch, "", {})
    out = capsys.readouterr().out
    assert "::notice::diff-cover gate not applied: no changed executable critical-path statements" in out
    assert EVIDENCE_LINE not in out
    assert GATE_NOT_APPLIED in summary.read_text(encoding="utf-8")
    assert output.read_text(encoding="utf-8") == ""


def test_scored_statements_keep_the_evidence_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    source = base64.b64encode(b"value = 1\nnew_value = 2\n").decode("ascii")
    output, summary = _run(tmp_path, monkeypatch, CODE_DIFF, {"src/kernel/example.py": source})
    out = capsys.readouterr().out
    assert EVIDENCE_LINE in out
    assert "::notice::" not in out
    assert not summary.exists()
    assert "+new_value = 2" in output.read_text(encoding="utf-8")


def test_empty_scored_diff_without_a_step_summary_still_prints_the_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    validate_diff_coverage.report_scored(tmp_path / "statement.diff.patch", [])
    assert f"::notice::{GATE_NOT_APPLIED}" in capsys.readouterr().out
