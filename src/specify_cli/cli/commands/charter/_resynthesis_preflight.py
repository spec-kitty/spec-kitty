"""Read-only checks for the activation state an eager synthesis would consume."""

from __future__ import annotations

from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

from charter.activation.cascade import CascadeScope, cascade_activation_targets
from charter.activation.catalog import resolve_doctrine_root
from charter.activation.compiler import resolve_config_activated_roots
from charter.activation.default_pack import load_default_pack_activation_ids
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
    defaults = load_default_pack_activation_ids()
    selections: dict[str, frozenset[str]] = {}

    def include(operator_kind: str, identifier: str) -> None:
        if operator_kind == "mission-type":
            return
        key = YAML_KEY_MAP[operator_kind]
        current = selections.get(key, getattr(context, key))
        selections[key] = frozenset(defaults.get(key, []) if current is None else current) | {identifier}

    include(kind, artifact_id)
    roots = resolve_layer_roots(repo_root)
    org_roots = resolve_org_root_chain(repo_root)
    if scope is not None and kind != "mission-type":
        source = resolve_artifact_urn(
            ArtifactKind.from_operator_token(kind), artifact_id, doctrine_root=resolve_doctrine_root(), layer_roots=roots, org_roots=org_roots
        )
        cascaded = cascade_activation_targets(graph, source, scope)
        for kind_value, identifiers in cascaded.activated.items():
            for identifier in identifiers:
                config_id = resolve_config_id(f"{kind_value}:{identifier}", doctrine_root=resolve_doctrine_root(), layer_roots=roots, org_roots=org_roots)
                include(ArtifactKind(kind_value).operator_token, config_id)
    resolve_config_activated_roots(repo_root=repo_root, pack_context=replace(context, **selections))
    # Reuse the synthesis emitter's support rules (including its additive-only
    # project-profile policy), so an unsupported profile fails before activation.
    try:
        emit_project_layer([], version("spec-kitty-cli"), load_built_in_graph(), project_root=repo_root)
    except ProjectDRGValidationError as exc:
        raise ValueError(f"Cannot resynthesize the requested activation: {exc}") from exc
