"""Reach-only synthesized tactics (#6404).

A synthesized ``how-we-apply-*`` tactic is linked FROM its directive by a
``directive:<id> --suggests--> tactic:<slug>`` edge in the project overlay. Such a
tactic must reach action context only through that edge, never as a closure root
of its own. :func:`reach_only_tactic_ids` names those tactics;
:func:`append_synthesized_tactic_activations` appends the tactics a synthesis run
created to an explicit ``activated_tactics`` list (an absent key stays absent).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from charter.offering.drg.loader import DRGLoadError, has_graph_files, load_graph_or_dir
from charter.offering.drg.models import NodeKind, Relation
from kernel.charter_pack_paths import project_pack_root

__all__ = ["append_synthesized_tactic_activations", "manifest_tactic_slugs", "reach_only_tactic_ids"]

_ACTIVATED_TACTICS_KEY = "activated_tactics"


def reach_only_tactic_ids(repo_root: Path) -> frozenset[str]:
    """Bare tactic ids targeted by an overlay ``directive:* --suggests-->`` edge.

    Reads the project overlay only (not the activation-filtered graph), so the set
    does not change when the owning directive is deactivated. An absent or
    unloadable overlay yields the empty set (matches ``project_degrade``).
    """
    pack_dir = project_pack_root(repo_root)
    try:
        if not pack_dir.is_dir() or not has_graph_files(pack_dir):
            return frozenset()
        graph = load_graph_or_dir(pack_dir)
    except DRGLoadError:
        return frozenset()
    tactic_urns = {node.urn for node in graph.nodes if node.kind is NodeKind.TACTIC}
    return frozenset(
        edge.target.split(":", 1)[1]
        for edge in graph.edges
        if edge.relation is Relation.SUGGESTS and edge.source.startswith("directive:") and edge.target in tactic_urns
    )


def append_synthesized_tactic_activations(repo_root: Path, tactic_slugs: Iterable[str]) -> list[str]:
    """Append *tactic_slugs* to an explicit ``activated_tactics`` list; return warnings.

    An absent key is left absent (C-001). The synthesis manifest's bundle hash is
    restamped after the write.
    """
    from charter.activation.activation_engine import promote_activations  # noqa: PLC0415
    from charter.activation.bundle_restamp import restamp_bundle_hash  # noqa: PLC0415
    from charter.activation.pack_manager import resolve_activation_write_target  # noqa: PLC0415

    slugs = list(dict.fromkeys(tactic_slugs))
    if not slugs:
        return []
    target_path, data, save = resolve_activation_write_target(repo_root)
    if data.get(_ACTIVATED_TACTICS_KEY) is None:
        return []
    outcome = promote_activations(
        {_ACTIVATED_TACTICS_KEY: slugs},
        config_path=target_path,
        config_data=data,
        save=save,
        effective_sets={},
    )
    restamp_bundle_hash(repo_root)
    return [warning for plan in outcome.committed for warning in plan.warnings]


def manifest_tactic_slugs(repo_root: Path) -> list[str]:
    """Tactic slugs recorded in the synthesis manifest (empty when there is none)."""
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml  # noqa: PLC0415

    manifest_path = repo_root / MANIFEST_PATH
    if not manifest_path.is_file():
        return []
    return [entry.slug for entry in load_yaml(manifest_path).artifacts if entry.kind == "tactic"]
