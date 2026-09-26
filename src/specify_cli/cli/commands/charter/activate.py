"""spec-kitty charter activate — activate a doctrine artifact.

FR-004 (direct activation), FR-008 (in-flight step-removal warning),
FR-013/FR-014 (cascade scope), FR-035 (fail-closed on invalid pack config).

Wiring (R-011-D, Contracts C3.2/C3.3, C1.5)
-------------------------------------------
This is the live caller that finally wires the WP10 plan/commit engine and the
WP11 scoped cascade engine into the CLI surface:

* ``--cascade`` is parsed through :meth:`charter.activation.cascade.CascadeScope.parse`
  (WP11) into a real scope value object — it is **never** collapsed to a bool
  (Contract C3.3). Absence of ``--cascade`` routes through
  :func:`charter.activation.cascade.referenced_but_not_cascaded` so the operator is warned
  about referenced-but-skipped artifacts (FR-013).
* In-scope cascade targets (:func:`charter.activation.cascade.cascade_activation_targets`)
  are activated through the same :class:`~charter.activation.pack_manager.CharterPackManager`
  seam as the direct activation, and rendered per kind (FR-014).
* :class:`charter.activation.pack_context.CharterPackConfigError` is caught and surfaced as
  a clean exit-1 with its diagnostic code + remediation, before any mutation
  (FR-035 fail-closed, C1.5).
"""

from __future__ import annotations

import contextlib
from specify_cli.core.constants import KITTY_SPECS_DIR
from pathlib import Path

import typer
from rich.console import Console
from specify_cli.cli.console import console

from charter.activation.cascade import (
    CascadeScope,
    cascade_activation_targets,
    referenced_but_not_cascaded,
)
from charter.drg import DRGLoadError
from charter.activation.catalog import resolve_doctrine_root
from charter.activation.drg_activation import load_org_drg
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import (
    ArtifactKind,
    MissionTypeNotAnArtifactKind,
    UnknownArtifactIdError,
    resolve_artifact_urn,
)
from charter.activation.pack_context import CharterPackConfigError, PackContext
from charter.activation.pack_manager import YAML_KEY_MAP, CharterPackManager
from charter.activation.project_registration import (
    commit_project_registration,
    plan_project_registration,
)

from specify_cli.cli.commands.charter._cascade_shared import (
    drg_urn_to_config_id,
    render_kind_filtered_line,
)
from specify_cli.cli.commands.charter._charter_write_root import (
    CharterWriteRootError,
    resolve_charter_write_root,
)
from specify_cli.cli.commands.charter._layer_roots import (
    resolve_layer_roots,
    resolve_org_root_chain,
)

__all__ = ["activate_cmd", "run_full_synthesize"]

RESYNTHESIZE_HELP = (
    "Eagerly refresh the FULL derived bundle/DRG (bundle content hash + "
    "project DRG layer, not just the compiled catalog) after this "
    "activation via the EXISTING synthesize pipeline (the same one "
    "`charter generate` + `charter synthesize` use). Default activation "
    "already recompiles `catalog.references` on its own via `charter "
    "generate`'s own compile seam (see --no-compile to opt out of that "
    "lightweight recompile); --resynthesize goes further and reconciles "
    "the freshness signal to fresh immediately (NFR-001)."
)

NO_COMPILE_HELP = (
    "Skip the default post-activation catalog recompile (FR-003): the fast "
    "config-only write from before issue #4785's fix. `catalog.references` "
    "is left as-is and may go stale until a later `charter generate` or "
    "`charter activate --resynthesize`."
)

#: FR-004 -- the explicit zero-activatable-targets message. Printed once,
#: never per-node, when the cascade resolved zero activatable targets AND at
#: least one referenced node was specifically kind-filtered (never for a
#: source with zero referenced nodes at all, and never for a pure
#: scope-narrowing case -- see the exact trigger condition in
#: `_render_cascade_activation` below).
CASCADE_ZERO_ACTIVATABLE_TARGETS_MESSAGE = (
    "[yellow]Cascade resolved zero activatable targets[/yellow] "
    "(every referenced node was kind-filtered; see the lines above)."
)



def render_pack_config_error(exc: CharterPackConfigError, console: Console) -> None:
    """Render a :class:`CharterPackConfigError` as fail-closed CLI guidance (FR-035).

    Surfaces the stable ``CHARTER_PACK_CONFIG_INVALID`` diagnostic code plus the
    error body (which already carries the remediation hint). Shared by the
    activate and deactivate commands so both fail closed identically.
    """
    console.print(f"[red]Error[/red] ({exc.code}): {exc.body}")


def validate_pack_config(repo_root: Path) -> None:
    """Load the project pack context to fail closed on invalid config (FR-035).

    :meth:`PackContext.from_config` raises :class:`CharterPackConfigError` when
    ``.kittify/config.yaml`` has an invalid charter-pack shape. Calling it here
    — *before* any mutation — gives that previously dead-ended error type a live
    external caller and guarantees no write happens on a malformed config (C1.5).
    """
    PackContext.from_config(repo_root)


