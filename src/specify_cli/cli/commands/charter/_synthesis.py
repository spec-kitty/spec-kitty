"""Synthesis helpers shared by ``charter synthesize`` and ``charter resynthesize``.

Lifted from the legacy ``charter.py`` during the WP06 MS-1 split. Module is
behaviour-preserving; only import paths changed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from specify_cli.cli.console import console, err_console
from specify_cli.task_utils import TaskCliError

if TYPE_CHECKING:
    from charter.activation.synthesizer.reconcile import (
        NodeOrEdgeRef,
        ReconciliationConflict,
        ReconciliationDelta,
    )

# ``_interview_path`` is part of the legacy charter test-patch surface. We must
# look it up on the package module at call time (not bind it at import time) so
# ``patch("specify_cli.cli.commands.charter._interview_path", …)`` propagates
# here after the WP06 split. ``_synthesis`` is imported from the package
# ``__init__`` itself, so the package import is performed lazily inside
# functions to avoid a circular import at module-load time.

# #2758: single hoisted message (Sonar S1192 -- also referenced verbatim by
# the fail-closed preflight test) for the fail-closed bundle-completeness
# guard. consolidate-charter-bundle WP03/T013: the bundle's sole
# content-hash input is now ``charter.yaml`` (data-model.md Landmine 1 /
# manifest v2 -- the legacy four-file set is retired). ``synthesize`` never
# itself compiles ``charter.yaml`` (only ``charter generate`` /
# ``compile_charter`` does), so failing closed toward ``charter generate``
# / the fold migration is the only non-circular remediation -- re-running
# ``synthesize`` can never self-heal a missing bundle file.
BUNDLE_INCOMPLETE_MESSAGE = (
    "Charter bundle incomplete: '{missing}' is missing. "
    "Run `spec-kitty charter generate` (or the charter.yaml migration) first "
    "to compile it, then retry `charter synthesize`."
)


def _build_synthesis_request(
    repo_root: Path,
    adapter_name: str,
    evidence: Any = None,
) -> tuple[Any, Any]:
    """Build a SynthesisRequest + adapter from the project's current interview state.

    Returns ``(SynthesisRequest, adapter)`` ready for synthesize() / resynthesize().
    Raises ``TaskCliError`` if the interview answers file does not exist.
    """
    import uuid

    from charter.activation.compiler import resolve_config_activated_roots
    from charter.activation.interview import read_interview_answers
    from charter.activation.pack_context import PackContext
    from charter.activation.synthesizer.fixture_adapter import FixtureAdapter
    from charter.activation.synthesizer.generated_artifact_adapter import GeneratedArtifactAdapter
    from charter.activation.synthesizer.request import SynthesisRequest, SynthesisTarget

    import specify_cli.cli.commands.charter as _charter_pkg

    answers_path = _charter_pkg._interview_path(repo_root)
    interview_data = read_interview_answers(answers_path)
    if interview_data is None:
        raise TaskCliError("No interview answers found. Run 'spec-kitty charter interview' first.")

    # FR-001/FR-002 (WP02): the project-graph derivation reads
    # ``config.activated_*``, not ``answers.selected_*`` -- ``answers.yaml``
    # remains the captured interview record (still folded into the snapshot
    # below via ``interview_data.answers``) but is retired as an activation
    # source. ``resolve_config_activated_roots`` is the shared charter-layer
    # seam that also drives the ``references.yaml`` derivation in
    # ``charter.activation.compiler.compile_charter``, so both derivation paths agree.
    config_roots = resolve_config_activated_roots(repo_root=repo_root)

    # #2577 (fast-follow fix of the #2526 regression): `config_roots.directives`
    # already applied the three-state absent-key fallback documented on
    # `PackContext` -- when `.kittify/config.yaml` has no `activated_directives`
    # key at all, `resolve_config_activated_roots()` returns EVERY built-in
    # directive (the correct default for the `compile_charter`/references.yaml
    # consumer, see `test_no_pack_context_and_no_repo_root_defaults_to_all_
    # builtins_active`). Feeding that same "all built-ins" list into
    # `interview_snapshot["selected_directives"]` is wrong for THIS consumer:
    # `resolve_sections()` expands one `how-we-apply-<directive>` companion-
    # tactic target per entry, so a first-run project with no explicit
    # activation yet demanded ~25 companion tactics nobody asked for and
    # failed `charter synthesize` closed on the first missing YAML. Read the
    # raw three-state signal directly so the absent-key case (first run) is
    # distinguished from an explicit (possibly empty) activation list -- only
    # the latter should drive companion-tactic expansion, matching the
    # pre-#2526 behavior where this field was sourced from
    # `answers.selected_directives` and defaulted to `[]` on a fresh interview.
    pack_context = PackContext.from_config(repo_root)
    directives_for_synthesis: list[str] = [] if pack_context.activated_directives is None else config_roots.directives

    # Build a minimal interview snapshot, config-activated selections + answers
    interview_snapshot: dict[str, Any] = {
        "mission_id": interview_data.mission,
        "selected_directives": directives_for_synthesis,
        "selected_paradigms": config_roots.paradigms,
    }
    interview_snapshot.update(dict(interview_data.answers))

    # Build a minimal doctrine snapshot (directives only for now)
    doctrine_snapshot: dict[str, Any] = {
        "directives": {},
        "tactics": {},
        "styleguides": {},
    }

    # Build a minimal DRG snapshot with config-activated directives as nodes.
    # Sourced from the SAME `directives_for_synthesis` list as
    # `selected_directives` above (rather than the raw `config_roots.directives`
    # fallback) so the two never drift into an inconsistent state where nodes
    # exist for directives no target references.
    drg_nodes = []
    for directive_id in directives_for_synthesis:
        # Only fields ``DRGNode`` declares: the snapshot is validated as a
        # ``DRGGraph`` downstream. An ``id`` key rode along here for a while --
        # redundant with the URN suffix, read by nothing, and silently dropped
        # at validation until WP04 made ``DRGNode`` forbid extras (FR-004).
        drg_nodes.append(
            {
                "urn": f"directive:{directive_id}",
                "kind": "directive",
            }
        )
    drg_snapshot: dict[str, Any] = {
        "nodes": drg_nodes,
        "edges": [],
        "schema_version": "1",
    }

    # Internal placeholder target. ``synthesize()`` derives the actual
    # target list from the interview, so this token is never the artifact
    # the synthesizer actually produces — it just satisfies the Pydantic
    # constructor that requires a non-None ``target``.
    #
    # FR-005 (WP02): ``PROJECT_000`` is INTERNAL ONLY here. The CLI
    # surface MUST NOT expose it. The four user-visible code paths
    # (``--json`` success, ``--json`` dry-run, ``--json`` failure, and
    # the human-readable text branch) all derive their displayed
    # artifact_id from ``ProvenanceEntry.artifact_urn`` produced by the
    # synthesizer (see ``_load_written_artifacts_from_manifest`` and
    # ``compute_written_artifacts``), never from this constructor
    # placeholder. The path-parity test in
    # ``tests/charter/synthesizer/test_synthesize_path_parity.py``
    # guards against regression.
    target = SynthesisTarget(
        kind="directive",
        slug="synthesize-placeholder",
        title="Synthesize Placeholder",
        artifact_id="PROJECT_000",
        source_section="mission_type",
    )

    run_id = str(uuid.uuid4()).replace("-", "").upper()[:26]

    request = SynthesisRequest(
        target=target,
        interview_snapshot=interview_snapshot,
        doctrine_snapshot=doctrine_snapshot,
        drg_snapshot=drg_snapshot,
        run_id=run_id,
        evidence=evidence,
    )

    adapter_obj: Any
    if adapter_name == "generated":
        adapter_obj = GeneratedArtifactAdapter(repo_root=repo_root)
    elif adapter_name == "fixture":
        adapter_obj = FixtureAdapter()
    else:
        raise TaskCliError(
            f"Unknown adapter '{adapter_name}'. "
            "Supported adapters are '--adapter generated' and '--adapter fixture'. "
            "Doctrine generation is performed by the LLM harness (Claude Code, Codex, "
            "Cursor, etc.) via the spec-kitty-charter-doctrine skill. "
            "spec-kitty never calls an LLM itself."
        )

    return request, adapter_obj


def _collect_evidence_result(
    repo_root: Path,
    *,
    skip_code_evidence: bool,
    skip_corpus: bool,
) -> Any:
    from charter.activation.evidence.orchestrator import EvidenceOrchestrator, load_url_list_from_config

    url_list = load_url_list_from_config(repo_root)
    orchestrator = EvidenceOrchestrator(
        repo_root=repo_root,
        url_list=url_list,
        skip_code=skip_code_evidence,
        skip_corpus=skip_corpus,
    )
    return orchestrator.collect()


def _build_synthesis_validation_callback(request: Any, *, repo_root: Path | None = None) -> Any:
    from charter.drg import DRGGraph
    from charter.activation._drg_helpers import org_chain_graph
    from charter.activation.synthesizer.interview_mapping import normalize_interview_snapshot, resolve_sections
    from charter.activation.synthesizer.orchestrator import _built_in_drg_from_snapshot
    from charter.activation.synthesizer.project_drg import emit_project_layer, persist as persist_project_graph
    from charter.activation.synthesizer.synthesize_pipeline import _get_synthesizer_version
    from charter.activation.synthesizer.targets import build_targets, detect_duplicates, order_targets
    from charter.activation.synthesizer.validation_gate import validate as validate_project_graph

    # WP03 campsite fix: this call site duplicated a bare, unprotected
    # ``importlib.metadata.version("spec-kitty-cli")`` lookup instead of
    # reusing the package's own safe helper. It never raised in production
    # (real installs resolve the distribution fine) but crashes with a bare
    # ``PackageNotFoundError`` under an editable/dev checkout where metadata
    # discovery differs by import context (e.g. pytest vs. a plain
    # interpreter) -- reproduced by this WP's own dry-run CLI tests, the
    # first callers to exercise this code path for real instead of mocking
    # it away. ``_get_synthesizer_version()`` (already used by
    # ``orchestrator.synthesize()`` for the exact same purpose) never raises.
    spec_kitty_version = _get_synthesizer_version()
    built_in_drg = DRGGraph.model_validate(_built_in_drg_from_snapshot(request.drg_snapshot))
    interview_snapshot = normalize_interview_snapshot(dict(request.interview_snapshot))
    sections = resolve_sections(interview_snapshot)
    targets = build_targets(
        interview_snapshot=interview_snapshot,
        mappings=sections,
        drg_snapshot=dict(request.drg_snapshot),
    )
    targets = order_targets(targets)
    detect_duplicates(targets)
    if not targets:
        targets = [request.target]

    # Org-aware base (#4121, MAJOR 2) shared by the emit and the gate below;
    # ``None`` for org-less repos keeps both byte-identical to before.
    org_drg = org_chain_graph(repo_root) if repo_root is not None else None

    def _validation_callback(staged_dir: Any) -> None:
        project_graph = emit_project_layer(
            targets=targets,
            spec_kitty_version=spec_kitty_version,
            built_in_drg=built_in_drg,
            # M6 (#3038): thread the project root so hand-authored project
            # agent_profile nodes are emitted here too, keeping this preview/
            # dry-run emit consistent with the real write path.
            project_root=repo_root,
            org_drg=org_drg,
        )
        persist_project_graph(project_graph, staged_dir.root, staged_dir.guard)
        validate_project_graph(staged_dir.root, built_in_drg, org_drg=org_drg)

    return _validation_callback


def _read_written_artifacts_from_manifest(repo_root: Path) -> list[dict[str, str]]:
    """Read manifest entries for the strict synthesize success envelope."""
    try:
        from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml as _load_manifest
    except Exception:
        return []
    manifest_path = repo_root / MANIFEST_PATH
    if not manifest_path.exists():
        return []
    try:
        manifest = _load_manifest(manifest_path)
    except Exception:
        return []
    return [{"path": entry.path, "kind": entry.kind} for entry in manifest.artifacts]


def _provenance_to_planned_artifacts(
    results: list[tuple[Any, Any]],
) -> list[dict[str, str]]:
    """Convert synthesis provenance entries into planned doctrine paths."""
    from charter.activation.synthesizer.artifact_naming import (
        artifact_filename,
        doctrine_kind_subdir,
    )

    planned: list[dict[str, str]] = []
    for _body, prov in results:
        kind = prov.artifact_kind
        slug = prov.artifact_slug
        artifact_id: str | None = None
        if kind == "directive":
            artifact_id = prov.artifact_urn.split(":", 1)[1]
        try:
            filename = artifact_filename(kind, slug, artifact_id)
            subdir = doctrine_kind_subdir(kind)
        except Exception:  # noqa: S112
            continue
        planned.append(
            {
                "path": f".kittify/doctrine/{subdir}/{filename}",
                "kind": kind,
            }
        )
    return planned


def _staged_to_planned_artifacts(staged_files: list[str]) -> list[dict[str, str]]:
    """Convert legacy staged ``kind:slug`` selectors to planned artifacts."""
    from charter.activation.synthesizer.artifact_naming import (
        artifact_filename,
        doctrine_kind_subdir,
    )

    planned: list[dict[str, str]] = []
    for selector in staged_files:
        if ":" not in selector:
            continue
        kind, slug = selector.split(":", 1)
        artifact_id: str | None = None
        if kind == "directive":
            artifact_id = "PROJECT_000"
        try:
            filename = artifact_filename(kind, slug, artifact_id)
            subdir = doctrine_kind_subdir(kind)
        except Exception:  # noqa: S112
            continue
        planned.append(
            {
                "path": f".kittify/doctrine/{subdir}/{filename}",
                "kind": kind,
            }
        )
    return planned


def _run_synthesis_dry_run(
    request: Any,
    syn_adapter: Any,
    repo_root: Path,
) -> list[str]:
    """Stage + validate without promoting; return ``kind:slug`` selectors.

    Legacy ``staged_artifacts`` field on the dry-run JSON envelope is sourced
    from this list. The strict ``written_artifacts`` field (FR-003) is built
    separately in :func:`_run_synthesis_dry_run_with_artifacts`, which calls
    this function and additionally projects the typed staged-artifact entries
    via :func:`charter.activation.synthesizer.write_pipeline.compute_written_artifacts`.
    """
    from charter.activation.synthesizer.staging import StagingDir
    from charter.activation.synthesizer.synthesize_pipeline import run_all
    from charter.activation.synthesizer.write_pipeline import stage_and_validate

    results = run_all(request, adapter=syn_adapter)
    validation_callback = _build_synthesis_validation_callback(request, repo_root=repo_root)

    with StagingDir.create(repo_root, request.run_id) as staging_dir:
        staged_artifacts: list[str] = stage_and_validate(
            request,
            staging_dir,
            results,
            validation_callback,
        )
        staging_dir.wipe()

    return staged_artifacts


def _run_synthesis_dry_run_with_artifacts(
    request: Any,
    syn_adapter: Any,
    repo_root: Path,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Stage + validate; return both legacy selectors and typed written-artifact entries.

    The typed ``written_artifacts`` list is sourced from the SAME
    ``compute_written_artifacts`` helper used by the real-run branch — this is
    the FR-004 byte-equal-path guarantee. ``run_all`` is invoked once; the
    same ``results`` feed both ``stage_and_validate`` (which exercises the
    write-time validation gate) and ``compute_written_artifacts`` (which
    projects per-artifact provenance).
    """
    from charter.activation.synthesizer.staging import StagingDir
    from charter.activation.synthesizer.synthesize_pipeline import run_all
    from charter.activation.synthesizer.write_pipeline import (
        compute_written_artifacts,
        stage_and_validate,
    )

    results = run_all(request, adapter=syn_adapter)
    validation_callback = _build_synthesis_validation_callback(request, repo_root=repo_root)

    with StagingDir.create(repo_root, request.run_id) as staging_dir:
        staged_artifacts = stage_and_validate(
            request,
            staging_dir,
            results,
            validation_callback,
        )
        staging_dir.wipe()

    # FR-003 / FR-004: typed staged-artifact entries — never reconstructed
    # from kind:slug selectors. Same source of truth as the real-run path.
    typed = compute_written_artifacts(results, repo_root)
    written_artifacts = [
        {
            "path": entry.path,
            "kind": entry.kind,
            "slug": entry.slug,
            "artifact_id": entry.artifact_id,
        }
        for entry in typed
    ]
    return staged_artifacts, written_artifacts


