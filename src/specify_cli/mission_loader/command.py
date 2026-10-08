"""Functional core for the ``spec-kitty mission run`` CLI subcommand.

Validates a custom-mission definition, registers synthesized step
contracts in the per-process runtime registry shadow, and starts (or
attaches to) the runtime for the requested tracked mission slug.

The functional core never raises on operator-fixable errors and never
calls :func:`sys.exit` or :func:`typer.Exit`; the Typer wrapper in
:mod:`specify_cli.cli.commands.mission_type` is responsible for
translating :class:`RunCustomMissionResult` into a process exit code.

Registry-shadow lifetime
------------------------
For v1 the registry is a process-singleton; this module enters the
registration once per CLI invocation and never exits. Subsequent
``spec-kitty next`` calls in the same process see the shadow. Future
tranches may revisit the lifetime model; until then, callers (including
tests) clear the registry manually when they need a clean slate.

Note (F-3, mission ``local-custom-mission-loader-01KQ2VNJ`` review): the
spec wording reads "registers in-process for the lifetime of the run."
v1 widens that to "lifetime of the *process*" -- a strict superset that
is operationally equivalent for the tested 1-shot CLI invocations
because the only id-collision risk is two sequential runs of the same
``mission_key`` in the same process, which v1 callers do not exercise.
A future tranche may tighten the lifetime (e.g., enter/exit
:func:`registered_runtime_contracts` per run) once a long-lived host
process is in the picture.
"""

from __future__ import annotations

from charter.activation.mission_type_key import read_mission_type
from kernel.charter_pack_paths import resolve_project_pack_read_root
from mission_runtime import MissionArtifactKind, placement_seam
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specify_cli.mission_loader.contract_synthesis import synthesize_contracts
from specify_cli.mission_loader.errors import (
    LoaderError,
    LoaderErrorCode,
    LoaderWarning,
    ValidationReport,
)
from specify_cli.mission_loader.registry import get_runtime_contract_registry
from specify_cli.mission_loader.validator import validate_custom_mission
from specify_cli.mission_metadata import load_meta_or_empty, write_meta
from runtime.next import runtime_bridge
from runtime.next._internal_runtime.discovery import DiscoveryContext
from runtime.next._internal_runtime.schema import MissionTemplate

# Infrastructure-level error code emitted by this CLI layer when
# ``runtime_bridge.get_or_start_run`` raises. Not part of the validator's
# closed enum (see contracts/validation-errors.md).
_RUN_START_FAILED_CODE = "RUN_START_FAILED"

# Operator-fixable refusal (#4965): the ``--mission`` handle resolved onto an
# existing mission whose recorded ``mission_type`` differs from the requested
# custom key. Emitted before any registry, runtime or ``meta.json`` write.
_MISSION_TYPE_CONFLICT_CODE = "MISSION_TYPE_CONFLICT"


@dataclass(frozen=True)
class RunCustomMissionResult:
    """Outcome of :func:`run_custom_mission`.

    Attributes:
        exit_code: 0 success, 1 infrastructure failure, 2 validation error.
        envelope: JSON-serializable dict matching
            ``contracts/mission-run-cli.md`` for the corresponding
            outcome (``result == "success"`` or ``result == "error"``).
    """

    exit_code: int
    envelope: dict[str, Any] = field(default_factory=dict)