def _source_urn(
    kind: str,
    artifact_id: str,
    layer_roots: dict[str, Path] | None,
    org_roots: list[Path] | None = None,
) -> str | None:
    """Resolve the DRG source URN for ``(kind, config-stem artifact_id)``.

    Returns ``None`` when the kind has no DRG artifact-node representation
    (``mission-type``) or the artifact has no resolvable DRG node — cascade is a
    no-op in those cases rather than an error.

    ``org_roots`` (T008/T009, mission ``cascade-org-inert-01M07E9P``): the
    full declaration-ordered org-pack chain, additive to ``layer_roots``'s
    single-pack-only ``roots["org"]`` — so a direct-activation target that
    lives only in org pack 2..N still resolves, not just pack 1's.
    """
    try:
        kind_enum = ArtifactKind.from_operator_token(kind)
    except MissionTypeNotAnArtifactKind:
        return None
    try:
        resolved: str = resolve_artifact_urn(
            kind_enum,
            artifact_id,
            doctrine_root=resolve_doctrine_root(),
            org_roots=org_roots,
            layer_roots=layer_roots,
        )
        return resolved
    except UnknownArtifactIdError:
        return None


def _emit_step_removal_warnings(kind: str, artifact_id: str, repo_root: Path) -> None:
    """Emit in-flight step-removal warnings for the activation (FR-008).

    Generalized out of the command body: the command no longer branches on
    ``kind == "mission-type"`` inline — it always calls this collector, which is
    a no-op for kinds that have no step-sequence semantics. Mission-type
    activations still surface the in-flight warning, now via this single seam.
    """
    if kind != "mission-type":
        return

    from specify_cli.charter_activate import (  # noqa: PLC0415
        emit_step_removal_warnings,
        find_removed_steps,
        scan_inflight_missions,
    )
    from specify_cli.cli.commands.charter.mission_type import (  # noqa: PLC0415
        resolve_layered_roster,
    )

    try:
        from charter.activation.mission_type_profiles import (  # noqa: PLC0415
            UnknownMissionTypeError,
            resolve_mission_type_context,
        )

        current_seq: list[str] = resolve_mission_type_context(
            repo_root, mission_type=artifact_id
        ).action_sequence
    except UnknownMissionTypeError:
        # FR-009: not yet activated (or no resolvable profile) -- there is no
        # previous state to compare against, so "no steps were removed" is
        # correct here, not a silent degrade. Any OTHER resolution failure --
        # e.g. WP06's MissionTypeEmptyActionSequenceError, raised when a
        # previously-active non-built-in type's action sequence cannot be
        # resolved at all -- MUST surface rather than being folded into this
        # same "no previous state" branch (spec.md Edge Cases: "must surface
        # that resolution failure rather than silently treating 'cannot
        # resolve' as 'no steps were removed'"). The bare `except Exception`
        # this replaces used to swallow that case too.
        current_seq = []

    # FR-009: the layered roster (built-in -> org -> project), not the
    # built-in-only MissionTypeRepository.default() -- a non-built-in type's
    # incoming (about-to-be-activated) action sequence was previously always
    # invisible here, so its removed steps were never detected.
    mt = resolve_layered_roster(repo_root).get(artifact_id)
    # Optional-narrowing (WP07 S-B cutover): `MissionType.action_sequence` is
    # `list[str] | None` since WP01 (projection-sourced post-cutover, YAML no
    # longer carries a literal fallback) — narrow before `list()` for mypy --strict.
    incoming_seq: list[str] = list(mt.action_sequence or []) if mt is not None else []

    removed = find_removed_steps(current_seq, incoming_seq)
    if removed:
        step_warnings = scan_inflight_missions(removed, repo_root / KITTY_SPECS_DIR)
        emit_step_removal_warnings(step_warnings, console)


def _validate_mission_type_activatable(kind: str, artifact_id: str, repo_root: Path) -> None:
    """FR-001 preflight: refuse activation of an empty-action-sequence mission type."""
    if kind != "mission-type":
        return
    from charter.activation.mission_type_profiles import validate_activatable_mission_type  # noqa: PLC0415

    validate_activatable_mission_type(artifact_id, repo_root=repo_root)


