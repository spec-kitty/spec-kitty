"""Default diagnostic set for a bare ``spec-kitty doctor`` (#6969).

#4678 made a bare ``spec-kitty doctor`` refuse to run: it printed the group help
and exited 2 so the output could never be mistaken for a passing check. That
guard removed the false-green, but it also made the command the docs, the skills
and the prompts tell people to run a usage error, and exit 2 reads as a failure
or a misuse to every wrapper.

This module keeps #4678's intent and replaces its remedy: the bare invocation
runs a small, fast, read-only, project-level set of diagnostics, prints one
summary line per check that names the subcommand owning it, and reports a real
verdict — 0 when every check is healthy, 1 when any check reports a finding (or
raises). Nothing here mutates state and nothing here adds a flag: the mutating
subcommands keep owning ``--fix``/``--repair``/``--close-stale``.

The checks are thin adapters over the same data primitives their subcommands
render, so a default run cannot drift from ``spec-kitty doctor <subcommand>``:
calling the printing shells instead would mean capturing their output or
duplicating their exit-code logic.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.markup import escape

from ._doctor_shared import console

__all__ = [
    "DEFAULT_CHECKS",
    "CheckResult",
    "DefaultCheck",
    "render_default_run",
    "run_default_checks",
    "run_default_doctor",
]


@dataclass(frozen=True)
class DefaultCheck:
    """One read-only diagnostic in the bare-invocation set.

    ``command`` is the ``spec-kitty doctor <command>`` that renders the same
    check in full; ``collect`` returns the finding lines (empty = healthy).
    """

    command: str
    description: str
    collect: Callable[[Path], list[str]]


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one :class:`DefaultCheck` run."""

    check: DefaultCheck
    findings: tuple[str, ...] = ()
    error: str | None = None

    @property
    def healthy(self) -> bool:
        """True when the check neither found anything nor raised."""
        return self.error is None and not self.findings


def _collect_command_files(repo_root: Path) -> list[str]:
    """Findings from ``doctor command-files``' data primitive."""
    from specify_cli.runtime.doctor import check_command_file_health

    findings: list[str] = []
    for issue in check_command_file_health(repo_root):
        agent = issue.get("agent", "?")
        command = issue.get("command", "?")
        problem = issue.get("issue", "issue")
        path = issue.get("file")
        findings.append(f"{agent} {command}: {problem}" + (f" ({path})" if path else ""))
    return findings


def _collect_state_roots(repo_root: Path) -> list[str]:
    """Findings from ``doctor state-roots``' data primitive (its warnings are the findings)."""
    from specify_cli.state.doctor import check_state_roots

    return list(check_state_roots(repo_root).warnings)


def _collect_ops(repo_root: Path) -> list[str]:
    """Findings from ``doctor ops``' data primitive: one line per orphan Op record."""
    from specify_cli.doctor.ops import list_orphan_ops

    return [str(path.relative_to(repo_root)) for path in list_orphan_ops(repo_root)]


#: The bare-invocation set. Deliberately short: a check that walks every mission
#: (``identity``, ``topology``) or can mutate (any ``--fix`` path) does not belong
#: here. tests/cli/test_doctor_default_run.py pins the membership.
DEFAULT_CHECKS: tuple[DefaultCheck, ...] = (
    DefaultCheck(
        command="command-files",
        description="agent command files match the installed version",
        collect=_collect_command_files,
    ),
    DefaultCheck(
        command="state-roots",
        description="state roots and runtime surfaces are present and gitignored",
        collect=_collect_state_roots,
    ),
    DefaultCheck(
        command="ops",
        description="no orphan Op records",
        collect=_collect_ops,
    ),
)


def run_default_checks(
    repo_root: Path,
    checks: Sequence[DefaultCheck] | None = None,
) -> list[CheckResult]:
    """Run every default check, isolating failures so one cannot hide the rest."""
    results: list[CheckResult] = []
    for check in DEFAULT_CHECKS if checks is None else checks:
        try:
            findings = tuple(check.collect(repo_root))
        except Exception as exc:  # noqa: BLE001 — a broken check is a finding, not a crash (#6969 FR-005)
            results.append(CheckResult(check=check, error=f"{type(exc).__name__}: {exc}"))
            continue
        results.append(CheckResult(check=check, findings=findings))
    return results


def _render_result(result: CheckResult) -> None:
    """Print one check's line, plus its findings indented beneath it."""
    if result.healthy:
        console.print(f"  [green]ok[/green]    {result.check.command:<15} {result.check.description}")
        return
    count = len(result.findings) or 1
    plural = "finding" if count == 1 else "findings"
    console.print(f"  [red]FAIL[/red]  {result.check.command:<15} {count} {plural} -- full report: spec-kitty doctor {result.check.command}")
    for finding in result.findings:
        console.print(f"        {escape(finding)}", soft_wrap=True)
    if result.error is not None:
        console.print(f"        [red]{escape(result.error)}[/red]", soft_wrap=True)


def render_default_run(results: Sequence[CheckResult]) -> int:
    """Render the default run and return its exit code (0 healthy / 1 anything else).

    An empty result sequence is a failure, not a pass: a run that executed no check
    must never read as healthy (the #4678/#6969 failure mode). The CLI cannot reach
    it today, but the renderer does not rely on that.
    """
    healthy = sum(1 for result in results if result.healthy)
    total = len(results)

    if total == 0:
        console.print("\n[red]No default check ran.[/red] Run `spec-kitty doctor <subcommand>` for a diagnostic.\n")
        return 1

    console.print(f"\n[bold]Default checks[/bold] ({total})\n")
    for result in results:
        _render_result(result)
    console.print()
    if healthy == total:
        console.print(f"[green]{healthy} of {total} checks healthy[/green] -- run `spec-kitty doctor <subcommand>` for a full report.\n")
        return 0
    console.print(f"[yellow]{healthy} of {total} checks healthy[/yellow] -- run `spec-kitty doctor <subcommand>` for a full report.\n")
    return 1


def run_default_doctor(repo_root: Path) -> int:
    """Run and render the default set for *repo_root*, returning the exit code."""
    return render_default_run(run_default_checks(repo_root))
