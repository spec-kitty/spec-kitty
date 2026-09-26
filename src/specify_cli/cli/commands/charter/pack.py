"""spec-kitty charter pack — charter pack management commands (FR-011).

``list`` / ``path`` / ``apply`` (#3064 follow-up) are the on-demand pack CLI
for the built-in charter packs shipped at ``src/charter/packs/`` (``default``
and ``minimal``). The pack -> ``config.yaml`` merge logic is shared with the
``3.2.0rc35_default_charter_pack`` upgrade migration via
``specify_cli.charter_pack_registry`` — see that module's docstring.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from ruamel.yaml import YAML
from specify_cli.cli.console import console

from charter.activation.invocation_context import ProjectContext
from specify_cli.charter_pack_registry import (
    BUILTIN_PACKS,
    UnknownPackError,
    load_pack_yaml,
    merge_pack_into_config,
    resolve_builtin_pack_path,
)

__all__ = ["charter_pack_app"]

charter_pack_app = typer.Typer(
    name="pack",
    help="Charter pack management commands.",
    no_args_is_help=True,
)


@charter_pack_app.command("consistency-check")
def consistency_check_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Run consistency check against activated doctrine artifacts (FR-011)."""
    from charter.activation.consistency_check import run_consistency_check  # noqa: PLC0415

    ctx = ProjectContext.from_repo(repo_root)
    report = run_consistency_check(ctx)
    if json_output:
        typer.echo(report.to_json())
    else:
        if report.coherent:
            console.print("[green]Charter pack is coherent.[/green]")
        else:
            console.print("[red]Consistency issues found:[/red]")
            for ref in report.unknown_references:
                console.print(f"  [red]Unknown reference:[/red] {ref}")
            for ref in report.missing_from_doctrine:
                console.print(f"  [yellow]Missing from charter.offering:[/yellow] {ref}")
            for v in report.kind_violations:
                console.print(f"  [red]Kind violation:[/red] {v}")
            for ref in report.reference_id_divergences:
                console.print(f"  [red]Reference ID divergence:[/red] {ref}")
            for kind in report.graph_kind_gaps:
                console.print(f"  [red]Graph kind gap:[/red] {kind}")
            for s in report.suggestions:
                console.print(f"  [dim]Suggestion:[/dim] {s}")
    raise typer.Exit(0 if report.coherent else 1)


