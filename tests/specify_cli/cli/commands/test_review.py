"""Integration tests for the ``spec-kitty review --mission`` command (WP06).

These tests exercise the command end-to-end using a temporary filesystem
fixture and verify:

- Exit 1 + verdict: fail when any WP is not in done
- The lightweight missing/null-baseline hard failures
- The ``uv tool`` remediation guidance for a missing pytest
- The env-skew preflight seam

Scope of *this* module: the ``fast`` half. Nothing here spawns a process — the
CLI runs in-process through ``typer.testing.CliRunner`` and every fixture is
pure filesystem work. The tests that need a real git repository to earn a
dead-code diff baseline live in the sibling ``test_review_git_baseline.py``
(``integration`` + ``git_repo``), keeping the ``fast`` lane's no-subprocess
promise intact — see ``tests/architectural/test_pytest_marker_correctness.py``
and ``docs/context/testing-taxonomy.md`` under "Fast".
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
from typer.testing import CliRunner

from tests.specify_cli.cli.commands._review_fixtures import (
    MISSION_SLUG as _MISSION_SLUG,
)
from tests.specify_cli.cli.commands._review_fixtures import (
    build_cli_app as _build_cli_app,
)
from tests.specify_cli.cli.commands._review_fixtures import (
    make_mock_resolved as _make_mock_resolved,
)
from tests.specify_cli.cli.commands._review_fixtures import (
    setup_fixture as _setup_fixture,
)

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uv_runtime(
    tool_dir: str | None = None,
    is_default_tool_dir: bool = True,
    python: str | None = None,
    platform: str = "posix",
    *,
    requirements: tuple[object, ...] | None = None,
    bin_dir: str | None = None,
    is_default_bin_dir: bool = True,
) -> object:
    """Return a UV_TOOL InstalledCliRuntime for use in detect_runtime() mocks.

    Args:
        tool_dir: The uv tool directory (raw path text). Defaults to a
            sentinel path when None (only needed if is_default_tool_dir=False).
        is_default_tool_dir: Whether tool_dir is the default uv tool dir.
        python: Optional python version override from the receipt.
        platform: "posix" or "windows".
        requirements: uv receipt requirement entries (provenance). Defaults to a
            single bare ``spec-kitty-cli`` entry so the reinstall path preserves
            provenance instead of conservatively refusing.
        bin_dir / is_default_bin_dir: uv tool bin dir provenance (raw path text).

    Issue #3726: path fields are built with the DECLARED platform's flavor
    (PurePosixPath / PureWindowsPath), never a host ``Path``. On a Windows
    host ``Path("/opt/uv-t")`` renders ``\\opt\\uv-t``; the backslash falls
    outside CHK028's character allowlist (compat/remediation.py), so
    ``RemediationCommand.render("posix")`` degrades a mocked POSIX runtime
    to the provenance fallback note instead of the reconstructed uv tool
    command. Pure flavors pin the path semantics to the declared platform
    on any host.
    """
    from typing import Literal

    from specify_cli.compat._detect.install_method import InstallMethod
    from specify_cli.compat._detect.runtime import (
        InstalledCliRuntime,
        PackageSource,
        UvRequirement,
    )

    resolved_platform: Literal["posix", "windows"] = "windows" if platform == "windows" else "posix"
    path_cls: type[PurePosixPath] | type[PureWindowsPath] = PurePosixPath if resolved_platform == "posix" else PureWindowsPath
    resolved_tool_dir = path_cls(tool_dir if tool_dir is not None else "/home/user/.local/share/uv/tools")
    resolved_bin_dir = path_cls(bin_dir if bin_dir is not None else "/home/user/.local/share/uv/bin")
    resolved_reqs: tuple[object, ...] = requirements if requirements is not None else (UvRequirement(name="spec-kitty-cli"),)

    return InstalledCliRuntime(
        install_method=InstallMethod.UV_TOOL,
        executable="/home/user/.local/share/uv/tools/spec-kitty-cli/bin/python",
        # PurePath is the honest fixture type: InstalledCliRuntime's consumers
        # only None-check / str() these fields (issue #3726), so a pure path
        # of the declared platform's flavor is safe on any host.
        receipt_path=resolved_tool_dir / "spec-kitty-cli" / "uv-receipt.toml",  # type: ignore[arg-type]
        tool_dir=resolved_tool_dir,  # type: ignore[arg-type]
        bin_dir=resolved_bin_dir,  # type: ignore[arg-type]
        is_default_tool_dir=is_default_tool_dir,
        is_default_bin_dir=is_default_bin_dir,
        python=python,
        requirements=resolved_reqs,  # type: ignore[arg-type]
        package_source=PackageSource.PYPI_SPECIFIER,
        platform=resolved_platform,
        safe_for_auto_upgrade=True,
    )


def _uv_req(**kwargs: object) -> object:
    """A spec-kitty-cli uv requirement entry (provenance)."""
    from specify_cli.compat._detect.runtime import UvRequirement

    return UvRequirement(name="spec-kitty-cli", **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_review_fails_when_wp_not_done(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit 1 and verdict: fail when a WP is in in_progress."""
    repo_root, feature_dir = _setup_fixture(
        tmp_path,
        {"WP01": "in_progress", "WP02": "done"},
    )

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.find_repo_root",
        lambda: repo_root,
    )
    _mock_resolved = _make_mock_resolved(feature_dir)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.resolve_mission_handle",
        lambda handle, repo_root: _mock_resolved,
    )

    app = _build_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["--mission", _MISSION_SLUG])

    assert result.exit_code == 1, result.output

    report_path = feature_dir / "mission-review-report.md"
    assert report_path.exists(), "mission-review-report.md was not written"

    content = report_path.read_text(encoding="utf-8")
    assert "verdict: fail" in content
    # WP01 must appear in findings
    assert "WP01" in content