def _activate_cascade_target(
    manager: CharterPackManager,
    ctx_project: ProjectContext,
    kind_token: str,
    config_id: str,
    layer_roots: dict[str, Path] | None,
    org_roots: list[Path] | None,
) -> None:
    """Activate one cascade target, trying each org root in the chain in turn.

    T009 (mission ``cascade-org-inert-01M07E9P``): :meth:`CharterPackManager.activate`
    validates artifact availability through its own ``layer_roots["org"]``
    single-``Path`` slot (``charter/pack_manager.py`` -- not owned by this WP;
    its ``dict[str, Path]`` contract is load-bearing for ``charter list
    --all-layers``, T013, so it cannot be widened there). A cascade target
    that the T008 org-roots chain correctly resolved (DRG visibility + ID
    mapping) to live in org pack 2..N would otherwise still fail here with
    "Unknown <kind> ID", because ``manager.activate``'s own availability scan
    only ever sees pack 1 through ``layer_roots``. This substitutes each
    candidate org root from the chain, in declaration order, for
    ``layer_roots["org"]`` and retries, so a chain artifact still activates
    without widening ``CharterPackManager.activate``'s signature. When
    ``org_roots`` is empty/``None`` (no org packs, or none in the chain),
    exactly one attempt is made with the original *layer_roots* -- byte-for-
    byte the pre-T008 call shape (FR-001 AC4 no-org-pack regression).

    R2-002 (pr-correctness.findings.yaml): when every candidate fails, the
    raised error aggregates every candidate's failure reason rather than
    surfacing only the last one. With a single candidate (the common
    no-org-pack / single-org-pack case) this is still byte-identical to
    raising that one exception directly -- aggregation only changes the
    multi-candidate "none of them worked" diagnostic, never the control
    flow or the success path.
    """
    candidate_layer_roots: list[dict[str, Path] | None] = (
        [{**(layer_roots or {}), "org": root} for root in org_roots]
        if org_roots
        else [layer_roots]
    )
    failures: list[ValueError] = []
    for candidate in candidate_layer_roots:
        try:
            manager.activate(
                ctx_project,
                kind_token,
                config_id,
                cascade=False,
                layer_roots=candidate,
            )
            return
        except ValueError as exc:
            failures.append(exc)
    if len(failures) == 1:
        raise failures[-1]
    joined = "; ".join(f"org root {i + 1}/{len(failures)}: {exc}" for i, exc in enumerate(failures))
    raise ValueError(
        f"No candidate org root could activate {kind_token}:{config_id} "
        f"({len(failures)} candidates tried): {joined}"
    ) from failures[-1]


def _render_cascade_activation(
    manager: CharterPackManager,
    ctx_project: ProjectContext,
    source_urn: str,
    scope: CascadeScope,
    repo_root: Path,
    layer_roots: dict[str, Path] | None,
) -> None:
    """Activate scoped cascade targets and render the outcome (FR-014).

    Walks the merged DRG from ``source_urn`` via the WP11 cascade engine, keeps
    only the kinds the scope selects, and activates each in-scope target through
    the same activation seam. Skipped-by-scope kinds are reported so the operator
    sees exactly what the explicit scope excluded.

    T009 (mission ``cascade-org-inert-01M07E9P``): threads the full,
    declaration-ordered org-pack chain into both the DRG load (so
    ``requires``/``suggests`` edges into/out of ANY configured org pack are
    visible to the cascade walk, not just none) and the DRG-ID-to-config-ID
    mapping below (so an org-pack-2..N target resolves to its real config-stem
    ID, not the raw DRG ID as a lossy fallback). Previously this call carried
    NO org roots at all.
    """
    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415

    org_roots = resolve_org_root_chain(repo_root)
    graph = load_validated_graph(
        repo_root,
        org_roots=org_roots,
        org_fragments=load_org_drg(repo_root, strict=False),
    )
    result = cascade_activation_targets(graph, source_urn, scope)
    doctrine_root = resolve_doctrine_root()

    for kind_value in sorted(result.activated):
        kind_token = ArtifactKind(kind_value).operator_token
        for cascade_drg_id in result.activated[kind_value]:
            # The cascade engine reports DRG bare IDs; activation lists use
            # config-stem IDs. Resolve back through the kind-vocabulary bridge.
            config_id = drg_urn_to_config_id(
                f"{kind_value}:{cascade_drg_id}", doctrine_root, layer_roots, org_roots
            )
            try:
                _activate_cascade_target(
                    manager, ctx_project, kind_token, config_id, layer_roots, org_roots
                )
            except ValueError as exc:
                console.print(
                    f"[yellow]Warning[/yellow]: could not cascade-activate "
                    f"{kind_token}/{config_id}: {exc}"
                )
                continue
            console.print(
                f"[cyan]Cascade-activated[/cyan]: {kind_token}/{config_id}"
            )

    for kind_value in sorted(result.skipped_by_scope):
        kind_token = ArtifactKind(kind_value).operator_token
        for skipped_id in result.skipped_by_scope[kind_value]:
            config_id = drg_urn_to_config_id(
                f"{kind_value}:{skipped_id}", doctrine_root, layer_roots, org_roots
            )
            console.print(
                f"[dim]Skipped (out of scope)[/dim]: {kind_token}/{config_id}"
            )

    # FR-003/FR-008 (issue #3705): render the kind-filtered nodes WP01's
    # shared `_referenced_artifacts` seam collected instead of silently
    # dropping them -- resolving each bare DRG id to its config-stem id
    # FIRST, the same call the `activated`/`skipped_by_scope` loops above
    # already make (an org-pack-2..N node's bare id and config-stem id can
    # differ; every other line in this function already prints the
    # operator-facing config-stem id).
    for kind_value in sorted(result.not_cascaded_kind_filtered):
        kind_token = ArtifactKind(kind_value).operator_token
        for filtered_id in result.not_cascaded_kind_filtered[kind_value]:
            config_id = drg_urn_to_config_id(
                f"{kind_value}:{filtered_id}", doctrine_root, layer_roots, org_roots
            )
            render_kind_filtered_line(kind_token, config_id)

    # FR-004: fires ONLY when the cascade resolved zero activatable targets
    # AND at least one referenced node was specifically kind-filtered --
    # never for a source with zero referenced nodes at all, and never when any
    # referenced node was scope-narrowed. The `not result.skipped_by_scope`
    # clause covers both the pure scope-narrowing case (every referenced node
    # is activatable-kind but excluded by a narrow --cascade <scope>) AND the
    # mixed case (some scope-narrowed, some kind-filtered): in either the
    # `Skipped (out of scope)` lines above already tell the full story (SC-007),
    # and the "every referenced node was kind-filtered" summary would be a
    # falsehood the moment a scope-skipped node exists. Deliberately NOT the
    # broader "zero landed in `activated`" condition.
    if (
        not result.activated
        and not result.skipped_by_scope
        and result.not_cascaded_kind_filtered
    ):
        console.print(CASCADE_ZERO_ACTIVATABLE_TARGETS_MESSAGE)


