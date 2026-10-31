"""Tests for the live ``specify_cli.review.scope_source`` surface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest

from specify_cli.review import baseline, scope_source
from specify_cli.review.scope_source import (
    DeclaredCommandScopeSource,
    RawRunResult,
    ScopeSource,
)

pytestmark = [pytest.mark.fast]


def _write_config(root: Path, *, test_command: str | None) -> None:
    config_dir = root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    if test_command is None:
        (config_dir / "config.yaml").write_text("review: {}\n", encoding="utf-8")
        return
    (config_dir / "config.yaml").write_text(
        f"review:\n  test_command: {test_command!r}\n",
        encoding="utf-8",
    )


def test_declared_command_scope_source_satisfies_the_port(tmp_path: Path) -> None:
    impl = DeclaredCommandScopeSource(repo_root=tmp_path)
    assert isinstance(impl, ScopeSource)


def test_declared_command_source_exposes_no_changed_files_method(tmp_path: Path) -> None:
    assert not hasattr(DeclaredCommandScopeSource(repo_root=tmp_path), "changed_files")


def test_port_declares_exactly_the_repo_shape_methods() -> None:
    port_methods = {name for name in vars(ScopeSource) if not name.startswith("_")} & {
        "test_command",
        "file_to_scope",
        "parse_results",
        "parse_mode",
        "changed_files",
    }
    assert port_methods == {"test_command", "file_to_scope", "parse_results", "parse_mode"}


def test_declared_command_test_command_wraps_in_a_posix_shell(tmp_path: Path) -> None:
    """Issue #3612 rewrite: previously pinned a bare ``shlex.split`` argv with
    no shell involved at all, which meant ``$VAR``/``~`` in a configured
    command were never expanded (they reached ``exec`` as literal tokens).
    ``test_command()`` now always wraps the configured command in ``["sh",
    "-c", ...]`` so it gets real POSIX shell semantics, matching every OTHER
    configured-command consumer in the codebase
    (``configured_command.run_configured_command``)."""
    _write_config(tmp_path, test_command="./run-tests.sh --ci")

    command = DeclaredCommandScopeSource(repo_root=tmp_path).test_command()

    assert command is not None
    assert command[:2] == ["sh", "-c"]
    assert command[2] == "./run-tests.sh --ci"


def test_declared_command_test_command_substitutes_output_file_placeholder(tmp_path: Path) -> None:
    """Issue #3612: a configured ``{output_file}`` placeholder must resolve
    to a REAL, absolute path this source owns — never the literal 8-char
    token ``{output_file}`` — so a declared command's own output-file flag
    (whatever its name — ``--junitxml=``, ``--report=``, ...) always
    receives something the source can actually read back later."""
    _write_config(tmp_path, test_command="./run-tests.sh --report={output_file}")

    source = DeclaredCommandScopeSource(repo_root=tmp_path)
    command = source.test_command()

    assert command is not None
    assert command[:2] == ["sh", "-c"]
    rendered = command[2]
    assert "{output_file}" not in rendered
    assert str(source._output_file) in rendered


def test_declared_command_returns_none_when_unconfigured(tmp_path: Path) -> None:
    _write_config(tmp_path, test_command=None)

    assert DeclaredCommandScopeSource(repo_root=tmp_path).test_command() is None


def test_declared_command_malformed_quoting_yields_none_instead_of_raising(tmp_path: Path) -> None:
    """The ``ScopeSource`` port contract degrades environmental errors."""
    _write_config(tmp_path, test_command='pytest "unterminated')

    assert DeclaredCommandScopeSource(repo_root=tmp_path).test_command() is None


def test_declared_command_file_to_scope_never_narrows(tmp_path: Path) -> None:
    assert DeclaredCommandScopeSource(repo_root=tmp_path).file_to_scope("src/pkg/foo.py") == ()


def test_declared_command_parse_mode_is_junit_xml_when_artifact_present(tmp_path: Path) -> None:
    junit_path = tmp_path / "declared.xml"
    junit_path.write_text("<testsuite></testsuite>", encoding="utf-8")
    impl = DeclaredCommandScopeSource(repo_root=tmp_path)
    raw = RawRunResult(returncode=0, stdout="", stderr="", output_artifact_path=junit_path)

    assert impl.parse_mode(raw) == "junit_xml"


def test_declared_command_parse_mode_is_text_without_artifact(tmp_path: Path) -> None:
    impl = DeclaredCommandScopeSource(repo_root=tmp_path)
    raw = RawRunResult(returncode=1, stdout="FAIL test_beta: boom\n", stderr="")

    assert impl.parse_mode(raw) == "text"


def test_declared_command_parse_results_reads_fail_lines(tmp_path: Path) -> None:
    impl = DeclaredCommandScopeSource(repo_root=tmp_path)
    raw = RawRunResult(returncode=1, stdout="FAIL test_beta: boom\n", stderr="")

    failures = impl.parse_results(raw)

    assert len(failures) == 1
    assert failures[0].test == "test_beta"
    assert failures[0].error == "boom"


def test_declared_command_parse_results_surfaces_unparseable_nonzero_exit(tmp_path: Path) -> None:
    impl = DeclaredCommandScopeSource(repo_root=tmp_path)
    raw = RawRunResult(returncode=2, stdout="", stderr="panic\n")

    failures = impl.parse_results(raw)

    assert len(failures) == 1
    assert failures[0].test == baseline.OPAQUE_FAILURE_TEST_ID
    assert failures[0].error == "panic"
    # The placeholder name is not the identity: the entry carries the run's
    # exit status and is marked opaque so the baseline diff compares the bound
    # identity (exit status + summary) instead (issue #6751).
    assert failures[0].opaque is True
    assert failures[0].exit_code == 2


def test_declared_command_parse_results_parses_junit_xml(tmp_path: Path) -> None:
    junit_path = tmp_path / "declared.xml"
    junit_path.write_text(
        '<testsuite><testcase classname="tests.foo" name="test_broken"><failure message="AssertionError: boom">traceback</failure></testcase></testsuite>',
        encoding="utf-8",
    )
    impl = DeclaredCommandScopeSource(repo_root=tmp_path)
    raw = RawRunResult(returncode=1, stdout="", stderr="", output_artifact_path=junit_path)

    failures = impl.parse_results(raw)

    assert len(failures) == 1
    assert failures[0].test == "tests.foo.test_broken"
    assert "boom" in failures[0].error


def test_declared_command_identity_is_stable_across_clean_and_failing_runs(tmp_path: Path) -> None:
    impl = DeclaredCommandScopeSource(repo_root=tmp_path)
    clean = RawRunResult(returncode=0, stdout="ok test_alpha\n", stderr="")
    failing = RawRunResult(returncode=1, stdout="FAIL test_beta: boom\n", stderr="")

    assert scope_source.scope_source_identity(impl, clean) == scope_source.scope_source_identity(impl, failing)
    assert scope_source.scope_source_identity(impl, clean) == "DeclaredCommandScopeSource/text"


def test_resolve_scope_source_always_returns_declared_command_source(tmp_path: Path) -> None:
    _write_config(tmp_path, test_command=None)

    result = scope_source.resolve_scope_source(
        tmp_path,
        filter_groups_override={"retired": ("src/**",)},
        composite_routing_override={"retired": (None, None, ())},
    )

    assert isinstance(result, DeclaredCommandScopeSource)
    assert result.test_command() is None


def test_resolve_scope_source_keeps_configured_command_behavior(tmp_path: Path) -> None:
    _write_config(tmp_path, test_command="./run-tests.sh --ci")

    result = scope_source.resolve_scope_source(tmp_path)

    assert isinstance(result, DeclaredCommandScopeSource)
    assert result.test_command() == ["sh", "-c", "./run-tests.sh --ci"]


@dataclass
class _PolicyWithoutCapabilitySource:
    treats_empty_scope_as_coverage_gap: ClassVar[bool] = True

    def test_command(self) -> list[str] | None:
        return None

    def file_to_scope(self, path: str) -> tuple[str, ...]:
        return ()

    def parse_mode(self, raw: RawRunResult) -> str:
        return "none"

    def parse_results(self, raw: RawRunResult) -> tuple[Any, ...]:
        return ()


@dataclass
class _CapabilityWithoutPolicySource:
    def test_command(self) -> list[str] | None:
        return None

    def file_to_scope(self, path: str) -> tuple[str, ...]:
        return self.scope_breakdown(path).test_targets

    def scope_breakdown(self, path: str) -> Any:
        from specify_cli.review.scope_source import FileScopeBreakdown

        return FileScopeBreakdown()

    def parse_mode(self, raw: RawRunResult) -> str:
        return "none"

    def parse_results(self, raw: RawRunResult) -> tuple[Any, ...]:
        return ()


def test_declared_command_source_has_no_breakdown_policy_or_capability(tmp_path: Path) -> None:
    impl = DeclaredCommandScopeSource(repo_root=tmp_path)

    assert scope_source.empty_scope_is_coverage_gap(impl) is False
    assert scope_source.exposes_scope_breakdown(impl) is False


def test_empty_scope_is_coverage_gap_and_exposes_scope_breakdown_are_independent_signals() -> None:
    policy_only = _PolicyWithoutCapabilitySource()
    capability_only = _CapabilityWithoutPolicySource()

    assert scope_source.empty_scope_is_coverage_gap(policy_only) is True
    assert scope_source.exposes_scope_breakdown(policy_only) is False

    assert scope_source.empty_scope_is_coverage_gap(capability_only) is False
    assert scope_source.exposes_scope_breakdown(capability_only) is True