def test_review_exits_2_when_mission_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit code 2 when --mission flag is empty."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.find_repo_root",
        lambda: repo_root,
    )

    app = _build_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["--mission", ""])

    assert result.exit_code == 2, result.output


def test_issue_matrix_violation_is_hard_failure(tmp_path: Path) -> None:
    """Report writer must fail-hard on issue-matrix violations."""
    import io

    import typer
    from rich.console import Console

    from specify_cli.cli.commands.review._report import write_review_report

    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)

    findings = [
        {
            "type": "issue_matrix_violation",
            "diagnostic_code": "MISSION_REVIEW_ISSUE_MATRIX_MISSING",
            "message": "issue-matrix.md is required in post-merge mode",
        }
    ]

    with pytest.raises(typer.Exit) as exc_info:
        write_review_report(
            feature_dir,
            repo_root,
            findings,
            Console(file=io.StringIO()),
            mode="post-merge",
            issue_matrix_present=False,
        )

    assert exc_info.value.exit_code == 1
    report_text = (feature_dir / "mission-review-report.md").read_text(encoding="utf-8")
    assert "verdict: fail" in report_text
    assert "MISSION_REVIEW_ISSUE_MATRIX_MISSING" in report_text


def test_review_lightweight_modern_missing_baseline_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Modern lightweight review must fail when baseline_merge_commit is missing."""
    repo_root, feature_dir = _setup_fixture(
        tmp_path,
        {"WP01": "done"},
    )

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.find_repo_root",
        lambda: repo_root,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.assert_pytest_available",
        lambda _: None,
    )
    _mock_resolved = _make_mock_resolved(feature_dir)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.resolve_mission_handle",
        lambda handle, repo_root: _mock_resolved,
    )

    app = _build_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["--mission", _MISSION_SLUG, "--mode", "lightweight"])

    assert result.exit_code == 1, result.output

    report_text = (feature_dir / "mission-review-report.md").read_text(encoding="utf-8")
    assert "verdict: fail" in report_text
    assert "LIGHTWEIGHT_REVIEW_MISSING_BASELINE" in result.output
    assert "LIGHTWEIGHT_REVIEW_MISSING_BASELINE" in report_text
    assert "issue_matrix_present: not_applicable" in report_text


def test_review_lightweight_modern_null_baseline_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #1428: explicit null baseline_merge_commit must fail lightweight review."""
    repo_root, feature_dir = _setup_fixture(
        tmp_path,
        {"WP01": "done"},
        baseline_merge_commit=None,
    )
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" in meta
    assert meta["baseline_merge_commit"] is None

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.find_repo_root",
        lambda: repo_root,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.assert_pytest_available",
        lambda _: None,
    )
    _mock_resolved = _make_mock_resolved(feature_dir)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.resolve_mission_handle",
        lambda handle, repo_root: _mock_resolved,
    )

    app = _build_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["--mission", _MISSION_SLUG, "--mode", "lightweight"])

    assert result.exit_code == 1, result.output

    report_text = (feature_dir / "mission-review-report.md").read_text(encoding="utf-8")
    assert "verdict: fail" in report_text
    assert "LIGHTWEIGHT_REVIEW_MISSING_BASELINE" in result.output
    assert "LIGHTWEIGHT_REVIEW_MISSING_BASELINE" in report_text
    assert ("  - id: gate_2\n    name: dead_code_scan\n    command: spec-kitty review (internal gate 2)\n    exit_code: 1\n    result: fail") in report_text