def _render_tension_warnings(repo_root: Path) -> None:
    """Surface unreconciled tension findings as activate-time warnings (FR-010).

    Calls the SAME scan :func:`charter.activation.consistency_check.scan_unreconciled_tensions`
    that ``spec-kitty charter pack consistency-check`` uses (single canonical
    authority, contracts/tension-finding.md SC-001) so this warning and that
    JSON surface can never render a tension pair differently.

    Builds its own fully-populated :class:`ProjectContext` via
    :meth:`ProjectContext.from_repo` (matching ``pack.py``'s consistency-check
    command) rather than reusing the caller's ``ctx_project`` -- the
    ``activate_cmd``/``deactivate_cmd`` local is a bare
    ``ProjectContext(repo_root=repo_root)`` with ``pack_context=None``, which
    would make :func:`scan_unreconciled_tensions` raise
    ``ContextPreconditionError`` on every call (a silent, permanent no-op --
    exactly the NFR-001 trap this finding exists to avoid).

    Best-effort, matching the existing DRG-load handling in this module (see
    ``_render_no_cascade_warning`` / ``_render_cascade_activation``, which
    already load the validated graph without a bespoke fail-closed path of
    their own): a DRG load failure here does not abort activation -- the
    fail-closed guarantee for this finding lives on the consistency-check
    surface (``ConsistencyReport.verification_errors``), which every project
    can run explicitly on demand.
    """
    from charter.activation.consistency_check import scan_unreconciled_tensions  # noqa: PLC0415

    try:
        scan_ctx = ProjectContext.from_repo(repo_root)
        findings = scan_unreconciled_tensions(scan_ctx)
    except Exception:  # noqa: BLE001 -- best-effort warning surface, not fail-closed here.
        return

    for finding in findings:
        side_a, side_b = finding.pair
        console.print(
            f"[yellow]Warning[/yellow]: {side_a} is in tension with "
            f"{side_b}. Resolve by: (1) deactivating one side, or "
            f"(2) activating a reconciler that bridges both."
        )


def _render_no_cascade_warning(
    source_urn: str,
    repo_root: Path,
    layer_roots: dict[str, Path] | None,
) -> None:
    """Warn about referenced-but-not-cascaded artifacts (FR-013, Contract C3.2).

    T009: threads the full org-pack chain into the DRG load and the ID
    mapping below, same rationale as ``_render_cascade_activation`` — an
    org-pack ``requires``/``suggests`` edge is invisible to this warning
    unless the DRG it walks actually contains org-pack nodes (FR-001 AC5).
    """
    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415

    org_roots = resolve_org_root_chain(repo_root)
    graph = load_validated_graph(
        repo_root,
        org_roots=org_roots,
        org_fragments=load_org_drg(repo_root, strict=False),
    )
    report = referenced_but_not_cascaded(graph, source_urn)
    if not report.has_skipped:
        return
    doctrine_root = resolve_doctrine_root()
    for kind_value in sorted(report.skipped):
        kind_token = ArtifactKind(kind_value).operator_token
        for skipped_drg_id in report.skipped[kind_value]:
            config_id = drg_urn_to_config_id(
                f"{kind_value}:{skipped_drg_id}", doctrine_root, layer_roots, org_roots
            )
            console.print(
                f"[yellow]Warning[/yellow]: referenced {kind_token}/{config_id} "
                f"was not activated (no --cascade)."
            )
    # FR-005a: gated on `report.skipped` specifically (not the broader
    # `has_skipped`) -- `recovery_hint` literally says "to activate the
    # referenced artifacts", which is only true of `skipped` entries.
    # Printing it for a source whose ONLY referenced nodes are kind-filtered
    # would be exactly the misleading "--cascade would fix this" recovery
    # hint FR-005's FAILS-if condition forbids for the per-node line -- this
    # extends the same guarantee to the summary Hint line. Pre-existing
    # behavior for every previously-reachable case (skipped non-empty) is
    # unchanged: this branch was unreachable before this WP (has_skipped was
    # `any(self.skipped.values())` alone, so reaching here already implied
    # `report.skipped` was non-empty).
    if report.skipped:
        console.print(f"[yellow]Hint[/yellow]: {report.recovery_hint}")

    # FR-005 (issue #3705): render the kind-filtered nodes WP01's shared
    # `_referenced_artifacts` seam collected instead of silently dropping
    # them, one render path over from `_render_cascade_activation` above --
    # via the SAME shared helper (FR-009) so the wording is identical and
    # never re-coined here. Never suggests `--cascade` as a recovery path:
    # re-running with `--cascade` would NOT activate an asset/template.
    # Resolves each bare DRG id to its config-stem id first, the same call
    # the `report.skipped` loop above already makes.
    for kind_value in sorted(report.not_cascaded_kind_filtered):
        kind_token = ArtifactKind(kind_value).operator_token
        for filtered_id in report.not_cascaded_kind_filtered[kind_value]:
            config_id = drg_urn_to_config_id(
                f"{kind_value}:{filtered_id}", doctrine_root, layer_roots, org_roots
            )
            render_kind_filtered_line(kind_token, config_id)


