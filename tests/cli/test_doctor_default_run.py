"""#6969: a bare ``spec-kitty doctor`` runs the default check set.

The exits-code contract is the point of the issue: before this change a bare
invocation printed the group help and exited 2, so neither a human nor a wrapper
could tell "no diagnostic ran" from "a diagnostic reported a problem".

These tests drive the real registered CLI (``CliRunner`` on the root app), the
same entry point a user runs. The three underlying primitives are stubbed to
known values except where a test deliberately plants a real finding, so the
suite stays deterministic on a machine whose global agent command files are not
installed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import register_commands
from specify_cli.cli.commands import _default_run_doctor as default_run

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _registered_root() -> typer.Typer:
    app = typer.Typer()
    register_commands(app)
    return app


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A minimal spec-kitty project root that ``locate_project_root`` accepts."""
    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


def _stub_healthy_primitives(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the three data primitives to a healthy project."""
    monkeypatch.setattr(
        "specify_cli.runtime.doctor.check_command_file_health",
        lambda _root: [],
    )
    monkeypatch.setattr(
        "specify_cli.state.doctor.check_state_roots",
        lambda _root: SimpleNamespace(warnings=[]),
    )
    monkeypatch.setattr(
        "specify_cli.doctor.ops.list_orphan_ops",
        lambda _root: [],
    )


def test_bare_doctor_runs_every_default_check_and_exits_zero(project, monkeypatch) -> None:
    """A healthy project: every default check runs, each line names its subcommand, exit 0."""
    _stub_healthy_primitives(monkeypatch)

    result = CliRunner().invoke(_registered_root(), ["doctor"])

    assert result.exit_code == 0, result.output
    for check in default_run.DEFAULT_CHECKS:
        assert check.command in result.output, check.command
    # The #4678 refusal message must be gone: something did run.
    assert "no diagnostic ran" not in result.output
    assert "3 of 3 checks healthy" in result.output


def test_bare_doctor_exits_one_and_names_the_owning_subcommand(project, monkeypatch) -> None:
    """A real finding flips the exit code and points at the subcommand that shows it in full."""
    monkeypatch.setattr(
        "specify_cli.runtime.doctor.check_command_file_health",
        lambda _root: [],
    )
    monkeypatch.setattr(
        "specify_cli.doctor.ops.list_orphan_ops",
        lambda _root: [],
    )
    monkeypatch.setattr(
        "specify_cli.state.doctor.check_state_roots",
        lambda _root: SimpleNamespace(warnings=["runtime surface .kittify/state is not gitignored"]),
    )

    result = CliRunner().invoke(_registered_root(), ["doctor"])

    assert result.exit_code == 1, result.output
    assert "runtime surface .kittify/state is not gitignored" in result.output
    assert "spec-kitty doctor state-roots" in result.output
    assert "2 of 3 checks healthy" in result.output


def test_a_raising_check_does_not_hide_the_other_checks(project, monkeypatch) -> None:
    """One broken check is reported as a failure; the rest still report (#6969 FR-005)."""
    _stub_healthy_primitives(monkeypatch)

    def _explode(_root: Any) -> list[str]:
        raise RuntimeError("primitive exploded")

    monkeypatch.setattr("specify_cli.doctor.ops.list_orphan_ops", _explode)

    result = CliRunner().invoke(_registered_root(), ["doctor"])

    assert result.exit_code == 1, result.output
    assert "primitive exploded" in result.output
    # The checks that did not raise are still reported.
    assert "command-files" in result.output
    assert "state-roots" in result.output


def test_default_check_set_is_the_documented_read_only_trio() -> None:
    """Guard the set itself: adding a heavy or mutating check must be a deliberate act."""
    assert [check.command for check in default_run.DEFAULT_CHECKS] == [
        "command-files",
        "state-roots",
        "ops",
    ]


def test_bare_doctor_reports_a_real_orphan_op(project, monkeypatch) -> None:
    """The real ``ops`` primitive surfaces a planted orphan record through the default run."""
    monkeypatch.setattr(
        "specify_cli.runtime.doctor.check_command_file_health",
        lambda _root: [],
    )
    monkeypatch.setattr(
        "specify_cli.state.doctor.check_state_roots",
        lambda _root: SimpleNamespace(warnings=[]),
    )
    ops_dir = project / "kitty-ops"
    ops_dir.mkdir()
    (ops_dir / "01ORPHANRECORD000000000000.jsonl").write_text('{"event": "started"}\n', encoding="utf-8")

    result = CliRunner().invoke(_registered_root(), ["doctor"])

    assert result.exit_code == 1, result.output
    assert "kitty-ops/01ORPHANRECORD000000000000.jsonl" in result.output
    assert "spec-kitty doctor ops" in result.output


def test_bare_doctor_mutates_nothing(project, monkeypatch) -> None:
    """A default run is read-only: the project tree is byte-identical afterwards."""
    _stub_healthy_primitives(monkeypatch)
    (project / "kitty-specs").mkdir()
    (project / "kitty-specs" / "marker.md").write_text("unchanged\n", encoding="utf-8")

    def _snapshot() -> dict[str, bytes]:
        return {str(path.relative_to(project)): path.read_bytes() for path in sorted(project.rglob("*")) if path.is_file()}

    before = _snapshot()
    CliRunner().invoke(_registered_root(), ["doctor"])
    assert _snapshot() == before


def test_bare_doctor_outside_a_project_exits_one(tmp_path, monkeypatch) -> None:
    """No project root: the standard not-in-project error, exit 1, never 2 or 0."""
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    # Pin the resolver rather than relying on a walk-up that can find a stray
    # .kittify/ in a shared ancestor (see core.paths.locate_project_root).
    monkeypatch.setattr("specify_cli.cli.commands.doctor.locate_project_root", lambda *_args, **_kwargs: None)

    result = CliRunner().invoke(_registered_root(), ["doctor"])

    assert result.exit_code == 1, result.output
    assert "Not in a spec-kitty project" in result.output
    assert "Default checks" not in result.output


def test_doctor_subcommand_is_not_intercepted(project, monkeypatch) -> None:
    """A real subcommand keeps its own behaviour; the default run never runs instead."""
    _stub_healthy_primitives(monkeypatch)

    result = CliRunner().invoke(_registered_root(), ["doctor", "ops"])

    assert result.exit_code == 0, result.output
    assert "Default checks" not in result.output


def test_an_empty_check_set_is_never_reported_healthy(project) -> None:
    """A run that executed nothing must not read as healthy (#4678's failure mode)."""
    results = default_run.run_default_checks(project, checks=())

    assert results == []
    assert default_run.render_default_run(results) == 1


def test_the_group_help_states_that_a_bare_run_runs_the_checks() -> None:
    """FR-006: the help text and the behaviour agree."""
    output = CliRunner().invoke(_registered_root(), ["doctor", "--help"]).output

    assert "bare invocation runs the default check set" in output


def test_a_command_file_issue_without_a_path_has_no_empty_parenthetical(project, monkeypatch) -> None:
    """The finding line stays readable when the primitive omits the file."""
    monkeypatch.setattr(
        "specify_cli.runtime.doctor.check_command_file_health",
        lambda _root: [{"agent": "claude", "command": "plan", "issue": "missing"}],
    )
    monkeypatch.setattr(
        "specify_cli.state.doctor.check_state_roots",
        lambda _root: SimpleNamespace(warnings=[]),
    )
    monkeypatch.setattr("specify_cli.doctor.ops.list_orphan_ops", lambda _root: [])

    result = CliRunner().invoke(_registered_root(), ["doctor"])

    assert result.exit_code == 1, result.output
    assert "claude plan: missing" in result.output
    assert "()" not in result.output
