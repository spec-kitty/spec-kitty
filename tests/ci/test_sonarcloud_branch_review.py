"""Token-free smoke test for ``scripts/ci/sonarcloud_branch_review.sh``.

Mission ``sonar-qa-config-remediation-01KWYCX7`` (FR-006, NFR-001, SC-003).

The review tool is a thin read-only wrapper over SonarCloud's public REST API.
This test drives it entirely offline: ``curl`` is replaced by a stub on ``PATH``
that maps each requested endpoint to a recorded JSON fixture, so the suite needs
**no network and no ``SONAR_TOKEN``**. It asserts argument parsing, subcommand
dispatch, and the output shape of every subcommand, and — the load-bearing
invariant — that the script only ever issues read-only ``GET`` requests, both by
static inspection of the script source and by inspecting every stubbed ``curl``
invocation at runtime.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

# This drives ``scripts/ci/sonarcloud_branch_review.sh`` through a real ``bash``
# subprocess against recorded fixtures (~40s, offline, no ``SONAR_TOKEN``) — a
# legitimately slow, subprocess-fanning suite, so it is ``integration`` and NEVER
# ``fast`` (the fast lane forbids subprocess users; test_pytest_marker_correctness
# Rule 2). The marker also routes the file into the ``integration-tests-core-misc``
# ``misc`` shard, whose ``git_repo or integration or architectural`` selector
# collects it in CI — without it the read-only-invariant guards below run in NO
# CI shard (a silent coverage hole).
pytestmark = [pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "sonarcloud_branch_review.sh"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sonarcloud"

SUBCOMMANDS = ("quality-gate", "coverage", "uncovered", "issues", "version")
MUTATING_METHODS = ("POST", "PUT", "DELETE", "PATCH")
_METHOD_OVERRIDE = re.compile(r"(?:^|\s)(?:-X|--request)\b")

# A stub ``curl`` that never touches the network. It records each invocation
# (one line per call) so the test can prove every request is a read-only GET,
# then replays the recorded fixture for the requested endpoint. The caller pins
# the method with ``--get`` and passes ``--write-out $'\n%{http_code}'``; the
# stub mirrors that contract by appending ``\n<code>`` after the body.
_FAKE_CURL = r"""#!/usr/bin/env bash
set -euo pipefail

# Collapse the newline that the caller's --write-out format injects into "$*"
# so each invocation is exactly one line in the call log.
printf '%s\n' "${*//$'\n'/ }" >> "${FAKE_CURL_LOG}"

code="${FAKE_CURL_HTTP_CODE:-200}"
request="$*"

pick() { cat "${FAKE_CURL_FIXTURES}/$1"; printf '\n%s' "${code}"; }

case "${request}" in
  *"/api/qualitygates/project_status"*) pick quality_gate.json ;;
  *uncovered_lines*)                    pick uncovered.json ;;
  *"/api/measures/component"*)          pick coverage.json ;;
  *"/api/issues/search"*)               pick issues.json ;;
  *"/api/project_analyses/search"*)     pick analyses.json ;;
  *"/api/components/show"*)             pick components_show.json ;;
  *) printf 'stub curl: unmapped request: %s\n' "${request}" >&2; exit 99 ;;