def _load_written_artifacts_from_manifest(repo_root: Path) -> list[dict[str, Any]]:
    """Project the on-disk synthesis manifest into ``WrittenArtifact`` dicts.

    Single source of truth for the real-run JSON envelope (FR-003): we read
    the manifest the write pipeline wrote last (KD-2 commit marker) and
    project each ``ManifestArtifactEntry`` plus its sibling provenance
    sidecar into the four-field ``WrittenArtifact`` shape.

    The provenance sidecar is consulted because the manifest does not carry
    ``artifact_id`` directly; the URN segment after ``directive:`` is the
    canonical id (e.g. ``directive:PROJECT_001`` → ``PROJECT_001``). For
    non-directive kinds (tactic, styleguide), ``artifact_id`` is ``None``
    per the ``WrittenArtifact`` schema.

    Returns ``[]`` when the manifest is absent — this happens when the
    real-run code path is mocked out by tests, so the JSON envelope still
    carries a valid empty ``written_artifacts`` list (FR-002 / INV-E-2).

    All fields are pure data; the function never raises (a corrupt manifest
    yields an empty list rather than blowing up the strict-JSON contract).
    """
    try:
        from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml
    except Exception:
        return []

    manifest_path = repo_root / MANIFEST_PATH
    if not manifest_path.is_file():
        return []

    try:
        manifest = load_yaml(manifest_path)
    except Exception:
        return []

    entries: list[dict[str, Any]] = []
    for entry in manifest.artifacts:
        artifact_id: str | None = None
        if entry.kind == "directive":
            # Provenance sidecar at .kittify/charter/provenance/<kind>-<slug>.yaml
            # carries the URN; that is the only on-disk surface that records
            # the symbolic artifact_id without lossy reconstruction.
            prov_path = repo_root / entry.provenance_path
            artifact_id = _extract_artifact_id_from_provenance(prov_path)

        entries.append(
            {
                "path": entry.path,
                "kind": entry.kind,
                "slug": entry.slug,
                "artifact_id": artifact_id,
            }
        )
    return entries