def test_dead_code_baseline_missing_is_hard_failure(tmp_path: Path) -> None:
    """Report writer must fail-hard on missing dead-code baselines."""
    import io

    import typer
    from rich.console import Console

    from specify_cli.cli.commands.review._report import write_review_report

    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)

    findings = [
        {
            "type": "dead_code_baseline_missing",
            "diagnostic_code": "LIGHTWEIGHT_REVIEW_MISSING_BASELINE",
            "remediation": "Run `spec-kitty merge` to bake baseline_merge_commit into meta.json.",
        }
    ]

    with pytest.raises(typer.Exit) as exc_info:
        write_review_report(
            feature_dir,
            repo_root,
            findings,
            Console(file=io.StringIO()),
            mode="lightweight",
        )

    assert exc_info.value.exit_code == 1
    report_text = (feature_dir / "mission-review-report.md").read_text(encoding="utf-8")
    assert "verdict: fail" in report_text
    assert "LIGHTWEIGHT_REVIEW_MISSING_BASELINE" in report_text


def test_review_emits_json_diagnostic_when_pytest_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing test extra should fail before selector resolution and print JSON."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.find_repo_root",
        lambda: repo_root,
    )

    from specify_cli.cli.commands.review import TestExtraMissing

    def _raise_missing(_: Path) -> None:
        raise TestExtraMissing("MISSION_REVIEW_TEST_EXTRA_MISSING")

    monkeypatch.setattr(
        "specify_cli.cli.commands.review.assert_pytest_available",
        _raise_missing,
    )

    app = _build_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["--mission", _MISSION_SLUG])

    assert result.exit_code == 1, result.output
    assert '"diagnostic_code": "MISSION_REVIEW_TEST_EXTRA_MISSING"' in result.output
    assert "uv sync --extra test" in result.output