def recompile_catalog(repo_root: Path) -> list[str]:
    """Recompile the derived charter catalog via the single compiler authority (T012/T013).

    Issue #4785 Finding 1: `activate`/`deactivate` used to be config-only
    writes, leaving `catalog.references` stale (the #2524 dangler class)
    until an operator remembered to run a separate recompile by hand. This
    is the coherent-by-construction fix, called by default from both
    `activate_cmd` and `deactivate_cmd` (FR-001/FR-002) unless `--no-compile`
    is passed.

    Modeled EXACTLY on `pack.py`'s `_compile_bundle_after_merge` (the
    `charter pack apply --compile` seam) -- the same
    `_load_interview_for_generate(..., from_interview=False, ...)` ->
    `compile_charter` -> `write_compiled_charter` call chain `charter
    generate --no-from-interview` itself uses (single compiler authority,
    C-001/C-004: no second, minimal catalog writer). `profile="minimal"`
    matches the established default-profile convention this same module
    already uses for a recompile with no interview answers (see
    `run_full_synthesize` below and `_resynthesis_preflight.py`).

    Unlike `pack.py`'s bridge, this does NOT gate on
    `_is_inside_git_worktree` -- that check exists there because `charter
    generate`'s own git-auto-track contract requires a git working tree
    (the produced `charter.md` must be trackable). `activate`/`deactivate`
    have no such auto-track step, and forcing git here would break every
    existing config-only-style test fixture (bare `tmp_path`, no `.git`).
    Worktree SAFETY (never landing in the wrong checkout) is a separate
    concern, already handled by `resolve_charter_write_root` before this is
    ever called (Contract C3, FR-006).

    Imports are function-local for the same reason `pack.py` documents:
    avoids a module-load-time circular import between this package's
    `_app.py` and `generate.py`.
    """
    from charter.activation.compiler import compile_charter, write_compiled_charter  # noqa: PLC0415
    from charter.activation.pack_context import PackContext  # noqa: PLC0415
    from charter.bundle import CHARTER_YAML  # noqa: PLC0415

    from specify_cli.cli.commands.charter._common import _interview_path  # noqa: PLC0415
    from specify_cli.cli.commands.charter.generate import (  # noqa: PLC0415
        _build_doctrine_service_with_org_layer,
        _load_interview_for_generate,
    )

    # #4785 Regression-2 fix: only REFRESH an ALREADY-established compiled
    # catalog. On a config.yaml-only project (no compiled ``charter.yaml``
    # yet) there is no ``catalog.references`` to keep fresh, and bootstrapping
    # one here would mint the ``config.yaml`` ``charter:`` pointer as an
    # incidental side effect -- silently migrating the activation write-target
    # off ``config.yaml`` onto ``charter.yaml`` mid-activate. A later
    # ``deactivate`` then updates ``charter.yaml`` while ``config.yaml`` keeps
    # a stale activation shadow (the C-001 single-authority split-brain that
    # left ``activated_glossary_packs`` un-removed and the deactivate test
    # red). The coherence guard itself no-ops on an absent ``charter.yaml``
    # ("not yet synthesized" -- see ``tests/doctrine/
    # test_activation_parity_guard.py`` and ``test_activate_recompile_4785``'s
    # ``_write_established_catalog`` precondition), so skipping here keeps the
    # F1 coherence gain intact for established stores while never migrating a
    # config-only project as an incidental side effect of activate/deactivate.
    charter_dir = repo_root / ".kittify" / "charter"
    # Route the existence check through the canonical repo-root-relative
    # ``charter.bundle.CHARTER_YAML`` rather than a hardcoded "charter.yaml"
    # literal (charter-path-literal authority gate / DRAIN PROCEDURE).
    if not (repo_root / CHARTER_YAML).exists():
        return []

    interview_data, _source, resolved_mission = _load_interview_for_generate(
        repo_root=repo_root,
        answers_path=_interview_path(repo_root),
        from_interview=False,
        resolved_mission_type=None,
        profile="minimal",
        prefer_recorded_mission=True,
    )
    compiled = compile_charter(
        mission=resolved_mission,
        interview=interview_data,
        repo_root=repo_root,
        doctrine_service=_build_doctrine_service_with_org_layer(repo_root),
        pack_context=PackContext.from_config(repo_root),
    )
    bundle_result = write_compiled_charter(charter_dir, compiled, repo_root=repo_root)
    return list(bundle_result.files_written)