def _extract_artifact_id_from_provenance(prov_path: Path) -> str | None:
    """Read ``artifact_urn`` from a provenance sidecar; return the id segment.

    The sidecar is YAML with a top-level ``artifact_urn`` key shaped like
    ``directive:PROJECT_001``. Return ``None`` on any parse failure or if
    the URN does not carry a non-empty id segment.
    """
    if not prov_path.is_file():
        return None
    try:
        from ruamel.yaml import YAML

        y = YAML(typ="safe")
        with prov_path.open("r", encoding="utf-8") as f:
            data = y.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    urn = data.get("artifact_urn")
    if not isinstance(urn, str):
        return None
    parts = urn.split(":", 1)
    if len(parts) != 2 or not parts[1]:
        return None
    return parts[1]


def _list_resynthesis_topics(
    request: Any,
    repo_root: Path,
) -> dict[str, list[str]]:
    from charter.activation.synthesizer.resynthesize_pipeline import (
        _load_merged_drg,
        _load_project_artifacts_from_provenance,
    )

    project_artifacts = _load_project_artifacts_from_provenance(repo_root)
    merged_drg = _load_merged_drg(repo_root, request)
    interview_sections = sorted(str(section) for section in request.interview_snapshot)

    artifact_topics = []
    for artifact in project_artifacts:
        selector = artifact.urn if artifact.kind == "directive" else f"{artifact.kind}:{artifact.slug}"
        artifact_topics.append(selector)

    drg_topics: list[str] = []
    for node in merged_drg.get("nodes", []):
        if isinstance(node, dict):
            urn = node.get("urn")
            if isinstance(urn, str) and urn:
                drg_topics.append(urn)

    return {
        "project_artifacts": sorted(dict.fromkeys(artifact_topics)),
        "drg_urns": sorted(dict.fromkeys(drg_topics)),
        "interview_sections": interview_sections,
        "interview_section_aliases": sorted(section.replace("_", "-") for section in interview_sections),
    }


