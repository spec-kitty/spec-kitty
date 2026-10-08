"""Read-only checks for the activation state an eager synthesis would consume."""

from __future__ import annotations

from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

from charter.activation.cascade import CascadeScope, cascade_activation_targets
from charter.activation.catalog import resolve_offering_root
from charter.activation.compiler import resolve_config_activated_roots
from charter.activation.effective_set import resolve_effective_sets
from charter.activation.kind_vocabulary import ArtifactKind, resolve_artifact_urn, resolve_config_id
from charter.activation.pack_context import PackContext
from charter.activation.pack_manager import YAML_KEY_MAP
from charter.activation.synthesizer.project_drg import emit_project_layer
from charter.activation.synthesizer.errors import ProjectDRGValidationError
from charter.drg import load_built_in_graph
from charter.drg import DRGGraph
from specify_cli.cli.commands.charter._common import _interview_path
from charter.activation.layer_roots import resolve_layer_roots, resolve_org_root_chain
from specify_cli.cli.commands.charter.generate import _is_inside_git_worktree, _load_interview_for_generate


def _seeded_from_effective_set(operator_kind: str) -> bool:
    """Whether an absent key of *operator_kind* means "everything effective" (a "required" kind seeds nothing)."""
    return bool(ArtifactKind.from_operator_token(operator_kind).effective_when_absent == "all")


def _future_selections(repo_root: Path, context: PackContext, requested: dict[str, set[str]]) -> dict[str, frozenset[str]]:
    """The activation sets after the write: the current set, or the effective set for an absent key, plus *requested*.

    An absent key is seeded from the effective set (FR-015, #4400) so the
    preflight checks the set the activation will actually write. When that set
    cannot be resolved this raises :class:`ValueError` before any write (the
    caller turns it into exit 1) rather than checking a narrowed set. A
    "required" kind (skills) is seeded from nothing, as its activation is.
    """
    key_kinds = {key: kind for kind, key in YAML_KEY_MAP.items()}
    absent = [key for key in requested if getattr(context, key) is None and _seeded_from_effective_set(key_kinds[key])]
    effective = resolve_effective_sets(repo_root, absent) if absent else {}
    selections: dict[str, frozenset[str]] = {}
    for key, identifiers in requested.items():
        current = getattr(context, key)
        if key in effective:
            seed = effective[key]
            if not seed.resolved:
                raise ValueError(f"Cannot resolve the effective {seed.kind} set for resynthesis: {seed.reason}. The activation was not written.")
            current = seed.ids
        selections[key] = frozenset(current or ()) | identifiers
    return selections


def preflight_resynthesis(repo_root: Path, kind: str, artifact_id: str, scope: CascadeScope | None, graph: DRGGraph) -> None:
    """Resolve the complete future activation set before any activation write."""
    if not _is_inside_git_worktree(repo_root):
        raise ValueError("Resynthesis requires a Git repository. Run `git init` before activation.")
    _load_interview_for_generate(
        repo_root=repo_root,
        answers_path=_interview_path(repo_root),
        from_interview=True,
        resolved_mission_type=None,
        profile="minimal",
    )
    context = PackContext.from_config(repo_root)
    requested: dict[str, set[str]] = {}

    def include(operator_kind: str, identifier: str) -> None:
        if operator_kind == "mission-type":
            return
        requested.setdefault(YAML_KEY_MAP[operator_kind], set()).add(identifier)

    include(kind, artifact_id)
    roots = resolve_layer_roots(repo_root)
    org_roots = resolve_org_root_chain(repo_root)
    if scope is not None and kind != "mission-type":
        source = resolve_artifact_urn(
            ArtifactKind.from_operator_token(kind), artifact_id, offering_root=resolve_offering_root(), layer_roots=roots, org_roots=org_roots
        )
        cascaded = cascade_activation_targets(graph, source, scope)
        for kind_value, identifiers in cascaded.activated.items():
            for identifier in identifiers:
                config_id = resolve_config_id(f"{kind_value}:{identifier}", offering_root=resolve_offering_root(), layer_roots=roots, org_roots=org_roots)
                include(ArtifactKind(kind_value).operator_token, config_id)
    selections = _future_selections(repo_root, context, requested)
    resolve_config_activated_roots(repo_root=repo_root, pack_context=replace(context, **selections))
    # Reuse the synthesis emitter's support rules (including its additive-only
    # project-profile policy), so an unsupported profile fails before activation.
    try:
        emit_project_layer([], version("spec-kitty-cli"), load_built_in_graph(), project_root=repo_root)
    except ProjectDRGValidationError as exc:
        raise ValueError(f"Cannot resynthesize the requested activation: {exc}") from exc