@charter_pack_app.command("list")
def list_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List the built-in charter packs shipped with spec-kitty (#3064)."""
    try:
        packs = [
            {
                "name": name,
                "path": str(resolve_builtin_pack_path(name)),
                "description": description,
            }
            for name, description in sorted(BUILTIN_PACKS.items())
        ]
    except FileNotFoundError as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    if json_output:
        typer.echo(json.dumps({"packs": packs}, indent=2))
        return

    console.print("[bold]Built-in charter packs:[/bold]")
    for pack in packs:
        console.print(f"  [cyan]{pack['name']}[/cyan] — {pack['description']}")
    console.print(
        "\n[dim]Resolve a path with `spec-kitty charter pack path <name>`, "
        "apply one with `spec-kitty charter pack apply <name>`.[/dim]"
    )


def _resolve_pack_path_or_exit(name: str, *, json_output: bool) -> Path:
    """Resolve a built-in pack name or exit(1) with a consistent error report.

    Shared by ``path_cmd`` and ``apply_cmd`` (T012 campsite) — both used to
    carry an IDENTICAL ``try: resolve_builtin_pack_path(name) except
    (UnknownPackError, FileNotFoundError)`` block. ``list_cmd`` is
    deliberately NOT routed through this helper: it resolves EVERY built-in
    pack in a list comprehension and only ever sees ``FileNotFoundError``
    (there is no single ``name`` argument for ``UnknownPackError`` to be
    raised about there) — forcing it through a helper shaped for a
    single-name lookup would make it catch an exception class it can never
    hit.
    """
    try:
        # `specify_cli.*` imports are `follow_imports = "skip"` under mypy
        # (pyproject.toml [[tool.mypy.overrides]]), which erases
        # `resolve_builtin_pack_path`'s own `-> Path` annotation to `Any`
        # when this file is checked in isolation. Wrapping in `Path(...)`
        # re-asserts the (already-true-at-runtime) type explicitly rather
        # than suppressing the check.
        return Path(resolve_builtin_pack_path(name))
    except (UnknownPackError, FileNotFoundError) as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


class _ApplyCompileGitWorktreeError(RuntimeError):
    """``apply --compile`` was requested outside a git working tree.

    Mirrors the requirement ``charter generate`` itself fails fast on
    (T030/#841) — ``--compile`` chains that same seam, so it inherits the
    same precondition.
    """


def _compile_bundle_after_merge(repo_root: Path, *, pack_name: str) -> list[str]:
    """Chain the EXISTING compile seam after an ``apply`` merge (T011/FR-003).

    Reuses ``charter generate``'s own building blocks — ``compile_charter``/
    ``write_compiled_charter`` (the same seam ``generate --no-from-interview``
    calls), its doctrine-service + pack-context wiring
    (``_build_doctrine_service_with_org_layer`` / ``PackContext.from_config``),
    its ``--no-from-interview`` interview resolution
    (``_load_interview_for_generate``), and its git-worktree gate
    (``_is_inside_git_worktree``) — rather than invoking the ``generate``
    typer command directly. ``generate`` always resolves its own repo root
    from the CLI process's cwd (it has no ``--repo-root`` override), which
    would silently diverge from the *repo_root* this command just merged
    the pack into for any caller passing a non-default one (this command's
    own hidden ``--repo-root``, or a test harness). Calling the seam
    functions directly with an explicit *repo_root* keeps both paths
    pointed at the same project and introduces ZERO new compiler code.

    All imports below are function-local: this mirrors ``generate.py``'s own
    lazy-import discipline for the pydantic-heavy ``charter.*`` package, and
    avoids a module-load-time circular import — ``pack.py`` is imported by
    ``_app.py`` before ``charter_app`` exists there, and ``generate.py``
    imports ``charter_app``/``console`` from ``_app.py`` at module scope, so
    a module-level import of ``generate.py`` here would fail during package
    initialization.

    *pack_name* is threaded straight into
    ``_load_interview_for_generate(..., profile=pack_name)`` instead of a
    hardcoded ``"minimal"``: :func:`charter.activation.interview.default_interview`'s
    ``profile`` argument has exactly one live branch --
    ``if profile == "minimal": answers = {filtered 7-question subset}``,
    else the full ``QUESTION_ORDER`` (11 questions) is used -- and today's
    two built-in packs (:data:`~specify_cli.charter_pack_registry.BUILTIN_PACKS`)
    are named exactly ``"minimal"`` and ``"default"``, so passing the applied
    pack's own name resolves to the SAME binary split the interview already
    implements: ``apply minimal`` keeps the filtered defaults, ``apply
    default`` now gets the full interview instead of silently reusing
    minimal's. Any future third pack name falls into the "not minimal"
    branch -- i.e. the full interview -- which is the same safe default
    ``default`` gets today, not a new failure mode. The derived value ends
    up in the compiled ``charter.yaml`` catalog's ``USER:PROJECT_PROFILE``
    reference content (``_user_profile_reference`` in
    :mod:`charter.activation.compiler`), which is exactly where this bug was
    observable and where the regression test below asserts it.

    Raises :class:`_ApplyCompileGitWorktreeError` when *repo_root* is not
    inside a git working tree.
    """
    from charter.activation.compiler import compile_charter, write_compiled_charter  # noqa: PLC0415
    from charter.activation.pack_context import PackContext  # noqa: PLC0415

    from specify_cli.cli.commands.charter._common import _interview_path  # noqa: PLC0415
    from specify_cli.cli.commands.charter.generate import (  # noqa: PLC0415
        _build_doctrine_service_with_org_layer,
        _is_inside_git_worktree,
        _load_interview_for_generate,
    )

    if not _is_inside_git_worktree(repo_root):
        raise _ApplyCompileGitWorktreeError(
            "charter pack apply --compile requires a git repository -- it "
            "inherits `charter generate`'s git-worktree requirement (the "
            "produced charter.yaml must be trackable). Initialize one with "
            "`git init`, then re-run with --compile, or finish governance "
            "later with `spec-kitty charter generate` once inside a git "
            "working tree."
        )

    interview_data, _source, resolved_mission = _load_interview_for_generate(
        repo_root=repo_root,
        answers_path=_interview_path(repo_root),
        from_interview=False,
        resolved_mission_type=None,
        profile=pack_name,
        prefer_recorded_mission=True,
    )
    compiled = compile_charter(
        mission=resolved_mission,
        interview=interview_data,
        repo_root=repo_root,
        doctrine_service=_build_doctrine_service_with_org_layer(repo_root),
        pack_context=PackContext.from_config(repo_root),
    )
    charter_dir = repo_root / ".kittify" / "charter"
    bundle_result = write_compiled_charter(charter_dir, compiled, repo_root=repo_root)
    return list(bundle_result.files_written)


def _apply_compile_bridge(
    repo_root: Path, compile_bundle: bool, *, json_output: bool, pack_name: str
) -> list[str]:
    """Run the ``--compile`` bridge when requested, else return no files.

    Isolates the ``--compile`` branch (including its git-worktree error
    reporting) out of ``apply_cmd`` so adding the flag does not grow that
    command's own cyclomatic complexity (campsite, T011).
    """
    if not compile_bundle:
        return []
    try:
        return _compile_bundle_after_merge(repo_root, pack_name=pack_name)
    except _ApplyCompileGitWorktreeError as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


@charter_pack_app.command("path")
def path_cmd(
    name: str = typer.Argument(..., help="Built-in pack name (e.g. 'default', 'minimal')."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Resolve a built-in charter pack name to its shipped filesystem path (#3064).

    Fails closed (exit 1) on an unknown pack name, naming it and the valid set.
    """
    resolved = _resolve_pack_path_or_exit(name, json_output=json_output)

    if json_output:
        typer.echo(json.dumps({"name": name, "path": str(resolved)}))
    else:
        typer.echo(str(resolved))


@charter_pack_app.command("apply")
def apply_cmd(
    name: str = typer.Argument(..., help="Built-in pack name to apply (e.g. 'default', 'minimal')."),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite activation keys already present in config.yaml (default: leave them untouched).",
    ),
    compile_bundle: bool = typer.Option(
        False,
        "--compile",
        help=(
            "Also compile the merged activation into "
            ".kittify/charter/charter.yaml by chaining the existing "
            "`spec-kitty charter generate --no-from-interview` seam (no new "
            "compiler is introduced). Requires a git repository -- inherits "
            "`charter generate`'s git-worktree requirement. The default "
            "merge (without this flag) stays git-agnostic."
        ),
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Apply a built-in charter pack's activation keys into .kittify/config.yaml (#3064).

    User Customization Preservation: by default this is an additive merge —
    a ``config.yaml`` key the pack declares is only written when it is
    currently absent. An already-present key (even an empty list a user
    explicitly authored) is left untouched unless ``--force`` is passed, in
    which case every key the pack declares is overwritten.

    Pass ``--compile`` to also chain the existing compile seam
    (``spec-kitty charter generate --no-from-interview``) so
    ``.kittify/charter/charter.yaml`` is produced in the same step. That
    flag requires a git repository (inherited from ``generate``); the
    default merge (no ``--compile``) stays a pure, git-agnostic additive
    merge (C-004).
    """
    pack_path = _resolve_pack_path_or_exit(name, json_output=json_output)

    config_path = repo_root / ".kittify" / "config.yaml"
    yaml = YAML()
    yaml.preserve_quotes = True
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.load(fh) or {}
    else:
        data = {}
    if not isinstance(data, dict):
        console.print("[red]Error:[/red] .kittify/config.yaml root must be a mapping.")
        raise typer.Exit(1)

    pack_data = load_pack_yaml(pack_path)
    keys_written, keys_skipped = merge_pack_into_config(data, pack_data, force=force)

    if keys_written:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh)

    compiled_files = _apply_compile_bridge(
        repo_root, compile_bundle, json_output=json_output, pack_name=name
    )

    result = {
        "pack": name,
        "path": str(pack_path),
        "config_path": str(config_path),
        "keys_written": keys_written,
        "keys_skipped": keys_skipped,
        "force": force,
        "compiled": compile_bundle,
        "compiled_files": compiled_files,
    }
    if json_output:
        typer.echo(json.dumps(result, indent=2))
        return

    if keys_written:
        console.print(
            f"[green]Applied charter pack '{name}':[/green] wrote {', '.join(keys_written)}"
        )
    else:
        console.print(
            f"[yellow]No keys written for pack '{name}'.[/yellow] All target keys "
            "already present in config.yaml; pass --force to overwrite them."
        )
    if keys_skipped:
        console.print(
            f"[dim]Skipped (already present; use --force to overwrite):[/dim] "
            f"{', '.join(keys_skipped)}"
        )

    if compile_bundle:
        written = ", ".join(compiled_files) if compiled_files else ".kittify/charter/charter.yaml"
        console.print(f"[green]Compiled charter bundle:[/green] wrote {written}")
    else:
        # T010: name the exact next command instead of a vague "may still be
        # needed" -- config.yaml alone is not read by `charter context` /
        # `charter status`; only the compiled `charter.yaml` is.
        console.print(
            "[dim]Next:[/dim] review activations with `spec-kitty charter list`, "
            "then run `spec-kitty charter generate` to compile this into "
            ".kittify/charter/charter.yaml -- that step (not this merge) is "
            "what delivers working governance to `charter context` / "
            "`charter status`. (Or re-run this command with --compile to do "
            "both in one step.)"
        )