def _raise_if_bundle_incomplete(repo_root: Path) -> None:
    """Fail closed before a real synthesize run persists an un-healable ``None``.

    Separate helper (not inlined into ``charter_synthesize``, which already
    carries a pre-existing ``# noqa: C901``): the real-run path eventually
    reaches ``write_pipeline.promote()``, which stamps
    ``compute_bundle_content_hash(repo_root)`` into the synthesis manifest.
    That helper is intentionally fail-safe (returns ``None``, never raises)
    when the ``charter.yaml`` bundle file is missing, and a ``None`` stored
    hash is unconditionally read back as ``stale`` by
    ``specify_cli.charter_runtime.freshness.computer`` -- with no signal
    telling the operator *why*, and no way for a subsequent ``synthesize``
    re-run to fix it (issue #2758).

    Raises
    ------
    TaskCliError
        When :func:`charter.bundle.first_missing_bundle_file` reports a
        missing file. consolidate-charter-bundle (#2773): the input is the
        single authoritative ``charter.yaml``; the message points the operator
        at ``spec-kitty upgrade`` / ``charter generate`` to produce it.
    """
    from charter.bundle import first_missing_bundle_file  # noqa: PLC0415

    missing = first_missing_bundle_file(repo_root)
    if missing is not None:
        raise TaskCliError(BUNDLE_INCOMPLETE_MESSAGE.format(missing=missing))


def _has_generated_artifacts(repo_root: Path) -> bool:
    """Return True iff ``.kittify/charter/generated/`` contains agent-authored YAMLs.

    The ``generated`` adapter (production default) reads YAML files written by
    the LLM harness under ``.kittify/charter/generated/{directives,tactics,
    styleguides}/``. On a fresh project the harness has not run yet, so this
    directory is either missing or empty. The fresh-project synthesize path
    (T032 / #839) keys on this signal.
    """
    generated_root = repo_root / ".kittify" / "charter" / "generated"
    if not generated_root.is_dir():
        return False
    for sub in ("directives", "tactics", "styleguides"):
        sub_dir = generated_root / sub
        if sub_dir.is_dir() and any(sub_dir.glob("*.yaml")):
            return True
    return False


# ---------------------------------------------------------------------------
# #4785 Finding 2-core: the fresh-project predicate must key on whether this
# store has actually been activated/synthesized for real, not merely on
# whether ``.kittify/charter/generated/`` currently has agent-authored YAML.
# A store that was compiled long ago, has real ``activated_*`` selections, or
# already completed one real (non-seed) synthesis run is ESTABLISHED even if
# its ``generated/`` directory happens to be empty right now (e.g. cleaned up
# after a prior harness session) -- reclassifying it as "fresh" would wipe
# its real state back down to the minimal built-in-only seed (the exact bug
# #4785 reproduced, see research.md Finding 2).
# ---------------------------------------------------------------------------

