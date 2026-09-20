"""``spec-kitty charter synthesize`` command (WP06 per-subcommand split).

Synthesis-pipeline helpers live in
:mod:`specify_cli.cli.commands.charter._synthesis`. The body here stays close
to its original layout so the FR-001 strict-JSON envelope contract is
trivially diffable against the legacy ``charter.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from charter.activation.evidence.orchestrator import ConfigShapeError
from charter.bundle import CHARTER_YAML
from kernel.errors import KittyInternalConsistencyError
from specify_cli.cli.console import err_console

from specify_cli.diagnostics import mark_invocation_succeeded
from specify_cli.task_utils import TaskCliError

from specify_cli.cli.commands.charter._app import charter_app, console
from specify_cli.cli.commands.charter._charter_write_root import (
    CharterWriteRootError,
    resolve_charter_write_root,
)

# Helpers that tests never patch (``_has_generated_artifacts``,
# ``_catalog_is_established``, ``_materialize_fresh_doctrine``,
# ``_planned_fresh_doctrine_paths``, and the WP03 reconciliation-reporting
# helpers below) can be imported directly. The patchable helpers
# (``_build_synthesis_request``, ``_collect_evidence_result``,
# ``_load_written_artifacts_from_manifest``,
# ``_run_synthesis_dry_run_with_artifacts``) are routed via ``_charter_pkg``
# below.
from specify_cli.cli.commands.charter._synthesis import (
    _catalog_is_established,
    _emit_dry_run_report,
    _emit_orphan_refusal,
    _emit_real_run_report,
    _has_generated_artifacts,
    _materialize_fresh_doctrine,
    _orphaned_removals,
    _planned_fresh_doctrine_deletes,
    _planned_fresh_doctrine_paths,
    _print_synthesis_commit_reminder,
    _raise_if_bundle_incomplete,
    _reconciliation_preview,
)

# NOTE: ``find_repo_root`` and the patchable synthesis helpers are intentionally
# looked up via the package module at call time (not bound at import time).
# Legacy tests patch ``specify_cli.cli.commands.charter.<name>`` and expect the
# patched value to be visible from this command body. Importing the package as
# a module reference and accessing attributes at call time preserves that
# contract across the WP06 split.
import specify_cli.cli.commands.charter as _charter_pkg

__all__ = ["charter_synthesize"]


def _coerce_cli_bool(value: bool) -> bool:
    """Coerce a non-``bool`` Typer sentinel to ``False`` (defense in depth).

    WP03 amendment #3 (charter-synthesize-reconciliation-01KZJQN6):
    ``charter_synthesize`` is also invoked **in-process** by
    ``activate.py``/``deactivate.py`` (WP05). When such a caller omits the
    ``prune``/``dry_run`` keyword, Python's own default-argument mechanism
    supplies whatever ``typer.Option(False, "--prune", ...)`` returned at
    *function-definition* time -- an ``OptionInfo`` sentinel object, never
    the declared ``False`` -- because Typer's CLI parser (not Python) is
    normally the one that resolves that sentinel to a real value before
    calling the function. WP05 owns the authoritative fix (always pass the
    flag explicitly); this coercion is a belt-and-braces guard so a future
    in-process caller that forgets the explicit flag can never silently
    trigger a prune or dry-run.
    """
    return value if isinstance(value, bool) else False


@charter_app.command("synthesize")
def charter_synthesize(  # noqa: C901
    # WP02 / FR-001..FR-005: this command body is the strict-JSON
    # envelope-emit point. Branches are deliberate: fresh-seed (dry-run +
    # real), evidence-dry-run, dry-run, real-run, and four typed
    # exception envelopes. Splitting them into helper functions would
    # obscure the FR-001 stdout contract — every branch must end with
    # exactly one ``json.dumps`` call when ``--json`` is set.
    adapter: str = typer.Option(
        "generated",
        "--adapter",
        help=("Adapter to use. 'generated' (default) validates agent-authored YAML under .kittify/charter/generated/. 'fixture' is offline/testing only."),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Stage and validate artifacts but do not promote to live tree. "
            "Also reports the reconciliation delta --prune would remove. "
            "Wins over --prune when both are given (preview only, no write)."
        ),
    ),
    prune: bool = typer.Option(
        False,
        "--prune",
        help=(
            "Remove on-disk content the current run no longer targets and "
            "list every deletion. Without this flag, that content is "
            "preserved (default) unless it is orphaned (backing artifact "
            "deleted), which refuses instead of silently keeping a "
            "dangling reference."
        ),
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
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
    dry_run_evidence: bool = typer.Option(
        False,
        "--dry-run-evidence",
        help="Print evidence summary and exit without running synthesis.",
    ),
) -> None:
    """Validate and promote agent-generated project-local doctrine artifacts.

    Reads the charter interview answers, resolves synthesis targets from the
    DRG + doctrine, and writes all artifacts to ``.kittify/doctrine/``.

    Doctrine generation is performed by the LLM harness (Claude Code, Codex,
    Cursor, etc.) via the spec-kitty-charter-doctrine skill. This command
    validates and promotes the artifacts the agent has written.

    Fresh-project behavior (issue #839 / WP06 T031-T033)
    ----------------------------------------------------
    On a fresh project where ``.kittify/charter/generated/`` is missing or
    empty (i.e. the LLM harness has not yet written agent artifacts), this
    command short-circuits the adapter pipeline and materializes the
    **minimal artifact set** the runtime requires:

    1. ``.kittify/doctrine/`` — directory marker. ``DoctrineService``'s
       project-root resolver (``src/charter/activation/_doctrine_paths.py``) is a
       presence-only check; an empty directory is a valid project layer.
    2. ``.kittify/doctrine/PROVENANCE.md`` — human-readable record of the
       fresh-project seed path, citing #839.

    The runtime falls back to the built-in doctrine (``packs/built-in/``) for
    all artifact lookups until the harness writes per-target YAML and the
    operator re-runs ``synthesize`` (which then takes the normal adapter
    path). The fresh-project path is **idempotent**: re-running produces
    bytewise-identical output (T033). Charter prerequisites are still
    enforced — ``charter.md`` must exist (else ``TaskCliError`` is raised
    via ``_build_synthesis_request``).

    Examples
    --------
    Validate + promote generated artifacts written by the harness::

        spec-kitty charter synthesize

    Validate + promote with fixture adapter (offline/testing)::

        spec-kitty charter synthesize --adapter fixture

    Dry-run (stage + validate, no promote)::

        spec-kitty charter synthesize --dry-run

    Preserve-and-warn default (WP03): a plain run never drops backed
    content -- it exits 0 and reports what it retained. Remove divergent
    content explicitly::

        spec-kitty charter synthesize --prune

    Only orphaned content (backing artifact deleted) or an unparseable
    on-disk overlay make a plain run refuse (exit 1); backed divergence is
    always preserved and reported, never a refusal.
    """
    from charter.activation.synthesizer.errors import NeutralityGateViolation, SynthesisError, render_error_panel
    from charter.activation.synthesizer.reconcile import DRGLoadError

    # WP03 amendment #3 (defense in depth): coerce a non-bool prune/dry_run
    # sentinel to False before any mode-selection logic acts on it. See
    # _coerce_cli_bool's docstring for the in-process-call footgun this
    # guards against.
    prune = _coerce_cli_bool(prune)
    dry_run = _coerce_cli_bool(dry_run)

    # FR-001: warnings collected so far. Initialised here (outside the
    # try/except) so failure-branch envelopes can carry the same
    # warnings the success branch would have surfaced — i.e. an
    # evidence warning followed by a synthesis error still ships its
    # warning inside the envelope rather than losing it.
    warnings_collected: list[str] = []

    try:
        # #4785 Finding 3 / FR-006 / NFR-004: fail closed BEFORE any root
        # resolution when invoked from a linked git worktree. Deliberately
        # probed against the raw invocation cwd, NOT the already-resolved
        # ``find_repo_root()`` result below -- that helper follows a linked
        # worktree's ``.git`` pointer back to the PRIMARY checkout by
        # contract (C-002, not changed here), which would silently mask the
        # very condition this guard exists to catch.
        resolve_charter_write_root(Path.cwd())

        repo_root = _charter_pkg.find_repo_root()

        # T032 (#839 fresh-project): When the operator runs synthesize on a
        # fresh project (post `charter generate` but before the LLM harness
        # has written YAMLs under .kittify/charter/generated/), the production
        # adapter has nothing to load and would raise GeneratedArtifactMissingError.
        # The intercept below takes the bounded fresh-project path: it requires
        # the authoritative charter.yaml to exist (the upstream `charter
        # generate` produced it) AND no agent-authored doctrine YAMLs to be
        # present. When both signals fire, we materialize the minimal
        # .kittify/doctrine/ artifact set documented in T031 so the runtime can
        # advance via the built-in doctrine fallback.
        #
        # Gating signal re-pointed from charter.md to charter.yaml for the
        # consolidate-charter-bundle inversion (#2773): post-inversion
        # charter.yaml is the authoritative charter the compiler writes, while
        # charter.md is a display-only companion (INV-3 — never a resolving
        # signal). Pre-#2773 this keyed on charter.md, which never fired on a
        # real fresh project once generate stopped emitting charter.md, so
        # synthesize fell through to the production adapter and crashed.
        # charter.yaml is the canonical fresh-project signal; when it is absent
        # we fall through to the existing pipeline so callers that mock
        # charter.activation.synthesizer.synthesize keep their established behaviour.
        charter_yaml = repo_root / CHARTER_YAML
        is_fresh_project_synthesize = adapter == "generated" and not _has_generated_artifacts(repo_root) and not dry_run_evidence and charter_yaml.is_file()

        if is_fresh_project_synthesize:
            from specify_cli.cli.commands.charter._fresh_doctrine import _synthesize_project_doctrine

            # ``_synthesize_project_doctrine`` runs regardless of the
            # #4785 Finding 2-core established-store check below: it has its
            # OWN internal ``scan_project_artifacts`` gate and only preserves
            # (never destructively resets) real registered direct-write
            # project artifacts -- a distinct, non-destructive mechanism from
            # the raw minimal-seed materialization further down, and one an
            # established store may legitimately still need (e.g. a
            # dry-run/idempotent preview of already-registered content).
            project_result = _synthesize_project_doctrine(repo_root, dry_run=dry_run)
            if project_result is not None:
                if json_output:
                    print(json.dumps(project_result, indent=2, sort_keys=True))
                else:
                    operation = "would preserve" if dry_run else "preserved"
                    console.print(f"[green]Charter synthesis[/green]: {operation} project doctrine and provenance.")
                    for warning in project_result["warnings"]:
                        console.print(f"[yellow]Warning[/yellow]: {warning}")
                mark_invocation_succeeded()
                return

            # #4785 Finding 2-core: no registered direct-write project
            # artifacts either. Before materializing the DESTRUCTIVE minimal
            # built-in-only seed, confirm this store hasn't ALREADY been
            # really activated and/or really synthesized -- an established
            # store whose ``generated/`` directory merely happens to be
            # empty right now must NOT be reset to the minimal seed (that
            # would silently discard its real state, the exact bug #4785
            # reproduced). An established store falls through past this
            # whole branch to the normal (non-fresh) adapter pipeline below,
            # which fails loud/actionable if ``generated/`` really is
            # required and missing -- never a silent built-in-only reset.
            if not _catalog_is_established(repo_root, charter_yaml):
                # FR-002 / FR-003 / FR-005: fresh-project seed mode emits the
                # strict four-field envelope. ``written_artifacts`` is built from
                # the already-known minimal seed file list (PROVENANCE.md). No
                # adapter actually ran, so ``adapter.id`` is the documented
                # internal "fresh-seed" sentinel — non-empty per AdapterRef
                # invariant — and ``adapter.version`` is the running CLI version.
                # ``warnings`` is intentionally empty: evidence collection has
                # not been triggered on this branch.
                from importlib.metadata import version as _pkg_version

                try:
                    _seed_version = _pkg_version("spec-kitty-cli")
                except Exception:
                    _seed_version = "unknown"

                if dry_run:
                    planned = _planned_fresh_doctrine_paths(repo_root)
                    planned_deletes = _planned_fresh_doctrine_deletes(repo_root)
                    fresh_written_artifacts: list[dict[str, Any]] = [
                        {
                            "path": p,
                            "kind": "seed",
                            "slug": "provenance",
                            "artifact_id": None,
                        }
                        for p in planned
                    ]
                    if json_output:
                        print(
                            json.dumps(
                                {
                                    # FR-002 contracted fields:
                                    "result": "dry_run",
                                    "adapter": {"id": "fresh-seed", "version": _seed_version},
                                    "written_artifacts": fresh_written_artifacts,
                                    "warnings": [],
                                    # Compatibility / fresh-seed identification fields:
                                    "success": True,
                                    "mode": "fresh_project_seed_dry_run",
                                    "files_planned": planned,
                                    "planned_deletes": planned_deletes,
                                    "note": ("Fresh project + --dry-run: would materialize minimal .kittify/doctrine/ (no files written). See issue #839."),
                                },
                                indent=2,
                                sort_keys=True,
                            )
                        )
                        mark_invocation_succeeded()
                        return
                    console.print("[yellow]Charter synthesis (fresh project, dry-run)[/yellow]: would materialize minimal .kittify/doctrine/ (no files written).")
                    for f in planned:
                        console.print(f"  • {f}")
                    for f in planned_deletes:
                        console.print(f"  delete {f}")
                    return

                written = _materialize_fresh_doctrine(repo_root)
                fresh_written_artifacts = [
                    {
                        "path": p,
                        "kind": "seed",
                        "slug": "provenance",
                        "artifact_id": None,
                    }
                    for p in written
                ]

                if json_output:
                    print(
                        json.dumps(
                            {
                                # FR-002 contracted fields:
                                "result": "success",
                                "adapter": {"id": "fresh-seed", "version": _seed_version},
                                "written_artifacts": fresh_written_artifacts,
                                "warnings": [],
                                # Compatibility / fresh-seed identification fields:
                                "success": True,
                                "mode": "fresh_project_seed",
                                "files_written": written,
                                "note": (
                                    "Fresh project: no agent-authored YAML under "
                                    ".kittify/charter/generated/. Materialized minimal "
                                    ".kittify/doctrine/ so the runtime can advance "
                                    "(see issue #839)."
                                ),
                            },
                            indent=2,
                            sort_keys=True,
                        )
                    )
                    mark_invocation_succeeded()
                    return

                console.print("[green]Charter synthesis (fresh project)[/green]: minimal .kittify/doctrine/ materialized.")
                for f in written:
                    console.print(f"  ✓ {f}")
                _print_synthesis_commit_reminder()
                return
            # else: established store -- fall through past the whole
            # ``if is_fresh_project_synthesize:`` branch to the normal
            # adapter pipeline below.

        # FR-001: when --json is set, evidence warnings MUST live inside the
        # envelope's ``warnings`` array, NOT on stdout. The previous
        # implementation called ``console.print`` here unconditionally,
        # which broke ``json.loads(stdout)`` for any run that produced
        # warnings (the bug behind FR-001 / AC-001).
        evidence_result = _charter_pkg._collect_evidence_result(
            repo_root,
            skip_code_evidence=skip_code_evidence,
            skip_corpus=skip_corpus,
        )
        warnings_collected.extend(str(w) for w in evidence_result.warnings)
        if not json_output:
            for warning in warnings_collected:
                console.print(f"[yellow]⚠ {warning}[/yellow]")

        if dry_run_evidence:
            bundle = evidence_result.bundle
            if json_output:
                # FR-001 / FR-002: evidence dry-run also emits the strict
                # envelope. ``written_artifacts`` is empty because no
                # synthesis ran; warnings live in the ``warnings`` array.
                print(
                    json.dumps(
                        {
                            # Contracted fields (FR-002):
                            "result": "success",
                            "adapter": {"id": adapter, "version": "evidence-dry-run"},
                            "written_artifacts": [],
                            "warnings": warnings_collected,
                            # Compatibility / mode-identification fields:
                            "mode": "evidence_dry_run",
                            "evidence": {
                                "code_signals": (
                                    {
                                        "stack_id": bundle.code_signals.stack_id,
                                        "primary_language": bundle.code_signals.primary_language,
                                        "representative_files_count": len(bundle.code_signals.representative_files),
                                    }
                                    if bundle.code_signals
                                    else None
                                ),
                                "url_list_count": len(bundle.url_list),
                                "corpus": (
                                    {
                                        "snapshot_id": bundle.corpus_snapshot.snapshot_id,
                                        "entries_count": len(bundle.corpus_snapshot.entries),
                                    }
                                    if bundle.corpus_snapshot
                                    else None
                                ),
                            },
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
                mark_invocation_succeeded()
                raise typer.Exit(0)

            console.print("[bold]Evidence dry-run summary:[/bold]")
            if bundle.code_signals:
                cs = bundle.code_signals
                console.print(f"  Code signals: stack={cs.stack_id}, lang={cs.primary_language}")
                console.print(f"  Representative files: {len(cs.representative_files)} found")
            else:
                console.print("  Code signals: none (skipped or not detected)")
            console.print(f"  URL list: {len(bundle.url_list)} URL(s) configured")
            if bundle.corpus_snapshot:
                console.print(f"  Corpus: {bundle.corpus_snapshot.snapshot_id} ({len(bundle.corpus_snapshot.entries)} entries)")
            else:
                console.print("  Corpus: none")
            for w in warnings_collected:
                console.print(f"  [yellow]Warning: {w}[/yellow]")
            raise typer.Exit(0)

        request, syn_adapter = _charter_pkg._build_synthesis_request(repo_root, adapter, evidence=evidence_result.bundle)

        if dry_run:
            # FR-003 / FR-004: ``written_artifacts`` for dry-run comes from
            # the SAME ``compute_written_artifacts`` helper the real-run
            # path uses. Paths are byte-equal to what a non-dry-run with the
            # same SynthesisRequest would write (the parity guarantee that
            # tests/charter/synthesizer/test_synthesize_path_parity.py
            # locks in). FR-010: planned_deletes/conflicts is the NEW
            # reconciliation-delta preview (_reconciliation_preview, adapter
            # free) added to the same envelope by _emit_dry_run_report. An
            # unparseable on-disk overlay raises DRGLoadError here, caught
            # below (FR-007 fail-closed, no write in either branch).
            staged_files, written_artifacts_dr = _charter_pkg._run_synthesis_dry_run_with_artifacts(request, syn_adapter, repo_root)
            delta = _reconciliation_preview(request, repo_root)
            _emit_dry_run_report(
                json_output=json_output,
                adapter_name=adapter,
                syn_adapter=syn_adapter,
                warnings_collected=warnings_collected,
                staged_files=staged_files,
                written_artifacts_dr=written_artifacts_dr,
                delta=delta,
            )
            return

        # #2758: fail closed BEFORE the real-run write path can persist an
        # un-healable None bundle-content hash into the synthesis manifest
        # (see _raise_if_bundle_incomplete docstring). Dry-run never reaches
        # write_pipeline.promote(), so it is intentionally not gated there.
        _raise_if_bundle_incomplete(repo_root)

        from charter.activation.synthesizer import synthesize
        from charter.activation.synthesizer.reconcile import SynthesizeMode

        # FR-007: an unparseable on-disk overlay raises DRGLoadError from
        # INSIDE this call (reconcile_synthesis runs before any write, in
        # every mode) -- caught below, no write happens either way.
        result = synthesize(
            request,
            adapter=syn_adapter,
            repo_root=repo_root,
            mode=SynthesizeMode.prune if prune else SynthesizeMode.preserve,
        )

        # #4121 (MAJOR 2): unresolved project-profile reference warnings from
        # the overlay emission ride on the result — surface them on the CLI
        # and in the --json envelope instead of leaving them in logging
        # output only. ``getattr`` keeps a mocked ``synthesize`` (tests never
        # write a manifest, let alone emit references) on the empty default.
        reference_warnings = list(getattr(result, "reference_warnings", ()))
        warnings_collected.extend(reference_warnings)
        if not json_output:
            for warning in reference_warnings:
                console.print(f"[yellow]⚠ {warning}[/yellow]")

        # FR-014 / T014: narrow refusal -- a plain (non-`--prune`) run that
        # dropped (preserve mode never deletes, so nothing was actually
        # destroyed by the write above) orphaned (backing-artifact-deleted)
        # content refuses instead of reporting success, so a dangling
        # reference is never silently reported as a clean preserve. Backed
        # divergence is never a refusal case (US2 AC4) -- it is preserved
        # and reported below.
        orphaned = _orphaned_removals(getattr(result, "reconciliation", None))
        if orphaned and not prune:
            _emit_orphan_refusal(
                json_output=json_output,
                adapter_name=adapter,
                warnings_collected=warnings_collected,
                orphaned=orphaned,
            )

        # FR-003: ``written_artifacts`` is sourced from the on-disk
        # synthesis manifest the write pipeline wrote last (KD-2 commit
        # marker). Each entry's ``artifact_id`` is read from the matching
        # provenance sidecar — never reconstructed by parsing the filename.
        # When ``synthesize()`` is mocked out by tests (the manifest is
        # never written), this returns ``[]`` and the four contracted
        # fields are still emitted (INV-E-2: empty list != absent field).
        written_artifacts_real = _charter_pkg._load_written_artifacts_from_manifest(repo_root)

        _emit_real_run_report(
            json_output=json_output,
            result=result,
            written_artifacts_real=written_artifacts_real,
            warnings_collected=warnings_collected,
            prune=prune,
        )

    except typer.Exit:
        raise
    except DRGLoadError as e:
        # FR-007 / T014: the on-disk project overlay could not be parsed.
        # The library seam (reconcile.py) already failed closed -- no write
        # happened -- this branch only turns that library exception into the
        # CLI's clean, actionable refusal instead of falling through to the
        # generic "Unexpected error" branch below.
        detail = (
            f"Refused: the on-disk doctrine overlay could not be parsed ({e}). "
            "No write was made. Repair or remove the corrupt overlay under "
            ".kittify/doctrine/ and re-run `spec-kitty charter synthesize`."
        )
        if json_output:
            print(
                json.dumps(
                    {
                        "result": "failure",
                        "adapter": {"id": adapter, "version": "unknown"},
                        "written_artifacts": [],
                        "warnings": warnings_collected + [detail],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            err_console.print(f"[red]Error:[/red] {detail}")
        raise typer.Exit(code=1) from e
    except NeutralityGateViolation as e:
        # Stderr-only (R-001): human-readable progress remains permitted on
        # stderr in --json mode. The error panel never reaches stdout.
        render_error_panel(e, err_console)
        err_console.print(
            f"\n[yellow]Staging directory preserved at:[/yellow] {e.staging_dir}\nInspect the staged artifacts, adjust the synthesis prompt or scope, and retry."
        )
        if json_output:
            # FR-001: even in failure mode, stdout MUST contain exactly one
            # JSON document. The error message is appended to whatever
            # warnings were already collected so callers reading only
            # stdout still see both.
            print(
                json.dumps(
                    {
                        "result": "failure",
                        "adapter": {"id": adapter, "version": "unknown"},
                        "written_artifacts": [],
                        "warnings": warnings_collected + [f"NeutralityGateViolation: {e}"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        raise typer.Exit(code=1) from e
    except SynthesisError as e:
        from charter.activation.synthesizer.errors import GeneratedArtifactMissingError as _GAME

        render_error_panel(e, err_console)
        if isinstance(e, _GAME):
            # Actionable remediation: the adapter found no agent-authored
            # YAML, which usually means `charter generate` was never run.
            _charter_hint = (
                "Charter prerequisite missing: no generated charter artifacts found. "
                "Run `spec-kitty charter generate` (or `charter interview` first) "
                "to produce the artifacts that synthesis needs."
            )
            if json_output:
                print(
                    json.dumps(
                        {
                            "result": "failure",
                            "adapter": {"id": adapter, "version": "unknown"},
                            "written_artifacts": [],
                            "warnings": warnings_collected + [_charter_hint],
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                console.print(f"[red]Error:[/red] {_charter_hint}")
            raise typer.Exit(code=1) from e

        if json_output:
            print(
                json.dumps(
                    {
                        "result": "failure",
                        "adapter": {"id": adapter, "version": "unknown"},
                        "written_artifacts": [],
                        "warnings": warnings_collected + [f"SynthesisError: {e}"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        raise typer.Exit(code=1) from e
    except (TaskCliError, ConfigShapeError) as e:
        # ConfigShapeError (a corrupt/non-mapping .kittify/config.yaml, ledger
        # SK-16) is a controlled, expected diagnostic -- treated the same as
        # TaskCliError, not routed through the generic "Unexpected error"
        # branch below.
        if json_output:
            print(
                json.dumps(
                    {
                        "result": "failure",
                        "adapter": {"id": adapter, "version": "unknown"},
                        "written_artifacts": [],
                        "warnings": warnings_collected + [str(e)],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e
    except CharterWriteRootError as e:
        # #4785 Finding 3 / FR-006: the write-root guard already fails
        # closed with the exact, actionable remedy text -- no additional
        # framing needed beyond routing it through the FR-001 envelope
        # contract like every other typed failure here. The BASE class is
        # caught so any write-root failure mode fails closed identically.
        detail = str(e)
        if json_output:
            print(
                json.dumps(
                    {
                        "result": "failure",
                        "adapter": {"id": adapter, "version": "unknown"},
                        "written_artifacts": [],
                        "warnings": warnings_collected + [detail],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            err_console.print(f"[red]Error:[/red] {detail}")
        raise typer.Exit(code=1) from e
    except KittyInternalConsistencyError as e:
        # Contract (kernel.errors): CLI/UI layers catch this base type to render
        # the diagnostic uniformly. Surface both the code AND the informative
        # `.body` instead of swallowing it into "Unexpected error: <code>"
        # (#2850 follow-up — the CHARTER_PACK_CONFIG_INVALID body was invisible).
        detail = f"{e.code}: {e.body}" if e.body else e.code
        if json_output:
            print(
                json.dumps(
                    {
                        "result": "failure",
                        "adapter": {"id": adapter, "version": "unknown"},
                        "written_artifacts": [],
                        "warnings": warnings_collected + [detail],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            console.print(f"[red]Error:[/red] {detail}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        if json_output:
            print(
                json.dumps(
                    {
                        "result": "failure",
                        "adapter": {"id": adapter, "version": "unknown"},
                        "written_artifacts": [],
                        "warnings": warnings_collected + [f"Unexpected error: {e}"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(code=1) from e