def run_custom_mission(
    mission_key: str,
    mission_slug: str,
    repo_root: Path,
    *,
    discovery_context: DiscoveryContext | None = None,
) -> RunCustomMissionResult:
    """Validate, register synthesized contracts, start (or attach to) the runtime.

    Args:
        mission_key: Reusable custom-mission key (e.g. ``"erp-integration"``).
        mission_slug: Tracked mission slug (e.g. ``"erp-q3-rollout-01KQ..."``)
            used to key the run under ``kitty-specs/<slug>/`` and the
            ``feature-runs.json`` index.
        repo_root: Project repository root.
        discovery_context: Optional override; defaults to
            :func:`_build_discovery_context` mirroring the runtime bridge.

    Returns:
        :class:`RunCustomMissionResult` with the wire-stable envelope.
    """
    ctx = discovery_context or _build_discovery_context(repo_root)
    report = validate_custom_mission(mission_key, ctx)

    if not report.ok:
        return _validation_error_result(report)

    assert report.template is not None  # narrowed by report.ok
    assert report.discovered is not None  # narrowed by report.ok

    # F-2 (mission local-custom-mission-loader-01KQ2VNJ): cross-module
    # ``contract_ref`` resolution. The validator deliberately skips this
    # check (it does not load the on-disk repository); it must happen
    # at run-start before we register synthesized contracts so operators
    # see the structured ``MISSION_CONTRACT_REF_UNRESOLVED`` envelope
    # rather than the executor's "No step contract found ..." error
    # later in the run.
    unresolved = _resolve_contract_refs(
        mission_key=mission_key,
        template=report.template,
        source_path=report.discovered.path,
        repo_root=repo_root,
    )
    if unresolved is not None:
        return RunCustomMissionResult(
            exit_code=2,
            envelope={
                "result": "error",
                "error_code": str(unresolved.code),
                "message": unresolved.message,
                "details": dict(unresolved.details),
                "warnings": [_warning_dict(w) for w in report.warnings],
            },
        )

    # read-side-placement-seam-migration WP07: names PRIMARY_METADATA through
    # the seam authority instead of the kind-blind
    # ``candidate_feature_dir_for_mission`` — this feeds
    # ``_ensure_feature_metadata``, a ``meta.json``-adjacent read.
    # PRIMARY_METADATA is PRIMARY-partition, so resolution is behavior-
    # identical to the prior resolver; no fail-loud arm is reachable here.
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.PRIMARY_METADATA
    )
    conflict = _mission_type_conflict(feature_dir, mission_key, mission_slug)
    if conflict is not None:
        return RunCustomMissionResult(
            exit_code=2,
            envelope={
                **conflict,
                "warnings": [_warning_dict(w) for w in report.warnings],
            },
        )

    # Register synthesized contracts in the process-singleton shadow. We
    # intentionally do not enter the ``registered_runtime_contracts``
    # context manager because v1 holds the shadow for the rest of the
    # process; tests clear the registry directly between cases.
    registry = get_runtime_contract_registry()
    registry.register(synthesize_contracts(report.template))

    try:
        run_ref = runtime_bridge.get_or_start_run(
            mission_slug=mission_slug,
            repo_root=repo_root,
            mission_type=mission_key,
        )
    except Exception as exc:  # noqa: BLE001 -- infrastructure boundary
        registry.clear()
        return RunCustomMissionResult(
            exit_code=1,
            envelope={
                "result": "error",
                "error_code": _RUN_START_FAILED_CODE,
                "message": str(exc),
                "details": {
                    "mission_key": mission_key,
                    "mission_slug": mission_slug,
                },
                "warnings": [_warning_dict(w) for w in report.warnings],
            },
        )

    _ensure_feature_metadata(feature_dir, mission_key)

    return RunCustomMissionResult(
        exit_code=0,
        envelope={
            "result": "success",
            "mission_key": mission_key,
            "mission_slug": mission_slug,
            "mission_id": _read_mission_id(feature_dir),
            "feature_dir": str(feature_dir),
            "run_dir": str(run_ref.run_dir),
            "warnings": [_warning_dict(w) for w in report.warnings],
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_discovery_context(repo_root: Path) -> DiscoveryContext:
    """Mirror :func:`runtime_bridge._build_discovery_context`.

    The runtime bridge's helper is module-private; we duplicate the
    construction here so this module does not depend on a private
    surface. Both implementations point ``builtin_roots`` at the
    packaged missions directory so built-in keys resolve identically.

    Also mirrors the runtime bridge's ``org_roots`` population (FR-008,
    DEC-006 site 3 -- the third, independently-duplicated production
    wiring site that backs ``mission run <key>``): sourced via the lazy
    ``charter.drg.resolve_org_roots`` facade, no ``try/except`` around the
    call (``OrgPackSubdirEscapeError``/``OrgPackEnvVarUnsetError`` must
    propagate, DEC-005/NFR-001). ``resolve_org_roots`` returns ``[]`` when
    no org packs are configured, so this is a no-op for the common case
    (NFR-005/SC-007). ``quiet=True``: this helper backs a resolution hot
    path (``mission run <key>``) that may run many times per invocation --
    an unparseable config.yaml with no readable org intent must not spam a
    UserWarning per call (see load_pack_registry's docstring). A genuinely
    declared-but-broken org pack still raises a loud UserWarning regardless.
    """
    package_missions = (
        Path(runtime_bridge.__file__).resolve().parent.parent / "missions"
    )

    from charter.drg import resolve_org_roots  # lazy, mirrors the resolve_org_dirs pattern below

    return DiscoveryContext(
        project_dir=repo_root,
        builtin_roots=[package_missions],
        org_roots=list(resolve_org_roots(repo_root, quiet=True)),
    )


def _resolve_contract_refs(
    *,
    mission_key: str,
    template: MissionTemplate,
    source_path: str,
    repo_root: Path,
) -> LoaderError | None:
    """Resolve every step's ``contract_ref`` against the on-disk repository.

    Returns ``None`` if every ``contract_ref`` resolves (or no step sets
    one). On the first unresolved reference, returns a
    :class:`LoaderError` with code
    :attr:`LoaderErrorCode.MISSION_CONTRACT_REF_UNRESOLVED` so the
    caller can surface a structured exit-code-2 envelope per
    ``contracts/validation-errors.md``.

    The on-disk repository is loaded with the same ``project_dir``
    layout the runtime executor uses
    (``<repo_root>/.kittify/charter-packs/mission_step_contracts``); built-in
    contracts come from the package data. This keeps loader semantics
    aligned with the runtime so an id that resolves here will resolve
    at runtime too.
    """
    # Local import to avoid load-time coupling on the doctrine package.
    from charter.drg import resolve_org_dirs
    from charter.mission_steps import (
        MissionStepContractRepository,
    )

    repository: MissionStepContractRepository | None = None
    for step in template.steps:
        if step.contract_ref is None:
            continue
        if repository is None:
            repository = MissionStepContractRepository(
                project_dir=resolve_project_pack_read_root(repo_root, quiet=True) / "mission_step_contracts",
                org_dirs=resolve_org_dirs(repo_root, "mission_step_contracts"),
            )
        if repository.get(step.contract_ref) is None:
            return LoaderError(
                code=LoaderErrorCode.MISSION_CONTRACT_REF_UNRESOLVED,
                message=(
                    f"Step {step.id!r} references contract "
                    f"{step.contract_ref!r}, which is not present in the "
                    f"on-disk MissionStepContractRepository."
                ),
                details={
                    "file": source_path,
                    "mission_key": mission_key,
                    "step_id": step.id,
                    "contract_ref": step.contract_ref,
                },
            )
    return None


def _validation_error_result(report: ValidationReport) -> RunCustomMissionResult:
    """Build the exit-code-2 envelope from the FIRST error in ``report``."""
    err: LoaderError = report.errors[0]
    return RunCustomMissionResult(
        exit_code=2,
        envelope={
            "result": "error",
            "error_code": str(err.code),
            "message": err.message,
            "details": dict(err.details),
            "warnings": [_warning_dict(w) for w in report.warnings],
        },
    )


def _warning_dict(warning: LoaderWarning) -> dict[str, Any]:
    """Render a :class:`LoaderWarning` as a JSON-serializable dict."""
    return {
        "code": str(warning.code),
        "message": warning.message,
        "details": dict(warning.details),
    }


def _mission_type_conflict(
    feature_dir: Path, mission_key: str, mission_slug: str
) -> dict[str, Any] | None:
    """Return a refusal envelope when ``feature_dir`` holds a mission of another type.

    #4965: ``--mission`` handles (mid8, numeric prefix, reused slug) fold onto
    an existing mission directory. ``mission run`` may start a fresh mission or
    re-attach to one already recorded with ``mission_key``, and may type a
    typeless mission; it must never rewrite a recorded ``mission_type`` to a
    different key, which would silently switch the workflow ``next`` drives.
    """
    existing = read_mission_type(load_meta_or_empty(feature_dir))
    if existing is None or existing == mission_key:
        return None
    return {
        "result": "error",
        "error_code": _MISSION_TYPE_CONFLICT_CODE,
        "message": (
            f"Mission {mission_slug!r} already has mission type {existing!r}; "
            f"refusing to start a {mission_key!r} run on it. Pass a new "
            f"--mission slug to create a separate {mission_key!r} mission."
        ),
        "details": {
            "mission_key": mission_key,
            "mission_slug": mission_slug,
            "existing_mission_type": existing,
            "feature_dir": str(feature_dir),
        },
    }


def _ensure_feature_metadata(feature_dir: Path, mission_key: str) -> None:
    """Persist the custom mission key so later ``spec-kitty next`` resolves it.

    The runtime index under ``.kittify/runtime`` is not the only reader:
    ``decide_next_via_runtime`` first asks ``kitty-specs/<slug>/meta.json`` for
    the mission type. Without this handoff, a normal separate-process
    ``mission run`` -> ``next`` flow falls back to ``software-dev``.
    """
    feature_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = load_meta_or_empty(feature_dir)
    data["mission_type"] = mission_key
    data["mission_key"] = mission_key
    data.setdefault("mission", mission_key)
    write_meta(feature_dir, data, validate=False)


def _read_mission_id(feature_dir: Path) -> str | None:
    """Read ``mission_id`` from ``<feature_dir>/meta.json`` if present.

    Returns ``None`` when the file is missing or malformed; the success
    envelope tolerates a null ``mission_id`` for runs whose tracked
    mission has not yet been minted.
    """
    data = load_meta_or_empty(feature_dir)
    value = data.get("mission_id")
    if isinstance(value, str) and value:
        return value
    return None


__all__ = [
    "RunCustomMissionResult",
    "run_custom_mission",
]