#: The ``activated_*`` root fields ``charter.yaml`` can carry (charter
#: contract G3 / ``schemas.py::CharterYaml``). ``mission_type_activations``
#: is DELIBERATELY excluded: ``charter generate``'s own provisioning step
#: (``provision_mission_type_activations``) unconditionally populates it on
#: EVERY run -- including a genuinely fresh, never-activated project -- so
#: treating it as an "established" signal would misclassify every
#: fresh-project fixture (confirmed empirically: a bare ``generate
#: --from-interview`` run with empty ``selected_*`` answers already writes a
#: non-empty ``mission_type_activations`` list, while every OTHER
#: ``activated_*`` field stays absent).
_ACTIVATION_SIGNAL_KEYS: tuple[str, ...] = (
    "activated_kinds",
    "activated_directives",
    "activated_tactics",
    "activated_styleguides",
    "activated_toolguides",
    "activated_paradigms",
    "activated_procedures",
    "activated_agent_profiles",
    "activated_mission_step_contracts",
)


def _has_real_prior_synthesis(repo_root: Path) -> bool:
    """Return True iff a REAL (non-seed) synthesis has already run.

    Reads ``.kittify/charter/synthesis-manifest.yaml`` directly (no full
    ``SynthesisManifest`` validation -- this is a cheap presence/flag probe,
    not a consumer of the manifest's content). The fresh-project seed path
    itself (``_materialize_fresh_doctrine``) writes this same file with
    ``built_in_only: true`` -- that is NOT evidence of a real synthesis (it
    is the seed's own marker, and re-running the seed on top of it must stay
    idempotent -- see ``tests/integration/test_charter_synthesize_fresh.py::
    test_synthesize_is_idempotent``). Only ``built_in_only: false`` --
    written exclusively by a real synthesis run (the production ``generated``
    adapter path, or the registered-direct-project-artifact path in
    ``_synthesize_project_doctrine``) -- counts as "already established".

    A present-but-unparseable manifest is treated conservatively as
    established (returns True): the fresh-project short-circuit must never
    fire on top of a manifest this code cannot positively prove is just the
    seed's own marker.
    """
    from charter.activation.charter_yaml_io import load_charter_yaml

    manifest_path = repo_root / ".kittify" / "charter" / "synthesis-manifest.yaml"
    if not manifest_path.is_file():
        return False
    try:
        data = load_charter_yaml(manifest_path)
    except Exception:  # noqa: BLE001 -- conservative fail-closed, see docstring.
        return True
    if not isinstance(data, dict):
        return True
    return data.get("built_in_only") is False


def _interview_answers_present(repo_root: Path) -> bool:
    """Return True iff readable ``charter interview`` answers exist on disk.

    A REAL ``charter synthesize`` run consumes the interview answers at
    ``.kittify/charter/interview/answers.yaml`` (see
    :func:`_build_synthesis_request`, which reads them and fails closed when
    they are absent). Their presence is therefore the on-disk footprint a
    genuine prior synthesis necessarily left behind -- used by
    :func:`_catalog_is_established` to tell a real established store apart
    from an orphan/incomplete one carrying only a ``built_in_only: false``
    manifest marker (#4785 Regression 3).

    Reads through :func:`~charter.activation.interview.read_interview_answers`
    (returns ``None`` for a missing or empty file) so an empty answers file is
    correctly treated as absent, and degrades to ``False`` on any read error
    rather than raising -- the caller's establishment probe must never crash
    ``charter synthesize``.
    """
    from charter.activation.interview import read_interview_answers  # noqa: PLC0415

    import specify_cli.cli.commands.charter as _charter_pkg  # noqa: PLC0415

    try:
        answers_path = _charter_pkg._interview_path(repo_root)
        return read_interview_answers(answers_path) is not None
    except Exception:  # noqa: BLE001 -- defensive presence probe, never fatal.
        return False


def _catalog_is_established(repo_root: Path, charter_yaml_path: Path) -> bool:
    """Return True iff ``charter_yaml_path`` shows evidence of a real, prior
    charter-store activation/synthesis -- the positive "not fresh" signal
    (#4785 Finding 2-core) that replaces the old ``generated/`` absence
    check.

    Two independent signals, either of which is sufficient:

    1. Any ``activated_*`` root field (see ``_ACTIVATION_SIGNAL_KEYS``) is an
       explicit, non-empty list -- i.e. an operator has really activated at
       least one artifact via ``charter activate`` (charter contract G3's
       three-state semantics: ``None`` == never touched, ``[]`` == explicit
       fail-closed empty, non-empty == real activation).
    2. ``.kittify/charter/synthesis-manifest.yaml`` already records a REAL
       (non-seed) synthesis (:func:`_has_real_prior_synthesis`) **AND** the
       interview answers a real synthesis run consumes are still on disk
       (:func:`_interview_answers_present`).

    The interview-answers conjunct on signal 2 (#4785 Regression 3) is the
    narrowing that distinguishes a genuinely established store from an
    orphan/incomplete one: a ``built_in_only: false`` manifest with no
    ``answers.yaml`` (and no ``activated_*`` selection, no ``generated/``
    content, no registered project artifacts) could not have been produced by
    a real synthesis run -- it is an incomplete marker the fresh-project seed
    legitimately repairs, not real state the seed would destroy. The
    Finding-2 protection stays intact: the store that finding targets (a real
    synthesis whose ``generated/`` dir was merely cleaned up) still has its
    ``activated_*`` selections and/or its ``answers.yaml``, so it is still
    classified established and never re-seeded (pinned by
    ``tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py``).

    Read directly off the round-tripped YAML mapping (``load_charter_yaml``)
    rather than through the full ``CharterYaml`` pydantic model: this is a
    narrow, defensive presence probe, not a schema-validating consumer. An
    unreadable ``charter.yaml`` yields no positive ``activated_*`` signal but
    still falls through to the answers-gated manifest check -- so an
    unreadable-but-genuinely-established store (real manifest + answers)
    stays established, while an unreadable, orphan-manifest, no-answers store
    is correctly seed-repairable.

    ``catalog.references`` itself is deliberately NOT used as a signal here,
    despite being the intuitive "compiled catalog" field: ``compile_charter``
    resolves an ABSENT ``activated_*`` config key to "every built-in artifact
    of that kind" (the #2577 default-pack fallback), so ``catalog.references``
    already carries ~250+ entries on a project's VERY FIRST ``charter
    generate`` run, before any real activation or synthesis has happened.
    Gating on non-empty ``catalog.references`` would misclassify every
    genuinely fresh project as established.
    """
    try:
        from charter.activation.charter_yaml_io import load_charter_yaml

        data: Any = load_charter_yaml(charter_yaml_path)
    except Exception:  # noqa: BLE001 -- unreadable: no activated_* signal, fall through.
        data = None
    if isinstance(data, dict):
        for key in _ACTIVATION_SIGNAL_KEYS:
            value = data.get(key)
            if isinstance(value, list) and value:
                return True
    return _has_real_prior_synthesis(repo_root) and _interview_answers_present(repo_root)


