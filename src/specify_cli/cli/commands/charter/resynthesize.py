"""``spec-kitty charter resynthesize`` command (WP06 per-subcommand split)."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from specify_cli.cli.console import err_console
from rich.panel import Panel
from rich.text import Text

from charter.activation.evidence.orchestrator import ConfigShapeError
from specify_cli.task_utils import TaskCliError

from specify_cli.cli.commands.charter._app import (
    CHARTER_YAML_FILENAME,
    charter_app,
    console,
)
from specify_cli.cli.commands.charter._charter_write_root import (
    CharterWriteRootError,
    resolve_charter_write_root,
)
from specify_cli.cli.commands.charter._common import _emit_error

# See ``synthesize.py`` for the package-module pattern: patches of
# ``specify_cli.cli.commands.charter.<name>`` must be visible here too. We route
# ``_assert_bundle_compatible``, ``_build_synthesis_request``,
# ``_collect_evidence_result``, and ``_list_resynthesis_topics`` through the
# package module at call time so legacy ``patch("…charter.X", …)`` fixtures
# remain effective across the WP06 split.
import specify_cli.cli.commands.charter as _charter_pkg

__all__ = ["charter_resynthesize"]


@charter_app.command("resynthesize")
def charter_resynthesize(  # noqa: C901
    topic: str | None = typer.Option(
        None,
        "--topic",
        help=("Structured topic selector: <kind>:<slug> (project-local), <drg-urn> (built-in+project graph), or <interview-section-label>."),
    ),
    list_topics: bool = typer.Option(
        False,
        "--list-topics",
        help="List valid structured topic selectors and exit.",
    ),
    adapter: str = typer.Option(
        "generated",
        "--adapter",
        help=("Adapter to use. 'generated' (default) validates agent-authored YAML under .kittify/charter/generated/. 'fixture' is offline/testing only."),
    ),
    skip_code_evidence: bool = typer.Option(
        False,
        "--skip-code-evidence",
        help="Skip code-reading evidence collection.",
    ),
    skip_corpus: bool = typer.Option(
        False,
        "--skip-corpus",
        help="Skip best-practice corpus loading.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Regenerate a bounded set of project-local doctrine artifacts (partial resynthesis).

    Uses a structured selector to identify the target set:

    - ``directive:PROJECT_001`` — regenerate a specific project directive.
    - ``tactic:how-we-apply-directive-003`` — regenerate one tactic.
    - ``directive:DIRECTIVE_003`` — regenerate every artifact whose provenance
      references the built-in DIRECTIVE_003 URN.
    - ``testing-philosophy`` — regenerate all artifacts from that interview section.

    Unrelated artifacts are never touched (FR-017).

    Examples
    --------
    Resynthesize a single tactic::

        spec-kitty charter resynthesize --topic tactic:how-we-apply-directive-003

    Resynthesize all artifacts referencing a built-in directive::

        spec-kitty charter resynthesize --topic directive:DIRECTIVE_003
    """
    from charter.activation.synthesizer.errors import (
        SynthesisError,
        TopicSelectorUnresolvedError,
        render_error_panel,
    )

    try:
        # #4785 Finding 3 / FR-006 / NFR-004: fail closed BEFORE any root
        # resolution when invoked from a linked git worktree. Probed against
        # the raw invocation cwd, NOT the already-resolved
        # ``find_repo_root()`` result below -- that helper follows a linked
        # worktree's ``.git`` pointer back to the PRIMARY checkout by
        # contract (C-002, not changed here), which would silently mask the
        # very condition this guard exists to catch.
        resolve_charter_write_root(Path.cwd())

        repo_root = _charter_pkg.find_repo_root()
        charter_dir = repo_root / ".kittify" / "charter"
        # consolidate-charter-bundle (#2773): gate on the authoritative
        # charter.yaml, not the retired metadata.yaml (deleted by the fold
        # migration) — else the bundle-compat check silently no-ops on v2 bundles.
        if (charter_dir / CHARTER_YAML_FILENAME).exists():
            _charter_pkg._assert_bundle_compatible(charter_dir)
        evidence_result = _charter_pkg._collect_evidence_result(
            repo_root,
            skip_code_evidence=skip_code_evidence,
            skip_corpus=skip_corpus,
        )
        warnings_collected = [str(warning) for warning in evidence_result.warnings]
        if not json_output:
            for warning in warnings_collected:
                console.print(f"[yellow]⚠ {warning}[/yellow]")

        request, syn_adapter = _charter_pkg._build_synthesis_request(repo_root, adapter, evidence=evidence_result.bundle)

        if list_topics:
            topics = _charter_pkg._list_resynthesis_topics(request, repo_root)
            if json_output:
                print(
                    json.dumps(
                        {
                            "result": "success",
                            "topics": topics,
                            "warnings": warnings_collected,
                        },
                        indent=2,
                    )
                )
                return

            if not any(topics.values()):
                console.print("[yellow]No topic selectors available yet.[/yellow]")
                return

            if topics["project_artifacts"]:
                console.print("[bold]Project artifact selectors[/bold]")
                for selector in topics["project_artifacts"]:
                    console.print(f"  {selector}")
            if topics["drg_urns"]:
                console.print("[bold]DRG URNs[/bold]")
                for selector in topics["drg_urns"]:
                    console.print(f"  {selector}")
            if topics["interview_sections"]:
                console.print("[bold]Interview sections[/bold]")
                for selector in topics["interview_sections"]:
                    alias = selector.replace("_", "-")
                    console.print(f"  {selector}  [dim](alias: {alias})[/dim]")
            return

        if topic is None:
            raise TaskCliError("Pass --topic <selector> or use --list-topics.")

        from charter.activation.synthesizer.resynthesize_pipeline import run as resynthesize_run

        result = resynthesize_run(
            request=request,
            adapter=syn_adapter,
            topic=topic,
            repo_root=repo_root,
        )

        # #4121 (MAJOR 2): surface the run's unresolved project-profile
        # reference warnings on the CLI / in the --json envelope rather than
        # leaving them in logging output only.
        reference_warnings = list(getattr(result, "reference_warnings", ()))
        warnings_collected.extend(reference_warnings)
        if not json_output:
            for warning in reference_warnings:
                console.print(f"[yellow]⚠ {warning}[/yellow]")

        if result.is_noop:
            if json_output:
                print(
                    json.dumps(
                        {
                            "result": "noop",
                            "topic": topic,
                            "diagnostic": result.diagnostic,
                            "matched_form": result.resolved_topic.matched_form,
                            "targets_count": 0,
                            "warnings": warnings_collected,
                        },
                        indent=2,
                    )
                )
                return
            console.print(f"[yellow]No-op:[/yellow] {result.diagnostic}")
            return

        regenerated = [f"{t.kind}:{t.slug}" for t in result.resolved_topic.targets]

        if json_output:
            print(
                json.dumps(
                    {
                        "result": "success",
                        "topic": topic,
                        "matched_form": result.resolved_topic.matched_form,
                        "matched_value": result.resolved_topic.matched_value,
                        "regenerated": regenerated,
                        "run_id": result.manifest.run_id,
                        "manifest_artifacts": len(result.manifest.artifacts),
                        "warnings": warnings_collected,
                    },
                    indent=2,
                )
            )
            return

        console.print(f"[green]Resynthesis complete[/green] (topic: {topic!r})")
        console.print(f"Matched form: {result.resolved_topic.matched_form}")
        console.print(f"Run ID: {result.manifest.run_id}")
        console.print("Regenerated artifacts:")
        for art in regenerated:
            console.print(f"  [green]✓[/green] {art}")

    except TopicSelectorUnresolvedError as e:
        # Exit code 2 — invalid usage (contracts/topic-selector.md §2.2)
        panel_body = str(e)
        if hasattr(e, "candidates") and e.candidates:
            cands = "\n".join(f"  * {c}" for c in e.candidates)
            panel_body += f"\n\nNearest candidates:\n{cands}"
        panel_body += "\n\nRun 'spec-kitty charter resynthesize --list-topics' to see all valid selectors."
        if json_output:
            _emit_error(console, json_output=True, message=panel_body)
        else:
            err_console.print(
                Panel(
                    Text(panel_body),
                    title=f'[bold red]Cannot resolve --topic "{e.raw}"[/]',
                    border_style="red",
                )
            )
        raise typer.Exit(code=2) from e
    except SynthesisError as e:
        if json_output:
            _emit_error(console, json_output=True, message=str(e))
        else:
            render_error_panel(e, err_console)
        raise typer.Exit(code=1) from e
    except FileNotFoundError as e:
        _emit_error(console, json_output=json_output, message=str(e))
        raise typer.Exit(code=1) from e
    except CharterWriteRootError as e:
        # #4785 Finding 3 / FR-006: the write-root guard already fails
        # closed with the exact, actionable remedy text. Catch the BASE class
        # so any write-root failure mode fails closed identically.
        _emit_error(console, json_output=json_output, message=str(e))
        raise typer.Exit(code=1) from e
    except (TaskCliError, ConfigShapeError) as e:
        # ConfigShapeError (a corrupt/non-mapping .kittify/config.yaml, ledger
        # SK-16) is a controlled, expected diagnostic -- treated the same as
        # TaskCliError, not routed through the generic "Unexpected error"
        # branch below.
        _emit_error(console, json_output=json_output, message=str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        _emit_error(console, json_output=json_output, message=str(e), unexpected=True)
        raise typer.Exit(code=1) from e