def test_review_emits_uv_tool_remediation_when_pytest_missing_in_uv_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """uv tool installs must repair the tool interpreter using --extra test."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.find_repo_root",
        lambda: repo_root,
    )

    from specify_cli.cli.commands.review import TestExtraMissing

    def _raise_missing(_: Path) -> None:
        raise TestExtraMissing("MISSION_REVIEW_TEST_EXTRA_MISSING")

    monkeypatch.setattr(
        "specify_cli.cli.commands.review.assert_pytest_available",
        _raise_missing,
    )
    # Mock detect_runtime() to return a UV_TOOL runtime with the default tool dir
    # (no UV_TOOL_DIR env prefix needed when using the default location).
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(),
    )

    app = _build_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["--mission", _MISSION_SLUG])

    assert result.exit_code == 1, result.output
    assert '"diagnostic_code": "MISSION_REVIEW_TEST_EXTRA_MISSING"' in result.output
    assert "uv tool install --force --with pytest spec-kitty-cli" in result.output
    assert '"remediation": "uv tool install --force --with pytest spec-kitty-cli"' in result.output


def test_uv_tool_remediation_non_default_tool_dir_adds_env_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UV_TOOL installs with a non-default tool_dir emit a UV_TOOL_DIR env prefix.

    Uses a short fixed path so the composed command stays within CHK028's 128-char limit.
    """
    import specify_cli.cli.commands.review as review_mod

    # Short path keeps the composed command within CHK028's 128-char ceiling.
    tool_dir = "/opt/uv-tools"
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(tool_dir=tool_dir, is_default_tool_dir=False),
    )

    assert review_mod._missing_test_extra_remediation() == (  # noqa: SLF001
        f"UV_TOOL_DIR={tool_dir!s} uv tool install --force --with pytest spec-kitty-cli"
    )


def test_uv_tool_remediation_source_install_falls_back_to_uv_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SOURCE install_method (e.g. dev checkout) falls back to uv sync --extra test."""
    import specify_cli.cli.commands.review as review_mod
    from specify_cli.compat._detect.runtime import InstalledCliRuntime, PackageSource
    from specify_cli.compat._detect.install_method import InstallMethod

    source_runtime = InstalledCliRuntime(
        install_method=InstallMethod.SOURCE,
        executable="/src/venv/bin/python",
        receipt_path=None,
        tool_dir=None,
        bin_dir=None,
        is_default_tool_dir=None,
        is_default_bin_dir=None,
        python=None,
        requirements=(),
        package_source=PackageSource.UNKNOWN,
        platform="posix",
        safe_for_auto_upgrade=False,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: source_runtime,
    )

    assert review_mod._missing_test_extra_remediation() == "uv sync --extra test"  # noqa: SLF001


def test_uv_tool_remediation_uses_with_pytest_not_extra_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UV_TOOL REINSTALL_WITH_TEST injects pytest via --with pytest, preserving source.

    FR-019 / SC-003 / issue #1358: ``--extra test`` would re-pin to PyPI and
    clobber the user's real source; the reinstall path must use ``--with pytest``.
    """
    import specify_cli.cli.commands.review as review_mod

    tool_dir = "/opt/uv-t"
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(tool_dir=tool_dir, is_default_tool_dir=False),
    )

    remediation = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert "--with pytest" in remediation
    assert "--extra test" not in remediation
    assert "spec-kitty-cli" in remediation


def test_uv_tool_remediation_preserves_receipt_specifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A receipt version specifier is preserved (not dropped) in the reinstall."""
    import specify_cli.cli.commands.review as review_mod

    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(requirements=(_uv_req(specifier="==3.2.0rc25"),)),
    )

    remediation = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert remediation == "uv tool install --force --with pytest spec-kitty-cli==3.2.0rc25"


def test_uv_tool_remediation_with_no_receipt_falls_back_to_uv_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the receipt is absent and install_method is not UV_TOOL, use uv sync."""
    import specify_cli.cli.commands.review as review_mod
    from specify_cli.compat._detect.runtime import InstalledCliRuntime, PackageSource
    from specify_cli.compat._detect.install_method import InstallMethod

    unknown_runtime = InstalledCliRuntime(
        install_method=InstallMethod.UNKNOWN,
        executable=str(tmp_path / "bin" / "python"),
        receipt_path=None,
        tool_dir=None,
        bin_dir=None,
        is_default_tool_dir=None,
        is_default_bin_dir=None,
        python=None,
        requirements=(),
        package_source=PackageSource.UNKNOWN,
        platform="posix",
        safe_for_auto_upgrade=False,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: unknown_runtime,
    )

    assert review_mod._missing_test_extra_remediation() == "uv sync --extra test"  # noqa: SLF001