def _print_synthesis_commit_reminder() -> None:
    console.print("[yellow]Synthesis artifacts written; commit provenance before continuing:[/yellow]")
    console.print("  git add .kittify/charter/synthesis-manifest.yaml .kittify/charter/provenance/ .kittify/doctrine/")
    console.print("  git commit -m 'chore: charter synthesis artifacts'")


# ---------------------------------------------------------------------------
# WP03 (charter-synthesize-reconciliation-01KZJQN6) -- CLI-owned reconciliation
# policy on top of the library's ReconciliationDelta (reconcile.py, WP01):
# preserve-and-warn default, --prune list-and-remove, --dry-run report-and-
# no-write, and the narrow orphan-without-prune / unparseable-overlay
# refusal (FR-003 / FR-007 / FR-010 / FR-014). The library seam owns the
# MECHANISM (merge/prune/dry-run); everything here is the CLI's POLICY on
# top of it.
# ---------------------------------------------------------------------------


def _reconciliation_preview(request: Any, repo_root: Path) -> ReconciliationDelta:
    """Compute this run's ``ReconciliationDelta`` without writing anything.

    Every WP03 mode decision -- the ``--dry-run`` report AND the orphan-
    refusal check ahead of a real preserve/prune write -- reads from this
    ONE preview computation.

    Deliberately does NOT call ``charter.activation.synthesizer.synthesize`` (nor
    ``run_all()``/the adapter): the GRAPH-level delta fields this WP consumes
    (``retained``/``added``/``removable`` node+edge refs, used for orphan
    detection and --dry-run reporting) depend only on ``targets`` --
    interview/DRG-snapshot-derived, computed identically to the real write
    path's ``_build_synthesis_validation_callback`` -- and on-disk state,
    never on adapter output. Reusing the canonical
    ``reconcile.reconcile_synthesis`` (C-002) with an empty ``new_results``
    list gives an EXACT graph-level preview without invoking the adapter, so
    a preview never fails (or double-runs) an adapter a real run would also
    exercise. Only the returned delta's ``manifest_delta`` is a coarser
    approximation (every existing manifest entry reads as "preserved" since
    no ``new_results`` are supplied) -- WP03 never reads ``manifest_delta``
    from this preview, only ``.removable``/``.retained``/``.conflicts``.
    """
    from charter.drg import DRGGraph  # noqa: PLC0415
    from charter.activation._drg_helpers import org_chain_graph  # noqa: PLC0415
    from charter.activation.synthesizer.interview_mapping import normalize_interview_snapshot, resolve_sections  # noqa: PLC0415
    from charter.activation.synthesizer.orchestrator import _built_in_drg_from_snapshot  # noqa: PLC0415
    from charter.activation.synthesizer.project_drg import emit_project_layer  # noqa: PLC0415
    from charter.activation.synthesizer.reconcile import reconcile_synthesis  # noqa: PLC0415
    from charter.activation.synthesizer.synthesize_pipeline import _get_synthesizer_version  # noqa: PLC0415
    from charter.activation.synthesizer.targets import build_targets, detect_duplicates, order_targets  # noqa: PLC0415

    spec_kitty_version = _get_synthesizer_version()
    built_in_drg = DRGGraph.model_validate(_built_in_drg_from_snapshot(request.drg_snapshot))
    interview_snapshot = normalize_interview_snapshot(dict(request.interview_snapshot))
    sections = resolve_sections(interview_snapshot)
    targets = build_targets(
        interview_snapshot=interview_snapshot,
        mappings=sections,
        drg_snapshot=dict(request.drg_snapshot),
    )
    targets = order_targets(targets)
    detect_duplicates(targets)
    if not targets:
        targets = [request.target]

    # Org-aware base (#4121, MAJOR 2) shared by the emit and the reconcile
    # below — the same universe the real write path threads through
    # ``orchestrator.synthesize`` — so the preview never mis-classifies an
    # org-referencing edge the real run would keep.
    org_drg = org_chain_graph(repo_root)
    fresh_overlay = emit_project_layer(
        targets=targets,
        spec_kitty_version=spec_kitty_version,
        built_in_drg=built_in_drg,
        # M6 (#3038): include hand-authored project agent_profile nodes so the
        # reconciliation preview (orphan-refusal + --dry-run report) matches the
        # real write path and never mis-classifies a persisted profile node as
        # a removable orphan.
        project_root=repo_root,
        org_drg=org_drg,
    )
    outcome = reconcile_synthesis(
        repo_root=repo_root,
        fresh_overlay=fresh_overlay,
        new_results=[],
        run_id=request.run_id,
        built_in_drg=built_in_drg,
        org_drg=org_drg,
    )
    return outcome.delta


