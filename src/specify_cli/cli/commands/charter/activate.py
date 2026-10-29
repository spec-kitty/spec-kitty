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
  are activated through the same :class:`~charter.activation.pack_manager.ActiveCharterManager`
  seam as the direct activation, and rendered per kind (FR-014).
* :class:`charter.activation.pack_context.ActiveCharterConfigError` is caught and surfaced as
  a clean exit-1 with its diagnostic code + remediation, before any mutation
  (FR-035 fail-closed, C1.5).
"""

from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from specify_cli.charter_activate import emit_step_removal_warnings
from specify_cli.core.constants import KITTY_SPECS_DIR
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import typer
from rich.console import Console
from rich.markup import escape
from specify_cli.cli.console import console, sanitize_terminal_text
from specify_cli.cli.helpers import parameter_source_name

from charter.activation.api import DenyListChoice, deny_delta
from charter.activation.cascade import (
    CascadeActivationResult,
    CascadeScope,
    ReferencedArtifact,
    cascade_activation_targets,
    referenced_but_not_cascaded,
)
from charter.drg import DRGLoadError, NodeKind
from charter.activation.catalog import resolve_offering_root
from charter.activation.drg_activation import load_org_drg
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import (
    ArtifactKind,
    MissionTypeNotAnArtifactKind,
    ResolutionPass,
    UnknownArtifactIdError,
    resolve_artifact_urn,
)
from charter.activation.pack_context import ActiveCharterConfigError, PackContext, load_denied
from charter.activation.api import ActivationResult
from charter.activation.pack_manager import YAML_KEY_MAP, ActiveCharterManager
from charter.activation.preset_application import (
    PresetApplicationError,
    PresetOutcome,
    PresetPlan,
    apply_preset_plan,
    plan_preset_application,
)
from charter.packs import PresetFormatError
from charter.activation.project_registration import (
    ProjectRegistrationPlan,
    commit_project_registration,
    plan_project_registration,
)

from specify_cli.cli.commands.charter._activation_report import (
    ActivationChangeReport,
    ArtifactRef,
    CascadeEntry,
    CascadeOutcome,
    CascadeReport,
    NoCascadeReport,
)
from specify_cli.cli.commands.charter._cascade_shared import (
    drg_urn_to_config_id,
    render_kind_filtered_line,
)
from specify_cli.cli.commands.charter._coded_errors import render_coded_error, render_preset_format_error
from specify_cli.cli.json_contract import json_output_guard
from specify_cli.cli.commands.charter._charter_write_root import (
    CharterWriteRootError,
    resolve_charter_write_root,
)
from charter.activation.layer_roots import (
    resolve_layer_roots,
    resolve_pack_chain,
)

if TYPE_CHECKING:
    from specify_cli.charter_activate import StepRemovalWarning

__all__ = ["activate_cmd", "run_full_synthesize"]

#: Local refusal codes of positional ``charter activate`` / ``charter deactivate``
#: (contracts/cli-json.md). UPPER_SNAKE and local to core: never the
#: spec-kitty-charter contract codes. ``ACTIVE_CHARTER_CONFIG_INVALID`` is the
#: exception's own ``.code``.
ACTIVATION_KIND_UNKNOWN = "ACTIVATION_KIND_UNKNOWN"
CASCADE_SCOPE_INVALID = "CASCADE_SCOPE_INVALID"
CHARTER_WRITE_ROOT_INVALID = "CHARTER_WRITE_ROOT_INVALID"
DEACTIVATION_REFUSED_REQUIRED = "DEACTIVATION_REFUSED_REQUIRED"
ACTIVATION_FAILED = "ACTIVATION_FAILED"


class CodedRefusal(Exception):
    """A refusal of positional activate/deactivate, carried out of the command's work to be rendered once.

    Raised before (or instead of) any write; :func:`render_refusal` prints it as
    ``Error (<CODE>): <message>`` or the canonical ``--json`` error envelope.
    """

    def __init__(self, code: str, message: str, payload: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.payload = payload


def render_refusal(refusal: CodedRefusal, *, json_output: bool) -> NoReturn:
    """Render *refusal* through the shared coded-error seam and exit 1."""
    render_coded_error(refusal.code, refusal.message, payload=refusal.payload, json_output=json_output)
    raise typer.Exit(1) from refusal


def config_refusal(exc: ActiveCharterConfigError) -> CodedRefusal:
    """An :class:`ActiveCharterConfigError` as a refusal under its own code (FR-035)."""
    return CodedRefusal(exc.code, exc.body)


def check_activation_kind(kind: str) -> None:
    """Refuse a KIND that is not an activation kind (before any I/O)."""
    if kind not in YAML_KEY_MAP:
        raise CodedRefusal(ACTIVATION_KIND_UNKNOWN, f"Unknown kind '{kind}'. Valid kinds: {', '.join(sorted(YAML_KEY_MAP))}.")


def parse_cascade_scope(cascade: str | None) -> CascadeScope | None:
    """Parse ``--cascade`` into its scope value object (never a bool, Contract C3.3), or refuse."""
    try:
        return CascadeScope.parse(cascade)
    except ValueError as exc:
        raise CodedRefusal(CASCADE_SCOPE_INVALID, str(exc)) from exc

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

INCLUDE_DEACTIVATED_HELP = (
    "Walk through deactivated artifacts during the cascade: activate them and "
    "clear their exclusions. Without it the cascade stops at a deactivated "
    "artifact and reports it. Only with --cascade."
)

PRESET_FORCE_HELP = (
    "Apply the preset even when it changes a customised activation key, and "
    "clear the exclusion of every deactivated id the preset lists. Only with --preset."
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
#: `_zero_activatable_targets` below).
CASCADE_ZERO_ACTIVATABLE_TARGETS_MESSAGE = (
    "[yellow]Cascade resolved zero activatable targets[/yellow] "
    "(every referenced node was kind-filtered; see the lines above)."
)



def render_pack_config_error(exc: ActiveCharterConfigError, console: Console) -> None:
    """Render a :class:`ActiveCharterConfigError` as fail-closed CLI guidance (FR-035).

    Surfaces the stable ``ACTIVE_CHARTER_CONFIG_INVALID`` diagnostic code plus the
    error body (which already carries the remediation hint). Shared by the
    activate and deactivate commands so both fail closed identically.
    """
    console.print(f"[red]Error[/red] ({exc.code}): {exc.body}")


def validate_pack_config(repo_root: Path) -> PackContext:
    """Load the project pack context to fail closed on invalid config (FR-035).

    :meth:`PackContext.from_config` raises :class:`ActiveCharterConfigError` when
    ``.kittify/config.yaml`` has an invalid charter-pack shape. Calling it here
    — *before* any mutation — gives that previously dead-ended error type a live
    external caller and guarantees no write happens on a malformed config (C1.5).
    Returns the context, so a caller reuses it (its deny set) instead of re-reading.
    """
    return PackContext.from_config(repo_root)


def _source_urn(
    kind: str,
    artifact_id: str,
    layer_roots: dict[str, Path] | None,
    org_roots: list[Path] | None = None,
) -> str | None:
    """Resolve the DRG source URN for ``(kind, config-stem artifact_id)``.

    A mission type resolves to its ``mission_type:<id>`` node (FR-022). Returns
    ``None`` when the artifact has no resolvable DRG node — cascade is a no-op
    then rather than an error (a mission type with no node simply reaches nothing).

    ``org_roots`` (T008/T009, mission ``cascade-org-inert-01M07E9P``): the
    full declaration-ordered org-pack chain, additive to ``layer_roots``'s
    single-pack-only ``roots["org"]`` — so a direct-activation target that
    lives only in org pack 2..N still resolves, not just pack 1's.
    """
    try:
        kind_enum = ArtifactKind.from_operator_token(kind)
    except MissionTypeNotAnArtifactKind:
        return mission_type_urn(artifact_id)
    try:
        resolved: str = resolve_artifact_urn(
            kind_enum,
            artifact_id,
            offering_root=resolve_offering_root(),
            org_roots=org_roots,
            layer_roots=layer_roots,
        )
        return resolved
    except UnknownArtifactIdError:
        return None


def _step_removal_warnings(kind: str, artifact_id: str, repo_root: Path) -> list[StepRemovalWarning]:
    """Collect the in-flight step-removal warnings of the activation (FR-008).

    Generalized out of the command body: the command no longer branches on
    ``kind == "mission-type"`` inline — it always calls this collector, which
    returns nothing for kinds that have no step-sequence semantics.
    :func:`_render_step_removal_warnings` prints them; :func:`step_removal_text`
    is their one-line report form.
    """
    if kind != "mission-type":
        return []

    from specify_cli.charter_activate import (  # noqa: PLC0415
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
    if not removed:
        return []
    found: list[StepRemovalWarning] = scan_inflight_missions(removed, repo_root / KITTY_SPECS_DIR)
    return found


def _render_step_removal_warnings(warnings: list[StepRemovalWarning]) -> None:
    """Print the step-removal warnings in their FR-008 text form."""
    emit_step_removal_warnings(warnings, console)


def step_removal_text(warning: StepRemovalWarning) -> str | None:
    """One report line per removed step naming its affected missions; ``None`` when none is affected (as the text form)."""
    if not warning.affected_missions:
        return None
    missions = ", ".join(f"{mission.mission_slug} ({mission.wp_id}, currently in lane '{mission.current_lane}')" for mission in warning.affected_missions)
    return f"Step '{warning.removed_step_id}' removed by mission-type override. Affected missions: {missions}"


def _validate_mission_type_activatable(kind: str, artifact_id: str, repo_root: Path) -> None:
    """FR-001 preflight: refuse activation of an empty-action-sequence mission type."""
    if kind != "mission-type":
        return
    from charter.activation.mission_type_profiles import validate_activatable_mission_type  # noqa: PLC0415

    validate_activatable_mission_type(artifact_id, repo_root=repo_root)


#: Line prefixes of the cascade report (data-model.md §7), shared by the cascade and no-cascade renders.
SKIPPED_OUT_OF_SCOPE = "Skipped (out of scope)"
SKIPPED_DEACTIVATED = "Skipped, deactivated"
UNREACHED_BEHIND_DEACTIVATED = "Unreached (behind a deactivated artifact)"
INCLUDE_DEACTIVATED_HINT = "Run with --include-deactivated to activate these and clear their exclusions."
_REQUIREMENT_NOTE = "the parent no longer has this requirement"
_OUT_OF_SCOPE_DEACTIVATED_NOTE = "(deactivated; nothing behind it was walked)"


@dataclass(frozen=True)
class _CascadeIds:
    """What the cascade renders need to map DRG ids back to config-stem ids."""

    offering_root: Path
    layer_roots: dict[str, Path] | None
    org_roots: list[Path]
    render_pass: ResolutionPass | None = None

    def config_id(self, urn: str) -> str:
        config_id: str = drg_urn_to_config_id(urn, self.offering_root, self.layer_roots, self.org_roots, self.render_pass)
        return config_id


def _deactivated_urns(repo_root: Path, org_roots: list[Path]) -> frozenset[str]:
    """Every denied DRG URN, read now (after the cascade activations, for the reinstated report).

    Goes through :func:`~charter.activation.pack_context.load_denied`, which
    returns at once when no deny list exists (NFR-003), not a whole ``PackContext``.
    """
    return frozenset().union(*(deny.urns for _plural, deny in load_denied(repo_root, org_roots=org_roots)))


def mission_type_urn(artifact_id: str) -> str:
    """The DRG node of a mission type (FR-022): its ``requires``/``scope``/``instantiates`` edges are the cascade."""
    return f"{NodeKind.MISSION_TYPE.value}:{artifact_id}"


def _activate_cascade_targets(
    manager: ActiveCharterManager,
    ctx_project: ProjectContext,
    activated: dict[str, list[str]],
    ids: _CascadeIds,
    *,
    reinstate: bool,
) -> list[CascadeEntry]:
    """Activate every in-scope target; return one ``cascaded`` or ``failed`` entry per target, in walk order.

    With *reinstate* (``--include-deactivated``) each activation carries
    :attr:`DenyListChoice.CASCADE_INCLUDE_DEACTIVATED`, so a denied target's
    exclusion is cleared; the caller reports what the deny delta shows.
    """
    entries: list[CascadeEntry] = []
    for kind_value in sorted(activated):
        kind_token = ArtifactKind(kind_value).operator_token
        for cascade_drg_id in activated[kind_value]:
            urn = f"{kind_value}:{cascade_drg_id}"
            # The cascade engine reports DRG bare IDs; activation lists use
            # config-stem IDs. Resolve back through the kind-vocabulary bridge.
            ref = ArtifactRef(kind_token, ids.config_id(urn), urn)
            try:
                manager.activate(
                    ctx_project,
                    kind_token,
                    ref.id,
                    layer_roots=ids.layer_roots,
                    org_root_chain=ids.org_roots,
                    reinstate=DenyListChoice.CASCADE_INCLUDE_DEACTIVATED if reinstate else DenyListChoice.ACTIVATE,
                )
            except ValueError as exc:
                entries.append(CascadeEntry(CascadeOutcome.FAILED, ref, message=str(exc)))
                continue
            entries.append(CascadeEntry(CascadeOutcome.CASCADED, ref))
    return entries


def _reinstated_entries(before: frozenset[str], after: frozenset[str], walked: list[CascadeEntry]) -> list[CascadeEntry]:
    """One ``reinstated`` entry per cascade target whose exclusion the walk cleared (from :func:`deny_delta`, R11)."""
    activated = {entry.ref.urn: entry.ref for entry in walked if entry.outcome is CascadeOutcome.CASCADED}
    _added, cleared = deny_delta(before, after)
    return [CascadeEntry(CascadeOutcome.REINSTATED, activated[urn]) for urn in cleared if urn in activated]


def _bucket_entries(bucket: dict[str, list[str]], ids: _CascadeIds, outcome: CascadeOutcome, deactivated: frozenset[str] = frozenset()) -> list[CascadeEntry]:
    """One *outcome* entry for every entry of a kind → bare-id bucket, sorted; *deactivated* URNs are flagged."""
    entries: list[CascadeEntry] = []
    for kind_value in sorted(bucket):
        kind_token = ArtifactKind(kind_value).operator_token
        for drg_id in bucket[kind_value]:
            urn = f"{kind_value}:{drg_id}"
            entries.append(CascadeEntry(outcome, ArtifactRef(kind_token, ids.config_id(urn), urn), deactivated=urn in deactivated))
    return entries


def _required_by(ref: ReferencedArtifact) -> tuple[str, ...]:
    """The requiring parents of a deactivated child; ``()`` when it was reached only through ``suggests``."""
    return ref.required_by if ref.via_requires else ()


def _required_by_note(required_by: tuple[str, ...]) -> str:
    """`` (required by <parents> — the parent no longer has this requirement)`` for a required child, else ``""``."""
    if not required_by:
        return ""
    return f" (required by {', '.join(required_by)} — {_REQUIREMENT_NOTE})"


def _deactivated_skip_entries(result: CascadeActivationResult, ids: _CascadeIds) -> list[CascadeEntry]:
    """The "Skipped, deactivated" and "Unreached" entries (FR-010/FR-011)."""
    entries: list[CascadeEntry] = []
    for kind_value in sorted(result.skipped_deactivated):
        kind_token = ArtifactKind(kind_value).operator_token
        for ref in result.skipped_deactivated[kind_value]:
            skipped = ArtifactRef(kind_token, ids.config_id(ref.urn), ref.urn)
            entries.append(CascadeEntry(CascadeOutcome.SKIPPED_DEACTIVATED, skipped, required_by=_required_by(ref)))
    entries += _bucket_entries(result.unreached_behind_deactivated, ids, CascadeOutcome.UNREACHED_BEHIND_DEACTIVATED)
    return entries


def _zero_activatable_targets(result: CascadeActivationResult) -> bool:
    """FR-004: nothing activatable was resolved and every referenced node was kind-filtered.

    Never for a source with zero referenced nodes at all, and never when any
    referenced node was scope-narrowed, deactivated or left unreached behind a
    deactivated node: the lines for those already tell the story (SC-007), and
    the "every referenced node was kind-filtered" summary would be false.
    Deliberately NOT the broader "zero landed in ``activated``" condition.
    """
    others = result.activated or result.skipped_by_scope or result.skipped_deactivated or result.unreached_behind_deactivated
    return not others and bool(result.not_cascaded_kind_filtered)


def scope_label(scope: CascadeScope) -> str | tuple[str, ...]:
    """The report spelling of a parsed ``--cascade`` value: ``"all"`` or the sorted kind tokens."""
    if scope.is_all:
        return str(CascadeScope.ALL_TOKEN)
    return tuple(sorted(kind.operator_token for kind in scope.kinds))


def _cascade_activation_report(
    manager: ActiveCharterManager,
    ctx_project: ProjectContext,
    source_urn: str,
    scope: CascadeScope,
    repo_root: Path,
    layer_roots: dict[str, Path] | None,
    *,
    include_deactivated: bool = False,
    deactivated: frozenset[str] = frozenset(),
) -> CascadeReport:
    """Activate scoped cascade targets and report the outcome (FR-014).

    Walks the merged DRG from ``source_urn`` via the WP11 cascade engine, keeps
    only the kinds the scope selects, and activates each in-scope target through
    the same activation seam. Skipped-by-scope kinds are reported so the operator
    sees exactly what the explicit scope excluded.

    *deactivated* is the denied DRG URNs (the pre-activation ``PackContext``'s;
    the engine never treats the source itself as denied, so the direct
    activation's own reinstatement cannot make it stale). Only with
    ``--include-deactivated`` is the deny set read again, after the walk, to
    report what the deny delta cleared.

    Deactivated artifacts (FR-010/FR-011): the walk stops at a denied node; it
    is reported as "Skipped, deactivated" (flagged when a reached parent
    requires it) and what is reachable only through it as "Unreached".
    ``include_deactivated`` walks through and clears those exclusions with
    :attr:`DenyListChoice.CASCADE_INCLUDE_DEACTIVATED`.

    T009 (mission ``cascade-org-inert-01M07E9P``): threads the full,
    declaration-ordered org-pack chain into both the DRG load (so
    ``requires``/``suggests`` edges into/out of ANY configured org pack are
    visible to the cascade walk, not just none) and the DRG-ID-to-config-ID
    mapping below (so an org-pack-2..N target resolves to its real config-stem
    ID, not the raw DRG ID as a lossy fallback).

    The entries are in render order (:func:`render_cascade_activation`).
    """
    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415

    org_roots = resolve_pack_chain(repo_root, strict=False)
    graph = load_validated_graph(
        repo_root,
        org_roots=org_roots,
        org_fragments=load_org_drg(repo_root, strict=False),
    )
    result = cascade_activation_targets(graph, source_urn, scope, deactivated_urns=deactivated, include_deactivated=include_deactivated)
    ids = _CascadeIds(resolve_offering_root(), layer_roots, org_roots)
    entries = _activate_cascade_targets(manager, ctx_project, result.activated, ids, reinstate=include_deactivated)
    if include_deactivated and deactivated:
        entries += _reinstated_entries(deactivated, _deactivated_urns(repo_root, org_roots), entries)

    # The activations above are done; everything below only reads, so one
    # resolution pass parses each artifact file once for all remaining entries.
    ids = dataclasses.replace(ids, render_pass=ResolutionPass())
    entries += _bucket_entries(result.skipped_by_scope, ids, CascadeOutcome.SKIPPED_OUT_OF_SCOPE, frozenset() if include_deactivated else deactivated)
    entries += _deactivated_skip_entries(result, ids)
    # FR-003/FR-008 (issue #3705): the kind-filtered nodes the shared
    # `_referenced_artifacts` seam collected, by config-stem id (an
    # org-pack-2..N node's bare id and config-stem id can differ).
    entries += _bucket_entries(result.not_cascaded_kind_filtered, ids, CascadeOutcome.SKIPPED_KIND_FILTERED)
    return CascadeReport(source_urn, scope_label(scope), tuple(entries), zero_activatable=_zero_activatable_targets(result))


def _cascade_activation_line(entry: CascadeEntry) -> str:
    """The text line of one cascade-activation entry (a kind-filtered one renders through the shared helper)."""
    label = entry.ref.label
    if entry.outcome is CascadeOutcome.CASCADED:
        return f"[cyan]Cascade-activated[/cyan]: {label}"
    if entry.outcome is CascadeOutcome.FAILED:
        return f"[yellow]Warning[/yellow]: could not cascade-activate {label}: {entry.message}"
    if entry.outcome is CascadeOutcome.REINSTATED:
        return f"[green]Reinstated[/green]: {label} (exclusion cleared)"
    if entry.outcome is CascadeOutcome.SKIPPED_OUT_OF_SCOPE:
        note = f" {_OUT_OF_SCOPE_DEACTIVATED_NOTE}" if entry.deactivated else ""
        return f"[dim]{SKIPPED_OUT_OF_SCOPE}[/dim]: {label}{note}"
    if entry.outcome is CascadeOutcome.SKIPPED_DEACTIVATED:
        return f"[yellow]{SKIPPED_DEACTIVATED}[/yellow]: {label}{escape(_required_by_note(entry.required_by))}"
    return f"[yellow]{UNREACHED_BEHIND_DEACTIVATED}[/yellow]: {label}"


_DEACTIVATED_OUTCOMES = frozenset({CascadeOutcome.SKIPPED_DEACTIVATED, CascadeOutcome.UNREACHED_BEHIND_DEACTIVATED})


def render_cascade_activation(report: CascadeReport) -> None:
    """Print a cascade activation report: one line per entry, in order.

    The ``--include-deactivated`` hint follows the last deactivated/unreached
    line; the zero-activatable-targets summary closes the report (FR-004).
    """
    last_deactivated = max((index for index, entry in enumerate(report.entries) if entry.outcome in _DEACTIVATED_OUTCOMES), default=-1)
    for index, entry in enumerate(report.entries):
        if entry.outcome is CascadeOutcome.SKIPPED_KIND_FILTERED:
            render_kind_filtered_line(entry.ref.kind, entry.ref.id)
        else:
            console.print(_cascade_activation_line(entry))
        if index == last_deactivated:
            console.print(f"[yellow]Hint[/yellow]: {INCLUDE_DEACTIVATED_HINT}")
    if report.zero_activatable:
        console.print(CASCADE_ZERO_ACTIVATABLE_TARGETS_MESSAGE)


def _tension_warnings(repo_root: Path) -> list[str]:
    """Unreconciled tension findings, as the activate-time warning texts (FR-010).

    Calls the SAME scan :func:`charter.activation.consistency_check.scan_unreconciled_tensions`
    that ``spec-kitty charter consistency-check`` uses (single canonical
    authority, contracts/tension-finding.md SC-001) so this warning and that
    JSON surface can never render a tension pair differently.

    Builds its own fully-populated :class:`ProjectContext` via
    :meth:`ProjectContext.from_repo` (matching ``consistency_check.py``'s
    command) rather than reusing the caller's ``ctx_project`` -- the
    ``activate_cmd``/``deactivate_cmd`` local is a bare
    ``ProjectContext(repo_root=repo_root)`` with ``pack_context=None``, which
    would make :func:`scan_unreconciled_tensions` raise
    ``ContextPreconditionError`` on every call (a silent, permanent no-op --
    exactly the NFR-001 trap this finding exists to avoid).

    Best-effort, matching the existing DRG-load handling in this module (see
    ``_no_cascade_report`` / ``_cascade_activation_report``, which already
    load the validated graph without a bespoke fail-closed path of their
    own): a DRG load failure here does not abort activation -- the
    fail-closed guarantee for this finding lives on the consistency-check
    surface (``ConsistencyReport.verification_errors``), which every project
    can run explicitly on demand.
    """
    from charter.activation.consistency_check import scan_unreconciled_tensions  # noqa: PLC0415

    try:
        scan_ctx = ProjectContext.from_repo(repo_root)
        findings = scan_unreconciled_tensions(scan_ctx)
    except Exception:  # noqa: BLE001 -- best-effort warning surface, not fail-closed here.
        return []

    warnings: list[str] = []
    for finding in findings:
        side_a, side_b = finding.pair
        warnings.append(
            f"{side_a} is in tension with {side_b}. Resolve by: (1) deactivating one side, or (2) activating a reconciler that bridges both."
        )
    return warnings


def _no_cascade_report(
    source_urn: str,
    repo_root: Path,
    layer_roots: dict[str, Path] | None,
    deactivated: frozenset[str] = frozenset(),
) -> NoCascadeReport:
    """Collect referenced-but-not-cascaded artifacts (FR-013, Contract C3.2).

    T009: threads the full org-pack chain into the DRG load and the ID
    mapping below, same rationale as ``_cascade_activation_report`` — an
    org-pack ``requires``/``suggests`` edge is invisible to this warning
    unless the DRG it walks actually contains org-pack nodes (FR-001 AC5).
    """
    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415

    org_roots = resolve_pack_chain(repo_root, strict=False)
    graph = load_validated_graph(
        repo_root,
        org_roots=org_roots,
        org_fragments=load_org_drg(repo_root, strict=False),
    )
    report = referenced_but_not_cascaded(graph, source_urn, deactivated_urns=deactivated)
    if not report.has_skipped:
        return NoCascadeReport()
    # A read-only collection: one resolution pass parses each artifact file
    # once for every referenced artifact, not once per artifact (#5526).
    ids = _CascadeIds(resolve_offering_root(), layer_roots, org_roots, ResolutionPass())

    def refs(bucket: dict[str, list[str]]) -> tuple[ArtifactRef, ...]:
        return tuple(entry.ref for entry in _bucket_entries(bucket, ids, CascadeOutcome.SKIPPED_KIND_FILTERED))

    skipped = refs(report.skipped)
    return NoCascadeReport(
        skipped=skipped,
        deactivated=refs(report.deactivated),
        kind_filtered=refs(report.not_cascaded_kind_filtered),
        # FR-005a: gated on `report.skipped` specifically (not the broader
        # `has_skipped`) -- `recovery_hint` literally says "to activate the
        # referenced artifacts", which is only true of `skipped` entries.
        hint=report.recovery_hint if report.skipped else None,
    )


def render_no_cascade_warning(report: NoCascadeReport) -> None:
    """Print the referenced-but-not-cascaded warning (FR-013/FR-005).

    The kind-filtered lines use the SAME shared helper as the cascade render
    (FR-009) and never suggest ``--cascade``: re-running with ``--cascade``
    would NOT activate an asset/template.
    """
    for ref in report.skipped:
        console.print(f"[yellow]Warning[/yellow]: referenced {ref.label} was not activated (no --cascade).")
    for ref in report.deactivated:
        console.print(f"[yellow]Warning[/yellow]: referenced {ref.label} is deactivated and was not activated.")
    if report.hint is not None:
        console.print(f"[yellow]Hint[/yellow]: {report.hint}")
    for ref in report.kind_filtered:
        render_kind_filtered_line(ref.kind, ref.id)


def recompile_catalog(repo_root: Path) -> list[str]:
    """Recompile the derived charter catalog via the single compiler authority (T012/T013).

    Issue #4785 Finding 1: `activate`/`deactivate` used to be config-only
    writes, leaving `catalog.references` stale (the #2524 dangler class)
    until an operator remembered to run a separate recompile by hand. This
    is the coherent-by-construction fix, called by default from both
    `activate_cmd` and `deactivate_cmd` (FR-001/FR-002) unless `--no-compile`
    is passed.

    Uses the same
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
        _build_active_charter_service_with_org_layer,
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
    # ("not yet synthesized" -- see ``tests/charter_offering/
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
        charter_service=_build_active_charter_service_with_org_layer(repo_root),
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


def resolve_write_root(repo_root: Path) -> Path:
    """Resolve the WP02-safe charter-write root, or raise a ``CHARTER_WRITE_ROOT_INVALID`` refusal (FR-006, Contract C3).

    Shared by ``activate_cmd``/``deactivate_cmd`` (T014 campsite): both
    otherwise carry an identical try/except around
    :func:`resolve_charter_write_root` -- extracting it keeps each command
    body under the complexity ceiling (Sonar S3776 / ruff C901).
    """
    try:
        # Resolve first: the kernel git-topology probes are ``lru_cache``d on the
        # path they receive, so the relative default ``Path(".")`` would return
        # the checkout of the first in-process call after a ``chdir``.
        return resolve_charter_write_root(repo_root.resolve())
    except CharterWriteRootError as exc:
        # Catch the BASE class (not just LinkedWorktreeCharterWriteError): the
        # only subclass raised today is the linked-worktree case, so this is
        # behaviourally identical, and any future write-root failure mode fails
        # closed here the same way rather than escaping as an uncaught traceback.
        raise CodedRefusal(CHARTER_WRITE_ROOT_INVALID, str(exc)) from exc


def resolve_write_root_or_exit(repo_root: Path, *, json_output: bool = False) -> Path:
    """:func:`resolve_write_root`, rendering its refusal (text or ``--json``) and exiting 1."""
    try:
        return resolve_write_root(repo_root)
    except CodedRefusal as refusal:
        render_refusal(refusal, json_output=json_output)


def _recompile_catalog_best_effort(repo_root: Path) -> None:
    """Run :func:`recompile_catalog`, degrading to a warning on three narrow,
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

    (3) ``compile_charter`` fails closed with
    :class:`~charter.activation.compiler.WholeKindUnresolvedError` when every
    activated reference of one tracked kind is unresolvable (a misconfigured
    pack root, a DRG edge to an artifact that does not exist). The exception
    text names the kind and ids; nothing is written, so the existing catalog is
    kept as-is rather than emptied, and the already-successful config write
    stands.

    All three are environmental/pre-existing-state preconditions, not a failure
    of the recompile itself on an otherwise-healthy, established store --
    letting any of them crash the whole command over an opportunistic recompile
    that a successful config write does not need would be a real
    regression, not coherence-by-construction. The mutation itself already
    succeeded by the time this runs; only the recompile is skipped, exactly
    like the explicit ``--no-compile`` notice above (an established store
    with git and no pre-existing danglers, the overwhelming common case, is
    unaffected by either branch).
    """
    from charter.activation.compiler import WholeKindUnresolvedError  # noqa: PLC0415
    from charter.activation.kind_vocabulary import UnknownArtifactIdError  # noqa: PLC0415
    from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError  # noqa: PLC0415

    try:
        recompile_catalog(repo_root)
    except (NotInsideRepositoryError, GitCommonDirUnavailableError, UnknownArtifactIdError, WholeKindUnresolvedError) as exc:
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


def reproject_pack_skills(repo_root: Path, kind: str) -> None:
    """Re-run the managed installer's pack-skill projection after a skill (de)activation.

    Shared tail for ``activate_cmd``/``deactivate_cmd``. Only the ``skill`` kind
    changes what is projected into the project skill roots (ADR 2026-09-27-1);
    deactivation retires manifest-owned pack entries, never built-in skills. The
    activation change is already committed when this runs, so a refusal (name
    collision, unknown wrapper target, unusable namespace) is reported with the
    remedy and exits non-zero without having written any skill file.
    """
    if kind != ArtifactKind.SKILL.operator_token:
        return
    from specify_cli.core.agent_config import AgentConfigError
    from specify_cli.skills.catalog import PackSkillCatalogError
    from specify_cli.skills.installer import project_pack_skills

    try:
        projection = project_pack_skills(repo_root)
    except (PackSkillCatalogError, AgentConfigError, OSError, ValueError) as exc:
        console.print(
            f"[red]Error:[/red] pack skills were not projected: {exc}. "
            "The activation change is recorded; fix the cause and re-run this command."
        )
        raise typer.Exit(1) from exc
    for path in projection.changed:
        console.print(f"[green]Skill file synced[/green]: {path}")
    for path, reason in projection.preserved:
        console.print(f"[yellow]Skill file preserved[/yellow]: {path} ({reason})")
    for warning in projection.warnings:
        console.print(f"[yellow]Warning[/yellow]: {warning}")


#: The pack ``--preset`` reads when ``--pack`` is not given.
DEFAULT_PRESET_PACK = "built-in"

#: Code of a ``--preset --json`` run whose preset was written but whose
#: post-write resynthesis failed.
_RESYNTHESIS_FAILED = "RESYNTHESIS_FAILED"

_PRESET_ONLY_OPTIONS: tuple[tuple[str, str], ...] = (("pack", "--pack"), ("force", "--force"))

#: Compared by ``.name``, never against ``click.core.ParameterSource``: typer
#: 0.26+ vendors its own click (``typer._click``) whose enum shares no identity
#: with the real ``click`` package's, so an identity check flags every option
#: as given (see ``parameter_source_name``, #4964).
_DEFAULT_SOURCE = "DEFAULT"


def _check_preset_flags(ctx: typer.Context, *, preset: str | None, positional: bool, cascade: str | None, only: bool = False) -> None:
    """Enforce the ``--preset`` flag rules through Click's usage path (exit 2, before any I/O).

    Refusals go through ``ctx.fail``, which raises the ``UsageError`` of the click
    universe that built ``ctx``: a real-click ``UsageError`` raised inside a
    vendored-click dispatch escapes typer's handler as a traceback.
    """
    if preset is not None:
        if positional:
            ctx.fail("--preset cannot be combined with a positional KIND ARTIFACT_ID.")
        if cascade is not None:
            ctx.fail("--cascade cannot be combined with --preset (presets do not cascade).")
        if only:
            ctx.fail("--only cannot be combined with --preset (a preset already replaces every key it governs).")
        return
    given = [flag for name, flag in _PRESET_ONLY_OPTIONS if parameter_source_name(ctx, name) != _DEFAULT_SOURCE]
    if given:
        ctx.fail(f"{', '.join(given)} only {'applies' if len(given) == 1 else 'apply'} with --preset.")
    if not positional and parameter_source_name(ctx, "json_output") != _DEFAULT_SOURCE:
        ctx.fail("--json applies with --preset or a positional KIND ARTIFACT_ID.")


def _render_preset_exclusions(outcome: PresetOutcome) -> None:
    """Name the listed ids a preset left deactivated, or whose exclusion ``--force`` cleared (FR-009, FR-014)."""
    for key, ids in outcome.kept_deactivated.items():
        console.print(
            f"  [yellow]Kept deactivated[/yellow]: {key}: {escape(', '.join(ids))} "
            "(listed by the preset; left out; --force clears the exclusion)"
        )
    for key, ids in outcome.cleared.items():
        console.print(f"  [green]Cleared exclusion[/green]: {key}: {escape(', '.join(ids))}")


def _render_preset_plan(plan: PresetPlan, outcome: PresetOutcome) -> None:
    if plan.is_noop and not outcome.cleared:
        console.print(f"Preset '{escape(plan.preset)}' of pack '{escape(plan.pack)}' is already in force in {plan.target_file}; nothing changed.")
        _render_preset_exclusions(outcome)
        return
    console.print(f"[green]Applied preset[/green] '{escape(plan.preset)}' of pack '{escape(plan.pack)}' to {plan.target_file}")
    for key, ids in outcome.written.items():
        console.print(f"  [green]Wrote[/green] {key}: {escape(', '.join(ids)) or '(none)'}")
    for key in plan.removed:
        console.print(f"  [yellow]Removed[/yellow] {key} (unrestricted)")
    _render_preset_exclusions(outcome)


def _preset_payload(plan: PresetPlan, outcome: PresetOutcome) -> dict[str, object]:
    """The ``--json`` shape of an applied preset (contracts/cli.md); the exclusion fields appear only when non-empty."""
    payload: dict[str, object] = {
        "pack": plan.pack,
        "preset": plan.preset,
        "written": outcome.written,
        "removed": plan.removed,
        "target_file": str(plan.target_file),
    }
    if outcome.kept_deactivated:
        payload["kept_deactivated"] = outcome.kept_deactivated
    if outcome.cleared:
        payload["cleared_exclusions"] = outcome.cleared
    return payload


def _plan_and_apply_preset(repo_root: Path, pack: str, preset: str, *, force: bool, json_output: bool) -> tuple[PresetPlan, PresetOutcome]:
    """Validate the config, plan and apply the preset; render a refusal and exit(1) on failure."""
    try:
        validate_pack_config(repo_root)
        plan = plan_preset_application(repo_root, pack, preset)
        outcome = apply_preset_plan(repo_root, plan, force=force)
    except PresetApplicationError as exc:
        render_coded_error(exc.code, str(exc), details=exc.detail_lines(), payload=exc.payload(), json_output=json_output)
        raise typer.Exit(1) from exc
    except ActiveCharterConfigError as exc:
        render_coded_error(exc.code, exc.body, json_output=json_output)
        raise typer.Exit(1) from exc
    except PresetFormatError as exc:
        render_preset_format_error(exc, json_output=json_output)
        raise typer.Exit(1) from exc
    return plan, outcome


def _activate_preset(repo_root: Path, pack: str, preset: str, *, force: bool, json_output: bool, compile_catalog: bool, resynthesize: bool) -> None:
    """``charter activate --preset``: apply a pack's preset with replace semantics (FR-001).

    Order: write-root resolution (fails closed from a linked worktree) ->
    pack-config validation -> the pure plan -> refusal without ``--force``
    when a customised key would change -> one write -> the same catalog
    refresh the positional path finishes with. Presets never govern skills, so
    no pack-skill re-projection runs. ``--resynthesize`` runs the full
    resynthesis after the write only: the positional path's read-only
    preflight is per ``(kind, id)`` and has no whole-preset form.
    """
    repo_root = resolve_write_root_or_exit(repo_root, json_output=json_output)
    plan, outcome = _plan_and_apply_preset(repo_root, pack, preset, force=force, json_output=json_output)
    if not json_output:
        _render_preset_plan(plan, outcome)
        recompile_or_notify(repo_root, resynthesize=resynthesize, compile_catalog=compile_catalog)
        return
    try:
        with console.capture():
            recompile_or_notify(repo_root, resynthesize=resynthesize, compile_catalog=compile_catalog)
    except typer.Exit as exc:
        if exc.exit_code == 0:
            raise
        message = (
            f"preset {plan.preset!r} of pack {plan.pack!r} was applied to {plan.target_file}, "
            f"but the resynthesis failed (exit {exc.exit_code}); re-run `spec-kitty charter synthesize`."
        )
        render_coded_error(_RESYNTHESIS_FAILED, message, payload=_preset_payload(plan, outcome), json_output=True)
        raise typer.Exit(1) from exc
    console.emit_json(_preset_payload(plan, outcome))


@contextlib.contextmanager
def _unwrapped(target: Console) -> Iterator[None]:
    """Print without wrapping at the terminal width, so one captured notice stays one line."""
    previous = target.soft_wrap
    target.soft_wrap = True
    try:
        yield
    finally:
        target.soft_wrap = previous


def captured_lines(text: str) -> list[str]:
    """The non-empty, whitespace-stripped lines of captured console output, with terminal styling removed."""
    return [line.strip() for line in sanitize_terminal_text(text).splitlines() if line.strip()]


def _captured_tail(step: Callable[[], None], code: str, what: str, payload: dict[str, object]) -> tuple[str, ...]:
    """Run a post-change *step* with its human output captured and return that output as notice lines.

    A non-zero exit becomes coded error *code*. Mirrors ``--preset --json``: the
    change is already recorded, so the error carries the change report as its
    payload, and the step's captured output as ``detail``.
    """
    capture = console.capture()
    try:
        with json_output_guard(True), capture, _unwrapped(console):
            step()
    except typer.Exit as exc:
        if exc.exit_code == 0:
            raise
        detail = "\n".join(captured_lines(capture.get()))
        render_coded_error(code, f"{what} (exit {exc.exit_code}).", payload={**payload, "detail": detail}, json_output=True)
        raise typer.Exit(1) from exc
    return tuple(captured_lines(capture.get()))


def emit_change_report_json(
    build: Callable[[], tuple[Path, ActivationChangeReport]], *, kind: str, resynthesize: bool, compile_catalog: bool
) -> None:
    """The ``--json`` form of positional activate/deactivate: exactly one JSON document on stdout.

    *build* runs the preflights, the write and the cascade with its human output
    captured; a :class:`CodedRefusal` is rendered after the capture closed, as
    the canonical error envelope. The catalog refresh and the pack-skill
    projection run captured too: what they print becomes the report's
    ``notices``. The change report is emitted last.
    """
    try:
        with json_output_guard(True), console.capture():
            repo_root, report = build()
    except CodedRefusal as refusal:
        render_refusal(refusal, json_output=True)
    recorded = f"the {report.command} of {report.kind} {report.id!r} is recorded, but"
    notices = _captured_tail(
        lambda: recompile_or_notify(repo_root, resynthesize=resynthesize, compile_catalog=compile_catalog),
        _RESYNTHESIS_FAILED,
        f"{recorded} the catalog refresh failed; re-run `spec-kitty charter synthesize`",
        report.to_json(),
    )
    report = dataclasses.replace(report, notices=notices)
    notices += _captured_tail(
        lambda: reproject_pack_skills(repo_root, kind),
        ACTIVATION_FAILED,
        f"{recorded} the pack skills were not projected; fix the cause and re-run this command",
        report.to_json(),
    )
    console.emit_json(dataclasses.replace(report, notices=notices).to_json())


def _dropped_footer(report: ActivationChangeReport) -> str:
    """The ``--only`` footer: what stopped being in force, or that it is unknown (Decision ``only_unknown_footer``)."""
    if report.no_longer_in_force is None:
        return "[yellow]No longer in force[/yellow]: unknown (see the warning above)"
    dropped = report.no_longer_in_force
    return f"[yellow]No longer in force ({len(dropped)})[/yellow]: {escape(', '.join(dropped)) or '(none)'}"


def _direct_activation_report(
    result: ActivationResult, registration: ProjectRegistrationPlan, *, only: bool, kind: str, artifact_id: str = ""
) -> ActivationChangeReport:
    """The direct-write part of a positional activation's change report (what ``manager.activate`` did)."""
    return ActivationChangeReport(
        command="activate",
        kind=kind,
        id=artifact_id,
        changed=tuple(result.activated),
        no_longer_in_force=tuple(result.deactivated) if only and result.dropped_known else None,
        now_listed=tuple(result.listed) if only else None,
        warnings=tuple(registration.warnings),
        result_warnings=tuple(result.warnings),
    )


def _render_activation_result(result: ActivationResult, registration: ProjectRegistrationPlan, *, only: bool, kind: str) -> None:
    """Print what ``manager.activate`` did: activated ids, warnings and, for ``--only``, the written list and what dropped."""
    _render_direct_activation(_direct_activation_report(result, registration, only=only, kind=kind))


def _render_direct_activation(report: ActivationChangeReport) -> None:
    """Print the direct-write lines of a change report (:func:`_render_activation_result`'s text)."""
    for msg in report.changed:
        console.print(f"[green]Activated[/green]: {msg}")
    for warn in report.warnings:
        console.print(f"[yellow]Warning[/yellow]: {warn}")
    for warn in report.result_warnings:
        console.print(f"[yellow]Warning[/yellow]: {escape(warn)}")
    if report.now_listed is not None:
        listed = report.now_listed
        console.print(f"Now listed for {escape(report.kind)} ({len(listed)}): {escape(', '.join(listed)) or '(none)'}")
        console.print(_dropped_footer(report))


def render_activation_change(report: ActivationChangeReport) -> None:
    """Print a positional activation's change report, in the order the command has always printed it."""
    _render_direct_activation(report)
    # FR-010: co-activated, unreconciled in_tension_with pairs, right after
    # the activation-result warnings and before the cascade.
    for warning in report.tension_warnings:
        console.print(f"[yellow]Warning[/yellow]: {warning}")
    if report.referenced is not None:
        render_no_cascade_warning(report.referenced)
    if report.cascade is not None:
        render_cascade_activation(report.cascade)


@dataclass(frozen=True)
class _ActivationRequest:
    """The positional ``charter activate`` arguments the change report is built from."""

    kind: str
    artifact_id: str
    cascade: str | None
    include_deactivated: bool
    resynthesize: bool
    only: bool


@dataclass(frozen=True)
class _Preflight:
    """What the checks before the first write resolved.

    ``repo_root``: the write root; ``scope``: the parsed ``--cascade``;
    ``deactivated``: the deny set the cascade walks with; ``step_warnings``: the
    report lines of the in-flight step-removal warnings already printed.
    """

    repo_root: Path
    scope: CascadeScope | None
    deactivated: frozenset[str]
    step_warnings: tuple[str, ...]


def _activation_preflight(request: _ActivationRequest, repo_root: Path) -> _Preflight:
    """Every check before the first write: write root, scope, pack config, mission-type preflights.

    Every refusal is a :class:`CodedRefusal`.
    """
    check_activation_kind(request.kind)
    # FR-006/Contract C3: fail closed from a linked git worktree before any
    # mutation, and resolve the ONE checkout root every downstream call in
    # this command (ctx_project, cascade rendering, the catalog recompile,
    # and run_full_synthesize's chdir) shares from here on -- closing the
    # split-brain where the activation flag landed in one checkout and the
    # recompile landed in another (issue #4785 Finding 3).
    repo_root = resolve_write_root(repo_root)

    # FR-013/014: parse the scope value object — never collapsed to a bool
    # (Contract C3.3). A bad kind token is a CASCADE_SCOPE_INVALID refusal.
    scope = parse_cascade_scope(request.cascade)

    # FR-035 fail-closed: reject invalid pack config before any mutation (C1.5).
    try:
        # Its deny set is the cascade's: the direct activation below can only clear
        # the source's own entry, which the cascade engine never treats as denied.
        deactivated = validate_pack_config(repo_root).deactivated_urns
    except ActiveCharterConfigError as exc:
        raise config_refusal(exc) from exc

    # FR-008: in-flight step-removal warnings (generalized — no inline
    # `kind == "mission-type"` branch in the command flow).
    #
    # CL-006/NFR-002 (post-fix verification sweep, mission
    # up-mission-type-seam-01KZY1JB): this reaches the layered mission-type
    # roster (``resolve_layered_roster`` -> ``resolve_layered_mission_types``
    # -> ``scan_mission_types_dir``), which loud-fails BY DESIGN (WP03,
    # PR-CONTRACT-002) on a malformed/unreadable YAML file anywhere in the
    # built-in, org, or project ``mission_types/`` layer. A bare
    # ``except ValueError`` also catches ``pydantic.ValidationError`` (the
    # schema-validation failure mode the same resolver chain documents as a
    # separate ``Raises`` entry) because ``pydantic.ValidationError``
    # subclasses ``ValueError`` in the pinned pydantic version.
    try:
        step_warnings = _step_removal_warnings(request.kind, request.artifact_id, repo_root)
        _render_step_removal_warnings(step_warnings)
        _validate_mission_type_activatable(request.kind, request.artifact_id, repo_root)
    except ValueError as exc:
        raise CodedRefusal(ACTIVATION_FAILED, str(exc)) from exc
    texts = tuple(text for text in map(step_removal_text, step_warnings) if text is not None)
    return _Preflight(repo_root, scope, deactivated, texts)


def _apply_direct_activation(
    request: _ActivationRequest,
    manager: ActiveCharterManager,
    ctx_project: ProjectContext,
    scope: CascadeScope | None,
    layer_roots: dict[str, Path] | None,
) -> tuple[ActivationResult, ProjectRegistrationPlan]:
    """Plan the project registration and activate the named artifact (the one direct write)."""
    repo_root = ctx_project.require_repo_root()
    try:
        registration = plan_project_registration(repo_root)
        if request.resynthesize:
            from specify_cli.cli.commands.charter._resynthesis_preflight import preflight_resynthesis

            preflight_resynthesis(
                repo_root, request.kind, request.artifact_id, scope, registration.graph, include_deactivated=request.include_deactivated
            )
        # #5779/#6006: one availability scan across the whole org-pack chain
        # (fail-closed on a declared-but-unfetched pack, #4984).
        result = manager.activate(
            ctx_project,
            request.kind,
            request.artifact_id,
            cascade=scope is not None,
            layer_roots=layer_roots,
            org_root_chain=resolve_pack_chain(repo_root, strict=True),
            only=request.only,
        )
    except ActiveCharterConfigError as exc:
        # FR-013: the strict required floor (read when a deny list exists) or the ledger cannot be read; nothing written.
        raise config_refusal(exc) from exc
    except (ValueError, DRGLoadError) as exc:
        raise CodedRefusal(ACTIVATION_FAILED, str(exc)) from exc
    return result, registration


def _activation_change_report(request: _ActivationRequest, repo_root: Path) -> tuple[Path, ActivationChangeReport]:
    """Run a positional activation (direct write, then cascade) and return its write root and change report."""
    preflight = _activation_preflight(request, repo_root)
    repo_root, scope, deactivated = preflight.repo_root, preflight.scope, preflight.deactivated
    ctx_project = ProjectContext(repo_root=repo_root)
    layer_roots = resolve_layer_roots(repo_root)
    manager = ActiveCharterManager()
    result, registration = _apply_direct_activation(request, manager, ctx_project, scope, layer_roots)
    commit_project_registration(registration)

    # FR-013/014: cascade is driven from the CLI via the WP11 engine over the
    # merged DRG (pack_manager's own cascade is deferred — the live wiring is
    # here). Resolve the source URN; mission-type / non-DRG kinds short-circuit.
    tension = _tension_warnings(repo_root)
    source_urn = _source_urn(request.kind, request.artifact_id, layer_roots, resolve_pack_chain(repo_root, strict=False))
    referenced: NoCascadeReport | None = None
    cascade: CascadeReport | None = None
    if source_urn is not None and scope is None:
        referenced = _no_cascade_report(source_urn, repo_root, layer_roots, deactivated - {source_urn})
    elif source_urn is not None and scope is not None:
        cascade = _cascade_activation_report(
            manager, ctx_project, source_urn, scope, repo_root, layer_roots, include_deactivated=request.include_deactivated, deactivated=deactivated
        )
    report = dataclasses.replace(
        _direct_activation_report(result, registration, only=request.only, kind=request.kind, artifact_id=request.artifact_id),
        preflight_warnings=preflight.step_warnings,
        tension_warnings=tuple(tension),
        referenced=referenced,
        cascade=cascade,
    )
    return repo_root, report


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
    include_deactivated: bool = typer.Option(
        False,
        "--include-deactivated",
        help=INCLUDE_DEACTIVATED_HELP,
        # Own panel: the long flag name would widen the main options table's
        # first column and wrap other options' printed defaults.
        rich_help_panel="Cascade options",
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
    preset: str | None = typer.Option(
        None,
        "--preset",
        help="Apply this activation preset of the pack with replace semantics instead of activating one artifact.",
    ),
    pack: str = typer.Option(
        DEFAULT_PRESET_PACK,
        "--pack",
        help="Pack whose preset --preset applies (built-in, an org pack name). Only with --preset.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=PRESET_FORCE_HELP,
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON (positional form: change report; --preset: applied preset)."),
    only: bool = typer.Option(
        False,
        "--only",
        help="Replace this kind's activation list with this id plus org-required ids (prints what stops being in force).",
    ),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Activate a doctrine artifact by kind and ID (FR-004), or apply a pack's preset.

    Two forms:

      spec-kitty charter activate KIND ARTIFACT_ID [--cascade SCOPE [--include-deactivated]] [--only] [--json]

      spec-kitty charter activate [--pack PACK] --preset PRESET [--force] [--json]

    A preset replaces every activation key it governs: keys it lists are
    written (plus the org's required ids), keys it leaves out are removed.
    A change to a customised key is refused without --force. A deactivated
    id the preset lists stays deactivated (and is left out) unless --force,
    which also clears its exclusion.

    The cascade stops at a deactivated artifact and reports it;
    --include-deactivated walks through and clears the exclusions.
    """
    if ctx.invoked_subcommand is not None:
        return
    if include_deactivated and cascade is None:
        ctx.fail("--include-deactivated only applies with --cascade.")
    _check_preset_flags(ctx, preset=preset, positional=kind is not None or artifact_id is not None, cascade=cascade, only=only)
    if preset is not None:
        _activate_preset(repo_root, pack, preset, force=force, json_output=json_output, compile_catalog=compile_catalog, resynthesize=resynthesize)
        return
    if kind is None or artifact_id is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    request = _ActivationRequest(kind, artifact_id, cascade, include_deactivated, resynthesize, only)
    if json_output:
        emit_change_report_json(lambda: _activation_change_report(request, repo_root), kind=kind, resynthesize=resynthesize, compile_catalog=compile_catalog)
        return
    try:
        repo_root, report = _activation_change_report(request, repo_root)
    except CodedRefusal as refusal:
        render_refusal(refusal, json_output=False)
    render_activation_change(report)

    # FR-001/FR-003/FR-007: default catalog recompile keeps activation
    # coherent-by-construction (issue #4785 Finding 1) -- runs AFTER cascade
    # so it reconciles the complete post-activation config state, not just
    # the direct target. See `recompile_or_notify` for the
    # resynthesize/compile/no-compile precedence.
    recompile_or_notify(repo_root, resynthesize=resynthesize, compile_catalog=compile_catalog)
    reproject_pack_skills(repo_root, kind)