def run_full_synthesize(repo_root: Path) -> None:
    """Eagerly refresh the derived bundle/DRG via the EXISTING full-synthesize pipeline (FR-007).

    FR-013 naming footgun fix: this function calls the FULL ``charter
    synthesize`` pipeline (the same one ``spec-kitty charter synthesize``
    runs), not the bounded ``resynthesize_pipeline`` module -- its previous
    name (``run_resynthesize_pipeline``) misleadingly suggested the latter.

    ``--resynthesize`` opts into the SAME production entry points
    ``spec-kitty charter generate`` uses (recompiles ``references.yaml`` from
    the current activation state) and ``spec-kitty charter synthesize`` uses
    (re-stamps ``bundle_content_hash`` against the freshly-recompiled bundle
    and regenerates the project DRG layer) -- single authority: no parallel
    reconciliation logic is built here (C-007-style reuse). Shared by
    ``activate_cmd`` and ``deactivate_cmd`` (FR-007 is symmetric).

    Both commands resolve their own project root via ``find_repo_root()``
    (cwd-based -- neither accepts a ``repo_root`` parameter), so this scopes
    the calls with a temporary cwd switch rather than threading a new
    parameter through either command -- keeps the two owned files
    (``activate.py``/``deactivate.py``) as the only touched surface (C-001).

    Both are ``@charter_app.command()`` callables: Typer resolves unset
    parameters to ``OptionInfo``/``ArgumentInfo`` sentinel objects when the
    function is called directly (bypassing Click's context machinery), not
    to the declared default value -- so every parameter is passed explicitly
    here with its production default; never rely on the bare function
    signature default when calling a Typer command body in-process.
    ``prune=False`` is REQUIRED here (WP05, #3270 sentinel-prune regression):
    WP03 added ``--prune`` to ``charter_synthesize``; an in-process caller
    that omits it would receive the truthy ``OptionInfo`` sentinel instead
    of the declared ``False`` default and silently prune the overlay on
    every activation/deactivation. ``synthesize.py``'s ``_coerce_cli_bool``
    is a belt-and-braces guard for this same footgun -- this explicit
    keyword is the authoritative fix.

    Imports are deliberately local: this whole call graph (evidence
    collection, doctrine service construction, git staging) is expensive and
    must stay off the default (no-flag) activation hot path (NFR-001).

    Split-brain fix (issue #4785 Finding 3, WP03): ``_generate``/``_synthesize``
    resolve their own root via ``find_repo_root()`` (cwd-based), which
    follows a linked worktree's ``.git`` pointer back to the PRIMARY
    checkout. Before WP03, the caller's un-resolved ``repo_root``
    (``Path(".")`` from a worktree) landed the activation-flag write in the
    worktree while this ``chdir`` + ``find_repo_root()`` combination landed
    the recompile in PRIMARY -- two different checkouts for one logical
    activation. Both callers now resolve *repo_root* through
    :func:`specify_cli.cli.commands.charter._charter_write_root.resolve_charter_write_root`
    BEFORE calling anything in this module (which fails closed on a linked
    worktree rather than silently redirecting to PRIMARY), so by the time
    this function's ``chdir(repo_root)`` runs, *repo_root* is already the
    one safe checkout -- ``find_repo_root()`` inside that ``chdir`` resolves
    right back to the same directory, never a different one.
    """
    from specify_cli.cli.commands.charter.generate import generate as _generate
    from specify_cli.cli.commands.charter.synthesize import (
        charter_synthesize as _synthesize,
    )

    with contextlib.chdir(repo_root):
        _generate(
            mission_type=None,
            mission=None,
            template_set=None,
            from_interview=True,
            profile="minimal",
            force=True,
            json_output=False,
        )
        _synthesize(
            adapter="generated",
            dry_run=False,
            prune=False,
            json_output=False,
            skip_code_evidence=False,
            skip_corpus=False,
            dry_run_evidence=False,
        )