def test_uv_tool_remediation_preserves_custom_bin_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UV_TOOL with a non-default bin_dir emits a UV_TOOL_BIN_DIR env prefix.

    The reinstall must not relocate the shim out of the user's custom bin dir
    (legacy parity); short fixed paths keep the command within CHK028's limit.
    """
    import specify_cli.cli.commands.review as review_mod

    tool_dir = "/opt/uv-t"
    bin_dir = "/opt/bin"
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(
            tool_dir=tool_dir,
            is_default_tool_dir=False,
            bin_dir=bin_dir,
            is_default_bin_dir=False,
        ),
    )

    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert result == ("UV_TOOL_DIR=/opt/uv-t UV_TOOL_BIN_DIR=/opt/bin uv tool install --force --with pytest spec-kitty-cli")


def test_uv_tool_remediation_preserves_receipt_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reinstall remediation must keep the uv tool Python interpreter.

    Uses a short fixed path so the composed command stays within CHK028's 128-char limit.
    """
    import specify_cli.cli.commands.review as review_mod

    # Short path keeps the composed command within CHK028's 128-char ceiling.
    tool_dir = "/opt/uv"
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(tool_dir=tool_dir, is_default_tool_dir=False, python="3.13"),
    )

    assert review_mod._missing_test_extra_remediation() == (  # noqa: SLF001
        f"UV_TOOL_DIR={tool_dir!s} uv tool install --force --python 3.13 --with pytest spec-kitty-cli"
    )


def test_uv_tool_remediation_uses_powershell_env_prefix_on_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows path with spaces causes CHK028 violation; degrades to note fallback."""
    import specify_cli.cli.commands.review as review_mod

    # A path with a space triggers the CHK028 violation in render("windows")
    # because $env:KEY='value with space'; contains chars outside the allowed set.
    tool_dir = str(tmp_path / "tool dir")  # has a space
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(tool_dir=tool_dir, is_default_tool_dir=False, platform="windows"),
    )

    # render("windows") raises ValueError (CHK028) → note fallback carrying the
    # safe provenance guidance (not a clobbering command).
    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert "could not preserve uv receipt provenance" in result


def test_uv_tool_remediation_windows_default_tool_dir_no_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows UV_TOOL with default tool_dir (no env) renders a valid CHK028 command."""
    import specify_cli.cli.commands.review as review_mod

    # Default tool_dir → env={} → no $env: prefix → CHK028 passes
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(platform="windows"),
    )

    result = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert result == "uv tool install --force --with pytest spec-kitty-cli"


def test_uv_tool_remediation_quotes_specifier_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CHK028-safe receipt specifier (==) is preserved in the reinstall command.

    Uses a short fixed path so the composed command stays within CHK028's 128-char limit.
    """
    import specify_cli.cli.commands.review as review_mod

    tool_dir = "/opt/uv-t"
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(
            tool_dir=tool_dir,
            is_default_tool_dir=False,
            requirements=(_uv_req(specifier="==3.2.0rc25"),),
        ),
    )

    remediation = review_mod._missing_test_extra_remediation()  # noqa: SLF001
    assert remediation == ("UV_TOOL_DIR=/opt/uv-t uv tool install --force --with pytest spec-kitty-cli==3.2.0rc25")


def test_uv_tool_remediation_omits_uv_tool_dir_for_default_tool_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default uv tool installs should keep the short copy/paste command."""
    import specify_cli.cli.commands.review as review_mod

    # is_default_tool_dir=True → env={} → no UV_TOOL_DIR prefix
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.detect_runtime",
        lambda: _make_uv_runtime(),  # default: is_default_tool_dir=True
    )

    assert review_mod._missing_test_extra_remediation() == (  # noqa: SLF001
        "uv tool install --force --with pytest spec-kitty-cli"
    )