def _orphaned_removals(delta: ReconciliationDelta | None) -> tuple[NodeOrEdgeRef, ...]:
    """``delta.removable`` entries with no backing artifact left on disk.

    FR-014 / T014: a plain (non-``--prune``) run that would need to drop one
    of these is the narrow orphan-refusal case -- the graph still
    references content that no longer exists on disk, so silently
    preserving it verbatim would keep a dangling reference instead of
    surfacing the problem to the operator. Backed divergence (the common
    case) is never refused -- it is preserved and reported (US2 AC4).

    Returns ``()`` when *delta* is not a real ``ReconciliationDelta`` (e.g.
    ``None``, or a test double standing in for a mocked ``SynthesisResult``)
    -- there is nothing to classify without a genuine delta.
    """
    from charter.activation.synthesizer.reconcile import ReconciliationDelta as _ReconciliationDelta  # noqa: PLC0415

    if not isinstance(delta, _ReconciliationDelta):
        return ()
    return tuple(ref for ref in delta.removable if ref.backing_artifact is None)


_ORPHAN_REMEDIATION_TEMPLATE = (
    "Remediation (orphaned {ref_kind}): '{urn}' has no backing artifact on "
    "disk. Restore the backing artifact, or run "
    "`spec-kitty charter synthesize --prune` to remove it."
)


def _format_conflict_line(kind: str, target_id: str, backing_artifact: str | None, remediation: str) -> str:
    """Render one refusal/prune/dry-run line from the DRG typed-conflict shape.

    FR-014 / T015: every reported class -- a real ``ReconciliationConflict``
    (``duplicate_triple`` / ``preserved_dangling_endpoint``) or a
    WP03-classified orphaned removal -- renders through this ONE formatter
    (``kind`` + ``target_id`` + ``backing_artifact`` + ``remediation``) so
    the CLI never hand-rolls a second, parallel message format.
    """
    backing = backing_artifact if backing_artifact else "(orphaned -- no backing artifact on disk)"
    return f"  [{kind}] {target_id} (backing: {backing})\n      {remediation}"


def _orphan_ref_to_line(ref: NodeOrEdgeRef) -> str:
    remediation = _ORPHAN_REMEDIATION_TEMPLATE.format(ref_kind=ref.ref_kind, urn=ref.urn)
    return _format_conflict_line(f"orphaned_{ref.ref_kind}", ref.urn, ref.backing_artifact, remediation)


def _conflict_to_line(conflict: ReconciliationConflict) -> str:
    return _format_conflict_line(conflict.kind, conflict.target_id, conflict.backing_artifact, conflict.remediation)


def _ref_to_dict(ref: NodeOrEdgeRef) -> dict[str, Any]:
    return {"ref_kind": ref.ref_kind, "urn": ref.urn, "backing_artifact": ref.backing_artifact}


def _conflict_to_dict(conflict: ReconciliationConflict) -> dict[str, Any]:
    return {
        "kind": conflict.kind,
        "target_id": conflict.target_id,
        "backing_artifact": conflict.backing_artifact,
        "remediation": conflict.remediation,
        "provenance": conflict.provenance,
    }


def _emit_dry_run_report(
    *,
    json_output: bool,
    adapter_name: str,
    syn_adapter: Any,
    warnings_collected: list[str],
    staged_files: list[str],
    written_artifacts_dr: list[dict[str, Any]],
    delta: ReconciliationDelta,
) -> None:
    """Emit the ``--dry-run`` report (FR-010): planned deletions, no write.

    ``written_artifacts``/``staged_artifacts`` still come from the legacy
    staging helper (``_run_synthesis_dry_run_with_artifacts`` -- byte-equal
    path parity with the real-run branch, FR-004); ``planned_deletes`` /
    ``conflicts`` are the NEW reconciliation-delta fields this WP adds to
    the same envelope (T013). Handles both ``--json`` and human console
    output, including the ``mark_invocation_succeeded()`` side effect, so
    the caller only needs to call this once and return.
    """
    from specify_cli.diagnostics import mark_invocation_succeeded  # noqa: PLC0415

    planned_deletes = [_ref_to_dict(ref) for ref in delta.removable]
    conflict_dicts = [_conflict_to_dict(c) for c in delta.conflicts]

    if json_output:
        print(
            json.dumps(
                {
                    # Contracted fields (FR-002):
                    "result": "dry_run",
                    "adapter": {
                        "id": getattr(syn_adapter, "id", adapter_name),
                        "version": getattr(syn_adapter, "version", "unknown"),
                    },
                    "written_artifacts": written_artifacts_dr,
                    "warnings": warnings_collected,
                    # Legacy compatibility fields (data-model.md §E-1):
                    "staged_artifacts": staged_files,
                    "artifact_count": len(staged_files),
                    "validated": True,
                    # FR-010: reconciliation delta preview -- what --prune would
                    # remove; empty when there is no divergence.
                    "planned_deletes": planned_deletes,
                    "conflicts": conflict_dicts,
                },
                indent=2,
                sort_keys=True,
            )
        )
        mark_invocation_succeeded()
        return

    console.print("[yellow]Dry-run:[/yellow] synthesis staged and validated (not promoted)")
    for f in staged_files:
        console.print(f"  [dim]staged:[/dim] {f}")
    if delta.removable:
        console.print("[yellow]Planned deletions (would run under --prune):[/yellow]")
        for ref in delta.removable:
            console.print(f"  - {ref.ref_kind}: {ref.urn}")
    else:
        console.print("[dim]No divergence: --prune would remove nothing.[/dim]")
    for conflict in delta.conflicts:
        console.print(f"[yellow]{_conflict_to_line(conflict)}[/yellow]")