def resolve_write_root_or_exit(repo_root: Path) -> Path:
    """Resolve the WP02-safe charter-write root, or exit(1) (FR-006, Contract C3).

    Shared by ``activate_cmd``/``deactivate_cmd`` (T014 campsite): both
    otherwise carry an identical try/except around
    :func:`resolve_charter_write_root` -- extracting it keeps each command
    body under the complexity ceiling (Sonar S3776 / ruff C901).
    """
    try:
        return resolve_charter_write_root(repo_root)
    except CharterWriteRootError as exc:
        # Catch the BASE class (not just LinkedWorktreeCharterWriteError): the
        # only subclass raised today is the linked-worktree case, so this is
        # behaviourally identical, and any future write-root failure mode fails
        # closed here the same way rather than escaping as an uncaught traceback.
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


def _recompile_catalog_best_effort(repo_root: Path) -> None:
    """Run :func:`recompile_catalog`, degrading to a warning on two narrow,
    environmental preconditions instead of crashing the command.

    (1) ``recompile_catalog``'s bootstrap branch (``charter.yaml`` absent)
    resolves the canonical repo root via git
    (:func:`charter.resolution.resolve_canonical_repo_root`, reached through
    ``compiler._bootstrap_charter_yaml`` ->
    ``sync.load_governance_config``/``load_directives_config``) -- a
    precondition ``activate``/``deactivate`` themselves have never required:
    plenty of established, config-only projects (and a large share of this
    repo's own existing test fixtures) have no ``.git`` at all.

    (2) ``compile_charter`` resolves EVERY currently-activated stem across
    the WHOLE catalog (not just the one this command just
    activated/deactivated -- that one is already validated by
    ``manager.activate``/``manager.deactivate`` before recompile ever runs)
    via its own :func:`~charter.activation.kind_vocabulary.resolve_artifact_urn`
    call, and raises :class:`~charter.activation.kind_vocabulary.UnknownArtifactIdError`
    the moment ANY of them cannot be resolved -- a pre-existing dangler
    (the #2524 class this whole mission targets) or a doctrine-layout
    mismatch unrelated to the artifact this command touched. Catching it
    here does not mask THIS activation being wrong (it already passed
    ``manager.activate``'s own validation); it stops an unrelated,
    pre-existing resolution gap elsewhere in the activation set from
    crashing an otherwise-successful, unrelated activate/deactivate call.

    Both are environmental/pre-existing-state preconditions, not a failure
    of the recompile itself on an otherwise-healthy, established store --
    letting either crash the whole command over an opportunistic recompile
    that a successful config write does not need would be a real
    regression, not coherence-by-construction. The mutation itself already
    succeeded by the time this runs; only the recompile is skipped, exactly
    like the explicit ``--no-compile`` notice above (an established store
    with git and no pre-existing danglers, the overwhelming common case, is
    unaffected by either branch).
    """
    from charter.activation.kind_vocabulary import UnknownArtifactIdError  # noqa: PLC0415
    from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError  # noqa: PLC0415

    try:
        recompile_catalog(repo_root)
    except (NotInsideRepositoryError, GitCommonDirUnavailableError, UnknownArtifactIdError) as exc:
        console.print(
            f"[yellow]Catalog not recompiled[/yellow]: {exc} catalog.references "
            "may go stale until the next `charter generate` (from a git "
            "repository, with a clean activation set) or `charter activate "
            "--resynthesize`."
        )


def recompile_or_notify(repo_root: Path, *, resynthesize: bool, compile_catalog: bool) -> None:
    """Run the post-mutation catalog refresh: full pipeline, lightweight
    recompile, or an explicit skip notice (FR-001/FR-002/FR-003/FR-007).

    Shared tail for ``activate_cmd``/``deactivate_cmd`` (T012/T013
    campsite): extracting the three-way branch keeps each command body
    under the complexity ceiling. Precedence is ``--resynthesize`` (the
    heavier, opt-in full pipeline, which already recompiles the catalog as
    part of its own work) over the default lightweight ``--compile`` over
    the explicit ``--no-compile`` skip notice.
    """
    if resynthesize:
        run_full_synthesize(repo_root)
    elif compile_catalog:
        _recompile_catalog_best_effort(repo_root)
    else:
        console.print(
            "[yellow]Catalog not recompiled[/yellow] (--no-compile): "
            "catalog.references may go stale until the next `charter "
            "generate` or `charter activate --resynthesize`."
        )