def test_uv_runtime_fixture_paths_carry_declared_platform_flavor() -> None:
    """Issue #3726 regression: fixture path fields use the DECLARED platform's flavor.

    On a Windows host a bare host ``Path("/opt/uv-t")`` renders ``\\opt\\uv-t``;
    the backslash falls outside CHK028's character allowlist, so the mocked
    POSIX runtime degrades to the provenance fallback note instead of the
    reconstructed uv tool command. The fixture must therefore build its path
    fields with the declared platform's PurePath flavor on every host — this
    guard fails on a Windows host the moment a host-flavored Path sneaks back
    into the fixture.
    """
    posix_runtime = _make_uv_runtime(tool_dir="/opt/uv-t", is_default_tool_dir=False)
    assert str(posix_runtime.tool_dir) == "/opt/uv-t"
    assert str(posix_runtime.bin_dir) == "/home/user/.local/share/uv/bin"
    assert str(posix_runtime.receipt_path) == "/opt/uv-t/spec-kitty-cli/uv-receipt.toml"

    windows_runtime = _make_uv_runtime(tool_dir="C:\\uv-tools", is_default_tool_dir=False, platform="windows")
    assert str(windows_runtime.tool_dir) == "C:\\uv-tools"
    assert str(windows_runtime.receipt_path) == "C:\\uv-tools\\spec-kitty-cli\\uv-receipt.toml"


# ---------------------------------------------------------------------------
# _check_env_skew CLI-seam coverage (#2283 Phase 3
# pre-merge findings): these behaviors previously had zero test coverage,
# which is how the tuple-repr bug in the fail-closed branch shipped.
# ---------------------------------------------------------------------------


def test_check_env_skew_fail_closed_emits_clean_message_not_tuple_repr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (#2283 pre-merge finding): the fail-closed diagnostic must
    carry the clean, already-formatted skew message (``exc.args[1]``) in both
    the console line and the JSON ``message`` field -- never ``str(exc)``,
    which for a 2-arg exception renders the raw args tuple's repr, e.g.
    ``"('MISSION_REVIEW_ENV_SKEW', 'MISSION_REVIEW_ENV_SKEW: ...')"``.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.find_repo_root",
        lambda: repo_root,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.assert_pytest_available",
        lambda _: None,
    )

    from specify_cli.cli.commands.review import (
        ENV_SKEW_DIAGNOSTIC_CODE,
        EnvSkew,
        PackageSkew,
        format_env_skew_message,
    )

    mismatches = [PackageSkew("typer", "0.24.2", "0.26.0")]
    expected_message = format_env_skew_message(mismatches)

    def _raise_env_skew(repo_root: Path) -> list[PackageSkew]:
        # Mirrors the real raise site in assert_typer_click_lock_parity():
        # a 2-arg exception, diagnostic code + the pre-formatted message.
        raise EnvSkew(ENV_SKEW_DIAGNOSTIC_CODE, expected_message)

    monkeypatch.setattr(
        "specify_cli.cli.commands.review.assert_typer_click_lock_parity",
        _raise_env_skew,
    )

    app = _build_cli_app()
    runner = CliRunner()
    # No --mission needed: the fail-closed preflight exits before mission
    # resolution.
    result = runner.invoke(app, [])

    assert result.exit_code == 1, result.output

    diagnostic_line = next(line for line in result.output.splitlines() if line.startswith("{"))
    diagnostic = json.loads(diagnostic_line)

    assert diagnostic["message"] == expected_message
    # The regression this guards against: str(exc) on a 2-arg Exception
    # renders the args tuple's repr -- wrapped in parens, quoting both
    # elements, and duplicating the diagnostic code.
    assert not diagnostic["message"].startswith("(")
    assert not diagnostic["message"].startswith("('MISSION_REVIEW_")
    # A tuple-repr also escapes the message's embedded newlines as a
    # literal backslash-n inside the (already-decoded) string.
    assert "\\n" not in diagnostic["message"]
    assert diagnostic["message"].count(ENV_SKEW_DIAGNOSTIC_CODE) == 1

    # The console line rendered the same clean message.
    assert expected_message in result.output