esac
"""


@dataclass(frozen=True)
class ScriptRun:
    """Result of one invocation of the review script under the curl stub."""

    returncode: int
    stdout: str
    stderr: str
    curl_calls: tuple[str, ...]


Runner = Callable[..., ScriptRun]


@pytest.fixture
def runner(tmp_path: Path) -> Runner:
    """Return a callable that runs the script offline against the fixtures.

    The returned runner removes ``SONAR_TOKEN`` from the child environment by
    default (proving the tool needs no token) and prepends a stub ``curl`` to
    ``PATH`` (proving it needs no network).
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl = fake_bin / "curl"
    curl.write_text(_FAKE_CURL, encoding="utf-8")
    curl.chmod(0o755)
    log = tmp_path / "curl.log"

    def _run(*args: str, http_code: str = "200", token: str | None = None) -> ScriptRun:
        log.write_text("", encoding="utf-8")
        env = dict(os.environ)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
        env["FAKE_CURL_FIXTURES"] = str(FIXTURES)
        env["FAKE_CURL_LOG"] = str(log)
        env["FAKE_CURL_HTTP_CODE"] = http_code
        env.pop("SONAR_TOKEN", None)
        if token is not None:
            env["SONAR_TOKEN"] = token
        completed = subprocess.run(
            ["bash", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
            check=False,
        )
        calls = tuple(
            line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()
        )
        return ScriptRun(completed.returncode, completed.stdout, completed.stderr, calls)

    return _run


# ---------------------------------------------------------------------------
# Argument parsing / dispatch
# ---------------------------------------------------------------------------


def test_help_lists_every_subcommand(runner: Runner) -> None:
    result = runner("--help")
    assert result.returncode == 0
    for sub in SUBCOMMANDS:
        assert sub in result.stdout
    assert not result.curl_calls  # help must not hit the network


def test_missing_subcommand_is_a_usage_error(runner: Runner) -> None:
    result = runner()
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()
    assert not result.curl_calls


def test_unknown_subcommand_errors(runner: Runner) -> None:
    result = runner("frobnicate")
    assert result.returncode == 2
    assert "unknown subcommand" in result.stderr
    assert not result.curl_calls


def test_unknown_global_option_errors(runner: Runner) -> None:
    result = runner("--nonsense", "coverage")
    assert result.returncode == 2
    assert "unknown option" in result.stderr


def test_uncovered_requires_a_file_argument(runner: Runner) -> None:
    result = runner("uncovered")
    assert result.returncode == 2
    assert "file" in result.stderr.lower()
    assert not result.curl_calls


# ---------------------------------------------------------------------------
# Output shape per subcommand
# ---------------------------------------------------------------------------


def test_quality_gate_output_shape(runner: Runner) -> None:
    result = runner("quality-gate")
    assert result.returncode == 0
    assert "status: ERROR" in result.stdout
    assert "condition: new_coverage status=ERROR" in result.stdout
    assert len(result.curl_calls) == 1
    assert "/api/qualitygates/project_status" in result.curl_calls[0]


def test_coverage_output_shape(runner: Runner) -> None:
    result = runner("coverage")
    assert result.returncode == 0
    assert "coverage: 68.4" in result.stdout
    assert "new_coverage: 72.5" in result.stdout  # new-code value from .period.value
    assert len(result.curl_calls) == 1
    assert "metricKeys=coverage,new_coverage" in result.curl_calls[0]


def test_uncovered_output_shape_routes_to_file_component(runner: Runner) -> None:
    result = runner("uncovered", "src/specify_cli/status/emit.py")
    assert result.returncode == 0
    assert "uncovered_lines: 12" in result.stdout
    assert "lines_to_cover: 76" in result.stdout
    assert any("uncovered_lines" in call for call in result.curl_calls)
    assert any(
        "component=spec-kitty_spec-kitty:src/specify_cli/status/emit.py" in call
        for call in result.curl_calls
    )


def test_issues_output_shape(runner: Runner) -> None:
    result = runner("issues")
    assert result.returncode == 0
    assert "total: 2" in result.stdout
    assert "python:S3776 [CRITICAL]" in result.stdout
    assert "/api/issues/search" in result.curl_calls[0]


def test_issues_rule_filter_is_forwarded(runner: Runner) -> None:
    result = runner("issues", "--rule", "python:S3776")
    assert result.returncode == 0
    assert any("rules=python:S3776" in call for call in result.curl_calls)


def test_issues_file_filter_scopes_the_component(runner: Runner) -> None:
    result = runner("issues", "--file", "src/specify_cli/status/store.py")
    assert result.returncode == 0
    assert any(
        "componentKeys=spec-kitty_spec-kitty:src/specify_cli/status/store.py" in call
        for call in result.curl_calls
    )


def test_version_backs_sc001b(runner: Runner) -> None:
    """`version` reports the analysed projectVersion + baseline history (SC-001b)."""
    result = runner("version")
    assert result.returncode == 0
    assert "latest_analysis_version: 3.2.0rc39" in result.stdout
    assert "component_last_analysis: 2026-07-06T02:17:00+0000" in result.stdout
    # The frozen 'not provided' baseline the mission fixes stays visible in history.
    assert "version=not provided" in result.stdout
    # Both endpoints that back SC-001b are queried.
    assert any("/api/project_analyses/search" in call for call in result.curl_calls)
    assert any("/api/components/show" in call for call in result.curl_calls)


def test_analyses_is_an_alias_for_version(runner: Runner) -> None:
    assert runner("analyses").stdout == runner("version").stdout


def test_project_override_flag_changes_the_component(runner: Runner) -> None:
    result = runner("--project", "some_other_key", "coverage")
    assert result.returncode == 0
    assert any("component=some_other_key" in call for call in result.curl_calls)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_non_200_status_is_reported_as_an_error(runner: Runner) -> None:
    result = runner("coverage", http_code="503")
    assert result.returncode != 0
    assert "503" in result.stderr


# ---------------------------------------------------------------------------
# Read-only invariant (NFR-001 / NFR-002 / SC-003) — the load-bearing checks
# ---------------------------------------------------------------------------


def test_script_source_is_statically_read_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    # The HTTP method is pinned to GET and never overridden.
    assert "--get" in source
    assert _METHOD_OVERRIDE.search(source) is None
    # No mutating HTTP verb token appears anywhere in the script.
    for verb in MUTATING_METHODS:
        assert re.search(rf"\b{verb}\b", source) is None, f"{verb} appears in the script"


def test_every_runtime_request_is_a_read_only_get(runner: Runner) -> None:
    invocations = (
        ("quality-gate",),
        ("coverage",),
        ("uncovered", "src/specify_cli/status/emit.py"),
        ("issues",),
        ("version",),
    )
    for args in invocations:
        result = runner(*args)
        assert result.returncode == 0, f"{args} failed: {result.stderr}"
        assert result.curl_calls, f"{args} issued no request"
        for call in result.curl_calls:
            assert "--get" in call, f"{args} issued a non-GET request: {call}"
            assert _METHOD_OVERRIDE.search(call) is None, f"method override in {call}"
            for verb in MUTATING_METHODS:
                assert re.search(rf"\b{verb}\b", call) is None, f"{verb} in {call}"


def test_runs_without_sonar_token(runner: Runner) -> None:
    # The runner removes SONAR_TOKEN from the child env; a green run proves the
    # tool never requires a token (NFR-001).
    result = runner("quality-gate")
    assert result.returncode == 0
    assert "status: ERROR" in result.stdout


def test_optional_token_is_forwarded_when_present(runner: Runner) -> None:
    # A token is optional; when supplied it is used for read auth only (still a GET).
    result = runner("coverage", token="deadbeef")
    assert result.returncode == 0
    assert any("--user deadbeef:" in call for call in result.curl_calls)
    for call in result.curl_calls:
        assert "--get" in call


def test_script_is_executable() -> None:
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "review script should be executable"