def activate_cmd(
    ctx: typer.Context,
    kind: str | None = typer.Argument(None, help="Activation kind (e.g. directive, agent-profile)."),
    artifact_id: str | None = typer.Argument(None, help="Artifact ID to activate."),
    cascade: str | None = typer.Option(
        None,
        "--cascade",
        help=(
            "Cascade activation scope: 'all' for every referenced kind, or a "
            "comma-separated kind list (e.g. 'agent-profile,tactic'). "
            "Omit to skip cascade (referenced artifacts are reported as a warning)."
        ),
    ),
    resynthesize: bool = typer.Option(
        False,
        "--resynthesize/--no-resynthesize",
        help=RESYNTHESIZE_HELP,
    ),
    compile_catalog: bool = typer.Option(
        True,
        "--compile/--no-compile",
        help=NO_COMPILE_HELP,
    ),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Activate a doctrine artifact by kind and ID (FR-004), with optional cascade."""
    if ctx.invoked_subcommand is not None:
        return
    if kind is None or artifact_id is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)
    if kind not in YAML_KEY_MAP:
        console.print(f"[red]Error:[/red] Unknown kind '{kind}'. Valid kinds: {', '.join(sorted(YAML_KEY_MAP))}.")
        raise typer.Exit(1)

    # FR-006/Contract C3: fail closed from a linked git worktree before any
    # mutation, and resolve the ONE checkout root every downstream call in
    # this command (ctx_project, cascade rendering, the catalog recompile,
    # and run_full_synthesize's chdir) shares from here on -- closing the
    # split-brain where the activation flag landed in one checkout and the
    # recompile landed in another (issue #4785 Finding 3).
    repo_root = resolve_write_root_or_exit(repo_root)

    # FR-013/014: parse the scope value object — never collapsed to a bool
    # (Contract C3.3). A bad kind token raises a structured ValueError.
    try:
        scope = CascadeScope.parse(cascade)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    # FR-035 fail-closed: reject invalid pack config before any mutation (C1.5).
    try:
        validate_pack_config(repo_root)
    except CharterPackConfigError as exc:
        render_pack_config_error(exc, console)
        raise typer.Exit(1) from exc

    ctx_project = ProjectContext(repo_root=repo_root)
    layer_roots = resolve_layer_roots(repo_root)

    # FR-008: in-flight step-removal warnings (generalized — no inline
    # `kind == "mission-type"` branch in the command flow).
    #
    # CL-006/NFR-002 (post-fix verification sweep, mission
    # up-mission-type-seam-01KZY1JB): this reaches the layered mission-type
    # roster (``resolve_layered_roster`` -> ``resolve_layered_mission_types``
    # -> ``scan_mission_types_dir``), which loud-fails BY DESIGN (WP03,
    # PR-CONTRACT-002) on a malformed/unreadable YAML file anywhere in the
    # built-in, org, or project ``mission_types/`` layer. Pre-fix this call
    # had no exception boundary at all, so that loud-fail surfaced as a raw,
    # uncaught traceback instead of the clean, operator-readable
    # ``typer.Exit(1)`` every other failure mode in this command already
    # gets. Same catch shape as ``manager.activate()`` below: a bare
    # ``except ValueError`` also catches ``pydantic.ValidationError`` (the
    # schema-validation failure mode the same resolver chain documents as a
    # separate ``Raises`` entry) because ``pydantic.ValidationError``
    # subclasses ``ValueError`` in the pinned pydantic version — no second
    # import, no second error-handling style.
    try:
        _emit_step_removal_warnings(kind, artifact_id, repo_root)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    try:
        _validate_mission_type_activatable(kind, artifact_id, repo_root)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    manager = CharterPackManager()
    try:
        registration = plan_project_registration(repo_root)
        if resynthesize:
            from specify_cli.cli.commands.charter._resynthesis_preflight import preflight_resynthesis

            preflight_resynthesis(repo_root, kind, artifact_id, scope, registration.graph)
        result = manager.activate(
            ctx_project,
            kind,
            artifact_id,
            cascade=scope is not None,
            layer_roots=layer_roots,
        )
    except (ValueError, DRGLoadError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    commit_project_registration(registration)
    for msg in result.activated:
        console.print(f"[green]Activated[/green]: {msg}")
    for warn in (*registration.warnings, *result.warnings):
        console.print(f"[yellow]Warning[/yellow]: {warn}")

    # FR-010: co-activated, unreconciled in_tension_with pairs (contracts/
    # tension-finding.md). Rendered right after the activation-result
    # warnings above, before cascade, so it reflects the direct target's
    # activation regardless of cascade outcome.
    _render_tension_warnings(repo_root)

    # FR-013/014: cascade is driven from the CLI via the WP11 engine over the
    # merged DRG (pack_manager's own cascade is deferred — the live wiring is
    # here). Resolve the source URN; mission-type / non-DRG kinds short-circuit.
    source_urn = _source_urn(kind, artifact_id, layer_roots, resolve_org_root_chain(repo_root))
    if source_urn is not None:
        if scope is None:
            _render_no_cascade_warning(source_urn, repo_root, layer_roots)
        else:
            _render_cascade_activation(
                manager, ctx_project, source_urn, scope, repo_root, layer_roots
            )

    # FR-001/FR-003/FR-007: default catalog recompile keeps activation
    # coherent-by-construction (issue #4785 Finding 1) -- runs AFTER cascade
    # so it reconciles the complete post-activation config state, not just
    # the direct target. See `recompile_or_notify` for the
    # resynthesize/compile/no-compile precedence.
    recompile_or_notify(repo_root, resynthesize=resynthesize, compile_catalog=compile_catalog)