def _emit_orphan_refusal(
    *,
    json_output: bool,
    adapter_name: str,
    warnings_collected: list[str],
    orphaned: tuple[NodeOrEdgeRef, ...],
) -> None:
    """FR-014 / T014: refuse (exit 1) a plain run that would drop orphaned content.

    Always raises ``typer.Exit(code=1)`` -- never returns normally. The real
    run's call site (``synthesize.py``) reaches this AFTER
    ``charter.activation.synthesizer.synthesize()`` has already run in preserve mode --
    i.e. after the write. Nothing was actually destroyed by that write:
    preserve mode never deletes, so the "refuse" here is about the *content*
    (a dangling, backing-artifact-deleted reference) rather than an
    in-progress write. A no-write preview path (e.g. a future dry-run
    caller reachable purely via ``_reconciliation_preview``) would reach
    this function before any write at all.
    """
    lines = [_orphan_ref_to_line(ref) for ref in orphaned]

    if json_output:
        print(
            json.dumps(
                {
                    "result": "failure",
                    "adapter": {"id": adapter_name, "version": "unknown"},
                    "written_artifacts": [],
                    "warnings": warnings_collected + lines,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        err_console.print(
            "[red]Refused:[/red] this run preserved orphaned content instead of dropping it; the following references are dangling (backing artifact deleted):"
        )
        for line in lines:
            err_console.print(line)
        err_console.print("[yellow]Re-run with `--prune` to remove it, or restore the backing artifact.[/yellow]")
    raise typer.Exit(code=1)


def _emit_real_run_report(
    *,
    json_output: bool,
    result: Any,
    written_artifacts_real: list[dict[str, Any]],
    warnings_collected: list[str],
    prune: bool,
) -> None:
    """Emit the real-run (preserve/prune) success report.

    ``prune=True`` lists every effected deletion (T012); ``prune=False``
    reports retained content plus preserved-content conflict warnings
    (T011). Both read ``result.reconciliation`` -- the SAME delta the write
    just acted on, never a second recomputation. When ``result`` is a test
    double that carries no ``.reconciliation`` attribute at all, or whose
    ``.reconciliation`` is not a real ``ReconciliationDelta`` (e.g. a
    fully-mocked ``SynthesisResult``), the reconciliation section of the
    report is simply omitted -- there is nothing genuine to report.
    """
    from specify_cli.diagnostics import mark_invocation_succeeded  # noqa: PLC0415
    from charter.activation.synthesizer.reconcile import ReconciliationDelta as _ReconciliationDelta  # noqa: PLC0415

    reconciliation = getattr(result, "reconciliation", None)
    if not isinstance(reconciliation, _ReconciliationDelta):
        reconciliation = None

    if json_output:
        payload: dict[str, Any] = {
            # Contracted fields (FR-002):
            "result": "success",
            "adapter": {
                "id": result.effective_adapter_id,
                "version": result.effective_adapter_version,
            },
            "written_artifacts": written_artifacts_real,
            "warnings": warnings_collected,
            # Legacy compatibility fields (data-model.md §E-1):
            "target_kind": result.target_kind,
            "target_slug": result.target_slug,
            "inputs_hash": result.inputs_hash,
            "adapter_id": result.effective_adapter_id,
            "adapter_version": result.effective_adapter_version,
        }
        if reconciliation is not None:
            if prune:
                payload["deletions"] = [_ref_to_dict(ref) for ref in reconciliation.removable]
            else:
                payload["retained"] = [_ref_to_dict(ref) for ref in reconciliation.retained]
                payload["conflicts"] = [_conflict_to_dict(c) for c in reconciliation.conflicts]
        print(json.dumps(payload, indent=2, sort_keys=True))
        mark_invocation_succeeded()
        return

    console.print("[green]Charter synthesis complete[/green]")
    console.print(f"Primary artifact: {result.target_kind}:{result.target_slug}")
    console.print(f"Adapter: {result.effective_adapter_id} v{result.effective_adapter_version}")
    if reconciliation is not None:
        if prune:
            if reconciliation.removable:
                console.print("[yellow]Pruned (removed):[/yellow]")
                for ref in reconciliation.removable:
                    console.print(f"  - {ref.ref_kind}: {ref.urn}")
            else:
                console.print("[dim]--prune: nothing to prune.[/dim]")
        else:
            if reconciliation.retained:
                console.print("[dim]Retained on-disk content (untargeted by this run):[/dim]")
                for ref in reconciliation.retained:
                    console.print(f"  - {ref.ref_kind}: {ref.urn}")
            for conflict in reconciliation.conflicts:
                console.print(f"[yellow]{_conflict_to_line(conflict)}[/yellow]")
    if written_artifacts_real:
        _print_synthesis_commit_reminder()


# Fresh-project doctrine seed helpers were carved out into ``_fresh_doctrine``
# so this module stays comfortably under the WP06 line budget. Re-exported so
# legacy ``from specify_cli.cli.commands.charter._synthesis import …`` consumers
# (and the package ``__init__``) keep working unchanged.
from specify_cli.cli.commands.charter._fresh_doctrine import (  # noqa: E402,F401
    _MINIMAL_FRESH_DOCTRINE_PROVENANCE_TEMPLATE,
    _materialize_fresh_doctrine,
    _planned_fresh_doctrine_deletes,
    _planned_fresh_doctrine_paths,
)

__all__ = [
    "_MINIMAL_FRESH_DOCTRINE_PROVENANCE_TEMPLATE",
    "_build_synthesis_request",
    "_build_synthesis_validation_callback",
    "_catalog_is_established",
    "_collect_evidence_result",
    "_emit_dry_run_report",
    "_emit_orphan_refusal",
    "_emit_real_run_report",
    "_extract_artifact_id_from_provenance",
    "_has_generated_artifacts",
    "_list_resynthesis_topics",
    "_load_written_artifacts_from_manifest",
    "_materialize_fresh_doctrine",
    "_orphaned_removals",
    "_planned_fresh_doctrine_deletes",
    "_planned_fresh_doctrine_paths",
    "_print_synthesis_commit_reminder",
    "_provenance_to_planned_artifacts",
    "_raise_if_bundle_incomplete",
    "_read_written_artifacts_from_manifest",
    "_reconciliation_preview",
    "_run_synthesis_dry_run",
    "_run_synthesis_dry_run_with_artifacts",
    "_staged_to_planned_artifacts",
]
